# Phase 2 notes: user-space baseline sniffer

Paper citations are `(paper.txt L<n>)`; `paper.txt` is a two-column layout, so a cited line holds a fragment of the quoted sentence. Every measured number below is parsed from logs/ by `scripts/p2_summarize.py` (output: `logs/p2_summary.log`) or quoted from the named log.

## What was built and run

- `src/baseline_sniffer.c`: AF_PACKET/SOCK_RAW/ETH_P_ALL socket bound to one interface; one `recvfrom()` per packet copies the whole frame into a 128 KiB user buffer, then `match_packet()` parses eth -> IPv4 -> TCP/UDP in user memory with a length check at every layer (IP total length is never used). Match: TCP or UDP port 4040, either direction, compared against `htons(4040)`. Counters printed once per second; the clock is read every 1024 packets and on each 200 ms idle timeout, not per packet. Compiled with `gcc -O2 -Wall -Wextra -Werror` (`logs/p2_compile.log`). The first attempt failed `-Werror` on an arm64 `uint64_t` vs `unsigned long long` printf format; fixed with `UINT64_C()` constants.
- `scripts/phase2_verify.sh`: veth pair with `p1veth1` in namespace `p2ns`, tcpdump as a systemd unit, iperf3 server in the namespace. Logs: `logs/p2_netsetup.log`, `p2_run.log`, `p2_tcpdump.log`, `p2_crosscheck.log`, `p2_full_*.log`, `p2_cleanup.log`, whole run in `p2_verify.log`.

## Cross-check rule (written before the runs)

    allowance = max(10, tcpdump_captured / 200) + sniffer kernel_drops + tcpdump "dropped by kernel"
    PASS         |sniffer matched_packets - tcpdump "packets captured"| <= allowance, and drops are valid evidence
    INCONCLUSIVE total drops > 1% of tcpdump captured, or a drop count is unavailable
    FAIL         otherwise

Justification:
- Start/stop skew is removed by construction: both tools are confirmed listening before the first packet and both are stopped after 3 s without traffic. With no loss the expected difference is 0.
- The only legitimate source of difference is a socket dropping packets when its receive buffer is full. Each tool reports its own drop count (`tp_drops` via PACKET_STATISTICS; tcpdump's "dropped by kernel"), so those are added one-for-one.
- The remaining slack, 0.5% with a floor of 10 packets, covers shutdown stragglers. It is small on purpose: a difference beyond drops plus slack is a FAIL to investigate, not a reason to widen the rule.
- UNVERIFIED (not stated in the man pages read): tcpdump's default capture direction, and whether `port N` includes SCTP/IPv6. The result below shows the two tools agree exactly on this traffic, so neither mattered here.

**Amendment, made after run 1 and before runs 2 and 3.** Run 1 was a full-rate run in which the sniffer dropped 82,093 of 194,418 packets (`logs/p2_run1_run.log`). With drops that large the allowance is larger than the whole signal, so a PASS would prove nothing about the matcher. I added the INCONCLUSIVE condition above and split the verification into a **paced** run (correctness: rates low enough that nobody should drop) and a **full-rate** run (stress: does the baseline keep up). The tolerance numbers themselves (0.5%, floor 10) were not changed.

## Results (logs/p2_summary.log)

**Stage A: the topology as first specified does not work.** With both 10.0.0.1 and 10.0.0.2 on interfaces in the root namespace, `ip route get 10.0.0.2 from 10.0.0.1` returns `local ... dev lo` (`logs/p2_stageA_net.log`). iperf3 moved 9.94 GBytes (`p2_stageA_iperf_client.log`) while the sniffer on p1veth0 saw 57 packets, 0 matching (`p2_stageA.log`): the traffic never touched the veth pair. Stage B moves p1veth1 into a network namespace; there `ip route get 10.0.0.2` goes `dev p1veth0` (`p2_netsetup.log`).

**Paced run** (TCP 100 Mbit/s 5 s + UDP 50 Mbit/s 2 s):

| | sniffer | tcpdump |
|---|---|---|
| packets seen | total 10,783 (matched 10,741, unmatched 42) | received by filter 10,741 |
| captured | matched 10,741 | captured 10,729 |
| drops | kernel_drops 0 | dropped by kernel 12 |

`abs_diff=12`, `allowance=65` (53 + 0 + 12): **CROSSCHECK PASS** (`logs/p2_crosscheck.log`). Stronger than the rule requires: the sniffer's matched count (10,741) equals tcpdump's own filter-accept count (10,741) exactly; the 12 difference is tcpdump dropping after its filter (10,729 + 12 = 10,741). The savefile holds TCP 2,108 and UDP 8,621 packets, so both branches of the matcher were exercised. The 42 unmatched packets are the non-port-4040 background (ARP, IPv6) on the link.

**Full-rate run** (TCP unlimited 5 s, iperf3 reports 7.85 Gbit/s, + UDP 50 Mbit/s 2 s):
- Sniffer: kernel_packets 319,908 reached the socket, kernel_drops 163,713 (**51.18%**), 156,195 delivered (156,193 matched); 2,357,138,315 bytes copied, mean 15,091 bytes/packet.
- tcpdump: received by filter 319,905, captured 94,281, dropped 225,624. tcpdump (immediate mode, `-U`) also fell behind, worse than the sniffer.
- Cross-check: **INCONCLUSIVE** by the rule (389,337 drops > 1% of 94,281). What it does show: the arrival counts agree, sniffer `kernel_packets` 319,908 vs tcpdump `received by filter` 319,905 (difference 3).

## Process finding: why runs 1 and 2 hung

Both earlier runs blocked while stopping tcpdump. Evidence: `kill -TERM` as root returned "Permission denied" and `pkill -KILL` also failed (`logs/p2_h1_tcpdump_term.log`, variant A; variants B and C never ran because that run was interrupted). `ps -o label` (shown in-session, not logged; only my own shell label is in `logs/p2_apparmor_probe.log`) showed tcpdump labelled `tcpdump (enforce)` and every process started from this terminal labelled `claude-desktop (unconfined)`. `/etc/apparmor.d/abstractions/base:146` is `signal (receive) peer=unconfined`; the sender's label is the named profile `claude-desktop`, not plain `unconfined`. That explains the EPERM; the AppArmor audit log that would confirm the exact denial needs root and was not read, so the mechanism is inferred, not observed. My script's `kill ... || wait` then waited forever on a live process. Fix: tcpdump is started with `systemd-run` and stopped with `systemctl stop` (systemd is unconfined and its SIGTERM is accepted); `stop_proc` no longer waits on a process it cannot signal. Run 3 stopped tcpdump cleanly both times and the cleanup check found no leftover processes (`logs/p2_cleanup.log`).

## Where this design pays the paper's cost

1. **A per-packet kernel-to-user copy, before any filtering.** `recvfrom()` copies the whole frame into the user buffer for every packet, and `match_packet()` runs afterwards. In the full-rate run all 2,357,138,315 bytes (156,195 packets) were copied across the boundary; matching only decided afterwards whether to count them. This is the structure the paper attributes to NIT: "a copy of each packet is always made, and many CPU cycles will be wasted copying unwanted packets" (paper.txt L103-104), and "copies packets then runs the filter over the copies. Thus the cost of running NIT increases with packet size even when the packet is discarded by the filter" (paper.txt L207-209).
2. **One system call per packet.** The paper says it "is not possible to do a read system call per packet" and BPF "must collect the data from several packets and return it as a unit" (paper.txt L144-146). Our loop is exactly the per-packet read the paper rules out: 156,195 `recvfrom` calls delivered in the full-rate run. The visible consequence is loss: 51.18% of packets that reached the socket were dropped because the loop could not drain it (`kernel_drops` above).
3. **Header handling in user space.** Each delivered packet also pays a user-space `memcpy` of the Ethernet, IP and TCP/UDP headers plus the bounds checks. This is small next to (1) and (2) but is cost BPF avoids by filtering in place (paper.txt L90-94).
4. **Alignment.** The Ethernet header is 14 bytes, so the IP header lands 2-byte aligned in the receive buffer; the paper's footnote makes the same point about NIT (paper.txt L225-234). We sidestep it by `memcpy`ing headers out rather than casting.

Not measured in Phase 2: CPU time or nanoseconds per packet, and the kernel-internal part of the cost (what the kernel does for AF_PACKET before the copy). Anything about those would be UNVERIFIED; Phase 2 records counts, bytes and drops only.

## Which claims this baselines (CLAIMS.md)

- **C3 "accept all", copy slope and per-packet cost (Fig. 2, paper.txt L186-189, L207-211).** Closest match: in both runs almost every packet matches (42 of 10,783 and 2 of 156,195 do not), so the sniffer behaves like an accept-all capture. This run gives the inputs of the C3 fit (bytes copied per packet: mean 7,004 paced, 15,091 full-rate; one syscall per packet) but not yet the fit itself, since no per-packet time was recorded.
- **C2 "reject all", flat cost vs packet size (Fig. 3, paper.txt L219-221).** The design cannot be flat: every packet pays the syscall and copy whether or not it matches (points 1-2). But this run barely offered any rejectable traffic, so the C2 cost is **not** measured here; it needs non-matching traffic at varied sizes in a later phase.
- **C4 end-to-end vs NIT (paper.txt L29-30).** This binary plays the NIT role (copy everything, filter in user space). Its full-rate loss (51.18% in run 3, 20.50% in the commit-time rerun; see below) is the user-visible baseline a kernel-side filter has to beat; no speed-up ratio is claimed from Phase 2.
- **C1 (register vs stack machine) and C5 (in-kernel VM):** not baselined by Phase 2 (no filter machine here); C5's "no in-kernel code" case is only implied by points 1-2.

## Rerun at commit time (CLAUDE.md workflow rule)

`sudo bash scripts/rerun_verifies.sh` re-ran both verify scripts. Phase 2 wrote to `logs/p2_rerun/` so the logs cited above were not overwritten; summary: `logs/p2_rerun_summary.log`.
- Phase 1 verify: 0 FAIL (`logs/phase1_verify_rerun.log`).
- Phase 2 paced: **PASS**. Sniffer matched 10,699 = tcpdump received-by-filter 10,699 (again exactly equal); captured 10,692 with 7 tcpdump drops; abs_diff 7, allowance 60; no sniffer drops (`logs/p2_rerun/p2_crosscheck.log`).
- Phase 2 full-rate: **INCONCLUSIVE** again. Sniffer dropped 84,644 of 412,809 packets (**20.50%**), versus 51.18% in run 3 with the same binary and script. So the full-rate loss figure is not stable between runs (plausibly it depends on how many large TCP packets iperf3 pushes before the receive queue fills; not investigated, UNVERIFIED). Quote it as a range, 20.50% to 51.18% over two runs, not as one number. The kernel_packets vs tcpdump received-by-filter agreement held (412,809 vs 412,805).
- The full-rate rerun leaves a 1.9 GB root-owned `logs/p2_rerun/p2_full_capture.pcap` (git-ignored via `*.pcap`).
