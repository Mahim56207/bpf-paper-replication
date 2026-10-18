/*
 * loader.c - Phase 4: load the Phase 3 socket filter, attach it to an AF_PACKET socket, and
 * print its two counters once per second.
 *
 * Usage: loader <iface> [object]      (needs root: CAP_BPF/CAP_NET_RAW; object defaults to
 *                                      build/phase3_kern.o)
 * Counter semantics (map p3_counters): slot 0 = dropped, slot 1 = matched, total = slot0 + slot1.
 * The two slots are read one after the other, so a line is not an atomic snapshot of both.
 * Stops on SIGINT/SIGTERM: prints a FINAL line, detaches the filter, closes the socket and object.
 *
 * Symbols used are recorded in CODE_NOTES.md with header file:line. The socket is only
 * attached to; packets the filter accepts queue on it unread (nothing reads them here).
 */
#include <arpa/inet.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <inttypes.h>
#include <linux/if_ether.h>
#include <linux/if_packet.h>
#include <net/if.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define DEFAULT_OBJ "build/phase3_kern.o"
#define PROG_NAME "phase3_filter"
#define MAP_NAME "p3_counters"
#define SLOT_DROPPED 0u
#define SLOT_MATCHED 1u
#define NS_PER_SEC UINT64_C(1000000000)

static volatile sig_atomic_t g_stop;

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

int main(int argc, char **argv)
{
	const char *obj_path = argc > 2 ? argv[2] : DEFAULT_OBJ;
	struct bpf_object *obj = NULL;
	struct bpf_program *prog;
	struct bpf_map *map;
	struct sockaddr_ll addr;
	struct sigaction sa;
	struct tpacket_stats st;
	socklen_t stlen = sizeof(st);
	uint64_t dropped = 0, matched = 0, prev_dropped = 0, prev_matched = 0;
	uint64_t start, prev_t, next_tick;
	unsigned int ifindex;
	int prog_fd, map_fd, sock = -1, err, rc = 1;

	if (argc < 2 || argc > 3) {
		fprintf(stderr, "usage: %s <iface> [object]\n", argv[0]);
		return 2;
	}
	ifindex = if_nametoindex(argv[1]);
	if (ifindex == 0) {
		fprintf(stderr, "if_nametoindex(%s): %s\n", argv[1], strerror(errno));
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
	prog = bpf_object__find_program_by_name(obj, PROG_NAME);
	map = bpf_object__find_map_by_name(obj, MAP_NAME);
	if (!prog || !map) {
		fprintf(stderr, "object %s: program '%s' %s, map '%s' %s\n", obj_path, PROG_NAME,
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

	/* No SA_RESTART: nanosleep must return EINTR so the loop sees g_stop. */
	memset(&sa, 0, sizeof(sa));
	sa.sa_handler = on_signal;
	sigaction(SIGINT, &sa, NULL);
	sigaction(SIGTERM, &sa, NULL);

	start = prev_t = now_ns();
	next_tick = start + NS_PER_SEC;
	printf("START iface=%s ifindex=%u object=%s prog_fd=%d map_fd=%d\n", argv[1], ifindex,
	       obj_path, prog_fd, map_fd);
	fflush(stdout);

	while (!g_stop) {
		struct timespec target = {.tv_sec = (time_t)(next_tick / NS_PER_SEC),
					  .tv_nsec = (long)(next_tick % NS_PER_SEC)};
		uint64_t t;
		double dt;

		if (clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &target, NULL) != 0 && g_stop)
			break;
		t = now_ns();
		next_tick += NS_PER_SEC;
		if (next_tick <= t) /* stalled: resync instead of bursting */
			next_tick = t + NS_PER_SEC;
		if (read_counters(map_fd, &dropped, &matched)) {
			perror("bpf_map_lookup_elem");
			goto out;
		}
		dt = (double)(t - prev_t) / (double)NS_PER_SEC;
		printf("t=%.3fs total=%" PRIu64 " matched=%" PRIu64 " dropped=%" PRIu64
		       " | pps total=%.0f matched=%.0f dropped=%.0f\n",
		       (double)(t - start) / (double)NS_PER_SEC, dropped + matched, matched, dropped,
		       (double)((dropped + matched) - (prev_dropped + prev_matched)) / dt,
		       (double)(matched - prev_matched) / dt, (double)(dropped - prev_dropped) / dt);
		fflush(stdout);
		prev_dropped = dropped;
		prev_matched = matched;
		prev_t = t;
	}

	/* Final reading before detaching. */
	if (read_counters(map_fd, &dropped, &matched) == 0) {
		printf("FINAL t=%.3fs total=%" PRIu64 " matched=%" PRIu64 " dropped=%" PRIu64 "\n",
		       (double)(now_ns() - start) / (double)NS_PER_SEC, dropped + matched, matched,
		       dropped);
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
