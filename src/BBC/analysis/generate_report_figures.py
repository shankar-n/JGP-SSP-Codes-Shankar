#!/usr/bin/env python3
"""
Clean §5 figures/tables for the 2026-08 protocol (all instances, uniform limit,
no early-stop, reported per family + performance profile).

Reads the merged raw_results.csv (or globs results/raw_*.csv) and writes, into
analysis/output/:
  * cactus.pdf        -- performance profile: #instances solved vs. time, per method
  * per_family.tex    -- solved / total, per method x family  (uniform denominators)
  * timing.tex        -- shifted-geometric-mean solve time on commonly-solved instances
  * bound_split.txt   -- bound-tight (opt == |U|) vs. loose share of solved instances

Every number traces to the raw CSV -- nothing is hand-entered.  Run after the
campaign finishes and `bash cluster/merge_results.sh`:

    python analysis/generate_report_figures.py
"""
import csv
import glob
import math
import os
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE = Path(__file__).resolve().parent           # .../src/BBC/analysis
_BBC = _HERE.parent                               # .../src/BBC
_OUT = _HERE / "output"
_OUT.mkdir(parents=True, exist_ok=True)
_DATA = _BBC.parent.parent / "data" / "From_Felipe" / "data"


def load_rows():
    """Prefer the merged raw_results.csv; else concatenate results/raw_*.csv."""
    merged = _BBC / "raw_results.csv"
    files = [merged] if merged.exists() else [Path(p) for p in glob.glob(str(_BBC / "results" / "raw_*.csv"))]
    rows = []
    for f in files:
        with open(f, newline="") as fh:
            rows.extend(list(csv.DictReader(fh)))
    return [r for r in rows if r.get("J", "").strip()]


def _solved(r):
    return "optimal" in str(r.get("status", "")).lower()


def _time(r):
    try:
        return float(r["time_s"])
    except (TypeError, ValueError, KeyError):
        return None


# ---------------------------------------------------------------------------
def cactus_plot(rows, time_limit=3600):
    """Performance profile: for each method, #instances solved within time t."""
    by_solver = defaultdict(list)
    # one representative config per solver family for the headline plot:
    headline = {"BBC-LP+ACC", "BBC-LP+F", "LSS", "SSPMF", "CATZ-F4", "PCFp", "PTF"}
    for r in rows:
        cfg = r.get("config", r.get("solver", ""))
        if cfg not in headline:
            continue
        if _solved(r) and _time(r) is not None:
            by_solver[cfg].append(_time(r))
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for cfg in sorted(by_solver):
        ts = sorted(by_solver[cfg])
        xs = ts + [time_limit]
        ys = list(range(1, len(ts) + 1)) + [len(ts)]
        ax.step(xs, ys, where="post", label=f"{cfg} ({len(ts)})")
    ax.set_xscale("log")
    ax.set_xlabel("time (s, log)")
    ax.set_ylabel("instances solved to optimality")
    ax.set_title("Performance profile (cactus plot)")
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(_OUT / "cactus.pdf")
    fig.savefig(_OUT / "cactus.png", dpi=110)
    return len(by_solver)


# ---------------------------------------------------------------------------
def per_family_table(rows):
    """solved / total, per config x family, uniform denominators -> LaTeX."""
    fams = sorted({r["benchmark_set"] for r in rows})
    cfgs = sorted({r.get("config", r.get("solver", "")) for r in rows})
    total = defaultdict(set)     # (cfg,fam) -> instances seen
    solv = defaultdict(set)      # (cfg,fam) -> instances solved
    for r in rows:
        cfg = r.get("config", r.get("solver", "")); fam = r["benchmark_set"]
        key = (cfg, fam); inst = r["instance"]
        total[key].add(inst)
        if _solved(r):
            solv[key].add(inst)
    lines = ["\\begin{tabular}{l" + "c" * len(fams) + "}", "\\toprule",
             "config & " + " & ".join(fams) + " \\\\", "\\midrule"]
    for cfg in cfgs:
        cells = []
        for fam in fams:
            t = len(total[(cfg, fam)]); s = len(solv[(cfg, fam)])
            cells.append(f"{s}/{t}" if t else "--")
        lines.append(f"{cfg} & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (_OUT / "per_family.tex").write_text("\n".join(lines))
    return len(cfgs), len(fams)


# ---------------------------------------------------------------------------
def timing_table(rows, shift=10.0):
    """Shifted geometric-mean solve time on instances a set of methods all solved."""
    solved_by = defaultdict(dict)   # cfg -> {instance: time}
    for r in rows:
        if _solved(r) and _time(r) is not None:
            solved_by[r.get("config", r.get("solver", ""))][r["instance"]] = _time(r)
    cfgs = sorted(solved_by)
    if not cfgs:
        (_OUT / "timing.tex").write_text("% no solved instances yet")
        return 0
    common = set.intersection(*(set(solved_by[c]) for c in cfgs)) if cfgs else set()
    lines = ["\\begin{tabular}{lc}", "\\toprule",
             f"config & shifted geo-mean time (s), {len(common)} common inst. \\\\",
             "\\midrule"]
    for c in cfgs:
        if common:
            g = math.exp(sum(math.log(solved_by[c][i] + shift) for i in common) / len(common)) - shift
            lines.append(f"{c} & {g:.1f} \\\\")
        else:
            lines.append(f"{c} & -- \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (_OUT / "timing.tex").write_text("\n".join(lines))
    return len(common)


# ---------------------------------------------------------------------------
def bound_split(rows):
    """Bound-tight (opt == |U|) vs. loose among instances solved by any method."""
    idx = {}
    for p in glob.glob(str(_DATA / "**" / "*.txt"), recursive=True):
        try:
            t = open(p).read().split(); J, T, C = int(t[0]), int(t[1]), int(t[2])
            import numpy as np
            A = np.array(list(map(int, t[3:3 + T * J]))).reshape(T, J)
            idx.setdefault((os.path.basename(p)[:-4], J, T, C), int((A.sum(1) > 0).sum()))
        except Exception:
            pass
    opt = {}
    for r in rows:
        if _solved(r) and r.get("obj_ktns", "").strip():
            key = (r["instance"], int(r["J"]), int(r["T"]), int(r["C"]))
            opt[key] = float(r["obj_ktns"])
    tight = sum(1 for (i, J, T, C), z in opt.items()
                if idx.get((i, J, T, C)) is not None and z == idx[(i, J, T, C)])
    total = len([k for k in opt if idx.get(k) is not None])
    pct = 100 * tight / total if total else 0
    msg = (f"solved instances with |U| known: {total}\n"
           f"bound-tight (opt == |U|): {tight}  ({pct:.1f}%)\n"
           f"bound-loose:              {total - tight}\n")
    (_OUT / "bound_split.txt").write_text(msg)
    return msg


# ---------------------------------------------------------------------------
def main():
    rows = load_rows()
    if not rows:
        print("No results found yet (results/raw_*.csv or raw_results.csv). "
              "Run the campaign + merge_results.sh first.")
        return
    print(f"loaded {len(rows)} result rows")
    print(f"cactus: {cactus_plot(rows)} methods -> {_OUT}/cactus.pdf")
    c, f = per_family_table(rows)
    print(f"per-family table: {c} configs x {f} families -> {_OUT}/per_family.tex")
    print(f"timing table: {timing_table(rows)} common instances -> {_OUT}/timing.tex")
    print(bound_split(rows))


if __name__ == "__main__":
    main()
