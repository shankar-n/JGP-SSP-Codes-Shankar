"""
Benchmark runner: BBC vs LSS vs SSPMF for the Job Sequencing and Tool Switching Problem.

Compares three exact formulations on a set of SSP instances:
  1. BBC  – Branch-and-Benders-Cut (branch_and_benders_cut.py)
  2. LSS  – Laporte-Salazar-González-Semet 2004  (lss_formulation.py)
  3. SSPMF – da Silva-Chaves-Yanasse 2024         (sspmf_formulation.py)

Usage
-----
    python benchmark.py [--instances GLOB] [--time-limit SECS] [--output CSV]
                        [--formulations bbc lss sspmf] [--verbose]

Examples
--------
    # Run all formulations on all instances in standard set:
    python benchmark.py --instances "../Instances/**/*.txt" --time-limit 300

    # Run only BBC and LSS, save results to CSV:
    python benchmark.py --formulations bbc lss --output results.csv

    # Quick smoke test on example instance:
    python benchmark.py --instances "../Instances/Shankar/*.txt" --time-limit 60

Output columns
--------------
instance, n_jobs, n_tools, capacity, formulation, status,
obj_val, time_sec, optimal, gap_pct, notes
"""

import argparse
import csv
import glob
import os
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import load_ssp_instance


# ─────────────────────────────────────────────────────────────────────────────
# Per-formulation solvers
# ─────────────────────────────────────────────────────────────────────────────

def run_bbc(n_jobs, n_tools, capacity, tool_req, time_limit, verbose=False):
    """Run Branch-and-Benders-Cut and return (status, obj_val, elapsed_sec)."""
    from branch_and_benders_cut import BranchAndBendersCutSSP
    solver = BranchAndBendersCutSSP(n_jobs, n_tools, capacity, tool_req)
    solver.build_master_problem(verbose=verbose)
    t0 = time.perf_counter()
    status, obj_val, sequence = solver.solve(time_limit=time_limit, verbose=verbose)
    elapsed = time.perf_counter() - t0
    return status, obj_val, elapsed


def run_lss(n_jobs, n_tools, capacity, tool_req, time_limit, verbose=False):
    """Run LSS formulation and return (status, obj_val, elapsed_sec)."""
    from lss_formulation import LSSFormulation
    solver = LSSFormulation(n_jobs, n_tools, capacity, tool_req)
    solver.build_model(verbose=verbose)
    t0 = time.perf_counter()
    status, obj_val, sequence = solver.solve(time_limit=time_limit, verbose=verbose)
    elapsed = time.perf_counter() - t0
    return status, obj_val, elapsed


def run_sspmf(n_jobs, n_tools, capacity, tool_req, time_limit, verbose=False):
    """Run SSPMF formulation and return (status, obj_val, elapsed_sec)."""
    from sspmf_formulation import SSPMFFormulation
    solver = SSPMFFormulation(n_jobs, n_tools, capacity, tool_req)
    solver.build_model(verbose=verbose)
    t0 = time.perf_counter()
    status, obj_val, sequence = solver.solve(time_limit=time_limit, verbose=verbose)
    elapsed = time.perf_counter() - t0
    return status, obj_val, elapsed


FORMULATION_RUNNERS = {
    'bbc'  : run_bbc,
    'lss'  : run_lss,
    'sspmf': run_sspmf,
}


# ─────────────────────────────────────────────────────────────────────────────
# Result record
# ─────────────────────────────────────────────────────────────────────────────

def _is_optimal(status):
    """Return True if the solver status string represents an optimal solution."""
    s = str(status).upper()
    return 'OPTIMAL' in s or s == '1' or s == 'OPTIMAL'


def run_instance(instance_path, formulations, time_limit, verbose):
    """
    Run all requested formulations on a single instance.

    Returns
    -------
    list of dicts, one per formulation
    """
    try:
        n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance(instance_path)
    except Exception as e:
        return [{'instance': Path(instance_path).name,
                 'n_jobs': '?', 'n_tools': '?', 'capacity': '?',
                 'formulation': f, 'status': 'LOAD_ERROR',
                 'obj_val': None, 'time_sec': None,
                 'optimal': False, 'gap_pct': None, 'notes': str(e)}
                for f in formulations]

    rows = []
    best_obj = {}   # formulation → obj_val (for gap computation)

    for form in formulations:
        runner = FORMULATION_RUNNERS[form]
        status  = 'NOT_RUN'
        obj_val = None
        elapsed = None
        notes   = ''

        try:
            if verbose:
                print(f"  [{form.upper()}] {Path(instance_path).name} "
                      f"(n={n_jobs}, m={n_tools}, c={capacity})")
            status, obj_val, elapsed = runner(
                n_jobs, n_tools, capacity, tool_req, time_limit, verbose=verbose
            )
        except ImportError as e:
            status = 'SOLVER_UNAVAILABLE'
            notes  = str(e)
        except Exception as e:
            status = 'ERROR'
            notes  = str(e)
            if verbose:
                import traceback
                traceback.print_exc()

        if obj_val is not None:
            best_obj[form] = obj_val

        rows.append({
            'instance'   : Path(instance_path).name,
            'n_jobs'     : n_jobs,
            'n_tools'    : n_tools,
            'capacity'   : capacity,
            'formulation': form,
            'status'     : str(status),
            'obj_val'    : obj_val,
            'time_sec'   : round(elapsed, 4) if elapsed is not None else None,
            'optimal'    : _is_optimal(status),
            'gap_pct'    : None,   # filled in post-processing
            'notes'      : notes,
        })

    # Cross-formulation gap: how far each solver is from the best known
    all_objs = [v for v in best_obj.values() if v is not None]
    if all_objs:
        best_known = min(all_objs)
        for row in rows:
            if row['obj_val'] is not None and best_known > 0:
                row['gap_pct'] = round(
                    100.0 * (row['obj_val'] - best_known) / best_known, 2
                )
            elif row['obj_val'] is not None:
                row['gap_pct'] = 0.0

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────

COLUMNS = [
    'instance', 'n_jobs', 'n_tools', 'capacity',
    'formulation', 'status', 'obj_val', 'time_sec',
    'optimal', 'gap_pct', 'notes'
]


def write_csv(rows, path):
    """Write result rows to a CSV file."""
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nResults written to: {path}")


def print_table(rows):
    """Pretty-print results as a formatted table."""
    if not rows:
        print("No results to display.")
        return

    # Group by instance
    instances = {}
    for row in rows:
        key = row['instance']
        instances.setdefault(key, []).append(row)

    header = (
        f"{'Instance':<30} {'Form':<8} {'N':>4} {'M':>4} {'C':>3} "
        f"{'Obj':>8} {'Time(s)':>9} {'Opt':>4} {'Gap%':>6} Status"
    )
    sep = '-' * len(header)

    print(f"\n{sep}")
    print(header)
    print(sep)

    for inst_name, inst_rows in sorted(instances.items()):
        for row in inst_rows:
            obj  = f"{row['obj_val']:.1f}" if row['obj_val'] is not None else 'N/A'
            t    = f"{row['time_sec']:.2f}" if row['time_sec'] is not None else 'N/A'
            opt  = 'Yes' if row['optimal'] else 'No'
            gap  = f"{row['gap_pct']:.1f}%" if row['gap_pct'] is not None else 'N/A'
            form = row['formulation'].upper()
            print(
                f"{inst_name:<30} {form:<8} {row['n_jobs']:>4} {row['n_tools']:>4} "
                f"{row['capacity']:>3} {obj:>8} {t:>9} {opt:>4} {gap:>6} "
                f"{row['status']}"
            )
        print()

    print(sep)

    # Summary statistics
    _print_summary(rows)


def _print_summary(rows):
    """Print per-formulation summary statistics."""
    from collections import defaultdict
    stats = defaultdict(lambda: {'n': 0, 'n_opt': 0, 'times': [], 'objs': []})

    for row in rows:
        f = row['formulation']
        stats[f]['n'] += 1
        if row['optimal']:
            stats[f]['n_opt'] += 1
        if row['time_sec'] is not None:
            stats[f]['times'].append(row['time_sec'])
        if row['obj_val'] is not None:
            stats[f]['objs'].append(row['obj_val'])

    print(f"\n{'Formulation':<12} {'Solved':>8} {'Opt%':>7} {'Avg Time':>10} "
          f"{'Avg Obj':>9}")
    print('-' * 50)
    for f, s in sorted(stats.items()):
        n        = s['n']
        n_opt    = s['n_opt']
        opt_pct  = 100.0 * n_opt / n if n > 0 else 0
        avg_time = sum(s['times']) / len(s['times']) if s['times'] else float('nan')
        avg_obj  = sum(s['objs'])  / len(s['objs'])  if s['objs']  else float('nan')
        print(f"{f.upper():<12} {f'{n_opt}/{n}':>8} {opt_pct:>6.1f}% "
              f"{avg_time:>10.2f} {avg_obj:>9.2f}")


# ─────────────────────────────────────────────────────────────────────────────
# Instance generator (for testing when standard instances are unavailable)
# ─────────────────────────────────────────────────────────────────────────────

def generate_random_instance(n_jobs, n_tools, capacity, density=0.3, seed=42):
    """
    Generate a random SSP instance.

    Parameters
    ----------
    n_jobs   : int
    n_tools  : int
    capacity : int
    density  : float   probability that job j requires tool t
    seed     : int

    Returns
    -------
    tool_req : dict {job: [tools]}
    """
    import random
    rng = random.Random(seed)
    tool_req = {}
    for j in range(n_jobs):
        tools = [t for t in range(n_tools) if rng.random() < density]
        if not tools:
            tools = [rng.randint(0, n_tools - 1)]
        # Ensure tool set fits in magazine
        while len(tools) > capacity:
            tools.pop(rng.randrange(len(tools)))
        tool_req[j] = tools
    return tool_req


def save_instance(path, n_jobs, n_tools, capacity, tool_req):
    """Save an instance in the standard format used by load_ssp_instance."""
    with open(path, 'w') as f:
        f.write(f"{n_jobs} {n_tools} {capacity}\n")
        for j in range(n_jobs):
            tools = tool_req.get(j, [])
            row   = [0] * n_tools
            for t in tools:
                row[t] = 1
            f.write(' '.join(map(str, row)) + '\n')


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Benchmark BBC vs LSS vs SSPMF formulations for SSP'
    )
    parser.add_argument(
        '--instances', '-i',
        default='../Instances/**/*.txt',
        help='Glob pattern for instance files (default: ../Instances/**/*.txt)'
    )
    parser.add_argument(
        '--time-limit', '-t',
        type=float, default=300.0,
        help='Time limit in seconds per instance per formulation (default: 300)'
    )
    parser.add_argument(
        '--output', '-o',
        default=None,
        help='Output CSV file path (default: benchmark_results.csv)'
    )
    parser.add_argument(
        '--formulations', '-f',
        nargs='+', choices=['bbc', 'lss', 'sspmf'],
        default=['bbc', 'lss', 'sspmf'],
        help='Formulations to run (default: all three)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print solver progress'
    )
    parser.add_argument(
        '--generate', '-g',
        action='store_true',
        help='Generate random test instances if no instances found'
    )
    args = parser.parse_args()

    # ── Discover instances ────────────────────────────────────────────────
    base_dir = Path(__file__).parent
    pattern  = str(base_dir / args.instances) if not os.path.isabs(args.instances) else args.instances
    files    = sorted(glob.glob(pattern, recursive=True))

    if not files and args.generate:
        print("No instances found — generating random test set …")
        gen_dir = base_dir / 'Instances' / 'Generated'
        gen_dir.mkdir(parents=True, exist_ok=True)
        configs = [
            (5,  8,  4, 0.4),
            (8,  10, 4, 0.35),
            (10, 12, 5, 0.3),
            (12, 15, 5, 0.3),
        ]
        for n_jobs, n_tools, capacity, density in configs:
            for seed in range(3):
                fname = gen_dir / f"n{n_jobs}_m{n_tools}_c{capacity}_s{seed}.txt"
                tool_req = generate_random_instance(
                    n_jobs, n_tools, capacity, density=density, seed=seed
                )
                save_instance(str(fname), n_jobs, n_tools, capacity, tool_req)
                files.append(str(fname))
        print(f"Generated {len(files)} instances in {gen_dir}")

    if not files:
        print(f"No instance files found matching: {pattern}")
        print("Use --generate to create random instances, or adjust --instances.")
        sys.exit(1)

    print(f"\nRunning benchmark on {len(files)} instance(s)")
    print(f"Formulations : {', '.join(f.upper() for f in args.formulations)}")
    print(f"Time limit   : {args.time_limit}s per solver per instance")
    print(f"{'─'*60}\n")

    all_rows = []
    for fp in files:
        print(f"▶ {Path(fp).name}")
        rows = run_instance(
            fp, args.formulations, args.time_limit, args.verbose
        )
        all_rows.extend(rows)

    # ── Output ────────────────────────────────────────────────────────────
    print_table(all_rows)

    output_path = args.output or str(base_dir / 'benchmark_results.csv')
    write_csv(all_rows, output_path)


if __name__ == '__main__':
    main()
