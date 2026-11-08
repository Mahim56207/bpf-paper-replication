# Why config N offered about 2.05 million pps in Phase 8.2 and about 421 thousand pps in the Phase 10 baseline topology

Read-only note. Nothing was re-run; every number comes from existing logs and result files through `scripts/p10_baseline_note_probe.py` (output: `logs/p10/p10_baseline_offered_load_analysis.log`) or from the files cited. "WP2(a) T0" is the baseline topology of `docs/phase10_design.md` section 5.1.

## The two numbers

| quantity | Phase 8.2, run set 2, config N | Phase 10 WP2(a), T0, config N | source |
|---|---|---|---|
| mean offered pps (classifier total over 10 s) | 2053399 | 422362 | `logs/p10/p10_baseline_offered_load_analysis.log` lines 2 and 5 (from the `CLS` line of each run log, e.g. `logs/p8/p8_2/run2/runs/p82_N_flood_256_1.log:9` and `logs/p10/wp2a/p10aT0_N_flood_256_1.log:10`) |
| the same as published (client packets per second, summed over both streams) | 2047448 | 420816 | `results/p8_2_summary_run2.md:20` and `results/p10_summary.json` (`wp2a.cells.T0_N.mean`) |
| per stream (4040, 5050) | 1023562, 1029832 | 210917, 211440 | `logs/p10/p10_baseline_offered_load_analysis.log` lines 2 and 5 |
| ratio | | | 2053399 / 422362 = 4.86 (arithmetic on the two rows above) |

## What differs, setting by setting

| setting | Phase 8.2 value | WP2(a) value | source file:line |
|---|---|---|---|
| core of the client of the noise stream (port 5050) | core 1 | **core 4** (same core as the match client) | `scripts/p8_2_bench.sh:34` and `scripts/p10_bench.sh:29`; run-log header line 3 of `logs/p8/p8_2/run2/runs/p82_N_flood_256_1.log` (`cli_match=4 cli_noise=1`) and of `logs/p10/wp2a/p10aT0_N_flood_256_1.log` (`cli_match=4 cli_noise=4 rps=1 sys=0`) |
| cores that are saturated during a config N run (busy CPU-s/s, mean of 6 runs) | core 1 1.000, core 3 0.998, core 4 1.001 (cores 0 and 2 about 0.015) | core 4 1.001, core 3 0.282 (cores 0, 1, 2 below 0.01) | `logs/p10/p10_baseline_offered_load_analysis.log` lines 3 and 6 (from the `/proc/stat` snapshots `### stat_before` and `### stat_after` of each run log) |
| kernel build | 6.17.0-19-generic | 6.17.0-41-generic | line 2 of `logs/p8/p8_2/run2/runs/p82_N_flood_256_1.log` and of `logs/p10/wp2a/p10aT0_N_flood_256_1.log`; `ENV.md` lines 9 and 70 |
| iperf3 client command | `taskset -c $cpu iperf3 -c ... -u -b 0 -l 214 -t 10` | identical | `scripts/p8_2_bench.sh:161-162` and `scripts/p10_bench.sh:168-169` (the Phase 10 line adds a paced branch that is not taken for the flood, `pps_target=0`, line 1 of each log) |
| frame size and payload | 256 B, payload 214 | 256 B, payload 214 | `scripts/p8_2_bench.sh:30`, `scripts/p10_bench.sh:25`; line 1 of each run log |
| duration | 10 s | 10 s | `scripts/p8_2_bench.sh:24`, `scripts/p10_bench.sh:19` |
| iperf3 servers | both in `p2ns`, pinned to core 3 | identical | `scripts/p8_2_bench.sh:124`, `scripts/p10_bench.sh:131` |
| classifier tap and system core | `build/classifier p1veth0`, core 0 | identical | `scripts/p8_2_bench.sh:130`, `scripts/p10_bench.sh:137` |
| namespace and veth configuration | `scripts/lab_up.sh` (veth pair, `p2ns`, addresses) | the same script, unchanged since Phase 4 | `scripts/lab_up.sh:15-21`; `git log -- scripts/lab_up.sh` shows only the Phase 4 commit |
| RPS on `p1veth1` rx-0 | not recorded, no code sets it | set to mask 0 before each T0 run and read back as `00` | `scripts/p10_bench.sh:108` and `:210`; line 4 of `logs/p10/wp2a/p10aT0_N_flood_256_1.log` (`rps_cpus_readback=00`); the default in the Phase 10 session is also `00` (`logs/p10/probe/rps_list.txt:5`). The Phase 8.2 value is UNVERIFIED (not logged) |
| capture process | none (config N) | none (config N) | line 4 of `logs/p8/p8_2/run2/runs/p82_N_flood_256_1.log` and line 5 of `logs/p10/wp2a/p10aT0_N_flood_256_1.log` (`capture_cmd=none`) |
| tx/rx queue length, GSO, offload, sysctls | not recorded in either set | not recorded | UNVERIFIED: no log of either set records them (`scripts/lab_up.sh` sets none) |

## What the logs show

1. **Cores, not rates, were the limit in both sets.** In Phase 8.2 three cores (the two client cores 1 and 4 and the server core 3) ran at 1.00 busy; in WP2(a) T0 only core 4 ran at 1.00 (both clients) and the server core was at 0.28. So WP2(a) T0 had one saturated sender core where Phase 8.2 had two. That is the pinning change of `scripts/p10_bench.sh:29` (`CPU_NOISE_CLI=4`, made so that core 1 could serve as the RPS core).
2. **That accounts for a factor of two, not five.** Per saturated sender core the offered load was about 1.03 million pps in Phase 8.2 (1023562 and 1029832 pps on two cores) and about 0.42 million pps in WP2(a) T0 on one core (422362 pps). Pinning two clients to one core can therefore explain at most the factor of two in the total; a factor of 2053399 / 2 / 422362 = 2.43 per core remains.
3. **The same per-core rate appears in a different Phase 10 measurement.** The WP0 probe used one iperf3 client on core 4, RPS off, 3 s: 1319174 packets, 439598 pps (`logs/p10/probe/cli_off.json`, `logs/p10/probe/rps_functional.txt`), on kernel 6.17.0-41, with the capture absent. So the low per-core rate is reproduced twice on the -41 kernel (probe and WP2(a) T0) and is not an artefact of the WP2(a) plan.
4. **No log separates the kernel build from other session differences.** The only recorded difference that could change the per-core cost of the sender's transmit path (client send, veth, receive processing in the sender's context, the classifier tap) is the kernel build, -19 for Phase 8.2 and -41 for Phase 10 (`ENV.md:70`: the kernel changed between the phases). No Phase 8.2-style run (clients on two cores) exists on the -41 kernel, and none of the single-client kind on the -19 kernel, so the two explanations (kernel build; something else not recorded, such as host load of the virtual machine, queue or offload settings, or CPU frequency of the host) cannot be told apart from the logs.

## Conclusion

The difference of the pinning of the noise client (`scripts/p8_2_bench.sh:34` against `scripts/p10_bench.sh:29`) plausibly accounts for a factor of about two of the 4.86: the baseline topology of WP2(a) generated the whole flood on one core where Phase 8.2 used two. **UNVERIFIED: cause not determined** for the remaining factor of 2.43 per core. The only recorded difference that could act on the per-core cost is the kernel build; nothing in the logs shows that it does.

**The one cheapest probe that would settle it** (to be run by the author, not run here): boot the still-installed kernel 6.17.0-19-generic (`/boot/vmlinuz-6.17.0-19-generic` exists) and repeat the WP0 single-client probe, one iperf3 UDP client on core 4, `-b 0 -l 214`, 3 s, RPS off (the commands of `scripts/p10_probe.sh` lines 51-59). If the offered rate is near 1.0 million pps the kernel build accounts for the 2.43 per-core factor (and the pinning for the 2); if it is near 0.44 million pps the kernel build is excluded and the difference lies in something that the logs do not record. This changes one thing, the kernel, with the same machine, namespace and tool.

## Consequence for the Phase 10 and Phase 11 text (stated, not applied)

The two N values are not comparable as a baseline: `docs/phase10_design.md` section 5.1 already says Phase 8.2's ratios came from "a different kernel and different pinning, not a baseline here". This note adds that the pinning change alone halves the sender capacity, and that the remaining difference is undetermined.

## Addendum (2026-11-09): the demo rehearsals are a Phase 8.2-style run on the -41 kernel

After the note was written, the two demo rehearsals (`logs/demo_rehearsal_1.log`, `logs/demo_rehearsal_2.log`, act 2; the rehearsal logs are committed in Phase 12) ran config N with the Phase 8.2 pinning (noise client on core 1, match client on core 4, servers on core 3) on kernel 6.17.0-41-generic, in the same lab, for 10 s each. Offered load, measured from the `p1veth0` tx counter (a different counter from the classifier total of the table above): 1187495 pps (`logs/demo_rehearsal_1.log:50`) and 1198229 pps (`logs/demo_rehearsal_2.log:50`). These are illustrative runs, not part of any pre-declared design, taken on a machine that was not prepared as in the hands-off protocol.

What this changes: on the -41 kernel, going from both clients on core 4 (422362 pps, WP2(a) T0) to the Phase 8.2 pinning gives about 1.19 million pps, a factor of 2.8, so the pinning accounts for more than the factor of two assumed above. What remains between 1.19 million and the 2.05 million of Phase 8.2 is a factor of about 1.7 (2053399 / 1187495, arithmetic). **UNVERIFIED: cause of the remaining factor of about 1.7 not determined**; the kernel build (-19 against -41) is still the only recorded difference, and the same cheapest probe (boot -19 and repeat the one-client probe, or the two-client run of act 2) would settle it. The counter used here differs from the one used for the table, so the 1.7 is approximate.
