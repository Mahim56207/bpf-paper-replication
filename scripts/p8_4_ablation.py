#!/usr/bin/env python3
"""Phase 8.4 rule N4: ablation of V8 from existing data (docs/phase8_4_design.md section 5). Recomputes, with V8 switched off, the Phase 6
verdicts C2, C3, C4 and the Phase 8.2 results, and compares them with the published ones. Variants:
  P  = V8 on, final runs only (must reproduce the published verdicts, else the ablation is not accepted)
  A1 = V8 off, final runs only          A2 = V8 off, final runs plus every earlier attempt as additional runs of its cell
Phase 6 uses scripts/summarize.py imported unchanged (CANARY_FACTOR set to infinity for V8 off, idle baseline = calibration as published, D6.13)
on symlink directories under build/p8_4/abl/; Phase 8.2 run set 2 is recomputed from logs/p8/p8_2/run2/ with the rules of docs/phase8_2_design.md;
run set 1 only from the surviving derived data (its raw logs were deleted, D8.14). Writes results/p8_4_ablation.md/.json and logs/p8/p8_4/ablation/
(deleted first, checked after). Usage: python3 -I scripts/p8_4_ablation.py"""
import contextlib, glob, importlib.util, io, json, math, os, pathlib, re, shutil, statistics, sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
outs = [pathlib.Path("results/p8_4_ablation.md"), pathlib.Path("results/p8_4_ablation.json")]
LOGD = pathlib.Path("logs/p8/p8_4/ablation")
for o in outs:
    o.unlink(missing_ok=True)
shutil.rmtree(LOGD, ignore_errors=True)
LOGD.mkdir(parents=True)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


summ = load("summ", "scripts/summarize.py")
os.environ["P8_2_RUN"] = "run2"
st = load("p82", "scripts/p8_2_summary.py")
md = ["# Phase 8.4: V8 ablation from existing data (computed by scripts/p8_4_ablation.py)\n",
      "Variants: **P** = V8 on, final runs only; **A1** = V8 off, final runs only; **A2** = V8 off, final runs plus every earlier attempt as an additional run of its cell (attempts are separate runs under the same conditions, treated as independent: a caveat).\n"]
res = {"phase6": {}, "p82_run2": {}, "p82_run1": {}}

# ------------------------------------------------------------------ Phase 6
pub = json.load(open("results/summary.json"))["verdicts"]
variants = {"P": (False, False), "A1": (True, False), "A2": (True, True)}
for name, (v8_off, with_attempts) in variants.items():
    d = pathlib.Path("build/p8_4/abl") / name
    shutil.rmtree(d, ignore_errors=True)
    (d / "logs").mkdir(parents=True)
    (d / "results").mkdir()
    for f in glob.glob("logs/bench_*.log"):
        os.symlink(ROOT / f, d / "logs" / os.path.basename(f))
    n_att = 0
    if with_attempts:
        for f in glob.glob("logs/attempts/*.log"):
            os.symlink(ROOT / f, d / "logs" / os.path.basename(f))
            n_att += 1
    for j in ("baseline_calibration.json", "calibration.json"):
        shutil.copy("results/" + j, d / "results" / j)
    summ.LOGS, summ.RESULTS = d / "logs", d / "results"
    summ.CANARY_FACTOR = float("inf") if v8_off else 1.2
    os.environ["SUMMARIZE_IDLE_BASELINE"] = "calibration"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = summ.main()
    (LOGD / ("phase6_%s.out" % name)).write_text(buf.getvalue())
    if rc not in (0, None) or not (d / "results" / "summary.json").exists():
        sys.exit("FATAL: summarize.main failed for variant %s: %s" % (name, buf.getvalue()[-500:]))
    v = json.load(open(d / "results" / "summary.json"))["verdicts"]
    res["phase6"][name] = {"verdicts": v, "attempts_added": n_att, "line": buf.getvalue().strip().splitlines()[-1][:300]}
ok_p = all(res["phase6"]["P"]["verdicts"][k][0] == pub[k][0] for k in ("C2", "C3", "C4"))
md += ["## Phase 6 (C2, C3, C4)\n", "Reproduction check (variant P against the published `results/summary.json`): **%s**.\n" % ("PASS, the recomputation reproduces the published labels" if ok_p else "FAIL, the ablation is not accepted"),
       "| claim | published | P (V8 on, final) | A1 (V8 off, final) | A2 (V8 off, final + attempts) |", "|---|---|---|---|---|"]
for k in ("C2", "C3", "C4"):
    md.append("| %s | **%s** | %s | **%s** | **%s** |" % (k, pub[k][0], res["phase6"]["P"]["verdicts"][k][0], res["phase6"]["A1"]["verdicts"][k][0], res["phase6"]["A2"]["verdicts"][k][0]))
md.append("")
for k in ("C2", "C3", "C4"):
    md.append("**%s statistics.**" % k)
    md.append("")
    for name in ("P", "A1", "A2"):
        md.append("- %s: %s" % (name, res["phase6"][name]["verdicts"][k][1]))
    md.append("")
for name in ("P", "A1", "A2"):
    md.append("- %s summarizer line: `%s`" % (name, res["phase6"][name]["line"]))
md.append("")
res["phase6_reproduced"] = ok_p


# ------------------------------------------------------------------ Phase 8.2
def verdict82(off, fs):
    """Rules S1 to S3 of docs/phase8_2_design.md. off: cfg -> offered pps list; fs: cfg -> profile shares f of the valid profiled runs."""
    out = {"n_off": {c: len(v) for c, v in off.items()}, "n_prof": {c: len(v) for c, v in fs.items()}}
    insuff = [c for c in "NAB" if len(off[c]) < 5 or len(fs[c]) < 3]
    h1 = {}
    for x in "AB":
        if len(off["N"]) >= 2 and len(off[x]) >= 2:
            d, se, df, lo, hi = st.welch(off["N"], off[x])
            h1[x] = {"diff": d, "lo": lo, "hi": hi}
    H1e = all(x in h1 for x in "AB")
    H1 = H1e and all(h1[x]["lo"] > 0 for x in "AB")
    h2, ne = {}, []
    for x in "AB":
        if len(fs["N"]) >= 2 and len(fs[x]) >= 2 and len(off["N"]) >= 2 and len(off[x]) >= 2:
            fn, fx = st.ci_mean(fs["N"]), st.ci_mean(fs[x])
            fcap = (fx[0] - fn[0]) / (1 - fn[0])
            P = 1 / (1 - fcap) if fcap < 1 else float("inf")
            R = statistics.fmean(off["N"]) / statistics.fmean(off[x])
            h2[x] = {"fcap": fcap, "P": P, "R": R, "R_over_P_minus_1": R / P - 1, "within": abs(R / P - 1) <= 0.25}
            if fcap >= 0.95:
                ne.append(x)
        else:
            ne.append(x)
    H2e = not ne and len(h2) == 2
    H2 = H2e and all(h2[x]["within"] for x in "AB")
    if insuff:
        v = "INCONCLUSIVE"
    elif not H1e:
        v = "INCONCLUSIVE"
    elif not H1:
        v = "NOT SUPPORTED"
    elif H2:
        v = "SENDER-LIMITED SUPPORTED"
    else:
        v = "MIXED"
    out.update({"h1": h1, "h2": h2, "H1": H1, "H2": H2, "verdict": v})
    return out


def runs82(dirname, v8_off, attempts):
    base = pathlib.Path(dirname)
    off = {c: [] for c in "NABC"}
    fs = {c: [] for c in "NABC"}
    files = [(c, f) for c in "NABC" for f in sorted(glob.glob(str(base / "runs" / ("p82_%s_flood_256_*.log" % c))))]
    if attempts:
        files += [(c, f) for c in "NABC" for f in sorted(glob.glob(str(base / "attempts" / ("p82_%s_flood_256_*.log" % c))))]
    for c, f in files:
        r = st.run_info(pathlib.Path(f), c, False)
        reasons = [x for x in r["reasons_kept"] if not (v8_off and x.startswith("V8 canary"))]
        if not reasons and r.get("offered_pps"):
            off[c].append(r["offered_pps"])
    for c in "NABC":
        for f in sorted(glob.glob(str(base / "runs" / ("p82prof_%s_flood_256_*.log" % c)))):
            r = st.run_info(pathlib.Path(f), c, True)
            cj = base / "profiles" / pathlib.Path(f).name.replace(".log", "_a1.json")
            if cj.exists() and not r["reasons_kept"]:
                j = json.load(open(cj))
                if j["S"] >= 5000:
                    fs[c].append(j["f_tap"])
    return verdict82(off, fs)


pub2 = json.load(open("results/p8_2_summary_run2.json"))
md += ["## Phase 8.2 run set 2 (logs/p8/p8_2/run2/)\n", "| variant | valid unprofiled N / A / B / C | S-H1 (N-A, N-B lower bounds) | S-H2 (R/P - 1 for A, B) | verdict |", "|---|---|---|---|---|"]
for name, (v8_off, att) in variants.items():
    r = runs82("logs/p8/p8_2/run2", v8_off, att)
    res["p82_run2"][name] = r
    md.append("| %s | %s | %s | %s | **%s** |" % (name, " / ".join(str(r["n_off"][c]) for c in "NABC"),
              ", ".join("%.0f" % r["h1"][x]["lo"] for x in "AB") if r["h1"] else "n/a",
              ", ".join("%+.1f%%" % (100 * r["h2"][x]["R_over_P_minus_1"]) for x in "AB") if r["h2"] else "n/a", r["verdict"]))
ok82 = res["p82_run2"]["P"]["verdict"] == pub2["verdict"] and abs(res["p82_run2"]["P"]["h1"]["A"]["diff"] - pub2["h1"]["tests"]["A"]["diff"]) < 1e-6
md.append("\nReproduction check (variant P against `results/p8_2_summary_run2.json`): **%s** (published verdict %s).\n" % ("PASS" if ok82 else "FAIL", pub2["verdict"]))
res["p82_run2_reproduced"] = ok82

# run set 1 from the surviving derived data
exp = open("logs/p8/p8_2/p8_2_diag_exploratory_offered.log").read()
blk = exp.split("-- profiled runs")[0]
off1 = {}
for c in "NABC":
    m = re.search(r"^\s+%s n=\d+ mean \d+ sd \d+\s+per-run: ([\d ]+)$" % c, blk, re.M)
    off1[c] = [float(x) for x in m.group(1).split()]
s1 = open("results/p8_2_summary.md").read()
fs1 = {}
for c in "NABC":
    m = re.search(r"^\| %s \| \d+ \| [\d.]+ \| \[[^\]]*\] \| \d+ \| ([\d., ]+) \|" % c, s1, re.M)
    fs1[c] = [float(x) for x in m.group(1).split(",")] if m else []
r1 = verdict82(off1, fs1)
res["p82_run1"]["V8_off"] = r1
md += ["## Phase 8.2 run set 1 (from the surviving derived data only; raw logs deleted, D8.14)\n",
       "Per-run offered pps of all final unprofiled runs from `logs/p8/p8_2/p8_2_diag_exploratory_offered.log` (every one of them failed only V8, if at all, per `results/p8_2_summary.md`), per-run profile shares f of the valid profiled runs from `results/p8_2_summary.md`.\n",
       "| variant | unprofiled N / A / B / C | profiled valid N / A / B / C | S-H1 lower bounds (N-A, N-B) | S-H2 R/P - 1 (A, B) | verdict |", "|---|---|---|---|---|---|",
       "| published (V8 on) | 5 / 0 / 0 / 4 | 4 / 3 / 4 / 2 | n/a | n/a | **INCONCLUSIVE** |",
       "| V8 off | %s | %s | %s | %s | **%s** |" % (" / ".join(str(r1["n_off"][c]) for c in "NABC"), " / ".join(str(r1["n_prof"][c]) for c in "NABC"),
                                                     ", ".join("%.0f" % r1["h1"][x]["lo"] for x in "AB") if r1["h1"] else "n/a",
                                                     ", ".join("%+.1f%%" % (100 * r1["h2"][x]["R_over_P_minus_1"]) for x in "AB") if r1["h2"] else "n/a", r1["verdict"]), ""]
outs[0].write_text("\n".join(md) + "\n")
outs[1].write_text(json.dumps(res, indent=1, default=str))
for o in outs:
    if not o.exists() or o.stat().st_size == 0:
        sys.exit("FATAL: %s not written" % o)
print("\n".join(md))
sys.exit(0 if ok_p and ok82 else 1)
