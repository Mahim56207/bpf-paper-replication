# Verdicts (reviewer rulings D6.13, D6.14 applied): C2, C3, C4

Computed by scripts/summarize.py from logs/bench_*.log; each verdict cites the tables in results/summary.md and the exclusions in results/exclusions.md. C1 waits for sub-phase 6c. No 1993 absolute number is compared. Final wording per reviewer rulings D6.13 (idle baseline) and D6.14, see Notes below.

## C2 reject-all: in-kernel cost flat vs size; user-space copy-then-filter grows (R-C2)

**Verdict: MIXED**

A-over-D slope -4.42 ns/byte, 95% CI [-9.19, 0.35] (excludes 0: False); B-over-D slope -2.15 ns/byte, 95% CI [-6.95, 2.66] (includes 0: True); CIs non-overlapping: False. Root cause: A's slope CI includes 0: no detectable size dependence for the copy-then-filter config; the two slope CIs overlap. D floor slope -0.0119 ns/byte (net).

Tables: see `results/summary.md` sections 'Reject curve'. Exclusions: 55 excluded runs/attempts in total (`results/exclusions.md`); steal exclusions per config: A 0/35, B 0/35, C 0/5, D 0/15, E 0/15.

## C3 accept-all: slope and fixed cost, A vs B (R-C3)

**Verdict: INCONCLUSIVE**

slope A -0.976 [-7.35, 5.39], slope B 1.39 [-4.31, 7.09] ns/byte; slope diff A - B = -2.37, 95% CI [-10.9, 6.18]; intercept diff A - B = 2.01e+03 ns/pkt, 95% CI [-5.27e+03, 9.3e+03]. Root cause: slope difference (A - B) CI does not lie above 0; intercept difference (A - B) CI does not lie above 0.

Tables: see `results/summary.md` sections 'Accept curve' and 'Cost decomposition for config B'. Exclusions: 55 excluded runs/attempts in total (`results/exclusions.md`); steal exclusions per config: A 0/35, B 0/35, C 0/5, D 0/15, E 0/15.

## C4 flood: matched-pps ceiling and CPU per matched packet, A vs B (R-C4)

**Verdict: INCONCLUSIVE**

not enough valid flood runs for A and B

Tables: see `results/summary.md` sections 'Flood (C4)'. Exclusions: 55 excluded runs/attempts in total (`results/exclusions.md`); steal exclusions per config: A 0/35, B 0/35, C 0/5, D 0/15, E 0/15.

## Notes

**D6.13.** Initial session idle windows were contaminated by startup noise (0.030 CPU-s/s). V8 correctly caught this for active runs, but idle runs lacked V8. C4 CPU-per-packet recalculated using the quiet calibration idle baseline (0.044 CPU-s/s) to ensure validity. C2/C3 slope verdicts are mathematically invariant to this constant offset (the labels are unchanged between the two baselines; the numbers move in the third digit because the per-packet offset depends slightly on each run's offered rate; the session-idle version is kept in results/session_idle_baseline/).

**D6.14.** Matrix revealed that at >600k pps, the sender's generation context becomes the limiting factor, masking receiver-side drop behavior. This is a valid modern architectural finding. C4: NOT SUPPORTED as a receiver-drop claim. Reveals a sender-generation bottleneck: offered rates diverge by config because the filter/classifier overhead impacts the sending core's capacity. Config A was offered-load-limited, not receiver-saturated.

