#!/usr/bin/env python3
"""
Cross-solver agreement / regression test for the SSP exact solvers.

On small instances (where brute-force KTNS gives the ground-truth optimum) this
runs every solver and checks that (a) its objective equals the brute optimum and
(b) the returned sequence is a valid permutation whose KTNS cost equals the
optimum:

  - BBC  (CPLEX)            branch_and_benders_cut_cplex.BranchAndBendersCutSSP_CPLEX
  - LSS  (Laporte 2004)     lss_formulation.LSSFormulation
  - SSPMF (da Silva 2024)   sspmf_formulation.SSPMFFormulation
  - CATZ-F4 (Catanzaro 2015) catanzaro_formulation.CatanzaroFormulation

This is the regression net the repo previously lacked: any formulation bug shows
up as a disagreement with brute force on a tiny instance (this is exactly how the
LSS switch-count bug and the SSPMF/depot-dual issues were caught). Any solver
whose library is unavailable is skipped.

Run:  python test_solver.py
"""

import sys
import itertools
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))          # src/
sys.path.insert(0, str(Path(__file__).parent.parent / "SSP"))  # src/SSP (utils, compute_ktns)
sys.path.insert(0, str(Path(__file__).parent))                 # src/BBC

from utils import load_ssp_instance, compute_ktns

TIME_LIMIT = 30   # seconds per solver (instances are tiny)


def brute(n, tool_req, C):
    """Ground-truth SSP optimum (empty-start KTNS) by full permutation search."""
    best = 10 ** 9
    for p in itertools.permutations(range(n)):
        c, _ = compute_ktns(list(p), tool_req, C)
        if c < best:
            best = c
    return best


# ── solver adapters: each returns (obj, sequence); ImportError => skipped ──────
def _make_bbc(comb, frac, trip):
    """Adapter for one BBC flag combination (comb_cuts, frac_cuts, triplet_bounds)."""
    def _run(n, m, C, tr):
        from branch_and_benders_cut_cplex import BranchAndBendersCutSSP_CPLEX
        s = BranchAndBendersCutSSP_CPLEX(n, m, C, tr, worker_lp_reuse=True,
                                         use_combinatorial_cuts=comb, use_fractional_cuts=frac,
                                         use_triplet_bounds=trip, parallel=False)
        s.build_master_problem(verbose=False)
        _st, ob, seq = s.solve(time_limit=TIME_LIMIT, verbose=False)
        return ob, seq
    return _run

def _run_lss(n, m, C, tr):
    from lss_formulation import LSSFormulation
    s = LSSFormulation(n, m, C, tr)
    s.build_model(verbose=False)
    _st, ob, seq = s.solve(time_limit=TIME_LIMIT, verbose=False)
    return ob, seq

def _run_sspmf(n, m, C, tr):
    from sspmf_formulation import SSPMFFormulation
    s = SSPMFFormulation(n, m, C, tr, use_constraint_21=False)
    s.build_model(verbose=False)
    _st, ob, seq = s.solve(time_limit=TIME_LIMIT, verbose=False)
    return ob, seq

def _run_catz(n, m, C, tr):
    from catanzaro_formulation import CatanzaroFormulation
    s = CatanzaroFormulation(n, m, C, tr)
    s.build_model(verbose=False)
    _st, ob, seq = s.solve(time_limit=TIME_LIMIT, verbose=False)
    return ob, seq

# All 8 BBC ablation flag combos (comb x frac x triplet) -- so a cut/bound bug in any
# config is caught vs brute force, not discovered mid-campaign. Plus the 3 baselines.
_BBC_FLAGS = [(c, f, t) for c in (False, True) for f in (False, True) for t in (False, True)]
SOLVERS = ([(f"BBC[c{int(c)}f{int(f)}t{int(t)}]", _make_bbc(c, f, t)) for (c, f, t) in _BBC_FLAGS]
           + [("LSS", _run_lss), ("SSPMF", _run_sspmf), ("CATZ-F4", _run_catz)])


def instances():
    """The 6-ring counterexample + a few random small instances."""
    out = []
    ring = Path(__file__).parent.parent.parent / "data" / "Shankar" / "shankar-example.txt"
    if ring.exists():
        n, m, C, _A, tr = load_ssp_instance(str(ring))
        out.append(("ring", n, m, C, tr))
    rnd = random.Random(0)
    for i, (n, m, C) in enumerate([(5, 5, 2), (6, 6, 3)]):
        tr = {j: sorted(rnd.sample(range(m), rnd.randint(1, min(C, m)))) for j in range(n)}
        out.append((f"rand{i}", n, m, C, tr))
    return out


def main():
    fails = 0
    for name, n, m, C, tr in instances():
        opt = brute(n, tr, C)
        print(f"\n=== {name}: J={n} T={m} C={C} | brute optimum = {opt} ===")
        for label, fn in SOLVERS:
            try:
                ob, seq = fn(n, m, C, tr)
            except ImportError as e:
                print(f"  SKIP  {label:8s} (import: {e})")
                continue
            except Exception as e:
                print(f"  ERROR {label:8s} {type(e).__name__}: {e}")
                fails += 1
                continue
            obr = round(ob) if ob is not None else None
            seq_ok = seq is not None and sorted(seq) == list(range(n))
            kt = compute_ktns(list(seq), tr, C)[0] if seq_ok else None
            ok = (obr == opt) and (kt == opt)
            fails += 0 if ok else 1
            print(f"  {'OK  ' if ok else 'FAIL'}  {label:8s} obj={obr}  seqKTNS={kt}  validperm={seq_ok}")
    print(f"\n{'ALL SOLVERS AGREE WITH BRUTE FORCE' if fails == 0 else f'*** {fails} disagreement(s) — check formulations ***'}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
