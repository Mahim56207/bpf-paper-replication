#!/usr/bin/env bash
# act2_sender_limit.sh - demo act 2 (about 2 minutes): the sender-limit effect, live. In the veth / namespace testbed (scripts/lab_up.sh) two unlimited iperf3 UDP streams
# (ports 4040 and 5050, 256-byte frames) run for 10 s with no capture (config N) and then for 10 s with the user-space sniffer (config A), with the documented Phase 8.2 pinning:
# servers in p2ns on core 3, sniffer on core 2, match client on core 4, noise client on core 1. Every second it prints the packets per second that left p1veth0 (offered load, read from
# /sys/class/net/p1veth0/statistics/tx_packets) and the sniffer's CPU (from /proc/<pid>/stat). A trap removes the iperf3 processes, the sniffer, the namespace and the veth pair even on Ctrl-C.
# Needs root. Usage: sudo bash scripts/demo/act2_sender_limit.sh
set -u
export LC_ALL=C
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
[[ $EUID -eq 0 ]] || { echo "act2: run with sudo (namespaces, raw sockets)" >&2; exit 1; }
PAUSE="${DEMO_PAUSE:-8}"; OUT=build/demo; NS=p2ns; VA=p1veth0; IPA=10.0.0.1; IPB=10.0.0.2
CAP=2; SRV=3; CLI_MATCH=4; CLI_NOISE=1; DUR=10; CLK=$(getconf CLK_TCK)
mkdir -p "$OUT" || exit 1
for f in build/baseline_sniffer scripts/lab_up.sh; do [[ -e $f ]] || { echo "act2: $f is missing" >&2; exit 1; }; done
command -v iperf3 > /dev/null || { echo "act2: iperf3 is not installed" >&2; exit 1; }
SNIFF=""
cleanup() {
    trap - EXIT INT TERM
    echo; echo "act2: teardown (iperf3, sniffer, namespace $NS, veth $VA)"
    [[ -n "$SNIFF" ]] && kill -TERM "$SNIFF" 2>> "$OUT/act2_cleanup.err"
    pkill -KILL -f "iperf3 -c $IPB -B $IPA" 2>> "$OUT/act2_cleanup.err"
    pkill -KILL -f "iperf3 -s -B $IPB" 2>> "$OUT/act2_cleanup.err"
    wait 2>> "$OUT/act2_cleanup.err"
    bash scripts/lab_up.sh down > "$OUT/act2_lab_down.log" 2>&1
    if ip link show "$VA" > "$OUT/act2_check_veth.txt" 2>&1 || ip netns list | grep -q "^$NS"; then echo "act2: WARNING: $VA or $NS still exists"; else echo "act2: teardown verified: no $VA, no $NS"; fi
}
trap cleanup EXIT
trap 'echo; echo "act2: interrupted"; exit 130' INT TERM
ticks() { awk '{print $14 + $15}' "/proc/$1/stat"; }          # utime + stime of a process, in clock ticks
tx() { cat "/sys/class/net/$VA/statistics/tx_packets"; }
run_cfg() { # run_cfg N|A
    local cfg=$1 p t0 t1 tx0 tx1 txp cp0=0 cp1 cpp now prev i; local -a wp=()
    echo; echo "--- config $cfg: $([[ $cfg == N ]] && echo 'no capture process (control)' || echo 'user-space sniffer on p1veth0 (copy every packet, then filter), core '"$CAP")"
    for p in 4040 5050; do
        ip netns exec "$NS" taskset -c "$SRV" iperf3 -s -B "$IPB" -p "$p" -J --logfile "$OUT/act2_${cfg}_srv_$p.json" -1 > "$OUT/act2_${cfg}_srv_$p.out" 2>&1 &
        wp+=($!)
    done
    sleep 1
    SNIFF=""
    if [[ $cfg == A ]]; then
        taskset -c "$CAP" build/baseline_sniffer "$VA" > "$OUT/act2_A_sniffer.out" 2>&1 &
        SNIFF=$!
        sleep 1
        kill -0 "$SNIFF" 2> /dev/null || { echo "act2: the sniffer did not start (see $OUT/act2_A_sniffer.out)"; exit 1; }
        cp0=$(ticks "$SNIFF")
    fi
    tx0=$(tx); t0=${EPOCHREALTIME}; prev=$t0; txp=$tx0; cpp=$cp0
    taskset -c "$CLI_MATCH" iperf3 -c "$IPB" -B "$IPA" -p 4040 -u -b 0 -l 214 -t "$DUR" -J > "$OUT/act2_${cfg}_cli_4040.json" 2> "$OUT/act2_${cfg}_cli_4040.err" &
    wp+=($!)
    taskset -c "$CLI_NOISE" iperf3 -c "$IPB" -B "$IPA" -p 5050 -u -b 0 -l 214 -t "$DUR" -J > "$OUT/act2_${cfg}_cli_5050.json" 2> "$OUT/act2_${cfg}_cli_5050.err" &
    wp+=($!)
    for i in $(seq 1 "$DUR"); do
        sleep 1
        now=${EPOCHREALTIME}; tx1=$(tx)
        if [[ $cfg == A ]]; then cp1=$(ticks "$SNIFF"); else cp1=0; fi
        awk -v i="$i" -v d="$tx1" -v dp="$txp" -v n="$now" -v pv="$prev" -v c1="$cp1" -v c0="$cpp" -v clk="$CLK" -v cfg="$cfg" 'BEGIN {
            dt = n - pv; cpu = (c1 - c0) / clk / dt * 100
            if (cfg == "A") printf "  t=%2ds  offered %9.0f pps   sniffer CPU %5.1f %% of one core\n", i, (d - dp) / dt, cpu
            else printf "  t=%2ds  offered %9.0f pps   (no capture process)\n", i, (d - dp) / dt }'
        prev=$now; txp=$tx1; cpp=$cp1
    done
    wait "${wp[@]}" 2>> "$OUT/act2_cleanup.err"
    t1=${EPOCHREALTIME}; tx1=$(tx)
    awk -v a="$tx0" -v b="$tx1" -v t0="$t0" -v t1="$t1" -v cfg="$cfg" 'BEGIN { printf "    config %s: mean offered load over the window %.0f pps\n", cfg, (b - a) / (t1 - t0) }'
    MEAN[$cfg]=$(awk -v a="$tx0" -v b="$tx1" -v t0="$t0" -v t1="$t1" 'BEGIN { printf "%.0f", (b - a) / (t1 - t0) }')
    if [[ $cfg == A ]]; then
        cp1=$(ticks "$SNIFF"); awk -v c="$((cp1 - cp0))" -v clk="$CLK" -v t0="$t0" -v t1="$t1" 'BEGIN { printf "    config A: sniffer CPU over the window %.1f %% of one core\n", c / clk / (t1 - t0) * 100 }'
        kill -INT "$SNIFF" 2>> "$OUT/act2_cleanup.err"; wait "$SNIFF" 2>> "$OUT/act2_cleanup.err"; SNIFF=""
        grep -E "^FINAL" "$OUT/act2_A_sniffer.out" | sed 's/^/    sniffer: /'
    fi
}
declare -A MEAN
echo "act 2: sender limit, live (pinning: servers core $SRV, sniffer core $CAP, match client core $CLI_MATCH, noise client core $CLI_NOISE)"
bash scripts/lab_up.sh > "$OUT/act2_lab_up.log" 2>&1 || { echo "act2: lab_up failed, see $OUT/act2_lab_up.log" >&2; exit 1; }
sleep 1
run_cfg N
sleep "$PAUSE"
run_cfg A
echo; awk -v n="${MEAN[N]}" -v a="${MEAN[A]}" 'BEGIN { printf "live: offered load without capture %.0f pps, with the user-space sniffer %.0f pps, ratio %.2f\n", n, a, n / a }'
echo "Illustrative live run, 10 s, not the logged result; the logged result is in results/p10_summary.md"
