#!/usr/bin/env bash
# Phase 2 verify: baseline_sniffer vs tcpdump over a veth pair, driven by iperf3.
# Usage: sudo bash scripts/phase2_verify.sh [skipA] 2>&1 | tee logs/p2_verify.log
#        sudo bash scripts/phase2_verify.sh teardown     # remove the veth pair and namespace
#
# Stage A (skipped with "skipA"): both addresses in the root namespace, as first specified, to
#   record whether traffic crosses the veth pair at all. Logs: p2_stageA*.log
# Stage B: p1veth1 lives in namespace p2ns so traffic must cross the veth pair. Two runs:
#   paced     TCP 100 Mbit/s 5 s + UDP 50 Mbit/s 2 s. The CORRECTNESS cross-check: rates low
#             enough that neither tool should drop. Logs: p2_run.log p2_tcpdump.log p2_crosscheck.log
#   fullrate  TCP unlimited 5 s + UDP 50 Mbit/s 2 s. The STRESS run: shows whether the baseline
#             keeps up. Logs: p2_full_*.log
#
# tcpdump is launched as a systemd transient unit (p2-tcpdump) and stopped with systemctl: this
# terminal's processes carry the AppArmor label "claude-desktop", and tcpdump's AppArmor profile only
# accepts signals from peer=unconfined, so even root's kill/pkill gets EPERM (logs/p2_h1_tcpdump_term.log).
# systemd (PID 1) is unconfined, so its SIGTERM is accepted.
#
# Cross-check rule (stated before any run; justified in docs/phase2_notes.md):
#   allowance = max(10, tcpdump_captured / 200) + sniffer kernel_drops + tcpdump dropped
#   PASS         if |sniffer matched - tcpdump captured| <= allowance AND drops are valid evidence
#   INCONCLUSIVE if total drops > 1% of tcpdump_captured, or a drop count is unavailable: when
#                drops dominate the allowance the comparison proves nothing about the matcher
#   FAIL         otherwise
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="${P2_LOGDIR:-$ROOT/logs}"   # P2_LOGDIR lets a re-run write elsewhere without overwriting cited logs
mkdir -p "$LOG"
SNIF="$ROOT/build/baseline_sniffer"
NS=p2ns; VA=p1veth0; VB=p1veth1; IPA=10.0.0.1; IPB=10.0.0.2; PORT=4040
SNIF_PID=""; TCPD_PID=""; SRV_PID=""

say() { echo; echo "== $*"; }

wait_for() { # wait_for <seconds> <command...>: poll every 0.1s until the command succeeds
    local n=$(($1 * 10)); shift
    while ((n-- > 0)); do "$@" >/dev/null 2>&1 && return 0; sleep 0.1; done
    return 1
}

# stop_proc <label> <pid>: SIGTERM, wait up to 5 s for exit, then SIGKILL (and say so in the log).
# Background jobs of a non-interactive script ignore SIGINT, so TERM is used throughout.
stop_proc() {
    local label="$1" pid="$2" n=50
    [[ -n "$pid" ]] || return 0
    if ! kill -TERM "$pid" 2>/dev/null; then
        # Already gone, or not signalable (EPERM): never `wait` on a live process we cannot signal.
        if kill -0 "$pid" 2>/dev/null; then echo "WARN: $label (pid $pid) cannot be signalled"; else wait "$pid" 2>/dev/null; fi
        return 0
    fi
    while ((n-- > 0)) && kill -0 "$pid" 2>/dev/null; do sleep 0.1; done
    if kill -0 "$pid" 2>/dev/null; then
        echo "WARN: $label (pid $pid) ignored SIGTERM for 5 s; sending SIGKILL"
        kill -KILL "$pid" 2>/dev/null
    fi
    wait "$pid" 2>/dev/null
}

# tcpdump as a systemd unit (see header). Its stderr goes to the journal.
tcpdump_start() { # tcpdump_start <savefile>
    systemctl stop p2-tcpdump 2>/dev/null; systemctl reset-failed p2-tcpdump 2>/dev/null
    TCPD_UP=1; TCPD_SINCE=$(date +%s)
    # -Z root: no privilege drop. --immediate-mode: deliver packets as they arrive. -U: flush per packet.
    systemd-run --quiet --unit=p2-tcpdump --collect --property=TimeoutStopSec=10 \
        tcpdump -i "$VA" -nn -Z root --immediate-mode -U -w "$1" "port $PORT"
}
tcpdump_stop() {
    [[ "${TCPD_UP:-0}" == 1 ]] || return 0
    systemctl stop p2-tcpdump || echo "WARN: systemctl stop p2-tcpdump failed"
    TCPD_UP=0
}
tcpdump_log() { sleep 1; journalctl -u p2-tcpdump --since "@$TCPD_SINCE" -o cat --no-pager 2>&1; }

topo_remove() {
    ip netns del "$NS" 2>/dev/null
    ip link del "$VA" 2>/dev/null
}

cleanup() {
    stop_proc sniffer "$SNIF_PID"; SNIF_PID=""
    tcpdump_stop
    stop_proc iperf3-server "$SRV_PID"; SRV_PID=""
}
trap cleanup EXIT

if [[ $EUID -ne 0 ]]; then echo "FATAL: run with sudo" >&2; exit 1; fi
if [[ "${1:-}" == "teardown" ]]; then topo_remove; ip -br link show; exit 0; fi
for f in "$SNIF" /usr/bin/iperf3 /usr/bin/tcpdump; do [[ -x "$f" ]] || { echo "FATAL: missing $f" >&2; exit 1; }; done

echo "== phase2_verify $(date -u +%Y-%m-%dT%H:%M:%SZ) arch=$(uname -m) kernel=$(uname -r)"

# Stale processes from an earlier aborted run would corrupt the counts.
pkill -KILL -f "baseline_sniffer $VA" 2>/dev/null
systemctl stop p2-tcpdump 2>/dev/null; systemctl reset-failed p2-tcpdump 2>/dev/null
# Orphan tcpdumps from earlier runs cannot be signalled from here; ask unconfined systemd to do it.
systemd-run --quiet --wait --collect pkill -KILL -f "tcpdump -i $VA" 2>/dev/null
pkill -KILL -f "iperf3 -s -B $IPB -p $PORT" 2>/dev/null
sleep 0.5

############################################ Stage A
if [[ "${1:-}" != "skipA" ]]; then
    say "Stage A: both addresses in the root namespace (topology as first specified)"
    topo_remove
    ip link add "$VA" type veth peer name "$VB" || exit 1
    ip link set "$VA" up; ip link set "$VB" up
    ip addr add "$IPA/24" dev "$VA"; ip addr add "$IPB/24" dev "$VB"
    {
        ip addr show "$VA"; ip addr show "$VB"
        echo "### ip route get $IPB (from $IPA)"; ip route get "$IPB" from "$IPA"
    } 2>&1 | tee "$LOG/p2_stageA_net.log"
    "$SNIF" "$VA" > "$LOG/p2_stageA_run.log" 2>&1 &
    SNIF_PID=$!
    wait_for 5 grep -q '^START' "$LOG/p2_stageA_run.log" || echo "WARN: sniffer did not start"
    iperf3 -s -B "$IPB" -p "$PORT" > "$LOG/p2_stageA_iperf_server.log" 2>&1 &
    SRV_PID=$!
    wait_for 5 bash -c "ss -ltn | grep -q ':$PORT '" || echo "WARN: iperf3 server not listening"
    iperf3 -c "$IPB" -B "$IPA" -p "$PORT" -t 2 > "$LOG/p2_stageA_iperf_client.log" 2>&1
    echo "iperf3 client exit=$?"; tail -4 "$LOG/p2_stageA_iperf_client.log"
    sleep 1
    stop_proc sniffer "$SNIF_PID"; SNIF_PID=""
    stop_proc iperf3-server "$SRV_PID"; SRV_PID=""
    echo "### Stage A sniffer on $VA:"; grep '^FINAL' "$LOG/p2_stageA_run.log" | tee "$LOG/p2_stageA.log"
fi

############################################ Stage B topology
say "Stage B topology: $VB in namespace $NS"
topo_remove
ip netns add "$NS" || exit 1
ip link add "$VA" type veth peer name "$VB" || exit 1
ip link set "$VB" netns "$NS"
ip addr add "$IPA/24" dev "$VA"; ip link set "$VA" up
ip netns exec "$NS" ip addr add "$IPB/24" dev "$VB"
ip netns exec "$NS" ip link set "$VB" up
ip netns exec "$NS" ip link set lo up
{
    echo "### root namespace: ip addr show"; ip addr show
    echo "### namespace $NS: ip addr show"; ip netns exec "$NS" ip addr show
    echo "### ip route get $IPB"; ip route get "$IPB"
} 2>&1 | tee "$LOG/p2_netsetup.log"

# run_stage <prefix> <tcp iperf3 extra args> <udp iperf3 extra args>
# <prefix> "" -> logs/p2_run.log, p2_tcpdump.log ...; "full_" -> logs/p2_full_run.log ...
run_stage() {
    local pfx="$1" tcp_args="$2" udp_args="$3"
    local run="$LOG/p2_${pfx}run.log" tdl="$LOG/p2_${pfx}tcpdump.log" pcap="$LOG/p2_${pfx}capture.pcap"
    local cross="$LOG/p2_${pfx}crosscheck.log"

    : > "$run"; : > "$tdl"; rm -f "$pcap"
    tcpdump_start "$pcap"
    "$SNIF" "$VA" > "$run" 2>&1 &
    SNIF_PID=$!
    wait_for 5 bash -c "journalctl -u p2-tcpdump --since '@$TCPD_SINCE' -o cat --no-pager | grep -q 'listening on'" || echo "WARN: tcpdump not listening"
    wait_for 5 grep -q '^START' "$run" || echo "WARN: sniffer did not start"
    ip netns exec "$NS" iperf3 -s -B "$IPB" -p "$PORT" > "$LOG/p2_${pfx}iperf_server.log" 2>&1 &
    SRV_PID=$!
    wait_for 5 ip netns exec "$NS" bash -c "ss -ltn | grep -q ':$PORT '" || echo "WARN: iperf3 server not listening"

    say "[$pfx] iperf3 TCP 5 s ($tcp_args) $IPA -> $IPB:$PORT"
    # shellcheck disable=SC2086
    iperf3 -c "$IPB" -B "$IPA" -p "$PORT" -t 5 $tcp_args > "$LOG/p2_${pfx}iperf_client.log" 2>&1
    echo "iperf3 tcp client exit=$?"; tail -5 "$LOG/p2_${pfx}iperf_client.log"
    say "[$pfx] iperf3 UDP 2 s ($udp_args)"
    # shellcheck disable=SC2086
    iperf3 -c "$IPB" -B "$IPA" -p "$PORT" -u -t 2 $udp_args > "$LOG/p2_${pfx}iperf_client_udp.log" 2>&1
    echo "iperf3 udp client exit=$?"; tail -6 "$LOG/p2_${pfx}iperf_client_udp.log"

    sleep 3 # quiescence before stopping either tool
    stop_proc sniffer "$SNIF_PID"; SNIF_PID=""
    tcpdump_stop
    tcpdump_log > "$tdl"
    stop_proc iperf3-server "$SRV_PID"; SRV_PID=""

    say "[$pfx] sniffer output ($run)"; cat "$run"
    say "[$pfx] tcpdump stderr ($tdl)"; cat "$tdl"

    say "[$pfx] cross-check"
    {
        local sn_total sn_match sn_drops td_cap td_drop td_pcap diff base tol tot_drops
        sn_total=$(sed -n 's/^FINAL .*total_packets=\([0-9]*\).*/\1/p' "$run")
        sn_match=$(sed -n 's/^FINAL .*matched_packets=\([0-9]*\).*/\1/p' "$run")
        sn_drops=$(sed -n 's/^FINAL_KERNEL .*kernel_drops=\([0-9]*\).*/\1/p' "$run")
        td_cap=$(sed -n 's/^\([0-9]*\) packets captured.*/\1/p' "$tdl")
        td_drop=$(sed -n 's/^\([0-9]*\) packets dropped by kernel.*/\1/p' "$tdl")
        td_pcap=$(tcpdump -nn -r "$pcap" 2>/dev/null | wc -l)
        echo "sniffer: total_packets=${sn_total:-NA} matched_packets=${sn_match:-NA} kernel_drops=${sn_drops:-NA}"
        echo "tcpdump: captured(summary)=${td_cap:-NA} dropped_by_kernel(summary)=${td_drop:-NA} packets_in_savefile=$td_pcap"
        if [[ -z "$sn_match" || -z "$sn_drops" ]]; then
            echo "CROSSCHECK[$pfx]: FAIL (sniffer counters missing)"
        else
            # Prefer tcpdump's own summary; fall back to the savefile count if tcpdump never printed one.
            local cap="${td_cap:-$td_pcap}"
            diff=$((sn_match - cap)); ((diff < 0)) && diff=$((-diff))
            base=$((cap / 200)); ((base < 10)) && base=10
            if [[ -z "$td_drop" ]]; then
                echo "abs_diff=$diff (tcpdump drop count unavailable)"
                echo "CROSSCHECK[$pfx]: INCONCLUSIVE (no tcpdump drop count)"
            else
                tot_drops=$((sn_drops + td_drop)); tol=$((base + tot_drops))
                echo "abs_diff=$diff allowance=$tol (base=$base + sniffer_drops=$sn_drops + tcpdump_drops=$td_drop)"
                if ((tot_drops * 100 > cap)); then
                    echo "CROSSCHECK[$pfx]: INCONCLUSIVE (drops $tot_drops > 1% of $cap captured)"
                elif ((diff <= tol)); then echo "CROSSCHECK[$pfx]: PASS"
                else echo "CROSSCHECK[$pfx]: FAIL"; fi
            fi
        fi
    } 2>&1 | tee "$cross"
}

############################################ Stage B runs
run_stage ""      "-b 100M" "-b 50M"
run_stage "full_" ""        "-b 50M"

############################################ Cleanup proof
say "Cleanup"
cleanup
{
    echo "### leftover processes (expect none):"
    pgrep -a 'baseline_sniffer|iperf3|tcpdump' || echo "none"
    echo "### topology left up for later phases (sudo bash scripts/phase2_verify.sh teardown removes it):"
    ip -br addr show "$VA"; ip netns exec "$NS" ip -br addr show "$VB"
} 2>&1 | tee "$LOG/p2_cleanup.log"
