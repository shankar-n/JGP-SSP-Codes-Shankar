# SSP/JGP Literature Skill — Document Finder & Distilled Knowledge

**Load this when**: any question touches papers, prior work, citations, SOTA, methods from the literature, or "what does X paper say about Y". This skill is both a document locator (telling you which file to `Read`) and a knowledge base (enough distilled content to answer most questions directly or to confirm you need the source).

After consulting this skill, `Read` the cited file for depth. Do not fabricate content not present here.

---

## Quick Reference: Topic → Document

| Topic                                              | File to Read                                                                                | Section                                                 |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| KTNS algorithm, optimality proof, complexity       | `references/ref- tang, denardo.pdf`                                                         | §2 (Tool Replacement Problem), Theorem 1                |
| SSP NP-hardness, formal proof                      | `references/ref - Minimizing the number of tool switches on a flexible machine - Crama.pdf` | §2.1 (Theorems 1 & 2)                                   |
| SSP assumptions and model variants                 | `references/ref - Minimizing the number of tool switches on a flexible machine - Crama.pdf` | §1 (7 assumptions)                                      |
| Compact ILP (LSS) for SSP, exact B&C and B&B       | `references/ref - laporte, salazar.pdf`                                                     | §2.2 (LSS), §3 (algorithms)                             |
| Valid inequalities (23), (24), (25) for SSP LP     | `references/ref - laporte, salazar.pdf`                                                     | §2.2                                                    |
| Why Tang-Denardo LP relaxation = 0                 | `references/ref - laporte, salazar.pdf`                                                     | §2.1                                                    |
| Improved ILP formulations (F3/F4), TU property     | `references/ref - catanzaro.pdf`                                                            | §3 (F3/F4), §3.3 (TU), §3.4 (1-arc ineq.)               |
| JGP ARF MILP formulation (used in codebase)        | `references/ref - catanzaro.pdf`                                                            | §4 or earlier section on ARF                            |
| 0-blocks interpretation of tool switching          | `references/ref - catanzaro.pdf`                                                            | §3.3                                                    |
| Multicommodity flow model (SSPMF, LP LB = M-C)     | `references/MTSP_Article.pdf`                                                               | §3 (model), §4 (computational results)                  |
| SSP as nonlinear Hamiltonian cycle problem         | `references/ref - ghiani.pdf`                                                               | §1, §3                                                  |
| Symmetry property (reverse sequence = same cost)   | `references/ref - ghiani.pdf`                                                               | §2 (Property 1)                                         |
| Non-uniform tool sizes, NP-completeness of TP      | `references/ref - The Tool Switching problem revisited - crama.pdf`                         | §2 (Theorem, 3-Partition reduction)                     |
| Fixed-C tooling polynomial via shortest path       | `references/ref - The Tool Switching problem revisited - crama.pdf`                         | §3                                                      |
| GENI/GENIUS heuristics for SSP                     | `references/Useless/[IIE Transactions...]Hertz...1998.pdf`                                  | §2 (heuristics)                                         |
| SSP SOTA survey, classification framework          | `references/ref - SSP-SOTA-Survey- Calmels, Dorothea.pdf`                                   | §4 (Table 2), §5, §6                                    |
| Colour print scheduling = SSP, JGP+GSP heuristic   | `references/printing2.pdf`                                                                  | §2, §3 (JGP), §4 (GSP)                                  |
| Stirling numbers for JGP solution enumeration      | `references/printing2.pdf`                                                                  | §3                                                      |
| SSP as GTSP, column generation (Colares preprint)  | `references/formal-def-ssp.pdf`                                                             | §2 (GTSP interpretation), §4 (non-compact ILP), §5 (CG) |
| Non-uniform tooling costs via min-cost flow        | `references/BF00123680.pdf`                                                                 | §3.2 (network construction)                             |
| Felipe B&P for TSIP/JGP                            | `references/felipe-thesis.pdf`                                                              | Chapters 2–4                                            |
| Metaheuristic for SSP (JGP warm-start seeding)     | `references/masters_dissertation_bernardo_bastos.pdf`                                       | relevant chapters                                       |
| GTSP comprehensive survey                          | `references/ref -GTSP-survey - pop.pdf`                                                     | §2 (formulations), §5 (algorithms)                      |
| Memetic algorithm for GTSP                         | `references/Useless/s11047-009-9111-6.pdf`                                                  | §2–3                                                    |
| Simultaneous column-and-row generation (CG method) | `references/Useless/s10107-012-0561-8.pdf`                                                  | §1–2                                                    |
| Yanasse enumerative algorithm (partial ordering)   | `references/ref-portugese-yanasse.pdf`                                                      | (Portuguese) §2 (Lemma 1)                               |

---

## Distilled Knowledge — Per Paper

### Tang & Denardo (1988) — `references/ref- tang, denardo.pdf`

_Operations Research 36(5), 767–777_

**Problem formulated**: N jobs, M tools, C-capacity magazine. Variables x_jn (job j at position n), W_n (tool vector). Objective: minimise Σ eP_n (total switches).

**Key theorem**: KTNS (Keep Tool Needed Soonest) is optimal for the Tool Replacement Problem (fixed sequence). Proof in Appendix. Complexity O(MN).

**KTNS procedure** (5 steps): At each position n, load tools needed by job n; keep the C tools whose next use is latest; evict the rest. The set T(i,n) = future instants tool i is needed; L(i,n) = min of T(i,n).

**LP relaxation flaw**: Their own formulation has LP relaxation always = 0. Setting u_jk=1/n, v_kt=|T_j|/n, w_kt=0 is always feasible and optimal for the relaxation — near-useless for B&B.

**Pairwise lower bound**: LB(i,j) = max(0, |T_i ∪ T_j| − C). Minimum switches when job i immediately precedes job j. Used as initial bound in BBC master.

**Dominance rule**: If T_i ⊆ T_j, job i can always follow j without any switches → remove i or fix ordering. Reduces instance size.

**Heuristic**: 3 steps — (1) find short Hamiltonian path on complete graph with LB(i,j) edge weights; (2) apply KTNS; (3) local improvement (adjacent swaps).

**Questions this paper answers**: What is KTNS? Why is it optimal? What is the pairwise lower bound w_ij used in BBC?

---

### Crama, Kolen, Oerlemans & Spieksma (1994) — `references/ref - Minimizing...Crama.pdf`

_Int. J. Flexible Manufacturing Systems 6, 33–54_

**NP-hardness**: Theorem 1 (P1, decision version, NP-hard via matrix permutation reduction); Theorem 2 (P2, minimisation for any fixed C≥2, NP-hard). Proof: edge-graph construction where SSP path = Hamiltonian path in edge-graph.

**Seven model assumptions** (explicit list): (1) each tool in one slot; (2) magazine always full (WLOG); (3) constant switch time; (4) one switch at a time; (5) fixed tool requirements; (6) no tool breakage; (7) complete job list known in advance.

**KTNS alternative proof**: via interval matrices and linear programming (Hoffman, Kolen, Sakarovitch), generalises to arbitrary per-tool setup costs b_k.

**11 heuristics**: divided into construction (4 TSP-based: nearest neighbour, farthest insertion, etc.) and refinement (adjacent swap, 2-opt on job sequence). TSP construction followed by KTNS gives competitive upper bounds.

**Benchmark instances**: Tabela 1–4 in `data/From_Felipe/data/Crama/`. Randomly generated with various (M, N, C) parameters.

**Questions**: Why is SSP NP-hard? What are the standard modelling assumptions? What construction heuristics exist?

---

### Laporte, Salazar-González & Semet (2004) — `references/ref - laporte, salazar.pdf`

_IIE Transactions 36(1), 37–45_

**Tang-Denardo LP = 0 proof**: u_jk=1/n, v_kt=|T_j|/n, w_kt=0 satisfies all TD constraints with objective = 0. This makes LP-based B&C near-useless for TD.

**LSS formulation** (constraints 10–20): Introduces dummy job 0 (T*0=∅, start/end depot). Variables: x_ij (arc), y_it (tool in magazine at job i), z_it (tool switch at job i). Objective (10): min Σ*{i∈J,t∈T_i} z_it.

- (11,12): degree constraints (TSP skeleton)
- (13): subtour elimination, lazy
- (14): magazine capacity Σ_t y_jt ≤ c
- (15): magazine persistence x_ij + y_jt − y_it ≤ z_jt + 1
- (16): y_it = 1 for t∈T_i (required tools always loaded)
- (17): z_it = 0 for t∉T_i (no switches for non-required tools)

**Lifted objective (21)**: min Σ z*it + Σ*{|T_i|=c, j≠i} |T_j \ T_i|·x_ij — adds term for full-magazine jobs.

**Valid inequalities**:

- (23): Σ*{t∈T_i} z_it ≥ Σ*{j:|T_j|≠c} l_ij·x_ij (pairwise lower bound on arc switches)
- (24): Σ\_{i∈J\{j}} x_ij + z_jt ≤ 1 for t∈T_j (tool either introduced at j or j immediately follows a job requiring t)
- (25): Σ\_{t∈T_i\T_j} y_jt ≥ (c−|T_j|)·x_ij when |T_i|=c, |T_j|<c (no unnecessary switches)

**LP relaxation on Tang-Denardo example**: LSS with valid inequalities = 6.0 (vs 1.9 without, vs 0 for TD). Optimal integer = 7.

**Branch-and-cut**: LP-based at each node; GENIUS heuristic (Gendreau, Hertz & Laporte 1992) for initial UB; broad branching (fixes positions of multiple jobs at once, not binary on x_ij). Solves ~8-job instances in 82–1057 seconds.

**Branch-and-bound**: No LP; greedy heuristic (largest-tool-first) for UB; two combinatorial lower bounds for partial sequences (partial KTNS + remaining jobs). Solves up to 25 jobs. Outperforms B&C because LP bound still weak.

**Questions**: What is the LSS formulation? What are valid inequalities (23)–(25)? What is GENIUS used for? Why does B&B outperform B&C here?

---

### Catanzaro, Gouveia & Labbé (2015) — `references/ref - catanzaro.pdf`

_European Journal of Operational Research 244, 766–777_

**Main contribution**: New ILP formulations (Formulations 3 and 4) for SSP with provably tighter LP relaxations than Laporte et al. (2004).

**Arc-based variables**: y^t*{ij} = 1 if tool t carried from job i to job j in optimal sequence; z^t*{ij} = 1 if tool t added at job j in transition from i to j.

**Formulation 3**: Uses y^t*{ij} and z^t*{ij}. Objective: min Σ*{i,j,t∉T_i} z^t*{ij}. LP relaxation of F3 ≥ LP relaxation of LSS (Proposition 1, proven).

**Formulation 4** (reduced): Eliminates z^t\_{ij} via equality constraints (11a)–(11c). Fewer variables; same LP relaxation as F3.

**TU property** (Proposition 3): For fixed x_ij values forming a Hamiltonian circuit, the constraint matrix of capacity constraints (13f) is totally unimodular → LP gives integral solutions for tooling problem. This proves KTNS is optimal for fixed sequence via LP duality.

**0-blocks interpretation**: A 0-block of matrix P is a maximal consecutive zero interval in a tool row — corresponds to a tool not needed during a contiguous sequence of jobs. Formulation 4 defines an optimal sequence as a path minimising the number of 0-blocks.

**1-arc inequalities** (Proposition 4): Σ*{i∈f(j,k)} y^t*{ij} ≥ y^t\_{jk} for each t∈T_k\T_j — ensures tool t needed at k is carried from some predecessor of j if carried to k.

**Computational improvement**: LP bounds improve on average vs Laporte et al. (2004). Enables solution of larger instances.

**JGP ARF formulation** (also in this paper): v[i,h] = 1 iff job i in batch h; y[t,h] = 1 iff tool t in batch h. Constraints: each job in exactly one batch, batch active if any job assigned, capacity per batch ≤ C·v[h,h]. Objective: min Σ_h v[h,h] (minimise number of batches). This is what `solve_jgp_arf` in `src/SSP/SCIP_formulation_solvers.py` implements.

**Questions**: What is the tightest known LP formulation for SSP? What is the 0-blocks interpretation? What is TU and why does it matter? How is JGP solved exactly?

---

### da Silva, Chaves & Yanasse (2024) — `references/MTSP_Article.pdf`

_Preprint, compiled May 2024_

**Main contribution**: New multicommodity flow model (SSPMF) for SSP with LP relaxation lower bound = M − C (number of tools minus capacity). Proven tight.

**LP bound claim**: LB_LP = M − C. This is the tightest known LP relaxation lower bound for SSP. Outperforms Catanzaro et al. (2015) in general.

**Symmetry-breaking**: Constraint eliminates half of all symmetric solutions (Ghiani et al. 2010 symmetry property exploited directly in the formulation).

**Pure MIP**: No lazy constraints needed (unlike LSS). Can use standard MIP solver directly.

**Computational results**: With CPLEX, solves 17.01% more benchmark instances (Catanzaro Tabela1C) compared to previous best formulations.

**SSPMF implemented in**: `src/BBC/sspmf_formulation.py`.

**Objective post-processing**: This formulation counts initial magazine loading from empty depot. When comparing with BBC (which uses a dummy depot with free transitions), subtract |T\_{seq[0]}| from reported objective.

**Questions**: What is the tightest LP bound for SSP? How does SSPMF outperform earlier formulations? Does SSPMF need lazy constraints?

---

### Ghiani, Grieco & Guerriero (2010) — `references/ref - ghiani.pdf`

_Networks 55(4), 379–385_

**Main contribution**: Frames SSP as a nonlinear least-cost Hamiltonian cycle problem, then develops a B&C exploiting the **symmetry property**.

**Symmetry property** (Property 1): For any sequence (u₁,…,uₙ), its reversal (uₙ,…,u₁) has the same total switch cost z* = z*\_R. **Note**: individual transition costs differ between forward and reverse; only the total is equal.

**Algorithmic use**: Symmetry halves the B&B search space. Only sequences in canonical form (e.g., first job ≤ last job) need be explored.

**Formulation**: SSP as minimise Σ c*ij(x)·x_ij where c_ij(x) = max(0, max*{p*k∈K_i} {Σ*{(r,s)∈p_k} x_rs + x_ij − |p_k| − 1}) (nonlinear). Relaxed to symmetric TSP with edge costs c^LB_ij = max(0, |T_i ∪ T_j| − c).

**Lower bounding**: c^LB_ij updated dynamically at each B&B node using partial sequence information and a Tailored KTNS with O(cn) complexity per arc.

**Separation**: Padberg-Rinaldi comb inequalities + max-flow for subtour elimination.

**Branching**: Type 1 (x'\_ij ≈ 0.5, highest score c^LB_ij·min(x̄_ij, 1−x̄_ij)); Type 2 (x̄_ij=1, lowest c^LB_ij).

**Result**: Solves instances larger than Laporte et al. (2004) (which maxed at 25 jobs). Verified: Ghiani et al. is the actual "Ghiani 2010" paper, NOT the unverified "Ghiani 2007" reference.

**Questions**: What is the symmetry property? How do Ghiani et al. improve on Laporte? How is the B&C structured?

---

### Crama, Moonen, Spieksma & Talloen (2007) — `references/ref - The Tool Switching problem revisited - crama.pdf`

_European Journal of Operational Research 182, 952–957_

**Topic**: Non-uniform tool sizes (tool t occupies s_k ≥ 1 slots, not just 1).

**Result 1** (Theorem): Tooling Problem (TP) with non-uniform sizes is **strongly NP-complete** even with unit L/U costs. Reduction from 3-Partition.

**Result 2**: For **fixed value of C** (given as input), TP is solvable in **polynomial time** via shortest path on a directed graph D=(V,A) with O(|T|^C · C!) vertices per layer. Arc (i,j) encodes switching cost from magazine config i to config j.

**Contrast with uniform sizes**: KTNS solves uniform-size TP in O(MN) for any C. Non-uniform: if C is variable (in the input), NP-complete even with unit costs.

**Types of magazines**: Results hold for both straight (PCB) and round (metal working) magazine layouts.

**Web caching connection**: Uniform TP ≡ Belady's paging problem (Belady 1966) — KTNS = optimal replacement. KTNS already known in OS context before SSP.

**Relevance to collapse variants**: Non-uniform costs d_ij (replacing tool i with tool j) were studied by Privault & Finke (1995) using min-cost flow. This paper extends to non-uniform sizes.

**Questions**: Is tooling NP-hard for non-uniform tool sizes? When is tooling polynomial? What is the connection to paging/web caching?

---

### Privault & Finke (1995) — `references/BF00123680.pdf`

_Journal of Intelligent Manufacturing 6, 87–94_

**Topic**: Tool switching with non-uniform switch costs d_ij (cost to replace tool i with tool j). Fixed job sequence (tooling problem).

**Key result**: For fixed job sequence and non-uniform costs d_ij, tooling problem reduces to **minimum cost flow of maximum value** in an acyclic network. Polynomial.

**Network construction**: Source s → C initial-config vertices (level 1) → tool-request vertices r_j (levels 2,3) → sink p. Horizontal arcs between r_j and r'\_j have weight −k (large), forcing insertion when required. Inter-group arcs have weight d_ij (the switching time).

**Sequencing heuristics**: Section 4 presents 4 heuristics for the full SSP (both sequence and tooling), tested on random instances.

**Relevance to collapse variants**: When setup time dominates (all d_ij → ∞ for i≠j), the network structure forces all tools to be loaded once at start → collapses to JGP. The min-cost flow construction is the key reference for proving this collapse mathematically.

**Questions**: How is tooling solved for non-uniform switch costs? What network construction encodes the tooling problem? Why does the collapse condition work?

---

### Hertz, Laporte, Mittaz & Stecke (1998) — `references/Useless/[IIE Transactions...]`

_IIE Transactions 30, 689–694_

**Topic**: SSP heuristics — modelled as TSP with KTNS for tooling evaluation.

**Key finding**: GENI (construction) and GENIUS (construction + post-optimisation) heuristics outperform all Crama et al. (1994) heuristics. GENIUS = GENI + local search (Gendreau, Hertz & Laporte 1992).

**Edge cost metric**: Several metrics tested for TSP arc costs. One global metric (considers interactions among all jobs, not just pairs) provides significant improvement.

**Benchmark**: Same instance sets as Crama et al. (1994).

**Note in Laporte et al. (2004)**: GENIUS used there as the initial upper bound generator in the B&C algorithm.

**Questions**: Which heuristic gives best upper bounds for SSP? What is GENIUS?

---

### Calmels (2018) — `references/ref - SSP-SOTA-Survey- Calmels, Dorothea.pdf`

_International Journal of Production Research_

**Scope**: Systematic review of 61 SSP papers from 1597 hits across 7 databases.

**Classification framework** (8 dimensions):

| Dimension             | Values                                                             |
| --------------------- | ------------------------------------------------------------------ |
| A — Machine           | 1 (single), M (multiple)                                           |
| B — Setup time        | ST_si (uniform/seq-independent), ST_sd (non-uniform/seq-dependent) |
| Γ — Objective         | SO (single: switches), MO (multi: makespan+switches)               |
| Δ — Tool size         | Tool_hom (homogeneous), Tool_het (heterogeneous)                   |
| E — Job/sequence info | L_k/Seq_u (known list, unknown seq), L_k/Seq_k, L_u/Seq_u          |
| Z — Magazine capacity | \|T_j\|≤C vs \|T_j\|>C                                             |
| H — Tool wear         | TW_no, TW_yes                                                      |

Standard SSP: [1/ST_si/SO/Tool_hom/L_k,Seq_u/\|T_j\|≤C/TW_no]

**Research gaps identified**:

- Multi-machine settings vastly understudied
- Non-uniform setup times rarely studied (real-world: sequence-dependent)
- Multi-objective (makespan + switches) emerging but rare
- Tool wear almost never included (real-world: critical)
- Online version (job list not fully known) rarely studied

**Questions**: What classification does the standard SSP fall under? What are open research directions? What problem variants exist?

---

### Burger, Jacobs, van Vuuren & Visagie (2015) — `references/printing2.pdf`

_Journal of Scheduling 18, 131–145_

**Application**: Colour Print Scheduling Problem (CPSP) — printing machine with b ink cartridges = magazine. Colours = tools. Number of colour changes = tool switches. Real case study from South African printing company.

**Key contribution**: CPSP ≡ SSP (proved). JGP+GSP heuristic decomposition applied:

- JGP modelled as **unicost set covering** problem
- GSP modelled as **TSP** (local one-job-only look-ahead or global all-jobs look-ahead)

**Stirling numbers for JGP enumeration**: Uses Stirling numbers of the second kind to count (and enumerate) all optimal JGP solutions. Directly relevant to Shankar's grouping selection research.

**Suboptimality study**: Measures degree of suboptimality of JGP+GSP heuristic. Endorses Salonen et al. (2006) finding that the decomposition performs "remarkably well."

**Burger et al. verified**: This IS the Burger et al. (2015) paper — confirmed present in `references/printing2.pdf`. Previously listed as unverified.

**Questions**: How are JGP solutions enumerated? What is the JGP+GSP suboptimality in practice? How does colour printing map to SSP?

---

### Colares, de Souza & Wagler (preprint ~2026) — `references/formal-def-ssp.pdf`

_Preprint (downloaded March 2026 from advisor's mail system)_

**Authors**: Rafael Colares, Mauricio de Souza, Annegret Wagler — this is Prof. Colares' group.

**GTSP interpretation**: Configurations C = all feasible tool subsets of size b. For job j, cluster H_j = {C ∈ C : T_j ⊆ C}. SSP = shortest Hamiltonian cycle in complete graph K_p visiting one config from each H_j. This is a GTSP (clusters can intersect).

**Note**: GTSP degenerates to regular GTSP (disjoint clusters) when |T_i ∪ T_j| > B for all job pairs — relevant to JGP+GSP when batches have disjoint tool sets.

**Non-compact ILP** (Section 4): Variables y(v) ∈ {0,1} (config used), x(u,v) ∈ {0,1} (transition). Objective: min Σ d(u,v)·x(u,v) where d(i,j) = b − |C_i ∩ C_j|. Constraints (2)–(7): coverage (H_j covered), degree (flow), subtour elimination, integrality. Exponentially many variables — non-compact.

**Column generation** (Section 5): Restricted Master Problem (RMP) with subset V̄ ⊆ V of configurations. Pricing problem generates new configs in V\V̄ with negative reduced cost. Preprocessing note: "to be written" (preprint!).

**Important**: Contains handwritten research notes in the preprint (footnote 1 on p.2: "Can we provide a property of the jobs that would induce disjoint clusters?"). This is active research by Colares — treat findings here as **current unpublished work**.

**Questions**: What is the GTSP formulation of SSP? What is Prof. Colares' current approach? When do clusters become disjoint?

---

### Pop, Cosma, Sabo & Pop Sitar (2024) — `references/ref -GTSP-survey - pop.pdf`

_European Journal of Operational Research 314, 819–835_

**Scope**: Comprehensive GTSP survey — problem definition, variants, real-world applications, formulations, exact + heuristic algorithms.

**GTSP definition**: Given undirected graph G=(V,E) with vertex partition C₁,…,Cₖ, find shortest Hamiltonian cycle visiting exactly one vertex from each cluster. TSP = special case (all clusters singletons).

**Key solution approaches surveyed**:

- Noon-Bean transformation: convert GTSP to equivalent TSP (exponential blowup but enables TSP solvers)
- Exact: B&C for symmetric GTSP (Fischetti, Salazar-González & Toth 1997)
- Heuristic: LKH-3 extended to GTSP; memetic algorithms (Gutin & Karapetyan 2010)

**Real-world applications**: Post-box routing, airport selection, material flow design, garment manufacturing, etc.

**Relevance**: GSP (Group Sequencing Problem — ordering JGP batches) = GTSP where each batch = one cluster; configurations within a cluster = all possible tool loadings for that batch.

**Questions**: What algorithms solve GTSP? How does GTSP relate to GSP? What is Noon-Bean transformation?

---

### Yanasse, Rodrigues & Senne (2009) — `references/ref-portugese-yanasse.pdf`

_Gest. Prod. 16(3), 303–314 (Portuguese)_

**Topic**: Enumerative algorithm using partial ordering for SSP (called MTSP in Portuguese literature).

**Lemma 1**: For sequence S₁=(s₁,…,sₖ), if T₂ ⊆ T₁ for some subset T₂ of remaining jobs, removing dominated jobs does not increase switches. Enables pruning.

**Algorithm**: Expands partial sequences by appending one job at a time; uses dominance to prune; lower bounds to fathom.

**Historical note**: Labels the problem MTSP (Minimization of Tool Switches Problem). Same problem as SSP.

**Questions**: What lower bounds exist for partial job sequences? (Background for Laporte B&B lower bounds.)

---

### Gutin & Karapetyan (2010) — `references/Useless/s11047-009-9111-6.pdf`

_Natural Computing 9, 47–60_

**Topic**: Memetic algorithm for GTSP (GA + local search).

**Local search**: Powerful local search on GTSP solutions — exchanges one cluster vertex for another, then reconnects tour. Key differentiator from pure GA.

**Results**: Clearly outperforms earlier GTSP heuristics on standard benchmarks.

**Relevance**: If solving GSP (ordering JGP batches) as GTSP, this provides a good upper-bound heuristic for batch sequencing.

---

### Muter, Birbil & Bülbül (2013) — `references/Useless/s10107-012-0561-8.pdf`

_Mathematical Programming 142, 47–82_

**Topic**: Simultaneous column-and-row generation for LPs where adding new columns also creates new linking constraints (column-dependent rows).

**Relevance**: If Colares' column generation approach for SSP (formal-def-ssp.pdf) involves constraints that depend on which configurations are generated, this framework applies. Background methodology for any CG approach to SSP.

---

## Unverified References — Do NOT Cite

| Reference                                             | Status                                                                                                                                           |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **daSilva 2021**: CG for SSP with set-covering master | **WRONG YEAR** — actual paper is da Silva, Chaves & Yanasse 2024 (MTSP_Article.pdf). If this refers to a different 2021 paper, it is unverified. |
| **Ghiani 2007**: SSP = min-cost Hamiltonian cycle     | **NOTE**: The verified paper is Ghiani, Grieco & Guerriero (2010), not 2007. The 2007 claim is an error.                                         |
| **Burger et al. 2015**                                | **VERIFIED** — confirmed as `references/printing2.pdf`. Safe to cite.                                                                            |
| **Salonen et al. (2006)**                             | Referenced in Burger et al. (2015) as endorsing JGP+GSP but paper itself not in `references/`. Verify before citing directly.                    |

---

## Benchmark Sets Quick Reference

| Dataset            | Location                                    | Paper          | Typical params  |
| ------------------ | ------------------------------------------- | -------------- | --------------- |
| Catanzaro A/B/C/D  | `data/From_Felipe/data/Catanzaro/Tabela1C/` | Catanzaro 2015 | n=10–40         |
| Crama Tabela 1–4   | `data/From_Felipe/data/Crama/`              | Crama 1994     | small-medium    |
| Laporte Tabela 3–7 | `data/From_Felipe/data/Laporte/`            | Laporte 2004   | medium          |
| Otiai large/medium | `data/From_Felipe/data/Otiai/`              | Otiai thesis   | large           |
| Shankar custom     | `data/Shankar/`                             | —              | 6-job ring etc. |

Primary benchmarks for exact solvers: Catanzaro Tabela1C. Always state which set was used in results.

---

## SOTA Timeline (for "new SOTA" proposals)

| Year  | Contribution                                                  | Beats                 |
| ----- | ------------------------------------------------------------- | --------------------- |
| 1988  | Tang & Denardo: KTNS + ILP formulation                        | —                     |
| 1994  | Crama et al.: NP-hardness proof + 11 heuristics               | —                     |
| 1998  | Hertz et al.: GENIUS heuristic                                | Crama 1994 heuristics |
| 2004  | Laporte et al.: LSS ILP + B&C + B&B (≤25 jobs exact)          | Tang-Denardo          |
| 2010  | Ghiani et al.: B&C via nonlinear Hamiltonian cycle + symmetry | Laporte 2004          |
| 2015  | Catanzaro et al.: Tighter LP (F3/F4), 1-arc inequalities      | Laporte 2004          |
| 2024  | da Silva et al.: SSPMF, LP LB=M−C, 17.01% more solved         | All prior exact       |
| ~2026 | Colares et al.: GTSP formulation + CG (preprint)              | —                     |

Before claiming "new SOTA", confirm against: (a) Catanzaro Tabela1C instances, (b) da Silva 2024 SSPMF, (c) Calmels 2018 survey classification.

---

## Citation Keys

All verified references are in `plans-genai/references.bib`. Check exact keys there before writing any `\cite{}`. Do not guess. Papers listed in this skill that are NOT in `references.bib` (e.g., Colares preprint) cannot be cited yet — ask Shankar first.
