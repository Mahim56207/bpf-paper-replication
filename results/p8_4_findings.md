# Phase 8.4: findings (does the V8 canary rule do what it is supposed to do?)

Numbers in backticks are copied from `results/p8_4_summary.md` (pooled analysis, pre-declared, the PRIMARY result), `results/p8_4_blocked.md` (blocked re-analysis, amendment A4, **post hoc and exploratory**, written after the pooled result had been seen) or `results/p8_4_ablation.md`; `scripts/p8_4_verify.sh` checks that each of them occurs there. Design, amendments A1 to A5 and the script-checked hash chain: section 7.

## 0. Result in one paragraph

By the pre-declared rules V8's premise is **PARTIAL**: V8 detects canary-core noise reliably, but the experiment could not decide whether the flagged levels (and only they) shift the headline metric, because every non-zero level came out **INDETERMINATE** (intervals far wider than the 5% tolerance, mainly because of variation between launches). A post hoc, exploratory blocked re-analysis (section 3) resolves the flagged curve levels as MATERIAL but leaves the overall premise PARTIAL. Nothing here shows that V8 keeps the metric within 5%; by arithmetic it is looser than that (section 4).

## 1. What was measured

720 windows of 10 s in 7 launches, none excluded by the harness-integrity rules: E1 paced curve (config B, 512 B, 32000 pps, noise on cores {0,1}; launches C1 to C3), E2 flood (config N, noise on core {0}; launches F1 to F3), E3 noise V8 cannot see (launch X1). Noise was stress-ng (cpu and cache types) pinned to the canary cores and duty-cycled; its intensity is the CPU time the workers themselves consumed (amendment A2). Levels straddle the V8 limit as designed (0.0826 for {0,1}, 0.0443 for {0}). **Level 0 appears in every launch of its family**: 10 level-0 windows per type in each of C1 to C3 (E1) and F1 to F3 (E2), script-counted in `results/p8_4_blocked.md` ("Level-0 windows per launch"), so the blocked comparison is possible for E1 and E2. **E3 is the exception**: its control (S0, 15 windows) exists only in the single launch X1, so E3 is compared with its control inside one launch and cannot be blocked; drift inside that launch is not removed.

## 2. Pre-declared (pooled) result: PARTIAL, all non-zero levels INDETERMINATE

- **Detection (rule N1).** V8 behaves as a threshold on the canary rate: the flagged fraction rises from `1/30` or `0/30` windows at level 0 to `30/30` at the high levels (E1 cpu level 4: `30/30`); the crossing is where ambient plus injected CPU exceeds the limit (E2 cpu level 2: `23/30`).
- **False-positive rate at level 0:** `3/120` windows over the four families, observed rate `0.025`, Wilson 95% interval [`0.009`, `0.071`], **exact binomial (Clopper-Pearson) 95% interval** [`0.005`, `0.071`]; per family `1/30`, `0/30`, `1/30`, `1/30`, with exact intervals up to `0.172` (`0.116` for `0/30`). The pre-declared acceptance test (Wilson upper bound at most 0.10 per family) cannot be met with 30 windows even with zero flags (it needs at least `35` windows), so the pooled summary prints "NOT acceptable"; that is a property of my rule and sample size (amendments A4 and A5), not evidence against V8. Restated criterion (observed rate at most 0.10, post hoc): met.
- **Validity (rule N2).** V8's premise is **PARTIAL** in all four families: no level could be shown MATERIAL or EQUIVALENT. The main reason is variation between launches, which enters the within-cell variance of the pooled test: level 0 of the flood is `1.07467e+06` pps in F1 against `2.03239e+06` in F2 and `2.08767e+06` in F3 (cpu noise), and level 0 of the curve metric is `6865.01`, `-222.68` and `5.40979` ns per packet in C1 to C3. V8 on cores {0,1} cannot see that drift.

## 3. Post hoc and exploratory: blocked re-analysis (amendment A4)

Written after the pooled result had been seen, so of lower weight; the pooled numbers above are unchanged. Each level is compared with level 0 inside each launch, the differences are averaged over the three launches, and the tolerance scale is the gross CPU per packet (curve) or the level-0 offered rate (flood).

- **Curve (E1), measured:** the flagged levels are **MATERIAL** in both noise types (cpu level 4 `+40.7%`, level 5 `+96.2%`; cache level 4 `+59.0%`, level 5 `+139.9%` of the gross CPU per packet). The within-launch dose-response slope is `4.385e+04` ns per packet per CPU-s/s of canary rate for cpu noise ([`3.798e+04`, `4.972e+04`]) and `3.913e+04` for cache noise, above the value `3.135e+04` that adding the canary CPU alone would give; why the metric rises somewhat more than the added CPU was not investigated. The blocked premise is still **PARTIAL**: the lowest levels stay INDETERMINATE (for example cache level 1: `+23.3%`, interval [`-15.7%`, `+62.3%`]).
- **Flood (E2), measured:** no level shows a resolvable shift of the offered rate, even above the V8 limit (flagged cpu level 3: `-6.4%`, interval [`-13.3%`, `+0.5%`]; flagged cache level 4: `+3.8%`, [`-2.4%`, `+10.1%`]). The intervals are too wide to call these windows harmless (EQUIVALENT within 5%), and the point estimates give no sign of harm: a "needless exclusion" is neither shown nor excluded.
- **Cores 2 to 4 (E1, informational):** the ratios of the CPU on the experiment cores are about 1 with wide intervals; there is no sign that noise on cores {0,1} reaches them.

## 4. Predicted (arithmetic), not measured: V8 is lax for a 5% tolerance

The "mechanical expectation" column of `results/p8_4_blocked.md` is **computed, not observed**: it is the difference of the measured canary CPU of a level and of level 0, times the window length, divided by the matched packets, relative to the level-0 gross cost. It assumes that the added CPU simply adds to the system-wide cost. By that arithmetic the levels that V8 flags in fewer than 90% of their windows would shift the metric by `+4.4%` (cpu level 1) up to `+38.7%` (cache level 3), for example `+18.5%` at cache level 1, which V8 flags in only `0.07` of its windows. **The measured shifts at those levels are INDETERMINATE** (section 2 and 3), so the claim "noise below the V8 limit shifts the metric by 4% to 39%" is a prediction from injected CPU, not a measurement. A 5% tolerance on this metric corresponds, by the same arithmetic, to roughly 0.01 CPU-s/s of added canary CPU, small against the V8 limit of 0.0826 for {0,1} (the level-0 canary rate over the 60 curve windows has mean 0.029 and a maximum of 0.41, a heavy-tailed ambient).

## 5. E3, noise V8 cannot see: UNRESOLVED (not shown harmless)

CPU noise on the capture core 2: ratio `2.141` against the control, interval [`0.831`, `3.452`]; on the server core 3: `2.273`; global memory pressure (holding 1774 to 1880 MB, so that MemAvailable fell to about 1.0 GB): `0.882`, interval [`0.222`, `1.542`]. V8 flagged 1 of 15, 2 of 15 and 0 of 15 windows. **All three are INDETERMINATE.** The point estimates for the two CPU conditions point to a doubling of the per-packet cost that V8 mostly does not flag, but no interval excludes 1, so no blind spot is established; the memory condition shows no significant shift, **but its interval is wide enough to contain large effects, so it is not evidence that memory pressure is harmless**. E3 compares each condition with a control from the same single launch (section 1).

## 6. Ablation (rule N4, `results/p8_4_ablation.md`)

The recomputation with V8 on reproduces every published label (reproduction check PASS). With V8 off the Phase 6 labels do not change (C2 MIXED, C3 INCONCLUSIVE, C4 NOT SUPPORTED) but the intervals change materially (C4 factor `1.05` with interval [`0.636`, `1.47`] against the published `0.892` [`0.816`, `0.967`]). Phase 8.2 run set 2 stays SENDER-LIMITED SUPPORTED. **Phase 8.2 run set 1** (V8 off: NOT SUPPORTED, lower bounds `-218396` and `-95249`, against INCONCLUSIVE published) is **not recomputed from raw logs, because they were deleted in the wrong launch (D8.14)**: it is computed from two surviving derived files, the per-run offered pps of all final unprofiled runs in `logs/p8/p8_2/p8_2_diag_exploratory_offered.log` (printed by a script from the raw logs before they were lost) and the per-run profile shares in `results/p8_2_summary.md`; it cannot be independently reproduced. So V8 did not change a Phase 6 verdict, and in Phase 8.2 it kept a contaminated set from giving a verdict that differs from the clean run set.

## 7. Amendments to the design, hash chain

The design file was amended five times; the chain was reproduced by `scripts/p8_4_design_chain.py` (log `logs/p8/p8_4/p8_4_design_chain.log`): the text as first written hashes to the first logged value (logged before the calibration probes and every launch), and each amendment's hash is reproduced from the current file by cutting section 10; every launch started when the design in force was at least A3. A4 and A5 were written after the launches (post hoc).

| id | date | reason |
|---|---|---|
| A1 | 2026-10-26 | before any run: cache noise needs `--cache-enable-all` (functional test message), memory-hold wording for S3, calibration probe length (78 windows) |
| A2 | 2026-10-26 | calibration probe 1 unusable at low levels (baseline subtraction swamped by ambient noise of about 0.1 CPU-s/s per core): the injected rate is the stress-ng workers' own CPU time; probe 2 (51 windows) |
| A3 | 2026-10-26 | levels fixed from probe 2 before the first launch; levels must be distinct and increasing (lowest E1 targets collapsed onto duty 1) |
| A4 | 2026-10-27 | **post hoc**: blocked re-analysis, gross-CPU scale, per-launch idle baseline (information), dose-response, restated N1 |
| A5 | 2026-10-27 | **post hoc**: erratum to A4 (35 windows, not 37) |

```
# design hash chain (script-computed) 2026-10-27T11:45:35+05:30
MATCH: design as first written
MATCH: design after amendment A1
MATCH: design after amendment A2
MATCH: design after amendment A3
MATCH: design after amendment A4
MATCH: design after amendment A5

amendments (id, date, first sentence):
  A1  2026-10-26  , before the calibration probe and before any measured run;
  A2  2026-10-26  , after calibration probe 1 and before calibration probe 2 and any measured run;
  A3  2026-10-26  , after calibration probe 2 and before the first measured run;
  A4  2026-10-27  , written AFTER the pooled analysis of all seven launches had been computed and seen;
  A5  2026-10-27  , erratum to A4, written after `scripts/p8_4_blocked.py` had run;
OK: first hash logged 2026-10-26T15:18:36+05:30, calibration probe output created 2026-10-26T17:40:45.165306+05:30
OK: launch C1 started 2026-10-26T18:09:51+05:30; design in force = after A3 (hash logged 2026-10-26T18:02:52+05:30)
OK: launch C2 started 2026-10-26T19:41:39+05:30; design in force = after A3 (hash logged 2026-10-26T18:02:52+05:30)
OK: launch C3 started 2026-10-26T21:59:46+05:30; design in force = after A3 (hash logged 2026-10-26T18:02:52+05:30)
OK: launch F1 started 2026-10-26T19:02:14+05:30; design in force = after A3 (hash logged 2026-10-26T18:02:52+05:30)
OK: launch F2 started 2026-10-26T20:29:26+05:30; design in force = after A3 (hash logged 2026-10-26T18:02:52+05:30)
OK: launch F3 started 2026-10-26T23:30:14+05:30; design in force = after A3 (hash logged 2026-10-26T18:02:52+05:30)
OK: launch X1 started 2026-10-27T11:10:08+05:30; design in force = after A3 (hash logged 2026-10-26T18:02:52+05:30)
INFO: amendment(s) A4, A5 logged after the last launch started: post-hoc by construction (their text says so)
hash-chain check: 0 problem(s)
```

## 8. Incidents and the VM pause

Two pre-flights failed the V8 idle limit before any window was measured (F1 first attempt, canary 0.0878; X1 first attempt, canary 0.0897) and were relaunched; their files are in `logs/p8/p8_4/{F1,X1}/aborted_attempt_1/`. The first X1 retry spanned a **pause of the virtual machine**: its context file is stamped 01:00 and its windows 11:01, a clock jump of about 10 hours; it was stopped after 9 windows and X1 was restarted from scratch; the partial files are in `logs/p8/p8_4/X1/aborted_attempt_2/` and **no window of that attempt is in the data**. For the analysed windows `scripts/p8_4_timecheck.py` (log `logs/p8/p8_4/p8_4_timecheck.log`) confirms that none spans a clock jump: every window length is within rule V6 and no gap between consecutive windows of a launch exceeds 120 s.

```
C1: 120 windows, length min 10.02 max 10.04 s, 0 outside V6; gap between consecutive windows min 7.6 max 7.9 s; gaps over 120 s: none
C2: 120 windows, length min 10.02 max 10.04 s, 0 outside V6; gap between consecutive windows min 7.5 max 7.9 s; gaps over 120 s: none
C3: 120 windows, length min 10.02 max 10.05 s, 0 outside V6; gap between consecutive windows min 7.6 max 7.8 s; gaps over 120 s: none
F1: 100 windows, length min 10.02 max 10.04 s, 0 outside V6; gap between consecutive windows min 7.5 max 7.7 s; gaps over 120 s: none
F2: 100 windows, length min 10.02 max 10.05 s, 0 outside V6; gap between consecutive windows min 7.4 max 7.8 s; gaps over 120 s: none
F3: 100 windows, length min 10.02 max 10.04 s, 0 outside V6; gap between consecutive windows min 7.4 max 7.7 s; gaps over 120 s: none
X1: 60 windows, length min 10.02 max 10.08 s, 0 outside V6; gap between consecutive windows min 7.6 max 11.0 s; gaps over 120 s: none
TOTAL 720 analysed windows; problems: 0
not analysed: logs/p8/p8_4/F1/aborted_attempt_1 (0 window logs)
not analysed: logs/p8/p8_4/X1/aborted_attempt_1 (0 window logs)
not analysed: logs/p8/p8_4/X1/aborted_attempt_2 (9 window logs)
```

## 9. Limits

Synthetic, duty-cycled noise on single cores of a virtual machine; one host, one config per experiment; slow drift of the machine across a session of hours (the seven launches span about 17 hours of wall-clock time); a metric that is system-wide and dominated at 32000 pps by background CPU; tolerance 5% chosen by me; the blocked analysis and its scale (gross CPU per packet) were chosen after the pooled results were seen; 30 windows per cell resolve only large shifts; E3 has no blocking.
