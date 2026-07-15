#!/usr/bin/env python3
"""Remove error/crash rows from a results CSV so the resuming runner retries them.
Usage: python3 strip_error_rows.py results/raw_LSS_primary.csv [more.csv ...]"""
import csv, sys, shutil
for p in sys.argv[1:]:
    rows = list(csv.DictReader(open(p, newline="")))
    keep = [r for r in rows if "error" not in (r.get("status") or "").lower()]
    if len(keep) == len(rows):
        print(f"{p}: no error rows"); continue
    shutil.copy(p, p + ".bak")
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(keep)
    print(f"{p}: removed {len(rows)-len(keep)} error rows (backup: {p}.bak)")
