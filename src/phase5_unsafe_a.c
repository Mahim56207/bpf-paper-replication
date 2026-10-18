/*
 * phase5_unsafe_a.c - Phase 5 variant A (INTENTIONALLY UNSAFE; do not fix).
 * phase3_kern.c with the NULL check on the bpf_map_lookup_elem() return removed before the map
 * value is dereferenced. The verifier is expected to reject it (map-value nullness).
 */
/*
 * phase3_kern.c - Phase 3 (revision 2): the Phase 2 match rule as an eBPF socket filter.
 *
 * Match: IPv4 TCP or UDP with source or destination port 4040. Revision 1 used direct packet
 * access (skb->data / skb->data_end); the verifier rejects that in a socket filter
 * (logs/p3_v1_direct_access/). Revision 2 reads each header with bpf_skb_load_bytes() into a
 * stack struct, after an explicit skb->len check for that layer. Any failed check or failed
 * load drops the packet.
 *
 * Return value: skb->len = accept (keep that many bytes), 0 = drop.
 * Counters (BPF_MAP_TYPE_ARRAY, 2 entries): slot 0 = dropped packets (every failed check and
 * every non-match), slot 1 = matched packets. total = slot0 + slot1.
 *
 * Symbols used are recorded in CODE_NOTES.md with header file:line.
 */
#include <vmlinux.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

#define MATCH_PORT 4040
/* Not in vmlinux.h (macros are not in BTF); value from linux/if_ether.h, see CODE_NOTES.md. */
#define ETH_P_IP 0x0800
/* IPv4 fragment-offset mask (RFC 791); a non-zero offset means no L4 header in this packet. */
#define IP_FRAG_OFFSET_MASK 0x1fff

/* Network byte order constants. */
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#define BE16(x) __builtin_bswap16(x)
#else
#define BE16(x) (x)
#endif

enum {
	SLOT_DROPPED = 0,
	SLOT_MATCHED = 1,
};

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(max_entries, 2);
	__type(key, __u32);
	__type(value, __u64);
} p3_counters SEC(".maps");

static __always_inline void count(__u32 slot)
{
	__u64 *v = bpf_map_lookup_elem(&p3_counters, &slot);

	__sync_fetch_and_add(v, 1);
}

SEC("socket")
int phase3_filter(struct __sk_buff *skb)
{
	__u32 len = skb->len;
	__u32 off = 0;
	__u32 ihl_bytes;
	__be16 port_be = BE16(MATCH_PORT);
	struct ethhdr eth;
	struct iphdr ip;

	/* Layer 2 */
	if (len < off + sizeof(eth))
		goto drop;
	if (bpf_skb_load_bytes(skb, off, &eth, sizeof(eth)) < 0)
		goto drop;
	if (eth.h_proto != BE16(ETH_P_IP))
		goto drop;
	off += sizeof(eth);

	/* Layer 3 */
	if (len < off + sizeof(ip))
		goto drop;
	if (bpf_skb_load_bytes(skb, off, &ip, sizeof(ip)) < 0)
		goto drop;
	if (ip.version != 4)
		goto drop;
	ihl_bytes = ip.ihl * 4;
	if (ihl_bytes < sizeof(ip))
		goto drop;
	if (ip.frag_off & BE16(IP_FRAG_OFFSET_MASK))
		goto drop;
	off += ihl_bytes;

	/* Layer 4 */
	if (ip.protocol == IPPROTO_TCP) {
		struct tcphdr tcp;

		if (len < off + sizeof(tcp))
			goto drop;
		if (bpf_skb_load_bytes(skb, off, &tcp, sizeof(tcp)) < 0)
			goto drop;
		if (tcp.source != port_be && tcp.dest != port_be)
			goto drop;
	} else if (ip.protocol == IPPROTO_UDP) {
		struct udphdr udp;

		if (len < off + sizeof(udp))
			goto drop;
		if (bpf_skb_load_bytes(skb, off, &udp, sizeof(udp)) < 0)
			goto drop;
		if (udp.source != port_be && udp.dest != port_be)
			goto drop;
	} else {
		goto drop;
	}

	count(SLOT_MATCHED);
	return skb->len;

drop:
	count(SLOT_DROPPED);
	return 0;
}

char LICENSE[] SEC("license") = "GPL";
