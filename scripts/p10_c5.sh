#!/usr/bin/env bash
# p10_c5.sh OUTDIR - Phase 10 WP4 (docs/phase10_design.md section 7): load an unbounded-loop and a bounded-loop socket filter with `bpftool -d prog load`
# and keep the verifier's stderr and exit status verbatim. Run as root from the repo root. Refuses to start if OUTDIR is not empty.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
OUT="${1:-logs/p10/wp4}"
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
mkdir -p "$OUT"
[[ -z "$(ls -A "$OUT")" ]] || { echo "ABORT: $OUT is not empty; refusing to overwrite (move it away on purpose)" >&2; exit 1; }
[[ -f build/vmlinux.h ]] || { echo "FATAL: build/vmlinux.h missing" >&2; exit 1; }
mkdir -p build/p10
{ echo "\$ uname -srm"; uname -srm; echo "\$ clang --version"; clang --version; echo "\$ bpftool version"; bpftool version; } > "$OUT/env.txt" 2>&1
bpftool feature probe kernel > "$OUT/features.txt" 2> "$OUT/features.err"; echo "bpftool feature probe kernel exit $?" >> "$OUT/env.txt"
grep -i "loop" "$OUT/features.txt" > "$OUT/features_loop.txt" 2>&1; echo "(loop-related lines of the feature probe: $(wc -l < "$OUT/features_loop.txt"))" >> "$OUT/env.txt"
for p in unbounded bounded; do
    obj="build/p10/p10_loop_$p.o"; pin="/sys/fs/bpf/p10_loop_$p"
    rm -f "$obj" "$pin"
    clang -O2 -g -target bpf -D__TARGET_ARCH_arm64 -I"$PWD/build" -c "src/p10/p10_loop_$p.c" -o "$obj" > "$OUT/${p}_clang.txt" 2>&1 || { echo "FATAL: clang failed for $p, see $OUT/${p}_clang.txt" >&2; exit 1; }
    [[ -s "$obj" ]] || { echo "FATAL: $obj was not created" >&2; exit 1; }
    bpftool -d prog load "$obj" "$pin" type socket > "$OUT/${p}_stdout.txt" 2> "$OUT/${p}_stderr.txt"
    rc=$?
    echo "$rc" > "$OUT/${p}_exit.txt"
    if [[ -e "$pin" ]]; then echo loaded > "$OUT/${p}_status.txt"; bpftool prog show pinned "$pin" > "$OUT/${p}_show.txt" 2>&1; rm -f "$pin"; else echo rejected > "$OUT/${p}_status.txt"; fi
    echo "$p: bpftool exit $rc, $(cat "$OUT/${p}_status.txt")"
    [[ -s "$OUT/${p}_exit.txt" && -s "$OUT/${p}_status.txt" ]] || { echo "FATAL: outputs of $p were not created" >&2; exit 1; }
done
chown -R "${SUDO_USER:-root}": "$OUT" 2>> "$OUT/chown.txt"
echo "p10_c5 finished"
