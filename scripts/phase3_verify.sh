#!/usr/bin/env bash
# Phase 3 verify: load build/phase3_kern.o through the kernel verifier and show the result.
# Usage: sudo bash scripts/phase3_verify.sh [logdir] 2>&1 | tee logs/p3_verify.log
# logdir (default logs) lets a re-run write elsewhere without overwriting the logs docs/phase3_review.md cites.
# Steps as specified: (1) file, (2) bpftool prog load ..., (3) prog show pinned. The prompt's
# `type socket_filter` is rejected by bpftool (logs/p3_v1_direct_access/p3_load.log), so the type
# name from `bpftool prog help` (`socket`) is used; see DEVIATIONS.md D3.1.
# Extras, only after a successful load: xlated/jited dumps, map list, and (4) BPF_PROG_TEST_RUN
# over the frames from scripts/p3_make_packets.py (build/p3_pkts_pfx14/), then counters.
# If the load fails the full verifier log is captured with `bpftool -d`.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
OBJ=build/phase3_kern.o
PIN=/sys/fs/bpf/repl_p3
L="${1:-logs}"
mkdir -p "$L"

mountpoint -q /sys/fs/bpf || mount -t bpf bpf /sys/fs/bpf
rm -f "$PIN"

echo "### 1. file $OBJ"
file "$OBJ" 2>&1 | tee $L/p3_file.log

# load_try <logfile> <extra args after the pin path...>: prints the exact command, then its output.
load_try() {
    local logf="$1"; shift
    rm -f "$PIN"
    echo "\$ bpftool prog load $OBJ $PIN $*" | tee "$logf"
    bpftool prog load "$OBJ" "$PIN" "$@" 2>&1 | tee -a "$logf"
    local rc=${PIPESTATUS[0]}
    echo "[exit $rc]" | tee -a "$logf"
    return "$rc"
}

echo; echo "### 2. bpftool prog load ... type socket"
loaded=0
if load_try $L/p3_load.log type socket; then
    loaded=1
else
    echo "### load failed; capturing the full log with -d"
    rm -f "$PIN"
    { echo "\$ bpftool -d prog load $OBJ $PIN type socket"
      bpftool -d prog load "$OBJ" "$PIN" type socket 2>&1
      echo "[exit $?]"; } | tee $L/p3_load_debug.log
fi

if [[ $loaded -eq 1 ]]; then
    echo; echo "### 3. bpftool prog show pinned $PIN"
    bpftool prog show pinned "$PIN" 2>&1 | tee $L/p3_show.log
    echo; echo "### extras"
    bpftool prog dump xlated pinned "$PIN" 2>&1 | tee $L/p3_xlated.log | head -5
    echo "(full xlated dump: $L/p3_xlated.log)"
    bpftool prog dump jited pinned "$PIN" 2>&1 > $L/p3_jited.log; echo "(jited dump: $L/p3_jited.log, $(wc -l < $L/p3_jited.log) lines)"
    echo "### maps"; bpftool map show 2>&1 | tee $L/p3_maps.log

    echo; echo "### 4. BPF_PROG_TEST_RUN: one run per frame in build/p3_pkts_pfx14 (14-byte zero prefix, see docs/phase3_review.md)"
    python3 -I scripts/p3_make_packets.py build/p3_pkts_pfx14 14 > $L/p3_packets_manifest_pfx14.log
    bpftool -j map dump name p3_counters > $L/p3_counters_before.json 2>&1
    echo "counters before: $(cat $L/p3_counters_before.json)"
    for f in build/p3_pkts_pfx14/*.bin; do
        echo "CASE $(basename "$f" .bin)"
        bpftool prog run pinned "$PIN" data_in "$f" repeat 1 2>&1
        echo "[exit $?]"
    done 2>&1 | tee $L/p3_testrun.log | grep -c '^CASE' | sed 's/^/frames run: /'
    bpftool -j map dump name p3_counters > $L/p3_counters_after.json 2>&1
    echo "counters after: $(cat $L/p3_counters_after.json)"
else
    echo; echo "### 3. NOT RUN: nothing is pinned at $PIN"
fi

echo; echo "### kernel helper list for socket_filter (bpftool feature probe kernel)"
bpftool feature probe kernel > $L/p3_feature_probe.log 2>&1
sed -n '/eBPF helpers supported for program type socket_filter/,/^eBPF helpers supported for program type kprobe/p' $L/p3_feature_probe.log \
    | sed '$d' | tee $L/p3_helpers_socket_filter.log

echo; echo "== phase3_verify: loaded=$loaded"
[[ $loaded -eq 1 ]]
