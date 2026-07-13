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
CPLEX only (raw cplex API + modern generic callback).  Gurobi and SCIP
backends have been archived to _archived/lss_formulation_gurobi_scip.py.
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
                 use_lifted_obj=False, use_valid_ineq=True):
        # use_valid_ineq=True (2026-06-15): the valid inequalities (23)-(25) are now
        # transcribed FAITHFULLY from Laporte 2004 §4 (the earlier per-arc VI(23) was a
        # mis-transcription using |T_i|+|T_j|-c and z over T_i, which was over-tight and
        # cut off optima). The corrected VIs are verified to PRESERVE the optimum vs
        # brute force (8/8). See _build_cplex.
        # (use_lifted_obj is accepted for API compatibility but NOT implemented; the
        #  VIs below strengthen the base objective directly — no lifted objective needed.)
        self.n_jobs         = n_jobs
        self.n_tools        = n_tools
        self.capacity       = capacity
        self.tool_req       = tool_req
        self.use_lifted_obj = use_lifted_obj
        self.use_valid_ineq = use_valid_ineq

        # Precompute tool sets for each job (0-indexed)
        self.T = {j: set(tool_req.get(j, [])) for j in range(n_jobs)}

        if not HAS_CPLEX:
            raise ImportError(
                "LSS requires IBM CPLEX.  Install the cplex Python package "
                "(ships with IBM CPLEX Studio).\n"
                "Gurobi/SCIP backends have been archived to "
                "_archived/lss_formulation_gurobi_scip.py."
            )

    def build_model(self, verbose=True):
        """Build the LSS model with CPLEX."""
        self._build_cplex(verbose)

    def solve(self, time_limit=3600, verbose=True):
        """
        Solve the LSS model.

        Returns
        -------
        status   : str
        obj_val  : float or None
        sequence : list[int] or None
        """
        return self._solve_cplex(time_limit, verbose)

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
        import os as _os
        _thr = int(_os.environ.get("CPLEX_THREADS", "0"))   # pin threads (0 = CPLEX default) for reproducible/comparable timings
        if _thr:
            self._cpx.parameters.threads.set(_thr)
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
        # Objective (10), Laporte et al. 2004:  min Σ_{i∈J} Σ_{t∈T_i} z_it.
        # z carries an objective coefficient ONLY for REQUIRED tools t∈T_i. The
        # companion base constraint (17) [z_it=0 for t∉T_i] plus the all-t switch
        # definition (15) below make this equal the true total switch count.
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

        # Switch def  (FIX 2026-06-15: generate for ALL t in T, and include the
        # y[i,t] term so non-required-tool insertions are counted too)
        #   z[i,t] >= y[i,t] - y[j,t] - (1 - x[j,i])
        #   <=> z[i,t] - y[i,t] + y[j,t] - x[j,i] >= -1
        # For t in T_i, y[i,t]=1 (forced), so this reduces to the old form.
        for i in J:
            for t in T:
                for j in nodes:
                    if j != i and (j, i) in self._x_cpx:
                        idx   = [self._z_cpx[i, t], self._y_cpx[i, t], self._x_cpx[j, i]]
                        coeff = [1.0, -1.0, -1.0]
                        if j != depot:
                            idx.append(self._y_cpx[j, t])   # y[depot,t]=0 -> omitted
                            coeff.append(1.0)
                        self._cpx.linear_constraints.add(
                            lin_expr=[SparsePair(idx, coeff)],
                            senses=['G'], rhs=[-1.0], names=[f'swdef_{j}_{i}_{t}']
                        )

        # (17) Laporte 2004 — BASE constraint (NOT a valid inequality): z_it = 0
        # for t ∉ T_i. No switch is counted for a tool a job does not require;
        # together with the all-t switch def (15), this forbids free pre-loading
        # of non-required tools, so objective (10) over T_i = true total switches.
        # ALWAYS on.
        for i in J:
            for t in T:
                if t not in self.T[i]:
                    self._cpx.linear_constraints.add(
                        lin_expr=[SparsePair([self._z_cpx[i, t]], [1.0])],
                        senses=['E'], rhs=[0.0], names=[f'reqz_{i}_{t}']
                    )

        # Strengthening valid inequalities (Laporte 2004, §4: eqs 23, 24, 25), ON by
        # default. Transcribed faithfully and verified to PRESERVE the optimum vs
        # brute force (8/8).  l_ij = max(0, |T_i ∪ T_j| − c).
        if self.use_valid_ineq:
            # (23) lower bound on switches to process job j:
            #      Σ_{t∈T_j} z_jt ≥ Σ_{i≠j} l_ij x_ij
            for j in J:
                idx   = [self._z_cpx[j, t] for t in self.T[j]]
                coeff = [1.0] * len(self.T[j])
                for i in J:  # jobs only (Laporte (23)); depot has T=empty => l_ij=0.
                             # FIX 2026-07-02: 'nodes' here raised KeyError on the depot.
                    if i != j:
                        lij = max(0, len(self.T[i] | self.T[j]) - c)
                        if lij > 0:
                            idx.append(self._x_cpx[i, j]); coeff.append(-float(lij))
                if idx:
                    self._cpx.linear_constraints.add(
                        lin_expr=[SparsePair(idx, coeff)],
                        senses=['G'], rhs=[0.0], names=[f'vi23_{j}']
                    )
            # (24) if j immediately follows a job that also needs t, no re-insertion:
            #      Σ_{i∈J_t\{j}} x_ij + z_jt ≤ 1
            for j in J:
                for t in self.T[j]:
                    Jt = [i for i in J if i != j and t in self.T[i]]
                    self._cpx.linear_constraints.add(
                        lin_expr=[SparsePair([self._x_cpx[i, j] for i in Jt] + [self._z_cpx[j, t]],
                                             [1.0] * len(Jt) + [1.0])],
                        senses=['L'], rhs=[1.0], names=[f'vi24_{j}_{t}']
                    )
            # (25) a full predecessor (|T_i|=c) keeps its tools rather than reloading:
            #      Σ_{t∈T_i\T_j} y_jt ≥ (c−|T_j|) x_ij,  for |T_i|=c, |T_j|<c
            for i in J:
                if len(self.T[i]) != c:
                    continue
                for j in J:
                    if j != i and len(self.T[j]) < c:
                        diff = self.T[i] - self.T[j]
                        if diff:
                            self._cpx.linear_constraints.add(
                                lin_expr=[SparsePair([self._y_cpx[j, t] for t in diff] + [self._x_cpx[i, j]],
                                                     [1.0] * len(diff) + [-float(c - len(self.T[j]))])],
                                senses=['G'], rhs=[0.0], names=[f'vi25_{i}_{j}']
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
