# Phase 8.2 design: is the flood's "offered load is limited by the sender" caused by the capture taps in the transmit path?

Status: written and frozen BEFORE any probe run, smoke run or measured run; its sha256 is logged in `logs/p8/p8_2/p8_2_design_sha256.log` before the first run. Any later change is a dated amendment at the end of this file, with the evidence that triggered it, written before the affected runs. Rule IDs below are new and start with `S` (sender) to avoid collisions with V1 to V8, K1, R-C2 to R-C4, M1, M2 of `docs/phase6_addenda.md`.

## 1. Question and background

Phase 6 flood runs (REPORT.md, threat 4; D6.12; D6.14) showed offered rates that differ by configuration: A 635995, B 749805, C 1038581 packets per second (REPORT.md flood table), so the flood "ceiling" measured the sender. The recorded explanation (D6.14, REPORT.md threat 4, UNVERIFIED item 10) is an inference: the in-kernel filter and the classifier run in the sending core's context. The short paper's perf profile of the iperf3 clients (`~/bpf-paper-short/data/perf/`, A and B only, read-only here, not used as data) points the same way. No configuration without a capture tap was ever measured, because the reviewer rejected a no-capture config N in Phase 6 (D6.1 item 4; `docs/phase6_design.md` section 1: "config D, as the floor, already removes the generation cost from the comparisons, and N would not be a paper control"). This phase reopens that rejection for a different purpose: N is the control that the sender-limit hypothesis needs, not a replication of a paper control. This is recorded as D8.11 in DEVIATIONS.md.

**Hypothesis under test (S0):** the capture taps (AF_PACKET sockets) run in the sender's transmit path and are what lowers the offered flood rate of A, B and C, i.e. removing the capture process and filter (config N) raises the offered rate by about the fraction of sender time that the taps use.

## 2. Configurations (all: flood, 256-byte frames, 10 s, two unlimited UDP streams)

Everything is as in `scripts/bench.sh one <cfg> flood 256 <rep> 0` (pinning: iperf3 clients on cores 4 (port 4040) and 1 (port 5050), iperf3 servers in namespace `p2ns` on core 3, capture process on core 2, classifier tap on core 0, system/bench on core 0; veth pair p1veth0 10.0.0.1 / p1veth1 10.0.0.2; pidstat, vmstat and `/proc/stat` snapshots as in the matrix), with these configurations:

| id | capture command (pinned to core 2) | meaning |
|---|---|---|
| **N** | none | iperf3 flood, the same two streams, the same classifier tap, **no capture process and no eBPF capture filter** |
| A | `build/baseline_sniffer p1veth0` | user-space copy-then-filter sniffer |
| B | `build/loader -d p1veth0 build/phase3_kern.o` | eBPF socket filter, draining loader |
| C | `build/loader p1veth0 build/phase3_kern.o` | same without drain |

The classifier tap (`build/classifier p1veth0`, A1 of `docs/phase6_addenda.md`) is present in **every** config including N, so the iperf3 control/data decomposition V5' can be checked on every run. Consequence: the classifier is itself an AF_PACKET tap, so N is "no capture tap other than the classifier", not "no tap at all" (see section 5, f_cap).

**Harness.** `scripts/bench.sh` is frozen (Phase 6) and has neither config N nor profiling. `scripts/p8_2_bench.sh` is a copy of it with only the changes needed for N, the profiler hook and the output location; the unified diff is saved in `logs/p8/p8_2/p8_2_bench_vs_bench.diff` and `scripts/p8_2_verify.sh` checks that the capture commands, pinning and iperf3 arguments of A, B and C are character-identical to `bench.sh`. This reads "A, B and C from the existing harness" as "the same harness code and commands", not literally the unmodified `bench.sh` binary (a modification of the frozen script is not allowed).

## 3. Runs

- **Unprofiled runs:** 6 repetitions per config (24 rows), of which at least 5 valid per config are required (rule S1).
- **Profiled runs:** 4 repetitions per config (16 rows), of which at least 3 valid per config are required (rule S1). Profiled runs are analysed separately and never enter the offered-rate statistics H1/H2 (section 6); they provide the sample shares f only.
- **Order:** all 40 rows in one seeded random order (seed 20261026) written by `scripts/p8_2_plan.py` to `results/p8_2_plan.tsv` before the launch; the file's sha256 is logged.
- **V8 re-run rule as in Phase 6** (`docs/phase6_addenda.md` section 2): an unprofiled run whose canary rate on core 0 (flood canary set) exceeds 1.2 x canary_max (`results/baseline_calibration.json`, canary_max {0} = 0.0369) is moved to `logs/p8/p8_2/attempts/` and repeated, at most 2 re-runs per cell; the last attempt is analysed, and a cell still contaminated is excluded. **Profiled runs are exempt from V8** (the profiler's collector process and the sampling itself load core 0, which would trip the canary); their quietness is covered by the pre-flight, by steal (V7) and by the sample-count rule S2.
- **Validity rules** for every run: V1, V2, V5'a to V5'e, V6, V7 exactly as implemented in `scripts/summarize.py` `parse_run` (imported, not copied). For N, V2 has nothing to check (no capture process, no map counters): the two reasons "V2 no FINAL line from the capture process" and "V2 map counters unreadable" are ignored for N and for N only, and `scripts/p8_2_summary.py` fails if any other reason is dropped.
- **Hands-off protocol and pre-flight:** the run script starts with a 60 s settle, then 3 idle windows of 10 s (config D attached, as in Phase 8.1); each window's canary rate on cores {0,1} must not exceed 1.2 x 0.0689 = 0.0826 CPU-s/s (the Phase 6 idle V8 limit) or the script aborts loudly before any measured run; `free -m` (memory and swap) is recorded before the pre-flight, after it and at the end; the pre-flight windows are not measured runs. The run is launched by the user from a Terminal tab; the assistant makes no tool call and prints nothing while it runs.
- **Expected duration:** 40 rows x about 24 s (10 s of traffic plus setup/teardown, as in Phase 6) plus re-runs, about 16 to 25 minutes, plus profile post-processing.
- **Excluded by pre-declaration:** the probe runs (`logs/p8/p8_2/probe/`, run once before the first measured run to check that perf, the tap symbol and the harness work; their numbers are not used for H1/H2) and the pre-flight windows.

## 4. Profiling

`perf record -e cpu-clock -F 997 -g -a -C 1,4 -o <file> -- sleep 10`, run as root, pinned to core 0, started when the first iperf3 client process appears (poll interval 20 ms) so that it covers the traffic window; the file stays in `build/p8_2/perf/` (untracked) and its sha256 is logged. `cpu-clock` is used because the guest has no hardware PMU (`logs/p8/p8_2/p8_2_perf_probe_nonroot.log`). Sender cores are 1 (noise client, port 5050) and 4 (match client, port 4040).

- **Sample set S** of a profiled run: all samples taken on CPU 1 or CPU 4 whose `comm` is not `swapper` (idle). A profile must contain at least 5000 such samples (rule S2) or it is invalid.
- **f_X(run)** = (samples in S whose call chain contains a frame named `packet_rcv`) / |S|. This is the short paper's definition ("weight of stacks containing packet_rcv, percent of all samples") restricted to the sender cores. The symbol name comes from the short paper's call graphs and is UNVERIFIED on this machine (CODE_NOTES.md Phase 8.2); if the probe shows another AF_PACKET handler in stacks (for example a ring-buffer variant), it is added by a dated amendment before the first measured run.
- Informational categories per profile, as in the short paper's figure code: stacks with `packet_rcv` (tap), stacks with `__udp4_lib_rcv`, `udp_queue_rcv_skb` or `__udp_enqueue_schedule_skb` (receiver-side UDP processing in the sender's context), others; plus the top comm/dso/symbol lines.
- Per config, **f_X** = mean of f_X(run) over the valid profiled runs, with a 95% t interval.

## 5. Hypotheses, prediction and verdicts (declared now)

Let offered(X) be the per-run total offered rate, packets per second summed over both streams (`parse_run` `offered_pps`: client-JSON packets / measured window), over the valid **unprofiled** runs of config X.

**S-H1.** offered(N) is above offered(A) and above offered(B): for X in {A, B}, the Welch 95% confidence interval of mean offered(N) - mean offered(X) (Satterthwaite degrees of freedom, exact Student t quantile) lies entirely above 0. Both must hold.

**S-H2 (quantitative prediction, made before any data).** If the capture tap work is a fraction f of the sender samples, removing it should raise the offered rate by 1/(1 - f): offered(N)/offered(X) is about P_X = 1/(1 - f_cap(X)), for X in {A, B}.

- **f_cap, why not the raw share.** The classifier is an AF_PACKET tap in every config, so `packet_rcv` stacks occur in N too (f_N > 0), and f_A counts the classifier's `packet_rcv` calls plus the capture socket's. Writing c for the sender cost per packet and assuming the classifier's per-packet cost is the same in N and A, the share removed by dropping only the capture tap is f_cap(X) = (f_X - f_N) / (1 - f_N), and 1/(1 - f_cap(X)) = (1 - f_N)/(1 - f_X). With f_N = 0 this is the raw formula. **The gating prediction uses f_cap**; the unadjusted prediction 1/(1 - f_X) is reported next to it for comparison (not gating). This choice is mine, made while writing this design, and is flagged to the reviewer.
- **Check.** R_X = mean offered(N) / mean offered(X). S-H2 holds for X when |R_X / P_X - 1| <= 0.25 (tolerance declared now, same for A and B). S-H2 holds iff it holds for both A and B. The same check for C is reported but does not gate.
- **Not evaluable:** if fewer than 3 valid profiled runs exist for N, A or B, or f_cap(X) >= 0.95, or f_cap(X) is negative with its whole 95% interval below 0, S-H2 is "not evaluable" and the verdict cannot be SUPPORTED.

**Verdicts (rule S3), evaluated in this order:**

1. **INCONCLUSIVE** (addition of mine to the three labels asked for, with the root cause stated): fewer than 5 valid unprofiled runs for N, A or B (rule S1) or fewer than 3 valid profiled runs for N, A or B (rule S1), or an invalid profile set (rule S2).
2. **NOT SUPPORTED** if S-H1 fails.
3. **SENDER-LIMITED SUPPORTED** if S-H1 holds and S-H2 holds.
4. **MIXED** if S-H1 holds and S-H2 fails or is not evaluable.

All numbers (means, standard deviations, confidence intervals of differences, R_X, P_X, f values, counts of valid and excluded runs with reasons) are produced by `scripts/p8_2_summary.py` from the logs only. Delta-method 95% intervals are given for R_X and for P_X (from the interval of f_cap); S-H2 itself is decided on the point estimates and the tolerance above.

Reported, not gating: offered(C); busy time of cores 1 and 4 during the runs (from the `/proc/stat` snapshots) per config, to show whether the sender cores are saturated in all configs, which the "sender-limited" reading needs; the profiling overhead (offered rate of profiled against unprofiled runs per config); the per-category shares; the unadjusted prediction.

## 6. Limits to state in any report

- Single host, a virtual machine (aarch64, 5 vCPUs), a veth pair instead of a NIC, one session, randomised order but no repetition across boots.
- Sampling: the guest has no hardware PMU, so perf samples come from a timer (`cpu-clock`). How much this skews samples taken in softirq or interrupt-disabled sections is not known here (UNVERIFIED); shares f are samples, not exact times.
- The profiler perturbs what it measures, so profiled runs are analysed separately and f is measured under profiling but applied to unprofiled offered rates (an assumption).
- The classifier tap is in every config; f_cap assumes that its per-packet cost is the same in N and in A/B (not tested).
- The prediction assumes the sender cores are CPU-saturated in all configs and that the removed work is serial in the sender context; the busy-time rows show whether the first holds.
- The result is about the configurations and the load of this harness (iperf3 UDP, 256 B), not about taps in general.

## 7. Files

`scripts/p8_2_bench.sh` (harness copy), `scripts/p8_2_plan.py`, `scripts/p8_2_probe.sh` (root probe, excluded runs), `scripts/p8_2_run.sh` (launcher: settle, pre-flight, plan, V8 re-runs, profile post-processing), `scripts/p8_2_perf_counts.py` (perf script to counts), `scripts/p8_2_summary.py` (statistics, verdict), `scripts/p8_2_verify.sh`; outputs `logs/p8/p8_2/`, `results/p8_2_*`.

## 8. Amendments

- **A1 (2026-10-26, after the probe and before the first measured run; evidence: `logs/p8/p8_2/p8_2_probe_console.log`, `logs/p8/p8_2/probe/counts_{N,A,B,C}.json`, first attempt `logs/p8/p8_2/p8_2_probe_console_attempt1_perf_owner_error.log`).** The probe (one 4 s profiled flood per config, excluded from analysis) checked the tooling; no rule, threshold, tolerance, hypothesis or verdict criterion changes. Findings that fix open points of this document:
  1. **Tap symbol (section 4):** the AF_PACKET-related frames in the non-idle samples of the four probe profiles are `dev_queue_xmit_nit`, `packet_rcv`, `skb_scrub_packet` and, once, `__skb_wait_for_more_packets`; no `tpacket_rcv` or other receive handler occurs. The tap symbol stays exactly `packet_rcv` (the UNVERIFIED mark in CODE_NOTES.md is resolved for this machine: the symbol occurs in A, B, C and, from the classifier alone, in N).
  2. **Idle task name (section 4):** the idle samples on the sender cores have `comm` exactly `swapper` in all four profiles; the rule "comm is not `swapper`" is therefore implemented literally (`swapper` and `swapper/N` are both treated as idle in `scripts/p8_2_perf_counts.py`, which makes no difference here).
  3. **Harness fix (section 2):** the first probe attempt failed in all four configs at `perf script` ("not owned by current user or root") because the copied `fix_owner` chowned the perf directory to the invoking user. `scripts/p8_2_bench.sh` now chowns only its log directory; the perf data stay root-owned until the run script finishes. The regenerated diff against `bench.sh` is in `logs/p8/p8_2/p8_2_bench_vs_bench.diff`.
  4. **Informational additions:** `scripts/p8_2_perf_counts.py` also counts the samples whose `comm` is `iperf3` and, among them, those with `packet_rcv` (`S_iperf3`, `tap_iperf3`), because other tasks (desktop processes) also appear on the sender cores; the gating definition of f (all non-idle samples of S) is unchanged.
  5. The sha256 of this file after the amendment is appended to `logs/p8/p8_2/p8_2_design_sha256.log`; `scripts/p8_2_run.sh` refuses to start unless the file matches the last logged value.

- **A2 (2026-10-26, approved by the user in chat: "A2 approved as drafted"; written after run set 1 and before run set 2; the sha256 of this file after the amendment is appended to `logs/p8/p8_2/p8_2_design_sha256.log`).** Repeat run under the same pre-declared rules; all rules, hypotheses, tolerance, thresholds, sample minima and verdict logic of sections 1 to 6 stand. The draft's text follows (the gate options 4a to 4c are chosen by the user before the launch and recorded in the run set 2 console log).

### A2 evidence (all from run set 1 in `logs/p8/p8_2/`, `results/p8_2_summary.md`, and post-hoc read-only diagnostics `logs/p8/p8_2/p8_2_diag_*.log`)

1. **Run set 1 verdict: INCONCLUSIVE** by the pre-declared rule S3: unprofiled A 0 of 6 valid, B 0 of 6 valid, because every A and B run exceeded the V8 limit on the flood canary core 0 (A 0.114 to 0.216, B 0.119 to 0.272 CPU-s/s; limit 0.0443). N had 5 and C 4 valid runs. The pre-flight passed (canary {0,1} 0.055 to 0.070 against 0.0826).
2. **Core 0 under load, run set 1:** mean busy CPU-s/s of core 0 over the six final unprofiled runs: N 0.062, A 0.144, B 0.164, C 0.050. **Phase 6 flood runs** (`logs/bench_*_flood_256_*.log`): A 0.709, 0.025, 0.040, 0.018, 0.030; B 0.062, 0.033, 0.032, 0.025, 0.032; C 0.515, 0.016, 0.009, 0.008, 0.010. So Phase 6 had the same configs with core 0 mostly at 0.01 to 0.04; run set 1 had B and A at 0.11 to 0.27.
3. **The clearest difference of the machine state:** swap in use during the flood runs, from `vmstat`: run set 1 about 3.6 to 3.7 GB (`swpd`), Phase 6 about 1.2 GB; free RAM about 100 to 175 MB against about 220 MB; swap in use grew from 3718 MB to 3984 MB of 4095 MB over the run (`logs/p8/p8_2/run_context.txt`). Swap I/O rates themselves were small (so 0 to 179 KB/s), and B had so = 0 with core 0 at 0.164.
4. **Sender profiling windows:** 3 of 16 profiled runs failed V6 (measured window 12.26 to 12.43 s, outside dur-1..dur+2): A rep 3, C rep 1, C rep 4. In `scripts/p8_2_bench.sh` the wait for `perf record` to finish (data flush) sits before the closing `/proc/stat` snapshot, so it lengthens the window.
5. **Reporting wording:** `results/p8_2_summary.md` prints "S-H1 does not hold" when A and B have no valid unprofiled runs; S-H1 was not evaluable, and the verdict line (INCONCLUSIVE) was right.

**Causes are not established (UNVERIFIED).** Two hypotheses for the core-0 load in A and B: (H-mem) memory pressure (page reclaim by `kswapd0`, `kcompactd0` or kernel workers, which are not pinned and can run on the least busy core, core 0) from the swap-heavy state; (H-cfg) work specific to A and B (the capture process wakeups and the load balancer moving other tasks to core 0 while cores 1, 3 and 4 are saturated), which would also have shown in Phase 6 and does not explain B's rise from 0.03. The data above fit H-mem better for B and fit neither fully; no task-level attribution of core 0 was recorded.

### A2 changes for run set 2 (rules, hypotheses, tolerance, thresholds, sample minima and verdict logic of the design stay exactly as declared)

1. **Same pre-declared rules, new run set.** Plan `results/p8_2_plan_run2.tsv`, seed 20261027 (6 unprofiled + 4 profiled per config, 40 rows, random order); its sha256 is logged before the launch. Outputs go to `logs/p8/p8_2/run2/` and `results/p8_2_summary_run2.{md,json}`; run set 1 files are not touched and stay the record of the first run. **The two run sets are never pooled** and each gets its own verdict; there is **at most one repeat** (no run set 3 without a new amendment), so that a verdict cannot be chosen by repeating until it looks right.
2. **Quieter state before the launch (user actions, recorded):** close Firefox and every other large application except the Claude app; then check `free -m`. Swap in use cannot be released by closing applications, so the memory state is handled by a gate and a choice (3 and 4).
3. **New pre-flight gate (environment, not a validity rule of a run):** `scripts/p8_2_run.sh` aborts loudly before the settle if swap in use exceeds **2000 MB** (Phase 6 flood runs: about 1224 MB; run set 1: 3600 to 3700 MB) or if `MemAvailable` is below 1500 MB. The gate level is a judgement from two data points, not a tested threshold. `free -m` and `/proc/pressure/{cpu,memory,io}` are recorded before and after.
4. **How to get below the gate (user's choice, nothing is done by the assistant):** (a) **reboot the VM**, the cleanest and also the Phase-6-like state (ends the Claude desktop session once; the repeat then starts from a fresh boot with only the Claude app, which is a documented change of condition); (b) `sudo swapoff -a && sudo swapon -a` after closing Firefox, **only** if `MemAvailable` exceeds swap in use by at least 1000 MB (otherwise it risks the out-of-memory killer; with 3.7 GB in swap it probably does not qualify); (c) run without meeting the gate is not allowed by the script (no waiver option), so the alternative is to accept INCONCLUSIVE as the Phase 8.2 outcome.
5. **Instrumentation added so that the cause can be seen this time (informational, no rule depends on it):** in the opening and closing `/proc/stat` snapshot of every run, `scripts/p8_2_bench.sh` also records (a) the cumulative user+system ticks of every task with non-zero ticks together with the CPU it last ran on (`/proc/<pid>/stat` fields utime, stime, processor), and (b) `/proc/pressure/{cpu,memory,io}`. These lines are ignored by the existing parser; a new read-only script `scripts/p8_2_diag_core0.py` attributes the core-0 busy time per task and per config by differences. The extra reads happen outside the traffic window, once per snapshot.
6. **Harness fix (profiled runs only):** the closing `/proc/stat` snapshot is taken immediately after the clients finish, and the wait for `perf record` moves after it, so that perf's data flush no longer lengthens the measured window (item 4 of the evidence). Unprofiled runs are unaffected; the saved diff against `bench.sh` is regenerated and its parity checks stay.
7. **Wording fix in the summary:** when S-H1 cannot be evaluated because A or B has fewer than 2 valid unprofiled runs, `scripts/p8_2_summary.py` prints "S-H1 is not evaluable (A: n valid unprofiled runs; B: n ...)" instead of "does not hold"; "does not hold" is printed only when both differences were computed and at least one lower bound is not above 0. Verdict logic (rule S3) is unchanged.
8. **Scripts parametrized by run set** (`P8_2_RUN=run2` selects the plan file, output directories and summary names; default stays run set 1 so that `scripts/p8_2_verify.sh` still verifies run set 1); the verify script gets a run-set 2 mode with the same checks plus: the gate lines in the console log, and the run set 1 files unchanged (hash comparison).

### A2 not changed, deliberately

- V8 (limit 1.2 x canary_max on core 0 for flood runs), the canary_max value and the exemption of profiled runs: relaxing V8 after seeing that it excluded A and B would be a post-hoc change in favour of getting data; the repeat tests whether a quieter machine yields valid runs under the same rule.
- H1, H2, the 25% tolerance, f_cap, the sample minima (5 unprofiled and 3 profiled valid per config) and the verdict rules.

### A2 exploratory, not part of any verdict (post hoc, from run set 1, `logs/p8/p8_2/p8_2_diag_exploratory_offered.log`)

Offered rate including the V8-excluded runs: N 1.15 M, A 0.92 M, B 0.82 M, C 1.11 M packets per second (sd 26 to 35% of the mean in each config); with profiling: N 1.11 M, A 0.65 M, B 0.83 M, C 0.77 M. The spread is large compared with the differences, so these numbers do not decide S-H1 and are not used for it.
