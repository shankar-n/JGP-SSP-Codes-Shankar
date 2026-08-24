# Where you actually stand, and what to do about it

Written after reading the archive (`_archive/2026-08/plans-genai`, `_archive/2026-08/verification-scratch`) alongside the live report, the verification records and the sources.

---

## 1. First, the thing you should know before anything else

I found the origin of two of the errors, and it changes how you should read this situation.

**The ρ ≈ 3–60 number.** In June, the working document `07_collapse_variants.tex` carried this note:

> `%% TODO-VERIFY: the numeric ranges above were attributed to Privault1995; I could not verify they appear there — treat as illustrative until a source is found (cite removed pending check; ask the advisor for a practical reference on magazine setup vs tool change times).`

The citation was **removed** there, correctly. In the report it is back, with `\citep{Privault1995,Privault2000}` restored, and promoted into a Corollary about real manufacturing practice. I read Privault & Finke (1995) — the number is not in it.

**The zero LP relaxation.** In June, `01_foundations.tex` was corrected with:

> `%% TODO-VERIFY: citation corrected — the LP=0 proof for the Tang–Denardo model is due to Laporte, Salazar-González & Semet (2004), §2.1, not Tang1988/Catanzaro2015.`

The report credits it to Tang & Denardo.

**What this means.** The problem is not that the work was done carelessly. There was a real audit in June that found and fixed dozens of things — the `TODO_VERIFY_INDEX` lists over fifty corrections, many of them substantive. What failed is that the report was written *afterwards*, from the ideas rather than from the corrected documents, and it **re-introduced errors that had already been caught**. Corrections lived in the archive and died there.

That is a process failure with a mechanical fix, and it is much better news than "the work is unreliable."

Same story with the frame error. The July session found the $H$ vs $H_{\text{walk}}$ conflation and wrote `verify_frame_audit_witnesses.py` to check it — but that script only tests the two $b=5$ witnesses W1 and W2. The rings were never put in it. The note says *"believed frame-safe … re-verify when recommitting scripts."* Nobody did. One missing test case, and a false headline result survived into the report.

---

## 2. What the project actually is

Strip away the prose and it is four questions, and they are the four your advisors actually asked. From `08_research_notes.md`, "Advisor Directions and Open Questions":

| Advisor's question | Where the project answers it | State |
|---|---|---|
| **Q1** Worst-case examples for the two-phase heuristic at fixed $K^*$ and $b$; a tight bound, not just for growing $K^*$ | §3.3–3.4 (worst-case guarantees, the $K^*=3$ analysis) | Theorems verified; **stated in the wrong frame** — repairable |
| **Q2** Grouping selection: enumerate JGP solutions, do sub-optimal groupings ($K>K^*$) ever help? | §3.7 | Posed, not answered — honest to say so |
| **Q3** Cost variants that collapse the SSP onto the JGP | §3.6 (the $\rho$ spectrum) | Proved and verified; the $\rho$ *number* is unsourced, the theorem is fine |
| **Q4** Benders: TSP master + KTNS subproblem, exploiting that the subproblem is polynomial | §4.2, and the whole BBC codebase | Built, verified against brute force, campaign run |

That is a coherent internship that addresses everything you were asked. You are not in a hole. The substance exists.

**In one paragraph, what the research says.** A machine holds $b$ tools; jobs need tool sets; changing tools costs time. Given a job order, the cheapest tool loading is a solved problem (KTNS — keep the tool needed soonest). So all the difficulty is the *ordering*. Practitioners never solve the ordering directly: they group jobs into the fewest magazine-fitting batches, then order the batches. Nobody had asked how much that costs you. Your §3 asks. Separately, every compact integer model of this problem has a linear relaxation stuck at one elementary number, $|U|-b$ — the tools you use beyond what fits. Your §4 builds two exact methods designed to get past that: Benders (which never forms the weak relaxation) and position-indexed branch-and-price (whose PTF variant provably exceeds it). Your §5 measures both.

If you can say that paragraph in your own words, you can open a defence.

---

## 3. What is solid, what is not

**Solid — verified independently, today, with code that shares nothing with the project's own:**
both lower bounds; the KTNS optimality claim; the convention identity; the worst-case ratio theorem; the zero-gap corollaries; the $K^*=3$ closed form; the general-$K^*$ bound; the clutter results; the setup-cost collapse theorem; the PCF relaxation results; the odd-ring covering result for $k\ge4$. Forty of fifty-three checks.

**Not solid:**
the frame labelling (10 of the 13 failures); the unbounded-gap witness family; the odd-ring claim at $k=3$; the ρ number; four literature attributions; the §5/§7 contradiction about whether the campaign is finished.

**Unknown to me:** whether the branch-and-price prototype and the campaign harness do what the report says they do. I verified the *formulations* mathematically, not the *code*. That is the one substantial gap in what I have checked.

---

## 4. What you should do

**Scope the report to what you can defend.** This is the single highest-value decision and it is yours, not mine. A shorter report you own completely is worth far more at a defence than a long one you cannot answer questions about — and the current draft has 57 pages of which the risky third is §3, which is precisely the part you have been telling your advisors is "under your line-by-line verification". The draft switch you already have (`gapstub`/`gaptheory`) exists for exactly this. Consider whether §3 goes in at all on 2 September, or goes in cut down to the results you can derive at a whiteboard.

**Learn four papers, not fifty.** The report cites fifty; the argument rests on four, and everything else is background:

1. **Tang & Denardo (1988)** — where KTNS comes from, why it is optimal, and the pairwise bound $LB(i,j)$ that seeds your Benders master. `references/ref- tang, denardo.pdf`
2. **Crama et al. (1994)** — why the problem is NP-hard (for every fixed $b\ge2$), and the seven modelling assumptions everyone since has used. `references/ref - Minimizing…Crama.pdf`
3. **Laporte et al. (2004)** — the LSS formulation, and the fact that their branch-and-**bound** beat their branch-and-**cut**, which is the first evidence that the relaxation, not the search, is the weak link. `references/ref - laporte, salazar.pdf`
4. **da Silva et al. (2024)** — the strongest compact model, whose relaxation equals $M-C$. This is the ceiling your §4 is trying to break. `references/MTSP_Article.pdf`

Two working days of reading. After them you will recognise every claim in §1, §2.7 and §4.1, because they all trace back to these four.

**Use the verifier as the way in.** `verify_report_independent.py` is not just an audit artifact — it is the fastest route to understanding §3. Open it, run it, then change one thing: take the 6-ring, print the grouping the heuristic produces, flatten it, and run KTNS by hand on the result. When you see why the answer is 3 and not 4, you understand the central subtlety of your own section — the difference between holding one magazine per group and letting KTNS re-load *inside* a group. That is a 30-minute exercise and it is worth more than re-reading the section ten times.

**Tell your advisors, and frame it correctly.** This is not a confession, it is a finding. "I re-verified §3 independently and found that the ring family — including our running example and the unbounded-gap construction — has zero gap for the heuristic as we define it; the gap we were measuring is the configuration-walk gap. The unboundedness survives with a different witness family, which I have verified. I also found a four-job instance with a genuine gap, smaller than the six-ring." That is a good thing to walk in with. It is the kind of thing a supervisor wants a student to find, and Colares is a co-advisor on Moreira's thesis and will care.

Two things to ask them while you are there: whether they have a source for the setup-to-switch ratio, and how to cite the Colares formulation (Moreira's bibliography lists it as personal communication, 2024).

**Keep the AI declaration.** It is already in the report and it is accurate. Do not weaken it. What makes a declaration honest is the second half — that every result was checked against independent ground truth. Running the verifier yourself is what makes that sentence true.

**Install a gate so this cannot recur.** The June corrections were lost because nothing forced the report to agree with them. Commit `verify_report_independent.py` to `verification/`, extend it whenever a claim is added, and require it to pass before any draft is circulated. The frame error would have been caught in July by one extra line in a script that already existed.

---

## 5. On the introduction and the writing

You said you are not happy with it, and I think you are right, for a specific reason worth naming.

The introduction is written to *persuade* rather than to *inform*. It opens by arguing a thesis — that one quantity, $|U|-b$, is "the hinge of the whole report" — before that quantity has been defined or shown to matter, and it keeps returning to that argument fourteen times across the document. It uses metaphor where a technical term exists: bounds "go slack", methods "get past" or are "stranded", the compact literature "climbed to the coverage bound and stopped". Individually these read as confident writing. Cumulatively they read as a document arguing for its own importance, which is exactly the register that makes an examiner start checking claims.

A report introduction has four jobs and no others: say what the problem is, say what is known, say what you did, say what you found. The reader should be able to stop after the introduction and correctly state your contribution.

That is fixable, and it is the same fix as the terminology problem you raised earlier: replace the persuasion with the statement. It is not a matter of cutting — some of it will get longer, because a precise statement often needs the hypothesis spelled out where a metaphor did not.

**Concretely, I suggest this:** let me rewrite the introduction once, properly, on the corrected content, and send it to you side by side with the current one. It is the shortest section, you will be able to judge the register immediately, and if you like it the same treatment applies to §2.7 and §6. If you do not, we have lost very little and I will have learned what you actually want. That seems better than either of us theorising about it further.

---

## 6. The order I would go in

1. Read the four papers. Nothing else moves until you can state the problem in your own words.
2. Run the verifier; do the 6-ring exercise by hand.
3. Talk to the advisors — the frame finding, the ρ source, the Colares citation.
4. Decide the scope for 2 September, with §3 in or out on the basis of what you can defend.
5. Then we fix the report, frame first, in the order already planned.

Steps 1–3 are yours and they do not need me. I would rather you did them before I touch the text, because a report you can defend is the actual deliverable, and I cannot produce that part.
