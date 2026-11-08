#!/usr/bin/env bash
# rehearse.sh - runs run_demo.sh twice, one after the other, with the output of each run tee'd into logs/demo_rehearsal_1.log and logs/demo_rehearsal_2.log, and prints the wall time
# of each. Refuses to start if either log exists. Usage: sudo bash scripts/demo/rehearse.sh
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
[[ $EUID -eq 0 ]] || { echo "rehearse: run with sudo: sudo bash scripts/demo/rehearse.sh" >&2; exit 1; }
for n in 1 2; do [[ ! -e logs/demo_rehearsal_$n.log ]] || { echo "rehearse: logs/demo_rehearsal_$n.log exists; refusing to overwrite" >&2; exit 1; }; done
for n in 1 2; do
    s=$(date +%s)
    bash scripts/demo/run_demo.sh 2>&1 | tee logs/demo_rehearsal_$n.log
    rc=${PIPESTATUS[0]}
    echo "REHEARSAL $n: wall time $(( $(date +%s) - s )) s, run_demo exit status $rc" | tee -a logs/demo_rehearsal_$n.log
    chown "$SUDO_USER": logs/demo_rehearsal_$n.log 2> /dev/null
    sleep 10
done
chown -R "${SUDO_USER:-root}": build/demo 2> /dev/null
echo "=== REHEARSALS FINISHED: tell Claude ==="
