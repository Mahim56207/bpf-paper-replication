#!/usr/bin/env bash
# bench.sh - Phase 6 measurement harness. Design, definitions and pre-declared rules: docs/phase6_design.md.
#
# Subcommands
#   plan [seed]                  write results/bench_plan.tsv, print matrix size and wall-clock estimate   (no traffic, no root)
#   topology                     write results/topology.md                                                (no traffic, no root)
#   one CFG TRAFFIC SIZE REP PPS [DUR]  one run -> logs/bench_<cfg>_<traffic>_<size>_<rep>.log   (root, generates traffic)
#                                BENCH_LABEL=smoke -> logs/smoke_*.log (smoke runs: excluded from analysis)
#   calibrate                    find config A's loss-free ceiling -> results/calibration.json            (root, generates traffic)
#   run [plan]                   execute the plan: warm-ups first (discarded), then the blocks in order   (root, generates traffic)
#
# Configs   A baseline_sniffer | B loader -d, port-4040 filter | C loader (no drain), port-4040 filter
#           D loader -d, reject_all | E loader -d, accept_all
# Traffic   nm = UDP to a non-matching port (5050) | m = UDP to port 4040 | flood = two unlimited UDP streams
#           (4040 match + 5050 noise) | warmup = like m at size 512 | cal = calibration ladder
# Size      L2 frame bytes without FCS; UDP payload = size - 42 (14 Ethernet + 20 IP + 8 UDP)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

DUR="${BENCH_DUR:-10}"                 # seconds of traffic per run
CAL_DUR="${BENCH_CAL_DUR:-5}"          # seconds per calibration step
OVERHEAD_EST="${BENCH_OVERHEAD_EST:-8}"  # ASSUMED seconds of per-run setup/teardown; measured only after the first runs
SIZES=(64 256 512 1024 1500)
R_CURVE=3
R_FLOOD=5
FLOOD_SIZE=256
MATCH_PORT=4040
NOISE_PORT=5050
# CPU pinning plan (nproc=5): the capture process, the iperf3 server and the iperf3 client(s) never share a core.
CPU_SYS=0; CPU_NOISE_CLI=1; CPU_CAP=2; CPU_SRV=3; CPU_MATCH_CLI=4
VA=p1veth0; IPA=10.0.0.1; IPB=10.0.0.2; NS=p2ns
CAL_LADDER=(1000 2000 4000 8000 16000 32000 64000)

mkdir -p results logs

############################################################ plan
cmd_plan() {
    local seed="${1:-${BENCH_SEED:-}}"
    [[ -n "$seed" ]] || seed="$(date +%s)"
    python3 -I - "$seed" "$DUR" "$OVERHEAD_EST" "$R_CURVE" "$R_FLOOD" "$FLOOD_SIZE" "$CAL_DUR" "${#CAL_LADDER[@]}" "${SIZES[*]}" <<'EOF'
import random, sys
seed, dur, overhead, r_curve, r_flood, flood_size, cal_dur, cal_steps = (int(x) for x in sys.argv[1:9])
sizes = [int(x) for x in sys.argv[9].split()]
rng = random.Random(seed)
points = []  # (cfg, traffic, size, rep)
for rep in range(1, r_curve + 1):
    for size in sizes:
        for cfg in "ABD":
            points.append(("curve_reject", cfg, "nm", size, rep))
        for cfg in "ABE":
            points.append(("curve_accept", cfg, "m", size, rep))
for rep in range(1, r_flood + 1):
    for cfg in "ABC":
        points.append(("flood", cfg, "flood", flood_size, rep))
rows = [("warmup", "warmup", cfg, "warmup", 512, 0) for cfg in "ABCDE"]
for rep in range(1, max(r_curve, r_flood) + 1):
    block = [p for p in points if p[4] == rep]
    rng.shuffle(block)  # run order randomised within each rep block
    rows += [("run",) + p for p in block]
with open("results/bench_plan.tsv", "w") as f:
    f.write("# seed=%d dur=%d\n# seq\tphase\tclass\tcfg\ttraffic\tsize\trep\n" % (seed, dur))
    for i, r in enumerate(rows, 1):
        f.write("%d\t%s\t%s\t%s\t%s\t%d\t%d\n" % ((i,) + r))
counts = {}
for r in rows:
    counts[r[1]] = counts.get(r[1], 0) + 1
n = len(rows)
print("seed=%d  plan written to results/bench_plan.tsv" % seed)
print("runs: %d total = %d warm-up (discarded) + %d measured" % (n, counts.get("warmup", 0), n - counts.get("warmup", 0)))
for k in ("curve_reject", "curve_accept", "flood"):
    print("  %-13s %3d runs" % (k, counts.get(k, 0)))
est = n * (dur + overhead)
print("wall-clock estimate for 'run': %d runs x (%d s traffic + %d s ASSUMED overhead) = %d s = %.1f min"
      % (n, dur, overhead, est, est / 60.0))
cal_runs = 2 * cal_steps  # sizes 64 and 1500
print("calibration (separate, 'calibrate'): %d runs x (%d s + %d s ASSUMED overhead) = %d s = %.1f min"
      % (cal_runs, cal_dur, overhead, cal_runs * (cal_dur + overhead), cal_runs * (cal_dur + overhead) / 60.0))
EOF
}

############################################################ topology
cmd_topology() {
    {
        echo "# Topology and controls (recorded by scripts/bench.sh topology)"
        echo
        echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ). Every value below is the output of the command shown."
        echo
        echo "## Host"
        echo '```'
        echo "\$ uname -srm";           uname -srm
        echo "\$ nproc";                nproc
        echo "\$ getconf CLK_TCK";      getconf CLK_TCK
        echo "\$ cat /proc/sys/net/core/bpf_jit_enable"; cat /proc/sys/net/core/bpf_jit_enable
        echo "\$ lscpu | grep -E 'Model name|Architecture|Thread|Core|Socket|CPU\\(s\\)'"; lscpu 2>&1 | grep -E 'Model name|Architecture|Thread|Core|Socket|^CPU\(s\)'
        echo '```'
        echo
        echo "ENV.md records the machine as arm64 (aarch64), not x86; nothing in the harness assumes x86."
        echo
        echo "## CPU frequency governor"
        echo '```'
        echo "\$ cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"
        cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>&1 | sort | uniq -c
        echo '```'
        echo
        echo "## Interface offloads (ethtool -k $VA)"
        echo '```'
        echo "\$ ethtool -k $VA"; ethtool -k "$VA" 2>&1
        echo '```'
        echo
        echo "## Link"
        echo '```'
        echo "\$ ip -d link show $VA"; ip -d link show "$VA" 2>&1
        echo '```'
        echo
        echo "## /proc/net/packet columns (the contract names a Drops column)"
        echo '```'
        echo "\$ head -1 /proc/net/packet"; head -1 /proc/net/packet
        echo '```'
        echo "If the header above has no Drops column, per-socket drops come from PACKET_STATISTICS instead: the"
        echo "sniffer prints \`FINAL_KERNEL kernel_drops=\` and the loader \`FINAL_SOCKET kernel_drops=\`."
        echo
        echo "## Tools"
        echo '```'
        for t in "iperf3 --version" "pidstat -V" "vmstat -V" "mpstat -V" "taskset --version" "bpftool version"; do
            echo "\$ $t"; $t 2>&1 | head -2
        done
        echo '```'
        echo
        echo "## Pinning plan (nproc=5)"
        echo
        echo "| core | use |"
        echo "|---|---|"
        echo "| $CPU_SYS | left free: system, bench.sh, pidstat, vmstat |"
        echo "| $CPU_NOISE_CLI | iperf3 client for the noise stream (flood runs only) |"
        echo "| $CPU_CAP | capture process: baseline_sniffer (A) or loader (B-E) |"
        echo "| $CPU_SRV | iperf3 server(s), inside namespace $NS |"
        echo "| $CPU_MATCH_CLI | iperf3 client for the main stream (curve runs and the matching flood stream) |"
        echo
        echo "The capture process, the iperf3 server and the iperf3 client are never on the same core. Note: for a veth"
        echo "pair the receive path (and therefore the in-kernel filter) normally runs in softirq context on the sending"
        echo "core, i.e. core $CPU_MATCH_CLI, not on core $CPU_CAP; the harness therefore also records per-CPU busy time from /proc/stat."
    } > results/topology.md
    echo "wrote results/topology.md ($(wc -l < results/topology.md) lines)"
}

############################################################ helpers for runs
need_root() { [[ $EUID -eq 0 ]] || { echo "FATAL: this subcommand needs sudo" >&2; exit 1; }; }
# Files written as root must stay owned by the invoking user, so later non-root summarize runs can rewrite them.
fix_owner() { [[ -n "${SUDO_USER:-}" ]] && chown -R "$SUDO_USER": results logs 2>/dev/null; return 0; }

section() { # section <name> <file>  (appends "### name" + file to the run log)
    { echo "### $1"; cat "$2" 2>/dev/null; echo; } >> "$OUT"
}

wait_for() { # wait_for <seconds> <command...>
    local n=$(($1 * 10)); shift
    while ((n-- > 0)); do "$@" >/dev/null 2>&1 && return 0; sleep 0.1; done
    return 1
}

cap_cmd() { # echo the capture command line for a config
    case "$1" in
        A) echo "build/baseline_sniffer $VA" ;;
        B) echo "build/loader -d $VA build/phase3_kern.o" ;;
        C) echo "build/loader $VA build/phase3_kern.o" ;;
        D) echo "build/loader -d -p reject_all $VA build/phase6_filters.o" ;;
        E) echo "build/loader -d -p accept_all $VA build/phase6_filters.o" ;;
        *) return 1 ;;
    esac
}

stat_snapshot() { # stat_snapshot <pid> <file>: wall time, per-CPU and total counters, process counters
    {
        echo "time $(date +%s.%N)"
        grep -E '^(cpu[0-9]* |ctxt )' /proc/stat
        echo "pid_stat $(cat /proc/"$1"/stat 2>/dev/null)"
        grep -E '^(voluntary|nonvoluntary)_ctxt_switches' /proc/"$1"/status 2>/dev/null
    } > "$2"
}

lab_check() {
    ip link show "$VA" >/dev/null 2>&1 && ip netns list | grep -q "^$NS" || bash scripts/lab_up.sh > /dev/null 2>&1
    ip link show "$VA" >/dev/null 2>&1 || { echo "FATAL: lab network missing" >&2; exit 1; }
}

############################################################ one run
# one <cfg> <traffic> <size> <rep> <pps> [duration]
cmd_one() {
    need_root
    local cfg="$1" traffic="$2" size="$3" rep="$4" pps="${5:-0}" dur="${6:-$DUR}"
    # BENCH_LABEL=smoke writes logs/smoke_*.log (excluded from analysis by pre-declaration); default label: bench
    local label="${BENCH_LABEL:-bench}"
    local name="${label}_${cfg}_${traffic}_${size}_${rep}"
    OUT="logs/$name.log"
    local tmp; tmp="$(mktemp -d)"
    local payload=$((size - 42)) ports="" cap_pid="" srv_pids="" cli_pids=""
    local rate=$((pps * payload * 8))
    : > "$OUT"
    lab_check
    pkill -KILL -f "iperf3 -s -B $IPB" 2>/dev/null; pkill -KILL -f "build/(loader|baseline_sniffer)" 2>/dev/null
    rm -f /sys/fs/bpf/repl_p3   # a stale pinned Phase 3 program would make `bpftool map ... name p3_counters` ambiguous

    case "$traffic" in
        nm) ports="$NOISE_PORT" ;;
        m|warmup|cal) ports="$MATCH_PORT" ;;
        flood) ports="$MATCH_PORT $NOISE_PORT" ;;
        *) echo "FATAL: bad traffic $traffic" >&2; return 1 ;;
    esac
    [[ "$traffic" == cal ]] && ports="$NOISE_PORT"   # calibration uses non-matching traffic

    {
        echo "# bench label=$label cfg=$cfg traffic=$traffic size=$size rep=$rep pps_target=$pps dur=$dur payload=$payload"
        echo "# clk_tck=$(getconf CLK_TCK) kernel=$(uname -r) start=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "# pinning cap=$CPU_CAP srv=$CPU_SRV cli_match=$CPU_MATCH_CLI cli_noise=$CPU_NOISE_CLI"
        echo "# capture_cmd=$(cap_cmd "$cfg")"
    } >> "$OUT"

    # servers (one-shot, JSON log)
    for p in $ports; do
        ip netns exec "$NS" taskset -c "$CPU_SRV" iperf3 -s -B "$IPB" -p "$p" -J --logfile "$tmp/srv_$p.json" -1 &
        srv_pids="$srv_pids $!"
    done
    for p in $ports; do wait_for 5 ip netns exec "$NS" bash -c "ss -ltn | grep -q ':$p '" || echo "WARN: iperf3 server $p not listening" >> "$OUT"; done

    # capture process
    # shellcheck disable=SC2046
    taskset -c "$CPU_CAP" $(cap_cmd "$cfg") > "$tmp/cap.log" 2>&1 &
    cap_pid=$!
    wait_for 10 grep -q '^START' "$tmp/cap.log" || echo "WARN: capture did not print START" >> "$OUT"
    [[ "$cfg" != A ]] && {
        n=$(bpftool map show 2>/dev/null | grep -c ' p3_counters ')
        [[ "$n" == 1 ]] || echo "WARN: $n maps named p3_counters (expected 1): run is ambiguous" >> "$OUT"
        bpftool -j map dump name p3_counters > "$tmp/map_before.json" 2>&1
    }

    # instrumentation: pidstat / vmstat start 1 s before traffic and run dur+2 s
    pidstat -p "$cap_pid" 1 $((dur + 2)) > "$tmp/pidstat.log" 2>&1 &
    pidstat -w -p "$cap_pid" 1 $((dur + 2)) > "$tmp/pidstat_w.log" 2>&1 &
    vmstat 1 $((dur + 2)) > "$tmp/vmstat.log" 2>&1 &
    sleep 1
    stat_snapshot "$cap_pid" "$tmp/stat_before"

    # traffic
    local k=0
    for p in $ports; do
        local cpu="$CPU_MATCH_CLI" bw="$rate"
        [[ "$p" == "$NOISE_PORT" && "$traffic" == flood ]] && cpu="$CPU_NOISE_CLI"
        [[ "$traffic" == flood ]] && { payload=$((FLOOD_SIZE - 42)); bw=0; }
        taskset -c "$cpu" iperf3 -c "$IPB" -B "$IPA" -p "$p" -u -b "$bw" -l "$payload" -t "$dur" -J > "$tmp/cli_$p.json" 2> "$tmp/cli_$p.err" &
        cli_pids="$cli_pids $!"
        k=$((k + 1))
    done
    for c in $cli_pids; do wait "$c"; echo "client_exit $?" >> "$tmp/cli_exit"; done
    stat_snapshot "$cap_pid" "$tmp/stat_after"
    [[ "$cfg" != A ]] && bpftool -j map dump name p3_counters > "$tmp/map_after.json" 2>&1
    sleep 2   # let the last instrumentation samples land

    # stop capture (TERM; not AppArmor-confined), then collect
    kill -TERM "$cap_pid" 2>/dev/null; wait "$cap_pid" 2>/dev/null
    for s in $srv_pids; do kill -TERM "$s" 2>/dev/null; wait "$s" 2>/dev/null; done

    section capture "$tmp/cap.log"
    section pidstat "$tmp/pidstat.log"
    section pidstat_w "$tmp/pidstat_w.log"
    section vmstat "$tmp/vmstat.log"
    section stat_before "$tmp/stat_before"
    section stat_after "$tmp/stat_after"
    [[ "$cfg" != A ]] && { section map_before "$tmp/map_before.json"; section map_after "$tmp/map_after.json"; }
    section client_exit "$tmp/cli_exit"
    for p in $ports; do
        section "client_json_$p" "$tmp/cli_$p.json"
        section "client_err_$p" "$tmp/cli_$p.err"
        section "server_json_$p" "$tmp/srv_$p.json"
    done
    echo "# end=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUT"
    rm -rf "$tmp"
    fix_owner
    sleep 3
    echo "run done: $OUT"
}

############################################################ calibrate
cmd_calibrate() {
    need_root
    fix_owner
    local size pps
    for size in 64 1500; do
        for pps in "${CAL_LADDER[@]}"; do
            cmd_one A cal "$size" "$pps" "$pps" "$CAL_DUR"
        done
    done
    python3 -I scripts/summarize.py calibrate
    fix_owner
}

############################################################ run
cmd_run() {
    need_root
    fix_owner
    local plan="${1:-results/bench_plan.tsv}"
    [[ -f "$plan" ]] || { echo "FATAL: no plan; run 'bench.sh plan' first" >&2; exit 1; }
    [[ -f results/calibration.json ]] || { echo "FATAL: results/calibration.json missing; run 'bench.sh calibrate' first" >&2; exit 1; }
    local p_curve; p_curve="$(python3 -I -c 'import json;print(json.load(open("results/calibration.json"))["p_curve"])')"
    echo "curve pps = $p_curve (from results/calibration.json); plan = $plan"
    grep -v '^#' "$plan" | while IFS=$'\t' read -r seq phase cls cfg traffic size rep; do
        echo "[$seq] $phase $cls cfg=$cfg traffic=$traffic size=$size rep=$rep"
        local pps="$p_curve"; [[ "$traffic" == flood ]] && pps=0
        cmd_one "$cfg" "$traffic" "$size" "$rep" "$pps" < /dev/null
    done
    python3 -I scripts/summarize.py
    fix_owner
}

############################################################ main
case "${1:-}" in
    plan) shift; cmd_plan "$@" ;;
    topology) cmd_topology ;;
    one) shift; cmd_one "$@" ;;
    calibrate) cmd_calibrate ;;
    run) shift; cmd_run "$@" ;;
    *) sed -n '2,15p' "${BASH_SOURCE[0]}"; exit 2 ;;
esac
