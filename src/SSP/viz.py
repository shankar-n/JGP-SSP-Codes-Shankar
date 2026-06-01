"""
SSP Visualisation Library
=========================

All functions return a matplotlib Figure or plotly Figure.
**None of them call plt.show() or fig.show()** — the caller decides when
to display.  In a marimo notebook, assign the returned figure to the last
expression of a cell and marimo will render it automatically.

Public API
----------
plot_incidence_matrix(A, title)
    Heatmap of the T×J tool-job matrix with 0-block annotations.

plot_ktns_timeline(sequence, tool_req, cap, title, show_switches)
    Magazine-state heatmap produced by KTNS for a given job sequence.
    Required tools (dark blue), carried tools (light blue), empty (white),
    newly loaded (orange border).  Switch cost Δ annotated per step.

plot_jgp_ssp_comparison(ssp_sequence, jgp_batches, tool_req, cap)
    Side-by-side magazine timelines: left = JGP batches, right = SSP sequence.

plot_solution_comparison(solutions_dict, tool_req, cap)
    One KTNS timeline per solution in a shared multi-row figure.

plot_config_chain(sequence, tool_req, cap, title)
    Linear chain of magazine configurations with switch-cost annotations.

plot_bounds_bar(bounds_dict, title)
    Horizontal bar chart for bound / heuristic comparison.

plot_interactive_timeline(sequence, tool_req, cap, jgp_batches, title)
    Interactive Plotly timeline (magazine capacity + tool-loading heatmap).
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.colors import ListedColormap
import seaborn as sns

from heuristics import ktns_magazine_states

# ── Global style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family"    : "DejaVu Sans",
    "axes.titlesize" : 12,
    "axes.labelsize" : 10,
    "figure.dpi"     : 110,
})

_BLUE_DARK  = "#1a5fa8"   # required tool
_BLUE_LIGHT = "#90c4e8"   # carried tool (KTNS carry-over)
_ORANGE     = "#e87a1a"   # newly loaded (switch)
_EMPTY      = "#f4f4f4"   # empty magazine slot
_WHITE      = "#ffffff"
_RED        = "#d62728"
_GREEN      = "#2ca02c"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Incidence matrix
# ─────────────────────────────────────────────────────────────────────────────

def plot_incidence_matrix(A, title=None):
    """
    Heatmap of the tool-job incidence matrix (T×J) with 0-block annotations.

    Parameters
    ----------
    A     : ndarray (T, J)  – binary incidence matrix
    title : str | None

    Returns
    -------
    matplotlib Figure
    """
    from utils import detect_0blocks

    T, J      = A.shape
    title     = title or f"Tool-Job Incidence Matrix  ({T} tools × {J} jobs)"
    zero_blks = detect_0blocks(A)

    fig, ax = plt.subplots(figsize=(max(7, J * 0.65), max(4, T * 0.50)))

    cmap = ListedColormap([_EMPTY, _BLUE_DARK])
    ax.imshow(A, cmap=cmap, aspect="auto", vmin=0, vmax=1,
              interpolation="nearest")

    # Grid
    for x in range(J + 1):
        ax.axvline(x - 0.5, color=_WHITE, lw=1.2)
    for y in range(T + 1):
        ax.axhline(y - 0.5, color=_WHITE, lw=1.2)

    # Binary value labels (only for small matrices)
    if J <= 20 and T <= 20:
        for t in range(T):
            for j in range(J):
                ax.text(j, t, str(A[t, j]),
                        ha="center", va="center", fontsize=7,
                        color=_WHITE if A[t, j] else "#aaaaaa")

    # 0-block rectangles
    for t, spans in zero_blks.items():
        for (s, e) in spans:
            rect = mpatches.FancyBboxPatch(
                (s - 0.5, t - 0.5), e - s + 1, 1,
                boxstyle="round,pad=0.05",
                fill=False, edgecolor=_RED, lw=1.8, linestyle="--"
            )
            ax.add_patch(rect)

    ax.set_xticks(range(J))
    ax.set_xticklabels([f"$j_{{{j+1}}}$" for j in range(J)], fontsize=8)
    ax.set_yticks(range(T))
    ax.set_yticklabels([f"$t_{{{t+1}}}$" for t in range(T)], fontsize=8)
    ax.set_xlabel("Jobs", fontsize=10)
    ax.set_ylabel("Tools", fontsize=10)
    ax.set_title(title, fontsize=11, pad=8)

    # Density annotation
    density = A.mean()
    ax.text(0.99, 0.01, f"density = {density:.1%}",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=8, color="#555555")

    legend_handles = [
        mpatches.Patch(facecolor=_BLUE_DARK, label="Tool required ($A_{tj}=1$)"),
        mpatches.Patch(facecolor=_EMPTY, edgecolor="#bbbbbb",
                       label="Not required"),
        mpatches.Patch(facecolor="none", edgecolor=_RED,
                       linestyle="--", linewidth=2, label="0-block gap"),
    ]
    ax.legend(handles=legend_handles, loc="upper right",
              fontsize=8, framealpha=0.92)

    fig.tight_layout()
    return fig


# backward-compat alias
def plot_zero_blocks(num_jobs, num_tools, zero_blocks, A):
    """Backward-compatible wrapper — returns a figure (does NOT call plt.show)."""
    return plot_incidence_matrix(A)


# ─────────────────────────────────────────────────────────────────────────────
# 2. KTNS magazine timeline
# ─────────────────────────────────────────────────────────────────────────────

def plot_ktns_timeline(sequence, tool_req, cap, title=None, show_switches=True):
    """
    Magazine-state heatmap for a job sequence under the KTNS policy.

    Colour encoding (per cell in the T×N grid)
    -------------------------------------------
    Dark blue  — tool is in magazine AND required by the current job
    Light blue — tool is in magazine but only carried over (KTNS hold)
    Orange     — tool was just loaded at this step (counts as a switch)
    White      — magazine slot empty

    Parameters
    ----------
    sequence      : list[int]  – job indices (0-based)
    tool_req      : dict       – {job: [tool indices]} (0-based tools)
    cap           : int        – magazine capacity
    title         : str | None
    show_switches : bool       – annotate Δ (switch count) above each column

    Returns
    -------
    matplotlib Figure
    """
    if not sequence:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "Empty sequence", ha="center", va="center")
        return fig

    cost, in_mag, switches, req_mat = ktns_magazine_states(sequence, tool_req, cap)

    n_tools, n_steps = in_mag.shape
    title = title or f"KTNS Magazine Timeline  (total switches = {cost})"

    # Build colour matrix
    # 0=empty, 1=carried, 2=required, 3=newly-loaded+required
    col_mat = np.zeros((n_tools, n_steps), dtype=int)
    col_mat[in_mag & ~req_mat] = 1   # carried
    col_mat[in_mag &  req_mat] = 2   # required

    # Newly loaded = in_mag but NOT in_mag at previous step
    prev_mag = np.zeros((n_tools, n_steps), dtype=bool)
    prev_mag[:, 1:] = in_mag[:, :-1]
    newly_loaded = in_mag & ~prev_mag
    col_mat[newly_loaded & req_mat]  = 3   # loaded + required
    col_mat[newly_loaded & ~req_mat] = 3   # loaded + carried (shouldn't happen much)

    cmap4 = ListedColormap([_EMPTY, _BLUE_LIGHT, _BLUE_DARK, _ORANGE])

    fig_h = max(4, n_tools * 0.42 + 1.5)
    fig_w = max(7, n_steps * 0.65 + 1.5)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    im = ax.imshow(col_mat, cmap=cmap4, aspect="auto",
                   vmin=0, vmax=3, interpolation="nearest")

    # Grid
    for x in range(n_steps + 1):
        ax.axvline(x - 0.5, color=_WHITE, lw=1.0)
    for y in range(n_tools + 1):
        ax.axhline(y - 0.5, color=_WHITE, lw=1.0)

    # Column header: job label + switch cost
    ax.set_xticks(range(n_steps))
    col_labels = []
    for k, j in enumerate(sequence):
        lbl = f"$j_{{{j+1}}}$"
        if show_switches:
            lbl += f"\nΔ={switches[k]}"
        col_labels.append(lbl)
    ax.set_xticklabels(col_labels, fontsize=8, rotation=0)
    ax.set_xlabel("Job sequence (position → job, Δ = tools loaded)", fontsize=9)

    ax.set_yticks(range(n_tools))
    ax.set_yticklabels([f"$t_{{{t+1}}}$" for t in range(n_tools)], fontsize=8)
    ax.set_ylabel("Tool", fontsize=9)
    ax.set_title(f"{title}   [capacity = {cap}]", fontsize=11, pad=8)

    # Vertical orange lines at switch boundaries
    for k, sw in enumerate(switches[1:], start=1):
        if sw > 0:
            ax.axvline(k - 0.5, color=_ORANGE, lw=1.2, alpha=0.55)

    legend_handles = [
        mpatches.Patch(facecolor=_BLUE_DARK,  label="Required by job"),
        mpatches.Patch(facecolor=_BLUE_LIGHT, label="Carried (KTNS)"),
        mpatches.Patch(facecolor=_ORANGE,     label="Newly loaded (switch)"),
        mpatches.Patch(facecolor=_EMPTY, edgecolor="#bbbbbb", label="Empty slot"),
    ]
    ax.legend(handles=legend_handles, loc="lower right",
              fontsize=8, framealpha=0.92, ncol=2)

    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 3. JGP vs SSP side-by-side comparison
# ─────────────────────────────────────────────────────────────────────────────

def plot_jgp_ssp_comparison(ssp_sequence, jgp_batches, tool_req, cap):
    """
    Side-by-side KTNS timelines: JGP batch sequence vs SSP optimised sequence.

    Left panel — JGP: jobs flattened from batches (ordered by |T_j| desc
                 within each batch), batch boundaries marked with red lines.
    Right panel — SSP: the provided sequence.

    Parameters
    ----------
    ssp_sequence : list[int]         – optimal/heuristic SSP sequence
    jgp_batches  : list of (jobs, tools) – JGP solution
    tool_req     : dict
    cap          : int

    Returns
    -------
    matplotlib Figure
    """
    from heuristics import warmstart_from_jgp

    jgp_cost, jgp_seq = warmstart_from_jgp(jgp_batches, tool_req, cap)
    ssp_cost, ssp_in_mag, ssp_sw, ssp_req = ktns_magazine_states(
        ssp_sequence, tool_req, cap)
    jgp_cost2, jgp_in_mag, jgp_sw, jgp_req = ktns_magazine_states(
        jgp_seq, tool_req, cap)

    n_tools = ssp_in_mag.shape[0]

    def _build_col_mat(in_mag, req_mat, sw):
        col = np.zeros_like(in_mag, dtype=int)
        col[in_mag & ~req_mat] = 1
        col[in_mag &  req_mat] = 2
        prev = np.zeros_like(in_mag)
        prev[:, 1:] = in_mag[:, :-1]
        col[in_mag & ~prev] = 3
        return col

    cmap4 = ListedColormap([_EMPTY, _BLUE_LIGHT, _BLUE_DARK, _ORANGE])
    fig, axes = plt.subplots(1, 2, figsize=(
        max(14, (jgp_in_mag.shape[1] + ssp_in_mag.shape[1]) * 0.55 + 3),
        max(5,  n_tools * 0.42 + 2)
    ))

    for ax, in_mag, req_mat, sw, seq, title, cost, batches in [
        (axes[0], jgp_in_mag, jgp_req, jgp_sw, jgp_seq,
         "JGP Sequence (warm-start)", jgp_cost2, jgp_batches),
        (axes[1], ssp_in_mag, ssp_req, ssp_sw, ssp_sequence,
         "SSP Optimal Sequence", ssp_cost, None),
    ]:
        col = _build_col_mat(in_mag, req_mat, sw)
        ax.imshow(col, cmap=cmap4, aspect="auto", vmin=0, vmax=3,
                  interpolation="nearest")

        for x in range(col.shape[1] + 1):
            ax.axvline(x - 0.5, color=_WHITE, lw=0.8)
        for y in range(n_tools + 1):
            ax.axhline(y - 0.5, color=_WHITE, lw=0.8)

        ax.set_xticks(range(len(seq)))
        ax.set_xticklabels(
            [f"$j_{{{j+1}}}$\nΔ={sw[k]}" for k, j in enumerate(seq)],
            fontsize=7, rotation=0
        )
        ax.set_yticks(range(n_tools))
        ax.set_yticklabels([f"$t_{{{t+1}}}$" for t in range(n_tools)],
                           fontsize=7)
        ax.set_title(f"{title}\n(total switches = {cost})", fontsize=10,
                     fontweight="bold")
        ax.set_xlabel("Job sequence", fontsize=9)

        # Batch boundaries (JGP only)
        if batches:
            pos = 0
            for bidx, (jobs, _) in enumerate(batches):
                if bidx > 0:
                    ax.axvline(pos - 0.5, color=_RED, lw=2.2, linestyle="--")
                pos += len(jobs)

    legend_handles = [
        mpatches.Patch(facecolor=_BLUE_DARK,  label="Required"),
        mpatches.Patch(facecolor=_BLUE_LIGHT, label="Carried (KTNS)"),
        mpatches.Patch(facecolor=_ORANGE,     label="Newly loaded"),
        mpatches.Patch(facecolor=_EMPTY, edgecolor="#aaa", label="Empty"),
    ]
    fig.legend(handles=legend_handles, loc="lower center",
               ncol=4, fontsize=8, bbox_to_anchor=(0.5, -0.04))
    fig.suptitle(
        f"Magazine Timeline: JGP (Δ={jgp_cost2}) vs SSP (Δ={ssp_cost})  "
        f"[capacity={cap}]",
        fontsize=11, y=1.02
    )
    fig.tight_layout()
    return fig


# backward-compat: old signature was (route, batches, n_tools, cap)
def plot_magazine_timeline(ssp_route_or_sequence, jgp_batches, tool_req_or_n_tools, cap):
    """
    Backward-compatible wrapper.

    Accepts either:
      - new API: (ssp_sequence:list[int], jgp_batches, tool_req:dict, cap)
      - old API: (ssp_route:list[tuple], jgp_batches, n_tools:int, cap)
        where ssp_route = [(cfg_tuple, job), …] from the GTSP solver.
    """
    if isinstance(tool_req_or_n_tools, dict):
        # New API
        return plot_jgp_ssp_comparison(
            ssp_route_or_sequence, jgp_batches, tool_req_or_n_tools, cap)
    else:
        # Old API: extract sequence from GTSP route
        route = ssp_route_or_sequence
        seq   = [j for (cfg, j) in route if cfg != "DUMMY"]
        # Reconstruct tool_req from the route configs
        # (we can't do this without T_j, so fall back to just SSP timeline)
        print("Warning: plot_magazine_timeline called with old route format — "
              "JGP panel will be omitted.  Pass tool_req dict for full plot.")
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5,
                "Re-call with (sequence, jgp_batches, tool_req, cap)\n"
                "to see the full comparison.",
                ha="center", va="center", fontsize=11)
        ax.axis("off")
        return fig


# ─────────────────────────────────────────────────────────────────────────────
# 4. Multi-solution comparison
# ─────────────────────────────────────────────────────────────────────────────

def plot_solution_comparison(solutions_dict, tool_req, cap):
    """
    Vertically stacked KTNS timelines for multiple solutions.

    Parameters
    ----------
    solutions_dict : dict {label: sequence}
                     e.g. {"BBC": [2,0,1,3], "FFD": [0,2,1,3]}
    tool_req : dict
    cap      : int

    Returns
    -------
    matplotlib Figure
    """
    labels    = list(solutions_dict.keys())
    sequences = list(solutions_dict.values())
    n         = len(labels)

    if n == 0:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No solutions provided", ha="center", va="center")
        return fig

    n_tools = max(t for tools in tool_req.values() for t in tools) + 1
    cmap4   = ListedColormap([_EMPTY, _BLUE_LIGHT, _BLUE_DARK, _ORANGE])

    max_steps = max(len(s) for s in sequences)
    fig_h = max(5, n * (n_tools * 0.38 + 1.2) + 0.5)
    fig_w = max(8, max_steps * 0.60 + 2)

    fig, axes = plt.subplots(n, 1, figsize=(fig_w, fig_h),
                             sharex=False, squeeze=False)

    for row, (lbl, seq) in enumerate(zip(labels, sequences)):
        ax = axes[row, 0]
        if not seq:
            ax.text(0.5, 0.5, f"{lbl}: no solution", ha="center", va="center")
            ax.axis("off")
            continue

        cost, in_mag, sw, req_mat = ktns_magazine_states(seq, tool_req, cap)

        col = _build_col_mat(in_mag, req_mat)

        ax.imshow(col, cmap=cmap4, aspect="auto", vmin=0, vmax=3,
                  interpolation="nearest")

        for x in range(len(seq) + 1): ax.axvline(x - 0.5, color=_WHITE, lw=0.7)
        for y in range(n_tools + 1):  ax.axhline(y - 0.5, color=_WHITE, lw=0.7)

        ax.set_xticks(range(len(seq)))
        ax.set_xticklabels(
            [f"$j_{{{j+1}}}$\nΔ{sw[k]}" for k, j in enumerate(seq)], fontsize=7
        )
        ax.set_yticks(range(n_tools))
        ax.set_yticklabels([f"$t_{{{t+1}}}$" for t in range(n_tools)], fontsize=7)
        ax.set_ylabel(lbl, fontsize=9, fontweight="bold", rotation=0,
                      labelpad=40, va="center")
        ax.set_title(f"{lbl}  (Δ = {cost})", fontsize=10, loc="left")

    legend_handles = [
        mpatches.Patch(facecolor=_BLUE_DARK,  label="Required"),
        mpatches.Patch(facecolor=_BLUE_LIGHT, label="Carried (KTNS)"),
        mpatches.Patch(facecolor=_ORANGE,     label="Newly loaded"),
        mpatches.Patch(facecolor=_EMPTY, edgecolor="#aaa", label="Empty"),
    ]
    fig.legend(handles=legend_handles, loc="lower center",
               ncol=4, fontsize=8, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle(f"Solution Comparison  [capacity = {cap}]",
                 fontsize=12, y=1.01)
    fig.tight_layout(h_pad=0.6)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 5. Configuration-chain diagram
# ─────────────────────────────────────────────────────────────────────────────

def plot_config_chain(sequence, tool_req, cap, title=None):
    """
    Linear chain of magazine configurations with switch-cost annotations.

    Each node is a box showing the magazine content at one sequence position.
    Arrows are coloured by switch cost:
      green (Δ=0), yellow (small), red (large).

    Parameters
    ----------
    sequence : list[int]
    tool_req : dict
    cap      : int
    title    : str | None

    Returns
    -------
    matplotlib Figure
    """
    cost, in_mag, switches, _ = ktns_magazine_states(sequence, tool_req, cap)
    n_steps = len(sequence)
    n_tools = in_mag.shape[0]

    # Build config strings
    configs = []
    for k in range(n_steps):
        loaded = sorted(t + 1 for t in range(n_tools) if in_mag[t, k])
        configs.append(loaded)

    fig_w = max(10, n_steps * 1.9 + 1)
    fig, ax = plt.subplots(figsize=(fig_w, 3.5))
    ax.axis("off")
    ax.set_xlim(-0.5, n_steps - 0.5)
    ax.set_ylim(-0.5, 1.5)

    max_sw = max(switches[1:] + [1]) if n_steps > 1 else 1

    for k in range(n_steps):
        x = k
        job  = sequence[k]
        cfg  = configs[k]
        sw   = switches[k]

        # Box colour by switch cost
        if k == 0 or sw == 0:
            box_color = "#d4edda"
        elif sw / max_sw < 0.4:
            box_color = "#fff3cd"
        else:
            box_color = "#f8d7da"

        rect = mpatches.FancyBboxPatch(
            (x - 0.42, 0.2), 0.84, 1.0,
            boxstyle="round,pad=0.05",
            facecolor=box_color, edgecolor="#555", linewidth=1.4
        )
        ax.add_patch(rect)

        # Job label (top)
        ax.text(x, 1.35, f"$j_{{{job+1}}}$",
                ha="center", va="center", fontsize=9, fontweight="bold")

        # Config content
        cfg_str = "{" + ",".join(str(t) for t in cfg) + "}"
        ax.text(x, 0.70, cfg_str,
                ha="center", va="center", fontsize=7.5,
                color="#1a1a1a")

        # Switch cost label (bottom of box)
        if k > 0:
            ax.text(x, 0.32, f"Δ={sw}",
                    ha="center", va="center", fontsize=7,
                    color=_RED if sw > 0 else _GREEN)

        # Arrow
        if k < n_steps - 1:
            sw_next = switches[k + 1]
            intensity = sw_next / max(max_sw, 1)
            arrow_color = (intensity * 0.85, (1 - intensity) * 0.65, 0.1)
            ax.annotate(
                "", xy=(k + 0.58, 0.70), xytext=(k + 0.42, 0.70),
                arrowprops=dict(arrowstyle="->", color=arrow_color,
                                lw=1.5 + 2.5 * intensity)
            )

    ax.set_title(
        (title or f"Configuration Chain  (total Δ = {cost}, capacity = {cap})"),
        fontsize=11, pad=10
    )
    fig.tight_layout()
    return fig


# backward-compat
def plot_active_config_network(ssp_route_or_sequence, cap, tool_req=None):
    """
    Backward-compatible wrapper for plot_config_chain.

    Accepts old GTSP route format [(cfg, job), …] or new list[int] sequence.
    """
    if isinstance(ssp_route_or_sequence, list) and ssp_route_or_sequence \
            and isinstance(ssp_route_or_sequence[0], (list, tuple)) \
            and len(ssp_route_or_sequence[0]) == 2 \
            and isinstance(ssp_route_or_sequence[0][0], (tuple, str)):
        # Old format: [(cfg_tuple, job_idx), …]
        route = ssp_route_or_sequence
        seq   = [j for (cfg, j) in route if cfg != "DUMMY"]
        # Reconstruct tool_req from route configs
        tr = {}
        for (cfg, j) in route:
            if cfg != "DUMMY":
                tr[j] = list(cfg)
        return plot_config_chain(seq, tr, cap)
    else:
        # New format: list of job indices — needs tool_req
        if tool_req is None:
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5,
                    "Pass tool_req dict to plot_config_chain(sequence, tool_req, cap)",
                    ha="center", va="center")
            ax.axis("off")
            return fig
        return plot_config_chain(ssp_route_or_sequence, tool_req, cap)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Bounds bar chart
# ─────────────────────────────────────────────────────────────────────────────

def plot_bounds_bar(bounds_dict, title="Bound / Heuristic Comparison"):
    """
    Horizontal bar chart comparing bounds and heuristic costs.

    Parameters
    ----------
    bounds_dict : dict {label: value}
                  Special labels:
                    '(LB)'  → rendered green
                    '(OPT)' → rendered blue
                    '(UB)'  or anything else → rendered orange/red gradient

    Returns
    -------
    matplotlib Figure
    """
    labels = [k for k, v in bounds_dict.items() if v is not None]
    values = [bounds_dict[k] for k in labels]

    if not labels:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return fig

    def _color(lbl):
        if "(LB)" in lbl:  return _GREEN
        if "(OPT)" in lbl: return _BLUE_DARK
        return "#e07b39"

    colors = [_color(lbl) for lbl in labels]
    fig, ax = plt.subplots(figsize=(8, max(3, len(labels) * 0.62 + 1)))

    bars = ax.barh(labels, values, color=colors, edgecolor="#333",
                   linewidth=0.8, height=0.55)

    max_val = max(v for v in values if v is not None)
    for bar, val in zip(bars, values):
        ax.text(val + max_val * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}", va="center", fontsize=9, fontweight="bold")

    # Vertical lines for LB and OPT
    for lbl, val in zip(labels, values):
        if "(LB)" in lbl:
            ax.axvline(val, color=_GREEN, lw=1.5, linestyle="--", alpha=0.6)
        if "(OPT)" in lbl:
            ax.axvline(val, color=_BLUE_DARK, lw=1.5, linestyle="--", alpha=0.6)

    # Gap annotation between LB and best UB
    lb_vals  = [v for l, v in zip(labels, values) if "(LB)" in l]
    opt_vals = [v for l, v in zip(labels, values) if "(OPT)" in l]
    ub_vals  = [v for l, v in zip(labels, values)
                if "(LB)" not in l and "(OPT)" not in l]

    if lb_vals and ub_vals:
        lb_val = max(lb_vals)
        ub_val = min(ub_vals)
        gap    = 100 * (ub_val - lb_val) / max(lb_val, 1)
        ax.annotate(
            f"gap = {gap:.1f}%",
            xy=(lb_val, 0), xytext=(lb_val + (ub_val - lb_val) / 2, -0.6),
            arrowprops=None, fontsize=8, color="#555", ha="center"
        )

    ax.set_xlabel("Tool switches", fontsize=10)
    ax.set_title(title, fontsize=11)
    ax.set_xlim(0, max_val * 1.15)
    ax.grid(axis="x", alpha=0.3, linestyle="--")
    ax.invert_yaxis()

    legend_handles = [
        mpatches.Patch(facecolor=_GREEN,     label="Lower bound (LB)"),
        mpatches.Patch(facecolor=_BLUE_DARK, label="Exact optimum (OPT)"),
        mpatches.Patch(facecolor="#e07b39",  label="Upper bound / heuristic"),
    ]
    ax.legend(handles=legend_handles, fontsize=8, loc="lower right",
              framealpha=0.9)

    fig.tight_layout()
    return fig


# removed: plot_timedep_costs — not grounded in SSP literature.
# (The SSP switch cost is a fixed integer per magazine transition,
#  not a time-dependent quantity.)
def plot_timedep_costs(sequence, tool_req, cap, tau_values=None):
    """Stub: time-dependent costs are not part of the standard SSP model."""
    import warnings
    warnings.warn(
        "plot_timedep_costs: time-dependent switch cost is not in the SSP "
        "literature.  Returning a KTNS timeline instead.",
        stacklevel=2
    )
    return plot_ktns_timeline(sequence, tool_req, cap,
                              title="KTNS Timeline (replacing time-dep. plot)")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Interactive Plotly timeline
# ─────────────────────────────────────────────────────────────────────────────

def plot_interactive_timeline(sequence, tool_req, cap,
                               jgp_batches=None,
                               title="Interactive SSP Magazine Timeline"):
    """
    Interactive Plotly timeline with two panels:
      Top    – magazine occupancy count vs capacity limit
      Bottom – tool-loading heatmap (required / carried / newly loaded)

    Parameters
    ----------
    sequence     : list[int]  – job sequence (0-based)
    tool_req     : dict       – {job: [tools]}
    cap          : int
    jgp_batches  : list | None  – draw batch boundaries if provided
    title        : str

    Returns
    -------
    plotly.graph_objects.Figure
    """
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        print("plotly not installed — run: pip install plotly")
        return None

    if not sequence:
        return go.Figure()

    cost, in_mag, switches, req_mat = ktns_magazine_states(sequence, tool_req, cap)
    n_tools, n_steps = in_mag.shape
    all_tools        = list(range(n_tools))

    x_steps = list(range(1, n_steps + 1))

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.06, row_heights=[0.22, 0.78],
        subplot_titles=["Magazine Occupancy", "Tool Loading (per step)"]
    )

    # ── Top: occupancy line ──────────────────────────────────────────────────
    occupancy = in_mag.sum(axis=0).tolist()
    fig.add_trace(go.Scatter(
        x=x_steps, y=occupancy,
        mode="lines+markers", name="Tools in magazine",
        line=dict(color=_BLUE_DARK, width=2),
        marker=dict(size=7),
        hovertemplate="Step %{x}<br>Loaded: %{y}<extra></extra>"
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=[1, n_steps], y=[cap, cap],
        mode="lines", name=f"Capacity (c={cap})",
        line=dict(color=_RED, width=2, dash="dash"),
        hoverinfo="skip"
    ), row=1, col=1)

    # Switch cost bar (secondary y via a bar trace)
    fig.add_trace(go.Bar(
        x=x_steps, y=switches,
        name="Δ (tools loaded)",
        marker_color=[_ORANGE if s > 0 else _GREEN for s in switches],
        opacity=0.55,
        hovertemplate="Step %{x}<br>Δ = %{y}<extra></extra>"
    ), row=1, col=1)

    # ── Bottom: heatmap ──────────────────────────────────────────────────────
    req_x, req_y, req_txt      = [], [], []
    carry_x, carry_y, carry_txt = [], [], []
    new_x, new_y, new_txt      = [], [], []

    prev_mag = set()
    for k, job in enumerate(sequence):
        step     = k + 1
        required = set(tool_req[job])
        loaded   = set(t for t in range(n_tools) if in_mag[t, k])
        newly    = loaded - prev_mag

        for t in loaded:
            tip = (f"Step {step} · Job j{job+1} · Tool t{t+1}<br>"
                   f"Status: ")
            if t in newly:
                new_x.append(step); new_y.append(t + 1)
                new_txt.append(tip + "<b>Newly loaded (switch)</b>")
            elif t in required:
                req_x.append(step); req_y.append(t + 1)
                req_txt.append(tip + "<b>Required</b>")
            else:
                carry_x.append(step); carry_y.append(t + 1)
                carry_txt.append(tip + "<i>Carried (KTNS)</i>")
        prev_mag = loaded

    _sym  = dict(symbol="square", size=22)
    fig.add_trace(go.Scatter(
        x=new_x,   y=new_y,   mode="markers", name="Newly loaded",
        marker=dict(**_sym, color=_ORANGE,     line=dict(width=1, color="#555")),
        text=new_txt,   hoverinfo="text"
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=req_x,   y=req_y,   mode="markers", name="Required",
        marker=dict(**_sym, color=_BLUE_DARK,  line=dict(width=1, color="#222")),
        text=req_txt,   hoverinfo="text"
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=carry_x, y=carry_y, mode="markers", name="Carried (KTNS)",
        marker=dict(**_sym, color=_BLUE_LIGHT, opacity=0.75),
        text=carry_txt, hoverinfo="text"
    ), row=2, col=1)

    # JGP batch boundaries
    if jgp_batches:
        pos = 1
        for bidx, (jobs, _) in enumerate(jgp_batches):
            if bidx > 0:
                for row in [1, 2]:
                    fig.add_vline(x=pos + 0.5, line_width=2,
                                  line_dash="dash", line_color=_GREEN,
                                  row=row, col=1)
            pos += len(jobs)

    # Layout
    x_labels = [f"Step {k+1}<br>j{sequence[k]+1}" for k in range(n_steps)]
    fig.update_layout(
        title=f"{title}   (Δ_total = {cost}, capacity = {cap})",
        xaxis2=dict(tickmode="array", tickvals=x_steps,
                    ticktext=x_labels, title="Sequence position"),
        yaxis=dict(title="Count", range=[0, cap + 1]),
        yaxis2=dict(title="Tool",
                    tickmode="array",
                    tickvals=list(range(1, n_tools + 1)),
                    ticktext=[f"t{t+1}" for t in range(n_tools)]),
        plot_bgcolor="white",
        hovermode="closest",
        height=680,
        legend=dict(orientation="h", y=-0.15)
    )
    return fig


# backward-compat alias for old visualize_ssp_jgp_solution signature
def visualize_ssp_jgp_solution(job_sequence, T_j, magazine_states=None,
                                b=None, jgp_batches=None,
                                title="Interactive SSP/JGP Configuration"):
    """
    Backward-compatible wrapper for plot_interactive_timeline.

    Old signature: (job_sequence, T_j, magazine_states, b, jgp_batches)
    New signature: (sequence, tool_req, cap)

    If magazine_states is provided it is ignored (recomputed from KTNS).
    """
    cap = b if b is not None else (len(magazine_states[0]) if magazine_states else 4)
    return plot_interactive_timeline(job_sequence, T_j, cap,
                                     jgp_batches=jgp_batches, title=title)


# ─────────────────────────────────────────────────────────────────────────────
# 3-D config-space functions (kept for interactive exploration)
# ─────────────────────────────────────────────────────────────────────────────

def embed_configurations_3d(configurations, capacity):
    """MDS embedding of configurations into 3D via switch-cost distance matrix."""
    from utils import compute_switch_cost
    n = len(configurations)
    D = np.array([[compute_switch_cost(configurations[i], configurations[j], capacity)
                   for j in range(n)] for i in range(n)], dtype=float)
    H = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * H @ (D ** 2) @ H
    eigvals, eigvecs = np.linalg.eigh(B)
    idx    = np.argsort(eigvals)[::-1][:3]
    coords = eigvecs[:, idx] * np.sqrt(np.maximum(eigvals[idx], 0))
    return coords


def visualize_3d(configurations, coords, hyperedges, capacity,
                 solutions=None, show_edges=False, edge_threshold=1):
    """3-D scatter of configuration space with job hyperedges (Plotly)."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("plotly not installed"); return None
    from utils import compute_switch_cost

    x, y, z = coords[:, 0], coords[:, 1], coords[:, 2]
    coverage = [sum(1 for nodes in hyperedges.values() if i in nodes)
                for i in range(len(configurations))]
    max_cov  = max(coverage) if max(coverage) > 0 else 1
    sizes    = [6 + 10 * (c / max_cov) for c in coverage]
    colors   = [c / max_cov for c in coverage]

    fig = go.Figure()
    fig.add_trace(go.Scatter3d(
        x=x, y=y, z=z, mode="markers+text",
        text=[f"{configurations[i]}<br>({coverage[i]})" for i in range(len(configurations))],
        textposition="top center",
        marker=dict(size=sizes, color=colors, colorscale="Viridis",
                    colorbar=dict(title="#Jobs"), opacity=0.9),
        name="Configurations"
    ))

    for j, nodes in hyperedges.items():
        kw = dict(name=f"Job {j}", hoverinfo="name")
        if len(nodes) >= 3:
            fig.add_trace(go.Mesh3d(
                x=[x[i] for i in nodes], y=[y[i] for i in nodes],
                z=[z[i] for i in nodes], opacity=0.08, **kw))
        elif len(nodes) == 2:
            fig.add_trace(go.Scatter3d(
                x=[x[nodes[0]], x[nodes[1]]],
                y=[y[nodes[0]], y[nodes[1]]],
                z=[z[nodes[0]], z[nodes[1]]],
                mode="lines", line=dict(width=4), **kw))

    if solutions:
        cfg_idx = {tuple(c): i for i, c in enumerate(configurations)}
        for si, sol in enumerate(solutions):
            px, py, pz = [], [], []
            for (_, c1), (_, c2) in zip(sol[:-1], sol[1:]):
                i1, i2 = cfg_idx[tuple(c1)], cfg_idx[tuple(c2)]
                px += [x[i1], x[i2], None]
                py += [y[i1], y[i2], None]
                pz += [z[i1], z[i2], None]
            fig.add_trace(go.Scatter3d(
                x=px, y=py, z=pz, mode="lines",
                line=dict(width=5), name=f"Solution {si+1}"))

    fig.update_layout(
        title="3D Configuration Space",
        scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False),
                   zaxis=dict(visible=False)),
        margin=dict(l=0, r=0, b=60, t=40)
    )
    return fig
