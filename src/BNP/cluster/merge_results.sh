#!/bin/bash
# Merge the per-task CSV shards (cluster/results/bnp_task*.csv) into one
# src/BNP/bnp_results.csv with a single header row. Idempotent; re-run anytime.
set -euo pipefail
cd "$(dirname "$0")"                            # -> src/BNP/cluster/
OUT="../bnp_results.csv"
shards=( results/bnp_task*.csv )
if [ ! -e "${shards[0]}" ]; then echo "no shards in cluster/results/"; exit 1; fi
head -1 "${shards[0]}" > "$OUT"
for f in "${shards[@]}"; do tail -n +2 "$f" >> "$OUT"; done
echo "merged ${#shards[@]} shards -> $OUT  ($(( $(wc -l < "$OUT") - 1 )) rows)"
