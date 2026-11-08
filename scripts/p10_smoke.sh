#!/usr/bin/env bash
# p10_smoke.sh - Phase 10 smoke run of every privileged tool with tiny plans (docs/phase10_design.md section 1: smoke runs are excluded from every verdict).
# Output only under logs/p10/smoke/. Needs root. Usage: sudo bash scripts/p10_smoke.sh 2>&1 | tee logs/p10/smoke/p10_smoke_console.log      (about 12 minutes)
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
S=logs/p10/smoke
for d in wp1 wp2a wp2b wp4; do
    if [[ -d $S/$d && -n "$(ls -A "$S/$d")" ]]; then echo "ABORT: $S/$d is not empty; refusing to overwrite (move it away on purpose)" >&2; exit 1; fi
done
mkdir -p $S
for t in p10_memcpy p10_testrun p10_drain; do [[ -x build/p10/$t ]] || { echo "FATAL: build/p10/$t missing: run scripts/p10_build.sh" >&2; exit 1; }; done
# tiny plans (same columns as the real plans)
{ echo -e "# seq\tkind\tsize\tbatch"; n=0; for k in memcpy tr_reject tr_accept tr_port dr_U dr_E dr_B; do for sz in 64 1500; do n=$((n+1)); echo -e "$n\t$k\t$sz\t1"; done; done; } > $S/plan_wp1_smoke.tsv
echo -e "# seq\ttopology\tcfg\trep\n1\tT0\tN\t1\n2\tT0\tA\t1\n3\tT1\tN\t1\n4\tT1\tA\t1\n5\tT1\tB\t1\n6\tT1\tC\t1" > $S/plan_wp2a_smoke.tsv
echo -e "# seq\tcfg\trate\trep\n1\tA\t100000\t1\n2\tB\t100000\t1\n3\tC\t100000\t1\n4\tA\t450000\t1\n5\tB\t450000\t1\n6\tC\t450000\t1" > $S/plan_wp2b_smoke.tsv
echo "=== smoke: WP1 $(date +%T)"
bash scripts/p10_wp1.sh $S/wp1 100 $S/plan_wp1_smoke.tsv || { echo "SMOKE FAIL: wp1"; exit 1; }
echo "=== smoke: WP4 $(date +%T)"
bash scripts/p10_c5.sh $S/wp4 || { echo "SMOKE FAIL: wp4"; exit 1; }
echo "=== smoke: WP2a $(date +%T)"
P10_PLAN=$S/plan_wp2a_smoke.tsv P10_CALIB_N=1 bash scripts/p10_wp2.sh a $S/wp2a || { echo "SMOKE FAIL: wp2a"; exit 1; }
echo "=== smoke: WP2b $(date +%T)"
P10_PLAN=$S/plan_wp2b_smoke.tsv P10_CALIB_N=1 bash scripts/p10_wp2.sh b $S/wp2b || { echo "SMOKE FAIL: wp2b"; exit 1; }
chown -R "${SUDO_USER:-root}": $S 2>> $S/chown.txt
echo "=== smoke finished $(date +%T)"
