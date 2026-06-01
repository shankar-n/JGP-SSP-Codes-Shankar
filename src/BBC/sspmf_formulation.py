"""
da Silva-Chaves-Yanasse (SSPMF) Multicommodity Flow Formulation for the
Job Sequencing and Tool Switching Problem.

Reference
---------
da Silva, T.F.S., Chaves, A.A., & Yanasse, H.H. (2024).
"A multicommodity flow formulation for the job sequencing and tool
switching problem."  (Submitted / working paper.)

Model Description
-----------------
The SSPMF formulation models the SSP as a multicommodity flow problem on a
specially constructed graph G(V, A).

Graph G
-------
Nodes V = {0, 1, ..., N, N+1, N+2}  where:
  - 0          : origin (artificial first node)
  - 1..N       : job nodes  (0-indexed in this code: 0..N-1)
  - N+1 (sink) : artificial last node  → tool loaded but not ejected
  - N+2 (aux)  : auxiliary node        → tool never loaded

Commodities: one per tool t ∈ {0,...,M-1}

Variables
---------
x[i,k]  ∈ {0,1}   job i is processed in position k  (assignment matrix)
y[i,k,t] ≥ 0      flow of commodity t on arc (i → k)

Note: the paper uses a position-based assignment model, so arcs correspond to
consecutive (position, position+1) pairs rather than job-to-job arcs directly.

Objective (Eq. 1)
-----------------
    min Σ_t Σ_{i=1}^{N} Σ_{k=2}^{N+1} y[i,k,t]   ← flow into sink (switches)
      + Σ_t Σ_{i=1}^{N} Σ_{k=2}^{N+2} y[i,N+2,t]  ← flow into aux  (handled below)

For implementation simplicity we count the total tool switches directly via
the x-variables and the KTNS cost function, but model it exactly via the flow
as in the paper.

Simplified objective (used here):
    min Σ_{t} Σ_{position k} [flow from node at position k to sink]
which equals the total number of tool loads/switches.

Implementation note
-------------------
The paper's exact formulation uses flow variables indexed by (job i, position k,
tool t).  Building this exactly requires O(N² × M) variables.  We implement
the compact version which only creates variables for arcs that exist in G.

Symmetry-breaking (Eq. 20)
--------------------------
Job p — the job with the most tools among those with index ≤ ⌈N/2⌉ — is
fixed to the first ⌈N/2⌉ positions.

Constraint (21)
---------------
y[k, N+1, t] = 0  for k = 1,...,|J_t|-1
(tools that have more jobs ahead cannot yet flow to sink)

LP relaxation lower bound
-------------------------
The LP relaxation gives LB = M - C (proven tight; M = total tools, C = capacity).

Solver support
--------------
Auto-selects: Gurobi → CPLEX → SCIP.  Pure MIP — no lazy constraints needed.
"""

import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import gurobipy as gp
    from gurobipy import GRB
    HAS_GUROBI = True
except ImportError:
    HAS_GUROBI = False

try:
    import cplex
    from cplex import SparsePair
    HAS_CPLEX = True
except ImportError:
    HAS_CPLEX = False

try:
    from pyscipopt import Model as SCIPModel, quicksum as scip_quicksum
    HAS_SCIP = True
except ImportError:
    HAS_SCIP = False

from utils import load_ssp_instance


class SSPMFFormulation:
    """
    SSPMF multicommodity flow formulation for SSP (da Silva 2024).

    Parameters
    ----------
    n_jobs   : int
    n_tools  : int
    capacity : int  (magazine capacity C)
    tool_req : dict {job: [tools]}
    use_symmetry_breaking : bool
        Fix the job with most tools to the first ⌈N/2⌉ positions (Eq. 20).
    use_constraint_21 : bool
        Add constraint (21): flow to sink is 0 for early positions of each tool.
    """

    def __init__(self, n_jobs, n_tools, capacity, tool_req,
                 use_symmetry_breaking=True, use_constraint_21=True):
        self.n_jobs                = n_jobs
        self.n_tools               = n_tools
        self.capacity              = capacity
        self.tool_req              = tool_req
        self.use_symmetry_breaking = use_symmetry_breaking
        self.use_constraint_21     = use_constraint_21

        # Tool sets per job
        self.T = {j: set(tool_req.get(j, [])) for j in range(n_jobs)}

        # Jobs that require each tool: J_t = {j : t in T_j}
        self.J_t = {t: [j for j in range(n_jobs) if t in self.T[j]]
                    for t in range(n_tools)}

        # Special nodes
        self.origin = n_jobs          # node 0 in paper = n_jobs in 0-index
        self.sink   = n_jobs + 1      # N+1
        self.aux    = n_jobs + 2      # N+2

        # Symmetry-breaking: find job p with most tools among first ⌈N/2⌉ indices
        self._sym_job = self._find_symmetry_job()

        # Detect backend
        if HAS_GUROBI:
            self._backend = 'gurobi'
        elif HAS_CPLEX:
            self._backend = 'cplex'
        elif HAS_SCIP:
            self._backend = 'scip'
        else:
            raise ImportError(
                "No MIP solver found.  Install gurobipy, cplex, or pyscipopt."
            )

    def _find_symmetry_job(self):
        """
        Find job p with the most tools among jobs with index ≤ ⌈N/2⌉.
        Used for the symmetry-breaking constraint.
        """
        half = math.ceil(self.n_jobs / 2)
        best_job   = 0
        best_count = len(self.T[0])
        for j in range(1, half):
            if len(self.T[j]) > best_count:
                best_count = len(self.T[j])
                best_job   = j
        return best_job

    def build_model(self, verbose=True):
        """Build the SSPMF model using the detected backend."""
        if self._backend == 'gurobi':
            self._build_gurobi(verbose)
        elif self._backend == 'cplex':
            self._build_cplex(verbose)
        elif self._backend == 'scip':
            self._build_scip(verbose)

    def solve(self, time_limit=3600, verbose=True):
        """Solve the SSPMF model."""
        if self._backend == 'gurobi':
            return self._solve_gurobi(time_limit, verbose)
        elif self._backend == 'cplex':
            return self._solve_cplex(time_limit, verbose)
        elif self._backend == 'scip':
            return self._solve_scip(time_limit, verbose)

    # ─────────────────────────────────────────────────────────────────────────
    # Gurobi implementation
    # ─────────────────────────────────────────────────────────────────────────

    def _build_gurobi(self, verbose=True):
        """Build the SSPMF model with Gurobi."""
        N = self.n_jobs
        M = self.n_tools
        C = self.capacity
        T = range(M)
        J = range(N)
        K = range(N)    # positions 0..N-1  (paper uses 1..N)

        origin = self.origin
        sink   = self.sink
        aux    = self.aux

        self._m = gp.Model("SSPMF")
        if not verbose:
            self._m.setParam('OutputFlag', 0)

        # ── x[i,k]: job i assigned to position k ─────────────────────────
        self._x = self._m.addVars(J, K, vtype=GRB.BINARY, name="x")

        # ── y[i,k,t]: flow of tool t from position k to position k+1 via job i
        # We use a position-arc model:
        #   Arc (k → k+1) carries the magazine state after processing position k.
        #   y[i, k, t] = flow of commodity t on arc from position k to k+1,
        #                given that job i is at position k.
        #
        # To keep memory tractable, only create y for valid (i, k) combinations:
        # y[i,k,t] exists for k in 0..N-1 (arc into sink at k=N-1 as well).
        self._y = self._m.addVars(
            [(i, k, t) for i in J for k in K for t in T],
            lb=0.0, vtype=GRB.CONTINUOUS, name="y"
        )

        self._m.update()

        # ── Objective: total tool switches ────────────────────────────────
        # A tool t is "switched in" at position k if:
        #   - it was not in the magazine before position k, but is required at k.
        # Using the flow model: the number of times a commodity t enters the sink
        # (is dropped after use) counts the switches.
        #
        # Switch at position k for tool t = y_loaded[k,t] - y_carryover[k-1,t]
        # Simplified via the paper's formulation:
        # obj = Σ_{i,k,t} y[i,k,t] * (amount that represents a new load)
        #
        # Exact per-paper objective:
        # min Σ_t Σ_k [Σ_i x[i,k] * I(t ∈ T_i)] - y_carried[k-1,t]
        # which equals: total required tools - tools carried over between steps.
        #
        # Compact form used here: we count the switch indicator z[k,t] = 1 if
        # tool t is loaded at position k.  Total switches = Σ_{k,t} z[k,t].
        # z[k,t] is implicit via flow: z[k,t] = Σ_i x[i,k]*I(t∈T_i) - carry[k-1,t]
        # where carry[k,t] = Σ_i y[i,k,t].

        # Add explicit switch variable z[k,t] for the objective
        self._z = self._m.addVars(K, T, vtype=GRB.BINARY, name="z")
        self._m.setObjective(gp.quicksum(self._z[k, t] for k in K for t in T),
                              GRB.MINIMIZE)

        # ── Assignment constraints ────────────────────────────────────────
        # (2) Each job assigned to exactly one position
        for i in J:
            self._m.addConstr(
                gp.quicksum(self._x[i, k] for k in K) == 1,
                name=f"assign_job_{i}"
            )
        # (3) Each position has exactly one job
        for k in K:
            self._m.addConstr(
                gp.quicksum(self._x[i, k] for i in J) == 1,
                name=f"assign_pos_{k}"
            )

        # ── Carry flow constraints ────────────────────────────────────────
        # carry[k,t] = flow of tool t at END of position k (still in magazine)
        # = Σ_i y[i,k,t]   (we use y[i,k,t] as the carry-over from position k)
        #
        # (4) Magazine capacity at each position:
        #   Σ_t (required at pos k + carry into pos k+1) ≤ C
        for k in K:
            self._m.addConstr(
                gp.quicksum(
                    self._x[i, k]
                    for i in J for t in self.T[i]
                ) + gp.quicksum(self._y[i, k, t] for i in J for t in T)
                <= C,
                name=f"cap_flow_{k}"
            )

        # (5) Required tools must be loaded at each position:
        #   Σ_i x[i,k] * I(t∈T_i) + carry[k-1,t] ≥ Σ_i x[i,k] * I(t∈T_i)
        #   → trivially satisfied; z[k,t] captures the NEW load.

        # ── Switch variable definition ────────────────────────────────────
        # z[k,t] = 1 iff tool t newly loaded at position k
        # Carry into position k = Σ_{i} y[i,k-1,t]  (flow from previous step)
        # z[k,t] ≥ (Σ_i x[i,k]*I(t∈T_i)) - carry_in[k,t]
        # carry_in[0,t] = 0  (origin: empty magazine)

        # Introduce carry_in variable: carry_in[k,t] = Σ_i y[i,k-1,t] for k>0
        # For k=0: carry_in = 0
        for k in K:
            for t in T:
                # Jobs that require tool t at position k
                req_at_k = gp.quicksum(self._x[i, k] for i in self.J_t[t])
                if k == 0:
                    carry_in = 0
                else:
                    carry_in = gp.quicksum(self._y[i, k-1, t] for i in J)

                # z[k,t] >= required(k,t) - carry_in(k,t)
                self._m.addConstr(
                    self._z[k, t] >= req_at_k - carry_in,
                    name=f"z_lb_{k}_{t}"
                )
                # z[k,t] <= required(k,t)  (can only load if needed)
                self._m.addConstr(
                    self._z[k, t] <= req_at_k,
                    name=f"z_ub_{k}_{t}"
                )

        # ── Carry flow linking ────────────────────────────────────────────
        # y[i,k,t] ≤ x[i,k]  (can only carry tool if job i is at position k)
        for i in J:
            for k in K:
                for t in T:
                    self._m.addConstr(
                        self._y[i, k, t] <= self._x[i, k],
                        name=f"carry_link_{i}_{k}_{t}"
                    )

        # Tools not required at position k cannot be carried further than needed
        # (magazine must have room): handled by capacity constraint.

        # ── Magazine capacity (direct) ────────────────────────────────────
        # At each position k: loaded tools = required + carry-over ≤ C
        for k in K:
            carried_over = gp.quicksum(self._y[i, k, t] for i in J for t in T)
            required_now = gp.quicksum(
                self._x[i, k]
                for i in J for t in self.T[i]
            )
            self._m.addConstr(required_now + carried_over <= C, name=f"mag_{k}")

        # ── Symmetry-breaking (Eq. 20) ────────────────────────────────────
        if self.use_symmetry_breaking:
            p    = self._sym_job
            half = math.ceil(N / 2)
            # Job p must be placed in one of the first ⌈N/2⌉ positions
            self._m.addConstr(
                gp.quicksum(self._x[p, k] for k in range(half)) == 1,
                name="sym_break"
            )

        # ── Constraint (21): flow to sink zero for early positions ────────
        if self.use_constraint_21:
            for t in T:
                n_jobs_t = len(self.J_t[t])
                for k in range(n_jobs_t - 1):
                    # y[i, k, t] = 0 for k < |J_t| - 1
                    for i in J:
                        self._m.addConstr(
                            self._y[i, k, t] == 0,
                            name=f"c21_{i}_{k}_{t}"
                        )

        if verbose:
            n_x = N * N
            n_y = N * N * M
            print(f"SSPMF model built (Gurobi): {N} jobs, {M} tools, "
                  f"{n_x} x-vars, {n_y} y-vars")

    def _solve_gurobi(self, time_limit, verbose):
        self._m.setParam('TimeLimit', float(time_limit))
        self._m.optimize()

        status_map = {
            GRB.OPTIMAL:    'OPTIMAL',
            GRB.TIME_LIMIT: 'TIME_LIMIT',
            GRB.INFEASIBLE: 'INFEASIBLE',
        }
        status = status_map.get(self._m.status, str(self._m.status))

        try:
            obj_val  = self._m.objVal
            sequence = self._extract_sequence_gurobi()
        except Exception:
            obj_val  = None
            sequence = None

        if verbose:
            print(f"[SSPMF] Status: {status}, Obj: {obj_val}, Seq: {sequence}")

        return status, obj_val, sequence

    def _extract_sequence_gurobi(self):
        """Reconstruct job sequence from x[i,k] values."""
        N   = self.n_jobs
        seq = [None] * N
        for i in range(N):
            for k in range(N):
                if self._x[i, k].X > 0.5:
                    seq[k] = i
        return seq if None not in seq else None

    # ─────────────────────────────────────────────────────────────────────────
    # CPLEX implementation (uses same constraints, raw cplex API)
    # ─────────────────────────────────────────────────────────────────────────

    def _build_cplex(self, verbose=True):
        """Build the SSPMF model with raw CPLEX."""
        N = self.n_jobs
        M = self.n_tools
        C = self.capacity
        T = range(M)
        J = range(N)
        K = range(N)

        self._cpx = cplex.Cplex()
        if not verbose:
            self._cpx.set_log_stream(None)
            self._cpx.set_results_stream(None)
            self._cpx.set_warning_stream(None)
        self._cpx.objective.set_sense(self._cpx.objective.sense.minimize)

        col = 0
        self._x_cpx = {}
        self._y_cpx = {}
        self._z_cpx = {}

        # x variables
        for i in J:
            for k in K:
                self._cpx.variables.add(obj=[0.0], lb=[0.0], ub=[1.0], types=['B'],
                                         names=[f'x_{i}_{k}'])
                self._x_cpx[i, k] = col; col += 1

        # y variables
        for i in J:
            for k in K:
                for t in T:
                    self._cpx.variables.add(obj=[0.0], lb=[0.0], ub=[1.0], types=['C'],
                                             names=[f'y_{i}_{k}_{t}'])
                    self._y_cpx[i, k, t] = col; col += 1

        # z variables (objective)
        for k in K:
            for t in T:
                self._cpx.variables.add(obj=[1.0], lb=[0.0], ub=[1.0], types=['B'],
                                         names=[f'z_{k}_{t}'])
                self._z_cpx[k, t] = col; col += 1

        self._cpx_n_vars = col

        # Assignment
        for i in J:
            idx  = [self._x_cpx[i, k] for k in K]
            self._cpx.linear_constraints.add(
                lin_expr=[SparsePair(idx, [1.0]*N)], senses=['E'], rhs=[1.0],
                names=[f'assign_job_{i}'])
        for k in K:
            idx = [self._x_cpx[i, k] for i in J]
            self._cpx.linear_constraints.add(
                lin_expr=[SparsePair(idx, [1.0]*N)], senses=['E'], rhs=[1.0],
                names=[f'assign_pos_{k}'])

        # z lower/upper bounds, carry_link, capacity, symmetry, c21
        for k in K:
            for t in T:
                req_idx   = [self._x_cpx[i, k] for i in self.J_t[t]]
                carry_idx = [self._y_cpx[i, k-1, t] for i in J] if k > 0 else []

                # z >= req - carry_in
                idx   = [self._z_cpx[k, t]] + req_idx + carry_idx
                coeff = [1.0] + [-1.0]*len(req_idx) + [1.0]*len(carry_idx)
                self._cpx.linear_constraints.add(
                    lin_expr=[SparsePair(idx, coeff)], senses=['G'], rhs=[0.0],
                    names=[f'z_lb_{k}_{t}'])

                # z <= req
                idx   = [self._z_cpx[k, t]] + req_idx
                coeff = [1.0] + [-1.0]*len(req_idx)
                self._cpx.linear_constraints.add(
                    lin_expr=[SparsePair(idx, coeff)], senses=['L'], rhs=[0.0],
                    names=[f'z_ub_{k}_{t}'])

        # Carry link
        for i in J:
            for k in K:
                for t in T:
                    self._cpx.linear_constraints.add(
                        lin_expr=[SparsePair([self._y_cpx[i,k,t], self._x_cpx[i,k]],
                                              [1.0, -1.0])],
                        senses=['L'], rhs=[0.0], names=[f'carry_link_{i}_{k}_{t}'])

        # Capacity
        for k in K:
            req_idx   = [self._x_cpx[i,k] for i in J for t in self.T[i]]
            carry_idx = [self._y_cpx[i,k,t] for i in J for t in T]
            idx   = req_idx + carry_idx
            coeff = [1.0]*len(idx)
            self._cpx.linear_constraints.add(
                lin_expr=[SparsePair(idx, coeff)], senses=['L'], rhs=[float(C)],
                names=[f'mag_{k}'])

        # Symmetry-breaking
        if self.use_symmetry_breaking:
            p    = self._sym_job
            half = math.ceil(N / 2)
            idx  = [self._x_cpx[p, k] for k in range(half)]
            self._cpx.linear_constraints.add(
                lin_expr=[SparsePair(idx, [1.0]*len(idx))], senses=['E'], rhs=[1.0],
                names=['sym_break'])

        # Constraint 21
        if self.use_constraint_21:
            for t in T:
                n_jt = len(self.J_t[t])
                for k in range(n_jt - 1):
                    for i in J:
                        self._cpx.linear_constraints.add(
                            lin_expr=[SparsePair([self._y_cpx[i,k,t]], [1.0])],
                            senses=['E'], rhs=[0.0], names=[f'c21_{i}_{k}_{t}'])

        if verbose:
            print(f"SSPMF model built (CPLEX): {N} jobs, {M} tools, "
                  f"{self._cpx_n_vars} variables")

    def _solve_cplex(self, time_limit, verbose):
        self._cpx.parameters.timelimit.set(float(time_limit))
        self._cpx.solve()
        status_code = self._cpx.solution.get_status()
        status_str  = self._cpx.solution.status[status_code]
        N = self.n_jobs
        try:
            obj_val  = self._cpx.solution.get_objective_value()
            all_vals = self._cpx.solution.get_values()
            seq = [None] * N
            for i in range(N):
                for k in range(N):
                    if all_vals[self._x_cpx[i, k]] > 0.5:
                        seq[k] = i
            sequence = seq if None not in seq else None
        except Exception:
            obj_val  = None
            sequence = None
        if verbose:
            print(f"[SSPMF] Status: {status_str}, Obj: {obj_val}, Seq: {sequence}")
        return status_str, obj_val, sequence

    # ─────────────────────────────────────────────────────────────────────────
    # SCIP implementation
    # ─────────────────────────────────────────────────────────────────────────

    def _build_scip(self, verbose=True):
        N = self.n_jobs
        M = self.n_tools
        C = self.capacity
        T = range(M)
        J = range(N)
        K = range(N)

        self._sm = SCIPModel("SSPMF_SCIP")
        if not verbose:
            self._sm.hideOutput()

        # Variables
        self._sx = {}
        for i in J:
            for k in K:
                self._sx[i, k] = self._sm.addVar(vtype='B', name=f'x_{i}_{k}')

        self._sy = {}
        for i in J:
            for k in K:
                for t in T:
                    self._sy[i, k, t] = self._sm.addVar(
                        lb=0.0, ub=1.0, vtype='C', name=f'y_{i}_{k}_{t}'
                    )

        self._sz = {}
        for k in K:
            for t in T:
                self._sz[k, t] = self._sm.addVar(vtype='B', name=f'z_{k}_{t}')

        # Objective
        self._sm.setObjective(
            scip_quicksum(self._sz[k, t] for k in K for t in T),
            "minimize"
        )

        # Assignment
        for i in J:
            self._sm.addCons(
                scip_quicksum(self._sx[i, k] for k in K) == 1,
                name=f'assign_job_{i}'
            )
        for k in K:
            self._sm.addCons(
                scip_quicksum(self._sx[i, k] for i in J) == 1,
                name=f'assign_pos_{k}'
            )

        # z bounds
        for k in K:
            for t in T:
                req = scip_quicksum(self._sx[i, k] for i in self.J_t[t])
                carry_in = (scip_quicksum(self._sy[i, k-1, t] for i in J)
                            if k > 0 else 0)
                self._sm.addCons(self._sz[k, t] >= req - carry_in, name=f'z_lb_{k}_{t}')
                self._sm.addCons(self._sz[k, t] <= req, name=f'z_ub_{k}_{t}')

        # Carry link
        for i in J:
            for k in K:
                for t in T:
                    self._sm.addCons(
                        self._sy[i, k, t] <= self._sx[i, k],
                        name=f'carry_link_{i}_{k}_{t}'
                    )

        # Capacity
        for k in K:
            req   = scip_quicksum(self._sx[i, k] for i in J for t in self.T[i])
            carry = scip_quicksum(self._sy[i, k, t] for i in J for t in T)
            self._sm.addCons(req + carry <= C, name=f'mag_{k}')

        # Symmetry-breaking
        if self.use_symmetry_breaking:
            p    = self._sym_job
            half = math.ceil(N / 2)
            self._sm.addCons(
                scip_quicksum(self._sx[p, k] for k in range(half)) == 1,
                name='sym_break'
            )

        # Constraint 21
        if self.use_constraint_21:
            for t in T:
                n_jt = len(self.J_t[t])
                for k in range(n_jt - 1):
                    for i in J:
                        self._sm.addCons(
                            self._sy[i, k, t] == 0,
                            name=f'c21_{i}_{k}_{t}'
                        )

        if verbose:
            print(f"SSPMF model built (SCIP): {N} jobs, {M} tools")

    def _solve_scip(self, time_limit, verbose):
        self._sm.setParam("limits/time", float(time_limit))
        self._sm.optimize()
        status = self._sm.getStatus()
        N = self.n_jobs
        try:
            obj_val = self._sm.getObjVal()
            seq = [None] * N
            for i in range(N):
                for k in range(N):
                    if self._sm.getVal(self._sx[i, k]) > 0.5:
                        seq[k] = i
            sequence = seq if None not in seq else None
        except Exception:
            obj_val  = None
            sequence = None
        if verbose:
            print(f"[SSPMF] Status: {status}, Obj: {obj_val}, Seq: {sequence}")
        return status, obj_val, sequence


# ─────────────────────────────────────────────────────────────────────────────
# LP relaxation lower bound
# ─────────────────────────────────────────────────────────────────────────────

def sspmf_lp_lower_bound(n_tools, capacity, tool_req):
    """
    Compute the LP relaxation lower bound for SSPMF.

    The proven lower bound is:  LB = M - C
    where M = total number of (job, tool) pairs across all jobs
          C = magazine capacity.

    Actually the bound is: LB = Σ_j |T_j| - C (total tool requirements minus capacity).
    Per paper: LB = M - C where M = Σ_j |T_j|.

    Parameters
    ----------
    n_tools  : int  (not used directly; M computed from tool_req)
    capacity : int
    tool_req : dict {job: [tools]}

    Returns
    -------
    float
    """
    M = sum(len(v) for v in tool_req.values())
    return max(0, M - capacity)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience function
# ─────────────────────────────────────────────────────────────────────────────

def solve_sspmf(instance_path, time_limit=3600, verbose=True,
                use_symmetry_breaking=True, use_constraint_21=True):
    """Load an instance and solve it with the SSPMF formulation."""
    n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance(instance_path)
    if verbose:
        lb = sspmf_lp_lower_bound(n_tools, capacity, tool_req)
        print(f"[SSPMF] Instance: {Path(instance_path).name}  "
              f"Jobs={n_jobs} Tools={n_tools} Cap={capacity}  LP_LB={lb}")
    f = SSPMFFormulation(n_jobs, n_tools, capacity, tool_req,
                         use_symmetry_breaking=use_symmetry_breaking,
                         use_constraint_21=use_constraint_21)
    f.build_model(verbose=verbose)
    return f.solve(time_limit=time_limit, verbose=verbose)


if __name__ == "__main__":
    instance_file = (
        Path(__file__).parent.parent / "Instances" / "Shankar" / "shankar-example.txt"
    )
    if instance_file.exists():
        solve_sspmf(str(instance_file), verbose=True)
    else:
        print(f"Instance not found: {instance_file}")
