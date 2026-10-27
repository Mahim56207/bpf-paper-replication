# Phase 8.4, amendment A4: blocked re-analysis (POST HOC, computed by scripts/p8_4_blocked.py)

Written after the pooled analysis (`results/p8_4_summary.md`) had been seen; the pooled analysis is the pre-declared primary result and its numbers are unchanged. Here every level is compared with level 0 **inside each launch** (3 launches per family, 10 windows per cell and launch), the differences are averaged over the launches, and the interval uses the launch-wise variances (Satterthwaite df, exact t). Tolerance delta = 5%, scale: E2 = mean level-0 offered pps; E1 = mean level-0 gross CPU per flow-scoped matched packet (the net metric's level-0 mean is near zero or negative in some launches).

## E1 paced curve, cpu noise

Reference scale for the tolerance: 6313.42 ns per packet (gross). Level-0 mean of the metric per launch: C1 6865.01, C2 -222.68, C3 5.40979.

Information only (A4 item c): level-0 mean of the net metric with each launch's own pre-flight idle rate (C1 0.1027, C2 0.1090, C3 0.1610): C1 7743.2, C2 456.7, C3 -944.4 (with the fixed 0.1307: C1 6865.0, C2 -222.7, C3 5.4).

| level | injected/added canary (mean) | flagged (pooled) | class | D = blocked shift [95%] | shift / scale [95%] | per-launch d | shift class | mechanical expectation / scale |
|---|---|---|---|---|---|---|---|---|
| 1 | +0.0089 | 0.03 | UNFLAGGED | -786.36 [-3174.25, 1601.53] | -12.5% [-50.3%, +25.4%] | -1782, -1458, 880 | INDETERMINATE | +4.4% |
| 2 | +0.0300 | 0.27 | TRANSITION | -284.455 [-2725.12, 2156.21] | -4.5% [-43.2%, +34.2%] | -2397, 577.5, 965.8 | INDETERMINATE | +14.9% |
| 3 | +0.0459 | 0.30 | TRANSITION | 1284.11 [-1220.85, 3789.08] | +20.3% [-19.3%, +60.0%] | -672.4, 2513, 2012 | INDETERMINATE | +22.8% |
| 4 | +0.0878 | 1.00 | FLAGGED | 2571.44 [69.1489, 5073.73] | +40.7% [+1.1%, +80.4%] | 277.5, 2853, 4584 | MATERIAL | +43.6% |
| 5 | +0.1918 | 1.00 | FLAGGED | 6075.1 [3220.49, 8929.71] | +96.2% [+51.0%, +141.4%] | 4792, 7349, 6084 | MATERIAL | +95.2% |

- **Blocked premise for E1 cpu: PARTIAL.** FLAGGED levels [4, 5], UNFLAGGED non-zero levels [1], TRANSITION [2, 3]; needless exclusion: none; blind spot: none; INDETERMINATE: [1, 2, 3].

- **Dose-response (launch intercepts, 180 windows):** metric changes by 4.385e+04 [3.798e+04, 4.972e+04] ns per packet per CPU-s/s of measured canary rate; adding the canary CPU alone would give 3.135e+04 (E1) / 0 (E2).

## E1 paced curve, cache noise

Reference scale for the tolerance: 5106.15 ns per packet (gross). Level-0 mean of the metric per launch: C1 4374.5, C2 -329.693, C3 -1020.5.

Information only (A4 item c): level-0 mean of the net metric with each launch's own pre-flight idle rate (C1 0.1027, C2 0.1090, C3 0.1610): C1 5252.7, C2 349.8, C3 -1970.5 (with the fixed 0.1307: C1 4374.5, C2 -329.7, C3 -1020.5).

| level | injected/added canary (mean) | flagged (pooled) | class | D = blocked shift [95%] | shift / scale [95%] | per-launch d | shift class | mechanical expectation / scale |
|---|---|---|---|---|---|---|---|---|
| 1 | +0.0301 | 0.07 | UNFLAGGED | 1191.81 [-799.126, 3182.75] | +23.3% [-15.7%, +62.3%] | 599.2, 1266, 1710 | INDETERMINATE | +18.5% |
| 2 | +0.0400 | 0.17 | TRANSITION | 1312.47 [16.3728, 2608.58] | +25.7% [+0.3%, +51.1%] | 1496, 454.2, 1987 | MATERIAL | +24.6% |
| 3 | +0.0630 | 0.43 | TRANSITION | 2230.23 [758.407, 3702.06] | +43.7% [+14.9%, +72.5%] | 2303, 1444, 2944 | MATERIAL | +38.7% |
| 4 | +0.1008 | 1.00 | FLAGGED | 3014.98 [1639.43, 4390.53] | +59.0% [+32.1%, +86.0%] | 2375, 3350, 3320 | MATERIAL | +61.9% |
| 5 | +0.1984 | 1.00 | FLAGGED | 7142.39 [5712.43, 8572.35] | +139.9% [+111.9%, +167.9%] | 6019, 8023, 7386 | MATERIAL | +121.8% |

- **Blocked premise for E1 cache: PARTIAL.** FLAGGED levels [4, 5], UNFLAGGED non-zero levels [1], TRANSITION [2, 3]; needless exclusion: none; blind spot: none; INDETERMINATE: [1].

- **Dose-response (launch intercepts, 180 windows):** metric changes by 3.913e+04 [3.352e+04, 4.475e+04] ns per packet per CPU-s/s of measured canary rate; adding the canary CPU alone would give 3.135e+04 (E1) / 0 (E2).

## E2 flood, cpu noise

Reference scale for the tolerance: 1.73158e+06 pps. Level-0 mean of the metric per launch: F1 1.07467e+06, F2 2.03239e+06, F3 2.08767e+06.

| level | injected/added canary (mean) | flagged (pooled) | class | D = blocked shift [95%] | shift / scale [95%] | per-launch d | shift class | mechanical expectation / scale |
|---|---|---|---|---|---|---|---|---|
| 1 | +0.0166 | 0.03 | UNFLAGGED | -53937.9 [-138588, 30711.8] | -3.1% [-8.0%, +1.8%] | 1.974e+04, -5.423e+04, -1.273e+05 | INDETERMINATE | n/a |
| 2 | +0.0350 | 0.77 | TRANSITION | -81281.2 [-185700, 23138.1] | -4.7% [-10.7%, +1.3%] | -1.601e+04, -1.063e+04, -2.172e+05 | INDETERMINATE | n/a |
| 3 | +0.0493 | 1.00 | FLAGGED | -111323 [-231016, 8368.91] | -6.4% [-13.3%, +0.5%] | -2.204e+04, 2.283e+04, -3.348e+05 | INDETERMINATE | n/a |
| 4 | +0.0944 | 1.00 | FLAGGED | -30210.6 [-111346, 50924.5] | -1.7% [-6.4%, +2.9%] | -1.894e+04, 3.786e+04, -1.095e+05 | INDETERMINATE | n/a |

- **Blocked premise for E2 cpu: PARTIAL.** FLAGGED levels [3, 4], UNFLAGGED non-zero levels [1], TRANSITION [2]; needless exclusion: none; blind spot: none; INDETERMINATE: [1, 2, 3, 4].

- **Dose-response (launch intercepts, 150 windows):** metric changes by -3.934e+05 [-1.311e+06, 5.237e+05] pps per CPU-s/s of measured canary rate; adding the canary CPU alone would give 0 (E1) / 0 (E2).

## E2 flood, cache noise

Reference scale for the tolerance: 1.65367e+06 pps. Level-0 mean of the metric per launch: F1 1.08491e+06, F2 2.01885e+06, F3 1.85725e+06.

| level | injected/added canary (mean) | flagged (pooled) | class | D = blocked shift [95%] | shift / scale [95%] | per-launch d | shift class | mechanical expectation / scale |
|---|---|---|---|---|---|---|---|---|
| 1 | +0.0148 | 0.10 | UNFLAGGED | 24247 [-108905, 157399] | +1.5% [-6.6%, +9.5%] | 1.29e+04, 4.961e+04, 1.022e+04 | INDETERMINATE | n/a |
| 2 | +0.0336 | 0.63 | TRANSITION | 11959.4 [-124531, 148450] | +0.7% [-7.5%, +9.0%] | -114.8, 2.375e+04, 1.224e+04 | INDETERMINATE | n/a |
| 3 | +0.0609 | 1.00 | FLAGGED | 31583.2 [-92061.8, 155228] | +1.9% [-5.6%, +9.4%] | -1.633e+04, -1009, 1.121e+05 | INDETERMINATE | n/a |
| 4 | +0.0973 | 1.00 | FLAGGED | 63181.8 [-40381.2, 166745] | +3.8% [-2.4%, +10.1%] | 3998, -1.004e+04, 1.956e+05 | INDETERMINATE | n/a |

- **Blocked premise for E2 cache: PARTIAL.** FLAGGED levels [3, 4], UNFLAGGED non-zero levels [1], TRANSITION [2]; needless exclusion: none; blind spot: none; INDETERMINATE: [1, 2, 3, 4].

- **Dose-response (launch intercepts, 150 windows):** metric changes by -2.731e+05 [-9.908e+05, 4.446e+05] pps per CPU-s/s of measured canary rate; adding the canary CPU alone would give 0 (E1) / 0 (E2).

## Overall (blocked, post hoc): V8's premise is **PARTIAL**

| family | blocked verdict |
|---|---|
| E1 cpu | PARTIAL |
| E1 cache | PARTIAL |
| E2 cpu | PARTIAL |
| E2 cache | PARTIAL |

## Level-0 windows per launch (the blocked analysis needs level 0 in every launch)

| family | C1 | C2 | C3 | F1 | F2 | F3 |
|---|---|---|---|---|---|---|
| E1 cpu | 10 | 10 | 10 | 0 | 0 | 0 |
| E1 cache | 10 | 10 | 10 | 0 | 0 | 0 |
| E2 cpu | 0 | 0 | 0 | 10 | 10 | 10 |
| E2 cache | 0 | 0 | 0 | 10 | 10 | 10 |

## N1 restated (A4 item e)

| family | flagged at level 0 | observed rate | Wilson 95% | exact binomial (Clopper-Pearson) 95% |
|---|---|---|---|---|
| E1 cpu | 1/30 | 0.033 | [0.006, 0.167] | [0.001, 0.172] |
| E1 cache | 0/30 | 0.000 | [0.000, 0.114] | [0.000, 0.116] |
| E2 cpu | 1/30 | 0.033 | [0.006, 0.167] | [0.001, 0.172] |
| E2 cache | 1/30 | 0.033 | [0.006, 0.167] | [0.001, 0.172] |
| all four | 3/120 | 0.025 | [0.009, 0.071] | [0.005, 0.071] |

The pre-declared criterion (Wilson upper bound at most 0.10) needs at least 35 windows even with zero flags, so it was unsatisfiable with 30 windows per family. Restated criterion (A4): the observed false-positive rate is at most 0.10 -> **acceptable** (observed 0.025 over 120 level-0 windows; the 95% interval reaches 0.071).
