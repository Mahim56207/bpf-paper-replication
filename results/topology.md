# Topology and controls (recorded by scripts/bench.sh topology)

Generated: 2026-10-18T17:30:09Z. Every value below is the output of the command shown.

## Host
```
$ uname -srm
Linux 6.17.0-19-generic aarch64
$ nproc
5
$ getconf CLK_TCK
100
$ cat /proc/sys/net/core/bpf_jit_enable
1
$ lscpu | grep -E 'Model name|Architecture|Thread|Core|Socket|CPU\(s\)'
Architecture:                            aarch64
CPU(s):                                  5
Model name:                              -
Thread(s) per core:                      1
Core(s) per cluster:                     5
Socket(s):                               -
```

ENV.md records the machine as arm64 (aarch64), not x86; nothing in the harness assumes x86.

## CPU frequency governor
```
$ cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
      1 cat: '/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor': No such file or directory (os error 2)
```

## Interface offloads (ethtool -k p1veth0)
```
$ ethtool -k p1veth0
Features for p1veth0:
rx-checksumming: on
tx-checksumming: on
	tx-checksum-ipv4: off [fixed]
	tx-checksum-ip-generic: on
	tx-checksum-ipv6: off [fixed]
	tx-checksum-fcoe-crc: off [fixed]
	tx-checksum-sctp: on
scatter-gather: on
	tx-scatter-gather: on
	tx-scatter-gather-fraglist: on
tcp-segmentation-offload: on
	tx-tcp-segmentation: on
	tx-tcp-ecn-segmentation: on
	tx-tcp-mangleid-segmentation: on
	tx-tcp6-segmentation: on
	tx-tcp-accecn-segmentation: on
generic-segmentation-offload: on
generic-receive-offload: off
large-receive-offload: off [fixed]
rx-vlan-offload: on
tx-vlan-offload: on
ntuple-filters: off [fixed]
receive-hashing: off [fixed]
highdma: on
rx-vlan-filter: off [fixed]
vlan-challenged: off [fixed]
tx-gso-robust: off [fixed]
tx-fcoe-segmentation: off [fixed]
tx-gre-segmentation: on
tx-gre-csum-segmentation: on
tx-ipxip4-segmentation: on
tx-ipxip6-segmentation: on
tx-udp_tnl-segmentation: on
tx-udp_tnl-csum-segmentation: on
tx-gso-partial: off [fixed]
tx-tunnel-remcsum-segmentation: off [fixed]
tx-sctp-segmentation: on
tx-esp-segmentation: off [fixed]
tx-udp-segmentation: on
tx-gso-list: on
tx-nocache-copy: off
loopback: off [fixed]
rx-fcs: off [fixed]
rx-all: off [fixed]
tx-vlan-stag-hw-insert: on
rx-vlan-stag-hw-parse: on
rx-vlan-stag-filter: off [fixed]
l2-fwd-offload: off [fixed]
hw-tc-offload: off [fixed]
esp-hw-offload: off [fixed]
esp-tx-csum-hw-offload: off [fixed]
rx-udp_tunnel-port-offload: off [fixed]
tls-hw-tx-offload: off [fixed]
tls-hw-rx-offload: off [fixed]
rx-gro-hw: off [fixed]
tls-hw-record: off [fixed]
rx-gro-list: off
macsec-hw-offload: off [fixed]
rx-udp-gro-forwarding: off
hsr-tag-ins-offload: off [fixed]
hsr-tag-rm-offload: off [fixed]
hsr-fwd-offload: off [fixed]
hsr-dup-offload: off [fixed]
```

## Link
```
$ ip -d link show p1veth0
20: p1veth0@if19: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether 1e:03:ef:ff:36:fa brd ff:ff:ff:ff:ff:ff link-netns p2ns promiscuity 0 allmulti 0 minmtu 68 maxmtu 65535 
    veth addrgenmode eui64 numtxqueues 5 numrxqueues 5 gso_max_size 65536 gso_max_segs 65535 tso_max_size 524280 tso_max_segs 65535 gro_max_size 65536 gso_ipv4_max_size 65536 gro_ipv4_max_size 65536 
```

## /proc/net/packet columns (the contract names a Drops column)
```
$ head -1 /proc/net/packet
sk               RefCnt Type Proto  Iface R Rmem   User   Inode
```
If the header above has no Drops column, per-socket drops come from PACKET_STATISTICS instead: the
sniffer prints `FINAL_KERNEL kernel_drops=` and the loader `FINAL_SOCKET kernel_drops=`.

## Tools
```
$ iperf3 --version
iperf 3.18 (cJSON 1.7.15)
Linux Ubuntu 6.17.0-19-generic #19-Ubuntu SMP PREEMPT_DYNAMIC Fri Mar  6 14:47:42 UTC 2026 aarch64
$ pidstat -V
sysstat version 12.7.7
(C) Sebastien Godard (sysstat <at> orange.fr)
$ vmstat -V
vmstat from procps-ng 4.0.4
$ mpstat -V
sysstat version 12.7.7
(C) Sebastien Godard (sysstat <at> orange.fr)
$ taskset --version
taskset from util-linux 2.41
$ bpftool version
bpftool v7.7.0
using libbpf v1.7
```

## Pinning plan (nproc=5)

| core | use |
|---|---|
| 0 | left free: system, bench.sh, pidstat, vmstat |
| 1 | iperf3 client for the noise stream (flood runs only) |
| 2 | capture process: baseline_sniffer (A) or loader (B-E) |
| 3 | iperf3 server(s), inside namespace p2ns |
| 4 | iperf3 client for the main stream (curve runs and the matching flood stream) |

The capture process, the iperf3 server and the iperf3 client are never on the same core. Note: for a veth
pair the receive path (and therefore the in-kernel filter) normally runs in softirq context on the sending
core, i.e. core 4, not on core 2; the harness therefore also records per-CPU busy time from /proc/stat.
