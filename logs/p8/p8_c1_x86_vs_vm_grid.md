# Phase 8.0: x86_64 container vs aarch64 VM, M2 (host instructions per packet), computed by scripts/p8_compare_grid.py

Inputs: `logs/p6c/p6c_m2.tsv` (x86_64, Phase 6c; no `Ir_eval` column, so E = T), `logs/p8/a3/p6c/p6c_m2.tsv` (VM, columns `Ir` = T and `Ir_eval` = E). Functions `ratio`, `evaluate`, `verdict` imported unchanged from `scripts/c1_summarize.py`; paper labels from `CLAIMS.md`. R = mean(CSPF)/mean(BPF) over the ten 1000-frame chunks, 95% t-interval of the ten per-chunk ratios.

## 1. Primary pairing (mix M0, BPF-opt vs CSPF sc-fused)

| filter | paper R | x86_64 BPF | x86_64 CSPF | x86_64 R [95%] | VM-E BPF | VM-E CSPF | VM-E R [95%] | VM-T R [95%] |
|---|---|---|---|---|---|---|---|---|
| F1 | 1.5 | 57 | 90 | 1.58 [1.58, 1.58] | 82.8 | 91 | 1.1 [1.1, 1.1] | 1.32 [1.32, 1.32] |
| F2 | 3.4 | 108 | 346 | 3.19 [3.18, 3.2] | 138 | 345 | 2.51 [2.5, 2.52] | 2.62 [2.61, 2.63] |
| F3 | 4.4 | 195 | 593 | 3.04 [3.03, 3.04] | 226 | 590 | 2.61 [2.6, 2.61] | 2.68 [2.67, 2.68] |
| F4 | 18.1 | 103 | 2121 | 20.6 [20.5, 20.7] | 132 | 2120 | 16.1 [16, 16.1] | 16 [15.9, 16] |

## 2. Outcomes (design section 7, rules unchanged)

| data set | C1a primary | C1a grid cells passing | C1b (R order, primary) | C1c (largest R in [9.05, 36.2]) | largest R | verdict |
|---|---|---|---|---|---|---|
| x86_64 | holds | 21 of 24 | fails | holds | 20.6 | **MIXED** |
| VM-E (A3 M2) | holds | 21 of 24 | holds | holds | 16.1 | **MIXED** |
| VM-T (toggle total) | holds | 21 of 24 | holds | holds | 16 | **MIXED** |

## 3. Full grid, R per filter [lower, upper] omitted for width; C1a = every filter's 95% lower bound above 1

| mix | BPF | CSPF | x86_64 F1 / F2 / F3 / F4 | C1a | VM-E F1 / F2 / F3 / F4 | C1a | VM-T C1a |
|---|---|---|---|---|---|---|---|
| M0 | bpf-opt | sm-full-general | 1.58 / 3.75 / 11.8 / 20.8 | yes | 1.1 / 2.96 / 10.4 / 16.3 | yes | yes |
| M0 | bpf-opt | sm-sc-general | 1.58 / 3.19 / 6.67 / 20.6 | yes | 1.1 / 2.51 / 5.84 / 16.1 | yes | yes |
| M0 | bpf-opt | sm-full-fused | 1.58 / 3.75 / 5.08 / 20.8 | yes | 1.1 / 2.96 / 4.39 / 16.3 | yes | yes |
| M0 | bpf-opt | sm-sc-fused | 1.58 / 3.19 / 3.04 / 20.6 | yes | 1.1 / 2.51 / 2.61 / 16.1 | yes | yes |
| M0 | bpf-raw | sm-full-general | 1.58 / 2.91 / 3.06 / 7.68 | yes | 1.1 / 2.38 / 2.92 / 6.7 | yes | yes |
| M0 | bpf-raw | sm-sc-general | 1.58 / 2.48 / 1.73 / 7.6 | yes | 1.1 / 2.02 / 1.64 / 6.62 | yes | yes |
| M0 | bpf-raw | sm-full-fused | 1.58 / 2.91 / 1.32 / 7.68 | yes | 1.1 / 2.38 / 1.23 / 6.7 | yes | yes |
| M0 | bpf-raw | sm-sc-fused | 1.58 / 2.48 / 0.787 / 7.6 | NO | 1.1 / 2.02 / 0.732 / 6.62 | NO | NO |
| Mip | bpf-opt | sm-full-general | 1.58 / 3.5 / 10.7 / 20.8 | yes | 1.1 / 2.79 / 9.47 / 16.2 | yes | yes |
| Mip | bpf-opt | sm-sc-general | 1.58 / 3.3 / 6.88 / 20.5 | yes | 1.1 / 2.62 / 6.08 / 16 | yes | yes |
| Mip | bpf-opt | sm-full-fused | 1.58 / 3.5 / 4.59 / 20.8 | yes | 1.1 / 2.79 / 4.01 / 16.2 | yes | yes |
| Mip | bpf-opt | sm-sc-fused | 1.58 / 3.3 / 3.09 / 20.5 | yes | 1.1 / 2.62 / 2.68 / 16 | yes | yes |
| Mip | bpf-raw | sm-full-general | 1.58 / 2.77 / 2.69 / 7.58 | yes | 1.1 / 2.27 / 2.57 / 6.61 | yes | yes |
| Mip | bpf-raw | sm-sc-general | 1.58 / 2.61 / 1.73 / 7.49 | yes | 1.1 / 2.13 / 1.65 / 6.53 | yes | yes |
| Mip | bpf-raw | sm-full-fused | 1.58 / 2.77 / 1.15 / 7.58 | yes | 1.1 / 2.27 / 1.09 / 6.61 | yes | yes |
| Mip | bpf-raw | sm-sc-fused | 1.58 / 2.61 / 0.778 / 7.49 | NO | 1.1 / 2.13 / 0.726 / 6.53 | NO | NO |
| Mnonip | bpf-opt | sm-full-general | 1.58 / 5 / 18.9 / 21.2 | yes | 1.1 / 3.76 / 15.7 / 16.5 | yes | yes |
| Mnonip | bpf-opt | sm-sc-general | 1.58 / 2.63 / 5.43 / 21 | yes | 1.1 / 1.98 / 4.49 / 16.3 | yes | yes |
| Mnonip | bpf-opt | sm-full-fused | 1.58 / 5 / 8.14 / 21.2 | yes | 1.1 / 3.76 / 6.64 / 16.5 | yes | yes |
| Mnonip | bpf-opt | sm-sc-fused | 1.58 / 2.63 / 2.7 / 21 | yes | 1.1 / 1.98 / 2.2 / 16.3 | yes | yes |
| Mnonip | bpf-raw | sm-full-general | 1.58 / 3.6 / 6.01 / 8.14 | yes | 1.1 / 2.87 / 5.57 / 7.08 | yes | yes |
| Mnonip | bpf-raw | sm-sc-general | 1.58 / 1.9 / 1.72 / 8.06 | yes | 1.1 / 1.51 / 1.59 / 7.01 | yes | yes |
| Mnonip | bpf-raw | sm-full-fused | 1.58 / 3.6 / 2.58 / 8.14 | yes | 1.1 / 2.87 / 2.36 / 7.08 | yes | yes |
| Mnonip | bpf-raw | sm-sc-fused | 1.58 / 1.9 / 0.857 / 8.06 | NO | 1.1 / 1.51 / 0.779 / 7.01 | NO | NO |

## 4. Cells where C1a fails

- x86_64: M0 / bpf-raw / sm-sc-fused; Mip / bpf-raw / sm-sc-fused; Mnonip / bpf-raw / sm-sc-fused
- VM-E (A3 M2): M0 / bpf-raw / sm-sc-fused; Mip / bpf-raw / sm-sc-fused; Mnonip / bpf-raw / sm-sc-fused
- VM-T (toggle total): M0 / bpf-raw / sm-sc-fused; Mip / bpf-raw / sm-sc-fused; Mnonip / bpf-raw / sm-sc-fused
