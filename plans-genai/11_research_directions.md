# Research Directions — honest assessment (v2, 2026-06-10, Claude-Fable)

v1 of this memo was written bottom-up from Shankar's existing material and read
like advocacy. This version separates: what is publishable TODAY (almost
nothing), what becomes publishable IF a specific missing piece lands, and what
is genuinely unexplored INDEPENDENT of current work. Uncertainty is labelled;
items marked [LIT-DIVE] need a literature search I could not perform from here
— do NOT trust novelty claims for them until checked.

---

## Honest re-grading of the current-work directions (v1's A1–B3)

- **Gap/approximation theory of JGP+GSP** (was "A1, strongest"). Truth: the
  *proved* content so far is elementary (the unconditional ratio bound, K*<=2,
  the cost identity are all short arguments); alone it is a technical note, not
  an EJOR paper. It becomes a real paper ONLY with a proof of gap <= K*-2, or
  at minimum the K*=3 case for all b, or a counterexample (also publishable!).
  The honest pitch: best *bet* because the niche is empty (Calmels 2018 lists
  no worst-case analysis of this decomposition), not because current results
  suffice. Risk: the conjecture may be hard; the empirical perfection of the
  witnesses is suggestive, not evidence of an easy proof.
- **PCF/PTF formulations** (was "A2, most novel"). The fixed-poly-row property
  is real and clean; BUT the headline (PTF LP > |U|-b) rests on ONE tiny
  instance, position-indexed models for JOBS are textbook (Tang–Denardo,
  SSPMF), and PTF's O(n|V|^2) columns may be impractical. Needs: bound study on
  Tabela1C + a working branch-and-price before any submission. Currently a
  good chapter, not a paper.
- **Solver comparison BBC/LSS/SSPMF** (was "A3"). Not publishable standalone
  in a good venue (comparison of known formulations + one new solver), and now
  BLOCKED: the repo SSPMF is proven buggy (8.0 vs 6.0 on the 6-ring,
  2026-06-10). Internship-report material; fix SSPMF first.
- **ML directions** (was "B1/B2"). Learning-for-CG and solution-scoring are
  crowded areas; nothing in our notes is differentiated yet. Honest: do not
  plan publications here; revisit only if the benchmark data reveals a real
  learning problem (e.g. the extreme class imbalance of positive-gap
  instances).

## Genuinely unexplored directions (beyond current work)

1. **Approximability of the uniform SSP** — DOWNGRADED after the lit-dive
   (see results section below): a C&OR-2018 paper already claims 3/2-ratio
   heuristics for SSP, so this is a partially explored niche, not a first-word
   opportunity. Still open and respectable: verify/critique the 3/2 claim
   (relative to which bound?), inapproximability/APX-hardness, beating 3/2,
   and reconciling with our JGP+GSP ratio theory.
2. **SSP as paging with reorderable requests** — ANSWERED by the lit-dive:
   bounded-delay request reordering for paging exists with tight competitive
   bounds. The value is now technique-import (their machinery applied to SSP's
   free-reordering, set-valued-request cell), not a novel framing.
3. **Online SSP** — survey-confirmed gap (Calmels: online variant rarely
   studied). Competitive analysis against KTNS-paging machinery is well-matched
   to the existing toolkit here. Risk: trivial lower bounds may make it dull;
   a 1-week feasibility probe before committing.
4. **PTF as a general GTSP device**. Nothing in PTF's construction is
   SSP-specific except the metric: position-transition columns + per-element
   consistency rows apply to ANY GTSP with overlapping clusters. If the
   LP-strength phenomenon survives in the general setting, the audience and
   venue jump from SSP-niche to general combinatorial optimisation. Cheap to
   test (same scipy harness, random GTSP instances).
5. **Multi-machine SSP / tool wear / non-uniform setup times** — all
   survey-confirmed gaps, but modelling-heavy and far from the current
   toolkit; mention to the advisor, do not self-start.

## Lit-dive results (2026-06-10, live web search — corrects the [LIT-DIVE] items)

1. **SSP approximability is NOT virgin.** A Computers & OR (2018) paper
   ("Improved heuristic algorithms for the JSSP/tool switching") claims three
   heuristics with WORST-CASE RATIO 3/2 for the SSP. Action: obtain and read
   critically — relative to which lower bound? is the proof sound? (our gap
   machinery says ratios interact subtly with conventions). Remaining open:
   inapproximability/APX-hardness, beating 3/2, and reconciling with our
   JGP+GSP ratio theory (our conjectured heuristic ratios 2-2/K* vs their 3/2).
   Downgraded from "first word on the problem" to "respectable open questions
   in a partially explored niche".
2. **Paging with request reordering EXISTS** in the online-algorithms
   literature: bounded-delay reordering of paging requests has tight bounds
   (k+O(1) deterministic, O(log k) randomized). SSP = free reordering +
   SET-valued requests; that exact cell may still be open, but the framing is
   not novel. Value shifts from "new connection" to "import their techniques".
3. **LLM-serving scheduling theory is ACTIVE and crowded** (2024-2026):
   competitive KV-cache scheduling (constant-ratio offline batch; Omega(sqrt p)
   online lower bounds; Jaillet et al.), cache-aware request scheduling with
   2-approximations, and systems (S-LoRA, dLoRA, Punica, EdgeLoRA) that do
   adapter paging/clustering HEURISTICALLY. The specific cell "adapter-SET
   swap-cost sequencing/batching as weighted (online) SSP with guarantees"
   still appears open — S-LoRA's adapter clustering is an unanalysed
   JGP-style heuristic — but the window is short and a systems-grade
   evaluation (or collaborator) is needed. Verdict: still the best
   impact-per-effort candidate, entered with speed, NOT an empty field.

## What this means concretely
1. FIX SSPMF (blocking; also the convention story depends on it).
2. Run the K*=3 proof attempt (2 weeks max, timeboxed) — it decides whether
   the gap-theory paper exists.
3. DONE (2026-06-10): both lit-dives executed — see "Lit-dive results" above.
   Follow-up: obtain and critically read the C&OR-2018 3/2-ratio paper.
4. PTF: Tabela1C bound study + the general-GTSP probe (4) before believing v1's
   enthusiasm.
5. Advisor conversation: Colares' preprint overlaps Parts II/III/X — scope
   split before any formulation writing.
