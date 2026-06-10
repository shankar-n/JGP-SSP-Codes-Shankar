# Research Notes: SSP / JGP — Directions, Implementation, and Open Questions

These notes summarise advisor discussions, implementation progress, and
research directions not yet formalised in the main documents. They are
working notes, not polished results.

---

## Current Research Status (as of May 2026)

### Completed / Verified
- Literature review: SSP, JGP, GTSP, compact and non-compact ILP formulations.
  Key works: Tang & Denardo (1988), Crama et al. (1994), Laporte et al. (2004),
  Catanzaro et al. (2015). Also reviewed: Bernardo Moreira's thesis (metaheuristic
  for SSP) and Felipe Otiai's thesis (Branch-and-Price for TSIP/JGP).
- **6-job ring counterexample**: verified by PORTA enumeration. JGP gives 2 optimal
  solutions; best JGP+GSP cost = 4 switches. SSP optimum = 3. Gap = 1.
- **Unbounded gap construction**: by copy-pasting $g$ disjoint ring instances,
  gap = $g$ is achievable with $K^* = 3g$ groups. See `05_jgp_ssp_gap_analysis.tex`.
- Implemented a **Golang program** for faster integral JGP solution enumeration
  (PORTA was too slow for instances beyond ~8 jobs).
- Modified **Felipe's instance generation code** to produce smaller instances with
  greater tool overlap (motivated by parameter regime $b \approx |T|/2$ and
  $|T| \times |J| \le 60$).

### In Progress
- **Approximation ratio of JGP+GSP**: conjectured $H/Z^*_\mathrm{SSP} \leq 4/3$ for
  all b=3 instances. Ring (K*=3) achieves ratio exactly 4/3 (lower bound proved).
  Copy-paste construction gives ratio 7/6 < 4/3 for large K*. The intermediate bound
  $\sum R_k \leq H/4$ used in an earlier draft is **FALSE** in general (counterexample
  exists: T^(1)={a,b,c}, T^(2)={a,b,d}, T^(3)={c,d,e} gives ΣR_k=1 > H/4=0.75).
  The 4/3 conjecture remains open. See Section 5 of `05_jgp_ssp_gap_analysis.tex`.
- **Branch-and-Benders cut** approach for SSP (compact formulation): implementation
  almost complete. Lazy cuts added on integer solutions using KTNS. Future: user
  cuts at fractional solutions.
- **MTZ-style constraints** replacing GSECs in the non-compact formulation: see
  `04_mtz_formulation.tex`. Long-term goal: column generation over MTZ-constrained
  master.
- **Tool Setup Time variant** ($S_\mathrm{stop}$ and $\rho$ parameterisation):
  theoretical results proved in `07_collapse_variants.tex`. Implementation and
  computational experiments planned.

---

## Advisor Directions and Open Questions

### Q1: Gap Analysis (from advisor discussions)
- Construct worst-case examples after **fixing $K^*$ and $b$**.
- Study instances where the gap is exactly attained to derive good lower bounds
  on the gap (not just the SSP cost).
- Prove a **tight bound** for fixed $K^*$, not just for growing $K^*$.
- The loose existing bound is: $H \le b \cdot (K^* - 1)$ (each of $K^*-1$
  transitions costs at most $b$). Tightening this for the JGP+GSP heuristic
  specifically (not the trivial sequential schedule) is the goal.

### Q2: Grouping Selection
- Enumerate **all integral JGP solutions** (done via Golang program).
- Select groupings that maximise tool overlap at boundaries (MWHP criterion,
  see `06_grouping_selection.tex`).
- Explore **sub-optimal JGP solutions** ($K > K^*$): conjecture that extra slack
  per group can reduce total SSP cost even with more configuration changes.
- Pending: does any sub-optimal grouping of the 6-job ring achieve cost < 4
  (matching the SSP optimum of 3)?

### Q3: Collapse Conditions
- Identify cost function variants that collapse SSP to JGP.
- Magazine setup time variant is the most natural — proved in `07_collapse_variants.tex`.
- The necessity question for conditions (C1)+(C2)+(C3) remains open.
- **GENIUS heuristic**: mentioned by advisors as a potential approach for routing
  configurations after collapse. This is a trajectory heuristic for TSP/ATSP;
  applicability to the GSP context needs investigation.

### Q4: Benders Decomposition
- **Master Problem (MP)**: a TSP/ATSP that decides the sequence of configuration
  changes, with a surrogate variable $\theta$ for the tool-switching cost.
- **Subproblem (SP)**: given the sequence from MP, compute the exact tool-switching
  cost via KTNS (polynomial). The dual subproblem generates Benders cuts.
- Key advantage: the subproblem is **polynomial** (KTNS), so exact cuts can always
  be computed. This avoids the NP-hard pricing problem of column generation.
- Reference: advisor mentioned a master's thesis exploiting Benders for a related
  problem (section 2.2 on Benders). **VERIFY which thesis this refers to.**
- Also study: Laporte et al. (2004) "new model" (Constraints 11-13, 18 define TSP;
  remaining constraints would be relaxed in Benders).

---

---

## Research Results (June 2026, this session)

The following results have been derived and written into the main LaTeX documents.
Check those files for full statements and proofs.

1. **Approximation ratio conjecture** (`05_jgp_ssp_gap_analysis.tex`, Section 5):
   Lower bound H/Z*_SSP ≥ 4/3 proved (6-ring witness). Upper bound H/Z*_SSP ≤ 4/3
   is a **conjecture** for all b=3 instances. The intermediate bound ΣR_k ≤ H/4
   was in an earlier draft but is false (counterexample found).

2. **Conflict graph independence theorem** (`05_jgp_ssp_gap_analysis.tex`, Section 6):
   Proved that LP tightness of JGP and the SSP-JGP gap are independent:
   - 6-ring: conflict graph 2K_3 (perfect, χ=χ_f=3), gap=1.
   - 5-ring: conflict graph C_5 (imperfect, χ=3>χ_f=5/2), gap=0.
   References: Chudnovsky et al. (2006) for SPGT, Cornuejols (2001) for clutter theory,
   Crama et al. (1994) for JGP=chromatic number equivalence.

3. **MTZ exchange argument partial results** (`04_mtz_formulation.tex`):
   Proved that cluster-simple optimal solutions exist for disjoint-tool instances and
   for the 6-job ring. General case remains open. The aggregate MTZ formulation is
   correct for these classes.

4. **TD-SSP R(ρ) analysis** (`07_collapse_variants.tex`): Approximation ratio R(ρ)
   decreases monotonically from ≤4/3 at ρ=0 to 1 as ρ→∞. Ring threshold ρ_c=1.
   Manufacturing parameters ρ≈3–60 (Privault & Finke 1995) all exceed ρ_c=1,
   so JGP+GSP is exactly optimal for the TD objective on ring-like instances.

---

## References to Verify

The following references were mentioned in earlier AI-generated notes but do not
appear in `references.bib` and must be verified before citation:

| Reference | Claim | Verification Status |
|---|---|---|
| daSilva (2021) | CG for SSP with set-covering master and bin-packing pricing | **UNVERIFIED** — ask Prof. Colares |
| Ghiani, Laporte, Semet (2007) | SSP = min-cost Hamiltonian cycle on configurations | **UNVERIFIED** — possibly Colares2026Exact |
| Burger et al. (2015) | Multiple optimal JGP solutions for Color Print Scheduling | **UNVERIFIED** — possibly a valid paper, not in bib |
| Salonen et al. (2006) | JGP+GSP performs "remarkably well" for large instances | **UNVERIFIED** |

Do not cite any of these until verified.

---

## Notes on Specific Papers

### Laporte, Salazar-González, Semet (2004)
- Contains compact TSP-based formulation for SSP.
- Constraints (11)-(13), (18) define the TSP skeleton.
- A Benders decomposition would relax the remaining constraints (tool coverage,
  magazine capacity) and add them as cuts.
- Study which constraints are in the master vs. subproblem.

### Catanzaro, Gouveia, Labbé (2015)
- Formulation 5 (linear ordering + overlap constraints) gives the tightest LP bounds
  among compact models. Study the 1-arc and cut inequalities they add.

### Privault & Finke (1995, 2000)
- Define the TD-SSP (non-uniform switch costs).
- Prove the tooling problem is polynomial via min-cost flow on interval graphs
  (total unimodularity).
- Important for the collapse variant: when $c_t$ are non-uniform but $S_\mathrm{stop}$
  dominates, the TD-SSP collapses to JGP (`07_collapse_variants.tex`, Theorem 4.2).

### Pop et al. (2024)
- Comprehensive GTSP review. Useful for GTSP solution methods applicable to GSP.
- Noon-Bean transformation, LKH-3 extensions, exact branch-and-cut for GTSP.

### Mecler, Subramanian, Vidal (2021)
- Hybrid genetic search for SSP. Provides SOTA heuristic benchmark.
- Uses JGP warm-start seeding for the initial population.

---

## Implementation Notes

### Branch-and-Benders
- Lazy callback: after LP relaxation produces an integer solution, run KTNS to
  compute the exact switching cost. If the surrogate $\theta$ < KTNS cost, add
  a Benders optimality cut: $\theta \ge \text{KTNS}(\sigma)$ for the current sequence $\sigma$.
- Future: user cuts at fractional solutions using the LP dual of the KTNS subproblem.

### MTZ Formulation (see `04_mtz_formulation.tex`)
- MTZ constraints eliminate subtours in polynomial number of constraints
  (vs. exponential GSECs).
- Test: does the MTZ formulation provide a tighter LP bound than GSECs for the
  non-compact SSP? Computational experiments on small instances needed.

### Instance Generation
- Generate instances with $|T| \times |J| \le 60$ and $b \approx |T|/2$ for
  polyhedral experiments.
- Felipe's generator (modified): controls $b$, $|T|$, $|J|$, and the density of
  the job-tool incidence matrix.
- Key regime: $b = 3$, $|T| = 6$, $|J| = 6$ (6-job ring); scale to $b=4$, $|T|=8$,
  $|J|=8$ for next experiments.
