#!/usr/bin/env python3
"""Build the PTF gap-instance testbed from campaign results.
A 'gap instance' here: solved by any exact solver with Z*_free > |U|-b, i.e.
obj_ktns > T (all tools used in these families). These are exactly the instances
where a relaxation stronger than the coverage bound can pay.
Writes: gap_testbed.csv  (set, instance, path, Z*_ktns, T, C, slack)"""
import csv, glob, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
best = {}
for f in glob.glob(str(ROOT/"src/BBC/results/raw_*.csv")) + \
         glob.glob(str(ROOT/"src/BNP/bnp_results.csv")) + \
         glob.glob(str(ROOT/"src/BNP/cluster/results/*.csv")):
    for r in csv.DictReader(open(f, newline="")):
        if "optimal" not in (r.get("status") or "").lower(): continue
        try: ok, T, C = float(r["obj_ktns"]), int(float(r["T"])), int(float(r["C"]))
        except (TypeError, ValueError): continue
        best[(r["benchmark_set"], r["instance"])] = (ok, T, C)
# map stems back to file paths
sys.path.insert(0, str(ROOT/"src/BBC"))
from benchmark_config import ALL_SETS, get_instances
paths = {(b, Path(p).stem): p for b, p, tl in get_instances(ALL_SETS)}
out = []
for (b, inst), (ok, T, C) in sorted(best.items()):
    excess = ok - T           # Z*_free - (|U|-b) = obj_ktns - |U|,  |U|=T here
    if excess > 0.5:
        out.append((b, inst, paths.get((b, inst), "?"), ok, T, C, excess))
with open(HERE/"gap_testbed.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["set","instance","path","obj_ktns","T","C","excess_over_coverage"])
    w.writerows(out)
print(f"gap testbed: {len(out)} instances (of {len(best)} solved) -> {HERE/'gap_testbed.csv'}")
for r in out[:8]: print("  ", r[0], r[1], "Z*ktns=%g T=%d C=%d excess=%g" % (r[3], r[4], r[5], r[6]))
