"""Reproduce the first H1–H3 analysis from accepted benchmark results."""

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = ROOT / "benchmarks" / "final-audit-20261117"
KEY = ("part", "cohort", "clients", "messages", "qos", "mode", "rep")
REAUTH = (
    "reauth_ok",
    "pre_reauth_publish_ok",
    "post_reauth_publish_ok",
    "post_reauth_old_topic_denied",
)

# Each comparison is evaluated only where both members share the effective
# workload coordinates in the same cohort and campaign round.
COMPARISONS = [
    ("H2 token-only", "TOKEN-BASELINE-BISCUIT", "TOKEN-BASELINE-JWT"),
    ("H2 static ACL", "STATIC-ACL-PUBLISH-BISCUIT", "STATIC-ACL-PUBLISH-JWT"),
    ("H2 HTTP simple", "HTTP-PROFILE-SIMPLE-BISCUIT", "HTTP-PROFILE-SIMPLE-JWT"),
    ("H2 HTTP complex", "HTTP-PROFILE-COMPLEX-BISCUIT", "HTTP-PROFILE-COMPLEX-JWT"),
    (
        "H3 architecture",
        "TOKEN-COMPLEXITY-DATALOG-HIGH-BISCUIT",
        "HTTP-PROFILE-COMPLEX-JWT",
    ),
    ("HTTP profile", "HTTP-PROFILE-COMPLEX-JWT", "HTTP-PROFILE-SIMPLE-JWT"),
]
for profile in ("SIMPLE", "COMPLEX"):
    COMPARISONS.append(
        (
            f"H2 HTTP {profile.lower()} identity-bound",
            f"HTTP-PROFILE-{profile}-PARITY-BISCUIT",
            f"HTTP-PROFILE-{profile}-PARITY-JWT",
        )
    )
COMPARISONS += [
    (f"{name} TLS", f"{candidate}-TLS", f"{reference}-TLS")
    for name, candidate, reference in COMPARISONS
    if name.startswith("H2")
]
PERFORMANCE_COHORTS = {("P2", "matrix"), ("P2", "tls_panel"), ("P1", "fixed-clients")}
METRICS = (
    "connect_p50_ms",
    "connect_p95_ms",
    "connect_p99_ms",
    "publish_p50_ms",
    "publish_p95_ms",
    "publish_p99_ms",
    "client_publish_mps",
    "allowed_acknowledged_mps",
    "broker_cpu_seconds",
    "broker_memory_mean_mib",
    "token_fixture_chars",
)
FUNCTIONAL = {
    "TOKEN-ATTENUATION-SUBSCRIBE-DENY-BISCUIT": "subscription denied",
    "TOKEN-DENY-READ-JWT": "delivery denied",
    "TOKEN-ATTENUATED-DENY-BISCUIT": "delivery denied",
    "TOKEN-MQTT5-REAUTH-JWT": "reauthentication and permission change",
    "TOKEN-MQTT5-REAUTH-BISCUIT": "reauthentication and permission change",
    "TOKEN-DELEGATION-HANDOFF-BISCUIT": "delegated handoff and authorized publication",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_result(row):
    path = Path(row["result_json_path"])
    payload = path.read_bytes()
    require(
        hashlib.sha256(payload).hexdigest() == row["result_sha256"],
        f"Hash mismatch: {path}",
    )
    result = json.loads(payload)
    require(result["scenario"] == row["scenario"], f"Scenario mismatch: {path}")
    return result


def performance(row, result, counter):
    slot = row["slot_id"]
    require(len(result["runs"]) == 1, f"Unexpected internal repetitions: {slot}")
    run = result["runs"][0]
    load = run["loadgen"]
    auth = counter["authentication"]
    authz = counter["authorization"]
    outcomes = counter["publish_outcomes"]
    expected = int(row["clients"]) * int(row["messages"])
    checks = authz["checks"]
    allows = authz["allows"]
    denies = authz["denies"]
    static_acl = row["scenario"].startswith("STATIC-ACL-")
    require(
        load["connect"]["count"] == auth["successes"] == int(row["clients"])
        and load["publish"]["count"]
        == outcomes["succeeded"]
        == outcomes["attempted"]
        == expected
        and counter["qos_completions"][f"qos_{row['qos']}_count"] == expected
        and not counter["errors"]
        and checks == expected
        and (allows, denies) == ((0, expected) if static_acl else (expected, 0)),
        f"Unexpected publish contract: {slot}",
    )
    http = counter["http_authorization"]
    if http is not None:
        require(http["requests"] == expected, f"Unexpected request count: {slot}")
    if row["qos"] == "0" and http is not None:
        require(
            counter["qos0_quiescence"] is not None, f"Missing terminal check: {slot}"
        )
    resource = run["resources"]
    throughput = load["publish_throughput_mps"]
    wall_seconds = load["topology"]["wall_duration_s"]
    require(
        math.isclose(throughput, expected / wall_seconds),
        f"Throughput denominator: {slot}",
    )

    config = result["scenario_config"]
    values = {
        **{
            key: row[key]
            for key in (*KEY, "slot_id", "slot_order", "scenario", "execution_unit")
        },
        "tls": result["tls"]["enabled"],
        "payload_bytes": load["inputs"]["message_size"],
        "topology": load["topology"]["mode"],
        "semantic_class": config["semantic_class"],
        "identity_binding": config[
            f"{'biscuit' if 'BISCUIT' in row['scenario'] else 'jwt'}_identity_binding"
        ],
        "policy_mode": authz["policy_mode"],
        "broker_allows": allows,
        "broker_denies": denies,
        "http_requests": http["requests"] if http is not None else None,
        "injected_http_failures": http["injected_failures"]
        if http is not None
        else None,
        "configured_http_delay_ms": http["configured_delay_ms"]
        if http is not None
        else None,
        "client_wall_seconds": wall_seconds,
        "client_publish_mps": throughput,
        "allowed_acknowledged_mps": throughput
        if allows == expected and row["qos"] != "0"
        else None,
        "broker_cpu_seconds": resource["cpu_usage_seconds"]
        if resource["available"]
        else None,
        "broker_memory_mean_mib": (
            resource["memory_working_set_bytes"]["mean"] / 2**20
            if resource["available"]
            else None
        ),
        "token_fixture_chars": result["token_len"],
    }
    for operation in ("connect", "publish"):
        for percentile in ("p50", "p95", "p99"):
            values[f"{operation}_{percentile}_ms"] = load[operation][f"{percentile}_ms"]
    return values


def functional(row, result, check):
    for run_index, run in enumerate(result["runs"]):
        load = run["loadgen"]
        observed = None
        reference = None
        if check == "subscription denied":
            probes = load["authorization_probes"]
            observed = probes["successes"]
            reference = int(row["clients"])
            passed = (
                probes["enabled"]
                and probes["operation"] == "subscribe"
                and probes["expected"] == "deny"
                and observed == reference
                and probes["failures"] == 0
            )
        elif check == "delivery denied":
            observed = load["received_messages"]["count"]
            reference = load["received_messages"]["expected"]
            published = load["publish_outcomes"]
            passed = (
                observed == 0
                and reference > 0
                and published["succeeded"] == published["attempted"] > 0
                and load["broker_authz_delta"]["denies"] > 0
            )
        elif check == "reauthentication and permission change":
            observed = sum(load[field] is True for field in REAUTH)
            reference = len(REAUTH)
            passed = observed == reference
        else:
            observed = load["delegation_handoff_publish"]["count"]
            handoff = load["topology"]["delegation_handoff"]
            reference = handoff["delegatees"]
            published = load["publish_outcomes"]
            passed = (
                handoff["delegators"] == 1
                and observed == reference > 0
                and published["succeeded"] == published["attempted"] > 0
            )
        yield {
            **{key: row[key] for key in (*KEY, "slot_id", "scenario")},
            "run_index": run_index,
            "check": check,
            "observed": observed,
            "reference": reference,
            "passed": passed,
        }


def compare(metrics, comparisons=COMPARISONS, metric_names=METRICS):
    for name, left, right in comparisons:
        for key, baseline in metrics.items():
            if right != key[-1]:
                continue
            candidate = metrics.get((*key[:-1], left))
            if candidate is None:
                continue
            for field in (
                "tls",
                "payload_bytes",
                "topology",
                "semantic_class",
                "identity_binding",
            ):
                require(
                    candidate[field] == baseline[field], f"Mismatched {field}: {key}"
                )
            require(
                candidate["execution_unit"] == baseline["execution_unit"]
                and candidate["broker_allows"] == baseline["broker_allows"]
                and candidate["broker_denies"] == baseline["broker_denies"],
                f"Mismatched workload or authorization outcome: {key}",
            )
            for metric in metric_names:
                value = candidate[metric]
                reference = baseline[metric]
                if value is None or reference is None:
                    continue
                effect = {
                    "comparison": name,
                    "metric": metric,
                    **dict(zip(KEY, key[:-1], strict=True)),
                    "candidate_slot": candidate["slot_id"],
                    "reference_slot": baseline["slot_id"],
                    "candidate": value,
                    "reference": reference,
                    "difference": value - reference,
                    "ratio": value / reference if reference else None,
                }
                yield effect


def summarize(effects):
    groups = defaultdict(list)
    fields = ("comparison", "metric", *KEY[:-1])
    for effect in effects:
        groups[tuple(effect[field] for field in fields)].append(effect)
    for key, group in groups.items():
        require(
            {item["rep"] for item in group} == {"1", "2", "3"} and len(group) == 3,
            f"Incomplete campaign repetitions: {key}",
        )
        group.sort(key=lambda row: int(row["rep"]))
        ratios = [item["ratio"] for item in group if item["ratio"] is not None]
        yield {
            **dict(zip(fields, key, strict=True)),
            "candidate_median": median(item["candidate"] for item in group),
            "reference_median": median(item["reference"] for item in group),
            "difference_median": median(item["difference"] for item in group),
            "ratio_median": median(ratios) if len(ratios) == 3 else None,
            "ratio_min": min(ratios) if len(ratios) == 3 else None,
            "ratio_max": max(ratios) if len(ratios) == 3 else None,
            "candidate_slots": " ".join(item["candidate_slot"] for item in group),
            "reference_slots": " ".join(item["reference_slot"] for item in group),
        }


def write_csv(path, rows):
    require(bool(rows), f"No rows for {path.name}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_audit(audit):
    with (audit / "ANALYSIS-INDEX.csv").open(encoding="utf-8", newline="") as stream:
        index = list(csv.DictReader(stream))
    require(
        len(index) == len({row["slot_id"] for row in index}) == 4101,
        "Unexpected audit index",
    )
    with (audit / "RUN-CONTRACT-COUNTERS.jsonl").open(encoding="utf-8") as stream:
        counters = {}
        for line in stream:
            counter = json.loads(line)
            if counter["run_index"] == 0:
                counters[counter["slot_order"]] = counter

    return index, counters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    index, counters = load_audit(args.audit)

    scenarios = {
        scenario
        for _, candidate, reference in COMPARISONS
        for scenario in (candidate, reference)
    }
    metrics = {}
    evidence = []
    for row in index:
        require(
            row["inclusion_status"] == "accepted_final", "Unexpected inclusion status"
        )
        name = row["scenario"]
        if (row["part"], row["cohort"]) in PERFORMANCE_COHORTS and name in scenarios:
            counter = counters[row["slot_order"]]
            require(
                counter["scenario"] == name
                and counter["execution_unit"] == row["execution_unit"],
                f"Counter join mismatch: {row['slot_id']}",
            )
            key = (*[row[field] for field in KEY], name)
            require(key not in metrics, f"Duplicate slot: {key}")
            metrics[key] = performance(row, load_result(row), counter)
        check = FUNCTIONAL.get(name.removesuffix("-TLS"))
        if check is not None:
            evidence.extend(functional(row, load_result(row), check))

    require(
        all(record["passed"] for record in evidence), "Unexpected functional result"
    )
    effects = list(compare(metrics))
    summary = list(summarize(effects))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.output / "comparison-spec.csv",
        [
            {
                "comparison": name,
                "candidate_scenario": candidate,
                "reference_scenario": reference,
            }
            for name, candidate, reference in COMPARISONS
            if any(row["comparison"] == name for row in summary)
        ],
    )
    write_csv(args.output / "performance-runs.csv", list(metrics.values()))
    write_csv(args.output / "effects-by-round.csv", effects)
    write_csv(args.output / "effects-by-condition.csv", summary)
    write_csv(args.output / "functional-evidence.csv", evidence)
    print(
        f"{len(metrics)} performance slots, {len(evidence)} functional records, {len(summary)} effect summaries"
    )


if __name__ == "__main__":
    main()
