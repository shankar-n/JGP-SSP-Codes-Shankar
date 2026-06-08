"""
ARCHIVED — Gurobi and SCIP backends for the LSS formulation.

These backends have been archived because CPLEX is the primary solver.
The active CPLEX-only implementation is in lss_formulation.py.

Archived: June 2026.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Gurobi backend  (_build_gurobi + _solve_gurobi)
# ─────────────────────────────────────────────────────────────────────────────
#
# To restore: copy these methods back into LSSFormulation in lss_formulation.py,
# restore the gurobipy import block, and update __init__ / build_model / solve
# to dispatch to Gurobi.

"""
    def _build_gurobi(self, verbose=True):
        \"\"\"Build the LSS ILP with Gurobi.\"\"\"
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
            obj = gp.quicksum(
                self._z[i, t]
                for i in J for t in self.T[i]
            )
            for i in J:
                if len(self.T[i]) == c:
                    for j in nodes:
                        if j != i and (i, j) in self._x:
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

        # ── Linking: magazine persistence (Eq. 15) ───────────────────────
        for i in J:
            for t in self.T[i]:
                for j in nodes:
                    if j != i and (j, i) in self._x:
                        y_j_t = self._y[j, t] if j != n else 0
                        self._m.addConstr(
                            self._y[i, t] >= self._x[j, i] + y_j_t - 1,
                            name=f"link_{j}_{i}_{t}"
                        )

        # ── Switch definition (Eq. 17) ────────────────────────────────────
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
            for i in J:
                for t in T:
                    if t not in self.T[i]:
                        self._m.addConstr(self._z[i, t] == 0, name=f"vi25_{i}_{t}")

        if verbose:
            n_arcs = len(self._x)
            print(f"LSS model built (Gurobi): {n} jobs, {n_arcs} arc vars, "
                  f"{n * self.n_tools} y-vars, {n * self.n_tools} z-vars")

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
"""

# ─────────────────────────────────────────────────────────────────────────────
# SCIP backend  (_build_scip + _solve_scip)
# ─────────────────────────────────────────────────────────────────────────────

"""
    def _build_scip(self, verbose=True):
        \"\"\"Build the LSS ILP with PySCIPOPT.\"\"\"
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
"""
