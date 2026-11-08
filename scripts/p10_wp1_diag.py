#!/usr/bin/env python3
"""Phase 10 WP1 diagnosis (read-only): reads logs/p10/wp1/b*_a*.log and writes the tables to stdout (tee'd into logs/p10/wp1_diag/). No measurement, no new data."""
import glob, os, re, statistics as st, sys, math
CLK = os.sysconf("SC_CLK_TCK")
rows = []
for f in sorted(glob.glob("logs/p10/wp1/b*_a*.log")):
    t = open(f).read().splitlines()
    h = re.match(r"# wp1 seq=(\d+) kind=(\S+) size=(\d+) batch=(\d+) attempt=(\d+)", t[0])
    seq, kind, size, batch, att = h.groups()
    res = next(l for l in t if l.startswith("RESULT")).split(None, 1)[1].split(",")
    rc = int(next(l for l in t if l.startswith("RC")).split()[1])
    c = re.search(r"rate=([\d.]+) wall=([\d.]+) limit=([\d.]+) cores=(\S+) status=(\S+)", next(l for l in t if l.startswith("CANARY")))
    rate, wall, limit, cores, status = float(c[1]), float(c[2]), float(c[3]), c[4], c[5]
    # tool duration in s from the tool's own output
    if kind == "memcpy": dur = int(res[1]) * float(res[2]) * 1e-9
    elif kind.startswith("tr_"): dur = int(res[1]) * int(res[2]) * 1e-9
    else: dur = float(res[7]) * 1e-9   # elapsed_ns of the drain phase only
    ticks = rate * wall * CLK
    rows.append(dict(seq=int(seq), kind=kind, size=int(size), att=int(att), rc=rc, dur=dur, wall=wall, rate=rate, limit=limit, ticks=ticks, ncores=len(cores.split(",")), bad=(status != "clean" or rc != 0)))
print(f"attempts: {len(rows)}; clean and rc 0: {sum(not r['bad'] for r in rows)}; failing: {sum(r['bad'] for r in rows)}; rc!=0: {sum(r['rc']!=0 for r in rows)}")
print(f"canary limit (CPU-s/s over {rows[0]['ncores']} cores): {sorted(set(round(r['limit'],6) for r in rows))}")
print(f"window wall (s) of the canary snapshots: min {min(r['wall'] for r in rows):.3f} median {st.median(r['wall'] for r in rows):.3f} max {max(r['wall'] for r in rows):.3f}")
print(f"tool duration (s): min {min(r['dur'] for r in rows):.4f} median {st.median(r['dur'] for r in rows):.4f} max {max(r['dur'] for r in rows):.3f}")
print("\n## failure rate by canary-window wall time (s)")
bins = [(0, .25), (.25, .5), (.5, 1), (1, 2), (2, 4), (4, 1e9)]
print("bin\tn\tfail\tfail_frac\tmedian_rate\tmedian_ticks\tlimit_in_ticks(median)")
for lo, hi in bins:
    g = [r for r in rows if lo <= r["wall"] < hi]
    if not g: continue
    print(f"[{lo},{hi if hi<1e8 else 'inf'})\t{len(g)}\t{sum(r['bad'] for r in g)}\t{sum(r['bad'] for r in g)/len(g):.3f}\t{st.median(r['rate'] for r in g):.4f}\t{st.median(r['ticks'] for r in g):.1f}\t{st.median(r['limit']*r['wall']*CLK for r in g):.2f}")
print("\n## by kind")
print("kind\tn\tfail\tfail_frac\tmedian_wall\tmedian_rate")
for k in sorted(set(r["kind"] for r in rows)):
    g = [r for r in rows if r["kind"] == k]
    print(f"{k}\t{len(g)}\t{sum(r['bad'] for r in g)}\t{sum(r['bad'] for r in g)/len(g):.3f}\t{st.median(r['wall'] for r in g):.3f}\t{st.median(r['rate'] for r in g):.4f}")
print("\n## tick quantisation: busy ticks (rate x wall x 100) of every attempt; integer if the rate is a multiple of 0.01/wall")
dev = [abs(r["ticks"] - round(r["ticks"])) for r in rows]
print(f"max |ticks - round(ticks)| over all attempts: {max(dev):.4f}  (the rate printed has 6 decimals)")
fails = [r for r in rows if r["bad"]]
from collections import Counter
cf = Counter(round(r["ticks"]) for r in fails); cp = Counter(round(r["ticks"]) for r in rows if not r["bad"])
print("ticks\tfailing\tpassing")
for k in sorted(set(cf) | set(cp)):
    if k <= 40: print(f"{k}\t{cf.get(k,0)}\t{cp.get(k,0)}")
print(f"(counts above 40 ticks: failing {sum(v for k,v in cf.items() if k>40)}, passing {sum(v for k,v in cp.items() if k>40)})")
print("\n## ticks = a + b x wall  (a = ticks per attempt independent of duration, b = ticks per second): OLS over all attempts, and over attempts with wall >= 1 s")
def ols(xs, ys):
    n = len(xs); mx, my = sum(xs)/n, sum(ys)/n
    sxx = sum((x-mx)**2 for x in xs); b = sum((x-mx)*(y-my) for x, y in zip(xs, ys))/sxx; a = my-b*mx
    res = sum((y-a-b*x)**2 for x, y in zip(xs, ys)); se_b = math.sqrt(res/(n-2)/sxx); se_a = math.sqrt(res/(n-2)*(1/n+mx*mx/sxx))
    return a, se_a, b, se_b, n
for name, g in (("all", rows), ("wall>=1s", [r for r in rows if r["wall"] >= 1]), ("wall<1s", [r for r in rows if r["wall"] < 1])):
    if len(g) > 3:
        a, sa, b, sb, n = ols([r["wall"] for r in g], [r["ticks"] for r in g]); print(f"{name}: n={n} a={a:.2f}+-{sa:.2f} ticks, b={b:.2f}+-{sb:.2f} ticks/s (= {b/CLK:.4f} CPU-s/s)")
print("\n## pre-flight idle windows of block B1 (10 s each, same 4 cores)")
print(open("logs/p10/preflight/wp1/preflight.json").read().strip() if os.path.exists("logs/p10/preflight/wp1/preflight.json") else "preflight.json not found")
print("\n## failure rate over the sequence (by plan seq decile): is contamination episodic (background) or uniform?")
seqs = sorted(set(r["seq"] for r in rows)); nb = 10
for i in range(nb):
    chunk = set(seqs[i*len(seqs)//nb:(i+1)*len(seqs)//nb]); g = [r for r in rows if r["seq"] in chunk]
    print(f"decile {i+1}: attempts {len(g)} fail {sum(r['bad'] for r in g)/len(g):.3f} median_rate {st.median(r['rate'] for r in g):.3f}")
print("\n## within long windows only (wall >= 1 s): rate distribution")
g = [r["rate"] for r in rows if r["wall"] >= 1]
if g: print(f"n={len(g)} min {min(g):.4f} median {st.median(g):.4f} max {max(g):.4f}; fail frac {sum(r['bad'] for r in rows if r['wall']>=1)/len(g):.3f}")
print("\n## single-tick exceedance: one /proc/stat tick is 0.01 CPU-s, so a window shorter than 0.01/limit seconds fails with ONE tick")
lim = rows[0]["limit"]; wmin = 0.01 / lim
g = [r for r in rows if r["wall"] < wmin]
print(f"0.01/limit = {wmin:.4f} s; attempts with canary wall below it: {len(g)}; failing among them: {sum(r['bad'] for r in g)}; passing with 0 ticks: {sum((not r['bad']) and round(r['ticks'])==0 for r in g)}")
ex = [r["ticks"] - r["limit"] * r["wall"] * CLK for r in rows if r["bad"]]
print(f"failing attempts exceeding the limit by less than 1 tick: {sum(e < 1 for e in ex)} of {len(ex)}; by less than 2 ticks: {sum(e < 2 for e in ex)}; by 5 ticks or more: {sum(e >= 5 for e in ex)}")
