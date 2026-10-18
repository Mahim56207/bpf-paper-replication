#!/usr/bin/env bash
# Phase 4 verify: load the Phase 3 filter with build/loader, drive paced match traffic (port 4040)
# plus noise (ports 5050/5051), and cross-check the counters against tcpdump.
# Usage: sudo bash scripts/phase4_verify.sh [logdir] [loader-flags] 2>&1 | tee logs/p4_verify.log
#   loader-flags: optional, e.g. "-d" (drain mode, Phase 6a regression); default none (Phase 4 behaviour).
#
# Cross-check rules (stated before any run; justified in docs/phase4_notes.md):
#   matched: |loader matched - tcpdump(port 4040) captured| <= max(10, captured/200) + tcpdump dropped
#            PASS; INCONCLUSIVE if tcpdump dropped > 1% of captured; FAIL otherwise.
#            This is the Phase 2 rule with the sniffer-drop term removed: the filter counts a packet
#            when it runs, and the AF_PACKET socket's own drops (reported in FINAL_SOCKET) are not
#            subtracted from that count. The run tests that assumption: socket drops are expected
#            to be large (nothing reads the socket) while matched must still agree with tcpdump.
#   total:   |loader (slot0+slot1) - tcpdump(no filter) "received by filter"| <= max(10, received/200)
#   dropped: slot 0 must be > 0 (the noise traffic and background frames), and
#            L2 view: slot 1 must be > 0 on real traffic (the filter parses ethhdr at offset 0).
#   drain (only when loader-flags contains -d; added in Phase 6a, declared before it was run):
#            |delivered_packets - matched| <= max(10, matched/200) AND socket kernel_drops <= max(10, matched/200),
#            i.e. every accepted packet was read and the socket queue never overflowed. PASS/FAIL.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
LOG="${1:-$ROOT/logs}"
LFLAGS="${2:-}"
mkdir -p "$LOG"
LOADER="$ROOT/build/loader"
VA=p1veth0; IPA=10.0.0.1; IPB=10.0.0.2; NS=p2ns
LOADER_PID=""; SRV_PIDS=""

say() { echo; echo "== $*"; }

wait_for() { # wait_for <seconds> <command...>
    local n=$(($1 * 10)); shift
    while ((n-- > 0)); do "$@" >/dev/null 2>&1 && return 0; sleep 0.1; done
    return 1
}

# stop_proc <label> <pid>: SIGTERM, wait up to 5 s, then SIGKILL; never wait on a process we cannot signal.
stop_proc() {
    local label="$1" pid="$2" n=50
    [[ -n "$pid" ]] || return 0
    if ! kill -TERM "$pid" 2>/dev/null; then
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

# tcpdump as a systemd unit: its AppArmor profile only accepts signals from unconfined peers
# (DEVIATIONS D2.8). td_start <unit> <tcpdump filter or ""> ; td_stop <unit>; td_log <unit> <since>
TD_SINCE=0
td_start() {
    systemctl stop "$1" 2>/dev/null; systemctl reset-failed "$1" 2>/dev/null
    TD_SINCE=$(date +%s)
    if [[ -n "$2" ]]; then
        systemd-run --quiet --unit="$1" --collect --property=TimeoutStopSec=10 \
            tcpdump -i "$VA" -nn -Z root --immediate-mode -w /dev/null "$2"
    else
        systemd-run --quiet --unit="$1" --collect --property=TimeoutStopSec=10 \
            tcpdump -i "$VA" -nn -Z root --immediate-mode -w /dev/null
    fi
}
td_stop() { systemctl is-active --quiet "$1" || return 0; systemctl stop "$1" || echo "WARN: systemctl stop $1 failed"; }
td_log() { sleep 1; journalctl -u "$1" --since "@$2" -o cat --no-pager 2>&1; }

cleanup() {
    stop_proc loader "$LOADER_PID"; LOADER_PID=""
    for p in $SRV_PIDS; do stop_proc iperf3-server "$p"; done; SRV_PIDS=""
    td_stop p4-td4040; td_stop p4-tdall
}
trap cleanup EXIT

[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
for f in "$LOADER" build/phase3_kern.o /usr/bin/iperf3 /usr/bin/tcpdump; do
    [[ -e "$f" ]] || { echo "FATAL: missing $f" >&2; exit 1; }
done
mountpoint -q /sys/fs/bpf || mount -t bpf bpf /sys/fs/bpf

echo "== phase4_verify $(date -u +%Y-%m-%dT%H:%M:%SZ) arch=$(uname -m) kernel=$(uname -r) loader-flags='$LFLAGS'"

# stale processes from an aborted run
pkill -KILL -f "build/loader.*$VA" 2>/dev/null
pkill -KILL -f "iperf3 -s -B $IPB" 2>/dev/null
systemctl stop p4-td4040 p4-tdall 2>/dev/null; systemctl reset-failed p4-td4040 p4-tdall 2>/dev/null
sleep 0.5

############################################ 1. lab
say "1. lab network (scripts/lab_up.sh, same commands as Stage B of phase2_verify.sh)"
bash scripts/lab_up.sh 2>&1 | tee "$LOG/p4_netsetup.log"
echo "### ip addr show (root namespace, as required)"; ip addr show "$VA" 2>&1 | tee -a "$LOG/p4_netsetup.log"

############################################ 2. capture + loader
say "2. start tcpdump (port 4040), tcpdump (no filter), loader"
td_start p4-td4040 "port 4040"; T4040_SINCE=$TD_SINCE
td_start p4-tdall ""; TALL_SINCE=$TD_SINCE
wait_for 5 bash -c "journalctl -u p4-td4040 --since '@$T4040_SINCE' -o cat --no-pager | grep -q 'listening on'" || echo "WARN: tcpdump(4040) not listening"
wait_for 5 bash -c "journalctl -u p4-tdall --since '@$TALL_SINCE' -o cat --no-pager | grep -q 'listening on'" || echo "WARN: tcpdump(all) not listening"
# shellcheck disable=SC2086
"$LOADER" $LFLAGS "$VA" > "$LOG/p4_run.log" 2>&1 &
LOADER_PID=$!
wait_for 10 grep -q '^START' "$LOG/p4_run.log" || { echo "FATAL: loader did not start"; cat "$LOG/p4_run.log"; exit 1; }
cat "$LOG/p4_run.log"

for port in 4040 5050 5051; do
    ip netns exec "$NS" iperf3 -s -B "$IPB" -p "$port" > "$LOG/p4_iperf_server_$port.log" 2>&1 &
    SRV_PIDS="$SRV_PIDS $!"
done
for port in 4040 5050 5051; do
    wait_for 5 ip netns exec "$NS" bash -c "ss -ltn | grep -q ':$port '" || echo "WARN: iperf3 server $port not listening"
done

############################################ 3. traffic
say "3. traffic: match = TCP 100 Mbit/s 5 s then UDP 50 Mbit/s 2 s on 4040; noise = TCP 20 Mbit/s (5050) and UDP 10 Mbit/s (5051) for 8 s"
iperf3 -c "$IPB" -B "$IPA" -p 5050 -t 8 -b 20M > "$LOG/p4_noise_tcp.log" 2>&1 &
NOISE1=$!
iperf3 -c "$IPB" -B "$IPA" -p 5051 -u -t 8 -b 10M > "$LOG/p4_noise_udp.log" 2>&1 &
NOISE2=$!
iperf3 -c "$IPB" -B "$IPA" -p 4040 -t 5 -b 100M > "$LOG/p4_iperf_client.log" 2>&1 &
TCP4040=$!
sleep 2
say "snapshots during traffic (loader attached)"
{ echo "### bpftool prog show"; bpftool prog show; } 2>&1 | tee "$LOG/p4_prog_show.log"
{ echo "### bpftool map show"; bpftool map show; } 2>&1 | tee "$LOG/p4_map_show.log"
wait "$TCP4040"; echo "iperf3 tcp 4040 exit=$?"; tail -4 "$LOG/p4_iperf_client.log"
iperf3 -c "$IPB" -B "$IPA" -p 4040 -u -t 2 -b 50M > "$LOG/p4_iperf_client_udp.log" 2>&1
echo "iperf3 udp 4040 exit=$?"; tail -4 "$LOG/p4_iperf_client_udp.log"
wait "$NOISE1"; echo "noise tcp exit=$?"; wait "$NOISE2"; echo "noise udp exit=$?"

sleep 3 # quiescence
stop_proc loader "$LOADER_PID"; LOADER_PID=""
td_stop p4-td4040; td_stop p4-tdall
td_log p4-td4040 "$T4040_SINCE" > "$LOG/p4_tcpdump_4040.log"
td_log p4-tdall "$TALL_SINCE" > "$LOG/p4_tcpdump_all.log"
for p in $SRV_PIDS; do stop_proc iperf3-server "$p"; done; SRV_PIDS=""

say "loader output ($LOG/p4_run.log)"; cat "$LOG/p4_run.log"
say "tcpdump port 4040 ($LOG/p4_tcpdump_4040.log)"; cat "$LOG/p4_tcpdump_4040.log"
say "tcpdump no filter ($LOG/p4_tcpdump_all.log)"; cat "$LOG/p4_tcpdump_all.log"

############################################ 4. after-exit snapshots
say "snapshots after the loader exited (its program and map should be gone)"
{ echo "### bpftool prog show"; bpftool prog show; } 2>&1 | tee "$LOG/p4_prog_show_after.log"
{ echo "### bpftool map show"; bpftool map show; } 2>&1 | tee "$LOG/p4_map_show_after.log"

############################################ 5. verifier silence
say "5. verifier silence: bpftool prog load build/phase3_kern.o /sys/fs/bpf/repl_p4 type socket 2>$LOG/p4_verifier.log"
rm -f /sys/fs/bpf/repl_p4
bpftool prog load build/phase3_kern.o /sys/fs/bpf/repl_p4 type socket 2> "$LOG/p4_verifier.log"
echo "bpftool exit=$?"
wc -c "$LOG/p4_verifier.log" | tee "$LOG/p4_verifier_wc.log"
rm -f /sys/fs/bpf/repl_p4; echo "temp pin removed: $([[ -e /sys/fs/bpf/repl_p4 ]] && echo NO || echo yes)"

############################################ 6. cross-check
say "6. cross-check"
{
    lm=$(sed -n 's/^FINAL t=.*matched=\([0-9]*\).*/\1/p' "$LOG/p4_run.log")
    ld=$(sed -n 's/^FINAL t=.* dropped=\([0-9]*\).*/\1/p' "$LOG/p4_run.log")
    lt=$(sed -n 's/^FINAL t=.* total=\([0-9]*\).*/\1/p' "$LOG/p4_run.log")
    sk=$(sed -n 's/^FINAL_SOCKET .*kernel_drops=\([0-9]*\).*/\1/p' "$LOG/p4_run.log")
    sp=$(sed -n 's/^FINAL_SOCKET kernel_packets=\([0-9]*\).*/\1/p' "$LOG/p4_run.log")
    c4=$(sed -n 's/^\([0-9]*\) packets captured.*/\1/p' "$LOG/p4_tcpdump_4040.log")
    r4=$(sed -n 's/^\([0-9]*\) packets received by filter.*/\1/p' "$LOG/p4_tcpdump_4040.log")
    d4=$(sed -n 's/^\([0-9]*\) packets dropped by kernel.*/\1/p' "$LOG/p4_tcpdump_4040.log")
    ra=$(sed -n 's/^\([0-9]*\) packets received by filter.*/\1/p' "$LOG/p4_tcpdump_all.log")
    echo "loader : total=${lt:-NA} matched=${lm:-NA} dropped=${ld:-NA}  socket kernel_packets=${sp:-NA} kernel_drops=${sk:-NA}"
    echo "tcpdump(4040): captured=${c4:-NA} received_by_filter=${r4:-NA} dropped=${d4:-NA}"
    echo "tcpdump(all) : received_by_filter=${ra:-NA}"
    if [[ -z "$lm" || -z "$ld" || -z "$lt" || -z "$c4" || -z "$d4" || -z "$r4" || -z "$ra" ]]; then
        echo "CROSSCHECK matched: FAIL (could not parse a counter)"
    else
        diff=$((lm - c4)); ((diff < 0)) && diff=$((-diff))
        base=$((c4 / 200)); ((base < 10)) && base=10
        tol=$((base + d4))
        echo "matched: abs_diff=$diff allowance=$tol (base=$base + tcpdump_drops=$d4); loader matched - tcpdump received_by_filter = $((lm - r4))"
        if ((d4 * 100 > c4)); then echo "CROSSCHECK matched: INCONCLUSIVE (tcpdump drops $d4 > 1% of $c4 captured)"
        elif ((diff <= tol)); then echo "CROSSCHECK matched: PASS"
        else echo "CROSSCHECK matched: FAIL"; fi
        tdiff=$((lt - ra)); ((tdiff < 0)) && tdiff=$((-tdiff))
        tbase=$((ra / 200)); ((tbase < 10)) && tbase=10
        echo "total: abs_diff=$tdiff allowance=$tbase (loader slot0+slot1 vs tcpdump(all) received_by_filter)"
        if ((tdiff <= tbase)); then echo "CROSSCHECK total: PASS"; else echo "CROSSCHECK total: FAIL"; fi
        if ((ld > 0)); then echo "CHECK dropped slot moved: PASS (slot0=$ld)"; else echo "CHECK dropped slot moved: FAIL (slot0=0)"; fi
        if ((lm > 0)); then echo "L2 VIEW: CONFIRMED (slot1=$lm > 0 on real traffic; the filter parses ethhdr at offset 0)"
        else echo "L2 VIEW: NOT CONFIRMED (slot1=0)"; fi
        if [[ "$LFLAGS" == *-d* ]]; then
            dp=$(sed -n 's/^FINAL t=.* delivered_packets=\([0-9]*\).*/\1/p' "$LOG/p4_run.log")
            if [[ -z "$dp" || -z "$sk" ]]; then echo "CHECK drain: FAIL (delivered_packets or kernel_drops missing)"
            else
                ddiff=$((dp - lm)); ((ddiff < 0)) && ddiff=$((-ddiff))
                dbase=$((lm / 200)); ((dbase < 10)) && dbase=10
                echo "drain: delivered_packets=$dp matched=$lm abs_diff=$ddiff allowance=$dbase; socket kernel_drops=$sk allowance=$dbase"
                if ((ddiff <= dbase && sk <= dbase)); then echo "CHECK drain: PASS"; else echo "CHECK drain: FAIL"; fi
            fi
        fi
    fi
} 2>&1 | tee "$LOG/p4_crosscheck.log"

############################################ cleanup proof
say "cleanup"
cleanup
{
    echo "### leftover processes (expect none):"
    pgrep -af 'build/loader|iperf3|tcpdump' || echo "none"
    echo "### topology left up (sudo bash scripts/lab_up.sh down removes it):"
    ip -br addr show "$VA"; ip netns exec "$NS" ip -br addr show p1veth1
} 2>&1 | tee "$LOG/p4_cleanup.log"
