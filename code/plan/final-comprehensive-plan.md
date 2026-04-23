# Final Comprehensive Research Plan: SSP via GTSP with Bounds & Visualizations

## RESEARCH OBJECTIVES (Advisor-Directed: Colares & Wagler)

1. **GTSP Equivalence**: Rigorously prove SSP ↔ GTSP bijection (with I-N transformation)
2. **Formulation Correctness**: Establish conditions for configuration-based MILP validity
3. **Bounds Framework**: Lower (JGP, LP, dominance), upper (warm-start, greedy, local search), approximation ratios
4. **Time-Dependent Variant**: Extend theory, bounds, costs to temporal domain
5. **Ryan Foster Inequality Analysis**: Conditions for tightening to equality
6. **Branch-and-Price Design**: Column generation with ML/metaheuristics for scalability

---

# STRUCTURE: Theory, Code, Visualizations (Integrated)

## LaTeX Draft Architecture

### Sections 1-3: Preliminaries & Problem Setup
- Introduction: FMS context, NP-hardness (cite Crama 1994)
- Formal problem definitions: JGP vs SSP
- Tang & Denardo decomposition: KTNS optimality (theorem statement + proof sketch)
- Visualization: Incidence matrix with 0-blocks highlighted

### Sections 4-5: Reformulation & Equivalence
- Configuration graph formulation (non-compact MILP)
- Why avoids 0-block symmetry (formal + intuitive)
- **GTSP Equivalence Theorem**: SSP ↔ GTSP bijection via I-N transformation
  - Theorem statement (rigorous)
  - Proof in 2 directions (Seq→GTSP, GTSP→Seq)
  - Plain-language explanation in sidebar
  - Visualization: State evolution, I-N transformation
- Correctness conditions: When formulation is valid, edge cases

### Section 6: BOUNDS FRAMEWORK (Core Differentiator)

**Lower Bounds** subsection:
- **LB.1 (JGP)**: OPT(JGP) ≤ OPT(SSP) [Theorem + proof]
  - Tightness: when equality, when loose
  - Comparison table
- **LB.2 (LP Relaxation)**: CONFIG-MILP LP ≥ OPT(SSP)
  - Gap analysis, GSEC cutting planes
- **LB.3 (Config Dominance)**: Non-dominated config MST
  - Algorithm, approximation ratio ≈ 2×
- **Visualization 6.1**: Bounds hierarchy (JGP | LP | OPT | UB)

**Upper Bounds** subsection:
- **UB.1 (Warm-Start)**: Solve JGP → order within batches → SSP cost
  - Algorithm, approximation factor ρ (1.1-1.5 typical)
- **UB.2 (Greedy FFD)**: First-Fit Decreasing by tool requirement size
  - Theorem: UB ≤ 2× OPT (bin packing analogy, cite Johnson 1973)
- **UB.3 (Local Search 2-Opt)**: Swap-improving heuristic
  - Quality: 3-10% empirical gap
- **Comparison table**: UB quality vs. speed

**Gap Analysis** subsection:
- Gap = (UB - LB) / LB definition
- When gap is large (loose bounds), tight (good bounds)
- How tightening bounds reduces uncertainty
- Visualization: Gap closing as methods improve

### Sections 7-9: Special Topics
- **Ryan Foster**: Inequality conditions, equality analysis, application to pricing
- **Time-Dependent Variant**: Formulation, equivalence under monotone w(τ), time-weighted bounds
- **Branch-and-Price Skeleton**: RMP, PSP (SUKP), pricing via heuristics/ML

---

## Code Component: Enhanced Notebook

### Key Improvements (Bound-Centric, Visualization-Rich)

**New Solver Functions**:
- `compute_lp_relaxation_bound()`: Solve LP relaxation of CONFIG-MILP
- `compute_config_dominance_bound()`: Build dominance graph, solve MST-TSP
- `compute_warmstart_ub()`: From JGP → SSP sequence → cost
- `compute_greedy_ffd_ub()`: FFD heuristic on tool requirements
- `apply_2opt_improvement()`: Local search refinement

**New Validation & Diagnostic Functions**:
- `validate_jgp_solution()`: Check batch feasibility, cost correctness
- `validate_ssp_solution()`: Check job coverage, tool requirements, capacity
- `verify_bounds_ordering()`: Confirm LB ≤ OPT ≤ UB (when OPT known)

**Enhanced Visualization Suite**:
1. **Incidence + 0-Blocks**: Heatmap with red dashed boxes highlighting consecutive zeros
2. **Magazine Timeline (2-panel)**: JGP rigid batches vs. SSP continuous routing with switch annotations
3. **Active Config Network**: Directed graph of used configurations, edge weights = switch costs
4. **Bounds Hierarchy**: Bar chart showing JGP | LP | OPT | Warm-Start | Greedy with gap shaded
5. **Time-Dependent Cost Surface**: Subplots for different w(τ) (linear, exponential, etc.)

**Bounds Computation Table**:
```
Instance | JGP_LB | LP_LB | Dominance_LB | UB_WarmStart | UB_Greedy | OPT | Gap%
```

---

# DUAL-LANGUAGE WRITING APPROACH (Draft)

Each major result structured as:
1. **Intuition Box** (sidebar, colored): Plain English without formalism
2. **Formal Theorem**: Rigorous statement with all conditions
3. **Proof**: Complete mathematical proof or detailed proof sketch with citation
4. **Visual Illustration**: Diagram, plot, or worked example
5. **Simple Explanation**: Rephrase intuition in light of proof (why it works)
6. **Citation & References**: Academic sourcing throughout

**Example Structure**:
- Sidebar: "JGP is a relaxation: we group jobs rigidly, SSP sequences flexibly. Any sequencing solution has a natural grouping, so JGP's best solution ≤ SSP's best."
- Theorem 6.1: [Formal statement]
- Proof: [Mathematical argument with ∀, ∃, inequalities]
- Visualization: [Diagram showing partition within sequence]
- Explanation: "The key is that SSP must process all jobs, and when the magazine is full, a reload is forced. These reloads naturally partition jobs into groups."
- Reference: "Similar decomposition appears in Catanzaro et al. (2015) and Laporte et al. (2004)."

---

# COMPREHENSIVE BOUNDS STRATEGY

**Integration Throughout**:
- Section 2: Introduce JGP as natural lower bound
- Section 6: Develop all lower/upper bounds with comparison
- Section 7: Ryan Foster as bound-tightening tool
- Section 8: Time-dependent bounds
- Section 9: Bounds in branch-and-price (dual bounds from LP, primal from heuristics)

**In Computational Experiments**:
- Table: Bounds for every instance (LB_JGP, LB_LP, LB_Dom, UB_Warm, UB_Greedy, OPT, Gap%)
- Chart: Average gap by instance class/size
- Analysis: Which lower bound is tightest? When is warm-start effective?

**No Timelines** - Just research components with natural dependencies:
1. Implement & debug (foundations)
2. Prove GTSP equivalence (theory)
3. Develop bounds framework (extensions)
4. Analyze special topics (applications)
5. Write & polish (integration)

---

# VISUALIZATION CHECKLIST

## In LaTeX Draft (TikZ)
- ☐ Section 2: Incidence matrix with 0-blocks
- ☐ Section 3: Compact vs. configuration-based (diagram)
- ☐ Section 4: Overlapping clusters → I-N disjoint clusters
- ☐ Section 4: Example GTSP path from sequence
- ☐ Section 6: Bounds hierarchy (bars)
- ☐ Section 8: Time-weight cost surface
- ☐ Section 9: Branch-and-price flowchart (RMP ↔ PSP)

## In Marimo Code
- ☐ Incidence + 0-blocks (heatmap)
- ☐ Magazine timeline (2-panel: JGP + SSP)
- ☐ Active config network (directed graph)
- ☐ Bounds comparison (bar chart)
- ☐ Time-dependent surfaces (subplots)
- ☐ Bounds table (DataFrame)

---

# KEY RESEARCH QUESTIONS (To Guide Writing & Experimentation)

1. **GTSP bijection**: Is the I-N transformation truly lossless for all instances? Any pathological cases?
2. **JGP tightness**: What instance properties make JGP ≈ OPT(SSP) vs. JGP ≪ OPT(SSP)?
3. **Which lower bound wins**: Does JGP, LP, or dominance bound converge fastest?
4. **Warm-start quality**: Does JGP-based warm-start give ≈ 5-10% gap consistently, or highly variable?
5. **Ryan Foster equality**: Can we characterize job subsets S where subtour constraint becomes equality?
6. **Time-dependent preservation**: For exponential w(τ) = e^{ατ}, does optimal structure change or remain similar?
7. **Feasibility of B&P**: Can SUKP pricing (even heuristically) enable scalability to 100+ jobs?

---

# NEXT STEPS (Not Phase-Based)

1. **Fix code bugs** (critical): JGP job extraction, path unwrapping, dummy visualization
2. **Add validators**: Ensure solutions are feasible, costs computed correctly
3. **Implement all bounds**: Code all 3 lower + 3 upper bound functions
4. **Create visualizations**: 5 new/enhanced plots as specified
5. **Write theory sections**: 1-5 (preliminaries, GTSP, correctness) with dual-language rigor
6. **Develop bounds section**: Section 6 with formal theorems, proofs, comparison tables
7. **Special topics**: Sections 7-9 (Ryan Foster, time-dependent, B&P)
8. **Polish & integrate**: Illustrations, citations, readable flow, example worked instances
