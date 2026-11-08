#!/usr/bin/env python3
"""Phase 10 summary and labels (docs/phase10_design.md), computed from the logs only. Reads logs/p10/{wp1,wp2a,wp2b,wp3,wp4}/ and results/p10_plan_*.tsv; run validity of the
network runs comes from scripts/summarize.py parse_run (imported, not copied) with the documented exemptions and the V8 rule of rule P7.
Writes results/p10_summary.md and results/p10_summary.json (deleted first, checked after). Verdict text is built only inside the functions named verdict_* from computed
values and digit-free fragments (rule P13); `scripts/p10_verify.sh` checks that with the abstract syntax tree of this file. Usage: python3 -I scripts/p10_summarize.py"""
import glob, importlib.util, json, math, os, pathlib, re, statistics, sys
from collections import defaultdict

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
SMOKE = "--smoke" in sys.argv          # smoke mode: reads logs/p10/smoke, minimums of one, tolerates missing blocks, writes to logs/p10/smoke (never to results/)
L = pathlib.Path("logs/p10/smoke") if SMOKE else pathlib.Path("logs/p10")
R = L if SMOKE else pathlib.Path("results")
W3 = L if SMOKE else L / "wp3"
PLAN1 = L / "plan_wp1_smoke.tsv" if SMOKE else pathlib.Path("results/p10_plan_wp1.tsv")
PLAN1B = pathlib.Path("results/p10_plan_wp1b.tsv")      # docs/phase10_wp1b_design.md: long batches that replace WP1 as the data of C2 and C3
MIN_S_B = 5.0           # WP1b: minimum measured wall time of a batch, seconds (docs/phase10_wp1b_design.md section 3)
MIN_BATCH_B = 10        # WP1b: minimum valid batches per (path, size) (docs/phase10_wp1b_design.md section 4)
KINDS = ("memcpy", "tr_reject", "tr_accept", "tr_port", "dr_U", "dr_E", "dr_B")
# RESULT columns of the WP1b tools: (primary metric, thread CPU metric, measured wall seconds)
COLS_B = {"memcpy": (3, 4, 5), "tr_reject": (4, 6, 7), "tr_accept": (4, 6, 7), "tr_port": (4, 6, 7), "dr_U": (11, 12, 13), "dr_E": (11, 12, 13), "dr_B": (11, 12, 13)}
DELTA = 10.0            # slope margin, ns/byte (design section 1)
MARGIN = 0.10           # cost-ratio margin (rule P2)
MIN_BATCH, MIN_RUN = (1, 1) if SMOKE else (8, 5)
NOT_HOLD_MIN = 4        # rule P11: NOT SUPPORTED if C1a fails in at least this many of the six cells
PAPER_BPF, PAPER_NIT = 148.0, 216.0
OUTS = [R / ("p10_summary_smoke.md" if SMOKE else "p10_summary.md"), R / ("p10_summary_smoke.json" if SMOKE else "p10_summary.json")]
FILTERS = ("F1", "F2", "F3", "F4")
LVL = "90% interval"   # the confidence statement, kept outside the verdict functions because rule P13 forbids digits in their strings


def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


summ = load_mod("summ", "scripts/summarize.py")
p82 = load_mod("p82", "scripts/p8_2_summary.py")


# ------------------------------------------------------------------------------------------------ statistics
def tq(level, df):
    """two-sided Student t quantile for the given confidence level and real df (bisection on the exact cdf of scripts/p8_2_summary.py)"""
    target = (1 + level) / 2
    lo, hi = 0.0, 1e4
    for _ in range(200):
        mid = (lo + hi) / 2
        if p82.t_cdf(mid, df) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def ols(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    icpt = my - slope * mx
    res = sum((y - icpt - slope * x) ** 2 for x, y in zip(xs, ys))
    df = n - 2
    s2 = res / df
    return {"slope": slope, "intercept": icpt, "se_slope": math.sqrt(s2 / sxx), "se_int": math.sqrt(s2 * (1 / n + mx * mx / sxx)), "df": df, "n": n}


def slope_ci(f, level):
    h = tq(level, f["df"]) * f["se_slope"]
    return f["slope"] - h, f["slope"] + h


def diff_ci(a, b, level):
    se = math.sqrt(a["se_slope"] ** 2 + b["se_slope"] ** 2)
    df = se ** 4 / (a["se_slope"] ** 4 / a["df"] + b["se_slope"] ** 4 / b["df"])
    h = tq(level, df) * se
    d = a["slope"] - b["slope"]
    return d - h, d, d + h


def slope_class(lo, hi):                      # rule P1
    if lo >= -DELTA and hi <= DELTA:
        return "INSIDE"
    if lo > DELTA:
        return "OUT+"
    if hi < -DELTA:
        return "OUT-"
    return "UNDECIDED"


def ratio_class(lo, hi):                       # rule P2
    if lo > 1 + MARGIN:
        return "B-CHEAPER"
    if hi < 1 / (1 + MARGIN):
        return "A-CHEAPER"
    if lo >= 1 / (1 + MARGIN) and hi <= 1 + MARGIN:
        return "EQUIVALENT"
    return "UNDECIDED"


def mean_sd_n(xs):
    return statistics.fmean(xs), (statistics.stdev(xs) if len(xs) > 1 else float("nan")), len(xs)


def log_ratio(a, b):
    """ratio of means a/b with the delta-method interval on the logarithm (z = 1.96, design section 5.1): returns (lo, est, hi, var of the log)"""
    r = a[0] / b[0]
    v = (a[1] / a[0]) ** 2 / a[2] + (b[1] / b[0]) ** 2 / b[2]
    return r * math.exp(-1.96 * math.sqrt(v)), r, r * math.exp(1.96 * math.sqrt(v)), v


def _betacf(a, b, x):
    """continued fraction of the regularized incomplete beta function (modified Lentz); works in log space, so n of millions is fine"""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 100000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d; d = d if abs(d) > tiny else tiny
        c = 1.0 + aa / c; c = c if abs(c) > tiny else tiny
        d = 1.0 / d; h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d; d = d if abs(d) > tiny else tiny
        c = 1.0 + aa / c; c = c if abs(c) > tiny else tiny
        d = 1.0 / d; delta = d * c; h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def betainc(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def clopper_pearson(k, n, alpha=0.05):
    """exact interval from the beta quantiles: low = Beta(alpha/2; k, n-k+1), high = Beta(1-alpha/2; k+1, n-k)"""
    def quant(q, a, b):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if betainc(a, b, mid) < q else (lo, mid)
        return (lo + hi) / 2
    low = 0.0 if k == 0 else quant(alpha / 2, k, n - k + 1)
    high = 1.0 if k == n else quant(1 - alpha / 2, k + 1, n - k)
    return low, high


def fx(x, d=4):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}g}"


def fint(t, d=4):
    return "[%s, %s]" % (fx(t[0], d), fx(t[1], d))


def need_files(pattern, what):
    fs = sorted(glob.glob(pattern))
    if not fs:
        sys.exit(f"FATAL: no {what} found ({pattern}); the measured run has not produced it")
    return fs


# ------------------------------------------------------------------------------------------------ WP1
def wp1():
    plan = [l.split("\t") for l in open(PLAN1).read().splitlines() if l and not l.startswith("#")]
    expected = {int(p[0]): (p[1], int(p[2]), int(p[3])) for p in plan}
    best = {}
    for f in need_files(str(L / "wp1" / "b*_a*.log"), "WP1 batch logs"):
        m = re.match(r"b(\d+)_a(\d+)\.log", os.path.basename(f))
        seq, att = int(m[1]), int(m[2])
        if seq not in best or att > best[seq][0]:
            best[seq] = (att, f)
    missing = sorted(set(expected) - set(best))
    if missing:
        sys.exit(f"FATAL: WP1 plan rows without a log: {missing[:10]} ({len(missing)} in all)")
    vals = defaultdict(list)
    invalid, reruns = [], sum(1 for f in glob.glob(str(L / "wp1" / "b*_a*.log")) if not re.search(r"_a1\.log$", f))
    for seq, (att, f) in sorted(best.items()):
        txt = open(f).read()
        kind, size, batch = expected[seq]
        res = re.search(r"^RESULT (.*)$", txt, re.M)
        rc = int(re.search(r"^RC (\d+)", txt, re.M).group(1))
        can = re.search(r"^CANARY rate=(\S+) .* status=(\S+)", txt, re.M)
        if rc != 0 or not res or can.group(2) != "clean":
            invalid.append((seq, kind, size, batch, rc, can.group(2)))
            continue
        c = res.group(1).split(",")
        y = float(c[8]) if kind.startswith("dr_") else float(c[2])
        vals[(kind, size)].append(y)
    fits, short = {}, []
    for kind in ("memcpy", "tr_reject", "tr_accept", "tr_port", "dr_U", "dr_E", "dr_B"):
        xs, ys = [], []
        for size in sorted({s for (k, s) in vals if k == kind}):
            v = vals[(kind, size)]
            if len(v) < MIN_BATCH:
                short.append((kind, size, len(v)))
            for y in v:
                xs.append(size)
                ys.append(y)
        if len({x for x in xs}) < 3 or any(k == kind for k, _, _ in short):
            fits[kind] = None
            continue
        f = ols(xs, ys)
        lo, hi = slope_ci(f, 0.90)
        f.update({"lo_ci": lo, "hi_ci": hi, "class": slope_class(lo, hi), "hi_over_bpf": hi / PAPER_BPF, "hi_over_nit": hi / PAPER_NIT,
                  "bpf_over_hi": paper_ratio(hi, PAPER_BPF), "nit_over_hi": paper_ratio(hi, PAPER_NIT),
                  "means": {s: statistics.fmean(vals[(kind, s)]) for s in sorted({s for (k, s) in vals if k == kind})}})
        fits[kind] = f
    return {"fits": fits, "invalid": invalid, "short": short, "reruns": reruns, "batches": len(best)}


def paper_ratio(hi, paper):
    """ratio of a 1993 slope to the upper bound of a 90% interval of this study (a comparison of different measurement paths); None when the bound is not positive"""
    return paper / hi if hi > 0 else None


def fit_kinds(vals, minb):
    """OLS fit and class per kind from vals[(kind, size)] (shared by WP1b; wp1 above keeps its own copy so the original numbers stay reproducible)"""
    fits, short = {}, []
    for kind in KINDS:
        xs, ys = [], []
        for size in sorted({s for (k, s) in vals if k == kind}):
            v = vals[(kind, size)]
            if len(v) < minb:
                short.append((kind, size, len(v)))
            for y in v:
                xs.append(size)
                ys.append(y)
        if len({x for x in xs}) < 3 or any(k == kind for k, _, _ in short):
            fits[kind] = None
            continue
        f = ols(xs, ys)
        lo, hi = slope_ci(f, 0.90)
        f.update({"lo_ci": lo, "hi_ci": hi, "class": slope_class(lo, hi), "hi_over_bpf": hi / PAPER_BPF, "hi_over_nit": hi / PAPER_NIT,
                  "bpf_over_hi": paper_ratio(hi, PAPER_BPF), "nit_over_hi": paper_ratio(hi, PAPER_NIT),
                  "means": {s: statistics.fmean(vals[(kind, s)]) for s in sorted({s for (k, s) in vals if k == kind})}})
        fits[kind] = f
    return fits, short


def memcpy_vs_user(fits):
    """post hoc, descriptive (not one of the frozen rules): the user-path slope against the copy-floor slope of the same run, as the 90% interval of the difference of the two slopes"""
    su, sm = fits["dr_U"], fits["memcpy"]
    if su is None or sm is None:
        return None
    lo, d, hi = diff_ci(su, sm, 0.90)
    return {"lo": lo, "d": d, "hi": hi, "agree": lo <= 0 <= hi, "overlap": su["lo_ci"] <= sm["hi_ci"] and sm["lo_ci"] <= su["hi_ci"]}


def verdict_memcpy(c):
    if c is None:
        return "no comparison possible (slope data missing)"
    return ("the difference of the user-path slope and the copy-floor slope has an interval that %s zero, so the two slopes %s at this precision; their own intervals %s"
            % ("contains" if c["agree"] else "excludes", "agree" if c["agree"] else "differ", "overlap" if c["overlap"] else "do not overlap"))


def wp1b(root=None, plan_path=None):
    """WP1b (docs/phase10_wp1b_design.md): final attempt of every plan row of the main block; valid = RC 0, canary clean, measured wall time at least MIN_S_B.
    Primary metric (wall based, the frozen WP1 quantity) and thread CPU metric are fitted separately; only the primary fits carry the label."""
    root = pathlib.Path(root) if root else L / "wp1b" / "main"
    plan = [l.split("\t") for l in open(plan_path or PLAN1B).read().splitlines() if l and not l.startswith("#")]
    expected = {int(p[0]): (p[1], int(p[2]), int(p[3])) for p in plan}
    best, allf = {}, glob.glob(str(root / "b*_a*.log"))
    if not allf:
        sys.exit(f"FATAL: no WP1b batch logs found in {root}")
    for f in allf:
        m = re.match(r"b(\d+)_a(\d+)\.log", os.path.basename(f))
        seq, att = int(m[1]), int(m[2])
        if seq not in best or att > best[seq][0]:
            best[seq] = (att, f)
    missing = sorted(set(expected) - set(best))
    if missing:
        sys.exit(f"FATAL: WP1b plan rows without a log: {missing[:10]} ({len(missing)} in all)")
    prim, cpu, invalid, walls = defaultdict(list), defaultdict(list), [], []
    for seq, (att, f) in sorted(best.items()):
        txt = open(f).read()
        kind, size, batch = expected[seq]
        res = re.search(r"^RESULT (.*)$", txt, re.M)
        rc = int(re.search(r"^RC (\d+)", txt, re.M).group(1))
        can = re.search(r"^CANARY rate=(\S+) .* status=(\S+)", txt, re.M)
        cp, cc, cw = COLS_B[kind]
        c = res.group(1).split(",") if res else []
        wall_ok = len(c) > cw and float(c[cw]) >= MIN_S_B
        if rc != 0 or not res or can.group(2) != "clean" or not wall_ok:
            invalid.append((seq, kind, size, batch, rc, can.group(2), "wall_ok" if wall_ok else "wall_short"))
            continue
        walls.append(float(c[cw]))
        prim[(kind, size)].append(float(c[cp]))
        cpu[(kind, size)].append(float(c[cc]))
    fits, short = fit_kinds(prim, MIN_BATCH_B)
    fits_cpu, _ = fit_kinds(cpu, MIN_BATCH_B)
    reruns = sum(1 for f in allf if not re.search(r"_a1\.log$", f))
    return {"fits": fits, "fits_cpu": fits_cpu, "invalid": invalid, "short": short, "reruns": reruns, "batches": len(best), "attempts": len(allf),
            "min_wall_s": min(walls) if walls else None, "valid": sum(len(v) for v in prim.values())}


def verdict_wp1b(c2p, c3p, c2c, c3c, c2o, c3o):
    """text for the two claims from the long-batch run: the primary verdict text, the thread-CPU sensitivity label and the label of the original short-batch run, all computed"""
    t2 = c2p[1] + "; scope: microbenchmarks of the in-kernel filter and of the user-space drain path, not end-to-end capture; same rule on thread CPU time (sensitivity): " + c2c[0] + "; original short-batch run (superseded): " + c2o[0]
    t3 = c3p[1] + "; scope: microbenchmarks of the in-kernel filter and of the user-space drain path, not end-to-end capture; same rule on thread CPU time (sensitivity): " + c3c[0] + "; original short-batch run (superseded): " + c3o[0]
    return t2, t3


def verdict_c2(w):
    sk, su = w["fits"]["tr_reject"], w["fits"]["dr_U"]
    if sk is None or su is None:
        return "INCONCLUSIVE", "slope data missing or fewer valid batches than the minimum: " + str(w["short"])
    lo, d, hi = diff_ci(su, sk, 0.90)
    cd = slope_class(lo, hi)
    if sk["class"] == "INSIDE" and cd == "OUT+":
        lab = "SUPPORTED"
    elif sk["class"] == "INSIDE" and cd == "INSIDE":
        lab = "BOUNDED"
    elif sk["class"] in ("OUT+", "OUT-"):
        lab = "NOT SUPPORTED"
    else:
        lab = "INCONCLUSIVE"
    return lab, ("kernel reject slope s_K %s ns/byte, %s %s, class %s; user path slope s_U %s, %s %s, class %s; d = s_U - s_K %s, %s %s, class %s"
                 % (fx(sk["slope"]), LVL, fint((sk["lo_ci"], sk["hi_ci"])), sk["class"], fx(su["slope"]), LVL, fint((su["lo_ci"], su["hi_ci"])), su["class"], fx(d), LVL, fint((lo, hi)), cd)
                 + "; ratio of the paper slopes to the upper bound (descriptive, a comparison of different measurement paths): s_K %s and %s, s_U %s and %s, d %s and %s"
                 % (fx(sk["bpf_over_hi"]), fx(sk["nit_over_hi"]), fx(su["bpf_over_hi"]), fx(su["nit_over_hi"]), fx(paper_ratio(hi, PAPER_BPF)), fx(paper_ratio(hi, PAPER_NIT)))), (lo, d, hi, cd)


def verdict_c3(w):
    su, se = w["fits"]["dr_U"], w["fits"]["dr_E"]
    if su is None or se is None:
        return "INCONCLUSIVE", "slope data missing or fewer valid batches than the minimum: " + str(w["short"])
    lo, e, hi = diff_ci(su, se, 0.90)
    ce = slope_class(lo, hi)
    lab = {"OUT+": "SUPPORTED", "INSIDE": "BOUNDED", "OUT-": "NOT SUPPORTED"}.get(ce, "INCONCLUSIVE")
    return lab, ("e = s_U - s_E %s ns/byte, %s %s, class %s; s_U %s, s_E %s, s_B %s; ratio of the paper slopes to the upper bound (descriptive, a comparison of different measurement paths): e %s and %s, s_U %s and %s, s_E %s and %s"
                 % (fx(e), LVL, fint((lo, hi)), ce, fx(su["slope"]), fx(se["slope"]), fx(w["fits"]["dr_B"]["slope"]) if w["fits"]["dr_B"] else "n/a",
                    fx(paper_ratio(hi, PAPER_BPF)), fx(paper_ratio(hi, PAPER_NIT)), fx(su["bpf_over_hi"]), fx(su["nit_over_hi"]), fx(se["bpf_over_hi"]), fx(se["nit_over_hi"]))), (lo, e, hi, ce)


# ------------------------------------------------------------------------------------------------ WP2 (common)
def non_v8(r):
    out = [x for x in r["reasons"] if not x.startswith("V8")]
    if r["cfg"] == "N":
        out = [x for x in out if not x.startswith("V2 no FINAL") and not x.startswith("V2 map counters")]
    return out


def wp2_runs(block, pattern_fn):
    d = L / ("wp2" + block)
    calib = json.load(open(d / "calib_v8.json"))
    limit = calib["limit"]
    runs = []
    for f in need_files(str(d / "*_flood_256_*.log"), "WP2 run logs"):
        b = os.path.basename(f)
        if b.startswith("calib") or b.startswith("bench_"):
            continue
        r = summ.parse_run(f)
        r["file_base"] = b
        r["reasons_p10"] = non_v8(r)
        r["v8_clean"] = r.get("canary_rate") is not None and r["canary_rate"] <= limit
        runs.append(r)
    return runs, calib


def wp2a(plan):
    runs, calib = wp2_runs("a", None)
    cells = defaultdict(list)
    excluded = []
    for r in runs:
        m = re.match(r"p10a(T[01])_([NABC])_flood_256_(\d+)\.log", r["file_base"])
        key = (m[1], m[2])
        if r["reasons_p10"] or not r["v8_clean"] or not r.get("offered_pps"):
            excluded.append((r["file_base"], r["reasons_p10"], r["v8_clean"]))
        else:
            cells[key].append(r["offered_pps"])
    need = lambda t, c: len(cells[(t, c)]) >= MIN_RUN
    missing = [(t, c) for t in ("T0", "T1") for c in "NABC" if not need(t, c)]
    stats = {k: mean_sd_n(v) for k, v in cells.items() if len(v) >= 2}
    out = {"cells": {f"{k[0]}_{k[1]}": {"mean": stats[k][0], "sd": stats[k][1], "n": stats[k][2]} for k in stats}, "excluded": excluded, "missing_cells": missing, "calib": calib}
    res = {}
    for x in "ABC":
        if not all(need(t, c) for t, c in (("T0", "N"), ("T1", "N"), ("T0", x), ("T1", x))):
            res[x] = None
            continue
        r0, r1 = log_ratio(stats[("T0", "N")], stats[("T0", x)]), log_ratio(stats[("T1", "N")], stats[("T1", x)])
        q = r1[1] / r0[1]
        vq = r0[3] + r1[3]
        res[x] = {"R_base": r0[:3], "R_mit": r1[:3], "Q": (q * math.exp(-1.96 * math.sqrt(vq)), q, q * math.exp(1.96 * math.sqrt(vq)))}
    out["ratios"] = res
    return out


GAP_CLOSED = ("REVERSED", "AT PARITY")   # classes of rule P6 that count as the gap closed (named differently in the first version of this script; thresholds unchanged, see DEVIATIONS D10.11)


def verdict_mitigation(a):
    cls = {}
    for x in "AB":
        v = a["ratios"].get(x)
        if v is None:
            return "INCONCLUSIVE", "fewer valid runs than the minimum in a cell: " + str(a["missing_cells"]), cls
        qlo, q, qhi = v["Q"]
        rhi = v["R_mit"][2]
        if qhi < 1 and rhi < 1:
            cls[x] = "REVERSED"
        elif qhi < 1 and rhi <= 1.10:
            cls[x] = "AT PARITY"
        elif qhi < 1 and rhi <= 1.25:
            cls[x] = "REDUCED"
        elif qlo > 0.90:
            cls[x] = "NOT REDUCED"
        else:
            cls[x] = "UNDECIDED"
    if all(c in GAP_CLOSED for c in cls.values()):
        lab = "SUPPORTED"
    elif all(c in GAP_CLOSED + ("REDUCED",) for c in cls.values()):
        lab = "BOUNDED"
    elif "NOT REDUCED" in cls.values():
        lab = "NOT SUPPORTED"
    else:
        lab = "INCONCLUSIVE"
    txt = "; ".join("%s: %s, ratio no-capture over this configuration in the baseline topology %s, in the mitigated topology %s, Q %s" % (x, cls[x], fint(a["ratios"][x]["R_base"][::2], 3), fint(a["ratios"][x]["R_mit"][::2], 3), fint(a["ratios"][x]["Q"][::2], 3)) for x in "AB")
    if any(c == "REVERSED" for c in cls.values()):
        txt += ("; reading: a ratio below one means the configuration with capture attached offered more load than the configuration without capture, so the gap is reversed, "
                "not just closed; the causes of the reversal are UNVERIFIED")
    return lab, txt, cls


def wp2b():
    runs, calib = wp2_runs("b", None)
    idle = [summ.parse_run(f) for f in need_files(str(L / "wp2b" / "bench_D_idle_0_*.log"), "WP2b idle windows")]
    ib = statistics.fmean((r["busy_sec_per_cpu"]["cpu1"] + r["busy_sec_per_cpu"]["cpu2"]) / r["window_s"] for r in idle)
    cells = defaultdict(list)
    excluded = []
    for r in runs:
        m = re.match(r"lad(\d+)_([ABC])_flood_256_(\d+)\.log", r["file_base"])
        rate, cfg = int(m[1]), m[2]
        held = r.get("offered_pps") is not None and 0.95 <= r["offered_pps"] / rate <= 1.05
        if r["reasons_p10"] or not r["v8_clean"] or not held or not r.get("matched_flow"):
            excluded.append((r["file_base"], r["reasons_p10"], r["v8_clean"], held))
            continue
        w = r["window_s"]
        busy = r["busy_sec_per_cpu"]["cpu1"] + r["busy_sec_per_cpu"]["cpu2"] - ib * w
        d = (r["kernel_drops"] or 0, r["kernel_packets"] or 0)
        cells[(rate, cfg)].append({"cpu": busy * 1e9 / r["matched_flow"], "drops": d[0], "pk": d[1]})
    rates = sorted({k[0] for k in cells} | {int(re.match(r"lad(\d+)_", os.path.basename(f))[1]) for f in glob.glob(str(L / "wp2b" / "lad*_flood_256_*.log"))})
    out = {"idle_busy_rate_cores_1_2": ib, "calib": calib, "excluded": excluded, "rates": {}}
    for rate in rates:
        n = {c: len(cells[(rate, c)]) for c in "ABC"}
        row = {"n": n}
        if min(n.values()) < MIN_RUN:
            row["status"] = "UNREACHABLE"
            out["rates"][str(rate)] = row
            continue
        row["status"] = "REACHABLE"
        cpu = {c: mean_sd_n([v["cpu"] for v in cells[(rate, c)]]) for c in "ABC"}
        row["cpu"] = {c: {"mean": cpu[c][0], "sd": cpu[c][1], "n": cpu[c][2]} for c in "ABC"}
        rho = summ.ratio_ci(cpu["A"], cpu["B"])
        row["rho"] = rho
        row["rho_class"] = ratio_class(rho[0], rho[2]) if rho else "UNDECIDED"
        dr = {}
        for c in "AB":
            k = sum(v["drops"] for v in cells[(rate, c)])
            p = sum(v["pk"] for v in cells[(rate, c)])
            dr[c] = {"drops": k, "packets": p, "frac": k / p if p else None, "cp95": clopper_pearson(k, p) if p else None}
        row["drops"] = dr
        if dr["A"]["cp95"] and dr["B"]["cp95"]:
            fa = [v["drops"] / v["pk"] for v in cells[(rate, "A")] if v["pk"]]
            fb = [v["drops"] / v["pk"] for v in cells[(rate, "B")] if v["pk"]]
            wd = summ.welch_diff_ci(mean_sd_n(fa), mean_sd_n(fb)) if len(fa) > 1 and len(fb) > 1 else None
            if dr["A"]["cp95"][1] <= 0.001 and dr["B"]["cp95"][1] <= 0.001:
                row["drop_class"] = "NO-LOSS-BOUND"
            elif wd and wd[0] > 0.001:
                row["drop_class"] = "B-BETTER"
            elif wd and (-wd[2]) > 0.001:
                row["drop_class"] = "A-BETTER"
            else:
                row["drop_class"] = "UNDECIDED"
        out["rates"][str(rate)] = row
    return out


def verdict_c4(b):
    reach = {r: v for r, v in b["rates"].items() if v["status"] == "REACHABLE"}
    if len(reach) < 3:
        return "INCONCLUSIVE", "fewer than three reachable rates: " + ", ".join("%s %s" % (r, v["status"]) for r, v in b["rates"].items())
    cl = [v["rho_class"] for v in reach.values()]
    half = math.ceil(len(cl) / 2)
    if cl.count("B-CHEAPER") >= half and cl.count("A-CHEAPER") == 0:
        lab = "SUPPORTED"
    elif cl.count("A-CHEAPER") >= half:
        lab = "NOT SUPPORTED"
    elif cl.count("EQUIVALENT") >= half and cl.count("B-CHEAPER") == 0 and cl.count("A-CHEAPER") == 0:
        lab = "BOUNDED"
    else:
        lab = "INCONCLUSIVE"
    return lab, "; ".join("rate %s: rho %s %s, class %s, drops %s" % (r, fx(v["rho"][1], 3) if v["rho"] else "n/a", fint((v["rho"][0], v["rho"][2]), 3) if v["rho"] else "", v["rho_class"], v.get("drop_class", "n/a")) for r, v in sorted(reach.items(), key=lambda kv: int(kv[0])))


# ------------------------------------------------------------------------------------------------ WP3
def tsv(path):
    lines = open(path).read().splitlines()
    h = lines[0].split("\t")
    return [dict(zip(h, l.split("\t"))) for l in lines[1:]]


def chunk_ratios(rows, build, mix, f, num, den):
    a = {int(r["chunk"]): int(r["Ir_eval"]) for r in rows if (r["build"], r["mix"], r["filter"], r["program"]) == (build, mix, f, num)}
    b = {int(r["chunk"]): int(r["Ir_eval"]) for r in rows if (r["build"], r["mix"], r["filter"], r["program"]) == (build, mix, f, den)}
    return [a[c] / b[c] for c in sorted(set(a) & set(b))]


def t_interval(xs):
    n = len(xs)
    m = statistics.fmean(xs)
    if n < 2:
        return m, m, m
    h = summ.tcrit(n - 1) * statistics.stdev(xs) / math.sqrt(n)
    return m - h, m, m + h


def cell_summary(rows, build, mix, num, den):
    """ratios per filter with intervals, direction class, ordering flags, F2 - F3 difference interval"""
    R = {f: t_interval(chunk_ratios(rows, build, mix, f, num, den)) for f in ("F1", "F2", "F3", "F4")}
    dirn = "HOLDS" if all(R[f][0] > 1 for f in R) else ("REVERSED" if any(R[f][2] < 1 for f in R) else "UNDECIDED")
    order = R["F1"][1] < R["F2"][1] < R["F3"][1] < R["F4"][1]
    c2 = chunk_ratios(rows, build, mix, "F2", num, den)
    c3 = chunk_ratios(rows, build, mix, "F3", num, den)
    d23 = t_interval([a - b for a, b in zip(c2, c3)])
    return {"R": R, "direction": dirn, "order_holds": order, "F2_minus_F3": d23}


def wp3():
    eg, mg = tsv(W3 / "grid_equiv.tsv"), tsv(W3 / "grid_m2.tsv")
    bad_builds = sorted({r["build"] for r in eg if int(r["decision_mismatches"]) != 0})
    out = {"excluded_builds": bad_builds, "grid": {}, "grid_raw": {}}
    for b in sorted({r["build"] for r in mg}):
        if b in bad_builds:
            continue
        out["grid"][b] = cell_summary(mg, b, "mix_M0", "sm-sc-fused", "bpf-opt")
        out["grid_raw"][b] = cell_summary(mg, b, "mix_M0", "sm-sc-fused", "bpf-raw")
    ie, im = tsv(W3 / "indep_equiv.tsv"), tsv(W3 / "indep_m2.tsv")
    out["indep"] = {}
    out["indep_equiv_bad"] = sum(1 for r in ie if int(r["decision_mismatches"]))
    for mix in sorted({r["mix"] for r in im}):
        out["indep"][mix] = {"ours": cell_summary(im, "gcc-O2", mix, "sm-ours", "bpf-opt"), "indep": cell_summary(im, "gcc-O2", mix, "sm-indep", "bpf-opt")}
    re_, rm = tsv(W3 / "real_equiv.tsv"), tsv(W3 / "real_m2.tsv")
    out["real_equiv_bad"] = sum(1 for r in re_ if int(r["decision_mismatches"]))
    out["real"] = {b: {"opt": cell_summary(rm, b, "real", "sm-sc-fused", "bpf-opt"), "raw": cell_summary(rm, b, "real", "sm-sc-fused", "bpf-raw")} for b in sorted({r["build"] for r in rm})}
    return out


def verdict_c1(w):
    cells = w["grid"]
    if len(cells) < (1 if SMOKE else 6):
        return "INCONCLUSIVE", "fewer than six valid builds: excluded " + str(w["excluded_builds"]), {}
    holds_a = [b for b, c in cells.items() if c["direction"] == "HOLDS"]
    holds_b = [b for b, c in cells.items() if c["order_holds"]]
    if len(holds_a) == len(cells) and len(holds_b) == len(cells):
        lab = "SUPPORTED"
    elif len(cells) - len(holds_a) >= NOT_HOLD_MIN:
        lab = "NOT SUPPORTED"
    else:
        lab = "BOUNDED"
    rng = {f: (min(c["R"][f][0] for c in cells.values()), max(c["R"][f][2] for c in cells.values())) for f in FILTERS}
    txt = "direction holds in %d of %d builds (%s), ordering holds in %d of %d (%s); range of R over the builds: %s" % (
        len(holds_a), len(cells), ",".join(holds_a), len(holds_b), len(cells), ",".join(holds_b), "; ".join("%s %s" % (f, fint(rng[f], 3)) for f in rng))
    return lab, txt, rng


# ------------------------------------------------------------------------------------------------ WP4
def wp4():
    d = L / "wp4"
    r = {}
    for p in ("unbounded", "bounded"):
        r[p] = {"status": open(d / f"{p}_status.txt").read().strip(), "exit": int(open(d / f"{p}_exit.txt").read().strip()),
                "stderr_bytes": os.path.getsize(d / f"{p}_stderr.txt")}
    return r


def verdict_c5(w):
    u, b = w["unbounded"]["status"], w["bounded"]["status"]
    if u == "rejected" and b == "loaded":
        return "SUPPORTED", "unbounded program %s (exit %d), bounded program %s (exit %d)" % (u, w["unbounded"]["exit"], b, w["bounded"]["exit"])
    if u == "rejected" and b == "rejected":
        return "BOUNDED", "unbounded program %s, bounded program %s" % (u, b)
    return "NOT SUPPORTED", "unbounded program %s, bounded program %s" % (u, b)


# ------------------------------------------------------------------------------------------------ main
def block(fn, *args):
    """smoke mode: a missing block is reported and replaced by None; in a real summary any failure is fatal"""
    if not SMOKE:
        return fn(*args)
    try:
        return fn(*args)
    except SystemExit as e:
        print("smoke: block %s skipped: %s" % (fn.__name__, e))
        return None


def main():
    for o in OUTS:
        if o.exists():
            o.unlink()
    out = {}
    w1 = block(wp1)
    out["wp1"] = w1
    c2 = block(verdict_c2, w1) if w1 else ("INCONCLUSIVE", "no WP1 data")
    c3 = block(verdict_c3, w1) if w1 else ("INCONCLUSIVE", "no WP1 data")
    c2_old, c3_old = c2, c3
    wb = block(wp1b) if not SMOKE else None
    out["wp1b"] = wb
    if wb:
        c2 = verdict_c2({"fits": wb["fits"], "short": wb["short"]})
        c3 = verdict_c3({"fits": wb["fits"], "short": wb["short"]})
        c2c = verdict_c2({"fits": wb["fits_cpu"], "short": wb["short"]})
        c3c = verdict_c3({"fits": wb["fits_cpu"], "short": wb["short"]})
        t2, t3 = verdict_wp1b(c2, c3, c2c, c3c, c2_old, c3_old)
        c2, c3 = (c2[0], t2) + tuple(c2[2:]), (c3[0], t3) + tuple(c3[2:])
    a = block(wp2a, None)
    mit = block(verdict_mitigation, a) if a else ("INCONCLUSIVE", "no WP2a data", {})
    b = block(wp2b)
    c4 = block(verdict_c4, b) if b else ("INCONCLUSIVE", "no WP2b data")
    w3 = block(wp3)
    c1 = block(verdict_c1, w3) if w3 else ("INCONCLUSIVE", "no WP3 data", {})
    w4 = block(wp4)
    c5 = block(verdict_c5, w4) if w4 else ("INCONCLUSIVE", "no WP4 data")
    out.update({"wp2a": a, "wp2b": b, "wp3": w3, "wp4": w4})
    det = lambda t: t[2] if len(t) > 2 else None
    out["labels"] = {"C1": {"label": c1[0], "text": c1[1], "detail": det(c1)}, "C2": {"label": c2[0], "text": c2[1], "detail": det(c2)}, "C3": {"label": c3[0], "text": c3[1], "detail": det(c3)},
                     "C4": {"label": c4[0], "text": c4[1]}, "C4-mitigation": {"label": mit[0], "text": mit[1], "detail": det(mit)}, "C5": {"label": c5[0], "text": c5[1]}}
    if wb:
        out["labels"]["C2 (WP1 original)"] = {"label": c2_old[0], "text": c2_old[1], "detail": det(c2_old)}
        out["labels"]["C3 (WP1 original)"] = {"label": c3_old[0], "text": c3_old[1], "detail": det(c3_old)}
    md = ["# Phase 10 summary", "", "Computed by scripts/p10_summarize.py from logs/p10/ only (rules P1 to P13 of docs/phase10_design.md).", "", "## Final labels", "",
          "| claim | label | evidence (computed) |", "|---|---|---|"]
    for k, v in out["labels"].items():
        md.append("| %s | **%s** | %s |" % (k, v["label"], v["text"].replace("|", "/")))
    if wb and wb["fits"]["tr_reject"] and wb["fits"]["dr_U"] and wb["fits"]["dr_E"] and wb["fits"]["memcpy"]:
        F = wb["fits"]
        rows = [("s_K, kernel reject_all (test run)", F["tr_reject"]["slope"], F["tr_reject"]["lo_ci"], F["tr_reject"]["hi_ci"]),
                ("s_U, user-space drain path U", F["dr_U"]["slope"], F["dr_U"]["lo_ci"], F["dr_U"]["hi_ci"]),
                ("d = s_U - s_K (claim C2)", *(lambda t: (t[1], t[0], t[2]))(diff_ci(F["dr_U"], F["tr_reject"], 0.90))),
                ("s_E, in-kernel accept-all drain path E", F["dr_E"]["slope"], F["dr_E"]["lo_ci"], F["dr_E"]["hi_ci"]),
                ("e = s_U - s_E (claim C3)", *(lambda t: (t[1], t[0], t[2]))(diff_ci(F["dr_U"], F["dr_E"], 0.90))),
                ("s_memcpy, copy floor", F["memcpy"]["slope"], F["memcpy"]["lo_ci"], F["memcpy"]["hi_ci"]),
                ("s_U - s_memcpy (post hoc, descriptive)", *(lambda t: (t[1], t[0], t[2]))(diff_ci(F["dr_U"], F["memcpy"], 0.90)))]
        md += ["", "## C2 and C3 as intervals (WP1b, ns per byte of frame size, 90% intervals) and the 1993 slopes", "",
               "Scope: WP1b measures the in-kernel filter (BPF_PROG_TEST_RUN) and the user-space drain path of an AF_PACKET queue as microbenchmarks; it does not measure end-to-end capture.", "",
               "| quantity | estimate | 90%% interval | class (delta = %s ns/byte, frozen) | 148 / upper bound | 216 / upper bound |" % fx(DELTA), "|---|---|---|---|---|---|"]
        for name, est, lo, hi in rows:
            md.append("| %s | %s | %s | %s | %s | %s |" % (name, fx(est), fint((lo, hi)), slope_class(lo, hi), fx(paper_ratio(hi, PAPER_BPF), 3), fx(paper_ratio(hi, PAPER_NIT), 3)))
        mcmp = memcpy_vs_user(F)
        out["wp1b"]["memcpy_vs_user"] = mcmp
        out["wp1b"]["interval_table"] = [{"quantity": n, "estimate": e, "lo": l, "hi": h, "bpf_over_hi": paper_ratio(h, PAPER_BPF), "nit_over_hi": paper_ratio(h, PAPER_NIT)} for n, e, l, h in rows]
        md += ["", "The two last columns are the ratio of the 1993 slopes (148 ns/byte for the BPF filter, 216 ns/byte for NIT, from the paper) to the upper bound of the interval of this study: a comparison of different measurement paths (different machine, kernel, and code path), not a replication; a blank means the upper bound is not positive.", "",
               "Copy floor against the user path: " + verdict_memcpy(mcmp) + " (post hoc and descriptive: this comparison is not one of the frozen rules and carries no label).", ""]
    if wb:
        md += ["", "## WP1b slopes (ns per byte of frame size; 90% intervals; long batches; these carry the C2 and C3 labels)", "", "| quantity | slope (wall based) | 90% interval | class | slope (thread CPU) | 90% interval | class | n |", "|---|---|---|---|---|---|---|---|"]
        for k, f in wb["fits"].items():
            g = wb["fits_cpu"][k]
            md.append("| %s | n/a | | | | | | |" % k if f is None else "| %s | %s | %s | %s | %s | %s | %s | %d |" % (k, fx(f["slope"]), fint((f["lo_ci"], f["hi_ci"])), f["class"], fx(g["slope"]), fint((g["lo_ci"], g["hi_ci"])), g["class"], f["n"]))
        md += ["", "WP1b batches: %d plan rows, %d attempts, %d re-run attempts, %d valid batches, %d final batches invalid, shortest measured wall time of a valid batch %s s." % (wb["batches"], wb["attempts"], wb["reruns"], wb["valid"], len(wb["invalid"]), fx(wb["min_wall_s"], 4)), ""]
    md += ["", "## WP1 slopes, original batches (superseded by WP1b when WP1b is present; ns per byte of frame size; 90% intervals)", "", "| quantity | slope | 90% interval | class | upper end / 148 | upper end / 216 | n |", "|---|---|---|---|---|---|---|"]
    for k, f in (w1["fits"].items() if w1 else []):
        md.append("| %s | n/a | | | | | |" % k if f is None else "| %s | %s | %s | %s | %s | %s | %d |" % (k, fx(f["slope"]), fint((f["lo_ci"], f["hi_ci"])), f["class"], fx(f["hi_over_bpf"], 3), fx(f["hi_over_nit"], 3), f["n"]))
    md += ["", ("WP1 batches: %d plan rows, %d re-run attempts, %d final batches invalid." % (w1["batches"], w1["reruns"], len(w1["invalid"]))) if w1 else "WP1: no data", ""]
    md += ["## WP2(a) offered load, flood (mean packets per second over valid runs)", "", "| topology | cfg | mean | sd | n |", "|---|---|---|---|---|"]
    for k, v in sorted(a["cells"].items()) if a else []:
        md.append("| %s | %s | %s | %s | %d |" % (k.split("_")[0], k.split("_")[1], fx(v["mean"], 7), fx(v["sd"], 4), v["n"]))
    md += ["", "| cfg | R in T0 (95%) | R in T1 (95%) | Q = R(T1)/R(T0) (95%) |", "|---|---|---|---|"]
    for x, v in (a["ratios"].items() if a else []):
        md.append("| %s | n/a | | |" % x if v is None else "| %s | %s %s | %s %s | %s %s |" % (x, fx(v["R_base"][1], 3), fint((v["R_base"][0], v["R_base"][2]), 3), fx(v["R_mit"][1], 3), fint((v["R_mit"][0], v["R_mit"][2]), 3), fx(v["Q"][1], 3), fint((v["Q"][0], v["Q"][2]), 3)))
    md += ["", "Mitigation classes: %s. Canary limit of rule P7: %s CPU-s/s." % (mit[2] if len(mit) > 2 else "n/a", fx(a["calib"]["limit"]) if a else "n/a"),
           "", "R is the mean offered load of the no-capture configuration over that of the capture configuration in the same topology. A value below one in the mitigated topology means that the configuration with capture attached offered MORE load than the one without capture: the gap is reversed. The causes of that reversal are UNVERIFIED; no run isolated them.", ""]
    md += ["## WP2(b) ladder", "", "| rate (pps) | status | valid runs A/B/C | rho = cpu(A)/cpu(B) (95%) | class | drop class |", "|---|---|---|---|---|---|"]
    for r, v in (sorted(b["rates"].items(), key=lambda kv: int(kv[0])) if b else []):
        n = v["n"]
        md.append("| %s | %s | %d/%d/%d | %s | %s | %s |" % (r, v["status"], n["A"], n["B"], n["C"], ("%s %s" % (fx(v["rho"][1], 3), fint((v["rho"][0], v["rho"][2]), 3))) if v.get("rho") else "n/a", v.get("rho_class", "n/a"), v.get("drop_class", "n/a")))
    md += ["", "## WP3 C1: ratio CSPF/BPF per filter (95% interval over chunks), primary pairing", "", "| build | F1 | F2 | F3 | F4 | direction | ordering |", "|---|---|---|---|---|---|---|"]
    for bname, c in (w3["grid"].items() if w3 else []):
        md.append("| %s | %s | %s | %s | %s | %s | %s |" % (bname, *[fx(c["R"][f][1], 3) + " " + fint((c["R"][f][0], c["R"][f][2]), 3) for f in ("F1", "F2", "F3", "F4")], c["direction"], "HOLDS" if c["order_holds"] else "FAILS"))
    md += ["", "Phase 10 verify (`scripts/p10_verify.sh`) checks these files against the rules.", ""]
    OUTS[0].write_text("\n".join(md) + "\n")
    OUTS[1].write_text(json.dumps(out, indent=1, default=str) + "\n")
    for o in OUTS:
        if not o.is_file() or o.stat().st_size == 0:
            sys.exit(f"FATAL: {o} was not created")
    print("\n".join(md[:14]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
