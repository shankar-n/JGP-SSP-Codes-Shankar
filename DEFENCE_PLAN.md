# Nine days to the defence

**Talk:** 25 min + 20 min questions, jury · **Date:** 2 September 2026

---

## 1. The honest answer first

You asked whether the work is correct, substantial, or even scientific. Three different
questions, three different answers.

**Correct — yes, and it is checkable.** Every quantitative claim is reproduced by a program
that shares no code with the solvers. Across 41,673 pairs of methods that both proved an
optimum on the same instance, none disagreed. The loading rule is verified against an exact
dynamic program on 83,670 instance-and-sequence pairs. Two errors were found this way; both
are fixed and both are documented in the report rather than quietly patched.

**Scientific — yes, more than most.** Every statement carries a label used strictly: a
Proposition has a proof, an Observation was computed, a Conjecture has neither. Negative
results are reported as negative. The failed runs are counted in the tables. That discipline
is the first thing a jury notices.

**Substantial — the theory is; the methods are not competitive, and that is the finding.**
Section 4 alone holds 2 theorems, 12 propositions, 4 corollaries, 4 lemmas, 5 observations,
3 conjectures and 1 open problem. Every question your advisors set has an answer. What you do
*not* have is a solver that beats the literature — the multicommodity model closes 1,038
instances against 727 for your best Benders configuration. Do not claim otherwise. **The
reason it loses is the result.**

**Publishable — one piece plausibly is:** the frame distinction together with the gap
analysis. That is Wagler's call. Bring it to her as a question, not a claim.

---

## 2. The one thing the 25 minutes should be about

> **The elementary counting bound `q = |U| − b` decides both how good the standard industrial
> heuristic is, and whether any exact method can close an instance.**

Tools that some job needs, minus what fits in the magazine. One line of arithmetic. Everything
else in the internship orbits it.

**Act 1 — the hook. The textbook example is wrong.**
The literature's canonical bad case for the two-phase heuristic is the ring family. Under the
method as actually specified, every ring from k=3 to 9 has gap **zero**. The published gaps are
*walk* gaps — one fixed magazine per group. The method's own final loading step closes them.

**Act 2 — the theory. The gap is a price, and you can name it.**
The optimum equals the cheapest walk over *all* groupings. So the two-phase gap is exactly what
you pay for insisting on the fewest groups — nothing else. Zero-gap classes for every capacity,
worst-case bounds, the extremal case at three groups.

**Act 3 — the close. The same number stops the exact side.**
Three unrelated formulations — your Benders master, your PCF′ column generation, and the
literature's strongest compact model — all reach exactly `q`. Where `q` is tight the solver
closes 94% of instances; where it is loose, 40%.

### The picture the whole talk hangs on

The 6-ring, magazine holds 3 tools.

```
FEWEST GROUPS — what the heuristic is told to do        3 configurations

    {1,2,3}  --+2-->  {4,5,6}  --+2-->  {1,4,...}            cost 4


BEST OVER ALL GROUPINGS — what the optimum actually uses  4 configurations

    {1,2,3} --+1--> {1,3,4} --+1--> {1,4,5} --+1--> {1,5,6}   cost 3
```

Every minimum-cardinality grouping of the 6-ring costs 4. The optimum uses one more group and
costs 3. That difference is the entire two-phase gap, and it is why the gap is a *price* rather
than a failure of sequencing. The heuristic's own final loading step recovers it, which is why
the measured heuristic gap is zero while the published walk gap is one.

**If the jury is more applied than theoretical:** make Act 3 the subject and Acts 1–2 the setup.
Same thesis, more measurement. Ask your advisors which room you are walking into — they know the
jury and you do not.

---

## 3. Every question they set, and where it stands

Print this and put it on the table at the advisor meeting before you say anything else.
Nine questions. Eight answered, one partial. Three of the answers are negative — a negative
answer to a well-posed question is still an answer, and you should present it as one.

### Prof. Wagler

| Question | Status | Where |
|---|---|---|
| Construct worst-case examples with the number of groups fixed | **Answered** | Extremal behaviour at three groups settled exactly — §4.4, `prop:hk3`, `prop:k3`, `prop:genk` |
| Study the instances on which the gap is attained | **Answered** | Zero-gap classes for every capacity; smallest sub-optimal instance identified; 420-instance census — §4.3, §4.5, `cor:zerogap`, `obs:smallest`, `obs:census` |
| Prove an upper bound tighter than the trivial `b(K*−1)` | **Answered ×5** | One unconditional guarantee plus four conditional — §4.3, `thm:uncond`, `cor:zerogap`, `cor:smallZ`, `cor:z3`, `lem:transcap` |
| Enumerate integral solutions of the grouping problem with PORTA | **Partial** | Sampled, not enumerated exhaustively. Say so plainly — the one loose end. §4.7 |
| Read the grouping problem through clutters and blocking duality | **Answered, negatively** | The gap cannot be recovered from the circuit clutter. `K*` is a hypergraph chromatic number; no matroid structure; odd rings not ideal — §4.6, `prop:noclutter`, `prop:chromK`, `prop:nonmatroid`, `prop:oddring` |

### Prof. Colares

| Question | Status | Where |
|---|---|---|
| Develop the configuration-based view of the problem | **Done** | A schedule is a walk through magazines; frames the whole report — §2.5 |
| Reduce the SSP to a generalised travelling-salesman problem | **Done** | The formal content of that view — §2.5 |
| Branch-and-Benders-cut: lazy cuts first, fractional second | **Both tested** | Lazy cuts work. Fractional cuts are a clean negative: 67.5M generated, bound at termination never rises on a single instance — §5.2, §5.3, §6.4 |
| Position-indexed formulations on a fixed polynomial row set | **Both built, both measured** | PCF′ equals `q` — proved, then confirmed on all 2,114 runs. PTF can exceed `q` — proved, observed on 3 runs of 233 — §5.4, §6.6 |

---

## 4. What worked, what didn't

The report keeps everything. The presentation keeps only the left column — plus one item from
the right, because a measured negative beats a hedge.

### Worked — presentable

- **The frame distinction.** `H` and `H_walk` are different quantities and the literature
  conflates them. Every ring has heuristic gap zero.
- **Grouping exactness.** The optimum is the cheapest walk over all groupings, so the gap is
  exactly the price of the fewest-groups restriction.
- **Zero-gap classes and worst-case bounds** for every capacity; exact extremal behaviour at
  three groups.
- **The census.** Positive gaps are rare, always equal one, always need `b ≥ 4` — which
  independently matches the one industrial study in the literature.
- **The setup-cost spectrum theorem.** SSP and the grouping problem are two ends of one
  parameterised model. Answers a question Burger et al. posed and left open.
- **The clutter analysis** — negative, but clean and well-posed.
- **The bound-limited diagnosis**, established four independent ways.
- **The validation itself.** 41,673 cross-method comparisons with zero disagreements is
  unusually strong for a student project.

### Didn't work — report only

- **Fractional Benders cuts.** 67.5M generated, node count down twentyfold, bound never
  improved, 67 solved instances lost. **Keep this one** — it is the single most convincing
  slide you have for the bound-limited thesis.
- **Pareto-optimal cut lifting.** Costs 37 instances.
- **The conflict-graph row.** Neutral, as predicted.
- **The Benders solver as a competitor.** 727 against 1,038. It is a diagnostic instrument, not
  a faster solver — present it that way.
- **Branch-and-price at scale.** Nothing above nine jobs. That is the Python pricer, not the
  formulation, and you must say which.
- **PTF's advantage in practice.** Three runs out of 233, one unit each.
- **The learned cut-selection prototype.** Never run on the SSP — trained on knapsack cover
  cuts. Leave it out of the talk, or one backup slide.

---

## 5. Nine days

Order matters. The problem before the methods, your own results before the literature's, and
the advisors before a single slide — their feedback should shape the talk, not arrive after it.

### ▶ TODAY — send the email

The only irreversible deadline here. The advisor meeting has to be booked before anything else
can be scheduled around it, and every day you wait costs a day of their calendar. Draft in §9.

- [ ] Send the email to Colares and Wagler, cc Chicoisne

### Mon 24 — the problem itself

No methods, no formulations. Just what the SSP is and why it is hard.

- [ ] Read §1 and §2.1–2.4 of your own report, slowly — written for a reader who knows nothing,
      which is the right level today
- [ ] Read Tang & Denardo (1988) properly — short, and the foundation
- [ ] Draw the three-job example from Figure 1 by hand and count the insertions yourself

### Tue 25 — KTNS, the two conventions, and `q`

The vocabulary of every conversation you will have.

- [ ] Understand *why* KTNS is optimal — the exchange argument, not just the statement
- [ ] Get empty-start vs free-initial straight. They differ by the initial load, and half the
      apparent contradictions in this field are really this
- [ ] Derive `q = |U| − b` yourself in one line, then say out loud why it is the weakest
      possible interesting bound
- [ ] Read Crama et al. (1994) §1–2: the seven assumptions and the NP-hardness proof

### Wed 26 — your contribution

All of §4. This is the day that decides whether the presentation works.

- [ ] Read §2.5 (configurations, the two frames), then all of §4, with a pen
- [ ] Be able to state the grouping-exactness theorem and its corollary from memory
- [ ] Work the 6-ring example — cost 3 with four groups vs cost 4 with three — until you can
      draw it cold
- [ ] Read Burger et al. (printing press) and find the sentence about the magazine-to-job-size
      gap. That is your independent corroboration

### Thu 27 — verify it yourself

You will stop feeling like an impostor on this day. Not because someone reassures you — because
you watch the machine confirm the claims one at a time, in front of you.

- [ ] Run `verification/verify_report_independent.py` (~25 min, no CPLEX). Read every line
- [ ] Run `verification/analyse_campaign_results.py --check` — re-derives ~100 figures in §6
- [ ] Read `compute_ktns` in `src/SSP/utils.py`. Trace it by hand on the Figure 1 example
- [ ] Read `verification/VERIFIED_FACTS.md` and `LINE_BY_LINE_FINDINGS.md` — the record of what
      was wrong and how it was caught

### Fri 28 — the compact models

Three formulations from the literature, and the one fact they share.

- [ ] Laporte, Salazar-González & Semet §2.2 — the LSS model, and why Tang & Denardo's own
      relaxation is identically zero
- [ ] Catanzaro et al. §3 — the F-family, total unimodularity, the 0-blocks reading
- [ ] da Silva et al. — the multicommodity flow model and the proof that its relaxation equals
      the counting bound. The most important paper for Act 3
- [ ] Say out loud: *three independent formulations, one bound.* That is your closing line

### Sat 29 — your own methods, in code

You built these. Today you read them as if someone else had.

- [ ] Skim the Rahmaniani et al. Benders survey — taxonomy section only. Lazy cut,
      Pareto-optimal cut, core point
- [ ] Open `src/BBC/branch_and_benders_cut_cplex.py`. Find the master. Find the coverage row
      `θ ≥ |U|`. Understand why its absence wrecked the first campaign
- [ ] Open `src/BNP/pcf_prime_bp.py`. Identify what a column is, what the pricing problem is,
      and why it is a set-union knapsack
- [ ] Read §5 of the report against the code as you go

### Sun 30 — build the long version

The advisor meeting is not the jury talk. Longer, covers everything, and its job is to find out
what *they* think matters.

- [ ] Assemble the advisor deck from the report's own structure — §4, then §5, then §6
- [ ] Put the question scoreboard (§3 above) on slide two
- [ ] Write down every question you cannot answer. Bring the list. Asking is not weakness;
      arriving without it is

### ▶ Mon 31 — meet Colares, Wagler and Chicoisne

Present everything, long form. Ask two things directly: **which single result should carry the
jury talk**, and **whether the frame distinction is worth writing up**. Take notes on what they
push back on — that is your Q&A preparation, free.

### Tue 1 — cut it to 25 minutes

From ~40 slides to ~15, built around whatever they told you yesterday.

- [ ] Rough shape: 4 min problem · 4 min the frame surprise · 7 min the gap theory ·
      6 min the measurement · 2 min what it means · 2 min next
- [ ] Every slide gets one sentence you say out loud. If you cannot say it, cut the slide
- [ ] Build the backup slides: ablation table, fractional-cut result, failed runs, RL prototype.
      Twenty minutes of questions will reach them

### Wed 2 — rehearse, then present

- [ ] Twice out loud with a timer, standing
- [ ] The 6-ring at the board once more from memory — the one thing you may be asked to draw

---

## 6. What to read, and what to take from it

Everything below is already on your disk. Note that `references/Useless/` is misnamed — several
important papers are duplicated in there.

### Read properly — five papers, a jury question will land on one of these

**Tang & Denardo (1988) — the KTNS rule**
`references/ref- tang, denardo.pdf`
The optimality theorem for loading at a fixed order, and the pairwise lower bound your Benders
master uses. Also the source of the fact that their own relaxation is identically zero.

**Crama, Kolen, Oerlemans & Spieksma (1994)**
`references/ref - Minimizing the number of tool switches on a flexible machine - Crama.pdf`
The seven assumptions that define the problem, and NP-hardness for every fixed capacity ≥ 2.
Also: KTNS *fails* under non-uniform tool costs while the loading LP stays exact — which is why
your Benders subproblem extends to that regime and the compact models do not.

**Laporte, Salazar-González & Semet (2004) — LSS**
`references/ref - laporte, salazar.pdf`
One of your three baselines and the branch-and-cut it sits in. §2.2 for the formulation and the
valid inequalities.

**Catanzaro, Gouveia & Labbé (2015) — the F-family**
`references/ref - catanzaro.pdf`
Your `CATZ-F4` baseline. §3 including the total-unimodularity argument. Know that they recommend
F5 and you implemented F4 — the jury may ask, and §7.3 already concedes it.

**da Silva et al. — the multicommodity flow model**
`references/To read/SSPMF.pdf`
The strongest method in your campaign, and the paper proving its relaxation equals the counting
bound. The single most important paper for Act 3.

### Read the abstract and results, skim the rest

**Burger et al. — colour printing, the industrial study** — `references/printing2.pdf`
Your independent corroboration. Find where they say solution quality degrades as the magazine
grows relative to the largest job. They also pose the question your setup-cost theorem answers.

**Mecler et al. — hybrid genetic search** — `references/To read/1910.10021v1.pdf`
The state-of-the-art heuristic and the source of the warm start in your `+H` configuration — the
one strengthening that helped.

**Calmels — the SSP survey** — `references/ref - SSP-SOTA-Survey- Calmels, Dorothea.pdf`
Your map of the field. §4's classification table. If a jury member names a paper you have never
heard of, it is in here.

**Colares — the GTSP reduction preprint** — `references/formal-def-ssp.pdf`
Your advisor's own framing of the problem and the origin of the configuration view. Read it
before you meet him.

**Otiai — branch-and-price for the grouping problem** — `references/felipe-thesis.pdf`
The instance collection you benchmark on, and the contrast case: for the grouping problem the
set-covering relaxation is strong; for the SSP it is not. Chapters 2–4.

### Only if the days allow

- **Rahmaniani et al. — Benders survey.** Taxonomy section only; the vocabulary of §5.3.
- **Lübbecke & Desrosiers — column generation primer.** If branch-and-price still feels like a
  black box after Saturday, read this then re-read your own §5.4.
- **Wolsey, *Integer Programming*** — `references/Integer Programming __ {Wolsey, Laurence} latest.pdf`
  Reference, not reading. Branch-and-bound, cutting planes, Lagrangian duality if §2.8 doesn't land.

---

## 7. Seven things you must be able to do at the board

With a pen, no notes, no slides. Reading alone will not remove the fear. These will.

1. **Run KTNS on the three-job example** and get four insertions.
   *Tests: do you understand the loading rule, or only its name.*
2. **Draw the 6-ring, group it two ways, and get 4 and 3.**
   *Tests: the contribution. If you do only one drill, do this one.*
3. **Derive `q = |U| − b` in one line** and say why it is valid.
   *Tests: the quantity the whole talk is about.*
4. **Sketch why KTNS is optimal** — the exchange argument, two sentences.
   *Tests: the one classical proof you are expected to know.*
5. **State the grouping-exactness theorem** and both directions of its proof idea.
   *Tests: your own main theorem. Not knowing it would be the worst moment of the day.*
6. **Explain a Benders cut here in two sentences** — what the master decides, what the subproblem
   returns, why the master's bound is `q`.
   *Tests: whether you can defend the method you spent months building.*
7. **Say what a column is in PCF′** and what the pricing problem asks for.
   *Tests: the branch-and-price half. Colares will ask this one.*

---

## 8. What they will ask, and what is true

None of these requires you to overstate anything.

**"Your solver doesn't beat the state of the art. So what is the contribution?"**
The contribution is the *reason* it doesn't, established four independent ways. Three unrelated
formulations reach exactly the same elementary bound. The search is not the bottleneck — where
the bound is loose the solver already holds the optimum two-thirds of the time and cannot
certify it. Every strengthening aimed at the bound made things worse; only the one aimed at the
incumbent helped. That rules out a family of approaches, which is worth knowing before someone
spends a year on it.

**"How do you know these numbers are right?"**
An independent verification program sharing no code with the solvers reproduces every
quantitative claim. Across 41,673 pairs of methods that both proved an optimum, none disagreed.
The loading rule is checked against an exact dynamic program on 83,670 pairs. Two analysis errors
were caught this way and both are documented rather than quietly fixed.

**"Isn't the ring counterexample already known?"**
The example is known; the gap reported for it is a *walk* gap. Under the two-phase method as
actually specified — group, sequence, then re-optimise the loading across the whole flattened
order — every ring from k=3 to 9 has gap zero. The standard method is better than the standard
model of it. That distinction is what makes the rest of the analysis correct.

**"Why did the PORTA enumeration not finish?"**
It was sampled rather than enumerated exhaustively. Say exactly that. It is the one question your
advisors set that lacks a complete answer, and pretending otherwise is far more damaging than the
gap itself.

**"Why is the branch-and-price so slow?"**
Python with a Python pricer, benchmarked against models compiled into CPLEX. Its solve counts are
a lower bound on what the formulations can do, and the report says so. The quantity free of that
problem is the root relaxation, which is why every conclusion drawn from it rests on the bound
and not on solve counts.

**"What would you do next?"**
Window inequalities — charging `|∪T_j| − b` over sets of consecutive jobs, generalising the
pairwise and triplet rows in one family. The only direction the measurements point to. Plus the
open problem: is the excess of the PTF relaxation over `q` bounded by a constant?

**"How much of this did you do yourself?"**
The report already answers this in §9 and §1.3 — the research directions were set by your
advisors, each attributed by name, and the use of AI tools is declared. You do not need a better
answer than the honest one. What you need is to be able to **defend every claim on every slide**,
because that is what distinguishes understanding from transcription — and that is precisely what
the nine days above are for. Do the drills and this question stops being frightening.

---

## 9. The email — send today

Short. No long apology; a paragraph of explanation reads worse than a line. Lead with results,
because that is what changes the tone of the reply.

> **To:** Rafael Colares, Annegret Wagler · **Cc:** Renaud Chicoisne
> **Subject:** SSP internship — campaigns finished, could we meet this week?
>
> Dear Prof. Colares, dear Prof. Wagler,
>
> My apologies for the long silence. The cluster campaigns have now finished and I have written
> up everything, so I would like to show you where the work stands.
>
> Three results in short. First, the two-phase heuristic admits two different readings that the
> literature does not separate, and under the method as actually specified the ring family has no
> gap at all — the published gaps are walk gaps. Second, the optimum equals the cheapest walk over
> all groupings, so the two-phase gap is exactly the price of using the fewest groups; this gives
> zero-gap classes for every capacity and several bounds tighter than the trivial one. Third, the
> campaign shows the coverage bound decides everything on the exact side: the Benders solver
> closes 94% of the instances where the bound is tight and 40% where it is not, and the
> position–configuration relaxation equals that bound on every one of 2,114 runs.
>
> The fractional Benders cuts did not work. They are generated in very large numbers and never
> improve the bound at termination, which I think is itself worth reporting.
>
> The report is attached. Could we meet this week, before the presentation on 2 September? I
> would like to go through all of it with you and hear which result you think should carry the
> jury talk. I also have a list of questions I could not answer on my own.
>
> Best regards,
> Shankar

**Two things not to do.** Do not explain the vacation at length — one clause if at all, and only
if asked. And do not open with an apology for the work: you have eight questions answered out of
nine asked, and the tone should match that rather than contradict it.

---

*Built from the report at `report/rebuild/`, the campaign record at
`verification/CAMPAIGN_RESULTS_2026-08-24.md`, and `verification/ATTRIBUTION.md`. Every figure
quoted here is reproduced by `verification/analyse_campaign_results.py --check`.*
