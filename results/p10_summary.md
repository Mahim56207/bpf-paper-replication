# Phase 10 summary

Computed by scripts/p10_summarize.py from logs/p10/ only (rules P1 to P13 of docs/phase10_design.md).

## Final labels

| claim | label | evidence (computed) |
|---|---|---|
| C1 | **BOUNDED** | direction holds in 5 of 6 builds (clang-O0,clang-O2,clang-O3,gcc-O2,gcc-O3), ordering holds in 2 of 6 (clang-O0,gcc-O2); range of R over the builds: F1 [0.656, 1.48]; F2 [1.18, 2.79]; F3 [1.15, 2.88]; F4 [7.67, 19.1] |
| C2 | **BOUNDED** | kernel reject slope s_K 0.0005174 ns/byte, 90% interval [-0.0001016, 0.001136], class INSIDE; user path slope s_U 0.05527, 90% interval [0.01183, 0.09871], class INSIDE; d = s_U - s_K 0.05476, 90% interval [0.01131, 0.0982], class INSIDE; ratio of the paper slopes to the upper bound (descriptive, a comparison of different measurement paths): s_K 1.302e+05 and 1.901e+05, s_U 1499 and 2188, d 1507 and 2200; scope: microbenchmarks of the in-kernel filter and of the user-space drain path, not end-to-end capture; same rule on thread CPU time (sensitivity): BOUNDED; original short-batch run (superseded): INCONCLUSIVE |
| C3 | **BOUNDED** | e = s_U - s_E 0.004678 ns/byte, 90% interval [-0.05815, 0.06751], class INSIDE; s_U 0.05527, s_E 0.05059, s_B 0.04546; ratio of the paper slopes to the upper bound (descriptive, a comparison of different measurement paths): e 2192 and 3200, s_U 1499 and 2188, s_E 1531 and 2234; scope: microbenchmarks of the in-kernel filter and of the user-space drain path, not end-to-end capture; same rule on thread CPU time (sensitivity): BOUNDED; original short-batch run (superseded): INCONCLUSIVE |
| C4 | **SUPPORTED** | rate 100000: rho 1.1 [1, 1.21], class UNDECIDED, drops NO-LOSS-BOUND; rate 200000: rho 1.4 [1.29, 1.51], class B-CHEAPER, drops NO-LOSS-BOUND; rate 300000: rho 1.43 [1.33, 1.54], class B-CHEAPER, drops NO-LOSS-BOUND; rate 450000: rho 1.56 [1.46, 1.66], class B-CHEAPER, drops NO-LOSS-BOUND; rate 600000: rho 1.64 [1.5, 1.79], class B-CHEAPER, drops UNDECIDED |
| C4-mitigation | **SUPPORTED** | A: REVERSED, ratio no-capture over this configuration in the baseline topology [1.44, 1.47], in the mitigated topology [0.899, 0.943], Q [0.616, 0.651]; B: REVERSED, ratio no-capture over this configuration in the baseline topology [1.21, 1.23], in the mitigated topology [0.904, 0.92], Q [0.741, 0.759]; reading: a ratio below one means the configuration with capture attached offered more load than the configuration without capture, so the gap is reversed, not just closed; the causes of the reversal are UNVERIFIED |
| C5 | **SUPPORTED** | unbounded program rejected (exit 255), bounded program loaded (exit 0) |
| C2 (WP1 original) | **INCONCLUSIVE** | slope data missing or fewer valid batches than the minimum: [('memcpy', 64, 6), ('tr_reject', 64, 2), ('tr_reject', 256, 2), ('tr_reject', 512, 1), ('tr_reject', 1024, 1), ('tr_reject', 1500, 1), ('tr_accept', 64, 3), ('tr_accept', 256, 4), ('tr_accept', 1024, 3), ('tr_accept', 1500, 1), ('tr_port', 512, 1), ('tr_port', 1024, 1), ('tr_port', 1500, 1), ('dr_U', 1024, 7), ('dr_U', 1500, 5), ('dr_E', 256, 6), ('dr_B', 64, 6), ('dr_B', 512, 7), ('dr_B', 1024, 7)] |
| C3 (WP1 original) | **INCONCLUSIVE** | slope data missing or fewer valid batches than the minimum: [('memcpy', 64, 6), ('tr_reject', 64, 2), ('tr_reject', 256, 2), ('tr_reject', 512, 1), ('tr_reject', 1024, 1), ('tr_reject', 1500, 1), ('tr_accept', 64, 3), ('tr_accept', 256, 4), ('tr_accept', 1024, 3), ('tr_accept', 1500, 1), ('tr_port', 512, 1), ('tr_port', 1024, 1), ('tr_port', 1500, 1), ('dr_U', 1024, 7), ('dr_U', 1500, 5), ('dr_E', 256, 6), ('dr_B', 64, 6), ('dr_B', 512, 7), ('dr_B', 1024, 7)] |

## C2 and C3 as intervals (WP1b, ns per byte of frame size, 90% intervals) and the 1993 slopes

Scope: WP1b measures the in-kernel filter (BPF_PROG_TEST_RUN) and the user-space drain path of an AF_PACKET queue as microbenchmarks; it does not measure end-to-end capture.

| quantity | estimate | 90% interval | class (delta = 10 ns/byte, frozen) | 148 / upper bound | 216 / upper bound |
|---|---|---|---|---|---|
| s_K, kernel reject_all (test run) | 0.0005174 | [-0.0001016, 0.001136] | INSIDE | 1.3e+05 | 1.9e+05 |
| s_U, user-space drain path U | 0.05527 | [0.01183, 0.09871] | INSIDE | 1.5e+03 | 2.19e+03 |
| d = s_U - s_K (claim C2) | 0.05476 | [0.01131, 0.0982] | INSIDE | 1.51e+03 | 2.2e+03 |
| s_E, in-kernel accept-all drain path E | 0.05059 | [0.004503, 0.09669] | INSIDE | 1.53e+03 | 2.23e+03 |
| e = s_U - s_E (claim C3) | 0.004678 | [-0.05815, 0.06751] | INSIDE | 2.19e+03 | 3.2e+03 |
| s_memcpy, copy floor | 0.01047 | [0.007088, 0.01385] | INSIDE | 1.07e+04 | 1.56e+04 |
| s_U - s_memcpy (post hoc, descriptive) | 0.04481 | [0.001243, 0.08837] | INSIDE | 1.67e+03 | 2.44e+03 |

The two last columns are the ratio of the 1993 slopes (148 ns/byte for the BPF filter, 216 ns/byte for NIT, from the paper) to the upper bound of the interval of this study: a comparison of different measurement paths (different machine, kernel, and code path), not a replication; a blank means the upper bound is not positive.

Copy floor against the user path: the difference of the user-path slope and the copy-floor slope has an interval that excludes zero, so the two slopes differ at this precision; their own intervals overlap (post hoc and descriptive: this comparison is not one of the frozen rules and carries no label).


## WP1b slopes (ns per byte of frame size; 90% intervals; long batches; these carry the C2 and C3 labels)

| quantity | slope (wall based) | 90% interval | class | slope (thread CPU) | 90% interval | class | n |
|---|---|---|---|---|---|---|---|
| memcpy | 0.01047 | [0.007088, 0.01385] | INSIDE | 0.01046 | [0.007086, 0.01384] | INSIDE | 60 |
| tr_reject | 0.0005174 | [-0.0001016, 0.001136] | INSIDE | 0.0004858 | [-9.677e-05, 0.001068] | INSIDE | 60 |
| tr_accept | -0.0003757 | [-0.001001, 0.0002499] | INSIDE | -0.0003548 | [-0.0009465, 0.0002369] | INSIDE | 60 |
| tr_port | -0.0003894 | [-0.001728, 0.0009491] | INSIDE | -0.0003074 | [-0.001559, 0.0009443] | INSIDE | 60 |
| dr_U | 0.05527 | [0.01183, 0.09871] | INSIDE | 0.05514 | [0.01177, 0.09851] | INSIDE | 60 |
| dr_E | 0.05059 | [0.004503, 0.09669] | INSIDE | 0.05087 | [0.004614, 0.09712] | INSIDE | 60 |
| dr_B | 0.04546 | [-0.002467, 0.09339] | INSIDE | 0.04587 | [-0.001806, 0.09354] | INSIDE | 60 |

WP1b batches: 420 plan rows, 421 attempts, 1 re-run attempts, 420 valid batches, 0 final batches invalid, shortest measured wall time of a valid batch 5 s.


## WP1 slopes, original batches (superseded by WP1b when WP1b is present; ns per byte of frame size; 90% intervals)

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

Mitigation classes: {'A': 'REVERSED', 'B': 'REVERSED'}. Canary limit of rule P7: 0.03946 CPU-s/s.

R is the mean offered load of the no-capture configuration over that of the capture configuration in the same topology. A value below one in the mitigated topology means that the configuration with capture attached offered MORE load than the one without capture: the gap is reversed. The causes of that reversal are UNVERIFIED; no run isolated them.

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

