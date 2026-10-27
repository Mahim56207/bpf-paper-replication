#!/usr/bin/env bash
# Phase 8.2 probe (excluded from analysis by pre-declaration, docs/phase8_2_design.md section 3): checks as root that the harness copy,
# config N, the perf profile, perf script parsing and the tap symbol work BEFORE the measured run. 4 s unlimited flood per config with
# PROFILE=1, one run each of N, A, B, C. Outputs: logs/p8/p8_2/probe/ (deleted first). Usage: sudo bash scripts/p8_2_probe.sh 2>&1 | tee logs/p8/p8_2/p8_2_probe_console.log
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
P=logs/p8/p8_2/probe; PD=build/p8_2/probe_perf
rm -rf "$P" "$PD"; mkdir -p "$P" "$PD"
echo "=== probe start $(date -Is); free -m:"; free -m
fail=0
for cfg in N A B C; do
    echo "--- probe run cfg=$cfg (4 s flood, PROFILE=1)"
    BENCH_LABEL=p82probe PROFILE=1 P8_OUT_DIR="$P" P8_PERF_DIR="$PD" BENCH_SESSION="probe_$(date +%s)" \
        bash scripts/p8_2_bench.sh one "$cfg" flood 256 1 0 4 < /dev/null; rc=$?
    log="$P/p82probe_${cfg}_flood_256_1.log"
    if [[ $rc -ne 0 || ! -s "$log" ]]; then echo "FAIL: run $cfg rc=$rc log=$log" >&2; fail=$((fail+1)); continue; fi
    f="$PD/p82probe_${cfg}_flood_256_1_a1.data"
    if [[ ! -s "$f" ]]; then echo "FAIL: perf data $f missing or empty" >&2; fail=$((fail+1)); continue; fi
    python3 -I scripts/p8_2_perf_counts.py "$f" "$P/counts_${cfg}.json" || { echo "FAIL: perf_counts for $cfg" >&2; fail=$((fail+1)); }
    echo "--- perf report top (comm,dso,symbol) for $cfg"
    perf report -i "$f" --stdio --no-children --sort comm,dso,symbol -g none 2>&1 | grep -v '^#' | grep -v '^$' | head -14 | tee "$P/report_top_${cfg}.txt"
done
echo "--- perf record logs"; for f in "$P"/p82probe_*_flood_256_1.log; do echo "$f"; sed -n '/^### perf_record/,/^### /p' "$f" | head -8; done
echo "--- header of each probe log"; for f in "$P"/p82probe_*_flood_256_1.log; do head -5 "$f"; done
chown -R "${SUDO_USER:-root}": "$P" "$PD" 2>/dev/null
echo "=== probe end $(date -Is); failures: $fail; free -m:"; free -m
echo "=== FINISHED $(date +%T) ==="
exit $((fail>0))
