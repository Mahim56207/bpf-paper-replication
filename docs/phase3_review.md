# Phase 3 review: eBPF socket filter (src/phase3_kern.c)

Line numbers are `src/phase3_kern.c` unless stated. Logs are in `logs/`. Statements about kernel internals that were not observed in a log are marked UNVERIFIED.

## Outcome

| step | result | evidence |
|---|---|---|
| compile (exact command from the prompt) | exit 0, no warnings; `ELF 64-bit LSB relocatable, eBPF, with debug_info` | `p3_compile.log` |
| load, revision 1 (direct packet access as specified) | **rejected**: `invalid bpf_context access off=80 size=4` at insn 0, `r2 = *(u32 *)(r1 +80)` = `skb->data_end` | `p3_v1_direct_access/p3_load_type_socket.log`, full log `p3_load_debug.log` |
| `type socket_filter` | rejected by bpftool before the kernel: `failed to guess program type from ELF section 'socket_filter/'` | `p3_v1_direct_access/p3_load.log` (DEVIATIONS D3.1) |
| load, revision 2 (`bpf_skb_load_bytes`) | **accepted**, `[exit 0]` | `p3_load.log` |
| `bpftool prog show pinned` | `906: socket_filter name phase3_filter tag 2d534a7c582f82ac gpl`, `xlated 920B jited 680B`, `map_ids 82` | `p3_show.log` |
| test run, 38 frames | 38/38 agree with an independent reference matcher; counters dropped +30 (expected 30), matched +8 (expected 8) | `p3_check.log`, `p3_testrun.log` |

`jited 680B` shows the program was JIT-compiled (bpf_jit_enable=1, ENV.md). `bpftool prog dump jited` itself printed `Error: No JIT disassembly support` (`p3_verify.log`), so the machine code was not inspected.

## 0. Why revision 2

The prompt asked for direct packet access. The verifier refused the very first instruction that reads `skb->data_end` (ctx offset 80); `skb->data` is at offset 76 in the same struct (`build/vmlinux.h:61514`, `data` and `data_end` consecutive `__u32` fields), and was not reached. So direct packet access is not available to a `socket` program on this kernel (6.17.0-19), which is what the Phase 3 prompt did not anticipate. With the user's approval (DEVIATIONS D3.3) revision 2 never forms a packet pointer: it reads `skb->len`, and copies each header out with `bpf_skb_load_bytes()` into a stack struct.

## 1. Every packet access and the check that licenses it

Revision 2 has no packet-pointer dereference at all. The accesses that touch packet data or the context are these. "Licensed by" is the explicit check in the source plus what the verifier accepted.

| source line | access | licensed by |
|---|---|---|
| 56 | `skb->len` (ctx field, `__u32` at offset 112, xlated insn 1 `r7 = *(u32 *)(r6 +112)`) | ctx read accepted by the verifier. No bounds check needed. `len` is later used only in comparisons |
| 66 | `bpf_skb_load_bytes(skb, 0, &eth, 14)` copies packet bytes 0..13 into stack `eth` | line 64: `len < 0 + 14` drops first, so the load runs only when `len >= 14`. Line 66 also drops on a negative return |
| 68 | read `eth.h_proto` (stack) | only reachable after the load on line 66 returned >= 0; stack object is initialised by the helper |
| 75 | `bpf_skb_load_bytes(skb, 14, &ip, 20)` | line 73: `len < 14 + 20` drops first, so load only when `len >= 34`; negative return drops (76) |
| 77, 79, 82 | read `ip.version`, `ip.ihl`, `ip.frag_off` (stack) | after the load on line 75 |
| 80, 84 | `ihl_bytes = ip.ihl * 4` is in [0, 60]; line 80 drops anything below 20; so `off += ihl_bytes` leaves `off` in [34, 74]. No `u32` overflow is possible (`off` <= 74, sizes <= 20) |
| 92 | `bpf_skb_load_bytes(skb, off, &tcp, 20)` | line 90: `len < off + 20` drops first; negative return drops (93) |
| 94 | read `tcp.source`, `tcp.dest` (stack) | after the load on line 92 |
| 101 | `bpf_skb_load_bytes(skb, off, &udp, 8)` | line 99: `len < off + 8` drops first; negative return drops (102) |
| 103 | read `udp.source`, `udp.dest` (stack) | after the load on line 101 |

Each helper call has a constant length (14, 20, 20, 8) into a stack buffer of exactly that size; the verifier accepted all four call sites.

Two independent layers guard each load: the explicit `skb->len` check in the program, and the helper's own failure return ("0 on success, or a negative error in case of failure", `/usr/include/bpf/bpf_helper_defs.h:714-731`). What the kernel checks inside the helper is UNVERIFIED (no kernel source was read); the program does not depend on it, because it checks `len` first and also handles a negative return.

Because the Ethernet header is loaded by value, no code path forms a pointer to packet memory, so the "pointer past `data_end`" class of bug that the paper-style direct-access version had to guard against does not exist in this revision. The cost is a helper call and a copy per layer (four per matching packet).

## 2. Every map operation and helper, and why a socket filter may use it

| item | where | status |
|---|---|---|
| `bpf_map_lookup_elem` (helper 1) | line 47, called from `count()`; two inlined call sites in the object (`p3_objdump.log` insns 85 and 97) | In the kernel's own helper list for `socket_filter` (`p3_helpers_socket_filter.log`, from `bpftool feature probe kernel`). The verifier accepted it. Key is a stack `u32` (`slot`), value pointer is NULL-checked at line 49 before use. In the loaded program the verifier replaced the call with inline array-lookup code that bounds the key (`if r0 >= 0x2` then NULL, `p3_xlated.log` insns 86-91), so a bad slot cannot index outside the 2-entry array |
| `__sync_fetch_and_add(v, 1)` | line 50 | Not a helper: a compiler builtin that clang emitted as a 64-bit BPF atomic (`r1 = atomic_fetch_add((u64 *)(r0 + 0x0), r1)` in `p3_objdump.log`; `atomic64_fetch_add` in `p3_xlated.log` insn 94). Accepted by the verifier on this kernel; this settles the "UNVERIFIED until the verifier accepts it" note in CODE_NOTES.md. It is an atomic add on a shared (non-per-CPU) array slot, so concurrent CPUs do not lose increments; contention cost was not measured |
| `bpf_skb_load_bytes` (helper 26) | lines 66, 75, 92, 101 | In the `socket_filter` helper list (`p3_helpers_socket_filter.log`). Accepted by the verifier |
| ctx field `skb->len` | lines 56, 110 | Accepted by the verifier. By contrast `skb->data`/`skb->data_end` were rejected in revision 1 |

Why a socket filter context permits these: the evidence is the running kernel's own report (the helper list above) plus the verifier's acceptance of this exact program. The reason inside the kernel (which helpers a program type is allowed, which ctx fields are readable) was not read from kernel source, so any statement beyond "the kernel reports and accepts it" is UNVERIFIED. The same list contains many helpers this program does not use (for example `bpf_map_update_elem`, `bpf_perf_event_output`, `bpf_ringbuf_output`); `bpf_trace_printk` is not in it. The program uses only the items in the table above.

## 3. Behaviour on truncated and garbage packets

Measured with `BPF_PROG_TEST_RUN` (`bpftool prog run pinned ... data_in FILE repeat 1`) over 38 frames built by `scripts/p3_make_packets.py`. The expected return value for each frame comes from a separate Python reference implementation of the Phase 2 rule, not from the C source (`logs/p3_packets_manifest_pfx14.log`). Result: 0 mismatches; counters moved by dropped +30, matched +8, as predicted (`logs/p3_check.log`).

| category | frames | observed return | counted in |
|---|---|---|---|
| well-formed, port 4040 (TCP/UDP, src or dst, IP options ihl 6 and 15, 100-byte payload, first fragment) | 8 | frame length (accept) | slot 1 |
| well-formed, other port or protocol (TCP 80, UDP 53, ICMP, ARP, IPv6 ethertype) | 5 | 0 | slot 0 |
| truncated: Ethernet only (14 B), IP cut at 10 B, IP with no L4, TCP cut at 10 B with port 4040 in the first 4 bytes, UDP cut at 4 B with port 4040, IHL 15 declared on a frame too short for it | 6 | 0 | slot 0 |
| below the Ethernet header: 0 bytes, 13 bytes | 2 | 0 | slot 0 |
| malformed headers: IHL 3, version 6 in an IPv4 frame, non-first fragment carrying port-4040 bytes | 3 | 0 | slot 0 |
| garbage: 64 zero bytes, 64 0xff bytes, 8 random frames with the IPv4 ethertype (21 to 126 B), 4 fully random frames (28 to 87 B) | 14 | 0 | slot 0 |

Which check dropped each frame, from reading the source (the test observes only the return value and counters, not the line that fired): an under-length Ethernet frame stops at line 64; an IP header that does not fit stops at 73; an IHL below 5 at 80; version != 4 at 77; a non-first fragment at 82; an L4 header that does not fit at 90 or 99 (this is why a TCP frame cut at 10 bytes is dropped even though port 4040 sits in the first four bytes: the filter requires the whole fixed header, as the Phase 2 matcher does); any other protocol at 106. On a truncated or garbage packet the program never accepts and never faults: the worst outcome in the data is a drop counted in slot 0.

## Limits of this evidence

- **Test-run framing.** The first test run, with frames sent as-is, dropped all 36 frames including the 8 that must match (`logs/p3_v2a_no_prefix/`). With 14 zero bytes prepended to every frame, all 38 behave as the reference predicts. This supports "for a socket filter, `BPF_PROG_TEST_RUN` removes the first 14 bytes before the program sees the packet" (the returned lengths equal the frame lengths without the prefix), but the mechanism was not read from kernel source. The 14 bytes come out of what the program is shown, not out of what was tested, so the results above describe the filter on the frame that follows the prefix.
- **Real socket framing is not tested.** Whether a real AF_PACKET `SOCK_RAW` socket presents the filter with the Ethernet header at offset 0 is UNVERIFIED until Phase 4 attaches the program to a live socket. If it does not, matched traffic will show as drops there.
- **Sample size.** 38 frames, of which 12 are random, show the checks work on these cases; they do not prove the absence of other bugs.
- **Counters.** Two counters, no per-reason breakdown, so the dropping line in section 3 is inferred from the source.
- **Timing.** `bpftool prog run` printed durations (about 125 to 750 ns per run); these are single runs of a test harness, not packet-rate measurements, and are not used anywhere.

## Relation to the claims (CLAIMS.md)

- **C5 (safe in-kernel VM):** the verifier refusing revision 1 at load time, with the reason in its log, is one concrete instance of safety being enforced before the code runs. It is one data point; Phase 5 is where rejections are collected on purpose.
- **C2 (reject-all cost flat vs packet size):** this phase does not measure cost. Structurally, a packet that fails an early check pays only the checks reached so far, and a non-matching packet is never copied to user space by this program (return 0). The measurement belongs to later phases.
- **C1 (register vs stack machine):** nothing here compares machines; the loaded program is 920 translated instructions (`p3_show.log`), a number about this program only.
