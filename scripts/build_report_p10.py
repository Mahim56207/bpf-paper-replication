#!/usr/bin/env python3
"""Phase 11: the Phase 10 parts of REPORT.md, README.md and results/comparison.md, imported by scripts/build_report.py (not run on its own).
Every number is read from results/p10_summary.json (computed by scripts/p10_summarize.py from logs/p10/), logs/p10/wp1_diag/diag.txt, logs/p10/wp1b/pilot_precision.txt,
logs/p10/wp4/ and git through the functions that build_report.py passes in (so that every source file is registered in logs/p8/p8_7/report_sources.txt);
the prose around the numbers is fixed text. Call build(rd, rj, mdtable, commit) -> dict of Markdown blocks."""
import re

DELTA = 10.0                                   # slope margin of docs/phase10_design.md (frozen); only used to print the class of an interval
GAP_CLOSED = ("REVERSED", "AT PARITY")


def g(x, d=4):
    return "n/a" if x is None else f"{x:.{d}g}"


def iv(lo, hi, d=4):
    return f"[{g(lo, d)}, {g(hi, d)}]"


def est_iv(t, d=4):
    return f"{g(t[1], d)} {iv(t[0], t[2], d)}"


def slope_class(lo, hi):
    if lo >= -DELTA and hi <= DELTA:
        return "INSIDE"
    if lo > DELTA:
        return "OUT+"
    if hi < -DELTA:
        return "OUT-"
    return "UNDECIDED"


def build(rd, rj, mdtable, commit):
    p10 = rj("results/p10_summary.json")
    L = {k: v["label"] for k, v in p10["labels"].items()}
    rd("results/p10_summary.md")
    rd("results/p10_summary_before_wp1b.md")
    diag = rd("logs/p10/wp1_diag/diag.txt")
    pilot = rd("logs/p10/wp1b/pilot_precision.txt")
    unb = rd("logs/p10/wp4/unbounded_stderr.txt")
    bnd = rd("logs/p10/wp4/bounded_stderr.txt")
    wp1b_log = rd("logs/p10/p10_wp1b_sha256.log")
    rd("docs/phase10_wp1b_design.md")
    env = rd("ENV.md")
    kernel_p10 = None
    for line in env.splitlines():
        if line.startswith("| kernel |") and "Phase 10" in line:             # the row of the Phase 10 session table
            kernel_p10 = re.search(r"Linux (6\.17\.0-\d+-generic)", line).group(1)
    assert kernel_p10, "ENV.md has no Phase 10 kernel row"
    w1, wb = p10["wp1"], p10["wp1b"]
    it = {r["quantity"]: r for r in wb["interval_table"]}
    kK, kU, kd, kE, ke, kM, kUM = (it[k] for k in ("s_K, kernel reject_all (test run)", "s_U, user-space drain path U", "d = s_U - s_K (claim C2)", "s_E, in-kernel accept-all drain path E",
                                                      "e = s_U - s_E (claim C3)", "s_memcpy, copy floor", "s_U - s_memcpy (post hoc, descriptive)"))
    mc = wb["memcpy_vs_user"]
    grid, raw, indep, real = p10["wp3"]["grid"], p10["wp3"]["grid_raw"], p10["wp3"]["indep"], p10["wp3"]["real"]
    n_dir = sum(1 for c in grid.values() if c["direction"] == "HOLDS")
    n_ord = sum(1 for c in grid.values() if c["order_holds"])
    dir_fail = [b for b, c in grid.items() if c["direction"] != "HOLDS"]
    ord_ok = [b for b, c in grid.items() if c["order_holds"]]
    rng = {f: (min(c["R"][f][0] for c in grid.values()), max(c["R"][f][2] for c in grid.values())) for f in ("F1", "F2", "F3", "F4")}
    a2, rs = p10["wp2a"], p10["wp2b"]["rates"]
    mit = p10["labels"]["C4-mitigation"]["detail"]
    # Phase 12 relabel (D12.1): the mechanical output of rule P6 is kept in results/p10_summary.json, but the report names the result by what the data show
    MIT = "REVERSED gap, cause not established (UNVERIFIED)" if all(mit.get(x) == "REVERSED" for x in "AB") else None
    assert MIT is not None, "the mitigation classes are no longer both REVERSED: the report text has to be rewritten"
    ratios = a2["ratios"]
    n_bc = sum(1 for r in rs if rs[r]["rho_class"] == "B-CHEAPER")
    undec_rho = [r for r in sorted(rs, key=int) if rs[r]["rho_class"] != "B-CHEAPER"]
    undec_drop = [r for r in sorted(rs, key=int) if rs[r]["drop_class"] != "NO-LOSS-BOUND"]
    dir_txt = ", ".join(dir_fail) or "none"
    f1_low = [b for b in dir_fail if grid[b]["R"]["F1"][2] < 1]
    # ---- numbers of the WP1 diagnosis, read back from its log
    att = re.search(r"attempts: (\d+); clean and rc 0: (\d+); failing: (\d+)", diag)
    wall = re.search(r"window wall \(s\) of the canary snapshots: min ([\d.]+) median ([\d.]+) max ([\d.]+)", diag)
    one = re.search(r"0\.01/limit = ([\d.]+) s; attempts with canary wall below it: (\d+); failing among them: (\d+)", diag)
    icpt = re.search(r"wall<1s: n=\d+ a=([\d.]+)\+-([\d.]+) ticks", diag)
    lim = re.search(r"canary limit \(CPU-s/s over 4 cores\): \[([\d.]+)\]", diag).group(1)
    tool = re.search(r"tool duration \(s\): min ([\d.]+) median ([\d.]+)", diag)
    first_pilot = pilot.splitlines()[0]
    pil_d = [l for l in pilot.splitlines() if l.startswith("d = ")][0]
    pil_e = [l for l in pilot.splitlines() if l.startswith("e = ")][0]
    infinite = re.search(r"^(infinite loop detected at insn \d+)$", unb, re.M).group(1)
    rej_last = re.search(r"^(libbpf: prog 'p10_unbounded': failed to load: -\w+)$", unb, re.M).group(1)
    proc_b = re.search(r"^(processed \d+ insns \(limit \d+\)[^\n]*)$", bnd, re.M).group(1)
    wb_design_time = re.search(r"design_logged_at (\S+)", wp1b_log).group(1)

    # ------------------------------------------------------------------------------------------------ final labels
    final = mdtable(
        ["claim", "label (Phase 10)", "what the label rests on (computed from `results/p10_summary.json`)", "label before Phase 10"],
        [["C1 register against stack machine, instructions per packet (Fig. 8)", f"**{L['C1']}**",
          f"direction (R above 1 for all four filters) holds in {n_dir} of {len(grid)} compiler and optimisation-level builds (fails in: {', '.join(dir_fail) or 'none'}); the ordering R(F1) < R(F2) < R(F3) < R(F4) holds in {n_ord} of {len(grid)} ({', '.join(ord_ok)}); range of R over the builds: F1 {iv(*rng['F1'], 3)}, F2 {iv(*rng['F2'], 3)}, F3 {iv(*rng['F3'], 3)}, F4 {iv(*rng['F4'], 3)}. Our own interpreters and CSPF programs, not the 1993 code",
          "MIXED (Phases 6c and 8.0)"],
         ["C2 reject all: in-kernel cost flat in packet size (Fig. 3)", f"**{L['C2']}**",
          f"kernel reject slope s_K {g(kK['estimate'])} ns/byte, 90% interval {iv(kK['lo'], kK['hi'])}; user-path slope s_U {g(kU['estimate'])} {iv(kU['lo'], kU['hi'])}; d = s_U - s_K {g(kd['estimate'])} {iv(kd['lo'], kd['hi'])}; all INSIDE the frozen margin of 10 ns/byte (**BOUNDED only means that**; the upper bound of s_U is {g(kU['hi'])} ns/byte, far below the margin). Microbenchmarks of the in-kernel filter and of the user-space drain path, **not end-to-end capture**",
          "MIXED (Phase 8.3)"],
         ["C3 accept all: copy slope and fixed cost (Fig. 2)", f"**{L['C3']}**",
          f"e = s_U - s_E {g(ke['estimate'])} ns/byte, 90% interval {iv(ke['lo'], ke['hi'])}, INSIDE the frozen margin; s_U {g(kU['estimate'])}, s_E {g(kE['estimate'])}. Same scope: microbenchmarks, not end-to-end capture",
          "INCONCLUSIVE (Phase 8.3)"],
         ["C4 end-to-end speed-up over NIT and CSPF (as tested here: capture-side CPU per matched packet, A against B, paced)", f"**{L['C4']}**",
          f"rule P9 of `docs/phase10_design.md`: at the paced rates where the label is decided, config A (user-space copy-then-filter) costs more capture-side CPU per flow-matched packet than config B (eBPF filter), ratio and class per rate in the ladder table below (B-CHEAPER at {n_bc} of {len(rs)} rates); the drop fraction is bounded below the declared margin at every rate except {', '.join(undec_drop) or 'none'}. **Not the 1993 end-to-end speed-up and not the CSPF ratio** (instruction counts are C1)",
          "INCONCLUSIVE under the frozen V8 rule (Phase 8.3); NOT SUPPORTED with the post hoc floor; NOT SUPPORTED in Phase 6"],
         ["C4-mitigation: the sender-side confound of Phase 8.2 when the capture runs on the receiving end with RPS", f"**{MIT}**",
          f"ratio of the offered load without capture over that with capture, baseline topology to mitigated topology: A {g(ratios['A']['R_base'][1], 3)} to {g(ratios['A']['R_mit'][1], 3)}, B {g(ratios['B']['R_base'][1], 3)} to {g(ratios['B']['R_mit'][1], 3)}, C {g(ratios['C']['R_base'][1], 3)} to {g(ratios['C']['R_mit'][1], 3)} (intervals in the section below; C is reported only); below one in the mitigated topology, so with capture attached the sender offered MORE load than without. Cause not established (UNVERIFIED). The mechanical output of rule P6 is in `results/p10_summary.json` and is not used as the result here",
          "C4-S SENDER-LIMITED SUPPORTED (Phase 8.2)"],
         ["C5 a safe in-kernel VM makes code to the data practical", f"**{L['C5']}**",
          f"the unbounded loop is rejected by the verifier (exit {p10['wp4']['unbounded']['exit']}: \"{infinite}\") and the loop with a constant bound is accepted (exit {p10['wp4']['bounded']['exit']}). The CPU-benefit part of C5 is C2 and C3 above (microbenchmarks only)",
          "MIXED (Phase 8.7)"],
         ["C2 (WP1 original, superseded)", f"**{L['C2 (WP1 original)']}**", f"short batches of the first Phase 10 run: {len(w1['invalid'])} of {w1['batches']} final batches invalid; kept alongside, never pooled with WP1b", "-"],
         ["C3 (WP1 original, superseded)", f"**{L['C3 (WP1 original)']}**", "same data as the row above", "-"]])

    final_block = f"""## Final labels after Phase 10

Phase 10 re-measured every claim under designs that were frozen before the runs (`docs/phase10_design.md` and, for C2 and C3, `docs/phase10_wp1b_design.md`; hashes and times logged). One machine only (the aarch64 virtual machine of `ENV.md`, kernel {kernel_p10}; earlier phases ran on a different kernel build, so no earlier number is reused as a baseline here, D10.5). **The labels below are the final ones; the table after them keeps the earlier verdicts of Phases 6 to 9 for the record, and where the two differ the Phase 10 label governs, with the scope stated in the second column.** A label of BOUNDED means an effect is absent or present only inside a declared margin; the margins are mine, flagged for the reviewer (10 ns/byte, 10 percent, 1.10 and 1.25, 0.1 percent).

{final}
"""

    # ------------------------------------------------------------------------------------------------ Phase 10 section
    wp1_tbl = mdtable(["quantity", "slope, wall (ns/byte)", "90% interval", "class", "slope, thread CPU", "90% interval", "class", "n"],
                      [[k, g(f["slope"]), iv(f["lo_ci"], f["hi_ci"]), f["class"], g(wb["fits_cpu"][k]["slope"]), iv(wb["fits_cpu"][k]["lo_ci"], wb["fits_cpu"][k]["hi_ci"]), wb["fits_cpu"][k]["class"], str(f["n"])]
                       for k, f in wb["fits"].items()])
    int_tbl = mdtable(["quantity", "estimate (ns/byte)", "90% interval", "class (frozen margin 10 ns/byte)", "148 / upper bound", "216 / upper bound"],
                      [[r["quantity"], g(r["estimate"]), iv(r["lo"], r["hi"]), slope_class(r["lo"], r["hi"]), g(r["bpf_over_hi"], 3), g(r["nit_over_hi"], 3)] for r in wb["interval_table"]])
    cells = a2["cells"]
    cell_tbl = mdtable(["topology", "N (no capture)", "A", "B", "C"],
                       [[t, *[f"{g(cells[f'{t}_{c}']['mean'], 6)} ± {g(cells[f'{t}_{c}']['sd'], 3)} (n={cells[f'{t}_{c}']['n']})" for c in "NABC"]] for t in ("T0", "T1")])
    mit_tbl = mdtable(["config", "R(T0), baseline [95%]", "R(T1), mitigated [95%]", "Q = R(T1) / R(T0) [95%]", "class (rule P6)"],
                      [[x, est_iv(ratios[x]["R_base"], 3), est_iv(ratios[x]["R_mit"], 3), est_iv(ratios[x]["Q"], 3), mit.get(x, "reported only, not gating")] for x in "ABC"])
    lad_rows = []
    for r in sorted(rs, key=int):
        v = rs[r]
        lad_rows.append([r, f"{g(v['cpu']['A']['mean'], 5)} ± {g(v['cpu']['A']['sd'], 3)}", f"{g(v['cpu']['B']['mean'], 5)} ± {g(v['cpu']['B']['sd'], 3)}", f"{g(v['cpu']['C']['mean'], 5)} ± {g(v['cpu']['C']['sd'], 3)}",
                         est_iv(v["rho"], 3), v["rho_class"], f"{g(v['drops']['A']['frac'], 3)} {iv(*v['drops']['A']['cp95'], 3)}", f"{g(v['drops']['B']['frac'], 3)} {iv(*v['drops']['B']['cp95'], 3)}", v["drop_class"]])
    lad_tbl = mdtable(["offered pps (total)", "A: capture CPU ns / matched pkt", "B", "C (reported only)", "rho = A / B [95%]", "class (rule P2)", "drop fraction A [95% Clopper-Pearson]", "drop fraction B", "drop class"], lad_rows)

    def r4(c):
        return " | ".join(est_iv(c["R"][f], 3) for f in ("F1", "F2", "F3", "F4"))

    grid_tbl = mdtable(["build (BPF optimised, our CSPF set)", "F1 R [95%]", "F2", "F3", "F4", "direction", "ordering", "R(F2) - R(F3) [95%]"],
                       [[b, *[est_iv(c["R"][f], 3) for f in ("F1", "F2", "F3", "F4")], c["direction"], "HOLDS" if c["order_holds"] else "FAILS", est_iv(c["F2_minus_F3"], 3)] for b, c in grid.items()])
    raw_tbl = mdtable(["build (BPF unoptimised, our CSPF set; reported, not gating)", "F1 R [95%]", "F2", "F3", "F4", "direction", "ordering", "R(F2) - R(F3) [95%]"],
                      [[b, *[est_iv(c["R"][f], 3) for f in ("F1", "F2", "F3", "F4")], c["direction"], "HOLDS" if c["order_holds"] else "FAILS", est_iv(c["F2_minus_F3"], 3)] for b, c in raw.items()])
    maj_dir = "HOLDS" if n_dir * 2 > len(grid) else "FAILS"
    maj_ord = "HOLDS" if n_ord * 2 > len(grid) else "FAILS"
    ind_rows = []
    for mix, d in indep.items():
        for which in ("ours", "indep"):
            c = d[which]
            ind_rows.append([mix.replace("mix_", ""), "our CSPF programs" if which == "ours" else "independent CSPF programs (fresh subagent)", *[est_iv(c["R"][f], 3) for f in ("F1", "F2", "F3", "F4")], c["direction"], "HOLDS" if c["order_holds"] else "FAILS",
                             est_iv(c["F2_minus_F3"], 3)])
    ind_tbl = mdtable(["mix", "CSPF set (gcc-O2 build, BPF optimised)", "F1 R [95%]", "F2", "F3", "F4", "direction", "ordering", "R(F2) - R(F3) [95%]"], ind_rows)
    real_rows = []
    for b, d in real.items():
        for which, c in d.items():
            real_rows.append([b, "optimised" if which == "opt" else "unoptimised", *[est_iv(c["R"][f], 3) for f in ("F1", "F2", "F3", "F4")], c["direction"], "HOLDS" if c["order_holds"] else "FAILS",
                              "AGREES" if c["direction"] == maj_dir and ("HOLDS" if c["order_holds"] else "FAILS") == maj_ord else "DISAGREES", est_iv(c["F2_minus_F3"], 3)])
    real_tbl = mdtable(["build", "BPF program", "F1 R [95%]", "F2", "F3", "F4", "direction", "ordering", "against grid majority", "R(F2) - R(F3) [95%]"], real_rows)
    n_raw_ord = sum(1 for c in raw.values() if c["order_holds"])
    n_ind_ord = sum(1 for d in indep.values() if d["indep"]["order_holds"])
    flip = [b for b, c in grid.items() if c["F2_minus_F3"][2] < 0]
    flip_txt = ", ".join(flip) if flip else "none"
    t1 = {c: cells[f"T1_{c}"]["mean"] for c in "NABC"}
    above_n = [c for c in "ABC" if t1[c] > t1["N"]]

    section = f"""### Phase 10: hardened re-measurement of C1 to C5 (`docs/phase10_design.md`, `docs/phase10_wp1b_design.md`, `DEVIATIONS.md` D10.1 to D10.11)

Design frozen and hashed before the runs (`logs/p10/p10_design_sha256.log`, `logs/p10/p10_wp1b_sha256.log`; the second design was logged at {wb_design_time}); one launch per block set, hands-off, with a 60 s settle, a memory gate and a pre-flight idle set per block; one machine. Run by `scripts/p10_run_all.sh` (WP1 to WP4) and `scripts/p10b_run.sh` (WP1b); labels computed by `scripts/p10_summarize.py` from `logs/p10/` and re-derived by `scripts/p10_check_labels.py`; `scripts/p10_verify.sh` reported no failure.

**WP1 and why WP1b exists.** The first run of the microbenchmarks (WP1) was INCONCLUSIVE for C2 and C3: {att.group(3)} of {att.group(1)} attempts exceeded the canary limit ({lim} CPU-s/s over four cores) and {len(w1['invalid'])} of {w1['batches']} final batches stayed invalid. A read-only diagnosis (`scripts/p10_wp1_diag.py`, `logs/p10/wp1_diag/diag.txt`) showed that the batches were far shorter than the canary can resolve: median tool time {tool.group(2)} s, canary window median {wall.group(2)} s and minimum {wall.group(1)} s, while one 10 ms tick of `/proc/stat` exceeds the limit in any window shorter than {one.group(1)} s ({one.group(2)} attempts, {one.group(3)} failed); a fixed cost of {icpt.group(1)} ± {icpt.group(2)} ticks per attempt was fitted. The design had named repetition counts and no minimum duration; that was my omission. Whether the remaining excess is real background load or caused by the measurement itself is UNVERIFIED. WP1b (`docs/phase10_wp1b_design.md`) kept the frozen V8 rule, the margin of 10 ns/byte and the verdict rules and changed only the batch length (at least 5 s), the recorded clocks (wall time and thread CPU time) and the replication ({wb['batches']} planned batches, {wb['valid']} valid, {len(wb['invalid'])} invalid, {wb['reruns']} re-run attempt, shortest measured wall time {g(wb['min_wall_s'])} s); its pilot ({first_pilot}) was excluded from every verdict.

**Scope of C2 and C3.** WP1b measures the in-kernel filter (`BPF_PROG_TEST_RUN`) and the user-space drain path of an AF_PACKET queue as microbenchmarks. It does not measure end-to-end capture, and it does not include the cost of the capture process outside the drain loop.

C2 and C3 as intervals (ns per byte of frame size, 90% intervals), with the ratio of the 1993 slopes (148 ns/byte for the BPF filter and 216 ns/byte for NIT, paper.txt L186-189 and L208) to the upper bound of each interval. **That ratio compares different measurement paths (a different machine, kernel and code path), not a replication.**

{int_tbl}

The same fits per quantity, wall-based (the label-carrying quantity) and thread-CPU based (sensitivity; same rule, same labels: C2 {L['C2']}, C3 {L['C3']}):

{wp1_tbl}

**Copy floor against the user path (post hoc and descriptive, no label).** The copy-floor slope s_memcpy is {g(kM['estimate'])} ns/byte, 90% interval {iv(kM['lo'], kM['hi'])}; the user-path slope s_U is {g(kU['estimate'])} {iv(kU['lo'], kU['hi'])}. Their intervals {'overlap' if mc['overlap'] else 'do not overlap'}, and the interval of the difference s_U - s_memcpy, {g(kUM['estimate'])} {iv(kUM['lo'], kUM['hi'])}, {'contains' if mc['agree'] else 'excludes'} zero: the two slopes {'agree' if mc['agree'] else 'differ'} at this precision, both far inside the margin. Why the user path grows faster than a pure copy is not investigated (UNVERIFIED).

**Frozen margin.** delta = 10 ns/byte was kept as frozen and no tighter margin was added. The labels are BOUNDED because every interval lies inside it; the upper bounds of the intervals are {g(kU['hi'])} ns/byte for s_U and {g(kK['hi'])} ns/byte for s_K, far below the margin, so BOUNDED here says that the size dependence is excluded above a margin much larger than what was measured, not that it was measured to be that large.

**C4 mitigation test (WP2a): offered load, flood, two topologies.** Topology T0 captures on the sender's side as in Phase 8.2; T1 captures on the receiving end inside the namespace with receive-packet steering to a dedicated core. Mean offered packets per second ± sd (n valid runs; {len(a2['excluded'])} runs excluded; V8 limit {g(a2['calib']['limit'])} CPU-s/s by calibration windows per cell, design amendment A2):

{cell_tbl}

R is the mean offered load of the no-capture configuration over that of the capture configuration in the same topology; Q = R(T1) / R(T0):

{mit_tbl}

**The gap is reversed, not removed.** A ratio below one in the mitigated topology means that the configuration with capture attached offered MORE load than the configuration without capture. In T1 the no-capture configuration N has the lowest offered load of the four ({', '.join(c for c in above_n)} are above it). The rule of the design (P6) was written for a gap that shrinks toward parity, and its mechanical output (recorded in `results/p10_summary.json`) counts a reversal as closing the gap; this report does not use that output as the result. The result is a **{MIT}**: the gap of Phase 8.2 (the capture configurations offering less load than no capture) does not appear in T1, and that is not the same as the confound having been removed or capture being free. **The causes of the reversal are UNVERIFIED**; no run isolated them. (The first version of the summary used a different name for this class; it was renamed at the author's request after the run, thresholds unchanged, D10.11.)

**C4 paced ladder (WP2b).** Topology T1, configs A, B and C, six runs per cell at five total rates; capture-side CPU is the busy time of the two receiver cores minus the idle busy time, per flow-matched packet (ns); rho = cost(A) / cost(B) with a 95% interval; drops are socket drops over packets received by the socket:

{lad_tbl}

Label {L['C4']} by rule P9 (at least half of the reachable rates B-CHEAPER, none A-CHEAPER): B-CHEAPER at {n_bc} of {len(rs)} rates; the ratio class is not B-CHEAPER at: {', '.join(undec_rho) or 'none'}; the drop class is not NO-LOSS-BOUND at: {', '.join(undec_drop) or 'none'}. The label concerns capture-side CPU per matched packet at paced rates on this machine, not the 1993 end-to-end speed-up and not the CSPF ratio.

**C1 hardening (WP3).** Same pipeline as Phase 6c (decision equivalence against libpcap: {p10['wp3']['indep_equiv_bad']} mismatches for the independent set, {p10['wp3']['real_equiv_bad']} for the real trace, builds excluded: {len(p10['wp3']['excluded_builds'])}). Primary pairing, mix M0, CSPF over BPF, M2 = host instructions per packet inside the evaluator, 95% interval over ten chunks of 1000 frames:

{grid_tbl}

Direction {maj_dir.lower()} in the majority of builds and ordering {maj_ord.lower()} in the majority; the ordering of F2 against F3 is the part that flips: R(F2) - R(F3) is below zero (the ratio of Filter 2 below that of Filter 3, the order of Fig. 8) only in {flip_txt}; the compiler and the optimisation level move it, as the rows show, and so does the libpcap optimiser setting (with the unoptimised BPF programs the ordering holds in {n_raw_ord} of {len(raw)} builds) and the CSPF set (the independent set gives the ordering in {n_ind_ord} of {len(indep)} mixes) (the direction fails in: {dir_txt}; in {', '.join(f1_low) or 'none'} the ratio for Filter 1 is below one, that is, the BPF program costs more instructions than the stack program there; why was not investigated, UNVERIFIED). With the unoptimised BPF programs (reported, not gating):

{raw_tbl}

An independent set of CSPF programs, written by a fresh subagent that was given only the paper excerpts and the opcode list (`src/p10_indep/`, hashes in `logs/p10/p10_indep_sha256.log`), and the real traffic mix (20000 captured frames, anonymised to 10.0.0.0/8 by `scripts/p10_traffic_anon.py`; the raw capture is not committed, the hash of the anonymised trace is in `logs/p10/real_trace_sha256.log`):

{ind_tbl}

{real_tbl}

**C5 termination (WP4).** `bpftool -d prog load` of two socket-filter programs built with clang (`logs/p10/wp4/`): the unbounded loop is rejected, verbatim from the captured stderr: "{infinite}", then "{rej_last}"; the loop with a constant bound is accepted ({proc_b}). One unbounded and one bounded program test termination enforcement; they do not establish it for all programs (UNVERIFIED beyond these two).
"""

    threats = f"""14. **Phase 10 is one machine and a different kernel.** The Phase 10 runs used kernel {kernel_p10}; the earlier phases ran on another build (D10.5). Phase 10 numbers are not pooled with earlier ones and the labels are about this machine.
15. **WP1 was badly designed (my omission) and WP1b repairs it.** The first microbenchmark run had no minimum batch duration, so most canary windows were shorter than the 10 ms tick can resolve (see the Phase 10 section); its labels are kept as superseded and INCONCLUSIVE. Hypothesis A (batches too short for the tick) is supported by the logs; hypothesis B (real background load) is neither shown nor excluded.
16. **C2 and C3 are microbenchmarks.** They measure the in-kernel filter and the user-space drain path, not end-to-end capture, and the margin of 10 ns/byte is much larger than the measured slopes, so BOUNDED is a weak statement; the comparison with the 1993 slopes is between different measurement paths.
17. **The mitigation result is a reversal with unknown causes.** In the mitigated topology the configurations with capture offered more load than the one without; the causes were not isolated. The ladder label C4 rests on capture-side CPU per matched packet and holds at {n_bc} of {len(rs)} rates; the ratio class is not B-CHEAPER at {', '.join(undec_rho) or 'none'} and the drop class is not NO-LOSS-BOUND at {', '.join(undec_drop) or 'none'}.
18. **C1 depends on our own CSPF programs and on the toolchain.** The independent set was written by a subagent from paper excerpts, still not the 1993 code; the real trace comes from one network and was anonymised; the direction of the ratio fails in {dir_txt} and the F2 against F3 ordering depends on compiler and optimisation level.
19. **Rules adjusted before or after seeing data.** The V8 rule for the flood blocks was amended (A2) after smoke runs and before any measured run; the summarizer had an overflow bug in the Clopper-Pearson interval that was fixed after the run (D10.7); the name of the mitigation class was changed after the run (D10.11); the copy-floor comparison is post hoc. The changes made after measured data had been seen (D10.7, D10.11) changed no threshold and no label.
"""

    unverified = f"""21. **Why the gap of Phase 8.2 is reversed in the mitigated topology** (Phase 10, WP2a): the offered load with capture attached is higher than without capture; the causes were not isolated.
22. **Whether the extra canary load in the first WP1 run was real background load or caused by the measurement itself** (D10.8): a fixed cost of about two ticks per attempt fits a harness explanation; no run isolated it.
23. **The real-traffic capture script after its repair** (`scripts/p10_capture_real.sh`, systemd-run based, D10.3) was not re-run; the anonymised trace that the labels use was captured before the repair.
24. **Why the user-space drain path grows faster with size than a pure copy** (post hoc, Phase 10): both slopes are small; no mechanism was tested.
25. **Why the BPF program for Filter 1 costs more instructions than the stack program in {dir_txt}** (Phase 10, WP3): observed, not investigated.
26. **C5 beyond two programs.** The verifier rejected one unbounded loop and accepted one bounded loop; termination enforcement for other programs was not tested.
"""

    d10 = rd("docs/phase10_design.md")
    am = {m.group(1): m.group(2) for m in re.finditer(r"^- \*\*(A\d+) \((\d{4}-\d{2}-\d{2})", d10, re.M)}
    amend_rows = [
        ["`docs/phase10_design.md`", "A1", am["A1"], "before any measured run: the independent CSPF set's input file omitted one table row (corrected, logged)"],
        ["`docs/phase10_design.md`", "A2", am["A2"], "before any measured run: calibration windows for every cell of the flood blocks (V8 differs by topology and config in smoke runs)"],
        ["`docs/phase10_wp1b_design.md`", "none (frozen once)", wb_design_time[:10], "written after the WP1 diagnosis and before any WP1b run; changes only batch length, clocks and replication"],
    ]
    selfaudit = ("- *Phase 10 and 11 records.* Designs were hashed before their runs (`logs/p10/p10_design_sha256.log`, `logs/p10/p10_wp1b_sha256.log`), amended only by dated amendments, and verified by script (`scripts/p10_verify.sh`, no failure); "
                 "every shown number comes from `results/p10_summary.json`, which `scripts/p10_summarize.py` computes from `logs/p10/`. Departures, all in `DEVIATIONS.md`: the first WP1 had no minimum batch duration (D10.8, repaired by WP1b, D10.9); "
                 "the real-traffic capture hung under AppArmor and was stopped by the user (D10.3); the summarizer overflowed on the packet counts and was fixed after the run (D10.7); the wording of the mitigation class and the tables of C2 and C3 were changed after the run at the author's request (D10.11). "
                 "Phase 10 was committed once after \"Phase 10 complete\" with its verify script and a secrets scan re-run (`logs/p10/p10_verify.log`, `logs/p10/p10_secrets_scan.log`); build artifacts and the raw capture are not in git.")
    abstract = (f"Phase 10 re-measured all five claims under designs that were frozen before the runs, on one machine (kernel {kernel_p10}): C1 {L['C1']} (the direction holds in {n_dir} of {len(grid)} builds, the ordering of the ratios in only {n_ord}), "
                f"C2 {L['C2']} and C3 {L['C3']} (microbenchmarks, every slope inside the frozen margin of 10 ns/byte, not end-to-end capture), C4 {L['C4']} (capture-side CPU per matched packet of the user-space sniffer against the eBPF filter at paced rates), "
                f"the mitigation test of the sender confound gave a {MIT}: with capture attached the sender offered more load than without, not just a smaller gap, and C5 {L['C5']} (the verifier rejects an unbounded loop and accepts a bounded one). "
                f"The earlier labels of Phases 6 to 9 are kept in the table that follows the final labels; the first microbenchmark run was INCONCLUSIVE because its batches were too short for the canary and is kept as superseded.")
    comparison_c1 = (f" **Phase 10:** with {len(grid)} builds (two compilers, three optimisation levels), an independent CSPF set and a real trace the label is {L['C1']}: the direction holds in {n_dir} of {len(grid)} builds and the ordering of the ratios in {n_ord}; "
                     f"R for Filter 4 ranges over {iv(*rng['F4'], 3)}.")
    comparison_c234 = (f" **Phase 10 update (final labels):** C2 {L['C2']} and C3 {L['C3']} from microbenchmarks of the in-kernel filter and of the user-space drain path (not end-to-end capture; every slope inside the frozen margin of 10 ns/byte; "
                       f"user-path slope {g(kU['estimate'])} ns/byte, 90% interval {iv(kU['lo'], kU['hi'])}, against the 1993 slope of 148 ns/byte: the 1993 slope is {g(kU['bpf_over_hi'], 3)} times the upper bound, a comparison of different measurement paths); "
                       f"C4 {L['C4']} (receiver-side capture CPU per matched packet at paced rates); in the mitigated topology the sender-side gap of Phase 8.2 is a {MIT}.")
    comparison_c5 = f" **Phase 10 update:** C5 {L['C5']}: the verifier rejects an unbounded loop (\"{infinite}\") and accepts a loop with a constant bound."
    return {"final": final_block, "section": section, "threats": threats, "unverified": unverified, "amend_rows": amend_rows, "selfaudit": selfaudit, "abstract": abstract,
            "comparison_c1": comparison_c1, "comparison_c234": comparison_c234, "comparison_c5": comparison_c5, "labels": L, "kernel": kernel_p10}
