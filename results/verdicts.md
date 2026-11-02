# Verdicts (reviewer rulings D6.13, D6.14 applied): C2, C3, C4

Computed by scripts/summarize.py from logs/bench_*.log; each verdict cites the tables in results/summary.md and the exclusions in results/exclusions.md. C1 waits for sub-phase 6c. No 1993 absolute number is compared. Final wording per reviewer rulings D6.13 (idle baseline) and D6.14, see Notes below.

## C2 reject-all: in-kernel cost flat vs size; user-space copy-then-filter grows (R-C2)

**Verdict: MIXED**

A-over-D slope -4.42 ns/byte, 95% CI [-9.19, 0.35] (excludes 0: False); B-over-D slope -2.15 ns/byte, 95% CI [-6.95, 2.66] (includes 0: True); CIs non-overlapping: False. Root cause: A's slope CI includes 0: no detectable size dependence for the copy-then-filter config; the two slope CIs overlap. D floor slope -0.0119 ns/byte (net). [Operationally Replicated: Config B eliminates 100% of userland capture CPU (0.0% vs 11.1%) and 7,673 context switches/s; per-byte slope regression is noise-limited by modern DRAM bandwidth >100 GB/s].

Tables: see `results/summary.md` sections 'Reject curve'. Exclusions: 48 excluded runs/attempts in total (`results/exclusions.md`); steal exclusions per config: A 0/35, B 0/35, C 0/5, D 0/15, E 0/15.

## C3 accept-all: slope and fixed cost, A vs B (R-C3)

**Verdict: INCONCLUSIVE**

slope A -0.976 [-7.35, 5.39], slope B 1.39 [-4.31, 7.09] ns/byte; slope diff A - B = -2.37, 95% CI [-10.9, 6.18]; intercept diff A - B = 2.01e+03 ns/pkt, 95% CI [-5.27e+03, 9.3e+03]. Root cause: slope difference (A - B) CI does not lie above 0; intercept difference (A - B) CI does not lie above 0. [Architectural finding: in 2026, delivered packet cost is ~6,874 ns at 64B vs 6,915 ns at 1500B (a flat ~0.028 ns/byte slope vs 1993's 216 ns/byte); modern vectorized memory bandwidth >100 GB/s makes frame copy time negligible compared to socket queue locking, rendering per-byte linear slope differences unresolvable on virtual timer resolution].

Tables: see `results/summary.md` sections 'Accept curve' and 'Cost decomposition for config B'. Exclusions: 48 excluded runs/attempts in total (`results/exclusions.md`); steal exclusions per config: A 0/35, B 0/35, C 0/5, D 0/15, E 0/15.

## C4 flood: matched-pps ceiling and CPU per matched packet, A vs B (R-C4)

**Verdict: NOT SUPPORTED**

flow-matched pps ceiling B - A = -4.56e+04 pps, 95% CI [-5.09e+04, -4.03e+04] (B higher = CI > 0: False); net CPU per flow-matched packet A/B factor = 0.863, 95% CI [0.852, 0.874] (A costs more = CI > 1: False). A saturated (socket drops > 1% of packets reaching it) in 0 of 5 valid runs; where it did not, A's figure is offered-load-limited, not a ceiling. C4's CSPF ratio is not replicated end-to-end (D6.1 item 5). NOT SUPPORTED as a receiver-drop claim. Reveals a sender-generation bottleneck: offered rates diverge by config because the filter/classifier overhead impacts the sending core's capacity. Config A was offered-load-limited, not receiver-saturated.

Tables: see `results/summary.md` sections 'Flood (C4)'. Exclusions: 48 excluded runs/attempts in total (`results/exclusions.md`); steal exclusions per config: A 0/35, B 0/35, C 0/5, D 0/15, E 0/15.

## Notes

**D6.13.** Initial session idle windows were contaminated by startup noise (0.030 CPU-s/s). V8 correctly caught this for active runs, but idle runs lacked V8. C4 CPU-per-packet recalculated using the quiet calibration idle baseline (0.044 CPU-s/s) to ensure validity. C2/C3 slope verdicts are mathematically invariant to this constant offset (the labels are unchanged between the two baselines; the numbers move in the third digit because the per-packet offset depends slightly on each run's offered rate; the session-idle version is kept in results/session_idle_baseline/).

**D6.14.** Matrix revealed that at >600k pps, the sender's generation context becomes the limiting factor, masking receiver-side drop behavior. This is a valid modern architectural finding. C4: NOT SUPPORTED as a receiver-drop claim. Reveals a sender-generation bottleneck: offered rates diverge by config because the filter/classifier overhead impacts the sending core's capacity. Config A was offered-load-limited, not receiver-saturated.

