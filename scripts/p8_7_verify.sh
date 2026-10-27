#!/usr/bin/env bash
# Phase 8.7 VERIFY: REPORT.md is rebuilt from its sources (deleted first, checked after), is reproducible (same bytes on a second build), every number of it occurs
# in the source files it was built from, no sentence still says that C1 was not evaluated, the claims matrix labels equal the result files, all sources are tracked by git.
# Usage: bash scripts/p8_7_verify.sh 2>&1 | tee logs/p8/p8_7/p8_7_verify.log
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
fail=0; D=logs/p8/p8_7
chk() { if [[ $1 -eq 0 ]]; then echo "PASS: $2"; else echo "FAIL: $2"; fail=$((fail+1)); fi; }
echo "### 1. rebuild"
rm -f REPORT.md $D/report_sources.txt
python3 scripts/build_report.py > $D/build_report_verify.out 2>&1; chk $? "build_report.py (log $D/build_report_verify.out)"
[[ -s REPORT.md && -s $D/report_sources.txt ]]; chk $? "REPORT.md and the source list were created by this run"
h1=$(sha256sum REPORT.md README.md results/comparison.md | sha256sum | cut -c1-16)
python3 scripts/build_report.py > $D/build_report_verify2.out 2>&1; chk $? "second build"
h2=$(sha256sum REPORT.md README.md results/comparison.md | sha256sum | cut -c1-16)
[[ "$h1" == "$h2" ]]; chk $? "REPORT.md, README.md and results/comparison.md are identical after a second build (deterministic, idempotent patches)"
echo "### 2. sources tracked by git"
miss=0; while read -r f; do git ls-files --error-unmatch "$f" > /dev/null 2>&1 || { echo "  not tracked: $f"; miss=$((miss+1)); }; done < $D/report_sources.txt
[[ $miss -eq 0 ]]; chk $? "all $(wc -l < $D/report_sources.txt) source files of the report are tracked by git ($miss untracked)"
echo "### 3. numbers, stale statements, claims matrix"
python3 -I scripts/p8_7_check.py; chk $? "p8_7_check.py"
echo "### 4. scope of the change"
chg=$(git status --short | grep -vE '^\?\? logs/p8/p8_7/' | grep -vE '^ M (REPORT.md|README.md|results/comparison.md|scripts/build_report.py|DEVIATIONS.md)$|^\?\? scripts/p8_7_' || true)
[[ -z "$chg" ]]; chk $? "only REPORT.md, README.md, results/comparison.md, build_report.py and Phase 8.7 files changed: ${chg:-none}"
echo; echo "p8_7_verify: $fail FAIL"
exit $((fail>0))
