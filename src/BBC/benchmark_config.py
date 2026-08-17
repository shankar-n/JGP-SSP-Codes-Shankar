"""
BBC Benchmark Configuration
============================

Single source of truth for the instance families, the solver grid, the time
limit, the CSV schema, and output paths.  Every benchmark script imports from
here; change something once and it propagates.

Methodology (2026-08 -- cleaned up to a standard protocol)
---------------------------------------------------------
  * Run EVERY instance in EVERY family to a single, uniform time limit.  No
    early-stop, no instance skipping.  The denominator in the results is then
    the real number of instances -- not an outcome of a heuristic ordering.
  * Instances are still processed easiest-first, but ONLY so that results stream
    in from easy to hard while you watch the run; since nothing is skipped, the
    order has no effect on which instances get solved.
  * All solver configs run on all families (no SSPMF exclusion; if it is too
    slow to build on a large instance it simply times out, which is honest data).
  * Report per FAMILY plus a cactus plot / performance profile -- the way the
    SSP literature (Catanzaro 2015, da Silva 2024, Mecler 2021) presents it.
"""

from pathlib import Path
import glob as _glob

# ── Directory layout ──────────────────────────────────────────────────────────
_HERE         = Path(__file__).resolve().parent          # .../src/BBC/
_PROJECT_ROOT = _HERE.parent.parent                      # project root
_DATA         = _PROJECT_ROOT / "data" / "From_Felipe" / "data"

# ── One uniform time limit for every instance (seconds) ───────────────────────
# 3600 s = 1 hour: the standard time limit in the SSP / exact-MILP literature.
# WALL-TIME NOTE: with only one job per config (15 jobs), running all ~1400
# instances at 1 h each takes the slowest config ~6 WEEKS (timeouts dominate).
# The campaign is therefore SHARDED across instances (run_campaign.sbatch splits
# each config into NSHARDS parallel jobs), which brings it back to ~a week.
TIME_LIMIT = 3600

# ── Instance families ─────────────────────────────────────────────────────────
# (label, glob_pattern, time_limit).  All families, one time limit, run in full.
FAMILIES = [
    ("Catanzaro", str(_DATA / "Catanzaro" / "Tabela1C" / "*.txt"), TIME_LIMIT),
    ("Crama",     str(_DATA / "Crama"     / "**"       / "*.txt"), TIME_LIMIT),
    ("Laporte7",  str(_DATA / "Laporte"   / "Tabela7"  / "*.txt"), TIME_LIMIT),
    ("Laporte3",  str(_DATA / "Laporte"   / "Tabela3"  / "*.txt"), TIME_LIMIT),
    ("Laporte4",  str(_DATA / "Laporte"   / "Tabela4"  / "*.txt"), TIME_LIMIT),
    ("Laporte5",  str(_DATA / "Laporte"   / "Tabela5"  / "*.txt"), TIME_LIMIT),
]

# Names still imported by the runner.  There is no longer a primary/secondary
# split in the methodology -- everything is one set.  Kept as aliases so the
# existing --sets flag keeps working (primary == all == the whole thing).
ALL_SETS       = FAMILIES
PRIMARY_SETS   = FAMILIES
SECONDARY_SETS = []          # unused; retained only for import compatibility

# ── Solver grid ───────────────────────────────────────────────────────────────
# 8 BBC ablation configs + 4 acceleration configs (2026-07) + 3 prior baselines.
BBC_CONFIGS = [
    # Ablation over BOTH cut strategies (LP-dual vs combinatorial) x fractional cuts.
    # We keep all four comb x frac combinations: the LAST campaign could NOT judge the
    # fractional ones (the fractional-cut bug meant they never fired), so they must be
    # re-tested now that the fix is in.
    {"label": "BBC-LP",    "solver": "BBC", "comb_cuts": False, "frac_cuts": False, "triplet_bounds": False, "lp_reuse": True},  # base (LP Benders)
    {"label": "BBC-LP+F",  "solver": "BBC", "comb_cuts": False, "frac_cuts": True,  "triplet_bounds": False, "lp_reuse": True},  # LP + fractional (the fix)
    {"label": "BBC-K",     "solver": "BBC", "comb_cuts": True,  "frac_cuts": False, "triplet_bounds": False, "lp_reuse": True},  # combinatorial
    {"label": "BBC-K+F",   "solver": "BBC", "comb_cuts": True,  "frac_cuts": True,  "triplet_bounds": False, "lp_reuse": True},  # combinatorial + fractional (RE-TEST; frac was buggy)
    {"label": "BBC-LP+T",  "solver": "BBC", "comb_cuts": False, "frac_cuts": False, "triplet_bounds": True,  "lp_reuse": True},  # one triplet config, to confirm neutrality empirically
    # ── PRUNED: only the triplet-ADDED crosses.  Triplet bounds are dominated by the
    #    coverage row (w_ijk <= |U|-b < |U|) -- a PROOF, independent of any run -- so
    #    adding triplets to a kept config cannot change it.  (NOT pruned via the buggy
    #    last run.)  Uncomment for the full 2^3 grid.
    # {"label": "BBC-LP+FT", "solver": "BBC", "comb_cuts": False, "frac_cuts": True,  "triplet_bounds": True,  "lp_reuse": True},  # = BBC-LP+F + triplet
    # {"label": "BBC-K+T",   "solver": "BBC", "comb_cuts": True,  "frac_cuts": False, "triplet_bounds": True,  "lp_reuse": True},  # = BBC-K + triplet
    # {"label": "BBC-K+FT",  "solver": "BBC", "comb_cuts": True,  "frac_cuts": True,  "triplet_bounds": True,  "lp_reuse": True},  # = BBC-K+F + triplet
    # Acceleration features (2026-07), layered on the corrected fractional-cut base.
    #   conflict_cuts    — conflict-graph constant root bound
    #   primal_heuristic — HGS -> CPLEX MIP start + seeded Benders cut at the root
    #   pareto_cuts      — Papadakos core-point lifting of the fractional Benders cuts
    {"label": "BBC-LP+F+C",  "solver": "BBC", "comb_cuts": False, "frac_cuts": True, "triplet_bounds": False, "lp_reuse": True, "conflict_cuts": True},
    {"label": "BBC-LP+F+H",  "solver": "BBC", "comb_cuts": False, "frac_cuts": True, "triplet_bounds": False, "lp_reuse": True, "primal_heuristic": True},
    {"label": "BBC-LP+F+P",  "solver": "BBC", "comb_cuts": False, "frac_cuts": True, "triplet_bounds": False, "lp_reuse": True, "pareto_cuts": True},
    {"label": "BBC-LP+ACC",  "solver": "BBC", "comb_cuts": False, "frac_cuts": True, "triplet_bounds": False, "lp_reuse": True, "conflict_cuts": True, "primal_heuristic": True, "pareto_cuts": True},
    # Prior-work baselines
    {"label": "LSS",       "solver": "LSS"},
    {"label": "SSPMF",     "solver": "SSPMF"},
    {"label": "CATZ-F4",   "solver": "CATZ"},    # Catanzaro et al. 2015, Formulation 4
]

# ── Early-stop: DISABLED (run everything) ─────────────────────────────────────
# 0 = disabled.  We run every instance to the time limit; nothing is skipped.
# (The knob is kept only so a quick exploratory run can re-enable it by hand.)
MAX_CONSECUTIVE_TIMEOUTS = 0

# ── Output paths ──────────────────────────────────────────────────────────────
OUTPUT_DIR   = _HERE
RAW_CSV      = OUTPUT_DIR / "raw_results.csv"
JGP_GSP_CSV  = OUTPUT_DIR / "jgp_gsp_costs.csv"
ANALYSIS_DIR = OUTPUT_DIR / "analysis" / "output"

# ── CSV column schema ─────────────────────────────────────────────────────────
COLUMNS = [
    # Instance descriptor
    "instance", "benchmark_set", "J", "T", "C", "density",
    # Solver config
    "solver", "config", "comb_cuts", "frac_cuts", "triplet_bounds",
    # Results
    "status",    # 'optimal' | 'time_limit' | 'error' | 'load_error'
    "obj",       # solver's NATIVE objective
    "obj_ktns",  # CANONICAL empty-start switches of the returned sequence; compare solvers on THIS
    "time_s",    # wall-clock solve time
    "gap_pct",   # MIP gap at termination (0 if optimal)
    # B&B diagnostics (BBC only)
    "nodes", "lp_iters", "cb_invocations",
    "cuts_sec", "cuts_benders", "cuts_comb", "cuts_frac",
    "root_lp_bound", "dual_bound",
    # Misc
    "notes",
]

# Subset of COLUMNS that are BBC-only diagnostics
BBC_DIAG_COLS = [
    "nodes", "lp_iters", "cb_invocations",
    "cuts_sec", "cuts_benders", "cuts_comb", "cuts_frac",
    "root_lp_bound", "dual_bound",
]


def get_instances(sets=None):
    """Expand glob patterns and return a flat list of
    (benchmark_set_label, instance_path_str, time_limit_s) tuples."""
    if sets is None:
        sets = ALL_SETS
    result = []
    for label, pattern, tl in sets:
        for f in sorted(_glob.glob(pattern, recursive=True)):
            result.append((label, f, tl))
    return result


def get_configs_for_set(benchmark_set_label):
    """Every family runs every solver config (no exclusions any more)."""
    return BBC_CONFIGS
