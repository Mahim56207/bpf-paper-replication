# Phase 6c design: C1, instructions per packet, register machine vs stack machine

Status: written and frozen BEFORE any trace, oracle or counter run (hashes of this file, the sources and the programs are recorded in `logs/p6c/p6c_design_freeze.log` before the first run; this is evidence of order, not a git commit, because commits wait for the reviewer's "Phase N complete"). Any later change needs a dated amendment at the end of this file.

Scope: claim C1 only (CLAIMS.md C1: Fig. 8, paper.txt L751-829 and the sentence "up to 20 times faster", L28). C4's CSPF ratio stays "not replicated end-to-end" (D6.1 item 5): nothing here is a packet-capture timing.

## 1. What is measured

Fig. 8 is the "Mean Number of CPU Instructions Per Packet" of the two filter models, profiled "outside the kernel using iprof, an instruction count profiler" on campus trace files (paper.txt L703-712; figure axis label at L751-760). Two quantities are therefore defined here:

- **M2, host instructions per packet (primary).** x86_64 instructions executed inside the evaluator function per packet, counted by `valgrind --tool=callgrind` (event `Ir`), the same kind of quantity as iprof's. It includes the interpreter's own overhead per filter instruction (decode, simulated stack pointer and its loads and stores, paper.txt L307-310). It depends on our C code and on gcc 13.3.0 `-O2`; it is not the 1993 SPARC count.
- **M1, filter-machine instructions executed per packet (secondary).** The count of BPF (or CSPF) instructions the evaluator executes for a packet, independent of host and compiler. Expected to be close for trivial filters; the paper's two-part argument (more filter instructions in the tree model, paper.txt L320-329, and a costlier host implementation per instruction, L307-310) is then visible as M2/M1.

Per-filter ratio `R = mean(CSPF) / mean(BPF)` for M1 and for M2, to be compared with the ratios computed from the Fig. 8 labels (CLAIMS.md C1: 1.5, 3.4, 4.4, 18.1; the paper itself states only "about 50%", "240%" and "up to 20 times").

## 2. The four filters (Fig. 8 definitions, paper.txt L823-826)

Frames are Ethernet (DLT_EN10MB). Constants chosen by us (the paper's host names have no addresses): horse H = 10.0.0.10 (0x0A00 000A), gauguin G = 10.0.0.20 (0x0A00 0014); TCP ports finger 79, domain 53, login 513, shell 514 (`/etc/services`, `logs/p6c/p6c_services_grep.log`).

| id | paper definition | libpcap expression (oracle and BPF source) |
|---|---|---|
| F1 | IP packets | `ip` |
| F2 | IP packets with src or dst "horse" | `ip host 10.0.0.10` |
| F3 | TCP packets with src or dst port of finger, domain, login, or shell | `ip and tcp and (port 79 or port 53 or port 513 or port 514)` |
| F4 | IP, ARP or RARP packets between hosts "horse" and "gauguin" | `host 10.0.0.10 and host 10.0.0.20` |

The oracle's semantics are the specification: F3 includes libpcap's "not a non-first IP fragment" test; F4 means (IP: one of src/dst is H and one of src/dst is G) or (ARP, RARP: sender or target protocol address is H, and sender or target is G). The CSPF programs must reproduce exactly these decisions (section 6).

## 3. The two machines

### 3.1 Register machine (BPF), paper section 3.3 and Tables 1 and 2
Interpreter `c1_eval_bpf` in `src/c1_interp.c`: accumulator and index register as C locals, 16-word scratch store, program counter, one `switch` over the opcode (paper constraint 4, L463-464), opcodes limited to Table 1 plus what libpcap emits (the interpreter aborts on any other opcode, so a missing opcode cannot pass silently). Out-of-packet load terminates with 0 and division by zero terminates with 0 (paper.txt L570-572, L577). Programs come from `pcap_compile` with optimizer on (**BPF-opt**, primary) and off (**BPF-raw**, secondary). M1 counts every executed instruction including the final `ret`.

### 3.2 Stack machine (CSPF analogue), paper section 3.1
Interpreter `c1_eval_sm`: a stack of 16-bit elements in memory with a stack pointer, one `switch` over the opcode. Accept if the stack is empty or its top is non-zero at the end (paper.txt L295-296). Opcodes (our choices, D6c.3):

| opcode | action |
|---|---|
| `PUSHLIT k` | push literal k |
| `PUSHWORD n` | push the big-endian 16-bit packet word at byte offset n; if it does not lie wholly inside the packet push 0 |
| `PUSHIND` | pop a byte offset, push the 16-bit packet word there (0 if out of the packet): the indirection operator of paper.txt L705 |
| `PUSHIPIND n` | push the 16-bit word at byte offset 14 + 4*(byte14 & 0xf) + n (0 if out of the packet): a fused indirection that knows the IP header length, the **optimistic** CSPF for Filter 3 |
| `EQ NEQ AND OR XOR ADD LSH RSH` | pop b, pop a, push a op b (16-bit result; EQ and NEQ push 1 or 0) |
| `CAND` | pop a; if a == 0 stop with REJECT, else continue |
| `COR` | pop a; if a != 0 stop with ACCEPT, else continue |

M1 counts every executed opcode (a push and a binary operation are separate instructions, following the paper's wording at L341-343). Stack depth is limited to 32; overflow aborts.

Why out-of-range words read as 0 and do not terminate: with a tree that evaluates every leaf, a leaf that lies past the end of a short frame must not by itself reject a frame that the register machine accepts on an earlier leaf. The choice is ours; the paper only says CSPF "does not permit access to the last byte of an odd-length packet" (L400). Decision equivalence on short and truncated frames (section 6) tests the choice.

### 3.3 CSPF program variants (construction rules fixed in advance)
Trees, with leaves tested exactly as the oracle semantics need (word offsets from Ethernet: ethertype 12; IP: flags and fragment word 20, protocol in the low byte of word 22, src 26-29, dst 30-33; ARP/RARP: sender protocol address 28-31, target 38-41):

- F1 = `eth == 0x0800`
- F2 = `eth == 0x0800 AND (src == H OR dst == H)`
- F3 = `eth == 0x0800 AND proto == 6 AND (word20 & 0x1fff) == 0 AND OR over the four ports p of (sport == p OR dport == p)`, where the TCP header is located from the IP header length at every leaf (the paper: "The CSPF filter must re-do the parse and relocate the TCP header for each port to be tested", L733-735)
- F4 = `(eth == 0x0800 AND ipHost(H) AND ipHost(G)) OR (eth == 0x0806 AND arpHost(H) AND arpHost(G)) OR (eth == 0x8035 AND arpHost(H) AND arpHost(G))` with `ipHost(X) = src == X OR dst == X` and `arpHost(X) = spa == X OR tpa == X`

A 32-bit compare is two 16-bit compares joined by AND (paper.txt L725-728). Variants (the programs are in `src/c1_progs/`, one file each, frozen by hash):

- **full**: post-order evaluation, every internal node a binary `AND` or `OR`; no short-circuit.
- **sc**: as full, plus `CAND` after every non-last conjunct of the ROOT conjunction and `COR` after every non-last disjunct of the root disjunction and of the TAIL disjunction of the root conjunction. Short-circuit is not applied inside a branch of an OR (a stack machine with no jumps cannot skip a nested conjunct without ending the whole filter). Paper.txt L327-329 presents short-circuit operators as an optional addition.
- **general** (F3 only): the TCP header offset is computed at every leaf with `PUSHWORD 14, PUSHLIT 8, RSH, PUSHLIT 15, AND, PUSHLIT 2, LSH, PUSHLIT 14, ADD` (+ `PUSHLIT 2, ADD` for the destination port) then `PUSHIND`.
- **fused** (F3 only): `PUSHIPIND 0` for the source port and `PUSHIPIND 2` for the destination port.

For F1, F2 and F4 general and fused coincide. Four CSPF variants per filter: `full-general`, `sc-general`, `full-fused`, `sc-fused`. **Primary CSPF = `sc-fused`**, declared now as the a-priori most optimised construction; it favours CSPF, so a win for BPF against it is the stronger finding.

## 4. Traces

`scripts/c1_make_trace.py` (seed 20261025, stdlib only) writes a classic pcap file (microsecond magic, DLT_EN10MB) of 10,000 frames per mix in shuffled order, plus a label file (one type label per frame). **The mixes are assumptions (D6c.4).** Parameters, as fractions of all frames unless stated:

| parameter | M0 (primary, "campus-like") | M-ip (IP-dominated) | M-nonip (non-IP-heavy) |
|---|---|---|---|
| IPv4 | 0.85 | 0.97 | 0.40 |
| ARP | 0.05 | 0.01 | 0.20 |
| RARP | 0.01 | 0.00 | 0.05 |
| IPv6 (ethertype 0x86dd) | 0.01 | 0.00 | 0.05 |
| other ethertypes (0x6003, 0x809b, 0x8137) | 0.08 | 0.02 | 0.30 |
| of IPv4: TCP / UDP / ICMP | 0.70 / 0.26 / 0.04 | same | same |

Common to all mixes (as fractions of the class they refine): of IPv4 frames, the address categories are exclusive: H and G are the two ends in 0.01 (half H to G, half G to H), H with another host in 0.07, G with another host in 0.04, neither in 0.88 (so H is involved in 0.08 and G in 0.05 overall); of UDP frames, 0.10 use port 53 or 513 (these must NOT match Filter 3); of TCP frames, source or destination port is in {79, 53, 513, 514} in 0.15 (of which a third the destination, a third the source, a third both ends in the set); IP header length 5 words in 0.95 and 6 to 8 in 0.05; non-first fragments in 0.01 of IPv4 frames; ARP and RARP frames: H and G both in 0.02, H alone in 0.08, G alone in 0.08, neither in 0.82; all other addresses are drawn from 10.0.0.30-10.0.0.250; ports otherwise drawn from {23, 25, 80, 110, 119, 6000} and 1024-5000; frames padded to at least 60 bytes as Ethernet does, payload lengths drawn in 0-1400; 1% of frames in each mix are cut to a random length between 1 and the frame length minus 1 (truncated capture). The mixes are not claimed to resemble the 1992 Berkeley traffic. Two small traces are run through the same decision-equivalence checks (section 6) but are not used for the means: **corpus38**, the 38-frame Phase 3 corpus (`scripts/p3_make_packets.py <dir> 1`, the one-byte prefix stripped when the pcap is written, so that the empty and the 13-byte frame are included), and **edge**, built by `scripts/c1_make_trace.py`: matching and near-matching frames of every filter (H or G as source or destination, with IP options, a fragment, the four ports as source and destination, ARP and RARP with H and G) each cut at every length from 0 to the full length. The Phase 3 corpus uses addresses 10.0.0.1 and 10.0.0.2 and port 4040, so it exercises malformed and truncated headers more than matches; the edge trace covers the matches.

## 5. Counting procedure

- **M1**: `c1_interp` runs a program over a trace and writes one CSV row per frame (index, decision, filter instructions executed). Mean over frames. 
- **M2**: the trace is cut into 10 consecutive chunks of 1000 frames (the shuffled order makes chunks exchangeable). For each (program, chunk) the interpreter is run under `valgrind --tool=callgrind --toggle-collect=<evaluator>` and the collected `Ir` total divided by the number of frames in the chunk gives M2 for that chunk. Harness cost outside the evaluator (reading the file, the loop) is not collected. Linearity check: for each evaluator, `Ir` of a 500-frame and a 1000-frame run of the same chunk must differ by 500 times the per-frame figure, to within the call overhead being identical (reported, not a pass/fail gate beyond showing the per-frame overhead is constant).
- **Ratios and intervals**: per filter and mix, `R` = (mean over the 10 chunks of CSPF) / (mean over the 10 chunks of BPF). Interval: the 95% Student-t interval (df = 9, t = 2.262) of the ten per-chunk ratios CSPF_c / BPF_c (same chunk, same frames). M1 uses the same ten chunks. Summaries are computed by `scripts/c1_summarize.py` from files in `logs/p6c/` only.

## 6. Checks that must pass before any number is reported (VERIFY)

1. Decision equivalence: for every mix trace, the 38-frame corpus, every filter and every program (BPF-opt, BPF-raw, four CSPF variants), the interpreter's accept/reject decision equals `pcap_offline_filter` on the oracle's own compiled program for the same expression, frame by frame. **Zero mismatches** are required. A mismatch stops the run: the cause is diagnosed, a program or interpreter bug may be fixed and logged, a change of semantics is a dated amendment.
2. Match counts per filter and mix equal `tcpdump -r <pcap> -n '<expression>' | wc -l` (same libpcap compiler, different program path).
3. Instrument self-checks logged: the M2 linearity check above, and an M1 check on a hand-traced example: the dumped libpcap program for `ip` is printed, the instruction count a frame must execute is traced by hand from that dump for one IPv4 and one non-IPv4 frame, and `scripts/phase6c_verify.sh` compares it with the interpreter's M1 for those two frames (the hand trace is written in the log before the comparison).

## 7. Verdict rules for C1 (declared now; applied by `scripts/c1_summarize.py`)

Primary pairing: M2, mix M0, BPF-opt vs CSPF `sc-fused`. Robustness grid: all three mixes x {BPF-opt, BPF-raw} x the four CSPF variants.

- **C1a, direction**: for each of F1 to F4, R > 1 with the lower bound of the 95% interval > 1.
- **C1b, order**: the point estimates satisfy R(F1) < R(F2) < R(F3) < R(F4), as in the figure labels (1.5 < 3.4 < 4.4 < 18.1) and the prose that each filter shows a larger gap (paper.txt L718-737).
- **C1c, magnitude**: max over filters of R lies within a factor of two of the figure's 18.1, i.e. in [9.05, 36.2].
- **Verdict (on M2)**: **SUPPORTED** if C1a holds in the primary pairing and in every cell of the robustness grid, and C1b and C1c hold in the primary pairing. **MIXED** if C1a holds in the primary pairing but fails in some grid cell, or if C1a holds everywhere and C1b or C1c fails in the primary pairing. **NOT SUPPORTED** if C1a fails for any filter in the primary pairing. M1 is reported with the same sub-criteria but does not gate the verdict; where M1 and M2 disagree this is stated in `results/c1_verdict.md`.
- Because the programs and the mixes are ours, the verdict is about the register and stack machine MODELS as implemented here; it says nothing about the exact 1993 numbers, and no 1993 absolute number is compared.

## 8. Files

`src/c1_oracle.c` (libpcap: compile, offline-filter decisions), `src/c1_interp.c` (both machines, per-frame CSV, evaluator functions for callgrind), `src/c1_progs/` (CSPF programs, text), `scripts/c1_make_trace.py`, `scripts/c1_build.sh`, `scripts/c1_run.sh`, `scripts/c1_summarize.py`, `scripts/phase6c_verify.sh`; outputs `logs/p6c/*`, `results/c1_summary.md`, `results/c1_verdict.md`.

## 9. Amendments (dated; the freeze hashes in logs/p6c/p6c_design_freeze.log refer to the text above)

- **A1 (2026-10-25, before any oracle, equivalence or counter run).** Section 5 describes a "linearity check" (Ir of a 500-frame run against a 1000-frame run of the same chunk). On inspection that check is a tautology (the difference of two prefixes of the same data is the cost of the rest of the data) and cannot detect harness cost leaking into M2. It is replaced by two checks that can fail: (i) **attribution**: `callgrind_annotate` of one run per evaluator must show all collected `Ir` inside `c1_eval_bpf` or `c1_eval_sm` and nothing in any other function; (ii) **build agreement**: for every M2 run the accept count printed by the callgrind (non-counting) build equals the accept count of the same chunk in the counting build's per-frame CSV. Rules, programs, mixes, metrics and the verdict rule are unchanged.
- **A2 (2026-10-25, after the first `equiv` run, before any counter run).** The first run of check 1 (section 6) stopped on one oracle inconsistency, not on a mismatch of our interpreters: on the `edge` trace for Filter 3, libpcap's optimized and unoptimized programs disagree on 6 of 1054 frames (`logs/p6c/p6c_diag_edge_F3.log`: IP header length 6, cut at 40 or 41 bytes, so the TCP destination port lies beyond the end of the frame while the source port is readable; the optimized program accepts on the source-port test, the unoptimized program reads the destination port first, goes out of the packet and returns 0; `tcpdump` shows the same split, 221 accepts with the default optimizer and 215 with `-O`). Rule change: each BPF program is compared with libpcap's decision for that same program (`bpf-opt` with the optimized program's `pcap_offline_filter` result, `bpf-raw` with the unoptimized program's); the CSPF variants are compared with the optimized program's decisions; the opt/raw disagreement is reported in `results/c1_summary.md` as an observation about libpcap, not hidden. `src/c1_oracle.c` now writes `<prefix>.rawdec` and no longer exits non-zero on an opt/raw disagreement; `scripts/c1_run.py` applies the per-program reference. The mixes are unaffected (opt/raw disagreement 0 on all three, `logs/p6c/p6c_equiv.log`). Zero mismatches against the chosen reference remain required.
