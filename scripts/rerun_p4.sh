#!/usr/bin/env bash
# Phase 4 negatives, then the Phase 4 verify re-run (CLAUDE.md workflow rule) under one sudo.
# The re-run writes to logs/p4_rerun/ so the logs cited by docs/phase4_notes.md are kept.
# Usage: sudo bash scripts/rerun_p4.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
mkdir -p logs/p4_rerun
bash scripts/p4_negatives.sh 2>&1 | tee logs/p4_negatives.log
echo; echo "######## Phase 4 verify rerun -> logs/p4_rerun/"
bash scripts/phase4_verify.sh logs/p4_rerun 2>&1 | tee logs/p4_rerun/p4_verify.log
echo; echo "######## rerun done"
