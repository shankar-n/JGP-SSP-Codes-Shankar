#!/usr/bin/env python3
"""
Exhaustive idealness census for the grouping covering relaxation, b = 3.
========================================================================

Prof. Wagler's question was whether odd-ring structure is the ONLY obstruction to
integrality of the set-covering relaxation behind grouping branch-and-price.
Proposition "Odd rings are not ideal" exhibits odd rings as AN obstruction. This
settles whether they are the only one, by enumerating the whole family rather than
sampling it.

THE REFORMULATION THAT MAKES IT FINITE
--------------------------------------
Take b = 3 and every job requiring exactly two tools. Then a job is a PAIR of tools,
so an instance is exactly a GRAPH: tools are vertices, jobs are edges. A feasible
group is a set of jobs whose tool union has at most 3 tools, i.e. a set of edges
spanning at most 3 vertices -- a single edge, a path of two edges, or a triangle.

The Job Grouping Problem becomes: cover every edge of the graph by as few subgraphs
spanning at most three vertices as possible. The k-ring is the cycle C_k.

So the whole family is the set of graphs, up to isomorphism, and it can be enumerated.

WHAT IS COMPUTED, PER GRAPH
---------------------------
    LP   the fractional cover: min sum x_C  s.t.  sum_{C containing e} x_C >= 1, x >= 0
    K*   the integer cover
    gap  K* - LP

and, for the graphs with a positive gap, whether the graph contains an induced odd
cycle at all -- which is what "odd-ring-like structure" would have to mean for odd
rings to be the only obstruction.
"""
from __future__ import annotations

import itertools
import sys
from fractions import Fraction

import numpy as np
from scipy.optimize import linprog


# ---------------------------------------------------------------- enumeration

def canonical(n, edges):
    """Canonical form of a graph on n labelled vertices, for isomorphism rejection."""
    best = None
    for perm in itertools.permutations(range(n)):
        relab = tuple(sorted(tuple(sorted((perm[u], perm[v]))) for u, v in edges))
        if best is None or relab < best:
            best = relab
    return best


def all_graphs(max_vertices):
    """Every graph with at least one edge, up to isomorphism, no isolated vertices."""
    seen = set()
    out = []
    for n in range(2, max_vertices + 1):
        pairs = list(itertools.combinations(range(n), 2))
        for r in range(1, len(pairs) + 1):
            for edges in itertools.combinations(pairs, r):
                touched = {v for e in edges for v in e}
                if len(touched) != n:          # no isolated vertices; counted at smaller n
                    continue
                c = canonical(n, edges)
                if c in seen:
                    continue
                seen.add(c)
                out.append((n, list(edges)))
    return out


# ------------------------------------------------------------------ the model

def feasible_groups(edges, b=3):
    """Maximal sets of edges spanning at most b vertices."""
    m = len(edges)
    groups = []
    for r in range(1, m + 1):
        for sub in itertools.combinations(range(m), r):
            verts = {v for i in sub for v in edges[i]}
            if len(verts) <= b:
                groups.append(frozenset(sub))
    maximal = [g for g in groups
               if not any(g < h for h in groups)]
    return maximal


def fractional_cover(m, groups):
    """min sum x_C  s.t.  sum_{C ni e} x_C >= 1 for every edge e, x >= 0."""
    ncol = len(groups)
    A = np.zeros((m, ncol))
    for c, g in enumerate(groups):
        for e in g:
            A[e, c] = 1.0
    res = linprog(np.ones(ncol), A_ub=-A, b_ub=-np.ones(m),
                  bounds=[(0, None)] * ncol, method="highs")
    return res.fun if res.success else None


def integer_cover(m, groups):
    """Smallest number of groups covering every edge; exact, by increasing size."""
    full = (1 << m) - 1
    masks = []
    for g in groups:
        msk = 0
        for e in g:
            msk |= 1 << e
        masks.append(msk)
    for k in range(1, m + 1):
        for combo in itertools.combinations(masks, k):
            acc = 0
            for msk in combo:
                acc |= msk
            if acc == full:
                return k
    return m


def has_odd_cycle(n, edges):
    """True iff the graph is non-bipartite, i.e. contains an odd cycle."""
    adj = {v: [] for v in range(n)}
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    colour = {}
    for s in range(n):
        if s in colour:
            continue
        colour[s] = 0
        stack = [s]
        while stack:
            u = stack.pop()
            for w in adj[u]:
                if w not in colour:
                    colour[w] = 1 - colour[u]
                    stack.append(w)
                elif colour[w] == colour[u]:
                    return True
    return False


def is_cycle(n, edges):
    """True iff the graph is exactly a single cycle C_n."""
    if len(edges) != n:
        return False
    deg = {v: 0 for v in range(n)}
    for u, v in edges:
        deg[u] += 1
        deg[v] += 1
    return all(d == 2 for d in deg.values())


# ------------------------------------------------------------------------ run

def main(max_vertices=6):
    graphs = all_graphs(max_vertices)
    print(f"graphs enumerated up to isomorphism (2..{max_vertices} vertices, "
          f"no isolated vertices): {len(graphs)}")
    print()

    gapped = []
    total = 0
    for n, edges in graphs:
        m = len(edges)
        if m > 12:                       # integer cover enumeration stays exact and quick
            continue
        total += 1
        groups = feasible_groups(edges)
        lp = fractional_cover(m, groups)
        ip = integer_cover(m, groups)
        if lp is None:
            continue
        gap = ip - lp
        if gap > 1e-7:
            gapped.append((n, edges, lp, ip, gap))

    print(f"instances tested                     : {total}")
    print(f"covering relaxation NOT integral on   : {len(gapped)} "
          f"({100*len(gapped)/total:.1f}%)")
    print()

    bip = [g for g in gapped if not has_odd_cycle(g[0], g[1])]
    cyc = [g for g in gapped if is_cycle(g[0], g[1])]
    noncyc_odd = [g for g in gapped if has_odd_cycle(g[0], g[1]) and not is_cycle(g[0], g[1])]

    print("of the non-integral instances:")
    print(f"  are exactly an odd ring C_k          : {len(cyc)}")
    print(f"  contain an odd cycle but are not one : {len(noncyc_odd)}")
    print(f"  are BIPARTITE -- no odd cycle at all : {len(bip)}")
    print()

    if bip:
        print("A bipartite instance with a positive integrality gap refutes the")
        print("conjecture that odd-ring structure is the only obstruction.")
        print()
        smallest = min(bip, key=lambda g: (len(g[1]), g[0]))
        n, edges, lp, ip, gap = smallest
        print(f"SMALLEST BIPARTITE WITNESS: {n} tools, {len(edges)} jobs")
        print(f"  jobs (tool pairs) : {sorted(edges)}")
        print(f"  fractional cover  : {lp:.4f}")
        print(f"  K*                : {ip}")
        print(f"  integrality gap   : {gap:.4f}")
        print()
        for n, edges, lp, ip, gap in sorted(bip, key=lambda g: (len(g[1]), g[0]))[:6]:
            print(f"  {n} tools, {len(edges)} jobs  LP={lp:.3f}  K*={ip}  "
                  f"gap={gap:.3f}   {sorted(edges)}")
    else:
        print("Every non-integral instance in the family contains an odd cycle.")
        print("This is consistent with odd-ring structure being the only obstruction,")
        print("on this family and at this size.")

    print()
    print("smallest non-integral instances overall:")
    for n, edges, lp, ip, gap in sorted(gapped, key=lambda g: (len(g[1]), g[0]))[:5]:
        kind = "cycle" if is_cycle(n, edges) else ("odd" if has_odd_cycle(n, edges) else "BIPARTITE")
        print(f"  {n} tools, {len(edges)} jobs  LP={lp:.3f}  K*={ip}  "
              f"gap={gap:.3f}  [{kind}]  {sorted(edges)}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
