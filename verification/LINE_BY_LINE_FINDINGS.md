# Line-by-line verification of JGP-SSP_report.tex — findings

Date: 2026-08-20. Verifier: `verify_report_independent.py` (delivered alongside; re-runnable, ~25 min, no CPLEX required).

## Method

Three independent tracks, each designed so that agreement is evidence rather than repetition.

1. **Computational.** A verifier written from scratch, sharing no code with `src/` or `plans-genai/_verification/`. Optimal loading for a fixed order is computed by exact DP over magazine states, so **Proposition 2.2 (KTNS optimality) is tested, not assumed**; KTNS is implemented separately and cross-checked against the DP. The optimum $Z^*$ comes from a Held–Karp DP over (finished jobs, magazine), itself cross-checked against brute force over all permutations. 53 checks.
2. **Literature.** Every claim the report attributes to a source, read against the source PDF in `references/`, using `skills/ssp-literature` as the index.
3. **Mathematical.** Statement-by-statement replay of definitions, theorem statements and proofs.

Result: **40 of 53 computational checks pass, 13 fail.** The 13 failures have **one dominant root cause**, and it is the thing you flagged as a terminology problem. It is not cosmetic.

---

## Finding 1 (critical) — the symbol $H$ denotes two different quantities, and the report's headline results are stated in the wrong one

The report defines the heuristic in §2.3 with three steps, the third being: *"concatenate the jobs group by group and evaluate the resulting order with KTNS"*, and writes $H$ for "the switch cost this heuristic returns" (l.564). Call that $H$.

§3.1 then silently redefines $H = \min\{\gamma(\mathcal P) : |\mathcal P| = K^*\}$ (cor:gap, l.1050) — the cost of a *configuration walk* that holds one fixed magazine per group. §3.4 finally names that quantity $H_{\text{walk}}$ and notes $H \le H_{\text{walk}}$.

So §3.1–§3.3, Table 3.1, and the examples in §2 all report $H_{\text{walk}}$ under the name $H$. The difference is not marginal:

| instance | $Z^*$ | $H_{\text{walk}}$ | walk gap | $H$ (as defined) | **actual gap** |
|---|---|---|---|---|---|
| 6-ring | 3 | 4 | 1 | **3** | **0** |
| 7-ring | 4 | 5 | 1 | **4** | **0** |
| 8-ring | 5 | 6 | 1 | **5** | **0** |
| 9-ring | 6 | 7 | 1 | **6** | **0** |
| $g=2$ disjoint 6-rings | 9 | 11 | 2 | **9** | **0** |
| $K^*=4$ witness (l.1399) | 4 | 5 | 1 | **4** | **0** |

**Every ring has zero gap for the heuristic as the report defines it.** The reason is visible in the report itself: Example 2.1 computes KTNS on the order $1,2,3,4,5,6$ and gets 6 (empty-start), calling it optimal. That order *is* the flattening of the grouping $\{1,2\},\{3,4\},\{5,6\}$ in group order 1,2,3. So step 3 of the heuristic produces the optimal schedule. Example 2.3's claim that the heuristic returns 7 on the same instance contradicts Example 2.1 — the two examples are two pages apart.

Consequences, each verified:

- **Example 2.3 and Table 3.1 report walk values as $H$.** In the heuristic frame the gap column of Table 3.1 is identically zero.
- **Proposition 3.2 (unbounded gap) is false as stated.** $g$ tool-disjoint 6-rings have heuristic gap $0$, not $g$ — verified at $g=1,2$. This is one of the three results the report's §3 status paragraph calls "computational and definitive".
- **The abstract's "unbounded on others" is a walk-frame claim** presented as a claim about the heuristic.
- **"The 6-ring is the smallest instance on which grouping-then-sequencing is provably sub-optimal" (l.451) is wrong twice over:** the 6-ring is not sub-optimal in this frame, and an exhaustive search finds a 4-job witness that is (below).
- **Theorem 3.16 (setup-cost collapse) is frame-dependent and does not say which frame.** Its threshold $\rho > H - Z^*$ is correct when $H$ means $H_{\text{walk}}$ (verified, 3/3 instances) and **fails** when $H$ means the heuristic's value (verified, 2/3 instances) — because the threshold then reads $\rho > 0$, and a larger grouping can still win.

The 2026-07-17 entry in `VERIFIED_FACTS.md` identified this conflation and correctly repaired §3.4 onwards, but recorded the unbounded-gap construction as *"believed frame-safe … re-verify when recommitting scripts"*. That re-verification never happened, and the belief was wrong.

### The good news: two constructive repairs

**(a) Unboundedness survives with a different witness family.** The construction is fine; the *seed* is wrong. The 6-ring has zero heuristic gap, so copies of it inherit zero. Seeded instead with $I_1$ — the report's own instance from prop:noclutter, $n=4$, $b=4$, $|U|=7$, heuristic gap 1 — the construction works:

| $g$ | $|U|$ | $K^*$ | $Z^*$ | $H$ | gap |
|---|---|---|---|---|---|
| 1 | 7 | 3 | 3 | 4 | **1** |
| 2 | 14 | 6 | 10 | 12 | **2** |

so $Z^* = 7g-4 = |U|-b$ and gap $= g$. Proposition 3.2 can be restated with this family and keeps its full strength. (The proof needs one new lemma — that KTNS decomposes across tool-disjoint copies — which is straightforward and which the walk-frame proof did not need.)

**(b) The smallest sub-optimal instance, found by exhaustive search over $n\le4$:** $b=4$, $\mathcal T = (\{0,1\},\{2,3\},\{0,2,4,5\},\{1,4,5,6\})$, with $K^*=3$, $Z^*=3$, $H=4$. Four jobs, gap 1. This replaces the false "smallest" claim with a true one.

### And a stronger result than the one currently claimed

A census of 420 random instances finds a positive heuristic gap in **1**. Every positive-gap instance found anywhere in this verification has gap exactly 1, and all require $b\ge4$. That is a *better* headline than "the gap is unbounded on rings": the KTNS evaluation step recovers the optimum far more often than the walk model suggests, and the decomposition is nearly always exact — with an explicit, characterisable set of exceptions. §3 currently buries this; it is the more interesting and more defensible claim, and it is consistent with what the applied literature reports (see Finding 4).

---

## Finding 2 — Proposition 3.15 (odd rings) is false at $k=3$

The statement asserts fractional cover $=k/2$ and $K^*=\lceil k/2\rceil$ for the $k$-ring. At $k=3$ all three jobs fit one magazine: $K^*=1$, fractional cover $1$, against the claimed $\lceil 3/2\rceil = 2$. The proof's opening — "the maximal groups are the adjacent edge pairs" — is false there. Verified $k=4,\dots,8$ pass. The fix is the hypothesis $k\ge4$.

---

## Finding 3 — Catanzaro et al. recommend Formulation 5; the report says F5 is unusable, without a source

The report justifies its baseline choice (l.1755–1760): F4 is *"the strongest member that scales: its linear relaxation coincides with F3's at a smaller model size, while F5's tighter relaxation is so large that at the $n=40$ benchmark sizes even its root linear relaxation does not complete."*

The first half is exactly right and matches the paper: *"We excluded from the analysis Formulation 3 as it provides the same lower bounds as Formulation 4 and contains more variables and constraints."*

The second half contradicts the source. Catanzaro et al. report that F5 **solved more instances than F4** (10 vs 7–9), **solved all of datA2 where F4+valid inequalities could not**, and their conclusions **"suggested Formulation 5 as the best ILP formulation"** for the SSP. If F5 was tried in this project and failed at $n=40$ under CPLEX, that is a legitimate finding — but it is the project's own measurement, must be reported with its data, and must acknowledge that the source recommends F5.

---

## Finding 4 — Burger et al.'s actual conclusion is conditional, and it corroborates this report's own theory

The report says (l.860–864) Burger et al. measured the decomposition's suboptimality and *"it is small on their instances"*. Their actual conclusion:

> "We concur, especially in cases where the largest job size is only slightly smaller than the magazine size. **However, as the difference between the magazine size and the largest job size grows, the quality of solutions uncovered by this heuristic solution approach decreases, as may be expected.**"

The report drops the second sentence — which is the one that matters, because it is an *empirical* statement of exactly what §3 proves *theoretically*: the gap opens as $b$ grows relative to the job sizes (cf. rem:bdep, "the extremal ratio is non-decreasing in $b$"; and every positive-gap witness in Finding 1 needs $b\ge4$). Independent industrial corroboration of the report's central structural claim is currently being cited as if it said the opposite.

Further, Burger et al.'s closing paragraph poses this as an open question:

> "It would be interesting to contrast the trade-off between minimizing the number of tools changed and the number of times tools are changed … for varying values of the setup times."

That is precisely §3.6 (the setup-cost spectrum, thm:collapse + lem:lowrho). **The report answers a question explicitly posed in the literature and does not say so.**

---

## Finding 5 — da Silva's bound is $M-C$, not $|U|-b$, and the 17% figure has no stated comparison

prop:sspmf-lp (l.1765) states the multicommodity relaxation "equals the coverage bound $|U|-b$" and attributes it to da Silva et al. The paper proves the LP relaxation equals $M-C$ — *number of tools* minus capacity — under their stated assumption that all $M$ tools are needed. The identification $M=|U|$ is a hypothesis, not an identity, and the report never states it. `VERIFIED_FACTS` separately records that the repo's own SSPMF root LP measured 2.0 where the paper's $M-C$ gives 3 on the 6-ring, flagged as an unresolved convention divergence — so this is not purely pedantic.

Related, in the same neighbourhood:
- **"solves some 17% more of the standard instances than any predecessor"** — the paper says 17.01% more than the models of Tang & Denardo, Laporte et al. and Catanzaro et al., on the instance sets of Yanasse et al. (2009). Neither the comparison set nor the baseline is currently stated.
- **tab:methods asserts F4 and LSS relaxations are "below $|U|-b$"** flatly. The source says prior models give LP below $M-C$ *"in the great majority of the cases"*, and separately that the LSS relaxation strengthens as capacity tightens. The table overstates a hedged source claim as a universal one.
- **`references.bib` has `year = {2021}` for `daSilva2024`**, so citations render "[2021]" and tab:lineage dates it 2021. The paper is compiled May 2024. Your own `skills/ssp-literature` flags "daSilva 2021: **WRONG YEAR**" — the bib is the thing that is wrong.

---

## Finding 6 — your own knowledge files contain a mis-attribution that the report gets right

`CLAUDE.md` ("JGP … solved exactly via the ARF MILP (Catanzaro 2015)") and `skills/ssp-literature` ("JGP ARF formulation (also in this paper)") both credit the asymmetric-representatives formulation to Catanzaro et al. 2015. That paper contains **zero** occurrences of "grouping", "representative" or "batch". The report's citation to Jans & Desrosiers is the defensible one. The skill and CLAUDE.md should be corrected, not the report.

(Separately verified as accurate against sources: Laporte's B&B reaching 25 jobs and B&C stalling at eight; Ghiani 2010 rather than 2007; Crama & Oerlemans as the JGP column-generation reference; Tang & Denardo's zero LP relaxation and pairwise bound.)

---

## What verified clean

Most of the mathematics holds. No violation was found, on 200 random instances plus the named witnesses, of: both lower bounds and their corollary; lem:costid; lem:transcap; thm:uncond; cor:zerogap (i)–(iii); cor:smallZ; cor:z3; prop:k3; prop:genk; prop:hk3 (the closed form at $K^*=3$, checked on 45 instances); prop:noclutter ($I_0$/$I_1$); prop:chromK; prop:nonmatroid; prop:oddring for $k\ge4$; thm:collapse in the walk frame; the convention identity; W1's walk gap of 2 and heuristic gap of 1; the sliding-window ring exceeding both bounds; PCF's relaxation being 0 without the counting rows and $|U|-b$ with them; and KTNS optimality itself.

**The §3 results are sound as theorems about $H_{\text{walk}}$.** What is wrong is which quantity they are claimed to be about.

---

## Plan

The objective is that every sentence be a statement someone can check, and that the report claim exactly what was established — no more, no less. Length is not a target and I will not treat it as one; some of this will make the report longer.

**Phase 1 — fix the frame.** The largest single defect and everything downstream of it.
- Define $H$ (the heuristic as specified, KTNS-evaluated) and $H_{\text{walk}}$ (one fixed configuration per group) once, in §2.3, with the inequality $H\le H_{\text{walk}}$ and a worked instance where they differ.
- Restate every §3 result in the frame it was actually proved in. Most become clean statements about $H_{\text{walk}}$ plus a corollary for $H$ where the inequality gives one.
- Repair Proposition 3.2 with the $I_1$-copy family; prove the tool-disjoint decomposition lemma KTNS needs.
- Fix Example 2.3 and Table 3.1 (add an $H$ column beside $H_{\text{walk}}$ — the contrast is itself a result).
- Replace the false "smallest instance" claim with the verified 4-job witness.
- State the census result: positive heuristic gaps are rare, are 1 in everything sampled, and need $b\ge4$.
- Decide whether the 6-ring stays as the running example. **This one needs you** — see the question at the end.

**Phase 2 — literature fidelity.** Every attributed claim says what the source says, with the qualifications the source attaches: the F5 recommendation, Burger's degradation regime and open question, da Silva's $M-C$ and its hypothesis, the 17.01% comparison basis, the hedge on prior LP bounds, the bib year. Where the project's own measurement disagrees with a source, say so explicitly as a measurement.

**Phase 3 — provenance.** Every number states where it came from: which family, which parameter range, which instance set, which script. Complete enumerations state the family completely (your rule); searches that are not exhaustive are described as such and carry no count.

**Phase 4 — proportionate reporting.** Abstract, contributions and conclusions carry only what was established. Work that was done but yielded no conclusion is recorded plainly in the body, once, without evaluative framing. This resolves the §5/§7 contradiction about whether the campaign is finished.

**Phase 5 — technical vocabulary.** One term per concept, rooted in the literature's own usage: *bound-tight/bound-loose* defined once; "relaxation value equals / is strictly below"; the heuristic named once; the $\rho$/$\gamma$/$\pi$/$\theta$ collisions resolved; conjecture demotion applied uniformly across abstract, §3 opener and §6.1 so the three status lists agree.

**Phase 6 — re-verification.** Re-run `verify_report_independent.py` against the revised text; every check must pass or be an intentional, documented contradiction. I suggest committing the script to `verification/` so it becomes a standing gate.

**Sequencing.** Phase 1 changes what the report claims, so it goes first and alone; you review it before anything else moves. Phases 2–4 are independent of each other. Phase 5 is mechanical once 1–4 settle. I will send each phase as a diff.

**Token note.** Phase 1 is the expensive one (new proof, restated statements). Phases 3–5 are surgical. If you want the proof of the disjoint-copy lemma developed carefully, that is worth a dedicated session or a subagent whose only output is the proof, so the derivation does not sit in this context.

---

## The one question that blocks Phase 1

The 6-ring is the report's running example, used in eight figures and four examples. It is an excellent illustration of the *walk* gap and a poor one for the heuristic, whose gap on it is zero. Options:

- **(a)** Keep the 6-ring as the walk-model example, and introduce the 4-job $b=4$ witness as the heuristic-gap example. Two examples, but each honest, and the contrast between them becomes the pedagogical point of §3.
- **(b)** Promote the 4-job witness to running example throughout and demote the ring to a remark. Cleaner single thread; costs a rewrite of the §2 figures.
- **(c)** Keep the ring throughout, state plainly that its heuristic gap is zero, and use it only to illustrate the walk model.

I would pick (a): it costs least, keeps the figures, and turns the defect into the section's main insight — that the KTNS step is doing more work than the walk model can see.
