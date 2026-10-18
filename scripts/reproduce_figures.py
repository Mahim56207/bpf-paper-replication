#!/usr/bin/env python3
"""Regenerate the Phase 6 figures from the raw logs. No number in this file is a result: everything is parsed.

Usage (repo root):  python3 scripts/reproduce_figures.py
Needs matplotlib (e.g. `sudo apt install python3-matplotlib`, or a venv with `pip install matplotlib`).
Inputs : logs/bench_*.log (the matrix, parsed by scripts/summarize.py), results/baseline_calibration.json (quiet idle baseline, D6.13),
         results/calibration.json and logs/cal_v1_frozen_rules/calibration.json (calibration ladders), logs/bench_*_flood_* (flood runs).
Outputs: results/fig_cpu_cost.png, results/fig_drop_rate.png, results/figures_data.json (the plotted values, for traceability).
"""
import glob
import importlib.util
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"

spec = importlib.util.spec_from_file_location("summarize", ROOT / "scripts" / "summarize.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def mean_sd(xs):
    xs = [x for x in xs if x is not None]
    return (statistics.mean(xs), statistics.stdev(xs) if len(xs) > 1 else 0.0, len(xs)) if xs else (None, None, 0)


def collect():
    """Parse the matrix logs and the calibration ladders; returns the dict that the figures plot."""
    base = json.loads((RES / "baseline_calibration.json").read_text())
    idle_rate = base["idle_rate_mean"]                       # quiet calibration idle baseline (D6.13)
    runs = [S.parse_run(f) for f in sorted(glob.glob(str(ROOT / "logs" / "bench_*.log")))]
    measured = [r for r in runs if r["traffic"] in ("nm", "m", "flood")]
    session = S.latest_session(measured)
    runs = [r for r in measured if r["session"] == session and r["valid"]]
    for r in runs:
        net = r["busy_sec_total"] - idle_rate * r["window_s"]
        r["net_per_offered_ns"] = net * 1e9 / r["offered_pkts"] if r.get("offered_pkts") else None
        r["net_per_matched_ns"] = net * 1e9 / r["matched_flow"] if r.get("matched_flow") else None
    out = {"session": session, "idle_rate_cpu_s_per_s": idle_rate, "reject": {}, "accept": {}, "flood": {}, "drop": {}}
    for key, traffic, cfgs, metric in (("reject", "nm", "ABD", "net_per_offered_ns"), ("accept", "m", "ABE", "net_per_matched_ns")):
        for cfg in cfgs:
            pts = []
            for size in sorted({r["size"] for r in runs if r["traffic"] == traffic}):
                m, sd, n = mean_sd([r[metric] for r in runs if (r["cfg"], r["traffic"], r["size"]) == (cfg, traffic, size)])
                if n:
                    pts.append({"size": size, "mean": m, "sd": sd, "n": n})
            out[key][cfg] = pts
    for cfg in "ABC":
        fr = [r for r in runs if r["cfg"] == cfg and r["traffic"] == "flood"]
        m, sd, n = mean_sd([r["net_per_matched_ns"] for r in fr])
        out["flood"][cfg] = {"mean": m, "sd": sd, "n": n, "offered_pps": mean_sd([r.get("offered_pps") for r in fr])[0]}
        out["drop"].setdefault("flood", {})[cfg] = [
            {"offered_pps": r["offered_pps"], "drop_pct": 100.0 * r["kernel_drops"] / r["kernel_packets"]}
            for r in fr if r.get("kernel_packets")]
    for label, path in (("quiet calibration (this session)", RES / "calibration.json"),
                        ("first calibration, busy desktop", ROOT / "logs" / "cal_v1_frozen_rules" / "calibration.json")):
        cal = json.loads(path.read_text())
        out["drop"][label] = {}
        for size, k in cal["knees"].items():
            out["drop"][label][size] = [{"offered_pps": st["offered_pps"], "drop_pct": 100.0 * (st["kernel_drops"] or 0) / st["kernel_packets"]}
                                        for st in k["steps"] if st.get("offered_pps") and st.get("kernel_packets")]
    return out


def plot(data):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        sys.exit("matplotlib is required: sudo apt install python3-matplotlib   (or: python3 -m venv .venv && .venv/bin/pip install matplotlib)")

    colors = {"A": "tab:red", "B": "tab:blue", "C": "tab:green", "D": "tab:gray", "E": "tab:orange"}
    names = {"A": "A: user-space copy-then-filter", "B": "B: kernel filter + drain", "C": "C: kernel filter, no drain",
             "D": "D: reject_all (floor)", "E": "E: accept_all"}
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), gridspec_kw={"width_ratios": [3, 3, 1.6]})
    for ax, key, title, ylab in ((axes[0], "reject", "Reject curve: non-matching UDP", "net CPU ns per offered packet"),
                                 (axes[1], "accept", "Accept curve: matching UDP", "net CPU ns per flow-matched packet")):
        for cfg, pts in data[key].items():
            if pts:
                ax.errorbar([p["size"] for p in pts], [p["mean"] for p in pts], yerr=[p["sd"] for p in pts], marker="o", capsize=3,
                            color=colors[cfg], label=names[cfg])
        ax.set_xlabel("frame size (bytes)")
        ax.set_ylabel(ylab)
        ax.set_title(title)
        ax.legend(fontsize=7)
        ax.grid(alpha=0.3)
    cfgs = [c for c in "ABC" if data["flood"][c]["n"]]
    axes[2].bar(cfgs, [data["flood"][c]["mean"] for c in cfgs], yerr=[data["flood"][c]["sd"] for c in cfgs], capsize=3,
                color=[colors[c] for c in cfgs])
    axes[2].set_title("Flood (flood-only configs)")
    axes[2].set_ylabel("net CPU ns per flow-matched packet")
    fig.suptitle("Per-packet CPU cost vs packet size (error bars = sd over valid reps; idle baseline from the quiet calibration, D6.13; "
                 "config C exists only as a flood run)", fontsize=9)
    fig.tight_layout()
    fig.savefig(RES / "fig_cpu_cost.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    styles = {"quiet calibration (this session)": ("-", "tab:blue"), "first calibration, busy desktop": ("--", "tab:red")}
    for label, sizes in data["drop"].items():
        if label == "flood":
            continue
        ls, col = styles[label]
        for size, pts in sizes.items():
            ax.plot([p["offered_pps"] for p in pts], [p["drop_pct"] for p in pts], ls, marker="o", color=col,
                    alpha=1.0 if size == min(sizes, key=int) else 0.55, label=f"A, {label}, {size} B")
    for cfg, pts in data["drop"]["flood"].items():
        if pts:
            ax.scatter([p["offered_pps"] for p in pts], [p["drop_pct"] for p in pts], marker="s", s=40, color=colors[cfg], label=f"flood, {names[cfg]}")
    ax.set_xscale("log")
    ax.set_xlabel("offered load (packets per second, log scale)")
    ax.set_ylabel("capture-socket drop rate (% of packets that reached the socket)")
    ax.set_title("Packet drop rate vs offered load (PACKET_STATISTICS, one read per run)")
    ax.legend(fontsize=6)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(RES / "fig_drop_rate.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    d = collect()
    (RES / "figures_data.json").write_text(json.dumps(d, indent=1))
    print("parsed matrix session", d["session"], "; wrote results/figures_data.json")
    plot(d)
    print("wrote results/fig_cpu_cost.png and results/fig_drop_rate.png")
