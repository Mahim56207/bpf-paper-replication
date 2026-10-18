#!/usr/bin/env bash
# Phase 5 (revised per reviewer ruling D5.2). Usage: sudo bash scripts/phase5_verify.sh [logdir] 2>&1 | tee logs/p5_verify.log
# logdir (default logs) lets a re-run write elsewhere without overwriting the logs docs/phase5_analysis.md cites.
# Order: pin hygiene check -> A mechanism (xlated) -> a2 -> b -> control -> a2 positive control -> pin hygiene.
# stderr of each bpftool attempt goes to its own log, verbatim. If a variant expected to be REJECTED
# loads, the script stops at once and reports it as a finding with the kernel version.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
L="${1:-logs}"
mkdir -p "$L"
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
mountpoint -q /sys/fs/bpf || mount -t bpf bpf /sys/fs/bpf
cleanup() { rm -f /sys/fs/bpf/repl_p5*; }
trap cleanup EXIT

echo "== phase5_verify $(date -u +%Y-%m-%dT%H:%M:%SZ) kernel=$(uname -r) arch=$(uname -m) bpftool=$(bpftool version | head -1)"

echo; echo "### 0. pin hygiene at start (answers whether the previous run's exit trap removed repl_p5a)"
echo "\$ ls /sys/fs/bpf"; ls /sys/fs/bpf 2>&1 | tee $L/p5_pins_start.log
echo "leftover repl_p5* pins: $(ls /sys/fs/bpf | grep -c '^repl_p5' )"
rm -f /sys/fs/bpf/repl_p5*

echo; echo "### 1. variant A (retained as evidence): load, then dump xlated"
echo "\$ bpftool prog load build/phase5_unsafe_a.o /sys/fs/bpf/repl_p5a type socket"
bpftool prog load build/phase5_unsafe_a.o /sys/fs/bpf/repl_p5a type socket 2> $L/p5_a_load_stderr.log
echo "exit=$?   stderr bytes: $(wc -c < $L/p5_a_load_stderr.log)"
echo "\$ bpftool prog dump xlated pinned /sys/fs/bpf/repl_p5a > $L/p5_a_xlated.log"
bpftool prog dump xlated pinned /sys/fs/bpf/repl_p5a > $L/p5_a_xlated.log 2>&1
echo "xlated lines: $(wc -l < $L/p5_a_xlated.log)"
echo "calls to bpf_map_lookup_elem in xlated stream: $(grep -c 'call bpf_map_lookup_elem' $L/p5_a_xlated.log)"
echo "other calls in xlated stream:"; grep 'call ' $L/p5_a_xlated.log | sed 's/^/    /'
echo "inlined-lookup pattern (map pointer load, 'r0 += r1' arithmetic):"; grep -n 'map\[id\|+= 264\|<<= 3\|r0 += r1\|if r0 >= ' $L/p5_a_xlated.log | sed 's/^/    /'
echo "\$ bpftool prog show   (full list, $L/p5_prog_show.log)"; bpftool prog show 2>&1 > $L/p5_prog_show.log; echo "(saved, $(wc -l < $L/p5_prog_show.log) lines)"
rm -f /sys/fs/bpf/repl_p5a

attempt() { # attempt <label> <objfile> <expect: reject|load>
    local x="$1" obj="$2" want="$3"
    echo; echo "### $x"
    echo "\$ bpftool prog load $obj /sys/fs/bpf/repl_p5$x type socket 2>$L/phase5_$x.log"
    bpftool prog load "$obj" "/sys/fs/bpf/repl_p5$x" type socket 2> "$L/phase5_$x.log"
    local rc=$?
    echo "exit=$rc"
    echo "stderr log bytes: $(wc -c < "$L/phase5_$x.log")"
    if [[ "$want" == reject && $rc -eq 0 ]]; then
        echo
        echo "FINDING: variant $x LOADED (exit 0) but a rejection was expected. Kernel $(uname -r)."
        echo "Stopping immediately as instructed."
        exit 3
    fi
    return $rc
}

attempt a2 build/phase5_unsafe_a2.o reject
attempt b build/phase5_unsafe_b.o reject

echo; echo "### CONTROL (safe program, same command shape)"
attempt control build/phase3_kern.o load; crc=$?
bpftool prog show pinned /sys/fs/bpf/repl_p5control 2>&1 | head -2
rm -f /sys/fs/bpf/repl_p5control

echo; echo "### POSITIVE CONTROL for a2 (NULL check restored)"
attempt a2fixed build/phase5_a2_fixed.o load; prc=$?
bpftool prog show pinned /sys/fs/bpf/repl_p5a2fixed 2>&1 | head -2

echo; echo "### pin hygiene at end"
rm -f /sys/fs/bpf/repl_p5*
echo "\$ ls /sys/fs/bpf"; ls /sys/fs/bpf 2>&1 | tee $L/p5_pins_end.log
echo "leftover repl_p5* pins: $(ls /sys/fs/bpf | grep -c '^repl_p5')"
echo "\$ bpftool prog show | grep -c socket_filter  ->  $(bpftool prog show | grep -c socket_filter) (the Phase 3 pin repl_p3, if still present, is not touched)"
[[ $crc -eq 0 && $prc -eq 0 ]]
