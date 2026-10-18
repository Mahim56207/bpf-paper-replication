#!/usr/bin/env bash
# Phase 4 negative runs (reviewer request): the loader's error paths must exit non-zero with a
# clean message, never hang or crash. `timeout` turns a hang into exit 124.
# Usage: sudo bash scripts/p4_negatives.sh 2>&1 | tee logs/p4_negatives.log
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
U="${SUDO_USER:-mahim}"

echo "### 1. sudo ./build/loader nosuchif0   (running as root)"
timeout 15 ./build/loader nosuchif0
echo "exit=$?"

echo
echo "### 2. ./build/loader p1veth0   (NO sudo: run as user $U via runuser; uid=$(id -u "$U"))"
timeout 15 runuser -u "$U" -- ./build/loader p1veth0
echo "exit=$?"

echo
echo "### 3. extra: sudo ./build/loader p1veth0 /no/such/object.o   (object open failure, as root)"
timeout 15 ./build/loader p1veth0 /no/such/object.o
echo "exit=$?"

echo
echo "### 4. extra: sudo ./build/loader   (usage)"
timeout 15 ./build/loader
echo "exit=$?"
