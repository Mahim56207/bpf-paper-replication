#!/usr/bin/env bash
# H1 reproducer: does tcpdump exit when sent SIGTERM while the capture is idle?
# Usage: sudo bash scripts/p2_h1_tcpdump_term_test.sh 2>&1 | tee logs/p2_h1_tcpdump_term.log
# Runs three tcpdump variants on p1veth0 with no traffic, SIGTERM after 2 s, waits up to 5 s.
set -u
IF=p1veth0
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="$ROOT/logs"

if [[ $EUID -ne 0 ]]; then echo "FATAL: run with sudo" >&2; exit 1; fi
ip -br link show "$IF" || { echo "FATAL: $IF missing" >&2; exit 1; }

# Stale processes from the hung verify runs.
pkill -KILL -f "tcpdump -i $IF" 2>/dev/null
pkill -KILL -f "iperf3 -s -B 10.0.0.2" 2>/dev/null
sleep 0.5
echo "== stale cleanup done; remaining: $(pgrep -af 'tcpdump -i p1veth0|iperf3 -s' || echo none)"

now() { date +%s.%N; }

# try <name> <tcpdump args...>
try() {
    local name="$1"; shift
    local err="$LOG/p2_h1_${name}.err" pid t0 t1 n=50 rc
    echo; echo "== variant $name: tcpdump $*"
    tcpdump "$@" 2> "$err" &
    pid=$!
    sleep 2
    echo "state before TERM: $(ps -o stat= -p "$pid" 2>/dev/null || echo gone)"
    t0=$(now)
    kill -TERM "$pid"; echo "kill -TERM rc=$?"
    while ((n-- > 0)) && kill -0 "$pid" 2>/dev/null; do sleep 0.1; done
    t1=$(now)
    if kill -0 "$pid" 2>/dev/null; then
        echo "RESULT[$name]: STILL RUNNING $(awk "BEGIN{printf \"%.1f\", $t1-$t0}") s after SIGTERM; sending SIGKILL"
        grep -E '^(State|SigPnd|ShdPnd|SigCgt)' "/proc/$pid/status"
        kill -KILL "$pid"
    else
        echo "RESULT[$name]: exited $(awk "BEGIN{printf \"%.1f\", $t1-$t0}") s after SIGTERM"
    fi
    wait "$pid" 2>/dev/null; rc=$?
    echo "wait rc=$rc"
    echo "--- tcpdump stderr:"; cat "$err"
}

# A: exactly the flags of run 2 (immediate mode, savefile, no privilege drop)
try A -i "$IF" -nn -Z root --immediate-mode -U -w /dev/null "port 4040"
# B: the flags of run 1 (default privilege drop, buffered, savefile)
try B -i "$IF" -nn -w /dev/null "port 4040"
# C: no savefile, no filter expression, immediate mode, printing to a file (control)
try C -i "$IF" -nn --immediate-mode -c 1000000

echo; echo "== leftover: $(pgrep -af 'tcpdump -i p1veth0' || echo none)"
