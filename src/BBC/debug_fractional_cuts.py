#!/usr/bin/env python3
"""
Diagnostic driver — are fractional Benders cuts *structurally* inactive, or is the
separator silently failing?  (Investigating why cuts_frac == 0 across the campaign.)

Runs one instance with use_fractional_cuts=True and prints the DEBUG counters added
to the callback in branch_and_benders_cut_cplex.py (all marked "# DEBUG").

Interpretation of the counters
------------------------------
  relax_calls == 0                     -> relaxation callback never fired
                                          (context registration problem).
  dsp_ok == 0  (dsp_none large)        -> the DSP never returns a value at fractional
                                          nodes => MASKED FAILURE (bug), NOT structural.
  violated == 0                        -> STRUCTURAL: at every LP optimum actually
                                          visited, no fractional cut is violated
                                          (the report's claim holds).
  violated > 0  and  cuts_frac == 0    -> BUG: cuts are violated but not added
                                          (add_failed tells you the add path is at fault).
  violated > 0  and  cuts_frac > 0     -> cuts DO fire here; the campaign's zero was
                                          environment/config-specific -> investigate.

Usage
-----
    # from a machine with CPLEX + the ssp_env conda env:
    source ~/miniforge3/etc/profile.d/conda.sh && conda activate ssp_env
    cd src/BBC
    python debug_fractional_cuts.py                 # default: a bound-LOOSE A-instance, 60 s
    python debug_fractional_cuts.py <inst.txt> 60   # any instance, custom time limit

Runtime: dominated by the time limit you pass (bound-loose instances run to it).
The counters are meaningful within the first few seconds of root-LP processing, so
30-60 s is plenty; you do NOT need the full 3600 s.
"""
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))                 # src/BBC
sys.path.insert(0, str(_HERE.parent / "SSP"))  # src/SSP  (utils, etc.)

from utils import load_ssp_instance, compute_ktns  # noqa: E402
from branch_and_benders_cut_cplex import BranchAndBendersCutSSP_CPLEX  # noqa: E402

# A bound-LOOSE primary instance (optimum = |U| + 1): BBC finds the optimum but the
# dual bound freezes at |U|, so the root LP stays fractional and the relaxation
# callback fires many times — exactly the regime to probe.
_DEFAULT = _HERE.parent.parent / "data/From_Felipe/data/Catanzaro/Tabela1C/A1-2.txt"


def run(path, time_limit=60):
    n, m, C, _A, tool_req = load_ssp_instance(str(path))
    U = len(set().union(*[set(v) for v in tool_req.values()])) if tool_req else 0
    print(f"instance {Path(path).name}: n={n} m={m} b={C} |U|={U} "
          f"coverage_bound(empty-start)=|U|={U}")

    s = BranchAndBendersCutSSP_CPLEX(
        n, m, C, tool_req,
        worker_lp_reuse=True,
        use_fractional_cuts=True,      # the path under investigation
        use_combinatorial_cuts=False,  # isolate: no integer-node Benders source
        use_triplet_bounds=False,
    )
    t0 = time.time()
    status, obj, seq = s.solve(time_limit=time_limit, verbose=False)
    dt = time.time() - t0

    d = getattr(s, "dbg_frac", None)
    ktns = compute_ktns(seq, tool_req, C) if seq else None
    st = getattr(s, "solve_stats", {})
    print(f"\n status={status}  obj={obj}  ktns(seq)={ktns}  time={dt:.1f}s")
    print(f" root_lp_bound={st.get('root_lp_bound')}  dual_bound={st.get('dual_bound')}"
          f"  nodes={st.get('nodes')}")

    if d is None:
        print("\n !! solver has no dbg_frac — is the instrumented "
              "branch_and_benders_cut_cplex.py on the path?")
        return

    print("\n --- fractional-cut diagnostics ---")
    print(f"  relaxation-callback calls : {d['relax_calls']}")
    print(f"  empty x_bar (skipped)     : {d['xbar_empty']}")
    print(f"  DSP returned None         : {d['dsp_none']}   <- if high => masked DSP failure")
    print(f"  DSP solved OK             : {d['dsp_ok']}")
    print(f"  VIOLATED (dsp>theta)      : {d['violated']}   <- the key number")
    print(f"  add_user_cut FAILED       : {d['add_failed']}")
    if d.get('add_err'):
        print(f"    first add-failure reason: {d['add_err']}")
    print(f"  frac cuts actually added  : {s.frac_cuts_added}")
    mx = d['max_excess']
    print(f"  max (dsp_obj - theta_lp)  : {mx:.4f}" if mx != float('-inf') else
          "  max (dsp_obj - theta_lp)  : (no DSP solved)")

    print("\n VERDICT:")
    if d['relax_calls'] == 0:
        print("  Relaxation callback never fired — check context registration.")
    elif d['dsp_ok'] == 0:
        print("  DSP never returned a value at fractional nodes -> MASKED FAILURE (bug).")
    elif d['violated'] == 0:
        print("  No fractional cut is ever violated at the LP optima visited")
        print("  -> STRUCTURAL: the campaign's cuts_frac=0 is genuine, not a masked bug.")
    elif s.frac_cuts_added == 0:
        print("  Cuts ARE violated but NONE were added -> BUG in the separation/add path")
        print(f"     ({d['add_failed']} add_user_cut failures) — 'structurally inactive' is wrong.")
    else:
        print("  Cuts violated AND added here -> the campaign's zero was config/env-specific.")


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT
    tl = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    run(p, tl)
