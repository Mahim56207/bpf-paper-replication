# Phase 8.2: is the flood's offered load limited by the capture taps in the sender's transmit path?

Computed by `scripts/p8_2_summary.py` from `logs/p8/p8_2/` only; rules: `docs/phase8_2_design.md`. Offered rate = packets per second summed over both streams (client JSON packets / measured window), unprofiled valid runs; 95% intervals; Welch for differences.

## 1. Runs

Plan rows: 40; final logs found: 40; missing: none; earlier attempts kept in `attempts/` (V8 re-runs): 3.

| config | unprofiled valid / planned | profiled valid / planned | exclusions (final attempts) |
|---|---|---|---|
| N | 6 / 6 | 4 / 4 | none |
| A | 6 / 6 | 4 / 4 | none |
| B | 6 / 6 | 4 / 4 | none |
| C | 6 / 6 | 4 / 4 | none |

## 2. Offered rate (unprofiled valid runs)

| config | n | mean offered pps | sd | 95% CI of the mean | sender cores {1,4} busy (CPU-s/s per core) | profiled runs: mean offered pps | profiling effect |
|---|---|---|---|---|---|---|---|
| N | 6 | 2047448 | 56075 | [1988601, 2106296] | 0.998 | 2003034 | 0.978 |
| A | 6 | 1231731 | 85955 | [1141527, 1321936] | 0.998 | 1264071 | 1.026 |
| B | 6 | 1403339 | 82111 | [1317169, 1489510] | 0.998 | 1456013 | 1.038 |
| C | 6 | 2016726 | 18169 | [1997659, 2035793] | 0.998 | 1885725 | 0.935 |

## 3. S-H1: offered(N) above offered(A) and above offered(B)

| comparison | mean difference | 95% CI | Welch df | lower bound above 0 |
|---|---|---|---|---|
| N - A | 815717 | [720267, 911168] | 8.6 | yes |
| N - B | 644109 | [552013, 736206] | 8.8 | yes |
| N - C (not gating) | 30723 | [-28070, 89515] | 6.0 | no |

**S-H1 holds.**

## 4. Profiles: share of sender samples with `packet_rcv` in the stack (profiled valid runs)

| config | n | f_X mean | 95% CI | samples in S per run (min) | per-run f | informational: receiver-side UDP share | tap share among iperf3 samples only |
|---|---|---|---|---|---|---|---|
| N | 4 | 0.0475 | [0.0428, 0.0522] | 19601 | 0.0502, 0.0498, 0.0455, 0.0445 | 0.1428 | 0.0475 |
| A | 4 | 0.2983 | [0.2872, 0.3093] | 19598 | 0.2949, 0.3007, 0.2907, 0.3067 | 0.1496 | 0.2984 |
| B | 4 | 0.2235 | [0.2144, 0.2325] | 19578 | 0.2279, 0.2216, 0.2163, 0.2281 | 0.1607 | 0.2236 |
| C | 4 | 0.0689 | [0.0643, 0.0735] | 19456 | 0.0702, 0.0722, 0.0678, 0.0655 | 0.1514 | 0.0690 |

## 5. S-H2: predicted P = 1/(1 - f_cap) against observed R = offered(N)/offered(X); tolerance 25% on R/P

f_cap(X) = (f_X - f_N)/(1 - f_N). Unadjusted prediction 1/(1 - f_X) shown for comparison (not gating).

| X | f_cap [95%] | P = 1/(1-f_cap) [95%] | R [95%, delta method] | R/P - 1 | within tolerance | unadjusted P' | R/P' - 1 | gating |
|---|---|---|---|---|---|---|---|---|
| A | 0.2633 [0.2511, 0.2754] | 1.357 [1.335, 1.380] | 1.662 [1.546, 1.778] | +22.5% | yes | 1.425 | +16.6% | yes |
| B | 0.1848 [0.1745, 0.1950] | 1.227 [1.211, 1.242] | 1.459 [1.372, 1.546] | +18.9% | yes | 1.288 | +13.3% | yes |
| C | 0.0225 [0.0157, 0.0293] | 1.023 [1.016, 1.030] | 1.015 [0.986, 1.044] | -0.8% | yes | 1.074 | -5.5% | no |

**S-H2 holds.**

## 6. Verdict (rule S3)

**SENDER-LIMITED SUPPORTED** (S-H1 and S-H2 hold).

Limits (design section 6): single host, VM, veth, one session; `cpu-clock` timer sampling without a hardware PMU (skew not measured, UNVERIFIED); profiled runs perturb the system and f is measured under profiling but applied to unprofiled rates; the classifier tap is in every config and f_cap assumes its per-packet cost is equal in N and in A/B; the prediction assumes saturated sender cores (busy column above) and serial removable work.

