# Research Verification Results: SSP, GTSP, and Related Concepts

## Executive Summary
Research conducted across academic literature reveals a mix of verified concepts and potential hallucinations. Key findings below.

---

## 1. KTNS Policy (Keep Tool Needed Soonest) ✅ VERIFIED

**Status**: REAL, well-established in literature

**Key Papers**:
- Tang & Denardo (1988) - **FOUNDATIONAL WORKS**:
  - "Models arising from a flexible manufacturing machine, Part I: minimization of the number of tool switches" - Operations Research, 36(5):767-777 (421 citations)
  - "Models arising from a flexible manufacturing machine, Part II: Minimization of the number of switching instants" - Operations Research, 36(5):778-784 (180 citations)
  - Tang & Denardo introduced KTNS as the optimal policy for the Tooling Problem (TP)

**Additional Confirmations**:
- Crama et al. (1994) - "Minimizing the number of tool switches on a flexible machine" - International Journal of Flexible Manufacturing Systems
- Zhou, Xi & Cao (2005) - "A beam-search-based algorithm for the tool switching problem" - The International Journal of Advanced Manufacturing Technology
- Cherniavskii & Goldengorin (2022) - "An almost linear time complexity algorithm for the tool loading problem" - arXiv:2207.02004
- Multiple citations across 1991-2025 literature

**Formal Property**: Optimal policy for magazine state management when job sequence is fixed. Greedy algorithm that removes tools least needed soonest.

---

## 2. Set Union Knapsack (SUKP) in SSP Column Generation ✅ REAL CONCEPT

**Status**: Real problem but connection to SSP pricing is NOT well-documented in my searches

**Key Papers**:
- Goldschmidt, Nehme & Yu (1994) - "Note: On the set-union knapsack problem" - Naval Research Logistics (121 citations)
- Wu & He (2020) - "Solving the set-union knapsack problem by a novel hybrid Jaya algorithm" - Soft Computing
- Locatelli (2023) - Thesis: "Optimization methods for knapsack and tool switching problems" - University of Modena
- Wahlen & Gschwind (2025) - "Branch-and-price for the set-union bin packing problem" - INFORMS Journal on Computing
  - Explicitly mentions "job grouping problem, toolswitching problem, or bin packing problem, which is a set-union knapsack problem (SUKP)"

**Connection to SSP**: SUKP appears relevant but specific papers on SSP column generation pricing subproblem are not prominent in search results. Need to check research theses directly.

---

## 3. GTSP-SSP Equivalence ⚠️ PARTIALLY VERIFIED

**Status**: Connection exists but formal equivalence proof is not a standard reference

**Key Evidence**:
- Strunk (2022) - arXiv:2205.02662 - "Greedy clustering-based algorithm for improving multi-point robotic manipulation sequencing"
  - "The GTSP accomplishes a similar mechanism... In this section we will describe the algorithm used to solve the SSP"
  - Explicitly models SSP as instance of GTSP
  
- Soares & Carvalho (SSRN) - "Faster, Competitive Approaches for the Job Sequencing and Tool Switching Problem"
  - "modeling the SSP as an instance of the generalized traveling salesman problem (GTSP)"
  - Explores connection between SSP and consecutive block minimization

**Formal Transformation Theory**:
- Vertex duplication technique is REAL but attributed to **Dimitrijević & Šarić (1997)**, NOT "I-N Transformation"
  - Paper: "An efficient transformation of the generalized traveling salesman problem into the traveling salesman problem on digraphs" - Information Sciences
  - Method: Creates copy i' of each vertex i, transforms GTSP with n vertices to TSP with 2n vertices
  - 119 citations, well-established in GTSP literature

**Issue**: The term "I-N Transformation" (Intersecting-to-Nonintersecting) appears to be local terminology, not standard in literature. Dimitrijević-Šarić transformation is the canonical reference.

---

## 4. Colares-Wagler Formulation ❌ LIKELY HALLUCINATED

**Status**: NO EVIDENCE FOUND

**Search Results**:
1. "Colares Wagler SSP tool switching" - **Zero matching papers** ("Aucun article ne correspond à votre recherche")
2. "Colares SSP job sequencing" - **Zero matching papers** (only agricultural/botanical unrelated papers)
3. "Wagler tool switching integer programming" - **ZERO tool switching papers**
   - A. Wagler (real researcher at LIMOS) works on:
     - Flow relocation models
     - Bandwidth allocation polytopes
     - Time-expanded networks
     - Systems biology networks
   - NO publications on tool switching or SSP

**Positive Finding on "Colares"**:
- Rafael Colares: Real PhD researcher (2019) on "stop number problem" at Université Clermont Auvergne
- Other Colares researchers in combinatorial optimization
- **BUT**: None have publications on SSP or tool switching

**Conclusion**: "Colares-Wagler" appears to be a misremembered or hallucinated attribution. The actual source of the configuration-based formulation may be:
- Potentially from other literature (Catanzaro? Laporte? Gouveia?)
- Or a novel formulation without published reference

---

## 5. Verified Standard References

### Core Foundational Papers:
- **Tang & Denardo (1988)** - Operations Research (2 papers) ✅ VERIFIED
- **Crama et al. (1994)** - "Minimizing the number of tool switches on a flexible machine" ✅ VERIFIED
- **Laporte, Salazar-González & Semet (2004)** - "Exact algorithms for the job sequencing and tool switching problem" - IIE Transactions (106 citations) ✅ VERIFIED
- **Catanzaro, Gouveia & Labbé (2015)** - "Improved integer linear programming formulations for the job sequencing and tool switching problem" - EJOR (69 citations) ✅ VERIFIED
- **Calmels (2019)** - "The job sequencing and tool switching problem: state-of-the-art literature review, classification, and trends" - International Journal of Production Research (64 citations) ✅ VERIFIED

### GTSP Transformation Papers:
- **Dimitrijević & Šarić (1997)** - "An efficient transformation of the generalized traveling salesman problem into the traveling salesman problem on digraphs" - Information Sciences (119 citations) ✅ VERIFIED
- **Gutin & Karapetyan (2009)** - "Generalized traveling salesman problem reduction algorithms" ✅ VERIFIED

---

## 6. Missing from Literature

**Not found despite searches**:
- "I-N Transformation" (Intersecting-to-Nonintersecting) as a named technique
  - Vertex duplication exists but is attributed to Dimitrijević-Šarić
- Bernardo's column generation heuristic for SSP
  - Search returned no relevant papers despite multiple attempts
- Specific column generation pricing formulation as SUKP for SSP
  - Connection exists but not formalized in accessible literature

---

## Key Recommendations

1. **Verify Colares-Wagler Attribution**
   - Check original draft sources carefully
   - May need to cite actual formulation differently or remove attribution
   - Search theses from LIMOS/University Clermont Auvergne directly

2. **I-N Transformation Nomenclature**
   - Consider renaming to "Vertex Duplication Transformation" or cite Dimitrijević-Šarić
   - Or clarify if "I-N" is novel local terminology

3. **Pricing Subproblem**
   - SUKP connection is real but may need more direct paper citations
   - Check Locatelli (2023) thesis for column generation treatment

4. **Bernardo Reference**
   - Verify if this is an internal thesis rather than published paper
   - May not be citable in final work

---

## Citation Guide for Verified Concepts

- KTNS Policy: Tang & Denardo (1988), Operations Research papers
- Set Union Knapsack: Goldschmidt et al. (1994), or modern Locatelli (2023)
- GTSP Transformation: Dimitrijević & Šarić (1997)
- SSP Core Literature: Crama (1994), Laporte et al. (2004), Catanzaro et al. (2015)
- SSP Survey: Calmels (2019)
