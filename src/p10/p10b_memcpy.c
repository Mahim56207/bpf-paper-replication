/*
 * p10b_memcpy.c - Phase 10 WP1b(a): copy floor, long batches. One batch per invocation: chunks of 5,000,000 memcpy calls of `size` bytes between two cache-resident,
 * page-aligned buffers, repeated until the measured wall time of the chunks is at least <min_s> seconds. Wall time is CLOCK_MONOTONIC_RAW, thread CPU time is
 * CLOCK_THREAD_CPUTIME_ID, both over the same chunks. Prints "size,total_iters,chunks,ns_per_call_wall,ns_per_call_cpu,wall_s,cpu_s".
 * Usage: p10b_memcpy <size> <min_s> <cpu>. Design: docs/phase10_wp1b_design.md section 3.
 */
#define _GNU_SOURCE
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define CHUNK 5000000UL

static void *(*volatile mc)(void *, const void *, size_t) = memcpy;

static double ts_ns(clockid_t id)
{
	struct timespec t;

	if (clock_gettime(id, &t) != 0) {
		perror("clock_gettime");
		exit(1);
	}
	return (double)t.tv_sec * 1e9 + (double)t.tv_nsec;
}

int main(int argc, char **argv)
{
	if (argc != 4) {
		fprintf(stderr, "usage: %s <size> <min_s> <cpu>\n", argv[0]);
		return 2;
	}
	size_t size = strtoul(argv[1], NULL, 10);
	double min_ns = atof(argv[2]) * 1e9;
	int cpu = atoi(argv[3]);
	if (size < 1 || min_ns <= 0) {
		fprintf(stderr, "bad arguments\n");
		return 2;
	}
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
	double w0 = ts_ns(CLOCK_MONOTONIC_RAW), c0 = ts_ns(CLOCK_THREAD_CPUTIME_ID), w = 0, c = 0;
	unsigned long chunks = 0;
	do {
		for (unsigned long i = 0; i < CHUNK; i++) {
			mc(b, a, size);
			__asm__ volatile("" ::: "memory");
		}
		chunks++;
		w = ts_ns(CLOCK_MONOTONIC_RAW) - w0;
		c = ts_ns(CLOCK_THREAD_CPUTIME_ID) - c0;
	} while (w < min_ns);
	double iters = (double)chunks * (double)CHUNK;
	printf("%zu,%.0f,%lu,%.5f,%.5f,%.4f,%.4f\n", size, iters, chunks, w / iters, c / iters, w / 1e9, c / 1e9);
	return ((unsigned char *)b)[size - 1] == 0x5a ? 0 : 1;
}
