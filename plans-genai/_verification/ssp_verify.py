#!/usr/bin/env python3
"""
ssp_verify.py -- Self-contained verification harness for the JGP+GSP / SSP gap study.

Conventions (match plans-genai/05):
  * Uniform SSP. Magazine capacity b. Job j needs tool set T_j (|T_j| <= b).
  * Switch cost of a sequence = number of tool INSERTIONS after a FREE initial fill
    of <= b tools (dummy-depot convention).
  * Z*_SSP        = min over job permutations of the exact tooling cost.
  * K*  (=Z*_JGP) = min number of CAPACITY-FEASIBLE groups partitioning the jobs
                    (group feasibility is |union T_j| <= b for the WHOLE group,
                     NOT merely pairwise -> this is the true JGP, not graph colouring).
  * H  (JGP+GSP)  = min over JGP-OPTIMAL groupings of the path-GTSP optimum
                    (best group order + best config per group).
  * gap = H - Z*_SSP ;  ratio = H / Z*_SSP (when Z*_SSP > 0).
Tool universe U = union of all T_j (padding with a tool no job needs is never
strictly beneficial, so this is WLOG for the minimum).
"""
import itertools

# ----------------------------------------------------------------- exact tooling cost
def tooling_cost(seq_sets, U, b):
    """EXACT min tool-switch cost for a FIXED job sequence, via DP over magazine
    states. No KTNS-policy assumption -- ground truth. Magazine kept full at
    size min(b,|U|); first magazine free; cost = sum |M_i minus M_{i-1}|."""
    n = len(seq_sets)
    if n == 0:
        return 0
    cap = min(b, len(U))
    Ul = sorted(U)
    def configs_for(req):
        free = cap - len(req)
        rest = [t for t in Ul if t not in req]
        return [frozenset(req | set(ex)) for ex in itertools.combinations(rest, free)]
    dp = {M: 0 for M in configs_for(set(seq_sets[0]))}
    for i in range(1, n):
        nxt = {}
        for M in configs_for(set(seq_sets[i])):
            best = None
            for Mp, c in dp.items():
                v = c + len(M - Mp)
                if best is None or v < best:
                    best = v
            nxt[M] = best
        dp = nxt
    return min(dp.values())

def ktns_cost(seq_sets, b):
    """Tang-Denardo keep-full KTNS (proactive initial fill, soonest-needed).
    Fast; validated against tooling_cost in the driver."""
    n = len(seq_sets)
    if n == 0:
        return 0
    U = set().union(*seq_sets)
    cap = min(b, len(U))
    INF = n + 1
    def next_need(t, i):
        for p in range(i, n):
            if t in seq_sets[p]:
                return p
        return INF
    mag = set(seq_sets[0])
    if len(mag) < cap:
        for t in sorted((set(U) - mag), key=lambda t: next_need(t, 1))[:cap - len(mag)]:
            mag.add(t)
    total = 0
    for i in range(1, n):
        req = set(seq_sets[i])
        missing = req - mag
        if missing:
            for t in sorted(mag - req, key=lambda t: -next_need(t, i))[:len(missing)]:
                mag.discard(t)
            mag |= missing
            total += len(missing)
    return total

def ssp_opt(job_sets, b, U=None, method="dp"):
    """Exact Z*_SSP over all permutations (reversal symmetry)."""
    n = len(job_sets)
    U = U if U is not None else set().union(*job_sets)
    cost = (lambda s: tooling_cost(s, U, b)) if method == "dp" else (lambda s: ktns_cost(s, b))
    best = None
    for perm in itertools.permutations(range(n)):
        if perm[0] > perm[-1]:
            continue
        c = cost([job_sets[i] for i in perm])
        if best is None or c < best:
            best = c
    return best

# ----------------------------------------------------------------- conflict graph (pairwise)
def conflict_graph(job_sets, b):
    n = len(job_sets)
    adj = [set() for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if len(job_sets[i] | job_sets[j]) > b:
                adj[i].add(j); adj[j].add(i)
    return adj

def chromatic_number(adj):
    """chi(G_conf): a LOWER bound on K* (every feasible grouping is a proper
    colouring, but not conversely -- a colour class may be capacity-infeasible)."""
    n = len(adj)
    if n == 0:
        return 0
    order = sorted(range(n), key=lambda v: -len(adj[v]))
    def colorable(k):
        color = [-1] * n
        def bt(idx):
            if idx == n:
                return True
            v = order[idx]
            used = {color[u] for u in adj[v] if color[u] != -1}
            for c in range(k):
                if c not in used:
                    color[v] = c
                    if bt(idx + 1):
                        return True
                    color[v] = -1
            return False
        return bt(0)
    k = 1
    while not colorable(k):
        k += 1
    return k

# ----------------------------------------------------------------- true JGP
def partitions_into_k(job_sets, b, k):
    """All partitions into EXACTLY k nonempty capacity-feasible groups."""
    n = len(job_sets)
    results = set()
    assign = [-1] * n
    unions = [frozenset() for _ in range(k)]
    def bt(v, used):
        if v == n:
            if used == k:
                classes = [[] for _ in range(k)]
                for i in range(n):
                    classes[assign[i]].append(i)
                results.add(frozenset(frozenset(c) for c in classes))
            return
        if used + (n - v) < k:
            return
        for g in range(min(used + 1, k)):
            nu = unions[g] | job_sets[v]
            if len(nu) <= b:
                old = unions[g]; unions[g] = nu; assign[v] = g
                bt(v + 1, used + (1 if g == used else 0))
                unions[g] = old; assign[v] = -1
    bt(0, 0)
    return results

def jgp_kstar(job_sets, b):
    """True JGP optimum and all optimal partitions. Returns (Kstar, set_of_parts)."""
    n = len(job_sets)
    if n == 0:
        return 0, set()
    for k in range(1, n + 1):
        parts = partitions_into_k(job_sets, b, k)
        if parts:
            return k, parts
    return n, partitions_into_k(job_sets, b, n)

# ----------------------------------------------------------------- GTSP / heuristic H
def group_clusters(group, U, b):
    req = set()
    for s in group:
        req |= s
    free = b - len(req)
    rest = sorted(U - req)
    return [frozenset(req | set(extra)) for extra in itertools.combinations(rest, free)]

def gtsp_opt_for_partition(part, job_sets, U, b):
    """Path-GTSP optimum for one grouping: best order + best config per group."""
    groups = [tuple(job_sets[i] for i in cls) for cls in part]
    K = len(groups)
    if K == 1:
        return 0
    clusters = [group_clusters(g, U, b) for g in groups]
    best = None
    for perm in itertools.permutations(range(K)):
        if perm[0] > perm[-1]:
            continue
        prev = {C: 0 for C in clusters[perm[0]]}
        for idx in range(1, K):
            cur = {}
            for C in clusters[perm[idx]]:
                bc = None
                for Cp, cost in prev.items():
                    v = cost + (b - len(C & Cp))
                    if bc is None or v < bc:
                        bc = v
                cur[C] = bc
            prev = cur
        c = min(prev.values())
        if best is None or c < best:
            best = c
    return best

def heuristic_H(job_sets, b, Kstar=None, U=None, parts=None):
    """JGP+GSP cost: min over ALL JGP-optimal partitions of the path-GTSP optimum."""
    n = len(job_sets)
    U = U if U is not None else (set().union(*job_sets) if n else set())
    if Kstar is None or parts is None:
        Kstar, parts = jgp_kstar(job_sets, b)
    best = None; best_part = None
    for part in parts:
        c = gtsp_opt_for_partition(part, job_sets, U, b)
        if best is None or c < best:
            best = c; best_part = part
    return best, Kstar, len(parts), best_part

# ----------------------------------------------------------------- analyse + helpers
def analyse(job_sets, b, name=""):
    job_sets = [frozenset(s) for s in job_sets]
    U = set().union(*job_sets) if job_sets else set()
    Z = ssp_opt(job_sets, b, U)
    Kstar, parts = jgp_kstar(job_sets, b)
    H, _, nparts, _ = heuristic_H(job_sets, b, Kstar, U, parts)
    chi = chromatic_number(conflict_graph(job_sets, b))
    gap = H - Z
    ratio = (H / Z) if Z and Z > 0 else float('nan')
    return dict(name=name, b=b, n=len(job_sets), nT=len(U), Z=Z, H=H, Kstar=Kstar,
                chi_conf=chi, gap=gap, ratio=ratio, lb_tools=len(U) - b, lb_k=Kstar - 1,
                nparts=nparts)

def ring(k):
    return [frozenset({i, (i % k) + 1}) for i in range(1, k + 1)]

def components(job_sets):
    n = len(job_sets)
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for i in range(n):
        for j in range(i + 1, n):
            if job_sets[i] & job_sets[j]:
                parent[find(i)] = find(j)
    comp = {}
    for i in range(n):
        comp.setdefault(find(i), []).append(i)
    return list(comp.values())
