#!/usr/bin/env python3
"""Checks the WP1b smoke stage: every plan row has a log whose RC is 0 and whose RESULT line has the right number of fields, a measured wall time of at least MIN_S, a thread
CPU time, and (drain) no drops. Exit 1 with the reason otherwise. Usage: python3 -I scripts/p10b_check_smoke.py SMOKE_DIR PLAN MIN_S"""
import glob, os, re, sys
d, plan, min_s = sys.argv[1], sys.argv[2], float(sys.argv[3])
nf = {"memcpy": 7, "tr_reject": 10, "tr_accept": 10, "tr_port": 10, "dr_U": 14, "dr_E": 14, "dr_B": 14}
wall = {"memcpy": 5, "tr_reject": 7, "tr_accept": 7, "tr_port": 7, "dr_U": 13, "dr_E": 13, "dr_B": 13}
bad = 0
for l in open(plan):
    if l.startswith("#") or not l.strip():
        continue
    seq, kind, size, batch = l.split()
    fs = sorted(glob.glob(f"{d}/b{seq}_a*.log"))
    if not fs:
        print(f"FAIL: no log for plan row {seq} ({kind})"); bad += 1; continue
    t = open(fs[-1]).read()
    rc = re.search(r"^RC (\d+)", t, re.M)
    res = re.search(r"^RESULT (.*)$", t, re.M)
    f = res[1].split(",") if res else []
    ok = bool(rc) and rc[1] == "0" and len(f) == nf[kind] and float(f[wall[kind]]) >= min_s
    if kind.startswith("dr_") and ok:
        ok = int(f[6]) == 0 and int(f[3]) >= 1 and f[8] != "0"
    print(f"{'PASS' if ok else 'FAIL'}: {kind} size {size}: rc {rc[1] if rc else None}, fields {len(f)}, wall {f[wall[kind]] if len(f) > wall[kind] else None}")
    bad += not ok
sys.exit(1 if bad else 0)
