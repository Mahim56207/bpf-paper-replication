/* c1_interp.c - the two filter machines of Phase 6c (docs/phase6c_design.md section 3).
 *   c1_eval_bpf: register machine, paper section 3.3 (accumulator, index register, scratch store, pc,
 *                one switch over the opcode). Opcodes: paper Table 1 plus what libpcap emits.
 *   c1_eval_sm:  stack machine, paper section 3.1 (16-bit operand stack kept in memory).
 * Two builds from this one file:
 *   -DC1_COUNT : every executed filter instruction increments *icount (metric M1), per-frame CSV.
 *   (default)  : no counting code in the evaluators, so callgrind's Ir inside the evaluator is metric M2
 *                without counter instructions mixed in.
 * Usage: c1_interp --machine bpf|sm --prog FILE --pcap FILE [--first N] [--count M] [--csv FILE]
 * Prints: machine=.. frames=.. accepts=.. dechash=.. (FNV-1a of the decision bytes). */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <pcap/bpf.h> /* struct bpf_insn and the BPF_* opcode macros only; no libpcap function is called */
#include "c1_pcapfile.h"

#ifdef C1_COUNT
#define TICK() (++*icount)
#else
#define TICK() ((void)0)
#endif

static void die(const char *m)
{
    fprintf(stderr, "c1_interp: %s\n", m);
    exit(3);
}

/* ---- register machine --------------------------------------------------------------------- */
static inline uint32_t be16(const uint8_t *p) { return ((uint32_t)p[0] << 8) | p[1]; }
static inline uint32_t be32(const uint8_t *p) { return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3]; }

#define CHK(off, sz) do { if ((uint32_t)(sz) > len || (uint32_t)(off) > len - (uint32_t)(sz)) return 0; } while (0)

__attribute__((noinline)) uint32_t c1_eval_bpf(const struct bpf_insn *pc, const uint8_t *p, uint32_t len, uint64_t *icount)
{
    uint32_t A = 0, X = 0, k;
    uint32_t mem[BPF_MEMWORDS];
    (void)icount;
    for (;;) {
        const struct bpf_insn *i = pc++;
        TICK();
        switch (i->code) {
        case BPF_RET | BPF_K: return i->k;
        case BPF_RET | BPF_A: return A;
        case BPF_LD | BPF_W | BPF_ABS: k = i->k; CHK(k, 4); A = be32(p + k); break;
        case BPF_LD | BPF_H | BPF_ABS: k = i->k; CHK(k, 2); A = be16(p + k); break;
        case BPF_LD | BPF_B | BPF_ABS: k = i->k; CHK(k, 1); A = p[k]; break;
        case BPF_LD | BPF_W | BPF_IND: k = X + i->k; if (k < X) return 0; CHK(k, 4); A = be32(p + k); break;
        case BPF_LD | BPF_H | BPF_IND: k = X + i->k; if (k < X) return 0; CHK(k, 2); A = be16(p + k); break;
        case BPF_LD | BPF_B | BPF_IND: k = X + i->k; if (k < X) return 0; CHK(k, 1); A = p[k]; break;
        case BPF_LD | BPF_IMM: A = i->k; break;
        case BPF_LD | BPF_LEN: A = len; break;
        case BPF_LD | BPF_MEM: A = mem[i->k]; break;
        case BPF_LDX | BPF_IMM: X = i->k; break;
        case BPF_LDX | BPF_LEN: X = len; break;
        case BPF_LDX | BPF_MEM: X = mem[i->k]; break;
        case BPF_LDX | BPF_B | BPF_MSH: k = i->k; CHK(k, 1); X = (uint32_t)(p[k] & 0xf) << 2; break;
        case BPF_ST: mem[i->k] = A; break;
        case BPF_STX: mem[i->k] = X; break;
        case BPF_JMP | BPF_JA: pc += i->k; break;
        case BPF_JMP | BPF_JGT | BPF_K: pc += (A > i->k) ? i->jt : i->jf; break;
        case BPF_JMP | BPF_JGE | BPF_K: pc += (A >= i->k) ? i->jt : i->jf; break;
        case BPF_JMP | BPF_JEQ | BPF_K: pc += (A == i->k) ? i->jt : i->jf; break;
        case BPF_JMP | BPF_JSET | BPF_K: pc += (A & i->k) ? i->jt : i->jf; break;
        case BPF_JMP | BPF_JGT | BPF_X: pc += (A > X) ? i->jt : i->jf; break;
        case BPF_JMP | BPF_JGE | BPF_X: pc += (A >= X) ? i->jt : i->jf; break;
        case BPF_JMP | BPF_JEQ | BPF_X: pc += (A == X) ? i->jt : i->jf; break;
        case BPF_JMP | BPF_JSET | BPF_X: pc += (A & X) ? i->jt : i->jf; break;
        case BPF_ALU | BPF_ADD | BPF_K: A += i->k; break;
        case BPF_ALU | BPF_SUB | BPF_K: A -= i->k; break;
        case BPF_ALU | BPF_MUL | BPF_K: A *= i->k; break;
        case BPF_ALU | BPF_DIV | BPF_K: if (i->k == 0) return 0; A /= i->k; break;
        case BPF_ALU | BPF_MOD | BPF_K: if (i->k == 0) return 0; A %= i->k; break;
        case BPF_ALU | BPF_AND | BPF_K: A &= i->k; break;
        case BPF_ALU | BPF_OR | BPF_K: A |= i->k; break;
        case BPF_ALU | BPF_XOR | BPF_K: A ^= i->k; break;
        case BPF_ALU | BPF_LSH | BPF_K: A <<= i->k; break;
        case BPF_ALU | BPF_RSH | BPF_K: A >>= i->k; break;
        case BPF_ALU | BPF_ADD | BPF_X: A += X; break;
        case BPF_ALU | BPF_SUB | BPF_X: A -= X; break;
        case BPF_ALU | BPF_MUL | BPF_X: A *= X; break;
        case BPF_ALU | BPF_DIV | BPF_X: if (X == 0) return 0; A /= X; break;
        case BPF_ALU | BPF_MOD | BPF_X: if (X == 0) return 0; A %= X; break;
        case BPF_ALU | BPF_AND | BPF_X: A &= X; break;
        case BPF_ALU | BPF_OR | BPF_X: A |= X; break;
        case BPF_ALU | BPF_XOR | BPF_X: A ^= X; break;
        case BPF_ALU | BPF_LSH | BPF_X: A <<= X; break;
        case BPF_ALU | BPF_RSH | BPF_X: A >>= X; break;
        case BPF_ALU | BPF_NEG: A = -A; break;
        case BPF_MISC | BPF_TAX: X = A; break;
        case BPF_MISC | BPF_TXA: A = X; break;
        default: die("unsupported BPF opcode"); /* not reached for the programs under test */
        }
    }
}

/* ---- stack machine ------------------------------------------------------------------------- */
enum sm_op { SM_PUSHLIT, SM_PUSHWORD, SM_PUSHIND, SM_PUSHIPIND, SM_EQ, SM_NEQ, SM_AND, SM_OR, SM_XOR,
             SM_ADD, SM_LSH, SM_RSH, SM_CAND, SM_COR };
struct sm_insn { uint8_t op; uint16_t arg; };
#define SM_MAXDEPTH 32

static inline uint16_t word_at(const uint8_t *p, uint32_t len, uint32_t off)
{
    if (off > len || len - off < 2) return 0; /* a word not wholly inside the packet reads as 0 (design 3.2) */
    return (uint16_t)((p[off] << 8) | p[off + 1]);
}

__attribute__((noinline)) uint32_t c1_eval_sm(const struct sm_insn *prog, uint32_t n, const uint8_t *p, uint32_t len, uint64_t *icount)
{
    uint16_t stk[SM_MAXDEPTH];
    int sp = 0;
    const struct sm_insn *pc = prog, *end = prog + n;
    (void)icount;
    while (pc < end) {
        const struct sm_insn *i = pc++;
        TICK();
        switch (i->op) {
        case SM_PUSHLIT: stk[sp++] = i->arg; break;
        case SM_PUSHWORD: stk[sp++] = word_at(p, len, i->arg); break;
        case SM_PUSHIND: stk[sp - 1] = word_at(p, len, stk[sp - 1]); break;
        case SM_PUSHIPIND: {
            uint32_t b = len > 14 ? p[14] : 0;
            stk[sp++] = word_at(p, len, 14 + 4 * (b & 0xf) + i->arg);
            break;
        }
        case SM_EQ: sp--; stk[sp - 1] = (uint16_t)(stk[sp - 1] == stk[sp]); break;
        case SM_NEQ: sp--; stk[sp - 1] = (uint16_t)(stk[sp - 1] != stk[sp]); break;
        case SM_AND: sp--; stk[sp - 1] = (uint16_t)(stk[sp - 1] & stk[sp]); break;
        case SM_OR: sp--; stk[sp - 1] = (uint16_t)(stk[sp - 1] | stk[sp]); break;
        case SM_XOR: sp--; stk[sp - 1] = (uint16_t)(stk[sp - 1] ^ stk[sp]); break;
        case SM_ADD: sp--; stk[sp - 1] = (uint16_t)(stk[sp - 1] + stk[sp]); break;
        case SM_LSH: sp--; stk[sp - 1] = (uint16_t)(stk[sp - 1] << (stk[sp] & 15)); break;
        case SM_RSH: sp--; stk[sp - 1] = (uint16_t)(stk[sp - 1] >> (stk[sp] & 15)); break;
        case SM_CAND: if (stk[--sp] == 0) return 0; break;
        case SM_COR: if (stk[--sp] != 0) return 1; break;
        default: die("unsupported stack-machine opcode");
        }
    }
    return sp == 0 || stk[sp - 1] != 0; /* paper.txt L295-296 */
}

/* ---- program loading ----------------------------------------------------------------------- */
static struct bpf_insn *load_bpf(const char *path, uint32_t *n)
{
    FILE *f = fopen(path, "r");
    if (!f) { perror(path); exit(1); }
    unsigned cnt;
    if (fscanf(f, "%u", &cnt) != 1 || cnt == 0) die("bad bpf program header");
    struct bpf_insn *prog = calloc(cnt, sizeof *prog);
    for (unsigned j = 0; j < cnt; j++) {
        unsigned c, jt, jf, k;
        if (fscanf(f, "%u %u %u %u", &c, &jt, &jf, &k) != 4) die("bad bpf instruction line");
        prog[j].code = (u_short)c; prog[j].jt = (u_char)jt; prog[j].jf = (u_char)jf; prog[j].k = k;
    }
    fclose(f);
    *n = cnt;
    return prog;
}

static struct sm_insn *load_sm(const char *path, uint32_t *n)
{
    static const struct { const char *name; int op, has_arg; int delta; } tab[] = {
        {"PUSHLIT", SM_PUSHLIT, 1, +1}, {"PUSHWORD", SM_PUSHWORD, 1, +1}, {"PUSHIND", SM_PUSHIND, 0, 0},
        {"PUSHIPIND", SM_PUSHIPIND, 1, +1}, {"EQ", SM_EQ, 0, -1}, {"NEQ", SM_NEQ, 0, -1}, {"AND", SM_AND, 0, -1},
        {"OR", SM_OR, 0, -1}, {"XOR", SM_XOR, 0, -1}, {"ADD", SM_ADD, 0, -1}, {"LSH", SM_LSH, 0, -1},
        {"RSH", SM_RSH, 0, -1}, {"CAND", SM_CAND, 0, -1}, {"COR", SM_COR, 0, -1},
    };
    FILE *f = fopen(path, "r");
    if (!f) { perror(path); exit(1); }
    size_t cap = 64, cnt = 0;
    struct sm_insn *prog = malloc(cap * sizeof *prog);
    char name[64];
    int depth = 0, maxdepth = 0;
    while (fscanf(f, "%63s", name) == 1) {
        size_t t;
        for (t = 0; t < sizeof tab / sizeof tab[0]; t++) if (!strcmp(name, tab[t].name)) break;
        if (t == sizeof tab / sizeof tab[0]) { fprintf(stderr, "unknown opcode %s\n", name); die("bad stack-machine program"); }
        unsigned arg = 0;
        if (tab[t].has_arg && fscanf(f, "%u", &arg) != 1) die("missing operand");
        int need = tab[t].op == SM_PUSHIND ? 1 : (tab[t].delta < 0 ? (tab[t].op == SM_CAND || tab[t].op == SM_COR ? 1 : 2) : 0);
        if (depth < need) die("stack underflow in program");
        depth += tab[t].delta;
        if (depth > maxdepth) maxdepth = depth;
        if (cnt == cap) { cap *= 2; prog = realloc(prog, cap * sizeof *prog); }
        prog[cnt].op = (uint8_t)tab[t].op; prog[cnt].arg = (uint16_t)arg; cnt++;
    }
    fclose(f);
    if (maxdepth > SM_MAXDEPTH) die("stack depth above limit");
    *n = (uint32_t)cnt;
    return prog;
}

int main(int argc, char **argv)
{
    const char *machine = NULL, *progf = NULL, *pcapf = NULL, *csvf = NULL;
    size_t first = 0, count = (size_t)-1;
    for (int a = 1; a + 1 < argc; a += 2) {
        if (!strcmp(argv[a], "--machine")) machine = argv[a + 1];
        else if (!strcmp(argv[a], "--prog")) progf = argv[a + 1];
        else if (!strcmp(argv[a], "--pcap")) pcapf = argv[a + 1];
        else if (!strcmp(argv[a], "--first")) first = strtoul(argv[a + 1], NULL, 10);
        else if (!strcmp(argv[a], "--count")) count = strtoul(argv[a + 1], NULL, 10);
        else if (!strcmp(argv[a], "--csv")) csvf = argv[a + 1];
        else { fprintf(stderr, "unknown option %s\n", argv[a]); return 1; }
    }
    if (!machine || !progf || !pcapf) { fprintf(stderr, "usage: c1_interp --machine bpf|sm --prog F --pcap F [--first N] [--count M] [--csv F]\n"); return 1; }
    int is_bpf = !strcmp(machine, "bpf");
    if (!is_bpf && strcmp(machine, "sm")) die("machine must be bpf or sm");
    struct c1_trace tr;
    if (c1_load_trace(pcapf, &tr)) return 1;
    uint32_t n = 0;
    struct bpf_insn *bp = NULL;
    struct sm_insn *sp = NULL;
    if (is_bpf) bp = load_bpf(progf, &n); else sp = load_sm(progf, &n);
    if (first > tr.nframes) first = tr.nframes;
    size_t last = (count > tr.nframes - first) ? tr.nframes : first + count;
    FILE *csv = NULL;
#ifdef C1_COUNT
    if (csvf) { csv = fopen(csvf, "w"); if (!csv) { perror(csvf); return 1; } fprintf(csv, "idx,decision,vm_instr\n"); }
#else
    (void)csvf;
#endif
    uint64_t icount = 0, accepts = 0, hash = 14695981039346656037ull;
    for (size_t i = first; i < last; i++) {
        uint64_t before = icount;
        uint32_t r = is_bpf ? c1_eval_bpf(bp, tr.data[i], tr.len[i], &icount)
                            : c1_eval_sm(sp, n, tr.data[i], tr.len[i], &icount);
        int dec = r != 0;
        accepts += (uint64_t)dec;
        hash = (hash ^ (uint64_t)('0' + dec)) * 1099511628211ull;
        if (csv) fprintf(csv, "%zu,%d,%llu\n", i, dec, (unsigned long long)(icount - before));
    }
    if (csv) fclose(csv);
    printf("machine=%s frames=%zu accepts=%llu dechash=%016llx\n", machine, last - first,
           (unsigned long long)accepts, (unsigned long long)hash);
    return 0;
}
