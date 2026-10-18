#!/usr/bin/env bash
# Phase 1 setup: install the eBPF toolchain, persist bpf_jit_enable=1, load veth.
# Usage: sudo bash scripts/phase1_setup.sh 2>&1 | tee logs/phase1_setup.log
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "FATAL: run as root: sudo bash $0" >&2
    exit 1
fi

KVER="$(uname -r)"
export DEBIAN_FRONTEND=noninteractive

echo "== kernel: $KVER"
echo "== apt-get update"
apt-get update

echo "== install toolchain"
apt-get install -y \
    build-essential clang llvm libelf-dev zlib1g-dev pkg-config libbpf-dev \
    "linux-headers-$KVER" iperf3 tcpdump ethtool linux-tools-common

echo "== bpftool"
if command -v bpftool >/dev/null 2>&1; then
    echo "bpftool already on PATH: $(command -v bpftool)"
else
    # Fallbacks, in order: standalone package, then kernel-matched tools, then generic tools.
    apt-get install -y bpftool \
        || apt-get install -y "linux-tools-$KVER" \
        || apt-get install -y linux-tools-generic
fi
command -v bpftool >/dev/null 2>&1 || { echo "FATAL: bpftool still missing after fallbacks" >&2; exit 1; }

echo "== persist net.core.bpf_jit_enable=1"
echo "net.core.bpf_jit_enable = 1" > /etc/sysctl.d/99-bpf-repl.conf
sysctl -w net.core.bpf_jit_enable=1
sysctl -p /etc/sysctl.d/99-bpf-repl.conf

echo "== modprobe veth"
modprobe veth
lsmod | grep '^veth' || { echo "FATAL: veth not loaded" >&2; exit 1; }

echo "== setup done"
