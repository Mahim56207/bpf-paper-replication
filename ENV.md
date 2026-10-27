# ENV.md - environment (updated after Phase 1)

Raw logs: logs/phase0_env_probe.log (Phase 0 probe, before setup), logs/phase1_env_reprobe.log (this table), logs/phase1_verify.log (verify run). Values are exactly as printed.

## Verified after Phase 1 (logs/phase1_env_reprobe.log)

| key | command | observed value |
|---|---|---|
| kernel | `uname -r` | `6.17.0-19-generic` |
| CPU arch | `uname -m` | `aarch64` |
| dpkg arch | `dpkg --print-architecture` | `arm64` |
| clang | `clang --version \| head -1` | `Ubuntu clang version 20.1.8 (0ubuntu4)` |
| libbpf (pkg-config) | `pkg-config --modversion libbpf` | `1.6.2` |
| libbpf-dev package | `dpkg-query -W libbpf-dev` | `libbpf-dev 1:1.6.2-1` |
| libbpf header version | `grep LIBBPF_(MAJOR\|MINOR)_VERSION /usr/include/bpf/libbpf_version.h` | `MAJOR 1`, `MINOR 6` |
| bpftool | `bpftool version` | `bpftool v7.7.0` / `using libbpf v1.7` / `features:` |
| bpftool path | `command -v bpftool` | `/usr/sbin/bpftool` |
| bpf_jit_enable (live) | `cat /proc/sys/net/core/bpf_jit_enable` | `1` |
| bpf_jit_enable (persisted) | `cat /etc/sysctl.d/99-bpf-repl.conf` | `net.core.bpf_jit_enable = 1` |
| nproc | `nproc` | `5` |
| BTF | `ls -l /sys/kernel/btf/vmlinux` | `-r--r--r-- 1 root root 7923950 Oct 18 15:21 /sys/kernel/btf/vmlinux` |
| veth | `lsmod \| grep -m1 '^veth'` | `veth                   36864  0` |

## Notes
- libbpf API surface for this repo (CLAUDE.md rule) = the installed headers, libbpf 1.6.x (package 1:1.6.2-1). bpftool's "using libbpf v1.7" is the libbpf bundled inside the bpftool binary, a different thing from the libbpf we compile against; do not use it for API questions.
- The machine is arm64 (aarch64), not x86. Anything arch-specific (BPF target arch defines, syscall/register names, asm includes) must be checked against this, not assumed.
- Phase 0 gaps (clang missing, libbpf version unknown) are resolved by the rows above; the pre-setup probe is kept in logs/phase0_env_probe.log.
- Phase 1 verify: 0 FAIL on the first run, logs/phase1_verify.log. Includes a real `bpftool prog load` of a trivial XDP program through the verifier and a veth pair create/delete.

## Added in Phase 2
- Processes started from the Claude desktop terminal are labelled `claude-desktop (unconfined)` (`cat /proc/self/attr/current` in logs/p2_apparmor_probe.log; the labels of the sudo chain and of the stuck tcpdump (`claude-desktop (unconfined)` vs `tcpdump (enforce)`) were shown in-session but not logged). tcpdump runs as `tcpdump (enforce)` and its profile accepts signals only from `unconfined` peers (/etc/apparmor.d/abstractions/base:146), so root's `kill`/`pkill` on tcpdump fails with EPERM from here. Workaround in use: `systemd-run` / `systemctl stop` (see DEVIATIONS.md D2.8).
- `sudo` needs a password here (`sudo -n true` fails); privileged scripts run in the user's Terminal tabs.
- Lab network (left up after Phase 2): `p1veth0` 10.0.0.1/24 in the root namespace, `p1veth1` 10.0.0.2/24 in namespace `p2ns`. Remove with `sudo bash scripts/phase2_verify.sh teardown`.

## Platform limitation recorded in Phase 3 (reviewer ruling, DEVIATIONS D3.6)
- `bpftool prog dump jited pinned ...` prints `Error: No JIT disassembly support` on this arm64 machine (logs/p3_verify.log, logs/p3_v2a_no_prefix/p3_verify.log). The JIT itself works: `bpftool prog show` reports `jited 680B` for the Phase 3 program with `bpf_jit_enable=1`. Machine code of JIT-compiled programs cannot be inspected here with bpftool.

## Phase 6 matrix session mode (reviewer ruling 3, D3; release condition f)
Matrix runs performed in the graphical session. GUI noise mitigated by the V8 canary rule and idle-subtraction (idle baseline 0.131 CPU-s/s, down from 1.0 to 2.7 CPU-s/s in the first smoke runs; canary_max 0.0689 CPU-s/s on cores {0,1}, 0.0369 on core {0}; results/baseline_calibration.json). Attempting a non-graphical session (`systemctl isolate multi-user.target`) was deemed too risky for workflow continuity: it would end the desktop app session this work runs in.

## Phase 8 session (2026-10-25, aarch64 VM; raw: logs/p8/p8_env_probe.log, logs/p8/p8_post_install_probe.log)
Re-probed with real commands; the older rows above were not reused. Values as printed.

| key | command | observed value |
|---|---|---|
| kernel / arch | `uname -srm` | `Linux 6.17.0-19-generic aarch64` |
| dpkg arch | `dpkg --print-architecture` | `arm64` |
| gcc | `gcc --version \| head -1` | `gcc (Ubuntu 15.2.0-4ubuntu4) 15.2.0` |
| clang | `clang --version \| head -1` | `Ubuntu clang version 20.1.8 (0ubuntu4)` |
| libbpf | `pkg-config --modversion libbpf` | `1.6.2` (`libbpf-dev:arm64 1:1.6.2-1`) |
| bpftool | `bpftool version` | `bpftool v7.7.0` / `using libbpf v1.7` |
| perf | `perf --version` | `perf version 6.17.13` |
| valgrind | `valgrind --version` | `valgrind-3.25.1` (installed this session, `1:3.25.1-0ubuntu1`) |
| stress-ng | `stress-ng --version` | `stress-ng, version 0.19.03 (gcc 15.1.0, aarch64 Linux 6.17.0-19-generic)` (installed this session) |
| tcpdump / libpcap runtime | `tcpdump --version` | `tcpdump version 4.99.5`, `libpcap version 1.10.5 (with TPACKET_V3)` |
| libpcap-dev | `pkg-config --modversion libpcap` | `1.10.5` (`libpcap-dev:arm64 1.10.5-2ubuntu2`, installed this session) |
| python3 | `python3 --version` | `Python 3.13.7` |
| nproc | `nproc` | `5` |
| perf_event_paranoid | `cat /proc/sys/kernel/perf_event_paranoid` | `4` |
| bpf_jit_enable | `cat /proc/sys/net/core/bpf_jit_enable` | `1` |
| sudo | `sudo -n true` | `sudo-rs: interactive authentication is required` (password needed; apt run in the user's Terminal tab, `logs/p8/p8_apt_install.log`) |

Notes: the Phase 6c environment (D6c.1) was an x86_64 container with gcc 13.3.0, valgrind 3.22.0, libpcap 1.10.4, tcpdump 4.99.4; the compiler, valgrind and libpcap versions all differ from this VM.
