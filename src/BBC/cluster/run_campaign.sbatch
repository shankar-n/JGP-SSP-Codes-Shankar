#!/bin/bash
# =============================================================================
# BBC benchmark campaign — SLURM job array for the ISIMA / LIMOS cluster
# Submit FROM the src/BBC directory on the frontalhpc2025 login node:
#     cd .../JGP-SSP-Codes-Shankar/src/BBC
#     sbatch cluster/run_campaign.sbatch
#
# Design: ONE array task per solver config.  Each task runs benchmark_runner.py
# for a single config over all PRIMARY instances (easiest-first, with per-config
# early-stop) and writes its OWN csv in results/ — so there are no concurrent
# writers to one file.  Merge afterwards (see cluster/merge_results.sh).
#
# Partitions (hpc.isima.fr/config): normal=7d (default), court=48h, long=90d.
# Each task is resumable: if it is killed (time limit, maintenance), just
# resubmit — benchmark_runner skips rows already in its results/raw_<CFG>.csv.
# =============================================================================

#SBATCH --job-name=bbc-ssp
#SBATCH --array=0-119               # 12 configs x 10 shards (NSHARDS below). Change both together: 0..NCONFIGS*NSHARDS-1
#SBATCH --partition=normal          # 7-day limit; switch to 'long' for unattended runs
#SBATCH --time=7-00:00:00           # wall-clock cap; killed tasks resume on resubmit
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4           # SLURM binds the task to 4 cores; CPLEX sees only these
#SBATCH --mem-per-cpu=4096          # 4 GB/core = 16 GB/task (raise for the J=40 D-instances)
#SBATCH --output=logs/bbc_%A_%a.out
#SBATCH --error=logs/bbc_%A_%a.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-.}"         # = src/BBC (where you ran sbatch)
mkdir -p logs results

# ----------------------------------------------------------------------------
# ENVIRONMENT  ——  EDIT THESE TWO LINES to match your cluster setup.
# Confirm what you need first with cluster/probe.sh (see SLURM_RUNBOOK.md, Step 1).
# ----------------------------------------------------------------------------
# (a) Python env: the shared conda env `ssp_env` (Miniforge, per the cluster wiki
#     https://hpc.isima.fr/doku.php?id=python — created in SLURM_RUNBOOK.md Step 2;
#     same env serves the BNP campaign).
source ~/miniforge3/etc/profile.d/conda.sh
conda activate ssp_env
# (b) Pin CPLEX to the cores SLURM gave us (reproducible, comparable solve times):
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export CPLEX_THREADS="$SLURM_CPUS_PER_TASK"          # all 4 solvers honor this (thread pin built in); 0/unset = CPLEX default

# ----------------------------------------------------------------------------
# 2-D job grid:  15 configs  x  NSHARDS instance-shards  =  15*NSHARDS tasks.
# Sharding splits each config's ~1400 instances across NSHARDS parallel jobs, so
# the 1-hour limit still finishes in ~a week.  NSHARDS = how many jobs your
# cluster runs at once (more = faster, up to your capacity).  If you change it,
# also change the header:  --array=0..15*NSHARDS-1.  (10 -> --array=0-149.)
# ----------------------------------------------------------------------------
NSHARDS=10
# 12 configs (only the triplet-added crosses pruned): 5 ablation + 4 acceleration
# + 3 baselines.  Order must match benchmark_config.BBC_CONFIGS.
CONFIGS=(BBC-LP BBC-LP+F BBC-K BBC-K+F BBC-LP+T \
         BBC-LP+F+C BBC-LP+F+H BBC-LP+F+P BBC-LP+ACC \
         LSS SSPMF CATZ-F4)
CFG_IDX=$(( SLURM_ARRAY_TASK_ID / NSHARDS ))
SHARD=$(( SLURM_ARRAY_TASK_ID % NSHARDS ))
CFG="${CONFIGS[$CFG_IDX]}"

echo "[$(date '+%F %T')] host=$(hostname) task=$SLURM_ARRAY_TASK_ID config=$CFG shard=$SHARD/$NSHARDS"
python3 -c "import cplex, numpy; print('cplex', cplex.__version__, '| numpy', numpy.__version__)"

# ----------------------------------------------------------------------------
# Run this config over ITS SHARD of the instances, all families, NO early-stop,
# to the uniform 1-hour time limit.  Own CSV per (config, shard); the runner
# appends each result live -- `tail -f results/raw_${CFG}_s${SHARD}.csv` -- and
# resumes/skips by (instance, config) if requeued.  merge_results.sh globs
# results/raw_*.csv, so the shards recombine automatically afterwards.
# ----------------------------------------------------------------------------
echo "[$(date '+%F %T')] running ALL families, no early-stop, shard $SHARD/$NSHARDS"
python3 benchmark_runner.py \
    --sets all \
    --configs "$CFG" \
    --shard "$SHARD/$NSHARDS" \
    --output "results/raw_${CFG}_s${SHARD}.csv" \
    --max-consecutive-timeouts 0

echo "[$(date '+%F %T')] DONE config=$CFG shard=$SHARD"
