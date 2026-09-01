# Experimental design audit — JGP-SSP campaign

Run 1 September 2026, deliberately looking for holes of the kind the missing `BBC-LP+H`
configuration belongs to: missing controls, confounded switches, and headline numbers whose
denominator does the work. This is **not** a check that the reported numbers are right —
that has been done twice independently (58/58 verifier, 101 campaign checks, and every §4
witness brute-forced against code sharing nothing with the solvers).

Findings are ordered by how much they change what you should say on 2 September.

---

## 1. The headline understates your own solver, and your own table proves it

**This is the most important thing in this document, and it is good news.**

The campaign reports *"every compact baseline certifies more than every Benders regime"* —
1,028 for SSPMF against 724 for the best Benders. True on the full 1,410-instance
denominator.

But **670 of those 1,410 instances — 48% — are Laporte3 and Laporte4, and all three compact
models close 100% of both.** Those families cannot discriminate between methods. They are
pure denominator.

Partition the benchmark and the picture changes. On the 740 instances that actually
discriminate (Catanzaro, Crama, Laporte5, Laporte7):

| Method | Discriminating families | Share |
|---|---|---|
| SSPMF (multicommodity) | 358 / 740 | **48.4 %** |
| **Benders + fractional + heuristic** | **213 / 740** | **28.8 %** |
| CATZ-F4 (arc-flow) | 206 / 740 | 27.8 % |
| Benders — base | 192 / 740 | 25.9 % |
| Benders — KTNS oracle | 192 / 740 | 25.9 % |
| LSS (tool-state) | 163 / 740 | 22.0 % |

**Your best Benders regime beats two of the three compact baselines on the half of the
benchmark where the comparison means anything.** Only SSPMF is clearly ahead.

Every number above is arithmetic on your own Table `tab:solves`. Nothing new was run.

*What to do:* say it. The current framing — "this does not go the way I hoped" — is more
self-critical than the data requires. The accurate framing is: *on the full benchmark the
compact models win; but half the benchmark is saturated, and on the discriminating half
this solver is competitive with two of the three baselines and only the multicommodity
model is clearly ahead.* That is both more honest and considerably stronger.

---

## 2. The `+F` switch is confounded, and there is no control for it

Enabling fractional separation **also disables CPLEX presolve** — the report says so
explicitly. But look at the configuration list:

```
BBC-LP   BBC-LP+T   BBC-K            (presolve ON,  no fractional cuts)
BBC-LP+F   BBC-K+F   BBC-LP+F+H   BBC-LP+F+C   BBC-LP+ACC   BBC-LP+F+P
                                     (presolve OFF, fractional cuts ON)
```

**Presolve-off and fractional-cuts-on are perfectly correlated across all nine regimes.**
No configuration has one without the other. So the headline *"fractional separation costs
69 certified instances"* is not separable from *"disabling presolve costs 69 certified
instances"*. It could be mostly the latter.

The report hedges this correctly ("the campaign does not isolate the cause"). The **deck**
currently states the −69 next to the fractional-cut mechanism, which reads as attribution.

*What survives regardless:* the bound result. *"The terminal dual bound is higher on 0 of
1,404 paired runs"* is a statement about whether these cuts ever tighten the bound. Presolve
does not generate bound-improving cuts. If fractional separation genuinely strengthened the
relaxation you would expect it to win somewhere, presolve or no presolve. It wins nowhere.
**That is the load-bearing measurement and it is not confounded.**

*What to do:* on the fractional-cut slide, lead with the 0-of-1,404, and present the −69 as
confounded rather than as the finding. Expect the question; the answer is that the missing
control is `BBC-LP` with presolve disabled, one more run.

---

## 3. No strengthening was ever tested on the best base

The generalisation of the `BBC-LP+H` hole. Every strengthening — `+H`, `+C`, `+P`, and
`+ACC` — was measured against `BBC-LP+F` (655). But the **best** Benders regime is
`BBC-LP` (724), and **no strengthening was tested on it at all**.

So the ablation answers "what do these do to a weakened solver?" and never asks "what do
they do to the strong one?" Since `+H` is worth +31 on the weak base, and the weak base is
69 behind the strong one, the interesting configuration is missing by construction.

*What to do:* already added to §7.4 and §8.2 of the report. On the day, own it as the first
experiment you would run.

---

## 4. The ablation is asymmetric across the two cut families

`BBC-K` (combinatorial cuts) exists in exactly two forms: bare and `+F`. None of `+H`,
`+C`, `+P` or `+T` was ever tested on the combinatorial-cut family.

So every statement of the form "strengthening X is neutral / harmful" is a statement about
the **dual-cut** family only. Whether the same holds for combinatorial cuts is unmeasured.

*Severity:* low. `BBC-K` (722) and `BBC-LP` (724) behave almost identically, so there is no
reason to expect divergence — but "no reason to expect" is not "measured".

---

## 5. `+T` is never combined with anything

`BBC-LP+T` (723) exists standalone and is one instance behind `BBC-LP` (724) — so triplet
rows are ~neutral on the base. Whether they interact with any strengthening is untested.

*Severity:* low, and §7.4's locality argument explains why triplets are expected to be worth
nothing (they are the weak linearisation of a product and vanish at a half-integral point).
The measurement agrees with the theory. Fine as is.

---

## 6. Thread asymmetry has no control run

Benders is pinned to one CPLEX thread; the compact baselines get four. Disclosed, and it
runs *against* your conclusion, so nothing is overstated. But there is no equal-thread run,
so *"what happens at parity?"* has no answer.

*Combined with finding 1 this matters more than it looks:* your solver is already
competitive with F4 on the discriminating families **at a 4:1 thread disadvantage**.

*What to do:* say exactly that. It is the strongest true sentence available about the
comparison.

---

## 7. The one construction billed as "provably exceeds q" is the least verified thing in the report

`prop:ptf` states that the position–transition relaxation **is at least q and can be
strictly greater**, and §5 calls it *"the one construction in this report that provably
exceeds the coverage bound"*. It carries a lot of weight — it is the entire justification
for the position-indexed route.

Its proof in Appendix A establishes **only the first half**. The "$\ge q$" clause is proved
in three lines by reusing the PCF argument. The **strictness clause is not proved there at
all.** It rests on `obs:ptf-strict`: two Laporte3 instances, `L11-6` and `L11-7`, where the
prototype recorded a root relaxation of 6 against $q=5$.

And that number has never been checked by anything but the prototype that produced it:

- **Appendix B does not mention PTF.** Zero occurrences.
- **`verify_report_independent.py` does not mention PTF.** Zero occurrences.

So the 58 independent checks cover the whole structural theory and none of this.

*What I could verify, and did:* I parsed both instances directly and brute-forced them.
`L11-6`: 8 jobs, 20 tools, $b=15$, so $q=5$, and $\Zst=12$ free-initial. `L11-7`: same
shape, $\Zst=13$. **Both match `obs:ptf-strict` exactly.** So the instances are what the
report says they are and the optima are right.

*What I could not:* the LP value itself. PTF prices ordered pairs of configurations, and
$\binom{20}{15}^2\approx2.4\times10^8$ columns puts a direct solve out of reach here.

*Severity: medium-high, but contained.* Nothing else in the report depends on it — the
diagnosis rests on the *coverage* bound recurring, not on PTF exceeding it. But if one
number in this report is going to be wrong, this is the one with the least protection.

*What to say if asked:* the $\ge q$ half is proved; the strictness is an exhibited witness
whose root value comes from the prototype, and it is not covered by the independent
verifier. Two runs out of 232, by one unit. The report already calls it "of little practical
use as it stands", which is the right register.

---

## 8. §2 says "delete repetitions" where it means "delete *consecutive* repetitions"

Section 2.3, in the sentence establishing the schedule–walk correspondence: *"take any
schedule, delete repetitions from its sequence of magazines, and what remains is a walk of
the same cost"*.

If a magazine recurs non-consecutively ($M_1=M_3\ne M_2$) deleting "repetitions" would
delete a genuine revisit and change the cost. The actual proofs get this right —
`prop:lb1` says "collapse each run of equal consecutive states", `thm:grouping` says
"maximal blocks of consecutive positions sharing one magazine". Only the informal
statement in §2 is loose.

*Severity: low.* One word. But it sits in the conceptual setup that the whole
configuration view rests on, so a careful reader meets it early.

---

## 9. The compact baselines are two steps behind the frontier, and that is never said in one place

Each is disclosed on its own:

- **F4 rather than F5**, which Catanzaro et al. themselves recommend (§3, §6, §7.4).
- **SSPMF rather than JGSMF**, which Akhundov et al. report as outperforming SSPMF (§3).
- And the actual exact frontier is not integer programming at all — Legrand et al.'s
  dynamic-programming and $A^\ast$ search, described in §3 as "the strongest exact
  reproducible published results located for this report".

Individually each is handled honestly. **Compounded, they say: the baselines that beat your
solver are themselves two generations behind the state of the art.** A jury member can
assemble that in one question, and it is worth having the answer ready rather than
assembling it live.

*The answer:* the claim is a **diagnosis, not a ranking**. The finding is that the coverage
bound governs this family of methods, and that survives regardless of where the family sits
against a DP/$A^\ast$ search. And per finding 1, on the discriminating families your solver
is competitive with two of the three baselines anyway.

---

## 10. What the proofs in Appendix A actually establish — checked line by line

- **`thm:grouping`** — both directions correct. The construction schedule→grouping collapses
  consecutive blocks properly. Needs $|T|\ge b$ for the full-magazine step, which the
  standing assumption at §2 line 20 supplies.
- **`prop:unbounded`** — correct, including the "at least $4g+3(g-1)$" step: with $3g-1$
  transitions of which at most $2g$ can be intra-copy at cost 2 and the rest inter-copy at
  cost 3, the minimum is exactly $7g-3$. Terse but sound.
- **The walk lemma** (used by `cor:smallZ` and `prop:k3`(iv)) — the persistence argument is
  correct and all six merge cases are covered. The $(1,2)$ case uses a looser bound than
  persistence actually gives (it concludes $\subseteq\{e_3\}$ where the set is in fact
  empty); harmless, the conclusion needs only $\le1$.
- **`prop:pcf`** — all four claims check out, including the blended point giving relaxation
  exactly 0 without (T) and exactly $q$ with it.
- **`prop:pcfprime`** — correct, and the reverse inequality properly uses (P$'$) rather than
  (P).
- **`prop:ptf`** — see finding 7.

---

## 11. §2 verified cell by cell

The two magazine diagrams are the load-bearing pictures of the report, so I checked them
against the rule rather than reading past them:

- **`fig:ktns`** — every insertion mark, every shaded cell, and every column count.
  All six columns hold exactly three tools; tool 1 is loaded once at position 1 and held to
  position 6; the six insertions are at $(1,t_1),(1,t_2),(1,t_3),(3,t_4),(4,t_5),(5,t_6)$.
  Matches the prose and the KTNS rule exactly.
- **`fig:frames`** — both panels. Panel (a) has seven insertions with tool 1 re-inserted at
  position 5; panel (b) has six with tool 1 held throughout. Every column is exactly full in
  both. The claim that $\{1,3,4\}$ sits at position 3 and $\{1,4,5\}$ at position 4 matches
  the shaded cells.
- **The 6-ring incidence matrix and its ring figure** — edge labels are the correct shared
  tools.
- **The both-bounds-slack instance** ($T_j=\{j,j+1,j+2\}\bmod 8$, $b=4$): brute-forced.
  $K^*=4$, $q=4$, $\Zst=5$. Matches.

---

## What I checked and found nothing wrong with

- **Denominator handling.** Fixed, audited, every planned pair counted once, non-optimal
  counted as unsolved, 58 recovered pairs completed under the same protocol. Clean.
- **Selection on outcome.** None. The eleven non-canonical Catanzaro files are excluded by
  identity, before results, with the count asserted.
- **Cross-method agreement.** 41,514 method pairs on 988 instances, zero disagreements.
- **Convention handling.** Empty-start cost of the returned sequence used uniformly, which
  is the right choice since the native objectives differ.
- **Early stopping.** None in the primary protocol. The BNP early-stop rule is disclosed and
  BNP carries no solve-count claim.
- **Baseline reimplementation risk.** The baselines *win*, so a weak reimplementation only
  strengthens your conclusion. No exposure.

---

## Still unaudited

Stated plainly so you know what is not covered:

- **The solver source.** Never read. The depot-term defect was found by your own testing,
  not by anyone auditing the implementation. This is now the largest unaudited surface.
- **The PTF root LP value** (finding 7) — not computable here, not covered by your verifier.
- **Appendix C** (reproducibility) — skimmed only.
- **§2 integer-programming primer** (§2.7) — read, nothing found, but it is expository and
  carries no results.
