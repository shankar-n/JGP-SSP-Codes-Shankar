"""
SSPMF — da Silva, Chaves & Yanasse (2024) multicommodity-flow model for the SSP.

Reference
---------
T. T. da Silva, A. A. Chaves, H. H. Yanasse, "A New Multicommodity Flow Model
for the Job Sequencing and Tool Switching Problem" (2024).
PDF: references/Useless/MTSP_Article.pdf  (model = eqs (1)-(16), Section 3).

This is a FAITHFUL transcription of the base model (1)-(16). Verified: it
recovers the optimal job SEQUENCE on every tested instance (== brute force).

Graph G(V,A), V = {0,1,...,N, N+1, N+2}: 0 = origin, N+1 = sink, N+2 = auxiliary.
Arcs: (i,i+1) i=0..N (capacity C); (i,N+2) i=0..N-2; (N+2,i) i=1..N-1; (i,N+1) i=1..N-1.

Variables
---------
x_ik in {0,1} : job i is processed in position k        (i,k = 0..N-1 here, 1-indexed in paper)
y_(u,v),t     : 1 unit of commodity (tool) t flows on arc (u,v)

Objective (1)  — FREE-INITIAL convention
----------------------------------------
  min Z_M = Σ_t [ Σ_{i=1..N-1} y_(i,N+1),t  +  Σ_{i=1..N-2} y_(i,N+2),t ]
This counts tools LEAVING the magazine; the initial fill (arc (0,1), C tools) and
the initially-held-out tools (arc (0,N+2), M-C tools) are NOT counted, so

        Z_M  =  (empty-start KTNS switches)  −  (initial magazine load).

Its LP-relaxation lower bound is M-C (Theorem 3.1). To compare against the other
solvers (BBC/LSS/Catanzaro, which are EMPTY-START) the benchmark re-evaluates the
returned SEQUENCE with compute_ktns (empty-start) — see benchmark_runner's
`obj_ktns` column. Do NOT compare raw `Z_M` directly to empty-start objectives.

Solver: CPLEX only. Honors CPLEX_THREADS for reproducible timings.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import cplex
    from cplex import SparsePair
    HAS_CPLEX = True
except ImportError:
    HAS_CPLEX = False

from utils import load_ssp_instance


class SSPMFFormulation:
    """da Silva et al. (2024) SSPMF — faithful base model (1)-(16)."""

    def __init__(self, n_jobs, n_tools, capacity, tool_req, use_constraint_21=False):
        self.N = n_jobs
        self.M = n_tools
        self.C = capacity
        self.tool_req = tool_req
        self.T = {i: set(tool_req.get(i, [])) for i in range(n_jobs)}
        # use_constraint_21: optional symmetry-breaking (Prop 4.1 / eq 20). NOT
        # implemented in this faithful base (the base (1)-(16) is already exact);
        # accepted for API compatibility. Add the symmetry cut later if needed
        # for speed, verifying it preserves the optimum first.
        self.use_constraint_21 = use_constraint_21
        if not HAS_CPLEX:
            raise ImportError("SSPMF requires IBM CPLEX (cplex Python API).")

    def build_model(self, verbose=True):
        self._build_cplex(verbose)

    def solve(self, time_limit=3600, verbose=True):
        return self._solve_cplex(time_limit, verbose)

    # ── build ───────────────────────────────────────────────────────────────
    def _build_cplex(self, verbose=True):
        N, M, C, T = self.N, self.M, self.C, self.T
        S, X = N + 1, N + 2
        self._S, self._X = S, X

        cpx = cplex.Cplex()
        if not verbose:
            cpx.set_log_stream(None); cpx.set_results_stream(None); cpx.set_warning_stream(None)
        cpx.objective.set_sense(cpx.objective.sense.minimize)
        thr = int(os.environ.get("CPLEX_THREADS", "0"))
        if thr:
            cpx.parameters.threads.set(thr)

        # ── arcs ──────────────────────────────────────────────────────────
        arcs = set()
        for i in range(0, N):
            arcs.add((i, i + 1))            # consec (0,1)..(N-1,N)
        arcs.add((N, S))                     # consec (N, N+1)
        for i in range(0, N - 1):
            arcs.add((i, X))                 # to-aux (i, N+2), i=0..N-2
        for i in range(1, N):
            arcs.add((X, i))                 # from-aux (N+2, i), i=1..N-1
        for i in range(1, N):
            arcs.add((i, S))                 # to-sink (i, N+1), i=1..N-1

        y = {}; x = {}; col = 0
        for (u, v) in arcs:
            for t in range(M):
                o = 0.0
                if v == S and 1 <= u <= N - 1:   # (1): Σ y_(i,N+1) , i=1..N-1
                    o = 1.0
                if v == X and 1 <= u <= N - 2:   # (1): Σ y_(i,N+2) , i=1..N-2
                    o = 1.0
                cpx.variables.add(obj=[o], lb=[0.0], ub=[1.0], types=['B'], names=[f'y_{u}_{v}_{t}'])
                y[u, v, t] = col; col += 1
        for i in range(N):
            for k in range(N):
                cpx.variables.add(obj=[0.0], lb=[0.0], ub=[1.0], types=['B'], names=[f'x_{i}_{k}'])
                x[i, k] = col; col += 1

        def C_add(idx, co, sense, rhs):
            cpx.linear_constraints.add(lin_expr=[SparsePair(idx, co)], senses=[sense], rhs=[rhs])

        # (2)(3) assignment
        for i in range(N):
            C_add([x[i, k] for k in range(N)], [1.0] * N, 'E', 1.0)
        for k in range(N):
            C_add([x[i, k] for i in range(N)], [1.0] * N, 'E', 1.0)
        # flow conservation (4)-(9), per commodity t
        for t in range(M):
            # (4) origin
            C_add([y[0, 1, t], y[0, X, t]], [1.0, 1.0], 'E', 1.0)
            # (5) nodes i=1..N-2
            for i in range(1, N - 1):
                idx = [y[i - 1, i, t]]; co = [1.0]
                if (X, i, t) in y: idx.append(y[X, i, t]); co.append(1.0)
                idx.append(y[i, i + 1, t]); co.append(-1.0)
                if (i, S, t) in y: idx.append(y[i, S, t]); co.append(-1.0)
                if (i, X, t) in y: idx.append(y[i, X, t]); co.append(-1.0)
                C_add(idx, co, 'E', 0.0)
            # (6) node N-1
            idx = [y[N - 2, N - 1, t]]; co = [1.0]
            if (X, N - 1, t) in y: idx.append(y[X, N - 1, t]); co.append(1.0)
            idx.append(y[N - 1, N, t]); co.append(-1.0)
            if (N - 1, S, t) in y: idx.append(y[N - 1, S, t]); co.append(-1.0)
            C_add(idx, co, 'E', 0.0)
            # (7) node N
            C_add([y[N - 1, N, t], y[N, S, t]], [1.0, -1.0], 'E', 0.0)
            # (8) Σ_{i=1..N} y_(i,N+1) = 1   (tosink i=1..N-1 + consec (N,N+1))
            idx = [y[i, S, t] for i in range(1, N) if (i, S, t) in y] + [y[N, S, t]]
            C_add(idx, [1.0] * len(idx), 'E', 1.0)
            # (9) auxiliary node N+2
            inn = [y[i, X, t] for i in range(0, N - 1) if (i, X, t) in y]
            out = [y[X, i, t] for i in range(1, N) if (X, i, t) in y]
            C_add(inn + out, [1.0] * len(inn) + [-1.0] * len(out), 'E', 0.0)
        # (10) x_ik <= y_(k,k+1),t  for t in T_i  (tools of job i present on its position arc)
        for i in range(N):
            for k in range(N):
                for t in T[i]:
                    C_add([x[i, k], y[k, k + 1, t]], [1.0, -1.0], 'L', 0.0)
        # (11) Σ_t y_(k,k+1),t = C  (magazine always full)
        for k in range(N):
            C_add([y[k, k + 1, t] for t in range(M)], [1.0] * M, 'E', float(C))

        self._cpx, self._x = cpx, x
        if verbose:
            print(f"SSPMF built (CPLEX): N={N} M={M} C={C}, {col} variables")

    # ── solve ───────────────────────────────────────────────────────────────
    def _solve_cplex(self, time_limit, verbose):
        cpx, x, N = self._cpx, self._x, self.N
        cpx.parameters.timelimit.set(float(time_limit))
        cpx.solve()
        code = cpx.solution.get_status()
        status_str = cpx.solution.status[code]
        try:
            obj_val = cpx.solution.get_objective_value()   # Z_M (free-initial)
            seq = [None] * N
            for i in range(N):
                for k in range(N):
                    if cpx.solution.get_values(x[i, k]) > 0.5:
                        seq[k] = i
            if any(s is None for s in seq):
                seq = None
        except Exception:
            obj_val, seq = None, None
        if verbose:
            print(f"[SSPMF] {status_str}  Z_M={obj_val} (free-initial)  seq={seq}")
        return status_str, obj_val, seq


def solve_sspmf(instance_path, time_limit=3600, verbose=True, use_constraint_21=False):
    """Load an instance and solve it with the SSPMF model."""
    n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance(instance_path)
    if verbose:
        print(f"[SSPMF] {Path(instance_path).name}  J={n_jobs} T={n_tools} C={capacity}")
    f = SSPMFFormulation(n_jobs, n_tools, capacity, tool_req, use_constraint_21=use_constraint_21)
    f.build_model(verbose=verbose)
    return f.solve(time_limit=time_limit, verbose=verbose)


if __name__ == "__main__":
    inst = Path(__file__).parent.parent.parent / "data" / "Shankar" / "shankar-example.txt"
    if inst.exists():
        solve_sspmf(str(inst), verbose=True)
    else:
        print(f"Instance not found: {inst}")
