#!/usr/bin/env python3
"""Post-campaign triage: status counts, error digests, cross-solver agreement.
Usage: python3 triage_results.py <csv-or-glob> [more ...]   (BBC and/or BNP CSVs)
"""
import csv, glob, sys, collections

rows = []
for pat in sys.argv[1:]:
    for f in sorted(glob.glob(pat)):
        with open(f, newline="") as fh:
            for r in csv.DictReader(fh):
                r["_file"] = f
                rows.append(r)
print(f"rows: {len(rows)} from {len(set(r['_file'] for r in rows))} files\n")

# 1) status by (config, set)
tab = collections.Counter()
for r in rows:
    tab[(r.get("config"), r.get("benchmark_set"), r.get("status"))] += 1
cfgs = sorted(set(k[0] for k in tab))
sets_ = sorted(set(k[1] for k in tab))
sts   = sorted(set(k[2] for k in tab))
print("== status by config ==")
print(f"{'config':<10}" + "".join(f"{s:>13}" for s in sts) + f"{'TOTAL':>8}")
for c in cfgs:
    cnt = [sum(v for k, v in tab.items() if k[0] == c and k[2] == s) for s in sts]
    print(f"{c:<10}" + "".join(f"{n:>13}" for n in cnt) + f"{sum(cnt):>8}")

# 2) error digests
errs = collections.Counter()
for r in rows:
    if r.get("status") in ("error", "load_error"):
        note = (r.get("notes") or "").strip().splitlines()
        errs[(r.get("config"), note[-1][:110] if note else "<no note>")] += 1
if errs:
    print("\n== error digests (config, last traceback line) ==")
    for (c, msg), n in errs.most_common(15):
        print(f"  {n:4d}x  [{c}]  {msg}")

# 3) cross-solver obj_ktns agreement on optimal rows  (THE integrity check)
opt = collections.defaultdict(dict)
for r in rows:
    if r.get("status", "").lower().find("optimal") >= 0 and r.get("obj_ktns") not in (None, "", "None"):
        opt[(r.get("benchmark_set"), r["instance"])][r["config"]] = float(r["obj_ktns"])
bad = {i: v for i, v in opt.items() if len(set(v.values())) > 1}
print(f"\n== cross-solver agreement: {len(opt)} instances with >=1 optimal row; DISAGREEMENTS: {len(bad)} ==")
for i, v in list(bad.items())[:10]:
    print(f"  {i}: {v}")

# 4) native-objective identity check (empty-start solvers: obj == obj_ktns)
mism = collections.Counter()
for r in rows:
    if "optimal" in r.get("status", "").lower() and r.get("config") not in ("SSPMF", "PCFp", "PTF"):
        try:
            if round(float(r["obj"])) != round(float(r["obj_ktns"])):
                mism[r["config"]] += 1
        except (TypeError, ValueError, KeyError):
            pass
print(f"\n== empty-start identity obj==obj_ktns violations (per config) == {dict(mism) or 'none'}")

# 5) WARN notes (BNP self-check) and time_limit share on big instances
warns = sum(1 for r in rows if "WARN" in (r.get("notes") or ""))
print(f"BNP convention-self-check WARNs: {warns}")
big_tl = sum(1 for r in rows if r.get("status") == "time_limit" and r.get("J") not in (None, "", "None") and int(float(r["J"])) >= 30)
tl = sum(1 for r in rows if r.get("status") == "time_limit")
print(f"time_limit rows: {tl}  (of which J>=30: {big_tl})")
