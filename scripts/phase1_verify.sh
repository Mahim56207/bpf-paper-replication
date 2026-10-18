#!/usr/bin/env bash
# Phase 1 verify: every check prints PASS or FAIL with the real observed value.
# Needs root for the bpf() load test and the veth test.
# Usage: sudo bash scripts/phase1_verify.sh 2>&1 | tee logs/phase1_verify.log
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="$ROOT/build"
mkdir -p "$BUILD"
FAILS=0

pass() { echo "PASS  $1: $2"; }
fail() { echo "FAIL  $1: $2"; FAILS=$((FAILS + 1)); }

# check <name> <command...>: PASS with the command's first output line, FAIL with its error output.
check() {
    local name="$1"; shift
    local out
    if out="$("$@" 2>&1)"; then pass "$name" "$(printf '%s' "$out" | head -1)"
    else fail "$name" "$(printf '%s' "$out" | head -3 | tr '\n' ' ')"; fi
}

echo "== phase1_verify $(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [[ $EUID -ne 0 ]]; then fail "root" "not root; run with sudo"; fi

check kernel          uname -r
check clang           bash -c 'clang --version | head -1'
check llc             bash -c 'llc --version | grep -m1 "LLVM version"'
check llvm-objdump    bash -c 'llvm-objdump --version | grep -m1 "LLVM version"'
check bpftool         bash -c 'bpftool version | head -1'
check pkg-config      pkg-config --version
check libbpf-pc       pkg-config --modversion libbpf
check libelf-pc       pkg-config --modversion libelf
check zlib-pc         pkg-config --modversion zlib
check gcc             bash -c 'gcc --version | head -1'
check make            bash -c 'make --version | head -1'
check iperf3          bash -c 'iperf3 --version | head -1'
check tcpdump         bash -c 'tcpdump --version 2>&1 | head -1'
check ethtool         bash -c 'ethtool --version'

# Headers named in CLAUDE.md API DISCIPLINE must exist.
for h in /usr/include/bpf/libbpf.h /usr/include/bpf/bpf_helpers.h /usr/include/linux/bpf.h; do
    check "header:$h" ls -l "$h"
done
# Header-declared libbpf version (read-only grep) vs the pkg-config version above.
check libbpf-header-version bash -c \
    'echo "MAJOR=$(grep -m1 "define LIBBPF_MAJOR_VERSION" /usr/include/bpf/libbpf_version.h | awk "{print \$3}") MINOR=$(grep -m1 "define LIBBPF_MINOR_VERSION" /usr/include/bpf/libbpf_version.h | awk "{print \$3}")"'
check kernel-headers  ls -d "/lib/modules/$(uname -r)/build"
check btf-vmlinux     ls -l /sys/kernel/btf/vmlinux

# JIT: live value and persistence.
jit="$(cat /proc/sys/net/core/bpf_jit_enable 2>&1)"
if [[ "$jit" == "1" ]]; then pass bpf_jit_enable "live=$jit"; else fail bpf_jit_enable "live=$jit (want 1)"; fi
if grep -qs '^net.core.bpf_jit_enable *= *1' /etc/sysctl.d/99-bpf-repl.conf; then
    pass bpf_jit_persist "$(cat /etc/sysctl.d/99-bpf-repl.conf)"
else fail bpf_jit_persist "/etc/sysctl.d/99-bpf-repl.conf missing or wrong"; fi

# vmlinux.h via bpftool (CLAUDE.md allows this instead of hand-written kernel structs).
check vmlinux.h bash -c "bpftool btf dump file /sys/kernel/btf/vmlinux format c > '$BUILD/vmlinux.h' && wc -l '$BUILD/vmlinux.h'"

# Compile a trivial BPF object. No includes, no helpers: it exercises clang's bpf backend only.
cat > "$BUILD/phase1_test.c" <<'EOF'
__attribute__((section("xdp"), used)) int phase1_test(void *ctx) { return 2; }
char _license[] __attribute__((section("license"), used)) = "GPL";
EOF
check bpf-compile     bash -c "clang -O2 -target bpf -c '$BUILD/phase1_test.c' -o '$BUILD/phase1_test.o' && ls -l '$BUILD/phase1_test.o'"

# Real kernel load through the verifier, then unpin.
if [[ $EUID -eq 0 ]]; then
    mountpoint -q /sys/fs/bpf || mount -t bpf bpf /sys/fs/bpf
    rm -f /sys/fs/bpf/phase1_test
    check bpf-load      bash -c "bpftool prog load '$BUILD/phase1_test.o' /sys/fs/bpf/phase1_test && echo loaded"
    check bpf-loaded-jit bash -c "bpftool prog show pinned /sys/fs/bpf/phase1_test | head -1"
    rm -f /sys/fs/bpf/phase1_test

    # veth: module loaded and a pair can be created and removed.
    check veth-module   bash -c "lsmod | grep -m1 '^veth'"
    ip link del p1veth0 2>/dev/null
    check veth-pair     bash -c "ip link add p1veth0 type veth peer name p1veth1 && ip -br link show p1veth0 && ip link del p1veth0"
fi

echo "== result: $FAILS FAIL"
[[ $FAILS -eq 0 ]] && echo "PHASE1 VERIFY: PASS" || echo "PHASE1 VERIFY: FAIL"
exit $((FAILS > 0))
