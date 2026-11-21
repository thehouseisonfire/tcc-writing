#!/usr/bin/env bash
# Focused verification reruns after failure-family fixes. Usage: rerun.sh START END
# (1-based line numbers into rerun_list.txt). Individual invocations; continues
# through failures without retrying.
REPO=/home/eagle/TCC2
LIST=/tmp/opencode/rerun_list.txt
TABLE=/tmp/opencode/rerun_table.csv
CMDLOG=/tmp/opencode/rerun_commands.log
cd "$REPO"
mapfile -t IDS < "$LIST"
for (( n=$1; n<=$2; n++ )); do
  id="${IDS[$((n-1))]}"
  dest="mqtt-auth-biscuit/benchmarks/results-rerun-fix-${id}"
  echo "=== RERUN $n id=$id ==="
  echo "$n :: ./scripts/run-benchmarks --scenarios $id --workload-shape matrix --clients 10 --messages 10 --client-topology container-per-client --client-memory 96m --skip-build --skip-tokens" >> "$CMDLOG"
  ./scripts/run-benchmarks \
    --scenarios "$id" \
    --workload-shape matrix \
    --clients 10 \
    --messages 10 \
    --client-topology container-per-client \
    --client-memory 96m \
    --skip-build \
    --skip-tokens > "/tmp/opencode/rerun-${n}.log" 2>&1
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
  echo "${n},${id},${exit_code},${json_path}" >> "$TABLE"
  echo "--- RERUN $n id=$id exit=$exit_code json=$json_path"
done
echo "RERUN_CHUNK_DONE $1..$2"
