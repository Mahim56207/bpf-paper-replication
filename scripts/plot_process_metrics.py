#!/usr/bin/env python3
"""Plot process-level metrics: Capture Process CPU % and Context Switches / sec.
Shows the undeniable operational benefit of in-kernel BPF filtering vs user-space copy-then-filter.
"""
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"

# Data parsed from results/summary.md (Reject curve: non-matching UDP)
sizes = [64, 256, 512, 1024, 1500]

# Capture process CPU %
cpu_A = [10.7, 11.3, 10.9, 11.2, 11.3]
cpu_B = [0.0, 0.0, 0.0, 0.0, 0.0]

# Process context switches per second
cs_proc_A = [7456, 7767, 7678, 7674, 7696]
cs_proc_B = [1, 1, 1, 1, 1]

# System context switches per second
cs_sys_A = [44793, 46963, 46265, 46380, 46465]
cs_sys_B = [32182, 32182, 32213, 32198, 32185]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

# Panel 1: Capture Process CPU %
x = np.arange(len(sizes))
width = 0.35

rects1 = ax1.bar(x - width/2, cpu_A, width, label='A: User-space (copy-then-filter)', color='#dc2626')
rects2 = ax1.bar(x + width/2, cpu_B, width, label='B: In-kernel eBPF filter', color='#2563eb')

ax1.set_ylabel('Capture Process CPU Utilization (%)', fontsize=11, fontweight='bold')
ax1.set_xlabel('Frame Size (bytes)', fontsize=11, fontweight='bold')
ax1.set_title('Capture Process CPU Utilization (Reject Curve)', fontsize=12, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(sizes)
ax1.set_ylim(0, 15)
ax1.grid(axis='y', linestyle='--', alpha=0.5)
ax1.legend(frameon=True, facecolor='white', edgecolor='#cbd5e1')

# Add values above bars
for rect in rects1:
    h = rect.get_height()
    ax1.annotate(f'{h:.1f}%',
                xy=(rect.get_x() + rect.get_width() / 2, h),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=9, fontweight='bold')

for rect in rects2:
    ax1.annotate('0.0%',
                xy=(rect.get_x() + rect.get_width() / 2, 0),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=9, fontweight='bold', color='#1e40af')

# Panel 2: Context Switches / sec
ax2.plot(sizes, cs_proc_A, 'o-', color='#dc2626', linewidth=2.5, markersize=8, label='A: Capture Process cs/s')
ax2.plot(sizes, cs_proc_B, 's-', color='#2563eb', linewidth=2.5, markersize=8, label='B: Capture Process cs/s (1 cs/s)')

ax2.set_ylabel('Process Context Switches / second', fontsize=11, fontweight='bold')
ax2.set_xlabel('Frame Size (bytes)', fontsize=11, fontweight='bold')
ax2.set_title('Process Context Switch Rate (Reject Curve)', fontsize=12, fontweight='bold')
ax2.grid(True, linestyle='--', alpha=0.5)
ax2.set_ylim(-500, 9500)
ax2.legend(frameon=True, facecolor='white', edgecolor='#cbd5e1')

for s, v in zip(sizes, cs_proc_A):
    ax2.annotate(f'{v:,}/s', (s, v), textcoords="offset points", xytext=(0, 7), ha='center', fontsize=9, fontweight='bold')
for s, v in zip(sizes, cs_proc_B):
    ax2.annotate(f'{v}/s', (s, v), textcoords="offset points", xytext=(0, 7), ha='center', fontsize=9, fontweight='bold', color='#1e40af')

plt.tight_layout()
out_path = RES / "fig_process_metrics.png"
plt.savefig(out_path)
print(f"Wrote {out_path}")
