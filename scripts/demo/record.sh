#!/usr/bin/env bash
# record.sh - the demo under a terminal recorder. Uses asciinema if it is installed (checked with command -v, nothing is installed here), otherwise `script -q`.
# Writes build/demo/demo_session.log (or build/demo/demo_session.cast); build/ is not committed. Usage: sudo bash scripts/demo/record.sh
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
[[ $EUID -eq 0 ]] || { echo "record: run with sudo: sudo bash scripts/demo/record.sh" >&2; exit 1; }
mkdir -p build/demo
if command -v asciinema > /dev/null; then
    out=build/demo/demo_session.cast; rm -f "$out"
    asciinema rec -q -c "bash scripts/demo/run_demo.sh" "$out"; rc=$?
else
    out=build/demo/demo_session.log; rm -f "$out"
    script -q -e -c "bash scripts/demo/run_demo.sh" "$out"; rc=$?
fi
[[ -s "$out" ]] || { echo "record: $out was not created" >&2; exit 1; }
chown "${SUDO_USER:-root}": "$out"
echo "recorded to $out (recorder: $(command -v asciinema > /dev/null && echo asciinema || echo 'script -q')), run_demo exit status $rc"
exit $rc
