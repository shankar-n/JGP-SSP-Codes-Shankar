# The rebuilt report

Written 2026-08-20. This is a complete replacement for `report/JGP-SSP_report.tex`,
rebuilt end to end against the audit in `verification/`.

## Files

| File | Contents |
|---|---|
| `JGP-SSP_report.tex` | main file: preamble (unchanged from the original), cover page, and the `\input` list |
| `ch0_abstract.tex` | abstract |
| `ch0_notation.tex` | notation table and the two fixed conventions |
| `ch1_introduction.tex` | problem, internship, what was done, how to read |
| `ch2_preliminaries.tex` | SSP, KTNS, configurations, grouping, **the two frames**, bounds, conventions, expanded IP background |
| `ch3_state_of_the_art.tex` | literature, rewritten from the sources |
| `ch4_gap.tex` | the structural analysis |
| `ch5_exact.tex` | compact baselines, branch-and-Benders-cut, position formulations, the RL prototype |
| `ch6_computational.tex` | the campaign |
| `ch7_discussion.tex` | interpretation and limitations |
| `ch8_conclusions.tex` | conclusions and further work |
| `ch9_declaration.tex` | declaration on the use of AI |
| `appA_proofs.tex` | proofs |
| `appB_verification.tex` | how every claim was checked |
| `appC_reproducibility.tex` | how to reproduce the experiments |
| `references.bib` | bibliography, with the `daSilva2024` year corrected from 2021 |
| `cover/` | the three logos the cover page uses |

## Building

```
pdflatex JGP-SSP_report
bibtex   JGP-SSP_report
pdflatex JGP-SSP_report
pdflatex JGP-SSP_report
```

Compiles with zero errors, zero undefined references, zero undefined citations and
zero overfull boxes. 74 pages.

`build_local.tex` is a throwaway variant used only inside the container, where
`lmodern` is not installed and `microtype` font expansion is unavailable. Ignore it;
it is not part of the report.

## What changed from the previous version, and why

Every change traces to a finding in `verification/`. The substantive ones:

1. **The symbol `H` had two meanings.** §2.5 now defines `H_walk` (one magazine per
   group) and `H` (what the method returns after its KTNS step) separately, proves
   `H ≤ H_walk`, and shows an instance where they differ. Every result in §4 names
   the value it is about. Without this the report stated false things.

2. **The ring family has no heuristic gap.** Table 4.1 now has two gap columns. The
   6-ring, the running example, has walk gap 1 and heuristic gap 0.

3. **The unbounded-gap result is reseeded.** Ring copies give unbounded *walk* gap
   (Prop. 4.9, proved). A different seed gives unbounded heuristic gap
   (Obs. 4.7 + Conj. 4.2).

4. **The "smallest sub-optimal instance" claim is replaced** by the verified 4-job
   instance found by exhaustive search.

5. **New content in §4.4**: the census showing positive heuristic gaps are rare, size
   one, and require b ≥ 4 — and that this matches Burger et al.'s industrial finding.

6. **Literature corrections**: the zero LP relaxation credited to Laporte (not Tang);
   Crama's non-uniform-cost result stated correctly, with the consequence that the
   Benders subproblem extends to that regime; Catanzaro's recommendation of F5
   acknowledged and F4's use recorded as a limitation; da Silva's bound stated as
   `|T| − b` with its hypothesis; the 17.01% figure given its comparison basis;
   Burger's conditional conclusion and their open question, which §4.6 answers.

7. **The ρ ≈ 3–60 corollary is removed.** No source was found. Remark 4.2 states the
   spectrum in terms of the parameter and says calibration is open.

8. **§6 is rewritten from the new campaign**, including the fractional-cut result and
   the ablation.

9. **`Kashou2025` is introduced as the origin of the method**, which is what it was.

10. **Appendix B is new**: it describes the verification programme, so the AI
    declaration is checkable rather than asserted.

## Revision of 2026-08-24 — the finished campaigns

All three campaigns completed. Every number in §6 is now from a finished run, and every
one of them is re-derivable by `verification/analyse_campaign_results.py --check`, which
reads the raw shards and compares what it computes against what the report states.

1. **§6 is rewritten again, from the complete BBC campaign**: 1,421 instances (Crama was
   wrongly counted as 40 rather than 160), 12 configurations including `CATZ-F4`,
   16,994 runs. New solve table, new times table, new fractional-cut and ablation tables.

2. **Cross-method agreement is now a measured result**: 41,673 pairwise comparisons on
   999 instances, zero disagreements. §6.2 explains what had to be right for that check
   to mean anything — the instance key must include the capacity, because Crama reuses
   file names across four of them.

3. **§6.6 is written from scratch.** It said the branch-and-price runs were in progress.
   They are in: 2,581 runs, and the result that matters is that the PCF′ root LP equals
   the coverage bound on all 2,114 runs where it was recorded, while PTF exceeds it on
   three of 233. Proposition on PCF confirmed empirically; the PTF proposition confirmed
   and shown to be of little practical use as it stands.

4. **New open problem** (§5.4): is the excess of the PTF relaxation over `q` bounded by a
   constant? The measurement raises it and cannot answer it.

5. **§5.5 gains its measurement** — the learned cut-selection agent beats random selection
   by 46–73% on held-out knapsack instances — together with an explicit statement, kept
   in three places, that this is knapsack cover cuts and says nothing about the SSP.
   §7.3 previously claimed SSP runs were in progress. They never existed.

6. **A tool-counting correction.** Ten instances declare a tool that no job requires, so
   the coverage bound is `|U| − b` and not `|T| − b`. All coverage figures use `|U|`.

7. **Failed runs are reported rather than hidden.** 427 of 16,994 returned nothing, 352 of
   them LSS crashes concentrated on one family, so the LSS row is flagged as running on a
   smaller and harder denominator than the rest.

## Still open

- Page limits or a departmental template, if any.
- `Calmels2018` — the entry says 2018, but volume 57 is 2019.
- How to cite `Colares2026Exact` — Moreira's bibliography lists it as personal
  communication, 2024.
- Catanzaro's F5 was never implemented; F4 is the baseline, and §7.3 records it.
