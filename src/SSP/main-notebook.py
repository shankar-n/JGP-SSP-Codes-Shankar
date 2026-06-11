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
    from viz import (
        plot_incidence_matrix, plot_ktns_timeline, plot_jgp_ssp_comparison,
        plot_solution_comparison, plot_config_chain, plot_bounds_bar,
        plot_interactive_timeline,
        # backward-compat aliases still importable:
        plot_zero_blocks, plot_magazine_timeline, plot_active_config_network,
    )
    from heuristics import (
        warmstart_from_jgp, greedy_ffd, adjacent_swap_ls,
        nearest_neighbor, ktns_magazine_states,
    )
    from SCIP_formulation_solvers import solve_jgp_arf, solve_ssp_gtsp
    from solution_validators import validate_jgp, validate_ssp
    from porta import run_jgp_porta, read_porta_output, run_ssp_porta, convert_ieq_to_ine
    from concorde_util import solve_hamiltonian_path
    import subprocess
    import os
    import tempfile
    from tqdm import tqdm

    return (
        adjacent_swap_ls,
        compute_ssp_cost,
        detect_0blocks,
        greedy_ffd,
        itertools,
        load_ssp_instance,
        mo,
        np,
        pd,
        plot_active_config_network,
        plot_bounds_bar,
        plot_config_chain,
        plot_interactive_timeline,
        plot_jgp_ssp_comparison,
        plot_ktns_timeline,
        plot_zero_blocks,
        read_porta_output,
        run_ssp_porta,
        solve_hamiltonian_path,
        solve_jgp_arf,
        solve_ssp_gtsp,
        tqdm,
        validate_jgp,
        validate_ssp,
        warmstart_from_jgp,
    )


@app.cell
def _(itertools, load_ssp_instance, np):
    """Cell 2: File loading and preprocessing."""

    # ── Adjust these two paths to switch instances ──────────────────────────
    INSTANCES_PTH   = '../../data/From_Felipe/data/'
    SAMPLE_INSTANCE = 'Catanzaro/Tabela1C/A0-0.txt'
    # ────────────────────────────────────────────────────────────────────────

    filepath = INSTANCES_PTH + SAMPLE_INSTANCE
    filepath = '../../data/Shankar/shankar-example.txt'
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
    return A, INSTANCES_PTH, T_j, all_configs, b, num_jobs, num_tools


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
def _(T_j, b, mo, num_jobs, num_tools):
    """Cell 6b: Exact formulation comparison — BBC vs LSS vs SSPMF.

    Runs all three exact ILP/B&B formulations on the loaded instance and
    produces a side-by-side comparison table.

    References
    ----------
    BBC  : Branch-and-Benders-Cut (this project)
    LSS  : Laporte, Salazar-González & Semet (2004), IIE Transactions 36(1)
    SSPMF: da Silva, Chaves & Yanasse (2024), multicommodity flow

    Objective convention (audit note, Claude-Fable 2026-06-10)
    ----------------------------------------------------------
    All three solvers here use the EMPTY-START convention (objective counts
    every insertion, including the first job's load) -- mutually consistent,
    no adjustment needed within this table.  But the GTSP reference (cell 6)
    and all plans-genai documents use the FREE-INITIAL convention:
        empty_start = free_initial + min(b, |union of required tools|)
    for every sequence (constant shift; argmin unaffected).  Convert before
    comparing objectives across cells, computing H/Z* ratios against Part V
    theory, or quoting published tables.
    """
    import sys as _sys
    import os as _os
    import time as _time
    from pathlib import Path as _Path

    # ── Add BBC/ to path (it is a sibling of SSP/ under src/) ──────────────
    _bbc_dir = str(_Path(_os.getcwd()).parent / "BBC")
    if _bbc_dir not in _sys.path:
        _sys.path.insert(0, _bbc_dir)

    # ── Configuration ────────────────────────────────────────────────────────
    TIME_LIMIT                = 120    # seconds per formulation
    BBC_WORKER_LP_REUSE       = False  # True → reuse DSP model across callbacks
    BBC_FRACTIONAL_CUTS       = False  # True → Benders user cuts at LP-relaxation nodes
    BBC_COMBINATORIAL_CUTS    = False   # True → KTNS combinatorial cuts (no LP DSP solve)
    BBC_TRIPLET_BOUNDS        = False  # True → O(n³) triplet lb constraints (tighter root)
    BBC_PARALLEL              = False  # True → multi-threaded B&B
    LSS_LIFTED_OBJ            = True   # True → use lifted LSS objective
    LSS_VALID_INEQ            = True   # True → add LSS valid inequalities (23)(25)
    SSPMF_SYM_BREAK           = True   # True → SSPMF symmetry-breaking constraint
    SSPMF_C21                 = False  # c21 overconstrained for n_jt=2 instances

    # ── Helper: run one formulation safely ───────────────────────────────────
    def _run(label, fn):
        try:
            _t0 = _time.perf_counter()
            status, obj, seq = fn()
            elapsed = round(_time.perf_counter() - _t0, 3)
            return {"label": label, "status": str(status),
                    "obj": obj, "seq": seq, "time": elapsed, "error": None}
        except Exception as _e:
            return {"label": label, "status": "ERROR",
                    "obj": None, "seq": None, "time": None, "error": str(_e)}

    # ── BBC ──────────────────────────────────────────────────────────────────
    # Use a list as mutable container so the nested function can write to it
    # (avoids `global` which doesn't work correctly inside a marimo cell).
    _bbc_backend = ["N/A"]
    def _run_bbc():
        from branch_and_benders_cut import BranchAndBendersCutSSP, _BACKEND
        _bbc_backend[0] = _BACKEND
        _s = BranchAndBendersCutSSP(
            num_jobs, num_tools, b, T_j,
            worker_lp_reuse        = BBC_WORKER_LP_REUSE,
            use_fractional_cuts    = BBC_FRACTIONAL_CUTS,
            use_combinatorial_cuts = BBC_COMBINATORIAL_CUTS,
            use_triplet_bounds     = BBC_TRIPLET_BOUNDS,
            parallel               = BBC_PARALLEL,
        )
        _s.build_master_problem(verbose=False)
        status, obj, seq = _s.solve(time_limit=TIME_LIMIT, verbose=False)
        # stash solver so we can read detailed stats below
        _bbc_backend.append(_s)
        return status, obj, seq

    # ── LSS ──────────────────────────────────────────────────────────────────
    def _run_lss():
        from lss_formulation import LSSFormulation
        _f = LSSFormulation(num_jobs, num_tools, b, T_j,
                            use_lifted_obj=LSS_LIFTED_OBJ,
                            use_valid_ineq=LSS_VALID_INEQ)
        _f.build_model(verbose=False)
        return _f.solve(time_limit=TIME_LIMIT, verbose=False)

    # ── SSPMF ────────────────────────────────────────────────────────────────
    def _run_sspmf():
        from sspmf_formulation import SSPMFFormulation
        _f = SSPMFFormulation(num_jobs, num_tools, b, T_j,
                              use_symmetry_breaking=SSPMF_SYM_BREAK,
                              use_constraint_21=SSPMF_C21)
        _f.build_model(verbose=False)
        return _f.solve(time_limit=TIME_LIMIT, verbose=False)

    # ── Run all three ────────────────────────────────────────────────────────
    _results = [
        _run("BBC",   _run_bbc),
        _run("LSS",   _run_lss),
        _run("SSPMF", _run_sspmf),
    ]

    # ── Compute best-known objective for gap calculation ─────────────────────
    _valid_objs = [r["obj"] for r in _results if r["obj"] is not None]
    _best = min(_valid_objs) if _valid_objs else None

    def _fmt_obj(obj):
        if obj is None:
            return "—"
        return f"**{obj:.1f}**" if (_best is not None and abs(obj - _best) < 1e-4) else f"{obj:.1f}"

    def _fmt_gap(obj):
        if obj is None or _best is None or _best == 0:
            return "—"
        gap = 100.0 * (obj - _best) / _best
        return f"{gap:.1f}%" if gap > 1e-4 else "0 %"

    def _fmt_time(t):
        return f"{t:.2f}s" if t is not None else "—"

    def _fmt_status(r):
        s = r["status"]
        if r["error"]:
            return f"`ERROR` ({r['error'][:40]})"
        return f"`{s}`"

    # ── Render comparison table ───────────────────────────────────────────────
    _rows = "\n".join(
        f"| **{r['label']}** | {_fmt_status(r)} | {_fmt_obj(r['obj'])} "
        f"| {_fmt_gap(r['obj'])} | {_fmt_time(r['time'])} "
        f"| `{str(r['seq'][:4])[:-1]}…`" if r['seq'] else
        f"| **{r['label']}** | {_fmt_status(r)} | {_fmt_obj(r['obj'])} "
        f"| {_fmt_gap(r['obj'])} | {_fmt_time(r['time'])} | — |"
        for r in _results
    )

    _table = "\n".join([
        f"| **{r['label']}** | {_fmt_status(r)} | {_fmt_obj(r['obj'])} "
        f"| {_fmt_gap(r['obj'])} | {_fmt_time(r['time'])} "
        f"| `{r['seq'][:5]}…` |" if r['seq'] is not None
        else
        f"| **{r['label']}** | {_fmt_status(r)} | — | — | {_fmt_time(r['time'])} | — |"
        for r in _results
    ])

    # ── BBC detailed stats (if solver object was captured) ───────────────────
    _bbc_solver = _bbc_backend[1] if len(_bbc_backend) > 1 else None
    _bbc_st = _bbc_solver.solve_stats if _bbc_solver is not None else {}

    def _stat(key, fmt=None):
        v = _bbc_st.get(key)
        if v is None: return "—"
        return fmt.format(v) if fmt else str(v)

    _bbc_detail = mo.md(f"""
    ### BBC Solver Diagnostics

    | Stat | Value |
    |---|---|
    | Root LP bound (θ before first cut) | {_stat('root_lp_bound', '{:.2f}')} |
    | Dual bound at termination | {_stat('dual_bound', '{:.2f}')} |
    | MIP gap | {_stat('mip_gap_pct', '{:.4f}%')} |
    | B&B nodes explored | {_stat('nodes')} |
    | LP iterations | {_stat('lp_iters')} |
    | Callback invocations | {_stat('cb_invocations')} |
    | Cuts — SECs | {_stat('cuts_sec')} |
    | Cuts — Benders LP | {_stat('cuts_benders')} |
    | Cuts — Combinatorial | {_stat('cuts_comb')} |
    | Cuts — Fractional | {_stat('cuts_frac')} |
    | Wall time (s) | {_stat('wall_time_s', '{:.2f}')} |

    **Flags:** comb_cuts=`{BBC_COMBINATORIAL_CUTS}` · triplet_bounds=`{BBC_TRIPLET_BOUNDS}` · \
    frac_cuts=`{BBC_FRACTIONAL_CUTS}` · lp_reuse=`{BBC_WORKER_LP_REUSE}`
    """) if _bbc_st else mo.md("*BBC stats not available*")

    _display = mo.md(f"""
    ## Exact Formulation Comparison

    **Instance:** {num_jobs} jobs · {num_tools} tools · capacity {b} · time limit {TIME_LIMIT}s per solver

    | Formulation | Status | Obj (switches) | Gap to best | Time | Sequence (first 5) |
    |---|---|---|---|---|---|
    {_table}

    > BBC backend: `{_bbc_backend[0]}` · LSS lifted obj: `{LSS_LIFTED_OBJ}` · \
    LSS valid ineqs: `{LSS_VALID_INEQ}` · SSPMF sym-break: `{SSPMF_SYM_BREAK}`
    """)

    # ── Unpack results for downstream cells ──────────────────────────────────
    _bbc_r, _lss_r, _sspmf_r = _results

    bbc_obj, bbc_sequence, bbc_status = _bbc_r["obj"], _bbc_r["seq"], _bbc_r["status"]
    lss_obj, lss_sequence, lss_status = _lss_r["obj"], _lss_r["seq"], _lss_r["status"]
    sspmf_obj, sspmf_sequence, sspmf_status = _sspmf_r["obj"], _sspmf_r["seq"], _sspmf_r["status"]

    mo.vstack([_display, _bbc_detail])
    return


@app.cell
def _():
    # """Cell 6c: SSP Instance Generator — produce & compare on a fresh instance.

    # Generates a new SSP instance using one of two methods:
    #   • Crama (1994) : inclusion-free random sampling, 16 standard benchmark types
    #   • Overlapping  : core-group sampling producing high job-tool overlap

    # The generated instance is immediately passed to BBC, LSS, and SSPMF for
    # a side-by-side exact-formulation comparison.

    # Fix notes vs. original SSPInstanceGenerator
    # -------------------------------------------
    # 1. save_instance header corrected from  "M N C"  (tools, jobs, capacity) to
    #    "N M C"  (jobs, tools, capacity) — matching load_ssp_instance token order.
    # 2. The spurious  "min_tools max_tools"  second header line was removed; it
    #    caused load_ssp_instance to corrupt the matrix (flat-token parser).
    # 3. load_instance in the class updated accordingly.
    # """
    # import sys as _sys, os as _os, time as _time, tempfile as _tf
    # from pathlib import Path as _Path
    # import numpy as _np

    # # ── Configuration ─────────────────────────────────────────────────────────
    # # Method: "crama" or "overlapping"
    # GEN_METHOD       = "crama"

    # # Crama preset — pick an index 0–15 from get_crama_instance_types():
    # #   0–3  : (M=10, N=10, C=4/5/6/7,   t∈[2,4])
    # #   4–7  : (M=20, N=15, C=6/8/10/12, t∈[2,6])
    # #   8–11 : (M=40, N=30, C=15/17/20/25,t∈[5,15])
    # #   12–15: (M=60, N=40, C=20/22/25/30,t∈[7,20])
    # CRAMA_TYPE_IDX   = 0     # index into get_crama_instance_types()

    # # Custom parameters (used when GEN_METHOD="overlapping" or to override Crama)
    # CUSTOM_M         = 10    # number of tools
    # CUSTOM_N         = 10    # number of jobs
    # CUSTOM_C         = 5     # magazine capacity  (must be >= max_tools)
    # CUSTOM_MIN_TOOLS = 2     # min tools per job
    # CUSTOM_MAX_TOOLS = 4     # max tools per job  (must be <= C)
    # OVERLAP_FACTOR   = 0.65  # only for method="overlapping"

    # GEN_SEED         = 42    # random seed (None for non-reproducible)

    # # Formulation time limit
    # TIME_LIMIT       = 120   # seconds per solver

    # # ── Add BBC directory to path (sibling of SSP/) ───────────────────────────
    # _bbc_dir = str(_Path(_os.getcwd()).parent / "BBC")
    # if _bbc_dir not in _sys.path:
    #     _sys.path.insert(0, _bbc_dir)

    # # ── Generate instance ─────────────────────────────────────────────────────
    # from ssp_instance_generator import SSPInstanceGenerator as _Gen

    # _gen = _Gen(seed=GEN_SEED)

    # if GEN_METHOD == "crama":
    #     _types   = _Gen.get_crama_instance_types()
    #     _idx     = max(0, min(CRAMA_TYPE_IDX, len(_types) - 1))
    #     _M, _N, _C, _min_t, _max_t = _types[_idx]
    #     _A, _meta = _gen.generate_instance(_M, _N, _C, _min_t, _max_t)
    #     _type_label = f"Crama type {_idx} (M={_M}, N={_N}, C={_C}, t∈[{_min_t},{_max_t}])"
    # else:
    #     _M, _N, _C = CUSTOM_M, CUSTOM_N, CUSTOM_C
    #     _min_t, _max_t = CUSTOM_MIN_TOOLS, CUSTOM_MAX_TOOLS
    #     _A, _meta = _gen.generate_overlapping_instance(
    #         _M, _N, _C, _min_t, _max_t, overlap_factor=OVERLAP_FACTOR)
    #     _type_label = f"Overlapping (M={_M}, N={_N}, C={_C}, overlap={OVERLAP_FACTOR})"

    # # After filtering null rows:
    # _Mf = _meta["M_after_filtering"]
    # _T_j = _Gen.matrix_to_tool_req(_A)

    # # ── Instance statistics ───────────────────────────────────────────────────
    # _tools_per_job = _A.sum(axis=0)          # sum over tool rows → per job
    # _jobs_per_tool = _A.sum(axis=1)          # sum over job cols → per tool
    # _density       = _A.mean()
    # _null_removed  = _meta.get("null_rows_removed", 0)

    # # ── Run BBC, LSS, SSPMF ───────────────────────────────────────────────────
    # def _run_safe(label, fn):
    #     try:
    #         t0 = _time.perf_counter()
    #         status, obj, seq = fn()
    #         return {"label": label, "status": str(status), "obj": obj,
    #                 "seq": seq, "time": round(_time.perf_counter() - t0, 3), "err": None}
    #     except Exception as e:
    #         return {"label": label, "status": "ERROR", "obj": None,
    #                 "seq": None, "time": None, "err": str(e)[:60]}

    # _bbc_backend = ["N/A"]
    # def _run_bbc():
    #     from branch_and_benders_cut import BranchAndBendersCutSSP, _BACKEND
    #     _bbc_backend[0] = _BACKEND
    #     s = BranchAndBendersCutSSP(_Mf, _meta["N"], _C, _T_j)
    #     s.build_master_problem(verbose=False)
    #     return s.solve(time_limit=TIME_LIMIT, verbose=False)

    # def _run_lss():
    #     from lss_formulation import LSSFormulation
    #     f = LSSFormulation(_Mf, _meta["N"], _C, _T_j)
    #     f.build_model(verbose=False)
    #     return f.solve(time_limit=TIME_LIMIT, verbose=False)

    # def _run_sspmf():
    #     from sspmf_formulation import SSPMFFormulation
    #     f = SSPMFFormulation(_Mf, _meta["N"], _C, _T_j)
    #     f.build_model(verbose=False)
    #     return f.solve(time_limit=TIME_LIMIT, verbose=False)

    # _results = [
    #     _run_safe("BBC",   _run_bbc),
    #     _run_safe("LSS",   _run_lss),
    #     _run_safe("SSPMF", _run_sspmf),
    # ]

    # # ── Compute gaps ──────────────────────────────────────────────────────────
    # _valid = [r["obj"] for r in _results if r["obj"] is not None]
    # _best  = min(_valid) if _valid else None

    # def _fo(obj):
    #     if obj is None: return "—"
    #     return f"**{obj:.1f}**" if _best is not None and abs(obj - _best) < 1e-4 else f"{obj:.1f}"

    # def _fg(obj):
    #     if obj is None or _best is None or _best == 0: return "—"
    #     g = 100.0 * (obj - _best) / _best
    #     return "0 %" if g < 1e-4 else f"{g:.1f} %"

    # def _ft(t):   return f"{t:.2f}s" if t is not None else "—"
    # def _fs(r):   return f"`{r['status']}`" if not r["err"] else f"`ERROR` {r['err']}"
    # def _fseq(r): return f"`{str(r['seq'][:4])[:-1]}…`" if r["seq"] else "—"

    # _table = "\n".join(
    #     f"| **{r['label']}** | {_fs(r)} | {_fo(r['obj'])} | {_fg(r['obj'])} "
    #     f"| {_ft(r['time'])} | {_fseq(r)} |"
    #     for r in _results
    # )

    # mo.md(f"""
    # ## Instance Generator + Formulation Comparison

    # **Generation method:** {_type_label}  ·  seed={GEN_SEED}  ·  time limit={TIME_LIMIT}s/solver

    # ### Instance statistics

    # | Parameter | Value |
    # |---|---|
    # | Jobs (N) | {_meta["N"]} |
    # | Tools (M, after null-row filter) | {_Mf} ({_null_removed} removed) |
    # | Capacity (C) | {_C} |
    # | Tools per job — min / mean / max | {int(_tools_per_job.min())} / {_tools_per_job.mean():.2f} / {int(_tools_per_job.max())} |
    # | Jobs per tool — min / mean / max | {int(_jobs_per_tool.min())} / {_jobs_per_tool.mean():.2f} / {int(_jobs_per_tool.max())} |
    # | Matrix density | {_density:.1%} |

    # ### Exact formulation comparison

    # | Formulation | Status | Obj (switches) | Gap to best | Time | Sequence |
    # |---|---|---|---|---|---|
    # {_table}

    # > BBC backend: `{_bbc_backend[0]}`
    # """)
    return


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
def _(
    T_j,
    adjacent_swap_ls,
    b,
    greedy_ffd,
    jgp_batches,
    num_jobs,
    warmstart_from_jgp,
):
    """Cell 8: Upper-bound heuristics (from heuristics.py).

    Methods
    -------
    warmstart_from_jgp  — flatten JGP batches, ordering jobs within each
                          batch by decreasing |T_j| (promotes carry-over).
                          Valid UB because KTNS is optimal for fixed sequence.
    greedy_ffd          — First-Fit Decreasing: sort all jobs by |T_j| desc,
                          evaluate with KTNS.  Fast O(n log n) construction.
    adjacent_swap_ls    — Adjacent-swap local search on the warm-start seed.
                          NOTE: not classical 2-opt (which reverses segments);
                          this is a 1-exchange on neighbouring pairs ("bubble
                          sort with cost"), converging to a local optimum.
    """
    ub_ws_cost, seq_ws    = warmstart_from_jgp(jgp_batches, T_j, b)
    ub_ffd_cost, seq_ffd  = greedy_ffd(num_jobs, T_j, b)
    seq_2opt, ub_2opt, _  = adjacent_swap_ls(seq_ws, T_j, b)

    print("── Upper Bounds ─────────────────────────────────────────────")
    print(f"  UB1 (JGP warm-start)  : {ub_ws_cost}   seq={seq_ws}")
    print(f"  UB2 (Greedy FFD)      : {ub_ffd_cost}  seq={seq_ffd}")
    print(f"  UB3 (adjacent-swap LS): {ub_2opt}   seq={seq_2opt}")
    return seq_ws, ub_2opt, ub_ffd_cost, ub_ws_cost


@app.cell
def _(jgp_obj, plot_bounds_bar, ssp_obj, ub_2opt, ub_ffd_cost, ub_ws_cost):
    """Cell 9: Bounds hierarchy bar chart (via viz.plot_bounds_bar)."""

    bounds = {
        "JGP  (LB)":              jgp_obj,
        "SSP exact  (OPT)":       ssp_obj,
        "Adjacent-swap LS  (UB)": ub_2opt,
        "JGP warm-start  (UB)":   ub_ws_cost,
        "Greedy FFD  (UB)":       ub_ffd_cost,
    }
    fig_bounds = plot_bounds_bar(bounds, title="Bounds Hierarchy: LB ≤ OPT ≤ UB")

    # Numerical gap report
    if ssp_obj and jgp_obj:
        dual_gap      = (ssp_obj    - jgp_obj)   / max(jgp_obj, 1)   * 100
        primal_gap_ws = (ub_ws_cost - ssp_obj)   / max(ssp_obj, 1)   * 100
        print(f"\nGap analysis:")
        print(f"  Dual gap    (OPT − JGP) / JGP        = {dual_gap:.1f}%")
        print(f"  Primal gap  (UB_ws − OPT) / OPT      = {primal_gap_ws:.1f}%")
        print(f"  Total gap   (UB_ws − JGP) / JGP       = "
              f"{(ub_ws_cost - jgp_obj)/max(jgp_obj,1)*100:.1f}%")

    fig_bounds
    return


@app.cell
def _(T_j, b, jgp_batches, plot_jgp_ssp_comparison, ssp_route):
    """Cell 10: JGP vs SSP magazine timeline comparison.

    Uses the KTNS-based timeline (works with any job sequence).
    """
    if ssp_route:
        ssp_sequence = [j for (cfg, j) in ssp_route if cfg != "DUMMY"]
        fig_timeline = plot_jgp_ssp_comparison(ssp_sequence, jgp_batches, T_j, b)
    else:
        print("SSP route not available — skipping timeline plot.")
        fig_timeline = None
    fig_timeline
    return


@app.cell
def _(T_j, b, plot_config_chain, ssp_route):
    """Cell 11: Configuration chain — linear sequence of magazine states."""
    if ssp_route:
        ssp_sequence = [j for (cfg, j) in ssp_route if cfg != "DUMMY"]
        fig_chain = plot_config_chain(ssp_sequence, T_j, b)
    else:
        fig_chain = None
    fig_chain
    return


@app.cell
def _(T_j, b, plot_interactive_timeline, plot_ktns_timeline, seq_ws):
    """Cell 12: KTNS timeline for the warm-start sequence + interactive viewer.

    plot_timedep_costs was removed — time-dependent switch cost is not part
    of the standard SSP model.  Replaced with:
      - Static KTNS timeline for the JGP warm-start sequence
      - Interactive Plotly timeline (returned for marimo rendering)
    """
    if seq_ws:
        # Static matplotlib KTNS timeline
        fig_ktns = plot_ktns_timeline(
            seq_ws, T_j, b, title="KTNS Timeline — JGP Warm-Start Sequence")

        # Interactive Plotly timeline (marimo renders this natively)
        fig_interactive = plot_interactive_timeline(
            seq_ws, T_j, b, title="Interactive KTNS — JGP Warm-Start")
    else:
        fig_ktns        = None
        fig_interactive = None
    fig_ktns
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
def _(b, plot_active_config_network, ssp_route):
    plot_active_config_network(ssp_route, b)
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
    return


@app.cell
def _(all_configs, jgp_bfs, pd, solve_hamiltonian_path, tqdm):
    jgp_df = pd.DataFrame(columns=['#','Group Configurations', 'Num groups', 'Min Cost Ham Path', 'Ham Path Opt. Routes']);
    jgp_df_row_id = 0

    for bfs in tqdm(jgp_bfs): # or jgp_optimal_solutions
        selected_configs = all_configs[bfs == 1]
        # (min_c, min_routes) = run_brute_force_TSP_on_configs(selected_configs)
        min_c, min_routes = solve_hamiltonian_path(selected_configs)
        jgp_df.loc[jgp_df_row_id, : ] = [jgp_df_row_id+1, selected_configs, sum(bfs == 1), min_c, min_routes]
        jgp_df_row_id += 1

    jgp_df.to_csv("jgp_bfs_analysis.csv",index=False)
    return (jgp_df,)


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
def _(pd):
    jgp_df = pd.read_csv("jgp_bfs_analysis.csv",index_col="#")
    jgp_df.head()
    return (jgp_df,)


@app.cell
def _(jgp_df):
    min_groups = min(jgp_df['Num groups'])
    optimal_jgp_df = jgp_df.loc[(jgp_df['Num groups'] == min_groups),:]
    tsp_best_cost = min(optimal_jgp_df['Min Cost Ham Path'])
    tsp_best_cost
    return (optimal_jgp_df,)


@app.cell
def _(optimal_jgp_df):
    optimal_jgp_df
    return


@app.cell
def _(jgp_df):
    min_ssp_cost = min(jgp_df['Min Cost Ham Path'])
    jgp_bfs_with_optimal_switches = jgp_df.loc[(jgp_df['Min Cost Ham Path'] == min_ssp_cost),:]
    jgp_bfs_with_optimal_switches
    return (min_ssp_cost,)


@app.cell
def _(jgp_df):
    df2 = jgp_df
    df2.boxplot(by='Num groups')
    return (df2,)


@app.cell
def _(df2):
    df2.boxplot(by='Min Cost Ham Path')
    return


@app.cell
def _(INSTANCES_PTH, load_ssp_instance):
    with open('../../data/From_Felipe/data/files.txt') as f:
        instance_files = f.readlines()

    instance_files = [INSTANCES_PTH + file[2:-1] for file in instance_files]

    for instance_file in instance_files:
        try:
            num_jobs, num_tools, b, A, T_j = load_ssp_instance(instance_file)
            if(num_jobs*num_tools < 100):
                print(instance_file)
        except:
            pass
    return A, T_j, b, num_jobs, num_tools


@app.cell
def _(generate_group):
    # from ....data.From_Felipe.instance_generator import generate_group
    OUT_DIR = "../../data/Shankar"

    import random

    def generate_test_classes(num_classes):
        TEST_CLASSES = {}
        for i in range(1, num_classes + 1):
            b = random.randint(4, 10)
            max_a = max(4, 40 // b)
            a = random.randint(4, max_a)
            variation = random.choice([-1, 0, 1])
            c = max(0, int(b / 2 + variation))
            d = random.choice([0.2, 0.3, 0.4])
            TEST_CLASSES[f"Class{i}"] = (a, b, c, d)
        return TEST_CLASSES

    SHANKAR_TEST_CLASSES = generate_test_classes(20)
    random.seed(42)
    generate_group(SHANKAR_TEST_CLASSES, OUT_DIR)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
