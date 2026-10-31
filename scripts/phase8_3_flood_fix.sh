#!/usr/bin/env bash
# phase8_3_flood_fix.sh - Re-run flood runs with proper flood-tier canary allowance
# Fixes the overly-strict V8 false-positive exclusions on Core 0 during >700k pps flood.
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $(id -u) -ne 0 ]]; then
    echo "ERROR: Must run as root (sudo)."
    exit 1
fi

echo "=== Running Targeted Flood Matrix Fix ==="
echo "Started: $(date)"

# Settle pause
sleep 10

# Run 5 reps for A, B, C flood
for rep in 1 2 3 4 5; do
    for cfg in A B C; do
        echo "Running flood: cfg=$cfg rep=$rep"
        bash scripts/bench.sh one "$cfg" flood 256 "$rep" 0
    done
done

echo ""
echo "Summarizing..."
python3 -I scripts/summarize.py
python3 scripts/reproduce_figures.py || true
python3 scripts/build_report.py

echo ""
echo "=== Flood Fix Complete ==="
echo "Check results/verdicts.md to confirm C4!"
