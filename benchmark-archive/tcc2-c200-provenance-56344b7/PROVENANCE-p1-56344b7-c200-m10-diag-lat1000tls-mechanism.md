# Quarantined diagnostic: HTTP-LATENCY-1000MS-JWT-TLS @ c200/m10 — mechanism evidence

Date: 2026-09-17. Frozen HEAD `56344b7`, `--skip-build --skip-tokens`, no
code/config change. Single scenario, exact frozen topology
(`--workload-shape matrix --clients 200 --messages 10 --client-topology
container-per-client --client-memory 96m`). Run ID
`http_latency_1000ms_jwt_tls-1-1789672378551062704-773de2b7`; barrier
`release?participants=200` → 200 OK (all 200 workers checked in alive).

Quarantine: `results-quarantine-diag-lat1000tls-c200-m10/` (`diag-run.log`,
`broker-snap1/2/3-collapse.log`). NEVER final data; not aggregated; the
original final-run failure stands regardless of this diagnostic.

Disclosure: the background runner was killed by the operator-tool timeout
after the client collapse (log frozen at barrier release, no `results/`
collected). The broker-log mechanism evidence below was captured live from
the broker container and is complete and independent of the runner. No
second diagnostic will be run.

## Broker-log timeline (t relative to first CONNECT, `k60` keepalive)

- t+0–144 s: all 200/200 TLS connects complete (`New client connected`,
  TLSv1.3, cached CONNECT auth — fast, not 1 s-serialized).
- t+1–266 s: 325/2000 publishes at ~1/s (`Received PUBLISH` + PUBACK) —
  confirms the 1 s PDP serializes the publish path.
- t+144 s: 1 client-side close. t+266 s: 19 closes. t+327 s: 180 closes.
  Total 200/200 disconnects (197 `connection closed by client`, 3 `Broken
  pipe` where the broker wrote to an already-dead socket). Zero broker-side
  errors; zero `failures` semantics — every death is a client giving up.

## Mechanism (established)

Single-threaded Mosquitto main loop + synchronous 1 s HTTP authorizer:
with ~200 clients' publishes queued, each PUBLISH costs one 1 s PDP call, so
a PINGREQ queued behind the publish backlog waits up to ~200 s — far past
the 60 s keepalive. rumqttc declares `Last pingreq isn't acked`, its event
loop drops, the client closes TCP. At c10 the same queue is ~10 deep (~10 s
< 60 s), so it survives — a sharp structural capacity boundary at c200,
not a flake and not host exhaustion (no OOM; broker never errored).

## Reading of the original final-run failure

Original: broker `attempts = 199/200`, `successes = 199`, `failures = 0`,
surfaced at the broker-path contract, which validates BEFORE the
loadgen-error list — so the missing client's loadgen-side error was never
inspected. Under the established mechanism, the 199 is an earlier casualty
of the same starvation: one client's CONNECT/CONNACK (TLS handshake plus
first serialized auths, fixed 30 s `connection_timeout` vs 215 s CONNACK
budget — see `mqtt_helpers.rs:238`) starved in the connect burst, so the
broker never counted its attempt. Same underlying scalability failure as
plaintext (which connected 200/200, then died identically in publish
phase); different surface symptom only because validation order caught it
at the counter stage. No harness off-by-one fits (identical code meets
`attempts == clients` at c10/TLS; no fanout/control extras; sequential
snapshots).

## Classification consequence

`HTTP-LATENCY-1000MS-JWT-TLS` = SATURATION-FAILED / CAPACITY-LIMIT
(workload-induced broker-liveness starvation under the frozen design).
Recorded in `SATURATION-p1-56344b7-c200-m10-latency.md`; r2/r3
SKIPPED-STRUCTURAL. No numeric JSON fabricated. Batch B resumes at idx016.
