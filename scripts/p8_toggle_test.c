/* Phase 8.0 D8.3: minimal program to test callgrind --toggle-collect on this platform, independent of the
 * project's interpreters. f_leaf and f_frame are the "evaluators" (noinline); g is heavy work that main does
 * between the calls and that must NOT be collected. Usage: p8_toggle_test <mode 0|1> <calls>.
 * mode 0 calls f_leaf (no stack frame needed), mode 1 calls f_frame (a local array indexed by data, like
 * the stack machine's stk[]). */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static uint8_t buf[256];
volatile uint64_t sink;

__attribute__((noinline)) uint64_t f_leaf(const uint8_t *p, int n)
{
    uint64_t a = 0;
    for (int i = 0; i < n; i++) a += p[i] * (uint64_t)(i + 1);
    return a;
}

__attribute__((noinline)) uint64_t f_frame(const uint8_t *p, int n)
{
    uint16_t stk[32];
    int sp = 0;
    for (int i = 0; i < n; i++) {
        stk[sp & 31] = (uint16_t)(p[i] + sp);
        sp = (sp + (p[i] & 3)) & 15;
    }
    return stk[sp & 31];
}

__attribute__((noinline)) uint64_t g(const uint8_t *p, int n)
{
    uint64_t a = 1;
    for (int i = 0; i < n; i++) a = a * 31 + p[i % 256];
    return a;
}

int main(int argc, char **argv)
{
    if (argc != 3) return 1;
    int mode = atoi(argv[1]), calls = atoi(argv[2]);
    for (int i = 0; i < 256; i++) buf[i] = (uint8_t)(i * 7 + 3);
    for (int c = 0; c < calls; c++) {
        sink += mode ? f_frame(buf, 64) : f_leaf(buf, 64);
        sink += g(buf, 1000); /* heavy, outside the evaluator: about 5000+ Ir per iteration */
    }
    printf("calls=%d sink=%llu\n", calls, (unsigned long long)sink);
    return 0;
}
