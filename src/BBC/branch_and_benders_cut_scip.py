"""
Branch-and-Benders-Cut Algorithm for the SSP – SCIP Implementation
(branch_and_benders_cut_scip.py)

Uses PySCIPOPT (the Python interface to SCIP) together with SCIP's
Constraint Handler API to implement lazy Branch-and-Benders-Cut.

Architecture
------------
Master Problem  : built with pyscipopt.Model  (TSP + surrogate θ)
Callback        : BendersConshdlr  –  a pyscipopt.Conshdlr subclass
                  registered with model.includeConshdlr(..., needscons=False)
                  so it fires on every LP / integer solution without needing
                  explicit constraint objects.
DSP             : solved with a separate pyscipopt.Model LP (self-contained –
                  no Gurobi or CPLEX needed).  Gurobi / docplex are used as
                  faster alternatives when available.

Key SCIP callback methods used
-------------------------------
conscheck   – called when SCIP verifies a candidate (integer) solution.
              Detects subtours and Benders violations; returns INFEASIBLE
              if any exist (which triggers consenfolp).
consenfolp  – called when LP enforcement is needed (after conscheck fails
              OR at every LP solve).  Adds SECs and Benders cuts as global
              constraints via self.model.addCons().
consenfops  – called for pseudo-solutions; returns FEASIBLE (no action).
conslock    – no-op (we do not have static constraint objects to lock).

Optional performance features
------------------------------
worker_lp_reuse : bool (default False)
    When True, one DSP model is built (using Gurobi if available, else SCIP)
    at first call and reused across callback invocations, updating only the
    objective coefficients before each re-solve.  Follows the LP-reuse
    pattern from IBM's bendersatsp2.py example.

use_fractional_cuts : bool (default False)
    When True, consenfolp also attempts Benders cuts at fractional LP nodes
    (not just integer solutions).  The DSP is solved with the fractional x̄
    values directly, and if a violated cut is found it is added as a global
    constraint.  This tightens the LP bound before branching.

parallel : bool (default False)
    When True, SCIP is allowed to use multiple threads via its parallel B&B
    support (limits/parallelisation).  Note: PySCIPOPT's constraint handler
    API is not fully thread-safe in all SCIP versions; use with caution.
    When False (default), SCIP is limited to 1 thread.

Install
-------
    pip install pyscipopt        # SCIP must be installed on the system
    pip install gurobipy         # optional – faster DSP
    pip install docplex          # optional – faster DSP fallback
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Solver imports ─────────────────────────────────────────────────────────────
try:
    from pyscipopt import Model as SCIPModel, Conshdlr, SCIP_RESULT
    from pyscipopt import quicksum as scip_quicksum
    HAS_SCIP = True
except ImportError:
    HAS_SCIP = False
    print("WARNING: pyscipopt not found.  Install with: pip install pyscipopt")

try:
    import gurobipy as gp
    from gurobipy import GRB
    HAS_GUROBI = True
except ImportError:
    HAS_GUROBI = False

try:
    from docplex.mp.model import Model as DocplexModel
    HAS_DOCPLEX = True
except ImportError:
    HAS_DOCPLEX = False

from utils import load_ssp_instance


# ─────────────────────────────────────────────────────────────────────────────
# SCIP Constraint Handler
# ─────────────────────────────────────────────────────────────────────────────

class BendersConshdlr(Conshdlr):
    """
    SCIP constraint handler for Branch-and-Benders-Cut.

    Flow (mirrors the Gurobi / CPLEX callback):
    1.  conscheck  – verify integer solution; return INFEASIBLE on subtour or
                     Benders violation.
    2.  consenfolp – add violated SECs and/or Benders cuts as global constraints.
                     When use_fractional_cuts=True, also fires at fractional LP
                     nodes and adds Benders user cuts.
    3.  consenfops – pass-through (returns FEASIBLE for pseudo-solutions).
    4.  conslock   – no-op (no static constraint objects).
    """

    def __init__(self, solver):
        super().__init__()
        self.solver          = solver
        self.cuts_added      = 0
        self.iteration_count = 0
        self.best_objective  = float('inf')
        self.best_solution   = None

    # ── conscheck ─────────────────────────────────────────────────────────────
    def conscheck(self, constraints, solution, checkintegrality,
                  checklprows, printreason, completely):
        """
        Verify a candidate solution.  Called by SCIP for every integer-feasible
        point before it is accepted as a new incumbent.
        """
        solver = self.solver

        sol = {
            (i, j): self.model.getSolVal(solution, var)
            for (i, j), var in solver.x.items()
        }
        theta_val = self.model.getSolVal(solution, solver.theta)

        subtours = solver._find_subtours_from_sol(sol)
        if subtours:
            return {"result": SCIP_RESULT.INFEASIBLE}

        sequence = solver._get_sequence_from_sol(sol)
        if sequence is None:
            return {"result": SCIP_RESULT.INFEASIBLE}

        x_bar   = solver._build_x_bar_from_sequence(sequence)
        dsp_obj, _ = solver._solve_dsp_with_xbar(x_bar)
        if dsp_obj is None:
            return {"result": SCIP_RESULT.FEASIBLE}

        if dsp_obj > theta_val + 1e-6:
            return {"result": SCIP_RESULT.INFEASIBLE}

        if dsp_obj < self.best_objective:
            self.best_objective = dsp_obj
            self.best_solution  = sequence[:]

        return {"result": SCIP_RESULT.FEASIBLE}

    # ── consenfolp ────────────────────────────────────────────────────────────
    def consenfolp(self, constraints, nusefulconss, solinfeasible):
        """
        Enforce constraints for the current LP solution.

        - Integer solutions: full B&B-C logic (subtour elimination + Benders).
        - Fractional solutions: subtour elimination on rounded solution;
          when use_fractional_cuts=True, also add Benders user cuts derived
          from the fractional x̄.
        """
        solver = self.solver
        self.iteration_count += 1

        sol = {
            (i, j): self.model.getVal(var)
            for (i, j), var in solver.x.items()
        }
        theta_val = self.model.getVal(solver.theta)

        is_integer = all(v < 1e-5 or v > 1.0 - 1e-5 for v in sol.values())

        if not is_integer:
            added_something = False

            # ── Fractional: SECs on rounded solution ─────────────────────
            sol_r    = {k: round(v) for k, v in sol.items()}
            subtours = solver._find_subtours_from_sol(sol_r)
            for st in subtours:
                lhs = scip_quicksum(
                    solver.x[i, j]
                    for i in st for j in st
                    if i != j and (i, j) in solver.x
                )
                self.model.addCons(
                    lhs <= len(st) - 1,
                    name=f"sec_frac_{self.cuts_added}",
                    local=False
                )
                self.cuts_added += 1
                added_something = True

            # ── Fractional Benders cut (use_fractional_cuts only) ────────
            if solver.use_fractional_cuts:
                x_bar = {k: v for k, v in sol.items() if v > 1e-8}
                if x_bar:
                    dsp_obj, duals = solver._solve_dsp_with_xbar(x_bar)
                    if dsp_obj is not None and dsp_obj > theta_val + 1e-6:
                        cut_cons = solver._generate_benders_cut_scip(duals)
                        self.model.addCons(
                            cut_cons,
                            name=f"benders_frac_{self.cuts_added}",
                            local=False
                        )
                        self.cuts_added += 1
                        added_something = True

            if added_something:
                return {"result": SCIP_RESULT.CONSADDED}
            return {"result": SCIP_RESULT.FEASIBLE}

        # ── Integer solution: full B&B-C logic ──────────────────────────────

        # Step A: Subtour elimination
        subtours = solver._find_subtours_from_sol(sol)
        if subtours:
            for st in subtours:
                lhs = scip_quicksum(
                    solver.x[i, j]
                    for i in st for j in st
                    if i != j and (i, j) in solver.x
                )
                self.model.addCons(
                    lhs <= len(st) - 1,
                    name=f"sec_{self.cuts_added}",
                    local=False
                )
                self.cuts_added += 1
            return {"result": SCIP_RESULT.CONSADDED}

        # Step B: Extract Hamiltonian sequence
        sequence = solver._get_sequence_from_sol(sol)
        if sequence is None:
            return {"result": SCIP_RESULT.FEASIBLE}

        # Step C: Solve DSP
        x_bar             = solver._build_x_bar_from_sequence(sequence)
        dsp_obj, duals    = solver._solve_dsp_with_xbar(x_bar)
        if dsp_obj is None:
            return {"result": SCIP_RESULT.FEASIBLE}

        # Step D: Benders cut
        if dsp_obj > theta_val + 1e-6:
            cut_cons = solver._generate_benders_cut_scip(duals)
            self.model.addCons(
                cut_cons,
                name=f"benders_{self.cuts_added}",
                local=False
            )
            self.cuts_added += 1
            return {"result": SCIP_RESULT.CONSADDED}

        if dsp_obj < self.best_objective:
            self.best_objective = dsp_obj
            self.best_solution  = sequence[:]

        return {"result": SCIP_RESULT.FEASIBLE}

    # ── consenfops ────────────────────────────────────────────────────────────
    def consenfops(self, constraints, nusefulconss, solinfeasible, objinfeasible):
        """Pass-through for pseudo-solutions."""
        return {"result": SCIP_RESULT.FEASIBLE}

    # ── conslock ──────────────────────────────────────────────────────────────
    def conslock(self, constraint, locktype, nlockspos, nlocksneg):
        """No static constraint objects to lock."""
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Main solver class
# ─────────────────────────────────────────────────────────────────────────────

class BranchAndBendersCutSSP_SCIP:
    """
    Solves SSP via Branch-and-Benders-Cut with SCIP (PySCIPOPT).

    Master Problem:
        min θ
        s.t. degree constraints (TSP)
             θ ≥ Σ w_ij x_ij  (pairwise lower bounds)
             subtour elimination   (via BendersConshdlr.consenfolp)
             Benders optimality cuts  (via BendersConshdlr.consenfolp)

    Parameters
    ----------
    n_jobs, n_tools, capacity, tool_req : problem data
    worker_lp_reuse : bool
        Build the DSP model once and reuse it per callback call, updating
        only objective coefficients.  Uses Gurobi if available, otherwise
        falls back to a fresh SCIP LP per call.
    use_fractional_cuts : bool
        Also add Benders cuts at fractional LP nodes (in consenfolp).
    parallel : bool
        Allow SCIP to use multiple threads.  Default: single-threaded.
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

        # Master problem model + variables
        self.model = None
        self.x     = {}    # x[i,j]  arc variables
        self.theta = None  # surrogate cost θ
        self.hdlr  = None  # constraint handler instance

        # Shared DSP model (worker_lp_reuse=True)
        # Stored as a dict with keys 'model', 'lam', 'mu', 'nu', 'eta'
        self._shared_dsp = None
        self._dsp_lock   = threading.Lock()  # guards _shared_dsp creation

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
        Build the TSP master problem with surrogate θ, then attach
        the BendersConshdlr constraint handler.
        """
        if not HAS_SCIP:
            raise ImportError(
                "pyscipopt not available.  "
                "Install SCIP and pyscipopt (pip install pyscipopt)."
            )

        self.model = SCIPModel("SSP_BranchAndBendersCut_SCIP")
        if not verbose:
            self.model.hideOutput()

        n = self.n_jobs

        # ── Arc variables x[i,j] ∈ {0,1} ────────────────────────────────
        for i in range(n):
            for j in range(n):
                if i != j:
                    self.x[i, j] = self.model.addVar(
                        vtype="B", name=f"x_{i}_{j}"
                    )

        # ── Surrogate cost θ ≥ 0 ─────────────────────────────────────────
        self.theta = self.model.addVar(vtype="C", lb=0.0, name="theta")

        # ── Objective: minimise θ ────────────────────────────────────────
        self.model.setObjective(self.theta, "minimize")

        # ── Degree constraints ────────────────────────────────────────────
        for i in range(n):
            self.model.addCons(
                scip_quicksum(self.x[i, j] for j in range(n) if i != j) == 1,
                name=f"out_{i}"
            )
            self.model.addCons(
                scip_quicksum(self.x[j, i] for j in range(n) if j != i) == 1,
                name=f"in_{i}"
            )

        # ── Initial lower bound: θ ≥ Σ w_ij x_ij ─────────────────────────
        self.model.addCons(
            self.theta >= scip_quicksum(
                self.w[i, j] * self.x[i, j]
                for i in range(n) for j in range(n) if i != j
            ),
            name="theta_lb"
        )

        # ── Parallel / threading ──────────────────────────────────────────
        if not self.parallel:
            self.model.setParam("lp/threads", 1)
        # Note: SCIP constraint handlers are not fully thread-safe in all
        # versions; parallel=True is provided for experimentation.

        # ── Register constraint handler ───────────────────────────────────
        self.hdlr = BendersConshdlr(self)
        self.model.includeConshdlr(
            self.hdlr,
            name          = "BendersConshdlr",
            desc          = "Subtour elimination and Benders optimality cuts",
            sepapriority  = 0,
            enfopriority  = -1,
            chckpriority  = -1,
            sepafreq      = -1,
            propfreq      = -1,
            eagerfreq     = 100,
            maxprerounds  = 0,
            delaysepa     = False,
            delayprop     = False,
            needscons     = False
        )

        if verbose:
            print(f"Master Problem built: {n} jobs, {n*(n-1)} arc variables")

        return self.model

    # ─────────────────────────────────────────────────────────────────────────
    # Solution helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _find_subtours_from_sol(self, sol):
        """Detect all subtours from binary x-solution values."""
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
        """Extract the Hamiltonian sequence from a subtour-free solution."""
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
        """Build x̄ dict from Hamiltonian sequence (arc → 1.0)."""
        n     = len(sequence)
        x_bar = {}
        for k in range(n - 1):
            x_bar[sequence[k], sequence[k + 1]] = 1.0
        x_bar[sequence[-1], sequence[0]] = 1.0
        return x_bar

    # ─────────────────────────────────────────────────────────────────────────
    # DSP routing
    # ─────────────────────────────────────────────────────────────────────────

    def _solve_dsp_with_xbar(self, x_bar):
        """
        Dispatch to fresh or reuse DSP solver.

        Parameters
        ----------
        x_bar : dict {(i,j): float}

        Returns
        -------
        (obj_val, duals) or (None, {})
        """
        if self.worker_lp_reuse:
            return self._solve_dsp_reuse(x_bar)
        else:
            return self._solve_dsp_fresh(x_bar)

    # ── Worker LP reuse (Gurobi-backed) ───────────────────────────────────────

    def _build_reuse_dsp_gurobi(self):
        """
        Build a Gurobi DSP model once.  lam objective coefficients start at 0;
        they are updated per call via _solve_dsp_reuse.

        Returns
        -------
        dict: {model, lam, mu, nu, eta}
        """
        n        = self.n_jobs
        T        = list(range(self.n_tools))
        tool_req = self.tool_req

        dsp = gp.Model("DSP_reuse")
        dsp.setParam('OutputFlag', 0)
        dsp.setParam('Method', 1)  # dual simplex for efficient warm starts

        lam = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in T:
                        lam[i, j, t] = dsp.addVar(lb=0.0, obj=0.0,
                                                   name=f"lam_{i}_{j}_{t}")

        mu  = {j: dsp.addVar(lb=0.0,
                              obj=-float(self.capacity),
                              name=f"mu_{j}") for j in range(n)}
        nu  = {}
        eta = {}
        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                obj_v = 1.0 if t in Tj else 0.0
                nu[j, t]  = dsp.addVar(lb=-GRB.INFINITY, obj=obj_v,
                                       name=f"nu_{j}_{t}")
                eta[j, t] = dsp.addVar(lb=-GRB.INFINITY, obj=0.0,
                                       name=f"eta_{j}_{t}")

        dsp.ModelSense = GRB.MAXIMIZE
        dsp.update()

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
                dsp.addConstr(lhs <= 0, name=f"dy_{j}_{t}")

        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                eta_term = eta[j, t] if t not in Tj else 0
                rhs = 1.0 if t in Tj else 0.0
                lhs = (
                    gp.quicksum(lam[i, j, t] for i in range(n) if i != j)
                    + eta_term
                )
                dsp.addConstr(lhs <= rhs, name=f"dz_{j}_{t}")

        return {'model': dsp, 'lam': lam, 'mu': mu, 'nu': nu, 'eta': eta}

    def _get_reuse_dsp(self):
        """Return (or lazily create) the shared reuse DSP model."""
        if self._shared_dsp is None:
            with self._dsp_lock:
                if self._shared_dsp is None:
                    if HAS_GUROBI:
                        self._shared_dsp = self._build_reuse_dsp_gurobi()
                    else:
                        # No reuse DSP available without Gurobi for SCIP backend
                        # Fall through to fresh SCIP LP (will happen in _solve_dsp_reuse)
                        self._shared_dsp = {}
        return self._shared_dsp

    def _solve_dsp_reuse(self, x_bar):
        """Solve DSP via model reuse (Gurobi-backed if available)."""
        dsp_data = self._get_reuse_dsp()

        if HAS_GUROBI and 'model' in dsp_data:
            dsp  = dsp_data['model']
            lam  = dsp_data['lam']
            mu   = dsp_data['mu']
            nu   = dsp_data['nu']
            eta  = dsp_data['eta']

            # Update lam objective coefficients
            for (i, j, t), var in lam.items():
                var.Obj = x_bar.get((i, j), 0.0) - 1.0
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

        # Fallback: fresh SCIP LP
        return self._solve_dsp_fresh(x_bar)

    # ── Fresh DSP ─────────────────────────────────────────────────────────────

    def _solve_dsp_fresh(self, x_bar):
        """Build and solve the DSP from scratch for a given x̄."""
        if HAS_GUROBI:
            return self._solve_dsp_gurobi(x_bar)
        if HAS_DOCPLEX:
            return self._solve_dsp_docplex(x_bar)
        return self._solve_dsp_scip(x_bar)

    # Legacy entry point used by conscheck
    def _solve_dual_subproblem(self, sequence):
        """Solve the DSP for a fixed integer sequence."""
        if sequence is None:
            return None, {}
        x_bar = self._build_x_bar_from_sequence(sequence)
        return self._solve_dsp_with_xbar(x_bar)

    def _solve_dsp_scip(self, x_bar):
        """
        Solve the Dual LP using a separate nested SCIP instance.
        Self-contained – no additional solver licence needed.
        """
        n        = self.n_jobs
        T        = range(self.n_tools)
        tool_req = self.tool_req

        dsp = SCIPModel("DSP_LP")
        dsp.hideOutput()
        dsp.setParam("display/verblevel", 0)
        dsp.setParam("presolving/maxrounds", 0)
        dsp.setParam("separating/maxrounds", 0)

        lam = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in T:
                        lam[i, j, t] = dsp.addVar(
                            lb=0.0, vtype="C", name=f"lam_{i}_{j}_{t}"
                        )

        mu = {j: dsp.addVar(lb=0.0, vtype="C", name=f"mu_{j}") for j in range(n)}

        nu  = {}
        eta = {}
        for j in range(n):
            for t in T:
                nu[j, t]  = dsp.addVar(lb=None, ub=None, vtype="C", name=f"nu_{j}_{t}")
                eta[j, t] = dsp.addVar(lb=None, ub=None, vtype="C", name=f"eta_{j}_{t}")

        obj = scip_quicksum(
            (x_bar.get((i, j), 0) - 1) * lam[i, j, t]
            for i in range(n) for j in range(n) if i != j
            for t in T
        )
        obj = obj + scip_quicksum(-self.capacity * mu[j] for j in range(n))
        obj = obj + scip_quicksum(
            nu[j, t]
            for j in range(n) for t in tool_req.get(j, [])
        )
        dsp.setObjective(obj, "maximize")

        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                nu_term = nu[j, t] if t in Tj else 0
                lhs = (
                    -mu[j]
                    - scip_quicksum(lam[i, j, t] for i in range(n) if i != j)
                    + scip_quicksum(lam[j, k, t] for k in range(n) if k != j)
                    + nu_term
                )
                dsp.addCons(lhs <= 0, name=f"dy_{j}_{t}")

        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                eta_term = eta[j, t] if t not in Tj else 0
                rhs      = 1.0 if t in Tj else 0.0
                lhs = (
                    scip_quicksum(lam[i, j, t] for i in range(n) if i != j)
                    + eta_term
                )
                dsp.addCons(lhs <= rhs, name=f"dz_{j}_{t}")

        dsp.optimize()

        if dsp.getStatus() != "optimal":
            return None, {}

        duals = {}
        for (i, j, t), v in lam.items():
            duals['lambda', i, j, t] = dsp.getVal(v)
        for j, v in mu.items():
            duals['mu', j] = dsp.getVal(v)
        for (j, t), v in nu.items():
            duals['nu', j, t] = dsp.getVal(v)
        for (j, t), v in eta.items():
            duals['eta', j, t] = dsp.getVal(v)

        return dsp.getObjVal(), duals

    def _solve_dsp_gurobi(self, x_bar):
        """Solve the Dual LP using Gurobi (faster alternative)."""
        n        = self.n_jobs
        T        = range(self.n_tools)
        tool_req = self.tool_req

        dsp = gp.Model("DSP")
        dsp.setParam('OutputFlag', 0)

        lam = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in T:
                        lam[i, j, t] = dsp.addVar(lb=0.0, name=f"lam_{i}_{j}_{t}")

        mu = {j: dsp.addVar(lb=0.0, name=f"mu_{j}") for j in range(n)}
        nu, eta = {}, {}
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

    def _solve_dsp_docplex(self, x_bar):
        """Solve the Dual LP using docplex / CPLEX."""
        n        = self.n_jobs
        T        = range(self.n_tools)
        tool_req = self.tool_req

        dsp     = DocplexModel("DSP", log_output=False)
        neg_inf = dsp.minus_infinity

        lam = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in T:
                        lam[i, j, t] = dsp.continuous_var(lb=0.0, name=f"lam_{i}_{j}_{t}")

        mu  = {j: dsp.continuous_var(lb=0.0, name=f"mu_{j}") for j in range(n)}
        nu, eta = {}, {}
        for j in range(n):
            for t in T:
                nu[j, t]  = dsp.continuous_var(lb=neg_inf, name=f"nu_{j}_{t}")
                eta[j, t] = dsp.continuous_var(lb=neg_inf, name=f"eta_{j}_{t}")

        obj = dsp.sum(
            (x_bar.get((i, j), 0) - 1) * lam[i, j, t]
            for i in range(n) for j in range(n) if i != j for t in T
        )
        obj += dsp.sum(-self.capacity * mu[j] for j in range(n))
        obj += dsp.sum(nu[j, t] for j in range(n) for t in tool_req.get(j, []))
        dsp.maximize(obj)

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
                dsp.add_constraint(lhs <= 0)

        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                eta_term = eta[j, t] if t not in Tj else 0
                rhs      = 1.0 if t in Tj else 0.0
                lhs = (
                    dsp.sum(lam[i, j, t] for i in range(n) if i != j)
                    + eta_term
                )
                dsp.add_constraint(lhs <= rhs)

        sol = dsp.solve(log_output=False)
        if sol is None:
            return None, {}

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

    # ─────────────────────────────────────────────────────────────────────────
    # Benders cut (SCIP expression form)
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_benders_cut_scip(self, duals):
        """
        Return a SCIP ExprCons for the Benders optimality cut:

            θ ≥ Σ_{i,j,t} (x_ij - 1) λ̄_ijt  - Σ_j c μ̄_j  + Σ_{j,t∈T_j} ν̄_jt

        Rearranged as:  θ ≥ Σ coeff_ij * x_ij  +  cut_rhs_constant
        """
        n = self.n_jobs

        coeff = {
            (i, j): sum(
                duals.get(('lambda', i, j, t), 0.0)
                for t in range(self.n_tools)
            )
            for i in range(n) for j in range(n) if i != j
        }

        cut_rhs = 0.0
        for j in range(n):
            cut_rhs -= self.capacity * duals.get(('mu', j), 0.0)
        for j in range(n):
            for t in self.tool_req.get(j, []):
                cut_rhs += duals.get(('nu', j, t), 0.0)
        for c in coeff.values():
            cut_rhs -= c

        rhs_expr = scip_quicksum(
            c * self.x[i, j]
            for (i, j), c in coeff.items()
            if c != 0.0 and (i, j) in self.x
        )

        return self.theta >= rhs_expr + cut_rhs

    # ─────────────────────────────────────────────────────────────────────────
    # Solve
    # ─────────────────────────────────────────────────────────────────────────

    def solve(self, time_limit=3600, verbose=True):
        """
        Run Branch-and-Benders-Cut to global optimality (or time limit).

        Returns
        -------
        status   : str
        obj_val  : float or None
        sequence : list[int] or None
        """
        if self.model is None:
            self.build_master_problem(verbose=verbose)

        self.model.setParam("limits/time", float(time_limit))

        self.model.optimize()

        status = self.model.getStatus()

        try:
            obj_val  = self.model.getObjVal()
            sol      = {(i, j): self.model.getVal(var) for (i, j), var in self.x.items()}
            sequence = self._get_sequence_from_sol(sol)
        except Exception:
            obj_val  = self.hdlr.best_objective if self.hdlr.best_objective < float('inf') else None
            sequence = self.hdlr.best_solution

        self.cuts_added      = self.hdlr.cuts_added
        self.iteration_count = self.hdlr.iteration_count
        if self.hdlr.best_objective < self.best_objective:
            self.best_objective = self.hdlr.best_objective
            self.best_solution  = self.hdlr.best_solution

        if verbose:
            dsp_name = ('Gurobi (reuse)' if self.worker_lp_reuse and HAS_GUROBI
                        else 'Gurobi' if HAS_GUROBI
                        else 'docplex' if HAS_DOCPLEX
                        else 'SCIP (nested)')
            sep = '=' * 60
            print(f"\n{sep}")
            print(f"Solution Status : {status}")
            print(f"Objective Value : {obj_val}")
            print(f"Sequence        : {sequence}")
            print(f"Iterations      : {self.iteration_count}")
            print(f"Cuts Added      : {self.cuts_added}")
            print(f"DSP solver      : {dsp_name}")
            print(f"{sep}\n")

        return status, obj_val, sequence


# ─────────────────────────────────────────────────────────────────────────────
# Convenience wrapper
# ─────────────────────────────────────────────────────────────────────────────

def solve_ssp_branch_and_benders_scip(instance_path, time_limit=3600, verbose=True,
                                       worker_lp_reuse=False, use_fractional_cuts=False,
                                       parallel=False):
    """
    Load an SSP instance file and solve it with Branch-and-Benders-Cut (SCIP).
    """
    n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance(instance_path)

    if verbose:
        sep = '=' * 60
        print(f"\n{sep}")
        print(f"Instance : {Path(instance_path).name}")
        print(f"Jobs: {n_jobs}  Tools: {n_tools}  Capacity: {capacity}")
        print(f"{sep}\n")

    solver = BranchAndBendersCutSSP_SCIP(
        n_jobs, n_tools, capacity, tool_req,
        worker_lp_reuse=worker_lp_reuse,
        use_fractional_cuts=use_fractional_cuts,
        parallel=parallel
    )
    solver.build_master_problem(verbose=verbose)
    return solver.solve(time_limit=time_limit, verbose=verbose)


if __name__ == "__main__":
    if not HAS_SCIP:
        print("ERROR: pyscipopt not installed.  pip install pyscipopt")
        import sys
        sys.exit(1)

    instance_file = (
        Path(__file__).parent.parent / "Instances" / "Shankar" / "shankar-example.txt"
    )

    if instance_file.exists():
        solve_ssp_branch_and_benders_scip(str(instance_file), verbose=True)
    else:
        print(f"Instance file not found: {instance_file}")
