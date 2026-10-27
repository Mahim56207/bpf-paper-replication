#!/usr/bin/env python3
"""Generate the Phase 6c traces (docs/phase6c_design.md section 4). Stdlib only, deterministic.

Usage: python3 -I scripts/c1_make_trace.py <outdir>
Writes, per trace NAME, <outdir>/NAME.pcap (classic pcap, microsecond magic, DLT_EN10MB, caplen == len)
and <outdir>/NAME.labels (one frame-type label per frame), and <outdir>/trace_manifest.txt.
Traces: mix_M0, mix_Mip, mix_Mnonip (10000 frames each, shuffled), edge (matching frames of every
filter cut at every length 0..len), and corpus38 when --corpus <dir> is given (the Phase 3 frames,
prefix bytes stripped; <dir> holds the *.bin files and manifest.tsv from p3_make_packets.py <dir> 1).
The mix parameters are assumptions of this study (DEVIATIONS D6c.4), not measurements.
"""
import random
import struct
import sys
from collections import Counter
from pathlib import Path

SEED = 20261025
N = 10000
H = bytes([10, 0, 0, 10])
G = bytes([10, 0, 0, 20])
S_PORTS = (79, 53, 513, 514)
OTHER_PORTS = (23, 25, 80, 110, 119, 6000)

MIXES = {  # fractions of all frames; the rest of 1.0 does not exist: they sum to 1
    "M0":    {"ip4": 0.85, "arp": 0.05, "rarp": 0.01, "ip6": 0.01, "other": 0.08},
    "Mip":   {"ip4": 0.97, "arp": 0.01, "rarp": 0.00, "ip6": 0.00, "other": 0.02},
    "Mnonip": {"ip4": 0.40, "arp": 0.20, "rarp": 0.05, "ip6": 0.05, "other": 0.30},
}
L4 = (("tcp", 0.70), ("udp", 0.26), ("icmp", 0.04))


def mac(rng):
    return bytes([0x02, 0, 0, rng.randrange(256), rng.randrange(256), rng.randrange(256)])


def eth(rng, et):
    return mac(rng) + mac(rng) + struct.pack("!H", et)


def rand_addr(rng):
    return bytes([10, 0, 0, rng.randrange(30, 251)])


def pick(rng, table):
    r, acc = rng.random(), 0.0
    for k, p in table:
        acc += p
        if r < acc:
            return k
    return table[-1][0]


def addrs(rng):
    """(src, dst, cat): categories exclusive; H involved 0.08, G involved 0.05, both 0.01 overall."""
    r = rng.random()
    if r < 0.01:
        return (H, G, "HG") if rng.random() < 0.5 else (G, H, "HG")
    if r < 0.08:
        o = rand_addr(rng)
        return (H, o, "H") if rng.random() < 0.5 else (o, H, "H")
    if r < 0.12:
        o = rand_addr(rng)
        return (G, o, "G") if rng.random() < 0.5 else (o, G, "G")
    return rand_addr(rng), rand_addr(rng), "-"


def ip_frame(rng):
    src, dst, cat = addrs(rng)
    proto_name = pick(rng, L4)
    proto = {"tcp": 6, "udp": 17, "icmp": 1}[proto_name]
    ihl = 5 if rng.random() < 0.95 else rng.randrange(6, 9)
    frag = rng.randrange(1, 8000) if rng.random() < 0.01 else 0
    ports = "-"
    if proto_name == "tcp":
        if rng.random() < 0.15:
            k = rng.randrange(3)
            sp_in = k in (0, 2)
            dp_in = k in (1, 2)
            sp = rng.choice(S_PORTS) if sp_in else rng.choice(OTHER_PORTS + (rng.randrange(1024, 5000),))
            dp = rng.choice(S_PORTS) if dp_in else rng.choice(OTHER_PORTS + (rng.randrange(1024, 5000),))
            ports = "S"
        else:
            sp = rng.choice(OTHER_PORTS + (rng.randrange(1024, 5000),))
            dp = rng.choice(OTHER_PORTS + (rng.randrange(1024, 5000),))
        l4 = struct.pack("!HHIIBBHHH", sp, dp, rng.getrandbits(32), 0, 5 << 4, 0x10, 1000, 0, 0)
    elif proto_name == "udp":
        pp = rng.choice(S_PORTS) if rng.random() < 0.10 else rng.choice(OTHER_PORTS)
        l4 = struct.pack("!HHHH", rng.randrange(1024, 5000), pp, 8, 0)
        ports = "udpS" if pp in S_PORTS else "-"
    else:
        l4 = b"\x08\x00\x00\x00\x00\x00\x00\x00"
    payload = bytes(rng.getrandbits(8) for _ in range(rng.randrange(0, 1401) // 8 * 8))
    opts = b"\x01" * ((ihl - 5) * 4)
    total = ihl * 4 + len(l4) + len(payload)
    iph = struct.pack("!BBHHHBBH4s4s", (4 << 4) | ihl, 0, total, rng.getrandbits(16), frag, 64, proto, 0, src, dst)
    label = "ip4-%s-%s%s%s%s" % (proto_name, cat, "-P" + ports if ports != "-" else "", "-frag" if frag else "",
                                  "-opt" if ihl > 5 else "")
    return eth(rng, 0x0800) + iph + opts + l4 + payload, label


def arp_frame(rng, et, name):
    r = rng.random()
    if r < 0.02:
        a, b, cat = (H, G, "HG") if rng.random() < 0.5 else (G, H, "HG")
    elif r < 0.10:
        o = rand_addr(rng)
        a, b, cat = (H, o, "H") if rng.random() < 0.5 else (o, H, "H")
    elif r < 0.18:
        o = rand_addr(rng)
        a, b, cat = (G, o, "G") if rng.random() < 0.5 else (o, G, "G")
    else:
        a, b, cat = rand_addr(rng), rand_addr(rng), "-"
    oper = rng.choice((1, 2)) if name == "arp" else rng.choice((3, 4))
    body = struct.pack("!HHBBH", 1, 0x0800, 6, 4, oper) + mac(rng) + a + mac(rng) + b
    return eth(rng, et) + body, "%s-%s" % (name, cat)


def ip6_frame(rng):
    body = bytes(rng.getrandbits(8) for _ in range(rng.randrange(40, 200)))
    return eth(rng, 0x86DD) + body, "ip6"


def other_frame(rng):
    et = rng.choice((0x6003, 0x809B, 0x8137))
    body = bytes(rng.getrandbits(8) for _ in range(rng.randrange(46, 1000)))
    return eth(rng, et) + body, "other-%04x" % et


def make_mix(name, rng):
    mix = MIXES[name]
    cls = [(k, mix[k]) for k in ("ip4", "arp", "rarp", "ip6", "other")]
    frames = []
    for _ in range(N):
        c = pick(rng, cls)
        if c == "ip4":
            f, lab = ip_frame(rng)
        elif c == "arp":
            f, lab = arp_frame(rng, 0x0806, "arp")
        elif c == "rarp":
            f, lab = arp_frame(rng, 0x8035, "rarp")
        elif c == "ip6":
            f, lab = ip6_frame(rng)
        else:
            f, lab = other_frame(rng)
        if len(f) < 60:
            f += b"\x00" * (60 - len(f))
        if rng.random() < 0.01:
            f = f[: rng.randrange(1, len(f))]
            lab += "-trunc"
        frames.append((f, lab))
    rng.shuffle(frames)
    return frames


def edge_frames(rng):
    """Matching (and near-matching) frames of every filter, each cut at every length 0..len."""
    base = []

    def ip(src, dst, proto, l4, ihl=5, frag=0):
        opts = b"\x01" * ((ihl - 5) * 4)
        iph = struct.pack("!BBHHHBBH4s4s", (4 << 4) | ihl, 0, ihl * 4 + len(l4), 0, frag, 64, proto, 0, src, dst)
        return eth(rng, 0x0800) + iph + opts + l4

    tcp = lambda sp, dp: struct.pack("!HHIIBBHHH", sp, dp, 0, 0, 5 << 4, 0x10, 1000, 0, 0)
    base.append(("e-ip-H-src", ip(H, rand_addr(rng), 6, tcp(1234, 80))))
    base.append(("e-ip-H-dst", ip(rand_addr(rng), H, 17, struct.pack("!HHHH", 1, 2, 8, 0))))
    base.append(("e-ip-HG", ip(H, G, 6, tcp(1234, 80))))
    base.append(("e-ip-GH-opt", ip(G, H, 6, tcp(1234, 80), ihl=7)))
    for p in S_PORTS:
        base.append(("e-tcp-dport-%d" % p, ip(rand_addr(rng), rand_addr(rng), 6, tcp(1234, p))))
        base.append(("e-tcp-sport-%d-ihl6" % p, ip(rand_addr(rng), rand_addr(rng), 6, tcp(p, 99), ihl=6)))
    base.append(("e-tcp-frag", ip(rand_addr(rng), rand_addr(rng), 6, tcp(1234, 79), frag=0x00B9)))
    base.append(("e-tcp-ihl15", ip(rand_addr(rng), rand_addr(rng), 6, tcp(1234, 513) + b"\0" * 60, ihl=15)))
    base.append(("e-arp-HG", arp_frame_fixed(rng, 0x0806, 1, H, G)))
    base.append(("e-arp-GH", arp_frame_fixed(rng, 0x0806, 2, G, H)))
    base.append(("e-rarp-HG", arp_frame_fixed(rng, 0x8035, 3, H, G)))
    base.append(("e-arp-H-only", arp_frame_fixed(rng, 0x0806, 1, H, rand_addr(rng))))
    out = []
    for name, f in base:
        for n in range(0, len(f) + 1):
            out.append((f[:n], "%s-cut%d" % (name, n)))
    return out


def arp_frame_fixed(rng, et, oper, spa, tpa):
    body = struct.pack("!HHBBH", 1, 0x0800, 6, 4, oper) + mac(rng) + spa + mac(rng) + tpa
    return eth(rng, et) + body


def write_pcap(path, frames):
    with open(path, "wb") as f:
        f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for i, (data, _lab) in enumerate(frames):
            f.write(struct.pack("<IIII", i, 0, len(data), len(data)))
            f.write(data)


def write_labels(path, frames):
    Path(path).write_text("".join(lab + "\n" for _d, lab in frames))


def main():
    args = sys.argv[1:]
    out = Path(args[0])
    corpus = Path(args[args.index("--corpus") + 1]) if "--corpus" in args else None
    out.mkdir(parents=True, exist_ok=True)
    man = []
    for i, name in enumerate(("M0", "Mip", "Mnonip")):
        fr = make_mix(name, random.Random(SEED + i))
        write_pcap(out / ("mix_%s.pcap" % name), fr)
        write_labels(out / ("mix_%s.labels" % name), fr)
        cnt = Counter(lab.split("-")[0] for _d, lab in fr)
        man.append("mix_%s: %d frames, %s" % (name, len(fr), ", ".join("%s=%d" % kv for kv in sorted(cnt.items()))))
    fr = edge_frames(random.Random(SEED + 100))
    write_pcap(out / "edge.pcap", fr)
    write_labels(out / "edge.labels", fr)
    man.append("edge: %d frames" % len(fr))
    if corpus:
        rows = [l.split("\t") for l in (corpus / "manifest.tsv").read_text().splitlines()]
        fr = []
        for name, _len, _exp in rows:
            data = (corpus / (name + ".bin")).read_bytes()[1:]  # prefix of 1 byte, see docstring
            fr.append((data, name))
        write_pcap(out / "corpus38.pcap", fr)
        write_labels(out / "corpus38.labels", fr)
        man.append("corpus38: %d frames" % len(fr))
    (out / "trace_manifest.txt").write_text("\n".join(man) + "\n")
    print("\n".join(man))


if __name__ == "__main__":
    main()
