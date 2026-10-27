# Phase 8.4: V8 ablation from existing data (computed by scripts/p8_4_ablation.py)

Variants: **P** = V8 on, final runs only; **A1** = V8 off, final runs only; **A2** = V8 off, final runs plus every earlier attempt as an additional run of its cell (attempts are separate runs under the same conditions, treated as independent: a caveat).

## Phase 6 (C2, C3, C4)

Reproduction check (variant P against the published `results/summary.json`): **PASS, the recomputation reproduces the published labels**.

| claim | published | P (V8 on, final) | A1 (V8 off, final) | A2 (V8 off, final + attempts) |
|---|---|---|---|---|
| C2 | **MIXED** | MIXED | **MIXED** | **MIXED** |
| C3 | **INCONCLUSIVE** | INCONCLUSIVE | **INCONCLUSIVE** | **INCONCLUSIVE** |
| C4 | **NOT SUPPORTED** | NOT SUPPORTED | **NOT SUPPORTED** | **NOT SUPPORTED** |

**C2 statistics.**

- P: A-over-D slope -0.951 ns/byte, 95% CI [-5.77, 3.87] (excludes 0: False); B-over-D slope 1.3 ns/byte, 95% CI [-2.29, 4.9] (includes 0: True); CIs non-overlapping: False. Root cause: A's slope CI includes 0: no detectable size dependence for the copy-then-filter config; the two slope CIs overlap. D floor slope 1.64 ns/byte (net).
- A1: A-over-D slope -4.43 ns/byte, 95% CI [-12.2, 3.33] (excludes 0: False); B-over-D slope 6.35 ns/byte, 95% CI [-4.62, 17.3] (includes 0: True); CIs non-overlapping: False. Root cause: A's slope CI includes 0: no detectable size dependence for the copy-then-filter config; the two slope CIs overlap. D floor slope 1.64 ns/byte (net).
- A2: A-over-D slope -7.8 ns/byte, 95% CI [-17.6, 1.97] (excludes 0: False); B-over-D slope 9.96 ns/byte, 95% CI [-2.32, 22.2] (includes 0: True); CIs non-overlapping: False. Root cause: A's slope CI includes 0: no detectable size dependence for the copy-then-filter config; the two slope CIs overlap. D floor slope 1.64 ns/byte (net).

**C3 statistics.**

- P: slope A 1.21 [-3.84, 6.25], slope B 0.101 [-3.99, 4.19] ns/byte; slope diff A - B = 1.1, 95% CI [-5.43, 7.64]; intercept diff A - B = -2.02e+03 ns/pkt, 95% CI [-7.76e+03, 3.71e+03]. Root cause: slope difference (A - B) CI does not lie above 0; intercept difference (A - B) CI does not lie above 0.
- A1: slope A -5.21 [-22.2, 11.8], slope B -3.99 [-17.2, 9.27] ns/byte; slope diff A - B = -1.23, 95% CI [-22.8, 20.3]; intercept diff A - B = 1.59e+03 ns/pkt, 95% CI [-1.63e+04, 1.95e+04]. Root cause: slope difference (A - B) CI does not lie above 0; intercept difference (A - B) CI does not lie above 0.
- A2: slope A -8.88 [-26.4, 8.67], slope B -3.99 [-17.2, 9.27] ns/byte; slope diff A - B = -4.89, 95% CI [-27.3, 17.5]; intercept diff A - B = 7.75e+03 ns/pkt, 95% CI [-1e+04, 2.55e+04]. Root cause: slope difference (A - B) CI does not lie above 0; intercept difference (A - B) CI does not lie above 0.

**C4 statistics.**

- P: flow-matched pps ceiling B - A = -4.16e+04 pps, 95% CI [-6.08e+04, -2.25e+04] (B higher = CI > 0: False); net CPU per flow-matched packet A/B factor = 0.892, 95% CI [0.816, 0.967] (A costs more = CI > 1: False). A saturated (socket drops > 1% of packets reaching it) in 0 of 4 valid runs; where it did not, A's figure is offered-load-limited, not a ceiling. C4's CSPF ratio is not replicated end-to-end (D6.1 item 5). NOT SUPPORTED as a receiver-drop claim. Reveals a sender-generation bottleneck: offered rates diverge by config because the filter/classifier overhead impacts the sending core's capacity. Config A was offered-load-limited, not receiver-saturated.
- A1: flow-matched pps ceiling B - A = -1.83e+04 pps, 95% CI [-7.37e+04, 3.71e+04] (B higher = CI > 0: False); net CPU per flow-matched packet A/B factor = 1.05, 95% CI [0.636, 1.47] (A costs more = CI > 1: False). A saturated (socket drops > 1% of packets reaching it) in 1 of 5 valid runs; where it did not, A's figure is offered-load-limited, not a ceiling. C4's CSPF ratio is not replicated end-to-end (D6.1 item 5). NOT SUPPORTED as a receiver-drop claim. Reveals a sender-generation bottleneck: offered rates diverge by config because the filter/classifier overhead impacts the sending core's capacity. Config A was offered-load-limited, not receiver-saturated.
- A2: flow-matched pps ceiling B - A = -6.3e+03 pps, 95% CI [-5.02e+04, 3.76e+04] (B higher = CI > 0: False); net CPU per flow-matched packet A/B factor = 1.15, 95% CI [0.829, 1.48] (A costs more = CI > 1: False). A saturated (socket drops > 1% of packets reaching it) in 3 of 8 valid runs; where it did not, A's figure is offered-load-limited, not a ceiling. C4's CSPF ratio is not replicated end-to-end (D6.1 item 5). NOT SUPPORTED as a receiver-drop claim. Reveals a sender-generation bottleneck: offered rates diverge by config because the filter/classifier overhead impacts the sending core's capacity. Config A was offered-load-limited, not receiver-saturated.

- P summarizer line: `session run_1792350994: parsed 130 logs (105 measured, 89 valid, 16 excluded or re-run); wrote results/summary.md, exclusions.md, verdicts.md`
- A1 summarizer line: `session run_1792350994: parsed 130 logs (105 measured, 99 valid, 6 excluded or re-run); wrote results/summary.md, exclusions.md, verdicts.md`
- A2 summarizer line: `session run_1792350994: parsed 158 logs (133 measured, 116 valid, 17 excluded or re-run); wrote results/summary.md, exclusions.md, verdicts.md`

## Phase 8.2 run set 2 (logs/p8/p8_2/run2/)

| variant | valid unprofiled N / A / B / C | S-H1 (N-A, N-B lower bounds) | S-H2 (R/P - 1 for A, B) | verdict |
|---|---|---|---|---|
| P | 6 / 6 / 6 / 6 | 720267, 552013 | +22.5%, +18.9% | **SENDER-LIMITED SUPPORTED** |
| A1 | 6 / 6 / 6 / 6 | 720267, 552013 | +22.5%, +18.9% | **SENDER-LIMITED SUPPORTED** |
| A2 | 6 / 8 / 7 / 6 | 723697, 571293 | +21.1%, +20.0% | **SENDER-LIMITED SUPPORTED** |

Reproduction check (variant P against `results/p8_2_summary_run2.json`): **PASS** (published verdict SENDER-LIMITED SUPPORTED).

## Phase 8.2 run set 1 (from the surviving derived data only; raw logs deleted, D8.14)

Per-run offered pps of all final unprofiled runs from `logs/p8/p8_2/p8_2_diag_exploratory_offered.log` (every one of them failed only V8, if at all, per `results/p8_2_summary.md`), per-run profile shares f of the valid profiled runs from `results/p8_2_summary.md`.

| variant | unprofiled N / A / B / C | profiled valid N / A / B / C | S-H1 lower bounds (N-A, N-B) | S-H2 R/P - 1 (A, B) | verdict |
|---|---|---|---|---|---|
| published (V8 on) | 5 / 0 / 0 / 4 | 4 / 3 / 4 / 2 | n/a | n/a | **INCONCLUSIVE** |
| V8 off | 6 / 6 / 6 / 6 | 4 / 3 / 4 / 2 | -218396, -95249 | -7.7%, +13.2% | **NOT SUPPORTED** |

