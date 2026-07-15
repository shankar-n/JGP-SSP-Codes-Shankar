# RUNBOOK — remaining runs + PTF improvement track (2026-07-15)

> Execute top to bottom. Every cluster command assumes you are on frontalhpc2025
> with the repo synced and, where python is invoked by hand, the env active:
> `source ~/miniforge3/etc/profile.d/conda.sh && conda activate ssp_env`.

## Phase A — finish the campaigns (cluster, ~1 night)

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
sbatch --array=8 --mem=32G cluster/run_campaign.sbatch
```
(`--array=8` = LSS only; resume re-attempts exactly the stripped rows, early-stop
counters re-seed from the CSV so no budget is wasted.)

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

## Phase B — PTF improvement track (started 2026-07-15)

**B1. DONE — gap-instance testbed.** `src/BNP/gap_testbed.csv`: 419 instances,
each solved by at least one exact solver, each with Z*_free strictly above the
coverage bound |U|−b — i.e., exactly the instances where a stronger relaxation
can pay, with ground-truth optima attached for free.

**B2. NEXT (Claude, code+proof):** in `ptf_bp.py`:
  (i) grouping cut  Σ(config-changing arcs) ≥ K*−1  with K* from `solve_jgp_arf`
      (validity = the grouping lower bound; to be stated + verified vs brute);
  (ii) warm-start columns from the JGP+GSP / greedy sequence (incumbent from
      the start, prunes the a-branching tree);
  (iii) root-gap instrumentation: log (|U|−b, PTF root LP, Z*) per instance.
  Each verified against the P0 scripts + brute before hand-off.

**B3. THEN (you, cluster):** benchmark `PTF` vs `PTF+cuts` on the 419-instance
testbed (exact command supplied with B2; ~overnight at 600 s TL).

**B4. Decision gate:** if the root-gap closure  (rootLP − (|U|−b)) / (Z* − (|U|−b))
improves materially and solves increase, the PTF section upgrades from
"first lever" to a measured contribution and seeds the follow-up methods paper.
If not, the paper reports the honest current state; nothing else changes.

**B5. Optional, with Prof. Wagler:** PORTA facet mining on the 6-ring PTF
polytope (Windows, `tools/porta-1.4.1`); input files prepared on request.

## Phase C — paper

After A4 lands: §5.3 tables + results narrative get built from the merged CSVs
(solve rates, ablation incl. the real F-axis, bound-tightness ≈48%/52% split,
LSS-strongest finding, BNP root-closure stats), then the full paper pass.
