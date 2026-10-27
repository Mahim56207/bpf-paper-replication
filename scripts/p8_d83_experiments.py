#!/usr/bin/env python3
"""Phase 8.0, D8.3: test why the callgrind attribution check fails on the aarch64 VM.
New file; does not edit any existing script or source. Reads build/p6c/ (built by scripts/c1_build.sh),
writes build/p8/ (untracked) and prints a log: python3 -I scripts/p8_d83_experiments.py 2>&1 | tee logs/p8/p8_d83_experiments.log

Method: for each (machine, program) and each frame count N, measure Ir three ways and compare.
  T   = the project's way: --toggle-collect=<evaluator>, 'summary:' line of the callgrind output.
  T0  = T plus --collect-atstart=no.
  INC = ground truth independent of toggling: no toggle, whole-program collection, inclusive Ir of the
        evaluator function from callgrind_annotate --inclusive=yes.
  BASE= no toggle, N=0 frames (process start-up, trace loading, program loading, exit).
H1 (collection stays on after the first return) predicts T(N) - INC(N) grows linearly with N (about the
per-frame loop cost). A start-up/exit cost that does not depend on N predicts a constant offset instead.
"""
import os, pathlib, re, subprocess, sys

R = pathlib.Path(".").resolve()
B6, B8 = R / "build/p6c", R / "build/p8"
B8.mkdir(parents=True, exist_ok=True)
PCAP = B6 / "traces/mix_M0.pcap"
CF = ["-O2", "-g", "-Wall", "-Wextra", "-std=gnu11", "-Isrc"]
NS = [0, 1, 2, 10, 100, 1000]
CASES = [("bpf", "F1 bpf-opt", B6 / "oracle/M0_F1.opt.bpf", "c1_eval_bpf"),
         ("sm", "F1 sm-sc-fused", R / "src/c1_progs/F1_sc_any.sm", "c1_eval_sm"),
         ("sm", "F4 sm-sc-fused", R / "src/c1_progs/F4_sc_any.sm", "c1_eval_sm")]


def sh(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def summary_ir(out):
    for line in out.read_text().splitlines():
        if line.startswith("summary:"):
            return int(line.split()[1])


def cg(exe, machine, prog, n, fn, tag, toggle=True, atstart_no=False):
    out = B8 / ("cg_%s_%s_%d.out" % (tag, pathlib.Path(prog).stem, n))
    cmd = ["valgrind", "--tool=callgrind", "--callgrind-out-file=" + str(out)]
    if toggle:
        cmd.append("--toggle-collect=" + fn)
    if atstart_no:
        cmd.append("--collect-atstart=no")
    cmd += [exe, "--machine", machine, "--prog", prog, "--pcap", PCAP, "--first", 0, "--count", n]
    r = sh(cmd)
    if r.returncode:
        sys.exit("valgrind failed: %s\n%s" % (" ".join(map(str, cmd)), r.stderr[-600:]))
    return out


def inclusive(out, fn):
    r = sh(["callgrind_annotate", "--inclusive=yes", "--threshold=100", "--auto=no", out])
    best = 0
    for line in r.stdout.splitlines():
        m = re.match(r"\s*([0-9,]+) \(\s*[0-9.]+%\)\s+\S*:?" + fn + r"(\S*)\s", line + " ")
        if m and "'" not in m.group(2):
            best = max(best, int(m.group(1).replace(",", "")))
        elif m:
            best = max(best, int(m.group(1).replace(",", "")))
    return best


def functions(out, top=8):
    r = sh(["callgrind_annotate", "--threshold=100", "--auto=no", out])
    rows, on = [], False
    for line in r.stdout.splitlines():
        if "file:function" in line:
            on = True
            continue
        if on and re.match(r"\s*[0-9,]+ \(", line):
            rows.append(re.sub(r"\s*\[.*\]$", "", line.strip()))
    return rows[:top]


def build_variants():
    v = {"gcc15-O2 (as in c1_build.sh)": B6 / "c1_interp_ir"}
    clang = B8 / "c1_interp_ir_clang"
    r = sh(["clang"] + CF + ["-o", clang, "src/c1_interp.c"])
    print("$ clang %s -o %s src/c1_interp.c  -> rc=%d %s" % (" ".join(CF), clang, r.returncode, r.stderr.strip()[:300]))
    if r.returncode == 0:
        v["clang20-O2"] = clang
    g1 = B8 / "c1_interp_ir_gccO0"
    r = sh(["gcc"] + [c for c in CF if c != "-O2"] + ["-O0", "-o", g1, "src/c1_interp.c"])
    print("$ gcc -O0 ... -o %s  -> rc=%d" % (g1, r.returncode))
    if r.returncode == 0:
        v["gcc15-O0"] = g1
    return v


print("# D8.3 experiments", sh(["date", "-Is"]).stdout.strip())
for c in ("valgrind --version", "gcc --version", "clang --version", "uname -srm"):
    print("$", c, "->", sh(c.split()).stdout.splitlines()[0])
print("objdump check: are c1_eval_* separate non-inlined functions in the gcc build?")
print(sh(["nm", "-C", B6 / "c1_interp_ir"]).stdout.count("c1_eval"), "c1_eval symbols;",
      " | ".join(l for l in sh(["nm", "-C", B6 / "c1_interp_ir"]).stdout.splitlines() if "c1_eval" in l))

variants = build_variants()
print()
for vname, exe in variants.items():
    for machine, label, prog, fn in CASES:
        print("=== variant %s | %s | evaluator %s" % (vname, label, fn))
        tag = re.sub(r"\W", "", vname) + machine + pathlib.Path(prog).stem
        base = summary_ir(cg(exe, machine, prog, 0, fn, tag + "base", toggle=False))
        print("N     T=toggle   T0=toggle+atstart=no   INC(true eval Ir)   T-INC   (T-INC)/N   T0-INC")
        for n in NS:
            if vname != "gcc15-O2 (as in c1_build.sh)" and n not in (1, 1000):
                continue
            t = summary_ir(cg(exe, machine, prog, n, fn, tag + "T"))
            t0 = summary_ir(cg(exe, machine, prog, n, fn, tag + "T0", atstart_no=True))
            full = cg(exe, machine, prog, n, fn, tag + "INC", toggle=False)
            inc = inclusive(full, fn)
            print("%-5d %-10d %-22s %-19d %-7d %-11s %d" % (n, t, t0, inc, t - inc, ("%.2f" % ((t - inc) / n)) if n else "-", (t0 or 0) - inc))
        print("(BASE: whole program at N=0 = %d Ir)" % base)
        top = cg(exe, machine, prog, 1000, fn, tag + "TOP")
        print("top functions of the project-style run at N=1000:")
        for l in functions(top):
            print("   ", l)
        print()
