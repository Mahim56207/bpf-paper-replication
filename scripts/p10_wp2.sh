#!/usr/bin/env bash
# p10_wp2.sh a|b OUTDIR: WP2 block (docs/phase10_design.md section 5). Run as root from the repo root, by p10_run_all.sh or by the smoke script.
#   a: mitigation test, flood (PPS 0), topologies T0 and T1, plan results/p10_plan_wp2a.tsv; calibration windows (amendment A2): P10_CALIB_N (default 3) per (topology, config) cell, 24 windows
#   b: paced ladder, topology T1, plan results/p10_plan_wp2b.tsv; calibration windows (amendment A2): P10_CALIB_N (default 3) per config at 600000 pps, 9 windows
# The idle windows (harness attached) come first, then the calibration windows (excluded), then the plan; a run above the canary limit of rule P7 is moved to
# OUTDIR/attempts/ and repeated at most twice. P10_PLAN overrides the plan file and P10_CALIB_N the number of calibration windows per set (smoke runs only; the design says 3).
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
BLOCK="$1"; OUT="$2"
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
[[ "$BLOCK" == a || "$BLOCK" == b ]] || { echo "FATAL: block must be a or b" >&2; exit 1; }
PLAN="${P10_PLAN:-results/p10_plan_wp2$BLOCK.tsv}"
[[ -f "$PLAN" ]] || { echo "FATAL: plan $PLAN missing" >&2; exit 1; }
mkdir -p "$OUT/attempts"
export P10_OUT_DIR="$OUT" BENCH_SESSION="p10${BLOCK}_$(date +%s)"
log() { echo "[$(date +%H:%M:%S)] $*"; }
one() { # one TOPO LABEL CFG PPS REP [ATTEMPT]
    P10_TOPO="$1" BENCH_LABEL="$2" BENCH_ATTEMPT="${6:-1}" bash scripts/p10_bench.sh one "$3" flood 256 "$5" "$4" 10 || { echo "FATAL: p10_bench.sh failed for $*" >&2; exit 1; }
}
log "idle windows with the harness attached (config D)"
P10_OUT_DIR="$OUT" bash scripts/p10_bench.sh idle 10 || { echo "FATAL: harness idle windows failed" >&2; exit 1; }
log "calibration windows for the flood canary limit (rule P7), excluded from analysis"
if [[ "$BLOCK" == a ]]; then
    for k in $(seq 1 "${P10_CALIB_N:-3}"); do for t in T0 T1; do for c in N A B C; do one "$t" "calib$t" "$c" 0 "$k"; done; done; done
else
    for k in $(seq 1 "${P10_CALIB_N:-3}"); do for c in A B C; do one T1 calibL "$c" 600000 "$k"; done; done
fi
python3 -I scripts/p10_wp2_tools.py calib "$OUT" || { echo "FATAL: calibration of the canary limit failed" >&2; exit 1; }
[[ -s "$OUT/calib_v8.json" ]] || { echo "FATAL: $OUT/calib_v8.json was not created" >&2; exit 1; }
n=0
while IFS=$'\t' read -r seq a b c d; do
    [[ "$seq" == \#* || -z "$seq" ]] && continue
    if [[ "$BLOCK" == a ]]; then topo="$a"; cfg="$b"; rep="$c"; pps=0; label="p10a$topo"
    else topo=T1; cfg="$a"; pps="$b"; rep="$c"; label="lad$pps"; fi
    attempt=1; name="${label}_${cfg}_flood_256_${rep}"
    while :; do
        one "$topo" "$label" "$cfg" "$pps" "$rep" "$attempt"
        [[ -s "$OUT/$name.log" ]] || { echo "FATAL: $OUT/$name.log was not created" >&2; exit 1; }
        python3 -I scripts/p10_wp2_tools.py v8 "$OUT/$name.log" "$OUT/calib_v8.json" > "$OUT/.v8_rate" 2>&1; rc=$?
        [[ $rc -eq 0 ]] && break
        [[ $rc -ne 1 ]] && { echo "FATAL: V8 check failed to run (rc $rc): $(cat "$OUT/.v8_rate")" >&2; exit 1; }
        if (( attempt >= 3 )); then log "V8: $name still contaminated after 2 re-runs (kept; the summary excludes it)"; break; fi
        log "V8: attempt $attempt of $name contaminated (canary $(cat "$OUT/.v8_rate")); re-running"
        mv "$OUT/$name.log" "$OUT/attempts/${name}_a${attempt}.log"
        attempt=$((attempt + 1))
    done
    n=$((n + 1)); log "wp2$BLOCK: row $seq done ($n)"
done < "$PLAN"
rm -f "$OUT/.v8_rate"
echo "wp2$BLOCK finished: $n plan rows"
