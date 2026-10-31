#!/usr/bin/env bash
# Phase 8.3: Re-run C2/C3 curves on a quiet machine.
# =====================================================
# INSTRUCTIONS:
#   1. Close ALL applications on the VM (browser, Claude, file manager, etc.)
#   2. Wait 5 minutes for the machine to settle
#   3. Run: sudo bash scripts/phase8_3_run.sh
#   4. DO NOT TOUCH THE MACHINE until the script finishes (~50 minutes)
#
# What this does:
#   - Ensures the lab network is up
#   - Rebuilds all binaries
#   - Takes 3 idle baseline windows
#   - Runs calibration to find the loss-free pps ceiling
#   - Runs the curve configs (A, B, D for reject; A, B, E for accept) at 5 sizes × 3 reps
#   - Summarizes results and regenerates verdicts
#
# Output: logs/p8_3/, results/summary.md, results/verdicts.md, results/exclusions.md
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== Phase 8.3: C2/C3 quiet re-run ==="
echo "Started: $(date)"
echo ""

# --- Pre-flight checks ---
if [[ $(id -u) -ne 0 ]]; then
    echo "ERROR: Must run as root (sudo). Exiting."
    exit 1
fi

# Ensure lab is up
echo "[1/6] Setting up lab network..."
bash scripts/lab_up.sh up 2>&1 | tail -3

# Build
echo "[2/6] Building binaries..."
bash scripts/build_all.sh 2>&1 | tail -3

# --- Settle pause ---
echo ""
echo "============================================"
echo "  SETTLE PAUSE: waiting 60 seconds"
echo "  DO NOT TOUCH THE MACHINE"
echo "============================================"
echo ""
sleep 60

# --- Idle baseline ---
echo "[3/6] Taking idle baseline (3 × 10s windows)..."
bash scripts/bench.sh idle 10 2>&1 | tee logs/p8_3_idle.log
echo ""

# Check idle rate
IDLE_RATE=$(python3 -c "
import json
d = json.load(open('results/baseline_calibration.json'))
print(f\"Idle rate: {d['idle_rate_mean']:.3f} CPU-s/s (quiet calibration was 0.131)\")
c_max = d['canary_max']
if isinstance(c_max, dict):
    print(f\"Canary max (cores 0,1): {c_max.get('01', 0):.4f}, (core 0): {c_max.get('0', 0):.4f}\")
else:
    print(f\"Canary max: {c_max:.4f}\")
if d['idle_rate_mean'] > 0.3:
    print('WARNING: Machine is still noisy! Consider waiting longer or killing more processes.')
")
echo "$IDLE_RATE"
echo ""

# --- Calibration ---
echo "[4/6] Running calibration (~15 min)..."
bash scripts/bench.sh calibrate 2>&1 | tee logs/p8_3_calibrate.log
echo ""

# --- Generate plan ---
echo "[5/6] Generating plan and running matrix..."
SEED=$(date +%s)
bash scripts/bench.sh plan "$SEED" 2>&1

echo ""
echo "============================================"
echo "  MATRIX RUN: ~40 minutes"
echo "  DO NOT TOUCH THE MACHINE"
echo "============================================"
echo ""

# --- Run the matrix ---
bash scripts/bench.sh run 2>&1 | tee logs/p8_3_matrix.log

echo ""
echo "[6/6] Summarizing results..."

# --- Summarize ---
python3 -I scripts/summarize.py 2>&1 | tee logs/p8_3_summarize.log

# --- Regenerate figures ---
python3 scripts/reproduce_figures.py 2>&1 && echo "Figures written." || echo "matplotlib not available; figures skipped."

# --- Regenerate report ---
python3 scripts/build_report.py 2>&1 && echo "Report regenerated." || echo "build_report.py failed; check manually."

echo ""
echo "=== Phase 8.3 COMPLETE ==="
echo "Finished: $(date)"
echo ""
echo "Check these files for updated verdicts:"
echo "  results/verdicts.md    — C2, C3, C4 verdicts"
echo "  results/summary.md     — full data tables"
echo "  results/exclusions.md  — excluded runs"
echo "  results/fig_cpu_cost.png — updated figure"
echo ""
echo "Next steps:"
echo "  git add -A && git commit -m 'Phase 8.3: C2/C3 re-run on quiet machine' && git push"
