#!/usr/bin/env python3
"""Phase 8.0: x86_64 container versus aarch64 VM, primary pairing and full robustness grid, M2 numbers.
Reads only the saved M2 tables (logs/p6c/p6c_m2.tsv = x86_64 Phase 6c run; logs/p8/a3/p6c/p6c_m2.tsv = VM run
with amendment A3) and applies the UNCHANGED functions ratio(), evaluate() and verdict() of scripts/c1_summarize.py
(imported, not copied). x86_64 has no Ir_eval column, so E = T there (c1_summarize.load_m2). Three data sets:
  x86_64 (E = T), VM-E (A3 evaluator-only, the M2 of the A3 summary), VM-T (toggle total, the Phase 6c definition).
Usage: python3 -I scripts/p8_compare_grid.py > logs/p8/p8_c1_x86_vs_vm_grid.md"""
import importlib.util, os, pathlib, statistics, sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
SETS = {"x86": "logs/p6c", "vm": "logs/p8/a3/p6c"}


def load(name, logdir):
    os.environ["C1_LOG"] = logdir
    spec = importlib.util.spec_from_file_location("c1s_" + name, ROOT / "scripts" / "c1_summarize.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mods = {k: load(k, v) for k, v in SETS.items()}
c = mods["x86"]
paper = c.paper_fig8()
x_e, x_t = mods["x86"].load_m2()
v_e, v_t = mods["vm"].load_m2()
assert x_e == x_t, "x86_64 E != T"
data = {"x86_64": x_e, "VM-E (A3 M2)": v_e, "VM-T (toggle total)": v_t}
ev = {k: c.evaluate(d, paper) for k, d in data.items()}
fmt = c.fmt
F, MIXES, BPFS, SMS, PRIMARY = c.FILTERS, c.MIXES, c.BPFS, c.SMS, c.PRIMARY

print("# Phase 8.0: x86_64 container vs aarch64 VM, M2 (host instructions per packet), computed by scripts/p8_compare_grid.py\n")
print("Inputs: `logs/p6c/p6c_m2.tsv` (x86_64, Phase 6c; no `Ir_eval` column, so E = T), `logs/p8/a3/p6c/p6c_m2.tsv` (VM, columns `Ir` = T and `Ir_eval` = E). Functions `ratio`, `evaluate`, `verdict` imported unchanged from `scripts/c1_summarize.py`; paper labels from `CLAIMS.md`. R = mean(CSPF)/mean(BPF) over the ten 1000-frame chunks, 95% t-interval of the ten per-chunk ratios.\n")

print("## 1. Primary pairing (mix M0, BPF-opt vs CSPF sc-fused)\n")
print("| filter | paper R | x86_64 BPF | x86_64 CSPF | x86_64 R [95%] | VM-E BPF | VM-E CSPF | VM-E R [95%] | VM-T R [95%] |")
print("|---|---|---|---|---|---|---|---|---|")
cell = lambda e, f: "%s [%s, %s]" % tuple(fmt(x) for x in e["cells"][PRIMARY][f])
for f in F:
    kb, ks = ("M0", f, "bpf-opt"), ("M0", f, "sm-sc-fused")
    print("| %s | %.1f | %s | %s | %s | %s | %s | %s | %s |" % (
        f, paper[f][2], fmt(statistics.fmean(x_e[kb])), fmt(statistics.fmean(x_e[ks])), cell(ev["x86_64"], f),
        fmt(statistics.fmean(v_e[kb])), fmt(statistics.fmean(v_e[ks])), cell(ev["VM-E (A3 M2)"], f),
        cell(ev["VM-T (toggle total)"], f)))

print("\n## 2. Outcomes (design section 7, rules unchanged)\n")
print("| data set | C1a primary | C1a grid cells passing | C1b (R order, primary) | C1c (largest R in [%.2f, %.1f]) | largest R | verdict |" % ev["x86_64"]["band"])
print("|---|---|---|---|---|---|---|")
for k, e in ev.items():
    print("| %s | %s | %d of %d | %s | %s | %s | **%s** |" % (
        k, "holds" if e["c1a_primary"] else "fails", sum(e["c1a_cells"].values()), len(e["cells"]),
        "holds" if e["c1b"] else "fails", "holds" if e["c1c"] else "fails", fmt(e["max_ratio"]), c.verdict(e)))

print("\n## 3. Full grid, R per filter [lower, upper] omitted for width; C1a = every filter's 95% lower bound above 1\n")
print("| mix | BPF | CSPF | x86_64 F1 / F2 / F3 / F4 | C1a | VM-E F1 / F2 / F3 / F4 | C1a | VM-T C1a |")
print("|---|---|---|---|---|---|---|---|")
for mix in MIXES:
    for bp in BPFS:
        for sm in SMS:
            k = (mix, bp, sm)
            row = lambda e: " / ".join(fmt(e["cells"][k][f][0]) for f in F)
            print("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                mix, bp, sm, row(ev["x86_64"]), "yes" if ev["x86_64"]["c1a_cells"][k] else "NO",
                row(ev["VM-E (A3 M2)"]), "yes" if ev["VM-E (A3 M2)"]["c1a_cells"][k] else "NO",
                "yes" if ev["VM-T (toggle total)"]["c1a_cells"][k] else "NO"))

print("\n## 4. Cells where C1a fails\n")
for kname, e in ev.items():
    print("- %s: %s" % (kname, "; ".join("%s / %s / %s" % k for k, ok in sorted(e["c1a_cells"].items()) if not ok) or "none"))
