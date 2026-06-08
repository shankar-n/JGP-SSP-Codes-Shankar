"""
BBC Full Benchmark Runner
=========================

Runs all configured solver × instance pairs and appends results to
raw_results.csv one row at a time.  Safe to interrupt and restart:
already-completed (instance, config) pairs are skipped on resume.

Architecture
------------
Each solver call runs in a child process (multiprocessing.Process).
The main process joins with timeout = time_limit + 90 s.  If the child
is still alive after the grace period, it is killed and the run is
recorded as 'time_limit'.  This guarantees wall-clock safety even when
CPLEX's internal time limit misbehaves inside a callback.

Usage
-----
    # Full run — primary sets, all 10 configs:
    python benchmark_runner.py

    # Primary sets only:
    python benchmark_runner.py --sets primary

    # Secondary sets (Laporte3-5), BBC+LSS only:
    python benchmark_runner.py --sets secondary

    # Specific benchmark sets:
    python benchmark_runner.py --only-sets Catanzaro Crama

    # Specific configs (useful for debugging):
    python benchmark_runner.py --configs BBC-K BBC-K+F LSS

    # Dry run — show the work queue without executing:
    python benchmark_runner.py --dry-run

    # Verbose solver output (for debugging a single run):
    python benchmark_runner.py --only-sets Catanzaro --configs BBC-K --verbose
"""

import argparse
import csv
import multiprocessing
import os
import sys
import time
from pathlib import Path

# ── sys.path: add src/ and src/SSP/ so imports work from any working directory
_BBC = Path(__file__).resolve().parent       # src/BBC/
_SRC = _BBC.parent                           # src/
sys.path.insert(0, str(_SRC))
sys.path.insert(0, str(_SRC / "SSP"))
sys.path.insert(0, str(_BBC))

from benchmark_config import (
    COLUMNS, BBC_DIAG_COLS, RAW_CSV,
    get_instances, get_configs_for_set,
    PRIMARY_SETS, SECONDARY_SETS, ALL_SETS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Worker (runs in a subprocess — must be module-level for spawn compatibility)
# ─────────────────────────────────────────────────────────────────────────────

def _worker(instance_path, benchmark_set, config, time_limit, result_queue, verbose):
    """
    Execute one (instance, config) pair.  Puts a single dict onto result_queue.
    Runs inside a child process so crashes / hangs don't affect the parent.
    """
    # Re-apply sys.path inside subprocess (spawn starts fresh)
    import sys
    from pathlib import Path as _Path
    _bbc = _Path(__file__).resolve().parent
    _src = _bbc.parent
    for p in [str(_src), str(_src / "SSP"), str(_bbc)]:
        if p not in sys.path:
            sys.path.insert(0, p)

    import time as _time
    import traceback

    from utils import load_ssp_instance

    # ── Load instance ──────────────────────────────────────────────────────
    try:
        J, T, C, A, tool_req = load_ssp_instance(instance_path)
    except Exception as e:
        result_queue.put({
            "instance": Path(instance_path).stem,
            "benchmark_set": benchmark_set,
            "J": None, "T": None, "C": None, "density": None,
            "solver": config.get("solver", "?"),
            "config": config["label"],
            "comb_cuts": config.get("comb_cuts"), "frac_cuts": config.get("frac_cuts"),
            "triplet_bounds": config.get("triplet_bounds"),
            "status": "load_error", "obj": None, "time_s": None, "gap_pct": None,
            **{c: None for c in BBC_DIAG_COLS},
            "notes": str(e)[:400],
        })
        return

    density = (sum(len(v) for v in tool_req.values()) / (J * T)) if J * T > 0 else 0.0

    base = {
        "instance":      Path(instance_path).stem,
        "benchmark_set": benchmark_set,
        "J": J, "T": T, "C": C, "density": round(density, 4),
        "solver":         config["solver"],
        "config":         config["label"],
        "comb_cuts":      config.get("comb_cuts"),
        "frac_cuts":      config.get("frac_cuts"),
        "triplet_bounds": config.get("triplet_bounds"),
    }
    null_diag = {c: None for c in BBC_DIAG_COLS}

    try:
        solver_name = config["solver"]

        # ── BBC ───────────────────────────────────────────────────────────
        if solver_name == "BBC":
            from branch_and_benders_cut import BranchAndBendersCutSSP
            solver = BranchAndBendersCutSSP(
                J, T, C, tool_req,
                worker_lp_reuse        = config.get("lp_reuse", False),
                use_fractional_cuts    = config["frac_cuts"],
                use_combinatorial_cuts = config["comb_cuts"],
                use_triplet_bounds     = config["triplet_bounds"],
                parallel               = False,
            )
            solver.build_master_problem(verbose=verbose)
            status, obj_val, _seq = solver.solve(time_limit=time_limit, verbose=verbose)
            st = solver.solve_stats
            result_queue.put({**base,
                "status":   str(status),
                "obj":      obj_val,
                "time_s":   st.get("wall_time_s"),
                "gap_pct":  st.get("mip_gap_pct"),
                "nodes":         st.get("nodes"),
                "lp_iters":      st.get("lp_iters"),
                "cb_invocations":st.get("cb_invocations"),
                "cuts_sec":      st.get("cuts_sec"),
                "cuts_benders":  st.get("cuts_benders"),
                "cuts_comb":     st.get("cuts_comb"),
                "cuts_frac":     st.get("cuts_frac"),
                "root_lp_bound": st.get("root_lp_bound"),
                "dual_bound":    st.get("dual_bound"),
                "notes": "",
            })

        # ── LSS ───────────────────────────────────────────────────────────
        elif solver_name == "LSS":
            from lss_formulation import LSSFormulation
            solver = LSSFormulation(J, T, C, tool_req)
            solver.build_model(verbose=verbose)
            t0 = _time.perf_counter()
            status, obj_val, _seq = solver.solve(time_limit=time_limit, verbose=verbose)
            result_queue.put({**base,
                "status": str(status), "obj": obj_val,
                "time_s": round(_time.perf_counter() - t0, 4),
                "gap_pct": None, **null_diag, "notes": "",
            })

        # ── SSPMF ─────────────────────────────────────────────────────────
        # use_constraint_21=False: per da Silva (2024) this gives better performance
        elif solver_name == "SSPMF":
            from sspmf_formulation import SSPMFFormulation
            solver = SSPMFFormulation(J, T, C, tool_req, use_constraint_21=False)
            solver.build_model(verbose=verbose)
            t0 = _time.perf_counter()
            status, obj_val, _seq = solver.solve(time_limit=time_limit, verbose=verbose)
            result_queue.put({**base,
                "status": str(status), "obj": obj_val,
                "time_s": round(_time.perf_counter() - t0, 4),
                "gap_pct": None, **null_diag, "notes": "",
            })

        else:
            result_queue.put({**base,
                "status": "error", "obj": None, "time_s": None, "gap_pct": None,
                **null_diag, "notes": f"Unknown solver: {solver_name}",
            })

    except Exception:
        result_queue.put({**base,
            "status": "error", "obj": None, "time_s": None, "gap_pct": None,
            **null_diag, "notes": traceback.format_exc()[-600:],
        })


# ─────────────────────────────────────────────────────────────────────────────
# CSV helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_completed(csv_path):
    """Return a set of completed (instance_stem, config_label) pairs."""
    done = set()
    if not csv_path.exists():
        return done
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            done.add((row["instance"], row["config"]))
    return done


def _append_row(csv_path, row):
    """Append one result row to the CSV, writing the header if the file is new."""
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

def build_work_queue(sets, config_filter=None, only_sets=None):
    """
    Return a list of (benchmark_set, instance_path, config_dict, time_limit) tuples.
    """
    work = []
    for bset, ipath, tl in get_instances(sets):
        if only_sets and bset not in only_sets:
            continue
        configs = get_configs_for_set(bset)
        if config_filter:
            configs = [c for c in configs if c["label"] in config_filter]
        for cfg in configs:
            work.append((bset, ipath, cfg, tl))
    return work


def run_benchmark(sets=None, config_filter=None, only_sets=None,
                  output_csv=None, dry_run=False, verbose=False, limit=None):
    """
    Main entry point.  Runs all pending (instance, config) pairs sequentially,
    each in an isolated subprocess with hard timeout.
    """
    if sets is None:
        sets = ALL_SETS
    csv_path = Path(output_csv) if output_csv else RAW_CSV

    work = build_work_queue(sets, config_filter, only_sets)
    completed = _load_completed(csv_path)

    pending = [
        (bset, ipath, cfg, tl)
        for bset, ipath, cfg, tl in work
        if (Path(ipath).stem, cfg["label"]) not in completed
    ]

    if limit is not None:
        # Limit by unique instances, keeping all configs per instance
        unique_insts = list(dict.fromkeys((bset, ipath) for bset, ipath, _, _ in pending))[:limit]
        inst_set = set(unique_insts)
        pending = [(bset, ipath, cfg, tl) for bset, ipath, cfg, tl in pending
                   if (bset, ipath) in inst_set]

    total          = len(work)
    n_already_done = len(completed)
    n_limit_excl   = (total - n_already_done - len(pending)) if limit is not None else 0
    print(f"\nBBC Benchmark Runner")
    limit_note = f", {n_limit_excl} excluded by --limit={limit}" if limit is not None else ""
    print(f"  Work queue : {total} pairs  ({n_already_done} done in CSV, {len(pending)} to run{limit_note})")
    print(f"  Output CSV : {csv_path}")
    if dry_run:
        print(f"\n  [DRY RUN] — first 10 pending pairs:")
        for row in pending[:10]:
            print(f"    {row[0]:<12}  {Path(row[1]).stem:<30}  {row[2]['label']}")
        return

    ctx = multiprocessing.get_context("spawn")

    for idx, (bset, ipath, cfg, tl) in enumerate(pending, 1):
        inst_name = Path(ipath).stem
        print(f"[{idx:>5}/{len(pending)}]  {bset:<12}  {inst_name:<35}  {cfg['label']}", flush=True)

        q = ctx.Queue()
        p = ctx.Process(target=_worker, args=(ipath, bset, cfg, tl, q, verbose))
        t_start = time.perf_counter()
        p.start()
        p.join(timeout=tl + 90)   # +90 s OS-level grace period

        if p.is_alive():
            # Hard timeout: kill the subprocess
            p.terminate()
            p.join(10)
            if p.is_alive():
                p.kill()
                p.join(5)
            elapsed = time.perf_counter() - t_start
            row = {
                "instance": inst_name, "benchmark_set": bset,
                "J": None, "T": None, "C": None, "density": None,
                "solver": cfg["solver"], "config": cfg["label"],
                "comb_cuts": cfg.get("comb_cuts"), "frac_cuts": cfg.get("frac_cuts"),
                "triplet_bounds": cfg.get("triplet_bounds"),
                "status": "time_limit", "obj": None,
                "time_s": round(elapsed, 2), "gap_pct": None,
                **{c: None for c in BBC_DIAG_COLS},
                "notes": "OS timeout",
            }
            print(f"         → TIMEOUT after {elapsed:.0f}s")
        else:
            # Process finished — pick up the result
            try:
                row = q.get(timeout=5)
                status_str = row.get("status", "?")
                obj_str = f"obj={row['obj']}" if row.get("obj") is not None else "no_obj"
                t_str = f"{row['time_s']:.1f}s" if row.get("time_s") is not None else "?s"
                print(f"         → {status_str}  {obj_str}  {t_str}")
            except Exception as e:
                # Subprocess crashed without putting anything in the queue
                row = {
                    "instance": inst_name, "benchmark_set": bset,
                    "J": None, "T": None, "C": None, "density": None,
                    "solver": cfg["solver"], "config": cfg["label"],
                    "comb_cuts": cfg.get("comb_cuts"), "frac_cuts": cfg.get("frac_cuts"),
                    "triplet_bounds": cfg.get("triplet_bounds"),
                    "status": "error", "obj": None,
                    "time_s": round(time.perf_counter() - t_start, 2), "gap_pct": None,
                    **{c: None for c in BBC_DIAG_COLS},
                    "notes": f"subprocess crash: {e}",
                }
                print(f"         → CRASH (no result in queue): {e}")

        _append_row(csv_path, row)

    print(f"\nDone. Results at: {csv_path}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="BBC full benchmark runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--sets", choices=["primary", "secondary", "all"], default="primary",
        help="Which instance sets to run")
    parser.add_argument("--only-sets", nargs="+", metavar="LABEL",
        help="Restrict to specific set labels (e.g. Catanzaro Crama)")
    parser.add_argument("--configs", nargs="+", metavar="LABEL",
        help="Restrict to specific config labels (e.g. BBC-K BBC-K+F LSS)")
    parser.add_argument("--output", "-o", default=None,
        help="Output CSV path (default: src/BBC/raw_results.csv)")
    parser.add_argument("--dry-run", action="store_true",
        help="Print work queue without running anything")
    parser.add_argument("--verbose", "-v", action="store_true",
        help="Pass verbose=True to each solver")
    parser.add_argument("--limit", "-n", type=int, default=None,
        help="Limit pilot run to N instances (all configs still run per instance)")
    args = parser.parse_args()

    if args.sets == "primary":
        sets = PRIMARY_SETS
    elif args.sets == "secondary":
        sets = SECONDARY_SETS
    else:
        sets = ALL_SETS

    run_benchmark(
        sets=sets,
        config_filter=set(args.configs) if args.configs else None,
        only_sets=set(args.only_sets) if args.only_sets else None,
        output_csv=args.output,
        dry_run=args.dry_run,
        verbose=args.verbose,
        limit=args.limit,
    )


if __name__ == "__main__":
    # Required for multiprocessing spawn on Windows
    multiprocessing.freeze_support()
    main()
