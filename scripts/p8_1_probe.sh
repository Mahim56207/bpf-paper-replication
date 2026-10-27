#!/usr/bin/env bash
# Phase 8.1 step 1: re-probe the machine state with real commands (no root, changes nothing).
# Usage: bash scripts/p8_1_probe.sh <label>   -> logs/p8/p8_1/p8_1_probe_<label>.log (deleted first, checked after)
# Every command is logged with its exit status; stderr goes into the log, nothing is discarded.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
label="${1:?usage: p8_1_probe.sh <label>}"
out="logs/p8/p8_1/p8_1_probe_${label}.log"
mkdir -p logs/p8/p8_1
rm -f "$out"
run() { { echo; echo "\$ $*"; bash -c "$*" 2>&1; echo "[rc=$?]"; } >> "$out"; }
{ echo "# Phase 8.1 probe label=$label start=$(date -Is) user=$(id -un) uid=$EUID"; } >> "$out"

run "uname -srm; hostname"
run "nproc; lscpu | grep -E 'Model name|^CPU\\(s\\)|Thread|Core|Socket|Vendor|Hypervisor|Virtualization'"
run "cat /proc/loadavg; uptime"
run "cat /proc/pressure/cpu"
run "echo XDG_SESSION_TYPE=\${XDG_SESSION_TYPE:-unset} DISPLAY=\${DISPLAY:-unset} WAYLAND_DISPLAY=\${WAYLAND_DISPLAY:-unset} XDG_SESSION_ID=\${XDG_SESSION_ID:-unset} SSH_CONNECTION=\${SSH_CONNECTION:-unset} SSH_TTY=\${SSH_TTY:-unset}; tty"
run "loginctl list-sessions --no-pager"
run "for s in \$(loginctl list-sessions --no-legend | awk '{print \$1}'); do echo \"-- session \$s\"; loginctl show-session \$s -p Id -p User -p Type -p Class -p State -p Remote -p Service -p TTY -p Display -p Active --no-pager; done"
run "who -a"
run "systemctl get-default; systemctl list-units --type=target --state=active --no-pager"
run "systemctl list-units --type=service --state=running --no-pager"
run "systemctl --user list-units --type=service --state=running --no-pager"
run "top -b -n 1 -o %CPU -w 200 | head -30"
run "ps -eo pid,ppid,pcpu,pmem,etime,time,psr,stat,comm --sort=-pcpu | head -25"
run "ps -eo pid,ppid,pcpu,etime,time,psr,comm --sort=-time | head -20"
run "ps -eo pid,pcpu,rss,comm,args --sort=-rss | head -15 | cut -c1-200"
run "ps -eo pid,comm | grep -Ei 'gnome|Xorg|Xwayland|gdm|lightdm|sddm|kwin|plasma|mutter|tracker|snapd|packagekit|unattended|apport|whoopsie|cups|avahi|modemmanager|NetworkManager|claude|chrome|firefox|electron|code' | head -40"
run "ls -d /sys/devices/system/cpu/cpu0/cpufreq /sys/devices/system/cpu/cpufreq 2>&1; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>&1; cat /sys/devices/system/cpu/cpuidle/current_governor 2>&1"
run "cat /sys/devices/system/cpu/online /sys/devices/system/cpu/isolated /sys/devices/system/cpu/nohz_full 2>&1; cat /proc/cmdline"
run "cat /sys/kernel/mm/transparent_hugepage/enabled 2>&1; cat /proc/sys/kernel/numa_balancing 2>&1; cat /proc/sys/kernel/sched_autogroup_enabled 2>&1"
run "systemctl list-timers --no-pager | head -15"
run "cat /proc/interrupts | awk 'NR==1 || /timer|IPI|virtio|eth|enp/' | head -20"
run "vmstat 1 6"
run "python3 -I scripts/p8_1_cpu_window.py 10"

if [[ ! -s "$out" ]]; then echo "FATAL: $out was not created" >&2; exit 1; fi
echo "# end=$(date -Is)" >> "$out"
echo "probe written: $out ($(wc -l < "$out") lines)"
