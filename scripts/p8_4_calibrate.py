#!/usr/bin/env python3
"""Phase 8.4 calibration probe (docs/phase8_4_design.md section 7; excluded from analysis). No traffic, no root needed. For each noise
type, noised core set and nominal duty it starts the controller (scripts/p8_4_noise.py under taskset), waits for NOISE_READY, lets it settle
1 s, measures per-CPU busy time from /proc/stat over 10 s, stops it and records the result. Output (deleted first, checked after):
logs/p8/p8_4/calib/calib.jsonl, one JSON object per window. Refuses to start if the folder is non-empty or the memory gate fails.
Usage (user, any terminal tab):  python3 -I scripts/p8_4_calibrate.py 2>&1 | tee logs/p8/p8_4/p8_4_calibrate_console.log
About 11 minutes; leave the machine alone until the line FINISHED.
Version 2 (amendment A2): the injected rate of a window is the CPU time the stress-ng workers themselves consumed (utime+stime from /proc/<pid>/stat at the
start and end of the window) divided by the window length, so it does not depend on the ambient noise of the machine; one window per cell."""
import json, os, pathlib, signal, subprocess, sys, time

os.chdir(pathlib.Path(__file__).resolve().parent.parent)
OUT = pathlib.Path(os.environ.get("P8_4_CALIB_DIR", "logs/p8/p8_4/calib2"))
OUT.mkdir(parents=True, exist_ok=True)
if any(OUT.iterdir()):
    sys.exit("ABORT: %s is not empty; refusing to overwrite (move it away on purpose)" % OUT)
CLK = os.sysconf("SC_CLK_TCK")
GRID = [1, 2, 3, 4, 5, 7.5, 10, 15, 20, 30, 40]
WINDOW = 10.0


def meminfo():
    d = {}
    for l in open("/proc/meminfo"):
        k, v = l.split(":")
        d[k] = int(v.split()[0]) // 1024
    return d


m = meminfo()
swap_used = m["SwapTotal"] - m["SwapFree"]
print("memory gate: swap in use %d MB (limit 2000), MemAvailable %d MB (minimum 1500)" % (swap_used, m["MemAvailable"]))
if swap_used > 2000 or m["MemAvailable"] < 1500:
    sys.exit("ABORT: memory gate failed")


def snap():
    cpu = {}
    for line in open("/proc/stat"):
        if line.startswith("cpu") and line[3].isdigit():
            f = line.split()
            v = [int(x) for x in f[1:9]]
            cpu[int(f[0][3:])] = v[0] + v[1] + v[2] + v[5] + v[6] + v[7]
    return time.time(), cpu


def wticks(pids):
    out = 0
    for p in pids:
        try:
            f = open("/proc/%d/stat" % p).read().rsplit(")", 1)[1].split()
            out += int(f[11]) + int(f[12])
        except (OSError, ValueError, IndexError):
            pass
    return out


def window(kind, cores, duty, extra=()):
    cs = ",".join(map(str, cores))
    p = subprocess.Popen(["taskset", "-c", cs, "python3", "-I", "scripts/p8_4_noise.py", kind, cs, str(duty)] + list(extra),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ready = None
    t_end = time.time() + 30
    while time.time() < t_end:
        line = p.stdout.readline()
        if line.startswith("NOISE_READY"):
            ready = json.loads(line.split(" ", 1)[1])
            break
        if line.startswith("NOISE_ABORT") or (line == "" and p.poll() is not None):
            sys.exit("FATAL: controller: %s %s" % (line.strip(), p.stderr.read()[-400:]))
    if ready is None:
        p.kill()
        sys.exit("FATAL: controller did not become ready")
    time.sleep(1.0)
    pids = [w for _, w in ready["workers"]]
    k0 = wticks(pids)
    t0, a = snap()
    mem_a = meminfo()
    time.sleep(WINDOW)
    t1, b = snap()
    k1 = wticks(pids)
    mem_b = meminfo()
    p.send_signal(signal.SIGTERM)
    out, err = p.communicate(timeout=30)
    stop = [json.loads(l.split(" ", 1)[1]) for l in out.splitlines() if l.startswith("NOISE_STOP")]
    w = t1 - t0
    rec = {"kind": kind, "cores": cores, "duty": duty, "window_s": w, "busy": {str(c): (b[c] - a[c]) / CLK / w for c in a},
           "injected": (k1 - k0) / CLK / (t1 - t0), "ready": ready, "stop": stop[0] if stop else None, "stderr_tail": err[-300:], "MemAvailable_MB": [mem_a["MemAvailable"], mem_b["MemAvailable"]],
           "SwapFree_MB": [mem_a["SwapFree"], mem_b["SwapFree"]]}
    with open(OUT / "calib.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print("%-5s cores %-4s duty %-5s injected %.4f CPU-s/s; busy per CPU: %s  stop=%s" % (kind, cs, duty, rec["injected"], " ".join("%.3f" % rec["busy"][str(c)] for c in sorted(a)), "ok" if stop else "MISSING"), flush=True)


N_WIN = 3 + 2 * (len(GRID) * 2) + 4
print("=== calibration probe (version 2) start %s; do not touch the machine until FINISHED (about 11 minutes)" % time.strftime("%H:%M:%S"))
time.sleep(20)                                        # settle
for _ in range(3):
    window("cpu", [0, 1], 0)                          # baseline: workers present and stopped (information only; the injected rate does not use it)
for kind in ("cpu", "cache"):
    for d in GRID:
        window(kind, [0, 1], d)
    for d in GRID:
        window(kind, [0], d)
for core in (2, 3):
    for d in (5, 10):
        window("cpu", [core], d)
n = sum(1 for _ in open(OUT / "calib.jsonl"))
if n != N_WIN:
    sys.exit("FATAL: %d windows written, expected %d" % (n, N_WIN))
print("windows written: %d; MemAvailable now %d MB" % (n, meminfo()["MemAvailable"]))
print("=== FINISHED %s ===" % time.strftime("%H:%M:%S"))
