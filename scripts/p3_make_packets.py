#!/usr/bin/env python3
"""Build the Phase 3 test frames and an independent reference verdict for each.

Usage: python3 -I scripts/p3_make_packets.py <outdir> [prefix_bytes]
Writes <outdir>/<name>.bin and <outdir>/manifest.tsv (name, length, expected return value).
With prefix_bytes=N every file gets N zero bytes in front (BPF_PROG_TEST_RUN strips the first
ETH_HLEN=14 bytes before a socket filter sees the packet, see docs/phase3_review.md), and two
extra frames shorter than an Ethernet header are added. The manifest length and expected return
value always refer to the frame the filter should see, i.e. without the prefix.
Expected return value = frame length if the reference matcher accepts it, else 0 (the filter's
contract). The reference matcher below is a separate Python implementation of the Phase 2 rule
(IPv4, TCP/UDP, port 4040 either direction, every layer length-checked, non-first fragments
rejected); it is not derived from phase3_kern.c.
"""
import random
import struct
import sys
from pathlib import Path

PORT = 4040
ETH_P_IP = 0x0800


def eth(proto):
    return b"\x02\x00\x00\x00\x00\x02" + b"\x02\x00\x00\x00\x00\x01" + struct.pack("!H", proto)


def ipv4(proto, payload_len, ihl=5, version=4, frag=0):
    opts = b"\x01" * max(0, (ihl - 5) * 4)  # NOP options
    hdr = struct.pack("!BBHHHBBH4s4s", (version << 4) | (ihl & 0xF), 0, ihl * 4 + payload_len, 0, frag,
                      64, proto, 0, b"\x0a\x00\x00\x01", b"\x0a\x00\x00\x02")
    return hdr + opts


def tcp(sp, dp):
    return struct.pack("!HHIIBBHHH", sp, dp, 0, 0, 5 << 4, 0x10, 1000, 0, 0)  # 20 bytes


def udp(sp, dp, payload=b""):
    return struct.pack("!HHHH", sp, dp, 8 + len(payload), 0) + payload


def ref_match(pkt):
    """Independent reference matcher (see module docstring)."""
    if len(pkt) < 14 or struct.unpack("!H", pkt[12:14])[0] != ETH_P_IP:
        return False
    ip = pkt[14:]
    if len(ip) < 20 or ip[0] >> 4 != 4:
        return False
    ihl = (ip[0] & 0xF) * 4
    if ihl < 20 or len(ip) < ihl:
        return False
    if struct.unpack("!H", ip[6:8])[0] & 0x1FFF:
        return False
    proto, l4 = ip[9], ip[ihl:]
    need = {6: 20, 17: 8}.get(proto)
    if need is None or len(l4) < need:
        return False
    sp, dp = struct.unpack("!HH", l4[:4])
    return PORT in (sp, dp)


def cases():
    c = []
    ip6 = lambda p, n, **k: ipv4(p, n, **k)  # noqa: E731  (name kept short for the table below)
    # accepted
    c.append(("tcp_dst_4040", eth(ETH_P_IP) + ip6(6, 20) + tcp(1234, PORT)))
    c.append(("tcp_src_4040", eth(ETH_P_IP) + ip6(6, 20) + tcp(PORT, 5555)))
    c.append(("udp_dst_4040", eth(ETH_P_IP) + ip6(17, 8) + udp(1111, PORT)))
    c.append(("udp_src_4040", eth(ETH_P_IP) + ip6(17, 8) + udp(PORT, 2222)))
    c.append(("tcp_ihl6_4040", eth(ETH_P_IP) + ip6(6, 20, ihl=6) + tcp(1234, PORT)))
    c.append(("tcp_ihl15_4040", eth(ETH_P_IP) + ip6(6, 20, ihl=15) + tcp(1234, PORT)))
    c.append(("tcp_4040_payload100", eth(ETH_P_IP) + ip6(6, 120) + tcp(1234, PORT) + b"P" * 100))
    c.append(("tcp_4040_first_fragment", eth(ETH_P_IP) + ip6(6, 20, frag=0x2000) + tcp(1234, PORT)))
    # well-formed, not matching
    c.append(("tcp_port80", eth(ETH_P_IP) + ip6(6, 20) + tcp(1234, 80)))
    c.append(("udp_port53", eth(ETH_P_IP) + ip6(17, 8) + udp(1111, 53)))
    c.append(("icmp", eth(ETH_P_IP) + ip6(1, 8) + b"\x08\x00\x00\x00\x00\x00\x00\x00"))
    c.append(("arp", eth(0x0806) + b"\x00" * 28))
    c.append(("ipv6_ethertype", eth(0x86DD) + b"\x00" * 40))
    # truncated
    c.append(("eth_only_ip_ethertype", eth(ETH_P_IP)))
    c.append(("ip_truncated_10", eth(ETH_P_IP) + ip6(6, 20)[:10]))
    c.append(("ip_no_l4", eth(ETH_P_IP) + ip6(6, 20)))
    c.append(("tcp_truncated_10_port4040", eth(ETH_P_IP) + ip6(6, 20) + tcp(1234, PORT)[:10]))
    c.append(("udp_truncated_4_port4040", eth(ETH_P_IP) + ip6(17, 8) + udp(1111, PORT)[:4]))
    c.append(("ihl15_declared_short_frame", eth(ETH_P_IP) + ip6(6, 20, ihl=15)[:20] + tcp(1234, PORT)))
    # malformed headers
    c.append(("ihl3_below_minimum", eth(ETH_P_IP) + ip6(6, 20, ihl=3)[:12] + tcp(1234, PORT)))
    c.append(("version6_in_ipv4_frame", eth(ETH_P_IP) + ip6(6, 20, version=6) + tcp(1234, PORT)))
    c.append(("non_first_fragment_4040", eth(ETH_P_IP) + ip6(6, 20, frag=0x00B9) + tcp(1234, PORT)))
    # garbage
    c.append(("garbage_zero_64", b"\x00" * 64))
    c.append(("garbage_ff_64", b"\xff" * 64))
    rng = random.Random(20260418)
    for i in range(8):
        n = rng.randint(14, 128)
        body = bytes(rng.getrandbits(8) for _ in range(n - 14))
        c.append((f"garbage_random_ip_ethertype_{i}", eth(ETH_P_IP) + body))
    for i in range(4):
        n = rng.randint(14, 128)
        c.append((f"garbage_random_all_{i}", bytes(rng.getrandbits(8) for _ in range(n))))
    return c


def main():
    out = Path(sys.argv[1])
    prefix = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    frames = cases()
    if prefix:  # only testable when the prefix carries the 14-byte minimum of BPF_PROG_TEST_RUN
        frames += [("empty_0_bytes", b""), ("short_13_bytes", eth(ETH_P_IP)[:13])]
    for name, pkt in frames:
        (out / f"{name}.bin").write_bytes(b"\x00" * prefix + pkt)
        rows.append((name, len(pkt), len(pkt) if ref_match(pkt) else 0))
    with open(out / "manifest.tsv", "w") as f:
        for r in rows:
            f.write("\t".join(map(str, r)) + "\n")
    acc = sum(1 for r in rows if r[2])
    print(f"{len(rows)} frames written to {out}: {acc} expected accepted, {len(rows) - acc} expected dropped")
    for r in rows:
        print("%-34s len=%-4d expected_return=%d" % r)


if __name__ == "__main__":
    main()
