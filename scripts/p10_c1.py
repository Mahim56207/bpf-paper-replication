#!/usr/bin/env python3
"""Phase 10 WP3: C1 hardening (docs/phase10_design.md section 6). Uses the Phase 6c tools and frozen traces unchanged (src/c1_interp.c, src/c1_oracle.c, build/p6c/traces,
the evaluator-only attribution of amendment A3); only the builds and the inputs differ. Stages (run from the repo root, no root needed):
  build                          oracle and the six interpreter builds (gcc, clang x O0, O2, O3; count build and Ir build each) into build/p10/c1/
  grid                           (a) primary pairing on mix M0: BPF-opt, BPF-raw and CSPF sc-fused, every build: decision equivalence + callgrind M2 + M1
  check DIR                      decision check of the CSPF set in DIR (files F1.sm .. F4.sm) against libpcap on the three mixes and the edge trace; prints mismatch counts only
  indep DIR                      (b) mixes M0, Mip, Mnonip, build gcc-O2: BPF-opt, our CSPF sc-fused and the independent set DIR
  real TRACE H G                 (c) real mix: our CSPF programs regenerated for hosts H and G (dotted quad), filters with the same hosts, builds gcc-O2 and clang-O2
Outputs: logs/p10/wp3/<stage>_equiv.tsv and <stage>_m2.tsv (deleted first, checked after). M2 = Ir attributed to the evaluator functions (amendment A3).
"""
import concurrent.futures as cf
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
B = ROOT / "build" / "p10" / "c1"
SMOKE = os.environ.get("P10_SMOKE") == "1"          # smoke runs: one build, one chunk, outputs under logs/p10/smoke (excluded from every verdict)
LOG = ROOT / "logs" / "p10" / ("smoke" if SMOKE else "wp3")
TR = ROOT / "build" / "p6c" / "traces"
FREEZE = ROOT / "logs" / "p6c" / "p6c_design_freeze.log"
FILTERS = ("F1", "F2", "F3", "F4")
EXPR = {"F1": "ip", "F2": "ip host 10.0.0.10", "F3": "ip and tcp and (port 79 or port 53 or port 513 or port 514)", "F4": "host 10.0.0.10 and host 10.0.0.20"}
BUILDS = [(cc, o) for cc in ("gcc", "clang") for o in ("O0", "O2", "O3")]
CHUNK = 1000
EVAL_FUNCS = ("c1_eval_bpf", "c1_eval_sm", "be16", "be32", "word_at")
_EVAL_RE = re.compile(r":(%s)('\d+)?$" % "|".join(EVAL_FUNCS))
SC_OURS = {"F1": "F1_sc_any.sm", "F2": "F2_sc_any.sm", "F3": "F3_sc_fused.sm", "F4": "F4_sc_any.sm"}


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def need(r, what):
    if r.returncode:
        sys.exit("FATAL: %s failed (rc %d): %s %s" % (what, r.returncode, r.stdout.strip()[-300:], r.stderr.strip()[-600:]))
    return r


def tag(cc, o):
    return "%s-%s" % (cc, o)


def eval_ir(profile):
    r = need(run(["callgrind_annotate", "--threshold=100", "--auto=no", profile]), "callgrind_annotate " + str(profile))
    total = 0
    for line in r.stdout.splitlines():
        m = re.match(r"\s*([0-9,]+) \(\s*[0-9.]+%\)\s+(\S+)", line)
        if m and _EVAL_RE.search(m.group(2)):
            total += int(m.group(1).replace(",", ""))
    return total


def machine(prog):
    return "bpf" if prog.startswith("bpf") else "sm"


def out_files(stage):
    return LOG / (stage + "_equiv.tsv"), LOG / (stage + "_m2.tsv")


def start(stage):
    LOG.mkdir(parents=True, exist_ok=True)
    for f in out_files(stage):
        if f.exists():
            f.unlink()


def finish(stage):
    for f in out_files(stage):
        if not f.is_file() or f.stat().st_size == 0:
            sys.exit("FATAL: %s was not created" % f)


def trace_ok(name):
    want = None
    for line in FREEZE.read_text().splitlines():
        if line.endswith("build/p6c/traces/%s.pcap" % name):
            want = line.split()[0]
    got = hashlib.sha256((TR / (name + ".pcap")).read_bytes()).hexdigest()
    if want is None or want != got:
        sys.exit("FATAL: trace %s hash %s does not match the frozen value %s" % (name, got, want))
    return got


# ------------------------------------------------------------------------------------------------ build
def stage_build():
    B.mkdir(parents=True, exist_ok=True)
    cf_ = ["-g", "-Wall", "-Wextra", "-std=gnu11", "-Isrc"]
    need(run(["gcc", "-O2"] + cf_ + ["-o", B / "c1_oracle", "src/c1_oracle.c", "-lpcap"]), "build oracle")
    for cc, o in BUILDS:
        d = B / tag(cc, o)
        d.mkdir(exist_ok=True)
        for f in ("c1_interp_count", "c1_interp_ir"):
            if (d / f).exists():
                (d / f).unlink()
        need(run([cc, "-" + o] + cf_ + ["-DC1_COUNT", "-o", d / "c1_interp_count", "src/c1_interp.c"]), "build %s count" % tag(cc, o))
        need(run([cc, "-" + o] + cf_ + ["-o", d / "c1_interp_ir", "src/c1_interp.c"]), "build %s ir" % tag(cc, o))
        for f in ("c1_interp_count", "c1_interp_ir"):
            if not (d / f).is_file():
                sys.exit("FATAL: %s missing" % (d / f))
        print("built", d)
    print(run(["gcc", "--version"]).stdout.splitlines()[0])
    print(run(["clang", "--version"]).stdout.splitlines()[0])
    return 0


# ------------------------------------------------------------------------------------------------ shared steps
def oracle(mixname, exprs, pcap):
    """libpcap programs (optimized and not) and decisions for each filter on one trace. Returns {filter: prefix}."""
    od = B / "oracle" / mixname
    if od.exists():
        shutil.rmtree(od)
    od.mkdir(parents=True)
    res = {}
    for f in FILTERS:
        pre = od / f
        r = need(run([B / "c1_oracle", exprs[f], pcap, pre]), "oracle %s %s" % (mixname, f))
        print(r.stdout.strip())
        for suf in (".opt.bpf", ".raw.bpf", ".dec", ".rawdec"):
            if not (od / (f + suf)).is_file():
                sys.exit("FATAL: oracle did not create %s" % (od / (f + suf)))
        res[f] = pre
    return res


def prog_path(f, prog, orc, sm_dir, sm_names):
    if prog == "bpf-opt":
        return Path(str(orc[f]) + ".opt.bpf")
    if prog == "bpf-raw":
        return Path(str(orc[f]) + ".raw.bpf")
    return sm_dir / sm_names[f]


def equiv(build_tag, mixname, pcap, orc, progs, sm_sets, rows):
    """Decision equivalence of every (filter, program) against libpcap's decision for the same program (amendment A2 of Phase 6c). Returns failures."""
    bad = 0
    exe = B / build_tag / "c1_interp_count"
    for f in FILTERS:
        dec_opt = Path(str(orc[f]) + ".dec").read_text().strip()
        dec_raw = Path(str(orc[f]) + ".rawdec").read_text().strip()
        for prog in progs:
            pf = prog_path(f, prog, orc, *sm_sets[prog]) if prog in sm_sets else prog_path(f, prog, orc, None, None)
            csv = B / "csv" / ("%s_%s_%s_%s.csv" % (build_tag, mixname, f, prog))
            csv.parent.mkdir(exist_ok=True)
            if csv.exists():
                csv.unlink()
            r = need(run([exe, "--machine", machine(prog), "--prog", pf, "--pcap", pcap, "--csv", csv]), "interp %s %s %s %s" % (build_tag, mixname, f, prog))
            if not csv.is_file():
                sys.exit("FATAL: %s was not created" % csv)
            got = [l.split(",")[1] for l in csv.read_text().splitlines()[1:]]
            dec = dec_raw if prog == "bpf-raw" else dec_opt
            mism = sum(1 for a, b in zip(dec, got) if a != b) + abs(len(dec) - len(got))
            rows.append((build_tag, mixname, f, prog, len(got), mism))
            bad += mism != 0
    return bad


def m2_task(a):
    build_tag, mixname, pcap, f, prog, pf, chunk, nch = a
    fn = "c1_eval_bpf" if prog.startswith("bpf") else "c1_eval_sm"
    out = B / "cg" / ("%s_%s_%s_%s_%d.out" % (build_tag, mixname, f, prog, chunk))
    out.parent.mkdir(exist_ok=True)
    if out.exists():
        out.unlink()
    r = need(run(["valgrind", "--tool=callgrind", "--toggle-collect=" + fn, "--callgrind-out-file=" + str(out), B / build_tag / "c1_interp_ir", "--machine", machine(prog),
                  "--prog", pf, "--pcap", pcap, "--first", chunk * CHUNK, "--count", CHUNK]), "callgrind " + out.name)
    ir = None
    for line in out.read_text().splitlines():
        if line.startswith("summary:"):
            ir = int(line.split()[1])
    if ir is None:
        sys.exit("FATAL: no summary line in " + str(out))
    acc = int(r.stdout.split("accepts=")[1].split()[0])
    csv = B / "csv" / ("%s_%s_%s_%s.csv" % (build_tag, mixname, f, prog))
    m1 = sum(int(l.split(",")[2]) for l in csv.read_text().splitlines()[1:][chunk * CHUNK:(chunk + 1) * CHUNK])
    return (build_tag, mixname, f, prog, chunk, CHUNK, ir, eval_ir(out), acc, m1)


def write_tsv(stage, equiv_rows, m2_rows):
    e, m = out_files(stage)
    with open(e, "w") as o:
        o.write("build\tmix\tfilter\tprogram\tframes\tdecision_mismatches\n")
        for r in equiv_rows:
            o.write("\t".join(map(str, r)) + "\n")
    with open(m, "w") as o:
        o.write("build\tmix\tfilter\tprogram\tchunk\tframes\tIr\tIr_eval\taccepts\tM1_instr\n")
        for r in m2_rows:
            o.write("\t".join(map(str, r)) + "\n")
    finish(stage)


def n_chunks(pcap):
    d = Path(pcap).read_bytes()
    import struct
    magic = struct.unpack("<I", d[:4])[0]
    e = "<" if magic in (0xA1B2C3D4, 0xA1B23C4D) else ">"
    off = n = 0
    off = 24
    while off + 16 <= len(d):
        off += 16 + struct.unpack(e + "I", d[off + 8: off + 12])[0]
        n += 1
    return n


def go(stage, builds, mixes, progs, sm_sets, exprs_by_mix, pcap_by_mix):
    start(stage)
    equiv_rows, tasks, bad = [], [], 0
    for mixname in mixes:
        pcap = pcap_by_mix[mixname]
        orc = oracle(mixname, exprs_by_mix[mixname], pcap)
        nch = 1 if SMOKE else min(10, n_chunks(pcap) // CHUNK)
        if nch < (1 if SMOKE else 5):
            sys.exit("FATAL: trace %s has fewer than 5000 frames" % mixname)
        for cc, o in builds:
            bt = tag(cc, o)
            bad += equiv(bt, mixname, pcap, orc, progs, sm_sets, equiv_rows)
            for f in FILTERS:
                for prog in progs:
                    pf = prog_path(f, prog, orc, *sm_sets[prog]) if prog in sm_sets else prog_path(f, prog, orc, None, None)
                    tasks += [(bt, mixname, pcap, f, prog, pf, c, nch) for c in range(nch)]
    print("%s: %d decision comparisons, %d with mismatches; %d callgrind runs follow" % (stage, len(equiv_rows), bad, len(tasks)))
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        m2_rows = list(ex.map(m2_task, tasks))
    write_tsv(stage, equiv_rows, m2_rows)
    print("%s: wrote %s and %s (%d M2 rows)" % ((stage,) + tuple(str(p) for p in out_files(stage)) + (len(m2_rows),)))
    return 2 if bad else 0          # exit 2: some decision mismatches (the summary excludes those builds); any other failure exits 1 through sys.exit with a message


def pcap_of(mix):
    for cand in (TR / (mix + ".pcap"), Path(mix)):
        if cand.exists():
            return cand
    sys.exit("FATAL: no trace " + mix)


# ------------------------------------------------------------------------------------------------ stages
def stage_grid():
    trace_ok("mix_M0")
    return go("grid", BUILDS[:1] if SMOKE else BUILDS, ["mix_M0"], ["bpf-opt", "bpf-raw", "sm-sc-fused"], {"sm-sc-fused": (ROOT / "src" / "c1_progs", SC_OURS)},
              {"mix_M0": EXPR}, {"mix_M0": TR / "mix_M0.pcap"})


def stage_check(d):
    d = Path(d)
    names = {f: "%s.sm" % f for f in FILTERS}
    for f in FILTERS:
        if not (d / names[f]).is_file():
            sys.exit("FATAL: %s missing" % (d / names[f]))
    bad = 0
    for mixname in ("mix_M0", "mix_Mip", "mix_Mnonip", "edge"):
        trace_ok(mixname)
        od = B / "check" / mixname
        if od.exists():
            shutil.rmtree(od)
        od.mkdir(parents=True)
        for f in FILTERS:
            need(run([B / "c1_oracle", EXPR[f], TR / (mixname + ".pcap"), od / f]), "oracle %s %s" % (mixname, f))
            dec = (od / (f + ".dec")).read_text().strip()
            csv = od / (f + ".csv")
            need(run([B / "gcc-O2" / "c1_interp_count", "--machine", "sm", "--prog", d / names[f], "--pcap", TR / (mixname + ".pcap"), "--csv", csv]), "interp check %s %s" % (mixname, f))
            got = [l.split(",")[1] for l in csv.read_text().splitlines()[1:]]
            mism = sum(1 for a, b in zip(dec, got) if a != b) + abs(len(dec) - len(got))
            print("check %-10s %s: %d frames, %d decision mismatches against libpcap" % (mixname, f, len(got), mism))
            bad += mism != 0
    print("check: %s" % ("all decisions equal libpcap's" if not bad else "%d (trace, filter) pairs with mismatches" % bad))
    return 1 if bad else 0


def stage_indep(d):
    d = Path(d)
    names = {f: "%s.sm" % f for f in FILTERS}
    for f in FILTERS:
        if not (d / names[f]).is_file():
            sys.exit("FATAL: %s missing" % (d / names[f]))
    mixes = ["mix_M0", "mix_Mip", "mix_Mnonip"]
    for m in mixes:
        trace_ok(m)
    return go("indep", [("gcc", "O2")], mixes, ["bpf-opt", "sm-ours", "sm-indep"],
              {"sm-ours": (ROOT / "src" / "c1_progs", SC_OURS), "sm-indep": (d, names)},
              {m: EXPR for m in mixes}, {m: TR / (m + ".pcap") for m in mixes})


def stage_real(trace, h, g):
    trace = Path(trace)
    sha = hashlib.sha256(trace.read_bytes()).hexdigest()
    print("real trace sha256 %s (%s)" % (sha, trace))
    gen_dir = B / "real_progs"
    if gen_dir.exists():
        shutil.rmtree(gen_dir)
    spec = importlib.util.spec_from_file_location("c1gen", ROOT / "scripts" / "c1_gen_progs.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    hh = [int(x) for x in h.split(".")]
    gg = [int(x) for x in g.split(".")]
    gen.H = (hh[0] << 8 | hh[1], hh[2] << 8 | hh[3])
    gen.G = (gg[0] << 8 | gg[1], gg[2] << 8 | gg[3])
    gen_dir.mkdir(parents=True)
    for fused in (False, True):
        t = gen.trees(fused)
        for f in FILTERS:
            if fused and f != "F3":
                continue
            tagname = ("fused" if fused else "general") if f == "F3" else "any"
            gen.emit(gen_dir / ("%s_sc_%s.sm" % (f, tagname)), gen.sc(t[f]))
    exprs = dict(EXPR)
    exprs["F2"] = "ip host %s" % h
    exprs["F4"] = "host %s and host %s" % (h, g)
    # the oracle takes the trace path; give it under the name "real"
    real_pcap = B / "real.pcap"
    shutil.copyfile(trace, real_pcap)
    return go("real", [("gcc", "O2")] if SMOKE else [("gcc", "O2"), ("clang", "O2")], ["real"], ["bpf-opt", "bpf-raw", "sm-sc-fused"], {"sm-sc-fused": (gen_dir, SC_OURS)},
              {"real": exprs}, {"real": real_pcap})


if __name__ == "__main__":
    st = sys.argv[1] if len(sys.argv) > 1 else ""
    if st == "build":
        sys.exit(stage_build())
    if st == "grid":
        sys.exit(stage_grid())
    if st == "check" and len(sys.argv) == 3:
        sys.exit(stage_check(sys.argv[2]))
    if st == "indep" and len(sys.argv) == 3:
        sys.exit(stage_indep(sys.argv[2]))
    if st == "real" and len(sys.argv) == 5:
        sys.exit(stage_real(sys.argv[2], sys.argv[3], sys.argv[4]))
    sys.exit(__doc__)
