# Exact and Structural Methods for the Job Sequencing and Tool Switching Problem

Code and computational campaign for a research project on the **Job Sequencing
and Tool Switching Problem (SSP)** and the **Job Grouping Problem (JGP)**,
carried out at LIMOS, Université Clermont Auvergne / ISIMA.

Author: Shankar Narayanan.
Advisors: Dr. Rafael Colares, Prof. Annegret Wagler. Supervisor: Dr. Renaud Chicoisne.

## The problem

A single flexible machine holds at most `b` tools in its magazine; job `j`
requires the tool set `T_j`. Processing the jobs in a different order changes
the number of tool switches, and for a *fixed* order the optimal loading is the
classical Keep-Tool-Needed-Soonest (KTNS) rule of Tang & Denardo (1988). The
joint problem — order the jobs and load the magazine to minimise switches — is
NP-hard. The project studies (i) worst-case guarantees for the standard
group-then-sequence heuristic and (ii) exact methods built on the
configuration view of the problem.

## Repository layout

| Path | Contents |
|---|---|
| `src/SSP/` | Instance I/O, KTNS, switch-cost conventions, JGP via the asymmetric-representatives MILP (PySCIPOpt), constructive heuristics, instance generators, solution validators |
| `src/BBC/` | Branch-and-Benders-cut solver (CPLEX generic callback); faithful reimplementations of three literature baselines — Laporte et al. (2004), Catanzaro et al. (2015, F4), da Silva et al. (2024, multicommodity flow); campaign configuration and resumable runner; SLURM scripts; per-instance results (`raw_results.csv`, `results/`) |
| `src/BNP/` | Position-indexed branch-and-price prototypes (PCF′ and PTF, PySCIPOpt), instance loaders for all benchmark families, campaign runner and results (`bnp_results.csv`) |
| `data/` | Standard SSP benchmark families (Catanzaro, Crama, Laporte, Otiai) |

## The campaign

1,421 standard benchmark instances; eight Benders configurations (cut families
switched on/off in every combination) against the three compact baselines and
the two branch-and-price prototypes. Every solver's returned sequence is
re-evaluated with the same KTNS routine in a single cost convention, so all
methods are scored on one canonical metric; 806 instances are solved by at
least one method with zero cross-method disagreements. Environment: CPLEX
22.1.1 (4 dedicated threads per run), PySCIPOpt (single-threaded), SLURM
cluster, 3600 s / 600 s time limits.

## Requirements

- Python ≥ 3.10, `numpy`
- IBM CPLEX 22.1.x with its Python API (install `cplex` from a local CPLEX
  Studio; the CLI alone does not provide the API)
- `pyscipopt` (JGP MILP and branch-and-price)
- Optional: `docplex`, `gurobipy` (subproblem fallbacks), Concorde (TSP oracle)

## Quick start

```bash
# cross-solver correctness check (all exact solvers vs brute force, small instances)
python src/BBC/test_solver.py

# benchmark campaign (resumable; grid defined in src/BBC/benchmark_config.py)
python src/BBC/benchmark_runner.py

# on a SLURM cluster
sbatch src/BBC/cluster/run_campaign.sbatch            # primary sets
SETS=secondary sbatch --array=0-9 src/BBC/cluster/run_campaign.sbatch
```

## Instance format

```
J  T  C
<T × J binary matrix>    # A[t,j] = 1  iff  job j requires tool t
```

Loaders: `src/SSP/utils.py` (`load_ssp_instance`) and
`src/BNP/instance_loader.py` (token-based, all families).

## License

MIT — see `LICENSE`.
