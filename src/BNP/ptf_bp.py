#!/usr/bin/env python3
"""
PTF EXACT branch-and-price (PySCIPOpt).  P3 (exact B&P) + P5b (MILP pricers).

Master (10b Sec. 'Pricing for PTF'): arc variables z^k_{(C,C')} on the
diagonal-free arc set + absorbing bottom node, with integer presence vars a_{t,p}
linked to the trajectory (robust branching, as in PCF' P2). Column generation
prices BOTH arc families:
  * real->real arcs  -- the coupled pair: a bilinear two-b-subset MILP (10b Sec 5),
    McCormick-linearized p_t = x'_t (1 - x_t);
  * (C, bot) arcs    -- a SINGLE b-subset problem (the head bot has no tools), i.e.
    the PCF' pricer; and (bot,bot) is one static arc per step.
Both pricing oracles enumerate when binom(|T|,b) is small and otherwise solve the
MILP in an in-process SCIP sub-model.

SCALE (P5b ⊥-arc fix, 2026-06-22): the master no longer enumerates the bottom
arcs -- the cons/abs rows are created explicitly (polynomial), so the model is
O(n|T|) rows and bottom arcs are priced like the rest. PTF therefore scales (the
limit is now pricing-MILP speed, not master construction).

Validated: coupled-pair MILP == enumeration on 60 random dual draws; (C,bot) MILP
== enumeration on 40 draws; B&P IP == Z* (brute KTNS) on 6-ring + randoms, both
enumerate and MILP pricer paths. Common SSP code reused from src/SSP/.
Requires: pyscipopt.
"""
import os
import sys
import math
from itertools import combinations, permutations
from pyscipopt import Model, Pricer, SCIP_RESULT, SCIP_PARAMSETTING, quicksum

HERE = os.path.dirname(os.path.abspath(__file__))
BOT = frozenset()                                   # the unique tool-less node
ENUM_MAX = 4000                                     # enumerate arc pairs below this; MILP-price above


def load_instance(path=None):
    if path is None:
        path = os.path.join(HERE, "..", "..", "data", "Shankar", "shankar-example.txt")
    try:
        sys.path.insert(0, os.path.join(HERE, "..", "SSP"))
        from utils import load_ssp_instance
        J, T, C, A, Tj = load_ssp_instance(path)
        return J, T, C, [frozenset(s) for s in Tj]
    except Exception:
        L = [l for l in open(path).read().split("\n") if l.strip()]
        J, T, b = map(int, L[0].split())
        A = [list(map(int, L[1 + t].split())) for t in range(T)]
        return J, T, b, [frozenset(t for t in range(T) if A[t][j]) for j in range(J)]


def cost(C, D):
    return 0 if len(D) == 0 else len(D - C)


def arc_coeffs(C, D, k, n, Tj, U):
    """Coefficients of arc (C->D) at step k in every master row -- single source of
    truth, used to BUILD constraints and to compute reduced costs when enumerating."""
    out = [(('Pz', k), 1.0)]
    if k <= n - 3:
        for t in D: out.append((('cons', (t, k)), 1.0))
    if 1 <= k <= n - 2:
        for t in C: out.append((('cons', (t, k - 1)), -1.0))
    if k <= n - 3 and len(C) > 0 and len(D) == 0: out.append((('abs', k), 1.0))
    if 1 <= k <= n - 2 and len(C) == 0 and len(D) == 0: out.append((('abs', k - 1), -1.0))
    for j in range(len(Tj)):
        c = 0.0
        if k == 0 and len(C) > 0 and Tj[j] <= C: c += 1
        if len(D) > 0 and Tj[j] <= D: c += 1
        if c: out.append((('Cz', j), c))
    for t in U:
        c = 0.0
        if (t in D) and (t not in C): c += 1
        if k == 0 and (t in C): c += 1
        if c: out.append((('Tz', t), c))
    if k <= n - 2:
        for t in C: out.append((('Link', (t, k)), -1.0))
    if k == n - 2:
        for t in D: out.append((('Link', (t, n - 1)), -1.0))
    return out


def _ktns(seq, Tj, b, T):
    nd = [Tj[j] for j in seq]; n = len(nd)
    nxt = lambda t, s: next((k for k in range(s, n) if t in nd[k]), 10**9)
    M, ins = set(), 0
    for i in range(n):
        for t in nd[i]:
            if t not in M:
                if len(M) < b: M.add(t)
                else:
                    c = [x for x in M if x not in nd[i]]; M.discard(max(c, key=lambda x: nxt(x, i))); M.add(t)
                ins += 1
        while len(M) < b:
            rem = [t for t in range(T) if t not in M]; M.add(min(rem, key=lambda t: nxt(t, i + 1))); ins += 1
    return ins - b


def zstar(J, T, b, Tj):
    return min(_ktns(list(p), Tj, b, T) for p in permutations(range(J)))


def seed_traj(J, T, b, Tj):
    """A feasible full-magazine trajectory (KTNS on identity order, consecutive dups collapsed)."""
    nd = [Tj[j] for j in range(J)]; n = J
    nxt = lambda t, s: next((k for k in range(s, n) if t in nd[k]), 10**9)
    M, traj = set(), []
    for i in range(n):
        for t in nd[i]:
            if t not in M:
                if len(M) < b: M.add(t)
                else:
                    c = [x for x in M if x not in nd[i]]; M.discard(max(c, key=lambda x: nxt(x, i))); M.add(t)
        while len(M) < b:
            rem = [t for t in range(T) if t not in M]; M.add(min(rem, key=lambda t: nxt(t, i + 1)))
        traj.append(frozenset(M))
    D = [traj[0]]
    for c in traj[1:]:
        if c != D[-1]: D.append(c)
    return D


class PTFPricer(Pricer):
    def pricerinit(self):
        self.data['cons'] = {k: self.model.getTransformedCons(c) for k, c in self.data['cons'].items()}

    def _best_real_arc(self, du, k):
        """Min-reduced-cost real->real arc at step k (coupled pair): enumerate or MILP."""
        d = self.data; n = d['n']; Tj = d['Tj']; U = d['U']; reals = d['reals']
        if reals is not None:
            bC = bD = None; brc = 1e18
            for C in reals:
                for D in reals:
                    if C == D: continue
                    rc = cost(C, D) - sum(du[key] * co for key, co in arc_coeffs(C, D, k, n, Tj, U))
                    if rc < brc: brc, bC, bD = rc, C, D
            return bC, bD, brc
        T = d['Tn']; b = d['b']; g = du.get
        dl = lambda t, kk: g(('cons', (t, kk)), 0.0); pij = lambda j: g(('Cz', j), 0.0)
        lam = lambda t: g(('Tz', t), 0.0); mu = lambda t, p: g(('Link', (t, p)), 0.0)
        sm = Model(); sm.hideOutput()
        x = {t: sm.addVar(vtype="B") for t in range(T)}; xp = {t: sm.addVar(vtype="B") for t in range(T)}
        p = {t: sm.addVar(vtype="C", lb=0, ub=1) for t in range(T)}      # = xp_t (1 - x_t) at integer
        u = {j: sm.addVar(vtype="C", lb=0, ub=1) for j in range(len(Tj))}
        up = {j: sm.addVar(vtype="C", lb=0, ub=1) for j in range(len(Tj))}
        obj = quicksum((1 - lam(t)) * p[t] for t in range(T)) - g(('Pz', k), 0.0)
        if k <= n - 3: obj += quicksum(-dl(t, k) * xp[t] for t in range(T))
        if 1 <= k <= n - 2: obj += quicksum(dl(t, k - 1) * x[t] for t in range(T))
        if k <= n - 2: obj += quicksum(mu(t, k) * x[t] for t in range(T))
        if k == n - 2: obj += quicksum(mu(t, n - 1) * xp[t] for t in range(T))
        if k == 0:
            obj += quicksum(-lam(t) * x[t] for t in range(T)) + quicksum(-pij(j) * u[j] for j in range(len(Tj)))
        obj += quicksum(-pij(j) * up[j] for j in range(len(Tj)))
        sm.setObjective(obj, "minimize")
        sm.addCons(quicksum(x[t] for t in range(T)) == b); sm.addCons(quicksum(xp[t] for t in range(T)) == b)
        for t in range(T):
            sm.addCons(p[t] <= xp[t]); sm.addCons(p[t] <= 1 - x[t]); sm.addCons(p[t] >= xp[t] - x[t])
        for j in range(len(Tj)):
            for t in Tj[j]:
                sm.addCons(u[j] <= x[t]); sm.addCons(up[j] <= xp[t])
        sm.addCons(quicksum(p[t] for t in range(T)) >= 1)               # C != D
        sm.optimize()
        C = frozenset(t for t in range(T) if sm.getVal(x[t]) > 0.5)
        D = frozenset(t for t in range(T) if sm.getVal(xp[t]) > 0.5)
        rc = sm.getObjVal(); sm.freeProb()
        return C, D, rc

    def _best_bot_arc(self, du, k):
        """Min-reduced-cost (C -> bot) arc at step k: single b-subset (head bot has no tools)."""
        d = self.data; n = d['n']; Tj = d['Tj']; U = d['U']; reals = d['reals']
        if reals is not None:
            bC = None; brc = 1e18
            for C in reals:
                rc = cost(C, BOT) - sum(du[key] * co for key, co in arc_coeffs(C, BOT, k, n, Tj, U))
                if rc < brc: brc, bC = rc, C
            return bC, brc
        T = d['Tn']; b = d['b']; g = du.get
        dl = lambda t, kk: g(('cons', (t, kk)), 0.0); pij = lambda j: g(('Cz', j), 0.0)
        lam = lambda t: g(('Tz', t), 0.0); mu = lambda t, p: g(('Link', (t, p)), 0.0)
        const = -g(('Pz', k), 0.0) - (g(('abs', k), 0.0) if k <= n - 3 else 0.0)

        def w(t):
            ww = 0.0
            if 1 <= k <= n - 2: ww += dl(t, k - 1)
            if k <= n - 2: ww += mu(t, k)
            if k == 0: ww -= lam(t)
            return ww

        sm = Model(); sm.hideOutput()
        x = {t: sm.addVar(vtype="B") for t in range(T)}
        u = {j: sm.addVar(vtype="C", lb=0, ub=1) for j in range(len(Tj))}
        obj = quicksum(w(t) * x[t] for t in range(T)) + const
        if k == 0: obj += quicksum(-pij(j) * u[j] for j in range(len(Tj)))
        sm.setObjective(obj, "minimize"); sm.addCons(quicksum(x[t] for t in range(T)) == b)
        if k == 0:
            for j in range(len(Tj)):
                for t in Tj[j]: sm.addCons(u[j] <= x[t])
        sm.optimize()
        C = frozenset(t for t in range(T) if sm.getVal(x[t]) > 0.5); rc = sm.getObjVal(); sm.freeProb()
        return C, rc

    def _price(self, getter):
        d = self.data; n = d['n']; Tj = d['Tj']; U = d['U']; cons = d['cons']
        du = {k: getter(c) for k, c in cons.items()}
        eps = 1e-7; added = 0
        for k in range(n - 1):
            rC, rD, rrc = self._best_real_arc(du, k)         # real->real (coupled pair)
            bC, brc = self._best_bot_arc(du, k)              # C -> bot (single set)
            C, D, rc = (rC, rD, rrc) if rrc <= brc else (bC, BOT, brc)
            if rc < -eps and (C, D, k) not in d['z']:
                v = self.model.addVar(f"z_{len(d['z'])}", vtype="C", lb=0, ub=1, obj=cost(C, D), pricedVar=True)
                d['z'][(C, D, k)] = v
                for key, co in arc_coeffs(C, D, k, n, Tj, U):
                    self.model.addConsCoeff(cons[key], v, co)
                added += 1
        return added

    def pricerredcost(self):
        self._price(self.model.getDualsolLinear); return {'result': SCIP_RESULT.SUCCESS}

    def pricerfarkas(self):
        self._price(self.model.getDualfarkasLinear); return {'result': SCIP_RESULT.SUCCESS}


def branch_and_price(J, T, b, Tj, timelimit=120, force_milp=False):
    """Exact PTF B&P. Polynomial master (bottom arcs priced). Returns (status, IP, nodes, n_real_arcs)."""
    n = J; U = sorted({t for s in Tj for t in s})
    use_milp = force_milp or math.comb(T, b) > ENUM_MAX
    reals = None if use_milp else [frozenset(c) for c in combinations(range(T), b)]
    m = Model("ptf_bp")
    m.setPresolve(SCIP_PARAMSETTING.OFF); m.setIntParam("presolving/maxrounds", 0)
    m.hideOutput(); m.setParam("limits/time", timelimit)
    z = {}

    def addarc(C, D, k):
        if (C, D, k) not in z:
            z[(C, D, k)] = m.addVar(f"z0_{len(z)}", vtype="C", lb=0, ub=1, obj=cost(C, D))

    D = seed_traj(J, T, b, Tj); mm = len(D)               # feasible seed; NO static (C,bot) enumeration
    for l in range(mm - 1): addarc(D[l], D[l + 1], l)
    addarc(D[mm - 1], BOT, mm - 1)
    for k in range(n - 1): addarc(BOT, BOT, k)            # (bot,bot) static, one per step

    a = {(t, p): m.addVar(f"a_{t}_{p}", vtype="I", lb=0, ub=1, obj=0) for t in range(T) for p in range(n)}
    dummy = m.addVar("dummy", lb=0, ub=0)                 # zero-fixed; keeps empty rows valid ExprCons
    keys = set()
    for (C, D2, k) in z:
        for key, _ in arc_coeffs(C, D2, k, n, Tj, U): keys.add(key)
    for k in range(n - 1): keys.add(('Pz', k))
    for j in range(J): keys.add(('Cz', j))
    for t in U: keys.add(('Tz', t))
    for t in range(T):
        for p in range(n): keys.add(('Link', (t, p)))
    for t in range(T):                                    # explicit cons rows (poly), k = 0..n-3
        for k in range(n - 2): keys.add(('cons', (t, k)))
    for k in range(n - 2): keys.add(('abs', k))           # explicit abs rows
    expr = {key: dummy for key in keys}
    for (C, D2, k), v in z.items():
        for key, co in arc_coeffs(C, D2, k, n, Tj, U): expr[key] = expr[key] + co * v
    cons = {}
    for key in keys:
        kind = key[0]
        if kind == 'Link': continue
        e = expr[key]
        if kind == 'Pz':   cons[key] = m.addCons(e == 1, str(key), modifiable=True)
        elif kind == 'cons': cons[key] = m.addCons(e == 0, str(key), modifiable=True)
        elif kind == 'abs':  cons[key] = m.addCons(e <= 0, str(key), modifiable=True)
        elif kind == 'Cz':   cons[key] = m.addCons(e >= 1, str(key), modifiable=True)
        elif kind == 'Tz':   cons[key] = m.addCons(e >= 1, str(key), modifiable=True)
    for t in range(T):
        for p in range(n):
            cons[('Link', (t, p))] = m.addCons(a[(t, p)] + expr[('Link', (t, p))] == 0,
                                               f"L_{t}_{p}", modifiable=True)
    pr = PTFPricer(); m.includePricer(pr, "PTFPricer", "PTF branch-and-price")
    pr.data = dict(cons=cons, z=z, reals=reals, Tj=Tj, U=U, n=n, Tn=T, b=b)
    m.setParam("limits/nodes", 1)                         # process root only -> capture CG-converged bound
    m.optimize()
    try:
        rlp = m.getDualbound()                            # root LP bound (getDualboundRoot gives +inf sentinel when root closes)
        rlp = None if rlp is None or abs(rlp) > 1e15 else rlp
    except Exception:
        rlp = None
    m.setParam("limits/nodes", -1)                        # resume to optimum (same limits/time budget, cumulative)
    m.optimize()
    nreal = sum(1 for (C, D2, k) in z if len(C) > 0 and len(D2) > 0)
    if m.getNSols() == 0:                                 # no incumbent (e.g. timed out): report cleanly
        return m.getStatus(), None, m.getNNodes(), nreal, None, rlp
    cfg = [frozenset(t for t in range(T) if m.getVal(a[(t, p)]) > 0.5) for p in range(n)]
    asg, seq = set(), []                                  # reconstruct a job sequence for obj_ktns
    for p in range(n):
        for j in range(len(Tj)):
            if j not in asg and Tj[j] <= cfg[p]: asg.add(j); seq.append(j)
    seq = seq if len(seq) == len(Tj) else None
    return m.getStatus(), m.getObjVal(), m.getNNodes(), nreal, seq, rlp


if __name__ == "__main__":
    J, T, b, Tj = load_instance()
    Z = zstar(J, T, b, Tj)
    st, ip, nodes, nr, seq, rlp = branch_and_price(J, T, b, Tj)
    print(f"6-ring: Z*={Z}  PTF B&P IP={ip:.2f} [{st}]  nodes={nodes}  real-arcs={nr}  rootLP={rlp}")
    print("PTF B&P (bottom arcs priced) == Z*." if abs(ip - Z) < 1e-6 else "FAIL")
