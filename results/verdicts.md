# Verdicts (reviewer rulings D6.13, D6.14 applied): C2, C3, C4

Computed by scripts/summarize.py from logs/bench_*.log; each verdict cites the tables in results/summary.md and the exclusions in results/exclusions.md. C1 waits for sub-phase 6c. No 1993 absolute number is compared. Final wording per reviewer rulings D6.13 (idle baseline) and D6.14, see Notes below.

## C2 reject-all: in-kernel cost flat vs size; user-space copy-then-filter grows (R-C2)

**Verdict: MIXED**

A-over-D slope -4.42 ns/byte, 95% CI [-9.19, 0.35] (excludes 0: False); B-over-D slope -2.15 ns/byte, 95% CI [-6.95, 2.66] (includes 0: True); CIs non-overlapping: False. Root cause: A's slope CI includes 0: no detectable size dependence for the copy-then-filter config; the two slope CIs overlap. D floor slope -0.0119 ns/byte (net). Descriptive, not part of the rule (means over the valid reject-curve runs of all sizes): capture-process CPU A 11.1 (n=15), B 0.0 (n=15) % of one CPU; capture-process context switches A 7654 (n=15), B 1 (n=15) per s.

Tables: see `results/summary.md` sections 'Reject curve'. Exclusions: 48 excluded runs/attempts in total (`results/exclusions.md`); steal exclusions per config: A 0/35, B 0/35, C 0/5, D 0/15, E 0/15.

## C3 accept-all: slope and fixed cost, A vs B (R-C3)

**Verdict: INCONCLUSIVE**

slope A -0.976 [-7.35, 5.39], slope B 1.39 [-4.31, 7.09] ns/byte; slope diff A - B = -2.37, 95% CI [-10.9, 6.18]; intercept diff A - B = 2.01e+03 ns/pkt, 95% CI [-5.27e+03, 9.3e+03]. Root cause: slope difference (A - B) CI does not lie above 0; intercept difference (A - B) CI does not lie above 0. EXPLORATORY, not part of R-C3 (the 1993 slopes are BPF 148 and NIT 216 ns/byte, paper.txt L186-189 and L208): upper bound of the 95% slope interval A 5.39 ns/byte, B 7.09 ns/byte; as a fraction of the 1993 BPF slope A 0.0365, B 0.0479; as a fraction of the 1993 NIT slope A 0.025, B 0.0328.

Tables: see `results/summary.md` sections 'Accept curve' and 'Cost decomposition for config B'. Exclusions: 48 excluded runs/attempts in total (`results/exclusions.md`); steal exclusions per config: A 0/35, B 0/35, C 0/5, D 0/15, E 0/15.

## C4 flood: matched-pps ceiling and CPU per matched packet, A vs B (R-C4)

**Verdict: INCONCLUSIVE** (frozen V8 rule, no floor)

not enough valid flood runs for A and B (frozen V8 rule, no floor: valid A 0, B 0, C 0; at least 2 needed)

**Sensitivity analysis, post hoc and uncalibrated flood V8 floor of 0.035 CPU-s/s (D8.22): NOT SUPPORTED**

flow-matched pps ceiling B - A = -4.56e+04 pps, 95% CI [-5.09e+04, -4.03e+04] (B higher = CI > 0: False); net CPU per flow-matched packet A/B factor = 0.863, 95% CI [0.852, 0.874] (A costs more = CI > 1: False). A saturated (socket drops > 1% of packets reaching it) in 0 of 5 valid runs; where it did not, A's figure is offered-load-limited, not a ceiling. Offered pps (mean of the valid runs): A 653245 (n=5), B 765540 (n=5), C 1026697 (n=5). The label concerns the receiver-drop reading of C4 (NOT SUPPORTED as a receiver-drop claim); C4's CSPF ratio is not tested end to end (D6.1 item 5).

**Phase 6 (noisy session) for comparison: NOT SUPPORTED**

Phase 6 matrix, noisy session run_1792350994 (results/phase6_noisy/): valid flood runs A 4, B 4, C 4; label as computed at that time.

Tables: see `results/summary.md` sections 'Flood (C4)'. Exclusions: 48 excluded runs/attempts in total (`results/exclusions.md`); steal exclusions per config: A 0/35, B 0/35, C 0/5, D 0/15, E 0/15.

## Notes

**Idle baseline (computed).** Session idle windows: 0.030 CPU-s/s; calibration baseline in results/baseline_calibration.json: 0.044 CPU-s/s; the net CPU of this summary subtracts 0.030 CPU-s/s (session idle windows).

**Flood V8 policies (computed).** Headline: the frozen rule (limit 1.2 x canary_max of the baseline file). Sensitivity analysis: canary_max raised to at least 0.035 CPU-s/s for flood runs, post hoc and without a calibration record (DEVIATIONS D8.22). Runs valid only because of the floor: 15.

The reviewer rulings D6.13 and D6.14 of the Phase 6 matrix are quoted in results/phase6_noisy/verdicts.md; they are statements about that matrix, not about this run.

