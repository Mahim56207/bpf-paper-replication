#!/usr/bin/env bash
# p8_4_bench.sh - Phase 8.4 copy of scripts/p8_2_bench.sh (itself a copy of scripts/bench.sh; see logs/p8/p8_4/p8_4_bench_vs_p8_2_bench.diff) (Phase 6 harness, frozen). Changes, all listed in logs/p8/p8_2/p8_2_bench_vs_bench.diff:
#   - config N (no capture process, no eBPF capture filter; classifier tap, iperf3 servers and clients as in the other configs)
#   - PROFILE=1: perf record -e cpu-clock -F 997 -g -a -C <sender cores> during the traffic window (docs/phase8_2_design.md section 4)
#   - outputs go to logs/p8/p8_2/ (P8_OUT_DIR), perf data to build/p8_2/perf/ (untracked)
#   - the plan/topology/calibrate/run subcommands are removed (they write tracked files under results/); only `one` and `idle` remain
# Phase 8.4 change: P8_NOISE_SPEC="kind:cores:duty[:vm_mb]" starts scripts/p8_4_noise.py (stress-ng noise, duty-cycled, pinned) before the instrumentation and stops it after the closing snapshot;
# the P8_OUT_DIR default is logs/p8/p8_4.
# Design, definitions and pre-declared rules: docs/phase8_4_design.md, docs/phase6_design.md, docs/phase6_addenda.md, docs/phase8_2_design.md.
#
# Subcommands
#   one CFG TRAFFIC SIZE REP PPS [DUR]  one run -> $P8_OUT_DIR/<label>_<cfg>_<traffic>_<size>_<rep>.log   (root, generates traffic)
#                                BENCH_LABEL sets the label (default bench), PROFILE=1 adds the perf profile
#   idle [DUR]                   3 idle windows (harness attached, no traffic)   (root)
#
# Configs   A baseline_sniffer | B loader -d, port-4040 filter | C loader (no drain), port-4040 filter
#           D loader -d, reject_all | E loader -d, accept_all | N no capture process (Phase 8.2)
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

P8_OUT_DIR="${P8_OUT_DIR:-logs/p8/p8_4}"
P8_PERF_DIR="${P8_PERF_DIR:-build/p8_4/perf}"
mkdir -p "$P8_OUT_DIR" "$P8_PERF_DIR"

############################################################ helpers for runs
need_root() { [[ $EUID -eq 0 ]] || { echo "FATAL: this subcommand needs sudo" >&2; exit 1; }; }
# Files written as root must stay owned by the invoking user, so later non-root summarize runs can rewrite them.
fix_owner() { [[ -n "${SUDO_USER:-}" ]] && chown -R "$SUDO_USER": "$P8_OUT_DIR" 2>/dev/null; return 0; }   # not the perf directory: perf refuses data files owned by another user, even as root

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
        N) echo "none" ;;   # Phase 8.2: no capture process
        *) return 1 ;;
    esac
}

stat_snapshot() { # stat_snapshot <pid> <file>: wall time, per-CPU and total counters, process counters
    {
        echo "time $(date +%s.%N)"
        grep -E '^(cpu[0-9]* |ctxt )' /proc/stat
        echo "pid_stat $(cat /proc/"$1"/stat 2>/dev/null)"
        grep -E '^(voluntary|nonvoluntary)_ctxt_switches' /proc/"$1"/status 2>/dev/null
        # Phase 8.2 amendment A2 item 5 (informational; scripts/summarize.py parse_stat ignores these lines):
        # pressure stall info and, for every task with non-zero ticks, "task <pid> <comm> <utime+stime ticks> <last cpu>"
        for _f in cpu memory io; do echo "psi_$_f $(head -1 /proc/pressure/$_f)"; done
        awk '{ s=$0; i=index(s,"("); j=0; for (k=length(s); k>0; k--) if (substr(s,k,1)==")") { j=k; break }
               pid=substr(s,1,i-2); comm=substr(s,i+1,j-i-1); gsub(/ /,"_",comm); n=split(substr(s,j+2),f," ")
               if (n >= 37 && f[12]+f[13] > 0) printf "task %s %s %d %d\n", pid, comm, f[12]+f[13], f[37] }' /proc/[0-9]*/stat 2>> "${OUT%.log}.snap_err"
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
    local label="${BENCH_LABEL:-bench}" session="${BENCH_SESSION:-nosession}" attempt="${BENCH_ATTEMPT:-1}"
    local name="${label}_${cfg}_${traffic}_${size}_${rep}"
    OUT="$P8_OUT_DIR/$name.log"
    local tmp; tmp="$(mktemp -d)"
    local payload=$((size - 42)) ports="" cap_pid="" cls_pid="" srv_pids="" cli_pids=""
    local rate=$((pps * payload * 8))
    : > "$OUT"
    lab_check
    pkill -KILL -f "iperf3 -s -B $IPB" 2>/dev/null; pkill -KILL -f "build/(loader|baseline_sniffer|classifier)" 2>/dev/null; pkill -KILL -f "p8_4_noise.py|stress-ng" 2>/dev/null
    rm -f /sys/fs/bpf/repl_p3   # a stale pinned Phase 3 program would make `bpftool map ... name p3_counters` ambiguous

    case "$traffic" in
        nm) ports="$NOISE_PORT" ;;
        m|warmup|cal|env) ports="$MATCH_PORT" ;;
        flood) ports="$MATCH_PORT $NOISE_PORT" ;;
        idle) ports="" ;;   # A2: harness attached, no traffic
        *) echo "FATAL: bad traffic $traffic" >&2; return 1 ;;
    esac
    [[ "$traffic" == cal ]] && ports="$NOISE_PORT"   # calibration uses non-matching traffic

    {
        echo "# bench label=$label session=$session attempt=$attempt cfg=$cfg traffic=$traffic size=$size rep=$rep pps_target=$pps dur=$dur payload=$payload"
        echo "# clk_tck=$(getconf CLK_TCK) kernel=$(uname -r) start=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "# pinning cap=$CPU_CAP srv=$CPU_SRV cli_match=$CPU_MATCH_CLI cli_noise=$CPU_NOISE_CLI"
        echo "# capture_cmd=$(cap_cmd "$cfg") profile=${PROFILE:-0} noise=${P8_NOISE_SPEC:-none}"
    } >> "$OUT"

    # servers (one-shot, JSON log)
    for p in $ports; do
        ip netns exec "$NS" taskset -c "$CPU_SRV" iperf3 -s -B "$IPB" -p "$p" -J --logfile "$tmp/srv_$p.json" -1 &
        srv_pids="$srv_pids $!"
    done
    for p in $ports; do wait_for 5 ip netns exec "$NS" bash -c "ss -ltn | grep -q ':$p '" || echo "WARN: iperf3 server $p not listening" >> "$OUT"; done

    # classifier tap (A1): identical for every config, pinned to the free core, started before the capture process
    taskset -c "$CPU_SYS" build/classifier "$VA" > "$tmp/cls.log" 2>&1 &
    cls_pid=$!
    wait_for 10 grep -q '^START' "$tmp/cls.log" || echo "WARN: classifier did not print START" >> "$OUT"

    # capture process
    # shellcheck disable=SC2046
    if [[ "$cfg" == N ]]; then
        : > "$tmp/cap.log"; cap_pid=""; meas_pid="$cls_pid"   # config N: nothing is captured; pidstat/stat_snapshot follow the classifier
    else
        taskset -c "$CPU_CAP" $(cap_cmd "$cfg") > "$tmp/cap.log" 2>&1 &
        cap_pid=$!; meas_pid="$cap_pid"
        wait_for 10 grep -q '^START' "$tmp/cap.log" || echo "WARN: capture did not print START" >> "$OUT"
    fi
    [[ "$cfg" != A && "$cfg" != N ]] && {
        n=$(bpftool map show 2>/dev/null | grep -c ' p3_counters ')
        [[ "$n" == 1 ]] || echo "WARN: $n maps named p3_counters (expected 1): run is ambiguous" >> "$OUT"
        bpftool -j map dump name p3_counters > "$tmp/map_before.json" 2>&1
    }

    # Phase 8.4: noise (stress-ng, duty-cycled, pinned), started before the instrumentation and stopped after the closing snapshot
    noise_pid=""
    if [[ -n "${P8_NOISE_SPEC:-}" ]]; then
        IFS=: read -r nz_kind nz_cores nz_duty nz_mb <<< "$P8_NOISE_SPEC"
        taskset -c "$nz_cores" python3 -I scripts/p8_4_noise.py "$nz_kind" "$nz_cores" "$nz_duty" ${nz_mb:+--vm-mb "$nz_mb"} > "$tmp/noise.log" 2>&1 &
        noise_pid=$!
        wait_for 30 grep -q '^NOISE_READY' "$tmp/noise.log" || { echo "FATAL: noise did not become ready: $(tail -3 "$tmp/noise.log")" >> "$OUT"; echo "FATAL: noise did not become ready (see $OUT)" >&2; kill -TERM "$noise_pid" 2>/dev/null; return 1; }
        sleep 1
    fi
    # instrumentation: pidstat / vmstat start 1 s before traffic and run dur+2 s
    pidstat -p "$meas_pid" 1 $((dur + 2)) > "$tmp/pidstat.log" 2>&1 &
    pidstat -w -p "$meas_pid" 1 $((dur + 2)) > "$tmp/pidstat_w.log" 2>&1 &
    vmstat 1 $((dur + 2)) > "$tmp/vmstat.log" 2>&1 &
    sleep 1
    stat_snapshot "$meas_pid" "$tmp/stat_before"

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
    if [[ "${PROFILE:-0}" == 1 ]]; then   # Phase 8.2: start the profile when the first iperf3 client process exists (poll 20 ms)
        for _i in $(seq 1 100); do pgrep -f "iperf3 -c $IPB -B $IPA" > /dev/null && break; sleep 0.02; done
        perf_data="$P8_PERF_DIR/${name}_a${attempt}.data"; rm -f "$perf_data"
        echo "# perf_data=$perf_data perf_cmd=perf record -e cpu-clock -F 997 -g -a -C $CPU_NOISE_CLI,$CPU_MATCH_CLI -- sleep $dur (pinned to core $CPU_SYS)" >> "$OUT"
        taskset -c "$CPU_SYS" perf record -e cpu-clock -F 997 -g -a -C "$CPU_NOISE_CLI,$CPU_MATCH_CLI" -o "$perf_data" -- sleep "$dur" > "$tmp/perf_record.log" 2>&1 &
        perf_pid=$!
    fi
    for c in $cli_pids; do wait "$c"; echo "client_exit $?" >> "$tmp/cli_exit"; done
    # (A2 item 6: the wait for perf record moves behind the closing stat snapshot below, so its data flush does not lengthen the window)
    [[ "$traffic" == idle ]] && sleep "$dur"
    stat_snapshot "$meas_pid" "$tmp/stat_after"
    [[ "$cfg" != A && "$cfg" != N ]] && bpftool -j map dump name p3_counters > "$tmp/map_after.json" 2>&1
    if [[ "${PROFILE:-0}" == 1 ]]; then wait "$perf_pid"; echo "perf_exit $?" >> "$tmp/perf_record.log"; [[ -s "$perf_data" ]] || echo "FATAL: perf data $perf_data missing" >> "$OUT"; fi
    if [[ -n "$noise_pid" ]]; then kill -TERM "$noise_pid" 2>/dev/null; wait "$noise_pid" 2>/dev/null; fi
    sleep 2   # let the last instrumentation samples land

    # stop capture (TERM; not AppArmor-confined), then collect
    [[ -n "$cap_pid" ]] && { kill -TERM "$cap_pid" 2>/dev/null; wait "$cap_pid" 2>/dev/null; }
    kill -TERM "$cls_pid" 2>/dev/null; wait "$cls_pid" 2>/dev/null
    for s in $srv_pids; do kill -TERM "$s" 2>/dev/null; wait "$s" 2>/dev/null; done

    section capture "$tmp/cap.log"
    section classifier "$tmp/cls.log"
    section pidstat "$tmp/pidstat.log"
    section pidstat_w "$tmp/pidstat_w.log"
    section vmstat "$tmp/vmstat.log"
    section stat_before "$tmp/stat_before"
    section stat_after "$tmp/stat_after"
    [[ "$cfg" != A && "$cfg" != N ]] && { section map_before "$tmp/map_before.json"; section map_after "$tmp/map_after.json"; }
    [[ "${PROFILE:-0}" == 1 ]] && section perf_record "$tmp/perf_record.log"
    [[ -n "${P8_NOISE_SPEC:-}" ]] && section noise "$tmp/noise.log"
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

############################################################ idle windows (A2, M1)
# idle [dur]: 3 windows with the harness attached (config D capture process, classifier, pidstat, vmstat), no traffic
cmd_idle() {
    need_root
    local k dur="${1:-$DUR}"
    for k in 1 2 3; do cmd_one D idle 0 "$k" 0 "$dur"; done
}

############################################################ main
case "${1:-}" in
    one) shift; cmd_one "$@" ;;
    idle) shift; cmd_idle "$@" ;;
    *) sed -n '2,16p' "${BASH_SOURCE[0]}"; exit 2 ;;
esac
