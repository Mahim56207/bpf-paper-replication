#!/usr/bin/env python3
"""Phase 10 plans (docs/phase10_design.md sections 2, 4, 5, 8): the randomized run orders of WP1, WP2(a) and WP2(b), drawn from seed 20261108, written once to
results/p10_plan_*.tsv; the sha256 of each plan is appended to logs/p10/p10_plan_sha256.log. Refuses to overwrite an existing plan (a plan is frozen when written).
Usage: python3 -I scripts/p10_plan.py"""
import hashlib, os, pathlib, random, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
SEED = 20261108
SIZES = [64, 256, 512, 1024, 1500]
WP1_KINDS = ["memcpy", "tr_reject", "tr_accept", "tr_port", "dr_U", "dr_E", "dr_B"]
BATCHES = 10
REPS = 6
RATES = [100000, 200000, 300000, 450000, 600000]


def write(name, header, rows):
    path = ROOT / "results" / name
    if path.exists():
        sys.exit(f"ABORT: {path} exists; a plan is frozen when written (move it away on purpose)")
    path.write_text("# " + "\t".join(header) + "\n" + "\n".join("\t".join(str(x) for x in r) for r in rows) + "\n")
    if not path.is_file() or path.stat().st_size == 0:
        sys.exit(f"FATAL: {path} was not created")
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    with open(ROOT / "logs" / "p10" / "p10_plan_sha256.log", "a") as f:
        f.write(f"{h}  results/{name}\n")
    print(f"wrote results/{name}: {len(rows)} rows, sha256 {h}")


(ROOT / "logs" / "p10").mkdir(parents=True, exist_ok=True)
rng = random.Random(SEED * 10 + 1)
rows = [(k, s, b) for k in WP1_KINDS for s in SIZES for b in range(1, BATCHES + 1)]
rng.shuffle(rows)
write("p10_plan_wp1.tsv", ["seq", "kind", "size", "batch"], [(i + 1, *r) for i, r in enumerate(rows)])

rng = random.Random(SEED * 10 + 2)
rows = [(t, c, r) for t in ("T0", "T1") for c in "NABC" for r in range(1, REPS + 1)]
rng.shuffle(rows)
write("p10_plan_wp2a.tsv", ["seq", "topology", "cfg", "rep"], [(i + 1, *r) for i, r in enumerate(rows)])

rng = random.Random(SEED * 10 + 3)
rows = [(c, rate, r) for c in "ABC" for rate in RATES for r in range(1, REPS + 1)]
rng.shuffle(rows)
write("p10_plan_wp2b.tsv", ["seq", "cfg", "rate", "rep"], [(i + 1, *r) for i, r in enumerate(rows)])
