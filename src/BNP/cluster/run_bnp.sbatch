#!/bin/bash
#SBATCH --job-name=bnp-campaign
#SBATCH --array=0-15
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --output=logs/bnp_%A_%a.out
#
# BNP (PCF' / PTF) branch-and-price campaign -- STANDALONE, SCIP-only.
# Separate from the BBC campaign; does not touch src/BBC/ or its raw_results.csv.
# No CPLEX/license needed (pyscipopt bundles SCIP).
#
# Each array task solves a DISJOINT shard of (instance) work (instance i goes to
# task i % NUM_TASKS), is independently resumable, and writes its OWN CSV shard;
# merge_results.sh combines them. Submit:  sbatch run_bnp.sbatch
set -euo pipefail

NUM_TASKS=16                                  # must equal array size (0-15 -> 16)
# Run from src/BNP (submit with: cd src/BNP && mkdir -p logs && sbatch cluster/run_bnp.sbatch).
# --output=logs/... is relative to the SUBMIT dir, so logs/ must already exist there.
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"   # -> src/BNP/
mkdir -p logs cluster/results

# Reproducible single-threaded timing (mirrors BBC's thread-pinning intent)
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

# Activate the BNP venv (created once; see cluster/README_BNP_CLUSTER.md)
source "${BNP_VENV:-$HOME/bnp-venv}/bin/activate"

# Optional J>MAX_JOBS extension run:  MINJ=26 MAXJ=45 sbatch cluster/run_bnp.sbatch
# (distinct CSV suffix -> safe to run concurrently with the main job; the OS
#  timeout guard + early-stop bound the cost; expect mostly time_limit rows.)
SUFFIX="${MAXJ:+_J${MINJ:-0}-${MAXJ}}"
python bnp_benchmark_runner.py \
    --sets all \
    ${MAXJ:+--max-jobs "$MAXJ" --max-nv 1e18} \
    ${MINJ:+--min-jobs "$MINJ"} \
    --task-id "${SLURM_ARRAY_TASK_ID}" --num-tasks "${NUM_TASKS}" \
    --output "cluster/results/bnp_task${SLURM_ARRAY_TASK_ID}${SUFFIX}.csv"
