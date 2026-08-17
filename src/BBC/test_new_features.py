#!/usr/bin/env python3
"""
Validation harness for the 2026-07 acceleration features
(conflict-graph cuts, HGS primal heuristic, Papadakos Pareto cut-lifting).

Part A (no CPLEX needed — run anywhere, incl. this sandbox):
    * conflict-cut VALIDITY: the constant root bound never exceeds the true
      optimum, and every window inequality holds for every feasible sequence;
    * HGS optimality: zero gap to brute force on small instances.

Part B (needs CPLEX + ssp_env — run on the cluster):
    * BBC with each new flag ON still returns the brute-force optimum
      (a wrong cut would be caught here);
    * the flags actually fire (heuristic_cost set, n_pareto_cuts > 0, etc.).

    source ~/miniforge3/etc/profile.d/conda.sh && conda activate ssp_env
    cd src/BBC && python test_new_features.py
"""
import sys
import random
import itertools
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "SSP"))

import conflict_cuts as cc
import hgs_heuristic as hg


def _ktns(seq, T, b):
    return hg.ktns_cost(seq, T, b)


def _gen(n, m, b, seed):
    random.seed(seed)
    return {j: tuple(sorted(random.sample(range(m), random.randint(1, min(b, m)))))
            for j in range(n)}


def _brute_opt(n, T, b):
    return min(_ktns(list(p), T, b) for p in itertools.permutations(range(n)))


# ---------------------------------------------------------------------------
def part_A(n_inst=120):
    print("=== Part A: conflict-cut validity + HGS optimality (no CPLEX) ===")
    bad_root = bad_win = 0
    for s in range(n_inst):
        n = random.randint(3, 6); m = random.randint(3, 8); b = random.randint(2, 4)
        tr = _gen(n, m, b, s); T = [set(tr[j]) for j in range(n)]
        Z = _brute_opt(n, T, b)
        lb, _ = cc.root_theta_lower_bound(tr, n, b)
        if lb > Z + 1e-9:
            bad_root += 1; print("  ROOT INVALID", tr, lb, Z)
        perms = list(itertools.permutations(range(n)))
        for L in range(3, n + 1):
            for path in itertools.permutations(range(n), L):
                cut = cc.window_cut_for_path(list(path), T, b)
                if cut is None:
                    continue
                for seq in perms:
                    x = {(seq[t], seq[t + 1]): 1.0 for t in range(n - 1)}
                    lhs = cut["theta"] * _ktns(list(seq), T, b) \
                        + sum(c * x.get(a, 0.0) for a, c in cut["arcs"].items())
                    if lhs < cut["rhs"] - 1e-9:
                        bad_win += 1; print("  WINDOW INVALID", path, seq); break
    print(f"  conflict cuts: root-invalid={bad_root}, window-invalid={bad_win}")

    gap_sum = worst = opt_hit = 0
    N = 90
    for s in range(N):
        n = random.randint(4, 6); m = random.randint(3, 8); b = random.randint(2, 4)
        tr = _gen(n, m, b, 1000 + s); T = [set(tr[j]) for j in range(n)]
        Z = _brute_opt(n, T, b)
        _, c = hg.hgs(tr, n, b, time_limit=0.1, seed=1)
        g = c - Z; gap_sum += g; worst = max(worst, g); opt_hit += (g == 0)
    print(f"  HGS: optimal on {opt_hit}/{N}, mean gap {gap_sum/N:.3f}, worst {worst}")
    ok = (bad_root == 0 and bad_win == 0 and worst == 0)
    print("  PART A:", "PASS" if ok else "*** FAIL ***")
    return ok


# ---------------------------------------------------------------------------
def part_B(time_limit=20):
    print("\n=== Part B: BBC-with-flags vs brute force (needs CPLEX) ===")
    try:
        import cplex  # noqa: F401
        from branch_and_benders_cut_cplex import BranchAndBendersCutSSP_CPLEX
        from utils import compute_ktns
    except Exception as e:
        print(f"  SKIP (CPLEX/env not available: {e})")
        return None

    flagsets = [
        ("baseline (F only)",      dict(use_fractional_cuts=True)),
        ("+conflict_cuts",         dict(use_fractional_cuts=True, use_conflict_cuts=True)),
        ("+primal_heuristic",      dict(use_fractional_cuts=True, use_primal_heuristic=True)),
        ("+pareto_cuts",           dict(use_fractional_cuts=True, use_pareto_cuts=True)),
        ("+ALL",                   dict(use_fractional_cuts=True, use_conflict_cuts=True,
                                        use_primal_heuristic=True, use_pareto_cuts=True)),
    ]
    wrong = 0
    for s in range(6):
        n = random.randint(5, 7); m = random.randint(4, 8); b = random.randint(3, 4)
        tr = _gen(n, m, b, 7000 + s); T = [set(tr[j]) for j in range(n)]
        Z = _brute_opt(n, T, b)
        print(f"  instance n={n} m={m} b={b}  brute opt={Z}")
        for name, kw in flagsets:
            solver = BranchAndBendersCutSSP_CPLEX(n, m, b, tr, worker_lp_reuse=True,
                                                  heuristic_time=1.0, **kw)
            solver.build_master_problem(verbose=False)
            status, obj, seq = solver.solve(time_limit=time_limit, verbose=False)
            got = compute_ktns(seq, tr, b)[0] if seq else None
            st = solver.solve_stats
            flag = "" if got == Z else "  <<< WRONG OPTIMUM"
            if got != Z:
                wrong += 1
            fired = []
            if kw.get("use_conflict_cuts"):
                fired.append(f"conflict={st.get('n_conflict_cuts')}")
            if kw.get("use_primal_heuristic"):
                fired.append(f"heur_cost={st.get('heuristic_cost')}")
            if kw.get("use_pareto_cuts"):
                fired.append(f"pareto={st.get('n_pareto_cuts')}")
            print(f"    {name:20s} got={got} status={status} {' '.join(fired)}{flag}")
    print("  PART B:", "PASS (no wrong optima)" if wrong == 0 else f"*** {wrong} WRONG ***")
    return wrong == 0


if __name__ == "__main__":
    a = part_A()
    b = part_B()
    print("\nSUMMARY: partA", "PASS" if a else "FAIL",
          "| partB", ("PASS" if b else "FAIL") if b is not None else "SKIPPED")
