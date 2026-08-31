#!/usr/bin/env python3
"""
make_figure_data.py -- regenerate every .dat file behind the figures in Section 1,
6 and 7 of the report, from the raw campaign output and from the instance files.

Nothing here is typed by hand. Run from the repository root:

    python3 report/make_figure_data.py

and it overwrites report/figdata/*.dat. If a figure in the report disagrees with
what this produces, the figure is wrong.

Inputs
    src/BBC/results/*.csv          the completed campaign, 17,052 runs
    data/**/Laporte/Tabela3/*.txt  the instance used for the landscape figure
    bound_probe_results.json       per-instance ceilings (produced by bound_probe.py)

Outputs (report/figdata/)
    landscape.dat     Figure 3   every ordering of one instance, by cost
    cactus.dat        Figure 10  instances closed against wall-clock time
    rootgap.dat       Figure 12  root relaxation minus the coverage row
    ceilings.dat      Figure 13  per-instance fixed-bound values, sorted alone
    solvedvsgap.dat   Figure 11  share closed against how loose the bound is
"""
import glob, itertools, json, math, os, re, sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "report", "figdata")
KEY = ["benchmark_set", "instance", "J", "T", "C"]


def _analysis():
    """Reuse the campaign analysis so the conventions match Section 6 exactly."""
    import importlib.util
    p = os.path.join(ROOT, "verification", "analyse_campaign_results.py")
    spec = importlib.util.spec_from_file_location("acr", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# --------------------------------------------------------------- Figure 3
def ktns(seq, Tj, b):
    mag, ins = set(), 0
    for i, j in enumerate(seq):
        for t in sorted(Tj[j] - mag):
            if len(mag) >= b:
                def nxt(x):
                    return next((k for k in range(i, len(seq)) if x in Tj[seq[k]]), 10 ** 6)
                mag.discard(max([x for x in mag if x not in Tj[j]], key=nxt))
            mag.add(t)
            ins += 1
    return ins


def landscape(path):
    tok = open(path).read().split()
    n, T, b = int(tok[0]), int(tok[1]), int(tok[2])
    M = np.array(list(map(int, tok[3:3 + T * n]))).reshape(T, n)
    Tj = [set(np.nonzero(M[:, j])[0]) for j in range(n)]
    U = set().union(*Tj)
    costs = np.fromiter((ktns(list(s), Tj, b) for s in itertools.permutations(range(n))),
                        int, math.factorial(n))
    free = costs - min(b, len(U))
    vals, cnts = np.unique(free, return_counts=True)
    with open(f"{OUT}/landscape.dat", "w") as f:
        f.write("cost count\n")
        for v, c in zip(vals, cnts):
            f.write(f"{v} {c}\n")
    source = os.path.relpath(path, ROOT).replace(os.sep, "/")
    meta = (source, n, T, b, len(U), len(U) - b, int(free.min()),
            int(np.median(free)), int(free.max()), int((free == free.min()).sum()))
    with open(f"{OUT}/landscape_meta.txt", "w") as f:
        f.write(" ".join(map(str, meta)) + "\n")
    print(f"landscape.dat   {path}: n={n} |U|={len(U)} b={b} q={len(U)-b} "
          f"Z*={free.min()} median={int(np.median(free))} "
          f"optimal orderings={int((free==free.min()).sum())} of {len(free)}")


# ------------------------------------------------------- Figures 10, 11, 12
def campaign():
    m = _analysis()
    bbc = m.canonical_rows(
        m.load_shards(os.path.join(ROOT, "src/BBC/results/*.csv"))
    )
    bbc["solved"] = bbc.status.astype(str).str.contains("optimal", case=False, na=False)
    bbc = bbc.join(bbc[bbc.solved].groupby(KEY)["obj_ktns"].min().rename("Zstar"), on=KEY)
    U = m.used_tool_counts()
    ucols = [c for c in U.columns if c in KEY]

    # ---- Figure 10: cumulative solved against time
    cfgs = ["SSPMF", "CATZ-F4", "LSS", "BBC-LP", "BBC-K", "BBC-LP+F"]
    grid = np.unique(np.concatenate([np.geomspace(0.05, 3600, 120), [3600]]))
    cols = [np.sort(bbc[(bbc.config == c) & bbc.solved]["time_s"].dropna().values) for c in cfgs]
    with open(f"{OUT}/cactus.dat", "w") as f:
        f.write("t " + " ".join(c.replace("+", "p").replace("-", "") for c in cfgs) + "\n")
        for t in grid:
            f.write(f"{t:.4f} " + " ".join(str(int(np.searchsorted(c, t, "right"))) for c in cols) + "\n")
    print("cactus.dat      " + "  ".join(f"{c}:{len(x)}" for c, x in zip(cfgs, cols)))

    # ---- Figure 12: root relaxation minus |U|
    rb = bbc[bbc.root_lp_bound.notna()].merge(U, on=ucols, how="left")
    rb = rb[rb.U.notna()].copy()
    rb["d"] = rb.root_lp_bound - rb.U
    edges = [1, 2, 4, 8, 16, 32]
    labs = ["0", "(0,1]", "(1,2]", "(2,4]", "(4,8]", "(8,16]", "(16,32]", ">32"]
    cnt = [int((rb.d.abs() < 1e-6).sum())]
    lo = 1e-6
    for hi in edges:
        cnt.append(int(((rb.d > lo) & (rb.d <= hi)).sum()))
        lo = hi
    cnt.append(int((rb.d > 32).sum()))
    with open(f"{OUT}/rootgap.dat", "w") as f:
        f.write("i n label\n")
        for i, (c, l) in enumerate(zip(cnt, labs)):
            f.write(f"{i} {c} {l}\n")
    print(f"rootgap.dat     {len(rb)} runs, {cnt[0]} exactly on the coverage row "
          f"({100*cnt[0]/len(rb):.1f}%)")

    # ---- Figure 11: share closed against how loose the bound is
    inst = bbc.groupby(KEY).first().reset_index().merge(U, on=ucols, how="left")
    k = inst[inst.Zstar.notna() & inst.U.notna()].copy()
    k["gap"] = (k.Zstar - k.U).round().astype(int)
    gapmap = k.set_index(KEY)["gap"]
    buckets = [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 6), (7, 9), (10, 14), (15, 10 ** 6)]
    with open(f"{OUT}/solvedvsgap.dat", "w") as f:
        f.write("x pct n cfg\n")
        for cfg in ["SSPMF", "BBC-LP", "CATZ-F4"]:
            r = bbc[bbc.config == cfg].set_index(KEY)
            for x, (lo_, hi_) in enumerate(buckets):
                idx = gapmap[(gapmap >= lo_) & (gapmap <= hi_)].index
                # Keep a fixed class denominator: missing or failed rows count as
                # not certified rather than disappearing from the comparison.
                sub = r.reindex(idx)
                if len(sub):
                    solved = sub["solved"].fillna(False).astype(bool)
                    f.write(f"{x} {100*solved.mean():.1f} {len(sub)} {cfg}\n")
    print(f"solvedvsgap.dat {len(k)} instances of known optimum, "
          f"{int((k.gap==0).sum())} bound-tight, {int((k.gap>0).sum())} loose")


# --------------------------------------------------------------- Figure 13
def ceilings():
    p = os.path.join(ROOT, "bound_probe_results.json")
    if not os.path.exists(p):
        p = os.path.join(ROOT, "verification", "bound_probe_results.json")
    d = [r for r in json.load(open(p)) if r["Z"] > r["q"]]
    pair = sorted(100 * (r["L_pair_cov"] - r["q"]) / (r["Z"] - r["q"]) for r in d)
    win = sorted(100 * (r["L_win"] - r["q"]) / (r["Z"] - r["q"]) for r in d)
    with open(f"{OUT}/ceilings.dat", "w") as f:
        f.write("i pair win\n")
        for i, (a, w) in enumerate(zip(pair, win), 1):
            f.write(f"{i} {a:.2f} {w:.2f}\n")
    z = lambda v: sum(1 for x in v if x < 1e-9)
    print(f"ceilings.dat    {len(d)} loose instances; fixed pairwise+coverage certifies "
          f"nothing on {z(pair)}, window on {z(win)}; peaks {max(pair):.0f}% "
          f"and {max(win):.0f}%")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    cands = sorted(glob.glob(os.path.join(ROOT, "data/**/Laporte/Tabela3/L1-1.txt"), recursive=True))
    if cands:
        landscape(cands[0])
    else:
        print("landscape: instance L1-1 not found, skipped", file=sys.stderr)
    campaign()
    ceilings()
    print("\nall figure data regenerated in report/figdata/")
