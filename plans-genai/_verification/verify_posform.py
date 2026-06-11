"""Tests for plans-genai/10_position_formulations.tex (Claude-Fable, 2026-06-10).

Variant (a): position-indexed configuration master.
  Vars y[C,k] (k=1..n), w[t,k] (k=2..n).  Free-initial convention.
  Rows: (P) sum_C y[C,k]=1; (C) sum_k sum_{C in H_j} y >= 1;
        (W) w[t,k] >= a_t^k - a_t^{k-1},  a_t^k := sum_{C ni t} y[C,k].
  Optional (T) tool-counting rows:  sum_{k>=2} w[t,k] >= 1 - a_t^1  (t in U).

Checks:
  A1  ILP(a) == Z*  (exactness)                            [assert]
  A2  LP(a) == 0    (uniform-blend pathology; proved)      [assert]
  A3  LP(a+T) >= |U|-b (SSPMF-level bound; proved) and report exact value
  C1  variant (c) with diagonal pairs allowed: LP == 0     [report]
"""
import sys, itertools
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
sys.path.insert(0, "/sessions/peaceful-happy-lovelace/mnt/JGP-SSP-Codes-Shankar/plans-genai/_verification")
from ssp_verify import ssp_opt, ring
import random


def build_a(js, b, T, tool_rows=False):
    n = len(js)
    V = [frozenset(c) for c in itertools.combinations(sorted(T), b)]
    Tl = sorted(T)
    yi = {(ci, k): len(V) * k + ci for k in range(n) for ci in range(len(V))}
    off = len(V) * n
    wi = {(t, k): off + (k - 1) * len(Tl) + ti
          for k in range(1, n) for ti, t in enumerate(Tl)}
    nv = off + len(Tl) * (n - 1)
    c = np.zeros(nv); c[off:] = 1.0
    Aeq, beq, Aub, bub = [], [], [], []
    for k in range(n):                                   # (P)
        r = np.zeros(nv)
        for ci in range(len(V)): r[yi[ci, k]] = 1
        Aeq.append(r); beq.append(1.0)
    for j, Tj in enumerate(js):                          # (C)
        r = np.zeros(nv)
        for ci, C in enumerate(V):
            if Tj <= C:
                for k in range(n): r[yi[ci, k]] = -1
        Aub.append(r); bub.append(-1.0)
    for k in range(1, n):                                # (W)
        for t in Tl:
            r = np.zeros(nv); r[wi[t, k]] = -1
            for ci, C in enumerate(V):
                if t in C: r[yi[ci, k]] += 1; r[yi[ci, k - 1]] -= 1
            Aub.append(r); bub.append(0.0)
    if tool_rows:                                        # (T)
        for t in Tl:
            r = np.zeros(nv)
            for k in range(1, n): r[wi[t, k]] = -1
            for ci, C in enumerate(V):
                if t in C: r[yi[ci, 0]] = -1
            Aub.append(r); bub.append(-1.0)              # -(sum w) - a_t^1 <= -1
    return c, Aeq, beq, Aub, bub, nv, off


def solve(build_out, integer):
    c, Aeq, beq, Aub, bub, nv, off = build_out
    cons = [LinearConstraint(np.array(Aeq), beq, beq),
            LinearConstraint(np.array(Aub), -np.inf, bub)]
    integ = np.zeros(nv); integ[:off] = 1 if integer else 0
    r = milp(c, constraints=cons, integrality=integ, bounds=Bounds(0, np.inf))
    assert r.status == 0, r.message
    return r.fun


def build_c_diag(js, b, T):
    """Variant (c) with diagonals: columns z[(C,C'),k] for k=1..n-1 (n-1 steps),
    tool-consistency rows aggregated per (t,k); coverage via heads+first tail."""
    n = len(js)
    V = [frozenset(c) for c in itertools.combinations(sorted(T), b)]
    Tl = sorted(T)
    P = [(i, j) for i in range(len(V)) for j in range(len(V))]
    zi = {(p, k): len(P) * k + pi for k in range(n - 1) for pi, p in enumerate(P)}
    # fix index map properly
    zi = {}
    cnt = 0
    for k in range(n - 1):
        for pi, p in enumerate(P):
            zi[pi, k] = cnt; cnt += 1
    nv = cnt
    c = np.zeros(nv)
    for k in range(n - 1):
        for pi, (i, j) in enumerate(P):
            c[zi[pi, k]] = len(V[j] - V[i])
    Aeq, beq, Aub, bub = [], [], [], []
    for k in range(n - 1):                               # one pair per step
        r = np.zeros(nv)
        for pi in range(len(P)): r[zi[pi, k]] = 1
        Aeq.append(r); beq.append(1.0)
    for k in range(n - 2):                               # tool consistency
        for t in Tl:
            r = np.zeros(nv)
            for pi, (i, j) in enumerate(P):
                if t in V[j]: r[zi[pi, k]] += 1          # head of step k
                if t in V[i]: r[zi[pi, k + 1]] -= 1      # tail of step k+1
            Aeq.append(r); beq.append(0.0)
    for jb, Tj in enumerate(js):                         # coverage
        r = np.zeros(nv)
        for pi, (i, j) in enumerate(P):
            if Tj <= V[i]: r[zi[pi, 0]] -= 1             # first tail
        for k in range(n - 1):
            for pi, (i, j) in enumerate(P):
                if Tj <= V[j]: r[zi[pi, k]] -= 1         # heads
        Aub.append(r); bub.append(-1.0)
    return c, Aeq, beq, Aub, bub, nv, nv


def main():
    random.seed(4)
    cases = [("6-ring", ring(6), 3)]
    # a bound-violating instance family member (Z* above both bounds), b=3
    cases.append(("viol", [frozenset(s) for s in
                           [{0, 1}, {1, 2}, {2, 3}, {3, 4}, {0, 4}]], 3))  # 5-ring
    for i in range(3):
        nT = random.randint(4, 5); b = random.choice([2, 3]); n = random.randint(3, 4)
        js = [frozenset(random.sample(range(nT), random.randint(1, b))) for _ in range(n)]
        if len(set().union(*js)) > b:
            cases.append((f"rnd{i}", js, b))
    print(f"{'inst':8} {'Z*':>3} {'ILP(a)':>6} {'LP(a)':>6} {'LP(a+T)':>8} {'|U|-b':>5} {'LP(c-diag)':>10}")
    for name, js, b in cases:
        U = sorted(set().union(*js))
        Z = ssp_opt(js, b, set(U))
        ba = build_a(js, b, U, tool_rows=False)
        bt = build_a(js, b, U, tool_rows=True)
        ilp = solve(ba, True); lp = solve(ba, False); lpt = solve(bt, False)
        try:
            lpc = solve(build_c_diag(js, b, U), False)
        except Exception as e:
            lpc = float('nan')
        print(f"{name:8} {Z:>3} {ilp:>6.1f} {lp:>6.2f} {lpt:>8.2f} {len(U)-b:>5} {lpc:>10.2f}")
        assert abs(ilp - Z) < 1e-6, "A1 exactness violated"
        assert abs(lp) < 1e-6, "A2: LP(a) expected 0"
        assert lpt >= len(U) - b - 1e-6, "A3: counting rows should give >= |U|-b"
    # also: ILP(a+T) still == Z* (rows are valid)
    bt = build_a(ring(6), 3, sorted(set().union(*ring(6))), tool_rows=True)
    assert abs(solve(bt, True) - 3) < 1e-6, "tool rows cut off integer optimum!"
    print("A1, A2, A3 hold; tool rows are integer-valid (6-ring ILP unchanged).")


if __name__ == "__main__":
    main()
