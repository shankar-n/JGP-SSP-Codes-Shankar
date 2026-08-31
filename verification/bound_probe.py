#!/usr/bin/env python3
"""
Bound-strength probe: how much of the gap Z* - q can two fixed bounds close?
============================================================================

The report's diagnosis is that every inequality in both exact methods is supported on
a LOCAL object -- an arc (i,j) in the Benders master, a single position in PCF'.  The
cost, however, is  Z = sum over tools of (number of magazine blocks of that tool), and
a re-insertion is caused by the GLOBAL interleaving of the sequence.

This probe measures the ceiling of two candidate families on real instances, WITHOUT a
commercial solver, by enumerating every sequence of an 8-job instance:

  q       = |U|                      the coverage bound (empty-start).  What the
                                     Benders master's root LP actually returns on 87%
                                     of runs, and exactly what the PCF' relaxation
                                     returns on 100% of runs.

  L_pair  = min over sequences of    the fixed Tang--Denardo pairwise row solved to
            [ |T_first| + sum w ]    optimality as a Hamiltonian path.

  L_pair_cov = max(q, L_pair)        that fixed pairwise row together with coverage.
                                     It is NOT a ceiling for all arc-supported cuts.

  L_win   = min over sequences of    the WINDOW family.  For a contiguous block of
            [ best window bound ]    positions W, the magazine before W holds at most b
                                     tools, so at least |U_W| - b insertions happen
                                     inside W (and |U_W| for a window starting at
                                     position 1, where the magazine is empty).
                                     Disjoint windows count disjoint insertions, so the
                                     contributions add.  Per sequence the best window
                                     decomposition is an O(n^2) dynamic program.

  Z*      = the proved optimum, taken from the finished campaign.

Both L_pair_cov and L_win are valid lower bounds on Z*: each is obtained from a
quantity that never exceeds a sequence's cost.  L_win >= q always, because the single
window [1, n] gives exactly |U|.  A cross-check against the recorded Benders roots is
printed explicitly because those roots can, and sometimes do, exceed L_pair_cov.

The number that decides whether the family is worth implementing is

    closed  =  (L - q) / (Z* - q)

on the instances where the coverage bound is loose.  A family that closes little of the
gap here cannot close it inside a solver either, and is not worth cluster time.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
from itertools import permutations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "From_Felipe" / "data" / "Laporte" / "Tabela3"
DEFAULT_MANIFEST = Path(__file__).resolve().with_name("bound_probe_instances.txt")
DEFAULT_OUTPUT = Path(__file__).resolve().with_name("bound_probe_results.json")
DEFAULT_CAMPAIGN_GLOB = ROOT / "src" / "BBC" / "results" / "*.csv"


def read_instance(path):
    """Returns (n_jobs, n_tools, capacity, [tool bitmask per job])."""
    tok = open(path).read().split()
    n, m, b = int(tok[0]), int(tok[1]), int(tok[2])
    grid = [int(x) for x in tok[3: 3 + m * n]]
    masks = [0] * n
    for t in range(m):
        for j in range(n):
            if grid[t * n + j]:
                masks[j] |= 1 << t
    return n, m, b, masks


def pairwise_weights(masks, b):
    """w[i][j] = max(0, |T_i U T_j| - b), the Tang-Denardo adjacency weight."""
    n = len(masks)
    return [[max(0, (masks[i] | masks[j]).bit_count() - b) for j in range(n)]
            for i in range(n)]


def probe(n, b, masks, w):
    """Enumerate every sequence once; return (L_pair, L_win)."""
    rng = range(n)
    best_pair = None
    best_win = None
    popc = int.bit_count

    for perm in permutations(rng):
        pm = [masks[j] for j in perm]

        # ---- pairwise Hamiltonian-path bound -----------------------------
        val = popc(pm[0])
        for k in range(n - 1):
            val += w[perm[k]][perm[k + 1]]
        if best_pair is None or val < best_pair:
            best_pair = val

        # ---- window bound: best decomposition into consecutive windows ----
        # c[p][k] = contribution of the window covering positions p..k
        #           = |U| for p == 0 (empty magazine), else max(0, |U| - b)
        # g[k] = best total over positions 0..k-1
        g = [0] * (n + 1)
        for k in range(1, n + 1):
            best = g[k - 1]                     # leave position k-1 out of any window
            u = 0
            for p in range(k - 1, -1, -1):
                u |= pm[p]
                size = popc(u)
                contrib = size if p == 0 else (size - b if size > b else 0)
                cand = g[p] + contrib
                if cand > best:
                    best = cand
            g[k] = best
        if best_win is None or g[n] < best_win:
            best_win = g[n]

    return best_pair, best_win


def _number(value):
    """Parse a numeric CSV/JSON value, keeping integer optima as integers."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return int(parsed) if parsed.is_integer() else parsed


def load_optima_json(path):
    """Load either the legacy key-value JSON or a prior list of probe rows."""
    with Path(path).open() as stream:
        data = json.load(stream)
    if isinstance(data, dict):
        return {str(key): _number(value) for key, value in data.items()
                if _number(value) is not None}
    if isinstance(data, list):
        result = {}
        for row in data:
            key = f"{row['inst']}|{int(row['n'])}|{int(row['T'])}|{int(row['b'])}"
            value = _number(row.get("Z"))
            if value is not None:
                result[key] = value
        return result
    raise ValueError(f"unsupported optima JSON structure in {path}")


def load_campaign_optima(pattern):
    """Derive proved empty-start optima from the checked-in campaign shards."""
    values = {}
    paths = sorted(glob.glob(str(pattern)))
    if not paths:
        raise FileNotFoundError(f"no campaign CSV matched {pattern}")
    for path in paths:
        with open(path, newline="") as stream:
            for row in csv.DictReader(stream):
                status = str(row.get("status", "")).strip().lower()
                if row.get("benchmark_set") != "Laporte3" or status not in {
                    "mip_optimal", "optimal"
                }:
                    continue
                value = _number(row.get("obj_ktns"))
                try:
                    key = (row["instance"], int(float(row["J"])),
                           int(float(row["T"])), int(float(row["C"])))
                except (KeyError, TypeError, ValueError):
                    continue
                if value is not None:
                    values.setdefault(key, set()).add(value)
    disagreements = {key: vals for key, vals in values.items() if len(vals) != 1}
    if disagreements:
        first = next(iter(disagreements.items()))
        raise ValueError(f"campaign optima disagree for {first[0]}: {sorted(first[1])}")
    return {f"{name}|{n}|{tools}|{capacity}": next(iter(vals))
            for (name, n, tools, capacity), vals in values.items()}


def selected_paths(data_dir, manifest, all_instances=False):
    """Return the explicit diagnostic sample, or every data file on request."""
    if all_instances:
        return sorted(data_dir.glob("*.txt"))
    names = [line.strip() for line in manifest.read_text().splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate entry in {manifest}")
    paths = [data_dir / name for name in names]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("manifest entries not found:\n  " + "\n  ".join(missing))
    return paths


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("legacy_optima", nargs="?",
                        help="legacy positional optima JSON (mapping or prior row list)")
    parser.add_argument("--optima", help="optima JSON (overrides campaign CSV loading)")
    parser.add_argument("--campaign-glob", default=str(DEFAULT_CAMPAIGN_GLOB),
                        help="campaign CSV glob used when no optima JSON is supplied")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--instances", type=Path, default=DEFAULT_MANIFEST,
                        help="one instance file name per line; defaults to report sample")
    parser.add_argument("--all-instances", action="store_true",
                        help="probe every n<=9 instance in --data-dir instead of manifest")
    parser.add_argument("--check", action="store_true",
                        help="fail unless the fixed report sample reproduces its claims")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main():
    args = parse_args()
    optima_path = args.optima or args.legacy_optima
    optima = (load_optima_json(optima_path) if optima_path
              else load_campaign_optima(args.campaign_glob))
    paths = selected_paths(args.data_dir, args.instances, args.all_instances)
    print(f"selection: {'all n<=9 instances' if args.all_instances else args.instances}")
    print(f"optima: {optima_path or args.campaign_glob}")
    print(f"output: {args.output}")

    rows = []
    for path in paths:
        stem = path.stem
        n, m, b, masks = read_instance(path)
        if n > 9:
            continue
        used = 0
        for msk in masks:
            used |= msk
        q = used.bit_count()                    # coverage bound, empty-start
        w = pairwise_weights(masks, b)
        L_pair, L_win = probe(n, b, masks, w)
        key = f"{stem}|{n}|{m}|{b}"
        Z = optima.get(key)
        if Z is None:
            raise ValueError(f"no proved optimum found for {key}")
        rows.append(dict(inst=stem, n=n, T=m, b=b, U=q, q=q,
                         L_pair=L_pair, L_win=L_win, Z=Z))
        print(f"{stem:8s} T={m:2d} b={b:2d}  |U|={q:2d}  L_pair={L_pair:3d} "
              f"L_win={L_win:3d}  Z*={Z}", flush=True)

    print()
    print("=" * 78)
    loose = [r for r in rows if r["Z"] is not None and r["Z"] > r["q"]]
    tight = [r for r in rows if r["Z"] is not None and r["Z"] == r["q"]]
    print(f"instances probed        : {len(rows)}")
    print(f"  coverage bound tight  : {len(tight)}")
    print(f"  coverage bound loose  : {len(loose)}")
    if not loose:
        return
    print()
    print("ON THE LOOSE INSTANCES -- fraction of the gap Z* - q each fixed bound closes")
    print("-" * 78)
    for r in rows:
        r["L_pair_cov"] = max(r["q"], r["L_pair"])
    for name in ("L_pair_cov", "L_win"):
        fr = [(r[name] - r["q"]) / (r["Z"] - r["q"]) for r in loose]
        exact = sum(1 for r in loose if r[name] == r["Z"])
        nogain = sum(1 for r in loose if r[name] == r["q"])
        fr_sorted = sorted(fr)
        med = fr_sorted[len(fr_sorted) // 2]
        print(f"  {name:7s}  mean {sum(fr)/len(fr):6.1%}   median {med:6.1%}   "
              f"max {max(fr):6.1%}   reaches Z* on {exact}/{len(loose)}   "
              f"no gain on {nogain}/{len(loose)}")
    print()
    print("absolute units of the gap closed (loose instances only):")
    for name in ("L_pair_cov", "L_win"):
        d = [r[name] - r["q"] for r in loose]
        tot = sum(r["Z"] - r["q"] for r in loose)
        print(f"  {name:7s}  {sum(d):.0f} of {tot:.0f} units  "
              f"(mean +{sum(d)/len(d):.2f} per instance)")
    print()
    print("raw pairwise path bound is BELOW the coverage bound on "
          f"{sum(1 for r in rows if r['L_pair'] < r['q'])}/{len(rows)} instances")
    both = [max(r["L_win"], r["L_pair_cov"]) for r in loose]
    fr = [(bb - r["q"]) / (r["Z"] - r["q"]) for bb, r in zip(both, loose)]
    print(f"taking the better of the two: mean {sum(fr)/len(fr):.1%} of the gap closed")

    # Guard against the former, invalid interpretation of L_pair_cov as a ceiling for
    # every arc-supported Benders cut.  The campaign roots provide a direct refutation.
    roots_any, roots_plain = {}, {}
    for campaign_path in sorted(glob.glob(str(args.campaign_glob))):
        with open(campaign_path, newline="") as stream:
            for campaign_row in csv.DictReader(stream):
                config = str(campaign_row.get("config", ""))
                if campaign_row.get("benchmark_set") != "Laporte3" or not config.startswith("BBC-"):
                    continue
                root = _number(campaign_row.get("root_lp_bound"))
                try:
                    root_key = (campaign_row["instance"], int(float(campaign_row["J"])),
                                int(float(campaign_row["T"])), int(float(campaign_row["C"])))
                except (KeyError, TypeError, ValueError):
                    continue
                if root is None:
                    continue
                roots_any[root_key] = max(root, roots_any.get(root_key, root))
                if config == "BBC-LP":
                    roots_plain[root_key] = max(root, roots_plain.get(root_key, root))

    comparable = []
    plain_comparable = []
    for r in rows:
        root_key = (r["inst"], int(r["n"]), int(r["T"]), int(r["b"]))
        if root_key in roots_any:
            comparable.append((r, roots_any[root_key]))
        if root_key in roots_plain:
            plain_comparable.append((r, roots_plain[root_key]))
    any_above = [(r, root) for r, root in comparable if root > r["L_pair_cov"] + 1e-6]
    plain_above = [(r, root) for r, root in plain_comparable
                   if root > r["L_pair_cov"] + 1e-6]
    print()
    print("campaign guard: L_pair_cov is not a ceiling for all arc-supported cuts")
    print(f"  any Benders configuration exceeds it on {len(any_above)}/{len(comparable)} "
          "comparable sample identities")
    print(f"  plain BBC-LP exceeds it on {len(plain_above)}/{len(plain_comparable)} "
          "comparable sample identities")

    if args.check:
        actual = {
            "instances": len(rows),
            "tight": len(tight),
            "loose": len(loose),
            "pair_no_gain": sum(r["L_pair_cov"] == r["q"] for r in loose),
            "window_no_gain": sum(r["L_win"] == r["q"] for r in loose),
            "comparable_roots": len(comparable),
            "any_benders_above": len(any_above),
            "plain_roots": len(plain_comparable),
            "plain_bbc_lp_above": len(plain_above),
        }
        expected = {
            "instances": 81,
            "tight": 19,
            "loose": 62,
            "pair_no_gain": 46,
            "window_no_gain": 18,
            "comparable_roots": 70,
            "any_benders_above": 7,
            "plain_roots": 70,
            "plain_bbc_lp_above": 3,
        }
        disagreements = {name: (actual[name], value) for name, value in expected.items()
                         if actual[name] != value}
        if disagreements:
            raise AssertionError(f"report-number disagreements: {disagreements}")
        print("  report-number check: PASS")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        json.dump(rows, fh, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    main()
