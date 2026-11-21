# Batch B (c200/m10, idx014-031) r1 provenance adjudication — HOLD

Date: 2026-09-17. Frozen HEAD `56344b7`, parent `452215f` (CONNECT-timeout
fix), clean tracked tree, `--skip-build --skip-tokens` throughout. No rebuild,
no token/password-map regeneration. All 4 frozen hashes verified before Batch A
and re-verified after the Batch B r1 failure (unchanged):
`mqtt-loadgen b3d4352b…`, plugin `b8b05cfa…`, `tokens.json 78de5f0c…`,
`password-map.json e6db4c97…`.

## Verdict: HOLD — stop the c200/m10 cell, do not auto-rerun

Batch B r1 failed on its first scenario with genuine workload-phase loadgen
errors under the exact frozen command. Per execution protocol (do not auto-rerun
genuine benchmark failures; stop only on HOLD or completion): r2/r3 NOT
attempted, Batches C–G NOT started.

## Evidence

- Exact command (repo root, established Batch B inventory order, 18 scenarios):
  `./scripts/run-benchmarks --scenarios "HTTP-LATENCY-1000MS-JWT,
  HTTP-LATENCY-1000MS-JWT-TLS,HTTP-LATENCY-200MS-BISCUIT,
  HTTP-LATENCY-200MS-BISCUIT-TLS,HTTP-LATENCY-200MS-JWT,
  HTTP-LATENCY-200MS-JWT-TLS,HTTP-PROFILE-COMPLEX-BISCUIT,
  HTTP-PROFILE-COMPLEX-BISCUIT-TLS,HTTP-PROFILE-COMPLEX-JWT,
  HTTP-PROFILE-COMPLEX-JWT-TLS,HTTP-PROFILE-MED-BISCUIT,
  HTTP-PROFILE-MED-BISCUIT-TLS,HTTP-PROFILE-MED-JWT,HTTP-PROFILE-MED-JWT-TLS,
  HTTP-PROFILE-SIMPLE-BISCUIT,HTTP-PROFILE-SIMPLE-BISCUIT-TLS,
  HTTP-PROFILE-SIMPLE-JWT,HTTP-PROFILE-SIMPLE-JWT-TLS" --workload-shape matrix
  --clients 200 --messages 10 --client-topology container-per-client
  --client-memory 96m --skip-build --skip-tokens`
- Failure: `RuntimeError: HTTP-LATENCY-1000MS-JWT: loadgen errors:
  publish_failed:publish_failed:event loop dropped notice sender,
  eventloop_failed:Mqtt state: Last pingreq isn't acked, ...` raised at
  `_validate_result_contract` (`run_scenarios.py:3227`). Process exit status 1
  after `Cleaning up Docker services...`.
- No scenario JSON was written by the failed run; `benchmarks/results/` does
  not exist afterward (runner cleaned up). Nothing to quarantine or splice.
  Failure is NOT operator-aborted, externally killed, or identity-uncertain:
  command identity is certain, workload reached the first scenario.
- Host state after failure: 23 GB RAM, ~14–16 GB available, no OOM evidence
  available (`dmesg` not permitted in container); failure signature is MQTT
  keepalive starvation, not memory exhaustion.

## Analysis

- The CONNECT-timeout fix IS effective here: derived per-operation budgets at
  c200/LAT1000 are `ceil(200 × 1.0 s + 15 s) = 215 s` for both publish PUBACK
  and connect CONNACK waits (`_publish_timeout_seconds`). The failure is not a
  connect or PUBACK timeout.
- Failure mechanism: the single-threaded Mosquitto ACL path serializes
  200 clients × 10 msgs = 2000 PDP authorizations × 1000 ms (≈33 min wall for
  this one scenario). While the broker thread is blocked, it cannot answer
  MQTT PINGREQ, so rumqttc client event loops drop (`Last pingreq isn't
  acked` → `event loop dropped notice sender` → publish failures). This is
  inherent to the frozen serialized-HTTP-authorizer design at 200 clients, not
  a flaky environment event.
- c10/m10 reference for the same scenario (accepted final data):
  `errors: []`, `connect.count: 10`, `publish.count: 100`,
  `connect_timeout = publish_timeout = 25`, wall ≈ 101 s. Scaling to c200
  multiplies the serialized PDP queue 20× while keepalive behavior is unchanged.
- Batch A c200/m10 r1/r2/r3 (14/14 JSONs each, `errors: []` everywhere,
  counters scale exactly per contract, TLS parity exact) is unaffected and
  remains accepted.

## Consequence

- `results-final-p1-56344b7-c200-m10-idx000-013-r1/r2/r3` remain on disk
  UNCHANGED and accepted (Batch A verdict: ADVANCE).
- No `results-final-p1-56344b7-c200-m10-idx014-031-*` directory was created.
- Batch B r2/r3 and Batches C–G NOT started (stop on HOLD). No data fabricated,
  no topology/memory/client-count change made.
- `b23eb22-*` and all `c10/*` directories untouched.

## Operator decision required (one of)

1. Declare the c200 LAT1000/LAT200 cells ENVIRONMENT-BLOCKED with this file as
   evidence, and continue Batches B–G for the non-latency scenarios only via
   an explicit new instruction (note: deviates from the exact batch command
   shape; would need a recorded slice exception).
2. Accept c200/m10 as complete-with-exclusions (Batch A only) and move on.
3. Change keepalive/PDP serialization (breaks frozen identity → new campaign,
   new hashes, supersedes this cell).

Do NOT silently lower memory, client count, or switch topology, and do NOT
rerun Batch B r1 under the frozen identity without an explicit operator order
overriding this HOLD.
