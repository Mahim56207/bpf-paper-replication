#!/usr/bin/env python3
"""Phase 8.2: reduce one perf.data (perf record -e cpu-clock -g -a -C 1,4) to the sample counts of docs/phase8_2_design.md section 4.
Runs `perf script` (needs the privileges of the user who recorded: run as root) and counts, from the call chain of every sample:
  S      = samples on CPU 1 or 4 whose comm is not an idle task (swapper, swapper/N)
  tap    = samples in S with a frame named packet_rcv anywhere in the chain          (f_X numerator, design section 4)
  rx     = samples in S with __udp4_lib_rcv, udp_queue_rcv_skb or __udp_enqueue_schedule_skb in the chain and no packet_rcv
  other  = the rest of S
Also: the top comms and leaf symbols of S, and every frame symbol that looks AF_PACKET related (regex 'packet|_nit'), with the
number of samples whose chain contains it, so that a handler other than packet_rcv would be noticed (design section 4).
Cross-check: the number of samples parsed from the call-chain output must equal the number of lines `perf script -G` prints (fails loudly).
Usage: python3 -I scripts/p8_2_perf_counts.py <perf.data> <out.json>"""
import collections, json, os, re, subprocess, sys

data, out = sys.argv[1], sys.argv[2]
if os.path.exists(out):
    os.remove(out)
if not os.path.getsize(data):
    sys.exit("FATAL: %s is empty" % data)


def perf_script(extra):
    r = subprocess.run(["perf", "script", "-i", data, "-F", "comm,cpu,ip,sym"] + extra, capture_output=True, text=True)
    if r.returncode:
        sys.exit("FATAL: perf script failed (rc=%d): %s" % (r.returncode, r.stderr[-500:]))
    return r.stdout, r.stderr


txt, err = perf_script([])
flat, _ = perf_script(["-G"])
n_flat = len([l for l in flat.splitlines() if l.strip()])

HDR = re.compile(r"^(?P<comm>.+?)\s+\[(?P<cpu>\d+)\]\s*$")
samples, cur = [], None
for line in txt.splitlines():
    if not line.strip():
        continue
    if line[0] not in " \t":
        m = HDR.match(line)
        if not m:
            sys.exit("FATAL: cannot parse perf script header line: %r" % line)
        cur = {"comm": m.group("comm").strip(), "cpu": int(m.group("cpu")), "frames": []}
        samples.append(cur)
    else:
        toks = line.split()
        if len(toks) < 2:
            cur["frames"].append("[unknown]")
        else:
            cur["frames"].append(re.sub(r"\+0x[0-9a-f]+$", "", toks[1]))
if len(samples) != n_flat or not samples:
    sys.exit("FATAL: parsed %d samples from the call-chain listing but `perf script -G` has %d lines" % (len(samples), n_flat))

IDLE = re.compile(r"^swapper(/\d+)?$")
RX = {"__udp4_lib_rcv", "udp_queue_rcv_skb", "__udp_enqueue_schedule_skb"}
PK = re.compile(r"packet|_nit")
res = {"perf_data": data, "samples_total": len(samples), "per_cpu": collections.Counter(), "S": 0, "tap": 0, "rx": 0, "other": 0,
       "idle_on_sender_cores": 0, "other_cpus": 0, "comms_S": collections.Counter(), "leaf_S": collections.Counter(),
       "idle_comm_names": collections.Counter(), "packet_symbols_in_S": collections.Counter(), "no_callchain": 0,
       "S_iperf3": 0, "tap_iperf3": 0}   # informational: the same counts restricted to comm iperf3
for s in samples:
    res["per_cpu"][str(s["cpu"])] += 1
    if s["cpu"] not in (1, 4):
        res["other_cpus"] += 1
        continue
    if IDLE.match(s["comm"]):
        res["idle_on_sender_cores"] += 1
        res["idle_comm_names"][s["comm"]] += 1
        continue
    res["S"] += 1
    fr = set(s["frames"])
    if not s["frames"]:
        res["no_callchain"] += 1
    res["comms_S"][s["comm"]] += 1
    if s["frames"]:
        res["leaf_S"][s["frames"][0]] += 1
    if s["comm"] == "iperf3":
        res["S_iperf3"] += 1
        res["tap_iperf3"] += "packet_rcv" in fr
    if "packet_rcv" in fr:
        res["tap"] += 1
    elif fr & RX:
        res["rx"] += 1
    else:
        res["other"] += 1
    for f in fr:
        if PK.search(f):
            res["packet_symbols_in_S"][f] += 1
if res["S"] == 0:
    sys.exit("FATAL: no sample in S (CPUs 1 and 4, non-idle)")
res["f_tap"] = res["tap"] / res["S"]
res["f_rx"] = res["rx"] / res["S"]
for k in ("per_cpu", "comms_S", "leaf_S", "idle_comm_names", "packet_symbols_in_S"):
    res[k] = dict(collections.Counter(res[k]).most_common(25))
res["perf_script_stderr"] = err.strip()[:300]
json.dump(res, open(out, "w"), indent=1)
if not os.path.exists(out) or os.path.getsize(out) == 0:
    sys.exit("FATAL: %s was not written" % out)
print("%s: %d samples, S=%d, f_tap=%.4f, f_rx=%.4f, no_callchain=%d; packet-related symbols: %s" % (
    os.path.basename(data), res["samples_total"], res["S"], res["f_tap"], res["f_rx"], res["no_callchain"],
    ", ".join("%s=%d" % kv for kv in list(res["packet_symbols_in_S"].items())[:8]) or "none"))
