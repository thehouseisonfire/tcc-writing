#!/usr/bin/env python3
"""Batch B (idx014-031) boundary review: HTTP/LAT family semantics + 3-rep determinism."""
import json, sys, statistics
from pathlib import Path

base = Path("mqtt-auth-biscuit/benchmarks")
TAG = "56344b7"
CELL = "c10-m10-idx014-031"
new_dirs = [base / f"results-final-p1-{TAG}-{CELL}-r{i}" for i in (1, 2, 3)]
old_dirs = [base / f"results-final-p1-b23eb22-{CELL}-r{i}" for i in (1, 2, 3)]

def load(d):
    out = {}
    for p in d.glob("*.json"):
        if p.name == "summary.json":
            continue
        out[p.stem] = json.load(open(p))
    return out

new = [load(d) for d in new_dirs]
old = [load(d) for d in old_dirs]
scenarios = sorted(new[0].keys())
print(f"inventory range: idx014-031 | expected 18 files/rep")
for i, d in enumerate(new_dirs):
    print(f"  {d.name}: actual {len(new[i])}")
assert all(len(n) == 18 for n in new)
assert all(set(n.keys()) == set(scenarios) for n in new)

fails, notes = [], []
for s in scenarios:
    recs = [n[s] for n in new]
    for i, r in enumerate(recs):
        lg = r["runs"][0]["loadgen"]; sc = r["scenario_config"]
        if lg.get("errors"):
            fails.append(f"{s} r{i+1} errors={lg.get('errors')}")
        if not (sc.get("clients") == 10 and sc.get("messages") == 10 and sc.get("workload_shape") == "matrix"):
            fails.append(f"{s} r{i+1} axes mismatch")
        tc = sc.get("client_topology") or {}
        if tc.get("mode") != "container-per-client" or tc.get("memory") != "96m":
            fails.append(f"{s} r{i+1} topo mismatch")
        if (lg.get("connect") or {}).get("count") != 10:
            fails.append(f"{s} r{i+1} connect.count={(lg.get('connect') or {}).get('count')} != 10")
        if (lg.get("raw_metrics") or {}).get("connect_failed", 0):
            fails.append(f"{s} r{i+1} connect_failed nonzero (CONNECT fix check)")
        st = lg.get("publish") or {}
        vs = [st.get(k) for k in ("min_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms")]
        if all(isinstance(v, (int, float)) for v in vs) and vs != sorted(vs):
            fails.append(f"{s} r{i+1} publish percentile inversion")
        vs = [ (lg.get("connect") or {}).get(k) for k in ("min_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms")]
        if all(isinstance(v, (int, float)) for v in vs) and vs != sorted(vs):
            fails.append(f"{s} r{i+1} connect percentile inversion")
        if (r["runs"][0]["resources"].get("coverage") or {}).get("missing_intervals"):
            fails.append(f"{s} r{i+1} resource missing intervals")
    # count determinism
    for field in ("connect", "publish", "publish_qos_0", "publish_qos_1", "publish_qos_2",
                  "receive", "control", "control_response", "policy_denial_count",
                  "received_messages", "qos_distribution_actual"):
        sigs = [json.dumps(r["runs"][0]["loadgen"].get(field, {}).get("count") if isinstance(r["runs"][0]["loadgen"].get(field), dict) else r["runs"][0]["loadgen"].get(field), sort_keys=True, default=str) for r in recs]
        if len(set(sigs)) > 1:
            fails.append(f"{s} {field}.count differs: {sigs}")
    nraw = [len(r["runs"][0]["loadgen"].get("raw_publish_ms") or []) for r in recs]
    if len(set(nraw)) > 1:
        fails.append(f"{s} raw counts differ: {nraw}")
    for field in ("token_metadata", "token_len", "tls", "parity"):
        if len({json.dumps(r.get(field), sort_keys=True, default=str) for r in recs}) > 1:
            fails.append(f"{s} {field} differs")
    # HTTP request/allow/deny + configured delays: inspect available counters
    for i, r in enumerate(recs):
        lg = r["runs"][0]["loadgen"]; sc = r["scenario_config"]
        delay = sc.get("http_expected_delay_ms")
        # surface PDP-related keys for manual check
        http_keys = [k for k in lg.keys() if "http" in k.lower() or "pdp" in k.lower() or "authoriz" in k.lower()]
        if i == 0 and s in ("HTTP-LATENCY-1000MS-JWT", "HTTP-PROFILE-COMPLEX-JWT", "HTTP-PROFILE-SIMPLE-BISCUIT"):
            print(f"  {s}: http_delay={delay} http_keys={http_keys} publish={lg.get('publish',{}).get('count')} raw_n={len(lg.get('raw_publish_ms') or [])}")
    # throughput spread diagnostic
    tps = [r["runs"][0]["loadgen"].get("publish_throughput_mps") for r in recs]
    try:
        vals = [float(t) for t in tps if isinstance(t, (int, float))]
        if len(vals) == 3 and min(vals) > 0:
            spread = (max(vals) - min(vals)) / statistics.mean(vals)
            if spread > 0.30:
                walls = [(r["runs"][0]["loadgen"].get("topology") or {}).get("wall_duration_s") for r in recs]
                p50s = [(r["runs"][0]["loadgen"].get("publish") or {}).get("p50_ms") for r in recs]
                notes.append(f"{s} tps spread {spread:.2f} tps={vals} pub_p50={p50s} wall={walls}")
    except Exception as e:
        notes.append(f"{s} spread err {e}")

# LAT1000 focus: connect latency must be healthy ms-scale, no timeouts, all reps
for s in ("HTTP-LATENCY-1000MS-JWT", "HTTP-LATENCY-1000MS-JWT-TLS"):
    for i, r in enumerate(new):
        lg = r[s]["runs"][0]["loadgen"]
        print(f"  {s} r{i+1}: connect={lg.get('connect')} errors={lg.get('errors')} pub_count={(lg.get('publish') or {}).get('count')}")

# base/TLS count parity
import itertools
bases = sorted({s.replace("-TLS", "") for s in scenarios if s.endswith("-TLS")})
for b in bases:
    t = b + "-TLS"
    for i in range(3):
        lb, lt = new[i][b]["runs"][0]["loadgen"], new[i][t]["runs"][0]["loadgen"]
        for f in ("publish", "connect", "policy_denial_count", "received_messages"):
            vb = (lb.get(f) or {}).get("count") if isinstance(lb.get(f), dict) else lb.get(f)
            vt = (lt.get(f) or {}).get("count") if isinstance(lt.get(f), dict) else lt.get(f)
            if vb != vt:
                notes.append(f"parity r{i+1} {b}/{t} {f}: base={vb} tls={vt}")

print("\nFAILURES:" if fails else "\nNO FAILURES")
for f in fails:
    print("  FAIL:", f)
print("\nNOTES:")
for w in notes:
    print("  NOTE:", w)
print("\nDiagnostic vs b23eb22 (reference only):")
for s in scenarios:
    nc = [(new[i][s]["runs"][0]["loadgen"].get("publish") or {}).get("count") for i in range(3)]
    oc = [(old[i][s]["runs"][0]["loadgen"].get("publish") or {}).get("count") for i in range(3)]
    ne = [new[i][s]["runs"][0]["loadgen"].get("errors") for i in range(3)]
    oe = [old[i][s]["runs"][0]["loadgen"].get("errors") for i in range(3)]
    flag = "MATCH" if (nc == oc and ne == oe) else "DIFF"
    print(f"  {flag} {s}: new pub={nc} err={ne} | old pub={oc} err={oe}")
sys.exit(1 if fails else 0)
