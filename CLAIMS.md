# CLAIMS

Source: docs/paper.txt (pdftotext -layout of the 2-column PDF). Because of the layout, each text line mixes a left-column and a right-column fragment; quotes below are the fragment of the cited line, with multi-line quotes marked "joined" (same column, consecutive lines). pdftotext dropped the "µ" glyph: "6 s" in the text means 6 µs.
"Modern metric" entries are proposals for Phases 2-6. Tool availability (perf, pktgen, veth, clang) is UNVERIFIED; see ENV.md gaps.

## C1 - Register-based vs stack-based filter machine, instructions/packet (Fig. 8)
- Quote (paper.txt L27-28, joined): "(BPF) uses a new, register-" + "based filter evaluator that is up to 20 times faster than the"
- 1993 headline (Fig. 8, paper.txt L751-829): mean CPU instructions per packet, BPF vs CSPF, from the figure's data labels (paper.txt L758-807):

  | Filter | BPF | CSPF | CSPF/BPF |
  |---|---|---|---|
  | 1 IP packets | 62 | 96 | 1.5x |
  | 2 IP src or dst "horse" | 160 | 549 | 3.4x |
  | 3 TCP src or dst port finger/domain/login/shell | 222 | 971 | 4.4x |
  | 4 IP, ARP or RARP between "horse" and "gauguin" | 129 | 2330 | 18.1x |

  Filter definitions: paper.txt L823-826. Prose cross-checks: Filter 1 "BPF faster by about 50%" (L720); Filter 2 "a performance gap of" / "240%" (L723-724, joined); abstract "up to 20 times" (L28). The ratios are computed from the figure labels; the paper itself states only 50%, 240%, and "up to 20 times".
  Bar-to-system assignment is inferred, not printed in the text: in `pdftotext -bbox` (logs/phase0_fig8_bbox.log) the smaller value in each pair sits left of the filter label and the larger right, and the ratios match the prose above. Legend colours were not checked. Fig. 8 labels Filter 4 as "Filter 4" but the prose calls it "filter 5" (L736); we treat that as the paper's typo for Filter 4 (the description at L736-738 refers to figs. 5-6, the IP/ARP/RARP "host foo" filter).
- Modern metric (Phases 2-6): dynamic instructions per packet for the same four filters, as eBPF (JIT on, bpf_jit_enable=1 per ENV.md) vs a stack-machine reference evaluator we write ourselves (CSPF analogue; no such thing exists in Linux). Static eBPF instruction count as a secondary proxy. Counter source (e.g. perf instructions retired / packets) UNVERIFIED.

## C2 - "Reject all": in-kernel filtering cost flat vs packet size (Fig. 3)
- Quote (paper.txt L220): "constant, independent of the packet size. For BPF this is true"
- 1993 headline (Fig. 3, paper.txt L246-291): BPF 4.6 µs fixed, 0 ns/byte incremental ("BPF Incremental Overhead: 0 ns/byte", L265); NIT 136 µs intercept, 210 ns/byte (L262, L264). Prose: ~5 µs for BPF; NIT ~450 µs vs 5 µs for large packets (L211, L221).
- Modern metric: per-packet CPU cost (ns/packet) of a reject-all eBPF filter at packet sizes 64-1500 B, linear fit slope in ns/byte (expect ~0) and intercept; versus a copy-everything-then-filter-in-userspace baseline (NIT analogue; expect slope > 0).

## C3 - "Accept all": copy slope (ns/byte) + fixed per-packet cost (Fig. 2)
- Quote (paper.txt L208): "(148ns/byte) while NIT runs 45% slower (216ns/byte)."
- 1993 headline (Fig. 2, paper.txt L159-204): BPF 148 ns/byte, 5.7 µs intercept ("about 6 µs", L210); NIT 216 ns/byte, 89.2 µs intercept ("89 µs", "15 times worse", L210-211). Labels at L186, L188-189.
- Modern metric: accept-all capture, per-packet cost vs packet size, linear fit: slope (ns/byte, copy cost) and intercept (µs/packet fixed cost), eBPF capture path vs conventional copy-to-user path. Absolute values will not be comparable with a 1993 Sparcstation 2; compare the structure (fixed cost + linear copy term) and the ratio.

## C4 - End-to-end: "10 to 150 times faster than Sun's NIT and 1.5 to 20 times faster than CSPF"
- Quote (paper.txt L29-30, joined): "facilities—10 to 150 times faster than Sun’s NIT and 1.5 to 20" + "times faster than CSPF on the same hardware and traffic mix."
- 1993 headline: 10-150x faster than NIT, 1.5-20x faster than CSPF, "on the same hardware and traffic mix" (L29-30). This sentence is in the right-hand column of page 1, which continues the 1 Introduction text that starts in the left column (L34). Related abstract claims (left column): filter evaluator "up to 20 times faster" (L28); overall performance "up to 100 times" / "faster than Sun’s NIT running on the same hardware." (L30-31, joined).
- The paper gives no single end-to-end table for these ranges; they are stated only in prose. UNVERIFIED: how the 10-150x and 1.5-20x ranges were derived from Figs. 2, 3, 8.
- Modern metric: end-to-end CPU cost per captured packet (and max lossless capture rate) for (a) kernel-side eBPF filtering vs (b) userspace copy-then-filter (NIT analogue) vs (c) a stack-machine filter in kernel (CSPF analogue). OPEN DECISION for the user: what stands in for CSPF on Linux (see C1).

## C5 - Thesis: a safe in-kernel VM makes "code to the data" practical (ancestor of eBPF)
- UNVERIFIED: the phrase "code to the data" does not occur in paper.txt (grep -i "code to\|to the data" returns no hit). The word "safe"/"safety" also does not occur (grep -i "safe" no hit); the paper does not discuss verification/termination safety. The thesis as worded in the prompt is an interpretation, not a quotation.
- Closest verbatim support (paper.txt L403-404, joined): "generalization of packet filtering: The idea of putting a" + "pseudo-machine language interpreter in the kernel"; this is in 3.1 (CSPF model), crediting CSPF, not in the intro. Also: "Its programmable" / "pseudo-machine model has demonstrated excellent general-" (L737-738) and "all knowledge of particular protocols is" / "factored out of the kernel" (L739-740) in the Conclusion; and the filter should discard packets "as early as possible" (L24) and "in place" (L90, L93-94).
- 1993 headline: none numeric. Supporting numbers are C2/C3 (in-place filtering avoids the per-byte copy: 0 ns/byte vs 210 ns/byte).
- Modern metric: (i) bytes copied across the kernel/user boundary per packet with in-kernel eBPF filtering vs without (the "code to the data" payoff); (ii) Phase 5: verifier accept/reject of unsafe programs, captured stderr verbatim. "Ancestor of eBPF" is not a paper claim and stays out of the quantitative claims.
