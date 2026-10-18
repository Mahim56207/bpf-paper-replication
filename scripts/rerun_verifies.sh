#!/usr/bin/env bash
# Re-run the Phase 1 and Phase 2 verify scripts (CLAUDE.md workflow rule) under one sudo.
# Phase 2 writes to logs/p2_rerun/ so the logs cited by docs/phase2_notes.md are not overwritten.
# Usage: sudo bash scripts/rerun_verifies.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }

echo "######## Phase 1 verify rerun"
bash scripts/phase1_verify.sh 2>&1 | tee logs/phase1_verify_rerun.log

echo; echo "######## Phase 2 verify rerun (skipA) -> logs/p2_rerun/"
mkdir -p logs/p2_rerun
P2_LOGDIR="$ROOT/logs/p2_rerun" bash scripts/phase2_verify.sh skipA 2>&1 | tee logs/p2_rerun/p2_verify.log
echo; echo "######## rerun done"
