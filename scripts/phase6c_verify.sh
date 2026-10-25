#!/usr/bin/env bash
# Phase 6c verify: rebuild, regenerate programs and traces, check they hash to the frozen values, run the
# decision-equivalence stage, the hand-traced M1 check, the callgrind stage, the attribution check and the
# summary. Usage: bash scripts/phase6c_verify.sh 2>&1 | tee logs/p6c/p6c_verify.log
# Needs: gcc, libpcap-dev, tcpdump, valgrind, python3 (stdlib only). No root, no network lab.
# C1_LOG / C1_RES redirect the outputs (defaults logs/p6c and results); the frozen hashes are always read from
# logs/p6c/p6c_design_freeze.log. Amendment A3 (docs/phase6c_design.md section 9) replaced the 100.0% attribution
# check by the leak report and cross-check of `c1_run.py attrib`, and the hand-trace step now creates its output
# directory first and removes any stale CSV (a missing oracle file can no longer pass on the committed CSV).
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
L=${C1_LOG:-logs/p6c}; R=${C1_RES:-results}; B=build/p6c; FZ=logs/p6c/p6c_design_freeze.log
export C1_LOG=$L C1_RES=$R
mkdir -p "$L" "$R" "$B/oracle"
fail=0
step() { echo; echo "### $*"; }
chk() { if [[ $1 -eq 0 ]]; then echo "PASS: $2"; else echo "FAIL: $2"; fail=$((fail+1)); fi; }

step "1. environment (real commands)"
uname -srm; gcc --version | head -1; valgrind --version; pkg-config --modversion libpcap; tcpdump --version 2>&1 | head -1; python3 --version
{ echo "uname=$(uname -sr) $(uname -m)"; echo "arch=$(uname -m)"; echo "gcc=$(gcc --version | head -1 | sed 's/^gcc (\(.*\)) \([0-9.]*\)$/gcc \2/')"; echo "valgrind=$(valgrind --version)"; echo "libpcap=$(pkg-config --modversion libpcap)"; } > "$L/p6c_env.log"

step "2. build"
bash scripts/c1_build.sh > $L/p6c_build_verify.log 2>&1; chk $? "c1_build.sh (log $L/p6c_build_verify.log)"

step "3. regenerate programs and traces; compare with the frozen hashes in $FZ"
rm -rf $B/corpus $B/traces; mkdir -p $B/corpus
python3 -I scripts/p3_make_packets.py $B/corpus 1 > $L/p6c_corpus_gen.log 2>&1; chk $? "p3_make_packets.py (38 frames)"
python3 -I scripts/c1_gen_progs.py src/c1_progs > $L/p6c_progs_gen.log 2>&1; chk $? "c1_gen_progs.py"
python3 -I scripts/c1_make_trace.py $B/traces --corpus $B/corpus > $L/p6c_trace_gen.log 2>&1; chk $? "c1_make_trace.py"
for f in src/c1_progs/*.sm $B/traces/*.pcap; do
    h=$(sha256sum "$f" | cut -d' ' -f1)
    if grep -q "$h  $f" $FZ; then echo "PASS: $f matches frozen hash"; else echo "FAIL: $f does not match frozen hash $h"; fail=$((fail+1)); fi
done

step "4. hand-traced M1 check (design section 6, item 3)"
rm -f "$L/p6c_handtrace.csv"
$B/c1_oracle 'ip' $B/traces/edge.pcap $B/oracle/hand_F1 > /dev/null; chk $? "c1_oracle wrote $B/oracle/hand_F1.* (A3: directory created above, no stale file)"
echo "dump of libpcap's optimized program for 'ip' (code jt jf k; first line = length):"; cat $B/oracle/hand_F1.opt.bpf
echo "hand trace, written from the dump BEFORE the comparison below:"
echo "  [0] code 40 = ldh [12]   [1] code 21 = jeq #2048 jt 0 jf 1   [2] code 6 = ret #65535   [3] code 6 = ret #0"
echo "  frame shorter than 14 bytes: [0] reads outside the packet and returns 0           -> 1 instruction"
echo "  frame of >= 14 bytes, ethertype 0x0800: [0], [1], [2]                              -> 3 instructions"
echo "  frame of >= 14 bytes, other ethertype:  [0], [1] (false, skips [2]), [3]           -> 3 instructions"
$B/c1_interp_count --machine bpf --prog $B/oracle/hand_F1.opt.bpf --pcap $B/traces/edge.pcap --csv $L/p6c_handtrace.csv; chk $? "c1_interp_count wrote $L/p6c_handtrace.csv"
python3 -I - <<'PY'
import csv, os, sys
rows = list(csv.DictReader(open(os.environ["C1_LOG"] + "/p6c_handtrace.csv")))
labels = open("build/p6c/traces/edge.labels").read().splitlines()
want = {"e-ip-H-src-cut0": 1, "e-ip-H-src-cut13": 1, "e-ip-H-src-cut14": 3, "e-arp-HG-cut42": 3}
bad = 0
for i, lab in enumerate(labels):
    if lab in want:
        got = int(rows[i]["vm_instr"])
        ok = got == want[lab]
        bad += not ok
        print("%s %-22s expected %d, interpreter M1 %d (decision %s)" % ("PASS:" if ok else "FAIL:", lab, want[lab], got, rows[i]["decision"]))
sys.exit(1 if bad or len(want) != sum(1 for l in labels if l in want) else 0)
PY
chk $? "hand-traced M1 values"

step "5. decision equivalence (libpcap oracle, tcpdump, 6 programs x 4 filters x 5 traces)"
python3 -I scripts/c1_run.py equiv > $L/p6c_equiv.log 2>&1; chk $? "c1_run.py equiv (log $L/p6c_equiv.log)"
tail -3 $L/p6c_equiv.log

step "6. callgrind chunks (720 runs) and attribution"
python3 -I scripts/c1_run.py m2 > $L/p6c_m2.log 2>&1; chk $? "c1_run.py m2 (log $L/p6c_m2.log)"; tail -1 $L/p6c_m2.log
python3 -I scripts/c1_run.py attrib > $L/p6c_attrib.log 2>&1; chk $? "A3 (i') leak report and (i'') cross-check (log $L/p6c_attrib.log)"
cat $L/p6c_attrib.log

step "7. summary and verdict"
rm -f $B/c1_summary_before.md; cp $R/c1_summary.md $B/c1_summary_before.md 2>/dev/null
python3 -I scripts/c1_summarize.py > $L/p6c_summarize.log 2>&1; chk $? "c1_summarize.py"; cat $L/p6c_summarize.log
if [[ -f $B/c1_summary_before.md ]]; then diff -q $B/c1_summary_before.md $R/c1_summary.md > /dev/null; chk $? "$R/c1_summary.md identical to the previous run (deterministic)"; fi

echo; echo "phase6c_verify: $fail FAIL"
exit $((fail>0))
