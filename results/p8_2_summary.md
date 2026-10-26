# Phase 8.2: is the flood's offered load limited by the capture taps in the sender's transmit path?

Computed by `scripts/p8_2_summary.py` from `logs/p8/p8_2/` only; rules: `docs/phase8_2_design.md`. Offered rate = packets per second summed over both streams (client JSON packets / measured window), unprofiled valid runs; 95% intervals; Welch for differences.

## 1. Runs

Plan rows: 40; final logs found: 40; missing: none; earlier attempts kept in `attempts/` (V8 re-runs): 39.

| config | unprofiled valid / planned | profiled valid / planned | exclusions (final attempts) |
|---|---|---|---|
| N | 5 / 6 | 4 / 4 | N rep3: V8 canary 0.195 CPU-s/s > 1.2 x canary_max 0.037 |
| A | 0 / 6 | 3 / 4 | A rep1: V8 canary 0.152 CPU-s/s > 1.2 x canary_max 0.037<br>A rep2: V8 canary 0.126 CPU-s/s > 1.2 x canary_max 0.037<br>A rep3: V8 canary 0.121 CPU-s/s > 1.2 x canary_max 0.037<br>A rep4: V8 canary 0.216 CPU-s/s > 1.2 x canary_max 0.037<br>A rep5: V8 canary 0.114 CPU-s/s > 1.2 x canary_max 0.037<br>A rep6: V8 canary 0.137 CPU-s/s > 1.2 x canary_max 0.037<br>prof A rep3: V6 window 12.43s outside dur-1..+2 |
| B | 0 / 6 | 4 / 4 | B rep1: V8 canary 0.272 CPU-s/s > 1.2 x canary_max 0.037<br>B rep2: V8 canary 0.187 CPU-s/s > 1.2 x canary_max 0.037<br>B rep3: V8 canary 0.119 CPU-s/s > 1.2 x canary_max 0.037<br>B rep4: V8 canary 0.136 CPU-s/s > 1.2 x canary_max 0.037<br>B rep5: V8 canary 0.122 CPU-s/s > 1.2 x canary_max 0.037<br>B rep6: V8 canary 0.152 CPU-s/s > 1.2 x canary_max 0.037 |
| C | 4 / 6 | 2 / 4 | C rep4: V8 canary 0.088 CPU-s/s > 1.2 x canary_max 0.037<br>C rep6: V8 canary 0.052 CPU-s/s > 1.2 x canary_max 0.037<br>prof C rep1: V6 window 12.26s outside dur-1..+2<br>prof C rep4: V6 window 12.29s outside dur-1..+2 |

## 2. Offered rate (unprofiled valid runs)

| config | n | mean offered pps | sd | 95% CI of the mean | sender cores {1,4} busy (CPU-s/s per core) | profiled runs: mean offered pps | profiling effect |
|---|---|---|---|---|---|---|---|
| N | 5 | 1191874 | 391729 | [705478, 1678270] | 0.999 | 1107455 | 0.929 |
| A | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| B | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| C | 4 | 1200909 | 315640 | [698656, 1703162] | 0.999 | 802651 | 0.668 |

## 3. S-H1: offered(N) above offered(A) and above offered(B)

| comparison | mean difference | 95% CI | Welch df | lower bound above 0 |
|---|---|---|---|---|
| N - A | n/a | n/a | n/a | n/a |
| N - B | n/a | n/a | n/a | n/a |
| N - C (not gating) | -9034 | [-566766, 548697] | 7.0 | no |

**S-H1 does not hold.**

## 4. Profiles: share of sender samples with `packet_rcv` in the stack (profiled valid runs)

| config | n | f_X mean | 95% CI | samples in S per run (min) | per-run f | informational: receiver-side UDP share | tap share among iperf3 samples only |
|---|---|---|---|---|---|---|---|
| N | 4 | 0.0490 | [0.0467, 0.0513] | 19042 | 0.0500, 0.0484, 0.0472, 0.0503 | 0.1495 | 0.0492 |
| A | 3 | 0.2965 | [0.2555, 0.3374] | 19212 | 0.3045, 0.3074, 0.2775 | 0.1646 | 0.2978 |
| B | 4 | 0.2261 | [0.2167, 0.2356] | 19142 | 0.2235, 0.2344, 0.2205, 0.2262 | 0.1607 | 0.2263 |
| C | 2 | 0.0775 | [-0.0075, 0.1625] | 19151 | 0.0842, 0.0708 | 0.1527 | 0.0775 |

## 5. S-H2: predicted P = 1/(1 - f_cap) against observed R = offered(N)/offered(X); tolerance 25% on R/P

f_cap(X) = (f_X - f_N)/(1 - f_N). Unadjusted prediction 1/(1 - f_X) shown for comparison (not gating).

| X | f_cap [95%] | P = 1/(1-f_cap) [95%] | R [95%, delta method] | R/P - 1 | within tolerance | unadjusted P' | R/P' - 1 | gating |
|---|---|---|---|---|---|---|---|---|
| A | n/a | n/a | n/a | n/a | not evaluable | n/a | n/a | yes |
| B | n/a | n/a | n/a | n/a | not evaluable | n/a | n/a | yes |
| C | 0.0300 [-0.0599, 0.1199] | 1.031 [0.944, 1.136] | 0.992 [0.530, 1.455] | -3.7% | yes | 1.084 | -8.4% | no |

**S-H2 is not evaluable (A: missing profile or offered data; B: missing profile or offered data).**

## 6. Verdict (rule S3)

**INCONCLUSIVE** (A: 0 valid unprofiled (need 5), 3 valid profiled (need 3); B: 0 valid unprofiled (need 5), 4 valid profiled (need 3)).

Limits (design section 6): single host, VM, veth, one session; `cpu-clock` timer sampling without a hardware PMU (skew not measured, UNVERIFIED); profiled runs perturb the system and f is measured under profiling but applied to unprofiled rates; the classifier tap is in every config and f_cap assumes its per-packet cost is equal in N and in A/B; the prediction assumes saturated sender cores (busy column above) and serial removable work.

