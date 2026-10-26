#!/usr/bin/env python3
"""Phase 8.1 step 4: idle CPU-s/s and canary rates of the Phase 8.1 windows against the Phase 6 numbers, computed from
the run logs only, with the same parser and the same definitions as scripts/baseline (summarize.py parse_run): busy =
user+nice+system+irq+softirq+steal over CLK_TCK; idle_rate = system-wide busy CPU-s per s of the /proc/stat window;
canary_01 = (cpu0 + cpu1) / window, canary_0 = cpu0 / window. V8 limit = 1.2 x the calibration canary_max
(results/baseline_calibration.json). Reads logs, writes results/p8_1_idle_table.md and results/p8_1_idle.json (deleted first,
checked after). Usage: python3 -I scripts/p8_1_stats.py"""
import glob, importlib.util, json, os, pathlib, statistics, sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
spec = importlib.util.spec_from_file_location("summ", "scripts/summarize.py")
summ = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summ)

OUT_MD, OUT_JSON = pathlib.Path("results/p8_1_idle_table.md"), pathlib.Path("results/p8_1_idle.json")
for p in (OUT_MD, OUT_JSON):
    p.unlink(missing_ok=True)

base = json.load(open("results/baseline_calibration.json"))
CAN01, CAN0 = base["canary_max"]["01"], base["canary_max"]["0"]
V8 = summ.CANARY_FACTOR

SETS = [("Phase 6 quiet calibration session", sorted(glob.glob("logs/cal_v2_session_idle/calibration_idle_*.log"))),
        ("Phase 6 matrix session start (noisy)", sorted(glob.glob("logs/bench_D_idle_0_*.log")))]
for d in sorted(glob.glob("logs/p8/p8_1/idle_*")):
    SETS.append(("Phase 8.1 " + os.path.basename(d)[len("idle_"):], sorted(glob.glob(d + "/p81*_D_idle_0_*.log"))))

rows, js = [], {"baseline_calibration": {"idle_rate_mean": base["idle_rate_mean"], "canary_max": base["canary_max"], "v8_factor": V8}, "sets": {}}
for name, files in SETS:
    if len(files) != 3:
        sys.exit("FATAL: %s: expected 3 windows, found %d (%s)" % (name, len(files), files))
    ws = []
    for f in files:
        r = summ.parse_run(f)
        if r["traffic"] != "idle" or r.get("window_s") is None or r["reasons"]:
            sys.exit("FATAL: %s not a clean idle window: traffic=%s reasons=%s" % (f, r["traffic"], r["reasons"]))
        w, pc = r["window_s"], r["busy_sec_per_cpu"]
        ws.append({"file": f, "window_s": w, "idle_rate": r["busy_sec_total"] / w, "canary_01": (pc["cpu0"] + pc["cpu1"]) / w,
                   "canary_0": pc["cpu0"] / w, "steal_pct": r["steal_pct"], "cls_T": r["cls"]["T"] if r["cls"] else None,
                   "per_cpu": {c: v / w for c, v in sorted(pc.items())}})
    idle_mean = statistics.fmean(x["idle_rate"] for x in ws)
    row = {"idle_mean": idle_mean, "idle_max": max(x["idle_rate"] for x in ws), "canary_01_max": max(x["canary_01"] for x in ws),
           "canary_0_max": max(x["canary_0"] for x in ws), "ratio_to_quiet": idle_mean / base["idle_rate_mean"],
           "v8_windows_contaminated": sum(1 for x in ws if x["canary_01"] > V8 * CAN01), "windows": ws}
    js["sets"][name] = row
    rows.append((name, row))

md = ["# Phase 8.1: idle CPU and canary rates (computed by scripts/p8_1_stats.py from the run logs)\n",
      "Definitions as in the Phase 6 calibration (`scripts/summarize.py` `baseline`): idle rate = system-wide busy CPU-s per s over the window with the matrix harness attached and no traffic; canary rate = busy CPU-s on the canary cores / window; canary_max = max over the 3 windows. V8 limit for cores {0,1} = %.1f x %.4f = %.4f CPU-s/s (calibration canary_max from `results/baseline_calibration.json`).\n" % (V8, CAN01, V8 * CAN01),
      "| window set | idle rate mean | idle rate max | x quiet calibration | canary {0,1} max | canary {0} max | windows over the V8 limit |",
      "|---|---|---|---|---|---|---|"]
for name, r in rows:
    md.append("| %s | %.3f | %.3f | %.1fx | %.4f | %.4f | %d of 3 |" % (name, r["idle_mean"], r["idle_max"], r["ratio_to_quiet"], r["canary_01_max"], r["canary_0_max"], r["v8_windows_contaminated"]))
md += ["", "Reference numbers recorded in earlier phases (D6.8, D6.13): quiet calibration 0.131 and canary_max 0.0689 on {0,1}; noisy matrix start 0.843. The rows above recompute them from the logs: the calibration row should read %.3f / %.4f and the matrix row 0.843 (rounded)." % (base["idle_rate_mean"], CAN01), "",
       "## Per window", "", "| set | window | length s | idle rate | canary {0,1} | canary {0} | steal % | classifier T | per-CPU busy (cpu0..cpu4) |", "|---|---|---|---|---|---|---|---|---|"]
for name, r in rows:
    for x in r["windows"]:
        md.append("| %s | %s | %.2f | %.4f | %.4f | %.4f | %.2f | %s | %s |" % (name, os.path.basename(x["file"]), x["window_s"], x["idle_rate"], x["canary_01"], x["canary_0"], x["steal_pct"], x["cls_T"], " / ".join("%.3f" % v for v in x["per_cpu"].values())))
OUT_MD.write_text("\n".join(md) + "\n")
OUT_JSON.write_text(json.dumps(js, indent=1))
for p in (OUT_MD, OUT_JSON):
    if not p.exists() or p.stat().st_size == 0:
        sys.exit("FATAL: %s was not created" % p)
print("\n".join(md))
