#!/usr/bin/env python3
"""Phase 8.0 D8.3: run scripts/p8_toggle_test.c under callgrind --toggle-collect and report, per compiler,
how much Ir is collected outside the toggled function. Usage:
python3 -I scripts/p8_toggle_test.py 2>&1 | tee logs/p8/p8_toggle_test.log"""
import pathlib, re, subprocess, sys

B = pathlib.Path("build/p8"); B.mkdir(parents=True, exist_ok=True)


def sh(cmd):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True)


def top(out):
    rows, on = [], False
    for line in sh(["callgrind_annotate", "--threshold=100", "--auto=no", out]).stdout.splitlines():
        if "file:function" in line:
            on = True
        elif on and re.match(r"\s*[0-9,]+ \(", line):
            rows.append(re.sub(r"\s*\[.*\]$", "", line.strip()))
    return rows


print("# toggle test", sh(["date", "-Is"]).stdout.strip(), sh(["valgrind", "--version"]).stdout.strip())
for cc, opt in (("gcc", "-O2"), ("gcc", "-O0"), ("clang", "-O2")):
    exe = B / ("toggle_%s%s" % (cc, opt))
    r = sh([cc, opt, "-g", "-std=gnu11", "-o", exe, "scripts/p8_toggle_test.c"])
    print("\n$ %s %s -g -std=gnu11 -o %s scripts/p8_toggle_test.c -> rc=%d" % (cc, opt, exe, r.returncode))
    if r.returncode:
        print(r.stderr[:400]); continue
    for mode, fn in ((0, "f_leaf"), (1, "f_frame")):
        print("-- %s %s, evaluator = %s; g() is ~5000 Ir per call and must not be collected" % (cc, opt, fn))
        print("calls  collected Ir   Ir per extra call   functions with Ir (top)")
        prev = None
        for calls in (0, 1, 2, 5, 20):
            out = B / ("tt_%s%s_%d_%d.out" % (cc, opt, mode, calls))
            v = sh(["valgrind", "--tool=callgrind", "--toggle-collect=" + fn, "--callgrind-out-file=" + str(out),
                    exe, mode, calls])
            if v.returncode:
                sys.exit("valgrind failed " + v.stderr[-300:])
            ir = int([l for l in out.read_text().splitlines() if l.startswith("summary:")][0].split()[1])
            d = "" if prev is None else "%.1f" % ((ir - prev[1]) / (calls - prev[0]))
            names = "; ".join(re.sub(r"^([0-9,]+) \(\s*([0-9.]+%)\)\s+\S*?:?", r"\1 \2 ", t)[:50] for t in top(out)[:3])
            print("%-6d %-14d %-19s %s" % (calls, ir, d, names))
            prev = (calls, ir)
