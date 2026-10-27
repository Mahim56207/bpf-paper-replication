# Phase 8.4: does V8 do what it is supposed to do? (computed by scripts/p8_4_summary.py from the logs only)

Windows: 720 logs in 7 launches. V8 limits: 0.0826 for canary cores {0,1} (E1, E3), 0.0443 for {0} (E2). Tolerance delta = 5%. Metric: E1/E3 net CPU ns per flow-scoped matched packet (system-wide, idle baseline 0.1307); E2 offered packets per second. Windows excluded by the harness-integrity rules V1, V2, V5', V6: 0.

## E1 paced curve, config B, 512 B, 32000 pps, noise on cores {0,1}, cpu noise

| level | n (excluded) | mean canary rate | added canary rate | flagged | Wilson 95% | class | metric mean | R vs level 0 [95%] | shift class | mechanical expectation | R of M_exp [95%] | V4 / V7 / V3 fails | mean socket drops |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 30 (0) | 0.0353 | +0.0000 | 1/30 = 0.03 | [0.01, 0.17] | UNFLAGGED | 2215.91 | 1.000 [1.000, 1.000] | - | n/a | n/a | 3 / 0 / 0 | 0.0002 |
| 1 | 30 (0) | 0.0442 | +0.0089 | 1/30 = 0.03 | [0.01, 0.17] | UNFLAGGED | 1429.55 | 0.645 [-0.264, 1.555] | INDETERMINATE | +12.6% | 0.795 [0.451, 1.138] | 2 / 0 / 0 | 0.0004 |
| 2 | 30 (0) | 0.0653 | +0.0300 | 8/30 = 0.27 | [0.14, 0.44] | TRANSITION | 1931.46 | 0.872 [-0.209, 1.953] | INDETERMINATE | +42.5% | 0.764 [0.441, 1.087] | 3 / 0 / 0 | 0.0002 |
| 3 | 30 (0) | 0.0812 | +0.0459 | 9/30 = 0.30 | [0.17, 0.48] | TRANSITION | 3500.03 | 1.579 [-0.232, 3.391] | INDETERMINATE | +65.0% | 0.968 [0.576, 1.360] | 2 / 0 / 0 | 0.0001 |
| 4 | 30 (0) | 0.1231 | +0.0878 | 30/30 = 1.00 | [0.89, 1.00] | FLAGGED | 4787.35 | 2.160 [-0.253, 4.574] | INDETERMINATE | +124.3% | 0.959 [0.574, 1.344] | 2 / 0 / 0 | 0.0001 |
| 5 | 30 (0) | 0.2271 | +0.1918 | 30/30 = 1.00 | [0.89, 1.00] | FLAGGED | 8291.01 | 3.742 [-0.387, 7.870] | INDETERMINATE | +271.4% | 1.011 [0.578, 1.444] | 3 / 0 / 0 | 0.0002 |

- **False-positive rate at level 0 (rule N1):** 0.033, Wilson upper bound 0.167 -> V8 NOT acceptable at level 0 (threshold 0.10).
- **Premise for E1 cpu: PARTIAL.** FLAGGED levels [4, 5]; UNFLAGGED non-zero levels [1]; TRANSITION or inconclusive levels [2, 3]; needless exclusion (flagged, equivalent): none; blind spot (unflagged, material): none; indeterminate: [4, 5, 1].

## E1 paced curve, config B, 512 B, 32000 pps, noise on cores {0,1}, cache noise

| level | n (excluded) | mean canary rate | added canary rate | flagged | Wilson 95% | class | metric mean | R vs level 0 [95%] | shift class | mechanical expectation | R of M_exp [95%] | V4 / V7 / V3 fails | mean socket drops |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 30 (0) | 0.0231 | +0.0000 | 0/30 = 0.00 | [0.00, 0.11] | UNFLAGGED | 1008.1 | 1.000 [1.000, 1.000] | - | n/a | n/a | 3 / 0 / 0 | 0.0002 |
| 1 | 30 (0) | 0.0531 | +0.0301 | 2/30 = 0.07 | [0.02, 0.21] | UNFLAGGED | 2199.91 | 2.182 [-1.189, 5.554] | INDETERMINATE | +93.5% | 1.057 [0.624, 1.490] | 5 / 0 / 0 | 0.0008 |
| 2 | 30 (0) | 0.0631 | +0.0400 | 5/30 = 0.17 | [0.07, 0.34] | TRANSITION | 2320.58 | 2.302 [-0.968, 5.572] | INDETERMINATE | +124.4% | 1.011 [0.624, 1.397] | 2 / 0 / 0 | 0.0003 |
| 3 | 30 (0) | 0.0860 | +0.0630 | 13/30 = 0.43 | [0.27, 0.61] | TRANSITION | 3238.34 | 3.212 [-1.245, 7.670] | INDETERMINATE | +195.9% | 1.054 [0.649, 1.459] | 3 / 0 / 0 | 0.0003 |
| 4 | 30 (0) | 0.1239 | +0.1008 | 30/30 = 1.00 | [0.89, 1.00] | FLAGGED | 4023.08 | 3.991 [-1.410, 9.391] | INDETERMINATE | +313.6% | 0.962 [0.604, 1.320] | 3 / 0 / 0 | 0.0002 |
| 5 | 30 (0) | 0.2215 | +0.1984 | 30/30 = 1.00 | [0.89, 1.00] | FLAGGED | 8150.49 | 8.085 [-2.675, 18.845] | INDETERMINATE | +617.2% | 1.207 [0.781, 1.634] | 4 / 0 / 0 | 0.0005 |

- **False-positive rate at level 0 (rule N1):** 0.000, Wilson upper bound 0.114 -> V8 NOT acceptable at level 0 (threshold 0.10).
- **Premise for E1 cache: PARTIAL.** FLAGGED levels [4, 5]; UNFLAGGED non-zero levels [1]; TRANSITION or inconclusive levels [2, 3]; needless exclusion (flagged, equivalent): none; blind spot (unflagged, material): none; indeterminate: [4, 5, 1].

## E2 flood, config N, noise on core {0}, cpu noise

| level | n (excluded) | mean canary rate | added canary rate | flagged | Wilson 95% | class | metric mean | R vs level 0 [95%] | shift class | mechanical expectation | R of M_exp [95%] | V4 / V7 / V3 fails | mean socket drops |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 30 (0) | 0.0175 | +0.0000 | 1/30 = 0.03 | [0.01, 0.17] | UNFLAGGED | 1.73158e+06 | 1.000 [1.000, 1.000] | - | n/a | n/a | 0 / 0 / 0 | n/a |
| 1 | 30 (0) | 0.0341 | +0.0166 | 1/30 = 0.03 | [0.01, 0.17] | UNFLAGGED | 1.67764e+06 | 0.969 [0.830, 1.107] | INDETERMINATE | n/a | n/a | 0 / 0 / 0 | n/a |
| 2 | 30 (0) | 0.0525 | +0.0350 | 23/30 = 0.77 | [0.59, 0.88] | TRANSITION | 1.65029e+06 | 0.953 [0.811, 1.095] | INDETERMINATE | n/a | n/a | 0 / 0 / 0 | n/a |
| 3 | 30 (0) | 0.0668 | +0.0493 | 30/30 = 1.00 | [0.89, 1.00] | FLAGGED | 1.62025e+06 | 0.936 [0.793, 1.079] | INDETERMINATE | n/a | n/a | 0 / 0 / 0 | n/a |
| 4 | 30 (0) | 0.1120 | +0.0944 | 30/30 = 1.00 | [0.89, 1.00] | FLAGGED | 1.70137e+06 | 0.983 [0.837, 1.128] | INDETERMINATE | n/a | n/a | 0 / 0 / 0 | n/a |

- **False-positive rate at level 0 (rule N1):** 0.033, Wilson upper bound 0.167 -> V8 NOT acceptable at level 0 (threshold 0.10).
- **Premise for E2 cpu: PARTIAL.** FLAGGED levels [3, 4]; UNFLAGGED non-zero levels [1]; TRANSITION or inconclusive levels [2]; needless exclusion (flagged, equivalent): none; blind spot (unflagged, material): none; indeterminate: [3, 4, 1].

## E2 flood, config N, noise on core {0}, cache noise

| level | n (excluded) | mean canary rate | added canary rate | flagged | Wilson 95% | class | metric mean | R vs level 0 [95%] | shift class | mechanical expectation | R of M_exp [95%] | V4 / V7 / V3 fails | mean socket drops |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 30 (0) | 0.0200 | +0.0000 | 1/30 = 0.03 | [0.01, 0.17] | UNFLAGGED | 1.65367e+06 | 1.000 [1.000, 1.000] | - | n/a | n/a | 0 / 0 / 0 | n/a |
| 1 | 30 (0) | 0.0348 | +0.0148 | 3/30 = 0.10 | [0.03, 0.26] | UNFLAGGED | 1.67791e+06 | 1.015 [0.863, 1.167] | INDETERMINATE | n/a | n/a | 0 / 0 / 0 | n/a |
| 2 | 30 (0) | 0.0536 | +0.0336 | 19/30 = 0.63 | [0.46, 0.78] | TRANSITION | 1.66563e+06 | 1.007 [0.855, 1.159] | INDETERMINATE | n/a | n/a | 0 / 0 / 0 | n/a |
| 3 | 30 (0) | 0.0809 | +0.0609 | 30/30 = 1.00 | [0.89, 1.00] | FLAGGED | 1.68525e+06 | 1.019 [0.867, 1.172] | INDETERMINATE | n/a | n/a | 0 / 0 / 0 | n/a |
| 4 | 30 (0) | 0.1173 | +0.0973 | 30/30 = 1.00 | [0.89, 1.00] | FLAGGED | 1.71685e+06 | 1.038 [0.889, 1.188] | INDETERMINATE | n/a | n/a | 0 / 0 / 0 | n/a |

- **False-positive rate at level 0 (rule N1):** 0.033, Wilson upper bound 0.167 -> V8 NOT acceptable at level 0 (threshold 0.10).
- **Premise for E2 cache: PARTIAL.** FLAGGED levels [3, 4]; UNFLAGGED non-zero levels [1]; TRANSITION or inconclusive levels [2]; needless exclusion (flagged, equivalent): none; blind spot (unflagged, material): none; indeterminate: [3, 4, 1].

## Overall: V8's premise is **PARTIAL**

| family | verdict |
|---|---|
| E1 cpu | PARTIAL |
| E1 cache | PARTIAL |
| E2 cpu | PARTIAL |
| E2 cache | PARTIAL |

## Drift: level-0 metric mean per launch

| family | launch | n | metric mean |
|---|---|---|---|
| E1 cache | C1 | 10 | 4374.5 |
| E1 cache | C2 | 10 | -329.693 |
| E1 cache | C3 | 10 | -1020.5 |
| E1 cpu | C1 | 10 | 6865.01 |
| E1 cpu | C2 | 10 | -222.68 |
| E1 cpu | C3 | 10 | 5.40979 |
| E2 cache | F1 | 10 | 1.08491e+06 |
| E2 cache | F2 | 10 | 2.01885e+06 |
| E2 cache | F3 | 10 | 1.85725e+06 |
| E2 cpu | F1 | 10 | 1.07467e+06 |
| E2 cpu | F2 | 10 | 2.03239e+06 |
| E2 cpu | F3 | 10 | 2.08767e+06 |

## E3: noise V8 cannot see (config B, 512 B, 32000 pps; canary cores quiet)

| condition | n (excluded) | mean canary rate | flagged | Wilson 95% | class | M_sys mean | R vs S0 [95%] | shift class | blind |
|---|---|---|---|---|---|---|---|---|---|
| S0 control | 15 (0) | 0.0357 | 0/15 = 0.00 | [0.00, 0.20] | UNFLAGGED | 3086.24 | 1.000 [1.000, 1.000] | - | - |
| S1 cpu noise on core 2 (capture) | 15 (0) | 0.0343 | 1/15 = 0.07 | [0.01, 0.30] | UNFLAGGED | 6608.98 | 2.141 [0.831, 3.452] | INDETERMINATE | False |
| S2 cpu noise on core 3 (server) | 15 (0) | 0.0391 | 2/15 = 0.13 | [0.04, 0.38] | TRANSITION | 7014.65 | 2.273 [0.935, 3.611] | INDETERMINATE | False |
| S3 global memory pressure | 15 (0) | 0.0280 | 0/15 = 0.00 | [0.00, 0.20] | UNFLAGGED | 2721.66 | 0.882 [0.222, 1.542] | INDETERMINATE | False |

Excluded windows (V1, V2, V5', V6): none.

