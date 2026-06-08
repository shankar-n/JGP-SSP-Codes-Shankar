"""
ARCHIVED — Gurobi and SCIP backends for the SSPMF formulation.

These backends have been archived because CPLEX is the primary solver.
The active CPLEX-only implementation is in sspmf_formulation.py.

Archived: June 2026.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Gurobi backend  (_build_gurobi + _solve_gurobi + _extract_sequence_gurobi)
# ─────────────────────────────────────────────────────────────────────────────

"""
    def _build_gurobi(self, verbose=True):
        \"\"\"Build the SSPMF model with Gurobi.\"\"\"
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
        self._y = self._m.addVars(
            [(i, k, t) for i in J for k in K for t in T],
            lb=0.0, vtype=GRB.CONTINUOUS, name="y"
        )

        self._m.update()

        # Add explicit switch variable z[k,t] for the objective
        self._z = self._m.addVars(K, T, vtype=GRB.BINARY, name="z")
        self._m.setObjective(gp.quicksum(self._z[k, t] for k in K for t in T),
                              GRB.MINIMIZE)

        # ── Assignment constraints ────────────────────────────────────────
        for i in J:
            self._m.addConstr(
                gp.quicksum(self._x[i, k] for k in K) == 1,
                name=f"assign_job_{i}"
            )
        for k in K:
            self._m.addConstr(
                gp.quicksum(self._x[i, k] for i in J) == 1,
                name=f"assign_pos_{k}"
            )

        # ── Carry flow constraints ────────────────────────────────────────
        for k in K:
            self._m.addConstr(
                gp.quicksum(
                    self._x[i, k]
                    for i in J for t in self.T[i]
                ) + gp.quicksum(self._y[i, k, t] for i in J for t in T)
                <= C,
                name=f"cap_flow_{k}"
            )

        # ── Switch variable definition ────────────────────────────────────
        for k in K:
            for t in T:
                req_at_k = gp.quicksum(self._x[i, k] for i in self.J_t[t])
                if k == 0:
                    carry_in = 0
                else:
                    carry_in = gp.quicksum(self._y[i, k-1, t] for i in J)
                self._m.addConstr(
                    self._z[k, t] >= req_at_k - carry_in, name=f"z_lb_{k}_{t}"
                )
                self._m.addConstr(
                    self._z[k, t] <= req_at_k, name=f"z_ub_{k}_{t}"
                )

        # ── Carry flow linking ────────────────────────────────────────────
        for i in J:
            for k in K:
                for t in T:
                    self._m.addConstr(
                        self._y[i, k, t] <= self._x[i, k],
                        name=f"carry_link_{i}_{k}_{t}"
                    )

        # ── Magazine capacity (direct) ────────────────────────────────────
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
            self._m.addConstr(
                gp.quicksum(self._x[p, k] for k in range(half)) == 1,
                name="sym_break"
            )

        # ── Constraint (21): flow to sink zero for early positions ────────
        if self.use_constraint_21:
            for t in T:
                n_jobs_t = len(self.J_t[t])
                for k in range(n_jobs_t - 1):
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
        \"\"\"Reconstruct job sequence from x[i,k] values.\"\"\"
        N   = self.n_jobs
        seq = [None] * N
        for i in range(N):
            for k in range(N):
                if self._x[i, k].X > 0.5:
                    seq[k] = i
        return seq if None not in seq else None
"""

# ─────────────────────────────────────────────────────────────────────────────
# SCIP backend  (_build_scip + _solve_scip)
# ─────────────────────────────────────────────────────────────────────────────

"""
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
"""
