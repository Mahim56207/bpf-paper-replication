#!/usr/bin/env bash
# Phase 8.1 VERIFY (no root, no measurement, no traffic): checks that the Phase 8.1 evidence is complete, that the table is
# recomputed from the logs and agrees with the Phase 6 reference numbers, that the numbers quoted in the findings file occur in
# the table, and that no tracked file of an earlier phase was modified except the D8.10 attribution line in DEVIATIONS.md.
# Usage: bash scripts/p8_1_verify.sh 2>&1 | tee logs/p8/p8_1/p8_1_verify.log
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
fail=0
chk() { if [[ $1 -eq 0 ]]; then echo "PASS: $2"; else echo "FAIL: $2"; fail=$((fail+1)); fi; }
T=results/p8_1_idle_table.md; J=results/p8_1_idle.json; F=results/p8_1_findings.md; O=results/p8_1_options.md
mkdir -p logs/p8/p8_1

echo "### 1. inputs exist"
for f in logs/p8/p8_1/p8_1_probe_current_desktop.log scripts/p8_1_probe.sh scripts/p8_1_idle.sh scripts/p8_1_stats.py scripts/p8_1_cpu_window.py \
         results/baseline_calibration.json; do [[ -s $f ]]; chk $? "$f exists and is non-empty"; done
for s in desktopnow desktopquiet desktopsettled; do
    n=$(ls logs/p8/p8_1/idle_$s/p81${s}_D_idle_0_[123].log 2>/dev/null | wc -l); [[ $n -eq 3 ]]; chk $? "idle_$s has 3 window logs ($n)"
    [[ -s logs/p8/p8_1/idle_$s/context.txt ]]; chk $? "idle_$s/context.txt exists"
done

echo "### 2. recompute the table from the logs (outputs deleted first, then checked)"
cp "$T" /tmp/p8_1_table_before.md 2>/dev/null; cp "$J" /tmp/p8_1_json_before.json 2>/dev/null
rm -f "$T" "$J"
python3 -I scripts/p8_1_stats.py > logs/p8/p8_1/p8_1_stats.out 2>&1; chk $? "p8_1_stats.py (log logs/p8/p8_1/p8_1_stats.out)"
[[ -s $T && -s $J ]]; chk $? "table and json were created by this run"
if [[ -f /tmp/p8_1_table_before.md ]]; then diff -q /tmp/p8_1_table_before.md "$T" > /dev/null; chk $? "table identical to the previous computation (deterministic)"; fi

echo "### 3. Phase 6 reference numbers recomputed from the Phase 6 logs"
python3 -I - <<'PY'
import json, sys
j = json.load(open("results/p8_1_idle.json")); b = json.load(open("results/baseline_calibration.json"))
s = j["sets"]
q, n = s["Phase 6 quiet calibration session"], s["Phase 6 matrix session start (noisy)"]
bad = 0
def ok(name, got, want, tol):
    global bad
    good = abs(got - want) <= tol
    bad += not good
    print("%s: %s computed %.4f, recorded %.4f" % ("PASS" if good else "FAIL", name, got, want))
ok("quiet idle rate mean (D6.8 0.131)", q["idle_mean"], b["idle_rate_mean"], 1e-9)
ok("quiet canary {0,1} max (0.0689)", q["canary_01_max"], b["canary_max"]["01"], 1e-9)
ok("quiet canary {0} max (0.0369)", q["canary_0_max"], b["canary_max"]["0"], 1e-9)
ok("noisy matrix idle rate mean (D6.13 0.843)", n["idle_mean"], 0.843, 0.0005)
sys.exit(1 if bad else 0)
PY
chk $? "reference numbers reproduce"

echo "### 4. numbers quoted in $F and $O occur in the table"
python3 -I - <<'PY'
import re, sys
t = open("results/p8_1_idle_table.md").read()
bad = 0
for f in ("results/p8_1_findings.md", "results/p8_1_options.md"):
    try:
        txt = open(f).read()
    except OSError:
        print("FAIL: %s missing" % f); bad += 1; continue
    # numbers in backticks of the form `n.nnn` or `n.nnnn` are the ones that must come from the table
    for m in sorted(set(re.findall(r"`(\d+\.\d{3,4})`", txt))):
        good = m in t
        bad += not good
        print("%s: %s quoted number %s %s the table" % ("PASS" if good else "FAIL", f, m, "occurs in" if good else "does NOT occur in"))
sys.exit(1 if bad else 0)
PY
chk $? "quoted numbers come from the table"

echo "### 5. nothing from earlier phases modified"
chg=$(git status --short | grep -vE '^\?\? (logs/p8/p8_1/|logs/p81|scripts/p8_1_|results/p8_1_)' | grep -v '^ M DEVIATIONS.md$' || true)
[[ -z "$chg" ]]; chk $? "only Phase 8.1 files and DEVIATIONS.md changed: ${chg:-none}"
d=$(git diff -U0 DEVIATIONS.md | grep '^[-+]' | grep -vE '^(\+\+\+|---)' | wc -l); [[ $d -eq 2 ]]; chk $? "DEVIATIONS.md diff is exactly the one corrected D8.10 line ($d changed lines)"
git ls-files --error-unmatch logs/bench_D_idle_0_1.log > /dev/null 2>&1 && git diff --quiet -- logs/bench_D_idle_0_1.log logs/bench_D_idle_0_2.log logs/bench_D_idle_0_3.log results/baseline_calibration.json; chk $? "tracked Phase 6 idle logs and baseline_calibration.json unchanged"

echo "### 6. result of the settled set against the V8 limit (information, not a gate)"
python3 -I - <<'PY'
import json
j = json.load(open("results/p8_1_idle.json")); lim = 1.2 * j["baseline_calibration"]["canary_max"]["01"]
for name, r in j["sets"].items():
    if name.startswith("Phase 8.1"):
        print("%-28s idle %.3f CPU-s/s, canary {0,1} max %.4f (limit %.4f), %d of 3 windows over the limit" % (name, r["idle_mean"], r["canary_01_max"], lim, r["v8_windows_contaminated"]))
PY

echo; echo "p8_1_verify: $fail FAIL"
exit $((fail>0))
