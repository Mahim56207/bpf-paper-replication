#!/usr/bin/env python3
"""Phase 8.4, amendment A4 (post hoc re-analysis, docs/phase8_4_design.md section 10): blocked comparison with the launch as block, scale of the tolerance
by the gross CPU per packet for E1/E3, per-launch idle baseline (information), dose-response with launch intercepts, and the restated N1.
Reads logs/p8/p8_4/<batch>/runs and preflight only. Writes results/p8_4_blocked.md and .json (deleted first, checked after).
Usage: python3 -I scripts/p8_4_blocked.py"""
import collections, glob, importlib.util, json, math, os, pathlib, re, statistics, sys

sys.dont_write_bytecode = True
os.chdir(pathlib.Path(__file__).resolve().parent.parent)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


summ = load("summ", "scripts/summarize.py")
st = load("p82", "scripts/p8_2_summary.py")
base = json.load(open("results/baseline_calibration.json"))
IDLE = base["idle_rate_mean"]
LIM = {"01": summ.CANARY_FACTOR * base["canary_max"]["01"], "0": summ.CANARY_FACTOR * base["canary_max"]["0"]}
DELTA = 0.05
KEEP = ("V1", "V2", "V5", "V6")
EXN = ("V2 no FINAL line from the capture process", "V2 map counters unreadable")
outs = [pathlib.Path("results/p8_4_blocked.md"), pathlib.Path("results/p8_4_blocked.json")]
for o in outs:
    o.unlink(missing_ok=True)


def wilson(k, n, z=1.959964):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def clopper_pearson(k, n, a=0.05):
    """Exact binomial 95% interval (Clopper-Pearson) by bisection on the binomial tail probabilities."""
    def cdf(x, p):                      # P(X <= x)
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, x + 1))
    lo = 0.0
    if k > 0:                           # smallest p with P(X >= k) >= a/2
        a_, b_ = 0.0, 1.0
        for _ in range(200):
            m_ = (a_ + b_) / 2
            if 1 - cdf(k - 1, m_) < a / 2: a_ = m_
            else: b_ = m_
        lo = (a_ + b_) / 2
    hi = 1.0
    if k < n:                           # largest p with P(X <= k) >= a/2
        a_, b_ = 0.0, 1.0
        for _ in range(200):
            m_ = (a_ + b_) / 2
            if cdf(k, m_) > a / 2: a_ = m_
            else: b_ = m_
        hi = (a_ + b_) / 2
    return lo, hi


# ---------------------------------------------------------------- windows
W = []
for f in sorted(glob.glob("logs/p8/p8_4/[CF][123]/runs/*.log")):
    t = open(f).read()
    if not t.rstrip().splitlines()[-1].startswith("# end="):
        sys.exit("FATAL: incomplete %s" % f)
    lab = re.search(r"# bench label=(p84\w+) ", t).group(1)
    mm = re.match(r"p84(E[12])(cpu|cache)L(\d)$", lab)
    r = summ.parse_run(f)
    bad = [x for x in r["reasons"] if x.startswith(KEEP) and not (r["cfg"] == "N" and x.startswith(EXN))]
    if bad:
        continue                                                     # none expected: the pooled summary excluded 0 windows
    w, pc = r["window_s"], r["busy_sec_per_cpu"]
    d = {"batch": f.split("/")[3], "exp": mm.group(1), "kind": mm.group(2), "level": int(mm.group(3)), "w": w, "canary": r["canary_rate"], "flag": r["canary_rate"] > LIM[r["canary_set"]]}
    if d["exp"] == "E2":
        d["y"] = r["offered_pps"]
    else:
        mf = r["matched_flow"]
        d["gross"] = r["busy_sec_total"] * 1e9 / mf
        d["y"] = (r["busy_sec_total"] - IDLE * w) * 1e9 / mf
        d["canary_ns"] = r["canary_rate"] * w * 1e9 / mf
        d["unit_ns"] = w * 1e9 / mf
    W.append(d)
pre_idle = {}
for b in ("C1", "C2", "C3", "F1", "F2", "F3"):
    v = []
    for f in sorted(glob.glob("logs/p8/p8_4/%s/preflight/p84pre_D_idle_0_[123].log" % b)):
        r = summ.parse_run(f)
        v.append(r["busy_sec_total"] / r["window_s"])
    pre_idle[b] = statistics.fmean(v)

md = ["# Phase 8.4, amendment A4: blocked re-analysis (POST HOC, computed by scripts/p8_4_blocked.py)\n",
      "Written after the pooled analysis (`results/p8_4_summary.md`) had been seen; the pooled analysis is the pre-declared primary result and its numbers are unchanged. Here every level is compared with level 0 **inside each launch** (3 launches per family, 10 windows per cell and launch), the differences are averaged over the launches, and the interval uses the launch-wise variances (Satterthwaite df, exact t). Tolerance delta = 5%, scale: E2 = mean level-0 offered pps; E1 = mean level-0 gross CPU per flow-scoped matched packet (the net metric's level-0 mean is near zero or negative in some launches).\n"]
res = {"families": {}}


def cell(b, exp, kind, lev):
    return [d for d in W if d["batch"] == b and d["exp"] == exp and d["kind"] == kind and d["level"] == lev]


for exp, blocks, nlev, title in (("E1", ("C1", "C2", "C3"), 6, "E1 paced curve"), ("E2", ("F1", "F2", "F3"), 5, "E2 flood")):
    for kind in ("cpu", "cache"):
        fam = "%s %s" % (exp, kind)
        z = [cell(b, exp, kind, 0) for b in blocks]
        if any(len(c) < 8 for c in z):
            sys.exit("FATAL: level 0 has fewer than 8 windows in a launch for %s" % fam)
        m0 = [statistics.fmean(d["y"] for d in c) for c in z]
        ref = statistics.fmean(m0) if exp == "E2" else statistics.fmean(statistics.fmean(d["gross"] for d in c) for c in z)
        md += ["## %s, %s noise\n" % (title, kind),
               "Reference scale for the tolerance: %.6g %s. Level-0 mean of the metric per launch: %s." % (ref, "pps" if exp == "E2" else "ns per packet (gross)", ", ".join("%s %.6g" % (b, v) for b, v in zip(blocks, m0))),
               ""]
        if exp == "E1":
            net_l = []
            for b, c in zip(blocks, z):
                gross = statistics.fmean(d["gross"] for d in c)
                wm = statistics.fmean(d["w"] for d in c); mmatched = statistics.fmean(d["w"] * 1e9 / d["unit_ns"] if False else 0 for d in c)
                net_l.append((b, statistics.fmean(d["gross"] - pre_idle[b] * d["unit_ns"] for d in c)))
            md.append("Information only (A4 item c): level-0 mean of the net metric with each launch's own pre-flight idle rate (%s): %s (with the fixed 0.1307: %s)." % (
                ", ".join("%s %.4f" % (b, pre_idle[b]) for b in blocks), ", ".join("%s %.1f" % kv for kv in net_l), ", ".join("%s %.1f" % (b, v) for b, v in zip(blocks, m0))))
            md.append("")
        md += ["| level | injected/added canary (mean) | flagged (pooled) | class | D = blocked shift [95%] | shift / scale [95%] | per-launch d | shift class | mechanical expectation / scale |", "|---|---|---|---|---|---|---|---|---|"]
        rows = []
        for lev in range(1, nlev):
            cs = [cell(b, exp, kind, lev) for b in blocks]
            terms, dfs, ds, dm = [], [], [], []
            for c, c0 in zip(cs, z):
                ds.append(statistics.fmean(d["y"] for d in c) - statistics.fmean(d["y"] for d in c0))
                for g in (c, c0):
                    v = statistics.variance([d["y"] for d in g]) / len(g)
                    terms.append(v); dfs.append(len(g) - 1)
                if exp == "E1":
                    dm.append(statistics.fmean(d["canary_ns"] for d in c) - statistics.fmean(d["canary_ns"] for d in c0))
            D = statistics.fmean(ds)
            var = sum(terms) / 9.0
            df = sum(terms) ** 2 / sum(t * t / f for t, f in zip(terms, dfs))
            t = st.t975(df)
            lo, hi = D - t * math.sqrt(var), D + t * math.sqrt(var)
            s, slo, shi = D / ref, lo / ref, hi / ref
            allc = [d for c in cs for d in c]
            p = sum(d["flag"] for d in allc) / len(allc)
            fcl = "FLAGGED" if p >= 0.9 else ("UNFLAGGED" if p <= 0.1 else "TRANSITION")
            if (slo > 0 or shi < 0) and abs(s) > DELTA:
                cl = "MATERIAL"
            elif slo > -DELTA and shi < DELTA:
                cl = "EQUIVALENT"
            else:
                cl = "INDETERMINATE"
            mech = statistics.fmean(dm) / ref if dm else None
            ca = statistics.fmean(d["canary"] for d in allc) - statistics.fmean(d["canary"] for g in z for d in g)
            rows.append({"level": lev, "p": p, "fclass": fcl, "D": D, "lo": lo, "hi": hi, "s": s, "slo": slo, "shi": shi, "class": cl, "mech": mech, "per_launch": ds, "added_canary": ca})
            md.append("| %d | %+.4f | %.2f | %s | %.6g [%.6g, %.6g] | %+.1f%% [%+.1f%%, %+.1f%%] | %s | %s | %s |" % (
                lev, ca, p, fcl, D, lo, hi, 100 * s, 100 * slo, 100 * shi, ", ".join("%.4g" % x for x in ds), cl, ("%+.1f%%" % (100 * mech)) if mech is not None else "n/a"))
        flagged = [r for r in rows if r["fclass"] == "FLAGGED"]
        unfl = [r for r in rows if r["fclass"] == "UNFLAGGED"]
        needless = [r["level"] for r in flagged if r["class"] == "EQUIVALENT"]
        blind = [r["level"] for r in unfl if r["class"] == "MATERIAL"]
        if flagged and unfl and all(r["class"] == "MATERIAL" for r in flagged) and all(r["class"] == "EQUIVALENT" for r in unfl):
            v = "SUPPORTED"
        elif needless or blind:
            v = "NOT SUPPORTED"
        else:
            v = "PARTIAL"
        md.append("\n- **Blocked premise for %s: %s.** FLAGGED levels %s, UNFLAGGED non-zero levels %s, TRANSITION %s; needless exclusion: %s; blind spot: %s; INDETERMINATE: %s.\n" % (
            fam, v, [r["level"] for r in flagged], [r["level"] for r in unfl], [r["level"] for r in rows if r["fclass"] == "TRANSITION"], needless or "none", blind or "none",
            [r["level"] for r in rows if r["class"] == "INDETERMINATE"] or "none"))
        # dose-response with launch intercepts
        fw = [d for d in W if d["exp"] == exp and d["kind"] == kind]
        xs, ys = [], []
        for b in blocks:
            g = [d for d in fw if d["batch"] == b]
            mx, my = statistics.fmean(d["canary"] for d in g), statistics.fmean(d["y"] for d in g)
            xs += [d["canary"] - mx for d in g]; ys += [d["y"] - my for d in g]
        sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
        slope = sxy / sxx
        resid = sum((y - slope * x) ** 2 for x, y in zip(xs, ys))
        dfr = len(xs) - len(blocks) - 1
        se = math.sqrt(resid / dfr / sxx)
        t = st.t975(dfr)
        exp_slope = statistics.fmean(d["unit_ns"] for d in fw) if exp == "E1" else 0.0
        md.append("- **Dose-response (launch intercepts, %d windows):** metric changes by %.4g [%.4g, %.4g] %s per CPU-s/s of measured canary rate; adding the canary CPU alone would give %.4g (E1) / 0 (E2)." % (
            len(xs), slope, slope - t * se, slope + t * se, "ns per packet" if exp == "E1" else "pps", exp_slope))
        md.append("")
        res["families"][fam] = {"verdict": v, "rows": rows, "dose_slope": slope, "dose_ci": [slope - t * se, slope + t * se], "mechanical_slope": exp_slope}
res["overall"] = "SUPPORTED" if all(f["verdict"] == "SUPPORTED" for f in res["families"].values()) else ("NOT SUPPORTED" if any(f["verdict"] == "NOT SUPPORTED" for f in res["families"].values()) else "PARTIAL")
md += ["## Overall (blocked, post hoc): V8's premise is **%s**\n" % res["overall"], "| family | blocked verdict |", "|---|---|"] + ["| %s | %s |" % (k, v["verdict"]) for k, v in res["families"].items()] + [""]
# level-0 windows in every launch (blocked design check)
md += ["## Level-0 windows per launch (the blocked analysis needs level 0 in every launch)\n", "| family | " + " | ".join(("C1", "C2", "C3", "F1", "F2", "F3")) + " |", "|---|---|---|---|---|---|---|"]
for exp, kind in (("E1", "cpu"), ("E1", "cache"), ("E2", "cpu"), ("E2", "cache")):
    md.append("| %s %s | " % (exp, kind) + " | ".join(str(len([d for d in W if d["batch"] == b and d["exp"] == exp and d["kind"] == kind and d["level"] == 0])) for b in ("C1", "C2", "C3", "F1", "F2", "F3")) + " |")
md.append("")
# restated N1
md += ["## N1 restated (A4 item e)\n", "| family | flagged at level 0 | observed rate | Wilson 95% | exact binomial (Clopper-Pearson) 95% |", "|---|---|---|---|---|"]
tot_k = tot_n = 0
for exp, kind in (("E1", "cpu"), ("E1", "cache"), ("E2", "cpu"), ("E2", "cache")):
    g = [d for d in W if d["exp"] == exp and d["kind"] == kind and d["level"] == 0]
    k, n = sum(d["flag"] for d in g), len(g)
    tot_k += k; tot_n += n
    lo, hi = wilson(k, n)
    cl, ch = clopper_pearson(k, n)
    md.append("| %s %s | %d/%d | %.3f | [%.3f, %.3f] | [%.3f, %.3f] |" % (exp, kind, k, n, k / n, lo, hi, cl, ch))
lo, hi = wilson(tot_k, tot_n)
need = next(n for n in range(5, 500) if wilson(0, n)[1] <= 0.10)
cl, ch = clopper_pearson(tot_k, tot_n)
md += ["| all four | %d/%d | %.3f | [%.3f, %.3f] | [%.3f, %.3f] |" % (tot_k, tot_n, tot_k / tot_n, lo, hi, cl, ch), "",
       "The pre-declared criterion (Wilson upper bound at most 0.10) needs at least %d windows even with zero flags, so it was unsatisfiable with 30 windows per family. Restated criterion (A4): the observed false-positive rate is at most 0.10 -> **%s** (observed %.3f over %d level-0 windows; the 95%% interval reaches %.3f)." % (need, "acceptable" if tot_k / tot_n <= 0.10 else "NOT acceptable", tot_k / tot_n, tot_n, hi)]
res["n1"] = {"flags": tot_k, "n": tot_n, "needed_for_zero_flags": need}
outs[0].write_text("\n".join(md) + "\n")
outs[1].write_text(json.dumps(res, indent=1, default=str))
for o in outs:
    if not o.exists() or o.stat().st_size == 0:
        sys.exit("FATAL: %s not written" % o)
print("\n".join(md))
