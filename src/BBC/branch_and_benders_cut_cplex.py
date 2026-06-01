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

Optional performance features
------------------------------
worker_lp_reuse : bool (default False)
    When True, one cplex.Cplex DSP model is built per thread at first call and reused
    by updating only the objective coefficients before each re-solve.  This avoids
    repeated model construction overhead inside the callback, following the pattern
    from IBM's bendersatsp2.py example.

use_fractional_cuts : bool (default False)
    When True, the callback also fires at LP-relaxation nodes
    (Context.id.relaxation) and adds Benders *user cuts* via
    context.add_user_cut().  This tightens the LP bound before branching and can
    substantially reduce the B&B tree size.  The same DSP is used for both integer
    and fractional solutions.

parallel : bool (default False)
    When True, CPLEX may use multiple threads for B&B.  Thread-safety is achieved
    via the Context.id.thread_up / thread_down mechanism: one DSP model is allocated
    per CPLEX worker thread in a thread_id → model dict, and cleaned up on
    thread_down.  When False, CPLEX is restricted to 1 thread (MIP.strategy.search
    is not constrained; the modern generic callback supports parallel search).

Dependencies
------------
    cplex      – raw IBM CPLEX Python API (ships with the CPLEX installation)
    docplex    – used ONLY for solving the DSP LP when worker_lp_reuse=False
                 (no callbacks needed there); falls back to Gurobi if unavailable
    gurobipy   – optional fallback for the DSP
    numpy      – required

Install notes:
    pip install cplex docplex   (requires an IBM CPLEX installation on the system)
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Solver imports ────────────────────────────────────────────────────────────
try:
    import cplex
    from cplex import SparsePair
    from cplex.callbacks import Context
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
from bbc_common import BBCSolverMixin


# ─────────────────────────────────────────────────────────────────────────────
# Modern generic callback (admipex8 / bendersatsp2 style)
# ─────────────────────────────────────────────────────────────────────────────

class BendersCutCallback:
    """
    CPLEX generic callback.

    Fires on:
      - Context.id.candidate   : integer-feasible incumbent
      - Context.id.relaxation  : LP relaxation node  (only if use_fractional_cuts)
      - Context.id.thread_up   : new worker thread started  (only if parallel)
      - Context.id.thread_down : worker thread ending        (only if parallel)

    Registration::

        cpx.set_callback(cb_instance, contextmask)

    At each integer incumbent:
    1. Extract x values and θ.
    2. Detect subtours via _find_subtours_from_sol().
       - If subtours exist → call context.reject_candidate() with SECs.
    3. No subtours → extract Hamiltonian sequence → solve DSP.
    4. DSP value > θ → inject Benders cut via context.reject_candidate().

    At each LP relaxation node (use_fractional_cuts=True):
    1. Extract fractional x values.
    2. Solve DSP with fractional x̄.
    3. DSP value > θ_rel → inject user cut via context.add_user_cut().
    """

    def __init__(self, solver):
        self.solver          = solver
        self.cuts_added      = 0
        self.iteration_count = 0
        self.best_objective  = float('inf')
        self.best_solution   = None

        # Thread-local DSP storage (used when parallel=True)
        # Maps thread_id (int) → cplex DSP model (or dict of components)
        self._thread_dsps: dict = {}

    # ── Entry point ───────────────────────────────────────────────────────────

    def invoke(self, context):
        """Entry point called by CPLEX for every registered context event."""
        try:
            ctx_id = context.get_id()

            # ── Thread lifecycle (parallel only) ──────────────────────────
            if ctx_id & Context.id.thread_up:
                if self.solver.parallel:
                    tid = context.get_int_info(Context.info.thread_id)
                    self._thread_dsps[tid] = self.solver._build_dsp_cplex_model()
                return

            if ctx_id & Context.id.thread_down:
                if self.solver.parallel:
                    tid = context.get_int_info(Context.info.thread_id)
                    dsp_obj = self._thread_dsps.pop(tid, None)
                    if dsp_obj is not None:
                        dsp_obj['model'].end()
                return

            # ── Integer candidate ─────────────────────────────────────────
            if ctx_id & Context.id.candidate:
                if context.is_candidate_point():
                    tid = (context.get_int_info(Context.info.thread_id)
                           if self.solver.parallel else None)
                    self._handle_candidate(context, tid)
                return

            # ── LP relaxation node (fractional cuts) ─────────────────────
            if ctx_id & Context.id.relaxation:
                if self.solver.use_fractional_cuts:
                    tid = (context.get_int_info(Context.info.thread_id)
                           if self.solver.parallel else None)
                    self._handle_relaxation(context, tid)
                return

        except Exception as exc:
            print(f"[CPLEX callback error] {exc}")
            import traceback
            traceback.print_exc()

    # ── Integer incumbent handler ─────────────────────────────────────────────

    def _handle_candidate(self, context, tid=None):
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
            return

        # ── Step B: Extract Hamiltonian sequence ──────────────────────────
        sequence = solver._get_sequence_from_sol(sol)
        if sequence is None:
            return

        x_bar = solver._build_x_bar_from_sequence(sequence)

        # ── Step C: Solve DSP ─────────────────────────────────────────────
        dsp_obj, duals = solver._solve_dsp_with_xbar(x_bar, tid=tid)
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

    # ── LP relaxation handler (fractional cuts) ───────────────────────────────

    def _handle_relaxation(self, context, tid=None):
        """
        Called at LP relaxation nodes when use_fractional_cuts=True.
        Solves the DSP with fractional x̄ and injects a user cut if violated.
        """
        solver = self.solver
        n      = solver.n_jobs
        n_vars = solver.n_vars

        # Extract relaxation values
        try:
            all_vals = context.get_relaxation_point(list(range(n_vars)))
        except Exception:
            return

        theta_val = all_vals[solver.theta_idx]

        x_bar = {}
        for (i, j) in solver.x_pairs:
            v = all_vals[solver.x_idx_map[i, j]]
            if v > 1e-8:
                x_bar[i, j] = v

        if not x_bar:
            return

        # Solve DSP with fractional x̄
        dsp_obj, duals = solver._solve_dsp_with_xbar(x_bar, tid=tid)
        if dsp_obj is None:
            return

        # Add user cut if violated
        if dsp_obj > theta_val + 1e-6:
            cut_sp, cut_rhs = solver._build_benders_cut_sparsepair(duals)
            try:
                context.add_user_cut(
                    cut_sp,
                    sense='G',
                    rhs=cut_rhs,
                    local=False,
                    purgeable=True
                )
                self.cuts_added += 1
            except Exception:
                pass  # Not all LP nodes support user cuts


# ─────────────────────────────────────────────────────────────────────────────
# Solver class
# ─────────────────────────────────────────────────────────────────────────────

class BranchAndBendersCutSSP_CPLEX(BBCSolverMixin):
    """
    Branch-and-Benders-Cut solver using IBM CPLEX (raw cplex API).

    Master Problem  : TSP with surrogate cost θ, built with cplex.Cplex()
    Callback        : Modern generic callback (cpx.set_callback)
    DSP             : Solved with raw cplex.Cplex (if worker_lp_reuse or as fresh
                      model), docplex, or Gurobi fallback.

    Parameters
    ----------
    n_jobs, n_tools, capacity, tool_req : problem data
    worker_lp_reuse : bool
        Build one DSP model per thread and reuse it across callback calls,
        updating only the objective coefficients (bendersatsp2.py pattern).
    use_fractional_cuts : bool
        Fire the callback at LP relaxation nodes and add Benders user cuts.
    parallel : bool
        Allow CPLEX to use multiple B&B threads.  Each thread gets its own DSP
        model via thread_up / thread_down.
    """

    def __init__(self, n_jobs, n_tools, capacity, tool_req,
                 worker_lp_reuse=False, use_fractional_cuts=False, parallel=False):
        self.n_jobs              = n_jobs
        self.n_tools             = n_tools
        self.capacity            = capacity
        self.tool_req            = tool_req
        self.worker_lp_reuse     = worker_lp_reuse
        self.use_fractional_cuts = use_fractional_cuts
        self.parallel            = parallel

        self._compute_pairwise_bounds()

        # CPLEX model and variable index bookkeeping
        self.cpx       = None
        self.theta_idx = None
        self.x_idx_map = {}    # (i,j) → column index
        self.x_pairs   = []    # ordered list of (i,j) arcs
        self.n_vars    = 0

        # Shared (non-parallel) DSP model when worker_lp_reuse=True
        self._shared_dsp = None   # dict: {model, lam_idx, mu_idx, nu_idx, eta_idx, n_lam}

        # Tracking
        self.best_solution   = None
        self.best_objective  = float('inf')
        self.cuts_added      = 0
        self.iteration_count = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Pre-computation
    # ─────────────────────────────────────────────────────────────────────────

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
        for k, (i, j) in enumerate(self.x_pairs):
            self.x_idx_map[i, j] = k + 1

        self.n_vars = 1 + n_arcs

        # Minimise θ
        self.cpx.objective.set_sense(self.cpx.objective.sense.minimize)

        # ── Degree constraints ─────────────────────────────────────────────
        for i in range(n):
            out_idx = [self.x_idx_map[i, j] for j in range(n) if i != j]
            self.cpx.linear_constraints.add(
                lin_expr = [SparsePair(out_idx, [1.0] * len(out_idx))],
                senses   = ['E'],
                rhs      = [1.0],
                names    = [f'out_{i}']
            )
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

        # ── Solver parameters ──────────────────────────────────────────────
        if not self.parallel:
            self.cpx.parameters.threads.set(1)

        if self.use_fractional_cuts:
            # Allow CPLEX to use user cuts at LP nodes
            self.cpx.parameters.preprocessing.presolve.set(0)

        if verbose:
            print(f"Master Problem built: {n} jobs, {n_arcs} arc variables")

    # ─────────────────────────────────────────────────────────────────────────
    # Solution helpers (shared with callback)
    # ─────────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────────
    # DSP routing
    # ─────────────────────────────────────────────────────────────────────────

    def _solve_dsp_with_xbar(self, x_bar, tid=None):
        """
        Dispatch to fresh or reuse DSP solver.

        Parameters
        ----------
        x_bar : dict {(i,j): float}
        tid   : int or None – thread id (used with parallel + worker_lp_reuse)

        Returns
        -------
        (obj_val, duals) or (None, {})
        """
        if self.worker_lp_reuse:
            return self._solve_dsp_reuse(x_bar, tid=tid)
        else:
            return self._solve_dsp_fresh(x_bar)

    # ── Worker LP reuse ───────────────────────────────────────────────────────

    def _build_dsp_cplex_model(self):
        """
        Build a raw cplex.Cplex LP for the DSP.

        The model is built with lam objective coefficients = 0 (to be updated
        per call).  Variable ordering is fixed so we can update by column index.

        Returns
        -------
        dict with keys:
          model     – cplex.Cplex instance
          lam_idx   – {(i,j,t): col_index}
          mu_idx    – {j: col_index}
          nu_idx    – {(j,t): col_index}
          eta_idx   – {(j,t): col_index}
          n_cols    – total number of columns
        """
        n        = self.n_jobs
        T        = list(range(self.n_tools))
        tool_req = self.tool_req

        dsp = cplex.Cplex()
        dsp.set_log_stream(None)
        dsp.set_results_stream(None)
        dsp.set_warning_stream(None)
        dsp.objective.set_sense(dsp.objective.sense.maximize)

        # ── Variables ─────────────────────────────────────────────────────
        lam_idx = {}
        mu_idx  = {}
        nu_idx  = {}
        eta_idx = {}

        col_names = []
        col_obj   = []
        col_lb    = []
        col_ub    = []

        def add_var(name, obj, lb, ub=cplex.infinity):
            idx = len(col_names)
            col_names.append(name)
            col_obj.append(obj)
            col_lb.append(lb)
            col_ub.append(ub)
            return idx

        # lam[i,j,t] >= 0; obj = 0 (updated per call)
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in T:
                        lam_idx[i, j, t] = add_var(f"lam_{i}_{j}_{t}", 0.0, 0.0)

        # mu[j] >= 0; obj = -capacity
        for j in range(n):
            mu_idx[j] = add_var(f"mu_{j}", -float(self.capacity), 0.0)

        # nu[j,t] FREE; obj = 1 if t in T_j else 0
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                obj_v = 1.0 if t in Tj else 0.0
                nu_idx[j, t] = add_var(f"nu_{j}_{t}", obj_v,
                                       -cplex.infinity, cplex.infinity)

        # eta[j,t] FREE; obj = 0
        for j in range(n):
            for t in T:
                eta_idx[j, t] = add_var(f"eta_{j}_{t}", 0.0,
                                        -cplex.infinity, cplex.infinity)

        n_cols = len(col_names)
        dsp.variables.add(
            obj   = col_obj,
            lb    = col_lb,
            ub    = col_ub,
            names = col_names
        )

        # ── Constraints for y_jt >= 0 ─────────────────────────────────────
        # dual of y_jt:  -mu_j - Σ_i lam_ijt + Σ_k lam_jkt + nu_jt <= 0
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                indices = []
                coeffs  = []

                indices.append(mu_idx[j]); coeffs.append(-1.0)

                for i in range(n):
                    if i != j:
                        indices.append(lam_idx[i, j, t]); coeffs.append(-1.0)

                for k in range(n):
                    if k != j:
                        indices.append(lam_idx[j, k, t]); coeffs.append(1.0)

                if t in Tj:
                    indices.append(nu_idx[j, t]); coeffs.append(1.0)

                dsp.linear_constraints.add(
                    lin_expr = [SparsePair(indices, coeffs)],
                    senses   = ['L'],
                    rhs      = [0.0],
                    names    = [f'dy_{j}_{t}']
                )

        # ── Constraints for z_jt >= 0 ─────────────────────────────────────
        # dual of z_jt:  Σ_i lam_ijt + eta_jt <= rhs  (rhs = 1 if t in T_j else 0)
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                indices = []
                coeffs  = []

                for i in range(n):
                    if i != j:
                        indices.append(lam_idx[i, j, t]); coeffs.append(1.0)

                if t not in Tj:
                    indices.append(eta_idx[j, t]); coeffs.append(1.0)

                rhs = 1.0 if t in Tj else 0.0
                dsp.linear_constraints.add(
                    lin_expr = [SparsePair(indices, coeffs)],
                    senses   = ['L'],
                    rhs      = [rhs],
                    names    = [f'dz_{j}_{t}']
                )

        # Use dual simplex for efficient re-solves
        dsp.parameters.lpmethod.set(dsp.parameters.lpmethod.values.dual)

        return {
            'model'   : dsp,
            'lam_idx' : lam_idx,
            'mu_idx'  : mu_idx,
            'nu_idx'  : nu_idx,
            'eta_idx' : eta_idx,
            'n_cols'  : n_cols,
        }

    def _get_dsp_model(self, tid=None):
        """
        Return the appropriate DSP model dict.

        If parallel, return the thread-local model from _thread_dsps[tid].
        Otherwise return (or lazily create) the shared model.
        """
        if self.parallel and tid is not None:
            # Thread model should have been created in thread_up
            if tid not in self._cb_ref._thread_dsps:
                self._cb_ref._thread_dsps[tid] = self._build_dsp_cplex_model()
            return self._cb_ref._thread_dsps[tid]
        else:
            if self._shared_dsp is None:
                self._shared_dsp = self._build_dsp_cplex_model()
            return self._shared_dsp

    def _solve_dsp_reuse(self, x_bar, tid=None):
        """
        Solve DSP by updating only lam objective coefficients, then re-solving.

        Parameters
        ----------
        x_bar : dict {(i,j): float}
        tid   : int or None

        Returns
        -------
        (obj_val, duals) or (None, {})
        """
        dsp_data = self._get_dsp_model(tid=tid)
        dsp      = dsp_data['model']
        lam_idx  = dsp_data['lam_idx']
        mu_idx   = dsp_data['mu_idx']
        nu_idx   = dsp_data['nu_idx']
        eta_idx  = dsp_data['eta_idx']

        # Update lam objective coefficients: coeff = x_bar.get((i,j), 0) - 1
        updates = []
        for (i, j, t), col in lam_idx.items():
            coeff = x_bar.get((i, j), 0.0) - 1.0
            updates.append((col, coeff))
        dsp.objective.set_linear(updates)

        dsp.solve()
        status = dsp.solution.get_status()
        # 1 = optimal
        if status != 1:
            return None, {}

        obj_val = dsp.solution.get_objective_value()
        all_vals = dsp.solution.get_values()

        duals = {}
        for (i, j, t), col in lam_idx.items():
            duals['lambda', i, j, t] = all_vals[col]
        for j, col in mu_idx.items():
            duals['mu', j] = all_vals[col]
        for (j, t), col in nu_idx.items():
            duals['nu', j, t] = all_vals[col]
        for (j, t), col in eta_idx.items():
            duals['eta', j, t] = all_vals[col]

        return obj_val, duals

    # ── Fresh DSP (docplex or Gurobi) ─────────────────────────────────────────

    def _solve_dsp_fresh(self, x_bar):
        """Build and solve the DSP from scratch for a given x̄."""
        if HAS_DOCPLEX:
            return self._solve_dsp_docplex(x_bar)
        elif HAS_GUROBI:
            return self._solve_dsp_gurobi(x_bar)
        elif HAS_CPLEX:
            # Build a fresh raw CPLEX DSP model
            dsp_data = self._build_dsp_cplex_model()
            # Set lam obj to x_bar values - 1
            updates = []
            for (i, j, t), col in dsp_data['lam_idx'].items():
                coeff = x_bar.get((i, j), 0.0) - 1.0
                updates.append((col, coeff))
            dsp_data['model'].objective.set_linear(updates)
            dsp_data['model'].solve()
            status = dsp_data['model'].solution.get_status()
            if status != 1:
                dsp_data['model'].end()
                return None, {}
            obj_val  = dsp_data['model'].solution.get_objective_value()
            all_vals = dsp_data['model'].solution.get_values()
            duals = {}
            for (i, j, t), col in dsp_data['lam_idx'].items():
                duals['lambda', i, j, t] = all_vals[col]
            for j, col in dsp_data['mu_idx'].items():
                duals['mu', j] = all_vals[col]
            for (j, t), col in dsp_data['nu_idx'].items():
                duals['nu', j, t] = all_vals[col]
            for (j, t), col in dsp_data['eta_idx'].items():
                duals['eta', j, t] = all_vals[col]
            dsp_data['model'].end()
            return obj_val, duals
        else:
            raise RuntimeError(
                "No LP solver available for the DSP.  "
                "Install docplex, gurobipy, or cplex."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Dual subproblem entry point (used when worker_lp_reuse=False)
    # ─────────────────────────────────────────────────────────────────────────

    def _solve_dual_subproblem(self, sequence):
        """Solve the Dual LP for a fixed sequence (fresh model)."""
        if sequence is None:
            return None, {}
        x_bar = self._build_x_bar_from_sequence(sequence)
        return self._solve_dsp_fresh(x_bar)

    # ─────────────────────────────────────────────────────────────────────────
    # Benders cut assembly (SparsePair form for CPLEX)
    # ─────────────────────────────────────────────────────────────────────────

    def _build_benders_cut_sparsepair(self, duals):
        """
        Convert Benders dual variables into a cplex.SparsePair + rhs.

        The cut is:
            θ ≥ Σ_{i,j,t} (x_ij - 1) λ̄_ijt  - Σ_j c μ̄_j  + Σ_{j,t∈T_j} ν̄_jt

        Rearranged as  θ - Σ coeff_ij x_ij ≥ cut_rhs :

        Returns
        -------
        sp       : cplex.SparsePair
        cut_rhs  : float
        """
        n = self.n_jobs

        coeff = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    coeff[i, j] = sum(
                        duals.get(('lambda', i, j, t), 0.0)
                        for t in range(self.n_tools)
                    )

        cut_rhs = 0.0
        for j in range(n):
            cut_rhs -= self.capacity * duals.get(('mu', j), 0.0)
        for j in range(n):
            for t in self.tool_req.get(j, []):
                cut_rhs += duals.get(('nu', j, t), 0.0)
        for (i, j), c in coeff.items():
            cut_rhs -= c

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
        obj_val  : float or None
        sequence : list[int] or None
        """
        if self.cpx is None:
            self.build_master_problem(verbose=verbose)

        self.cpx.parameters.timelimit.set(float(time_limit))

        # ── Register modern generic callback ─────────────────────────────
        cb = BendersCutCallback(self)
        # Keep a back-reference so _get_dsp_model can access _thread_dsps
        self._cb_ref = cb

        context_mask = Context.id.candidate
        if self.parallel:
            context_mask |= Context.id.thread_up | Context.id.thread_down
        if self.use_fractional_cuts:
            context_mask |= Context.id.relaxation

        self.cpx.set_callback(cb, context_mask)

        # ── Solve ─────────────────────────────────────────────────────────
        self.cpx.solve()

        # ── Extract result ────────────────────────────────────────────────
        status_code = self.cpx.solution.get_status()
        status_str  = self.cpx.solution.status[status_code]

        try:
            obj_val  = self.cpx.solution.get_objective_value()
            all_vals = self.cpx.solution.get_values()
            sol      = {(i, j): all_vals[self.x_idx_map[i, j]] for (i, j) in self.x_pairs}
            sequence = self._get_sequence_from_sol(sol)
        except Exception:
            obj_val    = cb.best_objective if cb.best_objective < float('inf') else None
            sequence   = cb.best_solution
            status_str = 'NO_SOLUTION'

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
