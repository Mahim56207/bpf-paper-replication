# DEVIATIONS

## Phase 2

Format: what / why / taken or not.

- **D2.1 veth pair recreated.** The Phase 2 prompt assumed p1veth0/p1veth1 exist (DOWN) from Phase 1. They do not: scripts/phase1_verify.sh ends its veth check with `ip link del p1veth0`, and `ip -br link show` at the start of Phase 2 listed only `lo` and `enp0s8` (logs/p2_pre_state.log). scripts/phase2_verify.sh creates the pair. Taken.
- **D2.2 tcpdump used as the cross-check oracle** (as instructed). It is a live tool, not a file in reference/. Taken.
- **D2.3 tcpdump invocation changed.** Prompt: `tcpdump -i p1veth0 port 4040 -c 100 | tail -1`. Problem: tcpdump prints its "N packets captured" summary on stderr, so `| tail -1` on stdout would log the last packet line, not a count; and `-c 100` stops after 100 packets while the sniffer counts every packet in a 5 s run, so the two numbers would not be comparable. Used instead: full-window capture (`-nn "port 4040" -w /dev/null`, started before traffic, stopped after 3 s of quiescence) with stderr captured to logs/p2_tcpdump.log. Taken.
- **D2.4 sniffer output goes to a file, not `| tee &`.** A background pipeline gives no clean PID to stop; the script redirects to logs/p2_run.log (which the outer `| tee logs/p2_verify.log` also shows). The sniffer calls fflush after each line so it also behaves when piped. Taken.
- **D2.5 additions beyond the prompt.** A short iperf3 UDP run (50 Mbit/s, 2 s) so the UDP branch of the matcher is exercised, and a `truncated` counter in the sniffer. Taken.
- **D2.6 sudo.** Passwordless sudo is not configured on this machine (`sudo -n true` fails); privileged scripts are run in the user's Terminal tabs and the user types the password. Not a design change.
- **D2.7 Topology (supersedes the prompt's addressing).** Prompt: both 10.0.0.1 and 10.0.0.2 on p1veth0/p1veth1 in the root namespace. Evidence it does not carry traffic over the veth: `ip route get` says `local ... dev lo`, 57 packets and 0 matched on p1veth0 while iperf3 moved 9.94 GBytes (logs/p2_stageA*.log). Used instead: p1veth1 in namespace `p2ns` with 10.0.0.2/24, iperf3 server inside it. Taken.
- **D2.8 tcpdump runs as a systemd unit.** The terminal's processes carry the AppArmor label `claude-desktop`; tcpdump's profile accepts signals only from `unconfined` (abstractions/base:146), so root's kill and pkill got EPERM and the verify script hung (runs 1 and 2; logs/p2_h1_tcpdump_term.log, logs/p2_run1_verify.log). `systemd-run` / `systemctl stop` are used. Taken.
- **D2.9 Verification split into paced and full-rate runs, INCONCLUSIVE rule added** (docs/phase2_notes.md, "Amendment"). Taken.
- **D2.10 Stale logs.** logs/p2_run1_*.log are run 1 (full rate, tcpdump never stopped); logs/p2_run2_partial_crosscheck.log is run 2 (hung, counts computed by hand; its pcap and sniffer log were overwritten by run 3). Kept as history, not used for results.
- **D2.11 `scripts/p2_h1_tcpdump_term_test.sh`** was interrupted after variant A; variants B and C have no result. Not rerun: the cause was identified from variant A plus `ps -Z` and the AppArmor profile.
