#!/usr/bin/env bash
# Phase 8.4 VERIFY (no root, no traffic). Checks the hash chain of the pre-declared files, harness parity, the statistics self-test, the evidence of the
# calibration probe and of every launch that exists, recomputes the summary and the ablation from the logs (outputs deleted first) and checks that
# nothing of earlier phases changed. The result of the validation itself is information, not a gate.
# Usage: bash scripts/p8_4_verify.sh 2>&1 | tee logs/p8/p8_4/p8_4_verify.log          (set P8_4_REQUIRE_ALL=1 to require all 7 launches)
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
fail=0; D=logs/p8/p8_4; DL=$D/p8_4_design_sha256.log
chk() { if [[ $1 -eq 0 ]]; then echo "PASS: $2"; else echo "FAIL: $2"; fail=$((fail+1)); fi; }

echo "### 1. pre-declared files"
d=$(grep -E '^[0-9a-f]{64}  docs/phase8_4_design.md' $DL | tail -1 | cut -d' ' -f1); [[ "$d" == "$(sha256sum docs/phase8_4_design.md | cut -d' ' -f1)" ]]; chk $? "design file equals the last logged sha256"
n=$(grep -cE '^[0-9a-f]{64}  docs/phase8_4_design.md' $DL); echo "INFO: $n design hashes logged (first = as first written)"
python3 -I scripts/p8_4_design_chain.py > /tmp/p8_4_chain.out 2>&1; chk $? "design hash chain reproduced from the current file (log $D/p8_4_design_chain.log)"

echo "### 2. harness parity"
python3 -I - <<'PY'
import sys
a, b = open("scripts/bench.sh").read(), open("scripts/p8_4_bench.sh").read()
must = ['A) echo "build/baseline_sniffer $VA" ;;', 'B) echo "build/loader -d $VA build/phase3_kern.o" ;;', 'C) echo "build/loader $VA build/phase3_kern.o" ;;',
        'CPU_SYS=0; CPU_NOISE_CLI=1; CPU_CAP=2; CPU_SRV=3; CPU_MATCH_CLI=4', 'VA=p1veth0; IPA=10.0.0.1; IPB=10.0.0.2; NS=p2ns',
        'taskset -c "$CPU_SYS" build/classifier "$VA" > "$tmp/cls.log" 2>&1 &',
        'taskset -c "$cpu" iperf3 -c "$IPB" -B "$IPA" -p "$p" -u -b "$bw" -l "$payload" -t "$dur" -J > "$tmp/cli_$p.json" 2> "$tmp/cli_$p.err" &',
        'vmstat 1 $((dur + 2)) > "$tmp/vmstat.log" 2>&1 &', 'FLOOD_SIZE=256']
bad = [m for m in must if not (m in a and m in b)]
print("PASS: all %d reference lines identical in bench.sh and p8_4_bench.sh" % len(must) if not bad else "FAIL: %s" % bad)
sys.exit(1 if bad else 0)
PY
chk $? "capture commands, pinning, classifier, iperf3 and vmstat lines identical to bench.sh"
diff -u scripts/p8_2_bench.sh scripts/p8_4_bench.sh > /tmp/p8_4_d1.txt; diff -q /tmp/p8_4_d1.txt $D/p8_4_bench_vs_p8_2_bench.diff > /dev/null; chk $? "saved diff against p8_2_bench.sh equals the diff now"
diff -u scripts/bench.sh scripts/p8_4_bench.sh > /tmp/p8_4_d2.txt; diff -q /tmp/p8_4_d2.txt $D/p8_4_bench_vs_bench.diff > /dev/null; chk $? "saved diff against bench.sh equals the diff now"
bash -n scripts/p8_4_bench.sh; chk $? "p8_4_bench.sh syntax"

echo "### 3. statistics self-test"
python3 -I scripts/p8_2_summary.py --selftest | tail -1; python3 -I scripts/p8_2_summary.py --selftest > /dev/null; chk $? "t quantile matches the table of summarize.py"

echo "### 4. calibration probe and levels"
n=$(wc -l < $D/calib/calib.jsonl 2>/dev/null || echo 0); [[ $n -eq 78 ]]; chk $? "calibration probe 1 (excluded, superseded by A2) has 78 windows ($n)"
n=$(wc -l < $D/calib2/calib.jsonl 2>/dev/null || echo 0); [[ $n -eq 51 ]]; chk $? "calibration probe 2 wrote 51 windows ($n)"
[[ -s results/p8_4_levels.json && -s results/p8_4_levels.md ]]; chk $? "levels chosen by scripts/p8_4_levels.py exist"
grep -q "A3 (" docs/phase8_4_design.md; chk $? "amendment A3 (levels chosen from calibration probe 2) is in the design"

echo "### 5. launches"
have=0
for B in C1 C2 C3 F1 F2 F3 X1; do
    L=$D/$B
    if [[ ! -d $L/runs || -z "$(ls -A $L/runs 2>/dev/null)" ]]; then echo "INFO: launch $B has no runs yet"; continue; fi
    have=$((have+1))
    p=$(grep -E "^[0-9a-f]{64}  results/p8_4_plan_$B.tsv" $D/p8_4_plan_sha256.log | tail -1 | cut -d' ' -f1); [[ "$p" == "$(sha256sum results/p8_4_plan_$B.tsv | cut -d' ' -f1)" ]]; chk $? "$B: plan equals the logged sha256"
    grep -q "launch $B started .*design in force = after A[3-9]" $D/p8_4_design_chain.log; chk $? "$B: the design version in force at the launch was at least A3 (hash chain log; later amendments are post hoc)"
    grep -q "=== FINISHED" $L/p8_4_${B}_console.log; chk $? "$B: console log ends with FINISHED"
    grep -q "memory gate passed" $L/p8_4_${B}_console.log && grep -q "pre-flight passed" $L/p8_4_${B}_console.log; chk $? "$B: memory gate and pre-flight passed before the plan"
    P8_4_B="$B" python3 -I - <<'PY'
import os, sys
B = os.environ["P8_4_B"]; bad = 0
rows = [l.split("\t") for l in open("results/p8_4_plan_%s.tsv" % B).read().splitlines() if l and not l.startswith("#")]
for seq, exp, label, cfg, traffic, size, rep, pps, spec in rows:
    f = "logs/p8/p8_4/%s/runs/%s_%s_%s_%s_%s.log" % (B, label, cfg, traffic, size, rep)
    ok = os.path.exists(f)
    if ok:
        t = open(f).read()
        ok = t.rstrip().splitlines()[-1].startswith("# end=") and "NOISE_READY" in t and "NOISE_STOP" in t and ("noise=" + spec) in t
    if not ok: bad += 1; print("FAIL: evidence missing/incomplete for", B, seq, label, rep)
print("%s: %s all %d rows have a complete log with NOISE_READY, NOISE_STOP and the planned noise spec" % ("PASS" if not bad else "FAIL", B, len(rows)))
sys.exit(1 if bad else 0)
PY
    chk $? "$B: plan rows complete"
done
[[ "${P8_4_REQUIRE_ALL:-0}" != 1 || $have -eq 7 ]]; chk $? "launches present: $have of 7 (P8_4_REQUIRE_ALL=${P8_4_REQUIRE_ALL:-0})"

echo "### 6. summary and ablation recomputed from the logs (outputs deleted first, checked after)"
if [[ $have -gt 0 ]]; then
    cp results/p8_4_summary.md /tmp/p8_4_summary_before.md 2>/dev/null;
    python3 -I scripts/p8_4_summary.py > $D/p8_4_summary.out 2>&1; chk $? "p8_4_summary.py (log $D/p8_4_summary.out)"
    [[ -s results/p8_4_summary.md && -s results/p8_4_summary.json ]]; chk $? "summary files created by this run"
    grep -E '^## Overall' results/p8_4_summary.md
fi
python3 -I scripts/p8_4_timecheck.py > /tmp/p8_4_timecheck.out 2>&1; chk $? "no analysed window spans a clock jump (log $D/p8_4_timecheck.log)"
rm -f results/p8_4_blocked.md results/p8_4_blocked.json
python3 -I scripts/p8_4_blocked.py > $D/p8_4_blocked.out 2>&1; chk $? "p8_4_blocked.py (post hoc, amendment A4; log $D/p8_4_blocked.out)"
[[ -s results/p8_4_blocked.md && -s results/p8_4_blocked.json ]]; chk $? "blocked files created by this run"
grep -E '^## Overall' results/p8_4_blocked.md
python3 -I - <<'PY'
import re, sys
srcs = ["results/p8_4_summary.md", "results/p8_4_blocked.md", "results/p8_4_ablation.md"]
allowed = "".join(open(p).read() for p in srcs)
f = re.sub(r"```.*?```", "", open("results/p8_4_findings.md").read(), flags=re.S)   # fenced blocks (script output embedded verbatim) are not checked
miss = [(t, n) for t in re.findall(r"`([^`]*)`", f) for n in re.findall(r"\d[\d.]*\d|\d", t) if n not in allowed and not t.startswith(("results/", "scripts/", "docs/", "logs/"))]
print("PASS: all backticked numbers of results/p8_4_findings.md occur in the sources" if not miss else "FAIL: not found: %s" % miss)
sys.exit(1 if miss else 0)
PY
chk $? "findings numbers come from the sources"
python3 -I scripts/p8_4_ablation.py > $D/p8_4_ablation.out 2>&1; chk $? "p8_4_ablation.py reproduces the published Phase 6 and 8.2 verdicts (variant P) (log $D/p8_4_ablation.out)"
[[ -s results/p8_4_ablation.md ]]; chk $? "ablation files created by this run"

echo "### 7. nothing from earlier phases modified"
chg=$(git status --short | grep -vE '^\?\? (logs/p8/p8_4/|scripts/p8_4_|results/p8_4_|docs/phase8_4_design.md)' | grep -vE '^ M (CODE_NOTES.md|DEVIATIONS.md)$' || true)
[[ -z "$chg" ]]; chk $? "only Phase 8.4 files, CODE_NOTES.md and DEVIATIONS.md changed: ${chg:-none}"
git diff --quiet -- logs/p6c logs/bench_A_flood_256_1.log scripts/bench.sh scripts/summarize.py scripts/p8_2_bench.sh scripts/p8_2_summary.py results/baseline_calibration.json results/summary.json docs/phase6_addenda.md; chk $? "Phase 6 and 8.2 scripts, logs and results unchanged"

echo; echo "p8_4_verify: $fail FAIL"
exit $((fail>0))
