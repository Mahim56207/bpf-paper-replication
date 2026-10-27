# Phase 8.2: findings (is the flood's offered load limited by the capture taps in the sender's transmit path?)

Numbers in backticks are copied from `results/p8_2_summary_run2.md` (computed by `scripts/p8_2_summary.py` from `logs/p8/p8_2/run2/` only), from `results/p8_2_summary.md` (run set 1), or from the logs named next to them; `scripts/p8_2_verify.sh` checks that each of them occurs in those files. Rules, hypotheses and tolerances are those of `docs/phase8_2_design.md` (hash chain in section 5 below).

## 1. Verdict and the size of the evidence

**SENDER-LIMITED SUPPORTED** under the pre-declared rules (S-H1 and S-H2 hold), on run set 2 only (section 4). Offered rate, packets per second summed over both streams, mean of 6 valid unprofiled runs per config: N (no capture process, no eBPF capture filter) `2047448`, A `1231731`, B `1403339`, C `2016726`. Every cell of run set 2 was valid (6 of 6 unprofiled, 4 of 4 profiled per config); 3 V8 re-runs.

- **S-H1 holds strongly.** N minus A is `815717` packets per second with a 95% interval of [`720267`, `911168`]; N minus B is `644109` with [`552013`, `736206`]. Both lower bounds are far above 0.
- **S-H2 holds only inside the pre-declared 25% tolerance, with the observed ratios above the prediction.** The prediction P = 1/(1 - f_cap), with f_cap taken from the share of sender samples that have `packet_rcv` in the stack (A `0.2633`, B `0.1848`; f for N, the classifier tap alone, is `0.0475`), is `1.357` for A and `1.227` for B. The observed ratios offered(N)/offered(X) are `1.662` and `1.459`, that is `+22.5%` for A and `+18.9%` for B above the prediction, both inside the tolerance and both on the same side. The unadjusted prediction (1/(1 - f_X)) is closer (`+16.6%` and `+13.3%`). So the **size** of the effect is only approximately explained by the tap's share of samples: removing the capture work raised the offered rate by more than its sample share alone predicts. Why was not investigated; candidates (not tested) are costs that sampling does not charge to `packet_rcv` frames (cache and wake-up effects on the sender core), the timer-based sampling without a hardware PMU, and the profiling itself.
- **f was measured under profiling but applied to unprofiled rates.** Profiled runs are analysed separately and perturb the system: the ratio of mean offered rate profiled/unprofiled is `0.978` for N, `1.026` for A, `1.038` for B and `0.935` for C, i.e. the perturbation is of different size and sign by config. Transferring f from the profiled to the unprofiled runs is an assumption of the design, not a measurement.
- Where the tap work is spent: among the samples whose task is `iperf3` on the sender cores (cores 1 and 4), the share with `packet_rcv` in the stack is `0.2984` for A, `0.2236` for B and `0.0690` for C, against `0.0475` for N (informational column of section 4 of the summary). So the capture work is executed in the sending process's context, which is the mechanism the hypothesis names. The sender cores are saturated in every config (busy `0.998` CPU-s/s per core), which the prediction needs.

## 2. C is not different from N

N minus C is `30723` packets per second with a 95% interval of [`-28070`, `89515`], which includes 0 (not a gating test). C is the same eBPF filter as B without the draining reader; its offered rate equals that of N, while B, which has a reader, offers `644109` fewer packets per second than N. That is consistent with the extra sender cost being the per-packet delivery to a reader (queue insertion and wake-up of the reader) and not the execution of the filter, since the filter also runs for every packet in C. This is an interpretation of one contrast, **not a tested cause**: the wake-up cost was not measured separately, and C differs from B in other ways too (its socket buffer fills and packets are dropped at insertion).

## 3. Limits

Single host, a virtual machine, a veth pair instead of a NIC, one boot, iperf3 UDP at 256-byte frames; `cpu-clock` timer sampling because the guest has no hardware PMU, with skew that was not measured (UNVERIFIED); the classifier tap is in every config, so f_cap assumes its per-packet cost is the same in N and in A or B (not tested); the prediction assumes serial, removable tap work and saturated sender cores. The result is about this harness and these configurations, not about packet taps in general. Run set 2 was run after closing Firefox, LibreOffice, Files and Settings, with the Claude desktop app open; the core-0 attribution (`results/p8_2_diag_core0_run2.md`) shows core 0 busy at `0.016` CPU-s/s for N and `0.036` for A, mostly the desktop app and gnome-shell.

## 4. History of the two run sets (the verdict rests on run set 2 alone)

- **Run set 1** (first run, same plan structure, seed 20261026) ended **INCONCLUSIVE**: 0 valid unprofiled runs for A and B (every one exceeded the V8 limit on core 0), 5 for N and 4 for C (`results/p8_2_summary.md`). Its **raw logs, profiles and perf data were deleted by a wrong launch** (the run set 1 command was run again instead of the run set 2 command, D8.14) and cannot be recovered; only the summary computed before the loss and the diagnostics derived from the logs survive, so run set 1 can no longer be re-verified. **The two run sets are not pooled**, and run set 1 contributes no number to the verdict.
- **Cause of the contamination in run set 1 is not identified.** A candidate is the memory state: swap in use was about `3718` MB at the start and `3625` to `3694` MB (vmstat means by config, `logs/p8/p8_2/p8_2_diag_vmstat_core0.log`) during the runs, against `1524` MB at the run set 2 gate. This was **not tested**: run set 2 differs from run set 1 in several ways at once (swap, closed applications, the A2 changes to the harness and the instrumentation), so it cannot say which one mattered. Run set 1 had no task-level data.
- Amendment A2 (written after run set 1, approved by the user) allowed exactly one repeat; it was used.

## 5. Design hash chain and amendments (script-computed by `scripts/p8_2_design_chain.py`, log `logs/p8/p8_2/p8_2_design_chain.log`)

The design file was amended twice, so the file as it is now is **not** the file whose hash was logged first. What the script confirms: the text as first written (sections 1 to 7 plus an empty amendment section) hashes to the first logged value, which was logged before the first probe and before any measured run; sections 1 to 7 were never edited afterwards (all three logged values are reproduced from the current file by cutting section 8); and the file now equals the last logged value, which was logged before run set 2.

```
# design hash chain (script-computed) 2026-10-26T15:11:25+05:30
MATCH: 1st logged hash = the design as first written (sections 1 to 7 unchanged, section 8 'none yet')
    reconstructed 4e96624e542fb724e60f8f3f40be48d956fc8b4afacf29a01b3409a9d7693d94
    logged        4e96624e542fb724e60f8f3f40be48d956fc8b4afacf29a01b3409a9d7693d94
MATCH: 2nd logged hash = the design after amendment A1
    reconstructed 90da1138af21b436f87f136728d0f00cc269c5a0eb900597aee23206b7abaf28
    logged        90da1138af21b436f87f136728d0f00cc269c5a0eb900597aee23206b7abaf28
MATCH: 3rd logged hash = the design after amendment A2 = the file now
    reconstructed 2e6becd9679930d5865667c4f576b3a7523b3b0be5269494e82cddabf1f86c19
    logged        2e6becd9679930d5865667c4f576b3a7523b3b0be5269494e82cddabf1f86c19
sections 1 to 7 are byte-identical in all three versions by construction of the reconstruction; the first check proves they equal the first logged text.

amendments in section 8 (id, date, first sentence):
  A1  2026-10-26  The probe (one 4 s profiled flood per config, excluded from analysis) checked the tooling;
  A2  2026-10-26  Repeat run under the same pre-declared rules;

logged times of the hashes: 2026-10-26T13:59:02+05:30 | 2026-10-26T14:08:44+05:30 | 2026-10-26T14:40:50+05:30
OK: first hash logged 2026-10-26T13:59:02+05:30, earliest probe start (excluded runs) 2026-10-26T14:01:58+05:30
OK: first hash logged 2026-10-26T13:59:02+05:30, run set 2 start 2026-10-26T14:51:59+05:30
hash-chain check: 0 problem(s)
```

Amendments (date; reason):
- **A1, 2026-10-26** (after the probe, before any measured run): the probe showed the tap symbol is exactly `packet_rcv` (no other AF_PACKET receive handler) and that idle samples are named `swapper`, so the definitions stayed; the harness copy no longer chowns the perf directory (the first probe attempt failed at `perf script`); informational iperf3-only sample counts added. No rule changed.
- **A2, 2026-10-26** (after run set 1, before run set 2): run set 1 was INCONCLUSIVE; one repeat under the same rules with its own plan and outputs, never pooled; memory gate (swap in use at most 2000 MB, MemAvailable at least 1500 MB); task-level and pressure-stall instrumentation; the `perf record` wait moved behind the closing snapshot (3 of 16 profiled runs of run set 1 failed V6, a window longer than allowed; the order of the wait in the script was the suspected cause, not separately tested); corrected S-H1 wording. No rule, threshold, tolerance, sample minimum or verdict logic changed.

Other records: D8.11 (N reopens D6.1 item 4; harness copy; f_cap; V8 exemption of profiled runs; INCONCLUSIVE label), D8.12 (run set 1), D8.13 (correction to A2 item 4: closing applications does release swap), D8.14 (the wrong launch), D8.15 (run set 2 and two corrections to the verify script) in `DEVIATIONS.md`.
