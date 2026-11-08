#!/usr/bin/env bash
# p10_run_all.sh - Phase 10 measurement blocks of WP1 to WP4 in ONE launch (docs/phase10_design.md section 8). Hands-off: nothing may be touched while it runs.
# Launch (fresh Terminal tab, from /home/mahim/bpf-repl):  sudo bash scripts/p10_run_all.sh 2>&1 | tee logs/p10/p10_run_all_console.log
# Every block starts with the pre-flight (memory gate, 60 s settle, 3 idle windows that must pass V8) and the whole run aborts on the first failing step.
# Refuses to start if logs/p10/{wp1,wp2a,wp2b,wp3,wp4,run_all}, results/p10_summary.* exist and are non-empty, or if scripts/p10_verify.sh --pre fails.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
# shellcheck source=scripts/p10_lib.sh
source scripts/p10_lib.sh
L=logs/p10
for d in $L/wp1 $L/wp2a $L/wp2b $L/wp3 $L/wp4 $L/run_all $L/preflight; do
    if [[ -d $d && -n "$(ls -A "$d")" ]]; then echo "ABORT: $d is not empty; refusing to overwrite (move it away on purpose)" >&2; exit 1; fi
done
for f in results/p10_summary.md results/p10_summary.json; do [[ ! -e $f ]] || { echo "ABORT: $f exists (a previous summary); move it away on purpose" >&2; exit 1; }; done
mkdir -p $L/run_all $L/preflight $L/wp1 $L/wp2a $L/wp2b $L/wp3 $L/wp4
TL=$L/run_all/timeline.txt
abort() { echo "ABORT: $*" | tee -a $L/run_all/abort.txt; chown -R "${SUDO_USER:-root}": $L 2>/dev/null; exit 1; }
bash scripts/p10_verify.sh --pre 2>&1 | tee $L/run_all/pre_verify.log
[[ ${PIPESTATUS[0]} -eq 0 ]] || abort "pre-launch checks failed (see $L/run_all/pre_verify.log)"
T0=$(date +%s)
mark() { echo "$(date -Is) $*" | tee -a $TL; }
limit_of() { python3 -I -c "import json,sys;print(json.load(open(sys.argv[1]))['limit'])" "$1"; }
mark "START of the Phase 10 measured run"
free -m | tee $L/run_all/free_start.txt

mark "BLOCK B1 WP1 (microbenchmarks)"
p10_preflight WP1 0,1,3,4 $L/preflight/wp1 || abort "pre-flight of WP1"
bash scripts/p10_wp1.sh $L/wp1 "$(limit_of $L/preflight/wp1/preflight.json)" || abort "WP1"
p10_block_end WP1 $L/preflight/wp1

mark "BLOCK B2 WP2(a) (mitigation test)"
p10_preflight WP2a 0,1 $L/preflight/wp2a || abort "pre-flight of WP2a"
bash scripts/p10_wp2.sh a $L/wp2a || abort "WP2a"
p10_block_end WP2a $L/preflight/wp2a

mark "BLOCK B3 WP2(b) (paced ladder)"
p10_preflight WP2b 0,1 $L/preflight/wp2b || abort "pre-flight of WP2b"
bash scripts/p10_wp2.sh b $L/wp2b || abort "WP2b"
p10_block_end WP2b $L/preflight/wp2b

mark "BLOCK B4 WP3 (C1 hardening)"
p10_preflight WP3 0,1,2,3,4 $L/preflight/wp3 || abort "pre-flight of WP3"
python3 -I scripts/p10_c1.py build > $L/wp3/build.log 2>&1 || abort "WP3 build (see $L/wp3/build.log)"
for st in grid; do
    python3 -I scripts/p10_c1.py $st > $L/wp3/$st.log 2>&1; rc=$?
    [[ $rc -eq 0 || $rc -eq 2 ]] || abort "WP3 $st (rc $rc, see $L/wp3/$st.log)"
    [[ $rc -eq 2 ]] && mark "note: WP3 $st reported decision mismatches (the summary excludes those builds)"
done
python3 -I scripts/p10_c1.py indep src/p10_indep > $L/wp3/indep.log 2>&1; rc=$?
[[ $rc -eq 0 || $rc -eq 2 ]] || abort "WP3 indep (rc $rc, see $L/wp3/indep.log)"
read -r H G < build/p10/real_anon.pcap.hg
python3 -I scripts/p10_c1.py real build/p10/real_anon.pcap "$H" "$G" > $L/wp3/real.log 2>&1; rc=$?
[[ $rc -eq 0 || $rc -eq 2 ]] || abort "WP3 real (rc $rc, see $L/wp3/real.log)"
p10_block_end WP3 $L/preflight/wp3

mark "BLOCK B5 WP4 (verifier loops)"
p10_preflight WP4 0,1,2,3,4 $L/preflight/wp4 || abort "pre-flight of WP4"
bash scripts/p10_c5.sh $L/wp4 || abort "WP4"
p10_block_end WP4 $L/preflight/wp4

free -m | tee $L/run_all/free_end.txt
mark "FINISHED after $(( ($(date +%s) - T0) / 60 )) minutes"
chown -R "${SUDO_USER:-root}": $L 2>> $L/run_all/chown.txt
echo "=== RUN FINISHED: tell Claude; do not open anything else until then ==="
