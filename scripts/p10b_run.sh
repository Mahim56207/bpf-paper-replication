#!/usr/bin/env bash
# p10b_run.sh - Phase 10 WP1b in ONE launch (docs/phase10_wp1b_design.md section 7): checks, smoke stage (excluded), pilot block (excluded, precision statement), main block.
# Hands-off: nothing may be touched while it runs.
# Launch (fresh Terminal tab, from /home/mahim/bpf-repl):  sudo bash scripts/p10b_run.sh 2>&1 | tee logs/p10/p10b_run_console.log
# Refuses to start if logs/p10/wp1b, logs/p10/wp1b_smoke, logs/p10/run_wp1b or logs/p10/preflight/wp1b_* exist and are non-empty. Aborts on the first failing step.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
# shellcheck source=scripts/p10_lib.sh
source scripts/p10_lib.sh
L=logs/p10; MIN_S=5.0
for d in $L/wp1b $L/wp1b_smoke $L/run_wp1b $L/preflight/wp1b_pilot $L/preflight/wp1b_main; do
    if [[ -d $d && -n "$(ls -A "$d")" ]]; then echo "ABORT: $d is not empty; refusing to overwrite (move it away on purpose)" >&2; exit 1; fi
done
mkdir -p $L/run_wp1b $L/wp1b/pilot $L/wp1b/main $L/wp1b_smoke $L/preflight
TL=$L/run_wp1b/timeline.txt
abort() { echo "ABORT: $*" | tee -a $L/run_wp1b/abort.txt; chown -R "${SUDO_USER:-root}": $L 2>/dev/null; exit 1; }
bash scripts/p10b_pre.sh 2>&1 | tee $L/run_wp1b/pre_check.log
[[ ${PIPESTATUS[0]} -eq 0 ]] || abort "pre-launch checks failed (see $L/run_wp1b/pre_check.log)"
mark() { echo "$(date -Is) $*" | tee -a $TL; }
limit_of() { python3 -I -c "import json,sys;print(json.load(open(sys.argv[1]))['limit'])" "$1"; }
mark "START of WP1b"
free -m | tee $L/run_wp1b/free_start.txt

mark "STAGE smoke (7 batches of 0.4 s, excluded from every verdict; canary limit not applied)"
bash scripts/p10b_wp1.sh $L/wp1b_smoke 1000000 results/p10_plan_wp1b_smoke.tsv 0.4 || abort "smoke stage"
python3 -I scripts/p10b_check_smoke.py $L/wp1b_smoke results/p10_plan_wp1b_smoke.tsv 0.4 | tee $L/run_wp1b/smoke_check.log
[[ ${PIPESTATUS[0]} -eq 0 ]] || abort "smoke check (see $L/run_wp1b/smoke_check.log)"

mark "BLOCK pilot (3 batches per kind and size, excluded from every verdict)"
p10_preflight WP1b-pilot 0,1,3,4 $L/preflight/wp1b_pilot || abort "pre-flight of the pilot"
bash scripts/p10b_wp1.sh $L/wp1b/pilot "$(limit_of $L/preflight/wp1b_pilot/preflight.json)" results/p10_plan_wp1b_pilot.tsv $MIN_S || abort "pilot"
p10_block_end WP1b-pilot $L/preflight/wp1b_pilot
python3 -I scripts/p10b_pilot_precision.py $L/wp1b/pilot > $L/wp1b/pilot_precision.txt 2>&1; rc=$?
cat $L/wp1b/pilot_precision.txt
[[ $rc -eq 0 && -s $L/wp1b/pilot_precision.txt ]] || abort "pilot precision statement (rc $rc)"

mark "BLOCK main (12 batches per kind and size)"
p10_preflight WP1b-main 0,1,3,4 $L/preflight/wp1b_main || abort "pre-flight of the main block"
bash scripts/p10b_wp1.sh $L/wp1b/main "$(limit_of $L/preflight/wp1b_main/preflight.json)" results/p10_plan_wp1b.tsv $MIN_S || abort "main block"
p10_block_end WP1b-main $L/preflight/wp1b_main

free -m | tee $L/run_wp1b/free_end.txt
chown -R "${SUDO_USER:-root}": $L 2> $L/run_wp1b/chown.txt
mark "FINISHED after $(( $(date +%s) - $(date -d "$(head -1 $TL | cut -d' ' -f1)" +%s) )) s"
echo "=== WP1b RUN FINISHED: tell Claude; do not open anything else until then ==="
