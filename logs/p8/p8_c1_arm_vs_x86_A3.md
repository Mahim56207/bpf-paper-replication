# Phase 8.0: C1 on the aarch64 VM vs the x86_64 container (computed by scripts/p8_compare_c1.py)

Sources: `logs/p8/x86_baseline/c1_summary.md` (x86_64 container, Phase 6c) and `logs/p8/a3/results/c1_summary.md` (aarch64 VM, this run). Primary pairing, mix M0, BPF-opt vs CSPF sc-fused. Rel. diff = (VM - x86) / x86.

| filter | metric | x86_64 | aarch64 VM | rel. diff |
|---|---|---|---|---|
| F1 | M1 BPF | 3 | 3 | +0.0% |
| F1 | M1 CSPF | 3 | 3 | +0.0% |
| F1 | M1 R | 1 | 1 | +0.0% |
| F1 | M2 BPF | 57 | 82.8 | +45.3% |
| F1 | M2 CSPF | 90 | 91 | +1.1% |
| F1 | M2 R | 1.58 | 1.1 | -30.4% |
| F2 | M1 BPF | 6.32 | 6.32 | +0.0% |
| F2 | M1 CSPF | 16.5 | 16.5 | +0.0% |
| F2 | M1 R | 2.61 | 2.61 | +0.0% |
| F2 | M2 BPF | 108 | 138 | +27.8% |
| F2 | M2 CSPF | 346 | 345 | -0.3% |
| F2 | M2 R | 3.19 | 2.51 | -21.3% |
| F3 | M1 BPF | 11.9 | 11.9 | +0.0% |
| F3 | M1 CSPF | 29.4 | 29.4 | +0.0% |
| F3 | M1 R | 2.48 | 2.48 | +0.0% |
| F3 | M2 BPF | 195 | 226 | +15.9% |
| F3 | M2 CSPF | 593 | 590 | -0.5% |
| F3 | M2 R | 3.04 | 2.61 | -14.1% |
| F4 | M1 BPF | 6.07 | 6.07 | +0.0% |
| F4 | M1 CSPF | 106 | 106 | +0.0% |
| F4 | M1 R | 17.5 | 17.5 | +0.0% |
| F4 | M2 BPF | 103 | 132 | +28.2% |
| F4 | M2 CSPF | 2121 | 2120 | -0.0% |
| F4 | M2 R | 20.6 | 16.1 | -21.8% |

Paper ratios (Fig. 8 labels, from the summaries): F1 1.5, F2 3.4, F3 4.4, F4 18.1.

M1 identical on both machines for all four filters: True
M2 R ordering F1<F2<F3<F4: x86_64 False, aarch64 VM True

Verdict lines, x86_64 (`logs/p8/x86_baseline/c1_verdict.md`):

    # C1 verdict (Phase 6c)
    **Verdict (M2, host instructions per packet): MIXED**
    - C1a (every filter's 95% interval of R above 1, primary): **holds**; in all 24 grid cells: **fails** (21 of 24 cells).
    - C1b (R(F1) < R(F2) < R(F3) < R(F4), primary): **fails** (R = 1.58, 3.19, 3.04, 20.6).
    - C1c (largest R within a factor of two of the paper's 18.1, i.e. in [9.05, 36.2]): **holds** (largest R = 20.6).
    - Grid cells where C1a fails (M2): M0 / bpf-raw / sm-sc-fused; Mip / bpf-raw / sm-sc-fused; Mnonip / bpf-raw / sm-sc-fused.
    Informational, M1 (filter instructions executed): verdict by the same rule would be **MIXED**; C1a primary holds, all cells fails, C1b fails, C1c holds (largest R = 17.5).
    Scope: the verdict concerns the register-machine and stack-machine MODELS as implemented here (our interpreters, our CSPF programs, libpcap's 1.10.4 BPF programs, assumed traffic mixes, x86_64 gcc -O2). It does not reproduce the 1993 numbers, and no 1993 absolute is compared; the paper's labels appear only as the reference ratios of C1b and C1c. Limits recorded in DEVIATIONS D6c.1 to D6c.4 and in `docs/phase6c_design.md`.

Verdict lines, aarch64 VM (`logs/p8/a3/results/c1_verdict.md`):

    # C1 verdict (Phase 6c)
    **Verdict (M2, host instructions per packet): MIXED**
    - C1a (every filter's 95% interval of R above 1, primary): **holds**; in all 24 grid cells: **fails** (21 of 24 cells).
    - C1b (R(F1) < R(F2) < R(F3) < R(F4), primary): **holds** (R = 1.1, 2.51, 2.61, 16.1).
    - C1c (largest R within a factor of two of the paper's 18.1, i.e. in [9.05, 36.2]): **holds** (largest R = 16.1).
    - Grid cells where C1a fails (M2): M0 / bpf-raw / sm-sc-fused; Mip / bpf-raw / sm-sc-fused; Mnonip / bpf-raw / sm-sc-fused.
    Informational, M1 (filter instructions executed): verdict by the same rule would be **MIXED**; C1a primary holds, all cells fails, C1b fails, C1c holds (largest R = 17.5).
    Scope: the verdict concerns the register-machine and stack-machine MODELS as implemented here (our interpreters, our CSPF programs, libpcap's 1.10.5 BPF programs, assumed traffic mixes, aarch64 gcc 15.2.0 -O2). It does not reproduce the 1993 numbers, and no 1993 absolute is compared; the paper's labels appear only as the reference ratios of C1b and C1c. Limits recorded in DEVIATIONS D6c.1 to D6c.4 and in `docs/phase6c_design.md`.
