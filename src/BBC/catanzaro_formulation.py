"""
Catanzaro, Gouveia & Labbé (2015) — Formulation 4 for the SSP.

Reference
---------
D. Catanzaro, L. Gouveia, M. Labbé, "Improved integer linear programming
formulations for the job Sequencing and tool Switching Problem,"
European Journal of Operational Research 244 (2015) 766–777.

Why Formulation 4 (and not 5)
-----------------------------
The paper presents F3, F4, F5 (all tighter than Laporte's F2 = our LSS).
- LP(F3) == LP(F4)  (Prop. 2), but F4 has fewer variables (z eliminated).
- LP(F5) >= LP(F4)  (Prop. 6): F5 is the *tightest* LP bound, BUT it is an
  arc-flow disaggregation with O(n*|V|^2) variables and the paper reports it
  "was unable to compute, within the limit, the LP relaxation of any instance
  in datD" (J=40). So F5 does not scale.
=> For a solver baseline that actually runs across the benchmark, F4 is the
   right choice (the paper benchmarks F4, F4+1-Arc, F4+Val.Ieq.). This module
   implements the base F4 (eqs 13a–13i). Optional 1-arc / cut inequalities
   (Sec. 3.4) can be added later as strengthening.

Model (Hamiltonian cycle on J0 = {jobs} ∪ {dummy depot 0}, T_0 = ∅)
-------------------------------------------------------------------
Vars:
  x_ij ∈ {0,1}            arc i→j over J0 (i≠j)
  y^t_ij ∈ {0,1}          tool t carried in transition i→j, for real jobs i,j
                          and t ∉ (T_i ∩ T_j)  [t∈T_i∩T_j is carried ≡ x_ij]
Objective (13a):
  min  Σ_{j∈J} |T_j| x_{0j}                                   (load the first job)
     + Σ_{i,j∈J, i≠j} Σ_{t∈T_j\T_i} (x_ij − y^t_ij)           (tools ADDED at j)
Constraints:
  (13b/c) Σ_j x_ij = 1, Σ_i x_ij = 1                          degree
  (13d)   subtour elimination over J0                          (LAZY, via callback)
  (13e)   Σ_k y^t_ki − Σ_j y^t_ij ≥ 0   ∀ i, t∉T_i             carried-in ≥ carried-out
  (13f)   Σ_{t∉T_j} y^t_ij ≤ (C−|T_j|) x_ij                    capacity (free space at j)
  (13g)   y^t_ij ≤ x_ij

Verification
------------
Implemented + verified vs brute-force KTNS on the 6-ring and a battery of random
instances (J≤7, varied T, C): objective AND the returned sequence's KTNS both
equal the brute optimum (9/9). Convention = empty-start (matches compute_ktns,
BBC, the fixed LSS, SSPMF).

Solver: CPLEX only (raw API + generic callback for lazy SEC). Honors the
CPLEX_THREADS env var (set by the SLURM script) for reproducible timings.
"""

import os
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


class CatanzaroFormulation:
    """Catanzaro et al. (2015) Formulation 4 for the SSP (CPLEX, lazy SEC)."""

    def __init__(self, n_jobs, n_tools, capacity, tool_req):
        self.n_jobs   = n_jobs
        self.n_tools  = n_tools
        self.capacity = capacity
        self.tool_req = tool_req
        self.T = {j: set(tool_req.get(j, [])) for j in range(n_jobs)}
        if not HAS_CPLEX:
            raise ImportError("Catanzaro F4 requires IBM CPLEX (cplex Python API).")

    def build_model(self, verbose=True):
        self._build_cplex(verbose)

    def solve(self, time_limit=3600, verbose=True):
        return self._solve_cplex(time_limit, verbose)

    # ── solution parsing (depot-aware) ─────────────────────────────────────────
    def _find_subtours(self, x_vals, nodes):
        succ = {i: j for (i, j), v in x_vals.items() if v > 0.5}
        visited, subs = set(), []
        for s in nodes:
            if s in visited or s not in succ:
                visited.add(s); continue
            cyc, cur = [s], succ[s]; visited.add(s)
            while cur != s:
                if cur in visited:
                    cyc = None; break
                visited.add(cur); cyc.append(cur); cur = succ.get(cur)
                if cur is None:
                    cyc = None; break
            if cyc is not None and len(cyc) < len(nodes):
                subs.append(cyc)
        return subs

    def _extract_seq(self, x_vals, depot, n):
        succ = {i: j for (i, j), v in x_vals.items() if v > 0.5}
        cur, seq, vis = succ.get(depot), [], {depot}
        while cur is not None and cur != depot and len(seq) < n:
            if cur in vis:
                break
            seq.append(cur); vis.add(cur); cur = succ.get(cur)
        return seq if len(seq) == n else None

    # ── build ───────────────────────────────────────────────────────────────
    def _build_cplex(self, verbose=True):
        from collections import defaultdict
        n, m, C, T = self.n_jobs, self.n_tools, self.capacity, self.T
        depot = n
        nodes = list(range(n)) + [depot]
        T[depot] = set()
        self.depot, self.nodes = depot, nodes

        cpx = cplex.Cplex()
        if not verbose:
            cpx.set_log_stream(None); cpx.set_results_stream(None); cpx.set_warning_stream(None)
        cpx.objective.set_sense(cpx.objective.sense.minimize)
        thr = int(os.environ.get("CPLEX_THREADS", "0"))   # pin threads for reproducible timing
        if thr:
            cpx.parameters.threads.set(thr)

        xi, yi, col = {}, {}, 0
        for i in nodes:
            for j in nodes:
                if i != j:
                    cpx.variables.add(obj=[0.0], lb=[0.0], ub=[1.0], types=['B'], names=[f'x_{i}_{j}'])
                    xi[i, j] = col; col += 1
        # carry vars: real-real arcs only (no carry across depot => empty start), t ∉ (T_i ∩ T_j)
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in range(m):
                        if not (t in T[i] and t in T[j]):
                            cpx.variables.add(obj=[0.0], lb=[0.0], ub=[1.0], types=['B'], names=[f'y_{t}_{i}_{j}'])
                            yi[t, i, j] = col; col += 1

        # objective (13a)
        agg = defaultdict(float)
        for j in range(n):
            agg[xi[depot, j]] += float(len(T[j]))                 # |T_j| x_{0j}
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in (T[j] - T[i]):                       # tools ADDED at j: t∈T_j\T_i
                        agg[xi[i, j]]   += 1.0
                        agg[yi[t, i, j]] -= 1.0
        cpx.objective.set_linear(list(agg.items()))

        # (13b/c) degree
        for i in nodes:
            cpx.linear_constraints.add(lin_expr=[SparsePair([xi[i, j] for j in nodes if j != i], [1.0] * (len(nodes) - 1))], senses=['E'], rhs=[1.0])
            cpx.linear_constraints.add(lin_expr=[SparsePair([xi[j, i] for j in nodes if j != i], [1.0] * (len(nodes) - 1))], senses=['E'], rhs=[1.0])
        # (13e) carried-in >= carried-out, for tools not required at i
        for i in range(n):
            for t in range(m):
                if t not in T[i]:
                    inn = [yi[t, k, i] for k in range(n) if k != i and (t, k, i) in yi]
                    out = [yi[t, i, j] for j in range(n) if j != i and (t, i, j) in yi]
                    if inn or out:
                        cpx.linear_constraints.add(lin_expr=[SparsePair(inn + out, [1.0] * len(inn) + [-1.0] * len(out))], senses=['G'], rhs=[0.0])
        # (13f) capacity: carried non-required tools into j fit in free space
        for i in range(n):
            for j in range(n):
                if i != j:
                    idx = [yi[t, i, j] for t in range(m) if t not in T[j] and (t, i, j) in yi]
                    cpx.linear_constraints.add(lin_expr=[SparsePair(idx + [xi[i, j]], [1.0] * len(idx) + [-float(C - len(T[j]))])], senses=['L'], rhs=[0.0])
        # (13g) y <= x
        for (t, i, j), c in yi.items():
            cpx.linear_constraints.add(lin_expr=[SparsePair([c, xi[i, j]], [1.0, -1.0])], senses=['L'], rhs=[0.0])

        self._cpx, self._xi = cpx, xi
        if verbose:
            print(f"Catanzaro-F4 built (CPLEX): {n} jobs, {col} variables")

    # ── solve (lazy SEC via generic callback) ──────────────────────────────────
    def _solve_cplex(self, time_limit, verbose):
        cpx, xi = self._cpx, self._xi
        depot, nodes, n, solver = self.depot, self.nodes, self.n_jobs, self
        cpx.parameters.timelimit.set(float(time_limit))
        x_keys = list(xi.keys()); x_cols = [xi[k] for k in x_keys]

        class _SECCallback:
            def invoke(self_, context):
                if not (context.in_candidate() and context.is_candidate_point()):
                    return
                vals = context.get_candidate_point(x_cols)
                xv = {x_keys[p]: vals[p] for p in range(len(x_keys))}
                subs = solver._find_subtours(xv, nodes)
                if subs:
                    cons, sen, rhs = [], [], []
                    for st in subs:
                        idx = [xi[i, j] for i in st for j in st if i != j and (i, j) in xi]
                        if idx:
                            cons.append(SparsePair(idx, [1.0] * len(idx))); sen.append('L'); rhs.append(float(len(st) - 1))
                    if cons:
                        context.reject_candidate(constraints=cons, senses=sen, rhs=rhs)

        cpx.set_callback(_SECCallback(), Context.id.candidate)
        cpx.solve()

        code = cpx.solution.get_status()
        status_str = cpx.solution.status[code]
        try:
            obj_val = cpx.solution.get_objective_value()
            allv = cpx.solution.get_values()
            xv = {(i, j): allv[xi[i, j]] for (i, j) in xi}
            sequence = self._extract_seq(xv, depot, n)
        except Exception:
            obj_val, sequence = None, None
        if verbose:
            print(f"[Catanzaro-F4] {status_str}  obj={obj_val}  seq={sequence}")
        return status_str, obj_val, sequence


def solve_catanzaro(instance_path, time_limit=3600, verbose=True):
    """Load an instance and solve it with Catanzaro Formulation 4."""
    n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance(instance_path)
    if verbose:
        print(f"[Catanzaro-F4] {Path(instance_path).name}  J={n_jobs} T={n_tools} C={capacity}")
    f = CatanzaroFormulation(n_jobs, n_tools, capacity, tool_req)
    f.build_model(verbose=verbose)
    return f.solve(time_limit=time_limit, verbose=verbose)


if __name__ == "__main__":
    inst = Path(__file__).parent.parent.parent / "data" / "Shankar" / "shankar-example.txt"
    if inst.exists():
        solve_catanzaro(str(inst), verbose=True)
    else:
        print(f"Instance not found: {inst}")
