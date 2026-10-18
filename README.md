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

`scripts/phase1_setup.sh` is created in Phase 1; it does not exist yet.

## Status

- [ ] Phase 0: bootstrap
- [ ] Phase 0.5: version control + GitHub
- [ ] Phase 1: setup
- [ ] Phase 2
- [ ] Phase 3
- [ ] Phase 4
- [ ] Phase 5: verifier rejections
- [ ] Phase 6: results tables

## License

BSD-3-Clause, see [LICENSE](LICENSE).
