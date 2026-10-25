#!/usr/bin/env python3
"""Phase 6c driver (docs/phase6c_design.md). Usage: python3 -I scripts/c1_run.py equiv|m2|attrib
Run from the repository root after scripts/c1_build.sh, scripts/c1_gen_progs.py and
scripts/c1_make_trace.py. Output goes to logs/p6c/ (tee it); build/p6c/ holds scratch files.

equiv : oracle (libpcap) per trace and filter; every interpreter program on every trace; decision
        equivalence frame by frame; tcpdump -r match counts; M1 per-frame CSVs of the three mixes
        (gzip, logs/p6c/m1/); table logs/p6c/p6c_equiv.tsv.
m2    : callgrind runs (toggle-collect on the evaluator), 10 chunks of 1000 frames per mix, filter and
        program; table logs/p6c/p6c_m2.tsv; build agreement against the M1 CSVs.
attrib: callgrind_annotate of one run per evaluator (amendment A1 check i).
"""
import concurrent.futures as cf
import gzip
import hashlib
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build" / "p6c"
LOG = ROOT / "logs" / "p6c"
TR = B / "traces"
EXPR = {
    "F1": "ip",
    "F2": "ip host 10.0.0.10",
    "F3": "ip and tcp and (port 79 or port 53 or port 513 or port 514)",
    "F4": "host 10.0.0.10 and host 10.0.0.20",
}
FILTERS = ("F1", "F2", "F3", "F4")
MIXES = ("M0", "Mip", "Mnonip")
TRACES = {"M0": "mix_M0", "Mip": "mix_Mip", "Mnonip": "mix_Mnonip", "edge": "edge", "corpus38": "corpus38"}
PROGS = ("bpf-opt", "bpf-raw", "sm-full-general", "sm-sc-general", "sm-full-fused", "sm-sc-fused")
CHUNKS, CHUNK = 10, 1000


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def sm_file(f, prog):
    _s, mode, style = prog.split("-")
    return ROOT / "src" / "c1_progs" / ("%s_%s_%s.sm" % (f, mode, style if f == "F3" else "any"))


def prog_file(f, prog, tracekey):
    if prog == "bpf-opt":
        return B / "oracle" / ("%s_%s.opt.bpf" % (tracekey, f))
    if prog == "bpf-raw":
        return B / "oracle" / ("%s_%s.raw.bpf" % (tracekey, f))
    return sm_file(f, prog)


def machine(prog):
    return "bpf" if prog.startswith("bpf") else "sm"


def count_pcap_records(path):
    d = Path(path).read_bytes()
    magic = struct.unpack("<I", d[:4])[0]
    if magic in (0xA1B2C3D4, 0xA1B23C4D):
        e = "<"
    elif magic in (0xD4C3B2A1, 0x4D3CB2A1):
        e = ">"
    else:
        raise SystemExit("unknown pcap magic %x" % magic)
    off, n = 24, 0
    while off + 16 <= len(d):
        caplen = struct.unpack(e + "I", d[off + 8: off + 12])[0]
        off += 16 + caplen
        n += 1
    return n


def stage_equiv():
    (B / "oracle").mkdir(parents=True, exist_ok=True)
    (LOG / "m1").mkdir(parents=True, exist_ok=True)
    rows, bad = [], 0
    prog_hashes = {}
    opt_raw_diff = []
    for tkey, tname in TRACES.items():
        pcap = TR / (tname + ".pcap")
        for f in FILTERS:
            pre = B / "oracle" / ("%s_%s" % (tkey, f))
            r = run([B / "c1_oracle", EXPR[f], pcap, pre])
            print(r.stdout.strip() + (" STDERR " + r.stderr.strip() if r.stderr.strip() else ""))
            if r.returncode:
                print("FAIL oracle rc=%d trace=%s filter=%s" % (r.returncode, tkey, f))
                bad += 1
                continue
            for kind in ("opt", "raw"):
                prog_hashes.setdefault((f, kind), set()).add(hashlib.sha256((pre.with_suffix("." + kind + ".bpf")).read_bytes()).hexdigest())
            dec_opt = (pre.with_suffix(".dec")).read_text().strip()
            dec_raw = (pre.with_suffix(".rawdec")).read_text().strip()
            acc_oracle = dec_opt.count("1")
            n_opt_raw = sum(1 for a, b in zip(dec_opt, dec_raw) if a != b)
            if n_opt_raw:
                print("NOTE libpcap opt vs raw program differ on %d frame(s): trace=%s filter=%s (amendment A2)" % (n_opt_raw, tkey, f))
                opt_raw_diff.append((tkey, f, n_opt_raw))
            # second readout: tcpdump -r (same libpcap compiler, different reader/pipeline)
            out = B / "oracle" / ("%s_%s.tcpdump.pcap" % (tkey, f))
            t = run(["tcpdump", "-r", pcap, "-w", out, "-n", EXPR[f]])
            tcpdump_n = count_pcap_records(out) if t.returncode == 0 else -1
            for prog in PROGS:
                pf = prog_file(f, prog, tkey)
                csv = B / "oracle" / ("%s_%s_%s.csv" % (tkey, f, prog))
                c = run([B / "c1_interp_count", "--machine", machine(prog), "--prog", pf, "--pcap", pcap, "--csv", csv])
                i = run([B / "c1_interp_ir", "--machine", machine(prog), "--prog", pf, "--pcap", pcap])
                if c.returncode or i.returncode:
                    print("FAIL interp rc=%d/%d %s %s %s: %s %s" % (c.returncode, i.returncode, tkey, f, prog, c.stderr.strip(), i.stderr.strip()))
                    bad += 1
                    continue
                got = []
                vm = 0
                for line in csv.read_text().splitlines()[1:]:
                    _idx, d, v = line.split(",")
                    got.append(d)
                    vm += int(v)
                dec = dec_raw if prog == "bpf-raw" else dec_opt  # amendment A2: each BPF program against its own libpcap decision
                mism = sum(1 for a, b in zip(dec, got) if a != b) + abs(len(dec) - len(got))
                hash_ok = c.stdout.split("dechash=")[1].strip() == i.stdout.split("dechash=")[1].strip()
                acc_i = got.count("1")
                ref = "raw" if prog == "bpf-raw" else "opt"
                rows.append((tkey, f, prog, len(got), dec.count("1"), acc_i, tcpdump_n, mism, int(hash_ok), ref))
                if mism or not hash_ok or tcpdump_n != acc_oracle:
                    bad += 1
                    print("FAIL %s %s %s: mismatches=%d count_vs_ir_build_hash_ok=%s oracle_accepts=%d tcpdump=%d" % (tkey, f, prog, mism, hash_ok, acc_oracle, tcpdump_n))
                if tkey in MIXES:
                    with gzip.open(LOG / "m1" / ("%s_%s_%s.csv.gz" % (tkey, f, prog)), "wt") as g:
                        g.write(csv.read_text())
    with open(LOG / "p6c_equiv.tsv", "w") as o:
        o.write("trace\tfilter\tprogram\tframes\toracle_accepts\tinterp_accepts\ttcpdump_accepts\tdecision_mismatches\tcount_ir_build_hash_equal\treference_program\n")
        for r in rows:
            o.write("\t".join(map(str, r)) + "\n")
    for (f, kind), hs in sorted(prog_hashes.items()):
        print("libpcap %s program for %s identical across traces: %s" % (kind, f, "yes" if len(hs) == 1 else "NO (%d variants)" % len(hs)))
        if len(hs) != 1:
            bad += 1
    for t, f, n in opt_raw_diff:
        print("libpcap opt vs raw disagreement recorded: trace=%s filter=%s frames=%d" % (t, f, n))
    tot = sum(r[3] for r in rows)
    print("equiv: %d (trace, filter, program) combinations, %d frames evaluated, %d failures" % (len(rows), tot, bad))
    return 1 if bad else 0


def m2_task(args):
    mix, f, prog, chunk = args
    tname = TRACES[mix]
    pf = prog_file(f, prog, mix)
    fn = "c1_eval_bpf" if prog.startswith("bpf") else "c1_eval_sm"
    out = B / "cg" / ("%s_%s_%s_%d.out" % (mix, f, prog, chunk))
    r = run(["valgrind", "--tool=callgrind", "--toggle-collect=" + fn, "--callgrind-out-file=" + str(out),
             B / "c1_interp_ir", "--machine", machine(prog), "--prog", pf, "--pcap", TR / (tname + ".pcap"),
             "--first", chunk * CHUNK, "--count", CHUNK])
    ir = None
    for line in out.read_text().splitlines():
        if line.startswith("summary:"):
            ir = int(line.split()[1])
    acc = int(r.stdout.split("accepts=")[1].split()[0])
    return (mix, f, prog, chunk, CHUNK, ir, acc)


def stage_m2():
    (B / "cg").mkdir(parents=True, exist_ok=True)
    tasks = [(m, f, p, c) for m in MIXES for f in FILTERS for p in PROGS for c in range(CHUNKS)]
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(m2_task, tasks))
    bad = 0
    with open(LOG / "p6c_m2.tsv", "w") as o:
        o.write("mix\tfilter\tprogram\tchunk\tframes\tIr\taccepts_ir_build\taccepts_count_build\n")
        for mix, f, prog, chunk, n, ir, acc in res:
            lines = gzip.open(LOG / "m1" / ("%s_%s_%s.csv.gz" % (mix, f, prog)), "rt").read().splitlines()[1:]
            acc_c = sum(1 for l in lines[chunk * CHUNK:(chunk + 1) * CHUNK] if l.split(",")[1] == "1")
            if acc != acc_c or ir is None:
                bad += 1
                print("FAIL build agreement %s %s %s chunk %d: ir_build=%s count_build=%s ir=%s" % (mix, f, prog, chunk, acc, acc_c, ir))
            o.write("%s\t%s\t%s\t%d\t%d\t%s\t%d\t%d\n" % (mix, f, prog, chunk, n, ir, acc, acc_c))
    print("m2: %d callgrind runs, %d build-agreement failures" % (len(res), bad))
    return 1 if bad else 0


def stage_attrib():
    bad = 0
    for prog, f in (("bpf-opt", "F3"), ("sm-sc-fused", "F3")):
        mix = "M0"
        out = B / "cg" / ("%s_%s_%s_0.out" % (mix, f, prog))
        if not out.exists():
            m2_task((mix, f, prog, 0))
        r = run(["callgrind_annotate", out])
        print("### callgrind_annotate %s" % out.name)
        print(r.stdout)
        # all collected cost must be on c1_eval_* lines
        funcs = [l for l in r.stdout.splitlines() if "c1_eval_" in l]
        print("attribution check %s: lines naming an evaluator = %d" % (prog, len(funcs)))
    return bad


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"equiv": stage_equiv, "m2": stage_m2, "attrib": stage_attrib}.get(stage)
    if not fn:
        raise SystemExit(__doc__)
    sys.exit(fn())
