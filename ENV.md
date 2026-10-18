# ENV.md - environment probe (Phase 0)

Raw log: logs/phase0_env_probe.log. Values are exactly as printed.

| key | command | observed value |
|---|---|---|
| kernel | `uname -r` | `6.17.0-19-generic` |
| clang | `clang --version \| head -1` | `bash: line 1: clang: command not found` |
| libbpf (pkg-config) | `pkg-config --modversion libbpf` | `bash: line 1: pkg-config: command not found` |
| bpftool | `bpftool version` | `bpftool v7.7.0` / `using libbpf v1.7` / `features:` |
| bpf_jit_enable | `cat /proc/sys/net/core/bpf_jit_enable` | `1` |
| nproc | `nproc` | `5` |
| BTF | `ls -l /sys/kernel/btf/vmlinux` | `-r--r--r-- 1 root root 7923950 Oct 18 15:21 /sys/kernel/btf/vmlinux` |

## Gaps
- UNVERIFIED: installed libbpf version for compilation. `pkg-config` is absent, so the libbpf *library/headers* version is unknown. bpftool reports it is built against libbpf v1.7, which is not necessarily what is in /usr/include/bpf/.
- clang is not installed, so no BPF C can be compiled yet.
