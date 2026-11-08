/*
 * p10_loop_bounded.c - Phase 10 WP4: a socket filter with a loop of a constant, small bound (100 iterations), not unrolled. Expected: the verifier
 * accepts it on a kernel with bounded-loop support (docs/phase10_design.md rule P12). The empty asm statement keeps the compiler from replacing the loop
 * by a closed form. Needs no helper.
 */
#include <vmlinux.h>
#include <bpf/bpf_helpers.h>

SEC("socket")
int p10_bounded(struct __sk_buff *skb)
{
	__u32 sum = skb->len;

#pragma nounroll
	for (__u32 i = 0; i < 100; i++) {
		sum = sum * 31 + i;
		__asm__ volatile("" : "+r"(sum));
	}
	return sum & 0xffff;
}

char LICENSE[] SEC("license") = "GPL";
