#!/usr/bin/env python3
"""
Analysis pass behind every number in Section 6 of the report.
=============================================================

Reads the raw per-instance result shards written by the campaign harness and
recomputes, from scratch, every figure quoted in Section 6, Appendix B and
Appendix C.  Run it with --check to compare each recomputed figure against the
value the report states; it exits non-zero if any of them disagree.

    python3 analyse_campaign_results.py            # print the numbers
    python3 analyse_campaign_results.py --check     # verify the report

TWO THINGS THE KEY MUST GET RIGHT, both of which were wrong in an earlier draft
of this analysis and both of which changed the reported conclusions:

  1. An instance is (benchmark_set, instance, J, T, C).  The Crama collection
     publishes the same matrices at four capacities under the same file names,
     so keying on (set, instance) merges rows describing different instances
     and manufactures cross-method disagreements that do not exist.

  2. The coverage bound is |U| - b, where U is the set of tools that some job
     actually requires -- NOT |T| - b using the tool count in the file header.
     Ten instances of the collection declare a tool no job needs.

Comparison across methods is on `obj_ktns`, the empty-start KTNS cost of the
returned sequence, never on `obj`: SSPMF and the branch-and-price prototypes
report their native objective in the free-initial convention, so `obj` is not
comparable across methods.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

BBC_GLOB = os.path.join(ROOT, "src", "BBC", "results", "*.csv")
BNP_GLOB = os.path.join(ROOT, "src", "BNP", "cluster", "results", "*.csv")
RL_GLOB = os.path.join(ROOT, "src", "BBC", "rl_results", "*.csv")
DATA_DIR = os.path.join(ROOT, "data", "From_Felipe", "data")

KEY = ["benchmark_set", "instance", "J", "T", "C"]
SOLVED = {"MIP_optimal", "optimal", "Optimal", "optimal_tolerance"}
FAMILIES = ["Catanzaro", "Crama", "Laporte3", "Laporte4", "Laporte5", "Laporte7"]

BBC_ORDER = ["SSPMF", "CATZ-F4", "LSS", "BBC-LP+T", "BBC-LP", "BBC-K",
             "BBC-LP+F+H", "BBC-LP+F", "BBC-LP+F+C", "BBC-LP+ACC",
             "BBC-K+F", "BBC-LP+F+P"]
BNP_ORDER = ["PCFp+MC", "PCFp", "PCFp+HP", "PTF", "PCFp+WS", "PCFp+ACC", "PCFp+STAB"]

TIME_SET = ["SSPMF", "LSS", "CATZ-F4", "BBC-LP", "BBC-LP+T", "BBC-K",
            "BBC-LP+F", "BBC-LP+F+H"]


# --------------------------------------------------------------------- loading

def load_shards(pattern: str) -> pd.DataFrame:
    frames = []
    for path in sorted(glob.glob(pattern)):
        try:
            frame = pd.read_csv(path)
        except Exception as exc:                     # a truncated shard
            print(f"  skipping {os.path.basename(path)}: {exc}", file=sys.stderr)
            continue
        if len(frame):
            frames.append(frame)
    if not frames:
        raise SystemExit(f"no result files matched {pattern}")
    out = pd.concat(frames, ignore_index=True)
    out["solved"] = out["status"].isin(SOLVED)
    return out


def used_tool_counts() -> pd.DataFrame:
    """|U| for every instance file, keyed by (instance, J, T, C).

    An instance file is: one header line "J T C", then the tool-by-job incidence
    matrix with one row per tool.  |U| counts the rows that are not all zero.
    """
    records = {}
    for path in glob.glob(os.path.join(DATA_DIR, "**", "*.txt"), recursive=True):
        try:
            tokens = open(path).read().split()
            jobs, tools, cap = (int(tokens[0]), int(tokens[1]), int(tokens[2]))
            body = np.array([int(x) for x in tokens[3:3 + tools * jobs]])
            if len(body) < tools * jobs:
                continue
            matrix = body.reshape(tools, jobs)
        except Exception:
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        records[(stem, float(jobs), float(tools), float(cap))] = int((matrix.sum(1) > 0).sum())
    series = pd.Series(records, name="U")
    series.index.names = ["instance", "J", "T", "C"]
    return series.reset_index()


# ------------------------------------------------------------------- reporting

class Report:
    """Collects (name, computed) pairs and optionally checks them."""

    def __init__(self, check: bool):
        self.check = check
        self.failures: list[str] = []

    def __call__(self, name, value, expected=None):
        if self.check and expected is not None:
            good = (abs(value - expected) < 1e-6
                    if isinstance(expected, (int, float, np.integer, np.floating))
                    else value == expected)
            mark = "ok  " if good else "FAIL"
            print(f"  {mark} {name}: computed {value}, report says {expected}")
            if not good:
                self.failures.append(name)
        else:
            print(f"  {name}: {value}")
        return value


def shifted_geometric_mean(values, shift=10.0):
    return float(np.exp(np.mean(np.log(np.asarray(values, float) + shift))) - shift)


# ------------------------------------------------------------------------ main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="compare every figure against the value stated in the report")
    args = parser.parse_args()
    say = Report(args.check)

    bbc = load_shards(BBC_GLOB)
    used = used_tool_counts()

    # Zstar: the best proved optimum for each instance, in the empty-start
    # convention, taken over every method that closed it.  Attached to every row
    # so that a run can be compared against the answer regardless of which
    # method found it.
    bbc = bbc.join(bbc[bbc.solved].groupby(KEY)["obj_ktns"].min().rename("Zstar"),
                   on=KEY)

    print("\n=== the instance collection ===")
    instances = bbc.groupby(KEY).first().reset_index()
    say("instances", len(instances), 1421)
    for family, expected in zip(FAMILIES, [171, 160, 340, 330, 340, 80]):
        say(f"  {family}", int((instances.benchmark_set == family).sum()), expected)
    say("runs", len(bbc), 16994)
    say("shards", len(glob.glob(BBC_GLOB)), 120)
    say("configurations", int(bbc.config.nunique()), 12)

    # ---------------------------------------------------------- cross-method
    print("\n=== cross-method agreement (Section 6.2) ===")
    proved = bbc[bbc.solved & bbc["obj_ktns"].notna()]
    grouped = proved.groupby(KEY)["obj_ktns"]
    per_instance = pd.DataFrame({"distinct": grouped.nunique(), "n": grouped.count()})
    say("instances with >=1 proved optimum", len(per_instance), 1115)
    say("instances with >=2 proved optima", int((per_instance.n >= 2).sum()), 999)
    say("pairwise comparisons",
        int((per_instance.n * (per_instance.n - 1) / 2).sum()), 41673)
    disagreements = per_instance[per_instance.distinct > 1]
    say("DISAGREEMENTS", len(disagreements), 0)
    if len(disagreements):
        print(disagreements.to_string())

    # ------------------------------------------------------------ conventions
    print("\n=== the two cost conventions (Section 6.2) ===")
    sspmf = bbc[(bbc.config == "SSPMF") & bbc.solved].copy()
    sspmf["shift"] = sspmf["obj_ktns"] - sspmf["obj"]
    say("SSPMF instances closed", len(sspmf), 1038)
    say("  shift equals b", int((np.abs(sspmf["shift"] - sspmf["C"]) < 1e-6).sum()), 1029)
    say("  shift below b", int((sspmf["shift"] < sspmf["C"] - 1e-6).sum()), 9)
    native = bbc[bbc.config.isin(["CATZ-F4", "LSS"]) & bbc.solved]
    say("CATZ-F4 and LSS runs closed", len(native), 1729)
    say("  shift zero",
        int((np.abs(native["obj_ktns"] - native["obj"]) < 1e-6).sum()), 1729)

    # ------------------------------------------------------------ unused tools
    print("\n=== tools no job requires (Section 6.2) ===")
    instances = instances.merge(used, on=["instance", "J", "T", "C"], how="left")
    say("instances matched to a file", int(instances.U.notna().sum()), 1421)
    say("instances with an unused tool", int((instances.U < instances["T"]).sum()), 10)

    # ------------------------------------------------------------ failed runs
    print("\n=== runs that returned no result (Section 6.2) ===")
    errors = bbc[bbc.status == "error"]
    say("failed runs", len(errors), 427)
    crashes = errors["notes"].fillna("").astype(str).str.startswith("subprocess crash")
    say("  worker crashes", int(crashes.sum()), 378)
    say("  harness failures", len(errors) - int(crashes.sum()), 49)
    say("  belonging to LSS", int((errors.config == "LSS").sum()), 352)
    say("    of those on Laporte5",
        int(((errors.config == "LSS") & (errors.benchmark_set == "Laporte5")).sum()), 239)
    say("  belonging to a Benders configuration", int((errors.config != "LSS").sum()), 75)
    say("    most in any one of them",
        int(errors[errors.config != "LSS"].groupby("config").size().max()), 26)

    # ------------------------------------------------------------ solve counts
    print("\n=== instances solved (Table 6.2) ===")
    header = "  ".join(f"{f[:9]:>9}" for f in FAMILIES)
    print(f"  {'configuration':<12} {header}       all")
    for config in BBC_ORDER:
        rows = bbc[bbc.config == config]
        cells = []
        for family in FAMILIES:
            sub = rows[rows.benchmark_set == family]
            cells.append(f"{int(sub.solved.sum())}/{int((sub.status != 'error').sum())}")
        total = f"{int(rows.solved.sum())}/{int((rows.status != 'error').sum())}"
        print(f"  {config:<12} " + "  ".join(f"{c:>9}" for c in cells) + f"  {total:>9}")

    # ------------------------------------------------------------------ times
    print("\n=== solving times (Table 6.3) ===")
    common = None
    for config in TIME_SET:
        idx = bbc[(bbc.config == config) & bbc.solved].set_index(KEY).index
        common = idx if common is None else common.intersection(idx)
    say("instances solved by all eight", len(common), 535)
    for config in TIME_SET:
        rows = bbc[(bbc.config == config) & bbc.solved].set_index(KEY).loc[common]
        rows = rows[~rows.index.duplicated()]
        print(f"  {config:<12} sgm {shifted_geometric_mean(rows['time_s']):8.2f}"
              f"   median {rows['time_s'].median():8.3f}   max {rows['time_s'].max():9.1f}")

    # --------------------------------------------------------- fractional cuts
    print("\n=== fractional cuts (Table 6.4) ===")
    with_f = bbc[bbc.config == "BBC-LP+F"].set_index(KEY).sort_index()
    plain = bbc[bbc.config == "BBC-LP"].set_index(KEY).sort_index()
    shared = with_f.index.intersection(plain.index)
    a, b = with_f.loc[shared], plain.loc[shared]
    say("common instances", len(shared), 1415)
    say("fractional cuts generated", int(with_f["cuts_frac"].fillna(0).sum()), 67513396)
    say("BBC-LP solved", int(b.solved.sum()), 726)
    say("BBC-LP+F solved", int(a.solved.sum()), 659)
    say("median nodes, BBC-LP", int(b["nodes"].median()), 77504)
    say("median nodes, BBC-LP+F", int(a["nodes"].median()), 3795)
    bounds = pd.DataFrame({"f": a["dual_bound"].values, "p": b["dual_bound"].values}).dropna()
    say("instances where both bounds recorded", len(bounds), 1404)
    say("  bound higher with cuts", int((bounds.f > bounds.p + 1e-6).sum()), 0)
    say("  bound equal", int((np.abs(bounds.f - bounds.p) <= 1e-6).sum()), 1228)
    say("  bound lower with cuts", int((bounds.f < bounds.p - 1e-6).sum()), 176)

    # --------------------------------------------------------------- ablation
    print("\n=== strengthenings against BBC-LP+F (Table 6.5) ===")
    for config, expected in [("BBC-LP+F+H", 31), ("BBC-LP+F+C", -2),
                             ("BBC-LP+ACC", -3), ("BBC-LP+F+P", -37), ("BBC-LP", 67)]:
        other = bbc[bbc.config == config].set_index(KEY)
        shared = other.index.intersection(with_f.index)
        delta = int(other.loc[shared].solved.sum()) - int(with_f.loc[shared].solved.sum())
        say(f"  {config}", delta, expected)

    # ------------------------------------------------------------- root node
    print("\n=== where the search stops (Section 6.3) ===")
    lp = bbc[bbc.config == "BBC-LP"]
    lp_solved = lp[lp.solved]
    say("BBC-LP solved", len(lp_solved), 726)
    say("  closed at the root", int((lp_solved["nodes"].fillna(1) <= 1).sum()), 259)
    root = lp[lp["root_lp_bound"].notna() & lp["Zstar"].notna()]
    say("root value and optimum both known", len(root), 883)
    say("  root value equals the optimum",
        int((np.abs(root["root_lp_bound"] - root["Zstar"]) < 1e-6).sum()), 294)
    say("    among runs that closed",
        int((np.abs(root[root.solved]["root_lp_bound"] - root[root.solved]["Zstar"]) < 1e-6).sum()), 264)
    say("      of", int(root.solved.sum()), 497)
    say("    among runs that did not",
        int((np.abs(root[~root.solved]["root_lp_bound"] - root[~root.solved]["Zstar"]) < 1e-6).sum()), 30)
    say("      of", int((~root.solved).sum()), 386)
    short = root[np.abs(root["root_lp_bound"] - root["Zstar"]) >= 1e-6]
    gaps = 100 * (short["Zstar"] - short["root_lp_bound"]) / short["Zstar"]
    say("  median shortfall (%)", round(float(gaps.median()), 1), 16.7)
    say("  maximum shortfall (%)", round(float(gaps.max()), 1), 42.9)

    benders = bbc[bbc.config.str.startswith("BBC")]
    at_limit = benders[benders.status == "MIP_time_limit_feasible"]
    say("Benders runs at the time limit", len(at_limit), 6562)
    known = at_limit[at_limit["Zstar"].notna() & at_limit["obj_ktns"].notna()]
    say("  with the optimum known", len(known), 3874)
    say("  incumbent already optimal",
        int((np.abs(known["obj_ktns"] - known["Zstar"]) < 1e-6).sum()), 2571)
    lp_limit = lp[(lp.status == "MIP_time_limit_feasible") & lp["Zstar"].notna()]
    say("BBC-LP at the limit with optimum known", len(lp_limit), 386)
    say("  incumbent already optimal",
        int((np.abs(lp_limit["obj_ktns"] - lp_limit["Zstar"]) < 1e-6).sum()), 229)

    # ----------------------------------------------------------- tightness
    print("\n=== the coverage bound split (Table 6.6) ===")
    known_opt = instances[instances.Zstar.notna() & instances.U.notna()].copy()
    known_opt["tight"] = np.abs(known_opt.Zstar - known_opt.U) < 1e-6
    say("instances with a known optimum", len(known_opt), 1115)
    say("  coverage bound tight", int(known_opt.tight.sum()), 523)
    say("  coverage bound loose", int((~known_opt.tight).sum()), 592)
    excess = known_opt[~known_opt.tight].Zstar - known_opt[~known_opt.tight].U
    say("  mean excess where loose", round(float(excess.mean()), 2), 5.71)
    say("  maximum excess", int(excess.max()), 30)
    keyed = known_opt.set_index(KEY)
    for config, tight_n, loose_n in [("BBC-LP", 492, 234), ("SSPMF", 523, 515)]:
        rows = bbc[bbc.config == config].set_index(KEY)
        for label, mask, expected in [("tight", keyed.tight, tight_n),
                                      ("loose", ~keyed.tight, loose_n)]:
            idx = keyed[mask].index.intersection(rows.index)
            say(f"  {config} solves, {label}", int(rows.loc[idx].solved.sum()), expected)

    # --------------------------------------------------------- branch-and-price
    print("\n=== branch-and-price (Section 6.5) ===")
    bnp = load_shards(BNP_GLOB)
    say("runs", len(bnp), 2581)
    say("instances", int(bnp.groupby(KEY).ngroups), 469)
    say("configurations", int(bnp.config.nunique()), 7)
    say("runs on 30- and 40-job instances", int(bnp.J.isin([30, 40]).sum()), 608)
    say("  of which closed", int(bnp[bnp.J.isin([30, 40])].solved.sum()), 0)
    for config, solved_n, runs_n in [("PCFp+MC", 102, 422), ("PCFp", 91, 415),
                                     ("PCFp+HP", 73, 360), ("PTF", 73, 387),
                                     ("PCFp+WS", 64, 359), ("PCFp+ACC", 60, 337),
                                     ("PCFp+STAB", 44, 301)]:
        rows = bnp[bnp.config == config]
        say(f"  {config} solved", int(rows.solved.sum()), solved_n)
        say(f"  {config} runs", len(rows), runs_n)

    optima = bbc[bbc.solved].groupby(KEY)["obj_ktns"].min().rename("Zbbc")
    joined = bnp.set_index(KEY).join(optima).reset_index()
    closed = joined[joined.solved]
    say("branch-and-price proved optima", len(closed), 507)
    say("  disagreeing with the campaign",
        int((np.abs(closed["obj_ktns"] - closed["Zbbc"]) > 1e-6).sum()), 0)
    say("  shift equals b",
        int((np.abs((closed["obj_ktns"] - closed["obj"]) - closed["C"]) < 1e-6).sum()), 507)

    merged = joined.merge(used, on=["instance", "J", "T", "C"], how="left")
    merged["q"] = merged["U"] - merged["C"]
    root_rows = merged[merged.root_lp_bound.notna() & merged.U.notna()]
    pcf = root_rows[root_rows.config != "PTF"]
    ptf = root_rows[root_rows.config == "PTF"]
    say("PCF' runs with a root value", len(pcf), 2114)
    say("  root value equal to the coverage bound",
        int((np.abs(pcf.root_lp_bound - pcf.q) < 1e-6).sum()), 2114)
    say("PTF runs with a root value", len(ptf), 233)
    say("  root value above the coverage bound",
        int((ptf.root_lp_bound > ptf.q + 1e-6).sum()), 3)
    above = ptf[ptf.root_lp_bound > ptf.q + 1e-6]
    print(above[["benchmark_set", "instance", "J", "T", "C",
                 "root_lp_bound", "q"]].to_string(index=False))

    both = joined[joined.root_lp_bound.notna() & joined["Zbbc"].notna()].copy()
    both["free"] = both["Zbbc"] - np.minimum(both["C"], both["T"])
    say("runs with root value and optimum", len(both), 1846)
    say("  root value equal to the optimum",
        int((np.abs(both.root_lp_bound - both.free) < 1e-6).sum()), 990)

    pcfp = bnp[bnp.config == "PCFp"].set_index(KEY)
    ptfp = bnp[bnp.config == "PTF"].set_index(KEY)
    shared = pcfp.index.intersection(ptfp.index)
    say("PCF' and PTF common instances", len(shared), 320)
    say("  PCF' solved", int(pcfp.loc[shared].solved.sum()), 73)
    say("  PTF solved", int(ptfp.loc[shared].solved.sum()), 73)
    say("  PCF' median nodes", int(pcfp.loc[shared]["nodes"].median()), 96)
    say("  PTF median nodes", int(ptfp.loc[shared]["nodes"].median()), 2)

    # ---------------------------------------------------------------- rl study
    print("\n=== learned cut selection, knapsack cover cuts (Table 5.3) ===")
    for path in sorted(glob.glob(RL_GLOB), key=lambda p: int(''.join(c for c in os.path.basename(p) if c.isdigit()))):
        row = pd.read_csv(path).iloc[-1]
        print(f"  n={int(row['n']):3d}  learned {row['learned_mean']:.4f}"
              f"   random {row['random_mean']:.4f}   improvement {row['improvement_pct']:+.2f}%"
              f"   (seed {int(row['seed'])}, {int(row['episodes'])} episodes)")

    if args.check:
        print()
        if say.failures:
            print(f"{len(say.failures)} FIGURES DISAGREE WITH THE REPORT:")
            for name in say.failures:
                print("  -", name)
            return 1
        print("every figure agrees with the report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
