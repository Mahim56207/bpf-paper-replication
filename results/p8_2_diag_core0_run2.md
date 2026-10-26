# Phase 8.2: core-0 attribution per config (informational), run set run2

Per config, over the final unprofiled runs: mean busy rate of core 0 (from `/proc/stat`) and the mean CPU-s/s of the tasks whose last CPU in the closing snapshot was 0 (tick differences between the two snapshots, so tasks that moved between CPUs are approximate), plus the memory pressure stall delta.

## N (n=6 runs)

Core 0 busy (mean) **0.016** CPU-s/s (per run: 0.013, 0.010, 0.012, 0.022, 0.021, 0.017); tasks attributed to core 0 sum to **0.014**; memory 'some' stall: 0.0000 s per s.

| task (comm) | mean CPU-s/s on core 0 | runs in which it appears |
|---|---|---|
| claude-desktop | 0.0048 | 6 of 6 |
| claude | 0.0038 | 5 of 6 |
| gnome-shell | 0.0027 | 2 of 6 |
| kworker/u20:0-events_unbound | 0.0012 | 3 of 6 |
| dbus-daemon | 0.0005 | 3 of 6 |
| kworker/u20:1-kvfree_rcu_reclaim | 0.0003 | 1 of 6 |
| kworker/u20:3-events_unbound | 0.0003 | 1 of 6 |
| systemd-logind | 0.0002 | 1 of 6 |
| systemd | 0.0002 | 1 of 6 |

## A (n=6 runs)

Core 0 busy (mean) **0.036** CPU-s/s (per run: 0.033, 0.030, 0.030, 0.044, 0.043, 0.039); tasks attributed to core 0 sum to **0.031**; memory 'some' stall: 0.0000 s per s.

| task (comm) | mean CPU-s/s on core 0 | runs in which it appears |
|---|---|---|
| claude-desktop | 0.0131 | 6 of 6 |
| claude | 0.0080 | 6 of 6 |
| gnome-shell | 0.0052 | 6 of 6 |
| kworker/u20:4-events_unbound | 0.0005 | 1 of 6 |
| kworker/u20:0-events_power_efficient | 0.0005 | 2 of 6 |
| kworker/u20:3-flush-8:0 | 0.0003 | 1 of 6 |
| kworker/u20:0-flush-8:0 | 0.0003 | 1 of 6 |
| kworker/u20:3-events_freezable_pwr_efficient | 0.0003 | 1 of 6 |
| systemd-oomd | 0.0003 | 2 of 6 |
| kworker/u20:2-kvfree_rcu_reclaim | 0.0003 | 1 of 6 |
| kworker/u20:0-events_unbound | 0.0003 | 1 of 6 |
| kworker/u20:2-events_freezable_pwr_efficient | 0.0003 | 1 of 6 |

## B (n=6 runs)

Core 0 busy (mean) **0.033** CPU-s/s (per run: 0.033, 0.032, 0.037, 0.035, 0.034, 0.029); tasks attributed to core 0 sum to **0.027**; memory 'some' stall: 0.0000 s per s.

| task (comm) | mean CPU-s/s on core 0 | runs in which it appears |
|---|---|---|
| claude-desktop | 0.0125 | 6 of 6 |
| claude | 0.0071 | 6 of 6 |
| gnome-shell | 0.0033 | 6 of 6 |
| kworker/u20:3-events_unbound | 0.0005 | 1 of 6 |
| kworker/u20:2-events_power_efficient | 0.0005 | 2 of 6 |
| kworker/u20:1-events_unbound | 0.0003 | 1 of 6 |
| rcu_preempt | 0.0003 | 2 of 6 |
| kworker/u20:0-kvfree_rcu_reclaim | 0.0003 | 1 of 6 |
| VBoxDRMClient | 0.0003 | 2 of 6 |
| kworker/u20:2-events_freezable_pwr_efficient | 0.0003 | 1 of 6 |
| bash | 0.0002 | 1 of 6 |
| kcompactd0 | 0.0002 | 1 of 6 |

## C (n=6 runs)

Core 0 busy (mean) **0.015** CPU-s/s (per run: 0.016, 0.015, 0.016, 0.011, 0.019, 0.015); tasks attributed to core 0 sum to **0.014**; memory 'some' stall: 0.0000 s per s.

| task (comm) | mean CPU-s/s on core 0 | runs in which it appears |
|---|---|---|
| claude-desktop | 0.0052 | 5 of 6 |
| gnome-shell | 0.0048 | 4 of 6 |
| claude | 0.0032 | 5 of 6 |
| kworker/u20:1-events_unbound | 0.0003 | 1 of 6 |
| kworker/u20:4-events_power_efficient | 0.0003 | 1 of 6 |
| VBoxDRMClient | 0.0002 | 1 of 6 |
| systemd | 0.0002 | 1 of 6 |
| kworker/u20:1-kvfree_rcu_reclaim | 0.0002 | 1 of 6 |

