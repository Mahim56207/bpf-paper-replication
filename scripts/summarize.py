#!/usr/bin/env python3
"""Phase 6 summariser. Reads ONLY logs/bench_*.log (and results/calibration.json when present).
Every number in its output is computed from those files. The only literals are the pre-declared
validity thresholds and statistical constants below, which are copied from docs/phase6_design.md
(amended by reviewer rulings D6.1) and printed with the results.

Usage: python3 -I scripts/summarize.py            # logs/bench_*.log -> results/{runs.json,summary.json,summary.md,exclusions.md,verdicts.md}
       python3 -I scripts/summarize.py calibrate  # logs/bench_A_cal_*.log -> results/calibration.json
       python3 -I scripts/summarize.py smoke      # logs/smoke_*.log -> results/smoke.md (SMOKE: excluded from analysis)
"""
import glob
import json
import math
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
RESULTS = ROOT / "results"

# ---- pre-declared validity thresholds (docs/phase6_design.md section 5) -------------------------
OFFERED_PPS_TOL = 0.05        # V3: curve runs: offered pps within +-5% of the target
DROP_FRAC_MAX = 0.001         # V4: curve runs: capture-socket drops <= 0.1% of packets that reached it
CONSERVATION_ABS = 20         # V5: |tap total - offered| <= max(20, 0.5% x offered)
CONSERVATION_FRAC = 0.005
WINDOW_TOL_S = (-1.0, 2.0)    # V6: measured window within dur-1 .. dur+2 s
STEAL_MAX_PCT = 5.0           # V7 (D6.1 item 6): exclude runs whose steal time > 5% of capacity
STEAL_CONFIG_EXCL_MAX = 0.20  # D6.1 item 6: > 20% steal exclusions in a config => config INCONCLUSIVE
MIN_VALID_REPS = 2            # a point with fewer valid reps is INCONCLUSIVE
CLASSES_CURVE = ("nm", "m")
# two-sided 95% Student t critical values for df = 1..30 (statistical constants); df > 30 uses 1.96
T975 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131,
        2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def tcrit(df):
    df = int(df)
    return T975[df - 1] if 1 <= df <= 30 else (1.96 if df > 30 else float("nan"))


# ---------------------------------------------------------------- parsing
def sections(text):
    out, cur = {}, None
    for line in text.splitlines():
        if line.startswith("### "):
            cur = line[4:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return {k: "\n".join(v).strip("\n") for k, v in out.items()}


def header(text):
    h = {}
    for line in text.splitlines():
        if line.startswith("# ") and "=" in line:
            h.update(dict(re.findall(r"(\w+)=(\S+)", line)))
    return h


def kv_ints(line):
    return {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", line)}


def parse_stat(block):
    d = {"cpu": {}}
    for line in block.splitlines():
        if line.startswith("time "):
            d["time"] = float(line.split()[1])
        elif re.match(r"^cpu\d* ", line):
            f = line.split()
            d["cpu"][f[0]] = [int(x) for x in f[1:9]]  # user nice system idle iowait irq softirq steal
        elif line.startswith("ctxt "):
            d["ctxt"] = int(line.split()[1])
        elif line.startswith("pid_stat "):
            rest = line.split(")", 1)[1].split()
            d["pid_ticks"] = int(rest[11]) + int(rest[12])  # utime + stime
        elif line.startswith("voluntary_ctxt_switches"):
            d["vol"] = int(line.split()[1])
        elif line.startswith("nonvoluntary_ctxt_switches"):
            d["nvol"] = int(line.split()[1])
    return d


def busy(v):
    return v[0] + v[1] + v[2] + v[5] + v[6] + v[7]


def parse_json(block):
    try:
        return json.loads(block)
    except (ValueError, TypeError):
        return None


def pidstat_avg(block, cols):
    hdr = None
    for line in block.splitlines():
        if line.startswith("Average:") and "PID" in line:
            hdr = line.split()[1:]
        elif line.startswith("Average:") and hdr:
            f = line.split()[1:]
            if len(f) == len(hdr):
                return {c: float(f[hdr.index(c)]) for c in cols if c in hdr}
    return {}


def vmstat_cs(block):
    hdr, vals = None, []
    for line in block.splitlines():
        f = line.split()
        if f and f[0] == "r":
            hdr = f
        elif f and hdr and f[0].isdigit():
            vals.append(int(f[hdr.index("cs")]))
    return statistics.mean(vals[1:]) if len(vals) > 1 else None  # first line = average since boot


def map_counters(block):
    data = parse_json(block)
    if not data:
        return None
    out = {}
    for e in data:
        f = e.get("formatted", e)
        out[int(f["key"])] = int(f["value"])
    return out if 0 in out and 1 in out else None


def parse_run(path):
    text = Path(path).read_text()
    h, s = header(text), sections(text)
    r = {"file": Path(path).name, "label": h.get("label", "bench"), "cfg": h.get("cfg"), "traffic": h.get("traffic"),
         "size": int(h.get("size", 0)), "rep": int(h.get("rep", 0)), "pps_target": int(h.get("pps_target", 0)),
         "dur": int(h.get("dur", 0)), "reasons": []}
    clk = int(h.get("clk_tck", 100))
    cap = s.get("capture", "")
    fin = next((l for l in cap.splitlines() if l.startswith("FINAL ") or l.startswith("FINAL t=")), None)
    sock = next((l for l in cap.splitlines() if l.startswith("FINAL_SOCKET") or l.startswith("FINAL_KERNEL")), None)
    if not fin:
        r["reasons"].append("V2 no FINAL line from the capture process")
    cnt = kv_ints(fin) if fin else {}
    sk = kv_ints(sock) if sock else {}
    r["kernel_drops"], r["kernel_packets"] = sk.get("kernel_drops"), sk.get("kernel_packets")
    b, a = parse_stat(s.get("stat_before", "")), parse_stat(s.get("stat_after", ""))
    if "time" in b and "time" in a:
        w = r["window_s"] = a["time"] - b["time"]
        ncpu = len([c for c in a["cpu"] if c != "cpu"])
        busy_cpu = {c: (busy(a["cpu"][c]) - busy(b["cpu"][c])) / clk for c in a["cpu"] if c in b["cpu"]}
        r["busy_sec_total"] = busy_cpu.get("cpu", 0.0)
        r["busy_sec_per_cpu"] = {c: v for c, v in busy_cpu.items() if c != "cpu"}
        steal = (a["cpu"]["cpu"][7] - b["cpu"]["cpu"][7]) / clk
        r["steal_pct"] = 100.0 * steal / (w * ncpu) if ncpu else None
        if "ctxt" in a and "ctxt" in b:
            r["sys_cs_per_s"] = (a["ctxt"] - b["ctxt"]) / w
        if "pid_ticks" in a and "pid_ticks" in b:
            r["proc_cpu_sec"] = (a["pid_ticks"] - b["pid_ticks"]) / clk
            r["proc_cpu_pct"] = 100.0 * r["proc_cpu_sec"] / w
        if "vol" in a and "vol" in b:
            r["proc_cs_per_s"] = ((a["vol"] + a["nvol"]) - (b["vol"] + b["nvol"])) / w
    else:
        r["reasons"].append("V2 stat snapshots missing")
    if r["cfg"] == "A":
        r["tap_total"] = r["kernel_packets"]
        r["matched"] = cnt.get("matched_packets")
        r["processed_by_proc"] = cnt.get("total_packets")
        r["filter_dropped"] = None
        r["delivered"] = cnt.get("matched_packets")
    else:
        mb, ma = map_counters(s.get("map_before", "")), map_counters(s.get("map_after", ""))
        if mb and ma:
            r["filter_dropped"], r["matched"] = ma[0] - mb[0], ma[1] - mb[1]
            r["tap_total"] = r["filter_dropped"] + r["matched"]
        else:
            r["reasons"].append("V2 map counters unreadable")
        r["delivered"] = cnt.get("delivered_packets")
        r["processed_by_proc"] = cnt.get("delivered_packets")
    pa = pidstat_avg(s.get("pidstat", ""), ("%CPU",))
    pw = pidstat_avg(s.get("pidstat_w", ""), ("cswch/s", "nvcswch/s"))
    r["pidstat_cpu_pct"], r["pidstat_cswch"], r["pidstat_nvcswch"] = pa.get("%CPU"), pw.get("cswch/s"), pw.get("nvcswch/s")
    r["vmstat_cs"] = vmstat_cs(s.get("vmstat", ""))
    offered, veth_rx, ok = 0, 0, True
    for key, blk in s.items():
        if key.startswith("client_json_") or key.startswith("server_json_"):
            j = parse_json(blk)
            if not j or "end" not in j:
                ok = False
                r["reasons"].append(f"V1 {key} unparsable")
            elif key.startswith("client_json_"):
                offered += j["end"]["sum"]["packets"]
            else:
                sm = j["end"]["sum"]
                veth_rx += sm["packets"] - sm.get("lost_packets", 0)
    ce = [int(x.split()[1]) for x in s.get("client_exit", "").splitlines() if x.startswith("client_exit")]
    if any(c != 0 for c in ce):
        r["reasons"].append("V1 iperf3 client exit != 0")
    r["offered_pkts"], r["veth_rx_pkts"] = offered, veth_rx
    w = r.get("window_s")
    if w and offered:
        r["offered_pps"] = offered / w
    if w and r.get("matched") is not None:
        r["matched_pps"] = r["matched"] / w
    if r.get("busy_sec_total") is not None and offered:
        r["cost_per_offered_ns"] = r["busy_sec_total"] * 1e9 / offered          # system-wide CPU ns per offered packet
    if r.get("busy_sec_total") is not None and r.get("matched"):
        r["cost_per_matched_ns"] = r["busy_sec_total"] * 1e9 / r["matched"]      # headline (D6.1 item 2)
    if r.get("proc_cpu_sec") is not None and r.get("processed_by_proc"):
        r["proc_cost_ns_pkt"] = r["proc_cpu_sec"] * 1e9 / r["processed_by_proc"]
    # ---- validity V3..V7
    if w is not None and not (r["dur"] + WINDOW_TOL_S[0] <= w <= r["dur"] + WINDOW_TOL_S[1]):
        r["reasons"].append(f"V6 window {w:.2f}s outside dur{WINDOW_TOL_S[0]:+g}..{WINDOW_TOL_S[1]:+g}")
    if r["traffic"] in CLASSES_CURVE + ("warmup",) and r["pps_target"] and r.get("offered_pps"):
        if abs(r["offered_pps"] - r["pps_target"]) > OFFERED_PPS_TOL * r["pps_target"]:
            r["reasons"].append(f"V3 offered {r['offered_pps']:.0f} pps vs target {r['pps_target']}")
    if r["traffic"] in CLASSES_CURVE and r["cfg"] != "C" and r.get("kernel_packets"):
        if r["kernel_drops"] and r["kernel_drops"] > DROP_FRAC_MAX * r["kernel_packets"]:
            r["reasons"].append(f"V4 socket drops {r['kernel_drops']} > {DROP_FRAC_MAX:.1%} of {r['kernel_packets']}")
    if r.get("tap_total") is not None and offered:
        allow = max(CONSERVATION_ABS, CONSERVATION_FRAC * offered)
        if abs(r["tap_total"] - offered) > allow:
            r["reasons"].append(f"V5 tap {r['tap_total']} vs offered {offered} (allowance {allow:.0f})")
    if r.get("steal_pct") is not None and r["steal_pct"] > STEAL_MAX_PCT:
        r["reasons"].append(f"V7 steal {r['steal_pct']:.1f}% > {STEAL_MAX_PCT:g}%")
    r["valid"] = not r["reasons"]
    return r


# ---------------------------------------------------------------- statistics
def ms(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None, 0
    return statistics.mean(xs), (statistics.stdev(xs) if len(xs) > 1 else None), len(xs)


def fmt(m, sd, n, digits=1):
    if m is None:
        return "n/a"
    s = f"{m:.{digits}f}"
    return f"{s} ± {sd:.{digits}f} (n={n})" if sd is not None else f"{s} (n={n})"


def ols(points):
    n = len(points)
    if n < 4:
        return None
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    if sxx == 0:
        return None
    slope = sum((p[0] - mx) * (p[1] - my) for p in points) / sxx
    icpt = my - slope * mx
    sse = sum((p[1] - (icpt + slope * p[0])) ** 2 for p in points)
    sst = sum((p[1] - my) ** 2 for p in points)
    s2 = sse / (n - 2)
    return {"slope": slope, "intercept": icpt, "se_slope": math.sqrt(s2 / sxx),
            "se_int": math.sqrt(s2 * (1.0 / n + mx * mx / sxx)), "r2": (1 - sse / sst) if sst else None, "n": n, "df": n - 2}


def slope_ci(f):
    h = tcrit(f["df"]) * f["se_slope"]
    return f["slope"] - h, f["slope"] + h


def welch_diff_ci(a, b):
    """a, b: (mean, sd, n). CI for mean_a - mean_b (Welch)."""
    if a[0] is None or b[0] is None or a[2] < 2 or b[2] < 2 or a[1] is None or b[1] is None:
        return None
    va, vb = a[1] ** 2 / a[2], b[1] ** 2 / b[2]
    se = math.sqrt(va + vb)
    if se == 0:
        return a[0] - b[0], a[0] - b[0], a[0] - b[0]
    df = (va + vb) ** 2 / (va ** 2 / (a[2] - 1) + vb ** 2 / (b[2] - 1))
    h = tcrit(math.floor(df)) * se
    return a[0] - b[0] - h, a[0] - b[0], a[0] - b[0] + h


def ratio_ci(a, b):
    """CI for mean_a / mean_b by the delta method; df = min(n)-1."""
    if a[0] is None or b[0] is None or not b[0] or a[1] is None or b[1] is None or a[2] < 2 or b[2] < 2:
        return None
    r = a[0] / b[0]
    se = abs(r) * math.sqrt((a[1] ** 2 / a[2]) / a[0] ** 2 + (b[1] ** 2 / b[2]) / b[0] ** 2)
    h = tcrit(min(a[2], b[2]) - 1) * se
    return r - h, r, r + h


def f3(x):
    return "n/a" if x is None else f"{x:.3g}"


# ---------------------------------------------------------------- calibration
def calibrate():
    runs = [parse_run(f) for f in sorted(glob.glob(str(LOGS / "bench_A_cal_*.log")))]
    if not runs:
        print("no logs/bench_A_cal_*.log found")
        return 1
    knees = {}
    for size in sorted({r["size"] for r in runs}):
        steps = sorted((r for r in runs if r["size"] == size), key=lambda r: r["pps_target"])
        knee = None
        for r in steps:
            frac = (r["kernel_drops"] or 0) / r["kernel_packets"] if r.get("kernel_packets") else 1.0
            if [x for x in r["reasons"] if not x.startswith("V4")] or frac > DROP_FRAC_MAX:
                break
            knee = r["pps_target"]
        knees[size] = {"knee_pps": knee, "ladder_top_reached": bool(knee) and knee == steps[-1]["pps_target"],
                       "steps": [{"pps": r["pps_target"], "offered_pps": r.get("offered_pps"), "kernel_drops": r["kernel_drops"],
                                  "kernel_packets": r["kernel_packets"], "reasons": r["reasons"]} for r in steps]}
    usable = [k["knee_pps"] for k in knees.values() if k["knee_pps"]]
    if len(usable) != len(knees):
        print("calibration FAILED: no loss-free step for some size; see steps in results/calibration.json")
    p_curve = int(0.5 * min(usable) // 100 * 100) if usable else None
    out = {"knees": {str(k): v for k, v in knees.items()}, "p_curve": p_curve,
           "rule": "p_curve = floor(0.5 * min over sizes of A's loss-free ceiling / 100) * 100; a step is loss-free if it passed "
                   "V1-V3,V5-V7 and kernel_drops <= 0.1% of kernel_packets; the ceiling is the highest step reached without a "
                   "failing step below it. Calibration data is not result data."}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "calibration.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({"p_curve": p_curve, "knees": {k: v["knee_pps"] for k, v in knees.items()}}))
    return 0 if p_curve else 1


# ---------------------------------------------------------------- smoke
def smoke():
    files = sorted(glob.glob(str(LOGS / "smoke_*.log")))
    if not files:
        print("no logs/smoke_*.log found")
        return 1
    runs = [parse_run(f) for f in files]
    md = ["# SMOKE runs (excluded from analysis by pre-declaration)", "",
          "Parsed by `summarize.py smoke` from logs/smoke_*.log. These runs check the plumbing only; no verdict uses them.", "",
          "| file | cfg | traffic | size | window s | offered pps | tap total | matched | filter drops | delivered | socket drops | system busy s | steal % | proc CPU % | proc cs/s | sys cs/s | per offered ns | per matched ns | parse result |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]

    def g(v, d=0):
        return "n/a" if v is None else f"{v:.{d}f}"
    for r in runs:
        md.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r["file"], r["cfg"], r["traffic"], r["size"], g(r.get("window_s"), 2), g(r.get("offered_pps")), r.get("tap_total"),
            r.get("matched"), r.get("filter_dropped"), r.get("delivered"), r.get("kernel_drops"), g(r.get("busy_sec_total"), 2),
            g(r.get("steal_pct"), 2), g(r.get("proc_cpu_pct"), 1), g(r.get("proc_cs_per_s")), g(r.get("sys_cs_per_s")),
            g(r.get("cost_per_offered_ns")), g(r.get("cost_per_matched_ns")),
            "valid" if r["valid"] else "; ".join(r["reasons"])))
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "smoke.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0 if all(r["valid"] for r in runs) else 2


# ---------------------------------------------------------------- summary
def main():
    files = [f for f in sorted(glob.glob(str(LOGS / "bench_*.log"))) if "_cal_" not in f]
    if not files:
        print("no logs/bench_*.log found: nothing to summarise")
        return 0
    runs = [parse_run(f) for f in files]
    measured = [r for r in runs if r["traffic"] in ("nm", "m", "flood")]
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "runs.json").write_text(json.dumps(runs, indent=1))

    # ---- config-level steal rule (D6.1 item 6)
    cfg_steal = {}
    for cfg in "ABCDE":
        rs = [r for r in measured if r["cfg"] == cfg]
        ex = [r for r in rs if any(x.startswith("V7") for x in r["reasons"])]
        cfg_steal[cfg] = (len(ex), len(rs), bool(rs) and len(ex) / len(rs) > STEAL_CONFIG_EXCL_MAX)
    bad_cfg = {c for c, (_, _, bad) in cfg_steal.items() if bad}

    def group(cfg, traffic, size):
        if cfg in bad_cfg:
            return []
        return [r for r in measured if r["valid"] and (r["cfg"], r["traffic"], r["size"]) == (cfg, traffic, size)]

    sizes = sorted({r["size"] for r in measured if r["traffic"] in CLASSES_CURVE})

    # ---- exclusions.md
    ex = ["# Excluded runs", "",
          "Every run that did not pass the pre-declared validity rules (V1-V7, docs/phase6_design.md section 5), with the rule(s) that failed. "
          "Warm-up runs, calibration runs and smoke runs are excluded by pre-declaration and not listed here.", "",
          "| file | cfg | traffic | size | rep | rule(s) |", "|---|---|---|---|---|---|"]
    n_ex = 0
    for r in measured:
        if not r["valid"]:
            n_ex += 1
            ex.append(f"| {r['file']} | {r['cfg']} | {r['traffic']} | {r['size']} | {r['rep']} | {'; '.join(r['reasons'])} |")
    if n_ex == 0:
        ex.append("| (none) | | | | | |")
    ex += ["", "Config-level steal rule (V7): runs excluded for steal > %g%% / measured runs per config:" % STEAL_MAX_PCT, ""]
    for cfg, (k, n, bad) in cfg_steal.items():
        ex.append(f"- {cfg}: {k} / {n}" + (" -> **config INCONCLUSIVE** (> %d%%)" % round(100 * STEAL_CONFIG_EXCL_MAX) if bad else ""))
    (RESULTS / "exclusions.md").write_text("\n".join(ex) + "\n")

    md = ["# Phase 6 summary", "",
          "Generated by scripts/summarize.py from logs/bench_*.log. Mean ± sd over valid reps (n = valid reps). Costs are system-wide CPU time "
          "(sum over all CPUs of user+nice+system+irq+softirq+steal) divided by packets; the headline metric is CPU ns per MATCHED packet "
          "(non-matching traffic has no matched packets, so the reject curve uses CPU ns per OFFERED packet). D is a floor, not a paper control. "
          "Intervals are 95% (Student t).", ""]
    md += ["## Validity", "", "| cfg | traffic | size | runs | valid | rules failed |", "|---|---|---|---|---|---|"]
    keys = sorted({(r["cfg"], r["traffic"], r["size"]) for r in measured}, key=lambda k: (k[1], k[0], k[2]))
    for k in keys:
        allr = [r for r in measured if (r["cfg"], r["traffic"], r["size"]) == k]
        why = sorted({x.split(" ")[0] for r in allr if not r["valid"] for x in r["reasons"]})
        md.append(f"| {k[0]} | {k[1]} | {k[2]} | {len(allr)} | {sum(r['valid'] for r in allr)} | {', '.join(why) or '-'} |")
    for c in sorted(bad_cfg):
        md.append(f"\nConfig {c}: INCONCLUSIVE ({cfg_steal[c][0]} of {cfg_steal[c][1]} runs excluded for steal time).")

    floor = {}   # D (non-matching) mean cost per offered packet, per size
    for size in sizes:
        m = ms([r.get("cost_per_offered_ns") for r in group("D", "nm", size)])
        if m[2] >= MIN_VALID_REPS:
            floor[size] = m

    fits = {"nm": {}, "m": {}}
    # ---------------- reject curve
    md += ["", "## Reject curve: non-matching UDP (C2)", "",
           "| cfg | size | offered pps | system CPU ns / offered pkt | over D floor ns / pkt | capture-proc CPU % | proc cs/s | sys cs/s | socket drops | filter drops (slot0) |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    pts_nm = {"A": [], "B": [], "D": []}
    for cfg in "ABD":
        for size in sizes:
            g = group(cfg, "nm", size)
            if len(g) < MIN_VALID_REPS:
                md.append(f"| {cfg} | {size} | INCONCLUSIVE (valid reps {len(g)} < {MIN_VALID_REPS}) | | | | | | | |")
                continue
            cost = ms([r.get("cost_per_offered_ns") for r in g])
            over = None
            if size in floor and cfg != "D":
                over = (cost[0] - floor[size][0], math.sqrt((cost[1] or 0) ** 2 / cost[2] + (floor[size][1] or 0) ** 2 / floor[size][2]))
            for r in g:
                if r.get("cost_per_offered_ns") is None:
                    continue
                if cfg == "D":
                    pts_nm["D"].append((size, r["cost_per_offered_ns"]))
                elif size in floor:
                    pts_nm[cfg].append((size, r["cost_per_offered_ns"] - floor[size][0]))
            md.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                cfg, size, fmt(*ms([r.get("offered_pps") for r in g]), 0), fmt(*cost, 0),
                (f"{over[0]:.0f} ± {over[1]:.0f} (SE)" if over else ("floor" if cfg == "D" else "n/a")),
                fmt(*ms([r.get("proc_cpu_pct") for r in g]), 1), fmt(*ms([r.get("proc_cs_per_s") for r in g]), 0),
                fmt(*ms([r.get("sys_cs_per_s") for r in g]), 0), fmt(*ms([r.get("kernel_drops") for r in g]), 0),
                fmt(*ms([r.get("filter_dropped") for r in g]), 0)))
    md += ["", "Linear fits against frame size (ns per packet = intercept + slope x size), 95% interval on the slope:", "",
           "| series | slope ns/byte | 95% CI of slope | intercept ns/pkt | R² | n |", "|---|---|---|---|---|---|"]
    for cfg, label in (("A", "A over D"), ("B", "B over D"), ("D", "D floor (absolute)")):
        f = ols(pts_nm[cfg])
        fits["nm"][cfg] = f
        if f:
            lo, hi = slope_ci(f)
            md.append(f"| {label} | {f3(f['slope'])} | [{f3(lo)}, {f3(hi)}] | {f3(f['intercept'])} | {f3(f['r2'])} | {f['n']} |")
        else:
            md.append(f"| {label} | INCONCLUSIVE (too few valid points) | | | | |")

    # ---------------- accept curve
    md += ["", "## Accept curve: matching UDP (C3)", "",
           "| cfg | size | offered pps | system CPU ns / matched pkt | capture-proc CPU % | proc ns / delivered pkt | proc cs/s | sys cs/s | socket drops | filter drops (slot0) |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    pts_m = {"A": [], "B": [], "E": []}
    cost_m = {}
    for cfg in "ABE":
        for size in sizes:
            g = group(cfg, "m", size)
            if len(g) < MIN_VALID_REPS:
                md.append(f"| {cfg} | {size} | INCONCLUSIVE (valid reps {len(g)} < {MIN_VALID_REPS}) | | | | | | | |")
                continue
            cost = ms([r.get("cost_per_matched_ns") for r in g])
            cost_m[(cfg, size)] = cost
            for r in g:
                if r.get("cost_per_matched_ns") is not None:
                    pts_m[cfg].append((size, r["cost_per_matched_ns"]))
            md.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                cfg, size, fmt(*ms([r.get("offered_pps") for r in g]), 0), fmt(*cost, 0),
                fmt(*ms([r.get("proc_cpu_pct") for r in g]), 1), fmt(*ms([r.get("proc_cost_ns_pkt") for r in g]), 0),
                fmt(*ms([r.get("proc_cs_per_s") for r in g]), 0), fmt(*ms([r.get("sys_cs_per_s") for r in g]), 0),
                fmt(*ms([r.get("kernel_drops") for r in g]), 0), fmt(*ms([r.get("filter_dropped") for r in g]), 0)))
    md += ["", "Linear fits of system CPU ns per matched packet against frame size:", "",
           "| cfg | slope ns/byte | 95% CI of slope | intercept ns/pkt | 95% CI of intercept | R² | n |", "|---|---|---|---|---|---|---|"]
    for cfg in "ABE":
        f = ols(pts_m[cfg])
        fits["m"][cfg] = f
        if f:
            lo, hi = slope_ci(f)
            h = tcrit(f["df"]) * f["se_int"]
            md.append(f"| {cfg} | {f3(f['slope'])} | [{f3(lo)}, {f3(hi)}] | {f3(f['intercept'])} | [{f3(f['intercept'] - h)}, {f3(f['intercept'] + h)}] | {f3(f['r2'])} | {f['n']} |")
        else:
            md.append(f"| {cfg} | INCONCLUSIVE (too few valid points) | | | | | |")

    # ---------------- decomposition (D6.1 item 3): B only
    md += ["", "### Cost decomposition for config B (D6.1 item 3)", "",
           "copy-to-user cost = B(matching) - B(non-matching); parse+reject cost = B(non-matching) - D. Both per packet, same size, with the combined SE.", "",
           "| size | copy-to-user ns/pkt | parse+reject ns/pkt |", "|---|---|---|"]
    for size in sizes:
        bm, bn, d = cost_m.get(("B", size)), None, floor.get(size)
        gb = group("B", "nm", size)
        bn = ms([r.get("cost_per_offered_ns") for r in gb]) if len(gb) >= MIN_VALID_REPS else None
        # B(m): per matched packet equals per offered packet when all offered packets match; use the per-offered values for a like-for-like difference
        gbm = group("B", "m", size)
        bmo = ms([r.get("cost_per_offered_ns") for r in gbm]) if len(gbm) >= MIN_VALID_REPS else None
        cells = []
        for a, b in ((bmo, bn), (bn, d)):
            if a and b and a[0] is not None and b[0] is not None:
                se = math.sqrt((a[1] or 0) ** 2 / a[2] + (b[1] or 0) ** 2 / b[2])
                cells.append(f"{a[0] - b[0]:.0f} ± {se:.0f} (SE)")
            else:
                cells.append("INCONCLUSIVE")
        md.append(f"| {size} | {cells[0]} | {cells[1]} |")

    # ---------------- flood
    md += ["", "## Flood (C4): full-rate UDP, matching + noise streams", "",
           "| cfg | offered pps | matched pps (ceiling) | system CPU % of one core | system CPU ns / matched pkt | capture-proc CPU % | proc cs/s | sys cs/s | filter drops (slot0) | socket drops |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    fl = {}
    for cfg in "ABC":
        g = [] if cfg in bad_cfg else [r for r in measured if r["valid"] and r["cfg"] == cfg and r["traffic"] == "flood"]
        fl[cfg] = g
        if len(g) < MIN_VALID_REPS:
            md.append(f"| {cfg} | INCONCLUSIVE (valid reps {len(g)} < {MIN_VALID_REPS}) | | | | | | | | |")
            continue
        md.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            cfg, fmt(*ms([r.get("offered_pps") for r in g]), 0), fmt(*ms([r.get("matched_pps") for r in g]), 0),
            fmt(*ms([100 * r["busy_sec_total"] / r["window_s"] for r in g if r.get("window_s")]), 0),
            fmt(*ms([r.get("cost_per_matched_ns") for r in g]), 0), fmt(*ms([r.get("proc_cpu_pct") for r in g]), 1),
            fmt(*ms([r.get("proc_cs_per_s") for r in g]), 0), fmt(*ms([r.get("sys_cs_per_s") for r in g]), 0),
            fmt(*ms([r.get("filter_dropped") for r in g]), 0), fmt(*ms([r.get("kernel_drops") for r in g]), 0)))

    # ---------------- verdicts (shape/sign rules, 95% CIs only)
    V = {}
    # C2
    fa, fb, fd = fits["nm"].get("A"), fits["nm"].get("B"), fits["nm"].get("D")
    if fa and fb:
        a_lo, a_hi = slope_ci(fa)
        b_lo, b_hi = slope_ci(fb)
        a_grows, b_flat = a_lo > 0, b_lo <= 0 <= b_hi
        V["C2"] = ("SUPPORTED" if a_grows and b_flat else ("NOT SUPPORTED" if not a_grows else "MIXED"),
                   f"A-over-D slope {f3(fa['slope'])} ns/byte, 95% CI [{f3(a_lo)}, {f3(a_hi)}] (grows = CI excludes 0 on the positive side: {a_grows}); "
                   f"B-over-D slope {f3(fb['slope'])} ns/byte, 95% CI [{f3(b_lo)}, {f3(b_hi)}] (flat = CI contains 0: {b_flat})."
                   + (f" D floor slope {f3(fd['slope'])} ns/byte (generator and veth size dependence, removed by subtraction)." if fd else ""))
    else:
        V["C2"] = ("INCONCLUSIVE", "not enough valid points for the A and B fits")
    # C3
    ma_, mb_ = fits["m"].get("A"), fits["m"].get("B")
    if ma_ and mb_:
        a_lo, a_hi = slope_ci(ma_)
        b_lo, b_hi = slope_ci(mb_)
        d = ma_["intercept"] - mb_["intercept"]
        se = math.sqrt(ma_["se_int"] ** 2 + mb_["se_int"] ** 2)
        h = tcrit(min(ma_["df"], mb_["df"])) * se
        pos = a_lo > 0 and b_lo > 0
        order = d - h > 0
        V["C3"] = ("SUPPORTED" if pos and order else ("NOT SUPPORTED" if not (a_lo > 0 or b_lo > 0) else "MIXED"),
                   f"slope A {f3(ma_['slope'])} ns/byte [{f3(a_lo)}, {f3(a_hi)}], slope B {f3(mb_['slope'])} ns/byte [{f3(b_lo)}, {f3(b_hi)}] "
                   f"(both positive = CI excludes 0: {pos}); intercept A - intercept B = {f3(d)} ns/pkt, 95% CI [{f3(d - h)}, {f3(d + h)}] "
                   f"(A above B = CI excludes 0 on the positive side: {order}).")
    else:
        V["C3"] = ("INCONCLUSIVE", "not enough valid points for the A and B fits")
    # C4
    if len(fl["A"]) >= MIN_VALID_REPS and len(fl["B"]) >= MIN_VALID_REPS:
        pa, pb = ms([r.get("matched_pps") for r in fl["A"]]), ms([r.get("matched_pps") for r in fl["B"]])
        ca, cb = ms([r.get("cost_per_matched_ns") for r in fl["A"]]), ms([r.get("cost_per_matched_ns") for r in fl["B"]])
        dci, rci = welch_diff_ci(pb, pa), ratio_ci(ca, cb)
        sat = [r for r in fl["A"] if r.get("kernel_packets") and r["kernel_drops"] > 0.01 * r["kernel_packets"]]
        if dci and rci:
            ceil_ok, cpu_ok = dci[0] > 0, rci[0] > 1
            V["C4"] = ("SUPPORTED" if ceil_ok and cpu_ok else ("NOT SUPPORTED" if not (ceil_ok or cpu_ok) else "MIXED"),
                       f"matched-pps ceiling B - A = {f3(dci[1])} pps, 95% CI [{f3(dci[0])}, {f3(dci[2])}] (B higher = CI > 0: {ceil_ok}); "
                       f"CPU per matched packet A/B factor = {f3(rci[1])}, 95% CI [{f3(rci[0])}, {f3(rci[2])}] (A costs more = CI > 1: {cpu_ok}). "
                       f"A saturated (socket drops > 1% of packets reaching it) in {len(sat)} of {len(fl['A'])} valid runs"
                       + ("" if len(sat) == len(fl["A"]) else "; where it did not, A's figure is offered-load-limited, not a ceiling") + ". "
                       "C4's CSPF ratio is not replicated end-to-end (D6.1 item 5).")
        else:
            V["C4"] = ("INCONCLUSIVE", "sd undefined (fewer than 2 valid reps)")
    else:
        V["C4"] = ("INCONCLUSIVE", "not enough valid flood runs for A and B")

    md += ["", "## Verdicts against the pre-declared rules (shape/sign with 95% CIs only; D6.1 item 7)", ""]
    for k in ("C2", "C3", "C4"):
        md.append(f"- **{k}: {V[k][0]}.** {V[k][1]}")
    (RESULTS / "summary.md").write_text("\n".join(md) + "\n")
    (RESULTS / "summary.json").write_text(json.dumps({"verdicts": V, "fits": fits, "steal": {c: list(v) for c, v in cfg_steal.items()}}, indent=1, default=list))

    vd = ["# Verdicts (DRAFT for reviewer review): C2, C3, C4", "",
          "Computed by scripts/summarize.py from logs/bench_*.log; each verdict cites the tables in results/summary.md and the exclusions in results/exclusions.md. "
          "C1 waits for sub-phase 6c. No 1993 absolute number is compared. These are drafts: the reviewer decides.", ""]
    for k, title in (("C2", "C2 reject-all: in-kernel cost flat vs size; user-space copy-then-filter grows"),
                     ("C3", "C3 accept-all: slope and fixed cost, A vs B"), ("C4", "C4 flood: matched-pps ceiling and CPU per matched packet, A vs B")):
        vd += [f"## {title}", "", f"**Verdict: {V[k][0]}**", "", V[k][1], "",
               "Tables: see `results/summary.md` sections " + {"C2": "'Reject curve'", "C3": "'Accept curve' and 'Cost decomposition for config B'", "C4": "'Flood (C4)'"}[k]
               + f". Exclusions affecting this verdict: {n_ex} excluded measured runs in total (`results/exclusions.md`); "
               + "config-level steal exclusions: " + ", ".join(f"{c} {v[0]}/{v[1]}" for c, v in cfg_steal.items() if v[1]) + ".", ""]
    (RESULTS / "verdicts.md").write_text("\n".join(vd) + "\n")
    print(f"parsed {len(runs)} logs ({len(measured)} measured, {sum(r['valid'] for r in measured)} valid, {n_ex} excluded); wrote results/summary.md, exclusions.md, verdicts.md")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit({"calibrate": calibrate, "smoke": smoke}.get(mode, main)())
