# Branch-and-Benders-Cut (BBC) for the Job Sequencing and Tool Switching Problem

## Overview

This directory contains three exact solvers for the **Job Sequencing and Tool Switching Problem (SSP)**:

1. **BBC** – Branch-and-Benders-Cut (CPLEX only — see note below)
2. **LSS** – Laporte, Salazar-González & Semet (2004) TSP-based ILP
3. **SSPMF** – da Silva, Chaves & Yanasse (2024) Multicommodity Flow ILP

---

## ⚠️ Deviations from the papers / original plan

### BBC: CPLEX only
The Gurobi and SCIP backends have been **archived** to `_archived/`.  
Only `branch_and_benders_cut_cplex.py` is active.

**Root-cause fix (depot node):** The original BBC master problem modelled a
Hamiltonian *cycle* on `n_jobs` nodes (no depot).  This caused the DSP to
compute cycle cost instead of path cost, leading to incorrect Benders cuts and
eventual infeasibility.  A **depot node** (index `n_jobs`, `T_depot=∅`) was
added to `build_master_problem`, converting the problem to a Hamiltonian *path*
as described in `idea.md` (the plan includes `J ∪ {0}` in all degree
constraints).

### Result post-processing in `main-notebook.py` cell 6b
LSS (Laporte 2004) and SSPMF (da Silva 2024) are kept **exactly as per their
papers**.  Both paper formulations count the initial magazine loading from the
empty depot as part of the objective.  The GTSP reference solver (cell 6) does
**not** count this (it uses a DUMMY node with zero-cost transitions).

To make the comparison table consistent, cell 6b **post-processes** each
result by subtracting `|T_{seq[0]}|` (the initial load at the first job):

```python
adjusted_obj = reported_obj - len(T_j[seq[0]])
```

This post-processing is applied only for display in the comparison table; the
solver code itself is untouched.

A `benchmark.py` runner compares all three on standard instances.

---

## Files

| File | Description |
|------|-------------|
| `branch_and_benders_cut.py` | Auto-detecting dispatcher (CPLEX → Gurobi → SCIP) |
| `branch_and_benders_cut_cplex.py` | BBC — IBM CPLEX backend |
| `branch_and_benders_cut_gurobi.py` | BBC — Gurobi backend |
| `branch_and_benders_cut_scip.py` | BBC — SCIP/PySCIPOPT backend |
| `lss_formulation.py` | LSS formulation (Laporte 2004) |
| `sspmf_formulation.py` | SSPMF formulation (da Silva 2024) |
| `benchmark.py` | Benchmark runner (BBC vs LSS vs SSPMF) |
| `test_solver.py` | Unit/integration tests for all backends |

---

## Requirements

```
Python 3.8+
numpy

# At least one MIP solver:
gurobipy      # Gurobi (requires licence)
cplex         # IBM CPLEX (requires installation)
pyscipopt     # SCIP (open-source)

# Optional (for CPLEX backend DSP):
docplex       # IBM DOcplex (uses CPLEX under the hood)
```

---

## Quick Start

### Dispatcher (auto-selects best solver)

```python
from branch_and_benders_cut import solve_ssp_branch_and_benders

status, obj_val, sequence = solve_ssp_branch_and_benders(
    "path/to/instance.txt",
    time_limit=300,
    verbose=True
)
```

### Specific backend

```python
from branch_and_benders_cut_gurobi import BranchAndBendersCutSSP
from utils import load_ssp_instance

n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance("instance.txt")

solver = BranchAndBendersCutSSP(
    n_jobs, n_tools, capacity, tool_req,
    worker_lp_reuse=True,        # reuse DSP model across callback calls
    use_fractional_cuts=True,    # add Benders cuts at LP relaxation nodes
    parallel=True                # multi-threaded B&B
)
solver.build_master_problem(verbose=True)
status, obj_val, sequence = solver.solve(time_limit=300, verbose=True)
```

### LSS and SSPMF

```python
from lss_formulation  import solve_lss
from sspmf_formulation import solve_sspmf

status, obj, seq = solve_lss("instance.txt",   time_limit=300)
status, obj, seq = solve_sspmf("instance.txt", time_limit=300)
```

### Command-line benchmark

```bash
# Run all formulations on all instances with 5-minute time limit:
python benchmark.py --instances "../Instances/**/*.txt" --time-limit 300 --output results.csv

# Run only BBC and LSS:
python benchmark.py --formulations bbc lss --time-limit 60

# Generate random instances and run a quick test:
python benchmark.py --generate --time-limit 30
```

---

## Algorithm: Branch-and-Benders-Cut

### Master Problem

$$\min\; \theta$$

Subject to:
- **Degree constraints**: each job has exactly one predecessor and one successor (TSP skeleton)
- **Initial lower bound**: $\theta \ge \sum_{i,j} w_{ij} x_{ij}$ where $w_{ij} = \max(0,\,|T_i \cup T_j| - c)$
- **Subtour elimination constraints (SECs)**: added lazily via callback
- **Benders optimality cuts**: added lazily via callback

### Dual Subproblem (DSP)

For a fixed Hamiltonian sequence $\bar{x}$, solve:

$$\max\;\; \sum_{i,j,t}(\bar{x}_{ij}-1)\lambda_{ijt} \;-\; \sum_j c\,\mu_j \;+\; \sum_{j,\,t \in T_j} \nu_{jt}$$

subject to dual feasibility constraints.  Variables $\nu_{jt}$, $\eta_{jt}$ are **free** (not bounded below).

### Benders Cut

If DSP objective $> \theta$, add:

$$\theta \;\ge\; \sum_{i,j,t}(x_{ij}-1)\bar{\lambda}_{ijt} \;-\; \sum_j c\,\bar{\mu}_j \;+\; \sum_{j,\,t \in T_j} \bar{\nu}_{jt}$$

### Convergence

The algorithm terminates when Gurobi/CPLEX/SCIP finds an integer solution where $\theta$ equals the actual KTNS cost, or the time/iteration limit is reached.

---

## Optional Performance Features

All three BBC backends support three optional boolean parameters (default `False`):

### `worker_lp_reuse`

Build the DSP model **once** per thread and update only the objective coefficients before each re-solve, instead of rebuilding the model from scratch.  Based on the LP-reuse pattern from IBM's `bendersatsp2.py` example.

- **Gurobi**: stores a shared `gp.Model`; updates `lam[i,j,t].Obj` per call.
- **CPLEX**: stores a `cplex.Cplex` DSP model; updates `dsp.objective.set_linear(...)`.
- **SCIP**: uses a Gurobi reuse model if available; otherwise falls back to fresh SCIP LP.

### `use_fractional_cuts`

Fire the DSP callback at **LP relaxation nodes** (not only integer solutions) to add Benders *user cuts* that tighten the LP bound before branching.  Can substantially reduce the B&B tree size.

- **Gurobi**: fires at `GRB.Callback.MIPNODE`; injects via `model.cbCut()`.
- **CPLEX**: fires at `Context.id.relaxation`; injects via `context.add_user_cut()`.
- **SCIP**: extends `consenfolp` to solve DSP at fractional nodes; injects via `model.addCons()`.

### `parallel`

Allow the MIP solver to use **multiple threads** for B&B.

- **Gurobi**: sets `Params.Threads = 0` (auto); each thread uses `threading.local()` DSP storage.
- **CPLEX**: registers `Context.id.thread_up / thread_down`; per-thread DSP dict in `_thread_dsps`.
- **SCIP**: sets `lp/threads` to allow parallel LP solves (note: SCIP Conshdlr has limited thread-safety guarantees).

---

## LSS Formulation (Laporte 2004)

**Variables**: $x_{ij} \in \{0,1\}$ (arc), $y_{it} \in \{0,1\}$ (tool loaded), $z_{it} \in \{0,1\}$ (tool switch)

**Objective**: $\min \sum_{i \in J} \sum_{t \in T_i} z_{it}$  (optionally lifted)

**Key constraints**:
- (11–12) TSP degree constraints + depot
- (13) Subtour elimination — lazy via callback
- (14) Magazine capacity: $\sum_t y_{it} \le c$
- (15) Magazine persistence: $y_{it} \ge x_{ji} + y_{jt} - 1$
- (16) Required tools: $y_{it} = 1$ for $t \in T_i$
- (17) Switch definition: $z_{it} \ge 1 - y_{jt} - (1 - x_{ji})$

**Valid inequalities** (optional):
- (23) Pairwise lower bound on arc switches
- (25) Unnecessary switches $= 0$

---

## SSPMF Formulation (da Silva 2024)

**Graph**: $G(V, A)$ where $V = \{0, \ldots, N, N+1, N+2\}$ with origin, sink, and auxiliary nodes.

**Variables**: $x_{ik} \in \{0,1\}$ (job $i$ at position $k$), $y_{ikt} \ge 0$ (commodity flow), $z_{kt} \in \{0,1\}$ (switch indicator)

**Objective**: $\min \sum_{k,t} z_{kt}$

**Key features**:
- Pure MIP — no lazy constraints needed
- LP relaxation lower bound: $LB = M - C$ (proven tight)
- Symmetry-breaking: job $p$ with most tools fixed to first $\lceil N/2 \rceil$ positions (Eq. 20)
- Constraint (21): flow to sink = 0 for early tool occurrences

---

## Benchmark Usage

```bash
# Full benchmark with default settings:
python benchmark.py

# Custom instance set:
python benchmark.py --instances "Instances/Yanasse/**/*.txt" --time-limit 600

# Generate random instances if none found:
python benchmark.py --generate --time-limit 60 --output test_results.csv
```

The benchmark outputs a formatted table like:

```
Instance                       Form      N    M   C      Obj   Time(s)  Opt   Gap% Status
──────────────────────────────────────────────────────────────────────────────────────────
shankar-example.txt            BBC       8   12   4     14.0      1.23  Yes   0.0% OPTIMAL
shankar-example.txt            LSS       8   12   4     14.0      2.87  Yes   0.0% OPTIMAL
shankar-example.txt            SSPMF     8   12   4     14.0      4.12  Yes   0.0% OPTIMAL
```

CSV output includes: `instance, n_jobs, n_tools, capacity, formulation, status, obj_val, time_sec, optimal, gap_pct, notes`

---

## Instance Format

Instances follow the standard SSP format:

```
<n_jobs> <n_tools> <capacity>
<tool_matrix row 0>    # binary: 1 if job 0 requires tool t
<tool_matrix row 1>
...
<tool_matrix row n-1>
```

Example (`shankar-example.txt`):
```
5 8 3
1 0 1 0 1 0 0 0
0 1 0 1 0 1 0 0
1 1 0 0 0 0 1 0
0 0 1 0 0 1 0 1
1 0 0 1 1 0 0 0
```

---

## References

- Laporte, G., Salazar-González, J.J., & Semet, F. (2004). *Exact algorithms for the job sequencing and tool switching problem.* IIE Transactions, 36(1), 37–45.
- da Silva, T.F.S., Chaves, A.A., & Yanasse, H.H. (2024). *A multicommodity flow formulation for the job sequencing and tool switching problem.*
- IBM CPLEX Optimization Studio — `bendersatsp.py`, `bendersatsp2.py` examples (insights on worker LP reuse, fractional cuts, thread safety).
