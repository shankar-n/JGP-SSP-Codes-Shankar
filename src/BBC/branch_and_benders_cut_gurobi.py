"""
Branch-and-Benders-Cut Algorithm for the SSP – Gurobi Implementation
(branch_and_benders_cut_gurobi.py)

Algorithm summary
-----------------
Master Problem (TSP + surrogate θ):
    min  θ
    s.t. degree constraints (Hamiltonian cycle)
         θ ≥ Σ w_ij x_ij          (initial pairwise lower bound)
         SECs                       (lazy, added by callback)
         Benders optimality cuts    (lazy, added by callback)

Dual Subproblem (DSP) for a fixed x̄ (integer or fractional):
    max  Σ_{i,j,t} (x̄_ij − 1) λ_ijt  −  Σ_j c μ_j  +  Σ_{j,t∈T_j} ν_jt
    s.t. −μ_j − Σ_i λ_ijt + Σ_k λ_jkt + (ν_jt if t∈T_j) ≤ 0   [y_jt ≥ 0]
          Σ_i λ_ijt           + (η_jt if t∉T_j) ≤ 1_{t∈T_j}    [z_jt ≥ 0]
         λ ≥ 0, μ ≥ 0, ν FREE, η FREE

Benders optimality cut:
    θ ≥ Σ_{i,j,t} (x_ij − 1) λ̄_ijt  −  Σ_j c μ̄_j  +  Σ_{j,t∈T_j} ν̄_jt

Optional performance features (all default False)
--------------------------------------------------
worker_lp_reuse : bool
    Build the DSP Gurobi model once and update only the objective coefficients
    (x̄_ij values) on each callback call, rather than rebuilding from scratch.
    Inspired by the Worker LP reuse pattern in IBM's bendersatsp2 example.
    Warm-starting the LP basis between calls gives significant speedup on
    large instances.  When parallel=True, one model is kept per thread via
    threading.local().

use_fractional_cuts : bool
    Fire the callback also at LP-relaxation nodes (GRB.Callback.MIPNODE) to
    add Benders *user cuts* from fractional x̄ solutions.  User cuts tighten
    the LP bound before branching, reducing tree size.  The DSP is solved
    with fractional x̄ values directly (the LP is always bounded).  Subtour
    checks are skipped for fractional solutions.  Requires PreCrush=1
    (set automatically when this flag is True).

parallel : bool
    Allow multi-threaded B&B (Gurobi Params.Threads = 0 → all cores).
    When False (default), Gurobi uses a single thread, which is safer when
    worker_lp_reuse=True because MIPSOL callbacks are already serialised.
    When True and worker_lp_reuse=True, a thread-local DSP model is used
    to avoid data races at MIPNODE (fractional) callback sites.

Bugs fixed vs. original version
---------------------------------
1. ν_jt / η_jt had lb=0 (Gurobi default) but must be FREE (lb=−∞).
2. Subtour detection rewrote as _find_subtours_from_sol() working directly
   on the binary x-solution dict.
3. _get_sequence_from_sol() with explicit visited guard replaced the
   loop-prone original.
4. Benders cut coefficient accumulation was silently overwritten in a loop.
"""

import threading
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import gurobipy as gp
    from gurobipy import GRB, quicksum
    HAS_GUROBI = True
except ImportError:
    HAS_GUROBI = False
    print("WARNING: Gurobi not found.  Install gurobipy to use this solver.")

from utils import load_ssp_instance


class BranchAndBendersCutSSP:
    """
    Solves the SSP via Branch-and-Benders-Cut using Gurobi lazy callbacks.

    Parameters
    ----------
    n_jobs            : int   – number of jobs
    n_tools           : int   – total distinct tools
    capacity          : int   – magazine capacity c
    tool_req          : dict  – tool_req[j] = list of tools required by job j
    worker_lp_reuse   : bool  – reuse DSP model across calls (default False)
    use_fractional_cuts : bool – add user cuts at LP nodes (default False)
    parallel          : bool  – multi-threaded B&B (default False)
    """

    def __init__(self, n_jobs, n_tools, capacity, tool_req,
                 worker_lp_reuse=False,
                 use_fractional_cuts=False,
                 parallel=False):
        self.n_jobs             = n_jobs
        self.n_tools            = n_tools
        self.capacity           = capacity
        self.tool_req           = tool_req
        self.worker_lp_reuse    = worker_lp_reuse
        self.use_fractional_cuts = use_fractional_cuts
        self.parallel           = parallel

        self._compute_pairwise_bounds()

        # Master problem model + variables
        self.model = None
        self.x     = {}   # x[i,j] arc variables
        self.theta = None # surrogate cost θ

        # Worker LP reuse: cached DSP model (single-threaded path)
        self._dsp_model = None
        self._dsp_lam   = None
        self._dsp_mu    = None
        self._dsp_nu    = None
        self._dsp_eta   = None
        # Thread-local storage for parallel path
        self._tls = threading.local()

        # Tracking
        self.best_solution   = None
        self.best_objective  = float('inf')
        self.iteration_count = 0
        self.cuts_added      = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Pre-computation
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_pairwise_bounds(self):
        """w_ij = max(0, |T_i ∪ T_j| − capacity)  for all ordered pairs (i,j)."""
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

        Variables  : x[i,j] ∈ {0,1},  θ ≥ 0
        Constraints: degree-1 in/out per node, initial lower bound θ ≥ Σ w_ij x_ij
        Dynamic    : SECs and Benders cuts added by callback

        When use_fractional_cuts=True, Params.PreCrush=1 is set so that
        cbCut() user cuts are post-processed correctly by Gurobi.
        """
        if not HAS_GUROBI:
            raise RuntimeError("Gurobi is required.  Please install gurobipy.")

        self.model = gp.Model("SSP_BranchAndBendersCut")
        if not verbose:
            self.model.setParam('OutputFlag', 0)

        n = self.n_jobs

        # ── Arc variables ────────────────────────────────────────────────────
        for i in range(n):
            for j in range(n):
                if i != j:
                    self.x[i, j] = self.model.addVar(
                        vtype=GRB.BINARY, name=f"x_{i}_{j}"
                    )

        self.theta = self.model.addVar(
            vtype=GRB.CONTINUOUS, lb=0.0, name="theta"
        )

        # ── Objective ─────────────────────────────────────────────────────────
        self.model.setObjective(self.theta, GRB.MINIMIZE)

        # ── Degree constraints ─────────────────────────────────────────────────
        for i in range(n):
            self.model.addConstr(
                quicksum(self.x[i, j] for j in range(n) if i != j) == 1,
                name=f"out_{i}"
            )
            self.model.addConstr(
                quicksum(self.x[j, i] for j in range(n) if j != i) == 1,
                name=f"in_{i}"
            )

        # ── Initial lower bound on θ ──────────────────────────────────────────
        self.model.addConstr(
            self.theta >= quicksum(
                self.w[i, j] * self.x[i, j]
                for i in range(n) for j in range(n) if i != j
            ),
            name="theta_lb"
        )

        # ── Solver settings ───────────────────────────────────────────────────
        self.model.Params.LazyConstraints = 1
        if self.use_fractional_cuts:
            self.model.Params.PreCrush = 1
        self.model.Params.Threads = 0 if self.parallel else 1

        if verbose:
            print(f"✓ Master Problem created: {n} jobs, {n*(n-1)} arc variables")
            print(f"  worker_lp_reuse={self.worker_lp_reuse}  "
                  f"use_fractional_cuts={self.use_fractional_cuts}  "
                  f"parallel={self.parallel}")

        return self.model

    # ─────────────────────────────────────────────────────────────────────────
    # Solution helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _find_subtours_from_sol(self, sol):
        """
        Detect all subtours directly from binary x-solution values.

        Parameters
        ----------
        sol : dict {(i,j): float}

        Returns
        -------
        list of lists – each inner list is a cycle of job indices with
        length < n_jobs.  Returns [] for a Hamiltonian cycle.
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
        Extract the Hamiltonian sequence from a subtour-free binary solution.
        Starts from job 0 and follows successor arcs.

        Returns list[int] of length n_jobs, or None if extraction fails.
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

    def _build_x_bar_from_sequence(self, sequence):
        """Convert a Hamiltonian sequence to a binary x̄ dict {(i,j): 1.0}."""
        n     = self.n_jobs
        x_bar = {}
        for k in range(n - 1):
            x_bar[sequence[k], sequence[k + 1]] = 1.0
        x_bar[sequence[-1], sequence[0]] = 1.0
        return x_bar

    # ─────────────────────────────────────────────────────────────────────────
    # Dual Subproblem – public entry point
    # ─────────────────────────────────────────────────────────────────────────

    def _solve_dual_subproblem(self, sequence):
        """
        Solve the DSP for a fixed integer sequence.

        Converts the sequence to x̄ and calls _solve_dsp_with_xbar().
        """
        if sequence is None:
            return None, {}
        return self._solve_dsp_with_xbar(self._build_x_bar_from_sequence(sequence))

    def _solve_dsp_with_xbar(self, x_bar):
        """
        Core DSP dispatcher.  x_bar may be integer (0/1) or fractional.

        Routes to:
        - _solve_dsp_reuse(x_bar)  if worker_lp_reuse=True
        - _solve_dsp_fresh(x_bar)  otherwise
        """
        if self.worker_lp_reuse:
            return self._solve_dsp_reuse(x_bar)
        return self._solve_dsp_fresh(x_bar)

    # ─────────────────────────────────────────────────────────────────────────
    # DSP – fresh build (default path)
    # ─────────────────────────────────────────────────────────────────────────

    def _solve_dsp_fresh(self, x_bar):
        """
        Build the DSP Gurobi model from scratch and solve.

        x_bar : dict {(i,j): float} – arc values (integer or fractional).

        Returns (obj_val, duals) or (None, {}) on failure.
        """
        n        = self.n_jobs
        T        = range(self.n_tools)
        tool_req = self.tool_req

        dsp = gp.Model("DSP")
        dsp.setParam('OutputFlag', 0)

        # ── Variables ────────────────────────────────────────────────────────
        lam = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in T:
                        lam[i, j, t] = dsp.addVar(
                            lb=0.0, vtype=GRB.CONTINUOUS, name=f"lam_{i}_{j}_{t}"
                        )

        mu  = {j: dsp.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name=f"mu_{j}")
               for j in range(n)}
        nu  = {}
        eta = {}
        for j in range(n):
            for t in T:
                nu[j, t]  = dsp.addVar(lb=-GRB.INFINITY, vtype=GRB.CONTINUOUS,
                                       name=f"nu_{j}_{t}")
                eta[j, t] = dsp.addVar(lb=-GRB.INFINITY, vtype=GRB.CONTINUOUS,
                                       name=f"eta_{j}_{t}")

        # ── Objective ────────────────────────────────────────────────────────
        obj = quicksum(
            (x_bar.get((i, j), 0.0) - 1.0) * lam[i, j, t]
            for i in range(n) for j in range(n) if i != j
            for t in T
        )
        obj += quicksum(-self.capacity * mu[j] for j in range(n))
        obj += quicksum(nu[j, t] for j in range(n) for t in tool_req.get(j, []))
        dsp.setObjective(obj, GRB.MAXIMIZE)

        # ── Constraints for y_jt ≥ 0 ────────────────────────────────────────
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                nu_term = nu[j, t] if t in Tj else 0
                lhs = (
                    -mu[j]
                    - quicksum(lam[i, j, t] for i in range(n) if i != j)
                    + quicksum(lam[j, k, t] for k in range(n) if k != j)
                    + nu_term
                )
                dsp.addConstr(lhs <= 0, name=f"dy_{j}_{t}")

        # ── Constraints for z_jt ≥ 0 ────────────────────────────────────────
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                eta_term = eta[j, t] if t not in Tj else 0
                rhs = 1.0 if t in Tj else 0.0
                lhs = (
                    quicksum(lam[i, j, t] for i in range(n) if i != j)
                    + eta_term
                )
                dsp.addConstr(lhs <= rhs, name=f"dz_{j}_{t}")

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
    # DSP – worker LP reuse path
    # ─────────────────────────────────────────────────────────────────────────

    def _build_dsp_model_once(self):
        """
        Build a Gurobi DSP model with fixed structure but zero-initialised
        objective coefficients for λ.  The constraints (which never change
        between callback calls) are added once here.  The lam objective
        coefficients are updated in _solve_dsp_reuse() per call.

        Uses dual simplex (Method=1) so that the LP basis warm-starts across
        objective changes.

        Returns (model, lam_dict, mu_dict, nu_dict, eta_dict).
        """
        n        = self.n_jobs
        T        = range(self.n_tools)
        tool_req = self.tool_req

        dsp = gp.Model("DSP_reuse")
        dsp.setParam('OutputFlag', 0)
        dsp.setParam('Method', 1)   # dual simplex – best for re-optimisation

        # ── Variables (obj for lam left at 0.0; updated per call) ────────────
        lam = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in T:
                        lam[i, j, t] = dsp.addVar(
                            lb=0.0, obj=0.0,
                            vtype=GRB.CONTINUOUS, name=f"lam_{i}_{j}_{t}"
                        )

        mu = {}
        for j in range(n):
            mu[j] = dsp.addVar(lb=0.0, obj=-self.capacity,
                               vtype=GRB.CONTINUOUS, name=f"mu_{j}")

        nu  = {}
        eta = {}
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                nu_obj = 1.0 if t in Tj else 0.0
                nu[j, t]  = dsp.addVar(lb=-GRB.INFINITY, obj=nu_obj,
                                       vtype=GRB.CONTINUOUS, name=f"nu_{j}_{t}")
                eta[j, t] = dsp.addVar(lb=-GRB.INFINITY, obj=0.0,
                                       vtype=GRB.CONTINUOUS, name=f"eta_{j}_{t}")

        dsp.ModelSense = GRB.MAXIMIZE

        # ── Fixed constraints ────────────────────────────────────────────────
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                nu_term = nu[j, t] if t in Tj else 0
                lhs = (
                    -mu[j]
                    - quicksum(lam[i, j, t] for i in range(n) if i != j)
                    + quicksum(lam[j, k, t] for k in range(n) if k != j)
                    + nu_term
                )
                dsp.addConstr(lhs <= 0, name=f"dy_{j}_{t}")

        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                eta_term = eta[j, t] if t not in Tj else 0
                rhs = 1.0 if t in Tj else 0.0
                lhs = (
                    quicksum(lam[i, j, t] for i in range(n) if i != j)
                    + eta_term
                )
                dsp.addConstr(lhs <= rhs, name=f"dz_{j}_{t}")

        dsp.update()
        return dsp, lam, mu, nu, eta

    def _get_dsp_model(self):
        """
        Return the cached DSP model (building it the first time).

        When parallel=True, returns a thread-local model so that concurrent
        MIPNODE callbacks on different threads don't share state.
        """
        if self.parallel:
            tls = self._tls
            if not hasattr(tls, 'dsp_model'):
                (tls.dsp_model, tls.dsp_lam,
                 tls.dsp_mu, tls.dsp_nu, tls.dsp_eta) = self._build_dsp_model_once()
            return tls.dsp_model, tls.dsp_lam, tls.dsp_mu, tls.dsp_nu, tls.dsp_eta
        else:
            if self._dsp_model is None:
                (self._dsp_model, self._dsp_lam,
                 self._dsp_mu, self._dsp_nu, self._dsp_eta) = self._build_dsp_model_once()
            return (self._dsp_model, self._dsp_lam,
                    self._dsp_mu, self._dsp_nu, self._dsp_eta)

    def _solve_dsp_reuse(self, x_bar):
        """
        Update λ objective coefficients in the cached DSP model and re-solve.

        Only the (x̄_ij − 1) terms change between calls.  The μ, ν, η objective
        coefficients and all constraints are static and never rebuilt.

        Returns (obj_val, duals) or (None, {}) on failure.
        """
        dsp, lam, mu, nu, eta = self._get_dsp_model()

        # Update only the λ objective coefficients
        for (i, j, t), v in lam.items():
            v.obj = x_bar.get((i, j), 0.0) - 1.0
        dsp.update()
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
    # Benders cut generation
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_benders_cut(self, duals):
        """
        Build the Benders optimality cut from DSP dual variables.

        Cut:  θ ≥ Σ_{i,j,t} (x_ij − 1) λ̄_ijt  −  Σ_j c μ̄_j  +  Σ_{j,t∈T_j} ν̄_jt

        Rearranged as  θ ≥ Σ_{i,j} coeff_ij · x_ij  +  cut_rhs:

            coeff_ij = Σ_t λ̄_ijt
            cut_rhs  = −Σ_{i,j} coeff_ij  −  c Σ_j μ̄_j  +  Σ_{j,t∈T_j} ν̄_jt

        Returns
        -------
        cut_expr : Gurobi LinExpr  (variable part)
        cut_rhs  : float           (constant part)
        """
        n = self.n_jobs

        coeff = {
            (i, j): sum(duals.get(('lambda', i, j, t), 0.0)
                        for t in range(self.n_tools))
            for i in range(n) for j in range(n) if i != j
        }

        cut_rhs = 0.0
        for j in range(n):
            cut_rhs -= self.capacity * duals.get(('mu', j), 0.0)
        for j in range(n):
            for t in self.tool_req.get(j, []):
                cut_rhs += duals.get(('nu', j, t), 0.0)
        for c in coeff.values():
            cut_rhs -= c   # from the (x_ij − 1) factor

        cut_expr = quicksum(
            coeff[i, j] * self.x[i, j]
            for i in range(n) for j in range(n) if i != j
        )

        return cut_expr, cut_rhs

    # ─────────────────────────────────────────────────────────────────────────
    # Callback
    # ─────────────────────────────────────────────────────────────────────────

    def _callback(self, model, where):
        """
        Gurobi callback.

        GRB.Callback.MIPSOL  – integer incumbent.
            1. Detect subtours → add SECs (lazy).
            2. Solve DSP → add Benders cut if violated (lazy).

        GRB.Callback.MIPNODE – LP node (only when use_fractional_cuts=True).
            1. Skip subtour check.
            2. Solve DSP with fractional x̄ → add Benders user cut if violated.
        """
        try:
            if where == GRB.Callback.MIPSOL:
                self._handle_integer(model)
            elif where == GRB.Callback.MIPNODE and self.use_fractional_cuts:
                if int(model.cbGet(GRB.Callback.MIPNODE_STATUS)) == GRB.OPTIMAL:
                    self._handle_fractional(model)
        except Exception as exc:
            import traceback
            print(f"[Callback error] {exc}")
            traceback.print_exc()

    def _handle_integer(self, model):
        """Process an integer incumbent (MIPSOL)."""
        self.iteration_count += 1

        sol = {
            (i, j): model.cbGetSolution(var)
            for (i, j), var in self.x.items()
        }
        theta_val = model.cbGetSolution(self.theta)

        # ── Step A: Subtour check ───────────────────────────────────────────
        subtours = self._find_subtours_from_sol(sol)
        if subtours:
            for st in subtours:
                model.cbLazy(
                    quicksum(
                        self.x[i, j]
                        for i in st for j in st
                        if i != j and (i, j) in self.x
                    ) <= len(st) - 1
                )
                self.cuts_added += 1
            return  # do not solve DSP when subtours exist

        # ── Step B: Hamiltonian sequence ────────────────────────────────────
        sequence = self._get_sequence_from_sol(sol)
        if sequence is None:
            return

        # ── Step C: Solve DSP ────────────────────────────────────────────────
        dsp_obj, duals = self._solve_dsp_with_xbar(sol)
        if dsp_obj is None:
            return

        # ── Step D: Benders lazy cut ─────────────────────────────────────────
        if dsp_obj > theta_val + 1e-6:
            cut_expr, cut_rhs = self._generate_benders_cut(duals)
            model.cbLazy(self.theta >= cut_expr + cut_rhs)
            self.cuts_added += 1

        if dsp_obj < self.best_objective:
            self.best_objective = dsp_obj
            self.best_solution  = sequence[:]

    def _handle_fractional(self, model):
        """
        Process a fractional LP node (MIPNODE) to add Benders user cuts.

        Subtour checks are skipped for fractional solutions.  The DSP is
        solved directly with fractional x̄ values; the resulting cut is valid
        because the Benders inequality holds for any x̄ ∈ [0,1]^{n×n}.

        User cuts are added via model.cbCut() (requires PreCrush=1).
        """
        sol = {
            (i, j): model.cbGetNodeRel(var)
            for (i, j), var in self.x.items()
        }
        theta_val = model.cbGetNodeRel(self.theta)

        dsp_obj, duals = self._solve_dsp_with_xbar(sol)
        if dsp_obj is None:
            return

        if dsp_obj > theta_val + 1e-6:
            cut_expr, cut_rhs = self._generate_benders_cut(duals)
            model.cbCut(self.theta >= cut_expr + cut_rhs)
            self.cuts_added += 1

    # ─────────────────────────────────────────────────────────────────────────
    # Solve
    # ─────────────────────────────────────────────────────────────────────────

    def solve(self, time_limit=3600, verbose=True):
        """
        Run Branch-and-Benders-Cut to global optimality (or time limit).

        Returns
        -------
        status   : str   – 'OPTIMAL', 'TIME_LIMIT', or Gurobi status code
        obj_val  : float – best-found objective (total tool switches)
        sequence : list  – job sequence (0-indexed)
        """
        if self.model is None:
            self.build_master_problem(verbose=verbose)

        self.model.Params.TimeLimit       = time_limit
        self.model.Params.LazyConstraints = 1
        if self.use_fractional_cuts:
            self.model.Params.PreCrush = 1
        self.model.Params.Threads = 0 if self.parallel else 1
        if not verbose:
            self.model.Params.OutputFlag = 0

        self.model.optimize(self._callback)

        # ── Extract result ────────────────────────────────────────────────────
        if self.model.status in (GRB.OPTIMAL, GRB.TIME_LIMIT):
            status  = 'OPTIMAL' if self.model.status == GRB.OPTIMAL else 'TIME_LIMIT'
            obj_val = self.model.objVal
            sol     = {(i, j): var.X for (i, j), var in self.x.items()}
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
            print(f"Worker LP reuse : {self.worker_lp_reuse}")
            print(f"Fractional cuts : {self.use_fractional_cuts}")
            print(f"Parallel        : {self.parallel}")
            print(f"{sep}\n")

        return status, obj_val, sequence


# ─────────────────────────────────────────────────────────────────────────────
# Convenience wrapper
# ─────────────────────────────────────────────────────────────────────────────

def solve_ssp_branch_and_benders(instance_path, time_limit=3600, verbose=True,
                                  worker_lp_reuse=False,
                                  use_fractional_cuts=False,
                                  parallel=False):
    """
    Load an SSP instance file and solve with Branch-and-Benders-Cut (Gurobi).

    Parameters
    ----------
    instance_path       : str
    time_limit          : int   – seconds (default 3600)
    verbose             : bool
    worker_lp_reuse     : bool  – reuse DSP model (default False)
    use_fractional_cuts : bool  – add user cuts at LP nodes (default False)
    parallel            : bool  – multi-threaded B&B (default False)

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

    solver = BranchAndBendersCutSSP(
        n_jobs, n_tools, capacity, tool_req,
        worker_lp_reuse=worker_lp_reuse,
        use_fractional_cuts=use_fractional_cuts,
        parallel=parallel
    )
    solver.build_master_problem(verbose=verbose)
    return solver.solve(time_limit=time_limit, verbose=verbose)


if __name__ == "__main__":
    instance_file = (
        Path(__file__).parent.parent / "Instances" / "Shankar" / "shankar-example.txt"
    )
    if instance_file.exists():
        solve_ssp_branch_and_benders(str(instance_file), verbose=True)
    else:
        print(f"Instance file not found: {instance_file}")
