#!/usr/bin/env python3
"""Build the vector figures used by the defence slides.

All numbers are recomputed from the canonical campaign shards in
``src/BBC/results/raw_*.csv``.  Loading, canonical-instance filtering, objective
normalisation, and used-tool counts reuse the audited definitions in
``verification/analyse_campaign_results.py``.  The assertions below are a
second guard against silently plotting a partial or differently filtered run.

Run from the repository root with::

    python report/make_defence_figures.py

Outputs are vector PDFs in ``report/assets/defence_figures``.  Matplotlib is
used instead of Plotly because Beamer embeds PDF vectors reliably and without
a browser-based export step.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "assets" / "defence_figures"
AUDIT_SCRIPT = ROOT / "verification" / "analyse_campaign_results.py"

INK = "#25324A"
MUTED = "#667085"
GRID = "#D8DEE9"
BLUE = "#3066BE"
TEAL = "#16897B"
ORANGE = "#E07A3F"
CORAL = "#CF5C5C"
PURPLE = "#7A63A8"
GREEN = "#4C956C"
PALE_BLUE = "#A9C7E8"
PALE_ORANGE = "#F2B38A"


mpl.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 13,
        "axes.labelsize": 14,
        "axes.titlesize": 15,
        "xtick.labelsize": 12,
        "ytick.labelsize": 12,
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "text.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    }
)



# ---------------------------------------------------------------------------
# Plain-English labels. The internal codes (BBC-LP+F+H and friends) are
# unreadable on a slide, so every figure prints the descriptive name instead.
# ---------------------------------------------------------------------------
NICE = {
    "SSPMF":       "Multicommodity",
    "CATZ-F4":     "Arc-flow (F4)",
    "LSS":         "Tool-state",
    "BBC-LP":      "Benders \u2014 base",
    "BBC-LP+T":    "Benders + triplet rows",
    "BBC-K":       "Benders \u2014 KTNS oracle",
    "BBC-LP+F":    "Benders + fractional cuts",
    "BBC-LP+F+H":  "Benders + fractional + heuristic",
    "BBC-K+F":     "Benders KTNS + fractional",
    "BBC-LP+F+C":  "Benders + fractional + conflict",
    "BBC-LP+ACC":  "Benders + all three",
    "BBC-LP+F+P":  "Benders + fractional + Pareto",
}
def nice(c):
    return NICE.get(c, c)


def audited_analysis_module():
    spec = importlib.util.spec_from_file_location("campaign_audit", AUDIT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {AUDIT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_campaign():
    audit = audited_analysis_module()
    raw = audit.load_shards(audit.BBC_GLOB)
    bbc = audit.canonical_rows(raw)
    bbc["solved"] = bbc["status"].isin(audit.SOLVED)
    bbc = bbc.join(
        bbc[bbc.solved].groupby(audit.KEY)["obj_ktns"].min().rename("Zstar"),
        on=audit.KEY,
    )
    instances = bbc.groupby(audit.KEY).first().reset_index()
    used = audit.used_tool_counts()

    assert len(raw) == 17_052, "raw campaign is not the audited ledger"
    assert len(bbc) == 16_920, "canonical campaign is not 12 x 1,410"
    assert len(instances) == 1_410
    assert bbc["config"].nunique() == 12
    assert (bbc.groupby("config").size() == 1_410).all()
    return audit, bbc, instances, used


def clean_axis(ax, *, xgrid=False, ygrid=False):
    if xgrid:
        ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    if ygrid:
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.tick_params(length=0)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)


def save(fig, stem, subject):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{stem}.pdf"
    fig.savefig(
        path,
        format="pdf",
        transparent=True,
        bbox_inches="tight",
        pad_inches=0.08,
        metadata={
            "Title": stem.replace("_", " ").title(),
            "Author": "JGP-SSP campaign figure generator",
            "Subject": subject,
        },
    )
    plt.close(fig)
    return path


def figure_solve_counts(bbc):
    expected = {
        "SSPMF": 1028,
        "CATZ-F4": 876,
        "LSS": 833,
        "BBC-LP": 724,
        "BBC-LP+T": 723,
        "BBC-K": 722,
        "BBC-LP+F+H": 686,
        "BBC-K+F": 657,
        "BBC-LP+F": 655,
        "BBC-LP+F+C": 654,
        "BBC-LP+ACC": 652,
        "BBC-LP+F+P": 618,
    }
    counts = bbc.groupby("config")["solved"].sum().astype(int).to_dict()
    assert counts == expected

    ordered = sorted(expected, key=expected.get)

    def category(config):
        if config in {"SSPMF", "CATZ-F4", "LSS"}:
            return "Compact baselines", BLUE
        if config in {"BBC-LP", "BBC-LP+T", "BBC-K"}:
            return "Integer-cut Benders", TEAL
        return "Benders with fractional separation", CORAL

    colors = [category(config)[1] for config in ordered]
    values = [expected[config] for config in ordered]

    fig, ax = plt.subplots(figsize=(11.8, 6.3))
    y = np.arange(len(ordered))
    ax.barh(y, values, color=colors, height=0.68, zorder=2)
    ax.set_yticks(y, [nice(c) for c in ordered])
    ax.set_xlim(0, 1_130)
    ax.set_xlabel("Instances certified optimal (fixed denominator: 1,410)")
    ax.set_xticks(np.arange(0, 1_101, 200))
    for yi, value in zip(y, values):
        ax.text(value + 15, yi, f"{value:,}", va="center", fontweight="bold", fontsize=12)
    clean_axis(ax, xgrid=True)
    ax.legend(
        handles=[
            Patch(facecolor=BLUE, label="Compact baselines"),
            Patch(facecolor=TEAL, label="Integer-cut Benders"),
            Patch(facecolor=CORAL, label="Fractional-separation regimes"),
        ],
        loc="lower center",
        bbox_to_anchor=(0.5, 1.01),
        ncol=3,
        frameon=False,
        fontsize=12,
    )
    fig.subplots_adjust(left=0.21, right=0.98, bottom=0.12, top=0.89)
    return save(
        fig,
        "solve_counts_all",
        "Solved counts for all 12 configurations, recomputed from the canonical 16,920-row campaign.",
    )


def figure_coverage_tightness(audit, bbc, instances, used):
    enriched = instances.merge(used, on=["instance", "J", "T", "C"], how="left")
    known = enriched[enriched.Zstar.notna() & enriched.U.notna()].copy()
    known["tight"] = np.isclose(known.Zstar, known.U)
    assert len(known) == 1_107
    assert int(known.tight.sum()) == 520
    assert int((~known.tight).sum()) == 587

    keyed = known.set_index(audit.KEY)
    methods = ["BBC-LP", "SSPMF", "CATZ-F4", "LSS"]
    expected = {
        "BBC-LP": (490, 234),
        "SSPMF": (520, 508),
        "CATZ-F4": (369, 507),
        "LSS": (369, 464),
    }
    tight_pct, loose_pct = [], []
    for method in methods:
        rows = bbc[bbc.config == method].set_index(audit.KEY)
        tight_idx = keyed[keyed.tight].index
        loose_idx = keyed[~keyed.tight].index
        tight_n = int(rows.reindex(tight_idx).solved.fillna(False).sum())
        loose_n = int(rows.reindex(loose_idx).solved.fillna(False).sum())
        assert (tight_n, loose_n) == expected[method]
        tight_pct.append(100 * tight_n / 520)
        loose_pct.append(100 * loose_n / 587)

    fig, ax = plt.subplots(figsize=(11.2, 5.7))
    x = np.arange(len(methods))
    width = 0.34
    b1 = ax.bar(x - width / 2, tight_pct, width, color=BLUE, label="Coverage bound exact")
    b2 = ax.bar(x + width / 2, loose_pct, width, color=ORANGE, label="Coverage bound loose")
    ax.set_ylim(0, 112)
    ax.set_ylabel("Certified optima (%)")
    ax.set_xticks(x, [nice(m) for m in methods])
    ax.set_yticks(np.arange(0, 101, 20))
    clean_axis(ax, ygrid=True)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2, frameon=False)
    for bars in (b1, b2):
        for bar in bars:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 2.0,
                f"{bar.get_height():.0f}%",
                ha="center",
                va="bottom",
                fontweight="bold",
                fontsize=12,
            )
    for xi, a, b in zip(x, tight_pct, loose_pct):
        ax.text(xi, 4, f"{b-a:+.0f} pp", ha="center", color="white", fontweight="bold", fontsize=11)
    fig.subplots_adjust(left=0.09, right=0.99, bottom=0.13, top=0.86)
    return save(
        fig,
        "coverage_tightness_closure",
        "Closure split on 1,107 known-optimum instances: 520 coverage-tight and 587 coverage-loose.",
    )


def figure_root_bounds(bbc, used):
    key_cols = [column for column in used.columns if column in ["benchmark_set", "instance", "J", "T", "C"]]
    roots = bbc[bbc.root_lp_bound.notna()].merge(used, on=key_cols, how="left")
    roots = roots[roots.U.notna()].copy()
    roots["excess"] = roots.root_lp_bound - roots.U
    exact = int(np.isclose(roots.excess, 0).sum())
    above = len(roots) - exact
    assert (len(roots), exact, above) == (10_392, 9_067, 1_325)

    edges = [1, 2, 4, 8, 16, 32]
    labels = ["(0, 1]", "(1, 2]", "(2, 4]", "(4, 8]", "(8, 16]", "(16, 32]", "> 32"]
    counts = []
    lo = 1e-6
    for hi in edges:
        counts.append(int(((roots.excess > lo) & (roots.excess <= hi)).sum()))
        lo = hi
    counts.append(int((roots.excess > 32).sum()))
    assert counts == [177, 210, 258, 314, 211, 104, 51]

    fig = plt.figure(figsize=(11.6, 5.7))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 2.5], hspace=0.68)
    share = fig.add_subplot(gs[0])
    dist = fig.add_subplot(gs[1])

    exact_pct = 100 * exact / len(roots)
    above_pct = 100 - exact_pct
    share.barh([0], [exact_pct], color=TEAL, height=0.55)
    share.barh([0], [above_pct], left=[exact_pct], color=ORANGE, height=0.55)
    share.text(exact_pct / 2, 0, f"Coverage only\n{exact:,} roots  |  {exact_pct:.1f}%", ha="center", va="center", color="white", fontweight="bold", fontsize=13)
    share.text(exact_pct + above_pct / 2, 0, f"Lifted\n{above:,}  |  {above_pct:.1f}%", ha="center", va="center", color="white", fontweight="bold", fontsize=11)
    share.set_xlim(0, 100)
    share.set_yticks([])
    share.set_xlabel("Share of recorded Benders root relaxations")
    share.set_xticks([0, 20, 40, 60, 80, 100], ["0%", "20%", "40%", "60%", "80%", "100%"])
    for spine in share.spines.values():
        spine.set_visible(False)
    share.tick_params(length=0)

    bars = dist.bar(np.arange(len(labels)), counts, color=ORANGE, width=0.72, zorder=2)
    dist.set_title("When the root rises above coverage: improvement in the empty-start bound", pad=8)
    dist.set_ylabel("Root records")
    dist.set_xlabel("Root bound minus coverage bound")
    dist.set_xticks(np.arange(len(labels)), labels)
    dist.set_ylim(0, 355)
    clean_axis(dist, ygrid=True)
    for bar, count in zip(bars, counts):
        dist.text(bar.get_x() + bar.get_width() / 2, count + 8, str(count), ha="center", va="bottom", fontweight="bold", fontsize=11)

    fig.subplots_adjust(left=0.09, right=0.99, bottom=0.13, top=0.98)
    return save(
        fig,
        "benders_root_bound_share",
        "Distribution of root relaxation minus the empty-start coverage bound over 10,392 canonical Benders root records.",
    )


def figure_fractional_tradeoff(audit, bbc):
    plain = bbc[bbc.config == "BBC-LP"].set_index(audit.KEY).sort_index()
    frac = bbc[bbc.config == "BBC-LP+F"].set_index(audit.KEY).sort_index()
    shared = plain.index.intersection(frac.index)
    plain, frac = plain.loc[shared], frac.loc[shared]
    assert len(shared) == 1_410
    assert (int(plain.solved.sum()), int(frac.solved.sum())) == (724, 655)
    assert int(plain.nodes.median()) == 77_439
    assert int(frac.nodes.median()) == 3_701
    assert int(frac.cuts_frac.fillna(0).sum()) == 67_047_595

    bounds = pd.DataFrame({"with": frac.dual_bound.values, "plain": plain.dual_bound.values}).dropna()
    outcomes = [
        int((bounds["with"] > bounds.plain + 1e-6).sum()),
        int(np.isclose(bounds["with"], bounds.plain).sum()),
        int((bounds["with"] < bounds.plain - 1e-6).sum()),
    ]
    assert len(bounds) == 1_404
    assert outcomes == [0, 1_226, 178]

    fig, axes = plt.subplots(1, 3, figsize=(12.4, 5.1), gridspec_kw={"width_ratios": [1, 1, 1.35]})
    methods = ["BBC-LP", "BBC-LP+F"]
    colors = [TEAL, CORAL]

    labels = ["Without\nfractional cuts", "With\nfractional cuts"]
    solve_ax, node_ax, bound_ax = axes
    solve_bars = solve_ax.bar(labels, [724, 655], color=colors, width=0.62)
    solve_ax.set_title("Certified optima")
    solve_ax.set_ylabel("Instances (of 1,410)")
    solve_ax.set_ylim(0, 810)
    clean_axis(solve_ax, ygrid=True)
    for bar, value in zip(solve_bars, [724, 655]):
        solve_ax.text(bar.get_x() + bar.get_width() / 2, value + 18, str(value), ha="center", fontweight="bold")

    node_bars = node_ax.bar(labels, [77_439, 3_701], color=colors, width=0.62)
    node_ax.set_title("Median nodes")
    node_ax.set_yscale("log")
    node_ax.set_ylim(1_000, 160_000)
    node_ax.set_ylabel("Search nodes (log scale)")
    clean_axis(node_ax, ygrid=True)
    for bar, value in zip(node_bars, [77_439, 3_701]):
        node_ax.text(bar.get_x() + bar.get_width() / 2, value * 1.16, f"{value:,}", ha="center", fontweight="bold", fontsize=12)

    outcome_labels = ["Higher", "Equal", "Lower"]
    outcome_colors = [GREEN, PALE_BLUE, CORAL]
    left = 0
    for label, value, color in zip(outcome_labels, outcomes, outcome_colors):
        if value:
            bound_ax.barh([0], [value], left=[left], color=color, height=0.55, label=label)
            if value > 100:
                bound_ax.text(left + value / 2, 0, f"{label}\n{value:,}", ha="center", va="center", fontweight="bold", color=INK)
        left += value
    bound_ax.text(18, 0.38, "Higher: 0", ha="left", va="bottom", color=GREEN, fontweight="bold", fontsize=12)
    bound_ax.set_title("Terminal dual bound with +F")
    bound_ax.set_xlim(0, 1_404)
    bound_ax.set_yticks([])
    bound_ax.set_xlabel("Paired runs with both bounds recorded")
    bound_ax.set_xticks([0, 350, 700, 1050, 1404])
    for spine in bound_ax.spines.values():
        spine.set_visible(False)
    bound_ax.tick_params(length=0)

    fig.text(
        0.5,
        0.015,
        "Fractional separation generated 67.0 million cuts, and also disables presolve.",
        ha="center",
        color=MUTED,
        fontsize=12,
    )
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.20, top=0.88, wspace=0.48)
    return save(
        fig,
        "fractional_separation_tradeoff",
        "BBC-LP versus BBC-LP+F on 1,410 common instances; terminal-bound comparison uses 1,404 paired recorded bounds.",
    )


def figure_common_solved_times(audit, bbc):
    common = None
    for config in audit.TIME_SET:
        idx = bbc[(bbc.config == config) & bbc.solved].set_index(audit.KEY).index
        common = idx if common is None else common.intersection(idx)
    assert common is not None and len(common) == 531

    display_order = [
        "SSPMF",
        "CATZ-F4",
        "LSS",
        "BBC-LP",
        "BBC-LP+T",
        "BBC-K",
        "BBC-LP+F",
        "BBC-LP+F+H",
    ]
    values = []
    medians = []
    for config in display_order:
        rows = bbc[(bbc.config == config) & bbc.solved].set_index(audit.KEY).loc[common]
        rows = rows[~rows.index.duplicated()]
        times = rows.time_s.astype(float).to_numpy()
        assert len(times) == 531 and np.all(times > 0)
        values.append(times)
        medians.append(float(np.median(times)))

    palette = [BLUE, ORANGE, PURPLE, TEAL, GREEN, "#287271", CORAL, "#B84E82"]
    fig, ax = plt.subplots(figsize=(11.8, 6.0))
    boxes = ax.boxplot(
        values,
        vert=False,
        tick_labels=[nice(c) for c in display_order],
        patch_artist=True,
        showfliers=False,
        widths=0.58,
        whis=1.5,
        medianprops={"color": INK, "linewidth": 2.0},
        whiskerprops={"color": MUTED, "linewidth": 1.2},
        capprops={"color": MUTED, "linewidth": 1.2},
    )
    for patch, color in zip(boxes["boxes"], palette):
        patch.set_facecolor(color)
        patch.set_edgecolor("none")
        patch.set_alpha(0.88)
    ax.set_xscale("log")
    ax.set_xlim(0.001, 4_200)
    ax.set_xlabel("Wall-clock time (seconds, log scale)")
    ax.set_title("Only instances solved by every method (n = 531)", pad=10)
    ax.set_xticks([0.001, 0.01, 0.1, 1, 10, 100, 1000, 3600])
    ax.set_xticklabels(["0.001", "0.01", "0.1", "1", "10", "100", "1,000", "3,600"])
    clean_axis(ax, xgrid=True)
    # Medians go in a dedicated column outside the axes, so no label ever sits on a box.
    ax.text(1.015, 1.035, "median", transform=ax.transAxes, fontsize=10.5,
            color=MUTED, fontweight="bold", ha="left", va="bottom")
    for yi, median in enumerate(medians, 1):
        ax.text(1.015, yi, f"{median:.3g} s", transform=ax.get_yaxis_transform(),
                fontsize=10.5, color=INK, ha="left", va="center", clip_on=False)
    ax.invert_yaxis()
    fig.subplots_adjust(left=0.16, right=0.87, bottom=0.13, top=0.90)
    return save(
        fig,
        "common_solved_time_boxplot",
        "Wall-clock distributions on the 531-instance intersection solved by all eight listed configurations.",
    )


def write_provenance(paths):
    lines = [
        "Defence figure provenance",
        "=========================",
        "",
        "Canonical inputs: src/BBC/results/raw_*.csv",
        "Audit definitions: verification/analyse_campaign_results.py",
        "Generator: report/make_defence_figures.py",
        "Raw rows: 17,052; canonical rows: 16,920; configurations: 12; instances: 1,410.",
        "Run `python verification/analyse_campaign_results.py --check` for the independent numeric audit.",
        "",
        "Generated vector PDFs:",
        *[f"- {path.name}" for path in paths],
        "",
        "Figure-specific denominators are printed in the plots or embedded PDF metadata.",
    ]
    (OUT / "PROVENANCE.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")



def figure_unbounded_family():
    """The connected family: why the grouping is forced, and how the gap grows.

    Closed-form construction, not campaign data: |U| = 8g+1, K* = 3g,
    Z* = 8g-5, H = 9g-5.  Verified by exhaustive enumeration at g = 1, 2.
    """
    from matplotlib.patches import FancyBboxPatch

    fig, (left, right) = plt.subplots(
        1, 2, figsize=(12.6, 4.5), gridspec_kw={"width_ratios": [1.30, 1.0]}
    )

    # ---------------- left: why the grouping is forced ---------------------
    left.set_xlim(0, 10.2)
    left.set_ylim(0, 5.0)
    left.axis("off")

    def box(x, y, w, h, face, edge, label, sub, bold=False):
        left.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.10",
            facecolor=face, edgecolor=edge, linewidth=1.1, zorder=3))
        left.text(x + w / 2, y + h * 0.62, label, ha="center", va="center",
                  fontsize=11, fontweight="bold" if bold else "normal",
                  color=INK, zorder=4)
        left.text(x + w / 2, y + h * 0.24, sub, ha="center", va="center",
                  fontsize=8, color=MUTED, zorder=4)

    # the universal tool, spanning everything
    left.add_patch(FancyBboxPatch(
        (0.25, 3.86), 9.7, 0.52, boxstyle="round,pad=0.02,rounding_size=0.10",
        facecolor=PALE_BLUE, edgecolor=BLUE, linewidth=1.0, alpha=0.55, zorder=2))
    left.text(5.10, 4.12, "tool $u$  —  in every job, of every copy",
              ha="center", va="center", fontsize=9.5, color=INK, zorder=4)

    for k, (x0, mark, tick) in enumerate([(0.25, "$v_1$", ""), (5.30, "$v_2$", "'")]):
        # per-copy marker band
        left.add_patch(FancyBboxPatch(
            (x0, 3.20), 4.42, 0.46, boxstyle="round,pad=0.02,rounding_size=0.10",
            facecolor=PALE_ORANGE, edgecolor=ORANGE, linewidth=1.0, alpha=0.55, zorder=2))
        left.text(x0 + 2.21, 3.43, f"marker {mark}  —  in all four jobs of copy {k+1}",
                  ha="center", va="center", fontsize=8.5, color=INK, zorder=4)
        t = tick
        jobs = [(f"$A_{k+1}$", f"$1{t},2{t}$",       "white"),
                (f"$B_{k+1}$", f"$3{t},4{t}$",       "white"),
                (f"$C_{k+1}$", f"$1{t},3{t},5{t},6{t}$", "#E8EDF6"),
                (f"$D_{k+1}$", f"$2{t},5{t},6{t},7{t}$", "#E8EDF6")]
        for j, (lab, sub, face) in enumerate(jobs):
            box(x0 + j * 1.10, 2.28, 1.00, 0.78, face, BLUE, lab, sub)

        # the forced grouping, drawn as brackets
        for (xa, xb, txt) in [(x0, x0 + 2.10, "one group"),
                              (x0 + 2.20, x0 + 3.20, "alone"),
                              (x0 + 3.30, x0 + 4.30, "alone")]:
            left.plot([xa, xa, xb, xb], [2.10, 1.90, 1.90, 2.10],
                      color=PURPLE, linewidth=1.2, zorder=3)
            left.text((xa + xb) / 2, 1.62, txt, ha="center", va="center",
                      fontsize=8.5, color=PURPLE)

    left.text(10.05, 3.43, "$\cdots$  g copies", ha="right", va="center",
              fontsize=9, color=MUTED)

    left.text(0.25, 1.10,
              "$C_i$ and $D_i$ already fill all six slots, so each must sit alone.\n"
              "$A_i$ and $B_i$ together need exactly six — but $A_i$ with any job of\n"
              "another copy needs seven. The minimum grouping is forced and unique.",
              ha="left", va="top", fontsize=9, color=INK, linespacing=1.55)

    # ---------------- right: the gap grows without bound -------------------
    g = np.arange(1, 9)
    opt = 8 * g - 5
    heur = 9 * g - 5

    right.fill_between(g, opt, heur, color=CORAL, alpha=0.20, zorder=1,
                       label="the loss")
    right.plot(g, heur, "-o", color=CORAL, linewidth=2.2, markersize=5.5,
               zorder=3, label="what the heuristic returns,  $9g-5$")
    right.plot(g, opt, "-o", color=TEAL, linewidth=2.2, markersize=5.5,
               zorder=3, label="the true optimum,  $8g-5$")

    for gi in (4, 8):
        right.annotate("", xy=(gi, heur[gi - 1]), xytext=(gi, opt[gi - 1]),
                       arrowprops=dict(arrowstyle="<->", color=INK, linewidth=1.1))
        right.text(gi - 0.30, (heur[gi - 1] + opt[gi - 1]) / 2, f"gap {gi}",
                   ha="right", va="center", fontsize=9.5, fontweight="bold", color=INK,
                   bbox=dict(boxstyle="round,pad=0.16", facecolor="white",
                             edgecolor="none", alpha=0.85))

    right.set_xlabel("number of copies $g$")
    right.set_ylabel("tool insertions")
    right.set_xticks(g)
    right.set_xlim(0.6, 8.6)
    right.set_ylim(0, 72)
    right.set_title("The loss is exactly $g$, and never stops growing", pad=10)
    clean_axis(right, ygrid=True)
    right.legend(loc="upper left", frameon=False, fontsize=9.5)
    right.text(8.45, 5.0,
               "ratio $\\to 9/8$: unbounded loss,\nbut a constant factor survives",
               ha="right", va="bottom", fontsize=9, color=MUTED)

    fig.subplots_adjust(left=0.01, right=0.985, bottom=0.13, top=0.90, wspace=0.14)
    return save(
        fig,
        "unbounded_family",
        "Connected family with |U|=8g+1, K*=3g, Z*=8g-5, H=9g-5; verified at g=1,2.",
    )


def main():
    audit, bbc, instances, used = load_campaign()
    paths = [
        figure_solve_counts(bbc),
        figure_coverage_tightness(audit, bbc, instances, used),
        figure_root_bounds(bbc, used),
        figure_fractional_tradeoff(audit, bbc),
        figure_common_solved_times(audit, bbc),
        figure_unbounded_family(),
    ]
    write_provenance(paths)
    print("Generated audited vector figures:")
    for path in paths:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
