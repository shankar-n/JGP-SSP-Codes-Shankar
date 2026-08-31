#!/usr/bin/env python3
"""
Window inequalities for the position-indexed master.
====================================================

AUDIT STATUS: VALID BUT REDUNDANT
---------------------------------
This module is retained to reproduce the internship diagnostic. The implemented
fractional row cannot strengthen PCF/PCF': for each tool and each h in W, summing the
existing transition rows gives

    sum_{k=p}^r w[t,k] >= a[t,h] - a[t,p-1].

Maximising the right-hand side over h and summing over tools gives exactly the row
below. Do not advertise or enable this module as a bound strengthening; a successor
needs job-window union structure or configuration-level consistency.

WHY THIS EXISTS
---------------
Every inequality in both exact methods of this project is supported on a *local*
object: an arc (i, j) in the Benders master, a single position in PCF'.  The
objective is not local.  Writing b_t for the number of maximal blocks of positions
in which tool t sits in the magazine,

    Z  =  sum_t b_t ,        and      b_t >= 1  gives exactly  q = |U| - b.

Everything above q is a *re-insertion*, and a re-insertion is caused by the global
interleaving of the sequence -- by which jobs are pushed apart, not by which pairs
happen to be adjacent.  That is why the Benders master's root LP equals |U| on 87%
of runs and why the PCF' relaxation equals q on 100% of them.

THE FAMILY
----------
Let W = [p, r] be a contiguous block of positions, 1 <= p <= r <= n-1.  Every tool
required somewhere inside W is either already in the magazine at position p-1, or is
inserted at some position of W.  The magazine at p-1 holds exactly b tools.  Hence

    sum_t sum_{k in W} w[t,k]   >=   |{t : t present somewhere in W}|  -  sum_t a[t,p-1]

Introducing  zw[t] >= a[t,k]  for every k in W  (the LP drives zw down to the max,
which is what we want, because zw appears with a negative coefficient) this becomes
the linear row

    sum_t sum_{k in W} w[t,k]  -  sum_t zw[t]  +  sum_t a[t,p-1]  >=  0.

Two properties originally motivated the diagnostic.

  * It is not local.  The row talks about a stretch of the schedule, so it can charge
    a re-insertion that no arc-indexed or single-position row can see.

  * It is a ROBUST cut.  The row contains only master variables -- w, a and the new
    zw -- and no column variable y.  Its dual therefore never reaches the pricing
    problem, and the set-union-knapsack oracle is completely unchanged.  Nothing in
    the pricer or the branching rule has to be touched.

The experiment uses the 15 admissible windows of lengths 2--4 at n=8 as a small,
static regression pool. The counting rows T_t are stronger than this fractional
max-presence construction because they require every used tool to appear somewhere.

WHAT IT IS WORTH
----------------
Measured by `verification/bound_probe.py` on the 62 loose cases in the fixed
81-instance Laporte3 diagnostic sample, taking for each family the best bound it could
possibly deliver:

    arc-supported family (what both solvers have today)   8.9% of the gap, 0% median
    window family                                        30.9% of the gap, 40% median

The window figure is a ceiling: it is the minimum over sequences of the best window
decomposition, and a linear relaxation will land somewhere below it.  The arc figure
is a ceiling too, and it is the one that matters -- it says the families currently in
the solver have almost no headroom left, whatever is done to them.

USE
---
    from window_cuts import add_window_cuts
    stats = add_window_cuts(m, a, w, n, T, b, Tj, max_len=4)

Call it after the master rows are built and before the first solve.
"""
from __future__ import annotations

try:
    from pyscipopt import quicksum
except ImportError:                       # allows the self-test to run without SCIP
    quicksum = None


def max_tools_in_window(Tj, length, n_used):
    """Valid upper bound on |U_W| for a window holding `length` jobs.

    The window can hold at most `length` jobs, so its tool union is at most the sum of
    the `length` largest job requirements, and never more than the tools in use.  A
    window whose bound is <= b can never be violated and is not created.
    """
    sizes = sorted((len(s) for s in Tj), reverse=True)
    return min(sum(sizes[:length]), n_used)


def add_window_cuts(m, a, w, n, T, b, Tj, max_len=4, min_len=2, verbose=False):
    """Add the redundant window extension to a PCF' master for reproduction only.

    Parameters
    ----------
    m        : the pyscipopt Model holding the master
    a        : dict (t, p) -> presence variable, p = 0 .. n-1
    w        : dict (t, p) -> insertion variable, p = 1 .. n-1  (these carry obj = 1)
    n, T, b  : jobs, tools, magazine capacity
    Tj       : list of tool requirement sets, one per job
    max_len  : longest window to create.  The reported n=8 experiment uses 4, giving
               a deliberately small static pool.  Cost grows linearly in this limit.
    min_len  : shortest window.  Length 1 is dominated by the existing W_{t}_{p} rows.

    Returns
    -------
    dict with the number of windows, rows and variables added.
    """
    if quicksum is None:
        raise RuntimeError("pyscipopt is required to add cuts to a live master")

    used = sorted({t for s in Tj for t in s})
    n_used = len(used)

    n_win = n_row = n_var = 0
    for length in range(min_len, max_len + 1):
        if max_tools_in_window(Tj, length, n_used) <= b:
            continue                       # this window length can never be violated
        for p in range(1, n - length + 1):
            r = p + length - 1             # window is positions p .. r inclusive
            if r > n - 1:
                break
            zw = {}
            for t in used:
                v = m.addVar(f"zw_{p}_{r}_{t}", vtype="C", lb=0.0, ub=1.0, obj=0.0)
                zw[t] = v
                n_var += 1
                for k in range(p, r + 1):
                    m.addCons(v - a[(t, k)] >= 0, f"zwlb_{p}_{r}_{t}_{k}")
                    n_row += 1
            m.addCons(
                quicksum(w[(t, k)] for t in used for k in range(p, r + 1))
                - quicksum(zw[t] for t in used)
                + quicksum(a[(t, p - 1)] for t in used)
                >= 0,
                f"win_{p}_{r}",
            )
            n_row += 1
            n_win += 1

    stats = {"windows": n_win, "rows": n_row, "vars": n_var,
             "max_len": max_len, "min_len": min_len}
    if verbose:
        print(f"[window cuts] {n_win} windows, {n_row} rows, {n_var} variables "
              f"(lengths {min_len}..{max_len})")
    return stats


# ---------------------------------------------------------------------------
# Self-test: brute-force validity check.  Run this before any cluster job.
# ---------------------------------------------------------------------------

def _ktns_trace(order, Tj, b, T):
    """Return (cost, presence[t][k], insert[t][k]) for the KTNS loading of `order`."""
    n = len(order)
    pres = [[0] * n for _ in range(T)]
    ins = [[0] * n for _ in range(T)]
    mag = set()
    cost = 0
    for k, j in enumerate(order):
        need = set(Tj[j])
        add = need - mag
        cost += len(add)
        for t in add:
            ins[t][k] = 1
        mag |= need
        if len(mag) > b:
            # evict the tools, not needed now, whose next use is furthest away
            def nxt(t):
                for kk in range(k + 1, n):
                    if t in Tj[order[kk]]:
                        return kk
                return n + 1
            drop = sorted(mag - need, key=nxt, reverse=True)
            for t in drop[:len(mag) - b]:
                mag.discard(t)
        for t in mag:
            pres[t][k] = 1
    return cost, pres, ins


def self_test(trials=400, seed=0):
    """Check the window inequality on random instances, against every sequence.

    For each instance and each sequence, the inequality is evaluated exactly as the
    master would evaluate it at that integer point.  Any violation is a bug in the
    derivation, not in the solver, so this must pass before the family is used.
    """
    import random
    from itertools import permutations

    rng = random.Random(seed)
    checked = violations = 0
    for _ in range(trials):
        n = rng.randint(3, 6)
        T = rng.randint(4, 9)
        b = rng.randint(2, min(5, T))
        Tj = [set(rng.sample(range(T), rng.randint(1, b))) for _ in range(n)]
        for order in permutations(range(n)):
            _, pres, ins = _ktns_trace(list(order), Tj, b, T)
            for p in range(1, n):
                for r in range(p, n):
                    lhs = sum(ins[t][k] for t in range(T) for k in range(p, r + 1))
                    zw = sum(1 for t in range(T)
                             if any(pres[t][k] for k in range(p, r + 1)))
                    prev = sum(pres[t][p - 1] for t in range(T))
                    checked += 1
                    if lhs - zw + prev < -1e-9:
                        violations += 1
                        if violations <= 3:
                            print(f"  VIOLATION n={n} T={T} b={b} W=[{p},{r}] "
                                  f"lhs={lhs} zw={zw} prev={prev} Tj={Tj} order={order}")
    print(f"window inequality checked at {checked:,} integer points; "
          f"{violations} violations")
    return violations == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_test() else 1)
