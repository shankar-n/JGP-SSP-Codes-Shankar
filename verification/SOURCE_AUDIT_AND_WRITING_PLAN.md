# Source audit of every citation, and the plan for the report

2026-08-20. Companion to `LINE_BY_LINE_FINDINGS.md` (mathematics and computation) — this file covers the literature.

## Method

All 50 distinct citation keys extracted from the tex, matched to `references.bib`, matched to PDFs in `references/` (including `To read/` and `Useless/`, which turn out to hold several of the primary sources). Text extracted and every claim the report attributes to a source read against that source. 18 sources verified directly; the rest are background citations (methodology textbooks, standard algorithms) whose use is unobjectionable and which I did not chase.

---

## A. Claims that do not match the source

**A1. The zero LP relaxation is Laporte's finding, not Tang & Denardo's.**
Report l.756–761: *"Their paper [Tang & Denardo] is also the source of two facts this report leans on … and the observation that their own integer formulation has a linear relaxation identically zero."* Also tab:lineage, l.897.
Tang & Denardo's paper does not discuss its LP relaxation at all. Laporte et al. (2004) prove it: *"is always equal to zero. Indeed the solution $u_{jk}=1/n$ …"*.
Note: `VERIFIED_FACTS` records this exact error being found and corrected in the 2026-06-10 session ("01–03 corrected (LP-collapse citation → Laporte2004)"). It has **regressed** into the report.

**A2. Crama's non-uniform-cost result is stated backwards — and the correct version strengthens your work.**
Report l.766–769: *"gave an interval-matrix proof of KTNS's optimality that extends to arbitrary per-tool switching costs."*
Crama et al. actually write: with non-identical setup times *"the greedy algorithm of Hoffman et al. (1985) **and KTNS are no longer valid**. However, the matrix $(m_{jk})$, being an interval matrix, is totally unimodular … the tooling subproblem can still be solved in polynomial time in that case, by simply solving the linear programming relaxation."*
So KTNS **breaks** under non-uniform costs; what survives is polynomial solvability via the LP. This is worth more than a correction: your Benders subproblem (§4.2) *is* that LP. It therefore remains exact and polynomial for non-uniform per-tool switching costs, where the KTNS-based framing of the whole SSP literature does not apply. That is a genuine extension of scope your report currently gives away.

**A3. Catanzaro et al. recommend Formulation 5; the report says it is unusable, with no source.**
Report l.1755–1760 justifies the F4 baseline partly by *"F5's tighter relaxation is so large that at the $n=40$ benchmark sizes even its root linear relaxation does not complete."*
The paper reports F5 solving **more** instances than F4 (10 vs 7–9), solving **all** of datA2 where F4+valid-inequalities could not, and its conclusions *"suggested Formulation 5 as the best ILP formulation"*. (The other half of the report's justification is exactly right and matches the paper: *"We excluded from the analysis Formulation 3 as it provides the same lower bounds as Formulation 4 and contains more variables and constraints."*)

**A4. Burger et al.'s conclusion is conditional, and its condition confirms your theory.**
Report l.860–864 says they measured the suboptimality and *"it is small on their instances."*
They write: *"We concur, especially in cases where the largest job size is only slightly smaller than the magazine size. **However, as the difference between the magazine size and the largest job size grows, the quality of solutions uncovered by this heuristic solution approach decreases.**"*
That degradation regime is precisely what §3 predicts (rem:bdep; every positive-gap witness found in the computational audit needs $b\ge4$). Independent industrial corroboration is being cited as though it said the opposite.

**A5. Burger et al. pose the setup-cost question that §3.6 answers, and the report does not say so.**
Their closing paragraph: *"It would be interesting to contrast the trade-off between minimizing the number of tools changed and the number of times tools are changed … for varying values of the setup times."* That is thm:collapse and lem:lowrho. Answering an explicitly posed question from the applied literature is a stronger claim than the report currently makes for itself.

**A6. da Silva's bound is $M-C$ under an explicit hypothesis, not $|U|-b$.**
prop:sspmf-lp (l.1765) states it as $|U|-b$ and attributes it to them. The paper: *"a LP relaxation lower bound equal to the number of tools minus the tool machine's capacity"*, justified by *"There is a total of $M$ tools **that are all needed** for processing the jobs."* Moreira's thesis independently restates it as $M-b$ with the same hypothesis. The identification $M=|U|$ is that hypothesis, and the report never states it. `VERIFIED_FACTS` separately records the repo's SSPMF root LP measuring 2.0 against the paper's 3 on the 6-ring, unresolved — so this is not pedantry.

**A7. The 17% figure has no stated basis.**
Report: *"solves some 17% more of the standard instances than any predecessor."* Paper: 17.01% more than the models of Tang & Denardo, Laporte et al. and Catanzaro et al., on the datasets of Yanasse, Rodrigues and Senne (2009). Neither baseline nor instance set is currently given.

**A8. tab:methods overstates a hedged source, and omits the convention.**
The table asserts F4 and LSS relaxations are *"below $|U|-b$"*. da Silva say prior models are below $M-C$ *"in the great majority of the cases"*; Laporte's own paper shows the LSS relaxation strengthening as capacity tightens. Separately, Moreira records that Catanzaro's objective counts the initial magazine load, so *"all of the obtained values with it will be $b$ switches above"* the others — the table compares relaxation values across formulations without stating which convention each uses, which is the exact trap §2.6 exists to prevent.

**A9. Calmels' survey does not say what it is cited for.**
Report l.252–254: *"the survey literature records the heuristic's empirical success and its missing guarantee side by side."* The survey mentions job grouping twice, descriptively, about Burger et al. It contains no worst-case discussion. What it *does* contain, and what would genuinely support the report: *"It is surprising that only a few authors propose decomposition methods to solve the SSP and more general models."*

**A10. Privault & Finke do not report a setup-to-switch ratio of 3–60.**
cor:manufacturing (l.1605–1609) states *"the setup-to-switch ratios $\rho\approx3$–$60$ reported for real tooling"* and concludes from it that the two-phase heuristic is exactly optimal on real instances. Privault & Finke (1995) contains no such range — its numbers are magazine capacities (~30 tools, >100 for drums/chains) and a shop with 1,800 distinct tools. Privault & Finke (2000) is not in `references/` and could not be checked. **A Corollary currently rests on a number I cannot find in either cited source.**

**A11. Moreira does not correct Colares' subtour elimination.**
Report l.2015–2020: *"As first stated, however, its subtour elimination is invalid; the correction of Moreira, through the classical Dantzig–Fulkerson–Johnson subtour-elimination constraints, restores exactness."* Moreira presents the Colares formulation with a generalised subtour-elimination family already in it (his constraint 2.6, separated lazily) and nowhere calls the original invalid. The invalidity result in your own records is about the *cluster-aggregated MTZ*, which is your finding, not Moreira's.

**A12. The Colares citations claim a publication status the sources do not support.**
`Colares2026Exact` and `Colares2026Tool` are cited as 2026 works, four and one times. Moreira's bibliography — he is co-advised by Colares — lists it as *"R. Colares, M. C. de Souza, and A. Wagler. Personal communication. 2024."* Your own `ssp-literature` skill flags the preprint as un-citable pending your confirmation. Since Colares is your advisor this is easy to settle, but it must be settled.

**A13. The da Silva year is genuinely ambiguous and needs deciding, not guessing.**
The bib says 2021; the key says 2024; the PDF is *"Compiled May 16, 2024"*; Moreira cites it as *da Silva et al. (2021)*. Both are probably right for different versions. Pick one, state it, and make key, bib and tab:lineage agree.

**A14. §7's exact pairwise bound is Tang & Denardo's idea, uncredited.**
§7 proposes *"solving the pairwise bound to optimality (a travelling-salesman path over the $w_{ij}$)"* with no citation. Tang & Denardo already propose exactly this: they define $LB(i,j)$ and observe that the shortest Hamiltonian path under those weights lower-bounds the optimum.

**A15. Your own knowledge files are wrong where the report is right.**
`CLAUDE.md` and `skills/ssp-literature` both credit the ARF job-grouping formulation to Catanzaro et al. 2015. That paper contains zero occurrences of "grouping", "representative" or "batch". The report's citation to Jans & Desrosiers is correct. Fix the knowledge files, not the report.

**A16. Unverifiable locally.** `felipe-thesis.pdf` (Otiai2024, five citations including the performance claim *"closes in seconds instances the compact model cannot"*) has no text layer. Privault2000 is not in `references/`. Legrand2025, Akhundov2024, Mecler2021, Jans2013, Crama1994Column and Goldschmidt1994 are cited for substantive claims but are not in `references/` at all.

## B. Claims verified as accurate

Tang & Denardo: KTNS optimality and $O(MN)$ complexity; the pairwise bound $LB(i,j)$; the shortest-Hamiltonian-path bound. Crama et al. 1994: NP-hardness for every fixed $C\ge2$ via a minimum-length travelling-salesman path in the edge graph; the seven modelling assumptions. Laporte et al.: the LSS formulation and its valid inequalities; branch-and-cut on eight-job instances; branch-and-bound to 25 jobs; GENIUS as the upper-bound source. Catanzaro et al.: F3 and F4 share a relaxation, F4 is smaller. da Silva et al.: no lazy constraints; the symmetry-breaking constraint; 17.01%. Ghiani et al.: the reversal-symmetry property, and their own caution that it does not make the problem symmetric. Crama et al. 2007: strong NP-hardness by 3-partition, polynomial for fixed capacity. Hertz et al.: GENI/GENIUS. Muter et al.: column-dependent rows. Burger et al.: the decomposition, unicost set covering, Stirling-number enumeration. Moreira: the configuration approach and the $M-b$ bound.

---

# The plan

## Modify, not rewrite

The verification supports keeping the document. The mathematics of §3 is sound — 40 of 53 independent computational checks pass, and the failures are all one labelling error, not wrong theorems. §4's formulations verified clean. The defects are concentrated: a frame error running from §2.3 into §3, a related-work section written at one remove from the sources, numbers without provenance, and results claimed beyond what was shown. Those are repairable in place. Rewriting from scratch would discard verified work and re-introduce risk in the parts that are currently correct.

Two sections are exceptions and need rewriting rather than repair: **§2.7 (Related work)**, where nine of the sixteen source problems live and the prose is built around characterisations rather than claims, and **§5 (Computational study)**, which per your own `RESEARCH_PLAN` must be re-derived from the new-protocol campaign and cannot be fixed before it lands.

## Section verdicts

| Section | Verdict | Why |
|---|---|---|
| Abstract | Rewrite last | Currently asserts the frame-dependent refutation and unboundedness as facts about the heuristic; must follow the corrected body |
| §1 Introduction | Repair | Frame claims in Contributions; the Calmels characterisation (A9); provenance |
| §2.1–2.6 Preliminaries | Repair + one addition | Sound. Needs $H$ and $H_{\text{walk}}$ defined here, once, with the instance where they differ |
| §2.7 Related work | **Rewrite against sources** | A1–A9, A12–A14 concentrate here |
| §3 Structural analysis | **Restructure, keep the theorems** | Every result verified in its own frame; re-anchor to the right one, repair prop:unbounded with the $I_1$ seed, fix prop:oddring's $k\ge4$, replace the "smallest instance" claim, add the census result |
| §4.1–4.4 Exact methods | Repair | F5 justification (A3), prop:sspmf-lp statement (A6), tab:methods (A8), the master row that omits the depot term the code carries, Colares/Moreira attribution (A11) |
| §4.5 RL prototype | Demote to a paragraph | Built, never evaluated on the SSP; its only number comes from a different problem |
| §5 Computational | **Hold, then rewrite** | Blocked on the campaign; protocol description is stale |
| §6 Conclusions | Rewrite last | Derives from §3 and §5 |
| §7 Remaining work | Repair | Resolve the contradiction with §5 about whether the re-run is finished; credit Tang for the pairwise-path bound |
| Appendix | Extend | New proof for the repaired prop:unbounded; prop:oddring hypothesis |

## Order of work

**Step 1 — the frame.** Define $H$ and $H_{\text{walk}}$ in §2.3; restate every §3 statement in the frame it was proved in; repair prop:unbounded with the $I_1$-copy family and prove the tool-disjoint decomposition lemma KTNS needs; fix Example 2.3 and Table 3.1; replace the false "smallest instance" claim with the verified four-job witness; add the census finding that positive heuristic gaps are rare, size 1, and need $b\ge4$. This changes what the report claims, so it goes first and alone, and you review before anything else moves.

**Step 2 — §2.7 rewritten from the sources.** Each paragraph rebuilt from what the paper says, with its qualifications: Laporte's zero-relaxation result attributed to Laporte; Crama's non-uniform-cost result stated correctly and its consequence for your Benders subproblem drawn out; Catanzaro's F5 recommendation acknowledged and your own contrary measurement reported as yours; Burger's conditional conclusion and its agreement with §3; Burger's open question identified as what §3.6 answers; Calmels cited for the decomposition gap she actually names; Colares' status settled.

**Step 3 — §4 repairs.** prop:sspmf-lp restated as $M-C$ with the all-tools-used hypothesis and the $|U|$ identification made explicit; tab:methods hedged to match its sources and given a convention column; the Benders master stated as implemented, including the depot-load term; the Colares/Moreira attribution corrected or reassigned to you; §4.5 demoted.

**Step 4 — provenance.** Every number states its source: which family and parameter range for enumerations, which instance set and baseline for literature figures, which script for computed ones. Complete enumerations state the family completely; non-exhaustive searches are described as such and carry no count. cor:manufacturing either gets a real source for $\rho$ or becomes a conditional statement with $\rho$ as a parameter.

**Step 5 — proportionate claims.** Abstract, contributions and conclusions carry only what was established. Work done without a conclusion is recorded once, plainly, in the body.

**Step 6 — terminology.** One term per concept, taken from the literature's own usage (*bound-tight*/*bound-loose*, *linear relaxation value*, *coverage bound*); symbol collisions resolved; conjecture demotion applied uniformly so the abstract, §3 opener and §6.1 status lists agree.

**Step 7 — §5 and §6** when the campaign lands, per your `RESEARCH_PLAN` TODO.

**Step 8 — re-verify.** Re-run `verify_report_independent.py` against the revised text and extend it to cover the new statements; every check passes or is a documented, intentional contradiction.

Each step arrives as a diff. Steps 2–6 are independent of one another and can be reordered to suit you.

## What I need from you

1. **The running example.** The 6-ring appears in eight figures but has zero heuristic gap. Keep it as the walk-model illustration and add the four-job witness for the heuristic gap (my recommendation — it costs least and makes the contrast the point of §3), promote the four-job witness throughout, or keep the ring and state plainly that its heuristic gap is zero.
2. **The $\rho\approx3$–60 source** (A10) — do you have it, or should cor:manufacturing become conditional?
3. **Colares' citation status** (A12) — you can ask him directly.
4. **The F5 claim** (A3) — did you measure F5 yourself? If so I will report your measurement; if not, the justification has to change.
5. **The Moreira/Colares subtour attribution** (A11) — is the invalidity your finding or theirs?
6. **§5** — hold all campaign numbers until the re-run, or report the old protocol explicitly labelled?

## Suggestions for your token budget

- Commit `verify_report_independent.py` to `verification/` as a standing gate; it re-runs in ~25 minutes with no CPLEX and needs no re-derivation.
- Correct `CLAUDE.md` and `skills/ssp-literature` (A15, plus A1 which the skill gets right and the report gets wrong) so future sessions inherit the fixes rather than rediscovering them. I can produce both edits.
- Step 1's new lemma is the only genuinely expensive item; it is worth a dedicated session or a subagent whose sole output is the proof.
