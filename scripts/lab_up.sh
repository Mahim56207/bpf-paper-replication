#!/usr/bin/env bash
# (Re)create the lab network used since Phase 2: p1veth0 (10.0.0.1/24) in the root namespace,
# p1veth1 (10.0.0.2/24) in namespace p2ns. Same commands as "Stage B topology" in
# scripts/phase2_verify.sh, kept in its own file so later phases can reuse it.
# Usage: sudo bash scripts/lab_up.sh        (removes any existing pair first)
#        sudo bash scripts/lab_up.sh down   (removes the pair and the namespace)
set -u
NS=p2ns; VA=p1veth0; VB=p1veth1; IPA=10.0.0.1; IPB=10.0.0.2
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }

ip netns del "$NS" 2>/dev/null
ip link del "$VA" 2>/dev/null
[[ "${1:-}" == "down" ]] && { ip -br link show; exit 0; }

ip netns add "$NS" || exit 1
ip link add "$VA" type veth peer name "$VB" || exit 1
ip link set "$VB" netns "$NS"
ip addr add "$IPA/24" dev "$VA"; ip link set "$VA" up
ip netns exec "$NS" ip addr add "$IPB/24" dev "$VB"
ip netns exec "$NS" ip link set "$VB" up
ip netns exec "$NS" ip link set lo up
echo "### root namespace: ip addr show $VA"; ip addr show "$VA"
echo "### namespace $NS: ip addr show $VB"; ip netns exec "$NS" ip addr show "$VB"
echo "### ip route get $IPB"; ip route get "$IPB"
