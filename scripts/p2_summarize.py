#!/usr/bin/env python3
"""Phase 2 summary: every number is parsed from logs/ (no inputs typed by hand).
Usage: python3 -I scripts/p2_summarize.py [logdir] | tee logs/p2_summary.log
"""
import re
import subprocess
import sys
from pathlib import Path

LOGS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "logs"


def kv(line):
    return {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", line)}


def sniffer(path):
    final = kernel = None
    for line in (LOGS / path).read_text().splitlines():
        if line.startswith("FINAL_KERNEL"):
            kernel = kv(line)
        elif line.startswith("FINAL "):
            final = kv(line)
    return final, kernel


def tcpdump_summary(path):
    text = (LOGS / path).read_text()
    out = {}
    for key, pat in (("captured", r"(\d+) packets captured"),
                     ("received_by_filter", r"(\d+) packets received by filter"),
                     ("dropped", r"(\d+) packets dropped by kernel")):
        m = re.search(pat, text)
        out[key] = int(m.group(1)) if m else None
    return out


def savefile_protocols(path):
    r = subprocess.run(["tcpdump", "-nn", "-r", str(LOGS / path)],
                       capture_output=True, text=True, check=False)
    lines = r.stdout.splitlines()
    return {"packets": len(lines),
            "tcp": sum(1 for l in lines if "Flags [" in l),
            "udp": sum(1 for l in lines if " UDP, " in l)}


def pct(a, b):
    return f"{100.0 * a / b:.2f}%" if b else "n/a"


if (LOGS / "p2_stageA_net.log").exists():  # absent in "skipA" reruns
    print("== Stage A (both addresses in root namespace; logs/p2_stageA*.log)")
    route = [l for l in (LOGS / "p2_stageA_net.log").read_text().splitlines() if l.startswith("local ")]
    print("ip route get 10.0.0.2 from 10.0.0.1:", route[0].strip() if route else "n/a")
    fa, ka = sniffer("p2_stageA_run.log")
    print(f"sniffer on p1veth0: total_packets={fa['total_packets']} matched_packets={fa['matched_packets']} "
          f"kernel_drops={ka['kernel_drops']}")
    cl = (LOGS / "p2_stageA_iperf_client.log").read_text().splitlines()
    print("iperf3 client (receiver line):", [l.strip() for l in cl if l.rstrip().endswith("receiver")][0])


for tag, pfx, label in (("paced", "p2_", "TCP 100 Mbit/s 5 s + UDP 50 Mbit/s 2 s"),
                        ("fullrate", "p2_full_", "TCP unlimited 5 s + UDP 50 Mbit/s 2 s")):
    f, k = sniffer(f"{pfx}run.log")
    t = tcpdump_summary(f"{pfx}tcpdump.log")
    s = savefile_protocols(f"{pfx}capture.pcap")
    unmatched = f["total_packets"] - f["matched_packets"]
    print(f"\n== Stage B {tag}: {label}")
    print(f"sniffer  total_packets={f['total_packets']} matched_packets={f['matched_packets']} "
          f"unmatched={unmatched} total_bytes={f['total_bytes']} truncated={f['truncated']}")
    print(f"sniffer  mean bytes/packet copied = {f['total_bytes'] / f['total_packets']:.0f}")
    print(f"sniffer  kernel_packets={k['kernel_packets']} kernel_drops={k['kernel_drops']} "
          f"({pct(k['kernel_drops'], k['kernel_packets'])} of packets that reached the socket)")
    print(f"tcpdump  captured={t['captured']} received_by_filter={t['received_by_filter']} "
          f"dropped_by_kernel={t['dropped']}")
    print(f"savefile packets={s['packets']} (tcp={s['tcp']}, udp={s['udp']})")
    print(f"sniffer matched_packets - tcpdump received_by_filter = {f['matched_packets'] - t['received_by_filter']}")
    print(f"sniffer kernel_packets  - tcpdump received_by_filter = {k['kernel_packets'] - t['received_by_filter']}")
