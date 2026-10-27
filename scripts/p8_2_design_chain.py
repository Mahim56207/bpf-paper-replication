#!/usr/bin/env python3
"""Phase 8.2: script-computed confirmation of the design hash chain. The logged hashes (logs/p8/p8_2/p8_2_design_sha256.log) are:
  1st = the design as first written, logged before any probe or measured run; 2nd = after amendment A1; 3rd = after amendment A2.
This script reconstructs those texts from the current docs/phase8_2_design.md (sections 1 to 7 were never edited; only section 8 grew),
hashes them and compares with the log; it also lists every amendment found in section 8 (id, date, first sentence) and compares the time of
the first logged hash with the earliest probe start and with the start of run set 2. Writes logs/p8/p8_2/p8_2_design_chain.log (deleted first).
Usage: python3 -I scripts/p8_2_design_chain.py"""
import datetime, hashlib, os, pathlib, re, sys

os.chdir(pathlib.Path(__file__).resolve().parent.parent)
OUT = pathlib.Path("logs/p8/p8_2/p8_2_design_chain.log")
OUT.unlink(missing_ok=True)
text = open("docs/phase8_2_design.md").read()
log = open("logs/p8/p8_2/p8_2_design_sha256.log").read().splitlines()
hashes, times = [], []
for i, l in enumerate(log):
    m = re.match(r"^([0-9a-f]{64})  docs/phase8_2_design.md$", l)
    if m:
        hashes.append(m.group(1))
        times.append(log[i + 1].strip() if i + 1 < len(log) else "")
sha = lambda s: hashlib.sha256(s.encode()).hexdigest()
idx8 = text.index("## 8. Amendments")
head = text[:idx8]
a2 = text.index("\n- **A2 (")
a1_body = text[idx8:a2]                     # section 8 up to the start of A2 (contains A1)
orig = head + "## 8. Amendments\n\n(none yet)\n"
after_a1 = text[:a2].rstrip("\n") + "\n"
lines, bad = [], 0


def check(label, got, want):
    global bad
    ok = got == want
    bad += not ok
    lines.append("%s: %s\n    reconstructed %s\n    logged        %s" % ("MATCH" if ok else "MISMATCH", label, got, want))


lines.append("# design hash chain (script-computed) %s" % datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
if len(hashes) != 3:
    sys.exit("FATAL: expected 3 logged design hashes, found %d" % len(hashes))
check("1st logged hash = the design as first written (sections 1 to 7 unchanged, section 8 'none yet')", sha(orig), hashes[0])
check("2nd logged hash = the design after amendment A1", sha(after_a1), hashes[1])
check("3rd logged hash = the design after amendment A2 = the file now", sha(text), hashes[2])
lines.append("sections 1 to 7 are byte-identical in all three versions by construction of the reconstruction; the first check proves they equal the first logged text.")
lines.append("")
lines.append("amendments in section 8 (id, date, first sentence):")
for m in re.finditer(r"^- \*\*(A\d) \((\d{4}-\d{2}-\d{2})[^)]*\)\.\*\* (.*)$", text, re.M):
    lines.append("  %s  %s  %s" % (m.group(1), m.group(2), re.split(r"(?<=[.;:])\s", m.group(3))[0][:200]))
lines.append("")
lines.append("logged times of the hashes: " + " | ".join(times))
first_probe = re.search(r"probe start ([0-9T:+-]+)", open("logs/p8/p8_2/p8_2_probe_console_attempt1_perf_owner_error.log").read()).group(1)
run2_start = re.search(r"start=([0-9T:+-]+)", open("logs/p8/p8_2/run2/run_context.txt").read()).group(1)
t0, tp, t2 = (datetime.datetime.fromisoformat(x) for x in (times[0], first_probe, run2_start))
for lab, t in (("earliest probe start (excluded runs)", tp), ("run set 2 start", t2)):
    ok = t0 < t
    bad += not ok
    lines.append("%s: first hash logged %s, %s %s" % ("OK" if ok else "FAIL", t0.isoformat(), lab, t.isoformat()))
lines.append("hash-chain check: %d problem(s)" % bad)
OUT.write_text("\n".join(lines) + "\n")
if not OUT.exists() or OUT.stat().st_size == 0:
    sys.exit("FATAL: %s not written" % OUT)
print("\n".join(lines))
sys.exit(1 if bad else 0)
