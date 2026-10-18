/*
 * phase6_filters.c - Phase 6 control programs: two trivial socket filters sharing the Phase 3
 * counter-map layout (BPF_MAP_TYPE_ARRAY, 2 entries, key u32, value u64).
 *
 *   reject_all: slot 0 (dropped) += 1, return 0          (config D: kernel filter, nothing delivered)
 *   accept_all: slot 1 (matched) += 1, return skb->len   (config E: kernel filter, everything delivered)
 *
 * The key is a constant in both programs; the NULL check is kept, as in phase3_kern.c.
 * Both programs live in one object; build/loader selects one with `-p`.
 * Symbols used are recorded in CODE_NOTES.md with header file:line.
 */
#include <vmlinux.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

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
int reject_all(struct __sk_buff *skb)
{
	(void)skb;
	count(SLOT_DROPPED);
	return 0;
}

SEC("socket")
int accept_all(struct __sk_buff *skb)
{
	count(SLOT_MATCHED);
	return skb->len;
}

char LICENSE[] SEC("license") = "GPL";
