# DEVIATIONS

## Phase 2

Format: what / why / taken or not.

- **D2.1 veth pair recreated.** The Phase 2 prompt assumed p1veth0/p1veth1 exist (DOWN) from Phase 1. They do not: scripts/phase1_verify.sh ends its veth check with `ip link del p1veth0`, and `ip -br link show` at the start of Phase 2 listed only `lo` and `enp0s8` (logs/p2_pre_state.log). scripts/phase2_verify.sh creates the pair. Taken.
- **D2.2 tcpdump used as the cross-check oracle** (as instructed). It is a live tool, not a file in reference/. Taken.
- **D2.3 tcpdump invocation changed.** Prompt: `tcpdump -i p1veth0 port 4040 -c 100 | tail -1`. Problem: tcpdump prints its "N packets captured" summary on stderr, so `| tail -1` on stdout would log the last packet line, not a count; and `-c 100` stops after 100 packets while the sniffer counts every packet in a 5 s run, so the two numbers would not be comparable. Used instead: full-window capture (`-nn "port 4040" -w /dev/null`, started before traffic, stopped after 3 s of quiescence) with stderr captured to logs/p2_tcpdump.log. Taken.
- **D2.4 sniffer output goes to a file, not `| tee &`.** A background pipeline gives no clean PID to stop; the script redirects to logs/p2_run.log (which the outer `| tee logs/p2_verify.log` also shows). The sniffer calls fflush after each line so it also behaves when piped. Taken.
- **D2.5 additions beyond the prompt.** A short iperf3 UDP run (50 Mbit/s, 2 s) so the UDP branch of the matcher is exercised, and a `truncated` counter in the sniffer. Taken.
- **D2.6 sudo.** Passwordless sudo is not configured on this machine (`sudo -n true` fails); privileged scripts are run in the user's Terminal tabs and the user types the password. Not a design change.
- **D2.7 Topology (supersedes the prompt's addressing).** Prompt: both 10.0.0.1 and 10.0.0.2 on p1veth0/p1veth1 in the root namespace. Evidence it does not carry traffic over the veth: `ip route get` says `local ... dev lo`, 57 packets and 0 matched on p1veth0 while iperf3 moved 9.94 GBytes (logs/p2_stageA*.log). Used instead: p1veth1 in namespace `p2ns` with 10.0.0.2/24, iperf3 server inside it. Taken.
- **D2.8 tcpdump runs as a systemd unit.** The terminal's processes carry the AppArmor label `claude-desktop`; tcpdump's profile accepts signals only from `unconfined` (abstractions/base:146), so root's kill and pkill got EPERM and the verify script hung (runs 1 and 2; logs/p2_h1_tcpdump_term.log, logs/p2_run1_verify.log). `systemd-run` / `systemctl stop` are used. Taken.
- **D2.9 Verification split into paced and full-rate runs, INCONCLUSIVE rule added** (docs/phase2_notes.md, "Amendment"). Taken.
- **D2.10 Stale logs.** logs/p2_run1_*.log are run 1 (full rate, tcpdump never stopped); logs/p2_run2_partial_crosscheck.log is run 2 (hung, counts computed by hand; its pcap and sniffer log were overwritten by run 3). Kept as history, not used for results.
- **D2.11 `scripts/p2_h1_tcpdump_term_test.sh`** was interrupted after variant A; variants B and C have no result. Not rerun: the cause was identified from variant A plus `ps -Z` and the AppArmor profile.

## Phase 3

- **D3.1 `type socket_filter` rejected by bpftool.** The prompt's command `bpftool prog load build/phase3_kern.o /sys/fs/bpf/repl_p3 type socket_filter` fails before the kernel is reached: `libbpf: failed to guess program type from ELF section 'socket_filter/'` (logs/p3_load.log); bpftool treats the `type` argument as a libbpf section name and `socket` is the listed name. The script retried with `type socket` (logs/p3_load_type_socket.log). Syntax fix only.
- **D3.2 Verifier rejects the program as specified (STOPPED, awaiting decision).** `invalid bpf_context access off=80 size=4` at insn 0, `r2 = *(u32 *)(r1 +80)`, i.e. reading `skb->data_end` (logs/p3_load_type_socket.log, full log in logs/p3_load_debug.log). Direct packet access through `skb->data` / `skb->data_end` is not allowed for a `socket` (socket filter) program on this kernel (6.17.0-19). Not changed silently: the spec requires direct access in SEC("socket").
- **D3.3 Packet access changed to `bpf_skb_load_bytes` (user-approved).** After D3.2 the user chose: keep `SEC("socket")`, check `skb->len` before each layer, load each header into a stack struct with `bpf_skb_load_bytes`, same rule and counters. Helper recorded in CODE_NOTES.md; the rejection logs are kept in logs/p3_v1_direct_access/ and the rejected source in src/rejected/phase3_kern_direct_access.c (useful for Phase 5).
- **D3.4 BPF_PROG_TEST_RUN framing: 14-byte prefix.** First test run (frames sent as-is, 36 frames): all 36 returned 0 including the 8 that must match (logs/p3_v2a_no_prefix/). Hypothesis: for this program type the test harness strips the first 14 bytes before the program sees the packet. Test: prepend 14 zero bytes to every frame. Result: 38 of 38 frames behave as the independent reference predicts (logs/p3_check.log). The hypothesis is supported by behaviour; the mechanism inside the kernel was not read. Whether a real AF_PACKET SOCK_RAW socket shows the filter the Ethernet header at offset 0 is UNVERIFIED until Phase 4.
- **D3.5 Extras beyond the Phase 3 prompt**: objdump of the object (logs/p3_objdump.log), xlated dump, `bpftool feature probe kernel` helper list (logs/p3_helpers_socket_filter.log), and the 38-frame test run with scripts/p3_make_packets.py + scripts/p3_check.py. The program stays pinned at /sys/fs/bpf/repl_p3 after the run.
- **D3.6 Reviewer rulings on Phase 3** (received with "Phase 3 complete"):
  - load_bytes design APPROVED: socket_filter context does not whitelist data/data_end; bounded-copy semantics match the paper's BPF machine loads. src/rejected/ kept as evidence.
  - "type socket" reclassified as tooling nomenclature, not a deviation (supersedes D3.1's framing).
  - 14-byte prepend accepted as BPF_PROG_TEST_RUN L3-view quirk; live AF_PACKET L2 view to be confirmed empirically in Phase 4.
  - arm64 JIT-disassembly absence recorded in ENV.md as platform limitation.
