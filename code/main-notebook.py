# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo>=0.8.0",
#     "numpy",
#     "pandas",
#     "matplotlib",
#     "seaborn",
#     "networkx",
#     "pyscipopt",
# ]
# ///

import marimo

__generated_with = "0.23.0"
app = marimo.App(width="medium")


@app.cell
def _():
    """Cell 1: Imports."""
    import numpy as np
    import pandas as pd
    import marimo as mo
    import matplotlib.pyplot as plt
    import itertools
    from utils import load_ssp_instance, detect_0blocks, compute_switch_cost, compute_ssp_cost, compute_ktns, run_brute_force_TSP_on_configs
    from viz import plot_zero_blocks, plot_magazine_timeline, plot_active_config_network, plot_timedep_costs
    from SCIP_formulation_solvers import solve_jgp_arf, solve_ssp_gtsp
    from solution_validators import validate_jgp, validate_ssp
    from porta import run_jgp_porta, read_porta_output, run_ssp_porta, convert_ieq_to_ine
    from concorde_util import solve_hamiltonian_path
    import subprocess
    import os
    import tempfile
    import ortools
    from tqdm import tqdm

    return (
        compute_ktns,
        compute_ssp_cost,
        detect_0blocks,
        itertools,
        load_ssp_instance,
        mo,
        np,
        pd,
        plot_active_config_network,
        plot_magazine_timeline,
        plot_timedep_costs,
        plot_zero_blocks,
        plt,
        read_porta_output,
        run_brute_force_TSP_on_configs,
        run_ssp_porta,
        solve_hamiltonian_path,
        solve_jgp_arf,
        solve_ssp_gtsp,
        tqdm,
        validate_jgp,
        validate_ssp,
    )


@app.cell
def _(itertools, load_ssp_instance, np):
    """Cell 2: File loading and preprocessing."""

    # ── Adjust these two paths to switch instances ──────────────────────────
    INSTANCES_PTH   = './Instances/From_Felipe/data/'
    SAMPLE_INSTANCE = 'Catanzaro/Tabela1C/A0-0.txt'
    # ────────────────────────────────────────────────────────────────────────

    filepath = INSTANCES_PTH + SAMPLE_INSTANCE
    filepath = './Instances/shankar-example.txt'
    J, T_dim, C, A, T_j = load_ssp_instance(filepath)

    num_jobs  = J
    num_tools = T_dim
    b         = C                # magazine capacity
    matrix    = A
    T_j = T_j

    all_configs = np.array(list(itertools.combinations(range(num_tools), b)))

    print(f"Instance loaded: {filepath}")
    print(f"  Jobs={num_jobs}, Tools={num_tools}, Capacity={b}")
    print(f"  Config space size: C({num_tools},{b}) = "
          f"{len(all_configs)}")
    return A, T_j, all_configs, b, num_jobs, num_tools


@app.cell
def _(A, mo, num_jobs, num_tools, pd):
    """Cell 3: Display styled incidence matrix."""
    row_names = [f"t{t+1}" for t in range(num_tools)]
    col_names = [f"j{j+1}" for j in range(num_jobs)]

    df_inc = pd.DataFrame(A, index=row_names, columns=col_names)
    styled_inc = df_inc.style.map(
        lambda v: "background-color:#4682B4; color:white; font-weight:bold"
                  if v == 1 else "color:#cccccc"
    ).set_caption(f"Incidence Matrix  ({num_tools} tools × {num_jobs} jobs)")

    mo.ui.table(df_inc, label="Incidence Matrix")
    return


@app.cell
def _(A, detect_0blocks, num_jobs, num_tools, plot_zero_blocks):
    """Cell 4: Visualization 1 — Incidence matrix with 0-block annotations."""

    zero_blocks = detect_0blocks(A)
    plot_zero_blocks(num_jobs, num_tools,zero_blocks,A)
    return


@app.cell
def _(T_j, b, num_jobs, num_tools, solve_jgp_arf):
    """Cell 5: JGP ARF Solver (Felipe / Catanzaro formulation)."""

    jgp_obj, jgp_batches = solve_jgp_arf(num_jobs, num_tools, b, T_j)
    print(f"JGP optimum: {jgp_obj} batches")
    for idx, (jobs, tools) in enumerate(jgp_batches):
        print(f"  Batch {idx+1}: jobs={[j+1 for j in jobs]}  "
              f"tools={[t+1 for t in tools]}")
    return jgp_batches, jgp_obj


@app.cell
def _(T_j, b, num_jobs, num_tools, solve_ssp_gtsp):
    """Cell 6: SSP solver via GTSP with I-N transformation."""

    ssp_obj, ssp_route = solve_ssp_gtsp(num_jobs, num_tools, b, T_j)
    return ssp_obj, ssp_route


@app.cell
def _(
    T_j,
    b,
    compute_ssp_cost,
    jgp_batches,
    num_jobs,
    ssp_obj,
    ssp_route,
    validate_jgp,
    validate_ssp,
):
    """Cell 7: Solution validators."""
    try:
        validate_jgp(jgp_batches, num_jobs, b, T_j)
        print("✓ JGP solution is feasible")
    except Exception as e:
        print(f"✗ JGP validation FAILED: {e}")

    try:
        if ssp_route:
            validate_ssp(ssp_route, num_jobs, b, T_j)
            recomputed = compute_ssp_cost(ssp_route, b)
            match = "✓" if abs(recomputed - ssp_obj) < 1e-4 else "✗"
            print(f"✓ SSP solution is feasible")
            print(f"{match} SSP cost recomputed={recomputed}  "
                  f"solver reported={ssp_obj}")
        else:
            print("⚠ SSP route is empty — solver may have failed")
    except Exception as e:
        print(f"✗ SSP validation FAILED: {e}")
    return


@app.cell
def _(T_j, b, compute_ktns, jgp_batches, num_jobs):
    """Cell 8: Upper bound computations."""

    def compute_warmstart_ub(batches, tool_req, cap, n_jobs):
        """
        Upper bound by flattening JGP batches into a sequence and
        computing its KTNS cost.
        """
        if not batches:
            return float('inf')
        sequence = []
        for (jobs, _tools) in batches:
            # Order within batch: descending tool-requirement size
            # (promotes tool reuse within batch)
            sequence.extend(sorted(jobs, key=lambda j: len(tool_req[j]),
                                   reverse=True))
        return compute_ktns(sequence, tool_req, cap)[0], sequence

    def compute_greedy_ffd_ub(n_jobs, tool_req, cap):
        """
        Upper bound via First-Fit Decreasing (FFD) heuristic.
        Sort jobs by decreasing |T_j|; greedily sequence them.
        """
        order = sorted(range(n_jobs), key=lambda j: len(tool_req[j]),
                       reverse=True)
        return compute_ktns(order, tool_req, cap)[0], order

    def apply_2opt_improvement(sequence, tool_req, cap, max_iter=200):
        """
        2-Opt local search: try all adjacent job swaps; accept if cost
        decreases.  Returns improved sequence and its cost.
        """
        seq = list(sequence)
        current_cost = compute_ktns(seq, tool_req, cap)[0]
        improved = True
        iters = 0
        while improved and iters < max_iter:
            improved = False
            iters += 1
            for k in range(len(seq) - 1):
                # Swap positions k and k+1
                seq[k], seq[k+1] = seq[k+1], seq[k]
                new_cost = compute_ktns(seq, tool_req, cap)[0]
                if new_cost < current_cost:
                    current_cost = new_cost
                    improved = True
                else:
                    # Revert
                    seq[k], seq[k+1] = seq[k+1], seq[k]
        return seq, current_cost

    # ── Compute bounds ────────────────────────────────────────────────────
    ub_ws_cost, seq_ws   = compute_warmstart_ub(jgp_batches, T_j, b, num_jobs)
    ub_ffd_cost, seq_ffd = compute_greedy_ffd_ub(num_jobs, T_j, b)
    seq_2opt, ub_2opt    = apply_2opt_improvement(seq_ws, T_j, b)

    print("── Upper Bounds ─────────────────────────────────────────────")
    print(f"  UB1 (JGP Warm-Start) : {ub_ws_cost}")
    print(f"  UB2 (Greedy FFD)     : {ub_ffd_cost}")
    print(f"  UB3 (2-Opt refined)  : {ub_2opt}")
    return seq_ws, ub_2opt, ub_ffd_cost, ub_ws_cost


@app.cell
def _(jgp_obj, np, plt, ssp_obj, ub_2opt, ub_ffd_cost, ub_ws_cost):
    """Cell 9: Visualization 2 — Bounds hierarchy bar chart."""

    bounds = {
        "JGP (LB)":        jgp_obj,
        "SSP Optimal":     ssp_obj,
        "2-Opt (UB3)":     ub_2opt,
        "Warm-Start (UB1)": ub_ws_cost,
        "FFD (UB2)":       ub_ffd_cost,
    }
    colors = {
        "JGP (LB)":         "#2ecc71",
        "SSP Optimal":      "#3498db",
        "2-Opt (UB3)":      "#f39c12",
        "Warm-Start (UB1)": "#e67e22",
        "FFD (UB2)":        "#e74c3c",
    }

    fig_bounds, ax_b = plt.subplots(figsize=(9, 5))

    x_pos   = np.arange(len(bounds))
    bar_vals = list(bounds.values())
    bar_clrs = [colors[k] for k in bounds]

    bars = ax_b.bar(x_pos, bar_vals, color=bar_clrs, edgecolor='black',
                    linewidth=1.2, width=0.6)

    # Value labels on bars
    for bar, val in zip(bars, bar_vals):
        if val is not None:
            ax_b.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                      f"{val:.1f}", ha='center', va='bottom',
                      fontsize=10, fontweight='bold')

    # Shade gap between JGP and warm-start
    ax_b.axhspan(jgp_obj, ub_ws_cost, alpha=0.06, color='gray',
                 label='Uncertainty gap')
    ax_b.axhline(jgp_obj, color='green', lw=1.4, linestyle='--', alpha=0.7)
    if ssp_obj is not None:
        ax_b.axhline(ssp_obj, color='blue', lw=1.4, linestyle='--', alpha=0.7)

    ax_b.set_xticks(x_pos)
    ax_b.set_xticklabels(list(bounds.keys()), fontsize=10)
    ax_b.set_ylabel("Tool-Switch Cost", fontsize=11)
    ax_b.set_title(
        "Bounds Hierarchy:  LB  ≤  OPT(SSP)  ≤  UB\n"
        "(green = lower bound, blue = exact optimum, orange/red = upper bounds)",
        fontsize=11
    )
    ax_b.set_ylim(0, max(v for v in bar_vals if v is not None) * 1.2)
    ax_b.grid(axis='y', alpha=0.3, linestyle='--')

    plt.tight_layout()
    plt.show()

    # Numerical gap report
    if ssp_obj and jgp_obj:
        dual_gap  = (ssp_obj  - jgp_obj)  / max(jgp_obj, 1) * 100
        primal_gap_ws  = (ub_ws_cost - ssp_obj) / max(ssp_obj, 1) * 100
        print(f"\nGap analysis:")
        print(f"  Dual gap   (OPT - JGP) / JGP  = {dual_gap:.1f}%")
        print(f"  Primal gap (UB_ws - OPT) / OPT = {primal_gap_ws:.1f}%")
        print(f"  Total gap  (UB_ws - JGP) / JGP  = "
              f"{(ub_ws_cost - jgp_obj)/max(jgp_obj,1)*100:.1f}%")
    return


@app.cell
def _(b, jgp_batches, num_tools, plot_magazine_timeline, plt, ssp_route):
    """Cell 10: Visualization 3 — Two-panel Magazine Timeline (JGP vs SSP)."""

    if ssp_route:
        fig_timeline = plot_magazine_timeline(ssp_route, jgp_batches, num_tools, b)
        plt.show()
    else:
        print("SSP route not available — skipping timeline plot.")
        fig_timeline = None
    return


@app.cell
def _(b, plot_active_config_network, plt, ssp_route):
    """Cell 11: Visualization 4 — Active Configuration Transition Network."""

    if ssp_route:
        fig_network = plot_active_config_network(ssp_route, b)
        plt.show()
    else:
        fig_network = None
    return


@app.cell
def _(T_j, b, plot_timedep_costs, plt, seq_ws):
    """Cell 12: Visualization 5 — Time-dependent cost surfaces."""

    if seq_ws:
        fig_timedep = plot_timedep_costs(seq_ws, T_j, b)
        plt.show()
    else:
        fig_timedep = None
    return


@app.cell
def _(
    b,
    jgp_obj,
    num_jobs,
    num_tools,
    pd,
    ssp_obj,
    ub_2opt,
    ub_ffd_cost,
    ub_ws_cost,
):
    """Cell 13: Results summary table."""

    import itertools as _it
    config_count = len(list(_it.combinations(range(num_tools), b)))

    rows = [
        ("JGP lower bound (LB1)",        jgp_obj,
         "Batch count from optimal JGP partition"),
        ("SSP exact optimum (GTSP)",      ssp_obj,
         "Optimal switch cost (GTSP/MILP)"),
        ("Warm-Start upper bound (UB1)",  ub_ws_cost,
         "JGP batch ordering → KTNS cost"),
        ("Greedy FFD upper bound (UB2)",  ub_ffd_cost,
         "Decreasing |T_j| greedy → KTNS cost"),
        ("2-Opt refined (UB3)",           ub_2opt,
         "Adjacent swap improvement on warm-start"),
    ]

    df_res = pd.DataFrame(rows, columns=["Bound / Method", "Value", "Description"])

    if ssp_obj and ssp_obj > 0:
        df_res["Gap to OPT (%)"] = df_res["Value"].apply(
            lambda v: f"{abs(v - ssp_obj)/ssp_obj*100:.1f}%" if v is not None else "—"
        )

    print("=" * 60)
    print("COMPUTATIONAL RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Instance:  {num_jobs} jobs, {num_tools} tools, capacity {b}")
    print(f"  Config space: |C| = {config_count}")
    print()
    print(df_res.to_string(index=False))
    print("=" * 60)
    return


@app.cell
def _(b, plot_configuration_network, ssp_route):
    plot_configuration_network(ssp_route,b)
    return


@app.cell
def _():
    porta_jgp_file = "shankar-example-jgp.ieq"
    porta_jgp_output_file = porta_jgp_file + ".poi"
    # run_jgp_porta(num_tools, num_jobs, T_j, b, porta_file)
    return (porta_jgp_output_file,)


@app.cell
def _(porta_jgp_output_file, read_porta_output):
    jgp_bfs = read_porta_output(porta_jgp_output_file)
    return (jgp_bfs,)


@app.cell
def _(jgp_bfs, np):
    num_groups = np.array([sum(bfs)  for bfs in jgp_bfs])
    optimal_num_groups = min(num_groups)
    optimal_jgp_indices = (num_groups == optimal_num_groups)
    jgp_optimal_solutions = jgp_bfs[optimal_jgp_indices,:]

    selected_jgp_bfs = jgp_bfs[num_groups < 10,:]
    return (selected_jgp_bfs,)


@app.cell
def _(all_configs, pd, run_brute_force_TSP_on_configs, selected_jgp_bfs, tqdm):
    jgp_df = pd.DataFrame(columns=['#','Group Configurations', 'Num groups', 'Min Cost Ham Path', 'Ham Path Opt. Routes']);
    jgp_df_row_id = 0

    for bfs in tqdm(selected_jgp_bfs): # or jgp_optimal_solutions
        selected_configs = all_configs[bfs == 1]
        (min_c, min_routes) = run_brute_force_TSP_on_configs(selected_configs)
        jgp_df.loc[jgp_df_row_id, : ] = [jgp_df_row_id+1, selected_configs, sum(bfs == 1), min_c, min_routes]
        jgp_df_row_id += 1 
    return (jgp_df,)


@app.cell
def _(jgp_df):
    jgp_df.head()
    jgp_df.to_csv("jgp_selected_solutions_atmost_10_groups.csv",index=False)
    return


@app.cell
def _(T_j, b, num_jobs, num_tools, run_ssp_porta):
    porta_ssp_file = "shankar-example-ssp.ieq"
    porta_ssp_output_file = porta_ssp_file + ".poi"

    # write_ssp_pctsp_ieq_file(num_tools, num_jobs, T_j, b, "test-ssp.ieq")
    run_ssp_porta(num_tools, num_jobs, T_j,b,porta_ssp_file)
    return


app._unparsable_cell(
    r"""
    visualize_ssp_jgp_solution(job_sequence: list, T_j: dict, magazine_states: list, b: int, jgp_batches: list = None):
    """,
    name="_"
)


@app.cell
def _():
    # convert_ieq_to_ine('shankar-example-ssp.ieq', 'shankar-example-ssp.ine')
    return


@app.cell
def _(pd):
    ssp_df = pd.read_csv("ssp_feasible_solutions.csv",index_col="#")
    ssp_df.head()
    return (ssp_df,)


@app.cell
def _(ssp_df):
    min_ssp_cost = min(ssp_df.iloc[:,2])
    return (min_ssp_cost,)


@app.cell
def _(min_ssp_cost, np, ssp_df):
    optimal_ssp_df = ssp_df.iloc[ssp_df.iloc[:,2] == min_ssp_cost,:]
    optimal_ssp_df["Configurations"] = optimal_ssp_df["Configurations"].map(lambda x: np.asarray(np.matrix(x[:-2] + x[-1])))
    optimal_ssp_df["Job Sequence"] = optimal_ssp_df["Job Sequence"].map(lambda x: np.squeeze(np.asarray(np.matrix(x[:-1]))))
    optimal_ssp_df.head()
    return (optimal_ssp_df,)


@app.cell
def _(np, optimal_ssp_df):
    optimal_ssp_df["Unique Configs"] = optimal_ssp_df["Configurations"].map(lambda x: np.unique(x,axis=0))
    optimal_ssp_df["Num Unique Configs"] = optimal_ssp_df["Unique Configs"].map(lambda x: x.shape[0])
    return


@app.cell
def _(optimal_ssp_df):
    min(optimal_ssp_df["Num Unique Configs"])
    return


@app.cell
def _(solve_hamiltonian_path):
    configurations = [[0,1,1],[1,1,0],[1,1,1],[0,0,1],[1,0,1],[1,1,1]]
    path_indices = solve_hamiltonian_path(configurations)

    print("Optimal Path Order (Indices):", path_indices)
    print("Optimal Path Order (Nodes):")
    for idx in path_indices:
        print(f" Node {idx}: {configurations[idx]}")
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
