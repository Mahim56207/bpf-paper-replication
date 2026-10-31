# Excluded runs and attempts

Every measured run that failed a pre-declared validity rule (V1-V8, V5'a-e; docs/phase6_design.md section 5 and docs/phase6_addenda.md), and every V8 re-run attempt (logs/attempts/), with the rule(s) that failed. Warm-up, calibration, idle and smoke runs are excluded by pre-declaration and not listed.

| file | cfg | traffic | size | rep | attempt | rule(s) |
|---|---|---|---|---|---|---|
| bench_A_flood_256_1_a1.log | A | flood | 256 | 1 | 1 (re-run follows) | V8 canary 0.020 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_A_flood_256_1_a2.log | A | flood | 256 | 1 | 2 (re-run follows) | V8 canary 0.016 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_A_flood_256_2_a1.log | A | flood | 256 | 2 | 1 (re-run follows) | V8 canary 0.016 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_A_flood_256_2_a2.log | A | flood | 256 | 2 | 2 (re-run follows) | V8 canary 0.017 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_A_flood_256_3_a1.log | A | flood | 256 | 3 | 1 (re-run follows) | V8 canary 0.016 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_A_flood_256_3_a2.log | A | flood | 256 | 3 | 2 (re-run follows) | V8 canary 0.018 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_A_flood_256_4_a1.log | A | flood | 256 | 4 | 1 (re-run follows) | V8 canary 0.017 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_A_flood_256_5_a1.log | A | flood | 256 | 5 | 1 (re-run follows) | V8 canary 0.017 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_A_flood_256_5_a2.log | A | flood | 256 | 5 | 2 (re-run follows) | V8 canary 0.018 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_A_m_256_1_a1.log | A | m | 256 | 1 | 1 (re-run follows) | V4 socket drops 741 > 0.1% of 320029; V8 canary 0.632 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_A_m_256_1_a2.log | A | m | 256 | 1 | 2 (re-run follows) | V8 canary 0.483 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_A_m_512_1_a1.log | A | m | 512 | 1 | 1 (re-run follows) | V8 canary 0.465 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_A_m_512_1_a2.log | A | m | 512 | 1 | 2 (re-run follows) | V8 canary 0.412 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_A_m_512_3_a1.log | A | m | 512 | 3 | 1 (re-run follows) | V8 canary 0.024 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_A_m_64_1_a1.log | A | m | 64 | 1 | 1 (re-run follows) | V8 canary 0.018 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_A_nm_1024_2_a1.log | A | nm | 1024 | 2 | 1 (re-run follows) | V8 canary 0.018 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_A_nm_256_1_a1.log | A | nm | 256 | 1 | 1 (re-run follows) | V4 socket drops 1309 > 0.1% of 320042; V8 canary 0.486 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_A_nm_512_2_a1.log | A | nm | 512 | 2 | 1 (re-run follows) | V8 canary 0.019 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_A_nm_64_1_a1.log | A | nm | 64 | 1 | 1 (re-run follows) | V8 canary 0.019 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_A_nm_64_1_a2.log | A | nm | 64 | 1 | 2 (re-run follows) | V4 socket drops 3795 > 0.1% of 320045; V8 canary 0.505 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_B_flood_256_1_a1.log | B | flood | 256 | 1 | 1 (re-run follows) | V8 canary 0.048 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_B_flood_256_1_a2.log | B | flood | 256 | 1 | 2 (re-run follows) | V8 canary 0.090 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_B_flood_256_3_a1.log | B | flood | 256 | 3 | 1 (re-run follows) | V8 canary 0.017 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_B_flood_256_3_a2.log | B | flood | 256 | 3 | 2 (re-run follows) | V8 canary 0.017 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_B_flood_256_4_a1.log | B | flood | 256 | 4 | 1 (re-run follows) | V8 canary 0.015 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_B_flood_256_4_a2.log | B | flood | 256 | 4 | 2 (re-run follows) | V8 canary 0.019 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_B_flood_256_5_a1.log | B | flood | 256 | 5 | 1 (re-run follows) | V8 canary 0.014 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_B_flood_256_5_a2.log | B | flood | 256 | 5 | 2 (re-run follows) | V8 canary 0.020 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_B_m_1024_1_a1.log | B | m | 1024 | 1 | 1 (re-run follows) | V4 socket drops 510 > 0.1% of 320034; V8 canary 0.548 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_B_m_1024_1_a2.log | B | m | 1024 | 1 | 2 (re-run follows) | V4 socket drops 709 > 0.1% of 320030; V8 canary 0.611 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_B_m_256_1_a1.log | B | m | 256 | 1 | 1 (re-run follows) | V4 socket drops 1196 > 0.1% of 320050; V8 canary 0.389 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_B_m_256_1_a2.log | B | m | 256 | 1 | 2 (re-run follows) | V4 socket drops 998 > 0.1% of 320028; V8 canary 0.477 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_B_nm_1500_1_a1.log | B | nm | 1500 | 1 | 1 (re-run follows) | V8 canary 0.493 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_B_nm_1500_1_a2.log | B | nm | 1500 | 1 | 2 (re-run follows) | V8 canary 0.469 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_B_nm_512_1_a1.log | B | nm | 512 | 1 | 1 (re-run follows) | V8 canary 0.430 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_B_nm_512_1_a2.log | B | nm | 512 | 1 | 2 (re-run follows) | V8 canary 0.461 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_C_flood_256_1_a1.log | C | flood | 256 | 1 | 1 (re-run follows) | V8 canary 0.452 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_C_flood_256_1_a2.log | C | flood | 256 | 1 | 2 (re-run follows) | V8 canary 0.551 CPU-s/s > 1.2 x canary_max 0.010 |
| bench_E_m_1024_1_a1.log | E | m | 1024 | 1 | 1 (re-run follows) | V4 socket drops 3397 > 0.1% of 320058; V8 canary 0.486 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_E_m_1024_1_a2.log | E | m | 1024 | 1 | 2 (re-run follows) | V4 socket drops 4151 > 0.1% of 320042; V8 canary 0.640 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_E_m_1500_1_a1.log | E | m | 1500 | 1 | 1 (re-run follows) | V8 canary 0.018 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_E_m_1500_1_a2.log | E | m | 1500 | 1 | 2 (re-run follows) | V8 canary 0.023 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_E_m_1500_2_a1.log | E | m | 1500 | 2 | 1 (re-run follows) | V8 canary 0.019 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_E_m_256_1_a1.log | E | m | 256 | 1 | 1 (re-run follows) | V8 canary 0.021 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_E_m_256_1_a2.log | E | m | 256 | 1 | 2 (re-run follows) | V8 canary 0.469 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_E_m_64_2_a1.log | E | m | 64 | 2 | 1 (re-run follows) | V8 canary 0.019 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_E_m_64_3_a1.log | E | m | 64 | 3 | 1 (re-run follows) | V8 canary 0.019 CPU-s/s > 1.2 x canary_max 0.015 |
| bench_E_m_64_3_a2.log | E | m | 64 | 3 | 2 (re-run follows) | V8 canary 0.018 CPU-s/s > 1.2 x canary_max 0.015 |

Config-level steal rule (V7): runs excluded for steal > 5% / measured runs per config:

- A: 0 / 30
- B: 0 / 30
- C: 0 / 0
- D: 0 / 15
- E: 0 / 15
