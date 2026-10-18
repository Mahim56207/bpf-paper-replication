# Phase 4 notes: loader and map reader (src/loader.c)

Logs are in `logs/`. Statements about kernel internals that were not observed in a log are marked UNVERIFIED.

## Outcome

| item | result | evidence |
|---|---|---|
| compile (exact command from the prompt) | exit 0, no warnings | `p4_compile.log` |
| lab network | `p1veth0` 10.0.0.1/24 in the root namespace, `p1veth1` 10.0.0.2/24 in `p2ns`; `ip route get 10.0.0.2` goes `dev p1veth0` | `p4_netsetup.log` |
| matched counter vs tcpdump (port 4040, full window) | loader matched **10,800**; tcpdump captured 10,800, received by filter 10,800, dropped 0. abs_diff 0, allowance 54 -> **PASS** | `p4_crosscheck.log` |
| total counter vs tcpdump (no filter) | loader slot0+slot1 = **18,478**; tcpdump received by filter 18,482. abs_diff 4, allowance 92 -> **PASS** | `p4_crosscheck.log` |
| dropped slot moved (noise traffic) | slot 0 = **7,678** | `p4_run.log`, `p4_crosscheck.log` |
| L2 view | **CONFIRMED** (see below) | `p4_crosscheck.log` |
| verifier silence | `bpftool prog load ... 2>logs/p4_verifier.log` exit 0, **0 bytes**; temp pin removed | `p4_verify.log` lines 274-276, `p4_verifier_wc.log` |
| prog/map snapshots | during traffic and after the loader exited | `p4_prog_show*.log`, `p4_map_show*.log` |
| cleanup | no loader, iperf3 or tcpdump left running | `p4_cleanup.log` |

Traffic: TCP 100 Mbit/s for 5 s then UDP 50 Mbit/s for 2 s to port 4040 (Phase 2's paced run), with concurrent noise to other ports: TCP 20 Mbit/s to 5050 and UDP 10 Mbit/s to 5051 for 8 s (`p4_iperf_client*.log`, `p4_noise_*.log`).

## Attach path

`loader <iface> [object]`:
1. `bpf_object__open_file("build/phase3_kern.o", NULL)`, then `bpf_object__load()`. libbpf picks the program type from the `socket` ELF section; `bpftool prog show` reports it as `socket_filter`.
2. `bpf_object__find_program_by_name("phase3_filter")` and `bpf_object__find_map_by_name("p3_counters")` give `bpf_program__fd` (5) and `bpf_map__fd` (4) (`p4_run.log`, START line).
3. `socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL))`, `bind()` to the interface index from `if_nametoindex`, then `setsockopt(sock, SOL_SOCKET, SO_ATTACH_BPF, &prog_fd, sizeof(prog_fd))`. No attach API other than this `setsockopt` is used (grounding in CODE_NOTES.md).
4. Once per second the loader reads slot 0 and slot 1 with `bpf_map_lookup_elem` and prints total, matched, dropped and per-second rates, using absolute-time sleeps so the interval does not drift.
5. On SIGINT/SIGTERM it reads the counters one last time, prints `FINAL`, then `SO_DETACH_BPF`, `close(sock)`, `bpf_object__close()`.

Evidence of attach and of cleanup: during traffic `bpftool prog show` lists `1671: socket_filter name phase3_filter ... loaded_at 22:18:26 ... map_ids 152` (the loader's) alongside `1289 ... map_ids 117` (the Phase 3 program still pinned at `/sys/fs/bpf/repl_p3`). After the loader exits only 1289 and map 117 remain, so the loader's program and map were released (`p4_prog_show.log`, `p4_prog_show_after.log`, `p4_map_show_after.log`).

## Counter semantics

Slot 0 counts packets the filter dropped (every failed check and every non-match), slot 1 counts matches, and total = slot0 + slot1, computed by the loader. The loader reads the two slots one after the other, so a printed line is not an atomic snapshot of both. The counts are cumulative from the moment the program is loaded and attached; they include both directions on `p1veth0` and background frames (ARP, IPv6).

The loader never reads the socket. Accepted packets queue on it, and when the queue fills the socket drops them. The final socket statistics show it: `kernel_packets=10800 kernel_drops=10763` (`p4_run.log`, FINAL_SOCKET). The kernel counter `kernel_packets` equals the matched count exactly, and 10,763 of those 10,800 accepted packets were dropped at the socket (so about 37 fit in the queue, an inference from the two numbers). The matched counter is unaffected by this: it still equals tcpdump's independent count. That is the evidence that the counters increment when the filter runs, before queueing; the kernel-side ordering itself was not read from source (UNVERIFIED), the run is what supports it. Consequence for later phases: this loader measures what the filter decides, not delivery to a user-space reader; a phase that measures delivery needs a reader.

## Cross-check

Rules were fixed in `scripts/phase4_verify.sh` before the run:
- **matched:** `|loader matched - tcpdump(port 4040) captured| <= max(10, captured/200) + tcpdump dropped`; INCONCLUSIVE if tcpdump dropped more than 1% of captured. This is the Phase 2 rule with the sniffer-drop term removed. In Phase 2 the sniffer counted only what it read, so its socket drops had to be allowed for. Here the counter is incremented by the filter before queueing, so the socket's own drops (10,763 above) are not subtracted. The run tests that assumption, and it held: matched equals tcpdump's count exactly even though almost all accepted packets were dropped at the socket.
- **total:** `|loader slot0+slot1 - tcpdump(no filter) received by filter| <= max(10, received/200)`.

Result: matched diff 0 (loader 10,800, tcpdump captured 10,800 and received-by-filter 10,800, no tcpdump drops). Total diff 4 (18,478 vs 18,482; the two captures start and stop a few milliseconds apart and the background ARP/IPv6 frames fall in that skew; allowance 92). One run each; the paced rates mean no tool was near its limit (tcpdump dropped 0 in both captures).

## L2 view confirmation (closes the Phase 3 open item, DEVIATIONS D3.6)

**Conclusion: a live AF_PACKET `SOCK_RAW` socket on this interface presents the attached filter with the frame starting at the Ethernet header (an L2 view).** Evidence: the program reads `eth.h_proto` at offset 0 and requires `0x0800`, then reads the IPv4 header at offset 14 (`src/phase3_kern.c` lines 64-84). It matched 10,800 packets on real iperf3 traffic, identical to tcpdump's independent count of port-4040 packets. Had the filter been shown the packet from the IP header on (as `BPF_PROG_TEST_RUN` does, which is why Phase 3 needed the 14-byte prefix), bytes 12-13 would be part of the IPv4 source address, not 0x0800, and slot 1 would have stayed at 0 with every packet counted as dropped. That is what the unprefixed Phase 3 test run showed (`logs/p3_v2a_no_prefix/`). Scope: this was shown for an Ethernet-type veth interface and `SOCK_RAW`; `SOCK_DGRAM` and other link types were not tested.

## Verifier silence

`bpftool prog load build/phase3_kern.o /sys/fs/bpf/repl_p4 type socket 2>logs/p4_verifier.log` exited 0 and the file is 0 bytes (`wc -c` output `0`), then the temp pin was removed (`p4_verify.log` lines 274-276). This shows bpftool printed nothing to stderr for a successful load at its default verbosity. It says nothing about the verifier's own log, which was not requested at this level.

## libbpf API notes (deviations)

- **D4.1 `bpf_object__find_map_by_name`** was needed to get the map from the object and is not in the prompt's list. Grepped and recorded first (`/usr/include/bpf/libbpf.h:988`).
- **Return conventions.** The header documents `bpf_object__open_file` (NULL, error in errno), `bpf_object__load` (0 or negative error) and `bpf_map__fd` (fd or -EINVAL). It has no doc comment for `bpf_program__fd`, `bpf_object__find_program_by_name` or `bpf_map_lookup_elem`; the loader treats `< 0`, NULL and non-zero respectively as failure. That convention is UNVERIFIED against the header text, and the successful run did not exercise the failure paths.
- No libbpf function outside CODE_NOTES.md is used, and `libbpf_set_print` is not called (libbpf's default stderr output applies).

## Other notes

- The first run printed `WARN: systemctl stop p4-td4040 failed` (and the same for p4-tdall) twice during cleanup. They are harmless: the units had already been stopped, `--collect` had removed them, and the later idempotent stop found nothing. `td_stop` now checks `systemctl is-active` first. The counts above were collected before those messages and are unaffected.
- Not measured here: CPU cost, or any packet-rate limit of the loader. The per-second `pps` columns in `p4_run.log` reflect the paced offered load, not capacity.
- The lab network is left up (`scripts/lab_up.sh down` removes it), and `/sys/fs/bpf/repl_p3` from Phase 3 is still pinned.

## Negative runs and commit-time re-run (reviewer request, DEVIATIONS D4.5)

`scripts/p4_negatives.sh`, output in `logs/p4_negatives.log`. Each ran under `timeout 15` so a hang would show as exit 124; none did.

| case | output (last line is the loader's own message) | exit |
|---|---|---|
| `sudo ./build/loader nosuchif0` | `if_nametoindex(nosuchif0): No such device` | 1 |
| `./build/loader p1veth0` as uid 1000 (no sudo) | libbpf warnings (`Failed to bump RLIMIT_MEMLOCK (err = -EPERM)`, `Error in bpf_object__probe_loading(): -EPERM`), then `bpf_object__load: Operation not permitted` | 1 |
| extra: object path that does not exist | `libbpf: elf: failed to open /no/such/object.o: -ENOENT`, then `bpf_object__open_file(/no/such/object.o): No such file or directory` | 1 |
| extra: no arguments | `usage: ./build/loader <iface> [object]` | 2 |

No crash and no hang. The loader's own message is clean in every case; in case 2 libbpf adds its own warnings above it. These exercise the interface lookup, object open, and object load failure paths; they do not reach the `socket()`, `bind()` or `SO_ATTACH_BPF` failure paths, which were not exercised.

Verify re-run (`logs/p4_rerun/`, via `scripts/rerun_p4.sh`): matched 10,770 = tcpdump captured 10,770 = received-by-filter 10,770 (diff 0, PASS); total 18,484 vs 18,484 (diff 0, PASS); slot 0 = 7,714; L2 view confirmed again; verifier-silence file 0 bytes; no WARN lines (the `td_stop` fix works); the socket again dropped almost all accepted packets (`kernel_drops=10731` of `kernel_packets=10770`) while the matched counter stayed equal to tcpdump's. Numbers differ slightly from the first run (traffic is not byte-identical between runs), which is why the first run's figures in this document are quoted from `logs/`, not the re-run.
