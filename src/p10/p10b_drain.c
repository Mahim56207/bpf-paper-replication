/*
 * p10b_drain.c - Phase 10 WP1b(c): drain cost of an AF_PACKET queue, long batches. One batch per invocation, made of repeated refill-and-drain cycles until the
 * accumulated wall time of the whole cycle loop is at least <min_s> seconds.
 * Usage: p10b_drain <path U|E|B> <frame_size> <N> <cpu> <min_s>
 *   U  no BPF filter; after every receive a user-space filter checks ethertype, IP protocol and UDP destination port 4040
 *   E  accept-all eBPF socket filter (build/phase6_filters.o, program accept_all), no user-space filter
 *   B  port-4040 eBPF socket filter (build/phase3_kern.o, program phase3_filter), no user-space filter (every frame matches)
 * One cycle: N UDP frames of <frame_size> bytes are sent from inside namespace p2ns (10.0.0.2) to 10.0.0.1:4040 and queue on an AF_PACKET socket (ETH_P_IP, bound to
 * p1veth0, receive buffer forced to 256 MB, read back and printed) that nothing reads; after 300 ms PACKET_STATISTICS is read (reading resets it) and the cycle is valid
 * only with tp_drops == 0 and tp_packets == N; then the queue is drained with recvfrom(MSG_DONTWAIT) until EAGAIN. Only the drain loop is timed: wall time with
 * CLOCK_MONOTONIC_RAW and thread CPU time with CLOCK_THREAD_CPUTIME_ID, both summed over the cycles. The batch ends after the first complete cycle at which the loop
 * has run for <min_s> seconds; it stops at once (exit 3) at the first invalid cycle.
 * Prints "path,frame_size,N,cycles,received,tp_packets,tp_drops,matched,rcvbuf,drain_wall_ns,drain_cpu_ns,ns_per_packet_wall,ns_per_packet_cpu,loop_wall_s".
 * Needs root (CAP_NET_RAW, CAP_NET_ADMIN, CAP_BPF) and the lab network (scripts/lab_up.sh). Symbols are recorded in CODE_NOTES.md (section Phase 10).
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/if_ether.h>
#include <linux/if_packet.h>
#include <net/if.h>
#include <netinet/in.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define NS_PATH "/var/run/netns/p2ns"
#define IFACE "p1veth0"
#define MATCH_PORT 4040

static double now_ns(clockid_t id)
{
	struct timespec t;

	if (clock_gettime(id, &t) != 0) {
		perror("clock_gettime");
		exit(1);
	}
	return (double)t.tv_sec * 1e9 + (double)t.tv_nsec;
}

static int big_rcvbuf(int fd, int bytes)
{
	return setsockopt(fd, SOL_SOCKET, SO_RCVBUFFORCE, &bytes, sizeof(bytes));
}

static int attach_ebpf(int sock, const char *obj_path, const char *prog_name, struct bpf_object **objp)
{
	struct bpf_object *obj = bpf_object__open_file(obj_path, NULL);

	if (!obj) {
		fprintf(stderr, "bpf_object__open_file(%s) failed\n", obj_path);
		return -1;
	}
	if (bpf_object__load(obj)) {
		fprintf(stderr, "bpf_object__load(%s) failed\n", obj_path);
		return -1;
	}
	struct bpf_program *prog = bpf_object__find_program_by_name(obj, prog_name);
	if (!prog) {
		fprintf(stderr, "program %s not found\n", prog_name);
		return -1;
	}
	int pfd = bpf_program__fd(prog);
	if (setsockopt(sock, SOL_SOCKET, SO_ATTACH_BPF, &pfd, sizeof(pfd)) != 0) {
		perror("setsockopt SO_ATTACH_BPF");
		return -1;
	}
	*objp = obj;
	return 0;
}

static int user_filter(const uint8_t *p, ssize_t n)      /* ethertype IPv4, protocol UDP, destination port 4040 */
{
	if (n < 14 + 20 + 8 || p[12] != 0x08 || p[13] != 0x00)
		return 0;
	size_t ihl = (size_t)(p[14] & 0x0f) * 4;
	if (ihl < 20 || (size_t)n < 14 + ihl + 8 || p[14 + 9] != 17)
		return 0;
	uint16_t dport = (uint16_t)(p[14 + ihl + 2] << 8 | p[14 + ihl + 3]);
	return dport == MATCH_PORT;
}

int main(int argc, char **argv)
{
	if (argc != 6) {
		fprintf(stderr, "usage: %s <U|E|B> <frame_size> <N> <cpu> <min_s>\n", argv[0]);
		return 2;
	}
	char path = argv[1][0];
	size_t size = strtoul(argv[2], NULL, 10);
	long n = strtol(argv[3], NULL, 10);
	int cpu = atoi(argv[4]);
	double min_ns = atof(argv[5]) * 1e9;
	if (min_ns <= 0 || (path != 'U' && path != 'E' && path != 'B') || size < 64 || size > 1514 || n < 1) {
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
	/* receiver of the UDP datagrams in the root namespace: stops ICMP port-unreachable replies, never read */
	int usink = socket(AF_INET, SOCK_DGRAM, 0);
	struct sockaddr_in rx = {.sin_family = AF_INET, .sin_port = htons(MATCH_PORT)};
	inet_pton(AF_INET, "10.0.0.1", &rx.sin_addr);
	if (usink < 0 || big_rcvbuf(usink, 256 << 20) != 0 || bind(usink, (struct sockaddr *)&rx, sizeof(rx)) != 0) {
		perror("udp sink");
		return 1;
	}
	/* the AF_PACKET socket */
	int ps = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_IP));
	if (ps < 0) {
		perror("socket AF_PACKET");
		return 1;
	}
	struct sockaddr_ll ll = {.sll_family = AF_PACKET, .sll_protocol = htons(ETH_P_IP), .sll_ifindex = (int)if_nametoindex(IFACE)};
	if (ll.sll_ifindex == 0 || big_rcvbuf(ps, 256 << 20) != 0 || bind(ps, (struct sockaddr *)&ll, sizeof(ll)) != 0) {
		perror("packet socket setup");
		return 1;
	}
	struct bpf_object *obj = NULL;
	if (path == 'E' && attach_ebpf(ps, "build/phase6_filters.o", "accept_all", &obj) != 0)
		return 1;
	if (path == 'B' && attach_ebpf(ps, "build/phase3_kern.o", "phase3_filter", &obj) != 0)
		return 1;
	/* sender: a UDP socket created inside namespace p2ns, thread switched back afterwards */
	int home = open("/proc/self/ns/net", O_RDONLY);
	int nsfd = open(NS_PATH, O_RDONLY);
	if (home < 0 || nsfd < 0 || setns(nsfd, CLONE_NEWNET) != 0) {
		perror("setns to p2ns");
		return 1;
	}
	int us = socket(AF_INET, SOCK_DGRAM, 0);
	struct sockaddr_in src = {.sin_family = AF_INET};
	inet_pton(AF_INET, "10.0.0.2", &src.sin_addr);
	if (us < 0 || bind(us, (struct sockaddr *)&src, sizeof(src)) != 0 || connect(us, (struct sockaddr *)&rx, sizeof(rx)) != 0) {
		perror("udp sender");
		return 1;
	}
	if (setns(home, CLONE_NEWNET) != 0) {
		perror("setns back");
		return 1;
	}
	size_t payload = size - 42;
	uint8_t *pkt = calloc(1, payload);
	uint8_t *rb = malloc(4096);
	if (!pkt || !rb)
		return 1;
	for (size_t i = 0; i < payload; i++)
		pkt[i] = (uint8_t)i;
	/* warm-up: one datagram resolves ARP and warms the path; drain and discard it, then reset the packet statistics */
	if (send(us, pkt, payload, 0) < 0) {
		perror("send warm-up");
		return 1;
	}
	usleep(200000);
	while (recvfrom(ps, rb, 4096, MSG_DONTWAIT, NULL, NULL) > 0)
		;
	struct tpacket_stats st;
	socklen_t sl = sizeof(st);
	getsockopt(ps, SOL_PACKET, PACKET_STATISTICS, &st, &sl);        /* reads and resets */
	int rcvbuf = 0;
	socklen_t rl = sizeof(rcvbuf);
	if (getsockopt(ps, SOL_SOCKET, SO_RCVBUF, &rcvbuf, &rl) != 0) {
		perror("getsockopt SO_RCVBUF");
		return 1;
	}
	long cycles = 0, received = 0, matched = 0;
	unsigned long tp_packets = 0, tp_drops = 0;
	double wall = 0, cpu_ns = 0;
	double l0 = now_ns(CLOCK_MONOTONIC_RAW);
	int invalid = 0;
	do {
		for (long i = 0; i < n; i++) {
			if (send(us, pkt, payload, 0) < 0) {
				perror("send");
				return 1;
			}
		}
		usleep(300000);                                          /* the queue has settled; nothing reads it */
		sl = sizeof(st);
		if (getsockopt(ps, SOL_PACKET, PACKET_STATISTICS, &st, &sl) != 0) {
			perror("PACKET_STATISTICS");
			return 1;
		}
		tp_packets += st.tp_packets;
		tp_drops += st.tp_drops;
		long rc = 0, mc = 0;
		double t0 = now_ns(CLOCK_MONOTONIC_RAW), c0 = now_ns(CLOCK_THREAD_CPUTIME_ID);
		for (;;) {
			ssize_t r = recvfrom(ps, rb, 4096, MSG_DONTWAIT, NULL, NULL);
			if (r < 0) {
				if (errno == EAGAIN || errno == EWOULDBLOCK)
					break;
				perror("recvfrom");
				return 1;
			}
			rc++;
			if (path == 'U')
				mc += user_filter(rb, r);
			else
				mc++;                                        /* an eBPF path delivers only what the filter accepted */
		}
		double t1 = now_ns(CLOCK_MONOTONIC_RAW), c1 = now_ns(CLOCK_THREAD_CPUTIME_ID);
		wall += t1 - t0;
		cpu_ns += c1 - c0;
		received += rc;
		matched += mc;
		cycles++;
		if (st.tp_drops != 0 || (long)st.tp_packets != n || rc != n || mc != n)
			invalid = 1;
	} while (now_ns(CLOCK_MONOTONIC_RAW) - l0 < min_ns && !invalid);
	double loop_s = (now_ns(CLOCK_MONOTONIC_RAW) - l0) / 1e9;
	printf("%c,%zu,%ld,%ld,%ld,%lu,%lu,%ld,%d,%.0f,%.0f,%.4f,%.4f,%.3f\n", path, size, n, cycles, received, tp_packets, tp_drops, matched, rcvbuf, wall, cpu_ns,
	       wall / (double)(received ? received : 1), cpu_ns / (double)(received ? received : 1), loop_s);
	if (invalid) {
		fprintf(stderr, "invalid batch at cycle %ld: tp_packets=%lu tp_drops=%lu received=%ld matched=%ld, per-cycle N=%ld\n", cycles, tp_packets, tp_drops, received, matched, n);
		return 3;
	}
	if (obj)
		bpf_object__close(obj);
	return 0;
}
