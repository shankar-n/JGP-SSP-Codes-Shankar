#!/bin/bash
#SBATCH --job-name=rl-cuts
#SBATCH --array=0-9
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=logs/rl_%A_%a.out
#
# RL-for-cuts training study (REINFORCE cut-selection, Tang, Agrawal & Faenza 2020).
# Pure Python (numpy + scipy) -- NO CPLEX/SCIP needed.
#
# WHAT THIS SWEEPS.  The prototype is a 4-parameter linear policy on a synthetic
# knapsack cover-cut testbed.  We verified it is SEED-STABLE (every training seed learns
# the same greedy ranking -> identical held-out result), so replicating seeds is
# redundant.  The axis that actually varies the result is INSTANCE DIFFICULTY n, so each
# array task trains+evaluates at one difficulty n = 8,10,...,26 and writes a shard.
# Afterwards aggregate the learned-vs-random lift across difficulties:
#
#     python rl_cut_select.py --summary "rl_results/rl_n*.csv"
#
# (To do a seed-replication run instead, call: python rl_cut_select.py --seeds 0-19 ...)
#
# Submit:  cd src/BBC && mkdir -p logs rl_results && sbatch cluster/run_rl.sbatch
# Heavier training per point:  EPISODES=5000 sbatch cluster/run_rl.sbatch
#
# NB: this is the synthetic-testbed prototype.  Wiring the learned policy into the live
#     CPLEX BBC cut loop (score_cut / ssp_cut_features) is separate future work, gated on
#     the BBC campaign exposing bound-loose instances (report Section 4.5) -- THAT is the
#     training that would actually need the cluster; this toy does not.
set -euo pipefail

cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"      # -> src/BBC/
mkdir -p logs rl_results

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

# Shared conda env (same one the BBC/BNP campaigns use; see src/BBC/cluster/SLURM_RUNBOOK.md).
source ~/miniforge3/etc/profile.d/conda.sh
conda activate ssp_env

# scipy is the only extra dependency (numpy is already in ssp_env); install once if absent.
python -c "import scipy" 2>/dev/null || pip install --quiet scipy

N=$(( 8 + 2 * SLURM_ARRAY_TASK_ID ))              # difficulty sweep: n = 8,10,...,26
EPISODES="${EPISODES:-2000}"
python rl_cut_select.py \
    --seed 0 \
    --n "$N" \
    --episodes "$EPISODES" \
    --out "rl_results/rl_n${N}.csv"
