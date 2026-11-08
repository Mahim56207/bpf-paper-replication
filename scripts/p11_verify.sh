#!/usr/bin/env bash
# p11_verify.sh - Phase 11 verify. REPORT.md, README.md and results/comparison.md are rebuilt (deleted first, checked after) and are identical after a second build; every source of the
# report is tracked; scripts/p8_7_check.py (numbers, stale statements, old claims matrix) passes; the final labels of REPORT.md equal results/p10_summary.json; the words the author asked to be
# replaced are gone and the required statements are present; presentation.html equals the version of origin/main once the notice block is removed; the paper repository is untouched;
# only the allowed files changed; secrets scan. Usage: bash scripts/p11_verify.sh 2>&1 | tee logs/p11/p11_verify.log
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
fail=0; D=logs/p11
chk() { if [[ $1 -eq 0 ]]; then echo "PASS: $2"; else echo "FAIL: $2"; fail=$((fail+1)); fi; }
mkdir -p $D
echo "### 1. rebuild"
rm -f REPORT.md logs/p8/p8_7/report_sources.txt
python3 scripts/build_report.py > $D/build_report_verify.out 2>&1; chk $? "build_report.py (log $D/build_report_verify.out)"
[[ -s REPORT.md && -s logs/p8/p8_7/report_sources.txt ]]; chk $? "REPORT.md and the source list were created by this run"
h1=$(sha256sum REPORT.md README.md results/comparison.md | sha256sum | cut -c1-16)
python3 scripts/build_report.py > $D/build_report_verify2.out 2>&1; chk $? "second build"
h2=$(sha256sum REPORT.md README.md results/comparison.md | sha256sum | cut -c1-16)
[[ "$h1" == "$h2" ]]; chk $? "REPORT.md, README.md and results/comparison.md are identical after a second build"
echo "### 2. sources tracked by git"
miss=0; while read -r f; do git ls-files --error-unmatch "$f" > /dev/null 2>&1 || { echo "  not tracked: $f"; miss=$((miss+1)); }; done < logs/p8/p8_7/report_sources.txt
[[ $miss -eq 0 ]]; chk $? "all $(wc -l < logs/p8/p8_7/report_sources.txt) source files of the report are tracked by git ($miss untracked)"
echo "### 3. numbers, stale statements, old claims matrix"
python3 -I scripts/p8_7_check.py > $D/p8_7_check.out 2>&1; rc=$?; tail -12 $D/p8_7_check.out; chk $rc "p8_7_check.py"
echo "### 4. final labels equal results/p10_summary.json"
python3 -I - <<'PY'
import json, re, sys
S = json.load(open("results/p10_summary.json"))["labels"]
rp = open("REPORT.md").read()
sec = rp[rp.index("## Final labels after Phase 10"):rp.index("## Claims matrix of Phases 6 to 9")]
rows = {}
for l in sec.splitlines():
    if l.startswith("| C"):
        c = [x.strip() for x in l.strip("|").split("|")]
        rows[c[0]] = re.sub(r"\*", "", c[1])
want = {"C1 register": "C1", "C2 reject": "C2", "C3 accept": "C3", "C4 end-to-end": "C4", "C4-mitigation": "C4-mitigation", "C5 a safe": "C5", "C2 (WP1 original": "C2 (WP1 original)", "C3 (WP1 original": "C3 (WP1 original)"}
ok = True
for prefix, key in want.items():
    got = [v for k, v in rows.items() if k.startswith(prefix)]
    exp = S[key]["label"]
    if key == "C4-mitigation":       # Phase 12 relabel (D12.1): named by what the data show when both classes are REVERSED
        exp = "REVERSED gap, cause not established (UNVERIFIED)" if all(v == "REVERSED" for v in S[key]["detail"].values()) else exp
    good = len(got) == 1 and got[0] == exp
    print(("PASS: " if good else "FAIL: ") + "final table row %s has label %s (expected %s; rule output in the summary: %s)" % (prefix, got, exp, S[key]["label"]))
    ok = ok and good
sys.exit(0 if ok else 1)
PY
chk $? "final labels of REPORT.md"
echo "### 5. words and statements"
hits=$(grep -n "REMOVED" REPORT.md README.md results/comparison.md scripts/build_report.py scripts/build_report_p10.py scripts/p10_summarize.py scripts/p10_check_labels.py || true)
[[ -z "$hits" ]]; chk $? "no 'REMOVED' in the report, README, comparison, build scripts or summarizer (${hits:-none})"
hits=$(grep -nE "Operationally Replicated|100 GB/s" REPORT.md README.md results/comparison.md scripts/build_report.py scripts/build_report_p10.py || true)
[[ -z "$hits" ]]; chk $? "no 'Operationally Replicated' or '100 GB/s' (${hits:-none})"
need() { grep -qF -- "$1" REPORT.md; chk $? "REPORT.md states: $2"; }
need "not end-to-end capture" "C2 and C3 are microbenchmarks, not end-to-end capture"
need "different measurement paths" "the 1993 slopes are a comparison of different measurement paths"
need "148 / upper bound" "ratio of the 1993 slopes to the upper bound is tabulated"
need "Copy floor against the user path" "copy-floor slope next to the user-path slope"
need "delta = 10 ns/byte was kept as frozen and no tighter margin was added" "delta kept frozen"
need "The gap is reversed, not removed." "the mitigation result is a reversed gap"
need "The causes of the reversal are UNVERIFIED" "causes of the reversal UNVERIFIED"
need "C2 (WP1 original, superseded)" "superseded WP1 result kept alongside"
bad=$(grep -nE "(mitigation|C4-mitigation)[^|]*\| \*\*SUPPORTED|mitigation[^.]*(label|labelled|is) \*{0,2}SUPPORTED" REPORT.md README.md results/comparison.md || true)
[[ -z "$bad" ]]; chk $? "no line calls the mitigation result SUPPORTED (${bad:-none})"
echo "### 6. presentation.html"
python3 - <<'PY'
import hashlib, subprocess, sys
t = open("presentation.html").read()
b, e = "<!-- p11-superseded-notice:begin -->", "<!-- p11-superseded-notice:end -->"
ok = t.count(b) == 1 and t.count(e) == 1 and "SUPERSEDED" in t[t.index(b):t.index(e)]
a, z = t.index(b), t.index(e) + len(e) + 1
rest = t[:a] + t[z:]
orig = subprocess.run(["git", "show", "origin/main:presentation.html"], capture_output=True, text=True).stdout
same = hashlib.sha256(rest.encode()).hexdigest() == hashlib.sha256(orig.encode()).hexdigest()
print("notice block present once: %s; file without the block equals origin/main: %s" % (ok, same))
sys.exit(0 if ok and same else 1)
PY
chk $? "presentation.html = origin/main + one notice block (nothing deleted or edited)"
echo "### 7. paper repository untouched"
now="$(git -C ~/bpf-paper-short rev-parse HEAD; git -C ~/bpf-paper-short status --porcelain | wc -l)"
[[ "$now" == "$(cat $D/paper_repo_head.txt)" ]]; chk $? "~/bpf-paper-short has the same HEAD and a clean working tree as when it was read ($(echo $now | tr '\n' ' '))"
echo "### 8. scope of the change"
allowed='^(REPORT\.md|README\.md|results/comparison\.md|presentation\.html|DEVIATIONS\.md)$|^scripts/(build_report\.py|build_report_p10\.py|p11_)|^logs/p8/p8_7/report_sources\.txt$|^logs/p11/|^docs/p11_paper_change_list\.md$|^logs/p10/p10_push\.log$|^logs/p12/|^logs/p11_ls_remote\.log$|^results/p10_baseline_offered_load_note\.md$|^logs/p10/p10_baseline_offered_load_analysis\.log$|^scripts/p10_baseline_note_probe\.py$'
deferred='^scripts/demo/|^logs/demo_rehearsal_[0-9]\.log$|^logs/demo_act3_preview\.log$|^CODE_NOTES\.md$'   # Phase 12 (demo kit) files and the Phase 12 CODE_NOTES entry: deliberately not part of Phase 11
chg=$(git status --short | cut -c4- | grep -vE "$allowed" | grep -vE "$deferred" || true)
[[ -z "$chg" ]]; chk $? "only the Phase 11 files changed (Phase 12 demo-kit files and its CODE_NOTES entry are deferred): ${chg:-none}"
echo "### 9. secrets scan"
bash scripts/p11_secrets_scan.sh > $D/p11_secrets_scan_console.log 2>&1; chk $? "secrets scan: $(tail -1 $D/p11_secrets_scan_console.log)"
echo; echo "p11_verify: $fail FAIL"
exit $((fail>0))
