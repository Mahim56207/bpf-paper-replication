#!/usr/bin/env bash
# p11_secrets_scan.sh - pattern scan (no scanner is installed) over the files that the Phase 11 commit would add or change, plus a check that no capture file, build artifact or
# oversized file is among them. Usage: bash scripts/p11_secrets_scan.sh 2>&1 | tee logs/p11/p11_secrets_scan_console.log   (writes logs/p11/p11_secrets_scan.log, deleted first, checked after)
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
OUT=logs/p11/p11_secrets_scan.log; rm -f $OUT
files=$( (git diff --name-only; git ls-files --others --exclude-standard) | sort -u )
PAT='AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(password|passwd|secret|api[_-]?key|token)[ "'"'"']*[:=][ "'"'"']*[A-Za-z0-9/+_-]{8,}|Authorization: *Bearer|ssh-rs[a] AAAA|AIza[0-9A-Za-z_-]{30,}'
nf=0; hits=0; bad=0
for f in $files; do
    [[ -f "$f" ]] || continue
    nf=$((nf+1))
    case "$f" in build/*|*.pcap|*.pcapng|*.o|*.so) echo "BAD: $f is a build artifact or capture"; bad=$((bad+1));; esac
    sz=$(stat -c %s "$f"); [[ $sz -le 5000000 ]] || { echo "BAD: $f is $sz bytes"; bad=$((bad+1)); }
    case "$f" in *.png|*.pdf|logs/p11/p11_secrets_scan*) continue;; esac
    if grep -InE "$PAT" "$f" > "$OUT.tmp" 2>&1; then echo "HIT in $f:"; cut -c1-160 "$OUT.tmp"; hits=$((hits+1)); fi
done
rm -f "$OUT.tmp"
echo "files scanned: $nf; files with pattern hits: $hits; build-artifact, capture or oversized files: $bad" | tee $OUT
[[ -s $OUT && $hits -eq 0 && $bad -eq 0 ]]
