# BSD Packet Filter Replication: final report

Replication of McCanne and Jacobson, "The BSD Packet Filter" (USENIX Winter 1993; `docs/paper.pdf`, text in `docs/paper.txt`), on modern Linux eBPF. Repository: https://github.com/Mahim56207/bpf-paper-replication. Every number below is produced by `scripts/build_report.py` from `results/`, `logs/`, `ENV.md` and git; nothing is typed in by hand. Figures: `scripts/reproduce_figures.py`.

## Abstract

The paper's filter design was rebuilt as an eBPF socket filter and measured against a user-space copy-then-filter sniffer on an arm64 virtual machine (6.17.0-19-generic, 5 cores). The eBPF program loads (the verifier accepts it), counts and matches exactly what tcpdump counts, and two deliberately unsafe variants show the verifier rejecting a possibly-null map value and a context read a socket filter may not make while accepting a source-unsafe program it can prove safe. The benchmark matrix (110 plan rows; 105 final measured runs, 89 valid; 28 re-run attempts kept) did not replicate the paper's shape claims cleanly: C2 is MIXED and C3 is INCONCLUSIVE, and C4 is NOT SUPPORTED as a receiver-drop claim, because at flood rates the sending core's generation capacity, not the receiver, became the limit, and the offered rate itself differed by configuration. Two measurement discoveries shaped the result: a noise-detection rule (V8) built on idle "canary" cores correctly flagged a noisy start of the session, and the idle baseline taken in that noisy phase (0.843 CPU-s/s against 0.131 at calibration) had to be replaced by the quiet calibration baseline (D6.13). C1 (instruction counts) was not evaluated, and the paper's CSPF ratio is not replicated end-to-end.

## Claims matrix

| ID | claim (CLAIMS.md) | final verdict | where to look |
|---|---|---|---|
| C1 | register-based vs stack-based filter machine, instructions per packet (Fig. 8) | **NOT EVALUATED**: sub-phase 6c (the two user-space interpreters with instruction counters) was not run | `DEVIATIONS.md` D6.1 item 5, `docs/phase6_addenda.md` |
| C2 | "reject all": in-kernel filtering cost flat vs packet size (Fig. 3) | **MIXED** | `results/verdicts.md`, `results/summary.md` (Reject curve), `logs/bench_[ABD]_nm_*.log` |
| C3 | "accept all": copy slope and fixed per-packet cost (Fig. 2) | **INCONCLUSIVE** | `results/verdicts.md`, `results/summary.md` (Accept curve), `logs/bench_[ABE]_m_*.log` |
| C4 | end-to-end speed-up over NIT and CSPF (abstract/introduction) | **NOT SUPPORTED as a receiver-drop claim**; reveals a sender-generation bottleneck; CSPF ratio not replicated end-to-end | `results/verdicts.md`, `results/summary.md` (Flood), `logs/bench_[ABC]_flood_*.log` |
| C5 | a safe in-kernel VM makes "code to the data" practical (ancestor of eBPF) | **MIXED**: the mechanism is demonstrated (in-kernel filter loads, runs, is counted, and the verifier accepts the provably safe program and rejects the unsafe ones); a CPU benefit of the in-kernel placement is not demonstrated (C2 MIXED). The paper itself has no safety discussion (`CLAIMS.md` C5) | `docs/phase3_review.md`, `docs/phase4_notes.md`, `docs/phase5_analysis.md`, `logs/phase5_a2.log`, `logs/phase5_b.log` |

Verdict texts (computed by `scripts/summarize.py` from the pre-declared rules, 95% intervals only):

- **C2 MIXED.** A-over-D slope -0.951 ns/byte, 95% CI [-5.77, 3.87] (excludes 0: False); B-over-D slope 1.3 ns/byte, 95% CI [-2.29, 4.9] (includes 0: True); CIs non-overlapping: False. Root cause: A's slope CI includes 0: no detectable size dependence for the copy-then-filter config; the two slope CIs overlap. D floor slope 1.64 ns/byte (net).
- **C3 INCONCLUSIVE.** slope A 1.21 [-3.84, 6.25], slope B 0.101 [-3.99, 4.19] ns/byte; slope diff A - B = 1.1, 95% CI [-5.43, 7.64]; intercept diff A - B = -2.02e+03 ns/pkt, 95% CI [-7.76e+03, 3.71e+03]. Root cause: slope difference (A - B) CI does not lie above 0; intercept difference (A - B) CI does not lie above 0.
- **C4 NOT SUPPORTED.** flow-matched pps ceiling B - A = -4.16e+04 pps, 95% CI [-6.08e+04, -2.25e+04] (B higher = CI > 0: False); net CPU per flow-matched packet A/B factor = 0.892, 95% CI [0.816, 0.967] (A costs more = CI > 1: False). A saturated (socket drops > 1% of packets reaching it) in 0 of 4 valid runs; where it did not, A's figure is offered-load-limited, not a ceiling. C4's CSPF ratio is not replicated end-to-end (D6.1 item 5). NOT SUPPORTED as a receiver-drop claim. Reveals a sender-generation bottleneck: offered rates diverge by config because the filter/classifier overhead impacts the sending core's capacity. Config A was offered-load-limited, not receiver-saturated.

## Methodology and environment

Testbed (`ENV.md`, `results/topology.md`): kernel 6.17.0-19-generic, aarch64, head -1, libbpf 1.6.2 (headers), bpftool bpftool v7.7.0` / `using libbpf v1.7` / `features:, bpf_jit_enable 1, 5 CPUs, no CPU-frequency governor (virtual machine). Traffic: iperf3 UDP between a veth pair, one end in network namespace `p2ns` (`scripts/lab_up.sh`); the capture process is pinned to core 2, the iperf3 server to core 3, the main client to core 4, the noise client to core 1, core 0 and (outside flood runs) core 1 are the canaries. Configurations: A user-space `baseline_sniffer`; B eBPF filter with a draining loader; C the same without drain; D `reject_all` (floor); E `accept_all`. Each run is 10 s; the matrix is the frozen plan `results/bench_plan.tsv` (seed 20261018) at 32000 offered pps for the curves (K1 redefined, D6.9) and unlimited rate for the flood. A separate always-on classifier tap (identical for every config) splits every frame into data flow, iperf3 control and other, so the conservation rules V5'a-e can be checked on every run (`docs/phase6_addenda.md`). Rules, thresholds and verdict criteria were frozen before any run (`docs/phase6_design.md`, commit 3591267) and changed only by the dated addenda below. The session ran in the graphical desktop (`ENV.md`, D6.9); noise was handled by rule V8 and idle subtraction. Phases: 0 bootstrap and claims; 1 toolchain; 2 user-space baseline; 3 eBPF filter; 4 loader and map reader; 5 verifier stress test; 6 benchmark design, calibration and matrix; 7 this report.

## Results

Figures (`python3 scripts/reproduce_figures.py` regenerates them from the logs):

- `results/fig_cpu_cost.png`: per-packet CPU cost against packet size (reject curve, accept curve, flood); error bars are one standard deviation over valid repetitions.
- `results/fig_drop_rate.png`: capture-socket drop rate against offered load for the calibration ladders (quiet session and the first, busy-desktop session) and the flood runs.

Flood table (mean ± sd over valid runs; from `results/summary.md`): offered pps, flow-matched pps, net CPU ns per flow-matched packet (quiet calibration idle baseline), raw CPU ns per flow-matched packet.

| config | offered pps | flow-matched pps | net CPU ns / flow-matched pkt | raw CPU ns / flow-matched pkt | valid runs |
|---|---|---|---|---|---|
| A | 635995 ± 14556 | 315392 ± 7070 | 9943 ± 254 | 10357 ± 263 | 4 |
| B | 749805 ± 24128 | 273744 ± 11854 | 11149 ± 519 | 11627 ± 540 | 4 |
| C | 1038581 ± 69006 | 517389 ± 35359 | 5603 ± 414 | 5857 ± 432 | 4 |

Calibration (`results/calibration.json`, `docs/phase6_addenda.md`): config A lost no packets at any ladder step up to the top of the ladder at either frame size in the quiet session, while the first calibration (busy desktop, `logs/cal_v1_frozen_rules/`) saw drops from a few thousand pps. The iperf3 control connection contributes a constant 27 to 29 frames per run (V5'c envelope validated at 5 s and 10 s).

Historical comparison with the 1993 code: `results/comparison.md`. Verifier experiments (Phases 3 and 5): `docs/phase3_review.md`, `docs/phase5_analysis.md`.

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

   28 attempts were re-runs, and 13 final cells stayed contaminated and are excluded (listed in `results/exclusions.md`). An earlier reading of the first 21 plan rows suggested V8 itself was broken (experiment spilling onto the canary cores); the full run refutes that (D6.10).
2. **Noisy idle baseline.** The three idle windows taken at the start of the session fell in the noisy phase (0.843 CPU-s/s, canary 0.28 to 0.40 CPU-s/s on cores 0 and 1 against a V8 limit of 1.2 x 0.069) and V8 was not applied to idle windows, so net CPU came out negative. Mitigation: net CPU recomputed with the quiet calibration baseline (0.131 CPU-s/s) as ruled in D6.13; C2/C3 labels are unchanged by the swap, their numbers move by about 1% (the per-packet offset depends slightly on each run's offered rate). The original numbers are kept in `results/session_idle_baseline/`.
3. **Instrument cost.** The classifier tap adds a per-packet cost to every configuration, including the floor; it cancels in config differences and slopes but not in absolute CPU. The loader's one-per-second map reads are inherent overhead of config B (parity audit, `logs/parity_audit.log`).
4. **Sender-limited flood.** In-kernel filtering and classification run in the sending core's context, so the offered rate differs by configuration and "matched pps" in the flood measures the sender (D6.14). Config A was not saturated; its figure is offered-load-limited, not a ceiling.
5. **Socket drops at the curve rate.** 6 final runs failed V4 (drops above 0.1% for the consumer configs at the chosen rate), so some cells have fewer than three valid repetitions; points with fewer than two are INCONCLUSIVE.
6. **Single machine, single session per phase, virtual machine.** No repetition across boots; the first calibration and the matrix differ mainly in background load, which the report treats as a finding about measurement conditions, not as a replication result.
7. **Process incidents** recorded in `DEVIATIONS.md`: zero-length git objects after an environment restart (D6.5, repaired from origin, `git fsck` clean before and after every later commit) and a premature reading of V8 (D6.10).

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

## UNVERIFIED items

Each item was marked UNVERIFIED where it arose; nothing here is claimed as a result.

1. **C5 wording.** The phrase "code to the data" and any safety discussion do not occur in `paper.txt` (grep, `CLAIMS.md` C5); the C5 claim is an interpretation, and "ancestor of eBPF" is not a paper claim.
2. **How the paper's speed-up ranges were derived** (10 to 150 times over NIT, 1.5 to 20 over CSPF, paper.txt L29-30): they are stated only in prose (`CLAIMS.md` C4).
3. **Mechanism behind variant A loading** (`docs/phase5_analysis.md`): the verifier's own register state shows `R0=map_value` (not or_null) after both lookups, but the claim that this comes from array-map inlining with a constant in-range key is the reviewer's account and was not read from kernel source.
4. **`BPF_PROG_TEST_RUN` strips 14 bytes** for a socket filter (`DEVIATIONS.md` D3.4): supported by behaviour (prefix experiment), mechanism not read; the live AF_PACKET L2 view was confirmed empirically in Phase 4.
5. **Kernel ordering of filter and socket queue** (`docs/phase4_notes.md`): the counter equals tcpdump's count while the socket dropped almost every accepted packet, which supports "the filter counts before queueing"; the kernel source was not read.
6. **libbpf return conventions** of `bpf_program__fd`, `bpf_object__find_program_by_name` and `bpf_map_lookup_elem` are not documented in the installed headers and the failure paths were exercised only for interface lookup, object open and object load (`docs/phase4_notes.md`, `logs/p4_negatives.log`).
7. **tcpdump's default capture direction and whether `port N` includes SCTP/IPv6** (`docs/phase2_notes.md`): not in the man pages read; the runs showed agreement on this traffic.
8. **Why the calibration of this session found no knee** (D6.8): suspected quiet machine versus a busy desktop in the first calibration; one session each, not isolated.
9. **Cause of the zero-length git objects** (D6.5): an unflushed-write loss around an environment restart is assumed, not established.
10. **Softirq locus of the in-kernel filter** (`docs/phase6_design.md` section 7): assumed to be the sending core; the divergence of the offered rate between configurations is consistent with it, but no per-core attribution of the filter cost was made, so "sender-generation bottleneck" (D6.14) is an inference from offered rates.
11. **Classifier-tap overhead** was not measured separately; it is common to all configurations by construction.
12. **JIT output** was not inspected: `bpftool prog dump jited` is unsupported on this arm64 build (`ENV.md`), only `jited <n>B` from `prog show` is known.
13. **C1** (instruction counts, Fig. 8) and the **CSPF half of C4** are not evaluated; the user-space stack-machine interpreter was never built (sub-phase 6c).
14. **The 1993 code.** `reference/freebsd-src/sys/net/bpf_filter.c` is absent (D7.1), so every 1993-code `file:line` cell in `results/comparison.md` is UNVERIFIED; the 1993 side is described from the paper with `paper.txt` line citations only.

## Self-audit against CLAUDE.md

GROUNDING
- *Paper truth cites (paper.txt L<n>).* Followed in `CLAIMS.md` and the phase documents; quotes were checked against their cited lines by script in Phase 0 (`logs/phase0_quote_check.log`). Known gap: C5's wording is not in the paper (item 1 above).
- *Environment truth = ENV.md; re-probe when unsure.* Followed: ENV.md was re-probed after Phase 1 and extended in Phases 2, 3 and 6.
- *Oracle consultation recorded in DEVIATIONS.md.* tcpdump (D2.2) is recorded; no 1993-code file was consulted (D7.1).

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
- *Commit rule (re-run the verify script, one commit titled "Phase N: ...", never commit build artifacts or secrets).* Followed for Phases 1 to 5 (verify scripts re-run into `logs/*_rerun/`). Phase 6 used several commits by ruling (C1 to C6, all logged). `.gitignore` excludes `build/` and `*.pcap` (about 3 GB of captures stay local); a secrets scan ran before every commit.

## Reproducibility

See `README.md` (section Reproducibility).
