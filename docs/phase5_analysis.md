# Phase 5 analysis: verifier stress test

Kernel 6.17.0-19-generic, aarch64, bpftool v7.7.0 (`logs/p5_verify.log`). Verifier text below is quoted from `logs/phase5_a2.log` and `logs/phase5_b.log`, which are the captured stderr of the real load attempts. Source line numbers are those of the named file in `src/`. Safe program: `src/phase3_kern.c`.

## Results at a glance

| program | what differs from `phase3_kern.c` | `bpftool prog load ... type socket` | stderr | evidence |
|---|---|---|---|---|
| A (`phase5_unsafe_a.c`) | NULL check on the lookup result removed, **constant** key | exit 0, **loaded** | 0 bytes | `p5_verify.log`, `p5_a_load_stderr.log`, earlier run `phase5_a.log` |
| A2 (`phase5_unsafe_a2.c`) | key = `skb->len & 1` (**runtime**), no NULL check | exit 255, **rejected** | 7,582 bytes | `phase5_a2.log` |
| B (`phase5_unsafe_b.c`) | direct packet access for layer 2 | exit 255, **rejected** | 709 bytes | `phase5_b.log` |
| control (`phase3_kern.c`) | none | exit 0 | 0 bytes | `phase5_control.log`, tag `2d534a7c582f82ac` (same tag as Phase 3) |
| A2-fixed (`phase5_a2_fixed.c`) | A2 with `if (v)` restored | exit 0 | 0 bytes | `phase5_a2fixed.log`, tag `5f2a1f05ac8ed9a4` |

Diffs against the safe program: `logs/phase5_diffs.log` (A, B), `logs/phase5_diffs_a2.log` (A2, A2-fixed). All five objects compile with the exact Phase 3 clang command and no warnings (`phase5_compile.log`, `phase5_compile_rev2.log`): the compiler does not catch any of these; only the kernel does. Pin hygiene: no `repl_p5*` pin was present at the start of the run (so the earlier run's exit trap did remove variant A's pin) or at the end (`p5_pins_start.log`, `p5_pins_end.log`); the Phase 3 pin `repl_p3` is untouched.

## 1. Variant A: why it loaded; semantic versus syntactic safety

Source (`phase5_unsafe_a.c`): line 52 `__u64 *v = bpf_map_lookup_elem(&p3_counters, &slot);`, line 54 `__sync_fetch_and_add(v, 1);` with no `if (v)`. The compiled object has no null check: 0 `if r0 == 0x0` branches versus 2 in the safe object, and the atomic add uses `r0` right after `call 0x1` (`phase5_a_objdump.log`, `p3_objdump.log`). Syntactically this is the textbook unchecked-NULL bug, and the kernel loaded it anyway.

Evidence for why (`p5_a_xlated.log`, dumped from the loaded program):
- **No call to `bpf_map_lookup_elem` exists in the loaded program.** The count is 0. The `.o` has `call 0x1` at two sites; the loaded stream has instead the inlined lookup at each site: `r1 = map[id:157]`, `r1 += 264`, `if r0 >= 0x2 goto pc+3` (the key bounds check), `r0 <<= 3`, `r0 += r1` (insns 83-89 and 100-106). The only calls left are the four `bpf_skb_load_bytes`.
- A2 shows that the difference is the key and not the helper: it also has no NULL check and calls the same helper on the same map, yet it is rejected with `R0=map_value_or_null` (section 2). The one change between A and A2 is the key: constants 0 and 1 in A, `skb->len & 1` in A2.

Reviewer ruling D5.2: for `BPF_MAP_TYPE_ARRAY` with a constant in-range key the verifier inlines the lookup during verification and types the result as a non-null map value, so the check is provably unnecessary.

**The verifier's own statement (gap closed, DEVIATIONS D5.3).** `bpftool -d prog load build/phase5_unsafe_a.o ...` printed the full verifier log (`logs/p5_a_verbose.log`, 461 lines; exit 0). The two lookup call sites are insns 85, 96 (`; __u64 *v = bpf_map_lookup_elem(&p3_counters, &slot); @ phase5_unsafe_a.c:52`); the other call lines in the log are the verifier revisiting the same two sites on different paths. The register state it prints after each call, extracted from the log with `grep -n "^[0-9]*: R0=map_value"`:

```
log line 270: 86: R0=map_value(map=p3_counters,ks=4,vs=8)
log line 293: 97: R0=map_value(map=p3_counters,ks=4,vs=8)
```

Both read `R0=map_value(map=p3_counters,ks=4,vs=8)`: a map value, **not** `map_value_or_null`. The string `map_value_or_null` occurs 0 times in the file. Compare variant A2 (section 2), where the same helper call on the same map produced `R0=map_value_or_null(id=3,...)` and the dereference was refused. The final verifier summary line is `processed 155 insns (limit 1000000) max_states_per_insn 0 total_states 14 peak_states 14 mark_read 4`. So the missing source-level check is safe because the verifier can prove the pointer non-null at both sites; this confirms the ruling with the verifier's own output, not an inference.

Takeaway: source-level unsafe is not the same as verifier-rejected. The verifier proves safety semantically, from what it can show about the values on the path, not from whether the source contains an `if (v)`. A program that looks wrong can be accepted when the proof goes through, and the same program with a fallible key is refused (A2). Variant A is therefore evidence for that point, not a verifier hole.

## 2. Variant A2: map-value nullness under a fallible lookup

Quoted from `logs/phase5_a2.log`, in verifier order, with the source line each verifier line carries (`@ file:line`):

| verifier line | source line |
|---|---|
| `; __u32 key = (__u32)(skb->len & 1); @ phase5_unsafe_a2.c:53` | line 53 |
| `79: (61) r1 = *(u32 *)(r6 +0)` then `80: (54) w1 &= 1 ; R1_w=scalar(smin=smin32=0,smax=umax=smax32=umax32=1,var_off=(0x0; 0x1))` | line 53: the verifier knows the key is in [0, 1], inside the map's 2 entries |
| `; __u64 *v = bpf_map_lookup_elem(&p3_counters, &key); @ phase5_unsafe_a2.c:54` | line 54 |
| `86: (85) call bpf_map_lookup_elem#1 ; R0=map_value_or_null(id=3,map=p3_counters,ks=4,vs=8)` | line 54: the result is typed **map_value_or_null** |
| `; __sync_fetch_and_add(v, 1); @ phase5_unsafe_a2.c:56` | line 56 |
| `88: (db) r1 = atomic64_fetch_add((u64 *)(r0 +0), r1)` | line 56: the dereference |
| `R0 invalid mem access 'map_value_or_null'` | the rejection, on insn 88 |

Property that fired: **map-value nullness**. A lookup result must be proven non-NULL before it is dereferenced. Even though the verifier knows the key is within range (`smax=umax=1`), it still types the result as `map_value_or_null` because the key is not a constant, and it refuses the dereference on insn 88. The 70 instructions processed before that (`processed 70 insns ... total_states 7`) all passed, including the bounded `bpf_skb_load_bytes` calls: the program is rejected for exactly one reason.

Positive control A2-fixed (line 55 `if (v)` restored, otherwise identical): exit 0, empty stderr (`phase5_a2fixed.log`), so the rejection was specifically the missing check under a fallible lookup, not the runtime key, the `skb->len` read or any other part of A2.

## 3. Variant B: context-access whitelist for a socket filter

Quoted from `logs/phase5_b.log`:

| verifier line | source line |
|---|---|
| `; __u32 len = skb->len; @ phase5_unsafe_b.c:62` then `0: (61) r7 = *(u32 *)(r1 +0)` | line 62: reading `skb->len` is accepted (offset 0) |
| `; void *data_end = (void *)(long)skb->data_end; @ phase5_unsafe_b.c:67` | line 67 |
| `1: (61) r3 = *(u32 *)(r1 +80)` | line 67: the load of `skb->data_end` from the context at offset 80 |
| `invalid bpf_context access off=80 size=4` | the rejection, on insn 1 |

Property that fired: the **context-access whitelist** for the program type. A `socket_filter` program may read some `__sk_buff` fields (`len`, at offset 0, was accepted two lines earlier) but not `data` / `data_end`. This is the same rejection as Phase 3 revision 1 (`logs/p3_v1_direct_access/p3_load_type_socket.log`: the same `off=80 size=4`). The ruling mentioned `off=76/80`: only 80 appears because the verifier stops at the first bad access, and the compiler emitted the `data_end` load (line 67, offset 80) before the `data` load (line 66, offset 76), which was never reached. The pointer arithmetic on line 72 and the dereference on line 74 were never evaluated either; the program fails on the context read alone.

## 4. Controls

- **Safe program (control):** `bpftool prog load build/phase3_kern.o /sys/fs/bpf/repl_p5control type socket`, exit 0, 0 bytes of stderr, prog 1716 with tag `2d534a7c582f82ac`, the same tag as the Phase 3 program (`phase5_control.log`, `p5_verify.log`). It was loaded in the same run, a few moments after the rejections, so the rejections come from the edits and not from the environment.
- **A2-fixed:** see section 2.
- Both temporary pins were removed; `p5_pins_end.log` lists only `repl_p3` and `snap`.

## 5. What the paper says (C5)

CLAIMS.md already records that `paper.txt` has no text on safety or verification of filter programs (no occurrence of "safe", "safety" or a validation step), so the citations below are the paper's motivation for running user-supplied code in the kernel, not statements about safety:
- The filter is user-supplied code run by the kernel on each packet: "This user-defined filter decides whether a packet" (paper.txt L100), executed "in interrupt context" (paper.txt L88; the performance argument for it is at L153-154).
- "The idea of putting a pseudo-machine language interpreter in the kernel provides a" nice abstraction (paper.txt L403-404, joined; the sentence continues in the next column).
- The conclusion credits the "programmable pseudo-machine model" with "excellent generality and extensibility (all knowledge of particular protocols is factored out of the kernel)" (paper.txt L737-740, joined).

These lines are the premise behind C5: filters written by user programs execute inside the kernel. What the paper does not say is how the kernel protects itself from a bad filter. Phase 5 is evidence for the modern answer on this machine: the eBPF verifier rejects a filter that dereferences a possibly-NULL map value (A2) or reads a context field a socket filter may not read (B), and it accepts one that is provably safe even when the source lacks a check (A). That supports C5's "safe in-kernel VM" reading as a statement about eBPF, not about the 1993 BPF.

## Limits

- One kernel (6.17.0-19), one run per program. The explanation of A's acceptance now rests on the verifier's own `R0=map_value` state (`p5_a_verbose.log`) plus the A/A2 contrast; the kernel-internal mechanism behind it (array-map inlining and the constant-key typing) is the reviewer's account of the verifier and was not read from kernel source.
- Two unsafe classes were tested. The verifier checks many more properties (bounded loops, stack initialisation, helper argument types, and so on); none were exercised here.
- The A2 log is the verifier's default failure log. It shows the path to the failing instruction, not every state it explored.

## Re-run at commit time (CLAUDE.md workflow rule)

`scripts/rerun_p5.sh` repeated the gap-closing verbose load and re-ran `scripts/phase5_verify.sh` into `logs/p5_rerun/`: variant A exit 0 with 0 calls to `bpf_map_lookup_elem` in its xlated stream; A2 exit 255 and B exit 255 (7,582 and 709 bytes of stderr, byte-identical sizes to the first run); safe control exit 0; A2-fixed exit 0; no `repl_p5*` pins at start or end (`logs/p5_rerun/p5_verify.log`).
