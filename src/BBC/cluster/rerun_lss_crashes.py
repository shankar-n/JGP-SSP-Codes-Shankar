#!/usr/bin/env python3
"""
rerun_lss_crashes.py -- prepare a correct re-run of the LSS runs that crashed.

Run from the repository root:

    python3 src/BBC/cluster/rerun_lss_crashes.py --check     # report only, changes nothing
    python3 src/BBC/cluster/rerun_lss_crashes.py --apply     # strip the crash rows

WHY THIS SCRIPT EXISTS -- two traps made a naive re-run silently do almost nothing.

TRAP 1.  The original runner resumed on (instance, config), ignoring the family and
         dimensions.  It now uses (family, instance, J, T, C, config), so repeated
         names such as the four Crama capacities no longer collide.  The diagnostic
         below retains the legacy-key comparison to document the original failure.

TRAP 2.  The runner retires a config after `max_consecutive_timeouts` consecutive
         non-optimal results and then skips every remaining harder instance.  The
         crash rows are concentrated late in the time limit, but their missing size
         fields do not support a clean difficulty ranking.  A recovery run must still
         disable retirement so that another run's status cannot suppress a target.
"""
import argparse, csv, glob, os, shutil, sys

ERR = "error"


def load(paths):
    out = []
    for p in paths:
        with open(p, newline="") as f:
            rows = list(csv.DictReader(f))
        out.append((p, rows))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="src/BBC/results/raw_LSS_*.csv")
    ap.add_argument("--apply", action="store_true", help="actually strip the crash rows")
    ap.add_argument("--check", action="store_true", help="report only (default)")
    ap.add_argument("--patch", action="store_true",
                    help="deprecated compatibility flag; the runner already uses the full key")
    a = ap.parse_args()

    paths = sorted(glob.glob(a.results))
    if not paths:
        sys.exit(f"no files matched {a.results}")
    data = load(paths)

    err_rows = [(p, r) for p, rows in data for r in rows if (r.get("status") or "").lower() == ERR]
    ok_rows = [(p, r) for p, rows in data for r in rows if (r.get("status") or "").lower() != ERR]
    print(f"{len(paths)} shards, {sum(len(r) for _, r in data)} rows, "
          f"{len(err_rows)} crashed")

    # --- how bad was trap 1 under the legacy key?
    done_now = {(r["instance"], r["config"]) for _, r in ok_rows}
    blocked = [r for _, r in err_rows if (r["instance"], r["config"]) in done_now]
    print(f"\nTRAP 1 under the legacy key (instance, config):")
    print(f"  {len(blocked)} of {len(err_rows)} crashed runs would be SKIPPED as already done")

    # --- and under the corrected key?
    def full_key(r):
        def as_int(value):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return None
        return (r.get("benchmark_set"), r["instance"], as_int(r.get("J")),
                as_int(r.get("T")), as_int(r.get("C")), r["config"])

    done_fix = {full_key(r) for _, r in ok_rows}
    blocked2 = [r for _, r in err_rows
                if full_key(r) in done_fix]
    print("TRAP 1 under the current full key "
          "(benchmark_set, instance, J, T, C, config):")
    print(f"  {len(blocked2)} would be skipped  -> {len(err_rows) - len(blocked2)} actually re-run")

    by_set = {}
    for _, r in err_rows:
        by_set[r.get("benchmark_set")] = by_set.get(r.get("benchmark_set"), 0) + 1
    print("\ncrashed runs to redo, by family:")
    for k, v in sorted(by_set.items()):
        print(f"  {k:<12} {v}")

    if a.patch:
        print("\n[patch] no action: benchmark_runner.py already uses the full six-field key")

    if a.apply:
        raise SystemExit(
            "REFUSED: this historical strip-and-rerun workflow is obsolete and can "
            "mix resource protocols. Use cluster/RECOVERY_RUNBOOK.md and the exact "
            "recovery manifests instead. No files were changed."
        )
    else:
        print("\n(read-only historical diagnostic; see cluster/RECOVERY_RUNBOOK.md)")


if __name__ == "__main__":
    main()
