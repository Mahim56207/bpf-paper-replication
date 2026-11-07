#!/usr/bin/env python3
"""Phase 8.7 checks on REPORT.md (called by scripts/p8_7_verify.sh):
  numbers : every number of REPORT.md with a decimal part or with three or more digits occurs, up to rounding to the printed precision, in the source files
            that scripts/build_report.py read (logs/p8/p8_7/report_sources.txt) or in the paper-number files CLAIMS.md and docs/paper.txt; dates must occur in git log or in
            a source. Not checked: integers below 100 (counts, section and phase numbers), identifiers (D6.13, V5'a, A1, F1, L29-30), and inline code spans.
  stale   : no sentence of REPORT.md, README.md or results/comparison.md that is about C1, sub-phase 6c or the instruction counts says that it was not evaluated or run.
  matrix  : the C1, C2, C3 labels of the claims matrix equal the labels in results/c1_summary.json and results/summary.json.
Usage: python3 -I scripts/p8_7_check.py"""
import json, os, pathlib, re, subprocess, sys

os.chdir(pathlib.Path(__file__).resolve().parent.parent)
REPORT_PATH = sys.argv[1] if len(sys.argv) > 1 else "REPORT.md"          # an alternate file can be given to test the checker itself
report = open(REPORT_PATH).read()
sources = [l for l in open("logs/p8/p8_7/report_sources.txt").read().split("\n") if l]
extra = ["CLAIMS.md", "docs/paper.txt"]
bad = 0

# ------------------------------------------------------------------ numbers
NUM = re.compile(r"(?<![\w.'/-])[-+]?\d[\d,]*(?:\.\d+)?(?:e[+-]?\d+)?(?![\w'])")
corpus = ""
for f in sources + extra:
    corpus += open(f).read() + "\n"
git_dates = subprocess.run(["git", "log", "--all", "--format=%cs"], capture_output=True, text=True).stdout
corpus_dates = set(re.findall(r"\d{4}-\d{2}-\d{2}", corpus + git_dates))
nums = set()
for m in NUM.finditer(corpus):
    t = m.group(0).replace(",", "")
    try:
        nums.add(abs(float(t)))
    except ValueError:
        pass
fmt = {}


def rounded_set(d):
    if d not in fmt:
        fmt[d] = {f"{x:.{d}f}" for x in nums}
    return fmt[d]


txt = re.sub(r"`[^`\n]*`", " ", report)                       # inline code spans (paths, commands, hashes)
txt = re.sub(r"\b[0-9a-f]{7,40}\b", " ", txt)                  # commit and file hashes
dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", txt)
txt = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", txt)
unchecked_small, checked, missing = 0, 0, []
for m in NUM.finditer(txt):
    tok = m.group(0)
    t = tok.replace(",", "").lstrip("+-")
    if "e" in t:
        mant, exp = t.split("e")
        d = len(mant.split(".")[1]) if "." in mant else 0
        ok = any(f"{x:.{d}e}".replace("e+0", "e+").replace("e-0", "e-") == t.replace("e+0", "e+").replace("e-0", "e-") or f"{x:.{d}e}" == t for x in nums)
        checked += 1
    elif "." in t:
        d = len(t.split(".")[1])
        ok = t in rounded_set(d)
        checked += 1
    elif len(t) >= 3:
        ok = t in rounded_set(0)
        checked += 1
    else:
        unchecked_small += 1
        continue
    if not ok:
        missing.append((tok, report[max(0, m.start() - 40):m.end() + 20].replace("\n", " ")))
for d in dates:
    checked += 1
    if d not in corpus_dates:
        missing.append((d, "date not in git log or sources"))
print("numbers: %d numbers/dates checked against %d source files (+ CLAIMS.md, docs/paper.txt); %d small integers below 100 not checked; %d NOT FOUND" % (checked, len(sources), unchecked_small, len(missing)))
for tok, ctx in missing[:40]:
    print("  NOT FOUND:", tok, "|", ctx)
bad += len(missing)

# ------------------------------------------------------------------ stale statements about C1
pat_topic = re.compile(r"\bC1\b|sub-phase 6c|instruction[- ]count|stack[- ]machine|interpreters?")
pat_neg = re.compile(r"not evaluated|NOT EVALUATED|was not run|never built|not been run|has not been evaluated|were not run")
stale = []
for f in (REPORT_PATH, "README.md", "results/comparison.md"):
    t = re.sub(r"\s+", " ", open(f).read())
    for sent in re.split(r"(?<=[.!?])\s+|\s*\|\s*", t):
        if pat_topic.search(sent) and pat_neg.search(sent):
            stale.append((f, sent[:200]))
print("stale: %d sentences about C1 / sub-phase 6c / instruction counts that say 'not evaluated' or 'not run'" % len(stale))
for f, sent in stale:
    print("  STALE:", f, "|", sent)
bad += len(stale)

# ------------------------------------------------------------------ claims matrix labels
c1 = json.load(open("results/c1_summary.json"))["verdict_m2"]
v = json.load(open("results/summary.json"))["verdicts"]
rows = {}
for l in report.splitlines():
    if re.match(r"\| (C1|C2|C3|C4|C4-S|C5) \|", l):
        rows.setdefault(l.split("|")[1].strip(), l)          # first occurrence: the claims matrix
for cid, label in (("C1", c1), ("C2", v["C2"][0]), ("C3", v["C3"][0])):
    ok = ("**" + label) in rows.get(cid, "")
    print("matrix: %s row has label %s: %s" % (cid, label, "PASS" if ok else "FAIL"))
    bad += not ok
# Phase 8.3 has been run (commits 2c3126d to 2d28bfd, DEVIATIONS D8.19 to D8.25): the rows must refer to it and must not say it was not run
ok = all("Phase 8.3" in rows.get(c, "") and "Phase 8.3 has not been run" not in rows.get(c, "") for c in ("C2", "C3"))
print("matrix: C2 and C3 rows refer to the Phase 8.3 re-run and do not say it was not run: %s" % ("PASS" if ok else "FAIL"))
bad += not ok
# C4: the headline is the frozen V8 rule; the floor result must be labelled as a post hoc sensitivity analysis
ok = ("**" + v["C4"][0] + "**") in rows.get("C4", "") and v["C4_floor"][0] in rows.get("C4", "") and "post hoc" in rows.get("C4", "")
print("matrix: C4 row has the headline label %s (frozen V8 rule) and names the post hoc floor result %s: %s" % (v["C4"][0], v["C4_floor"][0], "PASS" if ok else "FAIL"))
bad += not ok
ok = "C4-S" in rows and "SENDER-LIMITED SUPPORTED" in rows["C4-S"]
print("matrix: sender-bottleneck row present with its verdict: %s" % ("PASS" if ok else "FAIL"))
bad += not ok
print("p8_7_check: %d problem(s)" % bad)
sys.exit(1 if bad else 0)
