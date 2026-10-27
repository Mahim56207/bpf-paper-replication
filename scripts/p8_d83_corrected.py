#!/usr/bin/env python3
"""Phase 8.0 D8.3 diagnostic (informational, NOT a replacement of the frozen M2 definition): recompute the primary
pairing (mix M0, BPF-opt vs CSPF sc-fused) from the callgrind outputs of the VM run, counting only the Ir that
callgrind_annotate attributes to the evaluator functions (c1_eval_bpf / c1_eval_sm, all recursion-level variants),
i.e. M2 with the leaked harness Ir (main loop, libc printf at exit) removed. Reads build/p6c/cg/*.out only.
Usage: python3 -I scripts/p8_d83_corrected.py | tee logs/p8/p8_d83_corrected_m2.md"""
import pathlib, re, statistics, subprocess

CG = pathlib.Path("build/p6c/cg")
CHUNKS, FRAMES = 10, 1000


def eval_ir(path, fn):
    """(program total Ir, Ir attributed to fn in any recursion-level variant) from callgrind_annotate."""
    out = subprocess.run(["callgrind_annotate", "--threshold=100", "--auto=no", str(path)],
                         capture_output=True, text=True).stdout
    total = ev = 0
    for line in out.splitlines():
        m = re.match(r"\s*([0-9,]+) \(\s*[0-9.]+%\)\s+(\S+)", line)
        if not m:
            continue
        v = int(m.group(1).replace(",", ""))
        if m.group(2) == "PROGRAM":
            total = v
        elif re.search(r":" + fn + r"('\d+)?$", m.group(2)):
            ev += v
    return total, ev


def per_chunk(mix, f, prog, fn):
    evs, totals = [], []
    for c in range(CHUNKS):
        tot, ev = eval_ir(CG / ("%s_%s_%s_%d.out" % (mix, f, prog, c)), fn)
        evs.append(ev / FRAMES)
        totals.append(tot / FRAMES)
    return evs, totals


print("# D8.3 diagnostic: M2 with only the evaluator functions counted (aarch64 VM, mix M0, BPF-opt vs CSPF sc-fused)\n")
print("T = project definition (all Ir collected under --toggle-collect); E = Ir attributed to c1_eval_* only. Means over %d chunks of %d frames; R = mean(CSPF)/mean(BPF).\n" % (CHUNKS, FRAMES))
print("| filter | T BPF | T CSPF | T R | E BPF | E CSPF | E R | leaked share BPF | leaked share CSPF |")
print("|---|---|---|---|---|---|---|---|---|")
for f in ("F1", "F2", "F3", "F4"):
    eb, tb = per_chunk("M0", f, "bpf-opt", "c1_eval_bpf")
    ec, tc = per_chunk("M0", f, "sm-sc-fused", "c1_eval_sm")
    mb, mc, tmb, tmc = map(statistics.mean, (eb, ec, tb, tc))
    print("| %s | %.4g | %.4g | %.3g | %.4g | %.4g | %.3g | %.1f%% | %.1f%% |" %
          (f, tmb, tmc, tmc / tmb, mb, mc, mc / mb, 100 * (tmb - mb) / tmb, 100 * (tmc - mc) / tmc))
