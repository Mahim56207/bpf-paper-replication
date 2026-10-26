#!/usr/bin/env python3
"""Phase 8.2 amendment A2 item 5 (read-only, informational): who uses core 0 during the flood runs. For every final run log of a run set
(P8_2_RUN=run2 for run set 2; default run set 1, which has no task lines and is reported as such) it takes the "task <pid> <comm> <ticks> <cpu>"
lines of the opening and closing snapshots, forms per-task tick differences, attributes a task to core 0 when its last CPU in the closing snapshot
is 0 (an approximation: a task can run on several CPUs), and reports per config the CPU-s/s of the main core-0 tasks next to the measured core-0 busy rate.
Memory pressure: differences of psi_memory 'some' total (microseconds) over each window. Writes results/p8_2_diag_core0[_run2].md (deleted first, checked after).
Usage: python3 -I scripts/p8_2_diag_core0.py"""
import collections, glob, importlib.util, os, pathlib, re, statistics, sys

sys.dont_write_bytecode = True
os.chdir(pathlib.Path(__file__).resolve().parent.parent)
spec = importlib.util.spec_from_file_location("summ", "scripts/summarize.py")
summ = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summ)
RUN = os.environ.get("P8_2_RUN", "")
L = pathlib.Path("logs/p8/p8_2") / RUN
out = pathlib.Path("results/p8_2_diag_core0%s.md" % ("_" + RUN if RUN else ""))
out.unlink(missing_ok=True)
CLK = 100


def tasks(block):
    d = {}
    for line in block.splitlines():
        m = re.match(r"task (\d+) (\S+) (\d+) (\d+)$", line)
        if m:
            d[int(m.group(1))] = (m.group(2), int(m.group(3)), int(m.group(4)))
    return d


def psi(block, kind):
    m = re.search(r"psi_%s some .*total=(\d+)" % kind, block)
    return int(m.group(1)) if m else None


md = ["# Phase 8.2: core-0 attribution per config (informational), run set %s\n" % (RUN or "1"),
      "Per config, over the final unprofiled runs: mean busy rate of core 0 (from `/proc/stat`) and the mean CPU-s/s of the tasks whose last CPU in the closing snapshot was 0 (tick differences between the two snapshots, so tasks that moved between CPUs are approximate), plus the memory pressure stall delta.\n"]
for cfg in "NABC":
    files = sorted(glob.glob(str(L / "runs" / ("p82_%s_flood_256_*.log" % cfg))))
    if not files:
        md.append("## %s\n\nno final unprofiled logs.\n" % cfg)
        continue
    agg, busy0, mem, n_task_lines = collections.defaultdict(list), [], [], 0
    for f in files:
        txt = pathlib.Path(f).read_text()
        s = summ.sections(txt)
        tb, ta = tasks(s.get("stat_before", "")), tasks(s.get("stat_after", ""))
        n_task_lines += len(tb) + len(ta)
        b, a = summ.parse_stat(s["stat_before"]), summ.parse_stat(s["stat_after"])
        w = a["time"] - b["time"]
        busy0.append((summ.busy(a["cpu"]["cpu0"]) - summ.busy(b["cpu"]["cpu0"])) / CLK / w)
        per = collections.Counter()
        for pid, (comm, t1, cpu1) in ta.items():
            t0 = tb.get(pid, (comm, 0, 0))[1]
            if cpu1 == 0 and t1 > t0:
                per[comm] += (t1 - t0) / CLK / w
        for comm, v in per.items():
            agg[comm].append(v)
        m0, m1 = psi(s.get("stat_before", ""), "memory"), psi(s.get("stat_after", ""), "memory")
        if m0 is not None and m1 is not None:
            mem.append((m1 - m0) / 1e6 / w)
    nrun = len(files)
    md.append("## %s (n=%d runs)\n" % (cfg, nrun))
    if n_task_lines == 0:
        md.append("The logs of this run set contain no task lines (they were recorded from amendment A2 on); only the core-0 busy rates are available: %s.\n" % ", ".join("%.3f" % x for x in busy0))
        continue
    tot = {c: sum(v) / nrun for c, v in agg.items()}
    md.append("Core 0 busy (mean) **%.3f** CPU-s/s (per run: %s); tasks attributed to core 0 sum to **%.3f**; memory 'some' stall: %s s per s.\n" % (
        statistics.fmean(busy0), ", ".join("%.3f" % x for x in busy0), sum(tot.values()), ("%.4f" % statistics.fmean(mem)) if mem else "n/a"))
    md.append("| task (comm) | mean CPU-s/s on core 0 | runs in which it appears |")
    md.append("|---|---|---|")
    for c, v in sorted(tot.items(), key=lambda kv: -kv[1])[:12]:
        md.append("| %s | %.4f | %d of %d |" % (c, v, len(agg[c]), nrun))
    md.append("")
out.write_text("\n".join(md) + "\n")
if not out.exists() or out.stat().st_size == 0:
    sys.exit("FATAL: %s not written" % out)
print("\n".join(md))
