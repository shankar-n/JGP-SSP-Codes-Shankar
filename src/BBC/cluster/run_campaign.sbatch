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
#SBATCH --array=0-10                # 11 configs (primary). Secondary: use 0-9 (drop SSPMF, the last index)
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
# (a) Python with the CPLEX Python API + numpy on PATH. Typical options:
#       source "$HOME/ssp-env/bin/activate"          # a venv you created, OR
#       module load python/3.x cplex/22.x            # if the cluster provides modules
source "$HOME/ssp-env/bin/activate"
# (b) Pin CPLEX to the cores SLURM gave us (reproducible, comparable solve times):
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export CPLEX_THREADS="$SLURM_CPUS_PER_TASK"          # all 4 solvers honor this (thread pin built in); 0/unset = CPLEX default

# ----------------------------------------------------------------------------
# Map array index -> config label (order matches benchmark_config.BBC_CONFIGS)
# ----------------------------------------------------------------------------
CONFIGS=(BBC-LP BBC-LP+F BBC-LP+T BBC-LP+FT BBC-K BBC-K+F BBC-K+T BBC-K+FT LSS CATZ-F4 SSPMF)
CFG="${CONFIGS[$SLURM_ARRAY_TASK_ID]}"

echo "[$(date '+%F %T')] host=$(hostname) array_task=$SLURM_ARRAY_TASK_ID config=$CFG"
python3 -c "import cplex, numpy; print('cplex', cplex.__version__, '| numpy', numpy.__version__)"

# ----------------------------------------------------------------------------
# Run: this config, easiest-first, early-stop after 8 consecutive non-optimal
# results.  Its own output CSV.  Set selection: SETS env var, default primary.
#   primary   : sbatch cluster/run_campaign.sbatch
#   secondary : SETS=secondary sbatch --array=0-9 cluster/run_campaign.sbatch
#               (0-9 drops SSPMF, the last index; too slow at J=15)
# Same per-config CSV for both -- the runner resumes/skips by (instance,config).
# ----------------------------------------------------------------------------
SETS="${SETS:-primary}"
echo "[$(date '+%F %T')] sets=$SETS"
python3 benchmark_runner.py \
    --sets "$SETS" \
    --configs "$CFG" \
    --output "results/raw_${CFG}_${SETS}.csv" \
    --max-consecutive-timeouts 8

echo "[$(date '+%F %T')] DONE config=$CFG"
