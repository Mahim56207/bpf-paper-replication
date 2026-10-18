# Phase 6 addenda A1 and A2 (rule text)

Baseline: pre-registration commit **3591267** (`docs/phase6_design.md`, frozen). Bug-fix commit 8038194 changed no rule. This file is the full rule-text diff against the frozen design: what is superseded, what is added. Dated 2026-10-19, trigger and mechanism in section 5. Anything the frozen design says that is not mentioned here stands unchanged.

## 0. Rule index (ID -> one-line meaning)

Every rule has one ID; a new rule must not reuse one (collisions are caught by grepping this table).

| ID | meaning | status |
|---|---|---|
| V1 | iperf3 client exit 0; client and server JSON parse | frozen |
| V2 | capture process printed FINAL; snapshots and counters readable | frozen |
| V3 | curve and warm-up runs: offered pps within +-5% of target | frozen |
| V4 | curve runs, all configs except C: socket drops <= 0.1% of packets reaching the socket | frozen |
| V5 | tap total vs offered packets within max(20, 0.5%) | **superseded by V5'a to V5'e (A1)** |
| V5'a | drop side: F >= O - max(20, 0.005 x O) per data stream | A1 |
| V5'b | excess side: F <= O + max(20, 0.005 x O) per data stream | A1 |
| V5'c | control envelope: 1 <= C <= 20 + 4 x D per data stream | A1 |
| V5'd | unknown class: X <= B_max + 20 | A1 |
| V5'e | identity: T = F + C + X exactly, every run | A1 |
| V6 | measured window within D - 1 s .. D + 2 s | frozen |
| V7 | steal > 5% of capacity excludes a run; > 20% of a config's runs makes it INCONCLUSIVE | frozen (D6.1 item 6) |
| V8 | canary: unpinned cores' CPU in a window > canary_max x 1.2 contaminates the window | A2 |
| K1 | calibration knee rule: highest loss-free step with no failing step below it; p_curve = floor(0.5 x lowest knee / 100) x 100 | frozen, unchanged |
| R-C2 | C2 verdict criteria | A2 (replaces the frozen C2 rule) |
| R-C3 | C3 verdict criteria | A2 (replaces the frozen C3 rule) |
| R-C4 | C4 verdict criteria | frozen (D6.1 item 7), evaluated on net CPU and flow-scoped matched |
| M1 | net CPU = raw CPU - idle baseline x window | A2 |
| M2 | flow-scoped matched = config matched (parity rule, tcp+udp 4040) - C(4040) | A2 |

## 1. A1: V5 replaced by a three-class decomposition

Trigger: calibration under V5 failed at the 1000 pps step because of a constant excess (D6.4); R1 classified it (D6.4b).

**Classifier** (proto + port on IPv4; identical for every config). For a run whose iperf3 data streams use the port set P (m, warm-up: {4040}; nm, cal: {5050}; flood: {4040, 5050}):
- F_p = frames matching `udp port p` (data flow of stream p);
- C_p = frames matching `tcp port p` (the iperf3 control connection of stream p);
- X = every other frame at the tap, including all non-IPv4 frames and frames on ports not in P;
- T = all frames at the tap.

**Rules**, evaluated for every run (per stream p where a symbol has an index; O_p = datagrams the iperf3 client reports for stream p, from the JSON; D = run duration in seconds):
- V5'a: F_p >= O_p - max(20, 0.005 x O_p)
- V5'b: F_p <= O_p + max(20, 0.005 x O_p)
- V5'c: 1 <= C_p <= 20 + 4 x D. The envelope comes from the R1 structure (start- and teardown-dominated: 27 frames at D = 5) and is **fixed now**. The calibration re-run must observe C inside it at every duration the matrix uses (5 s and 10 s). If C falls outside it at any duration: HOLD and re-rule; the envelope is not stretched after the fact.
- V5'd: X <= B_max + 20, with B_max = the largest ambient frame count of the quiet windows (R1: 0, so X <= 20; R1 observed X = 0).
- V5'e: T = F + C + X exactly (summing over all classifier classes). This checks the classifier pipeline itself.

Rejected alternative: a flat raise of the V5 floor (a single bucket would hide unknown traffic inside the control class and weakens drop detection, which is V5's purpose). The knee/halt logic K1 is unchanged.

The 2-datagram residual (F = 5003 against O = 5001 in R1) stays inside V5'a/b. Hypothesis, recorded in D6.4b and not further tested: iperf3 sends or counts datagrams at the interval or window boundary that its JSON totals do not include.

**Mechanism (implementation note, disclosed because the rule says "identical across configs").** Neither capture program classifies by itself, and the frozen programs are the objects under test. The classifier is therefore a separate always-on instrument: a BPF socket filter that counts every frame into its own array map and returns 0 (accepts nothing), attached to the same interface by its own small loader, started before the capture process and read at teardown. It runs for every config, including D and E, so its per-packet cost is common to all configs. It is size-independent (it copies nothing) and therefore adds to intercepts, not to slopes, and cancels in config differences. This is instrumentation overhead and is reported as such. It is a harness addition made in commit C3; the programs under test are unchanged.

## 2. A2: noise instruments, metric reframe, verdict criteria

Trigger: the smoke runs showed background CPU of 1 to 3 CPU-seconds per 5 s on every core, with run B at about twice the others on cores it does not use (D6.4c).

**V8, canary rule.** The cores not pinned to the experiment are controls: core 0 always, core 1 whenever no noise-stream client runs there (every run except flood). From the quiet (idle) windows, canary_max = the largest value of (busy CPU-seconds on the canary cores) / (window seconds) over the idle windows, computed separately for the canary set {0, 1} and the set {0}. A measured window whose canary rate exceeds canary_max x 1.2 is contaminated: the run is repeated, at most 2 re-runs per cell (cfg, traffic, size, rep); every attempt is kept in `logs/attempts/` and listed in `results/exclusions.md`; the last attempt is the one analysed, and if it is still contaminated the cell is INCONCLUSIVE. Randomised config order stays.

**M1, idle subtraction.** 3 idle windows per session (harness attached: capture process, classifier, pidstat, vmstat; no iperf3), each of the matrix duration. Every CPU figure is reported raw and net: net = raw - idle_rate x window, with idle_rate the mean system-wide busy CPU-seconds per second over the session's idle windows. Headline numbers use net.

**Metric reframe.** The C2 and C3 headline is the **slope of net per-packet CPU against frame size, per config**, plus **config differences at equal frame sizes**; an additive, stationary background cancels in both. Absolute per-packet CPU is secondary.
- Reject curve (C2): per-packet metric = net system-wide CPU per offered packet. Series per config: its slope against size, and the difference to the D floor at each size ("over D"), with the slope of that difference series.
- Accept curve (C3): per-packet metric = net system-wide CPU per flow-scoped matched packet (M2). Series per config: slope and intercept against size; differences A - B of slopes and of intercepts.
- Flood (C4): matched-pps ceiling and net CPU per flow-scoped matched packet, as in R-C4.

**R-C2 (replaces the frozen C2 rule).** On the reject curve, slope of (net CPU per offered packet over D) against size:
REPLICATED iff the in-kernel slope (config B) has a 95% CI that includes 0 AND the copy-then-filter slope (config A) has a 95% CI that excludes 0, with the two CIs not overlapping. Otherwise MIXED or INCONCLUSIVE, with the root cause stated (for example: contamination, an unresolved common size dependence, too few valid points).

**R-C3 (replaces the frozen C3 rule).** On the accept curve, per-config linear fits of net CPU per flow-scoped matched packet against size:
REPLICATED iff the slope difference (A - B) and the intercept difference (A - B) are both positive with 95% CIs that exclude 0, i.e. the direction of the paper's Fig. 2 (the NIT-role config has the larger slope and the larger fixed cost); no absolute 1993 comparison. One of the two: MIXED. Neither, or too few valid points: INCONCLUSIVE with root cause.

**R-C4** is unchanged from the frozen rule and is evaluated on net CPU and flow-scoped matched counts.

INCONCLUSIVE after these mitigations is an acceptable verdict. No further tuning is allowed to obtain a different verdict.

**M2, reporting definition.** Per-config headline matched count = flow-scoped matched = (the config's matched count under the parity rule `tcp or udp port 4040`) - C_4040 from the classifier (same classifier for A and B, and every config). Raw matched is also logged. Reason: at p_curve (about 10,000 offered packets per 10 s run) the 27-frame control class is a constant 0.27% bias, the same order as the drop thresholds, and must not sit inside a drop percentage.

**Session mode.** The matrix is run from a non-graphical session where possible (`systemctl isolate multi-user.target`, or the display manager stopped); the mode used, or why it was impossible, is recorded in ENV.md.

## 3. Interpretations of the ruling (made while writing this text; flagged for the reviewer)

1. The ruling names port 4040 in F and C; for non-matching runs the data port is 5050 and for flood runs both, so F, C and the envelope are applied per data stream (P above).
2. A flood run has two control connections, so V5'c applies per stream.
3. The canary rule is called V8; "canary CPU" is normalised per second of window so that idle windows and measured windows of different lengths compare.
4. The slope used for the C2 criteria is the slope of the difference to D, because the net per-packet CPU of any config contains a size-dependent generator and veth cost common to all configs, which would otherwise make the "in-kernel slope includes 0" test fail for a reason unrelated to the filter.
5. Idle windows use config D as the attached capture process (the floor config, the lightest), 3 per session, matrix duration; the idle capture process is assumed to have negligible CPU.
6. "Direction matches Fig. 2" is read as: slope(A) > slope(B) and intercept(A) > intercept(B); Fig. 2 values are at paper.txt L186-189 and are used for direction only.

## 4. Release conditions for the matrix (reviewer ruling 2, D4.5)

(a) calibration PASS under V5' with the knee reproduced (loss-free <= 2000 pps at 1500 B and <= 8000 pps at 64 B; p_curve = 1000 expected); (b) V5'c envelope validated at every matrix duration during calibration; (c) commits C2 and C3 pushed to origin; (d) canary_max and the idle baseline recorded from the calibration quiet windows; (e) parity audit on file (`logs/parity_audit.log`); (f) ENV.md records the session mode. Then the matrix runs exactly as pre-registered plus these addenda.

## 5. Amendments table (for REPORT.md)

| commit | date | trigger | mechanism |
|---|---|---|---|
| 3591267 | 2026-10-18 | pre-registration | design, harness and thresholds frozen before any run |
| 8038194 | 2026-10-18 | smoke runs exposed parser and ownership bugs | bug fixes only, no rule change |
| C2 (A1) | 2026-10-19 | calibration failed under V5 at 1000 pps; R1 classified the excess as experiment-generated | V5 -> V5'a to V5'e, three-class decomposition |
| C2 (A2) | 2026-10-19 | smoke runs: background CPU noise, B 2x on unused cores | V8 canary, idle subtraction, slope metric, R-C2/R-C3, M2 |
