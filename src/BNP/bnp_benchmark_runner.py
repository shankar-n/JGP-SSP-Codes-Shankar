"""
BNP Benchmark Runner  (standalone; mirrors src/BBC/benchmark_runner.py)
======================================================================

Runs PCF'/PTF branch-and-price over the configured instance x solver pairs and
appends one CSV row per pair to bnp_results.csv. Safe to interrupt and restart:
completed (instance, config) pairs are skipped on resume and seed the early-stop
counters. Each solve runs in a child process joined with a hard timeout, so a
hung SCIP solve or an OOM model build can't wedge the campaign.

Usage
-----
    python bnp_benchmark_runner.py                       # primary sets, both solvers
    python bnp_benchmark_runner.py --only-sets Catanzaro
    python bnp_benchmark_runner.py --configs PCFp        # one solver
    python bnp_benchmark_runner.py --limit 20 --dry-run  # peek at easiest 20
    python bnp_benchmark_runner.py --task-id 3 --num-tasks 16   # SLURM array shard
"""
import argparse
import csv
import math
import multiprocessing
import sys
import time
from pathlib import Path

_BNP = Path(__file__).resolve().parent          # src/BNP/
_SRC = _BNP.parent                              # src/
for _p in (str(_SRC), str(_SRC / "SSP"), str(_BNP)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bnp_benchmark_config import (
    COLUMNS, RAW_CSV, MAX_JOBS, MAX_NV, MAX_CONSECUTIVE_TIMEOUTS,
    get_instances, get_configs_for_set, PRIMARY_SETS, SECONDARY_SETS, ALL_SETS,
)


# ── Worker (module-level for spawn) ───────────────────────────────────────────
def _worker(instance_path, benchmark_set, config, time_limit, result_queue):
    import sys as _sys
    from pathlib import Path as _Path
    _bnp = _Path(__file__).resolve().parent
    for p in (str(_bnp.parent), str(_bnp.parent / "SSP"), str(_bnp)):
        if p not in _sys.path:
            _sys.path.insert(0, p)
    import traceback
    from instance_loader import load_file
    from utils import compute_ktns

    name = _Path(instance_path).stem
    base = {"instance": name, "benchmark_set": benchmark_set,
            "solver": config["solver"], "config": config["label"]}
    try:
        J, T, C, Tj = load_file(instance_path)
    except Exception as e:
        result_queue.put({**base, "J": None, "T": None, "C": None, "density": None,
                          "status": "load_error", "notes": str(e)[:300]})
        return
    density = sum(len(s) for s in Tj) / (J * T) if J * T else 0.0
    base.update({"J": J, "T": T, "C": C, "density": round(density, 4)})
    tool_req = {j: list(Tj[j]) for j in range(J)}

    def ktns_of(seq):
        if seq is not None and sorted(seq) == list(range(J)):
            return compute_ktns(list(seq), tool_req, C)[0]
        return None

    try:
        from bnp_benchmark_config import accel_of
        accel = accel_of(config)                              # pricing-acceleration flags (empty for baselines)
        if config["solver"] == "PCFp":
            from pcf_prime_bp import branch_and_price
        elif config["solver"] == "PTF":
            from ptf_bp import branch_and_price
        else:
            result_queue.put({**base, "status": "error", "notes": f"unknown solver {config['solver']}"})
            return
        status, obj, nodes, ncols, seq, rlp = branch_and_price(J, T, C, Tj, timelimit=time_limit, accel=accel)
        status = str(status)
        if "time" in status.lower():
            status = "time_limit"          # normalize SCIP's 'timelimit' vs guard's 'time_limit'
        opt = "optimal" in status.lower()
        ok = ktns_of(seq)
        note = ""
        if opt and obj is not None and ok is not None:        # self-check: empty-start == free-initial + initial load
            Uset = set().union(*Tj) if Tj else set()
            expected = obj + min(C, len(Uset))
            if abs(ok - expected) > 0.5:
                note = f"WARN obj_ktns={ok} != obj+min(b,|U|)={expected}"
        result_queue.put({**base,
            "status": str(status), "obj": obj, "obj_ktns": ok,
            "time_s": None, "gap_pct": (0.0 if opt else None),
            "nodes": nodes, "ncols": ncols, "root_lp_bound": rlp, "notes": note})
    except Exception:
        result_queue.put({**base, "status": "error", "notes": traceback.format_exc()[-500:]})


# ── CSV + ordering helpers ────────────────────────────────────────────────────
def _completed(csv_path):
    done = {}
    if Path(csv_path).exists():
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                done[(row["instance"], row["config"])] = str(row.get("status", "")).lower()
    return done


def _append_row(csv_path, row):
    new = not Path(csv_path).exists() or Path(csv_path).stat().st_size == 0
    with open(csv_path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def _features(path):
    """(J, T, C, density) via a token read (handles Crama's 3-line header)."""
    try:
        toks = open(path).read().split()
        J, T, C = int(toks[0]), int(toks[1]), int(toks[2])
        ones = sum(1 for x in toks[3:3 + T * J] if x == "1")
        return J, T, C, (ones / (J * T) if J * T else 0.0)
    except Exception:
        return 10**6, 10**6, 0, 1.0


def build_work_queue(sets, config_filter=None, only_sets=None,
                     max_jobs=None, max_nv=None, min_jobs=None):
    mj = MAX_JOBS if max_jobs is None else max_jobs
    mv = MAX_NV if max_nv is None else max_nv
    lo = 0 if min_jobs is None else min_jobs
    insts = [(b, p, tl) for b, p, tl in get_instances(sets)
             if not only_sets or b in only_sets]
    feats = {p: _features(p) for _, p, _ in insts}
    def _nv(f):                                            # |V| = C(T, b); guards b>T degenerate
        T_, b_ = f[1], f[2]
        return math.comb(T_, b_) if 0 <= b_ <= T_ else 10**18
    kept = [(b, p, tl) for b, p, tl in insts
            if lo <= feats[p][0] <= mj and _nv(feats[p]) <= mv]
    n_skip = len(insts) - len(kept)
    kept.sort(key=lambda r: (feats[r[1]][0], feats[r[1]][1], round(feats[r[1]][3], 4), -feats[r[1]][2]))
    work = []
    for b, p, tl in kept:
        cfgs = get_configs_for_set(b)
        if config_filter:
            cfgs = [c for c in cfgs if c["label"] in config_filter]
        for c in cfgs:
            work.append((b, p, c, tl))
    return work, n_skip


def run_benchmark(sets=None, config_filter=None, only_sets=None, output_csv=None,
                  dry_run=False, limit=None, max_consecutive_timeouts=None,
                  task_id=None, num_tasks=None, max_jobs=None, max_nv=None,
                  min_jobs=None):
    sets = sets or ALL_SETS
    csv_path = Path(output_csv) if output_csv else RAW_CSV
    mct = MAX_CONSECUTIVE_TIMEOUTS if max_consecutive_timeouts is None else max_consecutive_timeouts
    work, n_skip = build_work_queue(sets, config_filter, only_sets,
                                    max_jobs=max_jobs, max_nv=max_nv, min_jobs=min_jobs)
    if limit is not None:
        uniq = list(dict.fromkeys((b, p) for b, p, _, _ in work))[:limit]
        s = set(uniq); work = [w for w in work if (w[0], w[1]) in s]
    if task_id is not None and num_tasks:                 # SLURM array shard by instance
        uniq = list(dict.fromkeys((b, p) for b, p, _, _ in work))
        mine = {uniq[i] for i in range(len(uniq)) if i % num_tasks == task_id}
        work = [w for w in work if (w[0], w[1]) in mine]
    done = _completed(csv_path)
    pending = [w for w in work if (Path(w[1]).stem, w[2]["label"]) not in done]
    print(f"BNP runner | queue {len(work)} ({len(work)-len(pending)} done, {len(pending)} to run) "
          f"| {n_skip} skipped (J outside [{0 if min_jobs is None else min_jobs},{MAX_JOBS if max_jobs is None else max_jobs}] or |V|>{(MAX_NV if max_nv is None else max_nv):.0e}) | early-stop {mct or 'off'} | CSV {csv_path}")
    if dry_run:
        for b, p, c, tl in pending[:12]:
            print(f"   {b:<11} {Path(p).stem:<28} {c['label']}  tl={tl}")
        return

    ctx = multiprocessing.get_context("spawn")
    consec, stopped = {}, set()

    def bump(label, status):
        if "optimal" in (status or "").lower():
            consec[label] = 0
        else:
            consec[label] = consec.get(label, 0) + 1
            if mct and consec[label] >= mct:
                stopped.add(label)

    n_run = 0
    for b, p, c, tl in work:
        name, label = Path(p).stem, c["label"]
        if (name, label) in done:
            bump(label, done[(name, label)]); continue
        if label in stopped:
            continue
        n_run += 1
        print(f"[{n_run}/{len(pending)}] {b:<11} {name:<30} {label}", flush=True)
        q = ctx.Queue()
        proc = ctx.Process(target=_worker, args=(p, b, c, tl, q))
        t0 = time.perf_counter(); proc.start(); proc.join(timeout=tl + 60)
        if proc.is_alive():
            proc.terminate(); proc.join(5)
            if proc.is_alive(): proc.kill(); proc.join(5)
            row = {**{k: None for k in COLUMNS}, "instance": name, "benchmark_set": b,
                   "solver": c["solver"], "config": label, "status": "time_limit",
                   "time_s": round(time.perf_counter() - t0, 1), "notes": "OS timeout"}
            print(f"      -> TIMEOUT {row['time_s']}s")
        else:
            try:
                row = q.get(timeout=5)
                if row.get("time_s") is None:
                    row["time_s"] = round(time.perf_counter() - t0, 2)
                print(f"      -> {row.get('status')} obj_ktns={row.get('obj_ktns')} {row['time_s']}s")
            except Exception as e:
                row = {**{k: None for k in COLUMNS}, "instance": name, "benchmark_set": b,
                       "solver": c["solver"], "config": label, "status": "error",
                       "time_s": round(time.perf_counter() - t0, 2), "notes": f"crash {e}"}
        _append_row(csv_path, row)
        bump(label, row.get("status", ""))
    print(f"Done. Ran {n_run}. Results: {csv_path}")


def main():
    ap = argparse.ArgumentParser(description="BNP (PCF'/PTF) benchmark runner")
    ap.add_argument("--sets", choices=["primary", "secondary", "all"], default="primary")
    ap.add_argument("--only-sets", nargs="+")
    ap.add_argument("--configs", nargs="+", help="PCFp and/or PTF")
    ap.add_argument("--output", "-o", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", "-n", type=int, default=None)
    ap.add_argument("--max-consecutive-timeouts", type=int, default=None)
    ap.add_argument("--task-id", type=int, default=None, help="SLURM array index (0-based)")
    ap.add_argument("--num-tasks", type=int, default=None, help="SLURM array size")
    ap.add_argument("--max-jobs", type=int, default=None, help="override MAX_JOBS size cap")
    ap.add_argument("--min-jobs", type=int, default=None, help="only instances with J >= this (extension runs)")
    ap.add_argument("--max-nv", type=float, default=None, help="override MAX_NV cap")
    a = ap.parse_args()
    sets = {"primary": PRIMARY_SETS, "secondary": SECONDARY_SETS, "all": ALL_SETS}[a.sets]
    run_benchmark(sets=sets, config_filter=set(a.configs) if a.configs else None,
                  only_sets=set(a.only_sets) if a.only_sets else None, output_csv=a.output,
                  dry_run=a.dry_run, limit=a.limit, max_consecutive_timeouts=a.max_consecutive_timeouts,
                  task_id=a.task_id, num_tasks=a.num_tasks,
                  max_jobs=a.max_jobs, max_nv=a.max_nv, min_jobs=a.min_jobs)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
