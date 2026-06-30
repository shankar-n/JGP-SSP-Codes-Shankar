#!/usr/bin/env python3
"""
Instance loaders for the SSP benchmark families (P5c).

A single token-based parse handles every family format uniformly: read all
whitespace-separated integers; the first three are J (jobs), T (tools), C
(magazine capacity b); the next T*J are the tool-major T x J matrix, with
A[t][j] = 1 iff job j needs tool t.  This covers the one-line headers
(Catanzaro / Laporte / Otiai, the last with leading spaces / huge rows) AND
Crama's three-separate-lines header. Verified on a sample of each family:
tokens-3 == T*J and |T_j| <= b throughout (orientation correct).

Size note (1735 files): most instances are in the MILP-pricing regime
(|V| = C(T,b) > 4000); Otiai is far beyond exact B&P (J up to 400, |V| ~ 1e57)
and will time out -- use the size filters below to pick a tractable subset.
"""
import os
import glob
import math

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "data", "From_Felipe", "data")
FAMILIES = ["Catanzaro", "Crama", "Laporte", "Otiai"]


def load_file(path):
    """Parse one instance file -> (J, T, b, Tj) with Tj a list of frozensets."""
    toks = open(path).read().split()
    J, T, C = int(toks[0]), int(toks[1]), int(toks[2])
    vals = list(map(int, toks[3:3 + T * J]))
    if len(vals) != T * J:
        raise ValueError(f"{path}: expected {T*J} matrix entries, got {len(vals)}")
    A = [vals[t * J:(t + 1) * J] for t in range(T)]
    Tj = [frozenset(t for t in range(T) if A[t][j]) for j in range(J)]
    return J, T, C, Tj


def list_family(family, data_dir=None):
    """All .txt instance paths for a family, sorted."""
    d = data_dir or DATA
    return sorted(glob.glob(os.path.join(d, family, "**", "*.txt"), recursive=True))


def iter_instances(family, max_jobs=None, max_nv=None, data_dir=None):
    """Yield (name, J, T, b, Tj) for a family, optionally filtered by size.
    max_jobs caps J; max_nv caps |V| = C(T,b) (use to keep the run tractable)."""
    for f in list_family(family, data_dir):
        try:
            J, T, b, Tj = load_file(f)
        except Exception:
            continue
        if max_jobs is not None and J > max_jobs:
            continue
        if max_nv is not None and (b > T or math.comb(T, b) > max_nv):
            continue
        yield os.path.basename(f), J, T, b, Tj


if __name__ == "__main__":
    for fam in FAMILIES:
        files = list_family(fam)
        if not files:
            print(f"{fam:10}: 0 files (data dir not found?)"); continue
        J, T, b, Tj = load_file(files[0])
        print(f"{fam:10}: {len(files):4} files | first={os.path.basename(files[0])} "
              f"J={J} T={T} b={b} |V|=C(T,b)={math.comb(T,b) if b<=T else 'NA'}")
