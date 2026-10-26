#!/usr/bin/env bash
# Phase 8.1 step 2: 3 idle windows of 10 s, the same instruments as the matrix (scripts/bench.sh one D idle: config D
# capture process, classifier tap, pidstat, vmstat, /proc/stat snapshots; no traffic). Needs root (BPF load, lab check).
# Usage:  sudo bash scripts/p8_1_idle.sh <label> [dur] [settle_s]      e.g. label = desktopnow | ttylogin
# settle_s (default 0): seconds of plain sleep after the sudo prompt and before the first window, so that typing, clicking and the
# assistant's own turn are over before the measurement (Phase 8.1 finding: activity in the Claude desktop app dominates the noise).
# Writes logs/p8/p8_1/idle_<label>/{run_1..3.out, p81<label>_D_idle_0_{1,2,3}.log}. Nothing outside logs/p8/p8_1/ is touched:
# bench.sh writes logs/p81<label>_D_idle_0_<k>.log (a new name, no tracked file) and the script moves it. Fails loudly.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
label="${1:?usage: p8_1_idle.sh <label> [dur]}"
dur="${2:-10}"
settle="${3:-0}"
[[ "$label" =~ ^[A-Za-z0-9]+$ ]] || { echo "FATAL: label must be alphanumeric (no underscore: it becomes part of the log name)" >&2; exit 1; }
out="logs/p8/p8_1/idle_${label}"
tag="p81${label}"
session="p81_${label}_$(date +%s)"
rm -rf "$out"; mkdir -p "$out"
rm -f logs/${tag}_D_idle_0_[123].log
{ echo "# p8_1_idle label=$label dur=$dur session=$session start=$(date -Is)"; uname -srm; cat /proc/loadavg
  echo "# swap/mem before:"; free -m; } 2>&1 | tee "$out/context.txt"
echo "=== DO NOT TOUCH THE MACHINE until the line FINISHED appears (settle ${settle} s, then 3 x ${dur} s windows) ==="
sleep "$settle"
fail=0
for k in 1 2 3; do
    BENCH_LABEL="$tag" BENCH_SESSION="$session" bash scripts/bench.sh one D idle 0 "$k" 0 "$dur" 2>&1 | tee "$out/run_${k}.out"
    rc=${PIPESTATUS[0]}
    src="logs/${tag}_D_idle_0_${k}.log"
    if [[ $rc -ne 0 || ! -s "$src" ]]; then echo "FAIL: window $k (bench.sh rc=$rc, $src missing or empty)" >&2; fail=$((fail+1)); continue; fi
    mv "$src" "$out/"
done
{ echo "# swap/mem after:"; free -m; echo "# end=$(date -Is)"; } 2>&1 | tee -a "$out/context.txt"
[[ -n "${SUDO_USER:-}" ]] && chown -R "$SUDO_USER": "$out" logs/p8/p8_1
n=$(ls "$out"/${tag}_D_idle_0_[123].log 2>/dev/null | wc -l)
echo "windows written: $n of 3 in $out; failures: $fail"
echo "=== FINISHED $(date +%T) ==="
[[ $n -eq 3 && $fail -eq 0 ]] || exit 1
