"""Tests for the new 'General-b ratio bounds' section of 05 (Claude-Fable, 2026-06-10).

PROVED claims (asserted):
  P1  every GSP transition costs <= min(b, |U|-b)  =>  H <= (K*-1)*min(b, |U|-b)
  P2  ratio H/Z* <= min(b, K*-1, |U|-b)            (for Z*>0)
  P3  K* <= 2  =>  gap = 0
CONJECTURE (violations reported, not asserted):
  C1  gap = H - Z* <= K* - 2          (generalises the K*=3,b=3 'gap<=1' conjecture)
Also checks the cost identity  cost = (|U|-b) + R  implicitly via P1/P2.
"""
import sys, random
sys.path.insert(0, "/sessions/peaceful-happy-lovelace/mnt/JGP-SSP-Codes-Shankar/plans-genai/_verification")
from ssp_verify import ring, ssp_opt, jgp_kstar, heuristic_H

def check(job_sets, b, tag, viol):
    U = set().union(*job_sets)
    m = len(U)
    if m <= b: return  # K*=1, trivial
    K, parts = jgp_kstar(job_sets, b)
    if K == 1: return
    Z = ssp_opt(job_sets, b, U)
    H = heuristic_H(job_sets, b, K, U, parts)[0]
    q = m - b
    assert H >= Z, (tag, "H<Z*!")
    assert H <= (K - 1) * min(b, q), (tag, "P1 violated", H, K, b, q)
    if Z > 0:
        assert H / Z <= min(b, K - 1, q) + 1e-9, (tag, "P2 violated", H, Z, K, b, q)
    if K <= 2:
        assert H == Z, (tag, "P3 violated: K*<=2 but gap>0", H, Z)
    if H - Z > K - 2:
        viol.append((tag, job_sets, b, dict(Z=Z, H=H, K=K, m=m, gap=H - Z)))

viol = []
# known witnesses
check(ring(6), 3, "6-ring", viol)
for k in range(3, 9): check(ring(k), 3, f"ring{k}", viol)
# random mixed-size instances
random.seed(7)
cnt = 0
for _ in range(900):
    b = random.choice([2, 3, 3, 4])
    nT = random.randint(b + 1, 7)
    n = random.randint(3, 5)
    T = list(range(1, nT + 1))
    js = [frozenset(random.sample(T, random.randint(1, min(b, nT)))) for _ in range(n)]
    if len(set().union(*js)) <= b: continue
    check(js, b, f"rnd-b{b}", viol); cnt += 1
# exhaustive-ish b=3 edge family on <=6 tools, <=6 edges (subsample of the 10691 family)
import itertools
edges6 = list(itertools.combinations(range(1, 7), 2))
random.seed(11)
ecnt = 0
for _ in range(600):
    me = random.randint(3, 6)
    js = [frozenset(e) for e in random.sample(edges6, me)]
    check(js, 3, "edge-b3", viol); ecnt += 1
print(f"checked: witnesses + {cnt} random + {ecnt} edge instances")
print(f"P1, P2, P3 (proved claims): all hold")
if viol:
    print(f"CONJECTURE gap<=K*-2: {len(viol)} VIOLATIONS:")
    for v in viol[:5]: print("  ", v)
else:
    print("CONJECTURE gap<=K*-2: no violation found")
