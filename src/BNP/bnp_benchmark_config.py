"""
BNP Benchmark Configuration  (standalone; mirrors src/BBC/benchmark_config.py)
=============================================================================

Campaign config for the position-formulation branch-and-price solvers
(PCF', PTF), run on SCIP/PySCIPOpt. This is a SEPARATE experiment from the BBC
campaign -- it does not import from or modify anything in src/BBC/. Results go
to src/BNP/bnp_results.csv and are compared to the BBC numbers later, offline,
on the shared canonical metric obj_ktns (empty-start switches).

Single source of truth for: instance sets + time limits, the solver grid, the
size cap, early-stop, the CSV schema, and output paths.
"""
from pathlib import Path
import glob as _glob

_HERE = Path(__file__).resolve().parent                  # src/BNP/
_DATA = _HERE.parent.parent / "data" / "From_Felipe" / "data"

# ── Instance sets ─────────────────────────────────────────────────────────────
# (label, glob_pattern, time_limit_seconds).  Same instance files as BBC.
PRIMARY_SETS = [
    ("Catanzaro", str(_DATA / "Catanzaro" / "Tabela1C" / "*.txt"), 1800),
    ("Crama",     str(_DATA / "Crama"     / "**"        / "*.txt"), 1800),
    ("Laporte7",  str(_DATA / "Laporte"   / "Tabela7"   / "*.txt"), 1800),
]
SECONDARY_SETS = [
    ("Laporte3",  str(_DATA / "Laporte" / "Tabela3" / "*.txt"), 600),
    ("Laporte4",  str(_DATA / "Laporte" / "Tabela4" / "*.txt"), 600),
    ("Laporte5",  str(_DATA / "Laporte" / "Tabela5" / "*.txt"), 600),
]
ALL_SETS = PRIMARY_SETS + SECONDARY_SETS

# ── Solver grid ───────────────────────────────────────────────────────────────
# The two position formulations plus the PCF' pricing-acceleration ablation. Each
# runs PCF'/PTF branch-and-price from src/BNP/ (enumerate-or-MILP pricer by size).
# The acceleration flags (heuristic_pricing, multiple_pricing, warm_start, stabilize)
# are passed straight to pcf_prime_bp.branch_and_price(accel=...); EACH PRESERVES
# EXACTNESS (verified IP == Z* on rings + randoms, 2026-08). They are laid out as a
# one-at-a-time ablation plus a combined +ACC, mirroring the BBC accelerator study,
# so the campaign measures each lever's separate and joint effect on the solve rate.
ACCEL_KEYS = ("heuristic_pricing", "multiple_pricing", "warm_start", "stabilize",
              "kcols", "stab_alpha")
CONFIGS = [
    {"label": "PCFp",      "solver": "PCFp"},                                          # baseline
    {"label": "PCFp+HP",   "solver": "PCFp", "heuristic_pricing": True},               # greedy-then-exact pricing
    {"label": "PCFp+MC",   "solver": "PCFp", "multiple_pricing": True, "kcols": 5},    # multiple columns/round
    {"label": "PCFp+WS",   "solver": "PCFp", "warm_start": True},                      # warm-start column pool
    {"label": "PCFp+STAB", "solver": "PCFp", "stabilize": True, "stab_alpha": 0.5},    # Wentges smoothing
    {"label": "PCFp+ACC",  "solver": "PCFp", "heuristic_pricing": True,
     "multiple_pricing": True, "warm_start": True, "stabilize": True, "kcols": 5, "stab_alpha": 0.5},
    {"label": "PTF",       "solver": "PTF"},                                           # transition formulation
]


def accel_of(config):
    """Extract the acceleration kwargs from a config dict (empty for baselines)."""
    return {k: config[k] for k in ACCEL_KEYS if k in config}

# ── Size cap + early-stop ─────────────────────────────────────────────────────
# The prototype exact B&P (a_{t,p} integer branching + MILP pricing) does not
# scale to the largest files (Otiai J=300-400 would OOM building the master), so
# we SKIP instances with J above MAX_JOBS rather than waste a time-limit on a
# model that can't be built. Raise this as the pricer/branching mature. (BBC has
# no such cap because CPLEX handles much larger compact models.)
MAX_JOBS = 25
# Also skip instances whose configuration space |V| = C(T, b) is astronomically
# large: a backstop against queueing a hopeless ENUMERATE-pricer path (the MILP
# pricer does not depend on |V|, but at these sizes the B&P prototype is untested).
# MEASURED 2026-07-02: primary contains 160 files with J in {30,40} (the large
# Catanzaro/Crama series, T up to 60, |V| up to ~1e17) -- BOTH caps trip there, so
# exactly those 160 are skipped. All 80 Laporte7 and all 1010 secondary files
# (J<=15) are kept. The skipped sizes are still covered by the BBC campaign
# (compact solvers, no cap); the B&P is benchmarked on the J<=25 subset.
MAX_NV = 1_000_000_000
# Per solver, after this many consecutive non-optimal results on increasingly
# hard instances, skip the remaining (harder) ones for that solver. 0 disables.
MAX_CONSECUTIVE_TIMEOUTS = 6

# ── Output + CSV schema ───────────────────────────────────────────────────────
OUTPUT_DIR = _HERE
RAW_CSV    = OUTPUT_DIR / "bnp_results.csv"

COLUMNS = [
    "instance", "benchmark_set", "J", "T", "C", "density",
    "solver", "config",
    "status",         # 'optimal' | 'time_limit' | 'error' | 'load_error' | 'skipped_size'
    "obj",            # B&P native objective (free-initial switch count)
    "obj_ktns",       # CANONICAL empty-start switches of the returned sequence -- compare on THIS
    "time_s",
    "gap_pct",        # 0 if optimal; None otherwise (v1)
    "nodes",
    "ncols",          # columns/arcs generated
    "root_lp_bound",  # SCIP root dual bound (PCF' = |U|-b by theory; PTF >=)
    "notes",
]


def get_instances(sets=None):
    """Flat list of (set_label, instance_path, time_limit_s)."""
    if sets is None:
        sets = ALL_SETS
    out = []
    for label, pattern, tl in sets:
        for f in sorted(_glob.glob(pattern, recursive=True)):
            out.append((label, f, tl))
    return out


def get_configs_for_set(_label):
    """Both solvers on every set (no per-set exclusions yet)."""
    return CONFIGS
