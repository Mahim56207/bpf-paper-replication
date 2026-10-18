# CLAUDE.md - anti-hallucination contract for this repo
GROUNDING
- Paper truth = docs/paper.txt. Cite as (paper.txt L<n>). No claim about the paper without a citation.
- Environment truth = ENV.md. Never assume versions; re-probe with a real command if unsure.
- Read-only oracles live in reference/. Consulting one => append to DEVIATIONS.md (what, why, taken or not).
API DISCIPLINE
- Before first use of ANY libbpf function or BPF helper: grep the installed headers
  (/usr/include/bpf/, /usr/include/linux/bpf.h) and append the hit (symbol, file:line) to CODE_NOTES.md.
  Symbol absent from headers => it does not exist => do not use it.
- libbpf API surface = the version recorded in ENV.md only.
- Kernel structs: parse packets manually with explicit bounds checks (paper style) OR generate
  vmlinux.h via bpftool. Never hand-write kernel struct layouts from memory.
EVIDENCE DISCIPLINE
- Every output shown to me = output of a command run this session, tee'd into logs/.
  No simulated, expected, or tidied output. Ever.
- No invented numbers. Phase 6 tables are computed by scripts reading logs/ only.
- Verifier rejections (Phase 5) = captured stderr of a real load attempt, verbatim.
WORKFLOW
- One phase at a time. After a phase's VERIFY passes: STOP, summarize, wait for my exact
  string "Phase N complete".
- Same error twice => stop, show the error plus two hypotheses, ask me. No silent architecture changes.
- Unsure => write "UNVERIFIED: <thing>" and ask me. Guessing is a contract violation.
