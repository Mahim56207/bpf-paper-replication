#!/usr/bin/env python3
"""Independent re-derivation of every Phase 10 label from the numbers stored in results/p10_summary.json by the rules of docs/phase10_design.md (rules P1, P2, P4 to P6, P9 to P12);
the code here does not import scripts/p10_summarize.py. Exit 1 if any label differs. Usage: python3 -I scripts/p10_check_labels.py"""
import json, math, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
S = json.load(open("results/p10_summary.json"))
lab = S["labels"]
bad = 0


def chk(name, want):
    global bad
    got = lab[name]["label"]
    ok = got == want
    bad += not ok
    print("%s: %s label %s, re-derived %s" % ("PASS" if ok else "FAIL", name, got, want))


# C2 (P4) and C3 (P5): classes of the stored slope intervals and of the stored difference interval
def cls(lo, hi, delta=10.0):
    return "INSIDE" if lo >= -delta and hi <= delta else ("OUT+" if lo > delta else ("OUT-" if hi < -delta else "UNDECIDED"))


def check_c23(label_prefix, fits, suffix=""):
    for name in ("C2", "C3"):
        key = name + suffix
        d = lab[key]["detail"]
        if d is None:
            chk(key, "INCONCLUSIVE")
            continue
        dcls = cls(d[0], d[2])
        if name == "C2":
            kcls = cls(fits["tr_reject"]["lo_ci"], fits["tr_reject"]["hi_ci"])
            want = "SUPPORTED" if kcls == "INSIDE" and dcls == "OUT+" else "BOUNDED" if kcls == "INSIDE" and dcls == "INSIDE" else "NOT SUPPORTED" if kcls in ("OUT+", "OUT-") else "INCONCLUSIVE"
        else:
            want = {"OUT+": "SUPPORTED", "INSIDE": "BOUNDED", "OUT-": "NOT SUPPORTED"}.get(dcls, "INCONCLUSIVE")
        chk(key, want)


if S.get("wp1b"):
    check_c23("WP1b", S["wp1b"]["fits"])                       # C2 and C3 are carried by WP1b (docs/phase10_wp1b_design.md section 4)
    check_c23("WP1", S["wp1"]["fits"], " (WP1 original)")      # the original WP1 labels stay in the summary next to them
else:
    check_c23("WP1", S["wp1"]["fits"])

# C4 mitigation (P6)
a = S["wp2a"]
if a is None:
    chk("C4-mitigation", "INCONCLUSIVE")
else:
    cl = {}
    for x in "AB":
        v = a["ratios"].get(x)
        if v is None:
            cl = None
            break
        qlo, q, qhi = v["Q"]
        rhi = v["R_mit"][2]
        cl[x] = "CLOSED" if qhi < 1 and rhi <= 1.10 else "REDUCED" if qhi < 1 and rhi <= 1.25 else "NOT REDUCED" if qlo > 0.90 else "UNDECIDED"     # CLOSED = REVERSED (rhi < 1) or AT PARITY
    if cl is None:
        want = "INCONCLUSIVE"
    elif cl["A"] == cl["B"] == "CLOSED":
        want = "SUPPORTED"
    elif all(c in ("CLOSED", "REDUCED") for c in cl.values()):
        want = "BOUNDED"
    elif "NOT REDUCED" in cl.values():
        want = "NOT SUPPORTED"
    else:
        want = "INCONCLUSIVE"
    chk("C4-mitigation", want)

# C4 ladder (P9): classes from the stored ratio intervals
b = S["wp2b"]
if b is None:
    chk("C4", "INCONCLUSIVE")
else:
    reach = [v for v in b["rates"].values() if v["status"] == "REACHABLE"]
    if len(reach) < 3:
        want = "INCONCLUSIVE"
    else:
        cl = []
        for v in reach:
            r = v["rho"]
            if not r:
                cl.append("UNDECIDED")
            elif r[0] > 1.10:
                cl.append("B-CHEAPER")
            elif r[2] < 1 / 1.10:
                cl.append("A-CHEAPER")
            elif r[0] >= 1 / 1.10 and r[2] <= 1.10:
                cl.append("EQUIVALENT")
            else:
                cl.append("UNDECIDED")
        half = math.ceil(len(cl) / 2)
        want = ("SUPPORTED" if cl.count("B-CHEAPER") >= half and cl.count("A-CHEAPER") == 0 else
                "NOT SUPPORTED" if cl.count("A-CHEAPER") >= half else
                "BOUNDED" if cl.count("EQUIVALENT") >= half and cl.count("B-CHEAPER") == 0 and cl.count("A-CHEAPER") == 0 else "INCONCLUSIVE")
    chk("C4", want)

# C1 (P10, P11)
w3 = S["wp3"]
if w3 is None:
    chk("C1", "INCONCLUSIVE")
else:
    cells = w3["grid"]
    if len(cells) < 6:
        want = "INCONCLUSIVE"
    else:
        da, ob = 0, 0
        for c in cells.values():
            r = c["R"]
            direction = "HOLDS" if all(r[x][0] > 1 for x in r) else ("REVERSED" if any(r[x][2] < 1 for x in r) else "UNDECIDED")
            da += direction == "HOLDS"
            ob += r["F1"][1] < r["F2"][1] < r["F3"][1] < r["F4"][1]
        want = "SUPPORTED" if da == len(cells) and ob == len(cells) else "NOT SUPPORTED" if len(cells) - da >= 4 else "BOUNDED"
    chk("C1", want)

# C5 (P12)
w4 = S["wp4"]
if w4 is None:
    chk("C5", "INCONCLUSIVE")
else:
    u, bb = w4["unbounded"]["status"], w4["bounded"]["status"]
    chk("C5", "SUPPORTED" if (u, bb) == ("rejected", "loaded") else "BOUNDED" if (u, bb) == ("rejected", "rejected") else "NOT SUPPORTED")
print("label check: %d difference(s)" % bad)
sys.exit(1 if bad else 0)
