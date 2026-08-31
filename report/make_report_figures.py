#!/usr/bin/env python3
"""
make_report_figures.py -- colour vector figures for the report body.

Reads the audited data files in report/figdata/ (regenerated from the raw
campaign by report/make_figure_data.py) and emits vector PDFs into
report/assets/report_figures/.  No number is re-derived here: this script
only draws what make_figure_data.py already produced, so
`verification/analyse_campaign_results.py --check` remains the authority.

Palette and rcParams are imported from make_defence_figures so the report
and the slides look like one document.
"""
from pathlib import Path
import importlib.util
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIGDATA = HERE / "figdata"
OUT = HERE / "assets" / "report_figures"

# reuse the deck's palette and matplotlib settings
spec = importlib.util.spec_from_file_location("mdf", HERE / "make_defence_figures.py")
mdf = importlib.util.module_from_spec(spec)
sys.modules["mdf"] = mdf
spec.loader.exec_module(mdf)

INK, MUTED, GRID = mdf.INK, mdf.MUTED, mdf.GRID
BLUE, TEAL, ORANGE = mdf.BLUE, mdf.TEAL, mdf.ORANGE
CORAL, PURPLE, GREEN = mdf.CORAL, mdf.PURPLE, mdf.GREEN
PALE_BLUE, PALE_ORANGE = mdf.PALE_BLUE, mdf.PALE_ORANGE

# report figures sit in a 6.1in text block and are read at print size
matplotlib.rcParams.update({
    "font.size": 9, "axes.labelsize": 9.5, "axes.titlesize": 10,
    "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "legend.fontsize": 8.5,
})


def save(fig, stem, subject):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{stem}.pdf"
    fig.savefig(p, format="pdf", transparent=True, bbox_inches="tight",
                pad_inches=0.02,
                metadata={"Title": stem.replace("_", " ").title(),
                          "Author": "JGP-SSP report figure generator",
                          "Subject": subject})
    plt.close(fig)
    return p


def tidy(ax, ygrid=True):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK); ax.spines[s].set_linewidth(0.8)
    if ygrid:
        ax.yaxis.grid(True, color=GRID, lw=0.6)
        ax.set_axisbelow(True)


def fig_cactus():
    d = pd.read_csv(FIGDATA / "cactus.dat", sep=r"\s+")
    series = [("SSPMF", "SSPMF", BLUE, "-"), ("CATZF4", "CATZ-F4", TEAL, "-"),
              ("LSS", "LSS", GREEN, "-"), ("BBCLP", "BBC-LP", ORANGE, "--"),
              ("BBCK", "BBC-K", CORAL, "--"), ("BBCLPpF", "BBC-LP+F", PURPLE, ":")]
    fig, ax = plt.subplots(figsize=(6.1, 3.3))
    for col, lab, c, ls in series:
        ax.plot(d["t"], d[col], color=c, ls=ls, lw=1.6, label=lab)
    ax.set_xscale("log")
    ax.set_xlabel("wall-clock time (seconds, log scale)")
    ax.set_ylabel("instances closed")
    ax.set_xlim(d["t"].min(), 3600)
    ax.legend(frameon=False, ncol=2, loc="upper left", handlelength=2.1)
    tidy(ax)
    return save(fig, "cactus", "Instances closed against wall-clock time.")


def fig_tightsplit():
    d = pd.read_csv(FIGDATA / "solvedvsgap.dat", sep=r"\s+")
    labels = ["0", "1", "2", "3", "4", "5-6", "7-9", "10-14", "15+"]
    style = {"SSPMF": (BLUE, "o", "-"), "BBC-LP": (ORANGE, "s", "--"),
             "CATZ-F4": (TEAL, "^", ":")}
    fig, ax = plt.subplots(figsize=(6.1, 3.2))
    for cfg, (c, m, ls) in style.items():
        s = d[d["cfg"] == cfg].sort_values("x")
        if s.empty:
            continue
        ax.plot(s["x"], s["pct"], color=c, marker=m, ls=ls, lw=1.6, ms=4.5,
                label=f"{cfg}")
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels)
    ax.set_xlabel(r"how loose the coverage bound is  ($Z^*-q$)")
    ax.set_ylabel("instances closed (%)")
    ax.set_ylim(0, 108)
    ax.legend(frameon=False, loc="lower left")
    tidy(ax)
    return save(fig, "tightsplit", "Share closed against coverage-bound looseness.")


def fig_rootgap():
    d = pd.read_csv(FIGDATA / "rootgap.dat", sep=r"\s+")
    labels = ["0", "(0,1]", "(1,2]", "(2,4]", "(4,8]", "(8,16]", "(16,32]", ">32"]
    n = d["n"].tolist()
    labels = labels[:len(n)]
    colors = [BLUE] + [PALE_BLUE] * (len(n) - 1)
    fig, ax = plt.subplots(figsize=(6.1, 2.9))
    bars = ax.bar(range(len(n)), n, color=colors, edgecolor=INK, lw=0.6, width=0.68)
    for b, v in zip(bars, n):
        ax.text(b.get_x() + b.get_width() / 2, v + max(n) * 0.02, f"{v:,}",
                ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_xticks(range(len(n))); ax.set_xticklabels(labels)
    ax.set_xlabel("root relaxation above the coverage row")
    ax.set_ylabel("Benders runs")
    ax.set_ylim(0, max(n) * 1.14)
    tidy(ax)
    return save(fig, "rootgap", "Root relaxation above the coverage row.")


def fig_ceilings():
    d = pd.read_csv(FIGDATA / "ceilings.dat", sep=r"\s+")
    a = np.sort(d.iloc[:, 1].values)
    w = np.sort(d.iloc[:, 2].values)
    x = np.arange(1, len(a) + 1)
    fig, ax = plt.subplots(figsize=(6.1, 3.0))
    ax.plot(x, a, color=ORANGE, lw=1.8, label="fixed pairwise row + coverage")
    ax.fill_between(x, a, color=ORANGE, alpha=0.13)
    ax.plot(x, w, color=TEAL, lw=1.8, label="window family")
    ax.fill_between(x, w, color=TEAL, alpha=0.13)
    ax.set_xlabel("loose instances, each family sorted on its own values")
    ax.set_ylabel("share of the gap certifiable (%)")
    ax.set_xlim(1, len(a)); ax.set_ylim(0, max(w.max(), a.max()) * 1.1)
    ax.legend(frameon=False, loc="upper left")
    tidy(ax)
    return save(fig, "ceilings", "Per-family ceilings on the loose instances.")


def fig_landscape():
    d = pd.read_csv(FIGDATA / "landscape.dat", sep=r"\s+")
    meta = (FIGDATA / "landscape_meta.txt").read_text().split()
    q = int(meta[5]) if len(meta) > 5 else None
    zstar = int(d["cost"].min())
    fig, ax = plt.subplots(figsize=(6.1, 2.9))
    ax.bar(d["cost"], d["count"], color=PALE_BLUE, edgecolor=INK, lw=0.6, width=0.8)
    ax.bar([zstar], [int(d[d["cost"] == zstar]["count"].iloc[0])],
           color=BLUE, edgecolor=INK, lw=0.6, width=0.8)
    if q is not None and q < zstar:
        ax.axvline(q, color=CORAL, ls="--", lw=1.4)
        ax.annotate(f"coverage bound $q={q}$", xy=(q, d["count"].max() * 0.82),
                    xytext=(q + 0.6, d["count"].max() * 0.92), color=CORAL, fontsize=8.5,
                    arrowprops=dict(arrowstyle="->", color=CORAL, lw=1.1))
    ax.annotate(f"$Z^*={zstar}$", xy=(zstar, int(d[d['cost'] == zstar]['count'].iloc[0])),
                xytext=(zstar + 0.8, d["count"].max() * 0.55), color=BLUE, fontsize=8.5,
                arrowprops=dict(arrowstyle="->", color=BLUE, lw=1.1))
    ax.set_xlabel("cost of the ordering (tool insertions)")
    ax.set_ylabel("orderings")
    tidy(ax)
    return save(fig, "landscape", "Cost of every ordering of one instance.")


def main():
    paths = [fig_cactus(), fig_tightsplit(), fig_rootgap(), fig_ceilings(), fig_landscape()]
    (OUT / "PROVENANCE.txt").write_text(
        "Report figure provenance\n========================\n\n"
        "Drawn from report/figdata/*.dat, which report/make_figure_data.py\n"
        "regenerates from src/BBC/results/*.csv and the instance files.\n"
        "No value is computed here; this script only draws.\n"
        "Authority for every number: verification/analyse_campaign_results.py --check\n\n"
        + "".join(f"- {p.name}\n" for p in paths))
    print("Generated report figures:")
    for p in paths:
        print("  ", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
