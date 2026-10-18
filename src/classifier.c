/*
 * classifier.c - loader for the classifier tap (src/phase6_classify.c), Phase 6 addendum A1.
 *
 * Usage: classifier <iface> [object]      (root; object defaults to build/phase6_classify.o)
 * Loads the object, attaches the `classify` socket filter to an AF_PACKET socket bound to <iface>, prints a START
 * line and then only sleeps (one wake-up per second, nothing else), so it adds no user-space work while a run is
 * measured. On SIGTERM/SIGINT it reads the six counters once, prints one CLS line, detaches and exits:
 *   CLS T=<n> F4040=<n> C4040=<n> F5050=<n> C5050=<n> X=<n> IDENTITY=<ok|BROKEN>
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
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define DEFAULT_OBJ "build/phase6_classify.o"
#define PROG_NAME "classify"
#define MAP_NAME "cls_counters"

static volatile sig_atomic_t g_stop;

static void on_signal(int sig)
{
	(void)sig;
	g_stop = 1;
}

int main(int argc, char **argv)
{
	const char *obj_path = argc > 2 ? argv[2] : DEFAULT_OBJ;
	struct bpf_object *obj = NULL;
	struct bpf_program *prog;
	struct bpf_map *map;
	struct sockaddr_ll addr;
	struct sigaction sa;
	struct timespec nap = {.tv_sec = 1, .tv_nsec = 0};
	uint64_t v[6];
	unsigned int ifindex, k;
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
	memset(&sa, 0, sizeof(sa));
	sa.sa_handler = on_signal;
	sigaction(SIGINT, &sa, NULL);
	sigaction(SIGTERM, &sa, NULL);
	printf("START classifier iface=%s ifindex=%u object=%s\n", argv[1], ifindex, obj_path);
	fflush(stdout);

	while (!g_stop)
		nanosleep(&nap, NULL);

	for (k = 0; k < 6; k++) {
		uint32_t key = k;

		if (bpf_map_lookup_elem(map_fd, &key, &v[k])) {
			perror("bpf_map_lookup_elem");
			goto out;
		}
	}
	printf("CLS T=%" PRIu64 " F4040=%" PRIu64 " C4040=%" PRIu64 " F5050=%" PRIu64 " C5050=%" PRIu64 " X=%" PRIu64
	       " IDENTITY=%s\n",
	       v[0], v[1], v[2], v[3], v[4], v[5], v[0] == v[1] + v[2] + v[3] + v[4] + v[5] ? "ok" : "BROKEN");
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
