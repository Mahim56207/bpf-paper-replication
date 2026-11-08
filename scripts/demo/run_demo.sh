#!/usr/bin/env bash
# run_demo.sh - the 5-minute live demo: act 1 (verifier), act 2 (sender limit), act 3 (C1 instruction counts). Live commands only; nothing is pre-written output.
# Needs root for acts 1 and 2; act 3 (scripts/demo_c1.sh, unchanged) runs as the invoking user. Pauses: DEMO_PAUSE seconds between steps (default 8).
# Usage: sudo bash scripts/demo/run_demo.sh
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
[[ $EUID -eq 0 ]] || { echo "run_demo: run with sudo: sudo bash scripts/demo/run_demo.sh" >&2; exit 1; }
[[ -n "${SUDO_USER:-}" && "$SUDO_USER" != root ]] || { echo "run_demo: start it with sudo from your own account (act 3 runs as that user)" >&2; exit 1; }
T0=$SECONDS; fails=0
title() { printf '\n==================== %s ====================\n' "$1"; sleep 2; }
act() { # act <n> <title> <command...>
    local n=$1 t=$2 a=$SECONDS; shift 2
    title "ACT $n of 3: $t"
    "$@"; local rc=$?
    echo "[act $n: $((SECONDS - a)) s, exit status $rc]"
    [[ $rc -eq 0 ]] || fails=$((fails+1))
    sleep 3
}
echo "demo start $(date -Is) on $(uname -srm); repo $(git rev-parse --short HEAD 2>&1), branch $(git branch --show-current 2>&1)"
act 1 "the kernel verifier decides what may run in the kernel" bash scripts/demo/act1_verifier.sh
act 2 "the sender, not the receiver, can be the limit (live, 10 s per configuration)" bash scripts/demo/act2_sender_limit.sh
act3() {
    local have want
    have=$(sha256sum scripts/demo_c1.sh | cut -d' ' -f1)
    want=$(grep -o '6b2a81ed[0-9a-f]\{56\}' scripts/p9_verify.sh | head -1)
    echo "scripts/demo_c1.sh sha256 $have"
    echo "hash logged earlier (scripts/p9_verify.sh, check 7): $want"
    [[ -n "$want" && "$have" == "$want" ]] || { echo "act3: the hash does not match; not running the script"; return 1; }
    echo "hash matches; running it unchanged as $SUDO_USER"
    sudo -u "$SUDO_USER" bash scripts/demo_c1.sh
}
act 3 "register machine against stack machine: instructions per packet" act3
echo; echo "demo finished $(date -Is); total $((SECONDS - T0)) s; acts with a non-zero exit status: $fails"
exit $((fails>0))
