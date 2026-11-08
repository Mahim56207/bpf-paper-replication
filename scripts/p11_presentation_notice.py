#!/usr/bin/env python3
"""Phase 11: put a "superseded" notice at the top of presentation.html. The deck is NOT deleted or edited otherwise: the notice is one block between two marker comments right after
the <body> tag, so removing the block gives back the original file byte for byte (scripts/p11_verify.sh checks that against origin/main). Numbers in the notice are computed here from
results/p10_summary.json and git, none is typed. Idempotent: an existing block is replaced. Usage: python3 scripts/p11_presentation_notice.py"""
import hashlib, html, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH = ROOT / "presentation.html"
BEGIN, END = "<!-- p11-superseded-notice:begin -->", "<!-- p11-superseded-notice:end -->"
S = json.load(open(ROOT / "results/p10_summary.json"))
L = {k: v["label"] for k, v in S["labels"].items()}
wb = S["wp1b"]
mm = wb["fits"]["memcpy"]["means"]
grid, indep, real = S["wp3"]["grid"], S["wp3"]["indep"], S["wp3"]["real"]
n_dir = sum(1 for c in grid.values() if c["direction"] == "HOLDS")
n_ord = sum(1 for c in grid.values() if c["order_holds"])
dir_fail = ", ".join(b for b, c in grid.items() if c["direction"] != "HOLDS") or "none"
f4_ind = indep["mix_M0"]["indep"]["R"]["F4"][1]
f4_real = [c["opt"]["R"]["F4"][1] for c in real.values()]
git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout
MIT = "REVERSED gap, cause not established (UNVERIFIED)"       # D12.1: named by what the data show, not by the mechanical output of rule P6
assert all(v == "REVERSED" for v in S["labels"]["C4-mitigation"]["detail"].values()), "the mitigation classes are no longer both REVERSED: rewrite this item"
n_logs = len([l for l in git("ls-files", "logs").splitlines() if l])
n_scripts = len([l for l in git("ls-files", "scripts").splitlines() if l])
kU = {r["quantity"]: r for r in wb["interval_table"]}["s_U, user-space drain path U"]
g = lambda x, d=4: f"{x:.{d}g}"

items = [
    ("Counts: \"2,597 raw logs\", \"65 automation scripts\", \"0 hand-typed numbers\"",
     f"No script of record reproduces these counts (git lists {n_logs} tracked files under logs/ and {n_scripts} under scripts/ when this notice was written), and REPORT.md (Self-audit) records that some numbers in the Phase 2 to 5 documents were typed by hand and that a few intermediate displays were not saved."),
    ("\"Pre-registered Matrix (110 rows)\", \"Design, thresholds and statistical criteria frozen before any execution\"",
     "True of the Phase 6 matrix (commit 3591267). The figures on the C2, C3 and C4 slides come from the Phase 8.3 re-run, which had no design document and no pre-declaration (DEVIATIONS D8.19)."),
    ("\"5 isolated virtual cores\"",
     "The cores were pinned, not isolated: no isolcpus is set on the kernel command line (logs/p10/probe/isolcpus.txt; ENV.md has no isolcpus entry)."),
    ("Environment \"Linux 6.17.0-19-generic\"",
     "The Phase 10 results ran on a different kernel build (ENV.md, D10.5)."),
    ("\"28.5 MHz SPARCstation 2\" and \"a 40 MB/s bus\" (and the 1993 copy time of 37.5 microseconds)",
     "Neither figure is in docs/paper.txt, which names only a Sparcstation 2 (L119). UNVERIFIED."),
    ("\"L1/L2 bandwidth exceeding 100 GB/s\", \"copying 1500 bytes takes < 15 nanoseconds\", \"noise +-2,000 to 5,000 ns\", \"SNR 1:200\", \"VM timer resolution ~3,000 ns\"",
     f"Not measured when the slide was written and not in any result file. The Phase 10 copy-floor microbenchmark (cache-resident memcpy, results/p10_summary.json) measured {g(mm['1500'])} ns for 1500 bytes and {g(mm['64'])} ns for 64 bytes, which is of the order of the slide's copy figure; the noise figures and the 1 : 200 ratio have no source and are UNVERIFIED."),
    ("\"Why per-byte slopes fail to separate\" (slopes drown in noise)",
     f"Superseded: the Phase 10 long-batch microbenchmarks resolved the user-space drain slope to {g(kU['estimate'])} ns/byte with a 90% interval of [{g(kU['lo'])}, {g(kU['hi'])}] (C2 {L['C2']}, C3 {L['C3']}, microbenchmarks of the in-kernel filter and the user-space drain path, not end-to-end capture)."),
    ("C1 slide: \"Register Architecture Wins in Every Dimension\", \"DIRECTION HOLDS\" for all four filters on both machines, F4 \"matching the headline\", verdict MIXED",
     f"Superseded by Phase 10 (C1 {L['C1']}): the direction holds in {n_dir} of {len(grid)} compiler and optimisation-level builds (it fails in: {dir_fail}) and the ordering of the ratios in {n_ord}; with an independent CSPF set Filter 4 gives {g(f4_ind, 3)} and on a real traffic mix {g(min(f4_real), 3)} to {g(max(f4_real), 3)}. The CSPF programs are our own, not the 1993 code."),
    ("C2 slide: \"The 1993 Hypothesis Holds Operationally\", \"completely insulates user-space applications\"",
     "The process-CPU and context-switch figures are in results/summary.md, but at one offered load (about 16000 pps) and as a process-level observation, not a per-byte measurement; the label was MIXED and the words \"Operationally Replicated\" were removed in Phase 9 (D8.24)."),
    ("\"Visual Separation Restored\": Config B cleanly separated below Config A across all packet sizes",
     "Not tested by any pre-declared rule; the net-over-floor columns of the reject curve in results/summary.md have standard errors as large as the values (some negative)."),
    ("C4 slides: \"Verdict: NOT SUPPORTED as a Receiver-Drop Claim\", \"The 1993 Bottleneck Inversion\"",
     f"NOT SUPPORTED was a post hoc sensitivity analysis that used an uncalibrated flood V8 floor (D8.22); under the frozen rule C4 was INCONCLUSIVE. Superseded by Phase 10: C4 {L['C4']} (capture-side CPU per matched packet of the user-space sniffer against the eBPF filter at paced rates, not the 1993 end-to-end speed-up), and with the capture on the receiving end the sender-side gap of Phase 8.2 is a {MIT} in the mitigated topology."),
    ("Phase 8.2 slide: \"the throughput degradation matched the predicted cycle loss within 22.5%\"",
     "S-H2 held only inside the pre-declared tolerance, with the observed ratios above the prediction; the samples are timer-based (no hardware PMU) and the share was measured under profiling (REPORT.md, UNVERIFIED items 10 and 17)."),
    ("\"The 20x Noise Reduction\": shutting down the desktop window reduced ambient noise by 19.2x",
     "The two idle figures come from different sessions and measurement sets; that the interactive session caused the noise is a hypothesis, not a tested cause (REPORT.md, UNVERIFIED item 20)."),
    ("\"The Pitfall of Hyper-Sensitive Canary Rules\": blips from legitimate softirq scheduling",
     "The cause of the canary blips was not tested, and the flood V8 floor that followed has no calibration record (D8.22)."),
    ("C5 slide: the verifier \"statically inlines the lookup address\" for array maps; \"enforces termination\"",
     "The inlining mechanism is the reviewer's account and was not read from kernel source (REPORT.md, UNVERIFIED item 3). Termination was tested in Phase 10 with one unbounded loop (rejected) and one bounded loop (accepted); that does not establish it for all programs."),
    ("Synthesis table and \"Defense Ready & Fully Reproducible ... audited\"",
     "Superseded by the final labels of REPORT.md. Not every number can be re-run: the raw logs of Phase 8.2 run set 1 were lost (D8.14) and the session label in the headers of 15 flood logs was edited (D8.23). The statements about eBPF as \"the foundation of modern infrastructure software\" are not results of this study."),
]
lis = "\n".join(f"<li><b>{html.escape(a)}</b><br>{html.escape(b)}</li>" for a, b in items)
block = f"""{BEGIN}
<div id="p11-superseded" style="position:fixed;top:0;left:0;right:0;z-index:2147483647;background:#7a1f0e;color:#fff;font:14px/1.45 system-ui,sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.4)">
<details open style="max-height:46vh;overflow:auto;padding:10px 16px">
<summary style="cursor:pointer;font-weight:700">SUPERSEDED: this deck predates Phase 10 and contains claims that the repository's record does not support. The final labels are in REPORT.md (section "Final labels after Phase 10"): C1 {html.escape(L['C1'])}, C2 {html.escape(L['C2'])}, C3 {html.escape(L['C3'])}, C4 {html.escape(L['C4'])}, C5 {html.escape(L['C5'])}. Click to fold or unfold the list.</summary>
<p style="margin:8px 0">The deck is kept unchanged below this notice. Claims listed here are unverified, unsupported or superseded; nothing below the notice was edited or deleted.</p>
<ol style="margin:0 0 6px 20px;padding:0">
{lis}
</ol>
</details>
</div>
<div style="height:2.2em"></div>
{END}
"""
text = PATH.read_text()
if BEGIN in text:
    a, b = text.index(BEGIN), text.index(END) + len(END) + 1
    text = text[:a] + text[b:]
m = re.search(r"<body[^>]*>\n?", text)
assert m, "no <body> tag"
new = text[:m.end()] + block + text[m.end():]
PATH.write_text(new)
orig = new.replace(block, "", 1)
print("notice inserted: %d items; the file without the notice has sha256 %s" % (len(items), hashlib.sha256(orig.encode()).hexdigest()))
