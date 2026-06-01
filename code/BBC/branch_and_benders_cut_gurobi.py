"""
Branch-and-Benders-Cut Algorithm for the SSP – Gurobi Implementation
(branch_and_benders_cut_gurobi.py)

Renamed from branch_and_benders_cut.py to follow the per-solver naming
convention shared with branch_and_benders_cut_cplex.py and
branch_and_benders_cut_scip.py.

This module implements an exact algorithm combining:
- Master Problem: Traveling Salesman Problem (TSP) with auxiliary variable θ
- Subproblem: Dual LP for tool switching constraints
- Lazy Constraint Callback: Injects subtour elimination and Benders cuts
  via Gurobi's GRB.Callback.MIPSOL / model.cbLazy()

Bugs fixed vs. original version
---------------------------------
1. nu_vars / eta_vars had lb=0 (Gurobi default) but must be FREE (lb=-∞).
   With lb=0 the dual LP was artificially constrained and produced wrong cuts.

2. Subtour detection was completely broken.
   The old code called _find_subtours(sequence) where `sequence` was already
   the result of following one chain from a start node.  If actual subtours
   existed, the chain would be shorter than n_jobs, the length check
   `len(sequence) != n_jobs` returned [] (no subtours found!), and the code
   fell through to the DSP with an incomplete/wrong sequence.
   Fix: _find_subtours_from_sol(sol) works directly on the binary x-solution
   dict and correctly identifies every cycle.

3. _get_sequence_from_solution had no visited-set guard, could loop infinitely
   and did not reliably start from node 0.
   Fix: replaced by _get_sequence_from_sol(sol) which uses a successor dict
   and a clean while-loop with a visited guard.

4. Benders cut generation: the `coeff` initialisation used a dict that was
   rewritten per (i,j), losing previous iterations.  Fixed with explicit
   accumulation.
"""

import numpy as np
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import gurobipy as gp
    from gurobipy import GRB
    HAS_GUROBI = True
except ImportError:
    HAS_GUROBI = False
    print("WARNING: Gurobi not found. Install gurobipy to run this solver.")

from utils import load_ssp_instance


class BranchAndBendersCutSSP:
    """
    Solves SSP via Branch-and-Benders-Cut with Gurobi.

    Master Problem:
        min θ
        s.t. degree constraints (TSP)
             θ ≥ Σ w_ij x_ij   (pairwise lower bounds)
             subtour elimination   (Lazy Constraints)
             Benders optimality cuts  (Lazy Constraints)

    Subproblem (for fixed sequence x̄):
        Dual LP that generates dual variables λ, μ, ν, η for Benders cuts.
    """

    def __init__(self, n_jobs, n_tools, capacity, tool_req):
        """
        Parameters
        ----------
        n_jobs   : int   – number of jobs
        n_tools  : int   – total number of distinct tools
        capacity : int   – magazine capacity c
        tool_req : dict  – tool_req[j] = list of tools required by job j
        """
        self.n_jobs    = n_jobs
        self.n_tools   = n_tools
        self.capacity  = capacity
        self.tool_req  = tool_req

        # Precompute pairwise minimum switches w_ij = max(0, |T_i ∪ T_j| - c)
        self._compute_pairwise_bounds()

        # Model and variables (created in build_master_problem)
        self.model = None
        self.x     = None   # TSP arc variables  x[i,j]
        self.theta = None   # Surrogate cost variable θ

        # Tracking
        self.best_solution  = None
        self.best_objective = float('inf')
        self.iteration_count = 0
        self.cuts_added      = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Pre-computation
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_pairwise_bounds(self):
        """w_ij = max(0, |T_i ∪ T_j| - capacity)  for all ordered pairs (i,j)."""
        self.w = {}
        for i in range(self.n_jobs):
            for j in range(self.n_jobs):
                if i != j:
                    union_size = len(set(self.tool_req[i]) | set(self.tool_req[j]))
                    self.w[i, j] = max(0, union_size - self.capacity)
                else:
                    self.w[i, j] = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Master Problem
    # ─────────────────────────────────────────────────────────────────────────

    def build_master_problem(self, verbose=True):
        """
        Build the TSP master problem with surrogate variable θ.

        Variables
        ---------
        x[i,j] ∈ {0,1}  : arc from job i to job j
        θ ≥ 0            : estimated tool-switching cost

        Static constraints
        ------------------
        - Out-degree 1 and in-degree 1 for every node (degree constraints)
        - θ ≥ Σ w_ij x_ij   (initial lower bound, avoids trivial θ=0 start)

        Dynamic constraints (added by callback)
        ----------------------------------------
        - Subtour-elimination cuts
        - Benders optimality cuts
        """
        if not HAS_GUROBI:
            raise RuntimeError("Gurobi is required. Please install gurobipy.")

        self.model = gp.Model("SSP_BranchAndBendersCut")
        if not verbose:
            self.model.setParam('OutputFlag', 0)

        n = self.n_jobs

        # ── Decision variables ──────────────────────────────────────────────
        self.x = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    self.x[i, j] = self.model.addVar(
                        vtype=GRB.BINARY, name=f"x_{i}_{j}"
                    )

        self.theta = self.model.addVar(
            vtype=GRB.CONTINUOUS, lb=0.0, name="theta"
        )

        # ── Objective ───────────────────────────────────────────────────────
        self.model.setObjective(self.theta, GRB.MINIMIZE)

        # ── Degree constraints ──────────────────────────────────────────────
        for i in range(n):
            self.model.addConstr(
                gp.quicksum(self.x[i, j] for j in range(n) if i != j) == 1,
                name=f"out_{i}"
            )
            self.model.addConstr(
                gp.quicksum(self.x[j, i] for j in range(n) if j != i) == 1,
                name=f"in_{i}"
            )

        # ── Initial lower bound on θ ─────────────────────────────────────────
        self.model.addConstr(
            self.theta >= gp.quicksum(
                self.w[i, j] * self.x[i, j]
                for i in range(n) for j in range(n) if i != j
            ),
            name="lower_bound_theta"
        )

        # Enable lazy constraints
        self.model.Params.LazyConstraints = 1

        if verbose:
            print(f"✓ Master Problem created: {n} jobs, {n*(n-1)} arc variables")

        return self.model

    # ─────────────────────────────────────────────────────────────────────────
    # Solution helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _find_subtours_from_sol(self, sol):
        """
        Detect subtours directly from binary solution values.

        Parameters
        ----------
        sol : dict  {(i,j): float}  – values from cbGetSolution / var.X

        Returns
        -------
        subtours : list of lists
            Each inner list is a cycle of job indices whose length < n_jobs.
            Returns [] when the solution is a single Hamiltonian cycle.
        """
        n = self.n_jobs

        # Build successor mapping from the binary solution
        succ = {}
        for i in range(n):
            for j in range(n):
                if i != j and sol.get((i, j), 0.0) > 0.5:
                    succ[i] = j

        visited  = set()
        subtours = []

        for start in range(n):
            if start in visited:
                continue
            if start not in succ:
                # Isolated node (shouldn't happen in feasible degree-constrained sol)
                visited.add(start)
                continue

            # Follow the cycle from `start`
            cycle   = [start]
            visited.add(start)
            current = succ[start]

            while current != start:
                if current in visited:
                    # Broken chain – degree constraint violated
                    cycle = None
                    break
                visited.add(current)
                cycle.append(current)
                nxt = succ.get(current)
                if nxt is None:
                    cycle = None
                    break
                current = nxt

            if cycle is not None and len(cycle) < n:
                subtours.append(cycle)

        return subtours

    def _get_sequence_from_sol(self, sol):
        """
        Extract the Hamiltonian sequence from a solution with no subtours.

        Starts from job 0 and follows successor arcs.

        Returns
        -------
        list[int] of length n_jobs, or None if extraction fails.
        """
        n = self.n_jobs

        # Build successor map
        succ = {}
        for i in range(n):
            for j in range(n):
                if i != j and sol.get((i, j), 0.0) > 0.5:
                    succ[i] = j

        if not succ:
            return None

        start    = 0
        sequence = [start]
        current  = succ.get(start)

        while current is not None and current != start and len(sequence) < n:
            sequence.append(current)
            current = succ.get(current)

        if len(sequence) != n:
            return None
        return sequence

    # ─────────────────────────────────────────────────────────────────────────
    # Dual Sub-Problem (DSP)
    # ─────────────────────────────────────────────────────────────────────────

    def _solve_dual_subproblem(self, sequence):
        """
        Solve the Dual LP for a fixed job sequence to obtain Benders dual vars.

        DSP (maximisation):
            max  Σ_{i,j,t} (x̄_ij - 1)λ_ijt  - Σ_j c μ_j  + Σ_{j,t∈T_j} ν_jt

        Subject to  (for each j ∈ J, t ∈ T):
            [y_jt ≥ 0]:  -μ_j - Σ_i λ_ijt + Σ_k λ_jkt + (ν_jt if t∈T_j) ≤ 0
            [z_jt ≥ 0]:   Σ_i λ_ijt       + (η_jt if t∉T_j) ≤ (1 if t∈T_j else 0)
            λ_ijt ≥ 0,  μ_j ≥ 0,  ν_jt free,  η_jt free

        IMPORTANT: ν and η are FREE variables (no lower bound).  The original
        code mistakenly left them at Gurobi's default lb=0, making the dual
        artificially infeasible / incorrectly constrained.

        Returns
        -------
        obj_val : float or None
        duals   : dict  {('lambda',i,j,t): v, ('mu',j): v, ('nu',j,t): v, ...}
        """
        if sequence is None:
            return None, {}

        try:
            import gurobipy as gp
            from gurobipy import GRB
        except ImportError:
            return None, {}

        n      = self.n_jobs
        T      = range(self.n_tools)

        dsp = gp.Model("DSP")
        dsp.setParam('OutputFlag', 0)

        # ── Dual variables ────────────────────────────────────────────────
        lam  = {}   # λ_ijt ≥ 0
        mu   = {}   # μ_j   ≥ 0
        nu   = {}   # ν_jt  free  ← FIX: was lb=0 by default
        eta  = {}   # η_jt  free  ← FIX: was lb=0 by default

        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in T:
                        lam[i, j, t] = dsp.addVar(
                            lb=0.0, vtype=GRB.CONTINUOUS, name=f"lam_{i}_{j}_{t}"
                        )

        for j in range(n):
            mu[j] = dsp.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name=f"mu_{j}")
            for t in T:
                # FIX: must be FREE (lb = -∞)
                nu[j, t]  = dsp.addVar(lb=-GRB.INFINITY, vtype=GRB.CONTINUOUS,
                                       name=f"nu_{j}_{t}")
                eta[j, t] = dsp.addVar(lb=-GRB.INFINITY, vtype=GRB.CONTINUOUS,
                                       name=f"eta_{j}_{t}")

        # ── x̄ from the fixed sequence (Hamiltonian cycle) ────────────────
        x_bar = {}
        for k in range(n - 1):
            x_bar[sequence[k], sequence[k + 1]] = 1
        x_bar[sequence[-1], sequence[0]] = 1   # close the cycle

        # ── Objective ─────────────────────────────────────────────────────
        tool_req = self.tool_req
        obj = gp.quicksum(
            (x_bar.get((i, j), 0) - 1) * lam[i, j, t]
            for i in range(n) for j in range(n) if i != j
            for t in T
        )
        obj += gp.quicksum(-self.capacity * mu[j] for j in range(n))
        obj += gp.quicksum(
            nu[j, t]
            for j in range(n) for t in tool_req.get(j, [])
        )
        dsp.setObjective(obj, GRB.MAXIMIZE)

        # ── Dual constraint for y_jt ≥ 0 ─────────────────────────────────
        # -μ_j - Σ_i λ_ijt + Σ_k λ_jkt + (ν_jt if t∈T_j) ≤ 0
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                nu_term = nu[j, t] if t in Tj else 0
                lhs = (
                    -mu[j]
                    - gp.quicksum(lam[i, j, t] for i in range(n) if i != j)
                    + gp.quicksum(lam[j, k, t] for k in range(n) if k != j)
                    + nu_term
                )
                dsp.addConstr(lhs <= 0, name=f"dual_y_{j}_{t}")

        # ── Dual constraint for z_jt ≥ 0 ─────────────────────────────────
        # Σ_i λ_ijt + (η_jt if t∉T_j) ≤ (1 if t∈T_j else 0)
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                eta_term = eta[j, t] if t not in Tj else 0
                rhs = 1.0 if t in Tj else 0.0
                lhs = (
                    gp.quicksum(lam[i, j, t] for i in range(n) if i != j)
                    + eta_term
                )
                dsp.addConstr(lhs <= rhs, name=f"dual_z_{j}_{t}")

        dsp.optimize()

        if dsp.status != GRB.OPTIMAL:
            return None, {}

        # ── Extract dual values ────────────────────────────────────────────
        duals = {}
        for (i, j, t), v in lam.items():
            duals['lambda', i, j, t] = v.X
        for j, v in mu.items():
            duals['mu', j] = v.X
        for (j, t), v in nu.items():
            duals['nu', j, t] = v.X
        for (j, t), v in eta.items():
            duals['eta', j, t] = v.X

        return dsp.objVal, duals

    # ─────────────────────────────────────────────────────────────────────────
    # Benders cut generation
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_benders_cut(self, sequence, duals):
        """
        Build the Benders optimality cut from DSP dual variables.

        The cut is:
            θ ≥ Σ_{i,j,t} (x_ij - 1) λ̄_ijt  - Σ_j c μ̄_j  + Σ_{j,t∈T_j} ν̄_jt

        Rearranging into (cut_expr + cut_rhs) form:
            θ ≥ Σ_{i,j} coeff_ij * x_ij  +  cut_rhs_constant

        where  coeff_ij = Σ_t λ̄_ijt
        and    cut_rhs  = Σ_{i,j} (-coeff_ij)  - c Σ_j μ̄_j  + Σ_{j,t∈T_j} ν̄_jt

        Returns
        -------
        cut_expr : Gurobi LinExpr   – the variable part  Σ coeff_ij x_ij
        cut_rhs  : float            – the constant part
        """
        n = self.n_jobs

        # Aggregate λ over tools to get per-arc coefficient
        coeff = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    coeff[i, j] = sum(
                        duals.get(('lambda', i, j, t), 0.0)
                        for t in range(self.n_tools)
                    )

        # Constant contributions
        cut_rhs = 0.0
        # -c * μ_j  terms
        for j in range(n):
            cut_rhs -= self.capacity * duals.get(('mu', j), 0.0)
        # +ν_jt  for t ∈ T_j
        for j in range(n):
            for t in self.tool_req.get(j, []):
                cut_rhs += duals.get(('nu', j, t), 0.0)
        # The (x_ij - 1) factor means each λ contributes -λ to the constant
        for (i, j), c in coeff.items():
            cut_rhs -= c

        # Variable part
        cut_expr = gp.quicksum(
            coeff.get((i, j), 0.0) * self.x[i, j]
            for i in range(n) for j in range(n) if i != j
        )

        return cut_expr, cut_rhs

    # ─────────────────────────────────────────────────────────────────────────
    # Callback
    # ─────────────────────────────────────────────────────────────────────────

    def _callback(self, model, where):
        """
        Gurobi lazy-constraint callback.

        Called on every integer incumbent (GRB.Callback.MIPSOL).

        Logic
        -----
        1. Extract x solution as a dict {(i,j): 0/1}.
        2. Detect subtours directly from that dict.
           If any exist → add SEC and return (do NOT try to solve DSP).
        3. If no subtours → extract Hamiltonian sequence → solve DSP.
        4. If DSP value > θ → inject Benders cut.
        """
        if where != GRB.Callback.MIPSOL:
            return

        self.iteration_count += 1

        try:
            # ── Retrieve solution ─────────────────────────────────────────
            sol = {
                (i, j): model.cbGetSolution(var)
                for (i, j), var in self.x.items()
            }
            theta_val = model.cbGetSolution(self.theta)

            # ── Step A: Subtour check ──────────────────────────────────────
            subtours = self._find_subtours_from_sol(sol)

            if subtours:
                for st in subtours:
                    # SEC:  Σ_{i,j ∈ st, i≠j} x_ij ≤ |st| - 1
                    model.cbLazy(
                        gp.quicksum(
                            self.x[i, j]
                            for i in st for j in st
                            if i != j and (i, j) in self.x
                        )
                        <= len(st) - 1
                    )
                    self.cuts_added += 1
                return   # ← critical: do not proceed to DSP

            # ── Step B: Extract Hamiltonian sequence ──────────────────────
            sequence = self._get_sequence_from_sol(sol)
            if sequence is None:
                return

            # ── Step C: Solve Dual Subproblem ──────────────────────────────
            dsp_obj, duals = self._solve_dual_subproblem(sequence)
            if dsp_obj is None:
                return

            # ── Step D: Inject Benders cut if violated ─────────────────────
            if dsp_obj > theta_val + 1e-6:
                cut_expr, cut_rhs = self._generate_benders_cut(sequence, duals)
                model.cbLazy(self.theta >= cut_expr + cut_rhs)
                self.cuts_added += 1

            # Track best feasible objective
            if dsp_obj < self.best_objective:
                self.best_objective = dsp_obj
                self.best_solution  = sequence[:]

        except Exception as exc:
            print(f"[Callback error] {exc}")
            import traceback
            traceback.print_exc()

    # ─────────────────────────────────────────────────────────────────────────
    # Solve
    # ─────────────────────────────────────────────────────────────────────────

    def solve(self, time_limit=3600, verbose=True):
        """
        Run Branch-and-Benders-Cut to global optimality (or time limit).

        Returns
        -------
        status   : str   – 'OPTIMAL', 'TIME_LIMIT', or Gurobi status code
        obj_val  : float – best-found objective (tool switches)
        sequence : list  – job sequence
        """
        if self.model is None:
            self.build_master_problem(verbose=verbose)

        self.model.Params.TimeLimit       = time_limit
        self.model.Params.LazyConstraints = 1
        if not verbose:
            self.model.Params.OutputFlag = 0

        self.model.optimize(self._callback)

        # ── Extract result ────────────────────────────────────────────────
        if self.model.status in (GRB.OPTIMAL, GRB.TIME_LIMIT):
            status  = 'OPTIMAL' if self.model.status == GRB.OPTIMAL else 'TIME_LIMIT'
            obj_val = self.model.objVal

            sol = {(i, j): var.X for (i, j), var in self.x.items()}
            sequence = self._get_sequence_from_sol(sol)
        else:
            status   = str(self.model.status)
            obj_val  = self.best_objective
            sequence = self.best_solution

        if verbose:
            sep = '=' * 60
            print(f"\n{sep}")
            print(f"Solution Status : {status}")
            print(f"Objective Value : {obj_val}")
            print(f"Sequence        : {sequence}")
            print(f"Iterations      : {self.iteration_count}")
            print(f"Cuts Added      : {self.cuts_added}")
            print(f"{sep}\n")

        return status, obj_val, sequence


# ─────────────────────────────────────────────────────────────────────────────
# Convenience wrapper
# ─────────────────────────────────────────────────────────────────────────────

def solve_ssp_branch_and_benders(instance_path, verbose=True):
    """
    Load an SSP instance file and solve it with Branch-and-Benders-Cut.

    Parameters
    ----------
    instance_path : str  – path to the instance file
    verbose       : bool

    Returns
    -------
    status, obj_val, sequence
    """
    n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance(instance_path)

    if verbose:
        sep = '=' * 60
        print(f"\n{sep}")
        print(f"Instance : {Path(instance_path).name}")
        print(f"Jobs: {n_jobs}  Tools: {n_tools}  Capacity: {capacity}")
        print(f"{sep}\n")

    solver = BranchAndBendersCutSSP(n_jobs, n_tools, capacity, tool_req)
    solver.build_master_problem(verbose=verbose)
    return solver.solve(verbose=verbose)


if __name__ == "__main__":
    instance_file = (
        Path(__file__).parent.parent / "Instances" / "Shankar" / "shankar-example.txt"
    )
    if instance_file.exists():
        solve_ssp_branch_and_benders(str(instance_file), verbose=True)
    else:
        print(f"Instance file not found: {instance_file}")
