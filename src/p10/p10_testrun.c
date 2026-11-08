/*
 * p10_testrun.c - Phase 10 WP1(b): in-kernel filter cost by BPF_PROG_TEST_RUN. One batch per invocation.
 * Usage: p10_testrun <object> <program> <frame_size> <repeat> <expect_accept 0|1> <cpu>
 * The frame is a UDP/IPv4 frame of <frame_size> bytes to port 4040; 14 zero bytes are prepended because the socket-filter test run strips the first 14 bytes
 * (DEVIATIONS D3.4). Prints "frame_size,repeat,duration_ns,retval". Exit 3 if retval does not match the expectation (0 for reject, non-zero for accept).
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

int main(int argc, char **argv)
{
	if (argc != 7) {
		fprintf(stderr, "usage: %s <object> <program> <frame_size> <repeat> <expect_accept 0|1> <cpu>\n", argv[0]);
		return 2;
	}
	size_t size = strtoul(argv[3], NULL, 10);
	int repeat = atoi(argv[4]), expect = atoi(argv[5]), cpu = atoi(argv[6]);
	if (size < 64 || size > 1514) {
		fprintf(stderr, "frame size out of range\n");
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
	if (bpf_prog_test_run_opts(fd, &opts) != 0) {
		fprintf(stderr, "bpf_prog_test_run_opts failed: %s\n", strerror(errno));
		return 1;
	}
	printf("%zu,%d,%u,%u\n", size, repeat, opts.duration, opts.retval);
	int accepted = opts.retval != 0;
	if (accepted != expect) {
		fprintf(stderr, "retval %u does not match the expectation (expect_accept=%d)\n", opts.retval, expect);
		return 3;
	}
	bpf_object__close(obj);
	return 0;
}
