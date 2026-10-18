/*
 * phase6_classify.c - Phase 6 addendum A1: the classifier tap (docs/phase6_addenda.md section 1).
 *
 * A BPF socket filter that counts every frame at the tap into its own array map and accepts nothing
 * (returns 0, so nothing is queued or copied). Classes, IPv4 only, by protocol and port, either direction:
 *   F4040 udp port 4040   C4040 tcp port 4040   F5050 udp port 5050   C5050 tcp port 5050
 *   X     everything else (non-IPv4, other protocols, other ports, non-first fragments, truncated frames)
 *   T     every frame
 * Every frame increments T once and exactly one of the five classes, so T = F4040 + C4040 + F5050 + C5050 + X
 * must hold exactly (rule V5'e). It is attached by build/classifier next to whichever capture process a run
 * measures, in every config, so its per-packet cost is common to all configs.
 *
 * Symbols used are recorded in CODE_NOTES.md with header file:line.
 */
#include <vmlinux.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

#define ETH_P_IP 0x0800
#define IP_FRAG_OFFSET_MASK 0x1fff
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#define BE16(x) __builtin_bswap16(x)
#else
#define BE16(x) (x)
#endif

enum {
	SLOT_T = 0,
	SLOT_F4040 = 1,
	SLOT_C4040 = 2,
	SLOT_F5050 = 3,
	SLOT_C5050 = 4,
	SLOT_X = 5,
	SLOT_MAX = 8,
};

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(max_entries, SLOT_MAX);
	__type(key, __u32);
	__type(value, __u64);
} cls_counters SEC(".maps");

static __always_inline void count(__u32 slot)
{
	__u64 *v = bpf_map_lookup_elem(&cls_counters, &slot);

	if (v)
		__sync_fetch_and_add(v, 1);
}

SEC("socket")
int classify(struct __sk_buff *skb)
{
	__u32 len = skb->len;
	__u32 off = 0;
	struct ethhdr eth;
	struct iphdr ip;
	struct {
		__be16 src;
		__be16 dst;
	} ports;
	int is_udp;

	count(SLOT_T);

	if (len < off + sizeof(eth))
		goto other;
	if (bpf_skb_load_bytes(skb, off, &eth, sizeof(eth)) < 0)
		goto other;
	if (eth.h_proto != BE16(ETH_P_IP))
		goto other;
	off += sizeof(eth);

	if (len < off + sizeof(ip))
		goto other;
	if (bpf_skb_load_bytes(skb, off, &ip, sizeof(ip)) < 0)
		goto other;
	if (ip.version != 4)
		goto other;
	if (ip.ihl * 4 < sizeof(ip))
		goto other;
	if (ip.frag_off & BE16(IP_FRAG_OFFSET_MASK))
		goto other;
	off += ip.ihl * 4;

	if (ip.protocol == IPPROTO_UDP)
		is_udp = 1;
	else if (ip.protocol == IPPROTO_TCP)
		is_udp = 0;
	else
		goto other;
	if (len < off + sizeof(ports))
		goto other;
	if (bpf_skb_load_bytes(skb, off, &ports, sizeof(ports)) < 0)
		goto other;

	if (ports.src == BE16(4040) || ports.dst == BE16(4040)) {
		if (is_udp)
			count(SLOT_F4040);
		else
			count(SLOT_C4040);
		return 0;
	}
	if (ports.src == BE16(5050) || ports.dst == BE16(5050)) {
		if (is_udp)
			count(SLOT_F5050);
		else
			count(SLOT_C5050);
		return 0;
	}

other:
	count(SLOT_X);
	return 0;
}

char LICENSE[] SEC("license") = "GPL";
