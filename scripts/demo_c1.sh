#!/usr/bin/env bash
# demo_c1.sh - 10-second live demo of claim C1 (register machine vs stack machine), Filter 4 of Fig. 8.
# Counts the filter instructions each machine executes per packet over 10,000 generated frames and checks
# that both machines give libpcap's accept/reject decision on every frame. Run from the repo root.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
B=build/p6c; mkdir -p "$B/oracle"
[[ -x $B/c1_oracle && -x $B/c1_interp_count ]] || bash scripts/c1_build.sh > /dev/null
if [[ ! -f $B/traces/mix_M0.pcap ]]; then
    mkdir -p "$B/corpus"
    python3 -I scripts/p3_make_packets.py "$B/corpus" 1 > /dev/null
    python3 -I scripts/c1_gen_progs.py src/c1_progs > /dev/null
    python3 -I scripts/c1_make_trace.py "$B/traces" --corpus "$B/corpus" > /dev/null
fi
EXPR='host 10.0.0.10 and host 10.0.0.20'
PCAP=$B/traces/mix_M0.pcap
echo "Filter 4 (IP, ARP or RARP between two hosts): $EXPR"
"$B/c1_oracle" "$EXPR" "$PCAP" "$B/oracle/demo_F4" | sed 's/^/  libpcap (oracle): /'
echo "  register machine program: $(head -1 "$B/oracle/demo_F4.opt.bpf") static instructions (libpcap, optimized)"
echo "  stack machine program:    $(wc -l < src/c1_progs/F4_sc_any.sm) static instructions (short-circuit, fused indirection)"
"$B/c1_interp_count" --machine bpf --prog "$B/oracle/demo_F4.opt.bpf" --pcap "$PCAP" --csv "$B/oracle/demo_bpf.csv" > /dev/null
"$B/c1_interp_count" --machine sm  --prog src/c1_progs/F4_sc_any.sm   --pcap "$PCAP" --csv "$B/oracle/demo_sm.csv"  > /dev/null
python3 -I - "$B/oracle/demo_F4.dec" "$B/oracle/demo_bpf.csv" "$B/oracle/demo_sm.csv" <<'PY'
import csv, statistics, sys
dec = open(sys.argv[1]).read().strip()
res = {}
for name, path in (("register machine", sys.argv[2]), ("stack machine", sys.argv[3])):
    rows = list(csv.DictReader(open(path)))
    bad = sum(1 for r, d in zip(rows, dec) if r["decision"] != d)
    res[name] = statistics.fmean(int(r["vm_instr"]) for r in rows)
    print("  %-16s mean instructions executed per packet: %6.2f   decision mismatches vs libpcap: %d of %d"
          % (name, res[name], bad, len(rows)))
print("  ratio stack / register = %.1fx   (1993 paper, Fig. 8 labels for Filter 4: 2330 / 129 = 18.1x, host instructions)"
      % (res["stack machine"] / res["register machine"]))
PY
