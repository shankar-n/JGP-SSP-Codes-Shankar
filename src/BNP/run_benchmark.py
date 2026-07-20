#!/usr/bin/env python3
"""
P4 benchmark harness -- PCF' vs PTF exact branch-and-price (SCIP).

Compares the two B&P codes (pcf_prime_bp.py, ptf_bp.py) on rings / disjoint
rings / randoms, cross-checks their integer optima against each other and brute
KTNS, and brute-searches for GAP instances (Z* > |U|-b) where PTF's stronger
bound pays off in node count. See P4_benchmark_results.md for the writeup.

Scope: SCIP only. CPLEX BBC/SSPMF baselines + the Tabela1C campaign run on the
cluster (see src/BBC/cluster/SLURM_RUNBOOK.md); they are intentionally NOT invoked here.
Run:  python3 run_benchmark.py     Requires: pyscipopt.
"""
import os
import sys
import time
import random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pcf_prime_bp import branch_and_price as pcf_bp, zstar
from ptf_bp import branch_and_price as ptf_bp


def ring(m, b=3):
    return m, m, b, [frozenset({j, (j + 1) % m}) for j in range(m)]


def disjoint(m1, m2, b=3):
    Tj = ([frozenset({j, (j + 1) % m1}) for j in range(m1)]
          + [frozenset({m1 + j, m1 + (j + 1) % m2}) for j in range(m2)])
    return m1 + m2, m1 + m2, b, Tj


def rnd(s):
    r = random.Random(s); J = r.choice([5, 6]); T = r.choice([6, 7]); b = r.choice([2, 3])
    return J, T, b, [frozenset(r.sample(range(T), r.randint(1, b))) for _ in range(J)]


def compare(name, J, T, b, Tj):
    ub = len({t for s in Tj for t in s}) - b
    Z = zstar(J, T, b, Tj) if J <= 7 else None
    t0 = time.time(); _, ip1, nd1, *_ = pcf_bp(J, T, b, Tj); t1 = time.time()
    _, ip2, nd2, *_ = ptf_bp(J, T, b, Tj); t2 = time.time()
    ok = abs(ip1 - ip2) < 1e-6 and (Z is None or abs(ip1 - Z) < 1e-6)
    gap = "" if abs(ip1 - ub) < 1e-6 else f"  GAP+{round(ip1 - ub)}"
    zt = ("%g" % Z) if Z is not None else "?"
    print(f"{name:11}{ub:>5}{zt:>4} | PCF' {ip1:>4.0f}/{nd1:<4}{t1-t0:>5.1f}s | "
          f"PTF {ip2:>4.0f}/{nd2:<4}{t2-t1:>5.1f}s  {'agree' if ok else 'DIFFER!'}{gap}")


def find_gaps(ntry=2000, want=3):
    r = random.Random(7); found = []
    for _ in range(ntry):
        J = r.choice([5, 6]); T = 5; b = 3
        Tj = [frozenset(r.sample(range(T), r.randint(2, 3))) for _ in range(J)]
        if len({t for s in Tj for t in s}) < T:
            continue
        if zstar(J, T, b, Tj) > T - b:
            found.append((J, T, b, Tj))
        if len(found) >= want:
            break
    return found


if __name__ == "__main__":
    print(f"{'instance':11}{'U-b':>5}{'Z*':>4} |  PCF' IP/nodes/time      |  PTF IP/nodes/time")
    for nm, inst in ([("5-ring", ring(5)), ("6-ring", ring(6)), ("7-ring", ring(7)),
                      ("disj4+4", disjoint(4, 4))] + [(f"rand{s}", rnd(s)) for s in range(3)]):
        compare(nm, *inst)
    print("\n-- gap instances (Z* > |U|-b): PTF's stronger bound should cut nodes --")
    for i, inst in enumerate(find_gaps()):
        compare(f"gap[{i}]", *inst)
