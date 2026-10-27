#!/usr/bin/env python3
"""Phase 8.4: script-computed design hash chain. logs/p8/p8_4/p8_4_design_sha256.log lists, in order, the sha256 of docs/phase8_4_design.md as first
written (section 10 'none yet') and after each amendment A1..An. This script rebuilds each version from the current file (only section 10 grows),
hashes it and compares; it lists the amendments (id, date, first sentence) and compares the logged times with the start of the calibration probe and
of every launch that exists (the first hash must precede the probe; the design version in force at each launch, i.e. the last hash logged before it, must be at least A3, the levels amendment; amendments logged after the launches are listed as post hoc).
Writes logs/p8/p8_4/p8_4_design_chain.log (deleted first). Usage: python3 -I scripts/p8_4_design_chain.py"""
import datetime, glob, hashlib, os, pathlib, re, sys

os.chdir(pathlib.Path(__file__).resolve().parent.parent)
OUT = pathlib.Path("logs/p8/p8_4/p8_4_design_chain.log")
OUT.unlink(missing_ok=True)
text = open("docs/phase8_4_design.md").read()
log = open("logs/p8/p8_4/p8_4_design_sha256.log").read().splitlines()
hashes, times = [], []
for i, l in enumerate(log):
    m = re.match(r"^([0-9a-f]{64})  docs/phase8_4_design.md$", l)
    if m:
        hashes.append(m.group(1))
        times.append(datetime.datetime.fromisoformat(log[i + 1].strip()))
sha = lambda s: hashlib.sha256(s.encode()).hexdigest()
i10 = text.index("## 10. Amendments")
starts = [m.start() for m in re.finditer(r"\n- \*\*A\d+ \(", text[i10:])]
versions = [text[:i10] + "## 10. Amendments\n\n(none yet)\n"]
for k in range(len(starts)):
    end = i10 + starts[k + 1] if k + 1 < len(starts) else len(text)
    versions.append(text[:end].rstrip("\n") + "\n" if k + 1 < len(starts) else text)
lines, bad = ["# design hash chain (script-computed) %s" % datetime.datetime.now().astimezone().isoformat(timespec="seconds")], 0
if len(hashes) != len(versions):
    lines.append("MISMATCH: %d logged hashes but %d versions (first + %d amendments)" % (len(hashes), len(versions), len(starts)))
    bad += 1
for k, v in enumerate(versions[:len(hashes)]):
    ok = sha(v) == hashes[k]
    bad += not ok
    lines.append("%s: %s\n    reconstructed %s\n    logged        %s  (%s)" % ("MATCH" if ok else "MISMATCH", "design as first written" if k == 0 else "design after amendment A%d" % k, sha(v), hashes[k], times[k].isoformat()))
lines.append("\namendments (id, date, first sentence):")
for m in re.finditer(r"^- \*\*(A\d+) \((\d{4}-\d{2}-\d{2})(.*)$", text, re.M):
    lines.append("  %s  %s  %s" % (m.group(1), m.group(2), re.split(r"(?<=[.;:])\s", m.group(3))[0][:200]))
cal = sorted(glob.glob("logs/p8/p8_4/calib/calib.jsonl"))
if cal:
    first = datetime.datetime.fromtimestamp(os.stat(cal[0]).st_ctime).astimezone()
    ok = times[0] < first
    bad += not ok
    lines.append("%s: first hash logged %s, calibration probe output created %s" % ("OK" if ok else "FAIL", times[0].isoformat(), first.isoformat()))
LEVELS_AMENDMENT = 3          # A3 fixed the levels; every launch must have started after its hash was logged
launch_starts = []
for B in ("C1", "C2", "C3", "F1", "F2", "F3", "X1"):
    f = "logs/p8/p8_4/%s/run_context.txt" % B
    if os.path.exists(f):
        m = re.search(r"start=([0-9T:+-]+)", open(f).read())
        start = datetime.datetime.fromisoformat(m.group(1))
        launch_starts.append(start)
        k = max(i for i, t in enumerate(times) if t < start)         # design version in force at the launch = last hash logged before it
        ok = k >= LEVELS_AMENDMENT
        bad += not ok
        lines.append("%s: launch %s started %s; design in force = %s (hash logged %s)" % ("OK" if ok else "FAIL", B, start.isoformat(), "as first written" if k == 0 else "after A%d" % k, times[k].isoformat()))
post = [k for k, t in enumerate(times) if launch_starts and t > max(launch_starts)]
if post:
    lines.append("INFO: amendment(s) A%s logged after the last launch started: post-hoc by construction (their text says so)" % ", A".join(map(str, post)))
lines.append("hash-chain check: %d problem(s)" % bad)
OUT.write_text("\n".join(lines) + "\n")
if not OUT.exists() or OUT.stat().st_size == 0:
    sys.exit("FATAL: %s not written" % OUT)
print("\n".join(lines))
sys.exit(1 if bad else 0)
