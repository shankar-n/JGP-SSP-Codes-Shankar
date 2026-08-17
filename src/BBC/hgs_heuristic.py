"""
Hybrid Genetic Search (HGS) primal heuristic for the SSP.
=========================================================

A compact implementation in the spirit of Mecler, Subramanian & Vidal (2021),
"A simple and effective hybrid genetic search for the job sequencing and tool
switching problem" (Computers & Operations Research; arXiv:1910.10021), the
current state of the art for the single-machine SSP.

Components:
  * solution = permutation of jobs; fitness = empty-start KTNS switch cost.
  * initial population = several constructive seeds (nearest-neighbour on the
    pairwise weights w_ij, largest-tool-first) + random, each *educated*.
  * crossover = Order Crossover (OX).
  * education = Variable Neighbourhood Descent local search: adjacent swaps,
    Or-opt (relocate segments of length 1..3), until no improvement.
  * diversity management = biased-fitness survivor selection removing clones.

Used by the BBC solver (use_primal_heuristic) to (a) supply a CPLEX MIP start
and (b) seed a Benders optimality cut at the root.  Time-boxed so it is cheap
relative to the exact solve.

Self-contained (KTNS included) so it is testable without the rest of the repo;
the BBC wiring passes the repo's compute_ktns to guarantee the same convention.
"""
import random
import time


# ---------------------------------------------------------------------------
# KTNS (empty-start) — matches src/SSP/utils.compute_ktns; used as fallback.
# ---------------------------------------------------------------------------
def ktns_cost(seq, T, b):
    """Empty-start total tool insertions for a fixed sequence.
    T is a list of tool sets indexed by job."""
    n = len(seq)
    mag = set()
    cost = 0

    def next_use(t, p):
        for k in range(p + 1, n):
            if t in T[seq[k]]:
                return k
        return 10 ** 9

    for p in range(n):
        need = T[seq[p]]
        cost += len(need - mag)
        mag |= need
        while len(mag) > b:
            cand = [x for x in mag if x not in need]
            mag.discard(max(cand, key=lambda x: next_use(x, p)))
    return cost


def _pairwise_weights(T, n, b):
    w = {}
    for i in range(n):
        for j in range(n):
            if i != j:
                w[(i, j)] = max(0, len(T[i] | T[j]) - b)
    return w


# ---------------------------------------------------------------------------
# Constructions
# ---------------------------------------------------------------------------
def _nearest_neighbour(T, n, b, start, w):
    seq = [start]
    used = {start}
    while len(seq) < n:
        last = seq[-1]
        nxt = min((j for j in range(n) if j not in used),
                  key=lambda j: (w[(last, j)], len(T[last] ^ T[j])))
        seq.append(nxt)
        used.add(nxt)
    return seq


def _largest_tool_first(T, n):
    return sorted(range(n), key=lambda j: len(T[j]), reverse=True)


# ---------------------------------------------------------------------------
# Education: Variable Neighbourhood Descent
# ---------------------------------------------------------------------------
def _vnd(seq, T, b, cost_fn, max_pass=8):
    seq = list(seq)
    best = cost_fn(seq)
    improved = True
    n = len(seq)
    passes = 0
    while improved and passes < max_pass:
        improved = False
        passes += 1
        # neighbourhood 1: adjacent swaps
        for i in range(n - 1):
            seq[i], seq[i + 1] = seq[i + 1], seq[i]
            c = cost_fn(seq)
            if c < best - 1e-9:
                best = c
                improved = True
            else:
                seq[i], seq[i + 1] = seq[i + 1], seq[i]
        # neighbourhood 2: Or-opt (relocate a segment of length L).
        # O(n^3) per pass; gated to the sizes BBC actually solves (n<=25) so
        # large-n seeding stays within its time box (adjacent swaps still run).
        for L in (1, 2, 3) if n <= 25 else ():
            i = 0
            while i + L <= n:
                seg = seq[i:i + L]
                rest = seq[:i] + seq[i + L:]
                placed = False
                for k in range(len(rest) + 1):
                    if k == i:
                        continue
                    cand = rest[:k] + seg + rest[k:]
                    c = cost_fn(cand)
                    if c < best - 1e-9:
                        seq = cand
                        best = c
                        improved = True
                        placed = True
                        break
                if not placed:
                    i += 1
    return seq, best


# ---------------------------------------------------------------------------
# Order Crossover (OX)
# ---------------------------------------------------------------------------
def _ox(p1, p2, rng):
    n = len(p1)
    a, c = sorted(rng.sample(range(n), 2))
    child = [None] * n
    child[a:c + 1] = p1[a:c + 1]
    taken = set(child[a:c + 1])
    fill = [x for x in p2 if x not in taken]
    idx = 0
    for k in range(n):
        if child[k] is None:
            child[k] = fill[idx]
            idx += 1
    return child


# ---------------------------------------------------------------------------
# Main HGS
# ---------------------------------------------------------------------------
def hgs(tool_req, n, b, cost_fn=None, time_limit=2.0, pop=12,
        max_iter=4000, seed=0):
    """Run HGS. Returns (best_sequence, best_cost).

    cost_fn(seq) -> switch cost; if None uses the built-in empty-start KTNS
    (the BBC wiring passes compute_ktns to lock the convention)."""
    rng = random.Random(seed)
    T = [set(tool_req.get(j, ())) for j in range(n)]
    if cost_fn is None:
        cost_fn = lambda s: ktns_cost(s, T, b)
    if n <= 1:
        return list(range(n)), cost_fn(list(range(n)))
    w = _pairwise_weights(T, n, b)

    # ---- initial population (constructions + random), all educated ----
    seeds = []
    for s in range(min(n, max(3, pop // 2))):
        seeds.append(_nearest_neighbour(T, n, b, s, w))
    seeds.append(_largest_tool_first(T, n))
    while len(seeds) < pop:
        r = list(range(n))
        rng.shuffle(r)
        seeds.append(r)

    t0 = time.perf_counter()
    population = []
    for k, s in enumerate(seeds):
        # Educate seeds, but stop spending on education past half the budget
        # (large n): keep the rest as cheap constructions so we never blow the
        # time box before the evolutionary loop even starts.
        if k >= 2 and (time.perf_counter() - t0) > 0.5 * time_limit:
            population.append((cost_fn(s), list(s)))
        else:
            seq, c = _vnd(s, T, b, cost_fn)
            population.append((c, seq))
    population.sort(key=lambda t: t[0])
    best_c, best_seq = population[0]

    # ---- evolutionary loop ----
    it = 0
    while it < max_iter and (time.perf_counter() - t0) < time_limit:
        it += 1
        # binary-tournament parents
        p1 = min(rng.sample(population, 2), key=lambda t: t[0])[1]
        p2 = min(rng.sample(population, 2), key=lambda t: t[0])[1]
        child = _ox(p1, p2, rng)
        child, c = _vnd(child, T, b, cost_fn)
        # insert if not a clone
        if all(child != s for _, s in population):
            population.append((c, child))
            population.sort(key=lambda t: t[0])
            # survivor selection: keep the pop best, drop worst
            population[:] = population[:pop]
            if c < best_c - 1e-9:
                best_c, best_seq = c, list(child)
    return best_seq, best_c
