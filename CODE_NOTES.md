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
