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
