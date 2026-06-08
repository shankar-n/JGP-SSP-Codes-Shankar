"""
Branch-and-Benders-Cut Algorithm for the Job Sequencing and Tool Switching Problem (SSP).
Dispatcher / façade — auto-selects the best available solver backend.

Detection order
---------------
1. CPLEX   (branch_and_benders_cut_cplex.py  → BranchAndBendersCutSSP_CPLEX)
2. Gurobi  (branch_and_benders_cut_gurobi.py → BranchAndBendersCutSSP)
3. SCIP    (branch_and_benders_cut_scip.py   → BranchAndBendersCutSSP_SCIP)

All three backends expose an identical public interface:
    solver = BranchAndBendersCutSSP(n_jobs, n_tools, capacity, tool_req)
    solver.build_master_problem(verbose=False)
    status, obj_val, sequence = solver.solve(time_limit=300, verbose=True)

The alias ``BranchAndBendersCutSSP`` (and the convenience function
``solve_ssp_branch_and_benders``) transparently delegate to whichever
backend was selected at import time.

Algorithm overview
------------------
Master Problem
    min  θ
    s.t. standard degree constraints (TSP skeleton)
         initial lower bound:  θ ≥ Σ w_ij x_ij
             where w_ij = max(0, |T_i ∪ T_j| − capacity)
         dynamically added subtour elimination constraints (SECs)
         dynamically added Benders optimality cuts

Dual Subproblem (DSP)  [one per job t in the sequence]
    max  Σ_{i,j} (x̄_ij − 1) λ_ijt  −  Σ_j c μ_jt  +  Σ_j ν_jt
    s.t. λ_ijt  ≥  0
         μ_jt   ≥  0
         ν_jt   FREE   (η_jt FREE)
         … see individual backend files for full dual formulation

Benders Optimality Cut (added as lazy constraint)
    θ  ≥  Σ_{i,j} (x_ij − 1) λ̄_ijt  −  Σ_j c μ̄_jt  +  Σ_j ν̄_jt

Subtour Elimination Constraint (SEC)
    Σ_{i,j ∈ S} x_ij  ≤  |S| − 1    for every subtour S

Notes on the CPLEX reference examples (bendersatsp.py / bendersatsp2.py)
-------------------------------------------------------------------------
Key insights extracted from the IBM examples that informed our design:

1. Worker LP reuse (performance)
   The ATSP examples build the dual LP **once** and update only the
   objective coefficients with ``cpx.objective.set_linear(zip(vars, coefs))``
   before each solve.  Our current backends rebuild the DSP model per
   callback call — a safe but slower approach.  A future optimisation would
   adopt the LP-reuse pattern (especially valuable for large instances).

2. Fractional cut separation (``Context.id.relaxation``)
   bendersatsp2.py also fires the callback on fractional LP relaxation
   solutions (``context.id.relaxation``) to add *user cuts* that tighten the
   LP bound before branching.  Our CPLEX backend currently only fires on
   integer candidates (``context.id.candidate``).  Adding relaxation-based
   user cuts can substantially reduce the B&B tree size.

3. Thread-safety (``context.id.thread_up / thread_down``)
   bendersatsp2.py allocates one WorkerLP per thread and stores them in a
   ``thread_id → WorkerLP`` dict, cleaned up on thread_down.  Our current
   CPLEX backend is effectively single-threaded for the subproblem.

4. Cut derivation via unbounded ray
   The ATSP worker LP becomes **unbounded** (not just infeasible / suboptimal)
   when a violated cut exists, and the cut is derived from the extreme ray.
   Our approach instead solves the DSP to optimality and checks the dual
   objective against θ — mathematically equivalent for our SSP formulation
   but a different LP structure.

5. Legacy vs. modern CPLEX callback API
   bendersatsp.py uses the legacy ``LazyConstraintCallback`` class (requires
   ``parameters.mip.strategy.search = traditional`` and ``threads = 1``).
   bendersatsp2.py (and our implementation) uses the modern generic callback
   (plain Python class + ``cpx.set_callback()``), which supports
   parallel B&B without the legacy restrictions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import load_ssp_instance

# ---------------------------------------------------------------------------
# Solver detection  (CPLEX → Gurobi → SCIP)
# ---------------------------------------------------------------------------

_BACKEND = None
_BackendClass = None

# CPLEX only — Gurobi and SCIP backends have been archived to _archived/
try:
    import cplex  # noqa: F401
    from branch_and_benders_cut_cplex import BranchAndBendersCutSSP_CPLEX as _BackendClass
    _BACKEND = "CPLEX"
except ImportError:
    pass

if _BackendClass is None:
    raise ImportError(
        "BBC requires IBM CPLEX.  Install the cplex Python package "
        "(ships with IBM CPLEX Studio).\n"
        "Gurobi/SCIP backends have been archived to BBC/_archived/."
    )

print(f"[branch_and_benders_cut] Using backend: {_BACKEND}")


# ---------------------------------------------------------------------------
# Public alias  — looks identical regardless of which backend was loaded
# ---------------------------------------------------------------------------

#: Unified solver class; delegates entirely to the selected backend.
BranchAndBendersCutSSP = _BackendClass


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def solve_ssp_branch_and_benders(instance_path: str,
                                  time_limit: int = 300,
                                  verbose: bool = True,
                                  worker_lp_reuse: bool = False,
                                  use_fractional_cuts: bool = False,
                                  use_combinatorial_cuts: bool = False,
                                  use_triplet_bounds: bool = False,
                                  parallel: bool = False):
    """
    Load an SSP instance from *instance_path* and solve it with BBC.

    Parameters
    ----------
    instance_path : str
        Path to the instance file understood by ``utils.load_ssp_instance``.
    time_limit : int
        Time limit in seconds.
    verbose : bool
        Print solver progress and stats table.
    worker_lp_reuse : bool
        Reuse DSP model across callback calls (bendersatsp2 pattern).
    use_fractional_cuts : bool
        Add Benders LP user cuts at LP relaxation nodes (attacks tailing-off).
    use_combinatorial_cuts : bool
        Use KTNS-based combinatorial cuts instead of LP Benders at integer nodes.
    use_triplet_bounds : bool
        Strengthen the root LP bound with O(n³) triplet constraints.
    parallel : bool
        Allow CPLEX to use multiple B&B threads.

    Returns
    -------
    status : str
    obj_val : float or None
    sequence : list[int] or None
    solver : BranchAndBendersCutSSP
        The solver instance; access solver.solve_stats and
        solver.plot_convergence() for diagnostics.
    """
    n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance(instance_path)

    if verbose:
        print(f"[BBC] Backend  : {_BACKEND}")
        print(f"[BBC] Instance : {Path(instance_path).name}")
        print(f"[BBC] Jobs={n_jobs}, Tools={n_tools}, Capacity={capacity}")

    solver = BranchAndBendersCutSSP(
        n_jobs, n_tools, capacity, tool_req,
        worker_lp_reuse        = worker_lp_reuse,
        use_fractional_cuts    = use_fractional_cuts,
        use_combinatorial_cuts = use_combinatorial_cuts,
        use_triplet_bounds     = use_triplet_bounds,
        parallel               = parallel,
    )
    solver.build_master_problem(verbose=False)
    status, obj_val, sequence = solver.solve(time_limit=time_limit, verbose=verbose)

    if verbose:
        solver.print_stats_table()

    return status, obj_val, sequence, solver


# ---------------------------------------------------------------------------
# __main__ — quick smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    instance_file = (
        Path(__file__).parent.parent / "Instances" / "Shankar" / "shankar-example.txt"
    )
    if instance_file.exists():
        solve_ssp_branch_and_benders(str(instance_file), verbose=True)
    else:
        print(f"Instance file not found: {instance_file}")
        print("Usage: python branch_and_benders_cut.py")
        print("       (place shankar-example.txt at Instances/Shankar/)")
