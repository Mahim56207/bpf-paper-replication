/*
 * p10_loop_unbounded.c - Phase 10 WP4: a socket filter with a loop that has no exit the verifier can bound. Expected: the verifier rejects it
 * (docs/phase10_design.md rule P12). The volatile counter keeps the compiler from removing the loop. Needs no helper.
 */
#include <vmlinux.h>
#include <bpf/bpf_helpers.h>

SEC("socket")
int p10_unbounded(struct __sk_buff *skb)
{
	volatile __u32 i = 0;

	(void)skb;
	while (1)
		i++;
	return 0;
}

char LICENSE[] SEC("license") = "GPL";
