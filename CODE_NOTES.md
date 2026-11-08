# CODE_NOTES

Header hits are from `grep -n` on the installed headers (arm64 Ubuntu 25.10, see ENV.md). Format: symbol | file:line.
No libbpf function or BPF helper is used yet.

## Phase 2: src/baseline_sniffer.c

### Requested kernel UAPI headers (/usr/include/linux/)
| symbol | file:line | use |
|---|---|---|
| `struct sockaddr_ll` | linux/if_packet.h:14 | bind address and `recvfrom` source address |
| `sll_family` | linux/if_packet.h:15 | set to `AF_PACKET` |
| `sll_protocol` | linux/if_packet.h:16 | `htons(ETH_P_ALL)` |
| `sll_ifindex` | linux/if_packet.h:17 | interface index from `if_nametoindex` |
| `PACKET_STATISTICS` | linux/if_packet.h:44 | `getsockopt` for kernel packet/drop counts |
| `struct tpacket_stats` (`tp_packets`, `tp_drops`) | linux/if_packet.h:77 (fields 78-79) | result of `PACKET_STATISTICS` |
| `ETH_P_ALL` | linux/if_ether.h:132 | socket protocol, receive every packet |
| `ETH_P_IP` | linux/if_ether.h:52 | only IPv4 frames are parsed |
| `ETH_HLEN` | linux/if_ether.h:34 | Ethernet header length (14) |
| `struct ethhdr` (`h_proto`) | linux/if_ether.h:173 (h_proto at 176) | L2 header |
| `ETH_ALEN` | linux/if_ether.h:32 | used inside `struct ethhdr` |
| `struct iphdr` | linux/ip.h:87 | L3 header; `ihl`/`version` are bitfields guarded by `__LITTLE_ENDIAN_BITFIELD` (ip.h:88) |
| `iphdr.tot_len` / `frag_off` / `protocol` | linux/ip.h:98 / 100 / 102 | length sanity check, fragment check, L4 selector |
| `struct tcphdr` (`source`, `dest`) | linux/tcp.h:25 (fields 26-27) | L4 ports |
| `struct udphdr` (`source`, `dest`) | linux/udp.h:23 (fields 24-25) | L4 ports |

Absent from these headers: `IP_OFFSET` / `IP_MF` (grep of linux/ip.h found none). The IPv4 fragment-offset mask 0x1fff is therefore defined locally in the C file from RFC 791 (not from a header, UNVERIFIED against the RFC text in this session; it is a constant of the IPv4 header format).

### libc headers (outside the five requested; needed for the same program)
| symbol | file:line |
|---|---|
| `AF_PACKET` (= `PF_PACKET`) | /usr/include/aarch64-linux-gnu/bits/socket.h:113 (PF_PACKET at :61) |
| `SOCK_RAW` | /usr/include/aarch64-linux-gnu/bits/socket_type.h:32 |
| `SOL_PACKET` | /usr/include/aarch64-linux-gnu/bits/socket.h:151 |
| `MSG_TRUNC` | /usr/include/aarch64-linux-gnu/bits/socket.h:224 |
| `SO_RCVTIMEO` | /usr/include/asm-generic/socket.h:160 (OLD/NEW selection at :167, `SO_RCVTIMEO_OLD` :33) |
| `socket` / `bind` / `recvfrom` / `getsockopt` / `setsockopt` | /usr/include/aarch64-linux-gnu/sys/socket.h:102 / 112 / 163 / 255 / 277 |
| `if_nametoindex` | /usr/include/net/if.h:193 |
| `htons` | /usr/include/netinet/in.h:406 (macro forms :425, :431) |
| `IPPROTO_TCP` / `IPPROTO_UDP` | /usr/include/netinet/in.h:50 / 56 |
| `clock_gettime` | /usr/include/time.h:288 |
| `CLOCK_MONOTONIC` | /usr/include/linux/time.h:48 (also aarch64-linux-gnu/bits/time.h:48) |
| `sigaction` | /usr/include/signal.h:243 |

### Design notes tied to ENV.md (arm64, little-endian)
- Headers are `memcpy`'d from the packet buffer into local structs instead of pointer-cast: the IP header starts at offset 14, which is not 4-byte aligned, and a cast would be an aliasing/alignment hazard. No x86-specific assumption (no unaligned-access reliance, no packed-struct tricks, byte order via `htons`).
- Port comparison is done in network byte order against `htons(4040)`.

## Phase 3: src/phase3_kern.c (eBPF socket filter)

Grepped before first use. Format: symbol | file:line.

### Kernel UAPI and libbpf headers
| symbol | file:line | use |
|---|---|---|
| `BPF_MAP_TYPE_ARRAY` | /usr/include/linux/bpf.h:983 (enum); also build/vmlinux.h:32941 (`= 2`) | the counter map type |
| `BPF_PROG_TYPE_SOCKET_FILTER` | /usr/include/linux/bpf.h:1042 | program type of `SEC("socket")` |
| `FN(map_lookup_elem, 1, ##ctx)` | /usr/include/linux/bpf.h:5856 | helper id 1 |
| `bpf_map_lookup_elem` | /usr/include/bpf/bpf_helper_defs.h:64 (`static void *(* const bpf_map_lookup_elem)(void *map, const void *key) = (void *) 1;`) | the only helper used |
| `struct __sk_buff` | /usr/include/linux/bpf.h:6288; build/vmlinux.h:61514 (`data`, `data_end`, `len` are `__u32`) | program context |
| `SEC(name)` | /usr/include/bpf/bpf_helpers.h:41 / :45 | section placement |
| `__uint(name, val)` / `__type(name, val)` | /usr/include/bpf/bpf_helpers.h:13 / :14 | BTF-defined map fields |
| `__always_inline` | /usr/include/bpf/bpf_helpers.h:55 | helper function inlining |
| `__TARGET_ARCH_arm64` branch | /usr/include/bpf/bpf_tracing.h:17 | bpf_tracing.h needs a `__TARGET_ARCH_*` define; compile line passes `-D__TARGET_ARCH_arm64` |
| `".maps"` section | /usr/include/bpf/btf.h:22 (`MAPS_ELF_SEC`) | BTF map definitions live in `.maps` |

### Kernel structs: from generated build/vmlinux.h, not hand-written
| struct | build/vmlinux.h line | fields used |
|---|---|---|
| `struct ethhdr` | 100825 | `h_proto` (`__be16`) |
| `struct iphdr` | 88647 | `ihl:4`, `version:4`, `frag_off`, `protocol` |
| `struct tcphdr` | 88669 | `source`, `dest` |
| `struct udphdr` | 187932 | `source`, `dest` |
| `IPPROTO_TCP = 6` / `IPPROTO_UDP = 17` | 4911 / 4914 | L4 selector |

Not in vmlinux.h (macros are not in BTF): `ETH_P_IP` (0 hits). It is defined locally as 0x0800; the value is recorded at /usr/include/linux/if_ether.h:52 (Phase 2 grounding above).

### Not from a header
- `__sync_fetch_and_add`: clang builtin (not a helper, no header). UNVERIFIED until the verifier accepts it for this program type.
- `SEC("license")` with `char[]`: a libbpf loader convention with no header hit; Phase 1's `char _license[] SEC("license") = "GPL"` loaded and `bpftool prog show` printed `gpl` (logs/phase1_verify.log).
- `__builtin_bswap16`, `__BYTE_ORDER__`, `__ORDER_LITTLE_ENDIAN__`: compiler builtins/macros. `clang -target bpf -dM -E` defines `__BYTE_ORDER__ __ORDER_LITTLE_ENDIAN__`, i.e. the BPF target is little-endian here (same as arm64 host).
- `bpftool prog help` lists `TYPE := { socket | kprobe | kretprobe | classifier | action | ...`; `socket_filter` (the name used in the Phase 3 prompt) is not in that list. UNVERIFIED whether bpftool 7.7.0 accepts it; the real load attempt will show.

### Phase 3 revision 2 (direct packet access rejected; see DEVIATIONS.md D3.2)
Revision 1 read `skb->data` / `skb->data_end` and the verifier answered `invalid bpf_context access off=80 size=4` (logs/p3_v1_direct_access/p3_load_type_socket.log). Revision 2 uses a helper that the kernel lists for socket filters.
| symbol | file:line | use |
|---|---|---|
| `FN(skb_load_bytes, 26, ##ctx)` | /usr/include/linux/bpf.h:5881 | helper id 26 |
| `bpf_skb_load_bytes` | /usr/include/bpf/bpf_helper_defs.h:732: `static long (* const bpf_skb_load_bytes)(const void *skb, __u32 offset, void *to, __u32 len) = (void *) 26;`; doc comment at :714-731 ("0 on success, or a negative error") | copies `len` bytes at `offset` of the packet into a stack buffer |
| helper availability for `socket_filter` | logs/p3_v1_direct_access/p3_helpers_socket_filter.log (`bpftool feature probe kernel`): lists `bpf_map_lookup_elem` and `bpf_skb_load_bytes` | kernel-reported, not assumed |
| `skb->len` | `struct __sk_buff.len`, build/vmlinux.h:61514 (first field) | length of the packet, checked before every load. Read access is allowed (UNVERIFIED until the load succeeds) |

`data` and `data_end` are no longer used.

## Phase 4: src/loader.c (loader + map reader)

Grepped before first use. Format: symbol | file:line.

### libbpf 1.6.2 (installed headers, ENV.md)
| symbol | file:line | signature / documented behaviour |
|---|---|---|
| `bpf_object__open_file` | /usr/include/bpf/libbpf.h:228 | `struct bpf_object *bpf_object__open_file(const char *path, const struct bpf_object_open_opts *opts)`; "NULL is returned on error, error code is stored in errno" (doc :217-227) |
| `bpf_object__load` | /usr/include/bpf/libbpf.h:264 | `int bpf_object__load(struct bpf_object *obj)`; "0, on success; negative error code, otherwise, error code is stored in errno" |
| `bpf_object__find_program_by_name` | /usr/include/bpf/libbpf.h:323 | `struct bpf_program *...(const struct bpf_object *obj, const char *name)`; no doc comment, NULL for not found (UNVERIFIED: not stated in the header, checked at run time) |
| `bpf_program__fd` | /usr/include/bpf/libbpf.h:410 | `int bpf_program__fd(const struct bpf_program *prog)`; no doc comment; treated as failing when < 0 |
| `bpf_object__find_map_by_name` | /usr/include/bpf/libbpf.h:988 | **not in the Phase 4 prompt's list**; needed to get a `struct bpf_map *` from the object. "BPF map instance ...; or NULL otherwise" (doc :980-987). Recorded in DEVIATIONS.md D4.1 |
| `bpf_map__fd` | /usr/include/bpf/libbpf.h:1050 | `int bpf_map__fd(const struct bpf_map *map)`; "the file descriptor; or -EINVAL in case of an error" |
| `bpf_object__close` | /usr/include/bpf/libbpf.h:271 | `void bpf_object__close(struct bpf_object *obj)`; "closes a BPF object and releases all resources" |
| `bpf_map_lookup_elem` | /usr/include/bpf/bpf.h:154 | `int bpf_map_lookup_elem(int fd, const void *key, void *value)`; no doc comment; any non-zero result treated as failure (UNVERIFIED convention) |

### Socket options (attach path)
| symbol | file:line | use |
|---|---|---|
| `SO_ATTACH_BPF` | /usr/include/asm-generic/socket.h:82 (= 50) | `setsockopt(sock, SOL_SOCKET, SO_ATTACH_BPF, &prog_fd, sizeof(prog_fd))` |
| `SO_DETACH_BPF` | /usr/include/asm-generic/socket.h:83 (`= SO_DETACH_FILTER`, defined at :46 as 27) | detach on exit |
| `SOL_SOCKET` | /usr/include/asm-generic/socket.h:9 | option level |
| `PACKET_STATISTICS`, `struct tpacket_stats`, `SOL_PACKET` | see Phase 2 table (linux/if_packet.h:44, :77; bits/socket.h:151) | kernel counters printed at exit |
No attach API is invented: attach is plain `setsockopt` on the AF_PACKET socket, as the prompt requires.
- Timing for the 1 Hz loop: `clock_nanosleep` /usr/include/time.h:323; `TIMER_ABSTIME` /usr/include/aarch64-linux-gnu/bits/time.h:69 (also linux/time.h:82); `CLOCK_MONOTONIC` see Phase 2 table.

## Phase 6a: loader drain mode (src/loader.c) and control programs (src/phase6_filters.c)
New symbols beyond the Phase 4 tables. Grepped before use. Format: symbol | file:line.
| symbol | file:line | use |
|---|---|---|
| `poll` | /usr/include/aarch64-linux-gnu/sys/poll.h:54 | wait for the AF_PACKET socket to become readable, with a timeout up to the next 1 s tick |
| `struct pollfd` (`fd`, `events`, `revents`) | /usr/include/aarch64-linux-gnu/sys/poll.h:36 | argument to poll |
| `POLLIN` | /usr/include/aarch64-linux-gnu/bits/poll.h:25 | readable event |
| `MSG_DONTWAIT` | /usr/include/aarch64-linux-gnu/bits/socket.h:225 | non-blocking `recvfrom` in the drain loop |
| `EAGAIN` / `EWOULDBLOCK` | /usr/include/asm-generic/errno-base.h:15 / errno.h:22 | not tested explicitly: any `recvfrom` failure just ends a drain batch |
| `MSG_TRUNC`, `recvfrom` | see Phase 2 table | real packet length in `rx_bytes`; full-size copy (128 KiB buffer) |
No new libbpf function is used. `src/phase6_filters.c` uses only symbols already recorded for Phase 3 (`SEC`, `__uint`, `__type`, `__always_inline`, `bpf_map_lookup_elem`, `struct __sk_buff`, `BPF_MAP_TYPE_ARRAY`).

## Phase 6 C3: classifier tap (src/phase6_classify.c, src/classifier.c)
No new libbpf function or BPF helper beyond those already recorded (Phase 3: `bpf_skb_load_bytes`, `bpf_map_lookup_elem`, `SEC`, `__uint`, `__type`, `__always_inline`, `struct __sk_buff`, `BPF_MAP_TYPE_ARRAY`; Phase 4: `bpf_object__open_file`, `bpf_object__load`, `bpf_object__find_program_by_name`, `bpf_object__find_map_by_name`, `bpf_program__fd`, `bpf_map__fd`, `bpf_map_lookup_elem`, `bpf_object__close`, `SO_ATTACH_BPF`, `SO_DETACH_BPF`). One libc call is new:
| symbol | file:line | use |
|---|---|---|
| `nanosleep` | /usr/include/time.h:281 | the classifier loader sleeps in 1 s steps until SIGTERM/SIGINT (no per-second work) |

## Phase 6c: C1 instruction counts (src/c1_oracle.c, src/c1_interp.c)
Environment of this sub-phase: x86_64 container, libpcap 1.10.4 (`logs/p6c/p6c_env_probe.log`). Headers grepped before use (`logs/p6c/p6c_header_grep.log`). These are libpcap symbols, not libbpf; recorded here under the same rule. No libbpf function and no BPF helper is used in 6c.

| symbol | file:line | use |
|---|---|---|
| `pcap_open_dead(int, int)` | /usr/include/pcap/pcap.h:518 | handle for compiling a filter with no device (`DLT_EN10MB`, snaplen 65535) |
| `pcap_compile(pcap_t *, struct bpf_program *, const char *, int, bpf_u_int32)` | /usr/include/pcap/pcap.h:613 | expression to classic-BPF program, optimize flag 1 and 0 |
| `pcap_offline_filter(const struct bpf_program *, const struct pcap_pkthdr *, const u_char *)` | /usr/include/pcap/pcap.h:626 | the decision oracle: libpcap's own evaluator, non-zero = accept |
| `pcap_freecode`, `pcap_close`, `pcap_geterr` | /usr/include/pcap/pcap.h:623, :562, :607 | cleanup, error text |
| `PCAP_NETMASK_UNKNOWN` | /usr/include/pcap/pcap.h:365 | netmask argument of `pcap_compile` |
| `struct bpf_program` (`bf_len`, `bf_insns`) | /usr/include/pcap/bpf.h:116 | compiled program |
| `struct bpf_insn` (`code`, `jt`, `jf`, `k`) | /usr/include/pcap/bpf.h:244 | one classic-BPF instruction (paper section 3.3 format: opcode:16, jt:8, jf:8, k:32) |
| `struct pcap_pkthdr` (`ts`, `caplen`, `len`) | /usr/include/pcap/pcap.h:245 | per-packet header passed to `pcap_offline_filter` |
| `DLT_EN10MB` | /usr/include/pcap/dlt.h:63 | Ethernet link type |
| opcode macros `BPF_CLASS`, `BPF_LD`..`BPF_MISC` (:135-143), `BPF_SIZE`/`BPF_W`/`BPF_H`/`BPF_B` (:146-149), `BPF_MODE`/`BPF_IMM`/`BPF_ABS`/`BPF_IND`/`BPF_MEM`/`BPF_LEN`/`BPF_MSH` (:151-157), `BPF_OP`/`BPF_ADD`..`BPF_XOR` (:162-173), `BPF_JA`/`BPF_JEQ`/`BPF_JGT`/`BPF_JGE`/`BPF_JSET` (:180-184), `BPF_SRC`/`BPF_K`/`BPF_X` (:196-198), `BPF_RVAL`/`BPF_A` (:201-202), `BPF_MISCOP`/`BPF_TAX`/`BPF_TXA` (:206-224), `BPF_MEMWORDS` (:285) | /usr/include/pcap/bpf.h | opcode decoding in the register-machine interpreter; `BPF_MSH` is the `4*([k]&0xf)` mode of paper Table 2 |
| `bpf_filter`, `bpf_validate` | /usr/include/pcap/bpf.h:271, :274 | present in the header but NOT used: the interpreter under test is our own code, `bpf_filter` is not called (the oracle path is `pcap_offline_filter`) |
Standard C and POSIX calls used (`fopen`, `fread`, `fprintf`, `malloc`, `strtoul`, `qsort`-free) are libc, not recorded further. Port numbers 79 finger, 53 domain, 513 login, 514 shell were read from `/etc/services` (`logs/p6c/p6c_services_grep.log`).

## Phase 8.2: sender-limit test (scripts/p8_2_*, docs/phase8_2_design.md)
Environment: aarch64 VM, kernel 6.17.0-19-generic, `perf version 6.17.13` (`logs/p8/p8_2/p8_2_perf_probe_nonroot.log`). **No libbpf function and no BPF helper is added in 8.2**: the capture programs and the classifier are the existing binaries (`build/baseline_sniffer`, `build/loader`, `build/classifier`). The tools below are command-line programs; their options were taken from the installed `-h` output and `perf list`, recorded in the probe log, and are recorded here under the same rule.

| item | where it was found | use |
|---|---|---|
| `perf record -e <event> -a -C <cpu list> -F <freq> -g -o <file> -- <cmd>` | `perf record -h` in the probe log: `-a, --all-cpus`, `-C, --cpu <cpu>`, `-e, --event`, `-F, --freq`, `-g` (call-graph), `-o, --output`, `-B, --no-buildid` | sampling of the sender cores 1 and 4 during a flood |
| event `cpu-clock` | `perf list sw` in the probe log ("Per-CPU high-resolution timer based event. Unit: software"); backing constant `PERF_COUNT_SW_CPU_CLOCK = 0` at /usr/include/linux/perf_event.h:122 | the only usable sampling event: `ls /sys/bus/event_source/devices/` lists breakpoint, kprobe, software, tracepoint, uprobe (no hardware PMU) and `perf list hw` printed nothing |
| `perf script -i <file> -F comm,cpu,ip,sym` | `perf script -h` in the probe log: `-F, --fields` lists `comm`, `cpu`, `ip`, `sym`, `dso`; `-i, --input` | text dump of samples with call chains for counting |
| `perf report --stdio --no-children --sort comm,dso,symbol -i <file>` | `perf report -h` in the probe log: `--stdio`, `--no-children`, `-s, --sort` | informational top-of-profile listing |
| permissions | `perf_event_paranoid = 4`, `kptr_restrict = 1`, `/proc/kallsyms` addresses read as 0 for the non-root user (probe log) | perf runs as root (the run scripts are launched with sudo); non-root `perf record` fails with "Access to performance monitoring and observability operations is limited" (probe log) |
| kernel symbol `packet_rcv` | not in any installed header (kernel source is not installed here); it appears in the short paper's call graphs (`~/bpf-paper-short/data/perf/*/perf_report.txt`, read-only) | the AF_PACKET tap handler to look for in stacks. **UNVERIFIED on this machine until the Phase 8.2 probe lists the AF_PACKET handler symbols found in stacks; whether a ring-buffer variant (`tpacket_rcv`) occurs is likewise UNVERIFIED** |

## Phase 8.4: V8 validation (scripts/p8_4_*, docs/phase8_4_design.md)
No libbpf function and no BPF helper is added: the captures and the classifier are the existing binaries. Tools used and where their options were found (`logs/p8/p8_4/p8_4_tool_probe.log`, `stress-ng, version 0.19.03` on this aarch64 VM):

| item | where it was found | use |
|---|---|---|
| `stress-ng --cpu N` / `-c N` ("start N workers that perform CPU only loading"), `-l P, --cpu-load P` | `stress-ng --help` in the probe log | pure CPU noise (`--cpu-load` is not used: the duty cycle is made by SIGSTOP/SIGCONT so that the cache stressor can use the same mechanism) |
| `stress-ng --cache N` / `-C N` ("start N CPU cache thrashing workers"), `--cache-no-affinity` ("do not change CPU affinity") | same | cache/memory pressure noise; without `--cache-no-affinity` the stressor changes its own CPU affinity and would leave the pinned core |
| `stress-ng --vm N`, `--vm-bytes N`, `--vm-hang N` ("sleep N seconds before freeing memory"), `--vm-keep` | same | global memory pressure holding a fixed number of bytes (S3); `--vm-keep` is not used (it redirties memory continuously) |
| `-t N, --timeout T` | same ("defaulting to a 1 day run per stressor" without it) | an explicit long timeout; the workers are killed by the controller |
| `taskset -c <cpus>` | existing use in `scripts/bench.sh` | pinning of the controller and of every worker |
| SIGSTOP, SIGCONT, SIGKILL via Python `os.kill`/`os.killpg`, `os.sched_getaffinity` | Python standard library (no C header used) | duty cycling and the affinity check |
| `/proc/meminfo` `MemAvailable`, `SwapTotal`, `SwapFree` | read in Phase 8.1/8.2 | memory gate and the S3 holding size |
| `stress-ng --cache-enable-all` | message printed by `stress-ng --cache 1` in `logs/p8/p8_4/p8_4_controller_functional_test.log` ("use --cache-enable-all to enable all cache flags for heavier cache stressing"); amendment A1 of the Phase 8.4 design | the cache noise uses it |
| `/proc/<pid>/stat` fields 14 (utime) and 15 (stime), in clock ticks | `proc(5)`; read as in `scripts/summarize.py` (`CLK_TCK`) | CPU time consumed by a stress-ng worker (injected rate, design amendment A2) |

## Phase 10 (p10_api_check.sh, 2026-11-07T23:50:46+05:30): symbols checked in the installed headers before first use (logs/p10/p10_api_check.hits)
```
bpf_prog_test_run_opts | /usr/include/bpf/bpf.h:685 | LIBBPF_API int bpf_prog_test_run_opts(int prog_fd,
struct_bpf_test_run_opts | /usr/include/bpf/bpf.h:662 | struct bpf_test_run_opts {
bpf_test_run_opts.data_in; | /usr/include/bpf/bpf.h:664 | const void *data_in; /* optional */
bpf_test_run_opts.data_size_in; | /usr/include/bpf/bpf.h:666 | __u32 data_size_in;
bpf_test_run_opts.data_size_out; | /usr/include/bpf/bpf.h:667 | __u32 data_size_out; /* in: max length of data_out
bpf_test_run_opts.repeat; | /usr/include/bpf/bpf.h:677 | int repeat;
bpf_test_run_opts.duration; | /usr/include/bpf/bpf.h:678 | __u32 duration;      /* out: average per repetition in ns */
bpf_test_run_opts.retval; | /usr/include/bpf/bpf.h:676 | __u32 retval;        /* out: return code of the BPF program */
bpf_test_run_opts.batch_size; | /usr/include/bpf/bpf.h:681 | __u32 batch_size;
BPF_PROG_TEST_RUN | /usr/include/linux/bpf.h:358 | * BPF_PROG_TEST_RUN
BPF_PROG_TYPE_SOCKET_FILTER | /usr/include/linux/bpf.h:1042 | BPF_PROG_TYPE_SOCKET_FILTER,
libbpf_set_print | /usr/include/bpf/libbpf.h:100 | * @brief **libbpf_set_print()** sets user-provided log callback function to
bpf_object__open_file | /usr/include/bpf/libbpf.h:218 | * @brief **bpf_object__open_file()** creates a bpf_object by opening
bpf_object__load | /usr/include/bpf/libbpf.h:258 | * @brief **bpf_object__load()** loads BPF object into kernel.
bpf_object__find_program_by_name | /usr/include/bpf/libbpf.h:323 | bpf_object__find_program_by_name(const struct bpf_object *obj,
bpf_program__fd | /usr/include/bpf/libbpf.h:410 | LIBBPF_API int bpf_program__fd(const struct bpf_program *prog);
SO_ATTACH_BPF | /usr/include/asm-generic/socket.h:82 | #define SO_ATTACH_BPF		50
SO_RCVBUFFORCE | /usr/include/asm-generic/socket.h:20 | #define SO_RCVBUFFORCE	33
SO_BINDTODEVICE | /usr/include/asm-generic/socket.h:42 | #define SO_BINDTODEVICE	25
SOL_PACKET | /usr/include/aarch64-linux-gnu/bits/socket.h:151 | #define SOL_PACKET	263
PACKET_STATISTICS | /usr/include/linux/if_packet.h:44 | #define PACKET_STATISTICS		6
struct_tpacket_stats | /usr/include/linux/if_packet.h:77 | struct tpacket_stats {
sendmmsg | /usr/include/aarch64-linux-gnu/sys/socket.h:89 | /* For `recvmmsg' and `sendmmsg'.  */
struct_mmsghdr | /usr/include/aarch64-linux-gnu/sys/socket.h:90 | struct mmsghdr
recvmmsg | /usr/include/aarch64-linux-gnu/sys/socket.h:89 | /* For `recvmmsg' and `sendmmsg'.  */
SYS_setns | /usr/include/aarch64-linux-gnu/bits/syscall.h:2143 | # define SYS_setns __NR_setns
syscall | /usr/include/unistd.h:1091 | extern long int syscall (long int __sysno, ...) __THROW;
CLONE_NEWNET | /usr/include/aarch64-linux-gnu/bits/sched.h:118 | # define CLONE_NEWNET	0x40000000	/* New network namespace.  */
CLONE_NEWNET | /usr/include/linux/sched.h:33 | #define CLONE_NEWNET		0x40000000	/* New network namespace */
clock_gettime | /usr/include/time.h:288 | extern int clock_gettime (clockid_t __clock_id, struct timespec *__tp)
CLOCK_MONOTONIC_RAW | /usr/include/linux/time.h:51 | #define CLOCK_MONOTONIC_RAW		4
CLOCK_MONOTONIC_RAW | /usr/include/aarch64-linux-gnu/bits/time.h:54 | # define CLOCK_MONOTONIC_RAW		4
clock_nanosleep | /usr/include/time.h:323 | extern int clock_nanosleep (clockid_t __clock_id, int __flags,
sched_setaffinity | /usr/include/sched.h:130 | extern int sched_setaffinity (__pid_t __pid, size_t __cpusetsize,
MSG_DONTWAIT | /usr/include/aarch64-linux-gnu/bits/socket.h:225 | MSG_DONTWAIT	= 0x40, /* Nonblocking IO.  */
ETH_P_ALL | /usr/include/linux/if_ether.h:132 | #define ETH_P_ALL	0x0003		/* Every packet (be careful!!!) */
```

## Phase 10 WP1b additions (2026-11-08)
- `CLOCK_THREAD_CPUTIME_ID`, `clock_gettime`: see hits below (glibc/kernel headers, not libbpf). The libbpf and kernel symbols of `p10b_testrun.c` and `p10b_drain.c` are the same as those of `p10_testrun.c` and `p10_drain.c`, already recorded in the Phase 10 section above.
- `CLOCK_THREAD_CPUTIME_ID`: /usr/include/linux/time.h:50 (`#define CLOCK_THREAD_CPUTIME_ID 3`). `clock_gettime`: /usr/include/time.h:288.

## Demo kit (scripts/demo/, 2026-11-09)
- No libbpf function, BPF helper or kernel symbol is used that is not already recorded above: act 1 runs the existing `build/loader` (libbpf calls recorded in the Phase 4 section) on objects built in Phases 3, 5 and 10; act 2 runs `iperf3`, `build/baseline_sniffer` and `scripts/lab_up.sh`; act 3 runs `scripts/demo_c1.sh` unchanged. The only new system interfaces are shell commands (`timeout`, `taskset`, `ip netns`, `/sys/class/net/<if>/statistics/tx_packets`, `/proc/<pid>/stat`), not C symbols.
