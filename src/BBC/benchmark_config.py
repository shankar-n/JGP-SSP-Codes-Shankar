"""
BBC Benchmark Configuration
============================

Single source of truth for instance set paths, BBC hyperparameter grid,
time limits, CSV column schema, and output paths.

All other benchmark scripts (benchmark_runner, precompute_jgp_gsp, analysis/*)
import from here.  Change something once; it propagates everywhere.
"""

from pathlib import Path
import glob as _glob

# ── Directory layout ──────────────────────────────────────────────────────────
_HERE         = Path(__file__).resolve().parent          # .../src/BBC/
_PROJECT_ROOT = _HERE.parent.parent                      # project root
_DATA         = _PROJECT_ROOT / "data" / "From_Felipe" / "data"

# ── Instance sets ─────────────────────────────────────────────────────────────
# Each entry:  (label, glob_pattern, time_limit_seconds)
#
# PRIMARY  (3 600 s TL, all 10 solver configs):
#   Catanzaro Tabela1C  — 174 instances, J=8-15, T=5-15, c=3-5
#   Crama     Tabela1-4 — 160 instances, J=10,   T=10,   c=4
#   Laporte   Tabela7   —  80 instances, J=10,   T=10,   c=4
#
# SECONDARY (600 s TL, BBC + LSS only — SSPMF too slow at J=15):
#   Laporte   Tabela3-5 — ~1010 instances, J=8-15, T=15, c=5

PRIMARY_SETS = [
    ("Catanzaro", str(_DATA / "Catanzaro" / "Tabela1C" / "*.txt"), 3600),
    ("Crama",     str(_DATA / "Crama"     / "**"       / "*.txt"), 3600),
    ("Laporte7",  str(_DATA / "Laporte"   / "Tabela7"  / "*.txt"), 3600),
]

SECONDARY_SETS = [
    ("Laporte3",  str(_DATA / "Laporte" / "Tabela3" / "*.txt"), 600),
    ("Laporte4",  str(_DATA / "Laporte" / "Tabela4" / "*.txt"), 600),
    ("Laporte5",  str(_DATA / "Laporte" / "Tabela5" / "*.txt"), 600),
    # Uncomment when primary runs are complete (BBC only, optional):
    # ("Laporte6",  str(_DATA / "Laporte" / "Tabela6" / "*.txt"), 600),
]

ALL_SETS = PRIMARY_SETS + SECONDARY_SETS

# ── BBC hyperparameter grid (2³ = 8 configs) ─────────────────────────────────
# Design:
#   comb_cuts      — use KTNS combinatorial cuts (vs. LP Benders at integer nodes)
#   frac_cuts      — add Benders user cuts at LP relaxation nodes (novel contribution)
#   triplet_bounds — add O(n³) triplet lower bound constraints to master problem root
#   lp_reuse       — FIXED to False throughout (confound elimination)
#
# The full-factorial 2³ design lets us isolate marginal value of each flag
# and report clean ablation results.

BBC_CONFIGS = [
    # LP Benders family
    {"label": "BBC-LP",    "solver": "BBC", "comb_cuts": False, "frac_cuts": False, "triplet_bounds": False, "lp_reuse": True},
    {"label": "BBC-LP+F",  "solver": "BBC", "comb_cuts": False, "frac_cuts": True,  "triplet_bounds": False, "lp_reuse": True},
    {"label": "BBC-LP+T",  "solver": "BBC", "comb_cuts": False, "frac_cuts": False, "triplet_bounds": True,  "lp_reuse": True},
    {"label": "BBC-LP+FT", "solver": "BBC", "comb_cuts": False, "frac_cuts": True,  "triplet_bounds": True,  "lp_reuse": True},
    # KTNS-Benders family (novel contribution)
    {"label": "BBC-K",     "solver": "BBC", "comb_cuts": True,  "frac_cuts": False, "triplet_bounds": False, "lp_reuse": True},
    {"label": "BBC-K+F",   "solver": "BBC", "comb_cuts": True,  "frac_cuts": True,  "triplet_bounds": False, "lp_reuse": True},
    {"label": "BBC-K+T",   "solver": "BBC", "comb_cuts": True,  "frac_cuts": False, "triplet_bounds": True,  "lp_reuse": True},
    {"label": "BBC-K+FT",  "solver": "BBC", "comb_cuts": True,  "frac_cuts": True,  "triplet_bounds": True,  "lp_reuse": True},
    # Prior-work baselines
    {"label": "LSS",       "solver": "LSS"},
    {"label": "SSPMF",     "solver": "SSPMF"},
]

# On secondary sets, skip SSPMF (prohibitively slow for J=15)
SECONDARY_CONFIGS = [c for c in BBC_CONFIGS if c["label"] != "SSPMF"]

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
    "obj",       # switch cost (None if no feasible solution found)
    "time_s",    # wall-clock solve time
    "gap_pct",   # MIP gap at termination (0 if optimal; None for LSS/SSPMF)
    # B&B diagnostics (BBC only; None for LSS/SSPMF)
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
    """
    Expand glob patterns and return a flat list of
    (benchmark_set_label, instance_path_str, time_limit_s) tuples.

    Parameters
    ----------
    sets : list of (label, pattern, tl) tuples, or None to use ALL_SETS
    """
    if sets is None:
        sets = ALL_SETS
    result = []
    for label, pattern, tl in sets:
        files = sorted(_glob.glob(pattern, recursive=True))
        for f in files:
            result.append((label, f, tl))
    return result


def get_configs_for_set(benchmark_set_label):
    """
    Return the appropriate config list for a given benchmark set.
    Secondary sets (Laporte3-5) use SECONDARY_CONFIGS (no SSPMF).
    """
    secondary_labels = {s[0] for s in SECONDARY_SETS}
    if benchmark_set_label in secondary_labels:
        return SECONDARY_CONFIGS
    return BBC_CONFIGS
