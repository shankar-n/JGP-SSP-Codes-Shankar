#!/usr/bin/env python3
"""
PCF' EXACT branch-and-price (PySCIPOpt), with optional pricing ACCELERATIONS.
Milestone P2 (2026-06-22) verified; accelerations added 2026-08 (P5/P6).

Base method (robust branching). The plain PCF' master is augmented with integer
presence variables a_{t,p} in {0,1} and linking constraints
    (Link)  a_{t,p} = sum_{C ni t} y_{C,p},
with (W),(T) written over a. SCIP branches on the a_{t,p} (NOT on the columns), so
branching never forbids a column the pricer might regenerate -- the pricer keeps its
exact form at every node. The LP relaxation is unchanged; root LP = |U|-b.

Pricer reduced cost (verified, sign-corrected in _verification/verify_pricing.py):
    rc(C,p) = beta(p) - sum_{t in C} rho2[t,p] - sum_{j: Tj<=C} pi_j,
    rho2[t,p] = -linkdual_{t,p},
and the most-negative column solves a max-weight-b-subset-with-coverage-bonus oracle
(Set-Union Knapsack): enumerate C(T,b) when small, else a compact MILP.

ACCELERATIONS (all OFF by default; each PRESERVES exactness -- verified IP == Z*):
  heuristic_pricing : a fast greedy b-subset is tried first; the exact oracle is used
                      only to CERTIFY that no improving column remains (so termination
                      still rests on the exact oracle -- exactness intact).
  multiple_pricing  : up to `kcols` negative-reduced-cost columns are added per
                      position per round (enumerate path), cutting master reoptimisations.
  warm_start        : the initial pool is seeded from a greedy nearest-overlap schedule
                      instead of the trivial one-config-per-job pool.
  stabilize         : Wentges dual-price smoothing (static alpha) with a mis-price
                      backtrack that reverts to Dantzig pricing, so the LP is only
                      declared optimal under the *real* duals (exactness intact).
Refs: Luebbecke & Desrosiers 2005 (CG survey); Wentges 1997; Pessoa et al. 2018 (INFORMS
JOC, smoothing); Tang et al. 1988 (KTNS); da Silva & Yanasse 2024 (coverage bound).

Run:  python3 pcf_prime_bp.py            (self-test: baseline + every accelerator == Z*)
Requires: pyscipopt.
"""
import os
import sys
import math
from itertools import combinations, permutations
from pyscipopt import Model, Pricer, SCIP_RESULT, SCIP_PARAMSETTING, quicksum

HERE = os.path.dirname(os.path.abspath(__file__))
_VERSION = "pcf_prime_bp/accel-2026-08"
LAST_STATS = {}          # populated by branch_and_price: {'rounds': CG iters, 'ncols': columns}


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


# ── acceleration helpers ──────────────────────────────────────────────────────
def _greedy_subset(rho2, piC, Tj, Tn, b):
    """Heuristic pricing: greedy max-weight b-subset for the Set-Union Knapsack
    max_{|C|=b} sum_{t in C} rho2[t] + sum_{j: Tj[j]<=C} piC[j].  O(b*T*|J|)."""
    C = set()
    while len(C) < b:
        best_t, best_gain = None, -1e18
        for t in range(Tn):
            if t in C:
                continue
            newC = C | {t}
            bonus = sum(piC[j] for j in range(len(Tj)) if Tj[j] <= newC and not Tj[j] <= C)
            gain = rho2[t] + bonus
            if gain > best_gain:
                best_gain, best_t = gain, t
        C.add(best_t)
    val = sum(rho2[t] for t in C) + sum(piC[j] for j in range(len(Tj)) if Tj[j] <= C)
    return frozenset(C), val


def _greedy_schedule_configs(J, T, b, Tj):
    """Warm start: a nearest-overlap job order, each job's requirement padded to a
    size-b configuration (padding preferentially with the next job's tools). Returns
    [(frozenset C, position p)] -- feasible seed columns near a good schedule."""
    unused = set(range(J))
    start = max(range(J), key=lambda j: len(Tj[j]))
    seq = [start]; unused.discard(start)
    while unused:
        nxt = max(unused, key=lambda j: len(Tj[seq[-1]] & Tj[j]))
        seq.append(nxt); unused.discard(nxt)
    cfgs = []
    for p, j in enumerate(seq):
        C = set(Tj[j])
        pad = (list(Tj[seq[p + 1]]) if p + 1 < len(seq) else []) + list(range(T))
        for t in pad:
            if len(C) >= b:
                break
            C.add(t)
        cfgs.append((frozenset(sorted(C)[:b]), p))
    return cfgs


class BPPricer(Pricer):
    def pricerinit(self):
        d = self.data
        d['Pp']  = [self.model.getTransformedCons(c) for c in d['Pp']]
        d['G']   = [self.model.getTransformedCons(c) for c in d['G']]
        d['Cov'] = [self.model.getTransformedCons(c) for c in d['Cov']]
        d['Link'] = {k: self.model.getTransformedCons(c) for k, c in d['Link'].items()}
        d.setdefault('rounds', 0); d.setdefault('pi_best', None); d.setdefault('best_rmp', 1e18)

    # -- dual bookkeeping --
    def _duals(self, getter):
        d = self.data
        return dict(al=[getter(c) for c in d['Pp']], ga=[getter(c) for c in d['G']],
                    piC=[getter(c) for c in d['Cov']],
                    ld={k: getter(c) for k, c in d['Link'].items()})

    def _blend(self, cur, best, a):
        return dict(
            al=[a * bb + (1 - a) * cc for cc, bb in zip(cur['al'], best['al'])],
            ga=[a * bb + (1 - a) * cc for cc, bb in zip(cur['ga'], best['ga'])],
            piC=[a * bb + (1 - a) * cc for cc, bb in zip(cur['piC'], best['piC'])],
            ld={k: a * best['ld'][k] + (1 - a) * cur['ld'][k] for k in cur['ld']})

    # -- candidate generation for one position --
    def _candidates(self, rho2, piC, p, k, use_heur):
        d = self.data; Tn = d['Tn']; Tj = d['Tj']; b = d['b']
        if use_heur:
            C, _ = _greedy_subset(rho2, piC, Tj, Tn, b)
            return [C]
        if d['Vall'] is not None:                              # enumerate: top-k by value
            scored = sorted(
                ((sum(rho2[t] for t in C) + sum(piC[j] for j in range(len(Tj)) if Tj[j] <= C), C)
                 for C in d['Vall']), key=lambda z: z[0], reverse=True)
            return [C for _, C in scored[:k]]
        return [self._milp_best(rho2, piC)]                    # large |V|: MILP single best

    def _milp_best(self, rho2, piC):
        d = self.data; Tn = d['Tn']; Tj = d['Tj']; b = d['b']
        sm = Model(); sm.hideOutput()
        x = {t: sm.addVar(vtype="B") for t in range(Tn)}
        u = {j: sm.addVar(vtype="C", lb=0, ub=1) for j in range(len(Tj))}
        sm.setObjective(quicksum(rho2[t] * x[t] for t in range(Tn))
                        + quicksum(piC[j] * u[j] for j in range(len(Tj))), "maximize")
        sm.addCons(quicksum(x[t] for t in range(Tn)) == b)
        for j in range(len(Tj)):
            for t in Tj[j]:
                sm.addCons(u[j] <= x[t])
        sm.optimize()
        C = frozenset(t for t in range(Tn) if sm.getVal(x[t]) > 0.5); sm.freeProb()
        return C

    def _round(self, gen, real, use_heur):
        """Generate candidate columns using dual set `gen`; ADD those whose reduced cost
        under the REAL duals is < -eps (up to kcols per position). Returns #added."""
        d = self.data; n = d['n']; Tn = d['Tn']; Tj = d['Tj']
        eps = 1e-7; k = d['kcols'] if d.get('multiple') else 1; added = 0
        for p in range(n):
            rho2g = {t: -gen['ld'][(t, p)] for t in range(Tn)}
            for C in self._candidates(rho2g, gen['piC'], p, k, use_heur):
                if (C, p) in d['y']:
                    continue
                rc = beta(p, n, real['al'], real['ga']) - (
                    sum(-real['ld'][(t, p)] for t in C)
                    + sum(real['piC'][j] for j in range(len(Tj)) if Tj[j] <= C))
                if rc < -eps:
                    self._add(C, p); added += 1
        return added

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
        d = self.data; d['rounds'] += 1
        real = self._duals(self.model.getDualsolLinear)
        heur = bool(d.get('heuristic'))
        if d.get('stabilize'):
            try:
                rmp = self.model.getLPObjVal()
            except Exception:
                rmp = None
            if d['pi_best'] is None or (rmp is not None and rmp < d['best_rmp'] - 1e-9):
                d['best_rmp'] = rmp if rmp is not None else d['best_rmp']; d['pi_best'] = real
            a = float(d.get('stab_alpha', 0.5)); added = 0
            while True:                                        # mis-price backtrack -> Dantzig
                gen = self._blend(real, d['pi_best'], a) if a > 1e-6 else real
                added = self._round(gen, real, use_heur=(heur and a <= 1e-6))
                if added > 0 or a <= 1e-6:
                    break
                a *= 0.5
            if heur and added == 0:                            # exact certification
                added = self._round(real, real, use_heur=False)
        else:
            added = self._round(real, real, use_heur=heur)
            if heur and added == 0:                            # exact certification
                added = self._round(real, real, use_heur=False)
        return {'result': SCIP_RESULT.SUCCESS}

    def pricerfarkas(self):
        real = self._duals(self.model.getDualfarkasLinear)
        self._round(real, real, use_heur=False)                # feasibility: exact, unsmoothed
        return {'result': SCIP_RESULT.SUCCESS}


try:
    from window_cuts import add_window_cuts
except Exception:                                   # keep the module importable without it
    add_window_cuts = None

LAST_WINDOW_STATS = {}


def branch_and_price(J, T, b, Tj, timelimit=90, accel=None):
    """Exact PCF' B&P. `accel` (dict) toggles pricing accelerations:
        heuristic_pricing, multiple_pricing, warm_start, stabilize (bools),
        kcols (int, default 5), stab_alpha (float in [0,1), default 0.5),
        window_cuts (bool), window_max_len (int, default 4),
        root_only (bool -- stop after the root bound, for pilots).
    Returns (status, IP, nodes, ncols, seq, root_lp)."""
    accel = accel or {}
    n = J; U = sorted({t for s in Tj for t in s})
    ENUM_MAX = 20000
    Vall = [frozenset(c) for c in combinations(range(T), b)] if math.comb(T, b) <= ENUM_MAX else None
    m = Model("pcf_bp")
    m.setPresolve(SCIP_PARAMSETTING.OFF); m.setIntParam("presolving/maxrounds", 0)
    m.hideOutput(); m.setParam("limits/time", timelimit)
    w = {(t, p): m.addVar(f"w_{t}_{p}", vtype="C", lb=0, obj=1.0) for t in range(T) for p in range(1, n)}
    a = {(t, p): m.addVar(f"a_{t}_{p}", vtype="I", lb=0, ub=1, obj=0) for t in range(T) for p in range(n)}
    y = {}
    for j in range(J):                                          # trivial feasible seed (always present)
        fill = [t for t in range(T) if t not in Tj[j]][:b - len(Tj[j])]
        C = frozenset(set(Tj[j]) | set(fill)); y[(C, j)] = m.addVar(f"y_seed_{j}", vtype="C", lb=0, ub=1, obj=0)
    if accel.get("warm_start"):                                 # extra seed near a good schedule
        for C, p in _greedy_schedule_configs(J, T, b, Tj):
            if (C, p) not in y:
                y[(C, p)] = m.addVar(f"y_ws_{p}", vtype="C", lb=0, ub=1, obj=0)
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
    LAST_WINDOW_STATS.clear()
    if accel.get("window_cuts"):
        if add_window_cuts is None:
            raise RuntimeError("window_cuts requested but window_cuts.py is not importable")
        LAST_WINDOW_STATS.update(
            add_window_cuts(m, a, w, n, T, b, Tj,
                            max_len=int(accel.get("window_max_len", 4)),
                            min_len=int(accel.get("window_min_len", 2))))
    Link = {(t, p): m.addCons(a[(t, p)] - quicksum(y[(C, pp)] for (C, pp) in y if pp == p and t in C) == 0,
                              f"L_{t}_{p}", modifiable=True) for t in range(T) for p in range(n)}
    pr = BPPricer(); m.includePricer(pr, "BPPricer", "PCF' branch-and-price")
    pr.data = dict(Pp=Pp, G=G, Cov=Cov, Link=Link, y=y, Vall=Vall, Tj=Tj, U=U, n=n, Tn=T, b=b,
                   heuristic=bool(accel.get("heuristic_pricing")),
                   multiple=bool(accel.get("multiple_pricing")),
                   stabilize=bool(accel.get("stabilize")),
                   kcols=int(accel.get("kcols", 5)),
                   stab_alpha=float(accel.get("stab_alpha", 0.5)),
                   rounds=0, pi_best=None, best_rmp=1e18)
    m.setParam("limits/nodes", 1)                         # root only -> capture CG-converged bound
    m.optimize()
    try:
        rlp = m.getDualbound(); rlp = None if rlp is None or abs(rlp) > 1e15 else rlp
    except Exception:
        rlp = None
    if accel.get("root_only"):                            # pilot: the bound is the measurement
        LAST_STATS.clear(); LAST_STATS.update(rounds=pr.data.get('rounds', 0), ncols=len(y))
        return m.getStatus(), None, m.getNNodes(), len(y), None, rlp
    m.setParam("limits/nodes", -1); m.optimize()          # resume to optimum (cumulative budget)
    LAST_STATS.clear(); LAST_STATS.update(rounds=pr.data.get('rounds', 0), ncols=len(y))
    if m.getNSols() == 0:
        return m.getStatus(), None, m.getNNodes(), len(y), None, rlp
    cfg = [frozenset(t for t in range(T) if m.getVal(a[(t, p)]) > 0.5) for p in range(n)]
    asg, seq = set(), []
    for p in range(n):
        for j in range(len(Tj)):
            if j not in asg and Tj[j] <= cfg[p]: asg.add(j); seq.append(j)
    seq = seq if len(seq) == len(Tj) else None
    return m.getStatus(), m.getObjVal(), m.getNNodes(), len(y), seq, rlp


if __name__ == "__main__":
    J, T, b, Tj = load_instance()
    Z = zstar(J, T, b, Tj)
    print(f"[{_VERSION}] 6-ring Z*={Z}")
    configs = {
        "baseline":   {},
        "heuristic":  {"heuristic_pricing": True},
        "multiple":   {"multiple_pricing": True, "kcols": 5},
        "warmstart":  {"warm_start": True},
        "stabilize":  {"stabilize": True, "stab_alpha": 0.5},
        "ALL":        {"heuristic_pricing": True, "multiple_pricing": True,
                       "warm_start": True, "stabilize": True, "kcols": 5, "stab_alpha": 0.5},
    }
    ok = True
    for name, acc in configs.items():
        st, ip, nodes, nc, seq, rlp = branch_and_price(J, T, b, Tj, accel=acc)
        good = ip is not None and abs(ip - Z) < 1e-6
        ok &= good
        print(f"  {name:<10} IP={ip}  [{st}] nodes={nodes} cols={nc} rootLP={rlp}  {'OK' if good else 'FAIL'}")
    print("ACCEL SELF-TEST PASS: every accelerator == Z*." if ok else "ACCEL SELF-TEST FAIL")
