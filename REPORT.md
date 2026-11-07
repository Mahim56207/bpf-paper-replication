# BSD Packet Filter Replication: final report

Replication of McCanne and Jacobson, "The BSD Packet Filter" (USENIX Winter 1993; `docs/paper.pdf`, text in `docs/paper.txt`), on modern Linux eBPF. Repository: https://github.com/Mahim56207/bpf-paper-replication. Every number below is produced by `scripts/build_report.py` from `results/`, `logs/`, `ENV.md` and git; nothing is typed in by hand. Figures: `scripts/reproduce_figures.py`.

## Abstract

The paper's filter design was rebuilt as an eBPF socket filter and measured against a user-space copy-then-filter sniffer on an arm64 virtual machine (6.17.0-19-generic, 5 cores). The eBPF program loads (the verifier accepts it), counts and matches exactly what tcpdump counts, and two deliberately unsafe variants show the verifier rejecting a possibly-null map value and a context read a socket filter may not make while accepting a source-unsafe program it can prove safe. The benchmark matrix (110 plan rows; 105 final measured runs, 105 valid; 27 re-run attempts kept) did not replicate the paper's shape claims cleanly: C2 is MIXED and C3 is INCONCLUSIVE, and C4 is INCONCLUSIVE under the frozen V8 rule (NOT SUPPORTED as a receiver-drop claim if the post hoc, uncalibrated flood V8 floor is applied, D8.22), because at flood rates the sending core's generation capacity, not the receiver, became the limit, and the offered rate itself differed by configuration. Two measurement discoveries shaped the result: a noise-detection rule (V8) built on idle "canary" cores correctly flagged a noisy start of the session, and the idle baseline taken in that noisy phase (0.843 CPU-s/s against 0.131 at calibration, Phase 6) had to be replaced by the quiet calibration baseline (D6.13). C1 (instruction counts, sub-phase 6c and Phase 8.0) is MIXED: the register machine executes fewer instructions than the stack machine for all four filters, but the order of the ratios is not stable across machines and compilers. A control configuration without any capture tap (Phase 8.2) supports the explanation that the flood's offered load is limited by the sender (SENDER-LIMITED SUPPORTED, run set 2). A direct test of the V8 noise rule (Phase 8.4) found that it detects canary-core noise reliably but could not show that it protects the headline metric to a 5% tolerance (premise PARTIAL). The paper's CSPF ratio is not replicated end-to-end.

## Claims matrix

| ID | claim (CLAIMS.md) | final verdict | where to look |
|---|---|---|---|
| C1 | register-based vs stack-based filter machine, instructions per packet (Fig. 8) | **MIXED** (M2, host instructions per packet, primary pairing; x86_64 container, repeated on the aarch64 VM with the same label). Direction holds for all four filters (R above 1), the order of the ratios is not robust across machines, the grid fails in the cells listed under the C1 results (M0 / bpf-raw / sm-sc-fused; Mip / bpf-raw / sm-sc-fused; Mnonip / bpf-raw / sm-sc-fused) on both machines; the measured ratios are for our own interpreters and CSPF programs, not the 1993 code (D6c.3, D6c.4) | `results/c1_verdict.md`, `results/c1_summary.md`, `logs/p8/a3/results/`, `docs/phase6c_design.md`, `DEVIATIONS.md` D6c.1-D6c.4, D8.1-D8.9 |
| C2 | "reject all": in-kernel filtering cost flat vs packet size (Fig. 3) | **MIXED** (Phase 8.3 quiet re-run) | `results/verdicts.md`, `results/summary.md` (Reject curve), `logs/bench_[ABD]_nm_*.log` |
| C3 | "accept all": copy slope and fixed per-packet cost (Fig. 2) | **INCONCLUSIVE** (Phase 8.3 quiet re-run) | `results/verdicts.md`, `results/summary.md` (Accept curve), `logs/bench_[ABE]_m_*.log` |
| C4 | end-to-end speed-up over NIT and CSPF (abstract/introduction) | **INCONCLUSIVE** under the frozen V8 rule (the flood windows exceed the canary limit; **NOT SUPPORTED as a receiver-drop claim** with the post hoc, uncalibrated flood V8 floor, D8.22, a sensitivity analysis; the Phase 6 matrix, noisy session, with 4, 4 and 4 valid flood runs for A, B and C, gave **NOT SUPPORTED**); at flood rates the sender, not the receiver, limits the offered load (see the sender-bottleneck row, which tests that explanation with a control configuration N); the CSPF ratio is not replicated end-to-end (instruction-count ratios are in C1) | `results/verdicts.md`, `results/summary.md` (Flood), `logs/bench_[ABC]_flood_*.log` |
| C4-S | sender bottleneck (D6.14): the offered load of the flood is limited by the capture taps running in the sender's transmit path | **SENDER-LIMITED SUPPORTED** (Phase 8.2, run set 2 only: S-H1 and S-H2 hold, S-H2 only inside the pre-declared tolerance with the observed ratios above the prediction; run set 1 was INCONCLUSIVE and its raw logs were lost, D8.14) | `results/p8_2_summary_run2.md`, `results/p8_2_findings.md`, `docs/phase8_2_design.md` |
| C5 | a safe in-kernel VM makes "code to the data" practical (ancestor of eBPF) | **MIXED**: the mechanism is demonstrated (in-kernel filter loads, runs, is counted, and the verifier accepts the provably safe program and rejects the unsafe ones); a CPU benefit of the in-kernel placement is not demonstrated (C2 MIXED). The paper itself has no safety discussion (`CLAIMS.md` C5) | `docs/phase3_review.md`, `docs/phase4_notes.md`, `docs/phase5_analysis.md`, `logs/phase5_a2.log`, `logs/phase5_b.log` |

Verdict texts (computed by `scripts/summarize.py` from the pre-declared rules, 95% intervals only):

- **C2 MIXED.** A-over-D slope -4.42 ns/byte, 95% CI [-9.19, 0.35] (excludes 0: False); B-over-D slope -2.15 ns/byte, 95% CI [-6.95, 2.66] (includes 0: True); CIs non-overlapping: False. Root cause: A's slope CI includes 0: no detectable size dependence for the copy-then-filter config; the two slope CIs overlap. D floor slope -0.0119 ns/byte (net). Descriptive, not part of the rule (means over the valid reject-curve runs of all sizes): capture-process CPU A 11.1 (n=15), B 0.0 (n=15) % of one CPU; capture-process context switches A 7654 (n=15), B 1 (n=15) per s.
- **C3 INCONCLUSIVE.** slope A -0.976 [-7.35, 5.39], slope B 1.39 [-4.31, 7.09] ns/byte; slope diff A - B = -2.37, 95% CI [-10.9, 6.18]; intercept diff A - B = 2.01e+03 ns/pkt, 95% CI [-5.27e+03, 9.3e+03]. Root cause: slope difference (A - B) CI does not lie above 0; intercept difference (A - B) CI does not lie above 0. EXPLORATORY, not part of R-C3 (the 1993 slopes are BPF 148 and NIT 216 ns/byte, paper.txt L186-189 and L208): upper bound of the 95% slope interval A 5.39 ns/byte, B 7.09 ns/byte; as a fraction of the 1993 BPF slope A 0.0365, B 0.0479; as a fraction of the 1993 NIT slope A 0.025, B 0.0328.
- **C4 INCONCLUSIVE** (frozen V8 rule, no floor). not enough valid flood runs for A and B (frozen V8 rule, no floor: valid A 0, B 0, C 0; at least 2 needed)
- **C4, post hoc flood V8 floor of 0.035 CPU-s/s (D8.22), sensitivity analysis: NOT SUPPORTED.** flow-matched pps ceiling B - A = -4.56e+04 pps, 95% CI [-5.09e+04, -4.03e+04] (B higher = CI > 0: False); net CPU per flow-matched packet A/B factor = 0.863, 95% CI [0.852, 0.874] (A costs more = CI > 1: False). A saturated (socket drops > 1% of packets reaching it) in 0 of 5 valid runs; where it did not, A's figure is offered-load-limited, not a ceiling. Offered pps (mean of the valid runs): A 653245 (n=5), B 765540 (n=5), C 1026697 (n=5). The label concerns the receiver-drop reading of C4 (NOT SUPPORTED as a receiver-drop claim); C4's CSPF ratio is not tested end to end (D6.1 item 5).

## Methodology and environment

Testbed (`ENV.md`, `results/topology.md`): kernel 6.17.0-19-generic, aarch64, head -1, libbpf 1.6.2 (headers), bpftool bpftool v7.7.0` / `using libbpf v1.7` / `features:, bpf_jit_enable 1, 5 CPUs, no CPU-frequency governor (virtual machine). Traffic: iperf3 UDP between a veth pair, one end in network namespace `p2ns` (`scripts/lab_up.sh`); the capture process is pinned to core 2, the iperf3 server to core 3, the main client to core 4, the noise client to core 1, core 0 and (outside flood runs) core 1 are the canaries. Configurations: A user-space `baseline_sniffer`; B eBPF filter with a draining loader; C the same without drain; D `reject_all` (floor); E `accept_all`. Each run is 10 s; the matrix is the frozen plan `results/bench_plan.tsv` (seed 20261018) at 16000 offered pps for the curves (K1 redefined, D6.9) and unlimited rate for the flood. A separate always-on classifier tap (identical for every config) splits every frame into data flow, iperf3 control and other, so the conservation rules V5'a-e can be checked on every run (`docs/phase6_addenda.md`). Rules, thresholds and verdict criteria were frozen before any run (`docs/phase6_design.md`, commit 3591267) and changed only by the dated addenda below. The session ran in the graphical desktop (`ENV.md`, D6.9); noise was handled by rule V8 and idle subtraction. Phases: 0 bootstrap and claims; 1 toolchain; 2 user-space baseline; 3 eBPF filter; 4 loader and map reader; 5 verifier stress test; 6 benchmark design, calibration and matrix (6c: C1 instruction counts, run first in an x86_64 container with gcc 13.3.0 and valgrind 3.22.0, D6c.1); 7 report and historical comparison; 8.0 C1 repeated on this VM (gcc 15.2.0, valgrind 3.25.1) with amendment A3; 8.1 quiet measurement setup; 8.2 sender-bottleneck test with a no-capture control; 8.3 quiet re-run for C2 and C3; 8.4 validation of rule V8; 8.7 this update of the report.

## Results

Figures (`python3 scripts/reproduce_figures.py` regenerates them from the logs):

- `results/fig_cpu_cost.png`: per-packet CPU cost against packet size (reject curve, accept curve, flood); error bars are one standard deviation over valid repetitions.
- `results/fig_drop_rate.png`: capture-socket drop rate against offered load for the calibration ladders (quiet session and the first, busy-desktop session) and the flood runs.

Flood table (mean ± sd over valid runs; from `results/summary.md`): offered pps, flow-matched pps, net CPU ns per flow-matched packet (idle baseline subtracted: 0.030 CPU-s/s, the mean of the session's idle windows, as printed in `results/summary.md`), raw CPU ns per flow-matched packet.

| config | offered pps | flow-matched pps | net CPU ns / flow-matched pkt | raw CPU ns / flow-matched pkt | valid runs |
|---|---|---|---|---|---|
| A | 653245 ± 1716 | 320927 ± 1774 | 9718 ± 63 | 9810 ± 64 | 5 |
| B | 765540 ± 5614 | 275318 ± 4224 | 11265 ± 89 | 11372 ± 91 | 5 |
| C | 1026697 ± 6914 | 502326 ± 4541 | 5835 ± 36 | 5894 ± 37 | 5 |

Calibration (`results/calibration.json`, `docs/phase6_addenda.md`): config A lost no packets at any ladder step up to the top of the ladder at either frame size in the quiet session, while the first calibration (busy desktop, `logs/cal_v1_frozen_rules/`) saw drops from a few thousand pps. The iperf3 control connection contributes a constant 27 to 29 frames per run (V5'c envelope validated at 5 s and 10 s).

Historical comparison with the 1993 code: `results/comparison.md`. Verifier experiments (Phases 3 and 5): `docs/phase3_review.md`, `docs/phase5_analysis.md`.

### C1: instructions per packet, register machine against stack machine (Phase 6c and Phase 8.0)

Two user-space interpreters (a register machine per paper section 3.3 and a stack machine standing in for CSPF) were run over generated traces of 10000 frames in three assumed mixes, for the four filters of Fig. 8, with libpcap as decision oracle (zero decision mismatches). M2 is the host instructions per packet inside the evaluator (callgrind); M1 is the filter instructions executed. R is CSPF over BPF with a 95% interval; the primary pairing is mix M0, optimised BPF against the fused short-circuit stack program. **The CSPF programs, the traces and the filter addresses are our own choices (D6c.3, D6c.4); only ratios and shapes are compared with the paper.**

| filter | paper BPF / CSPF / ratio (Fig. 8) | x86_64 container: M2 BPF / CSPF / R [95%] | aarch64 VM, evaluator-only (A3): M2 BPF / CSPF / R [95%] | M1 (filter instructions) R, both machines |
|---|---|---|---|---|
| F1 | 62 / 96 / 1.5 | 57 / 90 / 1.58 [1.58, 1.58] | 82.8 / 91 / 1.1 [1.1, 1.1] | 1 [1, 1] |
| F2 | 160 / 549 / 3.4 | 108 / 346 / 3.19 [3.18, 3.2] | 138 / 345 / 2.51 [2.5, 2.52] | 2.61 [2.6, 2.61] |
| F3 | 222 / 971 / 4.4 | 195 / 593 / 3.04 [3.03, 3.04] | 226 / 590 / 2.61 [2.6, 2.61] | 2.48 [2.47, 2.48] |
| F4 | 129 / 2330 / 18.1 | 103 / 2121 / 20.6 [20.5, 20.7] | 132 / 2120 / 16.1 [16, 16.1] | 17.5 [17.5, 17.6] |

x86_64 container, as published (`results/c1_verdict.md`):

**Verdict (M2, host instructions per packet): MIXED**
- C1a (every filter's 95% interval of R above 1, primary): **holds**; in all 24 grid cells: **fails** (21 of 24 cells).
- C1b (R(F1) < R(F2) < R(F3) < R(F4), primary): **fails** (R = 1.58, 3.19, 3.04, 20.6).
- C1c (largest R within a factor of two of the paper's 18.1, i.e. in [9.05, 36.2]): **holds** (largest R = 20.6).
- Grid cells where C1a fails (M2): M0 / bpf-raw / sm-sc-fused; Mip / bpf-raw / sm-sc-fused; Mnonip / bpf-raw / sm-sc-fused.

aarch64 VM, Phase 8.0 with amendment A3 (`logs/p8/a3/results/c1_verdict.md`):

**Verdict (M2, host instructions per packet): MIXED**
- C1a (every filter's 95% interval of R above 1, primary): **holds**; in all 24 grid cells: **fails** (21 of 24 cells).
- C1b (R(F1) < R(F2) < R(F3) < R(F4), primary): **holds** (R = 1.1, 2.51, 2.61, 16.1).
- C1c (largest R within a factor of two of the paper's 18.1, i.e. in [9.05, 36.2]): **holds** (largest R = 16.1).
- Grid cells where C1a fails (M2): M0 / bpf-raw / sm-sc-fused; Mip / bpf-raw / sm-sc-fused; Mnonip / bpf-raw / sm-sc-fused.

- **Verdict MIXED on both machines, by the same rules.** Direction (C1a) holds for all four filters in the primary pairing; the grid of mixes, BPF programs and CSPF programs fails C1a in the cells listed above (the unoptimised BPF program against the short-circuit fused stack program, where Filter 3's stack program is shorter than libpcap's unoptimised one). The ordering of the ratios (C1b) differs between the machines: R(F2) and R(F3) are close, so that ordering is not robust. The magnitude (C1c) holds on both.
- **Compiler and toolchain dependence of the measurement itself.** On the x86_64 container (gcc 13.3.0, valgrind 3.22.0) callgrind attributed 100.0% of the collected instructions to the evaluator. On the VM (gcc 15.2.0, valgrind 3.25.1) the first run failed that attribution check: with `--toggle-collect`, callgrind sometimes loses the return from the evaluator and keeps collecting, so that the toggle total included work outside the evaluator, between 0.23% and 18.88% over 720 runs; which evaluator leaks depends on the compiler and optimisation level (a 40-line program reproduces it at gcc -O0, D8.7). Amendment A3 therefore counts only the instructions attributed to the evaluator functions; its cross-check against a whole-program profile was equal in 6 of 6 cases (the project build, a clang build and a gcc -O0 build, both evaluators; `logs/p8/a3/p6c/p6c_attrib.log`).
- **x86_64 against VM.** M1 is identical on both machines; the stack-machine M2 per packet is nearly equal on both (table), while the BPF M2 per packet is higher on the VM, so the ratios are lower there (`logs/p8/p8_c1_arm_vs_x86_A3.md`). Compiler version and architecture changed together, so the cause was not separated.

### Phase 8.3: quiet re-run of the benchmark matrix (recorded in Phase 9, `DEVIATIONS.md` D8.19 to D8.25)

The Phase 8.3 run had no design document and no pre-declaration. It re-ran the whole plan (110 plan rows, session run_1793446731), not only the C2 and C3 curves, with its own calibration: curve rate 16000 pps (Phase 6: 32000 pps, D8.20), calibration HOLD, calibration idle baseline 0.044 CPU-s/s (net CPU subtracts the session idle windows' 0.030, D8.21) and canary_max 0.015 and 0.010 (Phase 6: 0.131, 0.069 and 0.037, D8.21). Of the 105 final measured runs 90 are valid under the frozen V8 rule and 105 with the post hoc flood floor. The 15 flood logs are a separate re-run made after the matrix (D8.23); they are valid under the frozen V8 rule in 0 of 15 cases (the headline) and under the post hoc flood V8 floor (D8.22) in 15; the headline C4 label is therefore INCONCLUSIVE, the floor result is a labelled sensitivity analysis (NOT SUPPORTED), and the Phase 6 matrix (noisy session, 4, 4 and 4 valid flood runs for A, B and C) gave NOT SUPPORTED. The Phase 6 summaries are kept in `results/phase6_noisy/`.

### Phase 8.1: a quiet measurement setup

Idle windows of ten seconds with the matrix harness attached and no traffic (`results/p8_1_idle_table.md`, same definition as the Phase 6 calibration):

| window set | idle rate mean | idle rate max | x quiet calibration | canary {0,1} max | windows over the V8 limit |
|---|---|---|---|---|---|
| Phase 6 quiet calibration session | 0.131 | 0.180 | 1.0x | 0.0689 | 0 of 3 |
| Phase 6 matrix session start (noisy) | 0.843 | 0.924 | 6.5x | 0.3995 | 3 of 3 |
| Phase 8.1 desktopnow | 0.801 | 1.052 | 6.1x | 0.4575 | 3 of 3 |
| Phase 8.1 desktopquiet | 0.826 | 1.272 | 6.3x | 0.5282 | 2 of 3 |
| Phase 8.1 desktopsettled | 0.126 | 0.139 | 1.0x | 0.0569 | 0 of 3 |

The desktop left alone, with the Claude app open, is as quiet as the Phase 6 calibration session (the settled set); the noisy sets coincide with activity in the interactive session. This is a hypothesis based on the timing of my own commands and your replies, not a tested cause (`results/p8_1_findings.md`). No system change is needed; what matters is that nothing interactive happens during a run, a settle pause and a pre-flight idle set with the V8 limit, which every later run script uses.

### Phase 8.2: is the flood's offered load limited by the capture taps in the sender's transmit path?

A control configuration N (iperf3 flood and the classifier tap, no capture process and no eBPF capture filter) was compared with A, B and C under pre-declared rules (`docs/phase8_2_design.md`, hash chain checked): H1, offered(N) above offered(A) and offered(B) with Welch 95% intervals above zero; H2, a quantitative prediction from the share of sender samples with `packet_rcv` in the stack (perf, `cpu-clock` sampling), with a tolerance of 25% on R/P. **Run set 2 is the only basis of the verdict.**

Offered rate, valid unprofiled runs (`results/p8_2_summary_run2.md`):

| config | n | mean offered pps | sd | 95% CI of the mean |
|---|---|---|---|---|
| N | 6 | 2047448 | 56075 | [1988601, 2106296] |
| A | 6 | 1231731 | 85955 | [1141527, 1321936] |
| B | 6 | 1403339 | 82111 | [1317169, 1489510] |
| C | 6 | 2016726 | 18169 | [1997659, 2035793] |

S-H1 (differences of means, 95% Welch intervals):

| comparison | mean difference | 95% CI | Welch df | lower bound above 0 |
|---|---|---|---|---|
| N - A | 815717 | [720267, 911168] | 8.6 | yes |
| N - B | 644109 | [552013, 736206] | 8.8 | yes |
| N - C (not gating) | 30723 | [-28070, 89515] | 6.0 | no |

S-H2 (predicted P = 1/(1 - f_cap) against observed R = offered(N)/offered(X)):

| X | f_cap [95%] | P [95%] | R [95%] | R/P - 1 | within tolerance |
|---|---|---|---|---|---|
| A | 0.2633 [0.2511, 0.2754] | 1.357 [1.335, 1.380] | 1.662 [1.546, 1.778] | +22.5% | yes |
| B | 0.1848 [0.1745, 0.1950] | 1.227 [1.211, 1.242] | 1.459 [1.372, 1.546] | +18.9% | yes |
| C | 0.0225 [0.0157, 0.0293] | 1.023 [1.016, 1.030] | 1.015 [0.986, 1.044] | -0.8% | yes |

**Verdict SENDER-LIMITED SUPPORTED.** S-H1 holds strongly. **S-H2 holds only inside the pre-declared tolerance, with the observed ratios above the prediction** (R/P - 1 as in the table, same side for A and B), so the size of the effect is only approximately explained by the taps' share of samples; f was measured under profiling but applied to unprofiled rates, and the classifier tap, which is present in every configuration, is accounted for by f_cap on the assumption that its per-packet cost is the same in N and in A or B. C is not different from N, consistent with a cost per delivered packet to a reader (queue insertion, wake-up) and not filter execution; the wake-up cost was not measured separately. Details: `results/p8_2_findings.md`.

**History of the two run sets.** Run set 1 (same design) was INCONCLUSIVE: valid unprofiled runs per config (valid / planned) were N 5 / 6, A 0 / 6, B 0 / 6, C 4 / 6, because every A and B run exceeded the V8 limit on core 0; its cause was not identified (a high swap use, 3624 to 3694 MB during the runs (vmstat means by configuration, `logs/p8/p8_2/p8_2_diag_vmstat_core0.log`) against 1223 to 1224 MB in the Phase 6 flood runs, is an untested candidate). Its raw logs, profiles and perf data were then **deleted by a wrong launch** of the run script (D8.14); only the summary computed before the loss and derived diagnostics survive, so run set 1 can no longer be re-verified. After closing applications and a memory gate (amendment A2), run set 2 had every cell valid. The two run sets are not pooled.

### Phase 8.4: does rule V8 do what it is supposed to do?

Noise (stress-ng, cpu and cache types, pinned to the canary cores and duty-cycled; intensity is the CPU time the workers consumed) was injected at levels straddling the V8 limit in two experiments: E1 paced curve (config B, net CPU per matched packet) and E2 flood (config N, offered pps), 30 windows per type and level, in several launches; E3 tests noise that V8 cannot see. Design, its 5 amendments and the script-checked hash chain: `docs/phase8_4_design.md`, `results/p8_4_findings.md`.

**Pre-declared (pooled) result, the primary one.** Detection works as designed: the flagged fraction rises with the level and crosses at the limit. False positives at level 0: 3/120 windows, rate 0.025, Wilson 95% [0.009, 0.071], exact binomial 95% [0.005, 0.071]; the pre-declared acceptance test (Wilson upper bound at most 0.10) needs at least 35 windows and was unsatisfiable with 30 (my design flaw, amendments A4 and A5). Validity: V8's premise is **PARTIAL** in every family, every non-zero level INDETERMINATE, mainly because of variation between launches that the pooled test puts into its variance. Per family (level, flagged fraction, class, ratio to level 0 [95%], shift class). **The pooled summary's own arithmetic-prediction column is omitted here:** it is relative to the net metric, whose level-0 mean is near zero (or negative in some launches), so relative changes of the kind +617.2% are meaningless; the gross-scale predictions in the blocked tables below are used instead.

*E1 cpu*

| level | flagged | class | R vs level 0 [95%] | shift class |
|---|---|---|---|---|
| 0 | 1/30 = 0.03 | UNFLAGGED | 1.000 [1.000, 1.000] | - |
| 1 | 1/30 = 0.03 | UNFLAGGED | 0.645 [-0.264, 1.555] | INDETERMINATE |
| 2 | 8/30 = 0.27 | TRANSITION | 0.872 [-0.209, 1.953] | INDETERMINATE |
| 3 | 9/30 = 0.30 | TRANSITION | 1.579 [-0.232, 3.391] | INDETERMINATE |
| 4 | 30/30 = 1.00 | FLAGGED | 2.160 [-0.253, 4.574] | INDETERMINATE |
| 5 | 30/30 = 1.00 | FLAGGED | 3.742 [-0.387, 7.870] | INDETERMINATE |

*E1 cache*

| level | flagged | class | R vs level 0 [95%] | shift class |
|---|---|---|---|---|
| 0 | 0/30 = 0.00 | UNFLAGGED | 1.000 [1.000, 1.000] | - |
| 1 | 2/30 = 0.07 | UNFLAGGED | 2.182 [-1.189, 5.554] | INDETERMINATE |
| 2 | 5/30 = 0.17 | TRANSITION | 2.302 [-0.968, 5.572] | INDETERMINATE |
| 3 | 13/30 = 0.43 | TRANSITION | 3.212 [-1.245, 7.670] | INDETERMINATE |
| 4 | 30/30 = 1.00 | FLAGGED | 3.991 [-1.410, 9.391] | INDETERMINATE |
| 5 | 30/30 = 1.00 | FLAGGED | 8.085 [-2.675, 18.845] | INDETERMINATE |

*E2 cpu*

| level | flagged | class | R vs level 0 [95%] | shift class |
|---|---|---|---|---|
| 0 | 1/30 = 0.03 | UNFLAGGED | 1.000 [1.000, 1.000] | - |
| 1 | 1/30 = 0.03 | UNFLAGGED | 0.969 [0.830, 1.107] | INDETERMINATE |
| 2 | 23/30 = 0.77 | TRANSITION | 0.953 [0.811, 1.095] | INDETERMINATE |
| 3 | 30/30 = 1.00 | FLAGGED | 0.936 [0.793, 1.079] | INDETERMINATE |
| 4 | 30/30 = 1.00 | FLAGGED | 0.983 [0.837, 1.128] | INDETERMINATE |

*E2 cache*

| level | flagged | class | R vs level 0 [95%] | shift class |
|---|---|---|---|---|
| 0 | 1/30 = 0.03 | UNFLAGGED | 1.000 [1.000, 1.000] | - |
| 1 | 3/30 = 0.10 | UNFLAGGED | 1.015 [0.863, 1.167] | INDETERMINATE |
| 2 | 19/30 = 0.63 | TRANSITION | 1.007 [0.855, 1.159] | INDETERMINATE |
| 3 | 30/30 = 1.00 | FLAGGED | 1.019 [0.867, 1.172] | INDETERMINATE |
| 4 | 30/30 = 1.00 | FLAGGED | 1.038 [0.889, 1.188] | INDETERMINATE |

**Post hoc and exploratory (amendment A4, written after the pooled result had been seen).** Comparing each level with level 0 inside each launch (level 0 is present in every launch of E1 and E2; not in E3) resolves the flagged curve levels as MATERIAL, tracking the shift that adding the injected CPU would give; the lowest levels and the whole flood stay INDETERMINATE; the blocked premise is **PARTIAL**. Per family (level, flagged fraction, class, blocked shift over scale [95%], shift class, arithmetic prediction):

*E1 cpu*

| level | flagged (pooled) | class | blocked shift / scale [95%] | shift class | arithmetic prediction / scale |
|---|---|---|---|---|---|
| 1 | 0.03 | UNFLAGGED | -12.5% [-50.3%, +25.4%] | INDETERMINATE | +4.4% |
| 2 | 0.27 | TRANSITION | -4.5% [-43.2%, +34.2%] | INDETERMINATE | +14.9% |
| 3 | 0.30 | TRANSITION | +20.3% [-19.3%, +60.0%] | INDETERMINATE | +22.8% |
| 4 | 1.00 | FLAGGED | +40.7% [+1.1%, +80.4%] | MATERIAL | +43.6% |
| 5 | 1.00 | FLAGGED | +96.2% [+51.0%, +141.4%] | MATERIAL | +95.2% |

*E1 cache*

| level | flagged (pooled) | class | blocked shift / scale [95%] | shift class | arithmetic prediction / scale |
|---|---|---|---|---|---|
| 1 | 0.07 | UNFLAGGED | +23.3% [-15.7%, +62.3%] | INDETERMINATE | +18.5% |
| 2 | 0.17 | TRANSITION | +25.7% [+0.3%, +51.1%] | MATERIAL | +24.6% |
| 3 | 0.43 | TRANSITION | +43.7% [+14.9%, +72.5%] | MATERIAL | +38.7% |
| 4 | 1.00 | FLAGGED | +59.0% [+32.1%, +86.0%] | MATERIAL | +61.9% |
| 5 | 1.00 | FLAGGED | +139.9% [+111.9%, +167.9%] | MATERIAL | +121.8% |

*E2 cpu*

| level | flagged (pooled) | class | blocked shift / scale [95%] | shift class | arithmetic prediction / scale |
|---|---|---|---|---|---|
| 1 | 0.03 | UNFLAGGED | -3.1% [-8.0%, +1.8%] | INDETERMINATE | n/a |
| 2 | 0.77 | TRANSITION | -4.7% [-10.7%, +1.3%] | INDETERMINATE | n/a |
| 3 | 1.00 | FLAGGED | -6.4% [-13.3%, +0.5%] | INDETERMINATE | n/a |
| 4 | 1.00 | FLAGGED | -1.7% [-6.4%, +2.9%] | INDETERMINATE | n/a |

*E2 cache*

| level | flagged (pooled) | class | blocked shift / scale [95%] | shift class | arithmetic prediction / scale |
|---|---|---|---|---|---|
| 1 | 0.10 | UNFLAGGED | +1.5% [-6.6%, +9.5%] | INDETERMINATE | n/a |
| 2 | 0.63 | TRANSITION | +0.7% [-7.5%, +9.0%] | INDETERMINATE | n/a |
| 3 | 1.00 | FLAGGED | +1.9% [-5.6%, +9.4%] | INDETERMINATE | n/a |
| 4 | 1.00 | FLAGGED | +3.8% [-2.4%, +10.1%] | INDETERMINATE | n/a |

**Predicted, not measured.** The "arithmetic prediction" columns are computed from the measured canary CPU of each level (it assumes the added CPU simply adds to the system-wide cost); by that arithmetic levels that V8 flags in fewer than a fraction 0.9 of their windows already shift the per-packet cost of the curve by +4.4% up to +38.7%, so V8's limit is lax for a tolerance of 5% on this metric. The measured shifts at those levels are INDETERMINATE.

**E3, noise V8 cannot see: unresolved, not shown harmless.** Condition, windows, mean canary, flagged, Wilson, class, mean metric, ratio to the control [95%], shift class, blind:

| condition | n (excluded) | mean canary | flagged | Wilson 95% | class | M_sys mean | R vs S0 [95%] | shift class | blind |
|---|---|---|---|---|---|---|---|---|---|
| S0 control | 15 (0) | 0.0357 | 0/15 = 0.00 | [0.00, 0.20] | UNFLAGGED | 3086.24 | 1.000 [1.000, 1.000] | - | - |
| S1 cpu noise on core 2 (capture) | 15 (0) | 0.0343 | 1/15 = 0.07 | [0.01, 0.30] | UNFLAGGED | 6608.98 | 2.141 [0.831, 3.452] | INDETERMINATE | False |
| S2 cpu noise on core 3 (server) | 15 (0) | 0.0391 | 2/15 = 0.13 | [0.04, 0.38] | TRANSITION | 7014.65 | 2.273 [0.935, 3.611] | INDETERMINATE | False |
| S3 global memory pressure | 15 (0) | 0.0280 | 0/15 = 0.00 | [0.00, 0.20] | UNFLAGGED | 2721.66 | 0.882 [0.222, 1.542] | INDETERMINATE | False |

**Ablation from existing data (V8 off).** Phase 6 labels C2, C3, C4 do not change (variant P, V8 on, reproduces the published labels; A1 final runs only; A2 with every earlier attempt as an extra run):

| claim | published | P | A1 | A2 |
|---|---|---|---|---|
| C2 | **MIXED** | MIXED | **MIXED** | **MIXED** |
| C3 | **INCONCLUSIVE** | INCONCLUSIVE | **INCONCLUSIVE** | **INCONCLUSIVE** |
| C4 | **NOT SUPPORTED** | NOT SUPPORTED | **NOT SUPPORTED** | **NOT SUPPORTED** |

Phase 8.2 run set 2 (valid unprofiled runs N / A / B / C, S-H1 lower bounds, R/P - 1, verdict):

| variant | valid unprofiled | S-H1 lower bounds | S-H2 R/P - 1 | verdict |
|---|---|---|---|---|
| P | 6 / 6 / 6 / 6 | 720267, 552013 | +22.5%, +18.9% | **SENDER-LIMITED SUPPORTED** |
| A1 | 6 / 6 / 6 / 6 | 720267, 552013 | +22.5%, +18.9% | **SENDER-LIMITED SUPPORTED** |
| A2 | 6 / 8 / 7 / 6 | 723697, 571293 | +21.1%, +20.0% | **SENDER-LIMITED SUPPORTED** |

Phase 8.2 run set 1 with V8 off, **computed only from surviving derived data** (the per-run offered rates in `logs/p8/p8_2/p8_2_diag_exploratory_offered.log`, printed by a script from the raw logs before they were deleted, and the per-run profile shares in `results/p8_2_summary.md`; the raw logs no longer exist, so this cannot be reproduced independently):

| variant | unprofiled N / A / B / C | profiled valid N / A / B / C | S-H1 lower bounds | S-H2 R/P - 1 | verdict |
|---|---|---|---|---|---|
| published (V8 on) | 5 / 0 / 0 / 4 | 4 / 3 / 4 / 2 | n/a | n/a | **INCONCLUSIVE** |
| V8 off | 6 / 6 / 6 / 6 | 4 / 3 / 4 / 2 | -218396, -95249 | -7.7%, +13.2% | **NOT SUPPORTED** |

So V8 did not change a Phase 6 label, and in Phase 8.2 it kept a contaminated set from giving a different verdict than the clean run set.

## Threats to validity

1. **Ambient noise (V8).** The first part of the matrix ran while the machine was still busy; the canary rate on cores 0 and 1 (what the experiment does not touch) was far above the idle level, and V8 flagged those windows and re-ran them (at most twice per cell). Per-block canary and busy medians, extracted from `logs/matrix_postcheck.log`:

```
  runs   1- 20  19:17:23 .. 19:22:36  median canary 0.501  V8-flagged 14 of 20  median system busy 1.23 CPU-s/s
  runs  21- 40  19:22:53 .. 19:28:05  median canary 0.472  V8-flagged 18 of 20  median system busy 1.42 CPU-s/s
  runs  41- 60  19:28:21 .. 19:33:34  median canary 0.044  V8-flagged  8 of 20  median system busy 0.37 CPU-s/s
  runs  61- 80  19:33:50 .. 19:39:02  median canary 0.025  V8-flagged  0 of 20  median system busy 0.20 CPU-s/s
  runs  81-100  19:39:18 .. 19:44:30  median canary 0.024  V8-flagged  0 of 20  median system busy 0.22 CPU-s/s
  runs 101-120  19:44:46 .. 19:49:58  median canary 0.024  V8-flagged  0 of 20  median system busy 0.21 CPU-s/s
  runs 121-138  19:50:14 .. 19:54:53  median canary 0.025  V8-flagged  1 of 18  median system busy 1.71 CPU-s/s
```

   In the Phase 6 matrix (`results/phase6_noisy/`), 28 attempts were re-runs, and 13 final cells stayed contaminated and are excluded; in the Phase 8.3 matrix (D8.19), 27 attempts were re-runs and 0 final cells are invalid (listed in `results/exclusions.md`; the flood cells depend on the post hoc floor, D8.22, D8.23). An earlier reading of the first 21 plan rows suggested V8 itself was broken (experiment spilling onto the canary cores); the full run refutes that (D6.10).
2. **Noisy idle baseline.** The three idle windows taken at the start of the session fell in the noisy phase (0.843 CPU-s/s, canary 0.28 to 0.40 CPU-s/s on cores 0 and 1 against a V8 limit of 1.2 x 0.069, Phase 6) and V8 was not applied to idle windows, so net CPU came out negative. Mitigation: net CPU recomputed with the quiet calibration baseline (0.131 CPU-s/s, Phase 6) as ruled in D6.13; the Phase 8.3 matrix takes its V8 limits from its own calibration baseline (canary_max 0.015 and 0.010, idle mean 0.044 CPU-s/s) and subtracts the mean of its session idle windows (0.030 CPU-s/s) for net CPU (D8.21); C2/C3 labels are unchanged by the swap, their numbers move by about 1% (the per-packet offset depends slightly on each run's offered rate). The original numbers are kept in `results/session_idle_baseline/`.
3. **Instrument cost.** The classifier tap adds a per-packet cost to every configuration, including the floor; it cancels in config differences and slopes but not in absolute CPU. The loader's one-per-second map reads are inherent overhead of config B (parity audit, `logs/parity_audit.log`).
4. **Sender-limited flood.** In-kernel filtering and classification run in the sending core's context, so the offered rate differs by configuration and "matched pps" in the flood measures the sender (D6.14). Config A was not saturated; its figure is offered-load-limited, not a ceiling. Phase 8.2 tested this with a no-capture control (see the results above); its limits are in item 10.
5. **Socket drops at the curve rate.** 6 final runs failed V4 in the Phase 6 matrix and 0 in the Phase 8.3 matrix (drops above 0.1% for the consumer configs at the chosen rate, 16000 pps in Phase 8.3, D8.20), so some cells have fewer than three valid repetitions; points with fewer than two are INCONCLUSIVE.
6. **Single machine, single session per phase, virtual machine.** No repetition across boots (Phase 8.4 ran in one boot; a VM pause of the host interrupted one attempt, D8.17); the first calibration and the matrix differ mainly in background load, which the report treats as a finding about measurement conditions, not as a replication result. C1 was measured on an x86_64 container and on this VM, whose compiler and architecture differ together.
7. **Process incidents** recorded in `DEVIATIONS.md`: zero-length git objects after an environment restart (D6.5, repaired from origin, `git fsck` clean before and after every later commit) and a premature reading of V8 (D6.10); in Phase 8, a wrong launch that deleted the raw logs of Phase 8.2 run set 1 (D8.14) and aborted pre-flights and a VM pause in Phase 8.4 (D8.17).
8. **Lost raw logs of Phase 8.2 run set 1.** Its summary and derived diagnostics survive, its raw logs, profiles and perf data do not; its INCONCLUSIVE verdict cannot be re-verified, and the V8-off ablation of that run set rests on derived files only. The verdict of Phase 8.2 rests on run set 2.
9. **Post hoc analyses.** Amendments A4 and A5 of Phase 8.4 and the evaluator-only M2 (A3 of Phase 6c) were written after seeing results; they are labelled as such and the pre-declared numbers are kept alongside. The statistics of the post hoc analyses have lower weight.
10. **Phase 8.2 sampling and model limits.** The guest has no hardware PMU, so perf samples come from a timer (`cpu-clock`) whose skew was not measured; profiling perturbs the system and f is measured under profiling but applied to unprofiled rates; f_cap assumes the classifier's per-packet cost is the same in N and in A or B; the observed ratios sit above the prediction for reasons not investigated.
11. **Phase 8.4 noise is synthetic.** stress-ng duty cycles on single cores are not the real ambient noise of Phase 6; the headline curve metric is system-wide and small at the chosen rate, so slow drift of the machine between launches dominates it; the tolerance of 5% is my choice; 30 windows per cell resolve only large shifts.
12. **Measurement tooling depends on compiler and platform.** callgrind's toggle collection lost returns on the VM in a compiler-dependent way (C1 results above); amendment A3 counts evaluator functions only.
13. **Interactive activity.** Runs started from, and monitored in, the same desktop session as the assistant are sensitive to its activity (Phase 8.1); the run scripts use a settle pause, a pre-flight and a hands-off protocol, and several launches had to be repeated for that reason.

## Amendments

| commit | date | trigger | mechanism |
|---|---|---|---|
| 3591267 (frozen) | 2026-10-18 | pre-registration before any run | design, harness and thresholds frozen (D6.2) |
| 8038194 (bugfix) | 2026-10-18 | smoke runs exposed parser and file-ownership bugs | harness bug fixes only, no rule change (D6.3) |
| db4343c = C2 / A1 + A2 | 2026-10-19 | calibration failed under V5 (constant excess); smoke runs showed background CPU noise (D6.4, D6.4b, D6.4c) | V5 -> V5'a-e three-class decomposition (A1); V8 canary, idle subtraction, slope metric, R-C2/R-C3, M2 (A2); full text docs/phase6_addenda.md |
| 8562119 = C3 | 2026-10-19 | implement A1 + A2 | classifier tap, V5' checks, V8 capture, idle windows, flow-scoped matched; V5'e self-check passed (D6.7) |
| a515e76 = C4 | 2026-10-19 | calibration under V5' | V5'c envelope validated; knee not reproduced, HOLD (D6.8) |
| 2fe2b94 = C5 | 2026-10-19 | reviewer ruling 3 | p_curve 32000 accepted, K1 redefined, session mode recorded (D6.9) |
| 8c7220b = matrix resolutions | 2026-10-19 | matrix completed; noisy session idle windows, sender-limited flood | idle baseline recalculated (D6.13), sender bottleneck recorded (D6.14), D6.10-D6.14 |

Dates are the commit dates from git. The rule text of A1 and A2 is in `docs/phase6_addenda.md`; every deviation, ruling and incident is in `DEVIATIONS.md`.

Design amendments of the later sub-phases (dates read from the amendment headings of each design document; the reasons are summarised, the full text is in the document):

| document | amendment | date | reason |
|---|---|---|---|
| `docs/phase6c_design.md` | A1 | 2026-10-25 | the linearity check was a tautology; replaced by an attribution check and a build-agreement check |
| `docs/phase6c_design.md` | A2 | 2026-10-25 | libpcap's optimised and unoptimised programs disagree on a few frames of one trace; each BPF program is compared with libpcap's decision for that same program |
| `docs/phase6c_design.md` | A3 | 2026-10-25 | on the VM the toggle total of callgrind included work outside the evaluator; M2 counts only the evaluator functions, with a leak report and a whole-program cross-check (written after the VM result, approved by the user) |
| `docs/phase8_2_design.md` | A1 | 2026-10-26 | after the probe: tap symbol packet_rcv confirmed, idle task name, harness ownership fix, informational counts; no rule changed |
| `docs/phase8_2_design.md` | A2 | 2026-10-26 | run set 1 INCONCLUSIVE: one repeat under the same rules with a memory gate, task-level instrumentation, a perf-window fix and corrected S-H1 wording; never pooled |
| `docs/phase8_4_design.md` | A1 | 2026-10-26 | before any run: cache noise needs --cache-enable-all; memory-hold wording; calibration length |
| `docs/phase8_4_design.md` | A2 | 2026-10-26 | calibration probe 1 unusable at low levels; the injected rate is the stress-ng workers' own CPU time |
| `docs/phase8_4_design.md` | A3 | 2026-10-26 | levels fixed from calibration probe 2; levels must be distinct and increasing |
| `docs/phase8_4_design.md` | A4 | 2026-10-27 | post hoc: blocked re-analysis, gross-CPU scale, dose-response, restated false-positive criterion |
| `docs/phase8_4_design.md` | A5 | 2026-10-27 | post hoc: erratum to A4 (the number of windows) |

Hash chains: `docs/phase8_2_design.md` (`logs/p8/p8_2/p8_2_design_chain.log`) and `docs/phase8_4_design.md` (`logs/p8/p8_4/p8_4_design_chain.log`) were reproduced by script; the file as it stands is not the version hashed first, because both were amended. Phase 8.4 amendments A4 and A5 and the `docs/phase6c_design.md` amendment A3 were written after results had been seen.

## UNVERIFIED items

Each item was marked UNVERIFIED where it arose; nothing here is claimed as a result. Items resolved by Phase 6c and Phase 8 are marked and no longer listed as open.

1. **C5 wording.** The phrase "code to the data" and any safety discussion do not occur in `paper.txt` (grep, `CLAIMS.md` C5); the C5 claim is an interpretation, and "ancestor of eBPF" is not a paper claim.
2. **How the paper's speed-up ranges were derived** (10 to 150 times over NIT, 1.5 to 20 over CSPF, paper.txt L29-30): they are stated only in prose (`CLAIMS.md` C4).
3. **Mechanism behind variant A loading** (`docs/phase5_analysis.md`): the verifier's own register state shows `R0=map_value` (not or_null) after both lookups, but the claim that this comes from array-map inlining with a constant in-range key is the reviewer's account and was not read from kernel source.
4. **`BPF_PROG_TEST_RUN` strips 14 bytes** for a socket filter (`DEVIATIONS.md` D3.4): supported by behaviour (prefix experiment), mechanism not read; the live AF_PACKET L2 view was confirmed empirically in Phase 4.
5. **Kernel ordering of filter and socket queue** (`docs/phase4_notes.md`): the counter equals tcpdump's count while the socket dropped almost every accepted packet, which supports "the filter counts before queueing"; the kernel source was not read.
6. **libbpf return conventions** of `bpf_program__fd`, `bpf_object__find_program_by_name` and `bpf_map_lookup_elem` are not documented in the installed headers and the failure paths were exercised only for interface lookup, object open and object load (`docs/phase4_notes.md`, `logs/p4_negatives.log`).
7. **tcpdump's default capture direction and whether `port N` includes SCTP/IPv6** (`docs/phase2_notes.md`): not in the man pages read; the runs showed agreement on this traffic.
8. **Why the calibration of this session found no knee** (D6.8): suspected quiet machine versus a busy desktop in the first calibration; one session each, not isolated.
9. **Cause of the zero-length git objects** (D6.5): an unflushed-write loss around an environment restart is assumed, not established.
10. **Softirq locus of the in-kernel filter (earlier item 10).** Partly resolved by Phase 8.2: with the capture process and filter removed the offered rate rises, and the samples with `packet_rcv` in the stack lie on the sender cores inside the iperf3 sender processes. Still open: why the observed ratio is above the sample-share prediction, and the exact mechanism (queue insertion, wake-up, cache effects), which was not measured separately.
11. **Classifier-tap overhead** was not measured separately; it is common to all configurations by construction. Phase 8.2 assumes its per-packet cost is the same in N and in A or B (f_cap); not tested.
12. **JIT output** was not inspected: `bpftool prog dump jited` is unsupported on this arm64 build (`ENV.md`), only `jited <n>B` from `prog show` is known.
13. **Resolved in Phase 6c and Phase 8.0 (earlier item 13): C1** is evaluated (MIXED). Open instead: the CSPF opcode set, the four stack programs, the filter addresses and the three trace mixes are our own choices (D6c.3, D6c.4), so the ratios describe our models, not the 1993 numbers; and the **CSPF half of C4** is still not replicated end-to-end.
14. **The 1993 code.** The 1993-code column of `results/comparison.md` cites today's FreeBSD `sys/net/bpf_filter.c` (pinned commit, D7.2), the descendant of the 1990 to 1993 code and not a 1993 snapshot; the caller `bpf_tap` and the buffer code in `bpf.c` were not read, and whether `bpf_validate` existed in 1993 is not known.
15. **Which code-generation feature makes callgrind lose a return on the VM** (D8.7): the dependence on compiler and optimisation level is observed, the cause is not identified; whether the BPF instruction-count difference between x86_64 and the VM is architecture or compiler version was not separated.
16. **Cause of the contamination of Phase 8.2 run set 1** (every A and B run exceeded the V8 limit on core 0): memory pressure (swap use 3624 to 3694 MB during the runs (vmstat means by configuration, `logs/p8/p8_2/p8_2_diag_vmstat_core0.log`) against 1223 to 1224 MB in the Phase 6 flood runs) is an untested candidate; run set 2 differs in several ways at once.
17. **Perf sampling skew**: the guest has no hardware PMU and perf uses the timer-based `cpu-clock` event; the skew of samples taken in softirq or interrupt-disabled sections was not measured.
18. **Whether rule V8 protects the headline metric to the tolerance** (Phase 8.4): the premise is PARTIAL; the pooled test is undecided, the post hoc blocked test supports it only for the flagged curve levels, and by arithmetic V8 is lax for that tolerance; the cause of the dose-response slope exceeding the additive-only value was not investigated.
19. **Noise that V8 cannot see (E3)** is unresolved: the ratios to the control for CPU noise on the measurement cores are 2.141 and 2.273, no interval excludes no effect, and the memory-pressure interval is wide enough to contain large effects.
20. **Whether the interactive session's activity caused the noisy idle windows of Phase 8.1** is a hypothesis from the timing of commands and replies, not a tested cause.

## Self-audit against CLAUDE.md

GROUNDING
- *Paper truth cites (paper.txt L<n>).* Followed in `CLAIMS.md` and the phase documents; quotes were checked against their cited lines by script in Phase 0 (`logs/phase0_quote_check.log`). Known gap: C5's wording is not in the paper (item 1 above).
- *Environment truth = ENV.md; re-probe when unsure.* Followed: ENV.md was re-probed after Phase 1 and extended in Phases 2, 3 and 6.
- *Oracle consultation recorded in DEVIATIONS.md.* tcpdump (D2.2) is recorded; FreeBSD `bpf_filter.c` is recorded as D7.2.

API DISCIPLINE
- *Grep installed headers and record the hit before first use.* Followed for every libbpf function, helper and socket option used (`CODE_NOTES.md`, per phase); builtins and libc calls are listed as such. `bpf_skb_load_bytes` and the Phase 6 additions were grepped and recorded before use.
- *libbpf surface = version in ENV.md.* Followed (1.6.x headers); one function outside the Phase 4 prompt's list was added and recorded (D4.1).
- *Kernel structs from vmlinux.h, not from memory.* Followed (`build/vmlinux.h` generated by bpftool); `ETH_P_IP` and the fragment mask, which are macros absent from BTF, are defined locally with their source recorded.

EVIDENCE DISCIPLINE
- *Every output shown = a command run this session, tee'd into logs/.* **Not fully followed.** Ad-hoc inspection commands (quick greps, one-off python tables for diagnosis) printed output that was not saved; the diagnoses that mattered were re-run into logs afterwards (for example `logs/p2_apparmor_probe.log`, `logs/matrix_postcheck.log`), but a few intermediate displays have no log. No output was simulated or tidied; pasted logs were read back from files.
- *No invented numbers; Phase 6 tables computed by scripts reading logs.* Followed for Phase 6 and for this report (generated by `scripts/build_report.py`). The Phase 2 to 5 documents contain numbers typed from logs at the time; the rule to extract verifier excerpts programmatically (D5.3) came after `docs/phase5_analysis.md` sections 2 and 3 were written, and those quoted lines were typed by hand (the later R0 paragraph is extracted by script).
- *Verifier rejections = captured stderr, verbatim.* Followed (`logs/phase5_a2.log`, `logs/phase5_b.log`, `logs/p3_v1_direct_access/`).

WORKFLOW
- *One phase at a time; wait for the exact "Phase N complete".* Followed; Phase 6 was split into sub-steps by reviewer rulings, with the single pre-registration commit as a logged exception (D6.2).
- *Same error twice: stop and ask; no silent architecture changes.* Followed for the tcpdump hang (stopped after the second occurrence, diagnosed), the direct-packet-access rejection (stopped and asked), the calibration HOLD (stopped), and the V5'c wording (asked). One judgment call was made before approval and disclosed afterwards: the classifier-tap mechanism (D6.7). One premature recommendation to stop the matrix was wrong and was corrected (D6.10).
- *Unsure: write UNVERIFIED and ask.* Followed; see the list above.
- *Phase 8 (follow-up) records.* Each Phase 8 step was committed once after "Phase 8.N complete" with its verify script re-run (`logs/p8/`); pre-declared design documents were hashed before their first run, amended only by dated amendments, and the hash chains were reproduced by script. Departures: Phase 8.4 amendments A4 and A5 and Phase 6c amendment A3 were written after results had been seen (labelled post hoc); a wrong launch deleted the raw logs of Phase 8.2 run set 1 (D8.14); several launches were repeated after pre-flight failures (D8.17).
- *Commit rule (re-run the verify script, one commit titled "Phase N: ...", never commit build artifacts or secrets).* Followed for Phases 1 to 5 (verify scripts re-run into `logs/*_rerun/`). Phase 6 used several commits by ruling (C1 to C6, all logged). `.gitignore` excludes `build/` and `*.pcap` (about 3 GB of captures stay local); a secrets scan ran before every commit.

## Reproducibility

See `README.md` (section Reproducibility).
