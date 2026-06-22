#!/usr/bin/env python3
"""
verify_pricing.py  --  sign/structure check of the PCF' pricing reduced cost
(eq. rc-pcf / rho in 10b_position_branch_and_price.tex, Sec. "Pricing for PCF'").

Method (route 2 / dual-plug-in). Solve the compact PCF' LP (all configurations
enumerated) with CBC; read the duals alpha,gamma,pi,mu,lambda; then for EVERY
column y_{C,k} compare three reduced costs:
  RC_def   : definitional, 0 - sum_con pi[con]*coeff(var,con)   [ground truth]
  RC_dj    : CBC's own reported reduced cost var.dj             [cross-check]
  RC_form  : the closed formula  beta_k - sum_{t in C} rho_t^k - sum_{j: Tj<=C} pi_j

RC_form == RC_def is a convention-FREE algebraic identity (both are c - pi.A in
the same duals), so a mismatch is a genuine derivation error, not a sign
convention. The script reports the printed-draft signs (rho_doc) AND the
corrected signs (rho_fix = -rho_doc); the corrected ones are what the .tex now
uses. Optimality (RC_def >= 0, == 0 on basic columns) sanity-checks the duals.

Requires: pip install pulp.  Run: python3 verify_pricing.py
"""
import os
from itertools import combinations
import random
import pulp

HERE = os.path.dirname(os.path.abspath(__file__))
_CAND = [os.path.join(HERE, "..", "..", "data", "Shankar", "shankar-example.txt"),
         os.path.join(HERE, "..", "data", "Shankar", "shankar-example.txt")]


def parse_ring():
    path = next((p for p in _CAND if os.path.exists(p)), _CAND[0])
    L = [l for l in open(path).read().split("\n") if l.strip()]
    J, T, b = map(int, L[0].split())
    A = [list(map(int, L[1 + t].split())) for t in range(T)]
    return J, T, b, [frozenset(t for t in range(T) if A[t][j]) for j in range(J)]


def rand_inst(seed):
    rng = random.Random(seed)
    J = rng.choice([4, 5, 6]); T = rng.choice([5, 6, 7]); b = rng.choice([2, 3])
    return J, T, b, [frozenset(rng.sample(range(T), rng.randint(1, b))) for _ in range(J)]


def check(J, T, b, Tj, tol=1e-6):
    U = sorted({t for s in Tj for t in s})
    V = [frozenset(c) for c in combinations(range(T), b)]
    Hj = [[i for i, C in enumerate(V) if Tj[j] <= C] for j in range(J)]
    m = pulp.LpProblem("pcfp", pulp.LpMinimize)
    y = {(i, k): pulp.LpVariable(f"y_{i}_{k}", 0, 1) for i in range(len(V)) for k in range(J)}
    w = {(t, k): pulp.LpVariable(f"w_{t}_{k}", 0) for t in range(T) for k in range(1, J)}
    m += pulp.lpSum(w.values())
    a = lambda t, k: pulp.lpSum(y[(i, k)] for i, C in enumerate(V) if t in C)
    for k in range(J):
        m += (pulp.lpSum(y[(i, k)] for i in range(len(V))) <= 1, f"Pp_{k}")
    for k in range(J - 1):
        m += (pulp.lpSum(y[(i, k + 1)] for i in range(len(V)))
              - pulp.lpSum(y[(i, k)] for i in range(len(V))) <= 0, f"G_{k}")
    for j in range(J):
        m += (pulp.lpSum(y[(i, k)] for i in Hj[j] for k in range(J)) >= 1, f"Cov_{j}")
    for t in range(T):
        for k in range(1, J):
            m += (w[(t, k)] - a(t, k) + a(t, k - 1) >= 0, f"W_{t}_{k}")
    for t in U:
        m += (pulp.lpSum(w[(t, k)] for k in range(1, J)) + a(t, 0) >= 1, f"T_{t}")
    m.solve(pulp.PULP_CBC_CMD(msg=0))
    con = m.constraints; pi = lambda nm: con[nm].pi
    n = J
    al = [pi(f"Pp_{k}") for k in range(J)]
    ga = [pi(f"G_{k}") for k in range(J - 1)]
    pC = [pi(f"Cov_{j}") for j in range(J)]
    mu = {(t, k): pi(f"W_{t}_{k}") for t in range(T) for k in range(1, J)}
    lam = {t: pi(f"T_{t}") for t in U}

    def beta(p):
        v = -al[p]
        if p >= 1: v -= ga[p - 1]
        if p <= n - 2: v += ga[p]
        return v

    def rho_doc(t, p):           # signs as ORIGINALLY printed (buggy)
        v = 0.0
        if p >= 1: v += mu[(t, p)]
        if p <= n - 2: v -= mu[(t, p + 1)]
        if p == 0 and t in lam: v -= lam[t]
        return v

    rho_fix = lambda t, p: -rho_doc(t, p)   # CORRECTED signs (now in the .tex)

    def RC_form(rho, C, p):
        return beta(p) - sum(rho(t, p) for t in C) - sum(pC[j] for j in range(J) if Tj[j] <= C)

    def RC_def(i, p):
        var = y[(i, p)]
        return -sum(c.pi * c.get(var, 0) for c in con.values() if c.get(var, 0))

    md = mdoc = mfix = 0.0; minrc = 1e9; basic = 0.0
    for i, C in enumerate(V):
        for p in range(n):
            rdef = RC_def(i, p)
            mdoc = max(mdoc, abs(RC_form(rho_doc, C, p) - rdef))
            mfix = max(mfix, abs(RC_form(rho_fix, C, p) - rdef))
            dj = getattr(y[(i, p)], "dj", None)
            if dj is not None: md = max(md, abs(dj - rdef))
            minrc = min(minrc, rdef)
            v = y[(i, p)].value()
            if v and v > tol: basic = max(basic, abs(rdef))
    return dict(nC=len(V), n=n, md=md, mdoc=mdoc, mfix=mfix, minrc=minrc, basic=basic)


def main():
    insts = [("6-ring",) + parse_ring()] + [(f"rand{s}",) + rand_inst(s) for s in range(6)]
    print(f"{'inst':8} {'n':>2} {'cfg':>4} | {'|dj-def|':>9} {'|printed-def|':>13} "
          f"{'|fixed-def|':>11} {'minRC':>7} {'basicRC':>8}  verdict")
    allok = True
    for name, J, T, b, Tj in insts:
        r = check(J, T, b, Tj)
        ok = r['mfix'] < 1e-6 and r['minrc'] > -1e-6 and r['basic'] < 1e-6
        allok &= ok
        print(f"{name:8} {r['n']:>2} {r['nC']:>4} | {r['md']:>9.1e} {r['mdoc']:>13.1e} "
              f"{r['mfix']:>11.1e} {r['minrc']:>7.3f} {r['basic']:>8.1e}  "
              f"{'PASS' if ok else 'FAIL'}")
    print("\nCorrected formula matches solver ground truth on all instances."
          if allok else "\nFAILURE.")
    print("(|printed-def| is the ORIGINAL draft's error, kept for the record.)")


if __name__ == "__main__":
    main()
