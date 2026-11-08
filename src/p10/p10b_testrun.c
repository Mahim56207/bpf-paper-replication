/*
 * p10b_testrun.c - Phase 10 WP1b(b): in-kernel filter cost by BPF_PROG_TEST_RUN, long batches. One batch per invocation: bpf_prog_test_run_opts is called with
 * repeat = <repeat> per call, again and again until the measured wall time of the calls is at least <min_s> seconds; retval is checked after every call.
 * Usage: p10b_testrun <object> <program> <frame_size> <repeat> <expect_accept 0|1> <cpu> <min_s>
 * The frame is a UDP/IPv4 frame of <frame_size> bytes to port 4040; 14 zero bytes are prepended because the socket-filter test run strips the first 14 bytes
 * (DEVIATIONS D3.4). Prints "frame_size,repeat,calls,total_reps,duration_mean_ns,wall_ns_per_rep,cpu_ns_per_rep,wall_s,cpu_s,retval" (duration_mean_ns = mean of the kernel's
 * integer average ns per repetition over the calls; wall: CLOCK_MONOTONIC_RAW around the calls; cpu: CLOCK_THREAD_CPUTIME_ID around the calls). Exit 3 if retval does not
 * match the expectation (0 for reject, non-zero for accept) in any call.
 * Needs root (CAP_BPF/CAP_PERFMON). Symbols used are recorded in CODE_NOTES.md (section Phase 10).
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static uint16_t csum16(const uint8_t *p, size_t n)
{
	uint32_t s = 0;

	for (size_t i = 0; i + 1 < n; i += 2)
		s += (uint32_t)p[i] << 8 | p[i + 1];
	while (s >> 16)
		s = (s & 0xffff) + (s >> 16);
	return (uint16_t)~s;
}

static void build_frame(uint8_t *buf, size_t size)
{
	memset(buf, 0, size + 14);
	uint8_t *f = buf + 14;                       /* the 14 prefix bytes are stripped by the test run */
	static const uint8_t dmac[6] = {0x02, 0, 0, 0, 0, 0x01}, smac[6] = {0x02, 0, 0, 0, 0, 0x02};
	memcpy(f, dmac, 6);
	memcpy(f + 6, smac, 6);
	f[12] = 0x08;
	f[13] = 0x00;
	uint8_t *ip = f + 14;
	size_t ip_len = size - 14;
	ip[0] = 0x45;
	ip[2] = ip_len >> 8;
	ip[3] = ip_len & 0xff;
	ip[8] = 64;
	ip[9] = 17;                                  /* UDP */
	ip[12] = 10; ip[15] = 2;                     /* 10.0.0.2 */
	ip[16] = 10; ip[19] = 1;                     /* 10.0.0.1 */
	uint16_t c = csum16(ip, 20);
	ip[10] = c >> 8;
	ip[11] = c & 0xff;
	uint8_t *udp = ip + 20;
	size_t udp_len = size - 34;
	udp[0] = 0x9c; udp[1] = 0x40;                /* source port 40000 */
	udp[2] = 0x0f; udp[3] = 0xc8;                /* destination port 4040 */
	udp[4] = udp_len >> 8;
	udp[5] = udp_len & 0xff;
	for (size_t i = 8; i < udp_len; i++)
		udp[i] = (uint8_t)i;
}

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
	if (argc != 8) {
		fprintf(stderr, "usage: %s <object> <program> <frame_size> <repeat> <expect_accept 0|1> <cpu> <min_s>\n", argv[0]);
		return 2;
	}
	size_t size = strtoul(argv[3], NULL, 10);
	int repeat = atoi(argv[4]), expect = atoi(argv[5]), cpu = atoi(argv[6]);
	double min_ns = atof(argv[7]) * 1e9;
	if (size < 64 || size > 1514 || repeat < 1 || min_ns <= 0) {
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
	struct bpf_object *obj = bpf_object__open_file(argv[1], NULL);
	if (!obj) {
		fprintf(stderr, "bpf_object__open_file(%s) failed: %s\n", argv[1], strerror(errno));
		return 1;
	}
	if (bpf_object__load(obj)) {
		fprintf(stderr, "bpf_object__load failed\n");
		return 1;
	}
	struct bpf_program *prog = bpf_object__find_program_by_name(obj, argv[2]);
	if (!prog) {
		fprintf(stderr, "program %s not found in %s\n", argv[2], argv[1]);
		return 1;
	}
	int fd = bpf_program__fd(prog);
	uint8_t buf[2048];
	build_frame(buf, size);
	LIBBPF_OPTS(bpf_test_run_opts, opts, .data_in = buf, .data_size_in = (__u32)(size + 14), .repeat = repeat);
	double w0 = ts_ns(CLOCK_MONOTONIC_RAW), c0 = ts_ns(CLOCK_THREAD_CPUTIME_ID), w = 0, c = 0, dsum = 0;
	unsigned long calls = 0;
	unsigned int retval = 0;
	int bad = 0;
	do {
		if (bpf_prog_test_run_opts(fd, &opts) != 0) {
			fprintf(stderr, "bpf_prog_test_run_opts failed: %s\n", strerror(errno));
			return 1;
		}
		calls++;
		dsum += (double)opts.duration;
		retval = opts.retval;
		if ((retval != 0) != expect)
			bad = 1;
		w = ts_ns(CLOCK_MONOTONIC_RAW) - w0;
		c = ts_ns(CLOCK_THREAD_CPUTIME_ID) - c0;
	} while (w < min_ns && !bad);
	double reps = (double)calls * (double)repeat;
	printf("%zu,%d,%lu,%.0f,%.4f,%.5f,%.5f,%.4f,%.4f,%u\n", size, repeat, calls, reps, dsum / (double)calls, w / reps, c / reps, w / 1e9, c / 1e9, retval);
	if (bad) {
		fprintf(stderr, "retval %u does not match the expectation (expect_accept=%d) in at least one call\n", retval, expect);
		return 3;
	}
	bpf_object__close(obj);
	return 0;
}
