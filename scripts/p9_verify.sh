#!/usr/bin/env bash
# Phase 9 VERIFY (integrity audit). Static checks only: nothing is measured and no data file is written except the logs of this script in logs/p9/audit/ (deleted first, checked after).
# Usage: bash scripts/p9_verify.sh 2>&1 | tee logs/p9/audit/p9_verify.log
# Checks: raw logs unchanged against origin/main, results/phase6_noisy against the last pre-8.3 commit, DEVIATIONS.md coverage, headline labels in REPORT.md and results/verdicts.md,
# forbidden phrases, the demo script hash and output, presentation.html unchanged, secrets scan over the Phase 9 files.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
fail=0; D=logs/p9/audit
chk() { if [[ $1 -eq 0 ]]; then echo "PASS: $2"; else echo "FAIL: $2"; fail=$((fail+1)); fi; }
mkdir -p $D; rm -f $D/p9_secrets_scan.log

echo "### 3. raw logs unchanged against origin/main"
git rev-parse --verify -q origin/main > /dev/null; chk $? "origin/main exists locally ($(git rev-parse --short origin/main 2>&1))"
chg=$(git diff --name-only origin/main -- logs | grep -E '^logs/(bench_[^/]*\.log|attempts/)' || true)
untr=$(git ls-files --others --exclude-standard logs | grep -E '^logs/(bench_[^/]*\.log|attempts/)' || true)
[[ -z "$chg$untr" ]]; chk $? "no logs/bench_*.log or logs/attempts/*.log differs from origin/main or is new (changed: ${chg:-none}; untracked: ${untr:-none})"
echo "  git diff --stat origin/main -- logs/ (all, for the record):"; git diff --stat origin/main -- logs | sed 's/^/    /'

echo "### 4. results/phase6_noisy against the last pre-8.3 commit"
last6=$(git rev-parse 995ccbf^); echo "  last pre-8.3 commit: $(git log -1 --format='%h %s' "$last6")"
[[ "$(git rev-parse --short "$last6")" == dcd9fd0 ]]; chk $? "the parent of the first Phase 8.3 commit (995ccbf) is dcd9fd0"
n=0; bad=0
for f in summary.md summary.json verdicts.md exclusions.md runs.json figures_data.json baseline_calibration.json calibration.json bench_plan.tsv fig_cpu_cost.png fig_drop_rate.png; do
    n=$((n+1)); a=$(git rev-parse "$last6:results/$f" 2>/dev/null || echo missing); b=$(git hash-object "results/phase6_noisy/$f" 2>/dev/null || echo missing)
    [[ "$a" == "$b" && "$a" != missing ]] || { echo "  MISMATCH $f: history $a, copy $b"; bad=$((bad+1)); }
done
[[ $bad -eq 0 ]]; chk $? "all $n files of results/phase6_noisy have the git blob id of results/<name> at $(git rev-parse --short "$last6") ($bad mismatches)"

echo "### 5. DEVIATIONS.md coverage"
dev=DEVIATIONS.md
has() { grep -qF -- "$1" $dev; }
has 'D8.19 What Phase 8.3 was: the whole matrix' && has 'bench.sh plan' && has 'no design document'; chk $? "Phase 8.3 quiet re-run (D8.19): whole matrix, no pre-declaration"
has 'D8.20 Offered rate of the curve runs: 16000 pps instead of 32000' && has '"calibration": "HOLD"' && has 'Release record: none'; chk $? "16000 pps and HOLD, with the statement that no release is on record (D8.20)"
has 'D8.22 A flood V8 floor of 0.035' && has 'no calibration record'; chk $? "flood floor 0.035 with no calibration record (D8.22)"
has 'SUMMARIZE_IDLE_BASELINE=calibration' && has '0.030 CPU-s/s'; chk $? "net-CPU baseline: session idle windows 0.030 against calibration baseline (D8.21)"
has 'session=nosession' && has 'session=run_1793446731' && has 'D8.23'; chk $? "the 15 log-header edits (D8.23)"
has 'D8.24 Bracketed narrative' && has 'D8.25 Phase 9'; chk $? "verdict-string changes (D8.24, D8.25)"

echo "### 6. headline labels and forbidden phrases"
python3 -I - <<'PY'
import json, re, sys
v = json.load(open("results/summary.json"))["verdicts"]
vd = open("results/verdicts.md").read()
rp = open("REPORT.md").read()
ok = True
def t(cond, msg):
    global ok
    print(("PASS: " if cond else "FAIL: ") + msg)
    ok = ok and cond
t(v["C4"][0] == "INCONCLUSIVE", "results/summary.json verdicts.C4 is the frozen no-floor label: %s" % v["C4"][0])
t("**Verdict: INCONCLUSIVE** (frozen V8 rule, no floor)" in vd, "results/verdicts.md C4 section starts with the frozen no-floor label")
t(re.search(r"\*\*Sensitivity analysis, post hoc and uncalibrated flood V8 floor.*: " + re.escape(v["C4_floor"][0]) + r"\*\*", vd) is not None, "results/verdicts.md labels the floor result as a post hoc sensitivity analysis (%s)" % v["C4_floor"][0])
t("**Phase 6 (noisy session) for comparison: NOT SUPPORTED**" in vd, "results/verdicts.md states the Phase 6 label NOT SUPPORTED")
row = next(l for l in rp.splitlines() if l.startswith("| C4 |"))
t("**INCONCLUSIVE** under the frozen V8 rule" in row and "sensitivity analysis" in row and "gave **NOT SUPPORTED**" in row, "REPORT.md claims matrix C4 row: frozen label, sensitivity analysis, Phase 6 NOT SUPPORTED")
sys.exit(0 if ok else 1)
PY
chk $? "headline labels (details above)"
hits=$(grep -nE "Operationally Replicated|100 GB/s" REPORT.md results/*.md scripts/summarize.py || true)
[[ -z "$hits" ]]; chk $? "no 'Operationally Replicated' or '100 GB/s' in REPORT.md, results/*.md, scripts/summarize.py (${hits:-none})"

echo "### 7. demo_c1.sh"
[[ "$(sha256sum scripts/demo_c1.sh | cut -d' ' -f1)" == 6b2a81ed4d890a6fc9caeff88b34b4368376a147053808a49f98c6e6e6a68024 ]]; chk $? "scripts/demo_c1.sh sha256"
grep -q 'ratio stack / register = 17.5x' logs/p9/p9_demo_c1.log && [[ $(grep -c 'decision mismatches vs libpcap: 0 of 10000' logs/p9/p9_demo_c1.log) -eq 2 ]]; chk $? "logs/p9/p9_demo_c1.log shows 17.5x and 0 mismatches for both machines"

echo "### 8. presentation.html"
git diff --quiet origin/main -- presentation.html; chk $? "presentation.html is unchanged compared with origin/main"

echo "### 9. secrets scan over the Phase 9 files (patterns; no scanner installed)"
files=$( (git diff --name-only origin/main; git ls-files --others --exclude-standard) | sort -u )
PAT='AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(password|passwd|secret|api[_-]?key|token)[ "'"'"']*[:=][ "'"'"']*[A-Za-z0-9/+_-]{8,}|Authorization: *Bearer|ssh-rs[a] AAAA|AIza[0-9A-Za-z_-]{30,}'
nf=0; hits=0
for f in $files; do
    [[ -f "$f" ]] || continue
    case "$f" in *.png|*.pdf|logs/p9/audit/*) continue;; esac
    nf=$((nf+1)); if grep -InE "$PAT" "$f" > /dev/null 2>&1; then echo "  HIT in $f"; hits=$((hits+1)); fi
done
echo "files scanned: $nf; files with hits: $hits" | tee $D/p9_secrets_scan.log
[[ -s $D/p9_secrets_scan.log && $hits -eq 0 ]]; chk $? "secrets scan: $nf files, $hits hits (log $D/p9_secrets_scan.log, created by this run)"

echo; echo "p9_verify: $fail FAIL"
exit $((fail>0))
