# RUNBOOK — remaining runs + PTF improvement track (2026-07-15)

> Execute top to bottom. Every cluster command assumes you are on frontalhpc2025
> with the repo synced and, where python is invoked by hand, the env active:
> `source ~/miniforge3/etc/profile.d/conda.sh && conda activate ssp_env`.

## Phase A — finish the campaigns  [COMPLETE 2026-07-15: +F structurally inactive (0 frac cuts); LSS crashes -> timeouts at 32GB (2 residual errors); BNP n>=30: zero solves. Final numbers in report tab:solves + VERIFIED_FACTS.]

**A0. Sync the repo to the cluster.** Today's fixes it carries: presolve-off for
fractional cuts (branch_and_benders_cut_cplex.py), CRLF fix (merge_results.sh,
probe.sh), BNP status normalization, `strip_error_rows.py`, `harvest_gap_testbed.py`,
`gap_testbed.csv`.

**A1. +F rerun** (the fractional-cut arm never fired before the fix; its old rows
must go or the runner will skip everything):
```bash
cd <repo>/src/BBC
rm -f results/raw_BBC-LP+F_*.csv results/raw_BBC-LP+FT_*.csv \
      results/raw_BBC-K+F_*.csv  results/raw_BBC-K+FT_*.csv
sbatch --array=1,3,5,7 cluster/run_campaign.sbatch
sbatch --export=ALL,SETS=secondary --array=1,3,5,7 cluster/run_campaign.sbatch
```
Success signature: `cuts_frac > 0` in the new rows. Either outcome is a finding
(bound lifts = positive ablation result; bound stays 2 = final nail for §5.4).

**A2. LSS memory retry** (8 OOM crashes on Catanzaro B-series):
```bash
cd <repo>/src/BBC
python3 cluster/strip_error_rows.py results/raw_LSS_primary.csv
sbatch --array=8 --mem-per-cpu=8192 cluster/run_campaign.sbatch
```
(`--array=8` = LSS only. NOTE: the script's header already sets
`--mem-per-cpu=4096`, and SLURM forbids mixing `--mem` with `--mem-per-cpu` —
so raise memory by overriding the SAME option: 8192 MB/core x 4 cores = 32 GB.
Resume re-attempts exactly the stripped rows; early-stop counters re-seed from
the CSV so no budget is wasted.)

**A3. BNP J>25 extension** — SKIP if you already submitted it:
```bash
cd <repo>/src/BNP
MINJ=26 MAXJ=45 sbatch --mem=16G cluster/run_bnp.sbatch
```

**A4. When queues drain — merge and sync back:**
```bash
cd <repo>/src/BBC && bash cluster/merge_results.sh
cd <repo>/src/BNP && bash cluster/merge_results.sh
# then rsync/copy src/BBC/results, src/BBC/raw_results.csv,
# src/BNP/cluster/results, src/BNP/bnp_results.csv back to the laptop repo
```

## Phase B — PTF improvement track  [2026-07-16: extremal-law hunts done (new attainment at R=1; (5,3)/(6,3) corners resist); idealness scan done (24% non-integral on edge-b3, off-ring witness — see plans-genai/wagler_prep_data.md); coverage row LIVE in BBC master (6-ring: 0 cuts). Remaining: cluster re-run arrays 0-7 (delete raw_BBC-*.csv first); Wagler sessions.]

**B1. DONE — gap-instance testbed.** `src/BNP/gap_testbed.csv`: 419 instances,
each solved by at least one exact solver, each with Z*_free strictly above the
coverage bound |U|−b — i.e., exactly the instances where a stronger relaxation
can pay, with ground-truth optima attached for free.

**B2. REVISED 2026-07-15 — the PTF study, done properly (methodology first).**
The earlier B2 (grouping cut / warm starts) was engineering ahead of science and
is withdrawn as a research step (the grouping cut binds almost nowhere on the
testbed: K*−1 ≤ q on typical benchmarks). Correct order:
  (i)  polytope study on small witnesses with everything known (6-ring, I0/I1,
       the b=5 refutation witnesses): enumerate integer points, PORTA/lrs for
       the full facet list;
  (ii) collect the ACTUAL fractional root solutions from the solver on those
       instances; identify which facet classes cut them;
  (iii) interpret the classes combinatorially (ring symmetry orbits), prove
       validity in general, ideally facetness under stated conditions;
  (iv) separation algorithm + complexity;
  (v)  ONLY THEN implementation and evaluation on the 419-instance testbed
       (root-gap closure = the metric).
Steps (i)-(iii) are the Wagler-collaboration content; the blocking-duality
section added to plans-genai/13 (odd-ring non-idealness) is the session opener.
Warm starts / instrumentation remain useful engineering but are not the study.

**B3. THEN (you, cluster):** benchmark `PTF` vs `PTF+cuts` on the 419-instance
testbed (exact command supplied with B2; ~overnight at 600 s TL).

**B4. Decision gate:** if the root-gap closure  (rootLP − (|U|−b)) / (Z* − (|U|−b))
improves materially and solves increase, the PTF section upgrades from
"first lever" to a measured contribution and seeds the follow-up methods paper.
If not, the paper reports the honest current state; nothing else changes.

**B5. Optional, with Prof. Wagler:** PORTA facet mining on the 6-ring PTF
polytope (Windows, `tools/porta-1.4.1`); input files prepared on request.

## Phase C — paper  [§5.3 written 2026-07-15; deck prepared; remaining: compile + read-through]

After A4 lands: §5.3 tables + results narrative get built from the merged CSVs
(solve rates, ablation incl. the real F-axis, bound-tightness ≈48%/52% split,
LSS-strongest finding, BNP root-closure stats), then the full paper pass.
