# SATURATION ledger — Part 1 c200/m10 HTTP-latency family, frozen `56344b7`

Frozen identity: HEAD `56344b77e49fff477b7ec7456fdf3e4469d995b4`, parent
`452215f73b092686b15cb6562f8dea4d071c3ac5` (CONNECT-timeout fix). No rebuild,
no token regeneration, no keepalive/PDP change. `--skip-build --skip-tokens`
throughout.

Taxonomy (do not conflate):

- `SATURATION-FAILED / CAPACITY-LIMIT`: workload-induced keepalive starvation
  under the frozen synchronous-HTTP-authorizer design. Categorical scalability
  outcome; excluded from numeric latency/throughput aggregation; never retried
  to force a pass.
- `SKIPPED-STRUCTURAL`: r2/r3 not executed because r1 established the
  structural saturation boundary for that scenario.
- `ENVIRONMENT-BLOCKED`: MTU-9000 `idx44/45/47` only (separate ledger
  convention); never mixed with saturation entries.

Failure signature qualifying as saturation (all must hold):

1. `Last pingreq isn't acked` / rumqttc event-loop drop with publish failures
   under serialized PDP delay;
2. failure occurs during the measured workload (not pre-workload);
3. CONNECT/PUBACK timeout budgets correctly derived (fix functioning);
4. no host OOM, no topology/container failure, no operator abort.

## idx014 HTTP-LATENCY-1000MS-JWT — SATURATION-FAILED (r1)

- r1: full 18-scenario Batch B invocation, exact frozen command
  (`--workload-shape matrix --clients 200 --messages 10 --client-topology
  container-per-client --client-memory 96m --skip-build --skip-tokens`).
  `RuntimeError: HTTP-LATENCY-1000MS-JWT: loadgen errors: publish_failed
  (event loop dropped notice sender), eventloop_failed (Last pingreq isn't
  acked)` at contract validation (`run_scenarios.py:3227`), exit 1. No JSON
  written; runner cleaned up. Full evidence in
  `PROVENANCE-p1-56344b7-c200-m10-batchB-r1-HOLD.md` (permanent, preserved).
- r2: SKIPPED-STRUCTURAL (not executed; r1 established the boundary).
- r3: SKIPPED-STRUCTURAL (not executed; r1 established the boundary).

## idx015 HTTP-LATENCY-1000MS-JWT-TLS — SATURATION-FAILED (r1)

- r1: 17-scenario reduced Batch B slice (exact frozen command, minus idx014).
  `RuntimeError: HTTP-LATENCY-1000MS-JWT-TLS: broker authentication path
  contract failed: {attempts: 199, successes: 199, failures: 0,
  jwt_validations: 199}` vs expected 200 (`run_scenarios.py:3028-3029`).
  No JSON written; runner cleaned up. Full evidence in
  `PROVENANCE-p1-56344b7-c200-m10-batchB-reduced-r1-HOLD.md` (permanent).
- Mechanism (established by the single quarantined diagnostic, see
  `PROVENANCE-p1-56344b7-c200-m10-diag-lat1000tls-mechanism.md`): 200/200
  fast TLS connects, then ~1/s serialized publishes, then total client-side
  close waves (1 + 19 + 180 = 200/200) as PINGREQ waits behind the ~200-deep
  x 1 s PDP queue exceed the 60 s keepalive — workload-induced
  broker-liveness starvation, same structural capacity limit as idx014. The
  199 (not 200) is an earlier connect-phase casualty of the same starvation
  (fixed 30 s TLS `connection_timeout` vs 215 s CONNACK budget), surfaced as
  a counter shortfall only because the broker-path contract validates before
  the loadgen-error list. No harness defect found.
- r2: SKIPPED-STRUCTURAL (not executed; r1 + diagnostic established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; r1 + diagnostic established the
  boundary).

## idx016 HTTP-LATENCY-200MS-BISCUIT — SATURATION-FAILED (r1, clean broker)

- r1 attempt 1 (superseded, INVALID): dirty broker reused from the killed
  diagnostic (see `...-batchB-rem-r1-attempt1-INVALID.md`);
  `publish_failed:publish_timeout ×5+` at contract validation. Not a result.
- r1 attempt 2 (clean, decisive): FRESH broker (log: `Container
  docker-mosquitto-1 Creating → Created → Starting → Started`), barrier
  `release?participants=200` 200 OK, full log preserved at
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-rem-r1-clean.log`.
  `RuntimeError: broker authentication path contract failed: {attempts: 120,
  successes: 120, failures: 0, biscuit_validations: 120}` vs expected 200.
- Mechanism (same capacity family, PUBACK/CONNACK-budget surface): the LAT200
  definitions set the real PDP delay (`authz_config delay_ms=200`) but omit
  `http_expected_delay_ms`, so per-operation budgets stay flat at BASE 10 s
  at every client count (c10 JSON confirms `cto=pto=10`; c10 max publish wait
  3.6 s fit, barely). At c200 the serialized 200 ms PDP builds ~200-deep
  queues (≈40 s+ waits in steady state, plus a ~40 s serialized connect
  wave), deterministically exceeding the frozen 10 s CONNACK/PUBACK budgets:
  late connecters time out with zero broker-side failures (120/200
  attempts), and late publishers time out identically (attempt-1 surface).
  The SUT queueing is genuine workload-induced serialization; the flat
  budget is a frozen annotation gap that cannot be fixed without breaking
  identity — structurally non-measurable at c200 either way. No harness
  off-by-one (same accounting passes at c10 and for all non-latency c200
  scenarios); no host OOM (Batch A ran the identical 200-container topology
  3× cleanly).
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx017 HTTP-LATENCY-200MS-BISCUIT-TLS — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-rem-r1b-clean.log`).
  Passed the broker-path contract (200/200 attempts), then failed at
  `_validate_result_contract:3227` with `publish_failed:publish_timeout ×5+`
  — the publish-side surface of the same LAT200 mechanism: steady-state
  serialized-200 ms-PDP queue waits exceed the frozen flat 10 s PUBACK
  budget (missing `http_expected_delay_ms` annotation; see idx016 entry).
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx018 HTTP-LATENCY-200MS-JWT — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-rem-r1c-clean.log`).
  Failed at `_validate_result_contract:3227` with both
  `connect_failed:connect_timeout` and `publish_failed:publish_timeout` —
  the ~40 s serialized connect wave and the publish queue both exceed the
  frozen flat 10 s budgets (missing `http_expected_delay_ms`; see idx016).
  Both LAT200 surfaces in one scenario; same capacity family.
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx019 HTTP-LATENCY-200MS-JWT-TLS — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-rem-r1d-clean.log`).
  Failed at `_validate_result_contract:3227` with
  `connect_failed:connect_timeout` — late connecters time out against the
  frozen flat 10 s CONNACK budget under the serialized 200 ms PDP connect
  wave (missing `http_expected_delay_ms`; see idx016). Same capacity
  family; completes the LAT200 set (idx016–019 all saturated).
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx021 HTTP-PROFILE-COMPLEX-BISCUIT-TLS — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-profiles-r1.log`).
  Failed at `_validate_result_contract:3227` with
  `connect_failed:connect_timeout ×5+`.
- Mechanism (same capacity family, no injected delay): the retained
  non-TLS twin idx020 (same invocation, fully validated: `errors: []`,
  `pub 2000`, `conn 200`) exposes the structural queue directly — connect
  p50 1186 ms / p95 8482 ms / max 8839 ms and publish p50 1058 ms /
  max 8712 ms against flat 10 s budgets. The 200-way connect burst through
  the single-threaded authorizer (Biscuit validation + complex-profile HTTP
  round trip per connection) already tails to ~8.8 s with zero PDP delay;
  the TLS variant's added handshake cost pushes the tail past the frozen
  10 s CONNACK budget. Workload-induced burst queueing vs frozen budget —
  no broker failure, no host fault.
- Retained: idx020 `HTTP-PROFILE-COMPLEX-BISCUIT.json` (validated prefix of
  the aborted invocation; written post-validation) moved to
  `results-final-p1-56344b7-c200-m10-idx020-031-r1/`, to be completed by
  subsequent remainder slices. No unvalidated data retained.
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx023 HTTP-PROFILE-COMPLEX-JWT-TLS — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-rem-r1e-clean.log`).
  Failed at the broker-path contract (`:3029`) with
  `{attempts: 182, successes: 182, failures: 0, jwt_validations: 182}` vs
  expected 200 — 18 connecters starved in the burst, zero broker failures.
  Same counter-shortfall surface as idx015 (there 199/200); the missing
  clients' loadgen connect errors are masked by broker-first validation
  order (see idx015 mechanism note).
- Mechanism (same capacity family, no injected delay): retained plaintext
  twin idx022 (same invocation, validated: `errors: []`, `pub 2000`,
  `conn 200`) tails to connect max 5541 ms against the flat 10 s budget;
  the TLS variant's handshake overhead pushes 18/200 connecters past it.
  Workload-induced burst queueing vs frozen budget.
- Retained: idx022 `HTTP-PROFILE-COMPLEX-JWT.json` (validated prefix) moved
  to `results-final-p1-56344b7-c200-m10-idx020-031-r1/`. No unvalidated
  data retained.
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx024 HTTP-PROFILE-MED-BISCUIT — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-rem-r1f-clean.log`).
  Failed at `_validate_result_contract:3227` with
  `publish_failed:publish_timeout ×5+` — steady-state publish queueing
  through the single-threaded authorizer exceeds the frozen flat 10 s
  PUBACK budget with zero injected PDP delay (cf. idx020 twin: publish max
  8712 ms plaintext). Same capacity family, publish-side surface. No JSON
  written (first scenario of its slice); nothing to retain.
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx026 HTTP-PROFILE-MED-JWT — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-rem-r1g-clean.log`).
  Failed at `_validate_result_contract:3227` with
  `publish_failed:publish_timeout ×5+`. Same capacity family,
  publish-side surface, zero injected delay.
- Retained: idx025 `HTTP-PROFILE-MED-BISCUIT-TLS.json` (validated prefix:
  `errors: []`, `pub 2000`, `conn 200`; margins tell the story — conn max
  9812 ms, pub max 7439 ms against the flat 10 s budgets, i.e. the boundary
  is stochastic at this profile) moved to
  `results-final-p1-56344b7-c200-m10-idx020-031-r1/`. No unvalidated data
  retained.
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx027 HTTP-PROFILE-MED-JWT-TLS — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-rem-r1h-clean.log`).
  Failed at `_validate_result_contract:3227` with
  `connect_failed:connect_timeout ×5+` — connect-burst queueing past the
  frozen flat 10 s CONNACK budget. Same capacity family, connect-side
  surface, zero injected delay. No JSON written (first of its slice).
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx028 HTTP-PROFILE-SIMPLE-BISCUIT — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-rem-r1i-clean.log`).
  Failed at `_validate_result_contract:3227` with
  `publish_failed:publish_timeout ×5+` — even the lightest HTTP profile
  (plaintext, zero PDP delay) exceeds the frozen flat 10 s PUBACK budget
  at 200-way concurrency through the single-threaded authorizer. Same
  capacity family, publish-side surface. No JSON written.
- Note: idx020/022/025 passes at neighboring profiles with 5.5–9.8 s tails
  show the boundary is stochastic run-to-run; those remain accepted as
  fully contract-validated measurements, not flakes.
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx029 HTTP-PROFILE-SIMPLE-BISCUIT-TLS — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-rem-r1j-clean.log`).
  Failed at `_validate_result_contract:3227` with
  `connect_failed:connect_timeout ×4+`. Same capacity family,
  connect-side surface, zero injected delay. No JSON written.
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx030 HTTP-PROFILE-SIMPLE-JWT — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-rem-r1k-clean.log`).
  Failed at `_validate_result_contract:3227` with
  `publish_failed:publish_timeout ×5+`. Same capacity family,
  publish-side surface, zero injected delay. No JSON written.
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx020 HTTP-PROFILE-COMPLEX-BISCUIT — SATURATION-FAILED (stochastic boundary)

- r1: PASSED fully validated (`errors: []`, `pub 2000`, `conn 200`) but on
  the edge (connect p95 8482 ms / max 8839 ms vs flat 10 s budget); JSON
  initially retained in `results-final-p1-56344b7-c200-m10-idx020-031-r1/`,
  then WITHDRAWN to
  `results-quarantine-diag-lat1000tls-c200-m10/` as boundary evidence (r1
  summary regenerated over the remainder) after r2.
- r2: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-runnable-r2.log`),
  first scenario of its slice — directly comparable position to r1 — failed
  at `_validate_result_contract:3227` with
  `connect_failed:connect_timeout ×5+`. Same capacity family.
- Split verdict (r1 pass / r2 fail, identical frozen setup) proves a
  stochastic boundary: the scenario cannot yield the required 3
  contract-valid repetitions, and chasing further passes would be
  outcome-hunting. Per the Phase 6 triplet rule (one bad repetition
  invalidates the triplet) the scenario is categorically SATURATION-FAILED;
  no numeric aggregation.
- r3: SKIPPED-STRUCTURAL (not executed; r1/r2 split established the
  stochastic boundary).

## idx022 HTTP-PROFILE-COMPLEX-JWT — SATURATION-FAILED (stochastic boundary)

- r1: PASSED fully validated (`errors: []`, `pub 2000`, `conn 200`;
  connect max 5541 ms vs flat 10 s budget); JSON initially retained, then
  WITHDRAWN to `results-quarantine-diag-lat1000tls-c200-m10/` as boundary
  evidence (r1 summary regenerated over the remainder) after r2.
- r2: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-runnable-r2b.log`),
  first of its slice, failed at `_validate_result_contract:3227` with
  `connect_failed:connect_timeout ×5+`. Same capacity family.
- Split verdict proves the stochastic boundary (cf. idx020); no
  outcome-hunting reruns, no numeric aggregation.
- r3: SKIPPED-STRUCTURAL (not executed; r1/r2 split established the
  stochastic boundary).

## idx025 HTTP-PROFILE-MED-BISCUIT-TLS — SATURATION-FAILED (stochastic boundary)

- r1: PASSED fully validated (`errors: []`, `pub 2000`, `conn 200`) with
  the thinnest margins observed (conn max 9812 ms, pub max 7439 ms vs flat
  10 s budgets); JSON initially retained, then WITHDRAWN to
  `results-quarantine-diag-lat1000tls-c200-m10/` as boundary evidence (r1
  summary regenerated over the remainder) after r2.
- r2: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-runnable-r2c.log`),
  first of its slice, failed at `_validate_result_contract:3227` with
  `connect_failed:connect_timeout ×5+`. Same capacity family.
- Split verdict proves the stochastic boundary (cf. idx020/022); no
  outcome-hunting reruns, no numeric aggregation.
- r3: SKIPPED-STRUCTURAL (not executed; r1/r2 split established the
  stochastic boundary).

## idx031 HTTP-PROFILE-SIMPLE-JWT-TLS — SATURATION-FAILED (stochastic boundary)

- r1: PASSED fully validated (`errors: []`, `pub 2000`, `conn 200`;
  conn max 8437 ms vs flat 10 s budget); JSON initially retained, then
  WITHDRAWN to `results-quarantine-diag-lat1000tls-c200-m10/` as boundary
  evidence (r1 summary regenerated, then the emptied r1 dir
  `results-final-p1-56344b7-c200-m10-idx020-031-r1/` removed to avoid an
  aggregator trap) after r2.
- r2: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchB-runnable-r2d.log`),
  single-scenario slice, failed at `_validate_result_contract:3227` with
  `connect_failed:connect_timeout`. Same capacity family.
- Split verdict proves the stochastic boundary (cf. idx020/022/025); no
  outcome-hunting reruns, no numeric aggregation. Batch B closes with ZERO
  accepted numeric JSONs: all 18 scenarios categorically saturated (14
  deterministic r1-observed + 4 stochastic r1-pass/r2-fail); the 4
  withdrawn r1 passes are preserved in quarantine as boundary evidence.
- r3: SKIPPED-STRUCTURAL (not executed; r1/r2 split established the
  stochastic boundary).

## idx032 HYBRID-FALLBACK-AUTHZ-DOWN-JWT — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchC-r1.log`), first of
  its slice. Failed at `_validate_result_contract:3227` with
  `connect_failed:connect_timeout ×5+`. No JSON written.
- Mechanism (same capacity family): the authz-DOWN fallback path pays a
  per-decision backend-failure wait on the single-threaded broker path
  (c10 reference: connect p50 224 ms / max 280 ms vs flat 10 s budgets —
  comfortable at 10 clients). At 200-way burst concurrency the queued
  fallback waits exceed the frozen flat 10 s CONNACK budget. Zero broker
  failures, zero host fault; deterministic on a clean broker.
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).

## idx033 HYBRID-FALLBACK-AUTHZ-DOWN-JWT-TLS — SATURATION-FAILED (r1, clean broker)

- r1: fresh broker (log `Container docker-mosquitto-1 Created`;
  `results-quarantine-diag-lat1000tls-c200-m10/batchC-r1b-clean.log`),
  first of its slice. Failed at `_validate_result_contract:3227` with
  `connect_failed:connect_timeout ×5+`. Same fallback-path burst queueing
  vs frozen 10 s budget, TLS-amplified; same capacity family. No JSON
  written.
- r2: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
- r3: SKIPPED-STRUCTURAL (not executed; clean-broker r1 established the
  boundary).
