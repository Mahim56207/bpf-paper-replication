/*
 * p10_drain.c - Phase 10 WP1(c): drain cost of an AF_PACKET queue. One batch per invocation.
 * Usage: p10_drain <path U|E|B> <frame_size> <N> <cpu>
 *   U  no BPF filter; after every receive a user-space filter checks ethertype, IP protocol and UDP destination port 4040
 *   E  accept-all eBPF socket filter (build/phase6_filters.o, program accept_all), no user-space filter
 *   B  port-4040 eBPF socket filter (build/phase3_kern.o, program phase3_filter), no user-space filter (every frame matches)
 * N UDP frames of <frame_size> bytes are sent from inside namespace p2ns (10.0.0.2) to 10.0.0.1:4040 and queue on an AF_PACKET socket (ETH_P_IP, bound to p1veth0,
 * receive buffer forced to 256 MB) that nothing reads; then PACKET_STATISTICS is read once (valid only with tp_drops == 0 and tp_packets == N), and the queue is
 * drained with recvfrom(MSG_DONTWAIT) until EAGAIN, timed with CLOCK_MONOTONIC_RAW.
 * Prints "path,frame_size,N,received,tp_packets,tp_drops,matched,elapsed_ns,ns_per_packet"; exit 3 if the batch is invalid.
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

static double now_ns(void)
{
	struct timespec t;

	clock_gettime(CLOCK_MONOTONIC_RAW, &t);
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
	if (argc != 5) {
		fprintf(stderr, "usage: %s <U|E|B> <frame_size> <N> <cpu>\n", argv[0]);
		return 2;
	}
	char path = argv[1][0];
	size_t size = strtoul(argv[2], NULL, 10);
	long n = strtol(argv[3], NULL, 10);
	int cpu = atoi(argv[4]);
	if ((path != 'U' && path != 'E' && path != 'B') || size < 64 || size > 1514 || n < 1) {
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
	for (long i = 0; i < n; i++) {
		if (send(us, pkt, payload, 0) < 0) {
			perror("send");
			return 1;
		}
	}
	usleep(300000);                                                  /* the queue has settled; nothing reads it */
	sl = sizeof(st);
	if (getsockopt(ps, SOL_PACKET, PACKET_STATISTICS, &st, &sl) != 0) {
		perror("PACKET_STATISTICS");
		return 1;
	}
	long matched = 0, received = 0;
	double t0 = now_ns();
	for (;;) {
		ssize_t r = recvfrom(ps, rb, 4096, MSG_DONTWAIT, NULL, NULL);
		if (r < 0) {
			if (errno == EAGAIN || errno == EWOULDBLOCK)
				break;
			perror("recvfrom");
			return 1;
		}
		received++;
		if (path == 'U')
			matched += user_filter(rb, r);
		else
			matched++;                                       /* an eBPF path delivers only what the filter accepted */
	}
	double t1 = now_ns();
	double ns = t1 - t0;
	printf("%c,%zu,%ld,%ld,%u,%u,%ld,%.0f,%.4f\n", path, size, n, received, st.tp_packets, st.tp_drops, matched, ns, ns / (double)(received ? received : 1));
	if (st.tp_drops != 0 || (long)st.tp_packets != n || received != n || matched != n) {
		fprintf(stderr, "invalid batch: tp_packets=%u tp_drops=%u received=%ld matched=%ld expected N=%ld\n", st.tp_packets, st.tp_drops, received, matched, n);
		return 3;
	}
	if (obj)
		bpf_object__close(obj);
	return 0;
}
