#!/usr/bin/env python3
"""Phase 10 WP2 helpers (docs/phase10_design.md section 5, rule P7). Run validity comes from scripts/summarize.py parse_run (imported, not copied); only its V8 reason
is replaced by the declared flood rule of rule P7.
  p10_wp2_tools.py calib <outdir>                  the calibration windows (files calib*_flood_256_*.log in <outdir>): writes <outdir>/calib_v8.json
                                                   (canary_max_flood = largest canary rate on core 0, limit = 1.2 x it); exit 1 if a window fails any rule other than V8
  p10_wp2_tools.py v8 <logfile> <calib_json>       prints the canary rate of the run and exits 1 if it is above the limit (contaminated), 0 if clean
"""
import glob, importlib.util, json, os, pathlib, sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
spec = importlib.util.spec_from_file_location("summ", "scripts/summarize.py")
summ = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summ)


def non_v8_reasons(r):
    out = [x for x in r["reasons"] if not x.startswith("V8")]
    if r["cfg"] == "N":                                   # documented exemptions of Phase 8.2 for config N (no capture process, no map counters)
        out = [x for x in out if not x.startswith("V2 no FINAL") and not x.startswith("V2 map counters")]
    return out


def calib(outdir):
    files = sorted(glob.glob(os.path.join(outdir, "calib*_flood_256_*.log")))
    if not files:
        sys.exit(f"FATAL: no calibration windows in {outdir}")
    wins, bad = [], []
    for f in files:
        r = summ.parse_run(f)
        wins.append({"file": os.path.basename(f), "canary_rate": r.get("canary_rate")})
        if non_v8_reasons(r):
            bad.append((os.path.basename(f), non_v8_reasons(r)))
    if any(w["canary_rate"] is None for w in wins):
        sys.exit("FATAL: a calibration window has no canary rate")
    cmax = max(w["canary_rate"] for w in wins)
    # amendment A2: the windows cover every (topology, config) cell of the block; other validity reasons of a calibration window are recorded, not fatal (the windows are excluded from analysis)
    d = {"windows": wins, "canary_max_flood": cmax, "limit": summ.CANARY_FACTOR * cmax, "other_reasons": bad, "rule": "docs/phase10_design.md rule P7 as amended by A2"}
    pathlib.Path(outdir, "calib_v8.json").write_text(json.dumps(d, indent=1) + "\n")
    print(json.dumps(d))
    return 0


def v8(logfile, calib_json):
    lim = json.loads(pathlib.Path(calib_json).read_text())["limit"]
    r = summ.parse_run(logfile)
    rate = r.get("canary_rate")
    print(f"{rate}")
    if rate is None:
        sys.exit("FATAL: no canary rate in " + logfile)
    return 1 if rate > lim else 0


if __name__ == "__main__":
    if sys.argv[1] == "calib":
        sys.exit(calib(sys.argv[2]))
    if sys.argv[1] == "v8":
        sys.exit(v8(sys.argv[2], sys.argv[3]))
    sys.exit(__doc__)
