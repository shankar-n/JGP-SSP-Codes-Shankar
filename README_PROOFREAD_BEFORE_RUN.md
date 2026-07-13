# Proofreading order — BBC & BNP campaigns (before launch)

> For Shankar's own line-by-line verification, independent of any AI checks.
> Read in this order: each step's correctness is assumed by the next.
> Written 2026-07-02. Companion docs: `src/BBC/docs-for-claude-code/README.md`,
> `src/BNP/README_RESUME.md`, `skills/ssp-bbc-expert/SKILL.md`.

## 0. Conventions to hold in your head while reading

- **Empty-start everywhere in the campaign**: BBC, LSS, CATZ-F4, repo-SSPMF's
  `obj_ktns`, and `compute_ktns` all count ALL insertions including the first
  job's load. SSPMF's *native* `Z_M` is free-initial; only its `obj_ktns` is
  comparable. Identity: `empty_start = free_initial + min(b, |U|)`.
- **Compare solvers on `obj_ktns`** (re-evaluated from the returned sequence),
  never on raw `obj`.
- plans-genai theory (gap, 4/3, K*−2) is **free-initial**; gaps are
  convention-invariant, **ratios are not** — convert before comparing.

## 1. Common core (everything depends on this)

1. `src/SSP/utils.py` — `load_ssp_instance` (J/T/C header, T×J matrix,
   A[t,j] orientation) and `compute_ktns` (evict furthest-next-use; never evict
   a tool required now; cost counts insertions from empty). This function is
   the campaign's ground truth via `obj_ktns`.

## 2. BBC chain (read top-down)

2. `src/BBC/bbc_common.py` — `BBCSolverMixin`: sequence extraction, subtour
   detection, DSP solvers. Note the mixin versions are **depot-unaware**; the
   CPLEX class overrides them.
3. `src/BBC/branch_and_benders_cut_cplex.py` — the solver. Check, in order:
   - Master: Hamiltonian **path via depot** `d = n_jobs`; degree constraints
     include depot; initial VI `θ ≥ Σ w_ij x_ij + Σ_j |T_j|·x_{d,j}`
     (depot→j arcs carry `|T_j|` — empty-start).
   - DSP: ν, η **FREE** (lb = −∞); RHS of the z-constraints = 1 for ALL t;
     depot-arc dual `λ̄d_jt` present in BOTH dual constraint families.
   - Benders cut: **depot-arc duals included** (the 2026-06-10 fix — this is
     the single most important thing to re-verify by eye).
   - Callback: candidate → subtour check (valid tour has `n_jobs+1` nodes) →
     SEC rejection, else DSP → Benders rejection; relaxation → user cuts only
     when `frac_cuts`. SECs are **lazy at integer candidates only** (connected
     components; no max-flow — exact by design; fractional SEC separation à la
     Ghiani would be a speedup, not a correctness need).
4. Baselines (formulation-faithful; solved by CPLEX with lazy SECs, not by the
   papers' 2004-era machinery — a deliberate, defensible choice):
   - `lss_formulation.py` — objective over T_i; (15) switch definition over
     ALL t (the LSS bug fix); (17) base constraint; VIs (23)(24)(25) faithful,
     `use_valid_ineq=True`.
   - `sspmf_formulation.py` — faithful (1)–(16); `use_constraint_21=False`
     (the invalid carry-prohibition stays OFF); native obj is free-initial.
   - `catanzaro_formulation.py` — F4, eqs 13a–13i; header documents why F4
     (LP(F4)=LP(F3), F5's LP doesn't even compute at J=40). Check (13e)
     carried-in ≥ carried-out and (13f) capacity `(C−|T_j|)x_ij`.
5. `src/BBC/benchmark_config.py` — 11 configs (8 BBC ablation + LSS + SSPMF +
   CATZ-F4); primary sets 3600 s; secondary excludes SSPMF only. Check the
   grid matches what you want to publish.
6. `src/BBC/benchmark_runner.py` — `obj_ktns` from returned sequence;
   easiest-first ordering; per-config early stop (`MAX_CONSECUTIVE_TIMEOUTS`);
   **resume skips rows already in the CSV** — confirm `raw_results.csv` holds
   no pre-2026-06-10 rows (stale-cut era) before submitting.
7. `src/BBC/cluster/` — `SLURM_RUNBOOK.md` end to end; `run_campaign.sbatch`
   (array 0-10 = 11 configs; `CPLEX_THREADS=$SLURM_CPUS_PER_TASK`, i.e. 4 —
   thread-pinned, not single-threaded); `probe.sh`, `merge_results.sh`.

## 3. Mandated pre-flight (do not skip)

8. On the CPLEX machine, inside the env
   (`source ~/miniforge3/etc/profile.d/conda.sh && conda activate ssp_env`):
   `python src/BBC/test_solver.py` — all four solvers
   (BBC both cut modes / LSS / SSPMF / CATZ) vs brute force must agree
   **in-repo**. Status 2026-07-02: first run surfaced an LSS VI(23) depot
   KeyError (fixed in lss_formulation.py) and a convention-naive SSPMF
   comparison in the harness (fixed in test_solver.py; SSPMF itself was
   correct). Post-fix battery is green in-sandbox; expect **exit code 0** on
   your machine — exit 2 means solvers were skipped, not passed.
9. Small pilot via `probe.sh` (one easy Catanzaro instance, one config) —
   check the CSV row: status, `obj == obj_ktns` for empty-start solvers,
   `root_lp_bound` populated, time sane.

## 4. BNP chain (read top-down)

10. Theory first: `plans-genai/10b_position_branch_and_price.tex` §3–4, then
    `src/BNP/README_RESUME.md` (the frozen, verified pricing formulas — the
    corrected `rho[t,p]` signs are the crux; **do not re-derive**, compare
    code against the frozen block).
11. P0 evidence: `plans-genai/_verification/verify_{pcf_prime,pricing,ptf_pricing}.py`
    — skim so you know what was checked (IP=Z*, LP values, reduced costs to
    1e-9).
12. `src/BNP/pcf_prime_bp.py` — master rows (P′)(G)(Cov)(W)(T) only, O(n|T|);
    pricer reduced cost == README's `beta/rho` block; robust branching on
    `a_{t,p}`; branching duals enter `rho` additively.
13. `src/BNP/ptf_bp.py` — coupled-pair pricer (McCormick on `x'_t(1−x_t)`);
    ⊥-arcs NOT enumerated (cons/abs rows explicit, (C,⊥) priced by the
    single-set MILP); both enumerate and MILP paths.
14. `src/BNP/instance_loader.py` — token-based parse of all four families
    (Crama 3-line header, Otiai huge rows); `iter_instances` filters.
15. `src/BNP/bnp_benchmark_config.py` + `bnp_benchmark_runner.py` — grid
    {PCFp, PTF}; `MAX_JOBS=25` cap (+|V| backstop); `obj_ktns` with the
    built-in convention self-check (`obj_ktns == obj + min(b,|U|)`);
    `root_lp_bound` may be None where SCIP's root value is unreliable
    (known `getDualboundRoot` issue — clamped, documented).
16. `src/BNP/cluster/run_bnp.sbatch` + `README_BNP_CLUSTER.md` — shared
    `ssp_env` conda env (pyscipopt; no CPLEX license needed for BNP), array
    shards, merge script.

## 5. Launch order

17. BBC: submit from frontalhpc2025 per `SLURM_RUNBOOK.md`:
    `sbatch src/BBC/cluster/run_campaign.sbatch` (primary, array 0-10) and
    `SETS=secondary sbatch --array=0-9 src/BBC/cluster/run_campaign.sbatch`.
    Safe to submit both at once (2026-07-02: per-config CSVs are now also
    per-set, `raw_<CFG>_<SETS>.csv`, so no concurrent writers). Watch the
    first array task's log, then leave it.
18. BNP: `sbatch src/BNP/cluster/run_bnp.sbatch` (independent harness; results
    merge offline; comparison to BBC happens at analysis level on `obj_ktns`).
19. After both: `merge_results.sh`, then `src/BBC/analysis/` for tables/plots;
    convert conventions before quoting any ratio against the theory.
