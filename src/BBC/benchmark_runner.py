"""
BBC Full Benchmark Runner
=========================

Runs all configured solver × instance pairs and appends results to
raw_results.csv one row at a time.  Safe to interrupt and restart:
already-completed (family, instance, J, T, C, config) pairs are skipped on
resume.  The full identity is essential because Crama reuses file names at
several capacities.

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
from functools import lru_cache
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
    MAX_CONSECUTIVE_TIMEOUTS,
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

    from utils import load_ssp_instance, compute_ktns

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

    def _ktns_of(seq):
        # Canonical EMPTY-START switch count of a returned sequence. Lets us compare
        # all solvers in one convention regardless of each model's native objective
        # (esp. SSPMF, whose Z_M is free-initial). None if no valid permutation.
        if seq is not None and sorted(seq) == list(range(J)):
            return compute_ktns(list(seq), tool_req, C)[0]
        return None

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
                use_conflict_cuts      = config.get("conflict_cuts", False),
                use_primal_heuristic   = config.get("primal_heuristic", False),
                use_pareto_cuts        = config.get("pareto_cuts", False),
            )
            solver.build_master_problem(verbose=verbose)
            # Save CPLEX's default per-instance log next to the CSV, so any single
            # instance can be opened and debugged after the run:  logs/<config>/<inst>.log
            import os as _os
            _ldir = _os.path.join("logs", config["label"])
            _os.makedirs(_ldir, exist_ok=True)
            # Crama reuses each instance stem at four capacities.  The old
            # stem-only name let concurrent shards overwrite one another's
            # CPLEX logs; include the full persisted identity instead.
            _log_name = (
                f"{benchmark_set}__{Path(instance_path).stem}__"
                f"J{J}_T{T}_C{C}.log"
            )
            _lf = open(_os.path.join(_ldir, _log_name), "w")
            for _stream in ("set_results_stream", "set_log_stream", "set_warning_stream"):
                try:
                    getattr(solver.cpx, _stream)(_lf)
                except Exception:
                    pass
            status, obj_val, seq = solver.solve(time_limit=time_limit, verbose=verbose)
            _lf.close()
            st = solver.solve_stats
            result_queue.put({**base,
                "status":   str(status),
                "obj":      obj_val,
                "obj_ktns": _ktns_of(seq),
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
            status, obj_val, seq = solver.solve(time_limit=time_limit, verbose=verbose)
            result_queue.put({**base,
                "status": str(status), "obj": obj_val, "obj_ktns": _ktns_of(seq),
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
            status, obj_val, seq = solver.solve(time_limit=time_limit, verbose=verbose)
            result_queue.put({**base,
                "status": str(status), "obj": obj_val, "obj_ktns": _ktns_of(seq),
                "time_s": round(_time.perf_counter() - t0, 4),
                "gap_pct": None, **null_diag, "notes": "",
            })

        # ── Catanzaro F4 (Catanzaro, Gouveia, Labbé 2015) ──────────────────
        elif solver_name == "CATZ":
            from catanzaro_formulation import CatanzaroFormulation
            solver = CatanzaroFormulation(J, T, C, tool_req)
            solver.build_model(verbose=verbose)
            t0 = _time.perf_counter()
            status, obj_val, seq = solver.solve(time_limit=time_limit, verbose=verbose)
            result_queue.put({**base,
                "status": str(status), "obj": obj_val, "obj_ktns": _ktns_of(seq),
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

def _as_int(value):
    """Return a CSV integer field in the same form as an instance header."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _row_key(row):
    """Return a complete persisted-run key, or None for an incomplete row."""
    benchmark_set = row.get("benchmark_set")
    instance = row.get("instance")
    config = row.get("config")
    J, T, C = (_as_int(row.get(name)) for name in ("J", "T", "C"))
    if not benchmark_set or not instance or not config or None in (J, T, C):
        return None
    return benchmark_set, instance, J, T, C, config


def _load_completed(csv_path):
    """Return completed full-instance keys from an existing result CSV."""
    done = set()
    if not csv_path.exists():
        return done
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            key = _row_key(row)
            if key is not None:
                done.add(key)
    return done


def _append_row(csv_path, row):
    """Append one result row to the CSV, writing the header if the file is new."""
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _load_completed_status(csv_path):
    """Return {full-instance key: status_lower} from an existing result CSV."""
    status = {}
    if not csv_path.exists():
        return status
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            key = _row_key(row)
            if key is not None:
                status[key] = str(row.get("status", "")).lower()
    return status


@lru_cache(maxsize=None)
def _instance_features(path):
    """Cheap token-based feature read (also handles Crama's 3-line header)."""
    try:
        with open(path) as f:
            tokens = f.read().split()
        J, T, C = (int(v) for v in tokens[:3])
        ones = sum(1 for value in tokens[3:3 + J * T] if value == "1")
        density = ones / (J * T) if J * T else 0.0
        return J, T, C, density
    except Exception:
        return 10**6, 10**6, 0, 1.0      # unparseable -> sort last (treat as hardest)


@lru_cache(maxsize=None)
def _campaign_difficulty_key(path):
    """Return the immutable ordering key used by the 2026-08 campaign.

    The original campaign parser read ``J T C`` from one physical line.  The
    Crama files store those values on three lines, so they deliberately fell
    into the sentinel bucket and were then ordered by their already-sorted
    paths.  Correcting the feature parser later changed which identities
    belonged to each persisted shard.  Resume compatibility is more important
    than rebalancing an existing campaign, so sharding retains the historical
    key while :func:`_instance_features` supplies the correct six-field identity.
    """
    try:
        with open(path) as handle:
            J, T, C = (int(v) for v in handle.readline().split()[:3])
            ones = sum(line.count("1") for line in handle)
        density = ones / (J * T) if J * T else 0.0
        return J, T, round(density, 4), -int(C)
    except Exception:
        return 10**6, 10**6, 1.0, 0


def _work_key(benchmark_set, instance_path, config_label):
    """Full identity used to decide whether a queued run is already recorded."""
    J, T, C, _density = _instance_features(instance_path)
    return benchmark_set, Path(instance_path).stem, J, T, C, config_label


def _difficulty_key(path):
    """Stable campaign ordering key (kept separate from identity parsing)."""
    return _campaign_difficulty_key(path)


# ─────────────────────────────────────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────────────────────────────────────

def build_work_queue(sets, config_filter=None, only_sets=None, shard=None):
    """
    Return a list of (benchmark_set, instance_path, config_dict, time_limit) tuples,
    ordered EASIEST-FIRST by instance difficulty.  Instance-major, config-minor.
    `shard=(i, n)` keeps only every n-th instance (offset i), so one config's
    instances can be split across n parallel cluster jobs; balanced by difficulty.
    """
    insts = []
    for bset, ipath, tl in get_instances(sets):
        if only_sets and bset not in only_sets:
            continue
        insts.append((bset, ipath, tl))
    insts.sort(key=lambda r: _difficulty_key(r[1]))      # easiest first
    if shard is not None:
        _i, _n = shard
        insts = insts[_i::_n]                            # this job's slice of instances
    work = []
    for bset, ipath, tl in insts:
        configs = get_configs_for_set(bset)
        if config_filter:
            configs = [c for c in configs if c["label"] in config_filter]
        for cfg in configs:
            work.append((bset, ipath, cfg, tl))
    return work


def run_benchmark(sets=None, config_filter=None, only_sets=None,
                  output_csv=None, dry_run=False, verbose=False, limit=None,
                  max_consecutive_timeouts=None, shard=None):
    """
    Main entry point.  Runs pending (instance, config) pairs EASIEST-FIRST, each in
    an isolated subprocess with a hard timeout.  Resumable: CSV-completed pairs are
    skipped but still seed the early-stop counters.

    Early-stop: for each config INDEPENDENTLY, after `max_consecutive_timeouts`
    consecutive non-optimal results on increasingly hard instances, the remaining
    harder instances are skipped for that config.  None -> config default
    (MAX_CONSECUTIVE_TIMEOUTS); 0 -> disabled.
    """
    if sets is None:
        sets = ALL_SETS
    csv_path = Path(output_csv) if output_csv else RAW_CSV
    if max_consecutive_timeouts is None:
        max_consecutive_timeouts = MAX_CONSECUTIVE_TIMEOUTS

    work = build_work_queue(sets, config_filter, only_sets, shard=shard)   # easiest-first
    completed_status = _load_completed_status(csv_path)

    if limit is not None:
        # Limit to the N easiest unique instances (all their configs)
        unique_insts = list(dict.fromkeys((bset, ipath) for bset, ipath, _, _ in work))[:limit]
        inst_set = set(unique_insts)
        work = [w for w in work if (w[0], w[1]) in inst_set]

    pending = [w for w in work
               if _work_key(w[0], w[1], w[2]["label"]) not in completed_status]
    n_already_done = len(work) - len(pending)

    print(f"\nBBC Benchmark Runner")
    es_note = (f"early-stop after {max_consecutive_timeouts} consecutive non-optimal / config"
               if max_consecutive_timeouts else "early-stop DISABLED")
    print(f"  Work queue : {len(work)} pairs  ({n_already_done} done in CSV, {len(pending)} to run)")
    print(f"  Order      : easiest-first;  {es_note}")
    print(f"  Output CSV : {csv_path}")
    if dry_run:
        print(f"\n  [DRY RUN] — first 10 pending pairs (easiest-first):")
        for row in pending[:10]:
            print(f"    {row[0]:<12}  {Path(row[1]).stem:<30}  {row[2]['label']}")
        return

    ctx = multiprocessing.get_context("spawn")

    consec  = {}     # config_label -> consecutive non-optimal count (difficulty order)
    stopped = set()  # config_labels that have hit the cap

    def _optimal(s):
        return "optimal" in (s or "").lower()

    def _bump(label, status_str):
        if _optimal(status_str):
            consec[label] = 0
        else:
            consec[label] = consec.get(label, 0) + 1
            if max_consecutive_timeouts and consec[label] >= max_consecutive_timeouts:
                stopped.add(label)

    n_run = n_skipped = 0
    for bset, ipath, cfg, tl in work:
        inst_name = Path(ipath).stem
        label     = cfg["label"]
        key       = _work_key(bset, ipath, label)

        # Already in CSV: seed the counter from its recorded status; don't re-run.
        if key in completed_status:
            _bump(label, completed_status[key])
            continue

        # Config already early-stopped: skip this (harder) pending pair silently.
        if label in stopped:
            n_skipped += 1
            continue

        n_run += 1
        print(f"[{n_run:>5}/{len(pending)}]  {bset:<12}  {inst_name:<35}  {label}", flush=True)

        J, T, C, density = _instance_features(ipath)
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
                "J": J, "T": T, "C": C, "density": round(density, 4),
                "solver": cfg["solver"], "config": label,
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
                    "J": J, "T": T, "C": C, "density": round(density, 4),
                    "solver": cfg["solver"], "config": label,
                    "comb_cuts": cfg.get("comb_cuts"), "frac_cuts": cfg.get("frac_cuts"),
                    "triplet_bounds": cfg.get("triplet_bounds"),
                    "status": "error", "obj": None,
                    "time_s": round(time.perf_counter() - t_start, 2), "gap_pct": None,
                    **{c: None for c in BBC_DIAG_COLS},
                    "notes": f"subprocess crash: {e}",
                }
                print(f"         → CRASH (no result in queue): {e}")

        _append_row(csv_path, row)
        _bump(label, row.get("status", ""))
        if label in stopped and consec.get(label, 0) == max_consecutive_timeouts:
            print(f"         [early-stop] '{label}': {max_consecutive_timeouts} consecutive "
                  f"non-optimal → skipping remaining harder instances for this config")

    tail = f", {n_skipped} skipped by early-stop" if n_skipped else ""
    print(f"\nDone. Ran {n_run}{tail}. Results at: {csv_path}")


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
        help="Limit pilot run to the N easiest instances (all configs per instance)")
    parser.add_argument("--max-consecutive-timeouts", type=int, default=None,
        help="Early-stop a config after N consecutive non-optimal results on harder "
             "instances (default: benchmark_config.MAX_CONSECUTIVE_TIMEOUTS; 0 disables)")
    parser.add_argument("--shard", default=None, metavar="I/N",
        help="Run only this job's slice of instances: shard I of N (0-indexed). "
             "Splits one config across N parallel cluster jobs.")
    args = parser.parse_args()
    _shard = None
    if args.shard:
        _si, _sn = args.shard.split("/")
        _shard = (int(_si), int(_sn))

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
        max_consecutive_timeouts=args.max_consecutive_timeouts,
        shard=_shard,
    )


if __name__ == "__main__":
    # Required for multiprocessing spawn on Windows
    multiprocessing.freeze_support()
    main()
