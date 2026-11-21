#!/usr/bin/env bash
# Qualification sweep chunk runner: runs scenarios individually in inventory
# order, preserving partial evidence and continuing through failures.
# Usage: qual_run.sh START_IDX END_IDX  (inclusive, 0-based into qual_matrix.txt)
REPO=/home/eagle/TCC2
MATRIX=/tmp/opencode/qual_matrix.txt
TABLE=/tmp/opencode/qual_table.csv
CMDLOG=/tmp/opencode/qual_commands.log
cd "$REPO"
mapfile -t IDS < "$MATRIX"
for (( idx=$1; idx<=$2; idx++ )); do
  id="${IDS[$idx]}"
  padded=$(printf '%03d' "$idx")
  dest="mqtt-auth-biscuit/benchmarks/results-qual-matrix-c10-m10-idx${padded}-${id}"
  echo "=== QUAL idx=$idx id=$id ==="
  echo "idx=$idx :: ./scripts/run-benchmarks --scenarios $id --workload-shape matrix --clients 10 --messages 10 --client-topology container-per-client --client-memory 96m --skip-build --skip-tokens" >> "$CMDLOG"
  ./scripts/run-benchmarks \
    --scenarios "$id" \
    --workload-shape matrix \
    --clients 10 \
    --messages 10 \
    --client-topology container-per-client \
    --client-memory 96m \
    --skip-build \
    --skip-tokens > "/tmp/opencode/qual-idx${padded}.log" 2>&1
  exit_code=$?
  json_path="NO_RESULTS_DIR"
  if [ -d mqtt-auth-biscuit/benchmarks/results ]; then
    if [ -f "mqtt-auth-biscuit/benchmarks/results/${id}.json" ]; then
      json_path="${dest}/${id}.json"
    else
      json_path="${dest}/MISSING_JSON"
    fi
    rm -rf "$dest"
    mv mqtt-auth-biscuit/benchmarks/results "$dest"
  fi
  echo "${idx},${id},${exit_code},${json_path}" >> "$TABLE"
  echo "--- QUAL idx=$idx id=$id exit=$exit_code json=$json_path"
done
echo "CHUNK_DONE $1..$2"
