/*
 * phase3_kern.c - Phase 3: the same match rule as the Phase 2 sniffer, as an eBPF socket filter.
 *
 * Match: IPv4 TCP or UDP with source or destination port 4040. Every packet-pointer
 * dereference is licensed by a bounds check against data_end made immediately before it
 * (see docs/phase3_review.md). Return value: skb->len = accept (keep that many bytes),
 * 0 = drop.
 *
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

	if (v)
		__sync_fetch_and_add(v, 1);
}

SEC("socket")
int phase3_filter(struct __sk_buff *skb)
{
	void *data = (void *)(long)skb->data;
	void *data_end = (void *)(long)skb->data_end;
	struct ethhdr *eth = data;
	struct iphdr *ip;
	void *l4;
	__u32 ihl_bytes;
	__be16 port_be = BE16(MATCH_PORT);

	/* Layer 2 */
	if ((void *)(eth + 1) > data_end)
		goto drop;
	if (eth->h_proto != BE16(ETH_P_IP))
		goto drop;

	/* Layer 3 */
	ip = (void *)(eth + 1);
	if ((void *)(ip + 1) > data_end)
		goto drop;
	if (ip->version != 4)
		goto drop;
	ihl_bytes = ip->ihl * 4;
	if (ihl_bytes < sizeof(*ip))
		goto drop;
	if (ip->frag_off & BE16(IP_FRAG_OFFSET_MASK))
		goto drop;
	l4 = (void *)ip + ihl_bytes;

	/* Layer 4 */
	if (ip->protocol == IPPROTO_TCP) {
		struct tcphdr *tcp = l4;

		if ((void *)(tcp + 1) > data_end)
			goto drop;
		if (tcp->source != port_be && tcp->dest != port_be)
			goto drop;
	} else if (ip->protocol == IPPROTO_UDP) {
		struct udphdr *udp = l4;

		if ((void *)(udp + 1) > data_end)
			goto drop;
		if (udp->source != port_be && udp->dest != port_be)
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
