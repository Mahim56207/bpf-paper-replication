#!/usr/bin/env bash
# Phase 8.2 VERIFY (no root, no traffic): completeness of the run evidence, hash chain of the pre-declared files, harness parity with
# bench.sh, deterministic summary recomputed from the logs (outputs deleted first), unit check of the statistics, and that nothing from
# earlier phases changed. The verdict itself is information, not a gate.
# Run set 1: bash scripts/p8_2_verify.sh 2>&1 | tee logs/p8/p8_2/p8_2_verify.log
# Run set 2: P8_2_RUN=run2 bash scripts/p8_2_verify.sh 2>&1 | tee logs/p8/p8_2/run2/p8_2_verify_run2.log   (amendment A2)
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
fail=0; RUN="${P8_2_RUN:-}"; export P8_2_RUN="$RUN"
if [[ -z "$RUN" ]]; then L=logs/p8/p8_2; PLAN=results/p8_2_plan.tsv; PLANLOG=$L/p8_2_plan_sha256.log; CON=$L/p8_2_run_console.log; SUM=results/p8_2_summary
else L=logs/p8/p8_2/$RUN; PLAN=results/p8_2_plan_$RUN.tsv; PLANLOG=logs/p8/p8_2/p8_2_plan_${RUN}_sha256.log; CON=$L/p8_2_${RUN}_console.log; SUM=results/p8_2_summary_$RUN; fi
DL=logs/p8/p8_2/p8_2_design_sha256.log
chk() { if [[ $1 -eq 0 ]]; then echo "PASS: $2"; else echo "FAIL: $2"; fail=$((fail+1)); fi; }
echo "run set: ${RUN:-run1}  evidence dir: $L"

echo "### 1. pre-declared files and hashes"
d=$(grep -E '^[0-9a-f]{64}  docs/phase8_2_design.md' $DL | tail -1 | cut -d' ' -f1); [[ "$d" == "$(sha256sum docs/phase8_2_design.md | cut -d' ' -f1)" ]]; chk $? "design file equals the last logged sha256"
d0=$(grep -E '^[0-9a-f]{64}  docs/phase8_2_design.md' $DL | head -1 | cut -d' ' -f1); [[ -n "$d0" && "$d0" != "$d" ]]; chk $? "first logged design hash differs from the amended one (amendments logged before the run)"
[[ -s $DL && $(stat -c %Y $DL) -lt $(stat -c %Y $L/run_context.txt 2>/dev/null || echo 9999999999) ]]; chk $? "design hash log is older than the run context (hash logged before the run)"
p=$(grep -E "^[0-9a-f]{64}  $PLAN" $PLANLOG | tail -1 | cut -d' ' -f1); [[ "$p" == "$(sha256sum $PLAN | cut -d' ' -f1)" ]]; chk $? "plan file equals the logged sha256"
n=$(grep -vc '^#' $PLAN); [[ $n -eq 40 ]]; chk $? "plan has 40 rows ($n)"

python3 -I scripts/p8_2_design_chain.py > /tmp/p8_2_chain.out 2>&1; chk $? "design hash chain: the three logged hashes are reproduced from the current file, logged before the probe and the run (logs/p8/p8_2/p8_2_design_chain.log)"

echo "### 2. harness parity with scripts/bench.sh"
python3 -I - <<'PY'
import sys
a, b = open("scripts/bench.sh").read(), open("scripts/p8_2_bench.sh").read()
must = ['A) echo "build/baseline_sniffer $VA" ;;', 'B) echo "build/loader -d $VA build/phase3_kern.o" ;;', 'C) echo "build/loader $VA build/phase3_kern.o" ;;',
        'CPU_SYS=0; CPU_NOISE_CLI=1; CPU_CAP=2; CPU_SRV=3; CPU_MATCH_CLI=4', 'VA=p1veth0; IPA=10.0.0.1; IPB=10.0.0.2; NS=p2ns',
        'taskset -c "$CPU_SYS" build/classifier "$VA" > "$tmp/cls.log" 2>&1 &',
        'taskset -c "$cpu" iperf3 -c "$IPB" -B "$IPA" -p "$p" -u -b "$bw" -l "$payload" -t "$dur" -J > "$tmp/cli_$p.json" 2> "$tmp/cli_$p.err" &',
        'ip netns exec "$NS" taskset -c "$CPU_SRV" iperf3 -s -B "$IPB" -p "$p" -J --logfile "$tmp/srv_$p.json" -1 &',
        'vmstat 1 $((dur + 2)) > "$tmp/vmstat.log" 2>&1 &', 'FLOOD_SIZE=256']
bad = 0
for m in must:
    ok = m in a and m in b
    bad += not ok
    print("%s: identical in both scripts: %s" % ("PASS" if ok else "FAIL", m[:90]))
sys.exit(1 if bad else 0)
PY
chk $? "capture commands, pinning, classifier, iperf3 and vmstat lines identical to bench.sh"
diff -u scripts/bench.sh scripts/p8_2_bench.sh > /tmp/p8_2_diff_now.txt; diff -q /tmp/p8_2_diff_now.txt logs/p8/p8_2/p8_2_bench_vs_bench.diff > /dev/null; chk $? "saved diff equals diff -u bench.sh p8_2_bench.sh now"
bash -n scripts/p8_2_bench.sh; chk $? "p8_2_bench.sh syntax"

echo "### 3. statistics unit check"
python3 -I scripts/p8_2_summary.py --selftest; chk $? "t quantile matches the table of summarize.py (df 1..30) and the normal limit"

echo "### 4. run evidence complete"
for f in $L/run_context.txt $CON; do [[ -s $f ]]; chk $? "$f exists"; done
grep -q "=== FINISHED" $CON; chk $? "run console log ends with FINISHED"
grep -q "pre-flight passed" $CON; chk $? "pre-flight passed before the plan started"
if [[ -n "$RUN" ]]; then grep -q "memory gate passed" $CON; chk $? "memory gate passed before the settle (amendment A2 item 3)"; grep -E "^memory gate:" $CON; fi
P8_2_L="$L" P8_2_PLAN="$PLAN" python3 -I - <<'PY'
import glob, os, sys
L, PLAN = os.environ["P8_2_L"], os.environ["P8_2_PLAN"]
bad = 0
rows = [l.split("\t") for l in open(PLAN).read().splitlines() if l and not l.startswith("#")]
for seq, prof, cfg, rep in rows:
    lab = "p82prof" if prof == "1" else "p82"
    f = "%s/runs/%s_%s_flood_256_%s.log" % (L, lab, cfg, rep)
    ok = os.path.exists(f) and open(f).read().rstrip().splitlines()[-1].startswith("# end=")
    if prof == "1":
        ok = ok and os.path.exists("%s/profiles/%s_%s_flood_256_%s_a1.json" % (L, lab, cfg, rep))
    if not ok:
        bad += 1; print("FAIL: missing or incomplete evidence for plan row", seq, prof, cfg, rep)
print("%s: 40 plan rows have a complete final log (profiled rows also a counts file)" % ("PASS" if not bad else "FAIL"))
pre = glob.glob(L + "/preflight/p82pre_D_idle_0_[123].log")
print("%s: 3 pre-flight windows (%d)" % ("PASS" if len(pre) == 3 else "FAIL", len(pre)))
sys.exit(1 if bad or len(pre) != 3 else 0)
PY
chk $? "plan rows and pre-flight windows complete"
shopt -s nullglob; pf=($L/profiles/perf_data_sha256.log); [[ -s ${pf[0]:-/nonexistent} ]]; chk $? "perf data hashes logged"
if [[ -n "$RUN" ]]; then
    n_task=$(grep -h -c '^task ' $L/runs/p82_N_flood_256_1.log 2>/dev/null | head -1); [[ ${n_task:-0} -gt 0 ]]; chk $? "run set 2 logs contain the A2 task lines (${n_task:-0} in one N log)"
    # INFO, not a gate: the run set 1 raw evidence was deleted by a wrong launch before run set 2 (incident D8.14), so this manifest can no longer be satisfied
    (cd logs/p8/p8_2 && sha256sum -c p8_2_run1_manifest.sha256 > /tmp/p8_2_manifest_check.txt 2>&1)
    echo "INFO: run set 1 manifest (105 files hashed before the incident D8.14): $(grep -c ': OK$' /tmp/p8_2_manifest_check.txt) OK, $(grep -c ': FAILED$' /tmp/p8_2_manifest_check.txt) changed, $(grep -c 'FAILED open or read$' /tmp/p8_2_manifest_check.txt) missing"
    n_new=$(find logs/p8/p8_2/runs logs/p8/p8_2/profiles logs/p8/p8_2/attempts -type f 2>/dev/null | wc -l); [[ $n_new -eq 0 ]]; chk $? "run set 2 wrote nothing into the run set 1 folders ($n_new files there)"
fi

echo "### 5. summary recomputed from the logs (outputs deleted first, checked after)"
rm -f /tmp/p8_2_summary_before.md   # no stale temp file from another run set
cp $SUM.md /tmp/p8_2_summary_before.md 2>/dev/null
rm -f $SUM.md $SUM.json
python3 -I scripts/p8_2_summary.py > $L/p8_2_summary.out 2>&1; chk $? "p8_2_summary.py (log $L/p8_2_summary.out)"
[[ -s $SUM.md && -s $SUM.json ]]; chk $? "summary files created by this run"
# determinism: identical except the S-H1 sentence, whose wording was corrected by amendment A2 item 7 after run set 1 was summarized
[[ -f /tmp/p8_2_summary_before.md ]] && { diff -q <(grep -v '^\*\*S-H1' /tmp/p8_2_summary_before.md) <(grep -v '^\*\*S-H1' $SUM.md) > /dev/null; chk $? "summary identical to the previous computation (S-H1 sentence excluded; deterministic)"; }
grep -E '^\*\*(S-H1|S-H2)|^\*\*[A-Z -]+\*\* \(' $SUM.md
python3 -I scripts/p8_2_diag_core0.py > $L/p8_2_diag_core0.out 2>&1; chk $? "p8_2_diag_core0.py (informational; log $L/p8_2_diag_core0.out)"

echo "### 6. nothing from earlier phases modified"
chg=$(git status --short | grep -vE '^\?\? (logs/p8/p8_2/|scripts/p8_2_|results/p8_2_|docs/phase8_2_design.md)' | grep -vE '^ M (CODE_NOTES.md|DEVIATIONS.md)$' || true)
[[ -z "$chg" ]]; chk $? "only Phase 8.2 files, CODE_NOTES.md and DEVIATIONS.md changed: ${chg:-none}"
git diff --quiet -- logs/p6c scripts/bench.sh scripts/summarize.py docs/phase6_design.md docs/phase6_addenda.md results/baseline_calibration.json; chk $? "bench.sh, summarize.py, Phase 6 docs, logs/p6c and baseline_calibration.json unchanged"

echo "### 7. findings file: every number in backticks occurs in its sources"
python3 -I - <<'PY'
import re, sys
srcs = ["results/p8_2_summary_run2.md", "results/p8_2_summary.md", "logs/p8/p8_2/p8_2_design_chain.log", "docs/phase8_2_design.md",
        "logs/p8/p8_2/p8_2_diag_vmstat_core0.log", "results/p8_2_diag_core0_run2.md", "logs/p8/p8_2/run2/p8_2_run2_console.log"]
allowed = "".join(open(p).read() for p in srcs)
f = open("results/p8_2_findings.md").read()
miss = [(t, n) for t in re.findall(r"`([^`]*)`", f) for n in re.findall(r"\d[\d.]*\d|\d", t) if n not in allowed]
print("PASS: all backticked numbers of results/p8_2_findings.md occur in the sources" if not miss else "FAIL: not found: %s" % miss)
sys.exit(1 if miss else 0)
PY
chk $? "findings numbers come from the sources"

echo; echo "p8_2_verify: $fail FAIL"
exit $((fail>0))
