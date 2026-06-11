# CLAUDE.md — JGP-SSP-Codes-Shankar

> Read this file first on every session. Do not open any file not listed here unless the user explicitly asks. Load the relevant skill from `skills/` for detailed technical context before doing specialised work.

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

1. Tight gap bound for fixed `K*` and `b` (conjecture: gap ≤ 1 when `K*=3, b=3`)
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
| `docs-for-claude-code/`             | Design documents — load `ssp-bbc-expert` skill for details            |
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
- **In progress**: tight gap bound (now generalised: gap ≤ K\*−2 conjecture, OP11), fractional Benders cuts (implemented, untested), MTZ vs. GSEC LP comparison, experiments at b=4, |T|=8, |J|=8
- **Verification campaign (2026-06-10, Claude-Fable)**: plans-genai 01–10 all verified/corrected (changes flagged `%% TODO-VERIFY`); BBC code audited — **Benders-cut depot-dual bug FIXED: re-run all pre-fix benchmarks and archive old `raw_results.csv` first (the runner resumes and would skip stale rows)**; conventions unified (repo exact solvers + `compute_ktns` are all EMPTY-START = free-initial + min(b,|U|); GTSP reference is free-initial); cluster-MTZ settled NOT exact, per-configuration MTZ proved exact; Part X (PCF/PTF) added — PTF LP can exceed |U|−b
