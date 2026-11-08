#!/usr/bin/env bash
# p10_api_check.sh - CLAUDE.md API discipline for Phase 10: grep the installed headers for every symbol the Phase 10 tools use, print file:line, and
# append the hits to CODE_NOTES.md (section "Phase 10"). A symbol that is absent from the headers must not be used: the script fails loudly.
# Usage: bash scripts/p10_api_check.sh 2>&1 | tee logs/p10/p10_api_check.log
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
OUT=logs/p10/p10_api_check.hits; rm -f "$OUT"
fail=0
hit() { # hit <symbol> <regex> <file...>: first matching line per file
    local sym="$1" re="$2"; shift 2
    local found=0 f
    for f in "$@"; do
        [[ -f "$f" ]] || continue
        local l; l=$(grep -nE -m1 "$re" "$f" || true)
        if [[ -n "$l" ]]; then echo "$sym | $f:${l%%:*} | $(echo "${l#*:}" | sed 's/^[ \t]*//' | cut -c1-120)" >> "$OUT"; found=1; fi
    done
    if [[ $found -eq 0 ]]; then echo "MISSING: $sym (regex $re)" | tee -a "$OUT"; fail=$((fail+1)); fi
}
BPFH=/usr/include/bpf/bpf.h; LBH=/usr/include/bpf/libbpf.h; KBPF=/usr/include/linux/bpf.h
SOCK=$(ls /usr/include/asm-generic/socket.h /usr/include/*/asm/socket.h 2>/dev/null | head -2)
hit bpf_prog_test_run_opts 'bpf_prog_test_run_opts\(' $BPFH
hit struct_bpf_test_run_opts 'struct bpf_test_run_opts' $BPFH
fieldhit() { # fieldhit <field>: first line of the field inside struct bpf_test_run_opts (not in the deprecated struct bpf_prog_test_run_attr)
    local l; l=$(awk -v f="$1" '/^struct bpf_test_run_opts \{/ {s=1} s && $0 ~ f {print NR": "$0; exit} s && /^};/ {exit}' $BPFH)
    if [[ -n "$l" ]]; then echo "bpf_test_run_opts.$1 | $BPFH:${l%%:*} | $(echo "${l#*: }" | sed 's/^[ \t]*//' | cut -c1-100)" >> "$OUT"; else echo "MISSING: bpf_test_run_opts.$1" | tee -a "$OUT"; fail=$((fail+1)); fi
}
for fld in 'data_in;' 'data_size_in;' 'data_size_out;' 'repeat;' 'duration;' 'retval;' 'batch_size;'; do fieldhit "$fld"; done
hit BPF_PROG_TEST_RUN 'BPF_PROG_TEST_RUN' $KBPF
hit BPF_PROG_TYPE_SOCKET_FILTER 'BPF_PROG_TYPE_SOCKET_FILTER' $KBPF
hit libbpf_set_print 'libbpf_set_print\(' $LBH
hit bpf_object__open_file 'bpf_object__open_file\(' $LBH
hit bpf_object__load 'bpf_object__load\(' $LBH
hit bpf_object__find_program_by_name 'bpf_object__find_program_by_name\(' $LBH
hit bpf_program__fd 'bpf_program__fd\(' $LBH
hit SO_ATTACH_BPF 'define[ \t]+SO_ATTACH_BPF' $SOCK
hit SO_RCVBUFFORCE 'define[ \t]+SO_RCVBUFFORCE' $SOCK
hit SO_BINDTODEVICE 'define[ \t]+SO_BINDTODEVICE' $SOCK
hit SOL_PACKET 'define[ \t]+SOL_PACKET' /usr/include/linux/socket.h /usr/include/*/bits/socket.h /usr/include/*/bits/socket-constants.h
hit PACKET_STATISTICS 'define[ \t]+PACKET_STATISTICS' /usr/include/linux/if_packet.h
hit struct_tpacket_stats 'struct tpacket_stats' /usr/include/linux/if_packet.h
hit sendmmsg 'sendmmsg' /usr/include/*/sys/socket.h /usr/include/sys/socket.h
hit struct_mmsghdr 'struct mmsghdr' /usr/include/*/sys/socket.h
hit recvmmsg 'recvmmsg' /usr/include/*/sys/socket.h /usr/include/sys/socket.h
hit SYS_setns 'define[ \t]+SYS_setns' /usr/include/*/bits/syscall.h
hit syscall 'extern long int syscall' /usr/include/unistd.h
hit CLONE_NEWNET 'CLONE_NEWNET' /usr/include/*/bits/sched.h /usr/include/linux/sched.h
hit clock_gettime 'clock_gettime' /usr/include/time.h
hit CLOCK_MONOTONIC_RAW 'CLOCK_MONOTONIC_RAW' /usr/include/linux/time.h /usr/include/*/bits/time.h
hit clock_nanosleep 'clock_nanosleep' /usr/include/time.h
hit sched_setaffinity 'sched_setaffinity' /usr/include/sched.h /usr/include/*/bits/sched.h
hit MSG_DONTWAIT 'MSG_DONTWAIT' /usr/include/*/bits/socket.h /usr/include/linux/socket.h
hit ETH_P_ALL 'define[ \t]+ETH_P_ALL' /usr/include/linux/if_ether.h
if [[ $fail -ne 0 ]]; then echo "FAIL: $fail symbols missing from the installed headers; do not use them"; exit 1; fi
cat "$OUT"
{
    echo
    echo "## Phase 10 (p10_api_check.sh, $(date -Is)): symbols checked in the installed headers before first use (logs/p10/p10_api_check.hits)"
    echo '```'
    cat "$OUT"
    echo '```'
} >> CODE_NOTES.md
echo "appended $(wc -l < "$OUT") hits to CODE_NOTES.md"
