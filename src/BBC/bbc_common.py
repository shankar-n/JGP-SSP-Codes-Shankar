"""
BBC Shared Utilities — BBCSolverMixin
======================================

All methods that are logically identical across the three BBC backends
(Gurobi, CPLEX, SCIP) live here.  Each backend class inherits from
``BBCSolverMixin`` instead of repeating the code.

Methods provided
----------------
_compute_pairwise_bounds   – sets self.w[i,j] = max(0, |T_i ∪ T_j| − c)
_find_subtours_from_sol    – detect subtour cycles from a binary x-dict
_get_sequence_from_sol     – extract Hamiltonian sequence from x-dict
_build_x_bar_from_sequence – build {(i,j):1.0} dict from a job sequence
_solve_dsp_gurobi          – solve the Benders DSP with Gurobi (fresh model)
_solve_dsp_docplex         – solve the Benders DSP with docplex / CPLEX

Requirements on the inheriting class
-------------------------------------
self.n_jobs, self.n_tools, self.capacity, self.tool_req  (set before calling)

All DSP solver methods use lazy imports so that the mixin itself does not
depend on any particular solver being installed.
"""

from typing import Dict, List, Optional, Tuple, Any


class BBCSolverMixin:
    """
    Mixin providing shared helpers for all BBC backend solver classes.

    The class does not define ``__init__``; it expects the following
    instance attributes to already exist when any method is called::

        self.n_jobs    : int
        self.n_tools   : int
        self.capacity  : int
        self.tool_req  : dict {job_idx: [tool_indices]}
    """

    # ── Pairwise lower-bound weights ──────────────────────────────────────────

    def _compute_pairwise_bounds(self) -> None:
        """
        Pre-compute w[i,j] = max(0, |T_i ∪ T_j| − c) for all arc (i,j).

        This is the minimum number of tools that must be switched when
        moving directly from job i to job j, used as the initial lower
        bound on θ in the master problem.
        """
        self.w = {}
        for i in range(self.n_jobs):
            Ti = set(self.tool_req.get(i, []))
            for j in range(self.n_jobs):
                if i == j:
                    self.w[i, j] = 0
                else:
                    Tj = set(self.tool_req.get(j, []))
                    self.w[i, j] = max(0, len(Ti | Tj) - self.capacity)

    # ── Solution parsing helpers ──────────────────────────────────────────────

    def _find_subtours_from_sol(self, sol: Dict) -> List[List[int]]:
        """
        Detect all subtours in a binary x-solution dict.

        Parameters
        ----------
        sol : dict {(i,j): float}   – x variable values (threshold 0.5)

        Returns
        -------
        list of lists   – each inner list is a cycle shorter than n_jobs.
                          Returns [] for a Hamiltonian cycle.
        """
        n    = self.n_jobs
        succ = {i: j
                for i in range(n) for j in range(n)
                if i != j and sol.get((i, j), 0.0) > 0.5}

        visited  = set()
        subtours = []

        for start in range(n):
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

            if cycle is not None and len(cycle) < n:
                subtours.append(cycle)

        return subtours

    def _get_sequence_from_sol(self, sol: Dict) -> Optional[List[int]]:
        """
        Extract a Hamiltonian sequence from a subtour-free binary x-solution.

        Starts from job 0 and follows successor arcs.

        Returns
        -------
        list[int] of length n_jobs, or None on failure.
        """
        n    = self.n_jobs
        succ = {i: j
                for i in range(n) for j in range(n)
                if i != j and sol.get((i, j), 0.0) > 0.5}

        if not succ:
            return None

        sequence = [0]
        current  = succ.get(0)
        while current is not None and current != 0 and len(sequence) < n:
            sequence.append(current)
            current = succ.get(current)

        return sequence if len(sequence) == n else None

    def _build_x_bar_from_sequence(self, sequence: List[int]) -> Dict:
        """
        Convert a Hamiltonian sequence to a binary arc dict {(i,j): 1.0}.

        Uses the actual depot arcs (depot→sequence[0] and sequence[-1]→depot)
        instead of closing a job-only cycle.  The depot arc forces the DSP to
        see y_{depot,t} = 0 (empty magazine at start), preventing the circular
        preloading LP artifact that returns DSP = 0 for all sequences.
        """
        n     = len(sequence)
        depot = self.depot          # = n_jobs
        x_bar = {}
        for k in range(n - 1):
            x_bar[sequence[k], sequence[k + 1]] = 1.0
        x_bar[depot, sequence[0]]  = 1.0   # depot → first job
        x_bar[sequence[-1], depot] = 1.0   # last job → depot
        return x_bar

    # ── Shared DSP solvers (fallback implementations) ─────────────────────────

    def _solve_dsp_gurobi(self, x_bar: Dict) -> Tuple:
        """
        Solve the Benders dual subproblem (DSP) using a fresh Gurobi model.

        DSP (maximisation):
            max  Σ_{i,j,t} (x̄_ij − 1) λ_ijt  −  Σ_j c μ_j  +  Σ_{j,t∈T_j} ν_jt
            s.t.  −μ_j − Σ_i λ_ijt + Σ_k λ_jkt + (ν_jt if t∈T_j) ≤ 0
                   Σ_i λ_ijt + (η_jt if t∉T_j) ≤ (1 if t∈T_j else 0)
                  λ ≥ 0, μ ≥ 0, ν free, η free

        Parameters
        ----------
        x_bar : dict {(i,j): float}   – arc values (integer or fractional)

        Returns
        -------
        (obj_val, duals) or (None, {}) on failure
        """
        try:
            import gurobipy as gp
            from gurobipy import GRB
        except ImportError:
            return None, {}

        n        = self.n_jobs
        T        = range(self.n_tools)
        tool_req = self.tool_req

        depot = self.depot  # = n_jobs

        dsp = gp.Model("DSP")
        dsp.setParam('OutputFlag', 0)

        lam = {(i, j, t): dsp.addVar(lb=0.0, name=f"lam_{i}_{j}_{t}")
               for i in range(n) for j in range(n) if i != j for t in T}
        # depot→j arc lam (enforces empty-magazine depot constraint)
        lam_d = {(j, t): dsp.addVar(lb=0.0, name=f"lam_d_{j}_{t}")
                 for j in range(n) for t in T}
        mu  = {j: dsp.addVar(lb=0.0, name=f"mu_{j}") for j in range(n)}
        nu  = {(j, t): dsp.addVar(lb=-GRB.INFINITY, name=f"nu_{j}_{t}")
               for j in range(n) for t in T}
        eta = {(j, t): dsp.addVar(lb=-GRB.INFINITY, name=f"eta_{j}_{t}")
               for j in range(n) for t in T}

        obj = gp.quicksum((x_bar.get((i, j), 0.0) - 1.0) * lam[i, j, t]
                          for i in range(n) for j in range(n) if i != j for t in T)
        obj += gp.quicksum((x_bar.get((depot, j), 0.0) - 1.0) * lam_d[j, t]
                           for j in range(n) for t in T)
        obj += gp.quicksum(-self.capacity * mu[j] for j in range(n))
        obj += gp.quicksum(nu[j, t]
                           for j in range(n) for t in tool_req.get(j, []))
        dsp.setObjective(obj, GRB.MAXIMIZE)

        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                nu_term = nu[j, t] if t in Tj else 0
                dsp.addConstr(
                    -mu[j]
                    - lam_d[j, t]
                    - gp.quicksum(lam[i, j, t] for i in range(n) if i != j)
                    + gp.quicksum(lam[j, k, t] for k in range(n) if k != j)
                    + nu_term <= 0, name=f"dy_{j}_{t}"
                )
                eta_term = eta[j, t] if t not in Tj else 0
                # rhs=1 for ALL t: dual constraint for z_{j,t} has obj coeff=1
                # regardless of t∈T_j. rhs=0 for t∉T_j was a bug.
                dsp.addConstr(
                    lam_d[j, t]
                    + gp.quicksum(lam[i, j, t] for i in range(n) if i != j)
                    + eta_term <= 1.0,
                    name=f"dz_{j}_{t}"
                )

        dsp.optimize()
        if dsp.status != GRB.OPTIMAL:
            return None, {}

        duals = {}
        for (i,j,t), v in lam.items(): duals['lambda', i, j, t] = v.X
        for j, v in mu.items():        duals['mu', j]           = v.X
        for (j,t), v in nu.items():    duals['nu',  j, t]       = v.X
        for (j,t), v in eta.items():   duals['eta', j, t]       = v.X
        return dsp.objVal, duals

    def _solve_dsp_docplex(self, x_bar: Dict) -> Tuple:
        """
        Solve the Benders DSP using docplex (CPLEX under the hood).

        Parameters
        ----------
        x_bar : dict {(i,j): float}

        Returns
        -------
        (obj_val, duals) or (None, {}) on failure
        """
        try:
            from docplex.mp.model import Model as DocplexModel
        except ImportError:
            return None, {}

        n        = self.n_jobs
        T        = range(self.n_tools)
        tool_req = self.tool_req

        depot   = self.depot  # = n_jobs
        dsp     = DocplexModel("DSP", log_output=False)
        neg_inf = dsp.minus_infinity

        lam = {(i, j, t): dsp.continuous_var(lb=0.0, name=f"lam_{i}_{j}_{t}")
               for i in range(n) for j in range(n) if i != j for t in T}
        # depot→j arc lam (enforces empty-magazine depot constraint)
        lam_d = {(j, t): dsp.continuous_var(lb=0.0, name=f"lam_d_{j}_{t}")
                 for j in range(n) for t in T}
        mu  = {j: dsp.continuous_var(lb=0.0, name=f"mu_{j}") for j in range(n)}
        nu  = {(j, t): dsp.continuous_var(lb=neg_inf, name=f"nu_{j}_{t}")
               for j in range(n) for t in T}
        eta = {(j, t): dsp.continuous_var(lb=neg_inf, name=f"eta_{j}_{t}")
               for j in range(n) for t in T}

        obj = dsp.sum((x_bar.get((i, j), 0) - 1) * lam[i, j, t]
                      for i in range(n) for j in range(n) if i != j for t in T)
        obj += dsp.sum((x_bar.get((depot, j), 0) - 1) * lam_d[j, t]
                       for j in range(n) for t in T)
        obj += dsp.sum(-self.capacity * mu[j] for j in range(n))
        obj += dsp.sum(nu[j, t] for j in range(n) for t in tool_req.get(j, []))
        dsp.maximize(obj)

        for j in range(n):
            Tj = set(tool_req.get(j, []))
            for t in T:
                nu_term = nu[j, t] if t in Tj else 0
                dsp.add_constraint(
                    -mu[j]
                    - lam_d[j, t]
                    - dsp.sum(lam[i, j, t] for i in range(n) if i != j)
                    + dsp.sum(lam[j, k, t] for k in range(n) if k != j)
                    + nu_term <= 0, f"dy_{j}_{t}"
                )
                eta_term = eta[j, t] if t not in Tj else 0
                # rhs=1 for ALL t: dual constraint for z_{j,t} has obj coeff=1
                # regardless of t∈T_j. rhs=0 for t∉T_j was a bug.
                dsp.add_constraint(
                    lam_d[j, t]
                    + dsp.sum(lam[i, j, t] for i in range(n) if i != j)
                    + eta_term <= 1.0,
                    f"dz_{j}_{t}"
                )

        sol = dsp.solve(log_output=False)
        if sol is None:
            return None, {}

        duals = {}
        for (i,j,t), v in lam.items(): duals['lambda', i, j, t] = sol.get_value(v)
        for j, v in mu.items():        duals['mu', j]           = sol.get_value(v)
        for (j,t), v in nu.items():    duals['nu',  j, t]       = sol.get_value(v)
        for (j,t), v in eta.items():   duals['eta', j, t]       = sol.get_value(v)
        return dsp.objective_value, duals
