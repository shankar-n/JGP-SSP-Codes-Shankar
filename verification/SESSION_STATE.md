# PROJECT STATE — read this first on any new session

**Last updated:** 2026-08-24
**Task:** rebuild `report/JGP-SSP_report.tex` end to end — correct, provenance-checked, in Shankar's voice.
**Deadline context:** presentation 2 September 2026. Report submitted to the university (comprehensive; length is not a constraint). Presentation must be concise.

---

## Read these, in this order

All live in `verification/` on Shankar's machine.

| File | What it holds |
|---|---|
| `SESSION_STATE.md` | this file — status, decisions, next actions |
| `REPORT_REBUILD_PLAN.md` | the agreed structure of the new report + style contract |
| `LINE_BY_LINE_FINDINGS.md` | mathematical + computational audit; the H vs H_walk frame error |
| `SOURCE_AUDIT_AND_WRITING_PLAN.md` | all 50 citations checked against sources; 16 problems |
| `CODE_AND_CAMPAIGN_AUDIT.md` | code verification + the new campaign result |
| `REPORT_AUDIT_2026-08-20.md` | first-pass defect list (E1–E11), superseded in part |
| `verify_report_independent.py` | re-runnable verifier, ~25 min, no CPLEX needed |
| `verify_output_2026-08-20.txt` | its output as of the audit |

---

## Status of the work itself

**Verified sound.** `compute_ktns` (83,670 instance/sequence pairs against two independent implementations, zero disagreements). Both lower bounds, the convention identity, thm:uncond, the zero-gap corollaries, cor:smallZ, cor:z3, prop:k3, prop:genk, prop:hk3, prop:noclutter, prop:chromK, prop:nonmatroid, prop:oddring for k≥4, thm:collapse (walk frame), PCF relaxation results. The PCF′/PTF code matches the report's formulations exactly. The Benders master is richer than the report states.

**Broken, with repairs identified.**
1. **The frame error.** `H` is defined twice: §2.3 = KTNS-evaluated heuristic; §3.1 = configuration-walk cost. Every k-ring has heuristic gap **0**; the walk gap is 1. Table 3.1, Example 2.3, prop:unbounded and the K*=4 witness are all walk-frame values labelled H. Repair: define both symbols; restate each result in its frame; reseed prop:unbounded with `I1 = ({0,1,3,6},{1,4,5,6},{2,4},{3,5})`, b=4 (verified gap = g at g=1,2).
2. **prop:oddring fails at k=3** (K*=1, not 2). Needs k≥4.
3. **"Smallest sub-optimal instance"** — false. Verified smallest: n=4, b=4, T=({0,1},{2,3},{0,2,4,5},{1,4,5,6}), K*=3, Z*=3, H=4.
4. **16 source-fidelity problems** — see `SOURCE_AUDIT_AND_WRITING_PLAN.md` §A.

**New results found during the audit, to be written up.**
- Positive heuristic gaps are rare (1 in 420 random instances), always size 1, always need b≥4.
- Open question created by the frame fix: *when does the KTNS step recover the optimum the walk model loses?*
- Crama et al. (1994) actually say KTNS **fails** under non-uniform tool costs while the LP stays exact — so the Benders subproblem extends to that regime. Scope extension, currently written as an error.
- Burger et al.'s degradation regime (gap grows as b exceeds job sizes) independently corroborates §3, and their closing paragraph poses the question §3.6 answers.

---

## The campaigns — ALL THREE FINISHED, analysed 2026-08-24

Full record in `CAMPAIGN_RESULTS_2026-08-24.md`. Re-derivable at any time with
`python3 verification/analyse_campaign_results.py --check`, which recomputes every
figure in §6 from the raw shards and compares it against what the report says. It
passes.

**BBC** — 120 shards, 16,994 runs, 12 configurations, 1,421 instances.
Cross-method agreement: 41,673 pairwise comparisons, **0 disagreements**.
Solved: SSPMF 1038, CATZ-F4 885, LSS 844 (of only 1,069 — see below), BBC-LP+T 727,
BBC-LP 726, BBC-K 725, then every `+F` variant below that.
Fractional cuts: 67.5M generated, node count down 20×, dual bound at termination
**higher on 0** instances, 67 solved instances lost.
Ablation vs `BBC-LP+F`: `+H` +31, `+C` −2, `+ACC` −3, `+P` −37, removing `+F` **+67**.
Coverage-bound split: BBC-LP 94% tight vs 40% loose; SSPMF 100% vs 87%.
427 runs failed; 352 of them LSS crashes, 239 on Laporte5, so LSS's rate is on a
biased subset and is flagged as not comparable.

**BNP** — 32 shards, 2,581 runs, 7 configurations, 469 instances. 507 proved optima,
**0 mismatches** against BBC. The result worth having: **PCF′ root LP = |U| − b on all
2,114 runs**, and **PTF exceeds it on 3 of 233** (A0-0, L11-6, L11-7, by one unit).
Nothing above 9 jobs closed — Python pricer, not the formulation.

**RL** — `src/BBC/rl_results/`, 6 sizes, one seed each. This is a **knapsack cover-cut**
study, not an SSP evaluation. Learned selection beats random by 46–73%. Reported as
such in §5.5 with the limits stated; §7.3 no longer claims SSP runs exist.

**Two analysis bugs found and fixed before anything was written down** (both in the
reading code, not a solver): the instance key must include the capacity (Crama reuses
file names across four capacities — keying without it manufactures disagreements), and
the coverage bound must use |U| not |T| (10 instances declare a tool no job needs).
Both are now documented inside the report, §6.2 / App. B / App. C.

---

## Decisions taken

- Modify rather than rewrite from zero — the mathematics survives; §2.7 and §5 get rewritten, everything else repaired. **Superseded 2026-08-20:** Shankar has asked for a full overhaul of every section including abstract, introduction and figures. Structure in `REPORT_REBUILD_PLAN.md`.
- Report is comprehensive; the *presentation* is where compression happens.
- Conjecture demotion: unverified §3 results become `\begin{conjecture}` with "Supporting argument" rather than "Proof".
- Keep the AI declaration; strengthen it with a verification appendix.
- `verify_report_independent.py` becomes a standing gate — extended whenever a claim is added, run before any draft circulates.

## Decisions taken 2026-08-20 (second round)

- **Voice: impersonal reporting register — no "I", no "we".** Passive or impersonal subject for narrative and experiments; standard impersonal mathematical constructions for theory. Authorship is made explicit in §1.3 and in the AI declaration, not in the prose elsewhere.
- **English only**, no French résumé. **Existing cover page retained.**
- **Integer-programming background section: keep and EXPAND**, with worked examples on SSP instances rather than generic ones. It doubles as Shankar's own revision material before the defence.
- Full overhaul of every section confirmed, abstract and figures included.
- **LaTeX styling: keep the existing report's exactly.** Shankar likes it. That means: the current preamble unchanged (12pt a4paper article, 1in margins, onehalfspacing, natbib numbers/sort&compress, the existing theorem environments and macros \Kst \Zst \U \confs \rset), the monochrome palette (cBlue/cOrange/cGreen/cRed/cPurple/cTeal all defined as HTML 111111, grayscale fills only), and the established TikZ idiom for grid figures: 0.8cm units, \footnotesize, `cBlue!20` for a tool held in the magazine, `cOrange!90` plus white crosshairs for an insertion, `black!35,step=1` grid, muted labels in `black!55`. New figures imitate `fig:ktns`. The existing cover page is retained.

## Open questions for Shankar

1. Page limits; report deadline distinct from 2 Sept; departmental template or mandated section order.
2. ~~Writing samples~~ — **received** 2026-08-20 (emails to Wagler, Colares, Chicoisne). Style profile derived in `REPORT_REBUILD_PLAN.md` §3b.
3. ~~His account of the work~~ — **received**; recorded in `ATTRIBUTION.md`. One point left open there: Colares proposed position-based formulations, but the June note credits Shankar with the fixed-polynomial-row-set device. Who proposed that refinement?
4. ~~Source for ρ ≈ 3–60~~ — **settled**: no source exists, it was AI-generated. The corollary is removed and Remark 4.2 replaces it.
5. Did he measure Catanzaro's F5 himself? The paper recommends F5 as best.
6. Colares citation status — Moreira's bibliography says "personal communication, 2024".
7. Is the Colares subtour-elimination invalidity his own finding or Moreira's? (The rebuilt §5.4 avoids the claim: it presents the MTZ non-exactness as this project's finding, with its own counterexample, and makes no claim about Colares' formulation.)
8. Which existing figures to keep.
9. Anything the advisors have already said about the current draft.

## Report rebuilt — 2026-08-20

The full report is written and delivered to `report/rebuild/` (17 source files + PDF +
`README_BUILD.md`, which lists every change and why). 74 pages, compiles with zero
errors, zero overfull boxes, zero undefined references or citations.

Structure as agreed: notation table, §1 introduction, §2 preliminaries with the two
frames and the expanded IP background, §3 state of the art rewritten from sources,
§4 the gap analysis, §5 exact methods, §6 the campaign, §7 discussion, §8 conclusions,
§9 AI declaration, appendices A (proofs), B (verification), C (reproducibility).

Attribution settled: position formulations including the fixed-row-set device are
Colares'. The ρ ≈ 3–60 value has no source and the corollary resting on it is removed;
Remark 4.2 states the spectrum in terms of the parameter instead.

It is committed to `report/rebuild/` rather than over `report/`, so the previous
version is untouched. Move it when ready.

## Report updated with the finished campaigns — 2026-08-24

Sections rewritten: abstract, §5.4, §5.5, all of §6, §7.1, §7.3, §8, Appendix B,
Appendix C. §6.6 (branch-and-price results) written from scratch — it was a placeholder
saying the runs were in progress. The full change list is the last table in
`CAMPAIGN_RESULTS_2026-08-24.md`.

Build: 78 pages, 0 errors, 0 overfull boxes, 0 undefined references or citations, all
Type 1 Latin Modern fonts (`lmodern` must be installed — without it pdflatex silently
falls back to Type 3 bitmaps and the text looks washed out on screen).

## Next action

The report is complete and submittable. What is left is not writing:

1. **Check `Calmels2018`.** The entry says 2018; volume 57 is 2019.
2. **Decide how to cite `Colares2026Exact`.** Moreira lists it as personal
   communication, 2024. Ask Colares.
3. **Read §6 once yourself before submitting** — it is the section the advisors will
   test you on, and every number in it is now defensible: run
   `python3 verification/analyse_campaign_results.py --check` and it re-derives all of
   them from the shards.
4. The presentation for 2 September still has to be built, and it is the opposite job:
   §6.5 (the coverage-bound split) and §6.6 (PCF′ = q on 2,114 runs) are the two slides
   that carry the whole story.

To preview a fragment in a container: a harness with the report's preamble (palette
included) and `\input{body}`; compile with `pdflatex -interaction=nonstopmode` twice.
`microtype` may need `[protrusion=false,expansion=false]` in a preview harness — that
change never applies to the real report.
