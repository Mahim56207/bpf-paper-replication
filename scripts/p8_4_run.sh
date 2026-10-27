#!/usr/bin/env bash
# Phase 8.4 measured launch (user, fresh Terminal tab; hands-off protocol). Usage:
#   sudo env P8_4_BATCH=C1 bash scripts/p8_4_run.sh 2>&1 | tee logs/p8/p8_4/C1/p8_4_C1_console.log        (C1 C2 C3 F1 F2 F3 X1)
# Steps: refuse if the batch's output folders are not empty -> design and plan hash checks -> memory gate (swap <= 2000 MB, MemAvailable >= 1500 MB)
# -> 60 s settle -> pre-flight (3 x 10 s idle windows, V8 limit 0.0826 on {0,1}) -> every row of the plan, each with its noise spec; NO window is
# repeated or dropped because of V8 (design section 4) -> FINISHED. Outputs: logs/p8/p8_4/<batch>/{preflight,runs}/.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
B="${P8_4_BATCH:?set P8_4_BATCH to C1 C2 C3 F1 F2 F3 or X1}"
case "$B" in C1|C2|C3|F1|F2|F3|X1) ;; *) echo "FATAL: bad batch $B" >&2; exit 1 ;; esac
L=logs/p8/p8_4/$B; PLAN=results/p8_4_plan_$B.tsv
die() { echo "ABORT: $*" >&2; echo "=== ABORTED $(date +%T) ===" >&2; free -m >&2; exit 3; }

for d in runs preflight; do [[ -z "$(ls -A "$L/$d" 2>/dev/null)" ]] || die "$L/$d is not empty: refusing to overwrite an existing launch (move it away on purpose)"; done
want=$(grep -E '^[0-9a-f]{64}  docs/phase8_4_design.md' logs/p8/p8_4/p8_4_design_sha256.log | tail -1 | cut -d' ' -f1)
[[ -n "$want" && "$want" == "$(sha256sum docs/phase8_4_design.md | cut -d' ' -f1)" ]] || die "design sha256 differs from the last logged value: amend and log it first"
wantp=$(grep -E "^[0-9a-f]{64}  $PLAN" logs/p8/p8_4/p8_4_plan_sha256.log | tail -1 | cut -d' ' -f1)
[[ -n "$wantp" && "$wantp" == "$(sha256sum "$PLAN" | cut -d' ' -f1)" ]] || die "plan sha256 mismatch for $PLAN"
for b in build/classifier build/baseline_sniffer build/loader build/phase3_kern.o build/phase6_filters.o; do [[ -e $b ]] || die "missing $b"; done
command -v stress-ng > /dev/null || die "stress-ng not found"

swap_mb=$(awk '/^SwapTotal:/{t=$2} /^SwapFree:/{f=$2} END{printf "%d", (t-f)/1024}' /proc/meminfo)
avail_mb=$(awk '/^MemAvailable:/{printf "%d", $2/1024}' /proc/meminfo)
echo "memory gate: swap in use ${swap_mb} MB (limit 2000), MemAvailable ${avail_mb} MB (minimum 1500)"
(( swap_mb <= 2000 )) || die "memory gate: swap in use ${swap_mb} MB > 2000 MB"
(( avail_mb >= 1500 )) || die "memory gate: MemAvailable ${avail_mb} MB < 1500 MB"
echo "memory gate passed"
mkdir -p "$L/runs" "$L/preflight"
{ echo "# p8_4_run batch=$B start=$(date -Is) design_sha=$want plan_sha=$wantp"; uname -srm; cat /proc/loadavg; free -m; for f in cpu memory io; do echo "psi_$f $(head -1 /proc/pressure/$f)"; done; } 2>&1 | tee "$L/run_context.txt"
rows=$(grep -vc '^#' "$PLAN")
echo "=== DO NOT TOUCH THE MACHINE until the line FINISHED appears. Settle 60 s, pre-flight 3 x 10 s, then $rows windows. ==="
sleep 60

for k in 1 2 3; do
    BENCH_LABEL=p84pre P8_OUT_DIR="$L/preflight" BENCH_SESSION="p84_pre_$$" bash scripts/p8_4_bench.sh one D idle 0 "$k" 0 10 < /dev/null \
        > "$L/preflight/run_$k.out" 2>&1 || die "pre-flight window $k failed (see $L/preflight/run_$k.out)"
    [[ -s "$L/preflight/p84pre_D_idle_0_$k.log" ]] || die "pre-flight window $k log missing"
done
P8_4_L="$L" python3 -I - <<'PY' || die "pre-flight failed the V8 limit; wait for the machine to settle and launch again"
import glob, importlib.util, json, os, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("summ", "scripts/summarize.py"); summ = importlib.util.module_from_spec(spec); spec.loader.exec_module(summ)
base = json.load(open("results/baseline_calibration.json"))
lim = summ.CANARY_FACTOR * base["canary_max"]["01"]
files = sorted(glob.glob(os.environ["P8_4_L"] + "/preflight/p84pre_D_idle_0_[123].log"))
if len(files) != 3: sys.exit("FATAL: expected 3 pre-flight logs")
bad = 0
for f in files:
    r = summ.parse_run(f); w, pc = r["window_s"], r["busy_sec_per_cpu"]
    can = (pc["cpu0"] + pc["cpu1"]) / w; bad += can > lim
    print("  %s idle %.4f, canary {0,1} %.4f (limit %.4f) -> %s" % (f.split("/")[-1], r["busy_sec_total"] / w, can, lim, "PASS" if can <= lim else "FAIL"))
sys.exit(1 if bad else 0)
PY
echo "=== pre-flight passed; starting the plan $(date +%T) ==="

export BENCH_SESSION="p84_${B}_$(date +%s)"
n=0
while IFS=$'\t' read -r seq exp label cfg traffic size rep pps spec; do
    [[ "$seq" =~ ^# ]] && continue
    n=$((n + 1))
    echo "[$seq/$rows] $exp $label cfg=$cfg $traffic rep=$rep noise=$spec $(date +%T)"
    P8_NOISE_SPEC="$spec" BENCH_LABEL="$label" P8_OUT_DIR="$L/runs" bash scripts/p8_4_bench.sh one "$cfg" "$traffic" "$size" "$rep" "$pps" 10 < /dev/null || die "window $label rep $rep failed"
    [[ -s "$L/runs/${label}_${cfg}_${traffic}_${size}_${rep}.log" ]] || die "log of $label rep $rep missing"
done < "$PLAN"
[[ $n -eq $rows ]] || die "ran $n of $rows rows"
{ echo "# at the end:"; free -m; for f in cpu memory io; do echo "psi_$f $(head -1 /proc/pressure/$f)"; done; echo "# end=$(date -Is)"; } 2>&1 | tee -a "$L/run_context.txt"
chown -R "${SUDO_USER:-root}": "$L" 2>/dev/null
echo "windows: $(ls "$L"/runs/*.log | wc -l) logs"
echo "=== FINISHED $(date +%T) ==="
