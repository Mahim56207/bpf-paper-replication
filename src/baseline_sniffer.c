/*
 * baseline_sniffer.c - Phase 2 user-space baseline.
 *
 * The "NIT-style" design: every packet on the interface is copied in full to a
 * user buffer by recvfrom(), and only then parsed (eth -> ip -> tcp/udp) in user
 * memory. Nothing is filtered in the kernel. Match rule: TCP or UDP port 4040 in
 * either direction.
 *
 * Usage: baseline_sniffer <iface>      (needs CAP_NET_RAW, i.e. run with sudo)
 * Stops on SIGINT/SIGTERM and prints a FINAL line.
 *
 * Symbols used are recorded in CODE_NOTES.md with header file:line.
 */
#include <arpa/inet.h>
#include <errno.h>
#include <inttypes.h>
#include <linux/if_ether.h>
#include <linux/if_packet.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <net/if.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define MATCH_PORT 4040
/* IPv4 fragment-offset mask (RFC 791). Not in linux/ip.h, see CODE_NOTES.md. */
#define IP_FRAG_OFFSET_MASK 0x1fff
/* Larger than any IPv4 packet (65535) plus the Ethernet header, so recvfrom never truncates. */
#define BUF_SIZE (128 * 1024)
/* Look at the clock once per this many packets (power of two), and on every idle timeout. */
#define CLOCK_CHECK_MASK 1023u

static volatile sig_atomic_t g_stop;

struct counters {
    uint64_t total_packets;
    uint64_t matched_packets;
    uint64_t total_bytes;
    uint64_t truncated;
};

static void on_signal(int sig)
{
    (void)sig;
    g_stop = 1;
}

static uint64_t now_ns(void)
{
    struct timespec ts;

    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

/*
 * Returns 1 if the packet is IPv4 TCP/UDP with source or destination port ==
 * MATCH_PORT. Every layer is length-checked against caplen (the bytes actually
 * in our buffer); IP total length is never used. Headers are memcpy'd out so no
 * unaligned or aliased access happens (the IP header sits at offset 14).
 */
static int match_packet(const uint8_t *pkt, size_t caplen)
{
    const uint16_t port_be = htons(MATCH_PORT);
    struct ethhdr eth;
    struct iphdr ip;
    size_t off = 0, ihl_bytes, avail;

    if (caplen < ETH_HLEN)
        return 0;
    memcpy(&eth, pkt, sizeof(eth));
    if (eth.h_proto != htons(ETH_P_IP))
        return 0;
    off += ETH_HLEN;

    if (caplen - off < sizeof(ip))
        return 0;
    memcpy(&ip, pkt + off, sizeof(ip));
    if (ip.version != 4)
        return 0;
    ihl_bytes = (size_t)ip.ihl * 4;
    if (ihl_bytes < sizeof(ip) || ihl_bytes > caplen - off)
        return 0;
    if (ip.frag_off & htons(IP_FRAG_OFFSET_MASK))
        return 0; /* non-first fragment: no L4 header here */
    off += ihl_bytes;
    avail = caplen - off;

    if (ip.protocol == IPPROTO_TCP) {
        struct tcphdr tcp;

        if (avail < sizeof(tcp))
            return 0;
        memcpy(&tcp, pkt + off, sizeof(tcp));
        return tcp.source == port_be || tcp.dest == port_be;
    }
    if (ip.protocol == IPPROTO_UDP) {
        struct udphdr udp;

        if (avail < sizeof(udp))
            return 0;
        memcpy(&udp, pkt + off, sizeof(udp));
        return udp.source == port_be || udp.dest == port_be;
    }
    return 0;
}

static void report(const char *tag, uint64_t elapsed_ns, const struct counters *c)
{
    printf("%s t=%" PRIu64 ".%03" PRIu64 "s total_packets=%" PRIu64 " matched_packets=%" PRIu64
           " total_bytes=%" PRIu64 " truncated=%" PRIu64 "\n",
           tag, elapsed_ns / UINT64_C(1000000000), (elapsed_ns / UINT64_C(1000000)) % 1000, c->total_packets,
           c->matched_packets, c->total_bytes, c->truncated);
    fflush(stdout); /* stdout is usually a pipe (| tee): without this nothing appears until exit */
}

int main(int argc, char **argv)
{
    static uint8_t buf[BUF_SIZE];
    struct counters c = {0};
    struct sockaddr_ll addr;
    struct sigaction sa;
    struct timeval tmo = {.tv_sec = 0, .tv_usec = 200000};
    struct tpacket_stats st;
    socklen_t stlen = sizeof(st);
    unsigned int ifindex;
    uint64_t start, next_report;
    int fd;

    if (argc != 2) {
        fprintf(stderr, "usage: %s <iface>\n", argv[0]);
        return 2;
    }
    ifindex = if_nametoindex(argv[1]);
    if (ifindex == 0) {
        fprintf(stderr, "if_nametoindex(%s): %s\n", argv[1], strerror(errno));
        return 1;
    }

    fd = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (fd < 0) {
        perror("socket(AF_PACKET)");
        return 1;
    }
    memset(&addr, 0, sizeof(addr));
    addr.sll_family = AF_PACKET;
    addr.sll_protocol = htons(ETH_P_ALL);
    addr.sll_ifindex = (int)ifindex;
    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        return 1;
    }
    /* Idle wake-up so the once-per-second report still prints with no traffic. */
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tmo, sizeof(tmo)) < 0) {
        perror("setsockopt(SO_RCVTIMEO)");
        return 1;
    }

    /* No SA_RESTART: recvfrom must return EINTR so the loop sees g_stop. */
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = on_signal;
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);

    start = now_ns();
    next_report = start + UINT64_C(1000000000);
    printf("START iface=%s ifindex=%u match_port=%d buf_size=%d\n", argv[1], ifindex, MATCH_PORT,
           BUF_SIZE);
    fflush(stdout);

    while (!g_stop) {
        int check_clock = 0;
        /* MSG_TRUNC: return the real packet length even if it exceeded the buffer. */
        ssize_t n = recvfrom(fd, buf, sizeof(buf), MSG_TRUNC, NULL, NULL);

        if (n < 0) {
            if (errno != EINTR && errno != EAGAIN && errno != EWOULDBLOCK) {
                perror("recvfrom");
                break;
            }
            check_clock = 1; /* idle timeout or signal */
        } else {
            size_t len = (size_t)n;
            size_t caplen = len < sizeof(buf) ? len : sizeof(buf);

            c.total_packets++;
            c.total_bytes += len;
            if (len > sizeof(buf))
                c.truncated++;
            if (match_packet(buf, caplen))
                c.matched_packets++;
            check_clock = (c.total_packets & CLOCK_CHECK_MASK) == 0;
        }

        if (check_clock) {
            uint64_t now = now_ns();

            if (now >= next_report) {
                report("STAT", now - start, &c);
                next_report += UINT64_C(1000000000);
                if (next_report <= now) /* we were stalled: resync instead of bursting */
                    next_report = now + UINT64_C(1000000000);
            }
        }
    }

    report("FINAL", now_ns() - start, &c);
    if (getsockopt(fd, SOL_PACKET, PACKET_STATISTICS, &st, &stlen) == 0)
        printf("FINAL_KERNEL kernel_packets=%u kernel_drops=%u\n", st.tp_packets, st.tp_drops);
    else
        perror("getsockopt(PACKET_STATISTICS)");
    fflush(stdout);
    close(fd);
    return 0;
}
