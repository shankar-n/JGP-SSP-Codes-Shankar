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
# The two position formulations. Each runs PCF'/PTF branch-and-price from src/BNP/
# (enumerate-or-MILP pricer by size, set automatically inside branch_and_price).
CONFIGS = [
    {"label": "PCFp", "solver": "PCFp"},
    {"label": "PTF",  "solver": "PTF"},
]

# ── Size cap + early-stop ─────────────────────────────────────────────────────
# The prototype exact B&P (a_{t,p} integer branching + MILP pricing) does not
# scale to the largest files (Otiai J=300-400 would OOM building the master), so
# we SKIP instances with J above MAX_JOBS rather than waste a time-limit on a
# model that can't be built. Raise this as the pricer/branching mature. (BBC has
# no such cap because CPLEX handles much larger compact models.)
MAX_JOBS = 25
# Also skip instances whose configuration space |V| = C(T, b) is astronomically
# large (Otiai ~1e57): a pure backstop against queueing a hopeless model. For the
# current sets every |V|>1e9 instance already has J>MAX_JOBS, so this is redundant
# with the J cap -- it only bites if MAX_JOBS is raised. (Verified against the data:
# Catanzaro/Crama J<=25 all have |V|<=5e6; Laporte max |V|~3.3e6, all kept.)
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
