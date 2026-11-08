#!/usr/bin/env python3
"""Phase 10 WP1b pilot precision statement (docs/phase10_wp1b_design.md section 6). Reads the pilot batch logs (logs/p10/wp1b/pilot/b*_a*.log: final attempt of each plan row,
valid = RC 0 and canary clean), fits cost against size per kind on the pilot points, and prints the slope precision EXPECTED from the main plan (10 valid batches per size at the
sizes 64, 256, 512, 1024, 1500, the same residual spread, Student-t 90% interval, df = points - 2), next to the margin delta. Informational only: it gates nothing, changes no
rule, and the pilot data enter no verdict. Usage: python3 -I scripts/p10b_pilot_precision.py [PILOT_DIR]  (output tee'd into logs/p10/wp1b/pilot_precision.txt)"""
import glob, importlib.util, math, os, pathlib, re, sys
from collections import defaultdict

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
D = sys.argv[1] if len(sys.argv) > 1 else "logs/p10/wp1b/pilot"
spec = importlib.util.spec_from_file_location("s10", "scripts/p10_summarize.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
SIZES, PER = [64, 256, 512, 1024, 1500], 10
col = {"memcpy": 3, "tr_reject": 4, "tr_accept": 4, "tr_port": 4, "dr_U": 11, "dr_E": 11, "dr_B": 11}      # primary metric column of the RESULT line (design section 4)
best = {}
n_att = n_bad = 0
for f in sorted(glob.glob(f"{D}/b*_a*.log")):
    m = re.match(r"b(\d+)_a(\d+)\.log", os.path.basename(f))
    seq, att = int(m[1]), int(m[2])
    txt = open(f).read()
    n_att += 1
    n_bad += (re.search(r"^CANARY .* status=clean", txt, re.M) is None) or (re.search(r"^RC 0$", txt, re.M) is None)
    if seq not in best or att > best[seq][0]:
        best[seq] = (att, txt)
pts = defaultdict(list)
for seq, (att, txt) in best.items():
    kind = re.search(r"kind=(\S+)", txt)[1]
    size = int(re.search(r"size=(\d+)", txt)[1])
    if re.search(r"^RC 0$", txt, re.M) and re.search(r"^CANARY .* status=clean", txt, re.M):
        pts[kind].append((size, float(re.search(r"^RESULT (.*)$", txt, re.M)[1].split(",")[col[kind]])))
if not pts:
    sys.exit("FATAL: no valid pilot batches found in " + D)
mx = sum(SIZES) / len(SIZES)
sxx = PER * sum((x - mx) ** 2 for x in SIZES)
df = PER * len(SIZES) - 2
t = S.tq(0.90, df)
print(f"pilot attempts {n_att}, of which canary-contaminated or rc != 0: {n_bad} (fraction {n_bad / n_att:.3f}); pilot plan rows with a valid final batch: {sum(len(v) for v in pts.values())} of {len(best)}")
print(f"main plan assumed: {PER} valid batches at each of {len(SIZES)} sizes, df {df}, t(90%) {t:.4f}, Sxx {sxx:.0f}")
se = {}
print("kind\tpilot_n\tpilot_slope\tresid_sd\tpred_se_slope\tpred_halfwidth90\thalfwidth/delta")
for k in col:
    v = pts.get(k, [])
    if len(v) < 5 or len({x for x, _ in v}) < 3:
        print(f"{k}\t{len(v)}\tn/a (too few valid pilot batches)")
        continue
    f = S.ols([x for x, _ in v], [y for _, y in v])
    sd = f["se_slope"] * math.sqrt(sum((x - sum(x for x, _ in v) / len(v)) ** 2 for x, _ in v))
    se[k] = sd / math.sqrt(sxx)
    print(f"{k}\t{len(v)}\t{f['slope']:.5f}\t{sd:.4f}\t{se[k]:.6f}\t{t * se[k]:.5f}\t{t * se[k] / S.DELTA:.5f}")
for name, a, b in (("d = s_U - s_K (C2)", "dr_U", "tr_reject"), ("e = s_U - s_E (C3)", "dr_U", "dr_E")):
    if a in se and b in se:
        h = t * math.sqrt(se[a] ** 2 + se[b] ** 2)
        print(f"{name}: predicted half-width of the 90% interval {h:.5f} ns/byte, {h / S.DELTA:.5f} of delta ({S.DELTA} ns/byte); a class INSIDE needs the half-width below delta in addition to an estimate near zero")
    else:
        print(f"{name}: n/a")
