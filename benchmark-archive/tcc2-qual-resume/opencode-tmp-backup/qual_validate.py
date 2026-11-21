#!/usr/bin/env python3
"""Diagnostic qualification validator for Part 1 matrix sweep (c10/m10).

Reads /tmp/opencode/qual_table.csv + result JSONs, emits PASS/FAIL/SUSPICIOUS
per scenario per TESTING.md universal + family contracts (single-run scope;
no 3-repetition statistics).
"""
import csv
import json
import math
import os
import sys

REPO = "/home/eagle/TCC2"
BENCH = os.path.join(REPO, "mqtt-auth-biscuit", "benchmarks")
MATRIX = "/tmp/opencode/qual_matrix.txt"
TABLE = "/tmp/opencode/qual_table.csv"


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def finite_nonneg(x):
    return is_num(x) and math.isfinite(x) and x >= 0


def check_percentiles(block, label, notes):
    """block like {'count':n,'min_ms':..,'p50_ms':..,...}; None-safe."""
    if not isinstance(block, dict):
        return True
    n = block.get("count") or 0
    if n <= 0:
        return True
    vals = [block.get(k) for k in ("min_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms")]
    if any(v is None for v in vals):
        notes.append(f"{label}: null percentile with count={n}")
        return False
    if any(not finite_nonneg(v) for v in vals):
        notes.append(f"{label}: non-finite/negative percentile")
        return False
    if not (vals[0] <= vals[1] <= vals[2] <= vals[3] <= vals[4]):
        notes.append(f"{label}: percentile inversion {vals}")
        return False
    return True


def find_key(obj, target, out, depth=0):
    if depth > 6 or not isinstance(obj, dict):
        return
    for k, v in obj.items():
        if k == target:
            out.append(v)
        if isinstance(v, dict):
            find_key(v, target, out, depth + 1)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    find_key(item, target, out, depth + 1)


def validate(idx, sid, exit_code, json_rel):
    fails, susps, info = [], [], []

    def fail(m):
        fails.append(m)

    def susp(m):
        susps.append(m)

    if exit_code != 0:
        fail(f"runner exit_status={exit_code}")
    if json_rel in ("NO_RESULTS_DIR", "MISSING_JSON") or not json_rel.endswith(".json"):
        fail(f"no result JSON ({json_rel})")
        return verdict(idx, sid, fails, susps, info)
    path = os.path.join(REPO, json_rel)
    if not os.path.isfile(path):
        fail(f"result JSON absent at {json_rel}")
        return verdict(idx, sid, fails, susps, info)
    try:
        with open(path) as f:
            r = json.load(f)
    except Exception as e:  # noqa: BLE001
        fail(f"JSON unparseable: {e}")
        return verdict(idx, sid, fails, susps, info)

    if r.get("scenario") != sid:
        fail(f"scenario mismatch: file={r.get('scenario')!r} expected={sid!r}")

    # TLS parity with ID suffix
    tls = r.get("tls") or {}
    tls_on = tls.get("enabled") is True
    if sid.endswith("-TLS") != tls_on:
        fail(f"TLS parity: id_tls_suffix={sid.endswith('-TLS')} tls.enabled={tls_on}")

    cfg = r.get("scenario_config") or {}
    runs = r.get("runs")
    lg = runs[0].get("loadgen") if isinstance(runs, list) and runs else None
    if not isinstance(lg, dict):
        fail("runs[0].loadgen missing")
        return verdict(idx, sid, fails, susps, info)

    # Requested vs effective axes
    req_c = cfg.get("requested_clients", cfg.get("client_count"))
    req_m = cfg.get("requested_messages", cfg.get("messages"))
    if req_c != 10:
        susp(f"requested_clients={req_c} (cell expects 10)")
    if req_m != 10:
        susp(f"requested_messages={req_m} (cell expects 10)")
    info.append(f"req_c={req_c} req_m={req_m} qos={cfg.get('requested_qos', cfg.get('qos'))}")

    # Topology
    topo = lg.get("topology") or {}
    if topo.get("mode") != "container-per-client":
        fail(f"topology mode={topo.get('mode')!r}")
    cc = topo.get("container_count")
    info.append(f"containers={cc}")
    if cc != 10:
        susp(f"container_count={cc} (cell expects 10)")

    # Connect vs containers
    conn = lg.get("connect") or {}
    if (conn.get("count") or 0) != (cc or 0) and cc:
        susp(f"connect.count={conn.get('count')} vs containers={cc}")
    if not check_percentiles(conn, "connect", susps):
        pass
    info.append(f"connect={conn.get('count')}")

    # Publish outcomes
    po = lg.get("publish_outcomes") or {}
    att, suc, fl = po.get("attempted", 0), po.get("succeeded", 0), po.get("failed", 0)
    info.append(f"pub att={att} suc={suc} fail={fl}")
    deny_like = ("DENY" in sid) or bool(cfg.get("runtime_control_expect_denial"))
    if suc <= 0 and not deny_like:
        fail(f"zero successful publishes (att={att} fail={fl})")
    by_qos = po.get("attempted_by_qos") or {}
    if by_qos and sum(by_qos.values()) != att:
        susp(f"per-QoS attempted sum={sum(by_qos.values())} != attempted={att}")
    if not check_percentiles(lg.get("publish") or {}, "publish", susps):
        pass
    for qk in ("publish_qos_0", "publish_qos_1", "publish_qos_2"):
        if not check_percentiles(lg.get(qk) or {}, qk, susps):
            pass

    # Errors
    errs = lg.get("errors")
    if errs:
        susp(f"errors non-empty: {json.dumps(errs)[:200]}")

    # Throughput finite/nonempty
    tp = lg.get("publish_throughput_mps")
    if suc > 0:
        if not (is_num(tp) and math.isfinite(tp) and tp > 0):
            susp(f"publish_throughput_mps={tp} with suc={suc}")
    pub = lg.get("publish") or {}
    if (pub.get("count") or 0) > 0 and (pub.get("p50_ms") or 0) == 0 and pub.get("min_ms") == 0 and pub.get("max_ms") == 0:
        susp("zero publish latency distribution for nonempty workload")

    # Raw sample counts
    raw = lg.get("raw_publish_ms")
    if isinstance(raw, list) and (pub.get("count") or 0) > 0 and len(raw) != pub.get("count"):
        susp(f"raw_publish_ms len={len(raw)} != publish.count={pub.get('count')}")

    # sync_connect contract (hard for thundering-herd)
    sync = lg.get("sync_connect") or {}
    is_herd = "THUNDERING-HERD" in sid
    if is_herd and sync.get("enabled") is not True:
        fail("thundering-herd: sync_connect not enabled")
    if sync.get("enabled") is True:
        parts = sync.get("participants")
        ready = sync.get("ready_count")
        skew = sync.get("max_ready_skew_ms")
        if parts != ready:
            (fail if is_herd else susp)(f"sync participants={parts} ready={ready}")
        if not (is_num(skew) and math.isfinite(skew) and skew >= 0):
            (fail if is_herd else susp)(f"sync max_ready_skew_ms invalid: {skew!r}")
        if sync.get("errors"):
            (fail if is_herd else susp)(f"sync errors: {json.dumps(sync.get('errors'))[:150]}")
        info.append(f"sync parts={parts} ready={ready} skew={skew}")

    # Resources present
    res = (runs[0] or {}).get("resources")
    if not res:
        susp("resources block missing/empty")

    # Family-specific
    if sid.startswith("HTTP-") or sid.startswith("HYBRID-"):
        reqs = []
        find_key(r, "requests", reqs)
        tot = sum(v for v in reqs if is_num(v))
        info.append(f"http_requests_sum={tot}")
        if tot <= 0:
            susp("no external PDP request evidence (requests sum<=0)")
    if sid.startswith("NETWORK-MTU-"):
        pa = r.get("packet_analysis_result") or r.get("packet_analysis")
        if not pa:
            susp("MTU: no packet_analysis(_result)")
        else:
            info.append("pcap_analysis=present")
    if "DENY" in sid or "SUBSCRIBE-DENY" in sid:
        pd = lg.get("policy_denial_count")
        ap = lg.get("authorization_probes") or {}
        info.append(f"denials={pd} probes={ap}")
        if not pd and not (ap.get("successes") or ap.get("failures")):
            susp("deny scenario without denial/probe evidence")
    if "QOS2" in sid and "MIXED" not in sid:
        q2 = (lg.get("publish_qos_2") or {}).get("count") or 0
        if q2 <= 0:
            fail(f"QOS2 scenario with publish_qos_2.count={q2}")
    if "QOS-MIXED" in sid:
        dist = lg.get("qos_distribution_actual") or {}
        if not any((dist.get(k) or 0) > 0 for k in ("qos_0_count", "qos_1_count", "qos_2_count")):
            susp(f"mixed-QoS without distribution evidence: {dist}")

    return verdict(idx, sid, fails, susps, info)


def verdict(idx, sid, fails, susps, info):
    if fails:
        v = "FAIL"
    elif susps:
        v = "SUSPICIOUS"
    else:
        v = "PASS"
    reason = "; ".join(fails + susps) if (fails or susps) else "all checks passed"
    return {"idx": idx, "scenario": sid, "verdict": v,
            "reason": reason, "info": " | ".join(info)}


def main():
    with open(MATRIX) as f:
        ids = [l.strip() for l in f if l.strip()]
    rows = {}
    with open(TABLE) as f:
        for row in csv.DictReader(f):
            rows[int(row["idx"])] = row
    out = []
    for idx, sid in enumerate(ids):
        if idx in rows:
            r = rows[idx]
            out.append(validate(idx, sid, int(r["exit_status"]), r["result_json"]))
        else:
            out.append({"idx": idx, "scenario": sid, "verdict": "NOT_RUN",
                        "reason": "no table entry", "info": ""})
    w = csv.DictWriter(sys.stdout, fieldnames=["idx", "scenario", "verdict", "reason", "info"])
    w.writeheader()
    for o in out:
        w.writerow(o)
    p = sum(1 for o in out if o["verdict"] == "PASS")
    f_ = sum(1 for o in out if o["verdict"] == "FAIL")
    s = sum(1 for o in out if o["verdict"] == "SUSPICIOUS")
    n = sum(1 for o in out if o["verdict"] == "NOT_RUN")
    sys.stderr.write(f"PASS={p} FAIL={f_} SUSPICIOUS={s} NOT_RUN={n} total={len(out)}\n")


if __name__ == "__main__":
    main()
