#!/usr/bin/env python3
"""Read-only analysis for results/p10_baseline_offered_load_note.md: from the run logs only (no experiment is run), per config-N flood run: kernel, pinning, topology, per-stream frames
counted by the classifier (CLS line), offered pps, and busy CPU-s/s of each core from the /proc/stat snapshots of the run log (busy = all columns except idle and iowait).
Usage: python3 -I scripts/p10_baseline_note_probe.py 2>&1 | tee logs/p10/p10_baseline_offered_load_analysis.log"""
import glob, re, statistics as st

SETS = [("Phase 8.2 run set 2, config N", "logs/p8/p8_2/run2/runs/p82_N_flood_256_[0-9].log"),
        ("Phase 10 WP2(a), T0 (baseline topology), config N", "logs/p10/wp2a/p10aT0_N_flood_256_[0-9].log"),
        ("Phase 10 WP2(a), T1 (mitigated topology), config N", "logs/p10/wp2a/p10aT1_N_flood_256_[0-9].log")]


def snap(txt, tag):
    blk = txt.split(f"### {tag}\n")[1].split("###")[0]
    return {l.split()[0]: [int(x) for x in l.split()[1:]] for l in blk.splitlines() if re.match(r"cpu\d ", l)}


def run(path):
    t = open(path).read()
    b, a = snap(t, "stat_before"), snap(t, "stat_after")
    busy = {}
    for c in sorted(a):
        d = [y - x for x, y in zip(b[c], a[c])]
        busy[c] = (sum(d) - d[3] - d[4]) / 100 / 10          # CPU-s per 10 s window, clk_tck 100
    m = re.search(r"^CLS T=(\d+) F4040=(\d+) .* F5050=(\d+)", t, re.M)
    T, f40, f50 = (int(x) for x in m.groups())
    return {"file": path, "kernel": re.search(r"kernel=(\S+)", t).group(1), "pin": re.search(r"# pinning (.*)", t).group(1), "topo": (re.search(r"# topology=(\S+) rps_cpus_readback=(\S+)", t).groups() if re.search(r"# topology=", t) else ("n/a", "n/a")),
            "T": T, "f40": f40, "f50": f50, "busy": busy}


for name, pat in SETS:
    rs = [run(f) for f in sorted(glob.glob(pat))]
    print(f"== {name}: {len(rs)} runs; kernel {rs[0]['kernel']}; pinning {rs[0]['pin']}; topology/rps readback {rs[0]['topo']}")
    print("   total offered pps (classifier T / 10 s): mean %.0f, per stream (4040, 5050): %.0f, %.0f" % (st.mean(r["T"] for r in rs) / 10, st.mean(r["f40"] for r in rs) / 10, st.mean(r["f50"] for r in rs) / 10))
    print("   busy CPU-s/s per core, mean over runs: " + ", ".join("%s %.3f" % (c, st.mean(r["busy"][c] for r in rs)) for c in sorted(rs[0]["busy"])))
