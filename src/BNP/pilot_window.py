#!/usr/bin/env python3
"""
pilot_window.py -- Stage 1 of RESEARCH_NEXT.md.

Measures what the window family actually delivers at the ROOT of PCF', against the
coverage bound q, on the loose instances.  Root bound only: no branching, so the
Python pricer cannot confound the measurement.

    python3 pilot_window.py --dir loose --meta loose/_meta.json --out pilot_win.csv

Bar to clear (RESEARCH_NEXT.md): mean root rise >= 15% of (Z* - q).
"""
import argparse, csv, json, os, sys, time, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcf_prime_bp import branch_and_price, LAST_WINDOW_STATS


def read_instance(path):
    tok = open(path).read().split()
    n, T, b = int(tok[0]), int(tok[1]), int(tok[2])
    v = list(map(int, tok[3:3 + T * n]))
    Tj = [set(t for t in range(T) if v[t * n + j]) for j in range(n)]
    return n, T, b, Tj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--meta", required=True, help="json: inst -> {q, Z}")
    ap.add_argument("--out", default="pilot_win.csv")
    ap.add_argument("--timelimit", type=float, default=120.0)
    ap.add_argument("--maxlen", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="only the first N instances")
    a = ap.parse_args()

    meta = json.load(open(a.meta))
    files = sorted(glob.glob(os.path.join(a.dir, "*.txt")))
    if a.limit:
        files = files[:a.limit]

    rows = []
    with open(a.out, "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["instance", "n", "T", "b", "q", "Zstar", "gap",
                     "root_plain", "root_window", "rise", "frac_of_gap",
                     "windows", "wrows", "wvars", "t_plain", "t_window"])
        for f in files:
            name = os.path.splitext(os.path.basename(f))[0]
            if name not in meta:
                continue
            n, T, b, Tj = read_instance(f)
            # bound_probe reports q and Z in the EMPTY-START convention; the master's
            # objective is free-initial.  Convert: subtract min(b, |U|) from both.
            U = len({t for s_ in Tj for t in s_})
            shift = min(b, U)
            q = meta[name]["q"] - shift
            Z = (meta[name]["Zstar"] if "Zstar" in meta[name] else meta[name]["Z"]) - shift
            gap = Z - q
            t0 = time.time()
            _, _, _, _, _, r0 = branch_and_price(n, T, b, Tj, timelimit=a.timelimit,
                                                 accel={"root_only": True})
            t1 = time.time()
            _, _, _, _, _, r1 = branch_and_price(n, T, b, Tj, timelimit=a.timelimit,
                                                 accel={"root_only": True, "window_cuts": True,
                                                        "window_max_len": a.maxlen})
            t2 = time.time()
            ws = dict(LAST_WINDOW_STATS)
            rise = (r1 - r0) if (r0 is not None and r1 is not None) else None
            frac = (rise / gap) if (rise is not None and gap > 0) else None
            wr.writerow([name, n, T, b, q, Z, gap,
                         None if r0 is None else round(r0, 4),
                         None if r1 is None else round(r1, 4),
                         None if rise is None else round(rise, 4),
                         None if frac is None else round(frac, 4),
                         ws.get("windows"), ws.get("rows"), ws.get("vars"),
                         round(t1 - t0, 2), round(t2 - t1, 2)])
            fh.flush()
            rows.append((name, r0, r1, q, Z, frac))
            print(f"  {name:<8} q={q:<3} Z*={Z:<3} gap={gap:<3} "
                  f"root {('%.3f' % r0) if r0 is not None else '  -  '} -> "
                  f"{('%.3f' % r1) if r1 is not None else '  -  '}   "
                  f"{'' if frac is None else f'{100*frac:5.1f}% of gap'}", flush=True)

    good = [f for *_, f in rows if f is not None]
    if good:
        good.sort()
        mean = sum(good) / len(good)
        med = good[len(good) // 2]
        print(f"\n{len(good)} instances measured")
        print(f"  mean rise  {100*mean:.1f}% of the gap")
        print(f"  median     {100*med:.1f}%")
        print(f"  no rise on {sum(1 for x in good if x < 1e-9)} of {len(good)}")
        print(f"\n  BAR IS 15% MEAN -> {'CLEARED, go to stage 2' if mean >= 0.15 else 'NOT CLEARED, fix the encoding not the cluster'}")


if __name__ == "__main__":
    main()
