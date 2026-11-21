# Batch B remainder r1 attempt 1 (c200/m10, idx016-031) — INVALID, superseded (dirty start)

Date: 2026-09-17. Frozen HEAD `56344b7`, `--skip-build --skip-tokens`.

## Ruling: environmentally invalid execution, NOT a genuine benchmark result

The 16-scenario remainder slice (idx016–031) aborted on its first scenario
(`HTTP-LATENCY-200MS-BISCUIT: loadgen errors: publish_failed:publish_timeout
×5+`). This attempt is ruled INVALID and is superseded by a clean rerun of
the identical slice (valid r1), because its broker was certainly dirty at
start:

- The killed LAT1000-TLS diagnostic never tore down its stack (runner killed
  by operator-tool timeout; infra containers observed still UP afterward,
  including `docker-mosquitto-1` holding 200 dead client sessions).
- Per-scenario startup is `compose up --build -d mosquitto authz ...`
  (`run_scenarios.py:8274`) with no `--force-recreate`: a running mosquitto
  container is REUSED, never replaced. The remainder attempt therefore ran
  its connect burst (same `client_1..200` IDs) as a 200-way session-takeover
  storm against the diagnostic's dead sessions — an uncontrolled,
  unmeasured confound on top of the workload.
- Nothing was written (no JSON; runner cleaned up); nothing to quarantine
  beyond this record. No data spliced.

## Deterministic annotation finding ( motivation for the clean rerun)

Independent of the dirt: the LAT200 scenario definitions set the real PDP
delay (`authz_config delay_ms=200`) but omit `http_expected_delay_ms`, so
`_publish_timeout_seconds` returns the flat BASE 10 s at every client count
(c10 JSON confirms `pto=10`). At c200 the steady-state serialized publish
queue (~200-deep × 200 ms ≈ 40 s waits) exceeds the frozen 10 s budget by
construction — the same serialized-PDP capacity family as LAT1000, via the
PUBACK budget instead of keepalive. The clean rerun tests this prediction:
identical `publish_timeout` failure on a clean broker confirms a structural
boundary (classify `SATURATION-FAILED`); a pass proves the dirt was
material (adopt the clean run as valid r1).

## Bound

Exactly ONE clean rerun of the identical 16-scenario slice. Its outcome is
final for this decision: identical failure → classify idx016 and continue
progressive exclusion; different failure → HOLD; pass → valid r1, continue
r2/r3. No further reruns of idx016 under any outcome.
