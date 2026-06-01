"""
Laporte-Salazar-González-Semet (LSS) Formulation for the Job Sequencing
and Tool Switching Problem (SSP).

Reference
---------
Laporte, G., Salazar-González, J.J., & Semet, F. (2004).
"Exact algorithms for the job sequencing and tool switching problem."
IIE Transactions, 36(1), 37–45.

Model Description
-----------------
This is a TSP-based Integer Linear Programme.

Variables
---------
x[i,j]  ∈ {0,1}   arc from job i to job j (1-indexed in the paper; 0-indexed here)
              where job 0 is a dummy depot connecting first and last jobs
y[i,t]  ∈ {0,1}   tool t is present in the magazine during job i
z[i,t]  ∈ {0,1}   tool t is loaded for job i (switch indicator)

Objective (Eq. 10 in paper)
---------------------------
    min Σ_{i∈J} Σ_{t∈T_i} z[i,t]

Optionally the objective is *lifted* by adding the contribution from
the successor arc (Eq. 27-ish):

    min Σ_{i∈J} Σ_{t∈T_i} z[i,t]
        + Σ_{i∈J: |T_i|=c} Σ_{j≠i} |T_j \\ T_i| * x[i,j]

Constraints
-----------
(11) Out-degree: Σ_j x[i,j] = 1  for all i ∈ J ∪ {depot}
(12) In-degree:  Σ_j x[j,i] = 1  for all i ∈ J ∪ {depot}
(13) Subtour elimination (lazy, DFS-based SECs)
(14) Capacity:   Σ_t y[i,t] ≤ c  for all i ∈ J
(15) Linking:    y[i,t] ≥ x[j,i] + y[j,t] - 1  for all i,j ∈ J, t ∈ T_i
         (if arc (j→i) is used and t was loaded at j, it stays at i)
(16) Fixing:     y[i,t] = 1  for all i ∈ J, t ∈ T_i  (required tools loaded)
(17) Switch def: z[i,t] ≥ y[i,t] - y[j,t] + 1 - x[j,i]  for ... t ∈ T_i
         (tool t introduced at i, after coming from j, if not already there)

Valid inequalities (from paper, Section 4)
-------------------------------------------
(23) Σ_{t∈T_i} z[i,t] ≥ max(0, |T_i| + |T_j| - c) * x[i,j]  for all i,j arcs
(24) z[i,t] ≥ Σ_{j≠i} x[j,i] - Σ_{j≠i,t∈T_j} x[j,i]  for all i ∈ J, t ∈ T_i
(25) Σ_{t∉T_i} z[i,t] = 0  (tools not required at i are never newly loaded there)

Note on depot
-------------
The paper uses a dummy depot node 0 with T_0 = ∅.  The arc x[last, 0] closes
the tour and x[0, first] opens it.  The magazine at the depot is empty
(y[0,t] = 0 for all t).

Solver support
--------------
Auto-selects backend: CPLEX (raw) → Gurobi → SCIP.  The lazy SECs are
injected via the same callback mechanism as the BBC solver.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import cplex
    from cplex import SparsePair
    from cplex.callbacks import Context
    HAS_CPLEX = True
except ImportError:
    HAS_CPLEX = False

try:
    import gurobipy as gp
    from gurobipy import GRB
    HAS_GUROBI = True
except ImportError:
    HAS_GUROBI = False

try:
    from pyscipopt import Model as SCIPModel, quicksum as scip_quicksum
    HAS_SCIP = True
except ImportError:
    HAS_SCIP = False

from utils import load_ssp_instance


# ─────────────────────────────────────────────────────────────────────────────
# LSS formulation – Gurobi backend
# ─────────────────────────────────────────────────────────────────────────────

class LSSFormulation:
    """
    LSS (Laporte 2004) formulation for SSP.

    Auto-selects solver: Gurobi → CPLEX → SCIP.

    Parameters
    ----------
    n_jobs   : int
    n_tools  : int
    capacity : int   (magazine capacity c)
    tool_req : dict  {job_index: [tool indices]}
    use_lifted_obj : bool
        Use the lifted objective (adds arc-based lower bound terms).
    use_valid_ineq : bool
        Add valid inequalities (23)-(25) from the paper.
    """

    def __init__(self, n_jobs, n_tools, capacity, tool_req,
                 use_lifted_obj=True, use_valid_ineq=True):
        self.n_jobs         = n_jobs
        self.n_tools        = n_tools
        self.capacity       = capacity
        self.tool_req       = tool_req
        self.use_lifted_obj = use_lifted_obj
        self.use_valid_ineq = use_valid_ineq

        # Precompute tool sets for each job (0-indexed)
        self.T = {j: set(tool_req.get(j, [])) for j in range(n_jobs)}

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

    def build_model(self, verbose=True):
        """Build the LSS model using the detected backend."""
        if self._backend == 'gurobi':
            self._build_gurobi(verbose)
        elif self._backend == 'cplex':
            self._build_cplex(verbose)
        elif self._backend == 'scip':
            self._build_scip(verbose)

    def solve(self, time_limit=3600, verbose=True):
        """
        Solve the LSS model.

        Returns
        -------
        status   : str
        obj_val  : float or None
        sequence : list[int] or None
        """
        if self._backend == 'gurobi':
            return self._solve_gurobi(time_limit, verbose)
        elif self._backend == 'cplex':
            return self._solve_cplex(time_limit, verbose)
        elif self._backend == 'scip':
            return self._solve_scip(time_limit, verbose)

    # ── Gurobi implementation ─────────────────────────────────────────────────

    def _build_gurobi(self, verbose=True):
        """Build the LSS ILP with Gurobi."""
        n = self.n_jobs
        c = self.capacity
        T = range(self.n_tools)
        J = range(n)   # 0-indexed jobs; depot = n

        self._m = gp.Model("LSS")
        if not verbose:
            self._m.setParam('OutputFlag', 0)
        self._m.setParam('LazyConstraints', 1)

        # ── Variables ────────────────────────────────────────────────────
        # x[i,j]: arc from i to j  (J ∪ {depot=n})
        nodes = list(J) + [n]  # n = depot index
        self._x = {}
        for i in nodes:
            for j in nodes:
                if i != j:
                    self._x[i, j] = self._m.addVar(
                        vtype=GRB.BINARY, name=f"x_{i}_{j}"
                    )

        # y[i,t]: tool t loaded at job i  (only job nodes, not depot)
        self._y = {}
        for i in J:
            for t in T:
                self._y[i, t] = self._m.addVar(
                    vtype=GRB.BINARY, name=f"y_{i}_{t}"
                )

        # z[i,t]: tool t switched (introduced) at job i
        self._z = {}
        for i in J:
            for t in T:
                self._z[i, t] = self._m.addVar(
                    vtype=GRB.BINARY, name=f"z_{i}_{t}"
                )

        self._m.update()

        # ── Objective ────────────────────────────────────────────────────
        if self.use_lifted_obj:
            # Lifted: add arc-based lower bound for saturated jobs
            obj = gp.quicksum(
                self._z[i, t]
                for i in J for t in self.T[i]
            )
            for i in J:
                if len(self.T[i]) == c:
                    for j in nodes:
                        if j != i and (i, j) in self._x:
                            # tools in T_j but not T_i contribute to switches
                            extra = len(self.T.get(j, set()) - self.T[i]) if j != n else 0
                            if extra > 0:
                                obj += extra * self._x[i, j]
            self._m.setObjective(obj, GRB.MINIMIZE)
        else:
            self._m.setObjective(
                gp.quicksum(self._z[i, t] for i in J for t in self.T[i]),
                GRB.MINIMIZE
            )

        # ── Degree constraints (Eqs. 11, 12) ─────────────────────────────
        for i in nodes:
            out_arcs = [self._x[i, j] for j in nodes if j != i and (i, j) in self._x]
            self._m.addConstr(gp.quicksum(out_arcs) == 1, name=f"out_{i}")

            in_arcs = [self._x[j, i] for j in nodes if j != i and (j, i) in self._x]
            self._m.addConstr(gp.quicksum(in_arcs) == 1, name=f"in_{i}")

        # ── Magazine capacity (Eq. 14) ────────────────────────────────────
        for i in J:
            self._m.addConstr(
                gp.quicksum(self._y[i, t] for t in T) <= c,
                name=f"cap_{i}"
            )

        # ── Required tools always loaded (Eq. 16) ────────────────────────
        for i in J:
            for t in self.T[i]:
                self._m.addConstr(self._y[i, t] == 1, name=f"req_{i}_{t}")

        # Depot: no tools loaded (y implicit = 0 via absence of variable)

        # ── Linking: magazine persistence (Eq. 15) ───────────────────────
        # y[i,t] ≥ x[j,i] + y[j,t] - 1  for j ∈ J, i ∈ T_i arcs
        for i in J:
            for t in self.T[i]:
                for j in nodes:
                    if j != i and (j, i) in self._x:
                        y_j_t = self._y[j, t] if j != n else 0  # depot: y=0
                        self._m.addConstr(
                            self._y[i, t] >= self._x[j, i] + y_j_t - 1,
                            name=f"link_{j}_{i}_{t}"
                        )

        # ── Switch definition (Eq. 17) ────────────────────────────────────
        # z[i,t] ≥ y[i,t] - y[j,t] + 1 - x[j,i]  for t ∈ T_i, j predecessors
        # ⟺ z[i,t] ≥ 1 - y[j,t] + (1 - x[j,i]) is only tight for active arc
        # Simplified: z[i,t] ≥ y[i,t] - y[j,t] * x[j,i]  (non-linear ⟹ use big-M)
        # Linear form (standard linearisation):
        #   z[i,t] ≥ (y[i,t]=1) - y[j,t] + 1 - x[j,i]  (holds when x[j,i]=1)
        for i in J:
            for t in self.T[i]:
                for j in nodes:
                    if j != i and (j, i) in self._x:
                        y_j_t = self._y[j, t] if j != n else 0
                        self._m.addConstr(
                            self._z[i, t] >= 1 - y_j_t - (1 - self._x[j, i]),
                            name=f"swdef_{j}_{i}_{t}"
                        )

        # ── Valid inequalities ────────────────────────────────────────────
        if self.use_valid_ineq:
            # (23): pair-wise lower bound on total switches along an arc
            for i in J:
                for j in nodes:
                    if j != i and (i, j) in self._x:
                        Ti_size = len(self.T[i])
                        Tj_size = len(self.T.get(j, set())) if j != n else 0
                        bound   = max(0, Ti_size + Tj_size - c)
                        if bound > 0:
                            self._m.addConstr(
                                gp.quicksum(self._z[i, t] for t in self.T[i])
                                >= bound * self._x[i, j],
                                name=f"vi23_{i}_{j}"
                            )

            # (25): tools not required at i are never introduced at i
            for i in J:
                for t in T:
                    if t not in self.T[i]:
                        self._m.addConstr(self._z[i, t] == 0, name=f"vi25_{i}_{t}")

        if verbose:
            n_arcs = len(self._x)
            print(f"LSS model built (Gurobi): {n} jobs, {n_arcs} arc vars, "
                  f"{n * self.n_tools} y-vars, {n * self.n_tools} z-vars")

    def _find_subtours_from_sol_lss(self, x_vals, nodes, n_depot):
        """Detect subtours in the LSS solution (includes depot node)."""
        succ = {}
        for (i, j), v in x_vals.items():
            if v > 0.5:
                succ[i] = j

        visited  = set()
        subtours = []
        for start in nodes:
            if start in visited or start not in succ:
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
            # A valid Hamiltonian tour includes the depot, so len = n+1 is full
            if cycle is not None and len(cycle) < len(nodes):
                subtours.append(cycle)
        return subtours

    def _solve_gurobi(self, time_limit, verbose):
        self._m.setParam('TimeLimit', float(time_limit))

        n     = self.n_jobs
        depot = n
        nodes = list(range(n)) + [depot]

        def callback(model, where):
            if where == GRB.Callback.MIPSOL:
                x_vals = {(i, j): model.cbGetSolution(self._x[i, j])
                          for (i, j) in self._x}
                subtours = self._find_subtours_from_sol_lss(x_vals, nodes, depot)
                for st in subtours:
                    expr = gp.quicksum(
                        self._x[i, j]
                        for i in st for j in st
                        if i != j and (i, j) in self._x
                    )
                    model.cbLazy(expr <= len(st) - 1)

        self._m.optimize(callback)

        status_map = {
            GRB.OPTIMAL:    'OPTIMAL',
            GRB.TIME_LIMIT: 'TIME_LIMIT',
            GRB.INFEASIBLE: 'INFEASIBLE',
        }
        status = status_map.get(self._m.status, str(self._m.status))

        try:
            obj_val  = self._m.objVal
            x_vals   = {(i, j): self._x[i, j].X for (i, j) in self._x}
            sequence = self._extract_sequence_lss(x_vals, depot)
        except Exception:
            obj_val  = None
            sequence = None

        if verbose:
            print(f"[LSS] Status: {status}, Obj: {obj_val}, Seq: {sequence}")

        return status, obj_val, sequence

    def _extract_sequence_lss(self, x_vals, depot):
        """Follow arcs from depot to reconstruct job sequence."""
        succ = {}
        for (i, j), v in x_vals.items():
            if v > 0.5:
                succ[i] = j

        current = succ.get(depot)
        if current is None:
            return None

        seq = []
        visited = {depot}
        while current != depot:
            if current in visited:
                break
            seq.append(current)
            visited.add(current)
            current = succ.get(current, depot)
        return seq if len(seq) == self.n_jobs else None

    # ── CPLEX implementation ───────────────────────────────────────────────────

    def _build_cplex(self, verbose=True):
        """Build the LSS ILP with raw CPLEX."""
        n = self.n_jobs
        c = self.capacity
        T = range(self.n_tools)
        J = range(n)
        depot = n
        nodes = list(J) + [depot]

        self._cpx = cplex.Cplex()
        if not verbose:
            self._cpx.set_log_stream(None)
            self._cpx.set_results_stream(None)
            self._cpx.set_warning_stream(None)

        self._cpx.objective.set_sense(self._cpx.objective.sense.minimize)

        # Index maps
        self._x_cpx = {}  # (i,j) → col idx
        self._y_cpx = {}  # (i,t) → col idx
        self._z_cpx = {}  # (i,t) → col idx

        # ── Add variables ─────────────────────────────────────────────────
        col = 0
        # x vars
        for i in nodes:
            for j in nodes:
                if i != j:
                    self._cpx.variables.add(
                        obj=[0.0], lb=[0.0], ub=[1.0], types=['B'],
                        names=[f'x_{i}_{j}']
                    )
                    self._x_cpx[i, j] = col
                    col += 1

        # z vars (objective coefficients)
        for i in J:
            for t in T:
                obj_v = 1.0 if t in self.T[i] else 0.0
                self._cpx.variables.add(
                    obj=[obj_v], lb=[0.0], ub=[1.0], types=['B'],
                    names=[f'z_{i}_{t}']
                )
                self._z_cpx[i, t] = col
                col += 1

        # y vars (no objective)
        for i in J:
            for t in T:
                self._cpx.variables.add(
                    obj=[0.0], lb=[0.0], ub=[1.0], types=['B'],
                    names=[f'y_{i}_{t}']
                )
                self._y_cpx[i, t] = col
                col += 1

        self._cpx_n_vars = col

        # ── Add constraints (lifted obj handled via valid ineqs) ──────────
        # Degree
        for i in nodes:
            out_idx = [self._x_cpx[i, j] for j in nodes if j != i and (i, j) in self._x_cpx]
            self._cpx.linear_constraints.add(
                lin_expr=[SparsePair(out_idx, [1.0]*len(out_idx))],
                senses=['E'], rhs=[1.0], names=[f'out_{i}']
            )
            in_idx = [self._x_cpx[j, i] for j in nodes if j != i and (j, i) in self._x_cpx]
            self._cpx.linear_constraints.add(
                lin_expr=[SparsePair(in_idx, [1.0]*len(in_idx))],
                senses=['E'], rhs=[1.0], names=[f'in_{i}']
            )

        # Capacity
        for i in J:
            idx = [self._y_cpx[i, t] for t in T]
            self._cpx.linear_constraints.add(
                lin_expr=[SparsePair(idx, [1.0]*len(idx))],
                senses=['L'], rhs=[float(c)], names=[f'cap_{i}']
            )

        # Required tools
        for i in J:
            for t in self.T[i]:
                idx = [self._y_cpx[i, t]]
                self._cpx.linear_constraints.add(
                    lin_expr=[SparsePair(idx, [1.0])],
                    senses=['E'], rhs=[1.0], names=[f'req_{i}_{t}']
                )

        # Linking
        for i in J:
            for t in self.T[i]:
                for j in nodes:
                    if j != i and (j, i) in self._x_cpx:
                        idx   = [self._y_cpx[i, t], self._x_cpx[j, i]]
                        coeff = [1.0, -1.0]
                        if j != depot:
                            idx.append(self._y_cpx[j, t])
                            coeff.append(-1.0)
                        self._cpx.linear_constraints.add(
                            lin_expr=[SparsePair(idx, coeff)],
                            senses=['G'], rhs=[-1.0], names=[f'link_{j}_{i}_{t}']
                        )

        # Switch def
        for i in J:
            for t in self.T[i]:
                for j in nodes:
                    if j != i and (j, i) in self._x_cpx:
                        # z[i,t] >= 1 - y[j,t] - (1 - x[j,i])
                        # => z[i,t] + y[j,t] - x[j,i] >= 0  (if j != depot)
                        idx   = [self._z_cpx[i, t], self._x_cpx[j, i]]
                        coeff = [1.0, -1.0]
                        rhs   = 0.0
                        if j != depot:
                            idx.append(self._y_cpx[j, t])
                            coeff.append(1.0)
                        else:
                            rhs = 0.0  # y[depot,t]=0
                        self._cpx.linear_constraints.add(
                            lin_expr=[SparsePair(idx, coeff)],
                            senses=['G'], rhs=[rhs], names=[f'swdef_{j}_{i}_{t}']
                        )

        # Valid ineqs (23), (25)
        if self.use_valid_ineq:
            for i in J:
                for j in nodes:
                    if j != i and (i, j) in self._x_cpx:
                        Ti = len(self.T[i])
                        Tj = len(self.T.get(j, set())) if j != depot else 0
                        bound = max(0, Ti + Tj - c)
                        if bound > 0:
                            idx   = [self._z_cpx[i, t] for t in self.T[i]]
                            idx  += [self._x_cpx[i, j]]
                            coeff = [1.0]*len(self.T[i]) + [-float(bound)]
                            self._cpx.linear_constraints.add(
                                lin_expr=[SparsePair(idx, coeff)],
                                senses=['G'], rhs=[0.0], names=[f'vi23_{i}_{j}']
                            )
            for i in J:
                for t in T:
                    if t not in self.T[i]:
                        idx = [self._z_cpx[i, t]]
                        self._cpx.linear_constraints.add(
                            lin_expr=[SparsePair(idx, [1.0])],
                            senses=['E'], rhs=[0.0], names=[f'vi25_{i}_{t}']
                        )

        if verbose:
            print(f"LSS model built (CPLEX): {n} jobs, {self._cpx_n_vars} variables")

    def _solve_cplex(self, time_limit, verbose):
        self._cpx.parameters.timelimit.set(float(time_limit))
        n     = self.n_jobs
        depot = n
        nodes = list(range(n)) + [depot]

        class LSSCallback:
            def __init__(self_, solver):
                self_.solver = solver

            def invoke(self_, context):
                if not context.in_candidate():
                    return
                if not context.is_candidate_point():
                    return
                all_vals = context.get_candidate_point(list(range(self_.solver._cpx_n_vars)))
                x_vals   = {(i, j): all_vals[self_.solver._x_cpx[i, j]]
                            for (i, j) in self_.solver._x_cpx}
                subtours  = self_.solver._find_subtours_from_sol_lss(x_vals, nodes, depot)
                if subtours:
                    constraints = []
                    senses      = []
                    rhs_vals    = []
                    for st in subtours:
                        idx = [self_.solver._x_cpx[i, j]
                               for i in st for j in st
                               if i != j and (i, j) in self_.solver._x_cpx]
                        if idx:
                            constraints.append(SparsePair(idx, [1.0]*len(idx)))
                            senses.append('L')
                            rhs_vals.append(float(len(st) - 1))
                    if constraints:
                        context.reject_candidate(constraints=constraints,
                                                  senses=senses, rhs=rhs_vals)

        cb = LSSCallback(self)
        self._cpx.set_callback(cb, Context.id.candidate)
        self._cpx.solve()

        status_code = self._cpx.solution.get_status()
        status_str  = self._cpx.solution.status[status_code]
        try:
            obj_val  = self._cpx.solution.get_objective_value()
            all_vals = self._cpx.solution.get_values()
            x_vals   = {(i, j): all_vals[self._x_cpx[i, j]] for (i, j) in self._x_cpx}
            sequence = self._extract_sequence_lss(x_vals, depot)
        except Exception:
            obj_val  = None
            sequence = None

        if verbose:
            print(f"[LSS] Status: {status_str}, Obj: {obj_val}, Seq: {sequence}")
        return status_str, obj_val, sequence

    # ── SCIP implementation ───────────────────────────────────────────────────

    def _build_scip(self, verbose=True):
        """Build the LSS ILP with PySCIPOPT."""
        from pyscipopt import Conshdlr, SCIP_RESULT

        n     = self.n_jobs
        c     = self.capacity
        T     = range(self.n_tools)
        J     = range(n)
        depot = n
        nodes = list(J) + [depot]

        self._sm = SCIPModel("LSS_SCIP")
        if not verbose:
            self._sm.hideOutput()

        # Variables
        self._sx = {}
        for i in nodes:
            for j in nodes:
                if i != j:
                    self._sx[i, j] = self._sm.addVar(vtype='B', name=f'x_{i}_{j}')

        self._sy = {}
        self._sz = {}
        for i in J:
            for t in T:
                self._sy[i, t] = self._sm.addVar(vtype='B', name=f'y_{i}_{t}')
                self._sz[i, t] = self._sm.addVar(
                    vtype='B', obj=1.0 if t in self.T[i] else 0.0,
                    name=f'z_{i}_{t}'
                )

        # Objective: minimize
        self._sm.setObjective(
            scip_quicksum(self._sz[i, t] for i in J for t in self.T[i]),
            "minimize"
        )

        # Degree constraints
        for i in nodes:
            self._sm.addCons(
                scip_quicksum(self._sx[i, j] for j in nodes if j != i) == 1,
                name=f'out_{i}'
            )
            self._sm.addCons(
                scip_quicksum(self._sx[j, i] for j in nodes if j != i) == 1,
                name=f'in_{i}'
            )

        # Capacity
        for i in J:
            self._sm.addCons(
                scip_quicksum(self._sy[i, t] for t in T) <= c,
                name=f'cap_{i}'
            )

        # Required
        for i in J:
            for t in self.T[i]:
                self._sm.addCons(self._sy[i, t] == 1, name=f'req_{i}_{t}')

        # Linking
        for i in J:
            for t in self.T[i]:
                for j in nodes:
                    if j != i:
                        y_j_t = self._sy[j, t] if j != depot else 0
                        self._sm.addCons(
                            self._sy[i, t] >= self._sx[j, i] + y_j_t - 1,
                            name=f'link_{j}_{i}_{t}'
                        )

        # Switch def
        for i in J:
            for t in self.T[i]:
                for j in nodes:
                    if j != i:
                        y_j_t = self._sy[j, t] if j != depot else 0
                        self._sm.addCons(
                            self._sz[i, t] >= 1 - y_j_t - (1 - self._sx[j, i]),
                            name=f'swdef_{j}_{i}_{t}'
                        )

        # Valid ineqs
        if self.use_valid_ineq:
            for i in J:
                for j in nodes:
                    if j != i:
                        Ti = len(self.T[i])
                        Tj = len(self.T.get(j, set())) if j != depot else 0
                        bound = max(0, Ti + Tj - c)
                        if bound > 0:
                            self._sm.addCons(
                                scip_quicksum(self._sz[i, t] for t in self.T[i])
                                >= bound * self._sx[i, j],
                                name=f'vi23_{i}_{j}'
                            )
            for i in J:
                for t in T:
                    if t not in self.T[i]:
                        self._sm.addCons(self._sz[i, t] == 0, name=f'vi25_{i}_{t}')

        # SEC constraint handler
        class LSSConshdlr(Conshdlr):
            def __init__(s, solver, nodes, depot):
                super().__init__()
                s.solver = solver
                s.nodes  = nodes
                s.depot  = depot

            def conscheck(s, constraints, solution, checkintegrality,
                          checklprows, printreason, completely):
                x_vals = {(i, j): s.model.getSolVal(solution, s.solver._sx[i, j])
                          for (i, j) in s.solver._sx}
                subtours = s.solver._find_subtours_from_sol_lss(x_vals, s.nodes, s.depot)
                return {"result": SCIP_RESULT.INFEASIBLE if subtours else SCIP_RESULT.FEASIBLE}

            def consenfolp(s, constraints, nusefulconss, solinfeasible):
                x_vals = {(i, j): s.model.getVal(s.solver._sx[i, j])
                          for (i, j) in s.solver._sx}
                subtours = s.solver._find_subtours_from_sol_lss(x_vals, s.nodes, s.depot)
                if not subtours:
                    return {"result": SCIP_RESULT.FEASIBLE}
                for st in subtours:
                    lhs = scip_quicksum(
                        s.solver._sx[i, j]
                        for i in st for j in st
                        if i != j and (i, j) in s.solver._sx
                    )
                    s.model.addCons(lhs <= len(st) - 1, local=False)
                return {"result": SCIP_RESULT.CONSADDED}

            def consenfops(s, constraints, nusefulconss, solinfeasible, objinfeasible):
                return {"result": SCIP_RESULT.FEASIBLE}

            def conslock(s, constraint, locktype, nlockspos, nlocksneg):
                pass

        hdlr = LSSConshdlr(self, nodes, depot)
        self._sm.includeConshdlr(hdlr, name="LSSConshdlr",
                                  desc="LSS subtour elimination",
                                  sepapriority=0, enfopriority=-1, chckpriority=-1,
                                  sepafreq=-1, propfreq=-1, eagerfreq=100,
                                  maxprerounds=0, delaysepa=False, delayprop=False,
                                  needscons=False)
        if verbose:
            print(f"LSS model built (SCIP): {n} jobs")

    def _solve_scip(self, time_limit, verbose):
        self._sm.setParam("limits/time", float(time_limit))
        self._sm.optimize()
        status = self._sm.getStatus()
        depot  = self.n_jobs
        try:
            obj_val  = self._sm.getObjVal()
            x_vals   = {(i, j): self._sm.getVal(v) for (i, j), v in self._sx.items()}
            sequence = self._extract_sequence_lss(x_vals, depot)
        except Exception:
            obj_val  = None
            sequence = None
        if verbose:
            print(f"[LSS] Status: {status}, Obj: {obj_val}, Seq: {sequence}")
        return status, obj_val, sequence


# ─────────────────────────────────────────────────────────────────────────────
# Convenience function
# ─────────────────────────────────────────────────────────────────────────────

def solve_lss(instance_path, time_limit=3600, verbose=True,
              use_lifted_obj=True, use_valid_ineq=True):
    """Load an instance and solve it with the LSS formulation."""
    n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance(instance_path)
    if verbose:
        print(f"[LSS] Instance: {Path(instance_path).name}  "
              f"Jobs={n_jobs} Tools={n_tools} Cap={capacity}")
    f = LSSFormulation(n_jobs, n_tools, capacity, tool_req,
                       use_lifted_obj=use_lifted_obj,
                       use_valid_ineq=use_valid_ineq)
    f.build_model(verbose=verbose)
    return f.solve(time_limit=time_limit, verbose=verbose)


if __name__ == "__main__":
    instance_file = (
        Path(__file__).parent.parent / "Instances" / "Shankar" / "shankar-example.txt"
    )
    if instance_file.exists():
        solve_lss(str(instance_file), verbose=True)
    else:
        print(f"Instance not found: {instance_file}")
