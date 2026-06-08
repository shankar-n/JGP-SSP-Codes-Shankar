# BBC Benchmark Plan

_Last updated: June 2026. This is a working research plan — update when results or scope change._

---

## 0. Context and Purpose

This plan covers the computational benchmarking of the BBC (Branch-and-Benders-Cut) solver for SSP, targeting a research-publishable comparison against LSS (Laporte 2004) and SSPMF (da Silva 2024). The benchmark has two purposes:

1. **Competitive**: Show where BBC sits relative to prior exact solvers across standard instance sets.
2. **Analytical**: Decompose BBC's performance to understand the marginal contribution of each algorithmic component (KTNS cuts, fractional user cuts, triplet bounds).

---

## 1. Instance Sets

### Primary Benchmark (Felipe's folder — use for all runs)

| Set                      | Path                                      | Count | J range | T range | c   |
| ------------------------ | ----------------------------------------- | ----- | ------- | ------- | --- |
| Catanzaro / Tabela1C     | `data/From_Felipe/data/Catanzaro/Tabela1C/` | 195   | 8–15    | 5–15    | 3–5 |
| Crama                    | `data/From_Felipe/data/Crama/`             | 160   | 10      | 10      | 4   |
| Laporte / Tabela7        | `data/From_Felipe/data/Laporte/Tabela7/`   | 80    | 10      | 10      | 4   |
| Laporte / Tabela3–5      | `data/From_Felipe/data/Laporte/Tabela3-5/` | ~680  | 8–15    | 15      | 5   |
| Laporte / Tabela6        | `data/From_Felipe/data/Laporte/Tabela6/`   | 260   | 20      | —       | —   |

**Primary subset for all 10 solver configs:** Catanzaro (195) + Crama (160) + Laporte/Tabela7 (80) = **435 instances**.

**Secondary (BBC + LSS only, 600s TL):** Laporte/Tabela3–5 (~680 instances).

**Excluded from exact solving:** Otiai (200–300 jobs, no exact solver will prove optimality in reasonable time). Include in paper as a scalability remark.

### Cross-Reference with MTSP Folder (da Silva's website)

`data/MTSP/` is da Silva's publicly released instance set. Before running the benchmark, verify overlap with Felipe's folder:

```bash
# Compare filenames between the two Catanzaro sets
diff <(ls data/MTSP/Catanzaro/ | sort) <(ls data/From_Felipe/data/Catanzaro/Tabela1C/ | sort)
```

If MTSP is a strict subset of Felipe's Catanzaro (160 ⊆ 195), we can write: _"Our primary set includes the 160 Catanzaro and 161 Crama instances benchmarked by da Silva et al. (2024), plus 35 additional Catanzaro instances."_ This enables direct numerical comparison of obj and time values against their Table 3.

MTSP is for cross-referencing only. Do **not** switch the primary data source to MTSP.

---

## 2. Solver Configurations

BBC has three binary flags with non-trivial independent effects: `comb_cuts`, `frac_cuts`, `triplet_bounds`. Fix `lp_reuse=False` throughout (affects only speed, not correctness or node count — keeping it fixed removes a confound). This gives a **2³ = 8 BBC configurations**, plus LSS and SSPMF:

| Label      | `comb` | `frac` | `triplet` | What it isolates                                                                                  |
| ---------- | ------ | ------ | --------- | ------------------------------------------------------------------------------------------------- |
| BBC-LP     | F      | F      | F         | Pure LP Benders baseline — Benders cuts from DSP LP dual only                                    |
| BBC-LP+F   | F      | T      | F         | Marginal effect of fractional user cuts in LP mode                                                |
| BBC-LP+T   | F      | F      | T         | Marginal effect of triplet root tightening in LP mode                                             |
| BBC-LP+FT  | F      | T      | T         | Full LP Benders                                                                                   |
| BBC-K      | T      | F      | F         | Pure KTNS-Benders baseline — combinatorial cuts, no LP DSP                                       |
| BBC-K+F    | T      | T      | F         | **Novel contribution**: KTNS + fractional cuts at LP nodes                                       |
| BBC-K+T    | T      | F      | T         | KTNS + triplet bounds — tests whether root tightening helps when cuts are already strong          |
| BBC-K+FT   | T      | T      | T         | Best-of-all configuration                                                                         |
| LSS        | —      | —      | —         | Laporte 2004 lifted objective + valid inequalities                                                |
| SSPMF      | —      | —      | —         | da Silva 2024 multicommodity flow, `C21=False`                                                    |

**Why triplet bounds must be included:** Their effect is not predictable a priori — they add O(n³) constraints (heavier LP per node) but potentially tighten the root relaxation significantly (fewer nodes). Whether the tradeoff is positive or negative is itself an empirical result. The LP+T vs. LP and K+T vs. K comparisons give a clean answer.

**Why all 8 BBC configs and not just the best:** The ablation structure (vary one flag at a time) is the publishable claim. A paper that only reports the best config cannot say _why_ it is best.

---

## 3. Metrics Recorded Per Run

```python
{
    # Instance descriptor
    'instance': str,           # filename without extension
    'benchmark_set': str,      # e.g. 'Catanzaro', 'Crama', 'Laporte7'
    'J': int, 'T': int, 'C': int,
    'density': float,          # mean |T_j| / T

    # Solver config
    'solver': str,             # 'BBC', 'LSS', 'SSPMF'
    'config': str,             # e.g. 'BBC-K+F', 'LSS'
    'comb_cuts': bool,
    'frac_cuts': bool,
    'triplet_bounds': bool,

    # Results
    'status': str,             # 'optimal' | 'time_limit' | 'error'
    'obj': float,              # switch cost (null if no feasible found)
    'time_s': float,           # wall-clock seconds
    'gap_pct': float,          # MIP gap at termination (0 if optimal)

    # B&B diagnostics (BBC only; null for LSS/SSPMF)
    'nodes': int,
    'lp_iters': int,
    'cb_invocations': int,
    'cuts_sec': int,           # subtour elimination cuts added
    'cuts_benders': int,       # integer Benders cuts
    'cuts_frac': int,          # fractional user cuts
    'root_lp_bound': float,    # LP bound at root before B&B
    'dual_bound': float,       # final dual bound
}
```

**JGP+GSP cost:** Computed in a separate preprocessing pass (one per instance), stored in `jgp_gsp_costs.csv`, joined during analysis. It is a problem-level descriptor (helps explain why some instances are harder) — not a solver output. Do not compute it inside benchmark_runner.

---

## 4. Research Hypotheses

These are falsifiable predictions. The benchmark either confirms or refutes each one. The paper reports the result either way.

**H1 — KTNS cuts are faster than LP Benders on sparse instances, LP Benders on dense instances.**

_Mechanism:_ On sparse instances (mean `|T_j|/c` < 0.6), the pairwise overlap `w_ij` values are small, making the LP DSP solution close to the LP relaxation bound — a weak cut. KTNS computes the exact combinatorial cost in O(n|T|) and generates a cut just as strong but without solving an LP. On dense instances, the LP DSP dual provides a tighter bound because the relaxation captures continuous mixing.

_Measurement:_ Compare BBC-LP vs. BBC-K on geometric mean solve time, stratified by density quartile. Expect BBC-K ≤ BBC-LP for density < 0.6, reversed above it.

**H2 — Fractional user cuts substantially reduce B&B tree size (nodes) on medium instances (J ≥ 12).**

_Mechanism:_ At LP relaxation nodes, `x̄` is fractional — many implied sequences are partial. Adding a Benders cut at this point eliminates a subtree of integer candidates that would otherwise be explored. On small instances the tree is already small so the overhead dominates. On large instances the LP nodes themselves take too long.

_Measurement:_ Compare `nodes` (BBC-K vs. BBC-K+F) and `time_s` on Catanzaro/Laporte instances split by J. The hypothesis predicts a >40% node reduction and net time reduction for 12 ≤ J ≤ 15. If time_s _increases_ despite fewer nodes, the per-node overhead of the fractional callback is the bottleneck — that is still a publishable result (negative).

**H3 — Triplet bounds tighten the root LP relaxation but are net-negative for BBC-K and net-positive for BBC-LP.**

_Mechanism:_ BBC-K+T adds O(n³) triplet constraints that strengthen the LP at every node. For BBC-K, the KTNS cuts already push the bound up fast; the triplets add overhead without much additional tightening. For BBC-LP, whose cuts are weaker, the additional root tightening helps more.

_Measurement:_ Compare `root_lp_bound` (LP+T vs. LP and K+T vs. K), and `time_s` (same comparisons). The hypothesis is asymmetric: expect `root_lp_bound` to increase in both cases, but `time_s` to decrease only for BBC-LP+T.

**H4 — BBC-K+FT solves more instances within 1 hour than LSS on Laporte/Tabela3-5 (J=15), while LSS is competitive or better on Catanzaro (J≤10).**

_Mechanism:_ LSS uses a lifted objective and valid inequalities that are highly effective on small, dense instances where the LP relaxation is tight. As J grows (Laporte Tabela4-5), the monolithic ILP's LP relaxation degrades and the BBC decomposition becomes relatively more efficient.

_Measurement:_ % optimal within TL on each benchmark set. Expected crossover around J=12.

**H5 — Instance difficulty (solve time) correlates with the JGP-SSP gap: gap=0 (collapse) instances are significantly easier for all solvers.**

_Mechanism:_ When gap=0, the JGP+GSP heuristic already provides an optimal solution as an upper bound. All exact solvers can terminate early once their dual bound meets this. Instances with gap≥1 require proof by contradiction across all feasible sequences.

_Measurement:_ Scatter of `time_s` vs. `jgp_gsp_gap` (joined from preprocessing). Run a Spearman rank correlation. If ρ > 0.5, include in paper as evidence that the JGP-SSP gap is not just a theoretical quantity but a practical difficulty predictor.

---

## 5. Time Limits

| Benchmark set         | Time limit | Rationale                                                    |
| --------------------- | ---------- | ------------------------------------------------------------ |
| Catanzaro + Crama + Laporte7 | **3600 s** | Matches da Silva 2024; enables direct comparison         |
| Laporte/Tabela3-5     | **600 s**  | ~680 × 10 configs × 600s ≈ manageable; trends visible       |
| Laporte/Tabela6       | **600 s**  | BBC only; feasibility check                                 |

---

## 6. SEC Strategy (Important Subtlety)

In the BBC master problem, degree constraints are present from the start. SECs (subtour elimination constraints) are added **lazily** as violated integer candidates appear. This means:

- The LP relaxation at the root has no SEC constraints → intentionally weak lower bound
- Fractional Benders cuts fire at LP nodes where `x̄` is fractional and may represent partial tours. These cuts implicitly partition the feasible space and can partially substitute for SECs.
- The `root_lp_bound` metric will reveal whether fractional cuts push the root LP up substantially — this is the observable test of the SEC-Benders interaction.

A separate MTZ experiment is **not needed** for this benchmark. The data from `root_lp_bound` across configs will make the point more cleanly.

---

## 7. Output for Paper

### Tables

**Table 1: Primary small instances** (Catanzaro 195 + Crama 160 + Laporte7 80, 3600s TL)

Columns: Instance group | J range | T range | c | % opt (LSS) | SGM(t) (LSS) | % opt (SSPMF) | SGM(t) (SSPMF) | % opt (BBC-K+FT) | SGM(t) (BBC-K+FT)

Aggregated by benchmark set. One row per set plus a TOTAL row.

**Table 2: BBC ablation** (same 435 instances)

Columns: Config | % opt | SGM(t) | Median nodes | Median cuts_benders | Median cuts_frac | Median root_lp_bound

One row per BBC config. Sorted by % opt descending. This table is the main evidence for the component analysis.

**Table 3: Medium instances** (Laporte/Tabela3-5, 600s TL, BBC + LSS only)

Same structure as Table 1. Shows scalability beyond small instances.

_Note: SGM = shifted geometric mean with shift=10 (standard in MIP computational papers)._

### Plots

**Figure 1: Performance Profile (Dolan-Moré)**

- x-axis: time ratio τ relative to best solver on that instance (log scale, 1 to 3600)
- y-axis: fraction of instances solved within factor τ of best
- One curve per configuration (10 curves)
- This is the single most informative plot in the paper — it shows dominance across all instances simultaneously without cherry-picking. Standard in computational OR (used by Dolan & Moré 2002, adopted universally since).

_Expected shape:_ BBC-K+FT and BBC-K+F curves should cross above LSS somewhere between τ=1 and τ=10 for the primary set.

**Figure 2: Ablation Contribution (Bar Chart)**

- x-axis: BBC configuration labels (BBC-LP, BBC-LP+F, ..., BBC-K+FT)
- y-axis: % instances solved within TL
- Grouped bars: one group per benchmark set (Catanzaro, Crama, Laporte7)
- Directly readable marginal contribution of each flag. The jump from BBC-K to BBC-K+F is the visual representation of H2.

**Figure 3: Root LP Bound vs. Node Count (Scatter)**

- x-axis: root_lp_bound (normalised by optimal obj)
- y-axis: nodes (log scale)
- Points coloured by triplet_bounds (on=red, off=blue), shaped by frac_cuts (filled=yes, open=no)
- Confirms H3: triplet bounds should shift points left (tighter root bound) and down (fewer nodes) for BBC-LP configs but show little effect for BBC-K configs.

**Figure 4: Node Reduction from Fractional Cuts (Histogram)**

- x-axis: log₂(nodes_BBC-K / nodes_BBC-K+F) for each instance where both solved optimally
- y-axis: count
- Positive values = fractional cuts helped; negative = they added overhead
- Separate panels for J ≤ 10 and J ≥ 12
- This is the quantitative evidence for H2. If the J≥12 panel is shifted right, the hypothesis is confirmed.

**Figure 5: Convergence Traces (Selected Hard Instances)**

- x-axis: wall-clock time (seconds)
- y-axis: dual bound (normalised by optimal obj)
- 4–6 representative instances from Laporte/Tabela5 that BBC-K+F solved but BBC-K did not within TL
- One line per relevant config (BBC-K, BBC-K+F, BBC-K+FT, LSS)
- Qualitative evidence — shows the shape of convergence and when fractional cuts fire

**Figure 6: Solve Time vs. Problem Size (Scalability)**

- x-axis: J (number of jobs)
- y-axis: SGM(time_s) across instances of that J value (log scale)
- One line per config: BBC-K+FT, LSS, SSPMF
- Shows which solver degrades least as J grows. Expected: SSPMF degrades fastest (multicommodity flow grows as J²×T), LSS is middle, BBC slowest degradation.

---

## 8. Code Structure

```
src/BBC/
  benchmark_runner.py      ← NEW: multi-config loop, process-based timeout,
                              incremental CSV append, skip completed pairs
  benchmark_config.py      ← NEW: instance set paths, BBC hyperparameter grid,
                              time limits, constants
  analysis/
    generate_tables.py     ← NEW: CSV → LaTeX tables (Table 1-3)
    generate_plots.py      ← NEW: all 6 figures
    precompute_jgp_gsp.py  ← NEW: one-off pass, writes jgp_gsp_costs.csv
  benchmark.py             ← KEEP AS IS for quick one-off single-config runs
```

### benchmark_runner.py — Key Design Decisions

- Outer loop: instances × configs. Inner: single solver call.
- Each solver call wrapped in `multiprocessing.Process` with `join(timeout=TL+60)`. CPLEX's internal time limit can be unreliable if callbacks hang — OS-level kill is the safety net.
- Results appended to `raw_results.csv` row-by-row after each run. A restart skips already-completed `(instance, config)` pairs.
- Crama file format uses J/T/C on separate lines — verify `load_ssp_instance` handles this before running.
- No parallelism across instances. Sequential for reproducibility. Use a second machine for a parallel run only if total wall time exceeds 72h.

### benchmark_config.py — Key Contents

```python
INSTANCE_SETS = {
    'Catanzaro': ('data/From_Felipe/data/Catanzaro/Tabela1C/', 3600),
    'Crama':     ('data/From_Felipe/data/Crama/',              3600),
    'Laporte7':  ('data/From_Felipe/data/Laporte/Tabela7/',    3600),
    'Laporte35': ('data/From_Felipe/data/Laporte/Tabela3-5/',   600),
    'Laporte6':  ('data/From_Felipe/data/Laporte/Tabela6/',     600),
}

BBC_CONFIGS = [
    {'label': 'BBC-LP',    'comb_cuts': False, 'frac_cuts': False, 'triplet_bounds': False},
    {'label': 'BBC-LP+F',  'comb_cuts': False, 'frac_cuts': True,  'triplet_bounds': False},
    {'label': 'BBC-LP+T',  'comb_cuts': False, 'frac_cuts': False, 'triplet_bounds': True},
    {'label': 'BBC-LP+FT', 'comb_cuts': False, 'frac_cuts': True,  'triplet_bounds': True},
    {'label': 'BBC-K',     'comb_cuts': True,  'frac_cuts': False, 'triplet_bounds': False},
    {'label': 'BBC-K+F',   'comb_cuts': True,  'frac_cuts': True,  'triplet_bounds': False},
    {'label': 'BBC-K+T',   'comb_cuts': True,  'frac_cuts': False, 'triplet_bounds': True},
    {'label': 'BBC-K+FT',  'comb_cuts': True,  'frac_cuts': True,  'triplet_bounds': True},
    {'label': 'LSS',       'solver_class': 'LSS'},
    {'label': 'SSPMF',     'solver_class': 'SSPMF', 'C21': False},
]
```

---

## 9. Pre-Run Checklist

Before launching the full benchmark:

1. Verify `load_ssp_instance` parses all three format variants (Catanzaro, Crama, Laporte)
2. Run all 10 configs on 5 small Catanzaro instances and confirm CSV output schema
3. Cross-reference MTSP vs. Felipe folder filenames (see §1)
4. Run `precompute_jgp_gsp.py` on all 435 primary instances; verify outputs are sensible
5. Confirm CPLEX license is available on the machine running the benchmark
6. Estimate wall time: run 1 instance of each size class with `time_limit=60` to get per-instance medians
