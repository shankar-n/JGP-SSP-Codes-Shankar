"""
Benchmark runner: BBC vs LSS vs SSPMF for the Job Sequencing and Tool Switching Problem.

Compares three exact formulations on a set of SSP instances:
  1. BBC   – Branch-and-Benders-Cut          (branch_and_benders_cut.py)
  2. LSS   – Laporte-Salazar-González-Semet 2004  (lss_formulation.py)
  3. SSPMF – da Silva-Chaves-Yanasse 2024         (sspmf_formulation.py)

Usage
-----
    python benchmark.py [options]

Examples
--------
    # Standard benchmark on Catanzaro Tabela1C with 300s limit:
    python benchmark.py --time-limit 300

    # Only BBC, with triplet bounds and combinatorial cuts:
    python benchmark.py --formulations bbc --bbc-triplet-bounds --bbc-comb-cuts

    # All three formulations on a custom glob:
    python benchmark.py --instances "../../data/From_Felipe/data/Crama/**/*.txt"

    # Quick smoke test on the Shankar example:
    python benchmark.py --instances "../../data/Shankar/*.txt" --time-limit 60

Output columns (CSV / table)
-----------------------------
Core:
    instance, n_jobs, n_tools, capacity, formulation,
    status, obj_val, time_sec, optimal, gap_pct

BBC-specific (populated only for bbc rows):
    root_lp_bound, dual_bound, mip_gap_pct,
    nodes, lp_iters, cb_invocations,
    cuts_sec, cuts_benders, cuts_comb, cuts_frac
"""

import argparse
import csv
import glob
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import load_ssp_instance

# Default instance set — Catanzaro Tabela1C (primary benchmark)
_DEFAULT_INSTANCES = str(
    Path(__file__).parent.parent.parent
    / "data" / "From_Felipe" / "data" / "Catanzaro" / "Tabela1C" / "*.txt"
)


# ─────────────────────────────────────────────────────────────────────────────
# Per-formulation solvers
# ─────────────────────────────────────────────────────────────────────────────

def run_bbc(n_jobs, n_tools, capacity, tool_req, time_limit, verbose=False,
            worker_lp_reuse=False, use_fractional_cuts=False,
            use_combinatorial_cuts=False, use_triplet_bounds=False,
            parallel=False):
    """Run Branch-and-Benders-Cut. Returns (status, obj_val, elapsed_sec, extra_stats)."""
    from branch_and_benders_cut import BranchAndBendersCutSSP
    solver = BranchAndBendersCutSSP(
        n_jobs, n_tools, capacity, tool_req,
        worker_lp_reuse        = worker_lp_reuse,
        use_fractional_cuts    = use_fractional_cuts,
        use_combinatorial_cuts = use_combinatorial_cuts,
        use_triplet_bounds     = use_triplet_bounds,
        parallel               = parallel,
    )
    solver.build_master_problem(verbose=verbose)
    status, obj_val, sequence = solver.solve(time_limit=time_limit, verbose=verbose)
    elapsed = solver.solve_stats.get("wall_time_s", None)

    extra = {
        "root_lp_bound":  solver.solve_stats.get("root_lp_bound"),
        "dual_bound":     solver.solve_stats.get("dual_bound"),
        "mip_gap_pct":    solver.solve_stats.get("mip_gap_pct"),
        "nodes":          solver.solve_stats.get("nodes"),
        "lp_iters":       solver.solve_stats.get("lp_iters"),
        "cb_invocations": solver.solve_stats.get("cb_invocations"),
        "cuts_sec":       solver.solve_stats.get("cuts_sec"),
        "cuts_benders":   solver.solve_stats.get("cuts_benders"),
        "cuts_comb":      solver.solve_stats.get("cuts_comb"),
        "cuts_frac":      solver.solve_stats.get("cuts_frac"),
    }
    return status, obj_val, elapsed, extra


def run_lss(n_jobs, n_tools, capacity, tool_req, time_limit, verbose=False, **kwargs):
    """Run LSS formulation. Returns (status, obj_val, elapsed_sec, extra_stats)."""
    from lss_formulation import LSSFormulation
    solver = LSSFormulation(n_jobs, n_tools, capacity, tool_req)
    solver.build_model(verbose=verbose)
    t0 = time.perf_counter()
    status, obj_val, sequence = solver.solve(time_limit=time_limit, verbose=verbose)
    return status, obj_val, time.perf_counter() - t0, {}


def run_sspmf(n_jobs, n_tools, capacity, tool_req, time_limit, verbose=False, **kwargs):
    """Run SSPMF formulation. Returns (status, obj_val, elapsed_sec, extra_stats)."""
    from sspmf_formulation import SSPMFFormulation
    solver = SSPMFFormulation(n_jobs, n_tools, capacity, tool_req)
    solver.build_model(verbose=verbose)
    t0 = time.perf_counter()
    status, obj_val, sequence = solver.solve(time_limit=time_limit, verbose=verbose)
    return status, obj_val, time.perf_counter() - t0, {}


FORMULATION_RUNNERS = {
    'bbc'  : run_bbc,
    'lss'  : run_lss,
    'sspmf': run_sspmf,
}


# ─────────────────────────────────────────────────────────────────────────────
# Result record
# ─────────────────────────────────────────────────────────────────────────────

BBC_EXTRA_COLS = [
    "root_lp_bound", "dual_bound", "mip_gap_pct",
    "nodes", "lp_iters", "cb_invocations",
    "cuts_sec", "cuts_benders", "cuts_comb", "cuts_frac",
]

COLUMNS = (
    ["instance", "n_jobs", "n_tools", "capacity",
     "formulation", "status", "obj_val", "time_sec", "optimal", "gap_pct"]
    + BBC_EXTRA_COLS
    + ["notes"]
)


def _is_optimal(status):
    s = str(status).upper()
    return "OPTIMAL" in s or s == "1"


def run_instance(instance_path, formulations, time_limit, verbose, bbc_kwargs):
    """Run all requested formulations on a single instance. Returns list of row dicts."""
    try:
        n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance(instance_path)
    except Exception as e:
        return [
            dict(instance=Path(instance_path).name, n_jobs="?", n_tools="?",
                 capacity="?", formulation=f, status="LOAD_ERROR",
                 obj_val=None, time_sec=None, optimal=False, gap_pct=None,
                 **{c: None for c in BBC_EXTRA_COLS}, notes=str(e))
            for f in formulations
        ]

    rows = []
    best_obj = {}

    for form in formulations:
        runner  = FORMULATION_RUNNERS[form]
        status  = "NOT_RUN"
        obj_val = None
        elapsed = None
        extra   = {}
        notes   = ""

        try:
            if verbose:
                print(f"  [{form.upper():5}] {Path(instance_path).name} "
                      f"(n={n_jobs}, m={n_tools}, c={capacity})")
            kwargs = bbc_kwargs if form == "bbc" else {}
            status, obj_val, elapsed, extra = runner(
                n_jobs, n_tools, capacity, tool_req,
                time_limit, verbose=verbose, **kwargs
            )
        except ImportError as e:
            status = "SOLVER_UNAVAILABLE"
            notes  = str(e)
        except Exception as e:
            status = "ERROR"
            notes  = str(e)
            if verbose:
                import traceback; traceback.print_exc()

        if obj_val is not None:
            best_obj[form] = obj_val

        rows.append({
            "instance":    Path(instance_path).name,
            "n_jobs":      n_jobs,
            "n_tools":     n_tools,
            "capacity":    capacity,
            "formulation": form,
            "status":      str(status),
            "obj_val":     obj_val,
            "time_sec":    round(elapsed, 4) if elapsed is not None else None,
            "optimal":     _is_optimal(status),
            "gap_pct":     None,
            **{c: extra.get(c) for c in BBC_EXTRA_COLS},
            "notes":       notes,
        })

    # Cross-formulation gap vs best known
    all_objs = [v for v in best_obj.values() if v is not None]
    if all_objs:
        best_known = min(all_objs)
        for row in rows:
            if row["obj_val"] is not None and best_known > 0:
                row["gap_pct"] = round(
                    100.0 * (row["obj_val"] - best_known) / best_known, 2
                )
            elif row["obj_val"] is not None:
                row["gap_pct"] = 0.0

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────

def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nResults written to: {path}")


def print_table(rows):
    if not rows:
        print("No results to display.")
        return

    # Group by instance
    instances = {}
    for row in rows:
        instances.setdefault(row["instance"], []).append(row)

    # Core table
    hdr = (f"{'Instance':<28} {'Form':<6} {'N':>4} {'M':>4} {'C':>3}"
           f" {'Obj':>7} {'Time':>8} {'Opt':>4} {'Gap%':>6}"
           f" {'RootLB':>7} {'DualLB':>7} {'Gap%MIP':>8}"
           f" {'Nodes':>7} {'SECs':>5} {'Bend':>5} {'Comb':>5} {'Frac':>5}"
           f"  Status")
    sep = "─" * len(hdr)
    print(f"\n{sep}\n{hdr}\n{sep}")

    for inst_name, inst_rows in sorted(instances.items()):
        for row in inst_rows:
            obj   = f"{row['obj_val']:.1f}"   if row["obj_val"]   is not None else "N/A"
            t     = f"{row['time_sec']:.2f}"  if row["time_sec"]  is not None else "N/A"
            opt   = "Yes" if row["optimal"] else "No"
            gap   = f"{row['gap_pct']:.1f}%"  if row["gap_pct"]   is not None else "N/A"
            rlb   = f"{row['root_lp_bound']:.1f}" if row["root_lp_bound"] is not None else "—"
            dlb   = f"{row['dual_bound']:.1f}"    if row["dual_bound"]    is not None else "—"
            mgap  = f"{row['mip_gap_pct']:.2f}%"  if row["mip_gap_pct"]  is not None else "—"
            nodes = str(row["nodes"])  if row["nodes"]       is not None else "—"
            secs  = str(row["cuts_sec"])     if row["cuts_sec"]     is not None else "—"
            bend  = str(row["cuts_benders"]) if row["cuts_benders"] is not None else "—"
            comb  = str(row["cuts_comb"])    if row["cuts_comb"]    is not None else "—"
            frac  = str(row["cuts_frac"])    if row["cuts_frac"]    is not None else "—"

            print(f"{inst_name:<28} {row['formulation'].upper():<6}"
                  f" {row['n_jobs']:>4} {row['n_tools']:>4} {row['capacity']:>3}"
                  f" {obj:>7} {t:>8} {opt:>4} {gap:>6}"
                  f" {rlb:>7} {dlb:>7} {mgap:>8}"
                  f" {nodes:>7} {secs:>5} {bend:>5} {comb:>5} {frac:>5}"
                  f"  {row['status']}")
        print()

    print(sep)
    _print_summary(rows)


def _print_summary(rows):
    stats = defaultdict(lambda: {
        "n": 0, "n_opt": 0, "times": [], "objs": [],
        "nodes": [], "root_lbs": [], "mip_gaps": [],
    })
    for row in rows:
        f = row["formulation"]
        stats[f]["n"] += 1
        if row["optimal"]:
            stats[f]["n_opt"] += 1
        if row["time_sec"]      is not None: stats[f]["times"].append(row["time_sec"])
        if row["obj_val"]       is not None: stats[f]["objs"].append(row["obj_val"])
        if row["nodes"]         is not None: stats[f]["nodes"].append(row["nodes"])
        if row["root_lp_bound"] is not None: stats[f]["root_lbs"].append(row["root_lp_bound"])
        if row["mip_gap_pct"]   is not None: stats[f]["mip_gaps"].append(row["mip_gap_pct"])

    def _avg(lst):
        return sum(lst) / len(lst) if lst else float("nan")

    hdr = (f"\n{'Form':<8} {'Solved':>8} {'Opt%':>6} {'AvgTime':>9}"
           f" {'AvgObj':>8} {'AvgNodes':>10} {'AvgRootLB':>10} {'AvgMIPgap%':>11}")
    print(hdr)
    print("─" * len(hdr))
    for f, s in sorted(stats.items()):
        n        = s["n"]
        solved   = f"{s['n_opt']}/{n}"
        opt_pct  = 100. * s["n_opt"] / n
        print(
            f"{f.upper():<8} {solved:>8} {opt_pct:>5.1f}%"
            f" {_avg(s['times']):>9.2f}"
            f" {_avg(s['objs']):>8.2f}"
            f" {_avg(s['nodes']):>10.0f}"
            f" {_avg(s['root_lbs']):>10.2f}"
            f" {_avg(s['mip_gaps']):>10.2f}%"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Instance generation (smoke-test fallback)
# ─────────────────────────────────────────────────────────────────────────────

def generate_random_instance(n_jobs, n_tools, capacity, density=0.3, seed=42):
    import random
    rng = random.Random(seed)
    tool_req = {}
    for j in range(n_jobs):
        tools = [t for t in range(n_tools) if rng.random() < density]
        if not tools:
            tools = [rng.randint(0, n_tools - 1)]
        while len(tools) > capacity:
            tools.pop(rng.randrange(len(tools)))
        tool_req[j] = tools
    return tool_req


def save_instance(path, n_jobs, n_tools, capacity, tool_req):
    with open(path, "w") as f:
        f.write(f"{n_jobs} {n_tools} {capacity}\n")
        for j in range(n_jobs):
            row = [0] * n_tools
            for t in tool_req.get(j, []):
                row[t] = 1
            f.write(" ".join(map(str, row)) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark BBC vs LSS vs SSPMF on SSP instances",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--instances", "-i", default=_DEFAULT_INSTANCES,
        help="Glob pattern for instance .txt files")
    parser.add_argument("--time-limit", "-t", type=float, default=300.0,
        help="Time limit (s) per solver per instance")
    parser.add_argument("--output", "-o", default=None,
        help="Output CSV path (default: benchmark_results.csv in BBC/ dir)")
    parser.add_argument("--formulations", "-f", nargs="+",
        choices=["bbc", "lss", "sspmf"], default=["bbc", "lss", "sspmf"],
        help="Formulations to run")
    parser.add_argument("--verbose", "-v", action="store_true",
        help="Print solver progress per instance")
    parser.add_argument("--generate", "-g", action="store_true",
        help="Generate random instances if none found at the glob path")

    # ── BBC-specific flags ────────────────────────────────────────────────
    bbc_grp = parser.add_argument_group("BBC options")
    bbc_grp.add_argument("--bbc-lp-reuse",       action="store_true",
        help="Reuse DSP model across callback calls (worker_lp_reuse)")
    bbc_grp.add_argument("--bbc-frac-cuts",       action="store_true",
        help="Add Benders user cuts at LP relaxation nodes")
    bbc_grp.add_argument("--bbc-comb-cuts",       action="store_true",
        help="Use KTNS combinatorial cuts instead of LP Benders at integer nodes")
    bbc_grp.add_argument("--bbc-triplet-bounds",  action="store_true",
        help="Add O(n³) triplet lower bound constraints to master problem")
    bbc_grp.add_argument("--bbc-parallel",        action="store_true",
        help="Allow CPLEX multi-threaded B&B")

    args = parser.parse_args()

    bbc_kwargs = {
        "worker_lp_reuse":        args.bbc_lp_reuse,
        "use_fractional_cuts":    args.bbc_frac_cuts,
        "use_combinatorial_cuts": args.bbc_comb_cuts,
        "use_triplet_bounds":     args.bbc_triplet_bounds,
        "parallel":               args.bbc_parallel,
    }

    # ── Discover instances ────────────────────────────────────────────────
    files = sorted(glob.glob(args.instances, recursive=True))

    if not files and args.generate:
        print("No instances found — generating random test set …")
        gen_dir = Path(__file__).parent / "generated_instances"
        gen_dir.mkdir(parents=True, exist_ok=True)
        configs = [(5, 8, 4, 0.4), (8, 10, 4, 0.35), (10, 12, 5, 0.3)]
        for n_jobs, n_tools, cap, density in configs:
            for seed in range(3):
                fname = gen_dir / f"n{n_jobs}_m{n_tools}_c{cap}_s{seed}.txt"
                tool_req = generate_random_instance(n_jobs, n_tools, cap, density, seed)
                save_instance(str(fname), n_jobs, n_tools, cap, tool_req)
                files.append(str(fname))
        print(f"Generated {len(files)} instances in {gen_dir}")

    if not files:
        print(f"No instance files found matching: {args.instances}")
        print("Hint: use --generate for a quick smoke test, or adjust --instances.")
        sys.exit(1)

    # Print run header
    flag_summary = ", ".join(
        k.replace("use_", "").replace("_", "-")
        for k, v in bbc_kwargs.items() if v
    ) or "defaults"
    print(f"\nBenchmark: {len(files)} instance(s)")
    print(f"Formulations : {', '.join(f.upper() for f in args.formulations)}")
    print(f"Time limit   : {args.time_limit}s per solver")
    print(f"BBC flags    : {flag_summary}")
    print(f"{'─'*60}\n")

    all_rows = []
    for fp in files:
        print(f"▶  {Path(fp).name}")
        rows = run_instance(fp, args.formulations, args.time_limit,
                            args.verbose, bbc_kwargs)
        all_rows.extend(rows)

    print_table(all_rows)

    output_path = args.output or str(Path(__file__).parent / "benchmark_results.csv")
    write_csv(all_rows, output_path)


if __name__ == "__main__":
    main()
