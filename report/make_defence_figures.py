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
    ax.set_yticks(y, ordered)
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
    ax.set_xticks(x, methods)
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

    solve_ax, node_ax, bound_ax = axes
    solve_bars = solve_ax.bar(methods, [724, 655], color=colors, width=0.62)
    solve_ax.set_title("Certified optima")
    solve_ax.set_ylabel("Instances (of 1,410)")
    solve_ax.set_ylim(0, 810)
    clean_axis(solve_ax, ygrid=True)
    for bar, value in zip(solve_bars, [724, 655]):
        solve_ax.text(bar.get_x() + bar.get_width() / 2, value + 18, str(value), ha="center", fontweight="bold")

    node_bars = node_ax.bar(methods, [77_439, 3_701], color=colors, width=0.62)
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
        "BBC-LP+F generated 67.0 million fractional cuts.  The +F regime also disables presolve.",
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
        tick_labels=display_order,
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
    for yi, median in enumerate(medians, 1):
        label = f"median {median:.3g}s"
        x = min(max(median * 1.35, 0.0018), 1_900)
        ax.text(x, yi - 0.26, label, fontsize=10.5, color=INK, va="center")
    ax.invert_yaxis()
    fig.subplots_adjust(left=0.18, right=0.99, bottom=0.13, top=0.90)
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


def main():
    audit, bbc, instances, used = load_campaign()
    paths = [
        figure_solve_counts(bbc),
        figure_coverage_tightness(audit, bbc, instances, used),
        figure_root_bounds(bbc, used),
        figure_fractional_tradeoff(audit, bbc),
        figure_common_solved_times(audit, bbc),
    ]
    write_provenance(paths)
    print("Generated audited vector figures:")
    for path in paths:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
