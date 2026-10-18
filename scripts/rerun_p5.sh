#!/usr/bin/env bash
# Phase 5: (1) the reviewer's gap-closing command (verbose load of variant A), then (2) the Phase 5
# verify re-run (CLAUDE.md workflow rule) into logs/p5_rerun/. One sudo.
# Usage: sudo bash scripts/rerun_p5.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
mountpoint -q /sys/fs/bpf || mount -t bpf bpf /sys/fs/bpf
mkdir -p logs/p5_rerun
rm -f /sys/fs/bpf/repl_p5v
echo "### 1. bpftool -d prog load build/phase5_unsafe_a.o /sys/fs/bpf/repl_p5v type socket 2>&1 | tee logs/p5_a_verbose.log"
bpftool -d prog load build/phase5_unsafe_a.o /sys/fs/bpf/repl_p5v type socket 2>&1 | tee logs/p5_a_verbose.log
echo "exit=${PIPESTATUS[0]}"
rm -f /sys/fs/bpf/repl_p5v
echo "pin removed: $([[ -e /sys/fs/bpf/repl_p5v ]] && echo NO || echo yes)"
echo; echo "######## Phase 5 verify rerun -> logs/p5_rerun/"
bash scripts/phase5_verify.sh logs/p5_rerun 2>&1 | tee logs/p5_rerun/p5_verify.log
echo; echo "######## rerun done"
