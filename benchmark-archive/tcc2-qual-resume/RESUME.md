# Qualification resume state — saved before reboot 2026-09-14 ~04:10 UTC

## Frozen identity
- Expected commit: `b23eb22630773ed11151bf7758148e9adb17cd84`
- Verified at session start: `git rev-parse HEAD` matched; `git status --short` clean.
- Inventory verified: 444 total / 222 base + 222 TLS / 112 Part-1 matrix (idx0–111).
- MTU verified: host NIC, all Docker bridges and veths at MTU 1500 (see `_mtu.txt` in evidence root).
- Plugin: `cargo build --locked --release -p mosquitto-auth-biscuit` → 0 crates compiled
  (already current); sha256 `b8b05cfa914844588bde504e55b963e1ef288ca1f5445d63014f262149a09994`.
- Tokens regenerated once for frozen commit; sha256
  `88038a7edfefe1bdd366c03db90de79baade497ebfaca10c88807c5e29f2293a`.
  (`tokens.json`/`password-map.json` are gitignored; they persist in the workspace,
  NOT in /tmp — no action needed after reboot. Verify hash before resuming.)

## Evidence root (in workspace, survives reboot)
- `mqtt-auth-biscuit/benchmarks/results-qual-frozen-b23eb22-c10-m10-20260914T060835Z/`
- Stamp: `20260914T060835Z` (copy in `stamp.txt`; evidence relpath in `evid.txt`).
- Contains `_provenance.txt`, `_mtu.txt`, `_inventory_idx0-111.txt`.

## Completed groups (evidence moved into evidence root, 12/19)
- grp01 idx000–005, grp02 idx006–011, grp03 idx012–017, grp04 idx018–023,
  grp05 idx024–029, grp06 idx030–035, grp07 idx036–041, grp08 idx042/043/046/048/049,
  grp09 idx050–055, grp10 idx056–061, grp11 idx062–067, grp12 idx068–073.
- All completed groups exited RUNNER_EXIT:0 with all expected scenario JSONs present.
- Blocked idx44/45/47 skipped by design (ENVIRONMENT-BLOCKED, MTU evidence only).

## FORFEIT — rerun from beginning after reboot
- grp13 idx074–079 (CHAIN family) was ABORTED mid-execution by user reboot.
- Partial runner log: `$EVID/grp13-idx074-079.runner.log` (truncated, forfeit).
- Live `mqtt-auth-biscuit/benchmarks/results/` did NOT exist at save time — nothing to discard.
- On resume: (1) confirm no live `results/` dir; (2) rename the partial
  `grp13-idx074-079.runner.log` to `grp13-idx074-079.runner.log-FORFEIT-partial`;
  (3) rerun G13 fresh (command below); (4) verify `git status` still clean first.

## Remaining groups (in order, groups of 4–6, --skip-build --skip-tokens)
- G13 idx74–79: TOKEN-COMPLEXITY-CHAIN-1-BISCUIT,TOKEN-COMPLEXITY-CHAIN-1-BISCUIT-TLS,TOKEN-COMPLEXITY-CHAIN-25-BISCUIT,TOKEN-COMPLEXITY-CHAIN-25-BISCUIT-TLS,TOKEN-COMPLEXITY-CHAIN-5-BISCUIT,TOKEN-COMPLEXITY-CHAIN-5-BISCUIT-TLS
- G14 idx80–85: TOKEN-COMPLEXITY-DATALOG-HIGH-BISCUIT,TOKEN-COMPLEXITY-DATALOG-HIGH-BISCUIT-TLS,TOKEN-COMPLEXITY-DATALOG-LOW-BISCUIT,TOKEN-COMPLEXITY-DATALOG-LOW-BISCUIT-TLS,TOKEN-COMPLEXITY-DATALOG-MED-BISCUIT,TOKEN-COMPLEXITY-DATALOG-MED-BISCUIT-TLS
- G15 idx86–91: TOKEN-DELEGATION-HANDOFF-BISCUIT,TOKEN-DELEGATION-HANDOFF-BISCUIT-TLS,TOKEN-DELEGATION-SIMULATED-BISCUIT,TOKEN-DELEGATION-SIMULATED-BISCUIT-TLS,TOKEN-DELEGATION-TEMP-ONLY-BISCUIT,TOKEN-DELEGATION-TEMP-ONLY-BISCUIT-TLS
- G16 idx92–97: TOKEN-ISSUER-BASELINE-BISCUIT,TOKEN-ISSUER-BASELINE-BISCUIT-TLS,TOKEN-ISSUER-BASELINE-JWT,TOKEN-ISSUER-BASELINE-JWT-TLS,TOKEN-LIFECYCLE-SHORT-RECONNECT-BISCUIT,TOKEN-LIFECYCLE-SHORT-RECONNECT-BISCUIT-TLS
- G17 idx98–103: TOKEN-LIFECYCLE-SHORT-RECONNECT-JWT,TOKEN-LIFECYCLE-SHORT-RECONNECT-JWT-TLS,TOKEN-QOS-MIXED-BISCUIT,TOKEN-QOS-MIXED-BISCUIT-TLS,TOKEN-QOS-MIXED-JWT,TOKEN-QOS-MIXED-JWT-TLS
- G18 idx104–109: TOKEN-QOS2-BISCUIT,TOKEN-QOS2-BISCUIT-TLS,TOKEN-QOS2-JWT,TOKEN-QOS2-JWT-TLS,TOKEN-THUNDERING-HERD-BISCUIT,TOKEN-THUNDERING-HERD-BISCUIT-TLS
- G19 idx110–111: TOKEN-THUNDERING-HERD-JWT,TOKEN-THUNDERING-HERD-JWT-TLS

Per-group template (from repo root, EVID=$(cat ~/tcc2-qual-resume/evid.txt)):
  ./scripts/run-benchmarks --scenarios "<CSV>" --workload-shape matrix --clients 10 \
    --messages 10 --client-topology container-per-client --client-memory 96m \
    --skip-build --skip-tokens 2>&1 | tee "$EVID/grpNN-idxAAA-BBB.runner.log" | tail -6
  # then: mv results → $EVID/grpNN-idxAAA-BBB/ ; mv runner log inside as runner.log
  # Never overwrite evidence; never auto-rerun failures; quarantine partials on abort.

## Still pending after execution
- Per-scenario TESTING.md review of all 109 executed JSONs + 8 named regression areas.
- Final report: frozen hash; PASS/FAIL/SUSPICIOUS/ENVIRONMENT-BLOCKED/NOT_RUN totals;
  ordered idx0–111 table/artifact; failure evidence paths; idx44/45/47 MTU confirmation;
  cross-family regressions. Verdict HOST-QUALIFIED only if 109/3/0/0/0 else HOLD.
- Constraints remain: no source/config/fixture/docs modification; no c10/m100;
  no 3-repetition collection; no fixes.

## Preserved /tmp artifacts (in this dir)
- `stamp.txt`, `evid.txt` (copies of /tmp/qual-stamp/).
- `qual-idx000..005.log`, `qual_commands.log` (current-session /tmp/opencode leftovers).
- `opencode-tmp-backup/` — full Sep-13 prior-session material: qual-idx006..111.log,
  rerun-1..23.log, qual_matrix.txt, qual_table.csv, qual_verdicts.csv,
  qual_validate.py, qual_run.sh, rerun.sh, rerun_lists/tables, tokens backups.
  NOTE: prior-session artifacts are reference only, NOT evidence for this frozen commit.
