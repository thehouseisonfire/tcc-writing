"""Compare credential complexity and MTU using the sealed campaign and TShark."""

import argparse
import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

from first_pass import (
    DEFAULT_AUDIT,
    KEY,
    METRICS,
    compare,
    load_audit,
    load_result,
    performance,
    require,
    summarize,
    write_csv,
)

CHAIN = "TOKEN-COMPLEXITY-CHAIN-{}-BISCUIT"
DATALOG = "TOKEN-COMPLEXITY-DATALOG-{}-BISCUIT"
COMPLEXITY = [
    ("chain 5 / 1", CHAIN.format(5), CHAIN.format(1)),
    ("chain 25 / 1", CHAIN.format(25), CHAIN.format(1)),
    ("chain 25 / 5", CHAIN.format(25), CHAIN.format(5)),
    ("Datalog medium / low", DATALOG.format("MED"), DATALOG.format("LOW")),
    ("Datalog high / low", DATALOG.format("HIGH"), DATALOG.format("LOW")),
    ("Datalog high / medium", DATALOG.format("HIGH"), DATALOG.format("MED")),
]
MTU = [
    (
        f"MTU {mtu}: Biscuit / JWT",
        f"NETWORK-MTU-{mtu}-BISCUIT-CHAIN-25",
        f"NETWORK-MTU-{mtu}-JWT",
    )
    for mtu in (500, 1500)
]
MTU.extend(
    [
        (
            "Biscuit MTU 500 / 1500",
            "NETWORK-MTU-500-BISCUIT-CHAIN-25",
            "NETWORK-MTU-1500-BISCUIT-CHAIN-25",
        ),
        ("JWT MTU 500 / 1500", "NETWORK-MTU-500-JWT", "NETWORK-MTU-1500-JWT"),
    ]
)
MTU_SCENARIOS = {
    f"{scenario}{suffix}"
    for _, candidate, reference in MTU
    for scenario in (candidate, reference)
    for suffix in ("", "-TLS")
}
PACKET_METRICS = (
    "mqtt_payload_packets_per_connection",
    "connect_segments_median",
    "connect_password_bytes_median",
)


def read_connects(path, expected):
    # Request numeric fields only. An absent reassembly count means a single
    # segment when the complete CONNECT is dissected directly in its frame.
    result = subprocess.run(
        [
            "tshark",
            "-n",
            "-2",
            "-r",
            str(path),
            "-d",
            "tcp.port==1883,mqtt",
            "-Y",
            "mqtt.msgtype == 1",
            "-T",
            "fields",
            "-e",
            "tcp.stream",
            "-e",
            "tcp.segment.count",
            "-e",
            "mqtt.passwd_len",
        ],
        text=True,
        capture_output=True,
        env={**os.environ, "LC_ALL": "C"},
        check=False,
    )
    truncated = (
        result.returncode == 14
        and "appears to have been cut short in the middle of a packet" in result.stderr
    )
    if result.returncode and not truncated:
        result.check_returncode()
    streams = set()
    segments = []
    lengths = []
    for line in result.stdout.splitlines():
        stream, count, length = line.split("\t")
        require(
            stream not in streams and int(length) > 0, f"Unexpected CONNECT: {path}"
        )
        streams.add(stream)
        segments.append(int(count) if count else 1)
        lengths.append(int(length))
    require(
        len(streams) == expected,
        f"Expected {expected} complete CONNECTs, got {len(streams)}: {path}",
    )
    return {
        "capture_truncated_tail": truncated,
        "connect_segments_min": min(segments),
        "connect_segments_median": median(segments),
        "connect_segments_max": max(segments),
        "connect_password_bytes_min": min(lengths),
        "connect_password_bytes_median": median(lengths),
        "connect_password_bytes_max": max(lengths),
    }


def extract_packets(task):
    row, packet, replay, metrics = task
    path = Path(packet["pcap_file"])
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    expected = int(row["clients"])
    require(
        digest == replay["pcap_sha256"]
        and replay["pcap"] == str(path)
        and replay["result_sha256"] == row["result_sha256"]
        and replay["corrected_replay"] == "PASS"
        and replay["interval_session_counts"] == [expected],
        f"Capture provenance mismatch: {row['slot_id']}",
    )
    observed = packet["metrics"]
    mtu = packet["effective_mtu"]
    require(mtu == int(row["scenario"].split("-")[2]), f"Unexpected MTU: {path}")
    require(observed["max_ip_packet_bytes"] <= mtu, f"Packet exceeds MTU: {path}")
    connect = read_connects(path, expected) if not metrics["tls"] else {}
    return {
        **metrics,
        "effective_mtu": mtu,
        "ip_fragments": observed["fragment_count"],
        "max_ip_packet_bytes": observed["max_ip_packet_bytes"],
        "max_tcp_payload_bytes": observed["max_tcp_payload_bytes"],
        "mqtt_payload_packets_per_connection": observed["mqtt_payload_packets"]
        / expected,
        "capture_truncated_tail": connect.get("capture_truncated_tail"),
        "connect_segments_min": connect.get("connect_segments_min"),
        "connect_segments_median": connect.get("connect_segments_median"),
        "connect_segments_max": connect.get("connect_segments_max"),
        "connect_password_bytes_min": connect.get("connect_password_bytes_min"),
        "connect_password_bytes_median": connect.get("connect_password_bytes_median"),
        "connect_password_bytes_max": connect.get("connect_password_bytes_max"),
        "pcap_sha256": digest,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    index, counters = load_audit(args.audit)
    replays = {
        row["result"]: row
        for row in json.loads(
            (args.audit / "PACKET-REVALIDATION.json").read_text(encoding="utf-8")
        )
    }
    complexity = {}
    tasks = []
    for row in index:
        name = row["scenario"]
        paired_mtu = (
            (row["part"], row["cohort"]) == ("P1", "matrix") and name in MTU_SCENARIOS
        )
        if not paired_mtu and not name.startswith("TOKEN-COMPLEXITY-"):
            continue
        key = (*[row[field] for field in KEY], name)
        counter = counters[row["slot_order"]]
        require(
            counter["scenario"] == name
            and counter["execution_unit"] == row["execution_unit"],
            f"Counter join mismatch: {row['slot_id']}",
        )
        result = load_result(row)
        metrics = performance(row, result, counter)
        if paired_mtu:
            tasks.append(
                (
                    row,
                    result["packet_analysis_result"],
                    replays[row["result_json_path"]],
                    metrics,
                )
            )
        else:
            complexity[key] = metrics
    with ThreadPoolExecutor(max_workers=4) as pool:
        packets = {
            (*[row[field] for field in KEY], row["scenario"]): row
            for row in pool.map(extract_packets, tasks)
        }
    require(
        len(complexity) == 288 and len(packets) == 72,
        "Incomplete analysis",
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows, pairs, metrics in (
        ("complexity", complexity, COMPLEXITY, METRICS),
        ("mtu", packets, MTU, (*METRICS, *PACKET_METRICS)),
    ):
        pairs = pairs + [
            (f"{label} TLS", f"{candidate}-TLS", f"{reference}-TLS")
            for label, candidate, reference in pairs
        ]
        effects = list(compare(rows, pairs, metrics))
        write_csv(args.output / f"{name}-runs.csv", list(rows.values()))
        write_csv(args.output / f"{name}-effects-by-round.csv", effects)
        write_csv(
            args.output / f"{name}-effects-by-condition.csv", list(summarize(effects))
        )
    print(f"{len(complexity)} complexity results and {len(packets)} verified captures")


if __name__ == "__main__":
    main()
