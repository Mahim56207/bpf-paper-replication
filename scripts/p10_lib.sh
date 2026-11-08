#!/usr/bin/env bash
# p10_lib.sh - common functions of the Phase 10 run scripts (sourced, never run). docs/phase10_design.md section 8.
# p10_preflight BLOCK CORES OUTDIR : memory gate, 60 s settle, 3 idle windows of 10 s on the canary cores (from /proc/stat), verdict against the idle limit,
#                                    OUTDIR/preflight.json with the block's canary limit; returns non-zero (and the caller must abort) on any failure.
P10_SETTLE="${P10_SETTLE:-60}"
p10_log() { echo "[$(date +%H:%M:%S)] $*"; }
p10_preflight() {
    local block="$1" cores="$2" out="$3" k r rates=() s0 s1
    mkdir -p "$out"
    s0="$out/.pre_before"; s1="$out/.pre_after"
    p10_log "pre-flight $block: memory before (free -m)"; free -m | tee "$out/free_before.txt"
    python3 -I scripts/p10_canary.py gate > "$out/gate_before.txt"; local grc=$?
    cat "$out/gate_before.txt"
    [[ $grc -eq 0 ]] || { p10_log "FATAL: memory gate failed before $block"; return 1; }
    p10_log "settle ${P10_SETTLE} s (do not touch the machine)"; sleep "$P10_SETTLE"
    for k in 1 2 3; do
        python3 -I scripts/p10_canary.py snap "$s0" || return 1
        sleep 10
        python3 -I scripts/p10_canary.py snap "$s1" || return 1
        r=$(python3 -I scripts/p10_canary.py rate "$s0" "$s1" "$cores" | cut -d' ' -f1) || return 1
        rates+=("$r"); p10_log "pre-flight $block idle window $k: canary rate $r CPU-s/s on cores $cores"
    done
    python3 -I scripts/p10_canary.py pre "$out" "$block" "$cores" "${rates[@]}" || { p10_log "FATAL: pre-flight idle set of $block failed the idle limit (V8); aborting before any measured run"; return 1; }
    [[ -s "$out/preflight.json" ]] || { p10_log "FATAL: $out/preflight.json was not created"; return 1; }
    return 0
}
p10_block_end() { # p10_block_end BLOCK OUTDIR : memory after the block
    local out="$2"; free -m > "$out/free_after.txt"
    python3 -I scripts/p10_canary.py gate > "$out/gate_after.txt"; local grc=$?
    cat "$out/gate_after.txt"; [[ $grc -eq 0 ]] || p10_log "WARN: memory gate failed after $1 (the block ran; check $out/gate_after.txt)"
}
