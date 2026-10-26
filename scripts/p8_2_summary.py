#!/usr/bin/env python3
"""Phase 8.2 summary and verdict (docs/phase8_2_design.md sections 3 to 6), computed from the logs only.
Reads logs/p8/p8_2/{runs,attempts,profiles}/ and results/p8_2_plan.tsv (run set 2, amendment A2: P8_2_RUN=run2 reads
logs/p8/p8_2/run2/ and results/p8_2_plan_run2.tsv and writes results/p8_2_summary_run2.{md,json}); run validity comes from scripts/summarize.py parse_run
(imported, not copied) with the documented exemptions only; writes results/p8_2_summary.md and results/p8_2_summary.json
(deleted first, checked after). Usage:
  python3 -I scripts/p8_2_summary.py                        full summary
  python3 -I scripts/p8_2_summary.py --parse-only DIR LABEL   print validity/offered/busy of DIR/LABEL_<cfg>_flood_256_1.log (probe data)
  python3 -I scripts/p8_2_summary.py --selftest             check the t quantile against the table of summarize.py"""
import glob, importlib.util, json, math, os, pathlib, re, statistics, sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
spec = importlib.util.spec_from_file_location("summ", "scripts/summarize.py")
summ = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summ)
RUN = os.environ.get("P8_2_RUN", "")
L = pathlib.Path("logs/p8/p8_2") / RUN
SUF = "_" + RUN if RUN else ""
CFGS = ("N", "A", "B", "C")
N_UNPROF, N_PROF = 5, 3          # rule S1 minima
S_MIN = 5000                      # rule S2
TOL = 0.25                        # S-H2 tolerance
FCAP_MAX = 0.95


# ------------------------------------------------------------------ statistics (stdlib only)
def _betacf(a, b, x):
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c; c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c; c = c if abs(c) > tiny else tiny
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-14:
            break
    return h


def betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    return bt * _betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - bt * _betacf(b, a, 1 - x) / b


def t_cdf(t, df):
    p = 0.5 * betai(df / 2.0, 0.5, df / (df + t * t))
    return 1 - p if t > 0 else p


def t975(df):
    """Two-sided 95% Student t quantile for real df > 0 (bisection on the exact cdf)."""
    lo, hi = 0.0, 1e4
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_cdf(mid, df) < 0.975:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def mean_sd_n(xs):
    return statistics.fmean(xs), (statistics.stdev(xs) if len(xs) > 1 else float("nan")), len(xs)


def welch(a, b):
    """mean(a) - mean(b), its 95% CI (Welch-Satterthwaite df, exact t)."""
    ma, sa, na = mean_sd_n(a); mb, sb, nb = mean_sd_n(b)
    va, vb = sa * sa / na, sb * sb / nb
    se = math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va * va / (na - 1) + vb * vb / (nb - 1))
    t = t975(df)
    return ma - mb, se, df, ma - mb - t * se, ma - mb + t * se


def ci_mean(xs):
    m, s, n = mean_sd_n(xs)
    se = s / math.sqrt(n)
    t = t975(n - 1)
    return m, se, m - t * se, m + t * se


def selftest():
    bad = 0
    for df in range(1, 31):
        want, got = summ.T975[df - 1], t975(df)
        ok = abs(want - got) < 0.0006
        bad += not ok
        if not ok or df in (1, 5, 10, 30):
            print("%s df=%d table %.3f computed %.4f" % ("PASS" if ok else "FAIL", df, want, got))
    ok = abs(t975(1e6) - 1.95996) < 1e-3
    bad += not ok
    print("%s df=1e6 -> %.5f (normal 1.95996)" % ("PASS" if ok else "FAIL", t975(1e6)))
    print("selftest: %d FAIL" % bad)
    return 1 if bad else 0


# ------------------------------------------------------------------ run loading
EXEMPT = {"N": ("V2 no FINAL line from the capture process", "V2 map counters unreadable")}


def run_info(path, cfg, profiled):
    r = summ.parse_run(str(path))
    if r["cfg"] != cfg:
        sys.exit("FATAL: %s has cfg=%s, expected %s" % (path, r["cfg"], cfg))
    kept, dropped = [], []
    for x in r["reasons"]:
        if cfg == "N" and x.startswith(EXEMPT["N"]):
            dropped.append(x)
        elif profiled and x.startswith("V8 canary"):
            dropped.append(x)
        else:
            kept.append(x)
    r["reasons_kept"], r["reasons_exempt"] = kept, dropped
    if cfg == "N" and len(dropped) != 2 and r.get("window_s") is not None:
        # N must show exactly the two documented V2 reasons (no capture section, no map counters); anything else changed in the harness
        if not all(any(x.startswith(e) for x in dropped) for e in EXEMPT["N"]):
            sys.exit("FATAL: config N run %s does not show the two expected V2 reasons: %s" % (path, r["reasons"]))
    w = r.get("window_s")
    pc = r.get("busy_sec_per_cpu", {})
    r["sender_busy"] = ((pc.get("cpu1", 0) + pc.get("cpu4", 0)) / (2 * w)) if w else None
    return r


def parse_only(d, label):
    for cfg in CFGS:
        p = pathlib.Path(d) / ("%s_%s_flood_256_1.log" % (label, cfg))
        r = run_info(p, cfg, True)
        print("%s: offered %.0f pps over %.2f s, sender cores busy %.3f, V5' T=%s, reasons kept=%s exempt=%d" % (
            p.name, r.get("offered_pps", float("nan")), r["window_s"], r["sender_busy"], r.get("cls_T"), r["reasons_kept"], len(r["reasons_exempt"])))


# ------------------------------------------------------------------ main
def fmt(x, d=0):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else ("%.*f" % (d, x))


def main():
    outs = [pathlib.Path("results/p8_2_summary%s.md" % SUF), pathlib.Path("results/p8_2_summary%s.json" % SUF)]
    for o in outs:
        o.unlink(missing_ok=True)
    plan = [l.split("\t") for l in open("results/p8_2_plan%s.tsv" % SUF).read().splitlines() if l and not l.startswith("#")]
    if len(plan) != 40:
        sys.exit("FATAL: plan has %d rows" % len(plan))
    runs, missing = {}, []
    for seq, prof, cfg, rep in plan:
        prof = int(prof)
        label = "p82prof" if prof else "p82"
        p = L / "runs" / ("%s_%s_flood_256_%s.log" % (label, cfg, rep))
        if not p.exists():
            missing.append(p.name)
            continue
        if not p.read_text().rstrip().splitlines()[-1].startswith("# end="):
            sys.exit("FATAL: %s is incomplete (no # end= footer)" % p)
        r = run_info(p, cfg, bool(prof))
        r["prof"], r["rep"], r["seq"] = prof, int(rep), int(seq)
        if prof:
            cj = L / "profiles" / ("%s_%s_flood_256_%s_a1.json" % (label, cfg, rep))
            r["counts"] = json.load(open(cj)) if cj.exists() else None
            if r["counts"] is None:
                r["reasons_kept"].append("S2 profile counts missing (%s)" % cj.name)
            elif r["counts"]["S"] < S_MIN:
                r["reasons_kept"].append("S2 only %d samples in S (< %d)" % (r["counts"]["S"], S_MIN))
        r["valid"] = not r["reasons_kept"]
        runs[(prof, cfg, int(rep))] = r
    attempts = sorted(os.listdir(L / "attempts")) if (L / "attempts").is_dir() else []

    res = {"missing_logs": missing, "attempts": attempts, "cfg": {}}
    md = ["# Phase 8.2: is the flood's offered load limited by the capture taps in the sender's transmit path?\n",
          "Computed by `scripts/p8_2_summary.py` from `logs/p8/p8_2/` only; rules: `docs/phase8_2_design.md`. Offered rate = packets per second summed over both streams (client JSON packets / measured window), unprofiled valid runs; 95% intervals; Welch for differences.\n"]
    md.append("## 1. Runs\n")
    md.append("Plan rows: 40; final logs found: %d; missing: %s; earlier attempts kept in `attempts/` (V8 re-runs): %d.\n" % (len(runs), ", ".join(missing) or "none", len(attempts)))
    md.append("| config | unprofiled valid / planned | profiled valid / planned | exclusions (final attempts) |")
    md.append("|---|---|---|---|")
    off, fshare, sbusy, offprof = {}, {}, {}, {}
    insufficient = []
    for cfg in CFGS:
        u = [runs[k] for k in sorted(runs) if k[0] == 0 and k[1] == cfg]
        p = [runs[k] for k in sorted(runs) if k[0] == 1 and k[1] == cfg]
        uv, pv = [r for r in u if r["valid"]], [r for r in p if r["valid"]]
        off[cfg] = [r["offered_pps"] for r in uv]
        offprof[cfg] = [r["offered_pps"] for r in pv]
        sbusy[cfg] = [r["sender_busy"] for r in uv]
        fshare[cfg] = [r["counts"]["f_tap"] for r in pv]
        ex = ["%s%s rep%d: %s" % ("prof " if r["prof"] else "", cfg, r["rep"], "; ".join(r["reasons_kept"])) for r in u + p if not r["valid"]]
        md.append("| %s | %d / 6 | %d / 4 | %s |" % (cfg, len(uv), len(pv), "<br>".join(ex) or "none"))
        if cfg in "NAB" and (len(uv) < N_UNPROF or len(pv) < N_PROF):
            insufficient.append("%s: %d valid unprofiled (need %d), %d valid profiled (need %d)" % (cfg, len(uv), N_UNPROF, len(pv), N_PROF))
    md.append("")
    md.append("## 2. Offered rate (unprofiled valid runs)\n")
    md.append("| config | n | mean offered pps | sd | 95% CI of the mean | sender cores {1,4} busy (CPU-s/s per core) | profiled runs: mean offered pps | profiling effect |")
    md.append("|---|---|---|---|---|---|---|---|")
    for cfg in CFGS:
        if len(off[cfg]) >= 2:
            m, se, lo, hi = ci_mean(off[cfg])
            sd = statistics.stdev(off[cfg])
            pr = statistics.fmean(offprof[cfg]) if offprof[cfg] else float("nan")
            md.append("| %s | %d | %s | %s | [%s, %s] | %s | %s | %s |" % (cfg, len(off[cfg]), fmt(m), fmt(sd), fmt(lo), fmt(hi), fmt(statistics.fmean(sbusy[cfg]), 3), fmt(pr), fmt(pr / m, 3) if offprof[cfg] else "n/a"))
        else:
            md.append("| %s | %d | n/a | n/a | n/a | n/a | n/a | n/a |" % (cfg, len(off[cfg])))
    res["offered"] = {c: off[c] for c in CFGS}
    md.append("")

    # ---------------- H1
    md.append("## 3. S-H1: offered(N) above offered(A) and above offered(B)\n")
    h1 = {}
    md.append("| comparison | mean difference | 95% CI | Welch df | lower bound above 0 |")
    md.append("|---|---|---|---|---|")
    for x in ("A", "B", "C"):
        if len(off["N"]) >= 2 and len(off[x]) >= 2:
            d, se, df, lo, hi = welch(off["N"], off[x])
            h1[x] = {"diff": d, "lo": lo, "hi": hi, "df": df, "above0": lo > 0}
            md.append("| N - %s%s | %s | [%s, %s] | %s | %s |" % (x, "" if x != "C" else " (not gating)", fmt(d), fmt(lo), fmt(hi), fmt(df, 1), "yes" if lo > 0 else "no"))
        else:
            md.append("| N - %s | n/a | n/a | n/a | n/a |" % x)
    H1_eval = all(x in h1 for x in ("A", "B"))
    H1 = H1_eval and all(h1[x]["above0"] for x in ("A", "B"))
    if H1_eval:
        md.append("\n**S-H1 %s.**\n" % ("holds" if H1 else "does not hold"))
    else:   # amendment A2 item 7: not evaluable is not the same as "does not hold"
        md.append("\n**S-H1 is not evaluable** (%s).\n" % "; ".join("%s: %d valid unprofiled runs" % (x, len(off[x])) for x in ("N", "A", "B") if len(off[x]) < 2))
    res["h1"] = {"holds": H1, "evaluable": H1_eval, "tests": h1}

    # ---------------- profiles and H2
    md.append("## 4. Profiles: share of sender samples with `packet_rcv` in the stack (profiled valid runs)\n")
    md.append("| config | n | f_X mean | 95% CI | samples in S per run (min) | per-run f | informational: receiver-side UDP share | tap share among iperf3 samples only |")
    md.append("|---|---|---|---|---|---|---|---|")
    fstat = {}
    for cfg in CFGS:
        pv = [r for k, r in sorted(runs.items()) if k[0] == 1 and k[1] == cfg and r["valid"]]
        if len(pv) >= 2:
            m, se, lo, hi = ci_mean(fshare[cfg])
            fstat[cfg] = {"m": m, "se": se, "n": len(pv), "lo": lo, "hi": hi}
            rx = statistics.fmean(r["counts"]["f_rx"] for r in pv)
            md.append("| %s | %d | %.4f | [%.4f, %.4f] | %d | %s | %.4f | %s |" % (cfg, len(pv), m, lo, hi, min(r["counts"]["S"] for r in pv), ", ".join("%.4f" % v for v in fshare[cfg]), rx,
                      fmt(statistics.fmean(r["counts"].get("tap_iperf3", float("nan")) / max(1, r["counts"].get("S_iperf3", 1)) for r in pv), 4)))
        else:
            md.append("| %s | %d | n/a | n/a | n/a | n/a | n/a | n/a |" % (cfg, len(pv)))
    md.append("")
    md.append("## 5. S-H2: predicted P = 1/(1 - f_cap) against observed R = offered(N)/offered(X); tolerance %d%% on R/P\n" % int(TOL * 100))
    md.append("f_cap(X) = (f_X - f_N)/(1 - f_N). Unadjusted prediction 1/(1 - f_X) shown for comparison (not gating).\n")
    md.append("| X | f_cap [95%] | P = 1/(1-f_cap) [95%] | R [95%, delta method] | R/P - 1 | within tolerance | unadjusted P' | R/P' - 1 | gating |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    h2 = {}
    reasons_ne = []
    for x in ("A", "B", "C"):
        gate = x in ("A", "B")
        if "N" not in fstat or x not in fstat or len(off["N"]) < 2 or len(off[x]) < 2:
            md.append("| %s | n/a | n/a | n/a | n/a | not evaluable | n/a | n/a | %s |" % (x, "yes" if gate else "no"))
            if gate:
                reasons_ne.append("%s: missing profile or offered data" % x)
            continue
        fx, fn = fstat[x], fstat["N"]
        fcap = (fx["m"] - fn["m"]) / (1 - fn["m"])
        se_f = math.sqrt((fx["se"] / (1 - fn["m"])) ** 2 + (((fx["m"] - 1) / (1 - fn["m"]) ** 2) * fn["se"]) ** 2)
        tdf = t975(min(fx["n"], fn["n"]) - 1)
        flo, fhi = fcap - tdf * se_f, fcap + tdf * se_f
        P = 1 / (1 - fcap) if fcap < 1 else float("inf")
        Plo = 1 / (1 - flo) if flo < 1 else float("inf")
        Phi = 1 / (1 - fhi) if fhi < 1 else float("inf")
        mN, sN, nN = mean_sd_n(off["N"]); mX, sX, nX = mean_sd_n(off[x])
        R = mN / mX
        vN, vX = sN * sN / nN, sX * sX / nX
        dfw = (vN + vX) ** 2 / (vN * vN / (nN - 1) + vX * vX / (nX - 1))
        seR = R * math.sqrt(vN / mN ** 2 + vX / mX ** 2)
        Rlo, Rhi = R - t975(dfw) * seR, R + t975(dfw) * seR
        Pu = 1 / (1 - fx["m"])
        ok = abs(R / P - 1) <= TOL if math.isfinite(P) else False
        ne = []
        if fcap >= FCAP_MAX:
            ne.append("f_cap %.3f >= %.2f" % (fcap, FCAP_MAX))
        if fhi < 0:
            ne.append("f_cap negative with its whole interval below 0")
        h2[x] = {"fcap": fcap, "fcap_lo": flo, "fcap_hi": fhi, "P": P, "P_lo": Plo, "P_hi": Phi, "R": R, "R_lo": Rlo, "R_hi": Rhi,
                 "R_over_P_minus_1": R / P - 1 if math.isfinite(P) else None, "within": ok, "not_evaluable": ne, "P_unadjusted": Pu, "R_over_Pu_minus_1": R / Pu - 1}
        if gate and ne:
            reasons_ne.append("%s: %s" % (x, "; ".join(ne)))
        md.append("| %s | %.4f [%.4f, %.4f] | %.3f [%.3f, %.3f] | %.3f [%.3f, %.3f] | %+.1f%% | %s | %.3f | %+.1f%% | %s |" % (
            x, fcap, flo, fhi, P, Plo, Phi, R, Rlo, Rhi, 100 * (R / P - 1), "not evaluable" if ne else ("yes" if ok else "no"), Pu, 100 * (R / Pu - 1), "yes" if gate else "no"))
    H2_eval = all(x in h2 and not h2[x]["not_evaluable"] for x in ("A", "B")) and not reasons_ne
    H2 = H2_eval and all(h2[x]["within"] for x in ("A", "B"))
    md.append("\n**S-H2 %s.**\n" % ("holds" if H2 else ("is not evaluable (%s)" % "; ".join(reasons_ne)) if not H2_eval else "does not hold"))
    res["h2"] = {"holds": H2, "evaluable": H2_eval, "not_evaluable_reasons": reasons_ne, "tests": h2}

    # ---------------- verdict S3
    if insufficient:
        verdict, why = "INCONCLUSIVE", "; ".join(insufficient)
    elif not H1_eval:
        verdict, why = "INCONCLUSIVE", "S-H1 not evaluable"
    elif not H1:
        verdict, why = "NOT SUPPORTED", "S-H1 fails"
    elif H2:
        verdict, why = "SENDER-LIMITED SUPPORTED", "S-H1 and S-H2 hold"
    else:
        verdict, why = "MIXED", "S-H1 holds; S-H2 " + ("does not hold" if H2_eval else "not evaluable")
    md.append("## 6. Verdict (rule S3)\n\n**%s** (%s).\n" % (verdict, why))
    md.append("Limits (design section 6): single host, VM, veth, one session; `cpu-clock` timer sampling without a hardware PMU (skew not measured, UNVERIFIED); profiled runs perturb the system and f is measured under profiling but applied to unprofiled rates; the classifier tap is in every config and f_cap assumes its per-packet cost is equal in N and in A/B; the prediction assumes saturated sender cores (busy column above) and serial removable work.\n")
    res["verdict"], res["verdict_reason"] = verdict, why
    outs[0].write_text("\n".join(md) + "\n")
    outs[1].write_text(json.dumps(res, indent=1, default=str))
    for o in outs:
        if not o.exists() or o.stat().st_size == 0:
            sys.exit("FATAL: %s was not written" % o)
    print("\n".join(md))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    if len(sys.argv) > 1 and sys.argv[1] == "--parse-only":
        parse_only(sys.argv[2], sys.argv[3])
    else:
        main()
