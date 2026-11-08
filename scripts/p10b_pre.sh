#!/usr/bin/env bash
# p10b_pre.sh [--post-hash-only] - checks before the WP1b launch: the WP1b design and every frozen input hash to the values logged in logs/p10/p10_wp1b_sha256.log (design logged first, with a time,
# before the first measured file exists), tools built from the logged sources, scripts parse, memory gate. Usage: bash scripts/p10b_pre.sh 2>&1 | tee logs/p10/p10b_pre.log
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
fail=0
chk() { if [[ $1 -eq 0 ]]; then echo "PASS: $2"; else echo "FAIL: $2"; fail=$((fail+1)); fi; }
LOG=logs/p10/p10_wp1b_sha256.log
[[ -s $LOG ]]; chk $? "$LOG exists"
grep -E '^[0-9a-f]{64}  (results|src|scripts|docs)/' $LOG | sha256sum -c -; chk $? "every file named in $LOG hashes to its logged value (plans, sources, scripts, design)"
d=$(grep -n 'docs/phase10_wp1b_design.md' $LOG | head -1 | cut -d: -f1); p=$(grep -n 'results/p10_plan_wp1b_smoke.tsv' $LOG | head -1 | cut -d: -f1)
[[ -n "$d" ]]; chk $? "the WP1b design hash is logged"
newest_meas=$(find logs/p10/wp1b logs/p10/wp1b_smoke -type f -printf '%T@\n' 2>/dev/null | sort -n | head -1)
dt=$(grep -m1 '^design_logged_at ' $LOG | cut -d' ' -f2)
[[ -n "$dt" ]]; chk $? "the design hash has a logged time ($dt)"
if [[ -n "${newest_meas:-}" && -n "$dt" ]]; then awk -v a="$(date -d "$dt" +%s)" -v b="$newest_meas" 'BEGIN { exit !(a <= b) }'; chk $? "the design was logged before the earliest WP1b output"; fi
if [[ "${1:-}" == --post-hash-only ]]; then echo; echo "p10b_pre (hash and time checks only): $fail FAIL"; exit $((fail>0)); fi
for t in p10b_memcpy p10b_testrun p10b_drain; do [[ -x build/p10/$t ]]; chk $? "build/p10/$t is built"; done
for t in memcpy testrun drain; do [[ build/p10/p10b_$t -nt src/p10/p10b_$t.c ]]; chk $? "build/p10/p10b_$t is newer than its source"; done
[[ -f build/phase3_kern.o && -f build/phase6_filters.o ]]; chk $? "Phase 3 and Phase 6 BPF objects are built"
for f in scripts/p10b_*.sh; do bash -n "$f"; chk $? "bash -n $f"; done
for f in scripts/p10b_*.py scripts/p10_summarize.py scripts/p10_check_labels.py; do python3 -I -c "import ast,sys;ast.parse(open(sys.argv[1]).read())" "$f"; chk $? "python syntax $f"; done
python3 -I scripts/p10_canary.py gate; chk $? "memory gate"
echo; echo "p10b_pre: $fail FAIL"
exit $((fail>0))
