# Phase 10 summary

Computed by scripts/p10_summarize.py from logs/p10/ only (rules P1 to P13 of docs/phase10_design.md).

## Final labels

| claim | label | evidence (computed) |
|---|---|---|
| C1 | **BOUNDED** | direction holds in 5 of 6 builds (clang-O0,clang-O2,clang-O3,gcc-O2,gcc-O3), ordering holds in 2 of 6 (clang-O0,gcc-O2); range of R over the builds: F1 [0.656, 1.48]; F2 [1.18, 2.79]; F3 [1.15, 2.88]; F4 [7.67, 19.1] |
| C2 | **INCONCLUSIVE** | slope data missing or fewer valid batches than the minimum: [('memcpy', 64, 6), ('tr_reject', 64, 2), ('tr_reject', 256, 2), ('tr_reject', 512, 1), ('tr_reject', 1024, 1), ('tr_reject', 1500, 1), ('tr_accept', 64, 3), ('tr_accept', 256, 4), ('tr_accept', 1024, 3), ('tr_accept', 1500, 1), ('tr_port', 512, 1), ('tr_port', 1024, 1), ('tr_port', 1500, 1), ('dr_U', 1024, 7), ('dr_U', 1500, 5), ('dr_E', 256, 6), ('dr_B', 64, 6), ('dr_B', 512, 7), ('dr_B', 1024, 7)] |
| C3 | **INCONCLUSIVE** | slope data missing or fewer valid batches than the minimum: [('memcpy', 64, 6), ('tr_reject', 64, 2), ('tr_reject', 256, 2), ('tr_reject', 512, 1), ('tr_reject', 1024, 1), ('tr_reject', 1500, 1), ('tr_accept', 64, 3), ('tr_accept', 256, 4), ('tr_accept', 1024, 3), ('tr_accept', 1500, 1), ('tr_port', 512, 1), ('tr_port', 1024, 1), ('tr_port', 1500, 1), ('dr_U', 1024, 7), ('dr_U', 1500, 5), ('dr_E', 256, 6), ('dr_B', 64, 6), ('dr_B', 512, 7), ('dr_B', 1024, 7)] |
| C4 | **SUPPORTED** | rate 100000: rho 1.1 [1, 1.21], class UNDECIDED, drops NO-LOSS-BOUND; rate 200000: rho 1.4 [1.29, 1.51], class B-CHEAPER, drops NO-LOSS-BOUND; rate 300000: rho 1.43 [1.33, 1.54], class B-CHEAPER, drops NO-LOSS-BOUND; rate 450000: rho 1.56 [1.46, 1.66], class B-CHEAPER, drops NO-LOSS-BOUND; rate 600000: rho 1.64 [1.5, 1.79], class B-CHEAPER, drops UNDECIDED |
| C4-mitigation | **SUPPORTED** | A: REMOVED, ratio in the baseline topology [1.44, 1.47], in the mitigated topology [0.899, 0.943], Q [0.616, 0.651]; B: REMOVED, ratio in the baseline topology [1.21, 1.23], in the mitigated topology [0.904, 0.92], Q [0.741, 0.759] |
| C5 | **SUPPORTED** | unbounded program rejected (exit 255), bounded program loaded (exit 0) |

## WP1 slopes (ns per byte of frame size; 90% intervals)

| quantity | slope | 90% interval | class | upper end / 148 | upper end / 216 | n |
|---|---|---|---|---|---|---|
| memcpy | n/a | | | | | |
| tr_reject | n/a | | | | | |
| tr_accept | n/a | | | | | |
| tr_port | n/a | | | | | |
| dr_U | n/a | | | | | |
| dr_E | n/a | | | | | |
| dr_B | n/a | | | | | |

WP1 batches: 350 plan rows, 463 re-run attempts, 169 final batches invalid.

## WP2(a) offered load, flood (mean packets per second over valid runs)

| topology | cfg | mean | sd | n |
|---|---|---|---|---|
| T0 | A | 289496.2 | 3355 | 6 |
| T0 | B | 345982.9 | 1846 | 6 |
| T0 | C | 415336.2 | 2600 | 6 |
| T0 | N | 420815.7 | 4241 | 6 |
| T1 | A | 843339.7 | 2.443e+04 | 6 |
| T1 | B | 851473.8 | 4257 | 6 |
| T1 | C | 808770.7 | 1.355e+04 | 6 |
| T1 | N | 776549.2 | 7082 | 6 |

| cfg | R in T0 (95%) | R in T1 (95%) | Q = R(T1)/R(T0) (95%) |
|---|---|---|---|
| A | 1.45 [1.44, 1.47] | 0.921 [0.899, 0.943] | 0.633 [0.616, 0.651] |
| B | 1.22 [1.21, 1.23] | 0.912 [0.904, 0.92] | 0.75 [0.741, 0.759] |
| C | 1.01 [1, 1.02] | 0.96 [0.946, 0.975] | 0.948 [0.931, 0.965] |

Mitigation classes: {'A': 'REMOVED', 'B': 'REMOVED'}. Canary limit of rule P7: 0.03946 CPU-s/s.

## WP2(b) ladder

| rate (pps) | status | valid runs A/B/C | rho = cpu(A)/cpu(B) (95%) | class | drop class |
|---|---|---|---|---|---|
| 100000 | REACHABLE | 6/6/6 | 1.1 [1, 1.21] | UNDECIDED | NO-LOSS-BOUND |
| 200000 | REACHABLE | 6/6/6 | 1.4 [1.29, 1.51] | B-CHEAPER | NO-LOSS-BOUND |
| 300000 | REACHABLE | 6/6/6 | 1.43 [1.33, 1.54] | B-CHEAPER | NO-LOSS-BOUND |
| 450000 | REACHABLE | 6/6/6 | 1.56 [1.46, 1.66] | B-CHEAPER | NO-LOSS-BOUND |
| 600000 | REACHABLE | 6/6/6 | 1.64 [1.5, 1.79] | B-CHEAPER | UNDECIDED |

## WP3 C1: ratio CSPF/BPF per filter (95% interval over chunks), primary pairing

| build | F1 | F2 | F3 | F4 | direction | ordering |
|---|---|---|---|---|---|---|
| clang-O0 | 1.48 [1.48, 1.48] | 2.78 [2.78, 2.79] | 2.87 [2.87, 2.88] | 19 [18.9, 19.1] | HOLDS | HOLDS |
| clang-O2 | 1.39 [1.39, 1.39] | 2.58 [2.57, 2.58] | 2.41 [2.41, 2.42] | 16.4 [16.3, 16.4] | HOLDS | FAILS |
| clang-O3 | 1.16 [1.16, 1.16] | 2.37 [2.37, 2.38] | 2.29 [2.28, 2.29] | 15.2 [15.1, 15.3] | HOLDS | FAILS |
| gcc-O0 | 0.656 [0.656, 0.656] | 1.18 [1.18, 1.18] | 1.15 [1.15, 1.15] | 7.71 [7.67, 7.74] | REVERSED | FAILS |
| gcc-O2 | 1.1 [1.1, 1.1] | 2.51 [2.5, 2.52] | 2.61 [2.6, 2.61] | 16.1 [16, 16.1] | HOLDS | HOLDS |
| gcc-O3 | 1.36 [1.36, 1.36] | 2.77 [2.76, 2.78] | 2.77 [2.76, 2.77] | 17.2 [17.1, 17.3] | HOLDS | FAILS |

Phase 10 verify (`scripts/p10_verify.sh`) checks these files against the rules.

