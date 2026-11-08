#!/usr/bin/env bash
# p10_capture_real.sh - Phase 10 WP3(c) data preparation: capture up to 20000 frames (or 600 s, whichever comes first) on the VM's own interface enp0s8 while the machine
# is used normally, then anonymize them (scripts/p10_traffic_anon.py). The raw capture stays in build/p10/ (untracked, never committed); the repository keeps only the
# anonymized trace hash and summary. Needs root. Usage: sudo bash scripts/p10_capture_real.sh 2>&1 | tee logs/p10/p10_capture_real.log
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[[ $EUID -eq 0 ]] || { echo "FATAL: run with sudo" >&2; exit 1; }
mkdir -p build/p10
RAW=build/p10/real_raw.pcap; ANON=build/p10/real_anon.pcap
[[ ! -e $RAW && ! -e $ANON ]] || { echo "ABORT: $RAW or $ANON exists; refusing to overwrite (move them away on purpose)" >&2; exit 1; }
echo "capturing on enp0s8 for up to 600 s or 20000 frames; use the machine normally (browse, update) meanwhile"
# NOTE (D2.8): tcpdump's AppArmor profile accepts signals only from unconfined peers, so `timeout` from the terminal (label claude-desktop) cannot stop it: the first run of this
# script hung until it was stopped with `sudo systemd-run --collect --wait pkill -INT -x tcpdump`. The line below runs it as a transient systemd unit with RuntimeMaxSec instead
# (UNVERIFIED: this replacement was written after the capture had been taken and was not re-run).
systemd-run --quiet --pipe --wait --collect -p RuntimeMaxSec=600 -p WorkingDirectory="$PWD" tcpdump -i enp0s8 -c 20000 -n -w "$RAW" 2> build/p10/real_capture.err; rc=$?
echo "tcpdump unit exit $rc (a unit stopped by RuntimeMaxSec reports a failure; the capture file is what counts)"; cat build/p10/real_capture.err
[[ -s $RAW ]] || { echo "FATAL: no capture file" >&2; exit 1; }
chown "${SUDO_USER:-root}": "$RAW"
python3 -I scripts/p10_traffic_anon.py "$RAW" "$ANON" || { echo "FATAL: anonymization failed" >&2; exit 1; }
chown "${SUDO_USER:-root}": "$ANON" "$ANON.hg" "$ANON.json"
echo "anonymized trace: $(sha256sum "$ANON")"; echo "H and G: $(cat "$ANON.hg")"
cp "$ANON.json" logs/p10/real_trace_summary.json; sha256sum "$ANON" > logs/p10/real_trace_sha256.log; date -Is >> logs/p10/real_trace_sha256.log
echo "the raw capture $RAW stays untracked (build/ is ignored); do not commit it"
