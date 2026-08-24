# Revision plan v2 — answering your four replies

Supersedes the "Proposed procedure" section of `REPORT_AUDIT_2026-08-20.md`. The 11 defects (E1–E11) in that file stand unchanged; this file is about *how* to fix the four systemic problems you named.

---

## D4 first, because you asked what is going on

**"Style trim" was my bad name for it, and the 5–7 pp figure alarmed you for a good reason — it sounded like I was going to delete content. I am not.** Nothing that carries information leaves: no theorem, proof, definition, figure, table, number, or citation. What shrinks is the number of *words spent per fact*.

Here is where the 5–7 pp actually comes from, measured, not guessed:

| Source | Measured now | After | Saves |
|---|---|---|---|
| Repetition of one thesis | The claim "compact relaxations stop at $\lvert U\rvert-b$, our methods aim past it" is restated **14 times** (abstract, §1 ×3, §2.7 ×2, §4 opener ×3, §4.1, §4.4 ×2, §5, §5.3, §6.1, §7) | stated once in §2.5, referenced elsewhere | ~1.5 pp |
| Tutorial primers | 6 paragraphs, **113 source lines**, explaining ILP, LP relaxation, branch-and-bound, cutting planes, duality, Benders, column generation from scratch | kept but compressed to the parts a reader of an OR internship report does not already know | ~1.5 pp |
| Rhetorical connective tissue | "exactly" ×66, "precisely" ×12, "The intuition is that…" ×3, plus one-off flourishes | removed | ~2 pp |
| Redundant restatement inside proofs and captions | captions that re-explain the body text | trimmed | ~1 pp |

**And here is the part that matters:** this is not a separate cosmetic pass. It is *the same fix* as your D3 complaint. The report is long precisely because it says things in loose English instead of in technical terms — and loose English takes more words and says less. Compressing it and making it technical are one operation. Worked example, real text from §2.7:

> **Now (108 words).** "More recently, da Silva et al. gave a multicommodity-flow model that needs no lazy constraints and solves some 17 % more of the standard instances than any predecessor, and whose relaxation they prove equals exactly $\lvert U\rvert-b$. That last fact is the ceiling. The strongest compact relaxation produced in twenty years coincides with the elementary coverage bound of Proposition 2.7 — the very quantity Section 3 shows to be the optimum on a large part of the instance space and a strict underestimate on the rest. The compact literature has, in effect, climbed to the coverage bound and stopped; the two methods of Section 4 are chosen precisely to get past it."

> **After (71 words).** "da Silva et al. give a multicommodity-flow model that requires no lazy constraints and prove that its linear relaxation equals $\lvert U\rvert-b$; they report solving 17 % more instances of the Catanzaro suite than F4 [exact comparison to be taken from their Table N]. That value is the coverage bound of Proposition 2.7, so the strongest compact relaxation in this lineage is no stronger than an elementary counting bound. The methods of Sections 4.2 and 4.4 are selected to obtain bounds that do not reduce to it."

What changed: "the ceiling", "in effect, climbed … and stopped", "that last fact", "precisely" are gone; "17 % more than any predecessor" — a number with no stated comparison — is given its comparison; "produced in twenty years" (rhetorical) becomes "in this lineage" (factual); "get past it" (vague) becomes "obtain bounds that do not reduce to it" (a checkable statement). Shorter *and* more technical, same content.

**If you want to see this on a real section before committing:** I will do §2.7 (Related work, ~2.5 pp) as a sample, send you the before/after diff, and you decide whether to apply it to the rest. That is my recommendation and it costs almost nothing.

---

## D3 — terminology: what is actually wrong

Your phrase "word salad without meaning anything technical" is accurate, and it has three distinct causes. They need three different fixes.

**(a) Metaphor standing in for a technical term.** The report has a private vocabulary that is never defined and never used the same way twice:

| Report says | Occurrences | Should say |
|---|---|---|
| the bound "is tight" / "is loose" | 7 / 6 | $\lvert U\rvert-b = Z^*$ / $\lvert U\rvert-b < Z^*$ — define once as *bound-tight* / *bound-loose instance*, then use only that |
| relaxations "collapse to", are "stuck at", "go slack", "adrift" | 4 | the relaxation *value equals* / *is strictly below* |
| the method "gets past", "breaks past", "reaches past" the bound | 5 | the relaxation value *strictly exceeds* $\lvert U\rvert-b$ |
| "bound-limited rather than implementation-limited" | 3 | used as a headline conclusion but never defined; needs a one-line definition (failure with incumbent $=Z^*$ and dual bound $<Z^*$) at first use |
| "the wall", "the ceiling", "the hinge", "the weak link" | 4 | delete; name the quantity |
| the conflict-graph row "bites" / "carries no load" | 2 | *is binding on* / *is not used by any other result* |
| "does real work beyond the root relaxation" | 1 | "closes a strictly positive root gap by branching" |
| KTNS "does its work", "what the rule buys", "the entire content of" | 3 | delete; the worked example already shows it |

**(b) The same object under several names** — the two-phase heuristic has 5 names, the campaign 4, the Benders cut families 2 each, tool count is both $m$ and $\lvert T\rvert$, groups are also "batches". Full table in §4 of the audit file; it is mechanical once you approve it.

**(c) Symbol collisions and the $H$ problem.** $\rho$, $\gamma$, $\pi$, $\theta$ each denote two different things in different sections. Worse, **$H$ is defined twice with different meanings** (audit E6): §2.3 defines it as the KTNS-evaluated heuristic cost, §3.1 redefines it as the configuration-walk cost, and §3.4 then introduces $H_{\text{walk}}$ for the second one. So §3.1–3.3 prove things about $H_{\text{walk}}$ while writing $H$. This is not a style problem — it is why the abstract currently states something false about the refutation (E2). Fixing $H$ is the single highest-value edit in the report.

**Conjecture demotion (your answer):** agreed, and it interlocks with the above. Unverified results become `\begin{conjecture}` with the derivation printed as "Supporting argument"; verified ones keep Theorem/Proposition. One partition, generated once, used identically in the abstract, the §3 opener, and §6.1 — currently those three lists disagree with each other (E7).

---

## D1 — numbers without provenance

Your rule, as I read it: **either the enumeration is complete over a precisely stated family, in which case say the family and the count; or give no count at all.** And more generally: no number appears without saying where it came from.

Applying that rule, sorted by verdict:

**Keep — complete enumeration of a defined family, once the family is stated in full:**
- 10,691 — currently "the $b=3$ two-tools-per-job family with $m\le6$". Per `VERIFIED_FACTS` this is the *complete* set of instances with $\lvert T_j\rvert=2$ for all $j$, $b=3$, $m\le6$, $n\le6$. State it that way and it becomes a mathematical statement.
- 21,569 / 2,410 (l.722) — complete for $b=3$, job sizes $\{2,3\}$, $m\le5$, $n\le5$. The report currently omits the $m,n$ bounds, which is what makes it look arbitrary.
- 1,421 (l.127) — you are right that it is fine *as a count of instances*, but as printed it has no provenance and, recounted from `benchmark_config.py`, the globs match 1,445 files (E9). Fix: re-derive from the harness and state it as "the 1,4xx instances of the Catanzaro, Crama and Laporte families listed in §5.1".

**Drop the number, keep the claim (not complete enumerations):**
- "several thousand instances we tested" (abstract l.112, §3 opener l.968) — a sample, not a family.
- 6,065 (l.1203) — described as "a further", ambiguous whether it is complete.
- "directed hunts across $b\in\{3,4,5\}$, $K^*\in\{3,4,5\}$" and "520 perturbations" — directed search, by construction not exhaustive. Restate as "no counterexample is known" with the search described in one clause, no count.
- "in exhaustive sampling" (l.1342) — contradiction in terms; either exhaustive over a stated family or a sample.

**Numbers with no source at all — get provenance or get cut:**
- 60 % RL bound improvement (l.2255) — no entry in `VERIFIED_FACTS`; also a candidate for D2 below.
- 24 % non-integral, 4.9 average lift, "under one per cent" (§7, l.2567–2590) — real (they are in `VERIFIED_FACTS`, 07-16 and 07-17 blocks) but printed in §7 with no statement of the instance set they range over.
- 48.0 % (l.370) and every §5/§7 campaign number — verified by `verify_19971.out` against the *old* protocol CSVs. Per your `RESEARCH_PLAN` TODO these must not be carried into the new-protocol report at all (E8).
- 17 % (da Silva, l.797) and "$\rho\approx3$–60" (Privault, l.1607) — from the literature; need the specific comparison and table cited, not a bare percentage.
- "$25$-job instances" for Laporte's B&B (l.785) — from the paper, fine, but should say on which family.

This is the answer to "so many problems like this in the report right": yes — **16 numeric claims, of which 3 have full provenance as printed.** The pass makes provenance a hard rule.

---

## D2 — hanging work presented as achievement

Your framing is right and I'd propose a three-tier rule rather than delete/keep:

- **Tier 1 — abstract, contributions, conclusions.** Only results that are *settled*: a proved theorem, a verified computation with a stated conclusion, or a built artifact with a measured outcome. Nothing else appears here at all.
- **Tier 2 — body, stated factually.** Work done that yielded no conclusion is described in one or two plain sentences where it belongs, with no evaluative language, and explicitly labelled as not yet evaluated. Not showcased, not hidden.
- **Tier 3 — §7 Remaining work.** Anything whose only content is a future question.

Sorting the current material by that rule:

| Item | Now | Proposed |
|---|---|---|
| §4.5 RL cut-selection prototype (2.5 pp, own subsection + §6.2 paragraph + §7 mention + contribution-adjacent framing) | presented as a capability with "a verified learning core and a ready integration path"; the one number (60 %) is from a *different* problem (knapsack cover cuts), not the SSP | **Tier 2**: one short paragraph in §4 — a prototype was implemented following Tang et al., validated on knapsack cover cuts, not evaluated on the SSP. Drop the subsection, the §6.2 paragraph, and the "ready integration path" language. |
| Contribution bullet 3 "the computational instrument" (l.368) | claims a *complete* benchmark, quantifies 48.0 %, and says it "demonstrates mechanically" that the methods are bound-limited | **Tier 1 only if the campaign has landed.** Today §5.2 says the opposite (E8). Until the re-run merges, this bullet states what was *built* (harness, reimplemented baselines, uniform protocol), not what was found. |
| §5.2 "provisional observations" | four sentences of hedged findings on the easiest instances, immediately after a paragraph saying nothing can be concluded from them | **Tier 2**, cut to one sentence, or removed with §5.2 reduced to the protocol statement. |
| §4.3 four accelerations (fractional cuts, HGS primal, conflict-graph row, Pareto lifting) | 4 pp, each with a paragraph of motivation and intuition; none has a measured effect | **Tier 2**: keep the definitions (they are real implemented methods and belong in the methods section), cut the motivational framing, state plainly that campaign-scale evaluation is pending. Saves ~1.5 pp. |
| §4.3 conflict-graph row "kept because it is exactly the lever the structural analysis predicts" | self-justifying | **Tier 2**: state what it is and that it is dominated by the coverage bound on most instances. |
| §7 "The corrected Benders master" claiming a completed re-run with outcomes | contradicts §5 (E8) | Resolve E8 first; then Tier 1 or Tier 3 depending on which protocol's results you are reporting. |
| §3 open-problem remarks (rem:bdep etc.) | inside the theory section | Legitimate in a theory section. **Keep**, but as short statements, and make sure §7 does not repeat them. |
| §6.2 "Beyond the project horizon" | three paragraphs of future directions | **Keep** — conventional and appropriate for an internship report. Trim the RL paragraph per row 1. |

Net: roughly 4 pp of showcase prose becomes about 1 pp of factual record, and the abstract stops claiming things §5 disowns.

---

## Revised pass order

Passes are ordered so the cheap high-value corrections land first and nothing is redone.

1. **Correctness (E1–E11).** Includes the $H$/$H_{\text{walk}}$ split, the walk-frame qualifier on the refutation, the E8 stale-July resolution, prop:oddring's $k\ge4$, and the conjecture demotion with one status partition. → diff for you.
2. **Sample style+terminology pass on §2.7 only.** ~2.5 pp, before/after. You approve or adjust the register. → diff for you.
3. **Terminology, report-wide.** The approved tables (a)/(b)/(c). Mechanical; grep audit afterwards. → diff.
4. **Provenance + D2 retiering.** Every number gets its source or goes; Tier 1/2/3 sorting applied. → diff.
5. **Prose pass, report-wide,** at the register you approved in pass 2.
6. **Verification.** (i) line-by-line mathematical replay with a written check-log; (ii) an independent brute-force verifier script committed to `verification/`, recomputing every small-instance claim from scratch (no CPLEX needed) and printing PASS/FAIL per report claim.
7. **Rebuild both draft-switch versions**, page/log check, consolidated diff.

**Token economy.** Passes 1, 3, 4 are surgical and cheap. Pass 6(i) is the expensive one — I recommend running it as a dedicated subagent whose only deliverable is the check-log, so the derivations never enter this session's context. Pass 6(ii) is cheap and permanent: the script re-runs any time and never needs re-derivation. I also suggest writing the approved terminology and provenance rules into a `skills/report-conventions/SKILL.md` in the repo, so no future session re-derives them or drifts back — I can produce that file for you to save.

**What I need from you to start:** nothing for pass 1 (E1–E11 are defects, not choices) except one call — for E8, are we reporting the old-protocol campaign results (labelled as such) or holding all campaign numbers until the re-run merges? Everything else can proceed and be reviewed as diffs.
