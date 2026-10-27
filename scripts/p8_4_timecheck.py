#!/usr/bin/env python3
"""Phase 8.4: no analysed window spans a clock jump. For every launch (C1 C2 C3 F1 F2 F3 X1) the windows are ordered by the start time of their
closing-snapshot pair (`/proc/stat` snapshots, wall clock); for each window the length must lie in [dur-1, dur+2] s (rule V6) and the gap between consecutive
windows must stay small. The aborted attempts (including the one that spanned the VM pause) are listed from their archived console logs but not analysed.
Writes logs/p8/p8_4/p8_4_timecheck.log (deleted first, checked after). Usage: python3 -I scripts/p8_4_timecheck.py"""
import glob, importlib.util, os, pathlib, re, sys

sys.dont_write_bytecode = True
os.chdir(pathlib.Path(__file__).resolve().parent.parent)
OUT = pathlib.Path("logs/p8/p8_4/p8_4_timecheck.log")
OUT.unlink(missing_ok=True)
spec = importlib.util.spec_from_file_location("summ", "scripts/summarize.py")
summ = importlib.util.module_from_spec(spec); spec.loader.exec_module(summ)
lines, bad, n_all = [], 0, 0
for B in ("C1", "C2", "C3", "F1", "F2", "F3", "X1"):
    ws = []
    for f in glob.glob("logs/p8/p8_4/%s/runs/*.log" % B):
        t = open(f).read()
        s = summ.sections(t)
        b, a = summ.parse_stat(s["stat_before"]), summ.parse_stat(s["stat_after"])
        dur = int(re.search(r" dur=(\d+)", t).group(1))
        ws.append((b["time"], a["time"], dur, f))
    ws.sort()
    gaps = [ws[i + 1][0] - ws[i][1] for i in range(len(ws) - 1)]
    lens = [w[1] - w[0] for w in ws]
    v6 = sum(1 for w in ws if not (w[2] - 1 <= w[1] - w[0] <= w[2] + 2))
    big = [(round(g, 1), ws[i][3].split("/")[-1]) for i, g in enumerate(gaps) if g > 120]
    n_all += len(ws)
    bad += v6 + len(big)
    lines.append("%s: %d windows, length min %.2f max %.2f s, %d outside V6; gap between consecutive windows min %.1f max %.1f s; gaps over 120 s: %s" % (
        B, len(ws), min(lens), max(lens), v6, min(gaps), max(gaps), big or "none"))
lines.append("TOTAL %d analysed windows; problems: %d" % (n_all, bad))
for a in sorted(glob.glob("logs/p8/p8_4/*/aborted_attempt_*/")):
    c = glob.glob(a + "*console*.log")
    lines.append("not analysed: %s (%d window logs)" % (a.rstrip("/"), len(glob.glob(a + "runs/*.log"))))
OUT.write_text("\n".join(lines) + "\n")
if not OUT.exists() or OUT.stat().st_size == 0:
    sys.exit("FATAL: not written")
print("\n".join(lines))
sys.exit(1 if bad else 0)
