#!/usr/bin/env python3
"""
PCF' EXACT branch-and-price (PySCIPOpt).  Milestone P2 (2026-06-22) -- DONE.

Idea (robust branching). The plain PCF' master is augmented with integer
presence variables a_{t,p} in {0,1} and linking constraints
    (Link)  a_{t,p} = sum_{C ni t} y_{C,p},
and (W),(T) are written over a. SCIP branches on the a_{t,p} (NOT on the
columns), so branching never forbids a column the pricer might regenerate --
the pricer keeps its exact form at every node. The LP relaxation is unchanged
(a is just a substitution), so the root LP is still |U|-b; integrality of all
a_{t,p} pins the magazine = the configuration at each position, hence an
integral, valid schedule.

Pricer. y_{C,p} now meets only [P'],[G],(C),(Link); its reduced cost is
    rc(C,p) = beta(p) - sum_{j: Tj<=C} pi_j + sum_{t in C} linkdual_{t,p},
i.e. the same max-weight-b-subset-with-coverage-bonus oracle as eq:rho, with the
per-tool weight rho2[t,p] = -linkdual_{t,p}.  (Equivalent to the W/T-dual form
verified in _verification/verify_pricing.py; here (W)/(T) sit on a, so their
duals reach y through Link.)

Verified: IP == Z* (brute-force KTNS) on the 6-ring (IP=3, root node, 7/120
columns) and random instances. Common SSP code reused from src/SSP/.
Run:  python3 pcf_prime_bp.py     Requires: pyscipopt.
"""
import os
import sys
import math
from itertools import combinations, permutations
from pyscipopt import Model, Pricer, SCIP_RESULT, SCIP_PARAMSETTING, quicksum

HERE = os.path.dirname(os.path.abspath(__file__))


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


# brute-force optimum (KTNS over all job orders) -- ground truth for the self-check
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


def beta(p, n, al, ga):
    v = -al[p]
    if p >= 1:     v -= ga[p - 1]
    if p <= n - 2: v += ga[p]
    return v


class BPPricer(Pricer):
    def pricerinit(self):
        d = self.data
        d['Pp']  = [self.model.getTransformedCons(c) for c in d['Pp']]
        d['G']   = [self.model.getTransformedCons(c) for c in d['G']]
        d['Cov'] = [self.model.getTransformedCons(c) for c in d['Cov']]
        d['Link'] = {k: self.model.getTransformedCons(c) for k, c in d['Link'].items()}

    def _price(self, getter):
        d = self.data; n = d['n']; Tn = d['Tn']; Tj = d['Tj']
        al = [getter(c) for c in d['Pp']]; ga = [getter(c) for c in d['G']]
        piC = [getter(c) for c in d['Cov']]
        ld = {k: getter(c) for k, c in d['Link'].items()}      # linking-constraint duals
        eps = 1e-7; added = 0
        for p in range(n):
            rho2 = {t: -ld[(t, p)] for t in range(Tn)}          # tool weight = -linkdual
            bC, bv = self._best_subset(rho2, piC)               # enumerate (small) or MILP (10b Sec 4)
            if beta(p, n, al, ga) - bv < -eps and (bC, p) not in d['y']:
                self._add(bC, p); added += 1
        return added

    def _best_subset(self, rho2, piC):
        """Most-rewarding b-subset: max sum_{t in C} rho2_t + sum_{j: Tj<=C} pi_j, |C|=b.
        Enumerate when binom(|T|,b) is small; else the coverage-bonus MILP (10b Sec 4) in an
        in-process SCIP sub-model. Both oracles were checked equal on 100 random dual vectors (P5b)."""
        d = self.data; Tn = d['Tn']; Tj = d['Tj']; b = d['b']
        if d['Vall'] is not None:                               # small |V|: enumerate
            bC, bv = None, -1e18
            for C in d['Vall']:
                val = sum(rho2[t] for t in C) + sum(piC[j] for j in range(len(Tj)) if Tj[j] <= C)
                if val > bv: bv, bC = val, C
            return bC, bv
        sm = Model(); sm.hideOutput()                          # large |V|: MILP price
        x = {t: sm.addVar(vtype="B") for t in range(Tn)}
        u = {j: sm.addVar(vtype="C", lb=0, ub=1) for j in range(len(Tj))}
        sm.setObjective(quicksum(rho2[t] * x[t] for t in range(Tn))
                        + quicksum(piC[j] * u[j] for j in range(len(Tj))), "maximize")
        sm.addCons(quicksum(x[t] for t in range(Tn)) == b)
        for j in range(len(Tj)):
            for t in Tj[j]:
                sm.addCons(u[j] <= x[t])
        sm.optimize()
        bC = frozenset(t for t in range(Tn) if sm.getVal(x[t]) > 0.5); sm.freeProb()
        bv = sum(rho2[t] for t in bC) + sum(piC[j] for j in range(len(Tj)) if Tj[j] <= bC)
        return bC, bv

    def _add(self, C, p):
        d = self.data; m = self.model; n = d['n']
        v = m.addVar(f"y_{len(d['y'])}", vtype="C", lb=0, ub=1, obj=0, pricedVar=True)
        d['y'][(C, p)] = v
        m.addConsCoeff(d['Pp'][p], v, 1.0)
        if p >= 1:     m.addConsCoeff(d['G'][p - 1], v, 1.0)
        if p <= n - 2: m.addConsCoeff(d['G'][p], v, -1.0)
        for j in range(len(d['Tj'])):
            if d['Tj'][j] <= C: m.addConsCoeff(d['Cov'][j], v, 1.0)
        for t in C:
            m.addConsCoeff(d['Link'][(t, p)], v, -1.0)

    def pricerredcost(self):
        self._price(self.model.getDualsolLinear); return {'result': SCIP_RESULT.SUCCESS}

    def pricerfarkas(self):
        self._price(self.model.getDualfarkasLinear); return {'result': SCIP_RESULT.SUCCESS}


def branch_and_price(J, T, b, Tj, timelimit=90):
    """Exact PCF' B&P. Returns (status, IP, nodes, ncols, full)."""
    n = J; U = sorted({t for s in Tj for t in s})
    ENUM_MAX = 20000                       # enumerate b-subsets below this; MILP-price above
    Vall = [frozenset(c) for c in combinations(range(T), b)] if math.comb(T, b) <= ENUM_MAX else None
    m = Model("pcf_bp")
    m.setPresolve(SCIP_PARAMSETTING.OFF); m.setIntParam("presolving/maxrounds", 0)
    m.hideOutput(); m.setParam("limits/time", timelimit)
    w = {(t, p): m.addVar(f"w_{t}_{p}", vtype="C", lb=0, obj=1.0) for t in range(T) for p in range(1, n)}
    a = {(t, p): m.addVar(f"a_{t}_{p}", vtype="I", lb=0, ub=1, obj=0) for t in range(T) for p in range(n)}
    y = {}
    for j in range(J):                                          # feasible seed
        fill = [t for t in range(T) if t not in Tj[j]][:b - len(Tj[j])]
        C = frozenset(set(Tj[j]) | set(fill)); y[(C, j)] = m.addVar(f"y_seed_{j}", vtype="C", lb=0, ub=1, obj=0)
    Pp = [m.addCons(quicksum(y[(C, pp)] for (C, pp) in y if pp == p) <= 1, f"Pp_{p}", modifiable=True)
          for p in range(n)]
    G = [m.addCons(quicksum(y[(C, pp)] for (C, pp) in y if pp == p + 1)
                   - quicksum(y[(C, pp)] for (C, pp) in y if pp == p) <= 0, f"G_{p}", modifiable=True)
         for p in range(n - 1)]
    Cov = [m.addCons(quicksum(y[(C, pp)] for (C, pp) in y if Tj[j] <= C) >= 1, f"Cov_{j}", modifiable=True)
           for j in range(J)]
    for t in range(T):
        for p in range(1, n):
            m.addCons(w[(t, p)] - a[(t, p)] + a[(t, p - 1)] >= 0, f"W_{t}_{p}")
    for t in U:
        m.addCons(quicksum(w[(t, p)] for p in range(1, n)) + a[(t, 0)] >= 1, f"T_{t}")
    Link = {(t, p): m.addCons(a[(t, p)] - quicksum(y[(C, pp)] for (C, pp) in y if pp == p and t in C) == 0,
                              f"L_{t}_{p}", modifiable=True) for t in range(T) for p in range(n)}
    pr = BPPricer(); m.includePricer(pr, "BPPricer", "PCF' branch-and-price")
    pr.data = dict(Pp=Pp, G=G, Cov=Cov, Link=Link, y=y, Vall=Vall, Tj=Tj, U=U, n=n, Tn=T, b=b)
    m.setParam("limits/nodes", 1)                         # process root only -> capture CG-converged bound
    m.optimize()
    try:
        rlp = m.getDualbound()                            # root LP bound (getDualboundRoot gives +inf sentinel when root closes)
        rlp = None if rlp is None or abs(rlp) > 1e15 else rlp
    except Exception:
        rlp = None
    m.setParam("limits/nodes", -1)                        # resume to optimum (same limits/time budget, cumulative)
    m.optimize()
    if m.getNSols() == 0:                                 # no incumbent (e.g. timed out): report cleanly
        return m.getStatus(), None, m.getNNodes(), len(y), None, rlp
    cfg = [frozenset(t for t in range(T) if m.getVal(a[(t, p)]) > 0.5) for p in range(n)]
    asg, seq = set(), []                                  # reconstruct a job sequence for obj_ktns
    for p in range(n):
        for j in range(len(Tj)):
            if j not in asg and Tj[j] <= cfg[p]: asg.add(j); seq.append(j)
    seq = seq if len(seq) == len(Tj) else None
    return m.getStatus(), m.getObjVal(), m.getNNodes(), len(y), seq, rlp


if __name__ == "__main__":
    J, T, b, Tj = load_instance()
    Z = zstar(J, T, b, Tj)
    st, ip, nodes, nc, seq, rlp = branch_and_price(J, T, b, Tj)
    print(f"6-ring: Z*={Z}  B&P IP={ip:.2f} [{st}]  nodes={nodes}  cols={nc}  rootLP={rlp}")
    print("P2 PASS: exact branch-and-price == Z*." if abs(ip - Z) < 1e-6 else "P2 FAIL")
