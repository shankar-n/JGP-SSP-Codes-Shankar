#!/usr/bin/env python3
"""
verify_pcf_prime.py  --  numerical check of the PCF' results in
10b_position_branch_and_price.tex (Part X cont.).

Confirms, by full-enumeration MILP/LP (PuLP + CBC), on the 6-ring and random
small instances:
  * IP(PCF')  == Z*_SSP  (brute-force KTNS)          -> Prop. "PCF' is exact"
  * plain LP(PCF') (drop counting rows (T)) == 0     -> Prop. "LP invariance" (b)
  * LP(PCF') with (T)      == |U|-b                  -> Prop. "LP invariance" (c)
  * every metric matches the corresponding PCF value -> region containment

Requires: pip install pulp   (CBC ships with PuLP).
Run:      python3 verify_pcf_prime.py
"""
import os
from itertools import permutations, combinations
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
    Tj = [frozenset(t for t in range(T) if A[t][j]) for j in range(J)]
    return J, T, b, Tj


def rand_inst(seed):
    rng = random.Random(seed)
    J = rng.choice([4, 5, 6]); T = rng.choice([5, 6, 7]); b = rng.choice([2, 3])
    Tj = [frozenset(rng.sample(range(T), rng.randint(1, b))) for _ in range(J)]
    return J, T, b, Tj


# ---- brute-force KTNS ground truth (full magazines, free initial config) ----
def ktns_cost(seq, Tj, b, T):
    needed = [Tj[j] for j in seq]; n = len(needed)
    nxt = lambda t, s: next((k for k in range(s, n) if t in needed[k]), 10**9)
    M, ins = set(), 0
    for i in range(n):
        for t in needed[i]:
            if t not in M:
                if len(M) < b:
                    M.add(t)
                else:
                    cand = [x for x in M if x not in needed[i]]
                    M.discard(max(cand, key=lambda x: nxt(x, i))); M.add(t)
                ins += 1
        while len(M) < b:
            rem = [t for t in range(T) if t not in M]
            M.add(min(rem, key=lambda t: nxt(t, i + 1))); ins += 1
    return ins - b


def zstar(J, T, b, Tj):
    return min(ktns_cost(list(p), Tj, b, T) for p in permutations(range(J)))


def build(J, T, b, Tj, prime, withT, integer):
    cat = "Integer" if integer else "Continuous"
    V = [frozenset(c) for c in combinations(range(T), b)]
    Hj = [[i for i, C in enumerate(V) if Tj[j] <= C] for j in range(J)]
    U = sorted({t for s in Tj for t in s})
    m = pulp.LpProblem("pcf", pulp.LpMinimize)
    y = {(i, k): pulp.LpVariable(f"y_{i}_{k}", 0, 1, cat) for i in range(len(V)) for k in range(J)}
    w = {(t, k): pulp.LpVariable(f"w_{t}_{k}", 0, None, cat) for t in range(T) for k in range(1, J)}
    m += pulp.lpSum(w.values())
    a = lambda t, k: pulp.lpSum(y[(i, k)] for i, C in enumerate(V) if t in C)
    for k in range(J):
        if prime:
            m += pulp.lpSum(y[(i, k)] for i in range(len(V))) <= 1
        else:
            m += pulp.lpSum(y[(i, k)] for i in range(len(V))) == 1
    if prime:
        for k in range(J - 1):
            m += pulp.lpSum(y[(i, k + 1)] for i in range(len(V))) <= pulp.lpSum(y[(i, k)] for i in range(len(V)))
    for j in range(J):
        m += pulp.lpSum(y[(i, k)] for i in Hj[j] for k in range(J)) >= 1
    for t in range(T):
        for k in range(1, J):
            m += w[(t, k)] >= a(t, k) - a(t, k - 1)
    if withT:
        for t in U:
            m += pulp.lpSum(w[(t, k)] for k in range(1, J)) >= 1 - a(t, 0)
    m.solve(pulp.PULP_CBC_CMD(msg=0))
    return pulp.value(m.objective)


def main():
    insts = [("6-ring",) + parse_ring()] + [(f"rand{s}",) + rand_inst(s) for s in range(6)]
    print(f"{'inst':8} {'|U|-b':>5} {'Z*':>3} | "
          f"{'PCF plainLP':>11} {'LP+T':>5} {'IP':>4} | "
          f"{'PCFp plainLP':>12} {'LP+T':>5} {'IP':>4}  verdict")
    allok = True
    for name, J, T, b, Tj in insts:
        U = sorted({t for s in Tj for t in s}); ub = len(U) - b; Z = zstar(J, T, b, Tj)
        row = {}
        for pr in (False, True):
            row[(pr, 'plain')] = build(J, T, b, Tj, pr, False, False)
            row[(pr, 'lpt')]   = build(J, T, b, Tj, pr, True, False)
            row[(pr, 'ip')]    = build(J, T, b, Tj, pr, True, True)
        ok = (abs(row[(True, 'ip')] - Z) < 1e-6 and abs(row[(True, 'plain')]) < 1e-6
              and abs(row[(True, 'lpt')] - ub) < 1e-6
              and all(abs(row[(True, m)] - row[(False, m)]) < 1e-6 for m in ('plain', 'lpt', 'ip')))
        allok &= ok
        print(f"{name:8} {ub:>5} {Z:>3} | "
              f"{row[(False,'plain')]:>11.2f} {row[(False,'lpt')]:>5.2f} {row[(False,'ip')]:>4.1f} | "
              f"{row[(True,'plain')]:>12.2f} {row[(True,'lpt')]:>5.2f} {row[(True,'ip')]:>4.1f}  "
              f"{'PASS' if ok else 'FAIL'}")
    print("\nAll instances PASS." if allok else "\nSOME INSTANCES FAILED.")


if __name__ == "__main__":
    main()
