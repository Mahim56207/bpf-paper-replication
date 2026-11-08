/*
 * p10_memcpy.c - Phase 10 WP1(a): copy floor. One batch per invocation: `iters` calls of memcpy of `size` bytes between two cache-resident,
 * page-aligned buffers; prints "size,iters,ns_per_call". Usage: p10_memcpy <size> <iters> <cpu>
 * Design: docs/phase10_design.md section 4. Symbols used are recorded in CODE_NOTES.md (section Phase 10).
 */
#define _GNU_SOURCE
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static void *(*volatile mc)(void *, const void *, size_t) = memcpy;   /* the call cannot be removed or inlined away */

int main(int argc, char **argv)
{
	if (argc != 4) {
		fprintf(stderr, "usage: %s <size> <iters> <cpu>\n", argv[0]);
		return 2;
	}
	size_t size = strtoul(argv[1], NULL, 10);
	unsigned long iters = strtoul(argv[2], NULL, 10);
	int cpu = atoi(argv[3]);
	cpu_set_t set;
	CPU_ZERO(&set);
	CPU_SET(cpu, &set);
	if (sched_setaffinity(0, sizeof(set), &set) != 0) {
		perror("sched_setaffinity");
		return 1;
	}
	void *a = NULL, *b = NULL;
	if (posix_memalign(&a, 4096, size + 4096) || posix_memalign(&b, 4096, size + 4096)) {
		fprintf(stderr, "posix_memalign failed\n");
		return 1;
	}
	memset(a, 0x5a, size);
	memset(b, 0, size);
	for (unsigned long i = 0; i < 100000; i++)         /* warm-up, not timed */
		mc(b, a, size);
	struct timespec t0, t1;
	if (clock_gettime(CLOCK_MONOTONIC_RAW, &t0) != 0) {
		perror("clock_gettime");
		return 1;
	}
	for (unsigned long i = 0; i < iters; i++) {
		mc(b, a, size);
		__asm__ volatile("" ::: "memory");
	}
	if (clock_gettime(CLOCK_MONOTONIC_RAW, &t1) != 0) {
		perror("clock_gettime");
		return 1;
	}
	double ns = (double)(t1.tv_sec - t0.tv_sec) * 1e9 + (double)(t1.tv_nsec - t0.tv_nsec);
	printf("%zu,%lu,%.4f\n", size, iters, ns / (double)iters);
	return ((unsigned char *)b)[size - 1] == 0x5a ? 0 : 1;   /* the copy really happened */
}
