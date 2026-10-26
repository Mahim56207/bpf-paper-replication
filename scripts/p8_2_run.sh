#!/usr/bin/env bash
# Phase 8.2 measured run (launched by the user from a Terminal tab; hands-off protocol). Usage:
#   sudo bash scripts/p8_2_run.sh 2>&1 | tee logs/p8/p8_2/p8_2_run_console.log                      (run set 1)
#   sudo env P8_2_RUN=run2 bash scripts/p8_2_run.sh 2>&1 | tee logs/p8/p8_2/run2/p8_2_run2_console.log   (run set 2, amendment A2: adds the memory gate)
# Steps: check design and plan hashes -> 60 s settle -> pre-flight (3 x 10 s idle windows, V8 limit on cores {0,1}, memory/swap recorded;
# aborts loudly on failure) -> the 40 rows of results/p8_2_plan.tsv (unprofiled rows: V8 re-runs, max 2 per cell; profiled rows: PROFILE=1,
# exempt from V8) -> perf post-processing (counts per profile) -> FINISHED. Outputs (deleted first): logs/p8/p8_2/{preflight,runs,attempts,profiles}/.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
RUN="${P8_2_RUN:-}"
if [[ -z "$RUN" ]]; then L=logs/p8/p8_2; PD=build/p8_2/perf; PLAN=results/p8_2_plan.tsv; PLANLOG=logs/p8/p8_2/p8_2_plan_sha256.log
else L=logs/p8/p8_2/$RUN; PD=build/p8_2/perf_$RUN; PLAN=results/p8_2_plan_$RUN.tsv; PLANLOG=logs/p8/p8_2/p8_2_plan_${RUN}_sha256.log; fi
DL=logs/p8/p8_2/p8_2_design_sha256.log
die() { echo "ABORT: $*" >&2; echo "=== ABORTED $(date +%T) ===" >&2; free -m >&2; exit 3; }

# --- integrity of the pre-declared files
want_design=$(tail -n +1 "$DL" | grep -E '^[0-9a-f]{64}  docs/phase8_2_design.md' | tail -1 | cut -d' ' -f1)
have_design=$(sha256sum docs/phase8_2_design.md | cut -d' ' -f1)
[[ -n "$want_design" && "$want_design" == "$have_design" ]] || die "design sha256 mismatch (logged $want_design, file $have_design): amend and log it first"
want_plan=$(grep -E "^[0-9a-f]{64}  $PLAN" "$PLANLOG" | tail -1 | cut -d' ' -f1)
have_plan=$(sha256sum "$PLAN" | cut -d' ' -f1)
[[ -n "$want_plan" && "$want_plan" == "$have_plan" ]] || die "plan sha256 mismatch"
for b in build/classifier build/baseline_sniffer build/loader build/phase3_kern.o build/phase6_filters.o; do [[ -e $b ]] || die "missing $b"; done
command -v perf > /dev/null || die "perf not found"

# --- memory gate (amendment A2 item 3; run set 2 only): swap in use <= 2000 MB and MemAvailable >= 1500 MB, else abort before anything starts
if [[ -n "$RUN" ]]; then
    swap_mb=$(awk '/^SwapTotal:/{t=$2} /^SwapFree:/{f=$2} END{printf "%d", (t-f)/1024}' /proc/meminfo)
    avail_mb=$(awk '/^MemAvailable:/{printf "%d", $2/1024}' /proc/meminfo)
    echo "memory gate: swap in use ${swap_mb} MB (limit 2000), MemAvailable ${avail_mb} MB (minimum 1500)"
    (( swap_mb <= 2000 )) || die "memory gate: swap in use ${swap_mb} MB > 2000 MB (close applications and reboot or swapoff/swapon as agreed in amendment A2 item 4, then launch again)"
    (( avail_mb >= 1500 )) || die "memory gate: MemAvailable ${avail_mb} MB < 1500 MB"
    echo "memory gate passed"
fi

# --- never overwrite an existing run set (incident 2026-10-26: the run set 1 command was launched by mistake and deleted run set 1's raw logs)
for d in runs profiles attempts preflight; do
    [[ -z "$(ls -A "$L/$d" 2>/dev/null)" ]] || die "$L/$d is not empty: this run set already has output; refusing to delete it (use P8_2_RUN=run2 for the repeat, or move the old output away on purpose)"
done

# --- outputs: deleted first
rm -rf "$L/preflight" "$L/runs" "$L/attempts" "$L/profiles" "$PD"
mkdir -p "$L/preflight" "$L/runs" "$L/attempts" "$L/profiles" "$PD"
{ echo "# p8_2_run start=$(date -Is) run=${RUN:-run1} design_sha=$have_design plan_sha=$have_plan"; uname -srm; cat /proc/loadavg; echo "# free -m before settle:"; free -m
  for f in cpu memory io; do echo "psi_$f $(head -1 /proc/pressure/$f)"; done; } 2>&1 | tee "$L/run_context.txt"
echo "=== DO NOT TOUCH THE MACHINE until the line FINISHED appears. Settle 60 s, pre-flight 3 x 10 s, then 40 runs (about 20 minutes). ==="
sleep 60

# --- pre-flight (V8 limit for idle windows: 1.2 x canary_max{0,1})
for k in 1 2 3; do
    BENCH_LABEL=p82pre P8_OUT_DIR="$L/preflight" BENCH_SESSION="p82_pre_$$" bash scripts/p8_2_bench.sh one D idle 0 "$k" 0 10 < /dev/null \
        > "$L/preflight/run_$k.out" 2>&1 || die "pre-flight window $k failed (see $L/preflight/run_$k.out)"
    [[ -s "$L/preflight/p82pre_D_idle_0_$k.log" ]] || die "pre-flight window $k log missing"
done
{ echo "# free -m after pre-flight:"; free -m; for f in cpu memory io; do echo "psi_$f $(head -1 /proc/pressure/$f)"; done; } 2>&1 | tee -a "$L/run_context.txt"
P8_2_L="$L" python3 -I - <<'PY' || die "pre-flight failed the V8 limit (see the table above); wait for the machine to settle and launch again"
import importlib.util, json, sys, glob
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("summ", "scripts/summarize.py"); summ = importlib.util.module_from_spec(spec); spec.loader.exec_module(summ)
base = json.load(open("results/baseline_calibration.json"))
lim = summ.CANARY_FACTOR * base["canary_max"]["01"]
bad = 0
print("pre-flight idle windows (limit on cores {0,1}: %.4f CPU-s/s; quiet calibration idle rate %.3f)" % (lim, base["idle_rate_mean"]))
import os
files = sorted(glob.glob(os.environ["P8_2_L"] + "/preflight/p82pre_D_idle_0_[123].log"))
if len(files) != 3:
    sys.exit("FATAL: expected 3 pre-flight logs, found %d" % len(files))
for f in files:
    r = summ.parse_run(f)
    w, pc = r["window_s"], r["busy_sec_per_cpu"]
    can = (pc["cpu0"] + pc["cpu1"]) / w
    ok = can <= lim
    bad += not ok
    print("  %s idle %.4f CPU-s/s, canary {0,1} %.4f -> %s" % (f.split("/")[-1], r["busy_sec_total"] / w, can, "PASS" if ok else "FAIL"))
sys.exit(1 if bad else 0)
PY
echo "=== pre-flight passed; starting the plan $(date +%T) ==="

# --- the plan
export BENCH_SESSION="p82_run_$(date +%s)"
n=0
while IFS=$'\t' read -r seq prof cfg rep; do
    [[ "$seq" =~ ^# ]] && continue
    n=$((n + 1))
    if [[ "$prof" == 1 ]]; then label=p82prof; else label=p82; fi
    name="${label}_${cfg}_flood_256_${rep}"
    attempt=1
    while :; do
        echo "[$seq] profile=$prof cfg=$cfg rep=$rep attempt=$attempt $(date +%T)"
        PROFILE="$prof" BENCH_LABEL="$label" BENCH_ATTEMPT="$attempt" P8_OUT_DIR="$L/runs" P8_PERF_DIR="$PD" \
            bash scripts/p8_2_bench.sh one "$cfg" flood 256 "$rep" 0 10 < /dev/null || die "run $name failed"
        [[ -s "$L/runs/$name.log" ]] || die "run log $L/runs/$name.log missing"
        [[ "$prof" == 1 ]] && break                      # profiled runs: exempt from V8, one attempt
        python3 -I scripts/summarize.py canary "$L/runs/$name.log"; rc=$?
        [[ $rc -ne 1 ]] && break                          # 0 clean, 2 not evaluable: keep
        if (( attempt >= 3 )); then echo "V8: cell $name still contaminated after 2 re-runs (kept; excluded by the summary)"; break; fi
        mv "$L/runs/$name.log" "$L/attempts/${name}_a${attempt}.log"
        echo "V8: attempt $attempt of $name contaminated; re-running"
        attempt=$((attempt + 1))
    done
done < "$PLAN"
[[ $n -eq 40 ]] || die "plan had $n rows, expected 40"

# --- profiles
echo "=== post-processing the profiles $(date +%T) ==="
shopt -s nullglob
np=0
for f in "$PD"/*.data; do
    b=$(basename "$f" .data)
    python3 -I scripts/p8_2_perf_counts.py "$f" "$L/profiles/$b.json" || die "perf counts failed for $f"
    sha256sum "$f" >> "$L/profiles/perf_data_sha256.log"
    np=$((np + 1))
done
[[ $np -ge 16 ]] || die "expected at least 16 perf files, found $np"
{ echo "# free -m at the end:"; free -m; for f in cpu memory io; do echo "psi_$f $(head -1 /proc/pressure/$f)"; done; echo "# end=$(date -Is)"; } 2>&1 | tee -a "$L/run_context.txt"
chown -R "${SUDO_USER:-root}": "$L" build/p8_2 2>/dev/null
echo "runs: $(ls "$L"/runs/*.log | wc -l) final logs, $(ls "$L"/attempts 2>/dev/null | wc -l) earlier attempts, $np profiles"
echo "=== FINISHED $(date +%T) ==="
