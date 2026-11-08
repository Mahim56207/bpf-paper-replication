#!/usr/bin/env bash
# p10_probe.sh - Phase 10 WP0 feasibility probes (docs/phase10_design.md is written AFTER this, from its answers). Nothing here is a result; every probe
# prints yes or no with the command evidence into logs/p10/probe/. Needs root (RPS write test, softnet counters under traffic, pktgen module query).
# Usage: sudo bash scripts/p10_probe.sh 2>&1 | tee logs/p10/p10_probe_console.log        (about 1 minute; leave the machine alone)
# Refuses to start if logs/p10/probe/ is not empty. No output is sent to /dev/null: every command writes into the probe folder.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
P=logs/p10/probe
mkdir -p "$P"
if [[ -n "$(ls -A "$P")" ]]; then echo "ABORT: $P is not empty; refusing to overwrite (move it away on purpose)" >&2; exit 1; fi
NS=p2ns; VA=p1veth0; VB=p1veth1; IPB=10.0.0.2
ans() { echo "PROBE $1: $2" | tee -a "$P/answers.txt"; }       # answers.txt is the summary read by WP2 and ENV.md
run() { local f="$P/$1.txt"; shift; { echo "\$ $*"; "$@"; echo "(exit $?)"; } > "$f" 2>&1; }

echo "=== Phase 10 WP0 probes $(date -Is) ==="
run uname uname -srm
run gcc gcc --version
run clang clang --version
run libpcap pkg-config --modversion libpcap
run tcpdump tcpdump --version
run nproc nproc
run cpu_online cat /sys/devices/system/cpu/online
run isolcpus cat /proc/cmdline
run free free -m
run swap cat /proc/swaps
ans gcc "$(head -2 "$P/gcc.txt" | tail -1)"
ans clang "$(head -2 "$P/clang.txt" | tail -1)"

echo "--- lab network"
if ! ip link show "$VA" > "$P/lab_check.txt" 2>&1 || ! ip netns list | grep -q "^$NS"; then bash scripts/lab_up.sh > "$P/lab_up.txt" 2>&1; fi
run lab_addr ip -br addr show "$VA"
run lab_ns_addr ip netns exec "$NS" ip -br addr show "$VB"

echo "--- RPS on the veth devices (receiving end in $NS)"
run rps_list ip netns exec "$NS" bash -c "ls -l /sys/class/net/$VB/queues/ && for q in /sys/class/net/$VB/queues/rx-*; do echo \$q rps_cpus=\$(cat \$q/rps_cpus); ls -l \$q/rps_cpus; done"
run rps_list_root bash -c "ls -l /sys/class/net/$VA/queues/ && for q in /sys/class/net/$VA/queues/rx-*; do echo \$q rps_cpus=\$(cat \$q/rps_cpus); done"
ip netns exec "$NS" bash -c "echo 2 > /sys/class/net/$VB/queues/rx-0/rps_cpus" > "$P/rps_write.txt" 2>&1
rc=$?
readback=$(ip netns exec "$NS" cat /sys/class/net/$VB/queues/rx-0/rps_cpus 2>> "$P/rps_write.txt")
echo "write rc=$rc readback=$readback" >> "$P/rps_write.txt"
if [[ $rc -eq 0 && -n "$readback" ]] && (( 16#$readback == 2 )); then ans rps_writable "yes (rx-0/rps_cpus accepted mask 2 and read back 2)"; else ans rps_writable "no (rc=$rc readback=$readback; see rps_write.txt)"; fi

echo "--- RPS functional test: softnet_stat per CPU during a 3 s iperf3 UDP flood (clients core 4, server core 3)"
snap() { python3 -I - "$1" <<'PY' > "$2"
import sys
rows = [[int(x, 16) for x in l.split()] for l in open("/proc/net/softnet_stat")]
print(" ".join(str(r[0]) for r in rows))
PY
}
flood3() {  # flood3 <tag>: 3 s unlimited UDP, 214-byte payload (256-byte frames), match port
    ip netns exec "$NS" taskset -c 3 iperf3 -s -B "$IPB" -p 4040 -J --logfile "$P/srv_$1.json" -1 > "$P/srv_$1.out" 2>&1 &
    local spid=$!
    sleep 1
    snap before "$P/softnet_$1_before.txt"
    taskset -c 4 iperf3 -c "$IPB" -p 4040 -u -b 0 -l 214 -t 3 -J > "$P/cli_$1.json" 2> "$P/cli_$1.err"
    snap after "$P/softnet_$1_after.txt"
    wait "$spid"
}
ip netns exec "$NS" bash -c "echo 0 > /sys/class/net/$VB/queues/rx-0/rps_cpus" > "$P/rps_off.txt" 2>&1
flood3 off
ip netns exec "$NS" bash -c "echo 2 > /sys/class/net/$VB/queues/rx-0/rps_cpus" > "$P/rps_on.txt" 2>&1
flood3 on
ip netns exec "$NS" bash -c "echo 0 > /sys/class/net/$VB/queues/rx-0/rps_cpus" > "$P/rps_reset.txt" 2>&1
python3 -I - "$P" <<'PY' | tee "$P/rps_functional.txt"
import sys
P = sys.argv[1]
def vec(n): return [int(x) for x in open(f"{P}/{n}.txt").read().split()]
res = {}
for tag in ("off", "on"):
    b, a = vec(f"softnet_{tag}_before"), vec(f"softnet_{tag}_after")
    d = [y - x for x, y in zip(b, a)]
    res[tag] = d
    print(f"softnet processed delta per CPU, RPS {tag}: {d}")
tot_on = sum(res["on"]) or 1
share1 = res["on"][1] / tot_on
tot_off = sum(res["off"]) or 1
print(f"CPU1 share of processed packets: RPS off {res['off'][1] / tot_off:.3f}, RPS on {share1:.3f}")
print("RESULT " + ("yes" if share1 > 0.5 and res["off"][1] / tot_off < 0.2 else "no"))
PY
verdict=$(grep '^RESULT' "$P/rps_functional.txt" | cut -d' ' -f2)
ans rps_steers_receive_work "${verdict:-no} (CPU1 share of softnet processed packets with mask 2 against mask 0; see rps_functional.txt)"

echo "--- paced generator candidates"
run pktgen_proc bash -c "ls -l /proc/net/pktgen 2>&1; echo ---; modinfo pktgen 2>&1; echo ---; modprobe -n -v pktgen 2>&1"
run gen_tools bash -c "for t in trafgen mausezahn pktgen.sh iperf3 pktgen; do printf '%s: ' \$t; command -v \$t || echo absent; done"
run sendmmsg_header bash -c "grep -rn 'sendmmsg' /usr/include/sys/socket.h /usr/include/*/sys/socket.h 2>&1"
# pktgen is a loadable module (modinfo found it in attempt 1); load it for the probe only and unload it again if this script loaded it
loaded_here=0
if ! lsmod > "$P/lsmod_before.txt" 2>&1 || ! grep -q '^pktgen' "$P/lsmod_before.txt"; then modprobe pktgen > "$P/modprobe_pktgen.txt" 2>&1; loaded_here=1; fi
ls -l /proc/net/pktgen > "$P/pktgen_ls.txt" 2>&1
if [[ -e /proc/net/pktgen/pgctrl ]]; then ans pktgen_available "yes (module loadable, /proc/net/pktgen/pgctrl present; loaded for the probe only)"; else ans pktgen_available "no (see modprobe_pktgen.txt, pktgen_ls.txt)"; fi
if [[ $loaded_here -eq 1 ]]; then rmmod pktgen > "$P/rmmod_pktgen.txt" 2>&1; echo "rmmod rc=$?" >> "$P/rmmod_pktgen.txt"; lsmod > "$P/lsmod_after.txt" 2>&1; fi
for t in trafgen mausezahn; do if command -v "$t" > "$P/which_$t.txt" 2>&1; then ans "${t}_available" "yes ($(cat "$P/which_$t.txt"))"; else ans "${t}_available" "no"; fi; done
if grep -q "sendmmsg" "$P/sendmmsg_header.txt"; then ans own_pacer_possible "yes (sendmmsg declared in sys/socket.h; a C pacer on one core is the fallback)"; else ans own_pacer_possible "no (sendmmsg not found)"; fi

echo "--- other facts needed by the design"
run rmem_max sysctl net.core.rmem_max net.core.rmem_default net.core.wmem_max net.core.netdev_max_backlog
run bpf_jit sysctl net.core.bpf_jit_enable
run unpriv_bpf sysctl kernel.unprivileged_bpf_disabled
run default_route ip route get 1.1.1.1
run tcpdump_ifaces tcpdump -D
run nsenter_present command -v nsenter
run perf_paranoid cat /proc/sys/kernel/perf_event_paranoid
ans nsenter "$(command -v nsenter || echo absent)"
ans swap_in_use_MB "$(free -m | awk '/^Swap:/ {print $3}')"
ans mem_available_MB "$(free -m | awk '/^Mem:/ {print $7}')"

chown -R "${SUDO_USER:-root}": logs/p10 2>> "$P/chown.txt"
echo "=== answers (logs/p10/probe/answers.txt) ==="; cat "$P/answers.txt"
echo "=== FINISHED $(date -Is) ==="
