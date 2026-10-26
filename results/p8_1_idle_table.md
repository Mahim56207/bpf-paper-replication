# Phase 8.1: idle CPU and canary rates (computed by scripts/p8_1_stats.py from the run logs)

Definitions as in the Phase 6 calibration (`scripts/summarize.py` `baseline`): idle rate = system-wide busy CPU-s per s over the window with the matrix harness attached and no traffic; canary rate = busy CPU-s on the canary cores / window; canary_max = max over the 3 windows. V8 limit for cores {0,1} = 1.2 x 0.0689 = 0.0826 CPU-s/s (calibration canary_max from `results/baseline_calibration.json`).

| window set | idle rate mean | idle rate max | x quiet calibration | canary {0,1} max | canary {0} max | windows over the V8 limit |
|---|---|---|---|---|---|---|
| Phase 6 quiet calibration session | 0.131 | 0.180 | 1.0x | 0.0689 | 0.0369 | 0 of 3 |
| Phase 6 matrix session start (noisy) | 0.843 | 0.924 | 6.5x | 0.3995 | 0.2157 | 3 of 3 |
| Phase 8.1 desktopnow | 0.801 | 1.052 | 6.1x | 0.4575 | 0.2378 | 3 of 3 |
| Phase 8.1 desktopquiet | 0.826 | 1.272 | 6.3x | 0.5282 | 0.2466 | 2 of 3 |
| Phase 8.1 desktopsettled | 0.126 | 0.139 | 1.0x | 0.0569 | 0.0340 | 0 of 3 |

Reference numbers recorded in earlier phases (D6.8, D6.13): quiet calibration 0.131 and canary_max 0.0689 on {0,1}; noisy matrix start 0.843. The rows above recompute them from the logs: the calibration row should read 0.131 / 0.0689 and the matrix row 0.843 (rounded).

## Per window

| set | window | length s | idle rate | canary {0,1} | canary {0} | steal % | classifier T | per-CPU busy (cpu0..cpu4) |
|---|---|---|---|---|---|---|---|---|
| Phase 6 quiet calibration session | calibration_idle_1.log | 10.02 | 0.1008 | 0.0339 | 0.0170 | 0.00 | 0 | 0.017 / 0.017 / 0.028 / 0.019 / 0.021 |
| Phase 6 quiet calibration session | calibration_idle_2.log | 10.03 | 0.1117 | 0.0429 | 0.0189 | 0.00 | 0 | 0.019 / 0.024 / 0.024 / 0.021 / 0.021 |
| Phase 6 quiet calibration session | calibration_idle_3.log | 10.02 | 0.1796 | 0.0689 | 0.0369 | 0.00 | 0 | 0.037 / 0.032 / 0.036 / 0.030 / 0.044 |
| Phase 6 matrix session start (noisy) | bench_D_idle_0_1.log | 10.01 | 0.7013 | 0.2797 | 0.1409 | 0.00 | 0 | 0.141 / 0.139 / 0.138 / 0.138 / 0.146 |
| Phase 6 matrix session start (noisy) | bench_D_idle_0_2.log | 10.01 | 0.9238 | 0.3995 | 0.2157 | 0.00 | 0 | 0.216 / 0.184 / 0.193 / 0.169 / 0.164 |
| Phase 6 matrix session start (noisy) | bench_D_idle_0_3.log | 10.01 | 0.9050 | 0.3666 | 0.1868 | 0.00 | 0 | 0.187 / 0.180 / 0.187 / 0.179 / 0.173 |
| Phase 8.1 desktopnow | p81desktopnow_D_idle_0_1.log | 10.01 | 0.9760 | 0.3936 | 0.2038 | 0.00 | 0 | 0.204 / 0.190 / 0.196 / 0.194 / 0.192 |
| Phase 8.1 desktopnow | p81desktopnow_D_idle_0_2.log | 10.01 | 1.0519 | 0.4575 | 0.2378 | 0.00 | 0 | 0.238 / 0.220 / 0.194 / 0.200 / 0.201 |
| Phase 8.1 desktopnow | p81desktopnow_D_idle_0_3.log | 10.01 | 0.3756 | 0.1738 | 0.0829 | 0.00 | 0 | 0.083 / 0.091 / 0.065 / 0.077 / 0.065 |
| Phase 8.1 desktopquiet | p81desktopquiet_D_idle_0_1.log | 10.01 | 1.0859 | 0.4466 | 0.2218 | 0.00 | 0 | 0.222 / 0.225 / 0.213 / 0.215 / 0.211 |
| Phase 8.1 desktopquiet | p81desktopquiet_D_idle_0_2.log | 10.01 | 1.2721 | 0.5282 | 0.2466 | 0.00 | 0 | 0.247 / 0.282 / 0.250 / 0.260 / 0.234 |
| Phase 8.1 desktopquiet | p81desktopquiet_D_idle_0_3.log | 10.01 | 0.1209 | 0.0490 | 0.0290 | 0.00 | 0 | 0.029 / 0.020 / 0.023 / 0.024 / 0.024 |
| Phase 8.1 desktopsettled | p81desktopsettled_D_idle_0_1.log | 10.01 | 0.1109 | 0.0429 | 0.0230 | 0.00 | 0 | 0.023 / 0.020 / 0.021 / 0.025 / 0.022 |
| Phase 8.1 desktopsettled | p81desktopsettled_D_idle_0_2.log | 10.01 | 0.1388 | 0.0569 | 0.0340 | 0.00 | 0 | 0.034 / 0.023 / 0.025 / 0.029 / 0.029 |
| Phase 8.1 desktopsettled | p81desktopsettled_D_idle_0_3.log | 10.01 | 0.1289 | 0.0519 | 0.0270 | 0.00 | 0 | 0.027 / 0.025 / 0.021 / 0.025 / 0.030 |
