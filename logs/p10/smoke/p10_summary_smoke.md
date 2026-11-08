# Phase 10 summary

Computed by scripts/p10_summarize.py from logs/p10/ only (rules P1 to P13 of docs/phase10_design.md).

## Final labels

| claim | label | evidence (computed) |
|---|---|---|
| C1 | **BOUNDED** | direction holds in 0 of 1 builds (), ordering holds in 0 of 1 (); range of R over the builds: F1 [0.656, 0.656]; F2 [1.18, 1.18]; F3 [1.15, 1.15]; F4 [7.69, 7.69] |
| C2 | **INCONCLUSIVE** | slope data missing or fewer valid batches than the minimum: [] |
| C3 | **INCONCLUSIVE** | slope data missing or fewer valid batches than the minimum: [] |
| C4 | **INCONCLUSIVE** | fewer than three reachable rates: 100000 REACHABLE, 450000 UNREACHABLE |
| C4-mitigation | **INCONCLUSIVE** | fewer valid runs than the minimum in a cell: [('T0', 'B'), ('T0', 'C'), ('T1', 'A')] |
| C5 | **SUPPORTED** | unbounded program rejected (exit 255), bounded program loaded (exit 0) |

## WP1 slopes (ns per byte of frame size; 90% intervals)

| quantity | slope | 90% interval | class | upper end / 148 | upper end / 216 | n |
|---|---|---|---|---|---|---|
| memcpy | n/a | | | | | |
| tr_reject | n/a | | | | | |
| tr_accept | n/a | | | | | |
| tr_port | n/a | | | | | |
| dr_U | n/a | | | | | |
| dr_E | n/a | | | | | |
| dr_B | n/a | | | | | |

WP1 batches: 14 plan rows, 0 re-run attempts, 0 final batches invalid.

## WP2(a) offered load, flood (mean packets per second over valid runs)

| topology | cfg | mean | sd | n |
|---|---|---|---|---|

| cfg | R in T0 (95%) | R in T1 (95%) | Q = R(T1)/R(T0) (95%) |
|---|---|---|---|
| A | n/a | | |
| B | n/a | | |
| C | n/a | | |

Mitigation classes: {}. Canary limit of rule P7: 0.03708 CPU-s/s.

## WP2(b) ladder

| rate (pps) | status | valid runs A/B/C | rho = cpu(A)/cpu(B) (95%) | class | drop class |
|---|---|---|---|---|---|
| 100000 | REACHABLE | 1/1/1 | n/a | UNDECIDED | NO-LOSS-BOUND |
| 450000 | UNREACHABLE | 0/1/1 | n/a | n/a | n/a |

## WP3 C1: ratio CSPF/BPF per filter (95% interval over chunks), primary pairing

| build | F1 | F2 | F3 | F4 | direction | ordering |
|---|---|---|---|---|---|---|
| gcc-O0 | 0.656 [0.656, 0.656] | 1.18 [1.18, 1.18] | 1.15 [1.15, 1.15] | 7.69 [7.69, 7.69] | REVERSED | FAILS |

Phase 10 verify (`scripts/p10_verify.sh`) checks these files against the rules.

