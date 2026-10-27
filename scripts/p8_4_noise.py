#!/usr/bin/env python3
"""Phase 8.4 noise controller (docs/phase8_4_design.md section 3). Starts stress-ng workers pinned to cores, then duty-cycles them with
SIGSTOP/SIGCONT (period 100 ms) so that the intensity is controlled; runs until SIGTERM.
Usage: p8_4_noise.py <cpu|cache|vm> <core[,core...]> <duty percent per worker> [--vm-mb N]
  cpu   one `stress-ng --cpu 1` per core        cache  one `stress-ng --cache 1 --cache-enable-all --cache-no-affinity` per core
  vm    ONE `stress-ng --vm 1 --vm-bytes <N>M --vm-hang 3600` on the first core (global memory pressure, no CPU after the allocation);
        N defaults to MemAvailable - 1000 MB capped at 2048 MB; exits 3 if that is below 200 MB, 4 if MemAvailable falls below 800 MB.
Prints NOISE_READY <json> when the workers run (and, for duty < 100, are in the duty cycle) and NOISE_STOP <json> on exit.
Run it under `taskset -c <cores>` so that its own (tiny) CPU use lands on the noised cores."""
import json, os, signal, subprocess, sys, time

PERIOD = 0.1


def meminfo():
    d = {}
    for l in open("/proc/meminfo"):
        k, v = l.split(":")
        d[k] = int(v.split()[0]) // 1024
    return d


def cpu_ticks(pid):
    """utime + stime of a process (all its threads), in clock ticks."""
    try:
        f = open("/proc/%d/stat" % pid).read().rsplit(")", 1)[1].split()
        return int(f[11]) + int(f[12])
    except (OSError, ValueError, IndexError):
        return 0


def children(pid):
    out = []
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                stat = open("/proc/%s/stat" % p).read()
                if int(stat.rsplit(")", 1)[1].split()[1]) == pid:
                    out.append(int(p))
            except (OSError, ValueError, IndexError):
                pass
    return out


kind, cores, duty = sys.argv[1], [int(c) for c in sys.argv[2].split(",")], float(sys.argv[3])
vm_mb = int(sys.argv[sys.argv.index("--vm-mb") + 1]) if "--vm-mb" in sys.argv else None
procs, workers = [], []
stop = False


def on_term(*_):
    global stop
    stop = True


signal.signal(signal.SIGTERM, on_term)
signal.signal(signal.SIGINT, on_term)
log = sys.stderr                                  # stress-ng messages go to the controller's stderr (the harness keeps it in the run log section "noise")
info = {"kind": kind, "cores": cores, "duty": duty}
mem0 = meminfo()
if kind == "vm":
    if vm_mb is None:
        vm_mb = min(2048, mem0["MemAvailable"] - 1000)
    if vm_mb < 200:
        print("NOISE_ABORT MemAvailable %d MB leaves less than 200 MB to hold" % mem0["MemAvailable"], flush=True)
        sys.exit(3)
    info["vm_mb"] = vm_mb
    cmds = [(cores[0], ["stress-ng", "--vm", "1", "--vm-bytes", "%dM" % vm_mb, "--vm-hang", "3600", "--timeout", "7200"])]
else:
    stress = ["--cpu", "1"] if kind == "cpu" else ["--cache", "1", "--cache-enable-all", "--cache-no-affinity"]
    cmds = [(c, ["stress-ng"] + stress + ["--timeout", "7200"]) for c in cores]
for core, cmd in cmds:
    procs.append((core, subprocess.Popen(["taskset", "-c", str(core)] + cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)))
deadline = time.time() + 20
while time.time() < deadline and not stop:
    workers = []
    for core, p in procs:
        kids = children(p.pid)
        workers += [(core, k) for k in kids]
    if len(workers) >= len(procs):
        break
    time.sleep(0.1)
if len(workers) < len(procs):
    print("NOISE_ABORT stress-ng workers did not start (%d of %d)" % (len(workers), len(procs)), flush=True)
    for _, p in procs:
        os.killpg(p.pid, signal.SIGKILL)
    sys.exit(2)
bad = [(c, w, sorted(os.sched_getaffinity(w))) for c, w in workers if os.sched_getaffinity(w) != {c}]
if bad:
    print("NOISE_ABORT worker affinity differs from the pinned core: %s" % bad, flush=True)
    for _, p in procs:
        os.killpg(p.pid, signal.SIGKILL)
    sys.exit(2)
info["workers"] = workers
if kind == "vm":
    time.sleep(3.0)                                  # let the worker touch its memory
    mem1 = meminfo()
    info["MemAvailable_before_MB"], info["MemAvailable_after_MB"] = mem0["MemAvailable"], mem1["MemAvailable"]
    info["SwapFree_after_MB"] = mem1["SwapFree"]
    if mem1["MemAvailable"] < 800:
        print("NOISE_ABORT MemAvailable fell to %d MB (< 800)" % mem1["MemAvailable"], flush=True)
        for _, p in procs:
            os.killpg(p.pid, signal.SIGKILL)
        sys.exit(4)
elif duty < 100:
    for _, w in workers:
        os.kill(w, signal.SIGSTOP)                   # start stopped: level 0 stays stopped, other levels enter the cycle below
ticks0 = {w: cpu_ticks(w) for _, w in workers}
print("NOISE_READY " + json.dumps(info), flush=True)
cycles = 0
t_on = 0.0
t0 = time.time()
try:
    if kind == "vm" or duty >= 100:
        while not stop:
            time.sleep(0.2)
    elif duty <= 0:
        while not stop:
            time.sleep(0.2)
    else:
        on = PERIOD * duty / 100.0
        while not stop:
            for _, w in workers:
                os.kill(w, signal.SIGCONT)
            time.sleep(on)
            for _, w in workers:
                os.kill(w, signal.SIGSTOP)
            t_on += on
            cycles += 1
            time.sleep(PERIOD - on)
finally:
    clk = os.sysconf("SC_CLK_TCK")
    info["worker_cpu_seconds"] = round(sum(cpu_ticks(w) - ticks0.get(w, 0) for _, w in workers) / clk, 3)   # CPU time the workers consumed since READY
    for _, p in procs:
        try:
            os.killpg(p.pid, signal.SIGCONT)
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for _, p in procs:
        p.wait()
    info.update({"cycles": cycles, "nominal_on_seconds_per_worker": round(t_on, 3), "seconds": round(time.time() - t0, 3)})
    print("NOISE_STOP " + json.dumps(info), flush=True)
