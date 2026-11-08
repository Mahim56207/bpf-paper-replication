#!/usr/bin/env python3
"""Hash chain of docs/phase10_design.md: the text as first written (section 9 = "none yet") must hash to the first value of logs/p10/p10_design_sha256.log, each amendment version
(section 9 cut after its k-th item) to the k-th value, the file as it is to the last value, and every logged time must precede the earliest measured log (logs/p10/{wp1,wp2a,wp2b,wp3,wp4})
that the amendment's version governs (here: all of them; amendments written during or after a run would be reported). Exit 1 on any problem. Usage: python3 -I scripts/p10_design_chain.py"""
import glob, hashlib, os, pathlib, re, sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
text = open("docs/phase10_design.md").read()
i = text.index("## 9. Amendments\n")
head = text[: i + len("## 9. Amendments\n")]
items = [l for l in text[i:].splitlines()[1:] if l.startswith("- **A")]
versions = [head + "\nnone yet\n"] + [head + "\n" + "\n".join(items[:k]) + "\n" for k in range(1, len(items) + 1)]
logged, lines = [], open("logs/p10/p10_design_sha256.log").read().splitlines()
for n, l in enumerate(lines):
    m = re.match(r"^([0-9a-f]{64})  docs/phase10_design\.md$", l)
    if m:
        logged.append((m.group(1), lines[n + 1].strip() if n + 1 < len(lines) else ""))
bad = 0
if len(logged) != len(versions):
    print("PROBLEM: %d logged hashes, %d versions of the design (1 + %d amendments)" % (len(logged), len(versions), len(items)))
    bad += 1
for k, (v, (h, when)) in enumerate(zip(versions, logged)):
    got = hashlib.sha256(v.encode()).hexdigest()
    ok = got == h
    print("%s: version %d (%s) reconstructed %s logged %s at %s" % ("MATCH" if ok else "MISMATCH", k, "as first written" if k == 0 else "after amendment A%d" % k, got[:16], h[:16], when))
    bad += not ok
if logged and hashlib.sha256(text.encode()).hexdigest() != logged[-1][0]:
    print("PROBLEM: the file as it is does not hash to the last logged value")
    bad += 1
meas = [p for d in ("wp1", "wp2a", "wp2b", "wp3", "wp4") for p in glob.glob("logs/p10/%s/*" % d)]
if meas and logged:
    first = min(os.path.getmtime(p) for p in meas)
    last_logged = max(datetime.fromisoformat(w).timestamp() for _, w in logged)
    ok = last_logged < first
    print("%s: last logged design time precedes the earliest measured log (%s before %s)" % ("OK" if ok else "PROBLEM", datetime.fromtimestamp(last_logged).isoformat(timespec="seconds"), datetime.fromtimestamp(first).isoformat(timespec="seconds")))
    bad += not ok
print("design chain: %d problem(s)" % bad)
sys.exit(1 if bad else 0)
