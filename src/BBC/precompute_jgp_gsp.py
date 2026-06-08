"""
JGP+GSP Preprocessing Pass
============================

For each instance in the configured benchmark sets, computes the JGP+GSP
two-phase heuristic cost and writes jgp_gsp_costs.csv.

Two-phase heuristic:
  1. Solve JGP via ARF MILP  →  K* batches
  2. Solve GSP (TSP on K* batches) to find best batch ordering:
       - If K* ≤ MAX_EXHAUSTIVE: try all K*! permutations, take minimum
       - Else: nearest-neighbour TSP on batches
  3. For each batch permutation, flatten with within-batch sort by
     decreasing |T_j|, then evaluate with KTNS

Output: jgp_gsp_costs.csv with columns:
    instance, benchmark_set, J, T, C, K_star, jgp_gsp_cost, jgp_gsp_gap

Usage
-----
    python precompute_jgp_gsp.py              # all primary + secondary sets
    python precompute_jgp_gsp.py --sets primary
    python precompute_jgp_gsp.py --only-sets Catanzaro
    python precompute_jgp_gsp.py --resume     # skip already-computed rows (default)
    python precompute_jgp_gsp.py --no-resume  # recompute everything

Note
----
jgp_gsp_gap is populated ONLY if the exact optimum is already in raw_results.csv.
Otherwise it is left NULL — run precompute after the benchmark, or join manually.
"""

import argparse
import csv
import itertools
import sys
from math import factorial
from pathlib import Path

# ── sys.path setup ─────────────────────────────────────────────────────────
_BBC = Path(__file__).resolve().parent      # src/BBC/
_SRC = _BBC.parent                          # src/
sys.path.insert(0, str(_SRC))
sys.path.insert(0, str(_SRC / "SSP"))
sys.path.insert(0, str(_BBC))

from benchmark_config import (
    JGP_GSP_CSV, ALL_SETS, PRIMARY_SETS, SECONDARY_SETS,
    get_instances,
)
from utils import load_ssp_instance, compute_ktns
from SCIP_formulation_solvers import solve_jgp_arf

# ── constants ──────────────────────────────────────────────────────────────
MAX_EXHAUSTIVE = 8   # enumerate all K*! permutations if K* ≤ this (8! = 40320)


# ─────────────────────────────────────────────────────────────────────────────
# GSP solver
# ─────────────────────────────────────────────────────────────────────────────

def _flatten_batch_order(batch_order, tool_req):
    """
    Flatten a sequence of (jobs, tools) batches into a job sequence.
    Within each batch, jobs are sorted by decreasing |T_j| for better carry-over.
    """
    seq = []
    for jobs, _tools in batch_order:
        seq.extend(sorted(jobs, key=lambda j: len(tool_req[j]), reverse=True))
    return seq


def solve_gsp_exact(batches, tool_req, cap):
    """
    Solve the Grouped Sequencing Problem by exhaustive enumeration of
    all K*! batch orderings.  Only call when len(batches) ≤ MAX_EXHAUSTIVE.

    Returns
    -------
    best_cost : int
    best_sequence : list[int]
    """
    best_cost = float("inf")
    best_seq  = []
    for perm in itertools.permutations(batches):
        seq  = _flatten_batch_order(perm, tool_req)
        cost, _ = compute_ktns(seq, tool_req, cap)
        if cost < best_cost:
            best_cost = cost
            best_seq  = seq
    return best_cost, best_seq


def _batch_transition_cost(batch_a, batch_b, tool_req, cap):
    """
    Estimate the marginal KTNS cost of placing batch_b after batch_a.
    Used for nearest-neighbour batch TSP when K* > MAX_EXHAUSTIVE.
    Approximation: compute KTNS of concatenated sequence; subtract cost of A alone.
    """
    seq_a  = _flatten_batch_order([batch_a], tool_req)
    seq_ab = _flatten_batch_order([batch_a, batch_b], tool_req)
    cost_a,  _ = compute_ktns(seq_a,  tool_req, cap)
    cost_ab, _ = compute_ktns(seq_ab, tool_req, cap)
    return cost_ab - cost_a


def solve_gsp_nn(batches, tool_req, cap):
    """
    Nearest-neighbour heuristic for the batch TSP.
    Used as fallback when K* > MAX_EXHAUSTIVE.

    Returns
    -------
    cost : int
    sequence : list[int]
    """
    remaining = list(batches)
    # Start with the batch that has largest total tool set (most constrained first)
    start_idx = max(range(len(remaining)),
                    key=lambda i: len(remaining[i][1]))
    ordered   = [remaining.pop(start_idx)]

    while remaining:
        last = ordered[-1]
        best_idx, best_delta = 0, float("inf")
        for i, b in enumerate(remaining):
            delta = _batch_transition_cost(last, b, tool_req, cap)
            if delta < best_delta:
                best_delta, best_idx = delta, i
        ordered.append(remaining.pop(best_idx))

    seq  = _flatten_batch_order(ordered, tool_req)
    cost, _ = compute_ktns(seq, tool_req, cap)
    return cost, seq


def compute_jgp_gsp(n_jobs, n_tools, cap, tool_req):
    """
    Full JGP+GSP computation for one instance.

    Returns
    -------
    k_star  : int   — optimal number of batches from JGP
    cost    : int   — JGP+GSP heuristic switch cost
    notes   : str   — '' or warning message
    """
    jgp_obj, batches = solve_jgp_arf(n_jobs, n_tools, cap, tool_req)

    if jgp_obj is None or not batches:
        return None, None, "JGP infeasible or solver error"

    k_star = int(round(jgp_obj))

    if k_star == 1:
        # Single batch — no GSP needed; just flatten and evaluate
        seq  = _flatten_batch_order(batches, tool_req)
        cost, _ = compute_ktns(seq, tool_req, cap)
        return k_star, cost, ""

    n_perms = factorial(k_star)
    if k_star <= MAX_EXHAUSTIVE:
        cost, _seq = solve_gsp_exact(batches, tool_req, cap)
        notes = f"exact ({n_perms} permutations)"
    else:
        cost, _seq = solve_gsp_nn(batches, tool_req, cap)
        notes = f"nn_heuristic (K*={k_star} > {MAX_EXHAUSTIVE})"

    return k_star, cost, notes


# ─────────────────────────────────────────────────────────────────────────────
# CSV helpers
# ─────────────────────────────────────────────────────────────────────────────

JGP_COLUMNS = ["instance", "benchmark_set", "J", "T", "C",
               "K_star", "jgp_gsp_cost", "jgp_gsp_gap", "notes"]


def _load_completed(csv_path):
    done = set()
    if not csv_path.exists():
        return done
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            done.add((row["instance"], row["benchmark_set"]))
    return done


def _load_exact_optima(raw_csv_path):
    """
    Load the best known optimal objective for each instance from raw_results.csv.
    Returns dict: instance_stem -> float (or None if not yet solved to optimality).
    """
    optima = {}
    if not raw_csv_path.exists():
        return optima
    with open(raw_csv_path, newline="") as f:
        for row in csv.DictReader(f):
            if "optimal" in str(row.get("status", "")).lower() and row.get("obj"):
                key = row["instance"]
                val = float(row["obj"])
                if key not in optima or val < optima[key]:
                    optima[key] = val
    return optima


def _append_row(csv_path, row):
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=JGP_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run_precompute(sets=None, only_sets=None, resume=True, output_csv=None):
    if sets is None:
        sets = ALL_SETS
    csv_path = Path(output_csv) if output_csv else JGP_GSP_CSV

    instances = [
        (bset, ipath, tl)
        for bset, ipath, tl in get_instances(sets)
        if not only_sets or bset in only_sets
    ]

    completed = _load_completed(csv_path) if resume else set()

    # Try to join with existing exact optima for gap computation
    raw_csv = csv_path.parent / "raw_results.csv"
    optima  = _load_exact_optima(raw_csv)
    if optima:
        print(f"  Loaded {len(optima)} exact optima from {raw_csv.name} for gap computation.")
    else:
        print(f"  No raw_results.csv found — jgp_gsp_gap will be NULL (populate after benchmark).")

    pending = [
        (bset, ipath)
        for bset, ipath, _ in instances
        if (Path(ipath).stem, bset) not in completed
    ]

    print(f"\nJGP+GSP Precompute")
    print(f"  Instances  : {len(instances)}  ({len(instances) - len(pending)} cached, {len(pending)} to compute)")
    print(f"  Output CSV : {csv_path}\n")

    for idx, (bset, ipath) in enumerate(pending, 1):
        inst = Path(ipath).stem
        print(f"[{idx:>5}/{len(pending)}]  {bset:<12}  {inst}", end="  ", flush=True)

        try:
            J, T, C, A, tool_req = load_ssp_instance(ipath)
        except Exception as e:
            print(f"LOAD ERROR: {e}")
            _append_row(csv_path, {
                "instance": inst, "benchmark_set": bset,
                "J": None, "T": None, "C": None,
                "K_star": None, "jgp_gsp_cost": None, "jgp_gsp_gap": None,
                "notes": f"load_error: {e}",
            })
            continue

        try:
            k_star, cost, notes = compute_jgp_gsp(J, T, C, tool_req)
        except Exception as e:
            print(f"ERROR: {e}")
            _append_row(csv_path, {
                "instance": inst, "benchmark_set": bset,
                "J": J, "T": T, "C": C,
                "K_star": None, "jgp_gsp_cost": None, "jgp_gsp_gap": None,
                "notes": f"error: {e}",
            })
            continue

        # Compute gap if we have the exact optimum
        gap = None
        if cost is not None and inst in optima:
            gap = cost - optima[inst]

        print(f"K*={k_star}  cost={cost}  gap={gap}  [{notes}]")
        _append_row(csv_path, {
            "instance": inst, "benchmark_set": bset,
            "J": J, "T": T, "C": C,
            "K_star": k_star, "jgp_gsp_cost": cost, "jgp_gsp_gap": gap,
            "notes": notes,
        })

    print(f"\nDone. JGP+GSP costs at: {csv_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Precompute JGP+GSP heuristic costs for all benchmark instances",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--sets", choices=["primary", "secondary", "all"], default="all")
    parser.add_argument("--only-sets", nargs="+", metavar="LABEL")
    parser.add_argument("--no-resume", dest="resume", action="store_false",
        help="Recompute all (ignore cached rows)")
    parser.add_argument("--output", default=None, help="Override output CSV path")
    args = parser.parse_args()

    if args.sets == "primary":
        sets = PRIMARY_SETS
    elif args.sets == "secondary":
        sets = SECONDARY_SETS
    else:
        sets = ALL_SETS

    run_precompute(
        sets=sets,
        only_sets=set(args.only_sets) if args.only_sets else None,
        resume=args.resume,
        output_csv=args.output,
    )


if __name__ == "__main__":
    main()
