# Verdicts (reviewer rulings D6.13, D6.14 applied): C2, C3, C4

Computed by scripts/summarize.py from logs/bench_*.log; each verdict cites the tables in results/summary.md and the exclusions in results/exclusions.md. C1 waits for sub-phase 6c. No 1993 absolute number is compared. C4 text per reviewer rulings D6.13 (idle baseline) and D6.14.

## C2 reject-all: in-kernel cost flat vs size; user-space copy-then-filter grows (R-C2)

**Verdict: MIXED**

A-over-D slope -0.951 ns/byte, 95% CI [-5.77, 3.87] (excludes 0: False); B-over-D slope 1.3 ns/byte, 95% CI [-2.29, 4.9] (includes 0: True); CIs non-overlapping: False. Root cause: A's slope CI includes 0: no detectable size dependence for the copy-then-filter config; the two slope CIs overlap. D floor slope 1.64 ns/byte (net).

Tables: see `results/summary.md` sections 'Reject curve'. Exclusions: 44 excluded runs/attempts in total (`results/exclusions.md`); steal exclusions per config: A 0/35, B 0/35, C 0/5, D 0/15, E 0/15.

## C3 accept-all: slope and fixed cost, A vs B (R-C3)

**Verdict: INCONCLUSIVE**

slope A 1.21 [-3.84, 6.25], slope B 0.101 [-3.99, 4.19] ns/byte; slope diff A - B = 1.1, 95% CI [-5.43, 7.64]; intercept diff A - B = -2.02e+03 ns/pkt, 95% CI [-7.76e+03, 3.71e+03]. Root cause: slope difference (A - B) CI does not lie above 0; intercept difference (A - B) CI does not lie above 0.

Tables: see `results/summary.md` sections 'Accept curve' and 'Cost decomposition for config B'. Exclusions: 44 excluded runs/attempts in total (`results/exclusions.md`); steal exclusions per config: A 0/35, B 0/35, C 0/5, D 0/15, E 0/15.

## C4 flood: matched-pps ceiling and CPU per matched packet, A vs B (R-C4)

**Verdict: NOT SUPPORTED**

flow-matched pps ceiling B - A = -4.16e+04 pps, 95% CI [-6.08e+04, -2.25e+04] (B higher = CI > 0: False); net CPU per flow-matched packet A/B factor = 0.892, 95% CI [0.816, 0.967] (A costs more = CI > 1: False). A saturated (socket drops > 1% of packets reaching it) in 0 of 4 valid runs; where it did not, A's figure is offered-load-limited, not a ceiling. C4's CSPF ratio is not replicated end-to-end (D6.1 item 5). Reviewer ruling D6.14: NOT SUPPORTED as a receiver-drop claim. However, it reveals a sender-generation bottleneck: offered rates diverge by config because the filter/classifier overhead impacts the sending core's capacity. Config A was offered-load-limited, not receiver-saturated.

Tables: see `results/summary.md` sections 'Flood (C4)'. Exclusions: 44 excluded runs/attempts in total (`results/exclusions.md`); steal exclusions per config: A 0/35, B 0/35, C 0/5, D 0/15, E 0/15.

