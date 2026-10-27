# Phase 8.1: findings (quiet measurement setup)

Numbers marked with backticks are copied from `results/p8_1_idle_table.md`, which `scripts/p8_1_stats.py` computes from the run logs; `scripts/p8_1_verify.sh` checks that each of them occurs there. Raw evidence: `logs/p8/p8_1/` (probe log, three idle sets with their run logs). The idle-window definition is the Phase 6 one (config D capture process, classifier tap, pidstat, vmstat, `/proc/stat` snapshots, no traffic, 10 s; system-wide busy = user+nice+system+irq+softirq+steal). Nothing in that definition was changed. One thing was added: the optional `settle` pause of `scripts/p8_1_idle.sh` before the first window (plain `sleep`), introduced after the first two sets showed that activity during the windows dominates the result; the old numbers are kept in the table next to the new ones.

## 1. State of the machine (probe `logs/p8/p8_1/p8_1_probe_current_desktop.log`, taken 13:35)

- Graphical session: GDM, Wayland, session on `tty2` (`loginctl`: Type=wayland, Service=gdm-password, Remote=no), default target `graphical.target`. `tty` is "not a tty" for the tool shell; no SSH variables.
- 5 vCPUs (Apple model, VirtualBox guest additions running), no CPU-frequency directory under `/sys/devices/system/cpu/cpu0/cpufreq` (no governor to set), cpuidle governor `menu`.
- Running: `gnome-shell` (top consumer: 90.9% in the `top` snapshot, 19.1% averaged over its life), Firefox with several content processes (about 1.2 GB RSS in one of them), the Claude desktop app and its `claude` CLI processes, 31 system services and 49 user services (Tracker/localsearch, Evolution, GNOME settings daemons, PipeWire, snapd, CUPS, Avahi, ModemManager and others).
- Memory pressure: 5.3 GB RAM, swap almost full (`free` before the idle sets: 3788 MB of 4095 MB used), `kswapd0`/`kcompactd0` and writeback kworkers in the CPU list.
- Timers: `sysstat-collect.timer` every 10 minutes, `anacron`, apt/fwupd/motd timers (hours apart).
- A 10 s window without the harness during that probe: 1.48 CPU-s/s system-wide, 0.60 on cores {0,1} (probe log, last section).

## 2. Idle windows (table: `results/p8_1_idle_table.md`)

| window set | what was going on | result |
|---|---|---|
| Phase 6 quiet calibration | recorded earlier | idle `0.131`, canary max `0.0689` on {0,1} |
| Phase 6 matrix start (noisy) | recorded earlier | idle `0.843` |
| Phase 8.1 desktopnow | windows run while the assistant was issuing commands and text | idle mean `0.801`, all 3 over the V8 limit |
| Phase 8.1 desktopquiet | windows 1 and 2 overlapped the user's reply and the assistant's replies; window 3 started after the assistant's turn had ended | window 3 idle `0.1209`, canary {0,1} `0.0490`; windows 1 and 2 about 1.1 and 1.3 |
| Phase 8.1 desktopsettled | 60 s pause after the password, then 3 windows; one silent watcher process (`pgrep` every 20 s) and no assistant output during the windows | idle mean `0.126`, canary {0,1} max `0.0569` (V8 limit `0.0826`), 0 of 3 windows over the limit |

Timing of the overlaps comes from the session transcript (not from a script) and is therefore approximate; the window start times are in the run logs (`stat_before` timestamps).

## 3. What this says

1. **The desktop itself, left alone, is as quiet as the Phase 6 calibration session**: the settled set (`0.126`) is the same as the quiet calibration (`0.131`) within the spread of its windows, with all three windows under the V8 canary limit, in the same graphical session with GNOME, Firefox and the Claude app open.
2. **The noise in the other sets coincides with activity in the interactive session.** This is a hypothesis resting on my recollection of the session (when I issued commands and text, when you replied or clicked), not a tested cause: no run varied the activity under control, no per-process attribution was recorded during the windows, and the overlap times were not logged by a script. Swap use was a second, unexamined candidate: 3788 of 4095 MB were in use before the first idle set (3780 and 3777 MB before the later two; `free -m` in each `context.txt`), and it was not varied either. What was observed in the noisy windows, which I associate with the assistant issuing commands and streaming text and the user clicking and typing, is about 6 times the quiet level on average (up to 10 times in single windows), on all five CPUs about equally (per-CPU columns in the table). The `top` snapshot taken during activity shows `gnome-shell` and the Claude app's renderer and GPU processes as the consumers. That is consistent with the Phase 6 observation (D6.10) that the load was concentrated in the first minutes of the matrix and then disappeared, but whether the Phase 6 matrix start was the same cause is UNVERIFIED; so is which process is responsible in detail (no per-process attribution was recorded during the windows).
3. **Consequence for the benchmark phases**: no system change is needed to reach the quiet level. What matters is that nothing interactive happens while measurements run (no assistant output, no mouse or keyboard use in the desktop), that a settle pause precedes the first window, and that V8 stays on as the guard. Only one set was measured under these conditions (3 windows); a longer hands-off period, such as a matrix of about 40 minutes, has not been tested here.
4. The tty/ssh variant of step 2 was not run: no separate login was available.
