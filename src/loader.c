/*
 * loader.c - load a socket filter, attach it to an AF_PACKET socket, and print its two counters
 * once per second.
 *
 * Usage: loader [-d] [-p prog] <iface> [object]
 *   -d        drain mode: read and discard every packet the filter accepts, so the socket queue
 *             never overflows (Phase 6 "full path" configurations). Default: aggregate only,
 *             nothing reads the socket (Phase 4 behaviour).
 *   -p prog   program name inside the object (default phase3_filter)
 *   object    default build/phase3_kern.o
 * Needs root: CAP_BPF/CAP_NET_RAW.
 *
 * Counter semantics (map p3_counters): slot 0 = dropped, slot 1 = matched, total = slot0 + slot1.
 * The two slots are read one after the other, so a line is not an atomic snapshot of both.
 * Stops on SIGINT/SIGTERM: prints a FINAL line, detaches the filter, closes the socket and object.
 *
 * Symbols used are recorded in CODE_NOTES.md with header file:line.
 */
#include <arpa/inet.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <inttypes.h>
#include <linux/if_ether.h>
#include <linux/if_packet.h>
#include <net/if.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define DEFAULT_OBJ "build/phase3_kern.o"
#define DEFAULT_PROG "phase3_filter"
#define MAP_NAME "p3_counters"
#define SLOT_DROPPED 0u
#define SLOT_MATCHED 1u
#define NS_PER_SEC UINT64_C(1000000000)
/* Larger than any IPv4 packet plus the Ethernet header, so a drained packet is copied whole
 * (same copy size as the baseline sniffer). */
#define RX_BUF (128 * 1024)
/* Packets read per drain call, so the once-per-second bookkeeping is never starved. */
#define DRAIN_BATCH 256

static volatile sig_atomic_t g_stop;
static uint8_t g_rxbuf[RX_BUF];

static void on_signal(int sig)
{
	(void)sig;
	g_stop = 1;
}

static uint64_t now_ns(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * NS_PER_SEC + (uint64_t)ts.tv_nsec;
}

static int read_counters(int map_fd, uint64_t *dropped, uint64_t *matched)
{
	uint32_t k_dropped = SLOT_DROPPED, k_matched = SLOT_MATCHED;

	if (bpf_map_lookup_elem(map_fd, &k_dropped, dropped) ||
	    bpf_map_lookup_elem(map_fd, &k_matched, matched))
		return -1;
	return 0;
}

/* Read and discard up to DRAIN_BATCH queued packets; returns the number read. MSG_TRUNC makes
 * recvfrom return the real packet length. */
static int drain_socket(int sock, uint64_t *pkts, uint64_t *bytes)
{
	int i;

	for (i = 0; i < DRAIN_BATCH; i++) {
		ssize_t n = recvfrom(sock, g_rxbuf, sizeof(g_rxbuf), MSG_DONTWAIT | MSG_TRUNC, NULL,
				     NULL);

		if (n < 0)
			break; /* EAGAIN (queue empty), EINTR, or an error the poll loop will meet again */
		(*pkts)++;
		*bytes += (uint64_t)n;
	}
	return i;
}

int main(int argc, char **argv)
{
	const char *prog_name = DEFAULT_PROG, *iface = NULL, *obj_path = DEFAULT_OBJ;
	int drain = 0, positional = 0, a;
	struct bpf_object *obj = NULL;
	struct bpf_program *prog;
	struct bpf_map *map;
	struct sockaddr_ll addr;
	struct sigaction sa;
	struct tpacket_stats st;
	socklen_t stlen = sizeof(st);
	uint64_t dropped = 0, matched = 0, prev_dropped = 0, prev_matched = 0;
	uint64_t rx_pkts = 0, rx_bytes = 0, prev_rx_pkts = 0, prev_rx_bytes = 0;
	uint64_t start, prev_t, next_tick;
	unsigned int ifindex;
	int prog_fd, map_fd, sock = -1, err, rc = 1;

	for (a = 1; a < argc; a++) {
		if (!strcmp(argv[a], "-d")) {
			drain = 1;
		} else if (!strcmp(argv[a], "-p") && a + 1 < argc) {
			prog_name = argv[++a];
		} else if (argv[a][0] == '-') {
			positional = -1;
			break;
		} else if (positional == 0) {
			iface = argv[a];
			positional = 1;
		} else if (positional == 1) {
			obj_path = argv[a];
			positional = 2;
		} else {
			positional = -1;
			break;
		}
	}
	if (positional < 1) {
		fprintf(stderr, "usage: %s [-d] [-p prog] <iface> [object]\n", argv[0]);
		return 2;
	}
	ifindex = if_nametoindex(iface);
	if (ifindex == 0) {
		fprintf(stderr, "if_nametoindex(%s): %s\n", iface, strerror(errno));
		return 1;
	}

	obj = bpf_object__open_file(obj_path, NULL);
	if (!obj) {
		fprintf(stderr, "bpf_object__open_file(%s): %s\n", obj_path, strerror(errno));
		return 1;
	}
	err = bpf_object__load(obj);
	if (err) {
		fprintf(stderr, "bpf_object__load: %s\n", strerror(-err));
		goto out;
	}
	prog = bpf_object__find_program_by_name(obj, prog_name);
	map = bpf_object__find_map_by_name(obj, MAP_NAME);
	if (!prog || !map) {
		fprintf(stderr, "object %s: program '%s' %s, map '%s' %s\n", obj_path, prog_name,
			prog ? "found" : "NOT found", MAP_NAME, map ? "found" : "NOT found");
		goto out;
	}
	prog_fd = bpf_program__fd(prog);
	map_fd = bpf_map__fd(map);
	if (prog_fd < 0 || map_fd < 0) {
		fprintf(stderr, "bad fd: prog_fd=%d map_fd=%d\n", prog_fd, map_fd);
		goto out;
	}

	sock = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
	if (sock < 0) {
		perror("socket(AF_PACKET)");
		goto out;
	}
	memset(&addr, 0, sizeof(addr));
	addr.sll_family = AF_PACKET;
	addr.sll_protocol = htons(ETH_P_ALL);
	addr.sll_ifindex = (int)ifindex;
	if (bind(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
		perror("bind");
		goto out;
	}
	if (setsockopt(sock, SOL_SOCKET, SO_ATTACH_BPF, &prog_fd, sizeof(prog_fd)) < 0) {
		perror("setsockopt(SO_ATTACH_BPF)");
		goto out;
	}

	/* No SA_RESTART: sleeping/polling must return EINTR so the loop sees g_stop. */
	memset(&sa, 0, sizeof(sa));
	sa.sa_handler = on_signal;
	sigaction(SIGINT, &sa, NULL);
	sigaction(SIGTERM, &sa, NULL);

	start = prev_t = now_ns();
	next_tick = start + NS_PER_SEC;
	printf("START iface=%s ifindex=%u object=%s prog=%s prog_fd=%d map_fd=%d drain=%d\n", iface,
	       ifindex, obj_path, prog_name, prog_fd, map_fd, drain);
	fflush(stdout);

	while (!g_stop) {
		uint64_t t = now_ns();

		if (t >= next_tick) {
			double dt = (double)(t - prev_t) / (double)NS_PER_SEC;

			next_tick += NS_PER_SEC;
			if (next_tick <= t) /* stalled: resync instead of bursting */
				next_tick = t + NS_PER_SEC;
			if (read_counters(map_fd, &dropped, &matched)) {
				perror("bpf_map_lookup_elem");
				goto out;
			}
			printf("t=%.3fs total=%" PRIu64 " matched=%" PRIu64 " dropped=%" PRIu64
			       " | pps total=%.0f matched=%.0f dropped=%.0f",
			       (double)(t - start) / (double)NS_PER_SEC, dropped + matched, matched,
			       dropped, (double)((dropped + matched) - (prev_dropped + prev_matched)) / dt,
			       (double)(matched - prev_matched) / dt,
			       (double)(dropped - prev_dropped) / dt);
			if (drain)
				printf(" | rx_packets=%" PRIu64 " rx_bytes=%" PRIu64 " rx_pps=%.0f", rx_pkts,
				       rx_bytes, (double)(rx_pkts - prev_rx_pkts) / dt);
			printf("\n");
			fflush(stdout);
			prev_dropped = dropped;
			prev_matched = matched;
			prev_rx_pkts = rx_pkts;
			prev_rx_bytes = rx_bytes;
			prev_t = t;
			continue;
		}

		if (drain) {
			struct pollfd pfd = {.fd = sock, .events = POLLIN, .revents = 0};
			int ms = (int)((next_tick - t + UINT64_C(999999)) / UINT64_C(1000000));

			if (poll(&pfd, 1, ms) > 0 && (pfd.revents & POLLIN))
				drain_socket(sock, &rx_pkts, &rx_bytes);
		} else {
			struct timespec target = {.tv_sec = (time_t)(next_tick / NS_PER_SEC),
						  .tv_nsec = (long)(next_tick % NS_PER_SEC)};

			clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &target, NULL);
		}
	}
	(void)prev_rx_bytes;

	/* Drain whatever is still queued, then read the counters one last time before detaching. */
	if (drain)
		while (drain_socket(sock, &rx_pkts, &rx_bytes) == DRAIN_BATCH)
			;
	if (read_counters(map_fd, &dropped, &matched) == 0) {
		printf("FINAL t=%.3fs total=%" PRIu64 " matched=%" PRIu64 " dropped=%" PRIu64,
		       (double)(now_ns() - start) / (double)NS_PER_SEC, dropped + matched, matched,
		       dropped);
		if (drain)
			printf(" delivered_packets=%" PRIu64 " delivered_bytes=%" PRIu64, rx_pkts,
			       rx_bytes);
		printf("\n");
	} else {
		perror("bpf_map_lookup_elem(final)");
	}
	if (getsockopt(sock, SOL_PACKET, PACKET_STATISTICS, &st, &stlen) == 0)
		printf("FINAL_SOCKET kernel_packets=%u kernel_drops=%u\n", st.tp_packets, st.tp_drops);
	fflush(stdout);
	rc = 0;

out:
	if (sock >= 0) {
		int unused = 0;

		if (setsockopt(sock, SOL_SOCKET, SO_DETACH_BPF, &unused, sizeof(unused)) < 0)
			perror("setsockopt(SO_DETACH_BPF)");
		close(sock);
	}
	bpf_object__close(obj);
	return rc;
}
