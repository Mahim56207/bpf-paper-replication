#!/usr/bin/env bash
# p10_c1_indep_check.sh DIR - decision check of an independently written CSPF set (DIR/F1.sm .. F4.sm) against libpcap on the three Phase 6c mixes and the edge trace.
# Prints only frame counts and decision-mismatch counts (never ratios). Needs `python3 -I scripts/p10_c1.py build` first. Usage: bash scripts/p10_c1_indep_check.sh DIR
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
exec python3 -I scripts/p10_c1.py check "$1"
