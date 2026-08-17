#!/usr/bin/env python3
"""
verify_everything.py  --  ONE script that checks the project against ground truth.

The point: you should not have to trust the code, the report, or me.  This script
re-derives things from scratch (brute force) and re-computes the report's numbers
straight from the raw result files, then prints PASS / FAIL for each claim.

Three independent parts:

  PART A  (no CPLEX -- run anywhere)   correctness of the NEW code:
          * the conflict-graph cuts are valid (never exclude a real schedule);
          * the HGS heuristic is optimal on small instances.
  PART B  (needs CPLEX -- run on the cluster)   the SOLVERS are correct:
          * every solver, with each new flag on, returns the brute-force optimum
            on small instances.  A wrong cut is caught here.
  PART C  (no CPLEX -- run anywhere)   the REPORT's numbers are real:
          * recompute the headline campaign numbers straight from the raw CSVs
            and compare to what the report claims.

Run:
    python verify_everything.py            # A + C always; B if CPLEX is present
    python verify_everything.py --quick    # smaller/faster
Exit code is 0 only if every check that ran passed.
"""
import sys
import os
import itertools
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent            # repo root (this script lives in verification/)
sys.path.insert(0, str(ROOT / "src" / "BBC"))
sys.path.insert(0, str(ROOT / "src" / "SSP"))

QUICK = "--quick" in sys.argv
_PASS, _FAIL = [], []


def check(name, ok, detail=""):
    (_PASS if ok else _FAIL).append(name)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"   ({detail})" if detail else ""))
    return ok


# ---------------------------------------------------------------------------
# shared: correct KTNS (empty-start) + tiny helpers
# ---------------------------------------------------------------------------
def ktns(seq, T, b):
    n = len(seq); mag = set(); cost = 0

    def nxt(t, p):
        for k in range(p + 1, n):
            if t in T[seq[k]]:
                return k
        return 10 ** 9
    for p in range(n):
        need = T[seq[p]]; cost += len(need - mag); mag |= need
        while len(mag) > b:
            cand = [x for x in mag if x not in need]
            mag.discard(max(cand, key=lambda x: nxt(x, p)))
    return cost


def rand_instance(n, m, b, seed):
    random.seed(seed)
    return {j: tuple(sorted(random.sample(range(m), random.randint(1, min(b, m)))))
            for j in range(n)}


def brute_opt(n, T, b):
    return min(ktns(list(p), T, b) for p in itertools.permutations(range(n)))


# ===========================================================================
# PART A -- the new code is correct (no CPLEX)
# ===========================================================================
def part_A():
    print("\nPART A -- new code correctness (conflict cuts + HGS), no CPLEX")
    try:
        import conflict_cuts as cc
        import hgs_heuristic as hg
    except Exception as e:
        return check("import conflict_cuts / hgs_heuristic", False, str(e))

    n_inst = 20 if QUICK else 60
    root_bad = win_bad = 0
    for s in range(n_inst):
        n = random.randint(3, 5 if QUICK else 6); m = random.randint(3, 8)
        b = random.randint(2, 4); tr = rand_instance(n, m, b, s)
        T = [set(tr[j]) for j in range(n)]
        Z = brute_opt(n, T, b)
        lb, _ = cc.root_theta_lower_bound(tr, n, b)
        if lb > Z + 1e-9:
            root_bad += 1
        perms = list(itertools.permutations(range(n)))
        for L in range(3, n + 1):
            for path in itertools.permutations(range(n), L):
                cut = cc.window_cut_for_path(list(path), T, b)
                if cut is None:
                    continue
                for seq in perms:
                    x = {(seq[t], seq[t + 1]): 1.0 for t in range(n - 1)}
                    lhs = cut["theta"] * ktns(list(seq), T, b) + \
                        sum(c * x.get(a, 0.0) for a, c in cut["arcs"].items())
                    if lhs < cut["rhs"] - 1e-9:
                        win_bad += 1
                        break
    check("conflict root bound never exceeds the true optimum", root_bad == 0,
          f"{n_inst} instances")
    check("conflict window cuts hold for every schedule", win_bad == 0,
          f"{n_inst} instances, all sequences")

    N = 40 if QUICK else 80
    opt_hit = 0
    for s in range(N):
        n = random.randint(4, 5 if QUICK else 6); m = random.randint(3, 8)
        b = random.randint(2, 4); tr = rand_instance(n, m, b, 1000 + s)
        T = [set(tr[j]) for j in range(n)]
        _, c = hg.hgs(tr, n, b, time_limit=0.1, seed=1)
        opt_hit += (c == brute_opt(n, T, b))
    check("HGS heuristic is optimal on small instances", opt_hit == N,
          f"{opt_hit}/{N} optimal")


# ===========================================================================
# PART B -- the solvers are correct (needs CPLEX; run on cluster)
# ===========================================================================
def part_B():
    print("\nPART B -- solver correctness vs brute force (needs CPLEX)")
    try:
        import cplex  # noqa
        from branch_and_benders_cut_cplex import BranchAndBendersCutSSP_CPLEX
        from utils import compute_ktns
    except Exception as e:
        print(f"  SKIP -- CPLEX / env not available here ({e}). Run this part on the cluster.")
        return
    flagsets = [
        ("baseline (frac only)", dict(use_fractional_cuts=True)),
        ("+conflict_cuts",       dict(use_fractional_cuts=True, use_conflict_cuts=True)),
        ("+primal_heuristic",    dict(use_fractional_cuts=True, use_primal_heuristic=True)),
        ("+pareto_cuts",         dict(use_fractional_cuts=True, use_pareto_cuts=True)),
        ("+ALL",                 dict(use_fractional_cuts=True, use_conflict_cuts=True,
                                      use_primal_heuristic=True, use_pareto_cuts=True)),
    ]
    wrong = 0; ninst = 4 if QUICK else 8
    for s in range(ninst):
        n = random.randint(5, 7); m = random.randint(4, 8); b = random.randint(3, 4)
        tr = rand_instance(n, m, b, 7000 + s); T = [set(tr[j]) for j in range(n)]
        Z = brute_opt(n, T, b)
        for name, kw in flagsets:
            sv = BranchAndBendersCutSSP_CPLEX(n, m, b, tr, worker_lp_reuse=True,
                                              heuristic_time=1.0, **kw)
            sv.build_master_problem(verbose=False)
            _, obj, seq = sv.solve(time_limit=20, verbose=False)
            got = compute_ktns(seq, tr, b)[0] if seq else None
            if got != Z:
                wrong += 1
                print(f"     WRONG: n={n} {name} got={got} brute={Z}")
    check("every BBC flag combination returns the brute-force optimum", wrong == 0,
          f"{ninst} instances x {len(flagsets)} configs")


# ===========================================================================
# PART C -- the report's numbers match the raw data (no CPLEX)
# ===========================================================================
def _load_csv(path):
    import csv
    with open(path) as f:
        return list(csv.DictReader(f))


def part_C():
    print("\nPART C -- report numbers recomputed from the raw CSVs (no CPLEX)")
    raw = ROOT / "src" / "BBC" / "raw_results.csv"
    bnp = ROOT / "src" / "BNP" / "bnp_results.csv"
    if not raw.exists():
        check("find src/BBC/raw_results.csv", False, str(raw))
        return
    rows = [r for r in _load_csv(raw) if r["J"].strip()]
    SEC = {"Laporte3", "Laporte4", "Laporte5"}

    def suite(r):
        return "secondary" if r["benchmark_set"] in SEC else "primary"

    def solved(solver, suite_name, config=None):
        return sum(1 for r in rows if r["solver"] == solver
                   and suite(r) == suite_name and r["status"] == "MIP_optimal"
                   and (config is None or r["config"] == config))

    # Each claim below cites where it appears in the report so YOU can check the
    # 'claimed' side against the paper; the 'actual' side is recomputed here.
    claims = [
        # (label, claimed, actual)   -- report Table 2 (tab:solves) + VERIFIED_FACTS
        ("LSS primary solves = 91",              91,  solved("LSS", "primary")),
        ("CATZ primary solves = 91",             91,  solved("CATZ", "primary")),
        ("CATZ secondary solves = 455",          455, solved("CATZ", "secondary")),
        ("SSPMF primary solves = 138",           138, solved("SSPMF", "primary")),
        ("BBC-LP primary solves = 43",           43,  solved("BBC", "primary", "BBC-LP")),
        ("BBC-LP secondary solves = 244",        244, solved("BBC", "secondary", "BBC-LP")),
        ("BBC-LP+T secondary solves = 274",      274, solved("BBC", "secondary", "BBC-LP+T")),
        ("BBC-K secondary solves = 239",         239, solved("BBC", "secondary", "BBC-K")),
    ]
    for label, claimed, actual in claims:
        check(label, claimed == actual, f"claimed {claimed}, data says {actual}")

    # BBC 'found but not proven': every BBC-LP timeout already holds the known optimum.
    opt = {}
    for r in rows:
        if r["status"] == "MIP_optimal" and r["obj_ktns"].strip():
            opt[(r["instance"], r["J"], r["T"], r["C"])] = float(r["obj_ktns"])
    to = [r for r in rows if r["solver"] == "BBC" and r["config"] == "BBC-LP"
          and r["status"] != "MIP_optimal"]
    held = 0
    for r in to:
        if not r["obj_ktns"].strip():
            continue
        key = (r["instance"], r["J"], r["T"], r["C"])
        if opt.get(key) == float(r["obj_ktns"]):
            held += 1
    check("every BBC-LP timeout already holds the optimum (found, not proven)",
          held == len(to) and len(to) > 0, f"{held}/{len(to)}")

    # Bound-tight split: needs |U| from the instance files.
    import numpy as np
    idx = {}
    for p in (ROOT / "data" / "From_Felipe" / "data").glob("**/*.txt"):
        try:
            t = open(p).read().split(); J, T, C = int(t[0]), int(t[1]), int(t[2])
            A = np.array(list(map(int, t[3:3 + T * J]))).reshape(T, J)
            idx.setdefault((os.path.basename(p)[:-4], J, T, C), int((A.sum(1) > 0).sum()))
        except Exception:
            pass
    if idx:
        solved_keys = {(r["instance"], int(r["J"]), int(r["T"]), int(r["C"])): float(r["obj_ktns"])
                       for r in rows if r["status"] == "MIP_optimal" and r["obj_ktns"].strip()}
        tight = sum(1 for (i, J, T, C), z in solved_keys.items()
                    if idx.get((i, J, T, C)) is not None and z == idx[(i, J, T, C)])
        total = len(solved_keys)
        pct = 100 * tight / total if total else 0
        check("bound-tight share of solved instances = 48.0% (report abstract)",
              abs(pct - 48.0) < 1.0, f"{tight}/{total} = {pct:.1f}%")

    # BNP numbers (if the file is present)
    if bnp.exists():
        brows = [r for r in _load_csv(bnp) if r["J"].strip()]

        def bsolved(solver):
            return sum(1 for r in brows if r["solver"] == solver
                       and int(r["J"]) <= 25 and r["status"] == "optimal")
        check("PCFp solves at n<=25 = 94 (report Section 5)", bsolved("PCFp") == 94,
              f"data says {bsolved('PCFp')}")
        check("PTF solves at n<=25 = 72 (report Section 5)", bsolved("PTF") == 72,
              f"data says {bsolved('PTF')}")
    else:
        print(f"  NOTE  src/BNP/bnp_results.csv not found -- BNP checks skipped.")


# ===========================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("verify_everything.py  --  checking the project against ground truth")
    print("=" * 70)
    part_A()
    part_B()
    part_C()
    print("\n" + "=" * 70)
    print(f"RESULT: {len(_PASS)} passed, {len(_FAIL)} failed")
    if _FAIL:
        print("FAILURES:")
        for f in _FAIL:
            print("   -", f)
    print("=" * 70)
    sys.exit(1 if _FAIL else 0)
