# C1 verdict (Phase 6c)

Computed by scripts/c1_summarize.py with the rules of docs/phase6c_design.md section 7. Tables: `results/c1_summary.md`.

**Verdict (M2, host instructions per packet): MIXED**

- Primary pairing: mix M0, BPF-opt vs CSPF sc-fused.
- C1a (every filter's 95% interval of R above 1, primary): **holds**; in all 24 grid cells: **fails** (21 of 24 cells).
- C1b (R(F1) < R(F2) < R(F3) < R(F4), primary): **holds** (R = 1.32, 2.62, 2.68, 16).
- C1c (largest R within a factor of two of the paper's 18.1, i.e. in [9.05, 36.2]): **holds** (largest R = 16).
- Grid cells where C1a fails (M2): M0 / bpf-raw / sm-sc-fused; Mip / bpf-raw / sm-sc-fused; Mnonip / bpf-raw / sm-sc-fused.

Informational, M1 (filter instructions executed): verdict by the same rule would be **MIXED**; C1a primary holds, all cells fails, C1b fails, C1c holds (largest R = 17.5).

Scope: the verdict concerns the register-machine and stack-machine MODELS as implemented here (our interpreters, our CSPF programs, libpcap's 1.10.4 BPF programs, assumed traffic mixes, x86_64 gcc -O2). It does not reproduce the 1993 numbers, and no 1993 absolute is compared; the paper's labels appear only as the reference ratios of C1b and C1c. Limits recorded in DEVIATIONS D6c.1 to D6c.4 and in `docs/phase6c_design.md`.
