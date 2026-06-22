# BBC Campaign — SLURM Runbook (ISIMA / LIMOS cluster)

Spoon-fed, in order. Run commands **on the cluster** unless noted. Login node is
**frontalhpc2025** (frontalhpc2020 is being retired). Cluster wiki: https://hpc.isima.fr
(partitions: `normal`=7 days [default], `court`=48 h, `long`=90 days).

**What you'll end up with:** 10 array tasks (one per solver config), each solving all
PRIMARY instances easiest-first with early-stop, writing `results/raw_<CFG>.csv`; then a
merged `raw_results.csv` for analysis.

---

## Step 0 — Get the code + data onto the cluster
```bash
# from your machine (option A: git, if reachable from the cluster)
ssh <user>@frontalhpc2025
git clone <your-repo-url> JGP-SSP-Codes-Shankar
# option B: rsync from your machine instead
rsync -avz --exclude '.git' /path/to/JGP-SSP-Codes-Shankar <user>@frontalhpc2025:~/
```
Check data arrived: `ls ~/JGP-SSP-Codes-Shankar/data/From_Felipe/data/Catanzaro/Tabela1C | head`

## Step 1 — Probe the cluster (PASTE ME THE OUTPUT)
```bash
cd ~/JGP-SSP-Codes-Shankar/src/BBC
bash cluster/probe.sh
```
This reports partitions/nodes, your account, and — crucially — whether the CPLEX
**Python API** (`import cplex`) is available and which Python. Paste the output and I'll
finalize the two ENV lines + partition/time in `cluster/run_campaign.sbatch` so it runs first try.

## Step 2 — Python environment (numpy + CPLEX Python API)  [CONFIRMED NEEDED]
Probe result: `cplex` CLI present, but `import cplex` and `import numpy` both FAIL. So
make ONE venv in your shared `$HOME` and install both (the CPLEX API comes from the local
CPLEX Studio install, NOT from PyPI):
```bash
# 1. locate the CPLEX Studio root from the CLI that IS on PATH
which cplex                       # e.g. /opt/ibm/ILOG/CPLEX_Studio2211/cplex/bin/x86-64_linux/cplex
STUDIO=$(dirname "$(dirname "$(dirname "$(dirname "$(readlink -f "$(which cplex)")")")")")
echo "$STUDIO"                    # confirm -> /opt/ibm/ILOG/CPLEX_StudioXXXX
ls "$STUDIO/cplex/python"         # supported python versions, e.g.  3.8  3.9  3.10

# 2. use a python whose version is IN that list (system python3, or `module load python/3.x`)
python3 --version

# 3. create venv + install numpy + the CPLEX Python API from the local install
python3 -m venv "$HOME/ssp-env"
source "$HOME/ssp-env/bin/activate"
pip install --upgrade pip numpy
pip install "$STUDIO/cplex/python/<PYVER>/x86-64_linux"      # <PYVER> = a dir from step 1
python -c "import cplex, numpy; print('cplex', cplex.__version__, '| numpy', numpy.__version__)"
```
> **Does the venv exist on the compute nodes too?** Yes — as long as `$HOME` is a shared
> filesystem, which it is on essentially every SLURM cluster (ISIMA included). The venv
> lives in `$HOME`; the sbatch runs `source "$HOME/ssp-env/bin/activate"`, so each node
> mounts the same path and sees it. You do NOT install per-node. Two caveats: (1) if you
> built the venv from a `module load python/3.x`, put that SAME `module load` in the sbatch
> *before* the `source ... activate` line (so the base python is on the node PATH);
> (2) if CPLEX itself is provided by a module rather than a fixed PATH, add that module
> load too. Verify once on a node:
> `srun --partition=court --pty bash` → `source ~/ssp-env/bin/activate && python -c "import cplex, numpy"`.

## Step 3 — Archive any pre-fix results (IMPORTANT)
The runner RESUMES from existing rows. Old results predate the Benders depot-dual fix
AND the LSS fix, so they must not be reused:
```bash
cd ~/JGP-SSP-Codes-Shankar/src/BBC
mkdir -p _archived_results
mv raw_results.csv _archived_results/raw_results_prefix_$(date +%F).csv 2>/dev/null || true
rm -f results/raw_*.csv 2>/dev/null || true
```

## Step 4 — CPLEX thread count (already built in)
All four solvers (BBC, LSS, SSPMF, Catanzaro-F4) already read the `CPLEX_THREADS` env
var and call `cpx.parameters.threads.set(N)` when it is > 0. The sbatch exports
`CPLEX_THREADS=$SLURM_CPUS_PER_TASK`, so each task uses exactly its allocated cores
(reproducible, comparable timings). Nothing to edit here. For fully deterministic
single-thread runs set `--cpus-per-task=1`; if `CPLEX_THREADS` is unset/0, CPLEX uses
its default and SLURM core-binding still caps it at `--cpus-per-task`.

## Step 5 — Sanity check BEFORE the big run
```bash
source ~/ssp-env/bin/activate          # or your module loads
cd ~/JGP-SSP-Codes-Shankar/src/BBC
python3 test_solver.py                                   # cross-solver agreement (confirms LSS fix)
python3 benchmark_runner.py --sets primary --configs BBC-K --dry-run    # easiest-first order (A0-0 first)
python3 benchmark_runner.py --sets primary --configs BBC-K --limit 3 --output /tmp/pilot.csv
head /tmp/pilot.csv
```
Expect: agreement in `test_solver`; dry-run lists the small instances first; pilot rows say `optimal`.

## Step 6 — Submit the campaign (job array, 1 task/config)
```bash
cd ~/JGP-SSP-Codes-Shankar/src/BBC
sbatch cluster/run_campaign.sbatch          # note the job ID it prints
```

## Step 7 — Monitor
```bash
squeue -u $USER                                              # queued/running tasks
sacct -j <jobid> --format=JobID,JobName,State,Elapsed,MaxRSS,ExitCode
tail -f logs/bbc_<jobid>_4.out                              # live log for task 4 (= BBC-K)
```
States: PENDING → RUNNING → COMPLETED (or TIMEOUT/FAILED → just resubmit, it resumes).

## Step 8 — Merge + sanity check
```bash
bash cluster/merge_results.sh                               # results/raw_*.csv -> raw_results.csv
python3 -c "import pandas as pd; d=pd.read_csv('raw_results.csv'); print(d.groupby(['config','status']).size())"
```
### 8b — Resume anything killed/incomplete (rows already done are skipped)
```bash
sbatch --array=4,9 cluster/run_campaign.sbatch             # e.g. re-run only BBC-K and SSPMF
```

## Step 9 — Secondary sets (optional, after primary)
Copy the sbatch to `run_campaign_secondary.sbatch`, change `--sets primary` → `--sets secondary`
and `--array=0-9` → `--array=0-8` (secondary drops SSPMF, the last index), then `sbatch` it.

## Troubleshooting
- **`import cplex` works on login but fails in the job**: the env isn't activated inside the
  job — fix the ENV lines in the sbatch (Step 1 output tells us the right ones).
- **Task killed, MaxRSS near limit**: raise `--mem-per-cpu` (e.g. 8192) — the J=40 D-instances are heavy.
- **Task stuck PENDING (reason Priority/Resources)**: fair-share — asking for less time/CPU raises priority; `sprio` shows it. Consider `--partition=court` for the quick configs.
- **Wrong/old login node**: use `frontalhpc2025`; see https://hpc.isima.fr/doku.php?id=acces.

---
**Next:** paste Step 1's probe output and I'll lock the two ENV lines + partition/time so this runs on the first submit.
