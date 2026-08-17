#!/bin/bash
# Run the whole verification on the cluster WITHOUT tying up your terminal.
# Submit once from the repo root; it runs on a compute node and writes its
# output to verify_<jobid>.out.  Your internet can drop -- the job keeps going.
#
#   cd .../JGP-SSP-Codes-Shankar
#   sbatch verification/verify.sbatch
#   # ... disconnect freely; come back later ...
#   squeue -u $USER            # still running?  (empty = finished)
#   cat verify_*.out           # read the PASS/FAIL results
#
#SBATCH --job-name=ssp-verify
#SBATCH --partition=court            # short queue (48h cap); verification is quick
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=4096
#SBATCH --output=verify_%j.out       # results land here (%j = job id)
#SBATCH --error=verify_%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-.}"          # = the repo root (where you ran sbatch)

source ~/miniforge3/etc/profile.d/conda.sh
conda activate ssp_env
export CPLEX_THREADS="$SLURM_CPUS_PER_TASK"

echo "[$(date '+%F %T')] host=$(hostname)  running verify_everything.py"
python verification/verify_everything.py
echo "[$(date '+%F %T')] verification finished, exit code $?"
