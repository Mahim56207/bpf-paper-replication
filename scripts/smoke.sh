#!/usr/bin/env bash
# Phase 6 smoke runs: one short run per config A-E to check the plumbing. Output is labelled SMOKE
# (logs/smoke_*.log, results/smoke.md) and is excluded from analysis by pre-declaration.
# Usage: sudo bash scripts/smoke.sh 2>&1 | tee logs/smoke_driver.log
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
echo "== SMOKE $(date -u +%Y-%m-%dT%H:%M:%SZ): one 5 s run per config, 512-byte matching UDP at 2000 pps (excluded from analysis)"
t0=$(date +%s)
for cfg in A B C D E; do
    echo "--- SMOKE cfg=$cfg"
    t1=$(date +%s)
    BENCH_LABEL=smoke bash scripts/bench.sh one "$cfg" m 512 1 2000 5 < /dev/null
    echo "SMOKE cfg=$cfg wall-clock for the run: $(( $(date +%s) - t1 )) s (5 s of traffic)"
done
echo "== SMOKE total wall-clock: $(( $(date +%s) - t0 )) s for 5 runs"
python3 -I scripts/summarize.py smoke
