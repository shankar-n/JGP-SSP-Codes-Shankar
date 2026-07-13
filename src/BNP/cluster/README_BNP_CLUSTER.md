# BNP campaign on the cluster — runbook

Standalone PCF′/PTF branch-and-price campaign. **Separate from the BBC campaign**
(does not touch `src/BBC/` or its `raw_results.csv`). **No CPLEX needed** — SCIP
ships inside `pyscipopt`. Results are compared to BBC offline on the shared metric
`obj_ktns` (empty-start switches), never by mixing harnesses.

## 1. Environment — the shared `ssp_env` conda env (no license needed for BNP)
ONE env serves both campaigns. Create it once following
`src/BBC/cluster/SLURM_RUNBOOK.md` Step 2 (Miniforge/conda, per the cluster wiki
https://hpc.isima.fr/doku.php?id=python); it includes `pyscipopt` (SCIP ships
inside the wheel). To use it in any shell:
```bash
source ~/miniforge3/etc/profile.d/conda.sh
conda activate ssp_env
python -c "import pyscipopt; print('SCIP', pyscipopt.__version__)"
```
The sbatch activates it the same way — nothing to configure.

## 2. Smoke test (login node, tiny)
```bash
cd src/BNP
python bnp_benchmark_runner.py --only-sets Catanzaro --configs PCFp --limit 3
```

## 3. Submit the array
```bash
cd src/BNP && mkdir -p logs     # logs/ must exist before submit (SLURM opens it at job start)
sbatch cluster/run_bnp.sbatch   # array 0-15; each task = a disjoint instance shard
```
Each task is independently **resumable** (re-`sbatch` to continue after a
walltime cut — completed `(instance,config)` rows are skipped) and writes its own
`cluster/results/bnp_task<id>.csv`. Tune in `bnp_benchmark_config.py`: time limits
per set, `MAX_JOBS` (size cap; raise as the pricer matures), `MAX_CONSECUTIVE_TIMEOUTS`.

## 4. Merge + analyse
```bash
cd src/BNP/cluster && ./merge_results.sh        # -> src/BNP/bnp_results.csv
```
Compare PCF′ vs PTF (and, offline, vs BBC) on: `obj_ktns` (optimum / cross-check —
every exact solver must agree), `status`/`time_s` (solve-rate; note SCIP-vs-CPLEX
when comparing time to BBC), `nodes`, and `root_lp_bound` (PCF′ = |U|−b; PTF ≥).

## Knobs
- `--sets {primary,secondary,all}`, `--only-sets`, `--configs {PCFp,PTF}`
- `--task-id i --num-tasks N` (array sharding), `--limit N`, `--dry-run`
- `--max-consecutive-timeouts K` (0 disables early-stop)

## Scope caveats (honest)
- The prototype exact B&P (`a_{t,p}` integer branching + MILP pricing) only closes
  the **small** instances; large ones (esp. Otiai, J≥200) are skipped by `MAX_JOBS`
  or time out — recorded as such, which is itself a result.
- `time_s` vs the BBC (CPLEX) numbers is **solver + formulation**, not pure
  formulation; `obj_ktns` and `root_lp_bound` compare cleanly.
