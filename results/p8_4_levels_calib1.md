# Phase 8.4: noise levels chosen from the calibration probe (script-computed)

Baseline per-CPU busy rate (3 windows, workers stopped): cpu0 0.0697, cpu1 0.0623, cpu2 0.0577, cpu3 0.0600, cpu4 0.0607. Largest added rate on a core that was not noised in any window: 0.1083 CPU-s/s.

## E1 (cores 0,1; V8 limit 0.0826)

| type | target added rate | chosen nominal duty (%) | measured added rate | ratio to target |
|---|---|---|---|---|
| cpu | 0.010 | 5 | 0.0025 | 0.25 |
| cpu | 0.025 | 1 | 0.0985 | 3.94 |
| cpu | 0.050 | 1 | 0.0985 | 1.97 |
| cpu | 0.100 | 1 | 0.0985 | 0.98 |
| cpu | 0.200 | 10 | 0.1930 | 0.96 |
| cache | 0.010 | 7.5 | 0.0295 | 2.95 |
| cache | 0.025 | 7.5 | 0.0295 | 1.18 |
| cache | 0.050 | 10 | 0.0750 | 1.50 |
| cache | 0.100 | 10 | 0.0750 | 0.75 |
| cache | 0.200 | 15 | 0.1790 | 0.89 |

## E2 (core 0; V8 limit 0.0443)

| type | target added rate | chosen nominal duty (%) | measured added rate | ratio to target |
|---|---|---|---|---|
| cpu | 0.010 | 4 | 0.0143 | 1.43 |
| cpu | 0.025 | 7.5 | 0.0143 | 0.57 |
| cpu | 0.050 | 10 | 0.0453 | 0.91 |
| cpu | 0.100 | 1 | 0.0963 | 0.96 |
| cache | 0.010 | 7.5 | 0.0143 | 1.43 |
| cache | 0.025 | 10 | 0.0403 | 1.61 |
| cache | 0.050 | 10 | 0.0403 | 0.81 |
| cache | 0.100 | 15 | 0.0841 | 0.84 |

## E3

| condition | chosen nominal duty (%) | measured added rate |
|---|---|---|
| cpu_core2 | 20 | 0.1433 |
| cpu_core3 | 20 | 0.1400 |
| vm (S3) | holds 2048 MB | MemAvailable 3096 -> 1059 MB |

All measured added rates by (type, cores, nominal duty):

| type | cores | duty | added CPU-s/s (mean of windows) | windows |
|---|---|---|---|---|
| cache | 0 | 1 | -0.0477 | 1 |
| cache | 0 | 2 | -0.0397 | 1 |
| cache | 0 | 3 | -0.0327 | 1 |
| cache | 0 | 4 | -0.0177 | 1 |
| cache | 0 | 5 | -0.0057 | 1 |
| cache | 0 | 7.5 | 0.0143 | 1 |
| cache | 0 | 10 | 0.0403 | 1 |
| cache | 0 | 15 | 0.0841 | 1 |
| cache | 0 | 20 | 0.1343 | 1 |
| cache | 0 | 30 | 0.2293 | 1 |
| cache | 0 | 40 | 0.3313 | 1 |
| cache | 0,1 | 1 | -0.0855 | 2 |
| cache | 0,1 | 2 | -0.0740 | 2 |
| cache | 0,1 | 3 | -0.0515 | 2 |
| cache | 0,1 | 4 | -0.0365 | 2 |
| cache | 0,1 | 5 | -0.0230 | 2 |
| cache | 0,1 | 7.5 | 0.0295 | 2 |
| cache | 0,1 | 10 | 0.0750 | 2 |
| cache | 0,1 | 15 | 0.1790 | 2 |
| cache | 0,1 | 20 | 0.2700 | 2 |
| cache | 0,1 | 30 | 0.4634 | 2 |
| cache | 0,1 | 40 | 0.6559 | 2 |
| cpu | 0 | 1 | 0.0963 | 1 |
| cpu | 0 | 2 | -0.0287 | 1 |
| cpu | 0 | 3 | -0.0177 | 1 |
| cpu | 0 | 4 | 0.0143 | 1 |
| cpu | 0 | 5 | -0.0117 | 1 |
| cpu | 0 | 7.5 | 0.0143 | 1 |
| cpu | 0 | 10 | 0.0453 | 1 |
| cpu | 0 | 15 | 0.0863 | 1 |
| cpu | 0 | 20 | 0.1393 | 1 |
| cpu | 0 | 30 | 0.2303 | 1 |
| cpu | 0 | 40 | 0.3303 | 1 |
| cpu | 0,1 | 1 | 0.0985 | 2 |
| cpu | 0,1 | 2 | -0.0170 | 2 |
| cpu | 0,1 | 3 | -0.0687 | 2 |
| cpu | 0,1 | 4 | -0.0185 | 2 |
| cpu | 0,1 | 5 | 0.0025 | 2 |
| cpu | 0,1 | 7.5 | 0.1184 | 2 |
| cpu | 0,1 | 10 | 0.1930 | 2 |
| cpu | 0,1 | 15 | 0.2905 | 2 |
| cpu | 0,1 | 20 | 0.3515 | 2 |
| cpu | 0,1 | 30 | 0.5485 | 2 |
| cpu | 0,1 | 40 | 0.7830 | 2 |
| cpu | 2 | 5 | -0.0007 | 1 |
| cpu | 2 | 10 | 0.0453 | 1 |
| cpu | 2 | 20 | 0.1433 | 1 |
| cpu | 2 | 40 | 0.3383 | 1 |
| cpu | 3 | 5 | -0.0060 | 1 |
| cpu | 3 | 10 | 0.0460 | 1 |
| cpu | 3 | 20 | 0.1400 | 1 |
| cpu | 3 | 40 | 0.3390 | 1 |
| vm | 3 | 100 | -0.0480 | 1 |
