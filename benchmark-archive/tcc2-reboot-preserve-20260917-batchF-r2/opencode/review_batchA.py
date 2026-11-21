#!/usr/bin/env python3
"""Batch boundary semantic + 3-rep numerical review for frozen c10/m10 collection."""
import json, sys, statistics
from pathlib import Path

base = Path("mqtt-auth-biscuit/benchmarks")
new_dirs = [base / f"results-final-p1-56344b7-c10-m10-idx000-013-r{i}" for i in (1, 2, 3)]
old_dirs = [base / f"results-final-p1-b23eb22-c10-m10-idx000-013-r{i}" for i in (1, 2, 3)]

def load(d):
    out = {}
    for p in d.glob("*.json"):
        if p.name == "summary.json":
            continue
        with open(p) as f:
            out[p.stem] = json.load(f)
    return out

new = [load(d) for d in new_dirs]
old = [load(d) for d in old_dirs]
scenarios = sorted(new[0].keys())
print(f"inventory range: idx000-013 | expected 14 files/rep")
for i, d in enumerate(new_dirs):
    print(f"  {d.name}: actual {len(new[i])} scenario JSONs")
assert all(len(n) == 14 for n in new), "file count mismatch"
assert all(set(n.keys()) == set(scenarios) for n in new), "scenario set mismatch across reps"

fails, warns = [], []

def pct_ok(vals):
    keys = ["min", "p50", "p95", "p99", "max"]
    vs = [vals.get(k) for k in keys]
    if all(isinstance(v, (int, float)) for v in vs):
        return vs == sorted(vs), vs
    return None, vs

for s in scenarios:
    recs = [n[s] for n in new]
    # --- semantic: errors ---
    for i, r in enumerate(recs):
        errs = r["runs"][0]["loadgen"]["errors"]
        if errs:
            fails.append(f"{s} r{i+1} errors={errs}")
    # --- semantic: workload axes / topology ---
    for i, r in enumerate(recs):
        sc = r["scenario_config"]
        if not (sc.get("clients") == 10 and sc.get("messages") == 10):
            fails.append(f"{s} r{i+1} effective clients/messages != 10: {sc.get('clients')}/{sc.get('messages')}")
        if sc.get("requested_clients") != 10 or sc.get("requested_messages") != 10:
            fails.append(f"{s} r{i+1} requested axes != 10")
        if sc.get("workload_shape") != "matrix":
            fails.append(f"{s} r{i+1} workload_shape != matrix")
        topo = sc.get("client_topology") or {}
        if topo.get("mode") != "container-per-client":
            fails.append(f"{s} r{i+1} topology != container-per-client: {topo.get('mode')}")
        if str(topo.get("client_memory", "")) != "96m":
            fails.append(f"{s} r{i+1} client_memory != 96m: {topo.get('client_memory')}")
    # --- CONNECT behavior post-fix: no connect_failed timeouts; connect.count == 10 ---
    for i, r in enumerate(recs):
        lg = r["runs"][0]["loadgen"]
        cc = (lg.get("connect") or {}).get("count")
        if cc != 10:
            fails.append(f"{s} r{i+1} connect.count={cc} != 10")
        raw = lg.get("raw_metrics") or {}
        cf = raw.get("connect_failed", 0)
        if cf:
            fails.append(f"{s} r{i+1} connect_failed={cf}")
    # --- deterministic counters identical across reps ---
    for field in ("connect", "publish", "publish_qos_0", "publish_qos_1", "publish_qos_2",
                  "receive", "control", "control_response", "control_responses",
                  "policy_denial_count", "received_messages"):
        sigs = []
        for r in recs:
            lg = r["runs"][0]["loadgen"]
            v = lg.get(field)
            if isinstance(v, dict):
                v = {k: v.get(k) for k in ("count", "successes", "failures", "attempts") if k in v} or v
            sigs.append(json.dumps(v, sort_keys=True, default=str))
        if len(set(sigs)) > 1:
            fails.append(f"{s} {field} differs across reps: {sigs}")
    # --- QoS totals: per-qos sums to publish count ---
    for i, r in enumerate(recs):
        lg = r["runs"][0]["loadgen"]
        pub = (lg.get("publish") or {}).get("count", 0)
        qsum = sum((lg.get(f"publish_qos_{q}") or {}).get("count", 0) for q in (0, 1, 2))
        if pub and qsum != pub:
            fails.append(f"{s} r{i+1} qos sum {qsum} != publish {pub}")
    # --- percentile ordering + raw sample counts ---
    for i, r in enumerate(recs):
        lg = r["runs"][0]["loadgen"]
        for sec in ("connect", "publish"):
            stats = lg.get(sec) or {}
            ok, vs = pct_ok(stats)
            if ok is False:
                fails.append(f"{s} r{i+1} {sec} percentile inversion {vs}")
        nraw = len(lg.get("raw_publish_ms") or [])
        if nraw == 0 and ((lg.get("publish") or {}).get("count", 0) or 0) > 0:
            warns.append(f"{s} r{i+1} zero raw_publish_ms with nonzero publishes")
    nraws = [len(r["runs"][0]["loadgen"].get("raw_publish_ms") or []) for r in recs]
    if len(set(nraws)) > 1:
        fails.append(f"{s} raw sample counts differ across reps: {nraws}")
    # --- token/profile metadata identical ---
    for field in ("token_metadata", "token_len", "tls", "parity", "scenario_config"):
        sigs = [json.dumps(r.get(field), sort_keys=True, default=str) for r in recs]
        if len(set(sigs)) > 1:
            # scenario_config contains wall-duration? no; must be identical
            fails.append(f"{s} {field} differs across reps")
    # --- sync barrier correctness ---
    for i, r in enumerate(recs):
        lg = r["runs"][0]["loadgen"]
        sb = lg.get("sync_connect_barrier_wait")
        if not isinstance(sb, dict) or sb.get("count", 0) != 10:
            warns.append(f"{s} r{i+1} barrier wait count != 10: {sb}")
    # --- resource coverage ---
    for i, r in enumerate(recs):
        res = r["runs"][0]["resources"]
        cov = (res.get("coverage") or {})
        if cov.get("missing_intervals"):
            warns.append(f"{s} r{i+1} resource missing_intervals={cov.get('missing_intervals')}")
    # --- throughput variance diagnostic (not auto-fail) ---
    tps = []
    for r in recs:
        lg = r["runs"][0]["loadgen"]
        tps.append(lg.get("throughput_mps") or lg.get("publish_throughput_mps"))
    try:
        vals = [float(t) for t in tps if isinstance(t, (int, float))]
        if len(vals) == 3 and min(vals) > 0:
            spread = (max(vals) - min(vals)) / statistics.mean(vals)
            if spread > 0.30:
                warns.append(f"{s} throughput spread {spread:.2f} across reps {vals} (investigate, not auto-fail)")
    except Exception:
        pass

# --- base/TLS parity (non-perf semantics) ---
pairs = [
    ("BASELINE-NO-AUTH", "BASELINE-NO-AUTH-TLS"),
    ("BASELINE-NO-AUTH-QOS0", "BASELINE-NO-AUTH-QOS0-TLS"),
    ("CONTROL-INTERLEAVED-DATA-BISCUIT", "CONTROL-INTERLEAVED-DATA-BISCUIT-TLS"),
    ("CONTROL-INTERLEAVED-DATA-JWT", "CONTROL-INTERLEAVED-DATA-JWT-TLS"),
    ("DYNAMIC-SECURITY-ANONYMOUS-BASELINE", "DYNAMIC-SECURITY-ANONYMOUS-BASELINE-TLS"),
    ("DYNAMIC-SECURITY-BASELINE", "DYNAMIC-SECURITY-BASELINE-TLS"),
    ("DYNAMIC-SECURITY-CHURN", "DYNAMIC-SECURITY-CHURN-TLS"),
]
for b, t in pairs:
    for i in range(3):
        lb = new[i][b]["runs"][0]["loadgen"]
        lt = new[i][t]["runs"][0]["loadgen"]
        for field in ("publish", "publish_qos_0", "publish_qos_1", "publish_qos_2",
                      "connect", "control_response", "control_responses", "policy_denial_count"):
            cb = json.dumps(lb.get(field), sort_keys=True, default=str)
            ct = json.dumps(lt.get(field), sort_keys=True, default=str)
            if cb != ct:
                warns.append(f"parity r{i+1} {b}/{t} {field} differs base vs TLS (check: perf may differ, semantics must not)")

print("\nFAILS:" if fails else "\nNO FAILS")
for f in fails:
    print("  FAIL:", f)
print("\nWARNINGS (diagnostic):" if warns else "\nNO WARNINGS")
for w in warns[:40]:
    print("  WARN:", w)

# --- diagnostic comparison vs superseded b23eb22 (never part of aggregate) ---
print("\nDiagnostic vs superseded b23eb22 c10/m10 idx000-013 (reference only):")
for s in scenarios:
    try:
        nstats = [new[i][s]["runs"][0]["loadgen"].get("publish_throughput_mps") for i in range(3)]
        ostats = [old[i][s]["runs"][0]["loadgen"].get("publish_throughput_mps") for i in range(3)]
        print(f"  {s}: new_pub_tps={nstats} old_pub_tps={ostats}")
    except Exception as e:
        print(f"  {s}: compare error {e}")

sys.exit(1 if fails else 0)
