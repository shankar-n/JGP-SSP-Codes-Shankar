"""
Generate Plots from raw_results.csv
=====================================

Produces 6 figures for the paper.  Each figure is saved as both .pdf
(for LaTeX \includegraphics) and .png (for quick inspection).

Figure descriptions
-------------------
Fig 1 — Performance profile (Dolan-Moré)
    x: τ = time ratio relative to best solver on that instance (log scale)
    y: fraction of instances solved within factor τ
    One curve per config.  Standard competitive comparison in OR.

Fig 2 — Ablation contribution bar chart
    x: BBC config labels
    y: % instances solved within TL
    Grouped bars by benchmark set.

Fig 3 — Root LP bound vs. node count (scatter)
    x: root_lp_bound normalised by optimal obj
    y: nodes (log scale)
    Coloured by triplet_bounds; shaped by frac_cuts.

Fig 4 — Node reduction from fractional cuts (histogram)
    x: log2(nodes_BBC-K / nodes_BBC-K+F)  for instances solved by both
    y: count.  Separate panels for J≤10 and J≥11.

Fig 5 — Convergence traces  [STUB — requires solve_stats['convergence_log']]
    Not generated unless 'convergence_log' data is present in raw_results.
    See TODO in BBC solver to add per-timestep (elapsed, dual_bound) logging.

Fig 6 — Scalability: SGM(time) vs J
    x: J (number of jobs)
    y: SGM(time) across instances of that J value (log scale)
    One line per key config: BBC-K+FT, LSS, SSPMF.

Usage
-----
    python generate_plots.py
    python generate_plots.py --raw raw_results.csv --jgp jgp_gsp_costs.csv
"""

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

_BBC = Path(__file__).resolve().parent.parent    # src/BBC/
sys.path.insert(0, str(_BBC))
from benchmark_config import RAW_CSV, JGP_GSP_CSV, ANALYSIS_DIR

ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

try:
    import matplotlib
    matplotlib.use("Agg")          # non-interactive backend
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("WARNING: matplotlib / numpy not installed.  "
          "Install with:  pip install matplotlib numpy --break-system-packages")


# ─────────────────────────────────────────────────────────────────────────────
# Data loading  (duplicated from generate_tables for standalone use)
# ─────────────────────────────────────────────────────────────────────────────

def load_results(raw_csv):
    rows = []
    with open(raw_csv, newline="") as f:
        for r in csv.DictReader(f):
            for col in ("J", "T", "C", "nodes", "lp_iters", "cb_invocations",
                        "cuts_sec", "cuts_benders", "cuts_comb", "cuts_frac"):
                r[col] = int(r[col]) if r.get(col) not in (None, "", "None") else None
            for col in ("density", "obj", "time_s", "gap_pct",
                        "root_lp_bound", "dual_bound"):
                r[col] = float(r[col]) if r.get(col) not in (None, "", "None") else None
            r["optimal"] = "optimal" in str(r.get("status", "")).lower()
            r["comb_cuts"]      = str(r.get("comb_cuts", "")).lower() == "true"
            r["frac_cuts"]      = str(r.get("frac_cuts", "")).lower() == "true"
            r["triplet_bounds"] = str(r.get("triplet_bounds", "")).lower() == "true"
            rows.append(r)
    return rows


def load_jgp_costs(jgp_csv):
    costs = {}
    if not Path(jgp_csv).exists():
        return costs
    with open(jgp_csv, newline="") as f:
        for r in csv.DictReader(f):
            key = r["instance"]
            if r.get("jgp_gsp_cost") not in (None, "", "None"):
                costs[key] = float(r["jgp_gsp_cost"])
    return costs


SHIFT = 10.0

def sgm(times, tl=3600.0):
    vals = [(t if t is not None else tl) for t in times]
    if not vals:
        return float("nan")
    return math.exp(sum(math.log(v + SHIFT) for v in vals) / len(vals)) - SHIFT


PRIMARY_SETS = {"Catanzaro", "Crama", "Laporte7"}
ALL_CONFIGS  = ["BBC-LP", "BBC-LP+F", "BBC-LP+T", "BBC-LP+FT",
                "BBC-K",  "BBC-K+F",  "BBC-K+T",  "BBC-K+FT",
                "LSS", "SSPMF"]
BBC_CONFIGS  = ALL_CONFIGS[:8]

# Colour palette — distinct and print-friendly (colourblind-safe)
PALETTE = {
    "BBC-LP":    "#1f77b4",
    "BBC-LP+F":  "#aec7e8",
    "BBC-LP+T":  "#17becf",
    "BBC-LP+FT": "#9edae5",
    "BBC-K":     "#d62728",
    "BBC-K+F":   "#ff9896",
    "BBC-K+T":   "#e377c2",
    "BBC-K+FT":  "#f7b6d2",
    "LSS":       "#2ca02c",
    "SSPMF":     "#ff7f0e",
}
LINESTYLE = {c: ("-" if "BBC-K" in c or c in ("LSS", "SSPMF") else "--")
             for c in ALL_CONFIGS}


def _save(fig, name):
    for ext in ("pdf", "png"):
        p = ANALYSIS_DIR / f"{name}.{ext}"
        fig.savefig(p, bbox_inches="tight", dpi=150)
    print(f"  Saved: {name}.pdf / .png")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1 — Performance Profile (Dolan-Moré)
# ─────────────────────────────────────────────────────────────────────────────

def fig1_performance_profile(rows, time_limit=3600.0):
    """
    Standard Dolan-Moré performance profile.
    Only instances that were solved to optimality by AT LEAST ONE config are included.
    """
    # Index: (instance, benchmark_set) → {config: time_s}
    by_inst = defaultdict(dict)
    for r in rows:
        if r["benchmark_set"] not in PRIMARY_SETS:
            continue
        by_inst[(r["instance"], r["benchmark_set"])][r["config"]] = (
            r["time_s"] if r["optimal"] else None
        )

    # Keep only instances solved by at least one config
    instances = {k: v for k, v in by_inst.items()
                 if any(t is not None for t in v.values())}

    if not instances:
        print("  Fig 1: no solved instances found — skipping.")
        return

    # Compute ratio matrix: ratio[config][instance] = t_c / t_best
    configs_present = [c for c in ALL_CONFIGS
                       if any(c in v for v in instances.values())]
    ratios = defaultdict(list)
    for inst_data in instances.values():
        t_best = min((t for t in inst_data.values() if t is not None), default=None)
        if t_best is None or t_best <= 0:
            t_best = 1e-3
        for cfg in configs_present:
            t = inst_data.get(cfg)
            if t is not None:
                ratios[cfg].append(t / t_best)
            else:
                ratios[cfg].append(float("inf"))

    n = len(instances)
    tau_max = time_limit
    tau_vals = sorted(set(r for rs in ratios.values() for r in rs if math.isfinite(r)))
    tau_vals = [1.0] + [t for t in tau_vals if t >= 1.0] + [tau_max]

    fig, ax = plt.subplots(figsize=(9, 5))
    for cfg in configs_present:
        rs = sorted(ratios[cfg])
        ys = [sum(r <= tau for r in rs) / n for tau in tau_vals]
        ax.plot(tau_vals, ys, label=cfg,
                color=PALETTE.get(cfg, "grey"),
                linestyle=LINESTYLE.get(cfg, "-"),
                linewidth=1.6)

    ax.set_xscale("log")
    ax.set_xlabel(r"$\tau$ (time ratio relative to best, log scale)")
    ax.set_ylabel("Fraction of instances solved")
    ax.set_title("Performance Profile — Primary instances (Dolan-Moré)")
    ax.set_xlim(1.0, tau_max)
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=7, ncol=2, loc="lower right")
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    _save(fig, "fig1_performance_profile")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2 — Ablation contribution bar chart
# ─────────────────────────────────────────────────────────────────────────────

def fig2_ablation_bars(rows, time_limit=3600.0):
    """
    % solved within TL per BBC config, grouped by benchmark set.
    """
    bbc_data = [r for r in rows if r["config"] in BBC_CONFIGS
                                and r["benchmark_set"] in PRIMARY_SETS]
    if not bbc_data:
        print("  Fig 2: no BBC primary data — skipping.")
        return

    sets = [s for s in ["Catanzaro", "Crama", "Laporte7"] if
            any(r["benchmark_set"] == s for r in bbc_data)]

    # pct_opt_matrix[set][config]
    by = defaultdict(lambda: defaultdict(list))
    for r in bbc_data:
        by[r["benchmark_set"]][r["config"]].append(r)

    x = np.arange(len(BBC_CONFIGS))
    width = 0.25
    offsets = np.linspace(-(len(sets)-1)*width/2, (len(sets)-1)*width/2, len(sets))

    fig, ax = plt.subplots(figsize=(11, 5))
    set_colors = ["#4393c3", "#d6604d", "#74add1"]
    for i, bset in enumerate(sets):
        pcts = [
            100.0 * sum(r["optimal"] for r in by[bset].get(cfg, [])) /
            max(len(by[bset].get(cfg, [])), 1)
            for cfg in BBC_CONFIGS
        ]
        bars = ax.bar(x + offsets[i], pcts, width,
                      label=bset, color=set_colors[i], alpha=0.85, edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(BBC_CONFIGS, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("% instances solved to optimality")
    ax.set_title("BBC Component Ablation — Primary Instances")
    ax.set_ylim(0, 110)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    _save(fig, "fig2_ablation_bars")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3 — Root LP bound vs. node count
# ─────────────────────────────────────────────────────────────────────────────

def fig3_root_lp_vs_nodes(rows):
    """
    Scatter: normalised root LP bound (root_lp_bound / obj) vs. nodes.
    Colour = triplet_bounds; shape = frac_cuts.
    """
    data = [r for r in rows
            if r["config"] in BBC_CONFIGS
            and r["benchmark_set"] in PRIMARY_SETS
            and r["optimal"]
            and r["root_lp_bound"] is not None
            and r["nodes"] is not None
            and r["obj"] is not None
            and r["obj"] > 0]
    if not data:
        print("  Fig 3: no data — skipping.")
        return

    fig, ax = plt.subplots(figsize=(7, 5))
    combos = [(False, False), (False, True), (True, False), (True, True)]
    markers = {(False, False): "o", (False, True): "s", (True, False): "^", (True, True): "D"}
    colors  = {False: "#4393c3", True: "#d6604d"}
    labels  = {
        (False, False): "trip=F, frac=F",
        (False, True):  "trip=F, frac=T",
        (True, False):  "trip=T, frac=F",
        (True, True):   "trip=T, frac=T",
    }

    for (trip, frac) in combos:
        pts = [r for r in data if r["triplet_bounds"] == trip and r["frac_cuts"] == frac]
        if not pts:
            continue
        xs = [r["root_lp_bound"] / r["obj"] for r in pts]
        ys = [max(r["nodes"], 1) for r in pts]
        ax.scatter(xs, ys, alpha=0.5, s=18,
                   color=colors[trip], marker=markers[(trip, frac)],
                   label=labels[(trip, frac)])

    ax.set_yscale("log")
    ax.set_xlabel("root_lp_bound / obj  (normalised root relaxation quality)")
    ax.set_ylabel("B&B nodes (log scale)")
    ax.set_title("Root LP Bound Quality vs. B&B Tree Size\n(BBC configs, primary instances)")
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    _save(fig, "fig3_root_lp_vs_nodes")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Figure 4 — Node reduction from fractional cuts
# ─────────────────────────────────────────────────────────────────────────────

def fig4_node_reduction(rows):
    """
    Histogram of log2(nodes_BBC-K / nodes_BBC-K+F) for instances solved by both.
    Panels for J≤10 and J≥11.
    """
    # Build dict: (instance, benchmark_set) → {config: nodes}
    by_inst = defaultdict(dict)
    for r in rows:
        if r["benchmark_set"] not in PRIMARY_SETS:
            continue
        if r["config"] in ("BBC-K", "BBC-K+F") and r["optimal"] and r["nodes"] is not None:
            by_inst[(r["instance"], r["benchmark_set"], r["J"])][r["config"]] = r["nodes"]

    # Compute ratios
    small_ratios, large_ratios = [], []
    for (inst, bset, J), cfg_nodes in by_inst.items():
        if "BBC-K" not in cfg_nodes or "BBC-K+F" not in cfg_nodes:
            continue
        n_base = max(cfg_nodes["BBC-K"], 1)
        n_frac = max(cfg_nodes["BBC-K+F"], 1)
        ratio  = math.log2(n_base / n_frac)   # positive = frac cuts helped
        if J is not None and J <= 10:
            small_ratios.append(ratio)
        else:
            large_ratios.append(ratio)

    if not small_ratios and not large_ratios:
        print("  Fig 4: no paired BBC-K / BBC-K+F data — skipping.")
        return

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=False)
    for ax, ratios, title in zip(axes,
                                  [small_ratios, large_ratios],
                                  ["J ≤ 10", "J ≥ 11"]):
        if not ratios:
            ax.set_title(f"{title}  (no data)")
            continue
        ax.hist(ratios, bins=20, color="#4393c3", edgecolor="white", alpha=0.85)
        ax.axvline(0, color="black", linewidth=1, linestyle="--")
        ax.set_xlabel(r"$\log_2$(nodes BBC-K / nodes BBC-K+F)")
        ax.set_ylabel("Count")
        ax.set_title(f"Node reduction from fractional cuts  [{title}]")
        ax.annotate(f"n={len(ratios)}", xy=(0.97, 0.95), xycoords="axes fraction",
                    ha="right", va="top", fontsize=9)

    fig.suptitle("Positive = fractional cuts reduced node count", fontsize=10, y=1.01)
    fig.tight_layout()
    _save(fig, "fig4_node_reduction")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Figure 5 — Convergence traces (STUB)
# ─────────────────────────────────────────────────────────────────────────────

def fig5_convergence_traces(rows):
    """
    STUB: Convergence traces require per-timestep (elapsed, dual_bound) logging
    inside the BBC solver (solve_stats['convergence_log']).

    TODO in src/BBC/branch_and_benders_cut_cplex.py:
        In the generic callback, after each Benders cut addition, append
        (context.get_elapsed_time(), dual_bound) to self.convergence_log.
        Expose as solve_stats['convergence_log'] = self.convergence_log.
    Then re-run benchmark_runner with --configs BBC-K BBC-K+F BBC-K+FT LSS
    on a small subset of hard Laporte5 instances and plot here.
    """
    print("  Fig 5: convergence traces — STUB (requires solve_stats['convergence_log']).")
    print("         See TODO in branch_and_benders_cut_cplex.py.")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 6 — Scalability: SGM(time) vs J
# ─────────────────────────────────────────────────────────────────────────────

def fig6_scalability(rows, time_limit=3600.0):
    """
    SGM(time) vs. J for key configs: BBC-K+FT, LSS, SSPMF.
    Uses all available instances (primary + secondary).
    """
    key_configs = ["BBC-K+FT", "LSS", "SSPMF"]
    data = [r for r in rows if r["config"] in key_configs and r.get("J") is not None]
    if not data:
        print("  Fig 6: no data — skipping.")
        return

    all_J = sorted({r["J"] for r in data})

    fig, ax = plt.subplots(figsize=(8, 4))
    for cfg in key_configs:
        sgm_by_j = []
        j_vals   = []
        for j in all_J:
            subset = [r for r in data if r["config"] == cfg and r["J"] == j]
            if len(subset) < 3:   # skip J values with very few instances
                continue
            times = [r["time_s"] for r in subset]
            tl = 600.0 if any(r["benchmark_set"] in {"Laporte3","Laporte4","Laporte5"}
                              for r in subset) else time_limit
            j_vals.append(j)
            sgm_by_j.append(sgm(times, tl))

        if j_vals:
            ax.plot(j_vals, sgm_by_j, "o-", label=cfg,
                    color=PALETTE.get(cfg, "grey"), linewidth=1.8, markersize=5)

    ax.set_yscale("log")
    ax.set_xlabel("J (number of jobs)")
    ax.set_ylabel("SGM of solve time (s, log scale)")
    ax.set_title("Scalability with Problem Size")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    _save(fig, "fig6_scalability")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main(raw_csv=None, jgp_csv=None):
    if not HAS_MPL:
        print("Cannot generate plots without matplotlib.  Aborting.")
        sys.exit(1)

    raw_csv = Path(raw_csv) if raw_csv else RAW_CSV
    jgp_csv = Path(jgp_csv) if jgp_csv else JGP_GSP_CSV

    if not raw_csv.exists():
        print(f"ERROR: {raw_csv} not found.  Run benchmark_runner.py first.")
        sys.exit(1)

    print(f"Loading {raw_csv} ...")
    rows = load_results(raw_csv)
    print(f"  {len(rows)} rows loaded.\n")

    print("Generating Fig 1 — Performance Profile ...")
    fig1_performance_profile(rows)

    print("Generating Fig 2 — Ablation Bar Chart ...")
    fig2_ablation_bars(rows)

    print("Generating Fig 3 — Root LP Bound vs. Nodes ...")
    fig3_root_lp_vs_nodes(rows)

    print("Generating Fig 4 — Node Reduction Histogram ...")
    fig4_node_reduction(rows)

    print("Generating Fig 5 — Convergence Traces (stub) ...")
    fig5_convergence_traces(rows)

    print("Generating Fig 6 — Scalability ...")
    fig6_scalability(rows)

    print(f"\nAll plots saved to: {ANALYSIS_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default=None, help="Path to raw_results.csv")
    parser.add_argument("--jgp", default=None, help="Path to jgp_gsp_costs.csv")
    args = parser.parse_args()
    main(args.raw, args.jgp)
