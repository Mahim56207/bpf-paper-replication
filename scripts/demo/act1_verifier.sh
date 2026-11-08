#!/usr/bin/env bash
# act1_verifier.sh - demo act 1 (about 90 s): the verifier accepts the baseline filter and rejects variant A2 (map lookup without the NULL check) and the unbounded loop.
# Live: every program is loaded by the project's real loader (build/loader, libbpf bpf_object__open_file / bpf_object__load / SO_ATTACH_BPF) on the loopback interface; the lines printed
# for a rejection are lines of the captured stderr, verbatim (the whole stderr stays in build/demo/, not committed). No new kernel code and no new libbpf call: the objects are the ones
# built in Phase 3, Phase 5 and Phase 10 (src/phase3_kern.c, src/phase5_unsafe_a2.c, src/p10_loop_unbounded.c). Needs root.
# Usage: sudo bash scripts/demo/act1_verifier.sh
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
[[ $EUID -eq 0 ]] || { echo "act1: run with sudo (loading BPF programs needs root)" >&2; exit 1; }
PAUSE="${DEMO_PAUSE:-8}"; OUT=build/demo; IFACE=lo
mkdir -p "$OUT" || exit 1
for f in build/loader build/phase3_kern.o build/phase5_unsafe_a2.o build/p10/p10_loop_unbounded.o; do
    [[ -e $f ]] || { echo "act1: $f is missing; build it first (scripts/build_all.sh, scripts/p10_c5.sh); this script writes no kernel code" >&2; exit 1; }
done
fails=0
try() { # try <title> <expected ACCEPTED|REJECTED> <object> <program> <source file>
    local title=$1 want=$2 obj=$3 prog=$4 src=$5 slug got n
    slug=$(basename "$obj" .o)
    rm -f "$OUT/act1_$slug.stdout" "$OUT/act1_$slug.stderr"
    echo; echo "--- $title"; echo "    source: $src"
    echo "\$ build/loader -p $prog $IFACE $obj"
    timeout -s INT 2 build/loader -p "$prog" "$IFACE" "$obj" > "$OUT/act1_$slug.stdout" 2> "$OUT/act1_$slug.stderr"
    [[ -f "$OUT/act1_$slug.stdout" && -f "$OUT/act1_$slug.stderr" ]] || { echo "act1: output files were not created" >&2; exit 1; }
    if grep -q '^START ' "$OUT/act1_$slug.stdout"; then
        got=ACCEPTED
        head -1 "$OUT/act1_$slug.stdout" | sed 's/^/    loader: /'
    else
        got=REJECTED
        grep -E "^(R[0-9]+ invalid|invalid |infinite loop|processed [0-9]+ insns|libbpf: prog .*(BPF program load failed|failed to load)|bpf_object__load)" "$OUT/act1_$slug.stderr" | sed 's/^/    stderr: /'
        n=$(wc -l < "$OUT/act1_$slug.stderr"); echo "    (the whole captured stderr is $n lines: $OUT/act1_$slug.stderr)"
    fi
    echo "==> $got by the kernel verifier"
    [[ "$got" == "$want" ]] || { echo "act1: UNEXPECTED: expected $want"; fails=$((fails+1)); }
    sleep "$PAUSE"
}
try "1/3 baseline filter (port-4040 match, bounds-checked loads)" ACCEPTED build/phase3_kern.o phase3_filter "src/phase3_kern.c"
try "2/3 variant A2: map lookup result used without the NULL check, dynamic key" REJECTED build/phase5_unsafe_a2.o phase3_filter "src/phase5_unsafe_a2.c (Phase 5)"
try "3/3 unbounded loop: while (1) with no exit the verifier can bound" REJECTED build/p10/p10_loop_unbounded.o p10_unbounded "src/p10_loop_unbounded.c (Phase 10)"
echo; [[ $fails -eq 0 ]] && echo "act 1 done: 3 of 3 outcomes as expected" || echo "act 1: $fails unexpected outcome(s)"
exit $((fails>0))
