#!/usr/bin/env python3
"""Phase 10 helper: canary rates from /proc/stat snapshots (docs/phase10_design.md section 8).
  p10_canary.py snap <file>                      write one snapshot ("cpuN busy_ticks" per CPU, busy = user+nice+system+irq+softirq+steal) and the monotonic time
  p10_canary.py rate <before> <after> <cores,..> print the summed busy CPU-s per second over the cores between two snapshots
  p10_canary.py check <before> <after> <cores,..> <limit>   print the rate and exit 1 if it exceeds the limit
  p10_canary.py pre <outdir> <block> <cores,..> <r1> <r2> <r3>   pre-flight verdict: write <outdir>/preflight.json (limit = 1.2 x the largest idle rate); exit 1 if the
                                                 largest idle rate exceeds 0.0826 x (number of cores)/2 (the Phase 6 idle limit 1.2 x 0.0689 for two cores)
  p10_canary.py gate                             memory gate: swap in use <= 2000 MB and MemAvailable >= 1500 MB (reads /proc/meminfo), exit 1 otherwise
"""
import os, sys, time

CLK = os.sysconf("SC_CLK_TCK")


def snap(path):
    lines = [f"time {time.monotonic():.6f}"]
    for l in open("/proc/stat"):
        if l.startswith("cpu") and l[3].isdigit():
            f = l.split()
            v = [int(x) for x in f[1:9]]
            lines.append(f"{f[0]} {v[0] + v[1] + v[2] + v[5] + v[6] + v[7]}")
    open(path, "w").write("\n".join(lines) + "\n")


def load(path):
    d = {}
    for l in open(path):
        k, v = l.split()
        d[k] = float(v)
    return d


def rate(b, a, cores):
    B, A = load(b), load(a)
    wall = A["time"] - B["time"]
    busy = sum(A[f"cpu{c}"] - B[f"cpu{c}"] for c in cores) / CLK
    return busy / wall, wall


def gate():
    m = {}
    for l in open("/proc/meminfo"):
        k, v = l.split(":")
        m[k] = int(v.split()[0]) // 1024
    swap = m["SwapTotal"] - m["SwapFree"]
    print(f"memory gate: swap in use {swap} MB (limit 2000), MemAvailable {m['MemAvailable']} MB (minimum 1500)")
    return 0 if swap <= 2000 and m["MemAvailable"] >= 1500 else 1


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "snap":
        snap(sys.argv[2])
    elif mode in ("rate", "check"):
        cores = [int(x) for x in sys.argv[4].split(",")]
        r, wall = rate(sys.argv[2], sys.argv[3], cores)
        print(f"{r:.6f} {wall:.3f}")
        if mode == "check" and r > float(sys.argv[5]):
            sys.exit(1)
    elif mode == "pre":
        import json
        out, block, cores = sys.argv[2], sys.argv[3], [int(x) for x in sys.argv[4].split(",")]
        rates = [float(x) for x in sys.argv[5:8]]
        idle_limit = 0.0826 * len(cores) / 2
        d = {"block": block, "cores": cores, "idle_rates": rates, "canary_max": max(rates), "limit": 1.2 * max(rates), "idle_limit": idle_limit,
             "passed": max(rates) <= idle_limit}
        open(os.path.join(out, "preflight.json"), "w").write(json.dumps(d, indent=1) + "\n")
        print(json.dumps(d))
        sys.exit(0 if d["passed"] else 1)
    elif mode == "gate":
        sys.exit(gate())
    else:
        sys.exit("usage: see the module docstring")
