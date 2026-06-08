# BBC Expert Skill — Branch-and-Benders-Cut for SSP

**Load this when**: editing any file in `src/BBC/`, implementing Benders cuts, debugging CPLEX callbacks, adding fractional cuts, or designing new subproblem variants.

---

## Design Documents — Read Before Structural Changes

These are in `src/BBC/docs-for-claude-code/`. Read the relevant one before touching architecture.

| File | When to Read | What It Contains |
|---|---|---|
| `idea.md` | Before any structural change to BBC | The original Benders decomposition blueprint: MP/DSP/cuts derived from scratch, KTNS vs LP dual discussion, lower bound strategy, solver comparison. The authoritative design intent. |
| `plan-from-gemma.md` | Before re-implementing the callback | Step-by-step implementation plan. **Caution**: written before depot node fix — says "no KTNS" (LP dual only) and uses Gurobi as primary. Both are outdated. CPLEX is primary; the LP DSP is still used as written. |
| `README.md` | For module-level overview or benchmark usage | Architecture summary, deviations from papers, LSS and SSPMF formulation summaries, benchmark CLI, instance format. Most up-to-date module-level doc. |
| `CPLEX-python-examples/admipex8.py` | When debugging the generic callback | Canonical IBM example for generic callback with lazy constraints — our callback is modelled on this. |
| `CPLEX-python-examples/bendersatsp2.py` | When implementing worker LP reuse or fractional cuts | Canonical IBM example for LP reuse + fractional user cuts + thread safety. Target pattern for full BBC performance. |

**Prototyping note**: new BBC features are typically first written in `src/SSP/main-notebook.py` as Marimo cells, then moved here once they work.

---

## Key Architectural Decision: Depot Node

The master problem models a **Hamiltonian path** via a depot node `d = n_jobs` (with empty tool set). This was **not in the original plan** (plan-from-gemma.md models a cycle on n_jobs nodes). The fix was required because the cycle formulation caused the DSP to compute cycle cost rather than path cost, producing incorrect Benders cuts.

- Arc set: all `(i,j)` over `range(n_jobs) + [depot]`
- Degree constraints include depot
- `_find_subtours_from_sol` in `branch_and_benders_cut_cplex.py` checks for tours of length `n_jobs + 1` (not `n_jobs`)
- `_get_sequence_from_sol` starts traversal from depot

The `BBCSolverMixin` versions of these methods do NOT include depot — they are overridden in `BranchAndBendersCutSSP_CPLEX`.

---

## Master Problem (MP)

| Variable | Index | Type | Objective |
|---|---|---|---|
| θ | col 0 (`theta_idx`) | continuous ≥ 0 | 1.0 |
| x[i,j] | cols 1… (`x_idx_map[(i,j)]`) | binary | 0.0 |

**Built-in constraints** (`build_master_problem`):
1. Out-degree = 1 per node (all nodes incl. depot)
2. In-degree = 1 per node
3. `θ - Σ w_ij·x_ij ≥ 0` where `w_ij = max(0, |T_i ∪ T_j| − c)` (depot arcs: w=0)

SECs and Benders cuts are added dynamically via callback.

---

## Dual Subproblem (DSP) — Full Formulation

**Variables** (all ≥ 0 or FREE as noted):

| Var | Bound | Objective coeff |
|---|---|---|
| λ_ijt (i≠j, t∈T) | ≥ 0 | (x̄_ij − 1) |
| μ_j | ≥ 0 | −c |
| ν_jt | **FREE** | 1 if t∈T_j else 0 |
| η_jt | **FREE** | 0 |

**ν and η must be FREE (lb = −∞)**. A prior bug set lb=0; this is fixed.

**Objective** (maximise):
```
Σ_{i,j,t} (x̄_ij − 1)·λ_ijt  −  Σ_j c·μ_j  +  Σ_{j, t∈T_j} ν_jt
```

**Constraints for y_jt ≥ 0**:
```
−μ_j  −  Σ_{i≠j} λ_ijt  +  Σ_{k≠j} λ_jkt  +  [ν_jt if t∈T_j]  ≤  0
```

**Constraints for z_jt ≥ 0**:
```
Σ_{i≠j} λ_ijt  +  [η_jt if t∉T_j]  ≤  [1 if t∈T_j else 0]
```

---

## Benders Optimality Cut

```
θ  ≥  Σ_{i,j,t} (x_ij − 1)·λ̄_ijt  −  Σ_j c·μ̄_j  +  Σ_{j, t∈T_j} ν̄_jt
```

In CPLEX SparsePair form: `θ − Σ coeff_ij·x_ij ≥ rhs` where:
- `coeff_ij = Σ_t λ̄_ijt`
- `rhs = −Σ_j c·μ̄_j + Σ_{j,t∈T_j} ν̄_jt − Σ_{i,j} coeff_ij`

Built in `_build_benders_cut_sparsepair(duals)`.

---

## Callback Control Flow

```
invoke(context)
  ├── thread_up   → build thread-local DSP (parallel=True)
  ├── thread_down → free thread-local DSP
  ├── candidate   → _handle_candidate()
  │     ├── get x values + θ from context
  │     ├── _find_subtours_from_sol(sol)      ← depot-aware version
  │     │     ├── subtours → reject_candidate(SECs)  return
  │     │     └── no subtours → proceed
  │     ├── _get_sequence_from_sol(sol)        ← starts from depot
  │     ├── _build_x_bar_from_sequence(seq)   ← depot→seq[0]→…→seq[-1]→depot
  │     ├── _solve_dsp_with_xbar(x_bar)
  │     └── dsp_obj > θ+1e-6 → reject_candidate(Benders cut)
  └── relaxation  → _handle_relaxation()   [use_fractional_cuts=True only]
        ├── get fractional x from context
        ├── _solve_dsp_with_xbar(x_bar_frac)
        └── dsp_obj > θ+1e-6 → add_user_cut(Benders cut)
```

Context mask:
```python
mask = Context.id.candidate
if parallel:             mask |= Context.id.thread_up | Context.id.thread_down
if use_fractional_cuts:  mask |= Context.id.relaxation
                         # also set: cpx.parameters.preprocessing.presolve.set(0)
```

---

## DSP Solver Dispatch

```python
_solve_dsp_with_xbar(x_bar, tid)
  ├── worker_lp_reuse=True  → _solve_dsp_reuse()   # update lam obj coeffs only
  └── worker_lp_reuse=False → _solve_dsp_fresh()
        ├── HAS_DOCPLEX → _solve_dsp_docplex()
        ├── HAS_GUROBI  → _solve_dsp_gurobi()
        └── HAS_CPLEX   → build fresh cplex.Cplex DSP model
```

`worker_lp_reuse=True` is the performance target (bendersatsp2 pattern): one model per thread, updated with `dsp.objective.set_linear(updates)` before each re-solve.

---

## Other Formulations in BBC (for comparison)

**LSS (Laporte 2004)** — `lss_formulation.py`
- Variables: x_ij (arc), y_it (tool loaded), z_it (switch indicator), all binary
- Key constraints: TSP degree (11-12), capacity (14), magazine persistence (15), required tools (16), switch definition (17)
- Subtour elimination (13): lazy via callback
- Valid inequalities: pairwise LB (23), unnecessary switches = 0 (25)

**SSPMF (da Silva, Chaves & Yanasse 2024)** — `sspmf_formulation.py`
- Pure MIP — no lazy constraints needed
- Multicommodity flow graph: V = {0,…,N, N+1, N+2} with origin/sink/aux nodes
- LP relaxation bound: LB = M − C (proven tight)
- Symmetry-breaking: most-tool job fixed to first ⌈N/2⌉ positions (Eq. 20)

**Objective post-processing** (important for consistent comparison in main-notebook.py cell 6b):
Both LSS and SSPMF count initial magazine loading from the empty depot in their objective. The GTSP reference solver does not (uses a DUMMY node). For the comparison table, subtract `|T_{seq[0]}|` from reported objective:
```python
adjusted_obj = reported_obj - len(T_j[seq[0]])
```
This is display-only; solver code is untouched.

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Using docplex for master problem | Must use `cplex.Cplex()` directly — docplex has no generic callback support |
| ν/η with lb=0 | Set `lb=-cplex.infinity` (or `dsp.minus_infinity` in docplex) |
| Subtour check using `len(set(sequence)) == n_jobs` | Wrong — use `_find_subtours_from_sol` on binary x-dict |
| `_get_sequence_from_sol` without visited-set guard | Can loop — current implementation has explicit visited set |
| Forgetting depot in subtour check | Valid tour has `n_jobs + 1` nodes; CPLEX version checks this correctly |

---

## Open Tasks

1. **Fractional cuts** (`use_fractional_cuts`): `_handle_relaxation` exists, untested. Study `bendersatsp2.py` LP-reuse + thread-safe pattern before enabling.
2. **Worker LP reuse benchmarking**: `_solve_dsp_reuse` implemented, not yet compared against fresh model on Catanzaro A/B instances.
3. **Combinatorial Benders cuts**: `θ ≥ Z*(π)·(1 − Σ_{(i,j)∈π}(1−x_ij))` — cheaper, weaker. Not implemented.
4. **Triplet lower bounds**: `w_ijk = max(0, |T_i ∪ T_j ∪ T_k| − c)` constraints on consecutive triplets — stronger root bound, larger MP.
