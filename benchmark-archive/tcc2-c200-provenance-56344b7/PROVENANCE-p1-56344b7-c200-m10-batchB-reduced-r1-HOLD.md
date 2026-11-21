# Batch B reduced-slice (c200/m10, idx015-031) r1 provenance — HOLD

Date: 2026-09-17. Frozen HEAD `56344b77e49fff477b7ec7456fdf3e4469d995b4`,
parent `452215f` (CONNECT-timeout fix), clean tracked tree,
`--skip-build --skip-tokens`. All 4 frozen hashes re-verified unchanged after
the failure. Prior HOLD provenance (`...-batchB-r1-HOLD.md`) and the saturation
ledger (`SATURATION-p1-56344b7-c200-m10-latency.md`) are preserved permanently
and untouched by this file.

## Verdict: HOLD — different/ambiguous failure signature, not classified

Per the saturation-boundary protocol, a failure with a different or ambiguous
reason returns HOLD. `HTTP-LATENCY-1000MS-JWT-TLS` is NOT classified as
`SATURATION-FAILED`; it is NOT retried, NOT excluded, and NOT aggregated.

## Evidence

- Exact command (repo root): 17-scenario Batch B slice in established order
  (`HTTP-LATENCY-1000MS-JWT-TLS` first, then `HTTP-LATENCY-200MS-*` ×4, then
  `HTTP-PROFILE-*` ×12; `HTTP-LATENCY-1000MS-JWT` excluded as established
  `SATURATION-FAILED`), `--workload-shape matrix --clients 200 --messages 10
  --client-topology container-per-client --client-memory 96m --skip-build
  --skip-tokens`.
- Failure: `RuntimeError: HTTP-LATENCY-1000MS-JWT-TLS: broker authentication
  path contract failed: {'anonymous_deferrals': 0, 'attempts': 199,
  'biscuit_validations': 0, 'cache_hits': 353, 'cache_misses': 0, 'failures':
  0, 'jwt_validations': 199, 'successes': 199}` at
  `_validate_result_contract` (`run_scenarios.py:3028-3029`), exit 1 after
  `Cleaning up Docker services...`.
- Contract logic: no handoff/fanout/control extras for this scenario, so
  `expected_connections = 200`; observed `attempts = 199`,
  `successes = attempts`, `failures = 0`. Trigger is exactly one missing
  broker-side authentication attempt — NOT a loadgen error list.
- Why ambiguous (not the established saturation signature): the r1
  `HTTP-LATENCY-1000MS-JWT` failure showed rumqttc `Last pingreq isn't acked`
  / event-loop-drop loadgen errors. Here there are no reported loadgen
  errors; the shortfall is broker-side (`199 != 200`) with zero failures. It
  is plausibly saturation-adjacent (one client never completing auth under the
  ~2000 s serialized PDP queue), but equally plausibly a distinct
  connect-accounting race at 200 clients. The evidence cannot distinguish
  them, so no classification is made.
- c10/m10 reference (accepted final): `errors: []`, `publish.count: 100`,
  `connect.count: 10`, `connect_timeout = publish_timeout = 25`, wall ≈ 103 s.
- No scenario JSON written; `benchmarks/results/` absent afterward (runner
  cleaned up). Nothing to quarantine or splice. Not operator-aborted,
  externally killed, or identity-uncertain. Host healthy after failure
  (23 GB RAM, ~13–16 GB available; no OOM evidence).

## Consequence

- No `results-final-p1-56344b7-c200-m10-idx014-031-*` directory was created.
  Batch A r1–r3 unchanged and accepted. Saturation ledger unchanged
  (`HTTP-LATENCY-1000MS-JWT` remains the only `SATURATION-FAILED` entry).
- Batch B r2/r3 and Batches C–G NOT started (stop on HOLD). No data
  fabricated; no topology/memory/client-count change; no rebuild.

## Operator decision required (one of)

1. Investigate the `199 vs 200` broker-auth shortfall (broker diagnostics for
   the missing attempt; whether loadgen-side connect.count was 200/199;
   keepalive-adjacent or accounting race), then rule: reclassify as
   `SATURATION-FAILED`, grant a slice exception to continue, or open a new
   campaign.
2. Declare the c200 LAT1000 pair jointly non-measurable on this evidence and
   authorize continuing Batch B from `HTTP-LATENCY-200MS-BISCUIT` onward.
3. Accept the cell complete-with-exclusions as it stands (Batch A numeric +
   LAT1000-JWT categorical saturation outcome).

Options 1 (second half) and 2 change the slice composition and therefore
require an explicit operator order; they are NOT taken autonomously.
