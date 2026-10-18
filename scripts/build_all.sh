#!/usr/bin/env bash
# Build every artifact from source into build/ (build/ is not committed). Run from the repo root.
# Needs the Phase 1 toolchain (sudo bash scripts/phase1_setup.sh) and build/vmlinux.h (generated below if missing).
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p build
if [[ ! -f build/vmlinux.h ]]; then
    bpftool btf dump file /sys/kernel/btf/vmlinux format c > build/vmlinux.h
fi
BPF="clang -O2 -g -target bpf -D__TARGET_ARCH_arm64 -I$PWD/build"   # arm64; use -D__TARGET_ARCH_x86 on x86 (not tested)
for f in phase3_kern phase6_filters phase6_classify; do $BPF -c src/$f.c -o build/$f.o; done
gcc -O2 -Wall -Wextra -Werror src/baseline_sniffer.c -o build/baseline_sniffer
for f in loader classifier; do gcc -O2 -Wall -Wextra -Werror src/$f.c -o build/$f -lbpf -lelf -lz; done
ls -l build/*.o build/baseline_sniffer build/loader build/classifier
