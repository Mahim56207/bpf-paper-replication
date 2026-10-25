#!/usr/bin/env python3
"""Generate the CSPF (stack machine) programs for Filters 1-4 from the construction rules of
docs/phase6c_design.md section 3.3. Usage: python3 -I scripts/c1_gen_progs.py <outdir>

Variants: full / sc (short-circuit) x general / fused (F3 only; F1, F2, F4 have one program per
short-circuit style). Trees are written below as nested ('and'|'or', [children]) over leaf
instruction lists; the code generator is mechanical so the rules are in code, not in the author's
head. Offsets are bytes from the start of an Ethernet frame (ethertype 12, IP header at 14).
"""
import sys
from pathlib import Path

H = (0x0A00, 0x000A)   # horse 10.0.0.10
G = (0x0A00, 0x0014)   # gauguin 10.0.0.20
PORTS = (79, 53, 513, 514)  # finger, domain, login, shell (/etc/services)


def lit(k): return [("PUSHLIT", k)]
def word(n): return [("PUSHWORD", n)]


def eq_word(off, val):
    return word(off) + lit(val) + [("EQ", None)]


def eq_word_masked(off, mask, val):
    return word(off) + lit(mask) + [("AND", None)] + lit(val) + [("EQ", None)]


def eq32(off, addr):
    return eq_word(off, addr[0]) + eq_word(off + 2, addr[1]) + [("AND", None)]


def tcp_off_general():
    # 14 + 4 * (IP header length in words): byte 14 is the high byte of word 14
    return (word(14) + lit(8) + [("RSH", None)] + lit(15) + [("AND", None)] + lit(2) + [("LSH", None)]
            + lit(14) + [("ADD", None)])


def port_leaf(port, which, fused):
    # which: 0 = source port (TCP offset 0), 2 = destination port (TCP offset 2)
    if fused:
        return [("PUSHIPIND", which)] + lit(port) + [("EQ", None)]
    code = tcp_off_general()
    if which:
        code += lit(which) + [("ADD", None)]
    return code + [("PUSHIND", None)] + lit(port) + [("EQ", None)]


def AND(*c): return ("and", list(c))
def OR(*c): return ("or", list(c))


def trees(fused):
    eth_ip = eq_word(12, 0x0800)
    ip_host = lambda x: OR(eq32(26, x), eq32(30, x))      # src or dst
    arp_host = lambda x: OR(eq32(28, x), eq32(38, x))     # sender or target protocol address
    f1 = eth_ip
    f2 = AND(eth_ip, ip_host(H))
    proto_tcp = eq_word_masked(22, 0x00FF, 6)
    no_frag = eq_word_masked(20, 0x1FFF, 0)
    leaves = []
    for p in PORTS:
        leaves += [port_leaf(p, 0, fused), port_leaf(p, 2, fused)]
    f3 = AND(eth_ip, proto_tcp, no_frag, OR(*leaves))
    branch = lambda eth, host: AND(eq_word(12, eth), host(H), host(G))
    f4 = OR(branch(0x0800, ip_host), branch(0x0806, arp_host), branch(0x8035, arp_host))
    return {"F1": f1, "F2": f2, "F3": f3, "F4": f4}


def full(node):
    """Post-order, binary AND/OR left fold, no short-circuit."""
    if isinstance(node, list):
        return list(node)
    op, kids = node
    code = full(kids[0])
    for k in kids[1:]:
        code += full(k) + [("AND" if op == "and" else "OR", None)]
    return code


def sc(node):
    """Short-circuit only at the root chain and at the tail disjunction of a root conjunction."""
    if isinstance(node, list):
        return list(node)
    op, kids = node
    code = []
    if op == "and":
        for k in kids[:-1]:
            code += full(k) + [("CAND", None)]
        last = kids[-1]
        if not isinstance(last, list) and last[0] == "or":
            code += tail_or(last[1])
        else:
            code += full(last)
    else:  # root disjunction
        for k in kids[:-1]:
            code += full(k) + [("COR", None)]
        code += full(kids[-1])
    return code


def tail_or(kids):
    code = []
    for k in kids[:-1]:
        code += full(k) + [("COR", None)]
    return code + full(kids[-1])


def emit(path, code):
    path.write_text("".join("%s%s\n" % (op, "" if a is None else " %d" % a) for op, a in code))


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    names = []
    for fused in (False, True):
        t = trees(fused)
        for f in ("F1", "F2", "F3", "F4"):
            if fused and f != "F3":
                continue  # general == fused for F1, F2, F4: one program per style
            style = "fused" if fused else "general"
            tag = style if f == "F3" else "any"
            for mode, fn in (("full", full), ("sc", sc)):
                name = "%s_%s_%s.sm" % (f, mode, tag)
                emit(out / name, fn(t[f]))
                names.append(name)
    for n in sorted(names):
        print(n, len((out / n).read_text().splitlines()), "static instructions")


if __name__ == "__main__":
    main()
