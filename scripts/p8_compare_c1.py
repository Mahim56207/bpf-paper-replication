#!/usr/bin/env python3
"""Phase 8.0: compare the C1 primary-pairing ratios of the x86_64 container run (committed
results/c1_summary.md, copied to logs/p8/x86_baseline/ before the VM run) with the aarch64 VM run
(results/c1_summary.md after scripts/phase6c_verify.sh). Reads the two files only; prints every number
by parsing them. Usage: python3 -I scripts/p8_compare_c1.py > logs/p8/p8_c1_arm_vs_x86.md"""
import re, sys

X86 = "logs/p8/x86_baseline/c1_summary.md"
import os
ARM = os.environ.get("P8_ARM_SUMMARY", "results/c1_summary.md")
X86V = "logs/p8/x86_baseline/c1_verdict.md"
ARMV = os.environ.get("P8_ARM_VERDICT", "results/c1_verdict.md")


def primary(path):
    """Rows of section 3 first table: filter -> dict of floats (first number of each cell)."""
    out = {}
    for line in open(path):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 10 and re.fullmatch(r"F[1-4]", cells[0]):
            num = lambda s: float(re.match(r"[-0-9.e+]+", s).group(0))
            out[cells[0]] = dict(m1_bpf=num(cells[1]), m1_cspf=num(cells[2]), m1_R=num(cells[3]),
                                 m2_bpf=num(cells[4]), m2_cspf=num(cells[5]), m2_R=num(cells[6]),
                                 paper_R=num(cells[9]))
    return out


def verdict_lines(path):
    return [l.rstrip() for l in open(path) if re.search(r"verdict|C1[abc]", l, re.I)]


x, a = primary(X86), primary(ARM)
if sorted(x) != ["F1", "F2", "F3", "F4"] or sorted(a) != sorted(x):
    sys.exit("could not parse four primary rows from both summaries")

print("# Phase 8.0: C1 on the aarch64 VM vs the x86_64 container (computed by scripts/p8_compare_c1.py)\n")
print("Sources: `%s` (x86_64 container, Phase 6c) and `%s` (aarch64 VM, this run). Primary pairing, mix M0, BPF-opt vs CSPF sc-fused. Rel. diff = (VM - x86) / x86.\n" % (X86, ARM))
print("| filter | metric | x86_64 | aarch64 VM | rel. diff |")
print("|---|---|---|---|---|")
for f in ("F1", "F2", "F3", "F4"):
    for k, name in (("m1_bpf", "M1 BPF"), ("m1_cspf", "M1 CSPF"), ("m1_R", "M1 R"),
                    ("m2_bpf", "M2 BPF"), ("m2_cspf", "M2 CSPF"), ("m2_R", "M2 R")):
        xv, av = x[f][k], a[f][k]
        print("| %s | %s | %.4g | %.4g | %+.1f%% |" % (f, name, xv, av, 100.0 * (av - xv) / xv))
print("\nPaper ratios (Fig. 8 labels, from the summaries): " + ", ".join("%s %.4g" % (f, x[f]["paper_R"]) for f in sorted(x)) + ".\n")
print("M1 identical on both machines for all four filters: %s" %
      all(x[f][k] == a[f][k] for f in x for k in ("m1_bpf", "m1_cspf", "m1_R")))
print("M2 R ordering F1<F2<F3<F4: x86_64 %s, aarch64 VM %s\n" %
      (x["F1"]["m2_R"] < x["F2"]["m2_R"] < x["F3"]["m2_R"] < x["F4"]["m2_R"],
       a["F1"]["m2_R"] < a["F2"]["m2_R"] < a["F3"]["m2_R"] < a["F4"]["m2_R"]))
print("Verdict lines, x86_64 (`%s`):\n" % X86V)
for l in verdict_lines(X86V):
    print("    " + l)
print("\nVerdict lines, aarch64 VM (`%s`):\n" % ARMV)
for l in verdict_lines(ARMV):
    print("    " + l)
