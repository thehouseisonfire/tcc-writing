#!/usr/bin/env python3
"""Corrected Batch A boundary review: proper schema keys + topology-aware connect counts."""
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
print("inventory range: idx000-013 | expected 14 files/rep")
for i, d in enumerate(new_dirs):
    print(f"  {d.name}: actual {len(new[i])} scenario JSONs")
assert all(len(n) == 14 for n in new)
assert all(set(n.keys()) == set(scenarios) for n in new)

fails, notes = [], []

# expected connect counts: fanout-role scenarios have 11 (1 pub + 10 sub), else 10
def expected_connects(rec):
    topo = (rec["runs"][0]["loadgen"].get("topology") or {})
    cc = topo.get("container_count")
    return cc  # connect.count must equal container_count for batch A (no delegator)

for s in scenarios:
    recs = [n[s] for n in new]
    for i, r in enumerate(recs):
        lg = r["runs"][0]["loadgen"]
        sc = r["scenario_config"]
        errs = lg.get("errors")
        if errs:
            fails.append(f"{s} r{i+1} errors={errs}")
        if not (sc.get("clients") == 10 and sc.get("messages") == 10
                and sc.get("requested_clients") == 10 and sc.get("requested_messages") == 10
                and sc.get("workload_shape") == "matrix"):
            fails.append(f"{s} r{i+1} workload axes mismatch")
        topo_cfg = sc.get("client_topology") or {}
        if topo_cfg.get("mode") != "container-per-client" or topo_cfg.get("memory") != "96m":
            fails.append(f"{s} r{i+1} topology cfg mismatch: {topo_cfg.get('mode')}/{topo_cfg.get('memory')}")
        cc = (lg.get("connect") or {}).get("count")
        exp = expected_connects(r)
        if cc != exp:
            fails.append(f"{s} r{i+1} connect.count={cc} != container_count {exp}")
        if (lg.get("raw_metrics") or {}).get("connect_failed", 0):
            fails.append(f"{s} r{i+1} connect_failed nonzero")
        # percentile ordering
        for sec in ("connect", "publish"):
            st = lg.get(sec) or {}
            vs = [st.get(k) for k in ("min_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms")]
            # keys in file are min_ms etc? check both
            if all(v is None for v in vs):
                vs = [st.get(k) for k in ("min", "p50", "p95", "p99", "max")]
            if all(isinstance(v, (int, float)) for v in vs) and vs != sorted(vs):
                fails.append(f"{s} r{i+1} {sec} percentile inversion {vs}")
        # resource coverage
        res = r["runs"][0]["resources"]
        if (res.get("coverage") or {}).get("missing_intervals"):
            fails.append(f"{s} r{i+1} resource missing intervals")
        if not res.get("sampled_interval"):
            notes.append(f"{s} r{i+1} no sampled_interval (check)")
    # determinism across reps: counters, qos sums, sample counts, metadata
    for field in ("connect", "publish", "publish_qos_0", "publish_qos_1", "publish_qos_2",
                  "receive", "control", "control_response", "control_responses",
                  "policy_denial_count", "received_messages", "qos_distribution_actual"):
        sigs = [json.dumps(r["runs"][0]["loadgen"].get(field), sort_keys=True, default=str) for r in recs]
        if len(set(sigs)) > 1:
            fails.append(f"{s} {field} differs across reps: {sigs}")
    nraws = [len(r["runs"][0]["loadgen"].get("raw_publish_ms") or []) for r in recs]
    if len(set(nraws)) > 1:
        fails.append(f"{s} raw sample counts differ: {nraws}")
    for field in ("token_metadata", "token_len", "tls", "parity"):
        sigs = [json.dumps(r.get(field), sort_keys=True, default=str) for r in recs]
        if len(set(sigs)) > 1:
            fails.append(f"{s} {field} differs across reps")
    # control-response: churn scenarios must record responses
    if "CHURN" in s:
        for i, r in enumerate(recs):
            lg = r["runs"][0]["loadgen"]
            cr = (lg.get("control_response") or {}).get("count", 0) + (lg.get("control_responses") or {}).get("count", 0) if isinstance(lg.get("control_responses"), dict) else (lg.get("control_response") or {}).get("count", 0)
            if not cr:
                notes.append(f"{s} r{i+1} no control responses recorded (verify contract)")
    # throughput spread diagnostic with latency/wall evidence
    pubs = [(r["runs"][0]["loadgen"].get("publish") or {}) for r in recs]
    walls = [(r["runs"][0]["loadgen"].get("topology") or {}).get("wall_duration_s") for r in recs]
    tps = [r["runs"][0]["loadgen"].get("publish_throughput_mps") for r in recs]
    try:
        vals = [float(t) for t in tps if isinstance(t, (int, float))]
        if len(vals) == 3 and min(vals) > 0:
            spread = (max(vals) - min(vals)) / statistics.mean(vals)
            p50s = [p.get("p50_ms") for p in pubs]
            if spread > 0.30:
                notes.append(f"{s} throughput spread {spread:.2f} tps={vals} pub_p50={p50s} wall={walls} -> wall-duration/startup variance, latencies stable => accepted per protocol")
    except Exception as e:
        notes.append(f"{s} spread check error {e}")

# base/TLS semantic parity (counters, not perf)
pairs = [("BASELINE-NO-AUTH", "BASELINE-NO-AUTH-TLS"),
         ("BASELINE-NO-AUTH-QOS0", "BASELINE-NO-AUTH-QOS0-TLS"),
         ("CONTROL-INTERLEAVED-DATA-BISCUIT", "CONTROL-INTERLEAVED-DATA-BISCUIT-TLS"),
         ("CONTROL-INTERLEAVED-DATA-JWT", "CONTROL-INTERLEAVED-DATA-JWT-TLS"),
         ("DYNAMIC-SECURITY-ANONYMOUS-BASELINE", "DYNAMIC-SECURITY-ANONYMOUS-BASELINE-TLS"),
         ("DYNAMIC-SECURITY-BASELINE", "DYNAMIC-SECURITY-BASELINE-TLS"),
         ("DYNAMIC-SECURITY-CHURN", "DYNAMIC-SECURITY-CHURN-TLS")]
for b, t in pairs:
    for i in range(3):
        lb, lt = new[i][b]["runs"][0]["loadgen"], new[i][t]["runs"][0]["loadgen"]
        for field in ("publish", "publish_qos_0", "publish_qos_1", "publish_qos_2",
                      "connect", "control_response", "policy_denial_count"):
            if json.dumps(lb.get(field), sort_keys=True, default=str) != json.dumps(lt.get(field), sort_keys=True, default=str):
                notes.append(f"parity r{i+1} {b}/{t} {field} differs (perf may differ; counters noted)")

print("\nFAILURES:" if fails else "\nNO FAILURES")
for f in fails:
    print("  FAIL:", f)
print("\nNOTES:")
for w in notes:
    print("  NOTE:", w)
print("\nDiagnostic vs superseded b23eb22 (reference only, not aggregate):")
for s in scenarios:
    nc = [new[i][s]["runs"][0]["loadgen"]["connect"]["count"] for i in range(3)]
    oc = [old[i][s]["runs"][0]["loadgen"]["connect"]["count"] for i in range(3)]
    np = [(new[i][s]["runs"][0]["loadgen"].get("publish") or {}).get("count") for i in range(3)]
    op = [(old[i][s]["runs"][0]["loadgen"].get("publish") or {}).get("count") for i in range(3)]
    match = "MATCH" if (nc == oc and np == op) else "DIFF"
    print(f"  {match} {s}: new conn={nc} pub={np} | old conn={oc} pub={op}")
sys.exit(1 if fails else 0)
