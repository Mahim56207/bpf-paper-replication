#!/usr/bin/env python3
"""Phase 8.4: run plans (docs/phase8_4_design.md section 4). Needs results/p8_4_levels.json (chosen from the calibration probe, fixed by
amendment A1). Launches: C1..C3 (E1 paced curve: 2 types x 6 levels x 10 windows = 120 rows each), F1..F3 (E2 flood: 2 types x 5 levels x 10 =
100 rows each), X1 (E3: 4 conditions x 15 = 60 rows). Rows are shuffled with a seed per launch (20261101 + index). Writes
results/p8_4_plan_<batch>.tsv (deleted first, checked after) and prints the sha256 of each.
Usage: python3 -I scripts/p8_4_plan.py"""
import hashlib, json, os, pathlib, random, sys

os.chdir(pathlib.Path(__file__).resolve().parent.parent)
lv = json.load(open("results/p8_4_levels.json"))
BATCHES = ["C1", "C2", "C3", "F1", "F2", "F3", "X1"]


def duty(entry):
    if entry is None:
        sys.exit("FATAL: a target level has no calibrated duty (see results/p8_4_levels.md)")
    return entry["duty"]


plans = {}
for bi, b in enumerate(BATCHES):
    rows = []
    k = int(b[1])
    if b[0] == "C":
        for kind in ("cpu", "cache"):
            for level in range(6):
                d = 0 if level == 0 else duty(lv["E1"][kind][level - 1])
                for j in range(10):
                    rows.append(("E1", "p84E1%sL%d" % (kind, level), "B", "m", 512, (k - 1) * 10 + j + 1, 32000, "%s:0,1:%s" % (kind, d)))
    elif b[0] == "F":
        for kind in ("cpu", "cache"):
            for level in range(5):
                d = 0 if level == 0 else duty(lv["E2"][kind][level - 1])
                for j in range(10):
                    rows.append(("E2", "p84E2%sL%d" % (kind, level), "N", "flood", 256, (k - 1) * 10 + j + 1, 0, "%s:0:%s" % (kind, d)))
    else:
        conds = [("S0", "cpu:2:0"), ("S1", "cpu:2:%s" % duty(lv["S"]["cpu_core2"])), ("S2", "cpu:3:%s" % duty(lv["S"]["cpu_core3"])), ("S3", "vm:3:100")]
        for name, spec in conds:
            for j in range(15):
                rows.append(("E3", "p84E3%s" % name, "B", "m", 512, j + 1, 32000, spec))
    random.Random(20261101 + bi).shuffle(rows)
    path = pathlib.Path("results/p8_4_plan_%s.tsv" % b)
    path.unlink(missing_ok=True)
    with open(path, "w") as f:
        f.write("# batch=%s seed=%d rows=%d\n# seq\texp\tlabel\tcfg\ttraffic\tsize\trep\tpps\tnoise_spec\n" % (b, 20261101 + bi, len(rows)))
        for i, r in enumerate(rows, 1):
            f.write("%d\t%s\n" % (i, "\t".join(map(str, r))))
    if not path.exists() or path.stat().st_size == 0:
        sys.exit("FATAL: %s not written" % path)
    plans[b] = path
    print("%s: %d rows, sha256 %s" % (path, len(rows), hashlib.sha256(path.read_bytes()).hexdigest()))
