#!/usr/bin/env bash
# R1 (reviewer ruling on D6.4): classify the V5 excess before amending anything.
#  1. three 5 s QUIET windows: capture point active (config A's baseline_sniffer, as in calibration), NO iperf3
#  2. one instrumented run, 1000 pps, 5 s (bench.sh one A m 512 1 1000 5, label v5diag) with a parallel tcpdump
# For every window the frames are classified: udp port 4040 (the data flow), tcp port 4040 (the iperf3 control
# connection), arp, icmp6 (IPv6 ND/MLD), other ip6, other. For the instrumented run each class is also split into
# before / inside / after the measured window. tcpdump is the classifier; the experiment's own capture-point total
# (kernel_packets) is printed next to tcpdump's total.
# Usage: sudo bash scripts/v5_excess.sh 2>&1 | tee logs/v5_excess_breakdown.log
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
VA=p1veth0
ip link show "$VA" >/dev/null 2>&1 || bash scripts/lab_up.sh >/dev/null 2>&1
pkill -KILL -f "build/(loader|baseline_sniffer)" 2>/dev/null
systemctl stop v5-td 2>/dev/null; systemctl reset-failed v5-td 2>/dev/null
rm -f logs/v5diag_*.pcap

td_start() { # td_start <pcap>
    TD_SINCE=$(date +%s)
    systemd-run --quiet --unit=v5-td --collect --property=TimeoutStopSec=10 \
        tcpdump -i "$VA" -nn -Z root --immediate-mode -U -w "$1"
    for _ in $(seq 1 50); do journalctl -u v5-td --since "@$TD_SINCE" -o cat --no-pager 2>/dev/null | grep -q 'listening on' && return 0; sleep 0.1; done
    echo "WARN: tcpdump not listening"
}
td_stop() { systemctl is-active --quiet v5-td && systemctl stop v5-td; sleep 1; }

classify() { # classify <label> <pcap> <window_start_epoch|-> <window_end_epoch|-> <capture_point_total>
    python3 -I - "$@" <<'PY'
import subprocess, sys
label, pcap, ws, we, cp = sys.argv[1:6]
ws = None if ws == "-" else float(ws); we = None if we == "-" else float(we)
FILTERS = [("udp port 4040 (data flow)", "udp port 4040"), ("tcp port 4040 (iperf3 control)", "tcp port 4040"),
           ("arp", "arp"), ("icmp6 (ND/MLD)", "icmp6"), ("other ip6", "ip6 and not icmp6"),
           ("other", "not (udp port 4040 or tcp port 4040 or arp or ip6)")]
def frames(flt):
    r = subprocess.run(["tcpdump", "-tt", "-nn", "-r", pcap, flt], capture_output=True, text=True)
    return [(float(l.split()[0]), l) for l in r.stdout.splitlines() if l and l[0].isdigit()]
allf = frames("")  # tcpdump with an empty filter prints everything
print(f"--- {label}")
print(f"capture point total (kernel_packets) = {cp};  tcpdump total = {len(allf)}")
print("%-34s %6s %8s %8s %8s" % ("class", "all", "before", "inside", "after"))
nonflow = 0
for name, flt in FILTERS:
    f = frames(flt)
    if ws is None:
        print("%-34s %6d %8s %8s %8s" % (name, len(f), "-", "-", "-"))
    else:
        b = sum(1 for t, _ in f if t < ws); i = sum(1 for t, _ in f if ws <= t <= we); a = sum(1 for t, _ in f if t > we)
        print("%-34s %6d %8d %8d %8d" % (name, len(f), b, i, a))
    if not name.startswith("udp port 4040"):
        nonflow += len(f)
print("%-34s %6d" % ("non-flow frames (everything but udp 4040)", nonflow))
print("non-flow frame list (epoch, summary):")
for t, l in sorted(x for flt in FILTERS[1:] for x in frames(flt[1]))[:60]:
    print("   ", l[:150])
PY
}

echo "== v5_excess $(date -u +%Y-%m-%dT%H:%M:%SZ) kernel=$(uname -r)"
echo
echo "######## 1. QUIET windows: 3 x 5 s, capture point active, NO iperf3"
for i in 1 2 3; do
    pcap="$ROOT/logs/v5diag_quiet_$i.pcap"
    td_start "$pcap"
    taskset -c 2 build/baseline_sniffer "$VA" > "/tmp/v5_sniffer_$i.log" 2>&1 &
    sp=$!
    for _ in $(seq 1 50); do grep -q '^START' "/tmp/v5_sniffer_$i.log" && break; sleep 0.1; done
    sleep 5
    kill -TERM "$sp"; wait "$sp" 2>/dev/null
    td_stop
    T=$(sed -n 's/^FINAL_KERNEL kernel_packets=\([0-9]*\).*/\1/p' "/tmp/v5_sniffer_$i.log")
    classify "quiet window $i" "$pcap" - - "${T:-NA}"
done

echo
echo "######## 2. INSTRUMENTED run: bench.sh one A m 512 1 1000 5 (label v5diag), tcpdump in parallel"
pcap="$ROOT/logs/v5diag_run.pcap"
td_start "$pcap"
BENCH_LABEL=v5diag bash scripts/bench.sh one A m 512 1 1000 5 < /dev/null
td_stop
log=logs/v5diag_A_m_512_1.log
WS=$(awk '/^### stat_before/{f=1;next} /^### /{f=0} f && /^time /{print $2}' "$log")
WE=$(awk '/^### stat_after/{f=1;next} /^### /{f=0} f && /^time /{print $2}' "$log")
T=$(sed -n 's/^FINAL_KERNEL kernel_packets=\([0-9]*\).*/\1/p' "$log")
echo "measured window: $WS .. $WE"
classify "instrumented run (1000 pps, 5 s, 512 B, udp 4040)" "$pcap" "$WS" "$WE" "${T:-NA}"
echo
echo "######## harness view of the same run (summarize.py parse_run)"
python3 -I - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("s", "scripts/summarize.py"); s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
r = s.parse_run("logs/v5diag_A_m_512_1.log")
print("offered_pkts=%s tap_total=%s excess=%s reasons=%s" % (r["offered_pkts"], r["tap_total"], r["tap_total"] - r["offered_pkts"], r["reasons"] or "-"))
PY
[[ -n "${SUDO_USER:-}" ]] && chown -R "$SUDO_USER": logs 2>/dev/null
echo "######## done"
