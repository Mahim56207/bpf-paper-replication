#!/usr/bin/env bash
# Phase 6a loader regression (no benchmark data is produced here):
#  1. Phase 4 cross-check, loader in its default aggregate-only mode  -> no regression
#  2. Phase 4 cross-check with loader -d (drain)                       -> drain check
#  3. controls D (reject_all) and E (accept_all) from build/phase6_filters.o, functional check
# Usage: sudo bash scripts/p6_regression.sh 2>&1 | tee logs/p6_loader_regression.log
#
# Pre-declared control rules (before any run), 3 s of paced UDP: 20 Mbit/s to port 4040 and
# 10 Mbit/s to port 5050, loader -d -p <prog> build/phase6_filters.o:
#   reject_all: slot 1 (matched) == 0, slot 0 (dropped) > 0, delivered_packets == 0, socket kernel_packets == 0
#   accept_all: slot 0 (dropped) == 0, slot 1 (matched) > 0,
#               |delivered_packets - matched| <= max(10, matched/200), socket kernel_drops <= max(10, matched/200)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
R=logs/p6_regression
mkdir -p "$R/default" "$R/drain" "$R/controls"
VA=p1veth0; IPA=10.0.0.1; IPB=10.0.0.2; NS=p2ns

echo "######## 1. Phase 4 cross-check, default mode"
bash scripts/phase4_verify.sh "$R/default" 2>&1 | tee "$R/default/p4_verify.log" | grep -E "CROSSCHECK|CHECK|L2 VIEW|^loader|^tcpdump|abs_diff|WARN|FATAL|bytes"
echo; echo "######## 2. Phase 4 cross-check, loader -d"
bash scripts/phase4_verify.sh "$R/drain" "-d" 2>&1 | tee "$R/drain/p4_verify.log" | grep -E "CROSSCHECK|CHECK|L2 VIEW|^loader|^tcpdump|abs_diff|drain|WARN|FATAL|bytes"

echo; echo "######## 3. controls (functional check of reject_all / accept_all)"
bash scripts/lab_up.sh > "$R/controls/lab_up.log" 2>&1
for prog in reject_all accept_all; do
    echo; echo "--- $prog"
    pkill -KILL -f "iperf3 -s -B $IPB" 2>/dev/null
    for port in 4040 5050; do
        ip netns exec "$NS" iperf3 -s -B "$IPB" -p "$port" > "$R/controls/${prog}_server_$port.log" 2>&1 &
    done
    sleep 1
    build/loader -d -p "$prog" "$VA" build/phase6_filters.o > "$R/controls/${prog}_loader.log" 2>&1 &
    LP=$!
    for _ in $(seq 1 50); do grep -q '^START' "$R/controls/${prog}_loader.log" && break; sleep 0.1; done
    iperf3 -c "$IPB" -B "$IPA" -p 4040 -u -b 20M -t 3 > "$R/controls/${prog}_client_4040.log" 2>&1 &
    C1=$!
    iperf3 -c "$IPB" -B "$IPA" -p 5050 -u -b 10M -t 3 > "$R/controls/${prog}_client_5050.log" 2>&1 &
    C2=$!
    wait "$C1" "$C2"
    sleep 2
    kill -TERM "$LP"; wait "$LP"; echo "loader exit=$?"
    pkill -TERM -f "iperf3 -s -B $IPB" 2>/dev/null; sleep 0.5
    cat "$R/controls/${prog}_loader.log" | grep -E "^START|^FINAL"
    m=$(sed -n 's/^FINAL t=.*matched=\([0-9]*\).*/\1/p' "$R/controls/${prog}_loader.log")
    d=$(sed -n 's/^FINAL t=.* dropped=\([0-9]*\).*/\1/p' "$R/controls/${prog}_loader.log")
    dp=$(sed -n 's/^FINAL t=.* delivered_packets=\([0-9]*\).*/\1/p' "$R/controls/${prog}_loader.log")
    kp=$(sed -n 's/^FINAL_SOCKET kernel_packets=\([0-9]*\).*/\1/p' "$R/controls/${prog}_loader.log")
    kd=$(sed -n 's/^FINAL_SOCKET .*kernel_drops=\([0-9]*\).*/\1/p' "$R/controls/${prog}_loader.log")
    if [[ -z "$m" || -z "$d" || -z "$dp" || -z "$kp" || -z "$kd" ]]; then echo "CONTROL $prog: FAIL (could not parse FINAL lines)"; continue; fi
    tol=$((m / 200)); ((tol < 10)) && tol=10
    diff=$((dp - m)); ((diff < 0)) && diff=$((-diff))
    echo "matched=$m dropped=$d delivered=$dp socket kernel_packets=$kp kernel_drops=$kd"
    if [[ $prog == reject_all ]]; then
        if ((m == 0 && d > 0 && dp == 0 && kp == 0)); then echo "CONTROL reject_all: PASS"; else echo "CONTROL reject_all: FAIL"; fi
    else
        if ((d == 0 && m > 0 && diff <= tol && kd <= tol)); then echo "CONTROL accept_all: PASS (delivered-matched=$diff allowance=$tol)"; else echo "CONTROL accept_all: FAIL (delivered-matched=$diff allowance=$tol)"; fi
    fi
done
echo; echo "### leftover processes (expect none):"; pgrep -af 'build/loader|iperf3|tcpdump' || echo none
echo "######## regression done"
