#!/usr/bin/env python3
"""
Bound-strength probe: how much of the gap Z* - q can each inequality family close?
==================================================================================

The report's diagnosis is that every inequality in both exact methods is supported on
a LOCAL object -- an arc (i,j) in the Benders master, a single position in PCF'.  The
cost, however, is  Z = sum over tools of (number of magazine blocks of that tool), and
a re-insertion is caused by the GLOBAL interleaving of the sequence.

This probe measures the ceiling of two candidate families on real instances, WITHOUT a
commercial solver, by enumerating every sequence of an 8-job instance:

  q       = |U|                      the coverage bound (empty-start).  What the
                                     Benders master's root LP actually returns on 87%
                                     of runs, and exactly what the PCF' relaxation
                                     returns on 100% of runs.

  L_pair  = min over sequences of    the pairwise family solved to optimality, as a
            [ |T_first| + sum w ]    Hamiltonian path over Tang & Denardo's weights.
                                     This is the best any arc-supported family can do.

  L_win   = min over sequences of    the WINDOW family.  For a contiguous block of
            [ best window bound ]    positions W, the magazine before W holds at most b
                                     tools, so at least |U_W| - b insertions happen
                                     inside W (and |U_W| for a window starting at
                                     position 1, where the magazine is empty).
                                     Disjoint windows count disjoint insertions, so the
                                     contributions add.  Per sequence the best window
                                     decomposition is an O(n^2) dynamic program.

  Z*      = the proved optimum, taken from the finished campaign.

Both L_pair and L_win are valid lower bounds on Z*: each is a minimum over sequences of
a quantity that never exceeds that sequence's cost.  L_win >= q always, because the
single window [1, n] gives exactly |U|.

The number that decides whether the family is worth implementing is

    closed  =  (L - q) / (Z* - q)

on the instances where the coverage bound is loose.  A family that closes little of the
gap here cannot close it inside a solver either, and is not worth cluster time.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from itertools import permutations

DATA = "/mnt/user-data/uploads/JGP-SSP-Codes-Shankar/data/From_Felipe/data/Laporte/Tabela3"


def read_instance(path):
    """Returns (n_jobs, n_tools, capacity, [tool bitmask per job])."""
    tok = open(path).read().split()
    n, m, b = int(tok[0]), int(tok[1]), int(tok[2])
    grid = [int(x) for x in tok[3: 3 + m * n]]
    masks = [0] * n
    for t in range(m):
        for j in range(n):
            if grid[t * n + j]:
                masks[j] |= 1 << t
    return n, m, b, masks


def pairwise_weights(masks, b):
    """w[i][j] = max(0, |T_i U T_j| - b), the Tang-Denardo adjacency weight."""
    n = len(masks)
    return [[max(0, (masks[i] | masks[j]).bit_count() - b) for j in range(n)]
            for i in range(n)]


def probe(n, b, masks, w):
    """Enumerate every sequence once; return (L_pair, L_win)."""
    rng = range(n)
    best_pair = None
    best_win = None
    popc = int.bit_count

    for perm in permutations(rng):
        pm = [masks[j] for j in perm]

        # ---- pairwise Hamiltonian-path bound -----------------------------
        val = popc(pm[0])
        for k in range(n - 1):
            val += w[perm[k]][perm[k + 1]]
        if best_pair is None or val < best_pair:
            best_pair = val

        # ---- window bound: best decomposition into consecutive windows ----
        # c[p][k] = contribution of the window covering positions p..k
        #           = |U| for p == 0 (empty magazine), else max(0, |U| - b)
        # g[k] = best total over positions 0..k-1
        g = [0] * (n + 1)
        for k in range(1, n + 1):
            best = g[k - 1]                     # leave position k-1 out of any window
            u = 0
            for p in range(k - 1, -1, -1):
                u |= pm[p]
                size = popc(u)
                contrib = size if p == 0 else (size - b if size > b else 0)
                cand = g[p] + contrib
                if cand > best:
                    best = cand
            g[k] = best
        if best_win is None or g[n] < best_win:
            best_win = g[n]

    return best_pair, best_win


def main():
    optima = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else {}
    rows = []
    for path in sorted(glob.glob(os.path.join(DATA, "*.txt"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        n, m, b, masks = read_instance(path)
        if n > 9:
            continue
        used = 0
        for msk in masks:
            used |= msk
        q = used.bit_count()                    # coverage bound, empty-start
        w = pairwise_weights(masks, b)
        L_pair, L_win = probe(n, b, masks, w)
        key = f"{stem}|{n}|{m}|{b}"
        Z = optima.get(key)
        rows.append(dict(inst=stem, n=n, T=m, b=b, U=q, q=q,
                         L_pair=L_pair, L_win=L_win, Z=Z))
        print(f"{stem:8s} T={m:2d} b={b:2d}  |U|={q:2d}  L_pair={L_pair:3d} "
              f"L_win={L_win:3d}  Z*={Z}", flush=True)

    print()
    print("=" * 78)
    loose = [r for r in rows if r["Z"] is not None and r["Z"] > r["q"]]
    tight = [r for r in rows if r["Z"] is not None and r["Z"] == r["q"]]
    print(f"instances probed        : {len(rows)}")
    print(f"  coverage bound tight  : {len(tight)}")
    print(f"  coverage bound loose  : {len(loose)}")
    if not loose:
        return
    print()
    print("ON THE LOOSE INSTANCES -- fraction of the gap Z* - q that each family closes")
    print("-" * 78)
    for r in rows:
        r["L_arc"] = max(r["q"], r["L_pair"])     # what an arc-supported family can reach
    for name in ("L_arc", "L_win"):
        fr = [(r[name] - r["q"]) / (r["Z"] - r["q"]) for r in loose]
        exact = sum(1 for r in loose if r[name] == r["Z"])
        nogain = sum(1 for r in loose if r[name] == r["q"])
        fr_sorted = sorted(fr)
        med = fr_sorted[len(fr_sorted) // 2]
        print(f"  {name:7s}  mean {sum(fr)/len(fr):6.1%}   median {med:6.1%}   "
              f"max {max(fr):6.1%}   reaches Z* on {exact}/{len(loose)}   "
              f"no gain on {nogain}/{len(loose)}")
    print()
    print("absolute units of the gap closed (loose instances only):")
    for name in ("L_arc", "L_win"):
        d = [r[name] - r["q"] for r in loose]
        tot = sum(r["Z"] - r["q"] for r in loose)
        print(f"  {name:7s}  {sum(d):.0f} of {tot:.0f} units  "
              f"(mean +{sum(d)/len(d):.2f} per instance)")
    print()
    print("raw pairwise path bound is BELOW the coverage bound on "
          f"{sum(1 for r in rows if r['L_pair'] < r['q'])}/{len(rows)} instances")
    both = [max(r["L_win"], r["L_arc"]) for r in loose]
    fr = [(bb - r["q"]) / (r["Z"] - r["q"]) for bb, r in zip(both, loose)]
    print(f"taking the better of the two: mean {sum(fr)/len(fr):.1%} of the gap closed")

    with open("/home/claude/bound_probe_results.json", "w") as fh:
        json.dump(rows, fh, indent=1)


if __name__ == "__main__":
    main()
