# Expansion guide — `mid_internship_report.tex`

Authoring notes for expanding the standalone report. **This file is scaffolding;
nothing here is rendered.** The `.tex` must remain a self-contained scientific
document: no references to this guide, to internal working notes, to script names,
or to internal problem-numbering.

## Global discipline
- **Audience:** a strong mathematician unfamiliar with the SSP. Define every object
  before use; precede every result with its objective and context.
- **Evidence provenance (use the verified record, not the working drafts).** State
  as *theorems/propositions* only results with a proof; state computationally
  supported but unproved results as *conjectures* and give the experiment scope in
  prose (e.g. "verified by exhaustive enumeration for all instances with $m\le 6$").
  The authoritative numbers/labels live in `plans-genai/_verification/` (e.g.
  `VERIFIED_FACTS.md`, `verify_*.py`); the prose `.tex` drafts in `plans-genai/`
  give topics only.
- **Long/awkward proofs → Appendix `app:proofs`.** Results proved in the literature
  → cite, do not reprove.
- **EXCLUDE-LIST (disproven; never state as results):** cluster-aggregated MTZ
  exactness (only per-configuration MTZ is exact); "2K_3" 6-ring conflict graph (it
  is the triangular prism); ratio $\le 4/3$ for all $b$ (a $b=3$ statement only;
  ratio is non-decreasing in $b$, reaching $3/2$ at $b=5$); $\sum R_k \le H/4$.
- **DO-NOT-CITE until verified (absent from `references.bib`):** da Silva 2021,
  Ghiani–Laporte–Semet 2007, Burger 2015, Salonen 2006.
- **Convention:** switch cost = insertions after a free initial fill of $\le b$
  tools; empty-start $=$ free-initial $+\min(b,|U|)$ per sequence (Prop. in §2.6).

## Per-section briefs
- **§1 Introduction — DONE.** Motivation, two pillars + GTSP lens, contributions,
  outline.
- **§2 Preliminaries — DONE.** SSP/KTNS/JGP definitions, configuration–GTSP lens,
  both lower bounds (proved), convention identity, related work. Lower bounds live
  here (shared infrastructure).
- **§3 Gap theory — TODO.** Lead with the grouping-exactness theorem ($\Zst=\min$
  GTSP cost over *all* feasible groupings; proved, verified 1306 instances) and its
  corollary (gap = price of minimum-cardinality restriction). Then: ring family +
  table $k=3..8$; unbounded gap ($g$ disjoint rings, gap $=g$, verified $g=1..4$);
  unconditional ratio $\le\min(b,\Kst-1,|U|-b)$ (proved); $K^\*\le 2\Rightarrow$
  gap $0$ (proved); conjectures gap $\le \Kst-2$ ($\sim$1380 inst.) and $4/3$ for
  $b=3$ ($\sim$17k inst.); zero-gap sufficient conditions (proved); setup-cost
  collapse $R(\rho)$ monotone, $\rho_c=1$ (proved). Remark: perfectness of the
  configuration conflict graph does not predict the gap. Cite Crama1994, Jans2013,
  daSilva2024, Chudnovsky2006, Privault1995/2000.
- **§4 Exact methods — TODO.** Compact baselines (Catanzaro F4, LSS, SSPMF) + the
  $|U|-b$ relaxation fact. BBC: master (TSP skeleton $+\theta$, degree, $w_{ij}=
  \max(0,|T_i\cup T_j|-b)$ bound, lazy SECs), tool-loading dual subproblem,
  optimality + KTNS-combinatorial cuts, fractional cuts, $O(n^3)$ triplet bounds;
  DSP verified $=$ KTNS, optima $=$ brute. PCF/PTF: fixed $O(n|T|)$ rows; PCF LP
  $=0$ plain, $=|U|-b$ with counting rows (proved); PTF LP can exceed $|U|-b$
  (verified); symmetry-reduced variant; pricing (coverage-bonus / Set-Union
  Knapsack; coupled-pair, McCormick); exact branch-and-price (IP $=\Zst$). Short
  per-config-vs-cluster MTZ remark (cluster-MTZ not exact). Cite Catanzaro2015,
  Laporte2004, daSilva2024, Colares2026*, Ryan1981, Goldschmidt1994.
- **§5 Computational study — TODO.** Verification (KTNS vs exact state-DP, 8000
  sequences, 0 disagreements; cross-solver agreement vs brute); experimental design
  (instance families, BBC ablation grid, PCF/PTF grid, empty-start KTNS comparison
  metric, root-LP-vs-optimum diagnostic). RESULTS deferred (campaigns running).
  §5.x competitiveness: Otiai strong-bound vs Moreira trivial-bound; the bound-limited
  conclusion. Cite Otiai2026, Moreira2026, daSilva2024.
- **§6 Conclusions & future directions — TODO (substantive).** Status summary;
  then future work: prove gap $\le\Kst-2$; PTF bound study and PTF as a general-GTSP
  device; reconcile the heuristic ratio theory with the published $3/2$-ratio claim
  (verify first); stronger SSP relaxations (cuts above $|U|-b$); online/competitive
  SSP; learning-augmented column generation (frame honestly as crowded). Note the
  scope overlap with the advisor's preprint for the meeting.
