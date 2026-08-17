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
import time
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

# New acceleration modules (2026-07): conflict-graph cuts + HGS primal heuristic.
# Imported defensively so the solver still loads if they are absent.
try:
    import conflict_cuts as _cc
except Exception:
    _cc = None
try:
    import hgs_heuristic as _hgs
except Exception:
    _hgs = None


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
    3. No subtours → extract Hamiltonian sequence.
       a. use_combinatorial_cuts=True  → KTNS cut (cheap, weaker).
       b. use_combinatorial_cuts=False → solve DSP LP, add Benders optimality cut.
    4. Cut violated → inject via context.reject_candidate().

    At each LP relaxation node (use_fractional_cuts=True):
    1. Extract fractional x values.
    2. Solve DSP LP with fractional x̄.
    3. DSP value > θ_rel → inject user cut via context.add_user_cut().
    """

    def __init__(self, solver):
        self.solver          = solver
        self.iteration_count = 0
        self.best_objective  = float('inf')
        self.best_solution   = None

        # ── Cut counters (separate for diagnostics) ───────────────────────
        self.sec_cuts_added      = 0   # subtour elimination constraints
        self.benders_cuts_added  = 0   # LP Benders optimality cuts
        self.comb_cuts_added     = 0   # combinatorial (KTNS-based) cuts
        self.frac_cuts_added     = 0   # fractional LP user cuts
        # total for backward compat
        self.cuts_added          = 0

        # ── DEBUG: fractional-cut diagnostics (2026-07; remove when resolved) ──
        self.dbg_relax_calls = 0   # times _handle_relaxation entered
        self.dbg_xbar_empty  = 0   # skipped: no fractional arc in x_bar
        self.dbg_dsp_none    = 0   # DSP returned None (non-optimal / failed)
        self.dbg_dsp_ok      = 0   # DSP returned a finite value
        self.dbg_violated    = 0   # dsp_obj > theta_val + 1e-6  (cut IS violated)
        self.dbg_add_failed  = 0   # add_user_cut raised (violated but not added)
        self.dbg_max_excess  = float('-inf')  # max(dsp_obj - theta_val) seen
        self.dbg_add_err     = None  # first add_user_cut failure repr (if any)

        # ── Convergence log: list of (elapsed_s, theta, best_primal) ─────
        self.convergence_log: list = []
        # True root LP relaxation: best_bound captured at root node (node_count==0),
        # frozen the moment node_count transitions to >=1.
        # This correctly reflects LP bound AFTER frac cuts (if any) but BEFORE branching.
        self.root_lp_bound: float  = None
        self._root_lp_last: float  = None   # running update while still at root
        self._root_lp_locked: bool = False  # True once we've left the root
        self._t0: float            = time.perf_counter()

    # ── Entry point ───────────────────────────────────────────────────────────

    def invoke(self, context):
        """Entry point called by CPLEX for every registered context event."""
        try:
            ctx_id = context.get_id()

            # ── Thread lifecycle (parallel only) ──────────────────────────
            # _thread_dsps lives on the solver (not the callback) to avoid
            # any race between callback construction and thread startup.
            if ctx_id & Context.id.thread_up:
                if self.solver.parallel:
                    tid = context.get_int_info(Context.info.thread_id)
                    self.solver._thread_dsps[tid] = self.solver._build_dsp_cplex_model()
                return

            if ctx_id & Context.id.thread_down:
                if self.solver.parallel:
                    tid = context.get_int_info(Context.info.thread_id)
                    dsp_obj = self.solver._thread_dsps.pop(tid, None)
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

            # ── LP relaxation node ────────────────────────────────────────
            # Always registered (for root LP capture); user cuts only when flag set.
            if ctx_id & Context.id.relaxation:
                self._capture_root_lp(context)
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
        elapsed = time.perf_counter() - self._t0

        solver  = self.solver
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
                    self.sec_cuts_added += 1
                    self.cuts_added     += 1

            if constraints:
                context.reject_candidate(
                    constraints=constraints,
                    senses=senses,
                    rhs=rhs_vals
                )
            # Log convergence even on SEC rejection
            self.convergence_log.append(
                (elapsed, theta_val, self.best_objective)
            )
            return

        # ── Step B: Extract Hamiltonian sequence ──────────────────────────
        sequence = solver._get_sequence_from_sol(sol)
        if sequence is None:
            # AUDIT(2026-06-10): this path FAILS OPEN — returning
            # without reject_candidate ACCEPTS the incumbent unverified.  It
            # should be unreachable after a clean subtour check; warn loudly so
            # a silent wrong optimum cannot pass unnoticed.
            print("[BBC WARNING] subtour-free candidate but sequence extraction "
                  "failed — candidate accepted UNVERIFIED. Investigate!")
            return

        # ── Step C: Compute subproblem cost and inject cut ────────────────
        cut_injected = False

        if solver.use_combinatorial_cuts:
            # ── Combinatorial (KTNS-based) cut — O(nM), no LP solve ───────
            # Cut: θ ≥ Z*(π) · (1 − Σ_{arc∈π}(1 − x_arc))
            #     = Z*(π) · (1 − |π| + Σ x_arc)
            # Rearranged: θ − Z*(π)·Σ x_arc ≥ Z*(π)·(1 − |π|)
            from utils import compute_ktns
            z_star, _ = compute_ktns(sequence, solver.tool_req, solver.capacity)

            if z_star > theta_val + 1e-6:
                d = solver.depot
                path_arcs = (
                    [(d, sequence[0])]
                    + [(sequence[k], sequence[k+1]) for k in range(len(sequence)-1)]
                    + [(sequence[-1], d)]
                )
                n_arcs = len(path_arcs)  # = n_jobs + 1
                indices = (
                    [solver.theta_idx]
                    + [solver.x_idx_map[i, j] for (i, j) in path_arcs]
                )
                coeffs = [1.0] + [-float(z_star)] * n_arcs
                rhs    = float(z_star) * (1 - n_arcs)

                context.reject_candidate(
                    constraints=[SparsePair(indices, coeffs)],
                    senses=['G'],
                    rhs=[rhs]
                )
                self.comb_cuts_added += 1
                self.cuts_added      += 1
                cut_injected = True

            # Track best primal regardless of cut
            if z_star < self.best_objective:
                self.best_objective = float(z_star)
                self.best_solution  = sequence[:]

        else:
            # ── LP Benders cut — solves the dual subproblem ───────────────
            x_bar = solver._build_x_bar_from_sequence(sequence)
            dsp_obj, duals = solver._solve_dsp_with_xbar(x_bar, tid=tid)
            if dsp_obj is None:
                # AUDIT-FIX(2026-06-10): previously FAILED OPEN
                # (accepted the candidate with theta unverified).  Fall back to
                # the KTNS combinatorial cut, which needs no LP.
                from utils import compute_ktns
                z_star, _ = compute_ktns(sequence, solver.tool_req,
                                         solver.capacity)
                print(f"[BBC WARNING] DSP failed at incumbent; using KTNS "
                      f"fallback cut (z*={z_star}).")
                if z_star > theta_val + 1e-6:
                    dd = solver.depot
                    path_arcs = ([(dd, sequence[0])]
                                 + [(sequence[k], sequence[k + 1])
                                    for k in range(len(sequence) - 1)]
                                 + [(sequence[-1], dd)])
                    indices = ([solver.theta_idx]
                               + [solver.x_idx_map[a] for a in path_arcs])
                    coeffs = [1.0] + [-float(z_star)] * len(path_arcs)
                    context.reject_candidate(
                        constraints=[SparsePair(indices, coeffs)],
                        senses=['G'],
                        rhs=[float(z_star) * (1 - len(path_arcs))]
                    )
                    self.comb_cuts_added += 1
                    self.cuts_added += 1
                if z_star < self.best_objective:
                    self.best_objective = float(z_star)
                    self.best_solution = sequence[:]
                self.convergence_log.append(
                    (elapsed, theta_val, self.best_objective))
                return

            if dsp_obj > theta_val + 1e-6:
                cut_sp, cut_rhs = solver._build_benders_cut_sparsepair(duals)
                context.reject_candidate(
                    constraints=[cut_sp],
                    senses=['G'],
                    rhs=[cut_rhs]
                )
                self.benders_cuts_added += 1
                self.cuts_added         += 1
                cut_injected = True

            if dsp_obj < self.best_objective:
                self.best_objective = dsp_obj
                self.best_solution  = sequence[:]

        # ── Log convergence after every integer candidate ─────────────────
        self.convergence_log.append(
            (elapsed, theta_val, self.best_objective)
        )

    # ── Root LP bound capture ─────────────────────────────────────────────────

    def _capture_root_lp(self, context):
        """
        Track the true root LP relaxation bound.

        Called on every Context.id.relaxation event.  While CPLEX is still
        processing the root node (node_count == 0), we keep updating
        `_root_lp_last` with `best_bound`.  The first time node_count >= 1
        we know branching has started: freeze root_lp_bound and stop.

        For frac_cuts=False: fires once at the root; `_root_lp_last` is set,
        then frozen by the post-solve fallback in solve() if branching never
        triggered a second call.
        For frac_cuts=True: fires many times at the root as user cuts tighten
        the LP; we always keep the most recent (tightest) value.
        """
        if self._root_lp_locked:
            return
        try:
            node_count = context.get_long_info(Context.info.node_count)
            # Read θ directly from the LP solution — this IS the root LP bound
            # for our formulation (min θ s.t. ...).  More reliable than
            # Context.info.best_bound, which is CPLEX's internal global tracker
            # and may lag behind the actual LP value.
            theta_lp = context.get_relaxation_point([self.solver.theta_idx])[0]
            if node_count == 0:
                self._root_lp_last = theta_lp   # keep updating at root
            else:
                # Just left root — freeze
                if self._root_lp_last is not None:
                    self.root_lp_bound = self._root_lp_last
                self._root_lp_locked = True
        except Exception:
            pass

    # ── LP relaxation handler (fractional cuts) ───────────────────────────────

    def _handle_relaxation(self, context, tid=None):
        """
        Called at LP relaxation nodes when use_fractional_cuts=True.
        Solves the DSP with fractional x̄ and injects a user cut if violated.
        """
        solver = self.solver
        n      = solver.n_jobs
        n_vars = solver.n_vars

        self.dbg_relax_calls += 1  # DEBUG

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
            self.dbg_xbar_empty += 1  # DEBUG
            return

        # Solve DSP with fractional x̄
        dsp_obj, duals = solver._solve_dsp_with_xbar(x_bar, tid=tid)
        if dsp_obj is None:
            self.dbg_dsp_none += 1  # DEBUG: DSP failed silently at this fractional node
            return
        self.dbg_dsp_ok += 1  # DEBUG
        self.dbg_max_excess = max(self.dbg_max_excess, dsp_obj - theta_val)  # DEBUG

        # Add user cut if violated
        if dsp_obj > theta_val + 1e-6:
            self.dbg_violated += 1  # DEBUG: a fractional cut IS violated here
            cut_sp, cut_rhs = solver._build_benders_cut_sparsepair(duals)
            try:
                # FIX(2026-07): the previous call passed `purgeable=True`, which is
                # NOT a valid add_user_cut keyword, so every call raised TypeError
                # and was silently caught -> cuts_frac stayed 0 across the whole
                # campaign (falsely reported as "structurally inactive").  The
                # correct generic-callback signature — cf. the bundled CPLEX
                # examples bendersatsp2.py and admipex8.py — is:
                #   add_user_cut(cut=<SparsePair>, sense, rhs, cutmanagement, local)
                _cutmgmt = cplex.callbacks.UserCutCallback.use_cut.purge
                context.add_user_cut(
                    cut=cut_sp,
                    sense='G',
                    rhs=cut_rhs,
                    cutmanagement=_cutmgmt,
                    local=False,
                )
                self.frac_cuts_added += 1
                self.cuts_added      += 1
            except Exception as _e:
                self.dbg_add_failed += 1  # DEBUG: violated but add failed (masked)
                if not getattr(self, 'dbg_add_err', None):
                    self.dbg_add_err = repr(_e)  # DEBUG: first add-failure reason

            # Papadakos core-point Pareto cut, added ALONGSIDE the normal cut.
            if solver.use_pareto_cuts and solver._core_point is not None:
                self._add_pareto_cut(context)


    def _add_pareto_cut(self, context):
        """Papadakos Pareto cut-lifting: generate the Benders cut at the
        maintained core point and add it ALONGSIDE the normal fractional cut
        (never instead of it), then move the core point toward the current
        relaxation point.  Validity is inherited from the same
        _build_benders_cut_sparsepair used by every other Benders cut, so this
        can only strengthen the relaxation, never remove a feasible point."""
        solver = self.solver
        x0 = solver._core_point
        if x0 is None:
            return
        try:
            dsp0, duals0 = solver._solve_dsp_with_xbar(x0)
            if dsp0 is not None:
                cut_sp, cut_rhs = solver._build_benders_cut_sparsepair(duals0)
                _cm = cplex.callbacks.UserCutCallback.use_cut.purge
                context.add_user_cut(cut=cut_sp, sense='G', rhs=cut_rhs,
                                     cutmanagement=_cm, local=False)
                solver.n_pareto_cuts += 1
                self.cuts_added += 1
        except Exception:
            pass
        # Papadakos update: core <- 1/2 (core + current relaxation point)
        try:
            vals = context.get_relaxation_point(list(range(solver.n_vars)))
            for (i, j) in solver.x_pairs:
                a = (i, j)
                x0[a] = 0.5 * (x0.get(a, 0.0) + vals[solver.x_idx_map[i, j]])
        except Exception:
            pass


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
        Fire the callback at LP relaxation nodes and add Benders LP user cuts.
        Requires presolve to be disabled.  Attacks tailing-off.
    use_combinatorial_cuts : bool
        Use KTNS-based combinatorial Benders cuts at integer candidates instead
        of the LP dual subproblem.  O(nM) per cut — much cheaper but weaker.
        Mutually exclusive with LP cuts at integer nodes; fractional LP cuts
        (use_fractional_cuts) can still be combined with this.
    use_triplet_bounds : bool
        Strengthen the initial θ lower bound with O(n³) triplet constraints:
        θ ≥ w_ijk·(x_ij + x_jk − 1) for all real-job triples (i,j,k).
        Tightens the root LP bound at the cost of a larger master problem.
    parallel : bool
        Allow CPLEX to use multiple B&B threads.  Each thread gets its own DSP
        model via thread_up / thread_down.  Thread-safe: _thread_dsps lives on
        the solver and is initialised before any thread starts.
    """

    def __init__(self, n_jobs, n_tools, capacity, tool_req,
                 worker_lp_reuse=False, use_fractional_cuts=False,
                 use_combinatorial_cuts=False, use_triplet_bounds=False,
                 parallel=False,
                 use_conflict_cuts=False, use_primal_heuristic=False,
                 use_pareto_cuts=False, heuristic_time=2.0):
        self.n_jobs                 = n_jobs
        self.n_tools                = n_tools
        self.capacity               = capacity
        self.tool_req               = tool_req
        self.worker_lp_reuse        = worker_lp_reuse
        self.use_fractional_cuts    = use_fractional_cuts
        self.use_combinatorial_cuts = use_combinatorial_cuts
        self.use_triplet_bounds     = use_triplet_bounds
        self.parallel               = parallel

        # ── New acceleration flags (2026-07); all default off, independent ──
        self.use_conflict_cuts      = use_conflict_cuts     # conflict-graph root bound
        self.use_primal_heuristic   = use_primal_heuristic  # HGS -> MIP start + seed cut
        self.use_pareto_cuts        = use_pareto_cuts       # Papadakos cut lifting
        self.heuristic_time         = heuristic_time
        self._core_point            = None   # Papadakos core point: arc -> value
        self.n_conflict_cuts        = 0
        self.n_seed_cuts            = 0
        self.n_pareto_cuts          = 0
        self.heuristic_cost         = None

        self._compute_pairwise_bounds()
        # Precompute triplet bounds if needed (done once at init)
        self.w3: dict = {}   # (i,j,k) → max(0, |T_i∪T_j∪T_k|−c)
        if use_triplet_bounds:
            self._compute_triplet_bounds()

        # CPLEX model and variable index bookkeeping
        self.cpx       = None
        self.theta_idx = None
        self.x_idx_map = {}    # (i,j) → column index
        self.x_pairs   = []    # ordered list of (i,j) arcs
        self.n_vars    = 0

        # Shared (non-parallel) DSP model when worker_lp_reuse=True
        self._shared_dsp = None   # dict: {model, lam_idx, mu_idx, nu_idx, eta_idx, n_lam}

        # Thread-local DSP storage (parallel=True).  Lives on the solver so
        # it is initialised before any CPLEX thread starts — no race condition.
        self._thread_dsps: dict = {}

        # Tracking (backward-compat + detailed)
        self.best_solution      = None
        self.best_objective     = float('inf')
        self.cuts_added         = 0   # total
        self.sec_cuts_added     = 0
        self.benders_cuts_added = 0
        self.comb_cuts_added    = 0
        self.frac_cuts_added    = 0
        self.iteration_count    = 0

        # Convergence log and stats (populated after solve())
        self.convergence_log: list = []
        self.root_lp_bound: float  = None
        self.solve_stats: dict     = {}

    # ─────────────────────────────────────────────────────────────────────────
    # Triplet bound pre-computation
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_triplet_bounds(self) -> None:
        """
        Precompute w3[i,j,k] = max(0, |T_i ∪ T_j ∪ T_k| − c) for all ordered
        triples of real jobs (i, j, k distinct).  Used in build_master_problem
        to add triplet lower bound constraints on θ.
        """
        n = self.n_jobs
        c = self.capacity
        tr = self.tool_req
        for i in range(n):
            Ti = set(tr.get(i, []))
            for j in range(n):
                if j == i:
                    continue
                Tj = set(tr.get(j, []))
                for k in range(n):
                    if k == i or k == j:
                        continue
                    Tk = set(tr.get(k, []))
                    val = max(0, len(Ti | Tj | Tk) - c)
                    if val > 0:
                        self.w3[i, j, k] = val

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
        import os as _os
        _thr = int(_os.environ.get("CPLEX_THREADS", "0"))   # pin threads (0 = CPLEX default) for reproducible/comparable timings
        if _thr:
            self.cpx.parameters.threads.set(_thr)
        if not verbose:
            self.cpx.set_log_stream(None)
            self.cpx.set_results_stream(None)
            self.cpx.set_warning_stream(None)

        n = self.n_jobs
        d = n           # depot node (idea.md: J∪{0}; here index=n_jobs)
        self.depot = d
        nodes = list(range(n)) + [d]

        # ── θ variable at column 0 ────────────────────────────────────────
        self.cpx.variables.add(
            obj   = [1.0],
            lb    = [0.0],
            types = ['C'],
            names = ['theta']
        )
        self.theta_idx = 0

        # ── Arc variables (all nodes including depot) ─────────────────────
        self.x_pairs = [(i, j) for i in nodes for j in nodes if i != j]
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
        self.cpx.objective.set_sense(self.cpx.objective.sense.minimize)

        # ── Degree constraints (all nodes including depot) ─────────────────
        for i in nodes:
            out_idx = [self.x_idx_map[i, j] for j in nodes if i != j]
            self.cpx.linear_constraints.add(
                lin_expr=[SparsePair(out_idx, [1.0]*len(out_idx))],
                senses=['E'], rhs=[1.0], names=[f'out_{i}']
            )
            in_idx = [self.x_idx_map[j, i] for j in nodes if j != i]
            self.cpx.linear_constraints.add(
                lin_expr=[SparsePair(in_idx, [1.0]*len(in_idx))],
                senses=['E'], rhs=[1.0], names=[f'in_{i}']
            )

        # ── Initial lower bound: θ ≥ Σ w_ij x_ij + Σ_j |T_j| x_{d,j} ─────────
        # AUDIT-IMPROVEMENT(2026-06-10): the DSP charges insertions
        # from an EMPTY depot magazine (y_{depot,t}=0), so the first job σ(1)
        # always costs ≥ |T_{σ(1)}| insertions.  The old version set w=0 on depot
        # arcs, leaving that term out of the root bound.  Valid: first-job
        # insertions and later transition insertions are disjoint position-wise.
        lb_indices = [self.theta_idx]
        lb_coeffs  = [1.0]
        for (i, j) in self.x_pairs:
            if j == d:
                continue  # j→depot arcs cost nothing
            lb_indices.append(self.x_idx_map[i, j])
            if i == d:
                lb_coeffs.append(-float(len(self.tool_req.get(j, []))))
            else:
                lb_coeffs.append(-float(self.w.get((i, j), 0)))
        self.cpx.linear_constraints.add(
            lin_expr=[SparsePair(lb_indices, lb_coeffs)],
            senses=['G'], rhs=[0.0], names=['theta_lb']
        )

        # -- Coverage bound: theta >= |U|  (ADDED 2026-07-16) ------------------
        # Every tool used by some job is inserted at least once from the empty
        # depot magazine, so the empty-start objective is at least |U|.  This is
        # Proposition lb2 of the report (empty-start form).  The 2026-07 campaign
        # showed the master's dual bound frozen at the trivial pairwise value on
        # capacity-loose instances precisely because this row was missing; every
        # other benchmarked method carries the bound through its own LP.
        used_tools = set()
        for req in self.tool_req.values():
            used_tools.update(req)
        self.cpx.linear_constraints.add(
            lin_expr=[SparsePair([self.theta_idx], [1.0])],
            senses=['G'], rhs=[float(len(used_tools))], names=['theta_coverage']
        )

        # ── Triplet lower bounds: θ ≥ w_ijk·(x_ij + x_jk − 1) ───────────
        # Valid because: if x_ij=x_jk=1 (j between i and k), the three-job
        # segment requires at least w_ijk switches.  For all other x values
        # the RHS ≤ 0 ≤ θ, so the constraint is trivially satisfied.
        if self.use_triplet_bounds and self.w3:
            triplet_exprs = []
            triplet_rhs   = []
            for (i, j, k), val in self.w3.items():
                if (i, j) not in self.x_idx_map or (j, k) not in self.x_idx_map:
                    continue
                # θ − val·x_ij − val·x_jk ≥ −val   ↔   θ ≥ val·(x_ij+x_jk−1)
                triplet_exprs.append(SparsePair(
                    [self.theta_idx, self.x_idx_map[i, j], self.x_idx_map[j, k]],
                    [1.0, -float(val), -float(val)]
                ))
                triplet_rhs.append(-float(val))
            if triplet_exprs:
                self.cpx.linear_constraints.add(
                    lin_expr = triplet_exprs,
                    senses   = ['G'] * len(triplet_exprs),
                    rhs      = triplet_rhs,
                )

        if not self.parallel:
            self.cpx.parameters.threads.set(1)
        if self.use_fractional_cuts:
            self.cpx.parameters.preprocessing.presolve.set(0)
        if verbose:
            flags = []
            if self.use_triplet_bounds:    flags.append(f"triplet_bounds({len(self.w3)})")
            if self.use_combinatorial_cuts: flags.append("comb_cuts")
            if self.use_fractional_cuts:   flags.append("frac_cuts")
            if self.worker_lp_reuse:       flags.append("lp_reuse")
            if self.parallel:              flags.append("parallel")
            flag_str = ", ".join(flags) if flags else "defaults"
            print(f"Master Problem built: {n} jobs + depot, {n_arcs} arc variables "
                  f"[{flag_str}]")

    # ─────────────────────────────────────────────────────────────────────────
    # Solution helpers (shared with callback)
    # ─────────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────────
    # Depot-aware sequence helpers (override bbc_common versions)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_sequence_from_sol(self, sol):
        """Start traversal from depot node, return only real-job sequence."""
        n = self.n_jobs
        d = self.depot
        succ = {i: j for i in range(n+1) for j in range(n+1)
                if i != j and sol.get((i, j), 0.0) > 0.5}
        current = succ.get(d)
        sequence = []
        visited = {d}
        while current is not None and current != d and len(sequence) < n:
            if current in visited:
                break
            sequence.append(current)
            visited.add(current)
            current = succ.get(current)
        return sequence if len(sequence) == n else None

    def _build_x_bar_from_sequence(self, sequence):
        """Path formulation: depot→seq[0]→...→seq[-1]→depot (no wrap-around)."""
        d = self.depot
        x_bar = {}
        x_bar[d, sequence[0]] = 1.0
        for k in range(len(sequence) - 1):
            x_bar[sequence[k], sequence[k + 1]] = 1.0
        x_bar[sequence[-1], d] = 1.0
        return x_bar

    def _find_subtours_from_sol(self, sol):
        """Detect subtours; valid tour visits all n_jobs+1 nodes (incl. depot)."""
        n = self.n_jobs
        d = self.depot
        all_nodes = list(range(n)) + [d]
        succ = {i: j for i in all_nodes for j in all_nodes
                if i != j and sol.get((i, j), 0.0) > 0.5}
        visited, subtours = set(), []
        for start in all_nodes:
            if start in visited or start not in succ:
                visited.add(start); continue
            cycle, current = [start], succ[start]
            visited.add(start)
            while current != start:
                if current in visited:
                    cycle = None; break
                visited.add(current)
                cycle.append(current)
                current = succ.get(current)
                if current is None:
                    cycle = None; break
            if cycle is not None and len(cycle) < n + 1:
                subtours.append(cycle)
        return subtours

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

        # lam[i,j,t] >= 0; obj = 0 (updated per call) — job-to-job arcs
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in T:
                        lam_idx[i, j, t] = add_var(f"lam_{i}_{j}_{t}", 0.0, 0.0)

        # lam_depot[j,t] >= 0; obj = 0 (updated per call) — depot→job arcs
        # Enforces y_{depot,t} = 0 (empty magazine at start), breaking the
        # cyclic-preloading LP artifact that gives DSP = 0 for all sequences.
        lam_depot_idx = {}
        for j in range(n):
            for t in T:
                lam_depot_idx[j, t] = add_var(f"lam_d_{j}_{t}", 0.0, 0.0)

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
        # dual of y_jt:  -mu_j - lam_depot_jt - Σ_i lam_ijt + Σ_k lam_jkt + nu_jt <= 0
        # lam_depot_jt is the dual of the depot→j arc, enforcing y_{depot,t}=0.
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                indices = []
                coeffs  = []

                indices.append(mu_idx[j]); coeffs.append(-1.0)

                # depot→j incoming arc
                indices.append(lam_depot_idx[j, t]); coeffs.append(-1.0)

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
        # dual of z_jt:  lam_depot_jt + Σ_i lam_ijt + eta_jt <= rhs
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                indices = []
                coeffs  = []

                # depot→j incoming arc
                indices.append(lam_depot_idx[j, t]); coeffs.append(1.0)

                for i in range(n):
                    if i != j:
                        indices.append(lam_idx[i, j, t]); coeffs.append(1.0)

                if t not in Tj:
                    indices.append(eta_idx[j, t]); coeffs.append(1.0)

                # rhs = 1 for ALL t (not 0 for t∉T_j).
                # The dual constraint for z_{j,t} has RHS = obj_coeff_z = 1
                # regardless of whether t∈T_j.  Using rhs=0 for t∉T_j forces
                # all inter-job lam to zero for non-required tools, which breaks
                # the dual chain and gives DSP=2 instead of the correct 6.
                dsp.linear_constraints.add(
                    lin_expr = [SparsePair(indices, coeffs)],
                    senses   = ['L'],
                    rhs      = [1.0],
                    names    = [f'dz_{j}_{t}']
                )

        # Use dual simplex for efficient re-solves
        dsp.parameters.lpmethod.set(dsp.parameters.lpmethod.values.dual)

        return {
            'model'         : dsp,
            'lam_idx'       : lam_idx,
            'lam_depot_idx' : lam_depot_idx,
            'mu_idx'        : mu_idx,
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
            # _thread_dsps lives on the solver (initialised before threads start)
            if tid not in self._thread_dsps:
                self._thread_dsps[tid] = self._build_dsp_cplex_model()
            return self._thread_dsps[tid]
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
        dsp_data      = self._get_dsp_model(tid=tid)
        dsp           = dsp_data['model']
        lam_idx       = dsp_data['lam_idx']
        lam_depot_idx = dsp_data['lam_depot_idx']
        mu_idx        = dsp_data['mu_idx']
        nu_idx        = dsp_data['nu_idx']
        eta_idx       = dsp_data['eta_idx']

        # Update job-to-job lam objective: coeff = x_bar.get((i,j), 0) - 1
        updates = []
        for (i, j, t), col in lam_idx.items():
            coeff = x_bar.get((i, j), 0.0) - 1.0
            updates.append((col, coeff))
        # Update depot→job lam objective: coeff = x_bar.get((depot,j), 0) - 1
        depot = self.depot
        for (j, t), col in lam_depot_idx.items():
            coeff = x_bar.get((depot, j), 0.0) - 1.0
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
        # AUDIT-FIX(2026-06-10): depot-arc duals were never extracted,
        # so _build_benders_cut_sparsepair silently dropped the term
        # sum_j (x_dj - 1)*lam_d[j,t] from the cut.  Dropping a non-positive term
        # makes the cut OVER-TIGHT and, at degenerate DSP optima (lam_d > 0 on
        # non-first-job depot arcs; these exist: lam_d and nu trade off at zero
        # reduced cost), the cut can cut off true optimal (sequence, theta) points.
        # Witnessed numerically: 193 violations on random instances
        # (plans-genai/_verification/verify_bbc_audit.py, T3).
        for (j, t), col in lam_depot_idx.items():
            duals['lambda_d', j, t] = all_vals[col]
        for j, col in mu_idx.items():
            duals['mu', j] = all_vals[col]
        for (j, t), col in nu_idx.items():
            duals['nu', j, t] = all_vals[col]
        for (j, t), col in eta_idx.items():
            duals['eta', j, t] = all_vals[col]

        return obj_val, duals

    # ── Fresh DSP (docplex or Gurobi) ─────────────────────────────────────────

    def _solve_dsp_fresh(self, x_bar):
        """Build and solve the DSP from scratch for a given x̄.

        Raw CPLEX is tried first because it contains the complete depot-arc
        lam fix.  docplex/gurobi are fallbacks only when CPLEX is unavailable.
        """
        if HAS_CPLEX:
            # Build a fresh raw CPLEX DSP model
            dsp_data = self._build_dsp_cplex_model()
            # Set lam obj to x_bar values - 1 (job-to-job and depot arcs)
            updates = []
            for (i, j, t), col in dsp_data['lam_idx'].items():
                coeff = x_bar.get((i, j), 0.0) - 1.0
                updates.append((col, coeff))
            depot = self.depot
            for (j, t), col in dsp_data['lam_depot_idx'].items():
                coeff = x_bar.get((depot, j), 0.0) - 1.0
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
            # AUDIT-FIX(2026-06-10): extract depot-arc duals (see
            # _solve_dsp_reuse for the full explanation of the cut-validity bug).
            for (j, t), col in dsp_data['lam_depot_idx'].items():
                duals['lambda_d', j, t] = all_vals[col]
            for j, col in dsp_data['mu_idx'].items():
                duals['mu', j] = all_vals[col]
            for (j, t), col in dsp_data['nu_idx'].items():
                duals['nu', j, t] = all_vals[col]
            for (j, t), col in dsp_data['eta_idx'].items():
                duals['eta', j, t] = all_vals[col]
            dsp_data['model'].end()
            return obj_val, duals
        elif HAS_DOCPLEX:
            return self._solve_dsp_docplex(x_bar)
        elif HAS_GUROBI:
            return self._solve_dsp_gurobi(x_bar)
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
            θ ≥ Σ_{i,j,t} (x_ij - 1) λ̄_ijt + Σ_{j,t} (x_dj - 1) λ̄d_jt
                - Σ_j c μ̄_j  + Σ_{j,t∈T_j} ν̄_jt

        AUDIT-FIX(2026-06-10): the depot-arc term Σ(x_dj-1)λ̄d_jt was
        previously OMITTED.  Since it is ≤ 0, omitting it over-tightens the cut;
        at degenerate DSP optima this cuts off true optimal solutions (witnessed:
        verify_bbc_audit.py T3, 193 violations).  Now included.

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
        # depot→job arcs (AUDIT-FIX): coeff for x_{d,j} from lam_depot duals
        d = self.depot
        for j in range(n):
            coeff[d, j] = sum(
                duals.get(('lambda_d', j, t), 0.0)
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
    # Root accelerators (2026-07): conflict cuts / HGS primal / Pareto init
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_root_accelerators(self, verbose=False):
        """Optional root-node accelerations, each behind its own flag and all
        validity-preserving.  Called once in solve() after the master is built.

        (1) use_conflict_cuts   : add the conflict-graph constant lower bound
                                  theta >= max(coverage, grouping) when the
                                  grouping term strictly beats coverage
                                  (validated in test_new_features.py).
        (2) use_primal_heuristic: run HGS -> push a CPLEX MIP start (warm
                                  incumbent) AND seed a Benders optimality cut
                                  from the heuristic sequence at the root.
        (3) use_pareto_cuts     : initialise the Papadakos core point used by
                                  the callback to lift fractional Benders cuts.
        """
        n = self.n_jobs

        # (1) Conflict-graph root bound ------------------------------------------------
        if self.use_conflict_cuts and _cc is not None:
            try:
                cut = _cc.root_bound_cut(self.tool_req, n, self.capacity)
                if cut is not None and cut["rhs"] > 0:
                    self.cpx.linear_constraints.add(
                        lin_expr=[SparsePair([self.theta_idx], [1.0])],
                        senses=['G'], rhs=[float(cut["rhs"])],
                        names=['conflict_root'])
                    self.n_conflict_cuts += 1
                    if verbose:
                        print(f"[conflict] theta >= {cut['rhs']}  {cut['detail']}")
            except Exception as e:
                if verbose:
                    print(f"[conflict] skipped: {e}")

        # (2) HGS primal heuristic -> MIP start + seeded Benders cut -------------------
        heur_seq = None
        if self.use_primal_heuristic and _hgs is not None:
            try:
                from utils import compute_ktns
                heur_seq, hc = _hgs.hgs(
                    self.tool_req, n, self.capacity,
                    cost_fn=lambda s: compute_ktns(s, self.tool_req, self.capacity)[0],
                    time_limit=self.heuristic_time)
                self.heuristic_cost = hc
            except Exception as e:
                heur_seq = None
                if verbose:
                    print(f"[heur] HGS failed: {e}")
            if heur_seq is not None:
                d = self.depot
                arcs = ([(d, heur_seq[0])]
                        + [(heur_seq[k], heur_seq[k + 1]) for k in range(n - 1)]
                        + [(heur_seq[-1], d)])
                aset = set(arcs)
                # (a) MIP start (warm incumbent) — cannot affect correctness.
                try:
                    ind = [self.theta_idx] + [self.x_idx_map[i, j] for i, j in self.x_pairs]
                    val = [float(self.heuristic_cost)] + [
                        1.0 if (i, j) in aset else 0.0 for i, j in self.x_pairs]
                    self.cpx.MIP_starts.add(
                        SparsePair(ind, val),
                        self.cpx.MIP_starts.effort_level.solve_fixed)
                except Exception as e:
                    if verbose:
                        print(f"[heur] MIP start skipped: {e}")
                # (b) seed a Benders optimality cut for the heuristic sequence.
                try:
                    x_bar = {a: 1.0 for a in arcs}
                    dsp_obj, duals = self._solve_dsp_with_xbar(x_bar)
                    if dsp_obj is not None:
                        cut_sp, cut_rhs = self._build_benders_cut_sparsepair(duals)
                        self.cpx.linear_constraints.add(
                            lin_expr=[cut_sp], senses=['G'], rhs=[cut_rhs],
                            names=['heur_seed'])
                        self.n_seed_cuts += 1
                except Exception as e:
                    if verbose:
                        print(f"[heur] seed cut skipped: {e}")
                if verbose:
                    print(f"[heur] HGS incumbent = {self.heuristic_cost}")

        # (3) Papadakos core point ----------------------------------------------------
        if self.use_pareto_cuts:
            base = 1.0 / max(1, n)
            core = {(i, j): base for (i, j) in self.x_pairs}
            if heur_seq is not None:
                d = self.depot
                for k in range(n - 1):
                    a = (heur_seq[k], heur_seq[k + 1])
                    if a in core:
                        core[a] = 0.5 * (core[a] + 1.0)
                a0 = (d, heur_seq[0])
                if a0 in core:
                    core[a0] = 0.5 * (core[a0] + 1.0)
            self._core_point = core

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

        After the call, self.solve_stats contains detailed diagnostics and
        self.convergence_log contains [(elapsed_s, dual_bound, primal_bound)].
        """
        if self.cpx is None:
            self.build_master_problem(verbose=verbose)

        self.cpx.parameters.timelimit.set(float(time_limit))

        # Root accelerators (conflict bound / HGS primal / Pareto init) — flags.
        self._apply_root_accelerators(verbose=verbose)

        if self.use_fractional_cuts:
            # User cuts added at relaxation nodes must remain valid for the
            # presolved model; without disabling presolve CPLEX silently makes
            # them unusable (bendersatsp2 pattern / design note). Symptom in
            # the 2026-07-02 campaign: every +F config recorded cuts_frac = 0.
            self.cpx.parameters.preprocessing.presolve.set(0)

        # ── Register modern generic callback ──────────────────────────────
        # _thread_dsps already lives on self — no _cb_ref needed, no race.
        cb = BendersCutCallback(self)

        # Always register relaxation so we can capture the true root LP bound.
        # (frac cuts also use it; the handler separates the two concerns.)
        context_mask = Context.id.candidate | Context.id.relaxation
        if self.parallel:
            context_mask |= Context.id.thread_up | Context.id.thread_down

        self.cpx.set_callback(cb, context_mask)

        # ── Solve ─────────────────────────────────────────────────────────
        t_start = time.perf_counter()
        self.cpx.solve()
        wall_time = time.perf_counter() - t_start

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

        # ── Finalise root LP bound ────────────────────────────────────────
        # If the solve finished at the root (no branching), node_count never
        # reached 1 inside the relaxation callback, so root_lp_bound was never
        # frozen.  Use the last captured value.
        if cb.root_lp_bound is None and cb._root_lp_last is not None:
            cb.root_lp_bound = cb._root_lp_last

        # ── Copy callback stats to solver ─────────────────────────────────
        self.cuts_added         = cb.cuts_added
        self.sec_cuts_added     = cb.sec_cuts_added
        self.benders_cuts_added = cb.benders_cuts_added
        self.comb_cuts_added    = cb.comb_cuts_added
        self.frac_cuts_added    = cb.frac_cuts_added
        self.iteration_count    = cb.iteration_count
        self.convergence_log    = cb.convergence_log
        self.root_lp_bound      = cb.root_lp_bound

        # ── DEBUG: surface fractional-cut diagnostics for the driver script ──
        self.dbg_frac = {
            "relax_calls": cb.dbg_relax_calls,
            "xbar_empty":  cb.dbg_xbar_empty,
            "dsp_none":    cb.dbg_dsp_none,
            "dsp_ok":      cb.dbg_dsp_ok,
            "violated":    cb.dbg_violated,
            "add_failed":  cb.dbg_add_failed,
            "max_excess":  cb.dbg_max_excess,
            "add_err":     cb.dbg_add_err,
        }

        if cb.best_objective < self.best_objective:
            self.best_objective = cb.best_objective
            self.best_solution  = cb.best_solution

        # ── Extract CPLEX MIP stats ───────────────────────────────────────
        try:
            # AUDIT-FIX(2026-06-10): was get_best_objval, which does
            # not exist in the CPLEX Python API (verified hasattr=False on 22.2);
            # the except silently substituted the root LP bound, so reported
            # dual_bound / mip_gap_pct were wrong whenever branching improved
            # the bound. Correct name: get_best_objective.
            dual_bound = self.cpx.solution.MIP.get_best_objective()
        except Exception:
            dual_bound = self.root_lp_bound

        # Compute gap manually from obj/dual — get_mip_relative_gap() throws
        # for many status codes (no solution, gap=inf, status type mismatch).
        # Formula: |UB - LB| / |UB| × 100  (0% when optimal, >0% when timed out)
        if obj_val is not None and dual_bound is not None and abs(obj_val) > 1e-10:
            mip_gap_pct = abs(obj_val - dual_bound) / abs(obj_val) * 100.0
        else:
            mip_gap_pct = None

        try:
            nodes    = self.cpx.solution.progress.get_num_nodes_processed()
            lp_iters = self.cpx.solution.progress.get_num_iterations()
        except Exception:
            nodes    = None
            lp_iters = None

        self.solve_stats = {
            "status":           status_str,
            "obj_val":          obj_val,
            "dual_bound":       dual_bound,
            "root_lp_bound":    self.root_lp_bound,
            "mip_gap_pct":      mip_gap_pct,
            "wall_time_s":      round(wall_time, 3),
            "nodes":            nodes,
            "lp_iters":         lp_iters,
            "cb_invocations":   self.iteration_count,
            "cuts_total":       self.cuts_added,
            "cuts_sec":         self.sec_cuts_added,
            "cuts_benders":     self.benders_cuts_added,
            "cuts_comb":        self.comb_cuts_added,
            "cuts_frac":        self.frac_cuts_added,
            # flags
            "use_combinatorial_cuts": self.use_combinatorial_cuts,
            "use_triplet_bounds":     self.use_triplet_bounds,
            "use_fractional_cuts":    self.use_fractional_cuts,
            "worker_lp_reuse":        self.worker_lp_reuse,
            # New acceleration features (2026-07)
            "use_conflict_cuts":      self.use_conflict_cuts,
            "use_primal_heuristic":   self.use_primal_heuristic,
            "use_pareto_cuts":        self.use_pareto_cuts,
            "n_conflict_cuts":        self.n_conflict_cuts,
            "n_seed_cuts":            self.n_seed_cuts,
            "n_pareto_cuts":          self.n_pareto_cuts,
            "heuristic_cost":         self.heuristic_cost,
        }

        if verbose:
            sep = '=' * 60
            st  = self.solve_stats
            print(f"\n{sep}")
            print(f"  Status          : {st['status']}")
            print(f"  Objective (UB)  : {st['obj_val']}")
            print(f"  Dual bound (LB) : {st['dual_bound']}")
            print(f"  Root LP bound   : {st['root_lp_bound']}")
            print(f"  MIP gap         : "
                  f"{st['mip_gap_pct']:.4f}%" if st['mip_gap_pct'] is not None
                  else f"  MIP gap         : —")
            print(f"  Wall time       : {st['wall_time_s']:.2f}s")
            print(f"  B&B nodes       : {st['nodes']}")
            print(f"  LP iterations   : {st['lp_iters']}")
            print(f"  CB invocations  : {st['cb_invocations']}")
            print(f"  Cuts — total    : {st['cuts_total']}")
            print(f"         SECs     : {st['cuts_sec']}")
            print(f"         Benders  : {st['cuts_benders']}")
            print(f"         Comb     : {st['cuts_comb']}")
            print(f"         Frac     : {st['cuts_frac']}")
            print(f"  Sequence        : {sequence}")
            print(f"{sep}\n")

        return status_str, obj_val, sequence

    # ─────────────────────────────────────────────────────────────────────────
    # Diagnostics
    # ─────────────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return the solve_stats dict (populated after solve())."""
        return self.solve_stats

    def plot_convergence(self, ax=None):
        """
        Plot the primal/dual bound convergence curve.

        Uses self.convergence_log: [(elapsed_s, dual_bound, primal_bound)].
        Returns the matplotlib Axes object.
        """
        import matplotlib.pyplot as plt

        if not self.convergence_log:
            print("No convergence data — run solve() first.")
            return None

        times   = [r[0] for r in self.convergence_log]
        duals   = [r[1] for r in self.convergence_log]
        primals = [r[2] for r in self.convergence_log]
        # Replace inf placeholders for plotting
        primals = [p if p < 1e15 else None for p in primals]

        if ax is None:
            _, ax = plt.subplots(figsize=(8, 4))

        ax.step(times, duals,   where='post', label='Dual (LB / θ)',  color='steelblue')
        ax.step(times, primals, where='post', label='Primal (UB)',     color='darkorange')

        if self.root_lp_bound is not None:
            ax.axhline(self.root_lp_bound, color='steelblue',
                       linestyle=':', alpha=0.6, label=f'Root LP = {self.root_lp_bound:.2f}')

        ax.set_xlabel("Elapsed time (s)")
        ax.set_ylabel("Objective (tool switches)")
        ax.set_title("BBC Convergence — Dual / Primal Bounds")
        ax.legend()
        ax.grid(True, alpha=0.3)

        return ax

    def print_stats_table(self):
        """Pretty-print solve_stats as a compact table for research reporting."""
        st = self.solve_stats
        if not st:
            print("No stats — run solve() first.")
            return
        rows = [
            ("Status",           st.get("status")),
            ("Objective (UB)",   st.get("obj_val")),
            ("Dual bound (LB)",  st.get("dual_bound")),
            ("Root LP bound",    st.get("root_lp_bound")),
            ("MIP gap (%)",      f"{st['mip_gap_pct']:.4f}" if st.get("mip_gap_pct") is not None else "—"),
            ("Wall time (s)",    st.get("wall_time_s")),
            ("B&B nodes",        st.get("nodes")),
            ("LP iterations",    st.get("lp_iters")),
            ("CB invocations",   st.get("cb_invocations")),
            ("Cuts — total",     st.get("cuts_total")),
            ("  SECs",           st.get("cuts_sec")),
            ("  Benders",        st.get("cuts_benders")),
            ("  Combinatorial",  st.get("cuts_comb")),
            ("  Fractional",     st.get("cuts_frac")),
            ("Flags",
             " | ".join(k for k in
                        ["use_combinatorial_cuts","use_triplet_bounds",
                         "use_fractional_cuts","worker_lp_reuse"]
                        if st.get(k))),
        ]
        width = max(len(r[0]) for r in rows) + 2
        print("─" * (width + 20))
        for label, val in rows:
            print(f"  {label:<{width}}: {val}")
        print("─" * (width + 20))
