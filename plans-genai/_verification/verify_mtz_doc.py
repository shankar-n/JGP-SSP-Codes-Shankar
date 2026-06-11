"""Verification of claims in plans-genai/04_mtz_formulation.tex (Claude-Fable, 2026-06-10).

Check 1: b=3 counterexample (thm:notexact): Z*_SSP=1, min covering-path cost=1,
         min cluster-MTZ-representable covering path cost=2.
Check 2: core of per-config MTZ exactness: min covering-config-walk cost == ssp_opt
         (exact state DP from ssp_verify.py) on random small instances.
Check 3: aggregate Desrochers-Laporte lifting (rem:dl) is INVALID: it cuts off a
         representable solution on a 3-job instance.
Check 4: parasitic-cycle soundness hole: on the thm:notexact instance, the ILP as
         written admits a cost-2 solution whose s-t path serves only jobs {1,3,4},
         with job 2 'covered' by a disconnected 2-cycle through the uncovered
         config {2,3,4}.  (Constraint-by-constraint check, no solver.)
"""
import sys, itertools, heapq, random
sys.path.insert(0, "/sessions/peaceful-happy-lovelace/mnt/JGP-SSP-Codes-Shankar/plans-genai/_verification")
from ssp_verify import ssp_opt

def configs(U, b):
    return [frozenset(c) for c in itertools.combinations(sorted(U), b)]

def cover(c, job_sets):
    return frozenset(j for j, T in enumerate(job_sets) if T <= c)

def d(a, b_):
    return len(a - b_)

def min_cover_walk(job_sets, b, U):
    """Min cost covering config walk, free initial config (dummy depot). Dijkstra over (jobmask,last)."""
    V = configs(U, b)
    full = (1 << len(job_sets)) - 1
    def m(c):
        x = 0
        for j, T in enumerate(job_sets):
            if T <= c: x |= 1 << j
        return x
    pq = [(0, m(c), i) for i, c in enumerate(V)]
    heapq.heapify(pq)
    best = {}
    while pq:
        cost, mask, i = heapq.heappop(pq)
        if mask == full: return cost
        if best.get((mask, i), 1 << 30) <= cost: continue
        best[(mask, i)] = cost
        for k, c2 in enumerate(V):
            if k == i: continue
            nc = cost + d(V[i], c2)
            nm = mask | m(c2)
            if best.get((nm, k), 1 << 30) > nc:
                heapq.heappush(pq, (nc, nm, k))
    return None

def clusters_of(c, job_sets):
    return [j for j, T in enumerate(job_sets) if T <= c]

def representable(path, job_sets):
    """Cluster-simple + acyclic precedence digraph D (prop:representable)."""
    n = len(job_sets)
    a = {}
    for c1, c2 in zip(path, path[1:]):
        for j1 in clusters_of(c1, job_sets):
            for j2 in clusters_of(c2, job_sets):
                if j1 != j2:
                    a[(j1, j2)] = a.get((j1, j2), 0) + 1
    if any(v > 1 for v in a.values()): return False
    # acyclicity of D
    adj = {j: [] for j in range(n)}
    indeg = {j: 0 for j in range(n)}
    for (j1, j2) in a: adj[j1].append(j2); indeg[j2] += 1
    q = [j for j in range(n) if indeg[j] == 0]; seen = 0
    while q:
        u = q.pop(); seen += 1
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    return seen == n

def min_representable_path(job_sets, b, U, maxlen=5):
    V = configs(U, b)
    best = None
    for L in range(1, maxlen + 1):
        for path in itertools.permutations(V, L):
            if not all(T <= set().union(*[set(c) for c in path]) for T in job_sets):
                pass  # cheap pre-filter below instead
            covered = set()
            for c in path: covered.update(clusters_of(c, job_sets))
            if len(covered) != len(job_sets): continue
            if not representable(list(path), job_sets): continue
            cost = sum(d(a_, b_) for a_, b_ in zip(path, path[1:]))
            if best is None or cost < best: best = cost
        if best is not None: return best
    return best

# ---------- Check 1 ----------
js = [frozenset({1, 4}), frozenset({1, 3, 4}), frozenset({1}), frozenset({1, 2, 4})]
U = {1, 2, 3, 4}
z = ssp_opt(js, 3, U)
w = min_cover_walk(js, 3, U)
r = min_representable_path(js, 3, U)
print(f"CHECK1: ssp_opt={z} (expect 1), min_cover_walk={w} (expect 1), min_representable={r} (expect 2)")
assert (z, w, r) == (1, 1, 2)

# ---------- Check 2 ----------
random.seed(42)
bad = 0; trials = 0
for _ in range(400):
    nT = random.randint(4, 6); b = random.choice([2, 3]); n = random.randint(3, 5)
    T = list(range(1, nT + 1))
    job_sets = [frozenset(random.sample(T, random.randint(1, b))) for _ in range(n)]
    Uu = set().union(*job_sets)
    if len(Uu) < b: continue
    trials += 1
    z = ssp_opt(job_sets, b, set(T))
    w = min_cover_walk(job_sets, b, set(T))
    if z != w:
        bad += 1
        print("MISMATCH:", job_sets, b, "ssp_opt", z, "walk", w)
print(f"CHECK2: {trials} instances, {bad} mismatches between ssp_opt and min covering walk")
assert bad == 0

# ---------- Check 3 ----------
# jobs T1={1},T2={2},T3={3}, b=2, path P1={1,4} -> P2={1,2} -> P3={3,5}, n=3
js3 = [frozenset({1}), frozenset({2}), frozenset({3})]
path = [frozenset({1, 4}), frozenset({1, 2}), frozenset({3, 5})]
assert representable(path, js3), "path should be representable under original cluster-MTZ"
# pair sums: S(1->2)=1 (P1->P2), S(2->3)=1 (P2->P3), S(1->3)=1 (P2->P3 since P2 in H1)
# original MTZ: u1<=u2-1, u2<=u3-1, u1<=u3-1  -> feasible (u=1,2,3)
# aggregate DL adds for pair (3,1): u3-u1+n*S(3->1)+(n-2)*S(1->3) <= n-1, n=3:
#   u3-u1+0+1 <= 2  -> u3-u1 <= 1, contradicting u3>=u1+2.  INFEASIBLE.
print("CHECK3: representable path exists; aggregate-DL forces u3-u1<=1 while MTZ forces u3-u1>=2 -> aggregate DL lifting INVALID (cuts off a representable solution)")

# ---------- Check 4 ----------
# Instance of Check 1. Candidate ILP solution: path s->{1,2,4}->t (cost 0) plus
# 2-cycle {2,3,4}<->{1,3,4} (cost 2). Verify all written constraints by hand:
V = configs(U, 3)
arcs = [("s", frozenset({1, 2, 4})), (frozenset({1, 2, 4}), "t"),
        (frozenset({2, 3, 4}), frozenset({1, 3, 4})), (frozenset({1, 3, 4}), frozenset({2, 3, 4}))]
# degree/flow: each V-node out<=1,in<=1, out==in for V nodes:
from collections import Counter
outc = Counter(a for a, b_ in arcs if a != "s"); inc = Counter(b_ for a, b_ in arcs if b_ != "t")
assert all(v <= 1 for v in outc.values()) and all(v <= 1 for v in inc.values())
for v in V: assert outc.get(v, 0) == inc.get(v, 0)
# coverage with V^+ sums: entry/exit per job
for j, T in enumerate(js):
    H = [c for c in V if T <= c]
    entry = any((a == "s" or (a not in ("s", "t") and not T <= a)) and (b_ not in ("s", "t") and T <= b_) for a, b_ in arcs)
    exit_ = any((a not in ("s", "t") and T <= a) and (b_ == "t" or (b_ not in ("s", "t") and not T <= b_)) for a, b_ in arcs)
    assert entry and exit_, f"coverage fails for job {j+1}"
# MTZ pairs: only arcs within V matter; {2,3,4} covers no job -> contributes no pairs
a = {}
for c1, c2 in arcs:
    if c1 in ("s",) or c2 in ("t",): continue
    for j1 in clusters_of(c1, js):
        for j2 in clusters_of(c2, js):
            if j1 != j2: a[(j1, j2)] = a.get((j1, j2), 0) + 1
assert not a, f"unexpected MTZ pairs {a}"
cost = d(frozenset({2, 3, 4}), frozenset({1, 3, 4})) + d(frozenset({1, 3, 4}), frozenset({2, 3, 4}))
print(f"CHECK4: parasitic solution feasible for ILP-as-written, cost={cost}; its s-t path serves only jobs 1,3,4 -- job 2 is 'covered' by a disconnected cycle. SOUNDNESS HOLE CONFIRMED.")
print("ALL CHECKS PASSED")
