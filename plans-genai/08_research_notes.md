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
- **Tight gap bound for fixed $K^*$ and $b$**: studying small instances computationally.
  Conjecture: gap $\le 1$ when $K^* = 3$, $b = 3$. No proof yet.
  See TODO 1 in `05_jgp_ssp_gap_analysis.tex`.
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
