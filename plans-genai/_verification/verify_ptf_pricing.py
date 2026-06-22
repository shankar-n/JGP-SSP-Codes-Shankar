#!/usr/bin/env python3
"""
verify_ptf_pricing.py -- (1) validate the PTF compact model and (2) check the
PTF pricing reduced cost (eq. rc-ptf in 10b_position_branch_and_price.tex).

Step 1 (model): build the full-arc PTF MILP (diagonal-free arcs among real
configs, + absorbing bottom node), solve IP, and assert IP == Z*_SSP
(brute-force KTNS).  A wrong model would make step 2 vacuous, so it is gated.

Step 2 (pricing): solve the PTF LP, read duals sigma,delta,pi,lambda, and for
every NON-bottom arc compare the printed formula eq:rc-ptf against the
ground-truth reduced cost (definitional from model coeffs, cross-checked with
CBC's var.dj).  RC_form == RC_def is a convention-free identity, so any mismatch
is a real derivation error.  Optimality (RC>=0, ==0 on basic arcs) sanity-checks
the duals; bottom-arcs are included in that check.

Result (2026-06-22): model exact on 5 instances; printed signs already correct
(max |formula - ground truth| = 0).  Requires: pip install pulp.
"""
import os
from itertools import combinations, permutations
import random
import pulp

HERE = os.path.dirname(os.path.abspath(__file__))
_CAND = [os.path.join(HERE, "..", "..", "data", "Shankar", "shankar-example.txt"),
         os.path.join(HERE, "..", "data", "Shankar", "shankar-example.txt")]
BOT = frozenset()                      # the unique tool-less node
real = lambda x: len(x) > 0


def parse_ring():
    p = next((q for q in _CAND if os.path.exists(q)), _CAND[0])
    L = [l for l in open(p).read().split("\n") if l.strip()]
    J, T, b = map(int, L[0].split())
    A = [list(map(int, L[1 + t].split())) for t in range(T)]
    return J, T, b, [frozenset(t for t in range(T) if A[t][j]) for j in range(J)]


def rand_inst(seed):
    rng = random.Random(seed)
    J = rng.choice([4, 4]); T = rng.choice([5, 5]); b = rng.choice([2, 2])
    return J, T, b, [frozenset(rng.sample(range(T), rng.randint(1, b))) for _ in range(J)]


def ktns(seq, Tj, b, T):
    nd = [Tj[j] for j in seq]; n = len(nd)
    nxt = lambda t, s: next((k for k in range(s, n) if t in nd[k]), 10**9)
    M, ins = set(), 0
    for i in range(n):
        for t in nd[i]:
            if t not in M:
                if len(M) < b:
                    M.add(t)
                else:
                    cand = [x for x in M if x not in nd[i]]
                    M.discard(max(cand, key=lambda x: nxt(x, i))); M.add(t)
                ins += 1
        while len(M) < b:
            rem = [t for t in range(T) if t not in M]
            M.add(min(rem, key=lambda t: nxt(t, i + 1))); ins += 1
    return ins - b


def zstar(J, T, b, Tj):
    return min(ktns(list(p), Tj, b, T) for p in permutations(range(J)))


def build(J, T, b, Tj, integer):
    cat = "Binary" if integer else "Continuous"
    reals = [frozenset(c) for c in combinations(range(T), b)]
    arcs = [(C, D) for C in reals for D in reals if C != D] + [(C, BOT) for C in reals] + [(BOT, BOT)]
    n = J; steps = range(n - 1)
    cost = lambda a: 0 if not real(a[1]) else len(a[1] - a[0])
    m = pulp.LpProblem("ptf", pulp.LpMinimize)
    z = {(ai, p): pulp.LpVariable(f"z_{ai}_{p}", 0, 1, cat) for ai in range(len(arcs)) for p in steps}
    m += pulp.lpSum(cost(arcs[ai]) * z[(ai, p)] for ai in range(len(arcs)) for p in steps)
    insx = lambda t, p: pulp.lpSum(z[(ai, p)] for ai, a in enumerate(arcs) if (t in a[1] and t not in a[0]))
    hd = lambda t, p: pulp.lpSum(z[(ai, p)] for ai, a in enumerate(arcs) if t in a[1])
    tl = lambda t, p: pulp.lpSum(z[(ai, p)] for ai, a in enumerate(arcs) if t in a[0])
    botbot = [i for i, a in enumerate(arcs) if a == (BOT, BOT)][0]
    U = sorted({t for s in Tj for t in s})
    for p in steps:
        m += (pulp.lpSum(z[(ai, p)] for ai in range(len(arcs))) == 1, f"Pz_{p}")
    for t in range(T):
        for p in range(n - 2):
            m += (hd(t, p) - tl(t, p + 1) == 0, f"cons_{t}_{p}")
    for p in range(n - 2):
        m += (pulp.lpSum(z[(ai, p)] for ai, a in enumerate(arcs) if real(a[0]) and not real(a[1]))
              - z[(botbot, p + 1)] <= 0, f"abs_{p}")
    for j in range(J):
        m += (pulp.lpSum(z[(ai, 0)] for ai, a in enumerate(arcs) if real(a[0]) and Tj[j] <= a[0])
              + pulp.lpSum(z[(ai, p)] for ai, a in enumerate(arcs) if real(a[1]) and Tj[j] <= a[1] for p in steps)
              >= 1, f"Cz_{j}")
    for t in U:
        m += (pulp.lpSum(insx(t, p) for p in steps) + tl(t, 0) >= 1, f"Tz_{t}")
    return m, z, arcs, U, n


def check(J, T, b, Tj, tol=1e-6):
    # ---- step 1: model exactness ----
    mi, zi, arcs, U, n = build(J, T, b, Tj, True)
    mi.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=25))
    ip = pulp.value(mi.objective); Z = zstar(J, T, b, Tj)
    model_ok = abs(ip - Z) < 1e-6
    # ---- step 2: pricing reduced cost ----
    m, z, arcs, U, n = build(J, T, b, Tj, False)
    m.solve(pulp.PULP_CBC_CMD(msg=0)); con = m.constraints; pi = lambda nm: con[nm].pi
    sig = [pi(f"Pz_{p}") for p in range(n - 1)]
    dl = {(t, p): pi(f"cons_{t}_{p}") for t in range(T) for p in range(n - 2)}
    pj = {j: pi(f"Cz_{j}") for j in range(J)}
    lam = {t: pi(f"Tz_{t}") for t in U}
    cost = lambda a: 0 if not real(a[1]) else len(a[1] - a[0])

    def RC_def(ai, p):
        v = z[(ai, p)]
        return cost(arcs[ai]) - sum(c.pi * c.get(v, 0) for c in con.values() if c.get(v, 0))

    def RC_form(C, D, p):                    # eq:rc-ptf as printed, 0-indexed
        s = sum((1 - lam.get(t, 0.0)) for t in (D - C))
        s -= sig[p]
        if p <= n - 3: s -= sum(dl[(t, p)] for t in D)
        if 1 <= p <= n - 2: s += sum(dl[(t, p - 1)] for t in C)
        s -= sum(pj[j] for j in range(J) if Tj[j] <= D)
        if p == 0: s -= sum(pj[j] for j in range(J) if Tj[j] <= C)
        if p == 0: s -= sum(lam.get(t, 0.0) for t in C)
        return s

    mform = mdj = 0.0; minrc = 1e9; basic = 0.0
    for ai, (C, D) in enumerate(arcs):
        for p in range(n - 1):
            rdef = RC_def(ai, p)
            dj = getattr(z[(ai, p)], "dj", None)
            if dj is not None: mdj = max(mdj, abs(dj - rdef))
            minrc = min(minrc, rdef); val = z[(ai, p)].value()
            if val and val > tol: basic = max(basic, abs(rdef))
            if real(C) and real(D):
                mform = max(mform, abs(RC_form(C, D, p) - rdef))
    return dict(Z=Z, ip=ip, model_ok=model_ok, lp=pulp.value(m.objective),
                nA=len(arcs), mform=mform, mdj=mdj, minrc=minrc, basic=basic)


def main():
    insts = [("6-ring",) + parse_ring()] + [(f"rand{s}",) + rand_inst(s) for s in range(4)]
    print(f"{'inst':7} {'arcs':>5} {'Z*':>3} {'IP':>5} {'LP':>5} | "
          f"{'|dj-def|':>9} {'|form-def|':>10} {'minRC':>7} {'basicRC':>8}  verdict")
    allok = True
    for name, J, T, b, Tj in insts:
        r = check(J, T, b, Tj)
        ok = r['model_ok'] and r['mform'] < 1e-6 and r['minrc'] > -1e-6 and r['basic'] < 1e-6
        allok &= ok
        print(f"{name:7} {r['nA']:>5} {r['Z']:>3} {r['ip']:>5.2f} {r['lp']:>5.2f} | "
              f"{r['mdj']:>9.1e} {r['mform']:>10.1e} {r['minrc']:>7.3f} {r['basic']:>8.1e}  "
              f"{'PASS' if ok else 'FAIL'}")
    print("\nPTF model exact and printed reduced cost matches ground truth on all instances."
          if allok else "\nFAILURE.")


if __name__ == "__main__":
    main()
