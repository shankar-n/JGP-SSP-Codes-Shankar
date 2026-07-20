# CLAUDE.md — JGP-SSP-Codes-Shankar

> Read this file first on every session. Do not open any file not listed here unless the user explicitly asks. Load the relevant skill from `skills/` for detailed technical context before doing specialised work.

---

## Current Focus (2026-07-17) — final report + presentation

Active objective: the project report **`report/JGP-SSP_report.tex`** (RENAMED from
mid_internship_report; it is the LIVING FINAL REPORT) and the Beamer deck
**`report/JGP-SSP_slides.tex`** (renamed from JGP-SSP_midterm_slides). Facts:
- **Draft switch**: comment-package environments `gaptheory`/`gapstub` (preamble
  block "DRAFT SWITCH") toggle §3 in/out; §3 is under Shankar's line-by-line
  verification and is EXCLUDED from circulated drafts. Full 29pp / circulation 20pp.
- Campaigns are DONE; §5 was rewritten 2026-07-17 from recomputed CSV numbers —
  see the 2026-07-17 block of `plans-genai/_verification/VERIFIED_FACTS.md`
  (387/806 tight = 48.0%; LSS 667/677 secondary; PCFp 94/319, PTF 72/291 at
  n≤25; 30/30 Benders timeouts held the optimum; wall = n=15 at T≈20).
- PENDING on cluster merge (corrected-master BBC re-run, jobs 14616/14624):
  refresh tab:solves BBC rows + Benders diagnosis, THEN rebuild the deck —
  **deck numbers are stale until that rebuild; do not present it before**.
- Repo is PUBLIC (github.com/shankar-n/JGP-SSP-Codes-Shankar): `src/` and all
  readmes are scrubbed of AI mentions (2026-07-17) — keep them that way; the
  private layer (plans-genai, skills, CLAUDE.md, runbooks) is gitignored for
  future adds but Shankar chose NOT to untrack existing files.
- Wagler polyhedral sessions: data in `plans-genai/wagler_prep_data.md`.
- `plans-genai/08_branch_and_benders.tex` renamed to `14_branch_and_benders.tex`
  (numbering collision with 08_research_notes.md).

Original campaign critical path (completed): SLURM runbook → repo cleanup → stale
docs → baseline decision → `test_solver.py` pilot → campaign → analysis.

**Cluster how-to (don't lose this):** `src/BBC/cluster/SLURM_RUNBOOK.md` — step-by-step SLURM + CPLEX setup; with `run_campaign.sbatch` (job array, one task per config), `probe.sh`, `merge_results.sh`. Submit from **frontalhpc2025**. Python env (2026-07-02): ONE shared conda env **`ssp_env`** (Miniforge in `$HOME`, per https://hpc.isima.fr/doku.php?id=python) serves BOTH the BBC and BNP campaigns — numpy + CPLEX Python API (pip-installed from the cluster's local CPLEX Studio; the `cplex` CLI on PATH does not provide it) + pyscipopt. Activate everywhere with `source ~/miniforge3/etc/profile.d/conda.sh && conda activate ssp_env` (never `conda init`).

Verified 2026-06-15: BBC optima correct on small instances (brute-force + SSPMF agree, both cut families; DSP obj == `compute_ktns`); `lp_reuse` and `frac_cuts` give correct optima; **LSS switch-count bug FIXED** (objective now counts insertions of ALL tools, not just required ones — verified 7/7 vs brute via standalone; re-run `test_solver.py` on full CPLEX to confirm in-repo). `benchmark_runner` now runs **easiest-first** with **per-config early-stop** after `MAX_CONSECUTIVE_TIMEOUTS` consecutive non-optimal results.

Baselines (all CPLEX, all **thread-pinned** via the `CPLEX_THREADS` env var for reproducible/comparable timings). Cross-solver dry run via the rewritten `test_solver.py` (BBC/LSS/SSPMF/CATZ vs brute), 2026-06-15:
- **BBC** ✓, **Catanzaro-F4** ✓ (`catanzaro_formulation.py`, Catanzaro 2015 F4 — F5 tighter-LP but doesn't scale), **LSS** ✓ (`lss_formulation.py`, Laporte 2004 (10)-(20) faithful: objective over T_i, switch-def (15) over ALL t [the real bug fix], (17) as base constraint, + faithfully-transcribed VIs (23)-(25), `use_valid_ineq=True`), **SSPMF** ✓ (`sspmf_formulation.py`, da Silva 2024 multicommodity flow (1)-(16) faithful; native objective `Z_M`). Each recovers the optimal SEQUENCE == brute on ring + random instances (verified standalone; BBC/Catanzaro also confirmed in-repo).
- **Convention (IMPORTANT)**: native objectives differ — BBC/LSS/Catanzaro/`compute_ktns` are EMPTY-START; SSPMF's `Z_M` is FREE-INITIAL (= empty-start − initial magazine load; LP bound M−C). The campaign now records **`obj_ktns` = `compute_ktns(returned sequence)`** (empty-start) per solver; **compare solvers on `obj_ktns`, not raw `obj`**.
- Earlier mistakes corrected this session: my over-edits to LSS (objective rewrite, VI/(17) drop) were reverted to the faithful Laporte model; SSPMF was NOT actually buggy in da Silva's math — the repo's empty-start-forcing modification was, so it's been replaced by the faithful (1)-(16).
- NB: this sandbox's Linux mount truncates just-edited files, so LSS/SSPMF were verified via standalone scripts mirroring the repo. **Run `test_solver.py` on the CPLEX machine to confirm all 4 vs brute in-repo before the campaign.**

Grid is 11 configs (8 BBC ablation + LSS + SSPMF + CATZ-F4); sbatch array `0-10`. Legacy `benchmark.py`, the pre-fix CSV, and `_archived/`/`old/`/`plans-genai/archive/` were deleted (recoverable via git).

**PARKED until the BBC paper is done** — these are separate future papers / where-SOTA-lacks directions, NOT on the BBC critical path: gap theory (`05_jgp_ssp_gap_analysis`), grouping selection (`06`), collapse variants (`07`), position formulations Part X (`10`), the ring `K>K*` experiment, and ML / CG-seed ideas. Concrete to-do for each is in `plans-genai/12_work_plan.md` (§A,B,C,E), `11_research_directions.md`, and `09_open_problems.tex`. Do not pick these up unless explicitly asked.

**ACTIVE side-thread (2026-06-22) — B&P for position formulations (NOT parked):** branch-and-price extension of PCF′/PTF is in progress. Theory: `plans-genai/10b_position_branch_and_price.tex`. P0 done — compact models + pricing formulas verified against solver ground truth (PCF′ `eq:rho` had a sign bug, now fixed; PTF correct). Live status, verified formulas, and the resume point: **`src/BNP/README_RESUME.md`** (read this first to continue). B&P code lives in `src/BNP/` (parallel to `src/BBC/`); common code is reused from `src/SSP/` as-is. Verify scripts: `plans-genai/_verification/verify_{pcf_prime,pricing,ptf_pricing}.py`. Next step: P1 (PySCIPOpt PCF′ pricer).

---

## Skills — Load Before Specialised Work

| Situation                                                      | Load skill                       |
| -------------------------------------------------------------- | -------------------------------- |
| Any question about papers, SOTA, citations, related work       | `skills/ssp-literature/SKILL.md` |
| Editing `src/BBC/`, implementing Benders cuts, CPLEX callbacks | `skills/ssp-bbc-expert/SKILL.md` |

---

## Research Problem

**SSP (Job Sequencing and Tool Switching Problem)**: CNC machine, magazine capacity `b`, `n` jobs, `T` tools. Each job `j` requires `T_j ⊆ T`. Find a job sequence minimising total tool switches. For a fixed sequence, KTNS (Tang & Denardo 1988) is the optimal `O(n·|T|)` loading strategy. Joint optimisation is NP-hard.

**JGP (Job Grouping Problem)**: Partition jobs into minimum `K*` batches such that each batch's tool union fits in `b`. Solved exactly via the ARF MILP (Catanzaro 2015).

**JGP+GSP Heuristic** (2-phase): (1) solve JGP → K\* batches; (2) solve GSP (TSP on batches) to order them; (3) flatten and evaluate with KTNS.

**Research question**: How large can `gap = JGP+GSP cost − SSP optimum` be? When is the gap zero (collapse)?

**Verified results (May 2026)**:

- 6-job ring counterexample: gap = 1 (PORTA-verified)
- Unbounded gap: `g` disjoint ring copies → gap = `g`, `K* = 3g`

**Open problems**:

1. Tight gap bound for fixed `K*` and `b` — **major update 2026-07-02**: gap ≤ 1 for `K*=3, b≤4` is now a THEOREM; the general conjecture gap ≤ K\*−2 (OP11) is **REFUTED** (b=5, K\*=3, gap=2 witness); the K*=3 quantitative law `gap ≤ max(0, min(q,⌊(2b−q)/3⌋)−R)` is proved and tight at every known extremum; open: is it the exact worst case, and K\*≥4. See `plans-genai/_verification/VERIFIED_FACTS.md` (2026-07-02 block) + 05 §K*=3.
2. Grouping selection: do sub-optimal groupings (`K > K*`) ever beat the JGP+GSP heuristic?
3. MTZ vs. GSECs: LP relaxation bound comparison
4. Fractional Benders cuts for BBC
5. Can we hypothesize something based on the ration of magazine setup time versus tool setup time to study how the problem varies the SSP to JGP and how it might affect in real life scenarios.

6. **Research is open-ended**: new results, flaws in existing work, novel formulations, problem variants, or a new SOTA proposal may all be in scope. Revisit this file when something significant changes.

---

## Critical Files (★ = read on demand, not by default)

### src/SSP/

| File                            | Purpose                                                                                                                                                  |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `utils.py` ★                    | `load_ssp_instance`, `compute_ktns`, `compute_switch_cost`                                                                                               |
| `SCIP_formulation_solvers.py` ★ | `solve_jgp_arf` — JGP via ARF MILP (PySCIP)                                                                                                              |
| `heuristics.py` ★               | `warmstart_from_jgp`, `greedy_ffd`, `adjacent_swap_ls`, `nearest_neighbor`                                                                               |
| `main-notebook.py` ★            | **Primary prototyping environment** — all new code (including BBC) is first written and tested here as Marimo cells before being moved to proper modules |
| `solution_validators.py`        | SSP solution validation                                                                                                                                  |
| `ssp_instance_generator.py`     | Random instance generation                                                                                                                               |
| `porta.py`                      | PORTA polyhedral tool wrapper                                                                                                                            |
| `concorde_util.py`              | Concorde TSP solver wrapper                                                                                                                              |
| `viz.py`                        | Magazine state visualisation                                                                                                                             |
| `generate_ssp_feasible.go/.exe` | Golang BFS for integral JGP enumeration (faster than PORTA for >8 jobs)                                                                                  |
| `jgp_bfs_analysis.csv`          | BFS results                                                                                                                                              |
| `ssp_feasible_solutions.csv`    | Feasible SSP solution catalogue                                                                                                                          |

### src/BBC/

BBC is the exact solver research. Code is also prototyped in `src/SSP/main-notebook.py` before being moved here.

| File                                | Purpose                                                               |
| ----------------------------------- | --------------------------------------------------------------------- |
| `branch_and_benders_cut.py` ★       | Public API dispatcher (CPLEX only)                                    |
| `branch_and_benders_cut_cplex.py` ★ | Full CPLEX implementation — edit this                                 |
| `bbc_common.py` ★                   | `BBCSolverMixin`: subtour detection, sequence extraction, DSP solvers |
| `lss_formulation.py`                | LSS formulation (Laporte 2004) — compact ILP comparison               |
| `sspmf_formulation.py`              | SSPMF formulation (da Silva 2024) — multicommodity flow comparison    |
| `benchmark.py`, `test_solver.py`    | Legacy runner; cross-solver agreement tests                           |
| `benchmark_config.py`, `benchmark_runner.py` | Campaign config (single source of truth) + resumable runner   |
| `precompute_jgp_gsp.py`, `analysis/` | JGP+GSP costs per instance; plots/tables generators                  |
| `docs-internal/`             | Design documents — load `ssp-bbc-expert` skill for details            |
| `_archived/`                        | Deprecated Gurobi/SCIP backends — do not touch                        |

### plans-genai/ (AI-generated working scratch — NOT ground truth)

**Important**: These are AI-assisted drafts written to explore research questions. They are NOT verified results, should NOT be cited or treated as authoritative by Claude, and may contain errors. They exist so Shankar can iterate on ideas with AI assistance. Read them only if explicitly asked, and always flag uncertainty.

| File                            | What it explores                                                            |
| ------------------------------- | --------------------------------------------------------------------------- |
| `05_jgp_ssp_gap_analysis.tex` ★ | Gap analysis drafts, ring counterexample writeup, unbounded gap argument    |
| `06_grouping_selection.tex` ★   | MWHP criterion exploration, sub-optimal JGP ideas                           |
| `07_collapse_variants.tex` ★    | Collapse condition ideas (S_stop, ρ parameterisation)                       |
| `08_research_notes.md` ★        | Advisor Q&A notes, open problems, implementation notes — most grounded file |
| `04_mtz_formulation.tex`        | MTZ approach exploration                                                    |
| `01_foundations.tex`            | Problem foundations writeup                                                 |
| `02_noncompact_formulation.tex` | Non-compact ILP exploration                                                 |
| `03_gtsp_equivalence.tex`       | SSP ↔ GTSP equivalence exploration                                          |
| `09_open_problems.tex` ★        | Consolidated OP index (OP1–11; updated 2026-06-10)                          |
| `10_position_formulations.tex` ★ | Part X: standalone PCF/PTF formulations with fixed O(n·|T|) rows (2026-06-10) |
| `_verification/` ★              | Verification scripts (`ssp_verify.py` + per-document `verify_*.py`); `VERIFIED_FACTS.md` |
| `references.bib`                | Bibliography (use for valid citation keys)                                  |

---

## Instance Format

```
J  T  C
<T × J binary matrix>   (row = tool, col = job; A[t,j]=1 iff job j needs tool t)
```

`load_ssp_instance(path)` → `(J, T, C, A, T_j)`

Benchmark sets:

- `data/From_Felipe/data/Catanzaro/Tabela1C/` — A/B/C/D instances (main benchmarks)
- `data/From_Felipe/data/Crama/`, `Laporte/`, `Otiai/` — secondary benchmarks
- `data/Shankar/` — custom instances (6-job ring etc.)

---

## Solver Stack

| Solver                                           | Used for                 | Status           |
| ------------------------------------------------ | ------------------------ | ---------------- |
| IBM CPLEX (`cplex`)                              | BBC master + DSP         | Primary          |
| PySCIP (`pyscipopt`)                             | JGP ARF MILP             | Required for JGP |
| docplex                                          | DSP fresh model fallback | Optional         |
| Gurobi (`gurobipy`)                              | DSP fallback             | Optional         |
| Concorde                                         | TSP oracle               | Optional         |
| PORTA (`tools/porta-1.4.1/win32/bin/xporta.exe`) | Polytope enumeration     | Windows only     |
| LRS (`tools/lrs/lrs.exe`)                        | Vertex enumeration       | Windows only     |

---

## Do NOT Read (Unless Explicitly Asked)

- `tools/porta-1.4.1/src/` and `tools/porta-1.4.1/win32/` — build artefacts
- `src/BBC/_archived/` — deprecated backends
- `plans-genai/archive/` — old drafts
- `src/SSP/old/` — old generators
- `data/From_Felipe/` individual `.txt` files — hundreds of raw instance files
- `references/Useless/` — papers not relevant to current work

---

## Current Status (June 2026)

- BBC CPLEX: complete, subtour detection fixed, FREE bounds on ν/η fixed
- Gap analysis: ring counterexample + unbounded gap proved
- Golang BFS enumerator: working
- **In progress**: exact extremal gap law (gap ≤ K\*−2 REFUTED 2026-07-02; K*=3 quantitative bounds proved & tight — see VERIFIED_FACTS), fractional Benders cuts (implemented, untested), MTZ vs. GSEC LP comparison, experiments at b=4, |T|=8, |J|=8
- **Verification campaign (2026-06-10, Claude-Fable)**: plans-genai 01–10 all verified/corrected (changes flagged `%% TODO-VERIFY`); BBC code audited — **Benders-cut depot-dual bug FIXED: re-run all pre-fix benchmarks and archive old `raw_results.csv` first (the runner resumes and would skip stale rows)**; conventions unified (repo exact solvers + `compute_ktns` are all EMPTY-START = free-initial + min(b,|U|); GTSP reference is free-initial); cluster-MTZ settled NOT exact, per-configuration MTZ proved exact; Part X (PCF/PTF) added — PTF LP can exceed |U|−b
