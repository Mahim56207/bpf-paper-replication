#!/usr/bin/env python3
"""Compare BPF_PROG_TEST_RUN results (logs/p3_testrun.log) with the reference manifest.
Usage: python3 -I scripts/p3_check.py [manifest_dir] [logdir] | tee logs/p3_check.log
Reads only logs/ and <manifest_dir>/manifest.tsv (default build/p3_pkts_pfx14, written by
scripts/p3_make_packets.py).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "logs"

manifest = {}
MDIR = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/p3_pkts_pfx14"
for line in (MDIR / "manifest.tsv").read_text().splitlines():
    name, length, expected = line.split("\t")
    manifest[name] = (int(length), int(expected))

actual = {}
cur = None
for line in (LOGS / "p3_testrun.log").read_text().splitlines():
    if line.startswith("CASE "):
        cur = line[5:].strip()
        actual[cur] = {"retval": None, "exit": None, "raw": []}
    elif cur:
        actual[cur]["raw"].append(line)
        m = re.search(r"Return value:\s*(-?\d+)", line)
        if m:
            actual[cur]["retval"] = int(m.group(1))
        m = re.match(r"\[exit (\d+)\]", line)
        if m:
            actual[cur]["exit"] = int(m.group(1))

bad = 0
print("%-34s %5s %9s %9s  %s" % ("frame", "len", "expected", "actual", "verdict"))
for name, (length, expected) in manifest.items():
    a = actual.get(name)
    got = a["retval"] if a else None
    ok = got == expected
    bad += 0 if ok else 1
    print("%-34s %5d %9d %9s  %s" % (name, length, expected, got, "ok" if ok else "MISMATCH"))
    if not ok and a:
        print("    raw:", " | ".join(a["raw"]))


def counters(path):
    data = json.loads((LOGS / path).read_text())
    out = {}
    for e in data:
        v = e.get("value", e.get("formatted", {}).get("value"))
        k = e.get("key", e.get("formatted", {}).get("key"))
        if isinstance(v, list):  # unformatted: little-endian byte list of hex strings
            v = int.from_bytes(bytes(int(x, 16) for x in v), "little")
        if isinstance(k, list):
            k = int.from_bytes(bytes(int(x, 16) for x in k), "little")
        out[int(k)] = int(v)
    return out


try:
    before, after = counters("p3_counters_before.json"), counters("p3_counters_after.json")
except Exception as exc:  # report, do not guess
    print("counter files unreadable:", exc)
    sys.exit(1)
d0, d1 = after[0] - before[0], after[1] - before[1]
e1 = sum(1 for _, (_, e) in manifest.items() if e)
e0 = len(manifest) - e1
print()
print(f"frames: {len(manifest)}  mismatches: {bad}")
print(f"counters before={before} after={after}")
print(f"slot0 (dropped) delta={d0} expected={e0}   slot1 (matched) delta={d1} expected={e1}")
print("RESULT:", "PASS" if bad == 0 and d0 == e0 and d1 == e1 else "FAIL")
sys.exit(0 if bad == 0 and d0 == e0 and d1 == e1 else 1)
