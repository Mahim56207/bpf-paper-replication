# D8.3 diagnostic: M2 with only the evaluator functions counted (aarch64 VM, mix M0, BPF-opt vs CSPF sc-fused)

T = project definition (all Ir collected under --toggle-collect); E = Ir attributed to c1_eval_* only. Means over 10 chunks of 1000 frames; R = mean(CSPF)/mean(BPF).

| filter | T BPF | T CSPF | T R | E BPF | E CSPF | E R | leaked share BPF | leaked share CSPF |
|---|---|---|---|---|---|---|---|---|
| F1 | 84.96 | 112.1 | 1.32 | 82.84 | 91 | 1.1 | 2.5% | 18.9% |
| F2 | 139.7 | 366.4 | 2.62 | 137.6 | 345.3 | 2.51 | 1.5% | 5.8% |
| F3 | 228.5 | 611.2 | 2.68 | 226.4 | 590.1 | 2.61 | 0.9% | 3.5% |
| F4 | 134 | 2141 | 16 | 131.9 | 2120 | 16.1 | 1.6% | 1.0% |
