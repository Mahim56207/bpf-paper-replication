#!/usr/bin/env bash
# p10_wp1.sh OUTDIR LIMIT [PLAN]: WP1 batches in the order of the plan (docs/phase10_design.md section 4). Run as root from the repo root, by p10_run_all.sh or by the smoke script.
# One log per attempt: OUTDIR/b<seq>_a<attempt>.log with the tool's CSV line (RESULT), its exit status (RC), the canary rate on cores 0,1,3,4 (the tools run on core 2) and CANARY status.
# A batch above LIMIT (CPU-s/s, the block's pre-flight limit) or an invalid batch (tool exit 3) is re-run at most twice; any other tool failure aborts the whole run.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
OUT="$1"; LIMIT="$2"; PLAN="${3:-results/p10_plan_wp1.tsv}"
CPU=2; CORES=0,1,3,4
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
[[ -f "$PLAN" ]] || { echo "FATAL: plan $PLAN missing" >&2; exit 1; }
mkdir -p "$OUT"
for t in p10_memcpy p10_testrun p10_drain; do [[ -x build/p10/$t ]] || { echo "FATAL: build/p10/$t missing (run scripts/p10_build.sh)" >&2; exit 1; }; done
bash scripts/lab_up.sh > "$OUT/lab_up.log" 2>&1 || { echo "FATAL: lab_up failed, see $OUT/lab_up.log" >&2; exit 1; }
wp1_cmd() { # wp1_cmd kind size
    case "$1" in
        memcpy)    echo "build/p10/p10_memcpy $2 20000000 $CPU" ;;
        tr_reject) echo "build/p10/p10_testrun build/phase6_filters.o reject_all $2 3000000 0 $CPU" ;;
        tr_accept) echo "build/p10/p10_testrun build/phase6_filters.o accept_all $2 3000000 1 $CPU" ;;
        tr_port)   echo "build/p10/p10_testrun build/phase3_kern.o phase3_filter $2 3000000 1 $CPU" ;;
        dr_U|dr_E|dr_B) echo "build/p10/p10_drain ${1#dr_} $2 20000 $CPU" ;;
        *) return 1 ;;
    esac
}
n=0
while IFS=$'\t' read -r seq kind size batch; do
    [[ "$seq" == \#* || -z "$seq" ]] && continue
    attempt=1
    while :; do
        f="$OUT/b${seq}_a${attempt}.log"
        cmd="$(wp1_cmd "$kind" "$size")" || { echo "FATAL: unknown kind $kind" >&2; exit 1; }
        python3 -I scripts/p10_canary.py snap "$OUT/.s0" || exit 1
        $cmd > "$OUT/.tool.out" 2> "$OUT/.tool.err"; rc=$?
        python3 -I scripts/p10_canary.py snap "$OUT/.s1" || exit 1
        read -r crate cwall < <(python3 -I scripts/p10_canary.py rate "$OUT/.s0" "$OUT/.s1" "$CORES")
        [[ -n "$crate" ]] || { echo "FATAL: canary rate could not be computed for seq $seq" >&2; exit 1; }
        status=clean; awk -v r="$crate" -v l="$LIMIT" 'BEGIN { exit !(r > l) }' && status=CONTAMINATED
        {
            echo "# wp1 seq=$seq kind=$kind size=$size batch=$batch attempt=$attempt cpu=$CPU"
            echo "# cmd=$cmd"
            echo "RESULT $(cat "$OUT/.tool.out")"
            echo "RC $rc"
            echo "STDERR $(tr '\n' ' ' < "$OUT/.tool.err")"
            echo "CANARY rate=$crate wall=$cwall limit=$LIMIT cores=$CORES status=$status"
        } > "$f"
        [[ -s "$f" ]] || { echo "FATAL: $f was not created" >&2; exit 1; }
        if [[ $rc -ne 0 && $rc -ne 3 ]]; then echo "FATAL: $cmd exited with $rc (see $f)" >&2; exit 1; fi
        if [[ $rc -eq 0 && $status == clean ]]; then break; fi
        if (( attempt >= 3 )); then echo "note: seq $seq still not clean after 2 re-runs (rc=$rc canary=$status); kept, the summary will exclude it"; break; fi
        attempt=$((attempt + 1))
    done
    n=$((n + 1))
    (( n % 25 == 0 )) && echo "[$(date +%H:%M:%S)] wp1: $n batches done"
done < "$PLAN"
rm -f "$OUT"/.s0 "$OUT"/.s1 "$OUT"/.tool.out "$OUT"/.tool.err
echo "wp1 finished: $n plan rows, $(ls "$OUT"/b*_a*.log | wc -l) attempt logs"
