#!/usr/bin/env bash
# p10_verify.sh [--pre] - Phase 10 verify. --pre: checks before the launch (design hash chain, frozen plans, frozen independent CSPF set and real trace, tools built, scripts parse,
# no digits in verdict strings, memory gate); without --pre: the same plus the checks after the run (summary fresher than its inputs, labels re-derived by
# scripts/p10_check_labels.py, validity counts, no leftover smoke or probe output in the analysed folders). Usage: bash scripts/p10_verify.sh [--pre] 2>&1 | tee logs/p10/p10_verify.log
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
MODE="${1:-post}"; fail=0
chk() { if [[ $1 -eq 0 ]]; then echo "PASS: $2"; else echo "FAIL: $2"; fail=$((fail+1)); fi; }
echo "### design hash chain"
python3 -I scripts/p10_design_chain.py; chk $? "design hash chain"
echo "### frozen inputs"
grep -E '^[0-9a-f]{64}  results/' logs/p10/p10_plan_sha256.log | sha256sum -c -; chk $? "the three plans hash to their logged values"
grep -E '^[0-9a-f]{64}  ' logs/p10/p10_indep_sha256.log | sha256sum -c -; chk $? "the independent CSPF set and its INPUT.md hash to their logged values"
if [[ "$MODE" == --pre ]]; then
    [[ -s build/p10/real_anon.pcap && -s build/p10/real_anon.pcap.hg ]]; chk $? "the anonymized real trace and its H/G file exist"
    grep -E '^[0-9a-f]{64}  ' logs/p10/real_trace_sha256.log | sha256sum -c -; chk $? "the anonymized real trace hashes to its logged value"
    for t in p10_memcpy p10_testrun p10_drain; do [[ -x build/p10/$t ]]; chk $? "build/p10/$t is built"; done
    [[ -x build/phase3_kern.o || -f build/phase3_kern.o && -f build/phase6_filters.o && -x build/loader && -x build/baseline_sniffer && -x build/classifier ]]; chk $? "Phase 3 and Phase 6 objects and capture tools are built"
    [[ -x build/p10/c1/c1_oracle ]] || python3 -I scripts/p10_c1.py build > logs/p10/p10_c1_build_pre.log 2>&1
    [[ -x build/p10/c1/c1_oracle && -x build/p10/c1/clang-O3/c1_interp_ir ]]; chk $? "the WP3 builds exist (built here if missing)"
    python3 -I scripts/p10_canary.py gate; chk $? "memory gate"
fi
echo "### scripts parse; no digits in verdict strings (rule P13)"
for f in scripts/p10_*.sh; do bash -n "$f"; chk $? "bash -n $f"; done
for f in scripts/p10_*.py; do python3 -I -c "import ast,sys;ast.parse(open(sys.argv[1]).read())" "$f"; chk $? "python syntax $f"; done
python3 -I - <<'PY'
import ast, sys
t = ast.parse(open("scripts/p10_summarize.py").read())
bad = [(n.name, c.value[:50]) for n in ast.walk(t) if isinstance(n, ast.FunctionDef) and n.name.startswith("verdict_")
       for c in ast.walk(n) if isinstance(c, ast.Constant) and isinstance(c.value, str) and any(ch.isdigit() for ch in c.value)]
print("digit-bearing strings in verdict_* functions:", bad or "none")
sys.exit(1 if bad else 0)
PY
chk $? "no typed numbers in verdict strings"
if [[ "$MODE" != --pre ]]; then
    echo "### after the run"
    [[ -s results/p10_summary.json && -s results/p10_summary.md ]]; chk $? "results/p10_summary.{md,json} exist"
    newest=$(find logs/p10/wp1 logs/p10/wp1b logs/p10/wp2a logs/p10/wp2b logs/p10/wp3 logs/p10/wp4 -type f -printf '%T@\n' 2>/dev/null | sort -n | tail -1)
    mt=$(stat -c %Y results/p10_summary.json)
    awk -v a="$mt" -v b="$newest" 'BEGIN { exit !(a >= b) }'; chk $? "the summary is newer than the newest measured log"
    python3 -I scripts/p10_check_labels.py; chk $? "every label equals its re-derivation from the stored numbers"
    if [[ -d logs/p10/wp1b/main ]]; then
        bash scripts/p10b_pre.sh --post-hash-only > logs/p10/.wp1b_hash.txt 2>&1; chk $? "WP1b design, plans and sources hash to their logged values (see below)"; grep -E '^(PASS|FAIL).*(hash|logged)' logs/p10/.wp1b_hash.txt; rm -f logs/p10/.wp1b_hash.txt
        [[ -s logs/p10/wp1b/pilot_precision.txt ]]; chk $? "the pilot precision statement exists (logs/p10/wp1b/pilot_precision.txt)"
        grep -q 'superseded' results/p10_summary.md || grep -q 'WP1 original' results/p10_summary.md; chk $? "the summary shows the original WP1 labels next to the WP1b labels"
    fi
    python3 -I - <<'PY'
import json, sys
S = json.load(open("results/p10_summary.json"))
w1 = S["wp1"]
print("WP1: %d batches, %d re-run attempts, %d final batches invalid, short cells %s" % (w1["batches"], w1["reruns"], len(w1["invalid"]), w1["short"]))
wb = S.get("wp1b")
if wb:
    print("WP1b: %d plan rows, %d attempts, %d re-run attempts, %d valid batches, %d final batches invalid, short cells %s, shortest valid wall %s s" % (wb["batches"], wb["attempts"], wb["reruns"], wb["valid"], len(wb["invalid"]), wb["short"], wb["min_wall_s"]))
print("WP2a: excluded runs %d, cells with fewer than the minimum: %s" % (len(S["wp2a"]["excluded"]), S["wp2a"]["missing_cells"]))
print("WP2b: excluded runs %d, rates: %s" % (len(S["wp2b"]["excluded"]), {r: v["status"] for r, v in S["wp2b"]["rates"].items()}))
print("WP3: excluded builds %s, independent-set mismatches %s, real-trace mismatches %s" % (S["wp3"]["excluded_builds"], S["wp3"]["indep_equiv_bad"], S["wp3"]["real_equiv_bad"]))
inc = [k for k, v in S["labels"].items() if v["label"] == "INCONCLUSIVE"]
print("labels that are INCONCLUSIVE:", inc or "none")
PY
    chk $? "validity counts printed"
    ls logs/p10/wp1 logs/p10/wp1b logs/p10/wp2a logs/p10/wp2b logs/p10/wp3 logs/p10/wp4 2>/dev/null | grep -iE 'smoke|probe' > logs/p10/.leftover.txt; [[ ! -s logs/p10/.leftover.txt ]]; chk $? "no smoke or probe files in the analysed folders"
    rm -f logs/p10/.leftover.txt
fi
echo; echo "p10_verify: $fail FAIL"
exit $((fail>0))
