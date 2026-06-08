"""
Generate LaTeX Tables from raw_results.csv
===========================================

Produces three tables for the paper:

  Table 1: Primary small instances — Catanzaro + Crama + Laporte7
           All 10 configs.  Columns: % optimal, SGM(time), median obj.

  Table 2: BBC ablation — all 8 BBC configs on primary instances.
           Columns: % opt, SGM(t), median nodes, median cuts, median root_lp_bound.

  Table 3: Secondary (medium) instances — Laporte3-5, BBC + LSS only.
           Same structure as Table 1.

All times use the shifted geometric mean with shift = 10 s (standard in
MIP computational papers; Achterberg et al. 2006).

Usage
-----
    python generate_tables.py
    python generate_tables.py --raw raw_results.csv --jgp jgp_gsp_costs.csv
"""

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

_BBC  = Path(__file__).resolve().parent.parent    # src/BBC/
sys.path.insert(0, str(_BBC))
from benchmark_config import RAW_CSV, JGP_GSP_CSV, ANALYSIS_DIR

# ── Output directory ──────────────────────────────────────────────────────────
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def load_results(raw_csv):
    rows = []
    with open(raw_csv, newline="") as f:
        for r in csv.DictReader(f):
            # Type-cast numerics
            for col in ("J", "T", "C", "nodes", "lp_iters", "cb_invocations",
                        "cuts_sec", "cuts_benders", "cuts_comb", "cuts_frac"):
                r[col] = int(r[col]) if r.get(col) not in (None, "", "None") else None
            for col in ("density", "obj", "time_s", "gap_pct",
                        "root_lp_bound", "dual_bound"):
                r[col] = float(r[col]) if r.get(col) not in (None, "", "None") else None
            r["optimal"] = "optimal" in str(r.get("status", "")).lower()
            rows.append(r)
    return rows


def load_jgp_costs(jgp_csv):
    costs = {}
    if not Path(jgp_csv).exists():
        return costs
    with open(jgp_csv, newline="") as f:
        for r in csv.DictReader(f):
            key = (r["instance"], r["benchmark_set"])
            val = float(r["jgp_gsp_cost"]) if r.get("jgp_gsp_cost") not in (None, "", "None") else None
            costs[key] = val
    return costs


# ─────────────────────────────────────────────────────────────────────────────
# Statistics helpers
# ─────────────────────────────────────────────────────────────────────────────

SHIFT = 10.0   # shifted geometric mean shift parameter

def sgm(times, time_limit=3600.0):
    """
    Shifted geometric mean of solve times.
    Unsolved instances (time_s is None or status != optimal) use time_limit.
    shift = SHIFT = 10 s  (Achterberg et al. 2006 convention)
    """
    vals = [(t if t is not None else time_limit) for t in times]
    if not vals:
        return float("nan")
    return math.exp(sum(math.log(v + SHIFT) for v in vals) / len(vals)) - SHIFT


def pct_opt(rows):
    if not rows:
        return float("nan")
    return 100.0 * sum(1 for r in rows if r["optimal"]) / len(rows)


def _median(vals):
    vs = sorted(v for v in vals if v is not None)
    if not vs:
        return None
    n = len(vs)
    return vs[n // 2] if n % 2 else (vs[n // 2 - 1] + vs[n // 2]) / 2


def _mean(vals):
    vs = [v for v in vals if v is not None]
    return sum(vs) / len(vs) if vs else None


# ─────────────────────────────────────────────────────────────────────────────
# Table builders
# ─────────────────────────────────────────────────────────────────────────────

PRIMARY_SETS   = {"Catanzaro", "Crama", "Laporte7"}
SECONDARY_SETS = {"Laporte3", "Laporte4", "Laporte5"}
BBC_CONFIGS    = ["BBC-LP", "BBC-LP+F", "BBC-LP+T", "BBC-LP+FT",
                  "BBC-K",  "BBC-K+F",  "BBC-K+T",  "BBC-K+FT"]
ALL_CONFIGS    = BBC_CONFIGS + ["LSS", "SSPMF"]


def build_table1_3(rows, set_filter, config_list, caption, label, time_limit=3600.0):
    """
    Table 1 and Table 3: one row per benchmark set × config showing
    % optimal, SGM(time), median obj.
    """
    # Filter
    data = [r for r in rows if r["benchmark_set"] in set_filter
                            and r["config"] in config_list]
    if not data:
        return f"% No data for {caption}\n"

    # Group: benchmark_set → config → [rows]
    grouped = defaultdict(lambda: defaultdict(list))
    for r in data:
        grouped[r["benchmark_set"]][r["config"]].append(r)

    cols = [c for c in config_list if any(c in grouped[s] for s in set_filter)]

    lines = []
    lines.append(r"\begin{table}[ht]")
    lines.append(r"\centering")
    lines.append(r"\small")
    col_spec = "l" + "".join("rr" for _ in cols)
    lines.append(f"\\begin{{tabular}}{{{col_spec}}}")
    lines.append(r"\toprule")

    # Header row 1: config names (spanning 2 cols each)
    hdr1 = "Set"
    for c in cols:
        hdr1 += f" & \\multicolumn{{2}}{{c}}{{{c.replace('+', '+')}}} "
    lines.append(hdr1 + r" \\")

    # Header row 2: % opt | SGM(t)
    hdr2 = ""
    for c in cols:
        hdr2 += r" & \%opt & SGM"
    lines.append(r"\cmidrule(lr){2-" + str(1 + 2 * len(cols)) + r"}")
    lines.append(r"" + hdr2 + r" \\")
    lines.append(r"\midrule")

    set_order = [s for s in ["Catanzaro", "Crama", "Laporte7",
                              "Laporte3", "Laporte4", "Laporte5"]
                 if s in set_filter and s in grouped]
    total_by_config = defaultdict(list)

    for bset in set_order:
        row_cells = bset
        for c in cols:
            rlist = grouped[bset].get(c, [])
            popt  = pct_opt(rlist)
            times = [r["time_s"] for r in rlist]
            s     = sgm(times, time_limit)
            row_cells += f" & {popt:.0f}\\% & {s:.1f}"
            total_by_config[c].extend(rlist)
        lines.append(row_cells + r" \\")

    # Summary row
    lines.append(r"\midrule")
    sumrow = "Total"
    for c in cols:
        rlist = total_by_config[c]
        popt  = pct_opt(rlist)
        times = [r["time_s"] for r in rlist]
        s     = sgm(times, time_limit)
        sumrow += f" & \\textbf{{{popt:.0f}\\%}} & \\textbf{{{s:.1f}}}"
    lines.append(sumrow + r" \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(f"\\caption{{{caption}}}")
    lines.append(f"\\label{{{label}}}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def build_table2_ablation(rows, time_limit=3600.0):
    """
    Table 2: BBC ablation — all 8 BBC configs on primary instances.
    Columns: % opt, SGM(t), median nodes, median cuts_benders+comb+frac, median root_lp_bound.
    """
    data = [r for r in rows if r["benchmark_set"] in PRIMARY_SETS
                            and r["config"] in BBC_CONFIGS]
    if not data:
        return "% No BBC ablation data\n"

    grouped = defaultdict(list)
    for r in data:
        grouped[r["config"]].append(r)

    lines = []
    lines.append(r"\begin{table}[ht]")
    lines.append(r"\centering")
    lines.append(r"\small")
    lines.append(r"\begin{tabular}{lrrrrrr}")
    lines.append(r"\toprule")
    lines.append(r"Config & \%opt & SGM(t) & Med.\ nodes & Med.\ B-cuts & Med.\ frac-cuts & Med.\ root-LB \\")
    lines.append(r"\midrule")

    for cfg in BBC_CONFIGS:
        rlist = grouped.get(cfg, [])
        if not rlist:
            lines.append(f"{cfg} & --- & --- & --- & --- & --- & --- \\\\")
            continue
        popt     = pct_opt(rlist)
        times    = [r["time_s"] for r in rlist]
        s        = sgm(times, time_limit)
        med_nodes = _median([r["nodes"] for r in rlist])
        # Total Benders cuts = cuts_benders + cuts_comb
        bcuts = [((r.get("cuts_benders") or 0) + (r.get("cuts_comb") or 0)) for r in rlist
                 if r.get("cuts_benders") is not None]
        med_bcuts = _median(bcuts) if bcuts else None
        med_frac  = _median([r["cuts_frac"] for r in rlist])
        med_rlb   = _median([r["root_lp_bound"] for r in rlist])

        def _fmt(v, fmt=".0f"):
            return (f"{v:{fmt}}" if v is not None else "---")

        lines.append(
            f"{cfg} & {popt:.0f}\\% & {s:.1f} & "
            f"{_fmt(med_nodes)} & {_fmt(med_bcuts)} & "
            f"{_fmt(med_frac)} & {_fmt(med_rlb, '.1f')} \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\caption{BBC component ablation on primary instances (Catanzaro + Crama + Laporte7). "
                 r"SGM = shifted geometric mean (shift=10\,s). "
                 r"B-cuts = integer Benders cuts (combinatorial + LP). "
                 r"Frac-cuts = fractional user cuts added at LP nodes.}")
    lines.append(r"\label{tab:bbc_ablation}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main(raw_csv=None, jgp_csv=None):
    raw_csv = Path(raw_csv) if raw_csv else RAW_CSV
    jgp_csv = Path(jgp_csv) if jgp_csv else JGP_GSP_CSV

    if not raw_csv.exists():
        print(f"ERROR: {raw_csv} not found.  Run benchmark_runner.py first.")
        sys.exit(1)

    print(f"Loading results from {raw_csv} ...")
    rows = load_results(raw_csv)
    print(f"  {len(rows)} rows loaded.")

    # ── Table 1: Primary, all 10 configs ─────────────────────────────────
    t1 = build_table1_3(
        rows,
        set_filter=PRIMARY_SETS,
        config_list=ALL_CONFIGS,
        caption=(r"Computational results on primary benchmark instances "
                 r"(Catanzaro, Crama, Laporte7). "
                 r"TL = 3600\,s. \%opt = percentage solved to optimality. "
                 r"SGM = shifted geometric mean of solve time (shift=10\,s); "
                 r"unsolved instances contribute the time limit."),
        label="tab:primary_results",
        time_limit=3600.0,
    )
    out1 = ANALYSIS_DIR / "table1_primary.tex"
    out1.write_text(t1)
    print(f"Table 1 → {out1}")

    # ── Table 2: BBC ablation ─────────────────────────────────────────────
    t2 = build_table2_ablation(rows)
    out2 = ANALYSIS_DIR / "table2_ablation.tex"
    out2.write_text(t2)
    print(f"Table 2 → {out2}")

    # ── Table 3: Secondary (Laporte3-5), BBC+LSS ─────────────────────────
    secondary_configs = [c for c in ALL_CONFIGS if c != "SSPMF"]
    t3 = build_table1_3(
        rows,
        set_filter=SECONDARY_SETS,
        config_list=secondary_configs,
        caption=(r"Computational results on secondary benchmark instances "
                 r"(Laporte Tabela 3--5, $J=8$--15, $T=15$, $c=5$). "
                 r"TL = 600\,s. SSPMF excluded (prohibitively slow at $J=15$)."),
        label="tab:secondary_results",
        time_limit=600.0,
    )
    out3 = ANALYSIS_DIR / "table3_secondary.tex"
    out3.write_text(t3)
    print(f"Table 3 → {out3}")

    print("\nAll tables written.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default=None, help="Path to raw_results.csv")
    parser.add_argument("--jgp", default=None, help="Path to jgp_gsp_costs.csv")
    args = parser.parse_args()
    main(args.raw, args.jgp)
