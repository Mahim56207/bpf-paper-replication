#!/usr/bin/env python3
"""Phase 8.4: choose the noise levels from the calibration probe by the rule of docs/phase8_4_design.md section 3. Reads
logs/p8/p8_4/calib/calib.jsonl; for every (type, noised cores, nominal duty) the added canary rate = sum over the noised cores of
(busy rate - baseline rate of that core), baseline = mean of the duty-0 windows. For each target the grid duty whose added rate is closest in
ratio is chosen. Writes results/p8_4_levels.json and results/p8_4_levels.md (deleted first, checked after).
Usage: python3 -I scripts/p8_4_levels.py"""
import collections, json, math, os, pathlib, statistics, sys

os.chdir(pathlib.Path(__file__).resolve().parent.parent)
outs = [pathlib.Path("results/p8_4_levels.json"), pathlib.Path("results/p8_4_levels.md")]
for o in outs:
    o.unlink(missing_ok=True)
CAL = os.environ.get("P8_4_CALIB_DIR", "logs/p8/p8_4/calib2")
rows = [json.loads(l) for l in open(CAL + "/calib.jsonl")]
base_rows = [r for r in rows if r["duty"] == 0]
if len(base_rows) != 3:
    sys.exit("FATAL: expected 3 baseline windows, found %d" % len(base_rows))
for src, dst in (("results/p8_4_levels.json", "results/p8_4_levels_calib1.json"), ("results/p8_4_levels.md", "results/p8_4_levels_calib1.md")):
    if os.path.exists(src) and not os.path.exists(dst):
        os.rename(src, dst)        # keep the numbers of calibration 1 alongside
base = {c: statistics.fmean(r["busy"][c] for r in base_rows) for c in base_rows[0]["busy"]}
agg = collections.defaultdict(list)
leak = 0.0
for r in rows:
    if r["duty"] == 0:
        continue
    added = r["injected"]                      # CPU time consumed by the workers themselves per second of window (amendment A2)
    agg[(r["kind"], tuple(r["cores"]), r["duty"])].append(added)
    for c, v in r["busy"].items():
        if int(c) not in r["cores"]:
            leak = max(leak, abs(v - base[c]))
tab = {k: statistics.fmean(v) for k, v in agg.items()}
T_E1 = [0.01, 0.025, 0.05, 0.10, 0.20]
T_E2 = [0.01, 0.025, 0.05, 0.10]


def pick(kind, cores, target):
    cand = [(abs(math.log(a / target)), d, a) for (k, c, d), a in tab.items() if k == kind and c == tuple(cores) and a > 0]
    if not cand:
        return None
    _, d, a = min(cand)
    return {"duty": d, "added_rate": a, "target": target, "ratio": a / target}


def pick_seq(kind, cores, targets):
    """Levels must be distinct and increasing (amendment A3): for the increasing targets choose, in order, the grid duty with the smallest ratio error
    among the duties above the previously chosen one."""
    out, prev = [], 0
    for t in targets:
        cand = [(abs(math.log(a / t)), d, a) for (k, c, d), a in tab.items() if k == kind and c == tuple(cores) and a > 0 and d > prev]
        if not cand:
            out.append(None)
            continue
        _, d, a = min(cand)
        out.append({"duty": d, "added_rate": a, "target": t, "ratio": a / t})
        prev = d
    return out


res = {"baseline_per_cpu": base, "max_added_on_non_noised_cores": leak, "E1": {}, "E2": {}, "S": {}}
for kind in ("cpu", "cache"):
    res["E1"][kind] = pick_seq(kind, [0, 1], T_E1)
    res["E2"][kind] = pick_seq(kind, [0], T_E2)
for core in (2, 3):
    res["S"]["cpu_core%d" % core] = pick("cpu", [core], 0.10)
vm = [json.loads(l) for l in open("logs/p8/p8_4/calib/calib.jsonl") if json.loads(l)["kind"] == "vm"]   # the memory window of calibration 1 (still valid: it does not use the duty cycle)
res["S"]["vm"] = vm[0]["ready"] if vm else None
md = ["# Phase 8.4: noise levels chosen from the calibration probe (script-computed)\n",
      "Baseline per-CPU busy rate (3 windows, workers stopped): " + ", ".join("cpu%s %.4f" % (c, v) for c, v in sorted(base.items())) + ". Largest added rate on a core that was not noised in any window: %.4f CPU-s/s.\n" % leak]
for exp, key in (("E1 (cores 0,1; V8 limit 0.0826)", "E1"), ("E2 (core 0; V8 limit 0.0443)", "E2")):
    md += ["## " + exp, "", "| type | target added rate | chosen nominal duty (%) | measured added rate | ratio to target |", "|---|---|---|---|---|"]
    for kind in ("cpu", "cache"):
        for t, p in zip(T_E1 if key == "E1" else T_E2, res[key][kind]):
            md.append("| %s | %.3f | %s | %s | %s |" % (kind, t, p["duty"] if p else "-", "%.4f" % p["added_rate"] if p else "-", "%.2f" % p["ratio"] if p else "-"))
    md.append("")
md += ["## E3", "", "| condition | chosen nominal duty (%) | measured added rate |", "|---|---|---|"]
for k in ("cpu_core2", "cpu_core3"):
    p = res["S"][k]
    md.append("| %s | %s | %s |" % (k, p["duty"] if p else "-", "%.4f" % p["added_rate"] if p else "-"))
md.append("| vm (S3) | holds %s MB | MemAvailable %s -> %s MB |" % (res["S"]["vm"] and res["S"]["vm"].get("vm_mb"), res["S"]["vm"] and res["S"]["vm"].get("MemAvailable_before_MB"), res["S"]["vm"] and res["S"]["vm"].get("MemAvailable_after_MB")))
md.append("\nAll measured added rates by (type, cores, nominal duty):\n\n| type | cores | duty | added CPU-s/s (mean of windows) | windows |\n|---|---|---|---|---|")
for (k, c, d), v in sorted(agg.items()):
    md.append("| %s | %s | %s | %.4f | %d |" % (k, ",".join(map(str, c)), d, tab[(k, c, d)], len(v)))
outs[0].write_text(json.dumps(res, indent=1))
outs[1].write_text("\n".join(md) + "\n")
for o in outs:
    if not o.exists() or o.stat().st_size == 0:
        sys.exit("FATAL: %s not written" % o)
print("\n".join(md))
