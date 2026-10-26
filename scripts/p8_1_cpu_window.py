#!/usr/bin/env python3
"""Phase 8.1: per-CPU busy rate over a window, no harness attached, from /proc/stat. Same definition of busy as
scripts/summarize.py busy(): user + nice + system + irq + softirq + steal (iowait and idle excluded), divided by
CLK_TCK, per second of wall time. Usage: python3 -I scripts/p8_1_cpu_window.py <seconds>"""
import os, sys, time

SECONDS = float(sys.argv[1])
CLK = os.sysconf("SC_CLK_TCK")


def snap():
    cpu = {}
    for line in open("/proc/stat"):
        if line.startswith("cpu"):
            f = line.split()
            v = [int(x) for x in f[1:9]]
            cpu[f[0]] = v[0] + v[1] + v[2] + v[5] + v[6] + v[7]
    return time.time(), cpu


t0, a = snap()
time.sleep(SECONDS)
t1, b = snap()
w = t1 - t0
print("window %.3f s, CLK_TCK %d" % (w, CLK))
for c in sorted(a, key=lambda x: (x != "cpu", int(x[3:]) if x != "cpu" else -1)):
    print("%-5s busy %.4f CPU-s/s" % (c, (b[c] - a[c]) / CLK / w))
print("canary cores {0,1}: %.4f CPU-s/s; core {0}: %.4f CPU-s/s" % ((b["cpu0"] - a["cpu0"] + b["cpu1"] - a["cpu1"]) / CLK / w, (b["cpu0"] - a["cpu0"]) / CLK / w))
