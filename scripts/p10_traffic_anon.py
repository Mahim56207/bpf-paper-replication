#!/usr/bin/env python3
"""Phase 10 WP3(c): anonymize a captured trace (docs/phase10_design.md section 6). Reads a classic pcap (DLT_EN10MB), writes a classic pcap in which
  - every MAC address is replaced by 02:00:00:<n> (n = first-seen index),
  - every IPv4 address (IP source and destination, ARP and RARP sender and target protocol addresses) by 10.<n>.<n>.<n> (n = first-seen index, starting at 1), IPv4 header checksum recomputed,
  - every IPv6 address by fd00::<n>,
  - all bytes after the layer-3/layer-4 headers (payload) by zeros; frame lengths are unchanged. TCP and UDP checksums are not recomputed (the filters never read them).
Prints the sha256 of the output, a JSON summary, and writes <out>.hg with the two most frequent IPv4 hosts (counted over IP source/destination and ARP sender/target after
anonymization; ties broken by the lower address): "H G". The raw input is never copied anywhere. Usage: p10_traffic_anon.py <in.pcap> <out.pcap>"""
import collections, hashlib, json, struct, sys
from pathlib import Path


def main(src, dst):
    d = Path(src).read_bytes()
    magic = struct.unpack("<I", d[:4])[0]
    if magic in (0xA1B2C3D4, 0xA1B23C4D):
        e = "<"
    elif magic in (0xD4C3B2A1, 0x4D3CB2A1):
        e = ">"
    else:
        sys.exit("FATAL: not a classic pcap (magic %08x); capture with tcpdump -w, not pcapng" % magic)
    linktype = struct.unpack(e + "I", d[20:24])[0]
    if linktype != 1:
        sys.exit("FATAL: link type %d is not Ethernet" % linktype)
    macs, ip4s, ip6s = {}, {}, {}
    count4 = collections.Counter()
    ethertypes = collections.Counter()

    def idx(table, key):
        if key not in table:
            table[key] = len(table) + 1
        return table[key]

    def m(mac):
        n = idx(macs, bytes(mac))
        return bytes([2, 0, 0, (n >> 16) & 255, (n >> 8) & 255, n & 255])

    def a4(a):
        n = idx(ip4s, bytes(a))
        if n >= 1 << 24:
            sys.exit("FATAL: more than 2^24 hosts")
        return bytes([10, (n >> 16) & 255, (n >> 8) & 255, n & 255])

    def a6(a):
        n = idx(ip6s, bytes(a))
        return bytes([0xfd, 0] + [0] * 12 + [(n >> 8) & 255, n & 255])

    def csum(b):
        s = 0
        for i in range(0, len(b) - 1, 2):
            s += b[i] << 8 | b[i + 1]
        while s >> 16:
            s = (s & 0xFFFF) + (s >> 16)
        return (~s) & 0xFFFF

    out = bytearray(d[:24])
    off = 24
    nframes = 0
    while off + 16 <= len(d):
        ts_s, ts_u, caplen, wirelen = struct.unpack(e + "IIII", d[off:off + 16])
        fr = bytearray(d[off + 16: off + 16 + caplen])
        off += 16 + caplen
        nframes += 1
        if caplen >= 14:
            fr[0:6] = m(fr[0:6])
            fr[6:12] = m(fr[6:12])
            et = fr[12] << 8 | fr[13]
            ethertypes["0x%04x" % et] += 1
            keep = 14
            if et == 0x0800 and caplen >= 34 and fr[14] >> 4 == 4:
                ihl = (fr[14] & 15) * 4
                fr[26:30] = a4(fr[26:30])
                fr[30:34] = a4(fr[30:34])
                count4[bytes(fr[26:30])] += 1
                count4[bytes(fr[30:34])] += 1
                if ihl >= 20 and caplen >= 14 + ihl:
                    fr[24:26] = b"\x00\x00"
                    fr[24:26] = struct.pack("!H", csum(bytes(fr[14:14 + ihl])))
                keep = 14 + ihl
                proto = fr[23]
                if (fr[20] << 8 | fr[21]) & 0x1FFF == 0 and caplen >= keep + 8:       # first fragment: keep the L4 header
                    if proto == 6 and caplen >= keep + 13:
                        keep += ((fr[keep + 12] >> 4) * 4)
                    elif proto == 17:
                        keep += 8
                    elif proto == 1:
                        keep += 8
            elif et in (0x0806, 0x8035) and caplen >= 42:
                fr[28:32] = a4(fr[28:32])
                fr[38:42] = a4(fr[38:42])
                count4[bytes(fr[28:32])] += 1
                count4[bytes(fr[38:42])] += 1
                keep = 42
            elif et == 0x86DD and caplen >= 54:
                fr[22:38] = a6(fr[22:38])
                fr[38:54] = a6(fr[38:54])
                keep = 54
            keep = min(keep, caplen)
            for i in range(keep, caplen):
                fr[i] = 0
        else:
            fr = bytearray(len(fr))
        out += struct.pack(e + "IIII", ts_s, ts_u, caplen, wirelen) + bytes(fr)
    Path(dst).write_bytes(bytes(out))
    sha = hashlib.sha256(bytes(out)).hexdigest()
    top = sorted(count4.items(), key=lambda kv: (-kv[1], kv[0]))
    ip = lambda b: ".".join(str(x) for x in b)
    if len(top) < 2:
        sys.exit("FATAL: fewer than two IPv4 hosts in the trace")
    Path(dst + ".hg").write_text("%s %s\n" % (ip(top[0][0]), ip(top[1][0])))
    summ = {"frames": nframes, "anonymized_sha256": sha, "hosts": len(ip4s), "macs": len(macs), "ipv6_hosts": len(ip6s), "ethertypes": dict(ethertypes.most_common()),
            "H": ip(top[0][0]), "H_count": top[0][1], "G": ip(top[1][0]), "G_count": top[1][1]}
    print(json.dumps(summ))
    Path(dst + ".json").write_text(json.dumps(summ, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
