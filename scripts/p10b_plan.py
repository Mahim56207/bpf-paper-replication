#!/usr/bin/env python3
"""Phase 10 WP1b plans (docs/phase10_wp1b_design.md section 5): randomized run orders of the smoke stage (one row per kind at one size), the pilot (3 batches per kind and size)
and the main run (12 batches per kind and size), drawn from seed 20261108 (streams 4, 5 and 6), written once to results/p10_plan_wp1b_{smoke,pilot,main}.tsv; sha256 appended to
logs/p10/p10_wp1b_sha256.log. Refuses to overwrite a plan. Usage: python3 -I scripts/p10b_plan.py"""
import hashlib, os, pathlib, random, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
SEED = 20261108
SIZES = [64, 256, 512, 1024, 1500]
KINDS = ["memcpy", "tr_reject", "tr_accept", "tr_port", "dr_U", "dr_E", "dr_B"]


def write(name, rows):
    path = ROOT / "results" / name
    if path.exists():
        sys.exit(f"ABORT: {path} exists; a plan is frozen when written (move it away on purpose)")
    path.write_text("# seq\tkind\tsize\tbatch\n" + "\n".join("\t".join(str(x) for x in r) for r in rows) + "\n")
    if not path.is_file() or path.stat().st_size == 0:
        sys.exit(f"FATAL: {path} was not created")
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    with open(ROOT / "logs" / "p10" / "p10_wp1b_sha256.log", "a") as f:
        f.write(f"{h}  results/{name}\n")
    print(f"wrote results/{name}: {len(rows)} rows, sha256 {h}")


(ROOT / "logs" / "p10").mkdir(parents=True, exist_ok=True)
smoke = [(i + 1, k, 256, 1) for i, k in enumerate(KINDS)]
write("p10_plan_wp1b_smoke.tsv", smoke)
for stream, name, per in ((5, "p10_plan_wp1b_pilot.tsv", 3), (6, "p10_plan_wp1b.tsv", 12)):
    rng = random.Random(SEED * 10 + stream)
    rows = [(k, s, b) for k in KINDS for s in SIZES for b in range(1, per + 1)]
    rng.shuffle(rows)
    write(name, [(i + 1, *r) for i, r in enumerate(rows)])
