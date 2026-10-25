/* c1_oracle.c - libpcap side of Phase 6c (docs/phase6c_design.md, DEVIATIONS D6c.2).
 * Usage: c1_oracle <expression> <trace.pcap> <out_prefix>
 * Compiles <expression> with pcap_compile twice (optimizer on and off), writes the two programs as
 * text (<out_prefix>.opt.bpf, <out_prefix>.raw.bpf: first line = length, then "code jt jf k" per
 * instruction), and writes the accept/reject decision of libpcap's own evaluator for every frame
 * of the optimized program (<out_prefix>.dec) and of the unoptimized one (<out_prefix>.rawdec): one
 * '0'/'1' per frame, newline-terminated. The two programs can differ on truncated frames (amendment
 * A2 of docs/phase6c_design.md): the count of frames on which they differ is printed, not an error. */
#include <pcap/pcap.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include "c1_pcapfile.h"

static int dump_prog(const char *path, const struct bpf_program *p)
{
    FILE *f = fopen(path, "w");
    if (!f) { perror(path); return -1; }
    fprintf(f, "%u\n", p->bf_len);
    for (u_int i = 0; i < p->bf_len; i++)
        fprintf(f, "%u %u %u %u\n", p->bf_insns[i].code, p->bf_insns[i].jt, p->bf_insns[i].jf, p->bf_insns[i].k);
    fclose(f);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc != 4) { fprintf(stderr, "usage: %s <expression> <trace.pcap> <out_prefix>\n", argv[0]); return 1; }
    const char *expr = argv[1];
    struct c1_trace tr;
    if (c1_load_trace(argv[2], &tr)) return 1;

    pcap_t *pd = pcap_open_dead(DLT_EN10MB, 65535);
    if (!pd) { fprintf(stderr, "pcap_open_dead failed\n"); return 1; }
    struct bpf_program opt, raw;
    if (pcap_compile(pd, &opt, expr, 1, PCAP_NETMASK_UNKNOWN) < 0 ||
        pcap_compile(pd, &raw, expr, 0, PCAP_NETMASK_UNKNOWN) < 0) {
        fprintf(stderr, "pcap_compile: %s\n", pcap_geterr(pd));
        return 1;
    }
    char path[1024];
    snprintf(path, sizeof path, "%s.opt.bpf", argv[3]);
    if (dump_prog(path, &opt)) return 1;
    snprintf(path, sizeof path, "%s.raw.bpf", argv[3]);
    if (dump_prog(path, &raw)) return 1;

    snprintf(path, sizeof path, "%s.dec", argv[3]);
    FILE *df = fopen(path, "w");
    if (!df) { perror(path); return 1; }
    snprintf(path, sizeof path, "%s.rawdec", argv[3]);
    FILE *rf = fopen(path, "w");
    if (!rf) { perror(path); return 1; }
    size_t disagree = 0, accepts = 0;
    for (size_t i = 0; i < tr.nframes; i++) {
        struct pcap_pkthdr h = { {0, 0}, tr.len[i], tr.len[i] };
        int a = pcap_offline_filter(&opt, &h, tr.data[i]) != 0;
        int b = pcap_offline_filter(&raw, &h, tr.data[i]) != 0;
        if (a != b) disagree++;
        accepts += (size_t)a;
        fputc(a ? '1' : '0', df);
        fputc(b ? '1' : '0', rf);
    }
    fputc('\n', df);
    fputc('\n', rf);
    fclose(df);
    fclose(rf);
    printf("expr=\"%s\" frames=%zu accepts=%zu opt_len=%u raw_len=%u opt_vs_raw_disagree=%zu\n",
           expr, tr.nframes, accepts, opt.bf_len, raw.bf_len, disagree);
    pcap_freecode(&opt);
    pcap_freecode(&raw);
    pcap_close(pd);
    return 0;
}
