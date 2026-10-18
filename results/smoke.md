# SMOKE runs (excluded from analysis by pre-declaration)

Parsed by `summarize.py smoke` from logs/smoke_*.log. These runs check the plumbing only; no verdict uses them.

| file | cfg | traffic | size | window s | offered pps | cls T | F4040 | C4040 | X | tap total | matched raw | matched flow | filter drops | delivered | socket drops | system busy s | canary CPU-s/s | steal % | parse result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| smoke_A_m_512_1.log | A | m | 512 | 5.01 | 1996 | 10030 | 10003 | 27 | 0 | 10030 | 10030 | 10003 | None | 10030 | 0 | 1.82 | 0.164 | 0.00 | valid |
| smoke_B_m_512_1.log | B | m | 512 | 5.01 | 1998 | 10031 | 10004 | 27 | 0 | 10031 | 10031 | 10004 | 0 | 10031 | 0 | 0.74 | 0.072 | 0.00 | valid |
| smoke_C_m_512_1.log | C | m | 512 | 5.01 | 1998 | 10030 | 10003 | 27 | 0 | 10030 | 10030 | 10003 | 0 | None | 9856 | 1.61 | 0.146 | 0.00 | valid |
| smoke_D_idle_0_1.log | D | idle | 0 | 5.00 | n/a | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2.43 | 0.208 | 0.00 | valid |
| smoke_D_idle_0_2.log | D | idle | 0 | 5.01 | n/a | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2.14 | 0.170 | 0.00 | valid |
| smoke_D_idle_0_3.log | D | idle | 0 | 5.01 | n/a | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3.43 | 0.278 | 0.00 | valid |
| smoke_D_m_512_1.log | D | m | 512 | 5.01 | 1997 | 10031 | 10004 | 27 | 0 | 10031 | 0 | 0 | 10031 | 0 | 0 | 0.94 | 0.084 | 0.00 | valid |
| smoke_E_m_512_1.log | E | m | 512 | 5.01 | 1998 | 10031 | 10004 | 27 | 0 | 10031 | 10031 | 10004 | 0 | 10031 | 0 | 0.85 | 0.074 | 0.00 | valid |
