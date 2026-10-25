/* c1_pcapfile.h - minimal reader for the classic pcap files written by scripts/c1_make_trace.py
 * (little-endian magic 0xa1b2c3d4, DLT_EN10MB, caplen == len). Header-only, libc only. */
#ifndef C1_PCAPFILE_H
#define C1_PCAPFILE_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct c1_trace {
    uint8_t *buf;        /* whole file */
    size_t nframes;
    const uint8_t **data; /* frame pointers into buf */
    uint32_t *len;        /* frame lengths (caplen) */
};

static inline uint32_t c1_le32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static inline int c1_load_trace(const char *path, struct c1_trace *t)
{
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); return -1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz < 24) { fprintf(stderr, "%s: too short\n", path); fclose(f); return -1; }
    t->buf = malloc((size_t)sz);
    if (!t->buf || fread(t->buf, 1, (size_t)sz, f) != (size_t)sz) { fprintf(stderr, "%s: read failed\n", path); fclose(f); return -1; }
    fclose(f);
    if (c1_le32(t->buf) != 0xa1b2c3d4u || c1_le32(t->buf + 20) != 1u) {
        fprintf(stderr, "%s: not a little-endian DLT_EN10MB pcap\n", path);
        return -1;
    }
    size_t cap = 1024, n = 0, off = 24;
    t->data = malloc(cap * sizeof *t->data);
    t->len = malloc(cap * sizeof *t->len);
    while (off + 16 <= (size_t)sz) {
        uint32_t caplen = c1_le32(t->buf + off + 8), len = c1_le32(t->buf + off + 12);
        if (caplen != len || off + 16 + caplen > (size_t)sz) { fprintf(stderr, "%s: bad record %zu\n", path, n); return -1; }
        if (n == cap) { cap *= 2; t->data = realloc(t->data, cap * sizeof *t->data); t->len = realloc(t->len, cap * sizeof *t->len); }
        t->data[n] = t->buf + off + 16;
        t->len[n] = caplen;
        n++;
        off += 16 + caplen;
    }
    t->nframes = n;
    return 0;
}
#endif
