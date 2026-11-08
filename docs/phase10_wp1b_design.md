# Phase 10 WP1b: long-batch re-measurement of C2 and C3 (design)

Status: written and frozen BEFORE any WP1b run (smoke, pilot or main); its sha256 and the time of logging are in `logs/p10/p10_wp1b_sha256.log`, together with the hashes of the plans, tool sources and run scripts it governs. It is an addition to `docs/phase10_design.md` (version 2, hash 1fdc98a3d9dd6cb3, which is not edited) and changes nothing in it except what section 2 lists. Rule numbers P1 to P13 are those of that document.

## 1. Why WP1b exists (evidence from the original WP1 logs, read-only diagnosis `scripts/p10_wp1_diag.py`, output `logs/p10/wp1_diag/diag.txt`)

The original WP1 (block B1 of the first run) gave C2 and C3 the label INCONCLUSIVE: 169 of 350 final batches were invalid after at most two re-runs, because 632 of 813 attempts exceeded the block's canary limit. The label is kept (section 4). The diagnosis of the logs showed:

- **The batches were very short.** The tools were written for 20 million `memcpy` calls, 3 million test-run repetitions and 20 000 drained frames; on this machine that is a median tool time of 0.033 s (shortest 0.0083 s). The canary window (two `/proc/stat` snapshots around the tool invocation) had a median of 0.096 s, a minimum of 0.050 s and a maximum of 2.728 s; only 10 of 813 windows were 1 s or longer. The design of `docs/phase10_design.md` section 4 named repetition counts but no minimum duration.
- **The canary has a granularity of 10 ms.** `/proc/stat` busy time is counted in ticks of 0.01 CPU-s (`os.sysconf("SC_CLK_TCK")` = 100). The canary limit of block B1 was 0.1018 CPU-s/s (1.2 x the largest of three idle windows, 0.0848, over cores 0, 1, 3 and 4). One tick therefore exceeds the limit in any window shorter than 0.01 / 0.1018 = 0.098 s. 441 of the 813 windows were shorter than that, and 417 of those 441 failed; 24 passed with zero ticks.
- **Failure rate falls with window length only partly:** 0.913 for windows below 0.25 s, 0.538 for 0.25 to 0.5 s, 0.583 for 0.5 to 1 s (n 309, the drain batches). Of the 632 failing attempts, 222 exceeded the limit by less than one tick and 356 by less than two ticks; 121 by five ticks or more.
- **A per-attempt fixed cost of about 2 ticks:** an ordinary least-squares fit of busy ticks against window length over the windows below 1 s gave an intercept of 1.93 +- 0.31 ticks and a slope of 10.5 +- 0.8 ticks per second (0.105 CPU-s/s), against pre-flight idle windows of 0.071 to 0.085 CPU-s/s. A fixed cost of this size is what the harness itself would add (the second snapshot is taken by a freshly started `python3`, inside the window); that reading is UNVERIFIED, no run isolated it.
- **Hypothesis B (real background load) is neither shown nor excluded.** The slope 0.105 +- 0.008 is above the idle windows, which would be consistent with background load or with activity caused by the measurement itself; UNVERIFIED which. The failure rate by decile of the plan sequence was 0.59 to 0.91 with no clear episode. WP1b is designed so that it does not need this question answered: with windows of at least 5 s one tick is at most 0.002 CPU-s/s and a fixed cost of 2 ticks is about 0.004 CPU-s/s, 4% of the limit of block B1.
- The limits "about 0.018 and 0.012 CPU-s/s" mentioned when this work was requested do not appear in the WP1 logs: the limit of the WP1 canary was 0.1018 CPU-s/s summed over four cores.

## 2. What does not change, and what does

**Unchanged, frozen from `docs/phase10_design.md`:**
- The V8 rule and its window definition: the canary rate is the summed busy CPU-s per second of the cores 0, 1, 3 and 4 between two `/proc/stat` snapshots taken immediately before and after the tool invocation (busy = user + nice + system + irq + softirq + steal; `scripts/p10_canary.py`); the block's limit is 1.2 x the largest canary rate of its own three pre-flight idle windows of 10 s (section 8 of that document); a batch above it is re-run at most twice and is then excluded (rule P3). The pre-flight idle limit (0.0826 CPU-s/s per two cores), the 60 s settle and the memory gate are unchanged.
- delta = 10 ns/byte; the 90% Student-t interval of an ordinary least-squares slope; slope classes (rule P1); the difference of independent slopes with Welch-Satterthwaite degrees of freedom; rules P4 (C2) and P5 (C3) exactly as written; the 1993 comparison ratios (descriptive).
- Sizes 64, 256, 512, 1024, 1500; the same paths and programs (`memcpy`; `reject_all`, `accept_all` of `build/phase6_filters.o`; `phase3_filter` of `build/phase3_kern.o`; drain paths U, E and B), the same frame, the same `retval` checks and the same drain validity rule (`tp_drops` = 0 and `tp_packets` = N in every cycle).
- The quantity that carries each label is the one of the original WP1: `memcpy` wall ns per call, the kernel-reported average `duration` of `bpf_prog_test_run_opts` (mean over the calls of a batch), and the drain wall ns per packet.

**Changed (and only this):**
- **Batch length.** Every batch measures for at least **5.0 s** of wall time: `p10b_memcpy` repeats chunks of 5 000 000 calls, `p10b_testrun` repeats `bpf_prog_test_run_opts` with `repeat` = 3 000 000 per call (so the total number of repetitions is raised by the number of calls), until the accumulated wall time of the chunks or calls reaches 5.0 s; `p10b_drain` repeats refill-and-drain cycles of N = 20 000 frames (send, 300 ms settle, read `PACKET_STATISTICS`, drain to `EAGAIN`) until the cycle loop has run for 5.0 s, checking in every cycle that `tp_drops` = 0, `tp_packets` = N and that N frames were received and matched (the receive buffer is forced to 256 MB and its read-back value is recorded; N frames of 1500 bytes occupy far less than that); the first invalid cycle ends the batch with exit status 3.
- **Two clocks.** Each tool records wall time (`CLOCK_MONOTONIC_RAW`) and thread CPU time (`CLOCK_THREAD_CPUTIME_ID`) over the same measured intervals. The measuring thread is pinned to core 2, which the canary does not include and nothing else of the harness uses; the busy rate of core 2 over each window is recorded next to the canary rate (reported, not gated). In `p10b_drain` only the drain loops are timed (as in WP1); the refill is not.
- **Replication.** 12 planned batches per (path, size) in randomized order; the minimum number of valid batches per (path, size) is raised from 8 to **10**; a cell with fewer makes the quantity, and every label that needs it, INCONCLUSIVE with the cause printed (rule P3). All valid batches are used.
- A batch is additionally invalid if its measured wall time is below 5.0 s (this cannot happen with the tools; it is checked).
- **Pilot** (section 6) and **smoke stage** (section 7), both excluded from every verdict.

## 3. Tools and commands (sources in `src/p10/`, built by `scripts/p10b_build.sh`, hashes in the log)

| path | tool and arguments | RESULT columns |
|---|---|---|
| memcpy | `p10b_memcpy size 5.0 2` | `size,total_iters,chunks,ns_per_call_wall,ns_per_call_cpu,wall_s,cpu_s` |
| reject_all / accept_all / phase3_filter | `p10b_testrun obj prog size 3000000 expect 2 5.0` | `size,repeat,calls,total_reps,duration_mean_ns,wall_ns_per_rep,cpu_ns_per_rep,wall_s,cpu_s,retval` |
| drain U / E / B | `p10b_drain path size 20000 2 5.0` | `path,size,N,cycles,received,tp_packets,tp_drops,matched,rcvbuf,drain_wall_ns,drain_cpu_ns,ns_per_packet_wall,ns_per_packet_cpu,loop_wall_s` |

Primary metric (the label-carrying one): memcpy column 4 (`ns_per_call_wall`), test run column 5 (`duration_mean_ns`), drain column 12 (`ns_per_packet_wall`), counting from 1. Thread-CPU metric (sensitivity): memcpy column 5, test run column 7, drain column 13. `scripts/p10b_wp1.sh` runs the plan rows, writes one log per attempt (`b<seq>_a<n>.log` with RESULT, RC, STDERR and the CANARY line including `core2_rate` and `min_s`), re-runs a contaminated or invalid batch at most twice and aborts the whole run on any other tool failure. No output is sent to /dev/null.

## 4. Labels and the old WP1 numbers

C2 and C3 are labelled by rules P4 and P5 from the WP1b main block only (pilot, smoke and the original WP1 batches are not pooled with it). `scripts/p10_summarize.py` (function `wp1b`, `verdict_c2`, `verdict_c3`) computes the labels; the same rules are applied to the thread-CPU metric and printed as a sensitivity result (no label of its own); the summary also prints the original WP1 labels (computed from `logs/p10/wp1/` by the unchanged WP1 code, label INCONCLUSIVE with its cause) in rows named "C2 (WP1 original)" and "C3 (WP1 original)", and the first summary files are kept unchanged as `results/p10_summary_before_wp1b.md` and `.json` (sha256 in the log). The label printed for C2 and C3 in the final table is the WP1b label, whatever it is; there is no second repeat of WP1b. `scripts/p10_check_labels.py` re-derives all of them; `scripts/p10_verify.sh` checks the WP1b hashes, the pilot statement, and that no typed number or narrative sits in a verdict string (rule P13).

## 5. Plans (`scripts/p10b_plan.py`, seed 20261108, streams 4 to 6; sha256 logged when written)

- `results/p10_plan_wp1b_smoke.tsv`: 7 rows (one per path, size 256), run with a batch length of 0.4 s and no canary limit, to prove the tools and the scripts work before any block; checked by `scripts/p10b_check_smoke.py`; outputs in `logs/p10/wp1b_smoke/`; excluded from every verdict; any failure aborts before the pilot.
- `results/p10_plan_wp1b_pilot.tsv`: 105 rows (7 paths x 5 sizes x 3 batches), randomized; outputs in `logs/p10/wp1b/pilot/`.
- `results/p10_plan_wp1b.tsv`: 420 rows (7 x 5 x 12), randomized; outputs in `logs/p10/wp1b/main/`.

## 6. Pilot and the expected slope precision

The pilot is a block of its own (60 s settle, memory gate, pre-flight idle windows that must pass V8, then its 105 batches at 5.0 s) run before the main block. Its batches are excluded from every verdict. After it, `scripts/p10b_pilot_precision.py` fits cost against size for each path on the valid pilot batches and prints, computed and not typed: the residual standard deviation, the standard error of the slope that the main plan (10 valid batches at each of the five sizes, same spread) would have, the half-width of the 90% interval (Student t with 48 degrees of freedom), its ratio to delta, the half-widths expected for d = s_U - s_K (C2) and e = s_U - s_E (C3), and the fraction of pilot attempts that failed the canary (the expected re-run burden). **This statement is informational: nothing in the main block depends on it. Sizes, batch length, plan and rules are fixed here; if the statement shows a half-width above delta, the run continues and the label that results is the label.** The statement is written to `logs/p10/wp1b/pilot_precision.txt` before the main block starts.

## 7. Run protocol and time

One command, `sudo bash scripts/p10b_run.sh 2>&1 | tee logs/p10/p10b_run_console.log`, from a fresh Terminal tab; I make no tool call while it runs. Stages: `scripts/p10b_pre.sh` (hashes, tools built, scripts parse, memory gate), smoke stage, pilot block, precision statement, main block. The run refuses to start if `logs/p10/wp1b`, `logs/p10/wp1b_smoke`, `logs/p10/run_wp1b` or `logs/p10/preflight/wp1b_*` exist and are non-empty, and aborts on the first failing step. Estimate of the hands-off time (UNVERIFIED until run): about 0.3 min smoke, 1.6 min for each of the two pre-flights, 105 and 420 batches at about 5.6 s each (9.8 and 39 min), plus re-runs; I expect 65 to 80 minutes in all.

## 8. Rules for changes

Any change to a definition above after data have been seen is a dated amendment in section 9 with the old numbers kept next to the new ones, and a new logged hash. Proposals that would change V8, delta or the verdict rules are not applied; they are written as proposals with evidence and put to the reviewer.

## 9. Amendments

none yet
