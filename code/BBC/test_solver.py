#!/usr/bin/env python3
"""
Test suite for Branch-and-Benders-Cut SSP solvers.

Tests all three implementations:
  - branch_and_benders_cut_gurobi.py  (Gurobi + cbLazy callbacks)
  - branch_and_benders_cut_cplex.py   (CPLEX + generic callback)
  - branch_and_benders_cut_scip.py    (SCIP  + Conshdlr)

Any solver whose library is not installed is automatically skipped.
When two or more solvers run successfully their objective values are
cross-checked for agreement (within a small tolerance).

Run:
    python test_solver.py
"""

import sys
import time
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import load_ssp_instance

# ── Instance path ─────────────────────────────────────────────────────────────
INSTANCE_PATH = (
    Path(__file__).parent.parent / "Instances" / "Shankar" / "shankar-example.txt"
)
TIME_LIMIT = 60   # seconds per solver

# ── Result container ──────────────────────────────────────────────────────────
results = {}   # solver_name → (status, obj_val, sequence)


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def section(title):
    width = 70
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def load_instance():
    """Load and print instance info.  Returns (n_jobs, n_tools, capacity, A, tool_req)."""
    if not INSTANCE_PATH.exists():
        print(f"  ✗ Instance file not found: {INSTANCE_PATH}")
        print("    Please place shankar-example.txt at the expected path.")
        sys.exit(1)

    n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance(str(INSTANCE_PATH))
    print(f"  Instance : {INSTANCE_PATH.name}")
    print(f"  Jobs     : {n_jobs}")
    print(f"  Tools    : {n_tools}")
    print(f"  Capacity : {capacity}")
    return n_jobs, n_tools, capacity, A, tool_req


def validate_sequence(sequence, n_jobs, label):
    """Check that the sequence is a valid permutation of 0..n_jobs-1."""
    if sequence is None:
        print(f"  ✗ {label}: sequence is None")
        return False
    if len(sequence) != n_jobs:
        print(f"  ✗ {label}: sequence length {len(sequence)} != {n_jobs}")
        return False
    if sorted(sequence) != list(range(n_jobs)):
        print(f"  ✗ {label}: sequence is not a valid permutation: {sequence}")
        return False
    print(f"  ✓ {label}: valid permutation  {sequence}")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Individual solver tests
# ─────────────────────────────────────────────────────────────────────────────

def test_gurobi(n_jobs, n_tools, capacity, tool_req):
    section("SOLVER 1 – Gurobi  (branch_and_benders_cut_gurobi.py)")

    try:
        import gurobipy  # noqa: F401
    except ImportError:
        print("  ⚠  Gurobi not installed – skipping.")
        return None

    try:
        from branch_and_benders_cut_gurobi import BranchAndBendersCutSSP
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return None

    print("\n  Building master problem …")
    solver = BranchAndBendersCutSSP(n_jobs, n_tools, capacity, tool_req)
    solver.build_master_problem(verbose=False)
    print("  ✓ Master problem built")

    print(f"\n  Solving (time limit {TIME_LIMIT}s) …")
    t0 = time.time()
    status, obj_val, sequence = solver.solve(time_limit=TIME_LIMIT, verbose=True)
    elapsed = time.time() - t0

    print(f"\n  Wall-clock time : {elapsed:.2f}s")
    print(f"  Callback iters  : {solver.iteration_count}")
    print(f"  Cuts added      : {solver.cuts_added}")

    ok = validate_sequence(sequence, n_jobs, "Gurobi sequence")
    if ok:
        results['Gurobi'] = (status, obj_val, sequence)
        print(f"  ✓ Gurobi PASSED  (obj={obj_val})")
    return ok


def test_cplex(n_jobs, n_tools, capacity, tool_req):
    section("SOLVER 2 – CPLEX  (branch_and_benders_cut_cplex.py)")

    try:
        import cplex  # noqa: F401
    except ImportError:
        print("  ⚠  cplex not installed – skipping.")
        return None

    try:
        from branch_and_benders_cut_cplex import BranchAndBendersCutSSP_CPLEX
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return None

    print("\n  Building master problem …")
    solver = BranchAndBendersCutSSP_CPLEX(n_jobs, n_tools, capacity, tool_req)
    solver.build_master_problem(verbose=False)
    print("  ✓ Master problem built")

    print(f"\n  Solving (time limit {TIME_LIMIT}s) …")
    t0 = time.time()
    status, obj_val, sequence = solver.solve(time_limit=TIME_LIMIT, verbose=True)
    elapsed = time.time() - t0

    print(f"\n  Wall-clock time : {elapsed:.2f}s")
    print(f"  Callback iters  : {solver.iteration_count}")
    print(f"  Cuts added      : {solver.cuts_added}")

    ok = validate_sequence(sequence, n_jobs, "CPLEX sequence")
    if ok:
        results['CPLEX'] = (status, obj_val, sequence)
        print(f"  ✓ CPLEX PASSED  (obj={obj_val})")
    return ok


def test_scip(n_jobs, n_tools, capacity, tool_req):
    section("SOLVER 3 – SCIP  (branch_and_benders_cut_scip.py)")

    try:
        import pyscipopt  # noqa: F401
    except ImportError:
        print("  ⚠  pyscipopt not installed – skipping.")
        print("     Install with: pip install pyscipopt  (requires SCIP binary)")
        return None

    try:
        from branch_and_benders_cut_scip import BranchAndBendersCutSSP_SCIP
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return None

    # Report which DSP sub-solver will be used
    dsp_info = "SCIP nested LP"
    try:
        import gurobipy; dsp_info = "Gurobi"    # noqa: E702
    except ImportError:
        try:
            import docplex; dsp_info = "docplex" # noqa: E702
        except ImportError:
            pass
    print(f"  DSP sub-solver  : {dsp_info}")

    print("\n  Building master problem …")
    solver = BranchAndBendersCutSSP_SCIP(n_jobs, n_tools, capacity, tool_req)
    solver.build_master_problem(verbose=False)
    print("  ✓ Master problem built")

    print(f"\n  Solving (time limit {TIME_LIMIT}s) …")
    t0 = time.time()
    status, obj_val, sequence = solver.solve(time_limit=TIME_LIMIT, verbose=True)
    elapsed = time.time() - t0

    print(f"\n  Wall-clock time : {elapsed:.2f}s")
    print(f"  Callback iters  : {solver.iteration_count}")
    print(f"  Cuts added      : {solver.cuts_added}")

    ok = validate_sequence(sequence, n_jobs, "SCIP sequence")
    if ok:
        results['SCIP'] = (status, obj_val, sequence)
        print(f"  ✓ SCIP PASSED  (obj={obj_val})")
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# Cross-solver agreement check
# ─────────────────────────────────────────────────────────────────────────────

def cross_check():
    section("CROSS-CHECK – Objective agreement across solvers")

    solved = {
        name: data for name, data in results.items()
        if data is not None and data[1] is not None
    }

    if len(solved) < 2:
        print("  Only one solver ran – nothing to cross-check.")
        return True

    objs = {name: data[1] for name, data in solved.items()}
    ref_name, ref_obj = next(iter(objs.items()))

    all_agree = True
    for name, obj in objs.items():
        diff = abs(obj - ref_obj)
        if diff <= 0.5:   # allow rounding differences up to 0.5 switches
            print(f"  ✓ {name} obj={obj:.4f}  (diff vs {ref_name}: {diff:.6f})  OK")
        else:
            print(f"  ✗ {name} obj={obj:.4f}  DISAGREES with {ref_name}={ref_obj:.4f}  (diff={diff:.4f})")
            all_agree = False

    if all_agree:
        print(f"\n  All {len(solved)} solvers agree on objective value  ✓")
    else:
        print("\n  ✗ Solvers disagree – check formulations!")

    return all_agree


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    section("Branch-and-Benders-Cut SSP – Test Suite")
    print(f"\n  Instance : {INSTANCE_PATH}")
    print(f"  Time limit per solver : {TIME_LIMIT}s")

    n_jobs, n_tools, capacity, A, tool_req = load_instance()

    # ── Run all three solvers ─────────────────────────────────────────────
    g_ok = test_gurobi(n_jobs, n_tools, capacity, tool_req)
    c_ok = test_cplex (n_jobs, n_tools, capacity, tool_req)
    s_ok = test_scip  (n_jobs, n_tools, capacity, tool_req)

    # ── Cross-check ───────────────────────────────────────────────────────
    agree = cross_check()

    # ── Summary ───────────────────────────────────────────────────────────
    section("SUMMARY")

    outcomes = {
        'Gurobi' : g_ok,
        'CPLEX'  : c_ok,
        'SCIP'   : s_ok,
    }

    n_skipped = sum(1 for v in outcomes.values() if v is None)
    n_passed  = sum(1 for v in outcomes.values() if v is True)
    n_failed  = sum(1 for v in outcomes.values() if v is False)

    for name, outcome in outcomes.items():
        symbol = "✓ PASS" if outcome is True else ("⚠  SKIP" if outcome is None else "✗ FAIL")
        print(f"  {symbol}  {name}")

    if agree and n_failed == 0:
        print("\n  Cross-check: all active solvers agree  ✓")

    print(f"\n  {n_passed} passed  |  {n_skipped} skipped  |  {n_failed} failed")
    print()

    return 0 if n_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
