#!/usr/bin/env python3
"""Phase 8.2: the run plan of docs/phase8_2_design.md section 3: 6 unprofiled + 4 profiled repetitions of each of the configs
N, A, B, C, all 40 rows in one seeded random order (seed 20261026). Writes results/p8_2_plan.tsv (deleted first, checked after)
and prints the sha256 of the file. Run set 2 (amendment A2): P8_2_RUN=run2 uses seed 20261027 and writes results/p8_2_plan_run2.tsv.
Usage: python3 -I scripts/p8_2_plan.py   |   P8_2_RUN=run2 python3 -I scripts/p8_2_plan.py"""
import hashlib, os, random, sys

RUN = os.environ.get("P8_2_RUN", "")
SEED = {"": 20261026, "run2": 20261027}[RUN]
CFGS = ("N", "A", "B", "C")
REPS = {0: 6, 1: 4}   # profile flag -> repetitions
path = "results/p8_2_plan%s.tsv" % ("_" + RUN if RUN else "")
if os.path.exists(path):
    os.remove(path)
rows = [(prof, cfg, rep) for prof in (0, 1) for cfg in CFGS for rep in range(1, REPS[prof] + 1)]
random.Random(SEED).shuffle(rows)
with open(path, "w") as f:
    f.write("# seed=%d dur=10 traffic=flood size=256 unprofiled=%d profiled=%d per config\n# seq\tprofile\tcfg\trep\n" % (SEED, REPS[0], REPS[1]))
    for i, r in enumerate(rows, 1):
        f.write("%d\t%d\t%s\t%d\n" % ((i,) + r))
if not os.path.exists(path) or os.path.getsize(path) == 0:
    sys.exit("FATAL: %s not written" % path)
print("%d rows written to %s; sha256 %s" % (len(rows), path, hashlib.sha256(open(path, "rb").read()).hexdigest()))
