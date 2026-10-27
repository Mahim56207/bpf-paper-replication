#!/usr/bin/env python3
"""Phase 8.4 summary: rules N1 to N3 of docs/phase8_4_design.md, computed from the logs only (logs/p8/p8_4/<batch>/runs/*.log).
Window validity: harness-integrity rules V1, V2, V5'a-e, V6 of scripts/summarize.py parse_run (imported); V3, V4, V7 and V8 are not applied
(counted per cell); V8 is evaluated as a classifier: flag = canary rate > 1.2 x canary_max of the window's canary set (0.0826 for {0,1}, 0.0443 for {0}).
Writes results/p8_4_summary.md and results/p8_4_summary.json (deleted first, checked after). Usage: python3 -I scripts/p8_4_summary.py"""
import collections, glob, importlib.util, json, math, os, pathlib, re, statistics, sys

sys.dont_write_bytecode = True
os.chdir(pathlib.Path(__file__).resolve().parent.parent)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


summ = load("summ", "scripts/summarize.py")
st = load("p82", "scripts/p8_2_summary.py")            # t975, mean_sd_n (statistics helpers; no run data is read at import)
base = json.load(open("results/baseline_calibration.json"))
IDLE = base["idle_rate_mean"]
LIM = {"01": summ.CANARY_FACTOR * base["canary_max"]["01"], "0": summ.CANARY_FACTOR * base["canary_max"]["0"]}
DELTA = 0.05
MIN_N = 25
KEEP_PREFIX = ("V1", "V2", "V5", "V6")
EXEMPT_N = ("V2 no FINAL line from the capture process", "V2 map counters unreadable")
outs = [pathlib.Path("results/p8_4_summary.md"), pathlib.Path("results/p8_4_summary.json")]
for o in outs:
    o.unlink(missing_ok=True)


def wilson(k, n, z=1.959964):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def ratio(a, b):
    """mean(a)/mean(b), delta-method 95% CI with Welch df."""
    ma, sa, na = st.mean_sd_n(a); mb, sb, nb = st.mean_sd_n(b)
    va, vb = sa * sa / na, sb * sb / nb
    R = ma / mb
    se = R * math.sqrt(va / ma ** 2 + vb / mb ** 2)
    df = (va + vb) ** 2 / (va * va / (na - 1) + vb * vb / (nb - 1))
    t = st.t975(df)
    return R, R - t * se, R + t * se


def classify(R, lo, hi):
    if lo > 1 or hi < 1:
        if abs(R - 1) > DELTA:
            return "MATERIAL"
    if lo > 1 - DELTA and hi < 1 + DELTA:
        return "EQUIVALENT"
    return "INDETERMINATE"


# ------------------------------------------------------------------ load windows
cells = collections.defaultdict(list)       # (exp, type, level) -> list of dicts
excluded = collections.defaultdict(list)
files = sorted(glob.glob("logs/p8/p8_4/[CFX][123]/runs/*.log"))
if not files:
    sys.exit("FATAL: no run logs under logs/p8/p8_4/<batch>/runs/")
for f in files:
    r = summ.parse_run(f)
    lab = r_label = None
    txt = open(f).read()
    if not txt.rstrip().splitlines()[-1].startswith("# end="):
        sys.exit("FATAL: %s is incomplete" % f)
    m = re.search(r"# bench label=(p84\w+) ", txt)
    lab = m.group(1)
    mm = re.match(r"p84(E[12])(cpu|cache)L(\d)$", lab)
    if mm:
        key = (mm.group(1), mm.group(2), int(mm.group(3)))
    else:
        m3 = re.match(r"p84(E3)(S\d)$", lab)
        if not m3:
            sys.exit("FATAL: unknown label %s in %s" % (lab, f))
        key = ("E3", m3.group(2), 0)
    reasons, other = [], []
    for x in r["reasons"]:
        if r["cfg"] == "N" and x.startswith(EXEMPT_N):
            continue
        (reasons if x.startswith(KEEP_PREFIX) else other).append(x)
    w, pc = r["window_s"], r["busy_sec_per_cpu"]
    canary = r["canary_rate"]
    cset = r["canary_set"]
    d = {"file": f, "batch": f.split("/")[3], "cfg": r["cfg"], "reasons": reasons, "other_reasons": other, "canary": canary, "cset": cset,
         "flag": canary > LIM[cset], "window": w, "V4": any(x.startswith("V4") for x in other), "V7": any(x.startswith("V7") for x in other),
         "V3": any(x.startswith("V3") for x in other), "drops": (r["kernel_drops"] or 0) / r["kernel_packets"] if r.get("kernel_packets") else None}
    if key[0] == "E2":
        d["metric"] = r.get("offered_pps")
    else:
        mf = r.get("matched_flow")
        d["metric"] = ((r["busy_sec_total"] - IDLE * w) * 1e9 / mf) if mf else None
        d["metric_exp"] = (sum(pc["cpu%d" % c] for c in (2, 3, 4)) * 1e9 / mf) if mf else None
        d["canary_ns"] = canary * w * 1e9 / mf if mf else None
    if reasons or d["metric"] is None:
        excluded[key].append((f, reasons or ["no metric"]))
    else:
        cells[key].append(d)

res = {"limits": LIM, "delta": DELTA, "cells": {}, "families": {}, "e3": {}}
md = ["# Phase 8.4: does V8 do what it is supposed to do? (computed by scripts/p8_4_summary.py from the logs only)\n",
      "Windows: %d logs in %d launches. V8 limits: %.4f for canary cores {0,1} (E1, E3), %.4f for {0} (E2). Tolerance delta = %d%%. Metric: E1/E3 net CPU ns per flow-scoped matched packet (system-wide, idle baseline %.4f); E2 offered packets per second. Windows excluded by the harness-integrity rules V1, V2, V5', V6: %d.\n" % (
          len(files), len({f.split("/")[3] for f in files}), LIM["01"], LIM["0"], int(DELTA * 100), IDLE, sum(len(v) for v in excluded.values()))]


def stats_of(key):
    ws = cells.get(key, [])
    n = len(ws)
    flags = sum(w["flag"] for w in ws)
    lo, hi = wilson(flags, n)
    met = [w["metric"] for w in ws]
    return {"n": n, "flags": flags, "p": flags / n if n else float("nan"), "wilson": (lo, hi), "metrics": met,
            "canary_mean": statistics.fmean(w["canary"] for w in ws) if n else float("nan"),
            "v4": sum(w["V4"] for w in ws), "v7": sum(w["V7"] for w in ws), "v3": sum(w["V3"] for w in ws),
            "drops_mean": statistics.fmean(w["drops"] for w in ws if w["drops"] is not None) if any(w["drops"] is not None for w in ws) else None,
            "exp": [w.get("metric_exp") for w in ws], "canary_ns": [w.get("canary_ns") for w in ws]}


def classp(p):
    return "FLAGGED" if p >= 0.9 else ("UNFLAGGED" if p <= 0.1 else "TRANSITION")


# ------------------------------------------------------------------ N1 and N2
fam_results = {}
for exp, title, nlev in (("E1", "E1 paced curve, config B, 512 B, 32000 pps, noise on cores {0,1}", 6), ("E2", "E2 flood, config N, noise on core {0}", 5)):
    for kind in ("cpu", "cache"):
        fam = "%s %s" % (exp, kind)
        md.append("## %s, %s noise\n" % (title, kind))
        md.append("| level | n (excluded) | mean canary rate | added canary rate | flagged | Wilson 95% | class | metric mean | R vs level 0 [95%] | shift class | mechanical expectation | R of M_exp [95%] | V4 / V7 / V3 fails | mean socket drops |")
        md.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        s0 = stats_of((exp, kind, 0))
        fam_rows = []
        for lev in range(nlev):
            s = stats_of((exp, kind, lev))
            exc = len(excluded.get((exp, kind, lev), []))
            if s["n"] < MIN_N or s0["n"] < MIN_N:
                md.append("| %d | %d (%d) | n/a | n/a | n/a | n/a | INCONCLUSIVE (n < %d) | n/a | n/a | n/a | n/a | n/a | n/a | n/a |" % (lev, s["n"], exc, MIN_N))
                fam_rows.append({"level": lev, "class": "INCONCLUSIVE", "shift": "INCONCLUSIVE"})
                continue
            R, lo, hi = ratio(s["metrics"], s0["metrics"]) if lev else (1.0, 1.0, 1.0)
            cl = classify(R, lo, hi) if lev else "-"
            mech = rexp = "n/a"
            if exp == "E1" and lev:
                mech = "%+.1f%%" % (100 * (statistics.fmean(s["canary_ns"]) - statistics.fmean(s0["canary_ns"])) / statistics.fmean(s0["metrics"]))
                Re, elo, ehi = ratio(s["exp"], s0["exp"])
                rexp = "%.3f [%.3f, %.3f]" % (Re, elo, ehi)
            lo_w, hi_w = s["wilson"]
            md.append("| %d | %d (%d) | %.4f | %+.4f | %d/%d = %.2f | [%.2f, %.2f] | %s | %.6g | %.3f [%.3f, %.3f] | %s | %s | %s | %d / %d / %d | %s |" % (
                lev, s["n"], exc, s["canary_mean"], s["canary_mean"] - s0["canary_mean"], s["flags"], s["n"], s["p"], lo_w, hi_w, classp(s["p"]), statistics.fmean(s["metrics"]),
                R, lo, hi, cl, mech, rexp, s["v4"], s["v7"], s["v3"], ("%.4f" % s["drops_mean"]) if s["drops_mean"] is not None else "n/a"))
            fam_rows.append({"level": lev, "p": s["p"], "wilson": s["wilson"], "class": classp(s["p"]), "R": R, "lo": lo, "hi": hi, "shift": cl, "n": s["n"]})
        md.append("")
        # N1 false-positive rate at level 0
        fp = fam_rows[0]
        if "p" in fp:
            ok = fp["wilson"][1] <= 0.10
            md.append("- **False-positive rate at level 0 (rule N1):** %.3f, Wilson upper bound %.3f -> V8 %s at level 0 (threshold 0.10)." % (fp["p"], fp["wilson"][1], "acceptable" if ok else "NOT acceptable"))
        # N2 premise
        flagged = [r for r in fam_rows[1:] if r["class"] == "FLAGGED"]
        unflagged = [r for r in fam_rows[1:] if r["class"] == "UNFLAGGED"]
        trans = [r["level"] for r in fam_rows[1:] if r["class"] in ("TRANSITION", "INCONCLUSIVE")]
        needless = [r["level"] for r in flagged if r["shift"] == "EQUIVALENT"]
        blind = [r["level"] for r in unflagged if r["shift"] == "MATERIAL"]
        indet = [r["level"] for r in flagged + unflagged if r["shift"] == "INDETERMINATE"]
        sup = all(r["shift"] == "MATERIAL" for r in flagged) and all(r["shift"] == "EQUIVALENT" for r in unflagged)
        if sup and flagged and unflagged:
            verdict = "SUPPORTED"
        elif needless or blind:
            verdict = "NOT SUPPORTED"
        else:
            verdict = "PARTIAL"
        md.append("- **Premise for %s: %s.** FLAGGED levels %s; UNFLAGGED non-zero levels %s; TRANSITION or inconclusive levels %s; needless exclusion (flagged, equivalent): %s; blind spot (unflagged, material): %s; indeterminate: %s.\n" % (
            fam, verdict, [r["level"] for r in flagged], [r["level"] for r in unflagged], trans, needless or "none", blind or "none", indet or "none"))
        fam_results[fam] = {"verdict": verdict, "flagged": [r["level"] for r in flagged], "unflagged": [r["level"] for r in unflagged], "transition": trans,
                            "needless": needless, "blind": blind, "indeterminate": indet, "fp": fp.get("p"), "rows": fam_rows}
overall = "SUPPORTED" if all(v["verdict"] == "SUPPORTED" for v in fam_results.values()) and len(fam_results) == 4 else (
    "NOT SUPPORTED" if any(v["verdict"] == "NOT SUPPORTED" for v in fam_results.values()) else "PARTIAL")
md.append("## Overall: V8's premise is **%s**\n" % overall)
md.append("| family | verdict |\n|---|---|\n" + "\n".join("| %s | %s |" % (k, v["verdict"]) for k, v in fam_results.items()) + "\n")
res["families"], res["overall"] = fam_results, overall

# ------------------------------------------------------------------ drift (level 0 per launch)
md.append("## Drift: level-0 metric mean per launch\n")
md.append("| family | launch | n | metric mean |\n|---|---|---|---|")
for (exp, kind, lev), ws in sorted(cells.items()):
    if lev == 0 and exp in ("E1", "E2"):
        by = collections.defaultdict(list)
        for w in ws:
            by[w["batch"]].append(w["metric"])
        for b, v in sorted(by.items()):
            md.append("| %s %s | %s | %d | %.6g |" % (exp, kind, b, len(v), statistics.fmean(v)))
md.append("")

# ------------------------------------------------------------------ N3
md.append("## E3: noise V8 cannot see (config B, 512 B, 32000 pps; canary cores quiet)\n")
md.append("| condition | n (excluded) | mean canary rate | flagged | Wilson 95% | class | M_sys mean | R vs S0 [95%] | shift class | blind |")
md.append("|---|---|---|---|---|---|---|---|---|---|")
s0 = stats_of(("E3", "S0", 0))
names = {"S0": "S0 control", "S1": "S1 cpu noise on core 2 (capture)", "S2": "S2 cpu noise on core 3 (server)", "S3": "S3 global memory pressure"}
for c in ("S0", "S1", "S2", "S3"):
    s = stats_of(("E3", c, 0))
    exc = len(excluded.get(("E3", c, 0), []))
    if s["n"] < 12 or s0["n"] < 12:
        md.append("| %s | %d (%d) | n/a | n/a | n/a | INCONCLUSIVE | n/a | n/a | n/a | n/a |" % (names[c], s["n"], exc))
        continue
    R, lo, hi = ratio(s["metrics"], s0["metrics"]) if c != "S0" else (1.0, 1.0, 1.0)
    cl = classify(R, lo, hi) if c != "S0" else "-"
    blind = (s["p"] <= 0.1 and cl == "MATERIAL") if c != "S0" else "-"
    md.append("| %s | %d (%d) | %.4f | %d/%d = %.2f | [%.2f, %.2f] | %s | %.6g | %.3f [%.3f, %.3f] | %s | %s |" % (
        names[c], s["n"], exc, s["canary_mean"], s["flags"], s["n"], s["p"], s["wilson"][0], s["wilson"][1], classp(s["p"]), statistics.fmean(s["metrics"]), R, lo, hi, cl, blind))
    res["e3"][c] = {"n": s["n"], "p": s["p"], "R": R, "lo": lo, "hi": hi, "shift": cl, "blind": blind}
md.append("\nExcluded windows (V1, V2, V5', V6): " + (", ".join("%s %s: %d" % (k[0], k[1] + str(k[2]), len(v)) for k, v in sorted(excluded.items())) or "none") + ".\n")
outs[0].write_text("\n".join(md) + "\n")
outs[1].write_text(json.dumps(res, indent=1, default=str))
for o in outs:
    if not o.exists() or o.stat().st_size == 0:
        sys.exit("FATAL: %s not written" % o)
print("\n".join(md))
