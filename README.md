# BSD Packet Filter Replication

This repository replicates McCanne & Jacobson, "The BSD Packet Filter: A New Architecture for User-level Packet Capture" (USENIX Winter 1993), on modern Linux eBPF. Each of the paper's five headline claims is paired with a metric we measure today, and every number reported comes from logs of commands actually run (see `CLAUDE.md` for the evidence rules).

## Claims

Citations are to `docs/paper.txt` (line numbers). Full quotes, caveats and open questions are in [CLAIMS.md](CLAIMS.md).

| ID | Claim | 1993 headline | Modern metric (Phases 2-6) |
|---|---|---|---|
| C1 | Register-based vs stack-based filter machine, instructions/packet (Fig. 8) | BPF vs CSPF instructions/packet: 62/96, 160/549, 222/971, 129/2330 for Filters 1-4; "up to 20 times faster" (L28) | Dynamic instructions per packet for the same four filters, eBPF vs a stack-machine reference evaluator we write |
| C2 | "Reject all": in-kernel filtering cost is flat vs packet size (Fig. 3) | BPF 4.6 µs fixed, 0 ns/byte; NIT 136 µs intercept, 210 ns/byte | Per-packet cost of a reject-all eBPF filter at 64-1500 B; fit slope (ns/byte) and intercept vs a copy-then-filter baseline |
| C3 | "Accept all": copy slope (ns/byte) plus fixed per-packet cost (Fig. 2) | BPF 148 ns/byte, 5.7 µs; NIT 216 ns/byte, 89.2 µs | Accept-all per-packet cost vs size; fit slope and intercept, eBPF vs conventional copy-to-user path |
| C4 | End-to-end: "10 to 150 times faster than Sun's NIT and 1.5 to 20 times faster than CSPF" (L29-30) | 10-150x vs NIT, 1.5-20x vs CSPF | End-to-end CPU per captured packet and max lossless rate: eBPF in-kernel filtering vs userspace copy-then-filter vs stack-machine filter |
| C5 | A safe in-kernel VM makes "code to the data" practical (ancestor of eBPF) | No numeric headline; wording is UNVERIFIED in the paper text (see CLAIMS.md) | Bytes copied across kernel/user boundary per packet with vs without in-kernel filtering; verifier accept/reject of unsafe programs |

## Repo layout

```
CLAUDE.md        anti-hallucination contract (rules for this repo)
ENV.md           environment probe (commands and observed values)
CLAIMS.md        the five claims with quotes, line numbers, metrics
CODE_NOTES.md    libbpf/BPF helper symbols, with header file:line hits
DEVIATIONS.md    log of oracle consultations and deviations
docs/            paper.pdf and paper.txt (pdftotext -layout)
src/             BPF programs and loaders
scripts/         setup, run and analysis scripts
logs/            raw logs of every command whose output is reported
results/         tables computed from logs/ by scripts
reference/       read-only oracles
prompts/         phase prompts
build/           build artifacts (not tracked)
```

## Setup

```bash
sudo bash scripts/phase1_setup.sh
```


## Status

- [x] Phase 0: bootstrap
- [x] Phase 0.5: version control + GitHub
- [x] Phase 1: setup
- [x] Phase 2: user-space baseline
- [x] Phase 3: eBPF kernel filter
- [x] Phase 4: loader and map reader
- [x] Phase 5: verifier stress test
- [x] Phase 6: benchmark (6a design and harness, calibration, matrix)
- [x] Phase 6c: claim C1 instruction counts (two user-space interpreters), first run in an x86_64 container (DEVIATIONS D6c.1), verdict in `results/c1_verdict.md`, design in `docs/phase6c_design.md`
- [x] Phase 7: final report (`REPORT.md`), figures, historical comparison
- [x] Phase 8.0: C1 repeated on the aarch64 VM with amendment A3 (evaluator-only instruction counts), outputs in `logs/p8/a3/`
- [x] Phase 8.1: quiet measurement setup (`results/p8_1_findings.md`)
- [x] Phase 8.2: sender-bottleneck test with a no-capture control (`results/p8_2_findings.md`)
- [x] Phase 8.3: quiet repeat for C2 and C3 with settled machine baseline
- [x] Phase 8.4: validation of the V8 noise rule (`results/p8_4_findings.md`)
- [x] Phase 8.7: `REPORT.md`, `README.md` and `results/comparison.md` brought up to date (`scripts/build_report.py`, `scripts/p8_7_verify.sh`)
- [x] Phase 9: integrity audit of Phase 8.3 (`DEVIATIONS.md` D8.19 to D8.25, `results/phase6_noisy/`, `logs/p9/`)
- [x] Phase 10: hardened re-measurement of C1 to C5 under frozen designs (`docs/phase10_design.md`, `docs/phase10_wp1b_design.md`, `results/p10_summary.md`, `logs/p10/`)
- [x] Phase 11: `REPORT.md`, `README.md` and `results/comparison.md` brought up to date with the Phase 10 results and final labels (`scripts/build_report.py`, `scripts/build_report_p10.py`)

Final results and verdicts: **[REPORT.md](REPORT.md)** (the section "Final labels after Phase 10" gives the final label of every claim; the claims matrix of Phases 6 to 9 is kept for the record); Phase 10 summary: `results/p10_summary.md`; rule text and amendments: `docs/phase6_design.md`, `docs/phase6_addenda.md`, `docs/phase10_design.md`, `docs/phase10_wp1b_design.md`, `DEVIATIONS.md`.

## Reproducibility

Everything below was run on the machine in `ENV.md` (Ubuntu 25.10, arm64, kernel 6.17). The committed logs under `logs/` and `results/` are the evidence; the figures are regenerated from them without any privileged step.

```bash
git clone https://github.com/Mahim56207/bpf-paper-replication.git
cd bpf-paper-replication

# 1. Figures from the committed logs (no sudo, no traffic). Needs matplotlib:
sudo apt install python3-matplotlib
python3 scripts/reproduce_figures.py      # writes results/fig_cpu_cost.png, results/fig_drop_rate.png, results/figures_data.json
python3 scripts/build_report.py           # regenerates REPORT.md from results/, logs/, ENV.md and git

# 2. Re-running the experiments on your own machine (privileged; it creates a veth pair and a network namespace)
sudo bash scripts/phase1_setup.sh         # toolchain, bpf_jit_enable, veth
bash scripts/build_all.sh                 # builds build/ (not committed)
sudo bash scripts/bench.sh calibrate      # calibration under rule V5'
sudo bash scripts/bench.sh run            # the pre-registered 110-row matrix (about 40 minutes; leave the machine idle)
python3 -I scripts/summarize.py           # results/summary.md, exclusions.md, verdicts.md
```

Phase 10 (privileged; each command is one hands-off launch, leave the machine idle; about an hour and a half and an hour; they refuse to start if their output folders are not empty):

```bash
sudo bash scripts/p10_run_all.sh 2>&1 | tee logs/p10/p10_run_all_console.log   # WP1 to WP4 (the first WP1 there is superseded by WP1b)
sudo bash scripts/p10b_run.sh 2>&1 | tee logs/p10/p10b_run_console.log        # WP1b, long-batch microbenchmarks for C2 and C3
python3 -I scripts/p10_summarize.py                                           # results/p10_summary.md and .json
bash scripts/p10_verify.sh                                                    # re-derives every label, checks hashes and the design chain
python3 scripts/build_report.py                                               # REPORT.md, README.md status, results/comparison.md
```

What a reviewer should see after step 1:

- `results/fig_cpu_cost.png`: three panels. The first two plot net CPU per packet against frame size for the reject curve (configs A, B and the D floor) and the accept curve (A, B and E), with error bars; the error bars are of the same order as the differences between configs, which is what the Phase 8.3 verdicts for C2 and C3 (MIXED and INCONCLUSIVE, superseded by the Phase 10 labels) say. The third panel is the flood (A, B, C), the only place config C exists.
- `results/fig_drop_rate.png`: capture-socket drop rate against offered load. The calibration ladder of the quiet session stays at zero up to the top of the ladder, the first (busy-desktop) calibration shows drops that grow with load and are non-monotonic at the top step (not explained, `REPORT.md`), and the flood points show config A and B near zero and config C (no consumer) near the maximum.
- `results/figures_data.json` holds the plotted values and `REPORT.md` quotes the same numbers; if a regenerated number differs, the logs, not the report, are the source.

## License

BSD-3-Clause, see [LICENSE](LICENSE).
