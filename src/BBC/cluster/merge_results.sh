#!/bin/bash
# Merge the per-config result CSVs (results/raw_<CFG>.csv) produced by the job
# array into a single raw_results.csv, keeping ONE header row.
set -euo pipefail
cd "$(dirname "$0")/.."          # -> src/BBC
shopt -s nullglob
files=(results/raw_*.csv)
if [ ${#files[@]} -eq 0 ]; then echo "No results/raw_*.csv found."; exit 1; fi
out="raw_results.csv"
first=1
: > "$out"
for f in "${files[@]}"; do
    if [ $first -eq 1 ]; then cat "$f" > "$out"; first=0
    else tail -n +2 "$f" >> "$out"; fi
done
echo "Merged ${#files[@]} files -> $out  ($(( $(wc -l < "$out") - 1 )) data rows)"
