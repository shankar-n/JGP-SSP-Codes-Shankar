"""
Branch-and-Benders-Cut Algorithm for the Job Sequencing Problem (SSP) – CPLEX Implementation.

This module implements the exact algorithm specified in plan-from-gemma.md using the
IBM CPLEX Python API (cplex package, NOT docplex) together with the modern generic
callback interface introduced in CPLEX 12.10 / 22.1.

Bugs fixed / redesigned vs. the original version
-------------------------------------------------
1.  The original code used docplex.mp.Model for the master problem.  docplex does NOT
    expose the generic callback interface that is required for lazy constraints with
    custom logic.  The master problem is now built with cplex.Cplex() directly, exactly
    as shown in the IBM example admipex8.py.

2.  BendersCutCallback inherited from docplex LazyConstraintCallback but was NEVER
    registered with the model.  self.model.solve() was a plain TSP solve – no Benders
    cuts were ever added.  The callback is now a plain Python class whose invoke()
    method is called by CPLEX via cpx.set_callback(cb, contextmask), following the
    admipex8 pattern.

3.  _find_subtours was completely wrong:  it checked `len(set(sequence)) == n_jobs`
    (unique element count), which can never detect cycles shorter than n_jobs in a
    degree-constrained solution.  Replaced by _find_subtours_from_sol(sol) that works
    directly on the binary x-solution dict.

4.  _get_sequence_from_solution started from job 0 and had no visited-set guard,
    so it could add duplicate nodes or loop forever on subtour solutions.  Replaced
    by _get_sequence_from_sol(sol) with an explicit visited guard.

5.  nu_vars / eta_vars in the DSP had lb=0 (docplex default) but must be FREE.
    Fixed with lb=dsp.minus_infinity.

6.  __main__ unpacked only 4 values from load_ssp_instance, but the function returns 5.
    Fixed.

Dependencies
------------
    cplex      – raw IBM CPLEX Python API (ships with the CPLEX installation)
    docplex    – used ONLY for solving the DSP LP (no callbacks needed there)
    gurobipy   – optional fallback for the DSP
    numpy      – required

Install notes:
    pip install cplex docplex   (requires an IBM CPLEX installation on the system)
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Solver imports ────────────────────────────────────────────────────────────
try:
    import cplex
    from cplex import SparsePair
    HAS_CPLEX = True
except ImportError:
    HAS_CPLEX = False
    print("WARNING: cplex not found.  Install the IBM CPLEX Python package.")

try:
    from docplex.mp.model import Model as DocplexModel
    HAS_DOCPLEX = True
except ImportError:
    HAS_DOCPLEX = False

try:
    import gurobipy as gp
    from gurobipy import GRB
    HAS_GUROBI = True
except ImportError:
    HAS_GUROBI = False

from utils import load_ssp_instance


# ─────────────────────────────────────────────────────────────────────────────
# Modern generic callback (admipex8 style)
# ─────────────────────────────────────────────────────────────────────────────

class BendersCutCallback:
    """
    CPLEX generic callback.  invoke() is called by CPLEX at candidate solutions
    (integer feasible points).

    The callback is registered with:
        cpx.set_callback(cb_instance, cplex.callbacks.Context.id.candidate)

    At each integer incumbent:
    1.  Extract x values and θ.
    2.  Detect subtours via _find_subtours_from_sol().
        - If subtours exist → call context.reject_candidate() with SEC constraints.
    3.  No subtours → extract Hamiltonian sequence → solve DSP.
    4.  DSP value > θ → inject Benders cut via context.reject_candidate().
    """

    def __init__(self, solver):
        self.solver          = solver
        self.cuts_added      = 0
        self.iteration_count = 0
        self.best_objective  = float('inf')
        self.best_solution   = None

    def invoke(self, context):
        """Entry point called by CPLEX."""
        try:
            if context.in_candidate():
                if not context.is_candidate_point():
                    return   # Ignore unbounded rays
                self._handle_candidate(context)
        except Exception as exc:
            print(f"[CPLEX callback error] {exc}")
            import traceback
            traceback.print_exc()

    def _handle_candidate(self, context):
        self.iteration_count += 1

        solver  = self.solver
        n       = solver.n_jobs
        n_vars  = solver.n_vars

        # ── Retrieve all variable values ──────────────────────────────────
        all_vals  = context.get_candidate_point(list(range(n_vars)))
        theta_val = all_vals[solver.theta_idx]

        sol = {}
        for (i, j) in solver.x_pairs:
            sol[i, j] = all_vals[solver.x_idx_map[i, j]]

        # ── Step A: Subtour check ─────────────────────────────────────────
        subtours = solver._find_subtours_from_sol(sol)

        if subtours:
            constraints = []
            senses      = []
            rhs_vals    = []
            for st in subtours:
                # SEC:  Σ_{i,j ∈ st, i≠j} x_ij ≤ |st| - 1
                indices = [
                    solver.x_idx_map[i, j]
                    for i in st for j in st
                    if i != j and (i, j) in solver.x_idx_map
                ]
                if indices:
                    constraints.append(SparsePair(indices, [1.0] * len(indices)))
                    senses.append('L')
                    rhs_vals.append(float(len(st) - 1))
                    self.cuts_added += 1

            if constraints:
                context.reject_candidate(
                    constraints=constraints,
                    senses=senses,
                    rhs=rhs_vals
                )
            return   # ← do not fall through to DSP

        # ── Step B: Extract Hamiltonian sequence ──────────────────────────
        sequence = solver._get_sequence_from_sol(sol)
        if sequence is None:
            return

        # ── Step C: Solve DSP ─────────────────────────────────────────────
        dsp_obj, duals = solver._solve_dual_subproblem(sequence)
        if dsp_obj is None:
            return

        # ── Step D: Benders cut ───────────────────────────────────────────
        if dsp_obj > theta_val + 1e-6:
            cut_sp, cut_rhs = solver._build_benders_cut_sparsepair(duals)
            context.reject_candidate(
                constraints=[cut_sp],
                senses=['G'],
                rhs=[cut_rhs]
            )
            self.cuts_added += 1

        # Track best incumbent
        if dsp_obj < self.best_objective:
            self.best_objective = dsp_obj
            self.best_solution  = sequence[:]


# ─────────────────────────────────────────────────────────────────────────────
# Solver class
# ─────────────────────────────────────────────────────────────────────────────

class BranchAndBendersCutSSP_CPLEX:
    """
    Branch-and-Benders-Cut solver using IBM CPLEX (raw cplex API).

    Master Problem  : TSP with surrogate cost θ, built with cplex.Cplex()
    Callback        : Modern generic callback (cpx.set_callback)
    DSP             : Solved with docplex (if available) or Gurobi fallback
    """

    def __init__(self, n_jobs, n_tools, capacity, tool_req):
        self.n_jobs    = n_jobs
        self.n_tools   = n_tools
        self.capacity  = capacity
        self.tool_req  = tool_req

        self._compute_pairwise_bounds()

        # CPLEX model and variable index bookkeeping
        self.cpx       = None
        self.theta_idx = None
        self.x_idx_map = {}    # (i,j) → column index
        self.x_pairs   = []    # ordered list of (i,j) arcs
        self.n_vars    = 0

        # Tracking
        self.best_solution   = None
        self.best_objective  = float('inf')
        self.cuts_added      = 0
        self.iteration_count = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Pre-computation
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_pairwise_bounds(self):
        """w_ij = max(0, |T_i ∪ T_j| - capacity)."""
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
        Build the TSP + θ master problem using cplex.Cplex().

        Variables
        ---------
        Column 0            : θ  (continuous, obj = 1)
        Columns 1 … n(n-1) : x[i,j]  (binary, obj = 0)

        Constraints
        -----------
        - Out-degree 1 per node  (equality)
        - In-degree  1 per node  (equality)
        - θ - Σ w_ij x_ij ≥ 0   (initial lower bound on θ)
        """
        if not HAS_CPLEX:
            raise ImportError(
                "cplex package not available.  "
                "Install it via your IBM CPLEX installation."
            )

        self.cpx = cplex.Cplex()
        if not verbose:
            self.cpx.set_log_stream(None)
            self.cpx.set_results_stream(None)
            self.cpx.set_warning_stream(None)

        n = self.n_jobs

        # ── θ variable at column 0 ────────────────────────────────────────
        self.cpx.variables.add(
            obj   = [1.0],
            lb    = [0.0],
            types = ['C'],
            names = ['theta']
        )
        self.theta_idx = 0

        # ── Arc variables x[i,j] ─────────────────────────────────────────
        self.x_pairs = [
            (i, j) for i in range(n) for j in range(n) if i != j
        ]
        n_arcs = len(self.x_pairs)

        self.cpx.variables.add(
            obj   = [0.0]  * n_arcs,
            lb    = [0.0]  * n_arcs,
            ub    = [1.0]  * n_arcs,
            types = ['B']  * n_arcs,
            names = [f'x_{i}_{j}' for i, j in self.x_pairs]
        )
        # Column index: theta=0, x_pairs[k] → k+1
        for k, (i, j) in enumerate(self.x_pairs):
            self.x_idx_map[i, j] = k + 1

        self.n_vars = 1 + n_arcs

        # Minimise θ
        self.cpx.objective.set_sense(self.cpx.objective.sense.minimize)

        # ── Degree constraints ─────────────────────────────────────────────
        for i in range(n):
            # Out-degree:  Σ_j x[i,j] = 1
            out_idx = [self.x_idx_map[i, j] for j in range(n) if i != j]
            self.cpx.linear_constraints.add(
                lin_expr = [SparsePair(out_idx, [1.0] * len(out_idx))],
                senses   = ['E'],
                rhs      = [1.0],
                names    = [f'out_{i}']
            )
            # In-degree:  Σ_j x[j,i] = 1
            in_idx = [self.x_idx_map[j, i] for j in range(n) if j != i]
            self.cpx.linear_constraints.add(
                lin_expr = [SparsePair(in_idx, [1.0] * len(in_idx))],
                senses   = ['E'],
                rhs      = [1.0],
                names    = [f'in_{i}']
            )

        # ── Initial lower bound:  θ - Σ w_ij x_ij ≥ 0 ────────────────────
        lb_indices = [self.theta_idx] + [self.x_idx_map[i, j] for i, j in self.x_pairs]
        lb_coeffs  = [1.0]            + [-self.w[i, j]         for i, j in self.x_pairs]
        self.cpx.linear_constraints.add(
            lin_expr = [SparsePair(lb_indices, lb_coeffs)],
            senses   = ['G'],
            rhs      = [0.0],
            names    = ['theta_lb']
        )

        if verbose:
            print(f"Master Problem built: {n} jobs, {n_arcs} arc variables")

    # ─────────────────────────────────────────────────────────────────────────
    # Solution helpers (shared with callback)
    # ─────────────────────────────────────────────────────────────────────────

    def _find_subtours_from_sol(self, sol):
        """
        Detect all subtours from binary x-solution values.

        Parameters
        ----------
        sol : dict  {(i,j): float}  – x variable values

        Returns
        -------
        list of lists – each sub-list is a cycle with len < n_jobs.
        Returns [] for a Hamiltonian cycle.
        """
        n    = self.n_jobs
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
                visited.add(start)
                continue

            cycle   = [start]
            visited.add(start)
            current = succ[start]

            while current != start:
                if current in visited:
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
        Extract the Hamiltonian sequence from a subtour-free solution.

        Starts from job 0 and follows successors.

        Returns
        -------
        list[int] or None
        """
        n    = self.n_jobs
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

        return sequence if len(sequence) == n else None

    # ─────────────────────────────────────────────────────────────────────────
    # Dual Subproblem
    # ─────────────────────────────────────────────────────────────────────────

    def _solve_dual_subproblem(self, sequence):
        """
        Solve the Dual LP for a fixed sequence.

        Tries docplex first, then Gurobi.  Raises if neither is available.

        Returns
        -------
        (obj_val, duals) or (None, {})
        """
        if sequence is None:
            return None, {}

        if HAS_DOCPLEX:
            return self._solve_dsp_docplex(sequence)
        elif HAS_GUROBI:
            return self._solve_dsp_gurobi(sequence)
        else:
            raise RuntimeError(
                "Neither docplex nor gurobipy is available to solve the DSP.  "
                "Install at least one of them."
            )

    def _solve_dsp_docplex(self, sequence):
        """Solve the Dual LP using docplex (uses CPLEX under the hood)."""
        n      = self.n_jobs
        T      = range(self.n_tools)
        tool_req = self.tool_req

        dsp = DocplexModel("DSP", log_output=False)
        neg_inf = dsp.minus_infinity

        # ── x̄ from sequence ──────────────────────────────────────────────
        x_bar = {}
        for k in range(n - 1):
            x_bar[sequence[k], sequence[k + 1]] = 1
        x_bar[sequence[-1], sequence[0]] = 1

        # ── Dual variables ────────────────────────────────────────────────
        lam = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in T:
                        lam[i, j, t] = dsp.continuous_var(
                            lb=0.0, name=f"lam_{i}_{j}_{t}"
                        )
        mu  = {j: dsp.continuous_var(lb=0.0, name=f"mu_{j}") for j in range(n)}
        nu  = {}
        eta = {}
        for j in range(n):
            for t in T:
                # FIX: must be FREE
                nu[j, t]  = dsp.continuous_var(lb=neg_inf, name=f"nu_{j}_{t}")
                eta[j, t] = dsp.continuous_var(lb=neg_inf, name=f"eta_{j}_{t}")

        # ── Objective ─────────────────────────────────────────────────────
        obj = dsp.sum(
            (x_bar.get((i, j), 0) - 1) * lam[i, j, t]
            for i in range(n) for j in range(n) if i != j
            for t in T
        )
        obj += dsp.sum(-self.capacity * mu[j] for j in range(n))
        obj += dsp.sum(nu[j, t] for j in range(n) for t in tool_req.get(j, []))
        dsp.maximize(obj)

        # ── Constraints for y_jt ≥ 0 ─────────────────────────────────────
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                nu_term = nu[j, t] if t in Tj else 0
                lhs = (
                    -mu[j]
                    - dsp.sum(lam[i, j, t] for i in range(n) if i != j)
                    + dsp.sum(lam[j, k, t] for k in range(n) if k != j)
                    + nu_term
                )
                dsp.add_constraint(lhs <= 0, f"dy_{j}_{t}")

        # ── Constraints for z_jt ≥ 0 ─────────────────────────────────────
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                eta_term = eta[j, t] if t not in Tj else 0
                rhs      = 1.0 if t in Tj else 0.0
                lhs = (
                    dsp.sum(lam[i, j, t] for i in range(n) if i != j)
                    + eta_term
                )
                dsp.add_constraint(lhs <= rhs, f"dz_{j}_{t}")

        # ── Solve ──────────────────────────────────────────────────────────
        sol = dsp.solve(log_output=False)
        if sol is None:
            return None, {}

        # ── Extract duals ──────────────────────────────────────────────────
        duals = {}
        for (i, j, t), v in lam.items():
            duals['lambda', i, j, t] = sol.get_value(v)
        for j, v in mu.items():
            duals['mu', j] = sol.get_value(v)
        for (j, t), v in nu.items():
            duals['nu', j, t] = sol.get_value(v)
        for (j, t), v in eta.items():
            duals['eta', j, t] = sol.get_value(v)

        return dsp.objective_value, duals

    def _solve_dsp_gurobi(self, sequence):
        """Solve the Dual LP using Gurobi (fallback when docplex unavailable)."""
        n        = self.n_jobs
        T        = range(self.n_tools)
        tool_req = self.tool_req

        dsp = gp.Model("DSP")
        dsp.setParam('OutputFlag', 0)

        x_bar = {}
        for k in range(n - 1):
            x_bar[sequence[k], sequence[k + 1]] = 1
        x_bar[sequence[-1], sequence[0]] = 1

        lam = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in T:
                        lam[i, j, t] = dsp.addVar(lb=0.0, name=f"lam_{i}_{j}_{t}")

        mu  = {j: dsp.addVar(lb=0.0, name=f"mu_{j}") for j in range(n)}
        nu  = {}
        eta = {}
        for j in range(n):
            for t in T:
                nu[j, t]  = dsp.addVar(lb=-GRB.INFINITY, name=f"nu_{j}_{t}")
                eta[j, t] = dsp.addVar(lb=-GRB.INFINITY, name=f"eta_{j}_{t}")

        obj = gp.quicksum(
            (x_bar.get((i, j), 0) - 1) * lam[i, j, t]
            for i in range(n) for j in range(n) if i != j for t in T
        )
        obj += gp.quicksum(-self.capacity * mu[j] for j in range(n))
        obj += gp.quicksum(nu[j, t] for j in range(n) for t in tool_req.get(j, []))
        dsp.setObjective(obj, GRB.MAXIMIZE)

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
                dsp.addConstr(lhs <= 0)

        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                eta_term = eta[j, t] if t not in Tj else 0
                rhs = 1.0 if t in Tj else 0.0
                lhs = (
                    gp.quicksum(lam[i, j, t] for i in range(n) if i != j)
                    + eta_term
                )
                dsp.addConstr(lhs <= rhs)

        dsp.optimize()
        if dsp.status != GRB.OPTIMAL:
            return None, {}

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
    # Benders cut assembly (SparsePair form for CPLEX)
    # ─────────────────────────────────────────────────────────────────────────

    def _build_benders_cut_sparsepair(self, duals):
        """
        Convert Benders dual variables into a cplex.SparsePair + rhs for
        use inside context.reject_candidate().

        The cut is:
            θ ≥ Σ_{i,j,t} (x_ij - 1) λ̄_ijt  - Σ_j c μ̄_j  + Σ_{j,t∈T_j} ν̄_jt

        Rearranged as  (θ - Σ coeff_ij x_ij) ≥ cut_rhs :
            sense = 'G',  rhs = cut_rhs

        Returns
        -------
        sp       : cplex.SparsePair
        cut_rhs  : float
        """
        n = self.n_jobs

        # Per-arc coefficient:  coeff_ij = Σ_t λ̄_ijt
        coeff = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    coeff[i, j] = sum(
                        duals.get(('lambda', i, j, t), 0.0)
                        for t in range(self.n_tools)
                    )

        # Constant part
        cut_rhs = 0.0
        for j in range(n):
            cut_rhs -= self.capacity * duals.get(('mu', j), 0.0)
        for j in range(n):
            for t in self.tool_req.get(j, []):
                cut_rhs += duals.get(('nu', j, t), 0.0)
        # (x_ij - 1) factor: each λ contributes -Σλ to the constant
        for (i, j), c in coeff.items():
            cut_rhs -= c

        # Build SparsePair:  θ - Σ coeff_ij x_ij  (sense G, rhs = cut_rhs)
        indices = [self.theta_idx] + [self.x_idx_map[i, j] for i, j in self.x_pairs]
        coeffs  = [1.0]            + [-coeff.get((i, j), 0.0) for i, j in self.x_pairs]

        return SparsePair(indices, coeffs), cut_rhs

    # ─────────────────────────────────────────────────────────────────────────
    # Solve
    # ─────────────────────────────────────────────────────────────────────────

    def solve(self, time_limit=3600, verbose=True):
        """
        Run Branch-and-Benders-Cut.

        Returns
        -------
        status   : str
        obj_val  : float
        sequence : list[int]
        """
        if self.cpx is None:
            self.build_master_problem(verbose=verbose)

        # Time limit
        self.cpx.parameters.timelimit.set(float(time_limit))

        # ── Register modern generic callback ─────────────────────────────
        cb           = BendersCutCallback(self)
        context_mask = cplex.callbacks.Context.id.candidate
        self.cpx.set_callback(cb, context_mask)

        # ── Solve ─────────────────────────────────────────────────────────
        self.cpx.solve()

        # ── Extract result ────────────────────────────────────────────────
        status_code = self.cpx.solution.get_status()
        status_str  = self.cpx.solution.status[status_code]

        try:
            obj_val  = self.cpx.solution.get_objective_value()
            all_vals = self.cpx.solution.get_values()

            sol = {(i, j): all_vals[self.x_idx_map[i, j]] for (i, j) in self.x_pairs}
            sequence = self._get_sequence_from_sol(sol)
        except Exception:
            obj_val  = cb.best_objective
            sequence = cb.best_solution
            status_str = 'NO_SOLUTION'

        # Propagate callback stats
        self.cuts_added      = cb.cuts_added
        self.iteration_count = cb.iteration_count
        if cb.best_objective < self.best_objective:
            self.best_objective = cb.best_objective
            self.best_solution  = cb.best_solution

        if verbose:
            sep = '=' * 60
            print(f"\n{sep}")
            print(f"Solution Status : {status_str}")
            print(f"Objective Value : {obj_val}")
            print(f"Sequence        : {sequence}")
            print(f"Iterations      : {self.iteration_count}")
            print(f"Cuts Added      : {self.cuts_added}")
            print(f"{sep}\n")

        return status_str, obj_val, sequence


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not HAS_CPLEX:
        print("ERROR: cplex not installed")
        sys.exit(1)

    # FIX: load_ssp_instance returns 5 values (original code only unpacked 4)
    instance_path = (
        Path(__file__).parent.parent / "Instances" / "Shankar" / "shankar-example.txt"
    )

    try:
        n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance(str(instance_path))

        print(f"Instance : {instance_path.name}")
        print(f"Jobs: {n_jobs}  Tools: {n_tools}  Capacity: {capacity}\n")

        solver = BranchAndBendersCutSSP_CPLEX(n_jobs, n_tools, capacity, tool_req)
        solver.build_master_problem(verbose=True)

        print("\nSolving …\n")
        status, obj_val, sequence = solver.solve(time_limit=60, verbose=True)

        print(f"Status   : {status}")
        print(f"Objective: {obj_val}")
        print(f"Sequence : {sequence}")

    except Exception as exc:
        import traceback
        print(f"Error: {exc}")
        traceback.print_exc()
