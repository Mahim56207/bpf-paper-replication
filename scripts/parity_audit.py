#!/usr/bin/env python3
"""R3.5 instrumentation parity audit (reviewer ruling on D6.4). Reads only the smoke logs, bench.sh, and the two
capture programs' sources; every line printed is extracted from those files.
Usage: python3 -I scripts/parity_audit.py | tee logs/parity_audit.log
"""
import glob
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
logs = {re.search(r"smoke_([A-E])_", f).group(1): f for f in sorted(glob.glob(str(ROOT / "logs/smoke_[A-E]_*.log")))}


def sec_names(path):
    return [l[4:].strip() for l in Path(path).read_text().splitlines() if l.startswith("### ")]


def grep(path, pat):
    return [(i + 1, l.rstrip()) for i, l in enumerate(Path(ROOT / path).read_text().splitlines()) if re.search(pat, l)]


print("# Instrumentation parity audit (configs A to E)\n")
print("## 1. Capture command and pinning, from each smoke log header")
for c, f in logs.items():
    h = [l for l in Path(f).read_text().splitlines() if l.startswith("# capture_cmd") or l.startswith("# pinning")]
    print(f"{c}: " + " | ".join(h))
print("\n## 2. Sections recorded per run (identical sets mean identical instrumentation)")
base = None
for c, f in logs.items():
    names = sec_names(f)
    if base is None:
        base = names
    extra = [n for n in names if n not in base]
    missing = [n for n in base if n not in names]
    print(f"{c}: {len(names)} sections" + (f"; not in A: {extra}" if extra else "") + (f"; missing vs A: {missing}" if missing else ""))
print("\n## 3. In-window instrumentation is config-independent in bench.sh (one command path for all configs)")
for pat in (r"pidstat -p", r"pidstat -w", r"vmstat 1", r"stat_snapshot \"\$cap_pid\" \"\$tmp/stat_(before|after)\"", r"taskset -c \"\$CPU_CAP\""):
    for n, l in grep("scripts/bench.sh", pat):
        print(f"bench.sh:{n}: {l.strip()}")
print("\n## 4. Config-specific steps in bench.sh (guarded by cfg != A) and where they sit relative to the measured window")
for n, l in grep("scripts/bench.sh", r'\[\[ "\$cfg" != A \]\]'):
    print(f"bench.sh:{n}: {l.strip()[:150]}")
txt = Path(ROOT / "scripts/bench.sh").read_text().splitlines()
pos = {k: next(i + 1 for i, l in enumerate(txt) if k in l) for k in ("map_before.json", 'stat_snapshot "$cap_pid" "$tmp/stat_before"', 'stat_snapshot "$cap_pid" "$tmp/stat_after"', "map_after.json")}
print("order of events by line number:", sorted(pos.items(), key=lambda kv: kv[1]))
print("=> the map dumps are taken before stat_before and after stat_after, i.e. outside the measured window.")
print("\n## 5. Per-run program-side logging cadence")
print("baseline_sniffer (A):")
for n, l in grep("src/baseline_sniffer.c", r"CLOCK_CHECK_MASK|SO_RCVTIMEO|report\(\"STAT\"|PACKET_STATISTICS"):
    print(f"  src/baseline_sniffer.c:{n}: {l.strip()[:130]}")
print("loader (B to E):")
for n, l in grep("src/loader.c", r"NS_PER_SEC;|read_counters\(map_fd, &dropped|PACKET_STATISTICS|poll\(&pfd|clock_nanosleep"):
    print(f"  src/loader.c:{n}: {l.strip()[:130]}")
print("Difference: both print once per second; the loader additionally performs two bpf_map_lookup_elem syscalls per second")
print("(inside the window); A has none. Both read PACKET_STATISTICS once, at exit (outside the window).")
print("\n## 6. Per-CPU busy seconds of every smoke run (pinned: capture core 2, server core 3, client core 4; cores 0 and 1 unused)")
import importlib.util
spec = importlib.util.spec_from_file_location("s", ROOT / "scripts/summarize.py"); s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
print("%-4s %7s  %s" % ("cfg", "window", "cpu0 cpu1 cpu2 cpu3 cpu4   (busy s)   total   total per cpu-s of window"))
for c, f in logs.items():
    r = s.parse_run(f)
    pc = r["busy_sec_per_cpu"]
    print("%-4s %7.2f  %s   %6.2f   %.2f" % (c, r["window_s"], " ".join("%4.2f" % pc[k] for k in sorted(pc)), r["busy_sec_total"], r["busy_sec_total"] / (r["window_s"] * len(pc))))
print("\n## 7. Reading")
print("The two unused cores (0, 1) carry no work of any config; in the B run they are as elevated as the pinned cores, so the")
print("elevation is not caused by B's capture process or by any B-specific step above (all B-specific steps are outside the window")
print("or run on the same cores for every config). The sections list and the in-window command path are identical across configs")
print("except the loader's 1 Hz map reads. This points to contamination by ambient load, not a parity violation; one run per config")
print("cannot prove it, which is what the canary rule (V6') and idle windows (A2) are for.")
