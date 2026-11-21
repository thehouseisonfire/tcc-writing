#!/usr/bin/env python3
"""Batch C (idx032-047) boundary review: 13 runnable + 3 blocked ledger."""
import json, sys, statistics
from pathlib import Path

base = Path("mqtt-auth-biscuit/benchmarks")
TAG = "56344b7"
CELL = "c10-m10-idx032-047"
new_dirs = [base / f"results-final-p1-{TAG}-{CELL}-r{i}" for i in (1, 2, 3)]
old_dirs = [base / f"results-final-p1-b23eb22-{CELL}-r{i}" for i in (1, 2, 3)]

def load(d):
    out = {}
    for p in d.glob("*.json"):
        if p.name in ("summary.json", "ENVIRONMENT-BLOCKED-idx044-045-047.json"):
            continue
        out[p.stem] = json.load(open(p))
    led = json.load(open(d / "ENVIRONMENT-BLOCKED-idx044-045-047.json"))
    return out, led

new, leds = zip(*[load(d) for d in new_dirs])
old, old_leds = zip(*[load(d) for d in old_dirs])
scenarios = sorted(new[0].keys())
print(f"inventory range: idx032-047 | expected 13 runnable + 3 blocked")
for i, d in enumerate(new_dirs):
    print(f"  {d.name}: actual {len(new[i])} scenario JSONs + ledger")
assert all(len(n) == 13 for n in new)
assert all(set(n.keys()) == set(scenarios) for n in new)
assert "NETWORK-MTU-9000-JWT" in scenarios
assert not any("MTU-9000-BISCUIT" in s or s == "NETWORK-MTU-9000-JWT-TLS" for s in scenarios)
for i, led in enumerate(leds):
    assert led["frozen_commit"] == "56344b77e49fff477b7ec7456fdf3e4469d995b4", "ledger commit"
    assert led["repetition"] == i + 1
    assert [b["index"] for b in led["blocked_scenarios"]] == [44, 45, 47]
    print(f"  r{i+1} ledger OK: blocked idx44/45/47, repetition {led['repetition']}")

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
            fails.append(f"{s} r{i+1} connect.count != 10")
        if (lg.get("raw_metrics") or {}).get("connect_failed", 0):
            fails.append(f"{s} r{i+1} connect_failed nonzero")
        for sec in ("connect", "publish"):
            st = lg.get(sec) or {}
            vs = [st.get(k) for k in ("min_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms")]
            if all(isinstance(v, (int, float)) for v in vs) and vs != sorted(vs):
                fails.append(f"{s} r{i+1} {sec} percentile inversion")
        if (r["runs"][0]["resources"].get("coverage") or {}).get("missing_intervals"):
            fails.append(f"{s} r{i+1} resource missing intervals")
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

# MTU specifics: pcap presence + idx46 normal run + hybrid fallback counters
for i in range(3):
    pcapd = new_dirs[i] / "pcap"
    pcaps = sorted(p.name for p in pcapd.glob("*.pcap")) if pcapd.exists() else []
    print(f"  r{i+1} pcap files: {len(pcaps)}")
    r46 = new[i]["NETWORK-MTU-9000-JWT"]["runs"][0]["loadgen"]
    print(f"  r{i+1} idx46 MTU-9000-JWT: pub={r46.get('publish',{}).get('count')} conn={r46.get('connect',{}).get('count')} err={r46.get('errors')}")
    for h in ("HYBRID-FALLBACK-AUTHZ-DOWN-JWT", "HYBRID-FALLBACK-AUTHZ-DOWN-JWT-TLS"):
        lg = new[i][h]["runs"][0]["loadgen"]
        print(f"  r{i+1} {h}: pub={lg.get('publish',{}).get('count')} err={lg.get('errors')}")

# base/TLS count parity
for b in ("HYBRID-FALLBACK-AUTHZ-DOWN-JWT", "NETWORK-MTU-1500-BISCUIT-CHAIN-25",
          "NETWORK-MTU-1500-JWT", "NETWORK-MTU-200-JWT", "NETWORK-MTU-500-BISCUIT-CHAIN-25",
          "NETWORK-MTU-500-JWT"):
    for i in range(3):
        lb, lt = new[i][b]["runs"][0]["loadgen"], new[i][b + "-TLS"]["runs"][0]["loadgen"]
        for f in ("publish", "connect", "policy_denial_count", "received_messages"):
            vb = (lb.get(f) or {}).get("count") if isinstance(lb.get(f), dict) else lb.get(f)
            vt = (lt.get(f) or {}).get("count") if isinstance(lt.get(f), dict) else lt.get(f)
            if vb != vt:
                notes.append(f"parity r{i+1} {b}/{b}-TLS {f}: base={vb} tls={vt}")

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
    print(f"  {'MATCH' if nc == oc else 'DIFF'} {s}: new pub={nc} | old pub={oc}")
sys.exit(1 if fails else 0)
