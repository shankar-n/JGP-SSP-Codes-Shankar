#!/usr/bin/env python3
"""
rerun_lss_crashes.py -- prepare a correct re-run of the LSS runs that crashed.

Run from the repository root:

    python3 src/BBC/cluster/rerun_lss_crashes.py --check     # report only, changes nothing
    python3 src/BBC/cluster/rerun_lss_crashes.py --apply     # strip the crash rows

WHY THIS SCRIPT EXISTS -- two traps make a naive re-run silently do almost nothing.

TRAP 1.  benchmark_runner.py resumes on the key (instance, config).  That key ignores
         benchmark_set and the capacity.  Laporte3 and Laporte5 both contain an
         instance called L1-1, and the Crama collection reuses each name at four
         capacities.  253 of the crashed instance NAMES also appear on a completed
         row, so 289 of the 352 crashed runs would be seen as 'already done' and
         skipped.  Fix: patch the two key functions to include benchmark_set and C
         (see --patch below), or the re-run covers 63 runs instead of 352.

TRAP 2.  The runner retires a config after `max_consecutive_timeouts` consecutive
         non-optimal results and then skips every remaining harder instance.  The
         crashed runs ARE the harder third of the collection, so on a re-run of only
         those the rule fires almost immediately.  Disable it for this job.
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
                    help="also patch benchmark_runner.py's resume key")
    a = ap.parse_args()

    paths = sorted(glob.glob(a.results))
    if not paths:
        sys.exit(f"no files matched {a.results}")
    data = load(paths)

    err_rows = [(p, r) for p, rows in data for r in rows if (r.get("status") or "").lower() == ERR]
    ok_rows = [(p, r) for p, rows in data for r in rows if (r.get("status") or "").lower() != ERR]
    print(f"{len(paths)} shards, {sum(len(r) for _, r in data)} rows, "
          f"{len(err_rows)} crashed")

    # --- how bad is trap 1 under the CURRENT key?
    done_now = {(r["instance"], r["config"]) for _, r in ok_rows}
    blocked = [r for _, r in err_rows if (r["instance"], r["config"]) in done_now]
    print(f"\nTRAP 1 under the current key (instance, config):")
    print(f"  {len(blocked)} of {len(err_rows)} crashed runs would be SKIPPED as already done")

    # --- and under the corrected key?
    done_fix = {(r.get("benchmark_set"), r["instance"], r.get("C"), r["config"]) for _, r in ok_rows}
    blocked2 = [r for _, r in err_rows
                if (r.get("benchmark_set"), r["instance"], r.get("C"), r["config"]) in done_fix]
    print(f"TRAP 1 under (benchmark_set, instance, C, config):")
    print(f"  {len(blocked2)} would be skipped  -> {len(err_rows) - len(blocked2)} actually re-run")

    by_set = {}
    for _, r in err_rows:
        by_set[r.get("benchmark_set")] = by_set.get(r.get("benchmark_set"), 0) + 1
    print("\ncrashed runs to redo, by family:")
    for k, v in sorted(by_set.items()):
        print(f"  {k:<12} {v}")

    if a.patch:
        rp = "src/BBC/benchmark_runner.py"
        s = open(rp, encoding="utf8").read()
        old1 = '            done.add((row["instance"], row["config"]))'
        new1 = '            done.add((row.get("benchmark_set"), row["instance"], row.get("C"), row["config"]))'
        old2 = '            status[(row["instance"], row["config"])] = str(row.get("status", "")).lower()'
        new2 = ('            status[(row.get("benchmark_set"), row["instance"], row.get("C"),\n'
                '                    row["config"])] = str(row.get("status", "")).lower()')
        if old1 not in s or old2 not in s:
            print("\n[patch] anchors not found -- runner already patched, or changed. Not touching it.")
        else:
            shutil.copy(rp, rp + ".bak")
            s = s.replace(old1, new1, 1).replace(old2, new2, 1)
            open(rp, "w", encoding="utf8").write(s)
            print(f"\n[patch] {rp} resume key widened (backup at {rp}.bak)")
            print("        NOTE: the call sites that build `key` must pass the same 4-tuple.")

    if a.apply:
        for p, rows in data:
            keep = [r for r in rows if (r.get("status") or "").lower() != ERR]
            if len(keep) == len(rows):
                continue
            shutil.copy(p, p + ".bak")
            with open(p, "w", newline="") as f:
                wr = csv.DictWriter(f, fieldnames=rows[0].keys())
                wr.writeheader(); wr.writerows(keep)
            print(f"  stripped {len(rows)-len(keep):>3} crash rows from {os.path.basename(p)} "
                  f"(backup {os.path.basename(p)}.bak)")
        print("\nCrash rows removed. Now re-run LSS with early-stop OFF:")
        print("  sbatch --array=0-9 src/BBC/cluster/run_campaign.sbatch "
              "--configs LSS --max-consecutive-timeouts 0")
    else:
        print("\n(nothing changed -- pass --apply to strip the crash rows)")


if __name__ == "__main__":
    main()
