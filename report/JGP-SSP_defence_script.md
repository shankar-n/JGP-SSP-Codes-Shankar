# Defence script — Job Sequencing and Tool Switching

**Shankar Narayanan · LIMOS, Université Clermont Auvergne · 2 September 2026**

35 slides. Main talk 1–26, target 24–25 minutes. Thank-you on 27. Backup 28–34:
the full branch-and-price is 28–31, then per-family results, the ablation and the
validation ledger.

The slides are a guide. What is below is what to **say**; the slide carries the picture
and the numbers only. Speak equations slowly. Never read a table aloud.

---

## Part 0 — Problem, context, questions (slides 1–8, ~7 min)

### Slide 1 · Title — 0:35
Good morning. This internship is about a machine that holds only a few tools at a time.
Every job needs its own subset, so running a set of jobs means stopping to change tools,
and each stop costs production time. I will ask two questions: one structural, one
algorithmic.

### Slide 2 · Outline — 0:15
Context and the two questions; a summary of the structural results; then the exact
methods in detail, which is where most of the work went; results; conclusion.

### Slide 3 · The order decides which tools return — 1:10
Capacity two, machine starts empty. Jobs one, two, three costs four insertions. Jobs
one, three, two costs five — because tool *b* is removed and comes back. Same jobs, same
loading rule; only the order changed.

That returning tool is what this whole talk is about. The word is **reinsertion**.

### Slide 4 · Loading is easy; the order is hard — 1:10
For a fixed order the best loading is known in closed form — evict the tool needed
furthest in the future. Keep Tool Needed Soonest, Tang and Denardo, 1988, linear time.

The order is the opposite: forty thousand orderings of an eight-job instance, and the
problem is NP-hard for every capacity of two or more. All the difficulty is in sequencing.

### Slide 5 · Every stop costs production time — 0:45
The same core appears in CNC cells, circuit-board assembly, colour printing and
warehouse picking: a capacity-*b* resource, jobs needing subsets, a changeover between
consecutive jobs. It matters because the sequence is decided once and paid every shift.

### Slide 6 · State of the art — 1:00
Two threads. Grouping: Crama and van de Klundert proved the industrial two-phase method
is a *b*-approximation in 1999; Burger and co-authors gave an industrial study in 2015.
Exact: the tool-state model, Catanzaro's formulations, the multicommodity model.

Two things absent. A bound on the two-phase loss that depends on **your** instance. And
a relaxation that beats the counting bound.

### Slide 7 · Two questions — 1:00
**Structural:** industry does not solve this problem — it groups into the fewest
magazine-fitting batches, then sequences. What does insisting on the fewest groups cost?

**Algorithmic:** every compact model surveyed relaxes to the counting bound. Can a
method that never forms that relaxation get past it?

### Slide 8 · The configuration view — 1:20
This is the idea both halves run on. A magazine configuration is a set of *b* tools.
Make configurations the nodes of a graph; the step cost from *C* to *C-prime* is the
number of tools you must insert; a schedule is a **walk**, and each job must be served
at a node containing its requirement.

Two consequences. The optimum is a shortest covering walk. And every used tool enters at
least once while at most *b* start loaded — so the optimum is at least the number of used
tools minus the capacity. That is **q**. Watch it; it governs everything that follows.

---

## Part I — Structural results, in summary (slides 9–11, ~3 min)

*Keep this brisk. It is a summary; the detail is in the report and in questions.*

### Slide 9 · Where the loss enters — 1:00
The method groups, orders, then re-optimises with KTNS. The commitment happens at step
one, before anything knows the cost.

The key fact: if you allow **all** feasible groupings, the construction is exact — the
optimum equals the cheapest walk over every grouping. So the method is not wrong in
kind. The loss is precisely the price of insisting on the **fewest** groups.

One caution: two readings must be separated — the walk through one fixed magazine per
group, and the value after KTNS re-optimises. They differ, and the published worst cases
belong to the first.

### Slide 10 · The main result — 1:20
Take *g* copies of a four-job seed, add one universal tool in every job and a private
marker per copy. The universal tool makes the instance **connected**; the markers make
the minimum grouping **unique**.

Then the optimum is eight *g* minus five, the construction reaches nine *g* minus five,
and the loss is *g* — unbounded, on connected instances. That answers the question the
walk reading leaves open.

Be precise: the **additive** loss is unbounded; the **ratio** tends to nine over eight,
so this does not disprove a constant factor.

### Slide 11 · At a glance — 0:45
Everything proved: the grouping identity, zero-gap classes for every capacity, an
instance-sensitive ratio bound that holds uniformly over tie-breaking, four jobs
necessary and sufficient, and the connected unbounded family. One thing open: a
constant-factor bound at capacity three.

> *Transition:* that is the structural half. The rest of the talk is the exact side,
> where most of the implementation went.

---

## Part II — Exact methods (slides 12–20, ~9 min)

### Slide 12 · Two routes — 0:50
The obstacle: every compact model surveyed relaxes to *q* or below. Two classical routes
around a weak relaxation — **decompose**, never forming it; or **reformulate** over
configurations. I built both. The first is the main line; the second is in backup.

### Slide 13 · Benders: the idea — 1:00
The master picks a job order. For that fixed order the loading is polynomial, so the
subproblem is solved **exactly** and returns a cut. The master's bound is therefore built
from true subproblem values, not from a relaxation of the loading. Logic-based and
combinatorial Benders lineage.

### Slide 14 · The master — 1:00
Arc variables over jobs plus a depot marking start and end, so *x* describes a
Hamiltonian path, minimising a stand-in theta. It starts from two lower bounds: the
coverage row, and a pairwise row from how much two adjacent jobs must differ.

### Slide 15 · The subproblem — 1:20
Fix the order. *y* says a tool is in the magazine while a job runs; *z* charges an
insertion. Four constraint families: requirement, capacity, the link across a selected
arc, and the depot link for the first job.

Why it is exact rather than a price: for fixed *x-bar* the master variables sit only on
the right-hand side, the remaining matrix has consecutive ones along the selected path
and is totally unimodular, so the relaxation is integral and its value is the KTNS cost.

### Slide 16 · The cut, in full — 1:20
Because *x-bar* appears only in the objective of the dual, an optimal dual gives this
cut directly. Four multiplier families: the arc links, the depot links, capacity, and
requirement.

Valid globally, because the dual feasible region does not depend on the order. Tight
locally. And affine in *x*, which is why fractional separation needs no separate
argument.

### Slide 17 · One term, and 193 lost optima — 1:10
This is worth telling. The depot sum was initially omitted. The cut then became **too
tight** and cut off genuine optima. Random instances solved both by brute force and by
the solver disagreed on **193** of them.

The term was restored, the derivation rewritten from the implementation, and the whole
campaign re-run. The machine starts empty, so the first magazine must be charged in
full; dropping that term silently assumes the first job's tools are free.

*If asked "how do you know your solver is right?" — this is the answer. It wasn't, I
found out how, and I fixed it.*

### Slide 18 · Cut families and the ablation — 0:50
Two families: dual cuts from the loading LP, and combinatorial cuts from the KTNS value
directly. Then four standard strengthenings — fractional separation, triplet bounds, a
conflict-graph row, Pareto-optimal lifting — plus a hybrid genetic incumbent.

### Slide 19 · Fractional separation — 1:30
The most informative negative result in the work. When a Benders scheme tails off, the
textbook fix is to separate at fractional points. The cut is affine, so this is
legitimate.

And it does exactly what it should, locally: sixty-seven and a half million cuts, median
node count down from seventy-seven thousand to three thousand seven hundred — a factor
of twenty.

Now the other column. Across one thousand four hundred and four paired runs the dual
bound at termination was higher **zero** times. Equal twelve hundred and twenty-six.
Lower a hundred and seventy-eight. And sixty-nine instances were lost.

The remedy is being applied correctly, to the wrong obstacle.

### Slide 20 · The rest, and the one that helped — 1:00
Triplet bounds: neutral. Conflict row: costs one — the coverage row already dominates it.
Pareto lifting: costs thirty-seven, a deeper cut inside the wrong family. Only the
hybrid incumbent helps, and it is the only one aimed at the **primal** side.

That is the pattern: everything aimed at the dual bound is neutral or harmful. A solver
whose difficulty was finding good solutions would not behave like this.

---

## Results and close (slides 21–26, ~4 min)

### Slide 21 · The campaign — 0:45
Nine Benders regimes, three compact baselines, one thousand four hundred and ten
canonical instances, sixteen thousand nine hundred and twenty outcomes, one hour per run
against a fixed denominator. One caveat up front: Benders ran on one thread, the compact
models on four, and Catanzaro F4 stands in for the stronger F5.

### Slide 22 · The baselines certify more — 0:55
This does not go my way and I will say so plainly. The multicommodity model certifies one
thousand and twenty-eight, Catanzaro eight hundred and seventy-six, the tool-state model
eight hundred and thirty-three. My best Benders regime, seven hundred and twenty-four.
With those caveats the margin is if anything understated.

The rest is about **why**, and the reason is not the search.

### Slide 23 · Quick, with a long tail — 0:45
On the five hundred and thirty-one instances everyone solves, the Benders medians are
orders of magnitude below the compact ones. So it is not slow. It closes almost at once
or not within the hour — the signature of a bound that is either exactly right or useless.

### Slide 24 · Closure drops when the bound misses — 1:10
Where coverage is exact, ninety-four per cent. One unit above, thirty-one, then no trend.

Two guards. It is a fact about this master, not the instances — Catanzaro moves the
**other** way and closes all forty-five of the loosest. And not every method whose
relaxation is *q* collapses: the multicommodity model's is also *q* and it loses only
thirteen points. What loses fifty-four is a master carrying coverage and, at the root,
almost nothing else.

And it is a certificate failure, not a discovery failure: two hundred and twenty-three of
three hundred and eighty-three time-limited runs already hold the optimum.

### Slide 25 · What next — 1:00
The through-line: cost is coverage plus reinsertions; every inequality either method
carries sits on one arc or one position; a reinsertion is created across a span.

I tested the obvious repair — a window family counting tools across a stretch. Valid, much
larger ceiling, but its fractional row is **implied** by rows the formulation already has,
and it raised none of the thirty-seven roots measured. Writing a global inequality down is
necessary; it is not sufficient.

Next: disaggregate theta by position; encode job-union structure over a window; test under
a matched protocol. And the grouping result is usable directly — search slightly above the
minimum number of groups, flatten with KTNS, use those as seeds.

The work narrows the next experiment. It does not claim a new state-of-the-art solver.

### Slide 26 · Key References — 0:15
Leave up during questions. Every work listed is cited on a slide.

---

## Backup

### Slides 28–31 · Branch-and-price, in full
**28 — why reformulate.** Configurations become the columns. PCF puts one at each
position; PCF-prime is its prefix form; PTF prices transitions.

**29 — PCF.** Four row families. The counting rows are load-bearing: without them the
relaxation is **zero**, because one convex blend repeated at every position satisfies
everything at no cost. With them it is exactly *q* — proved, and confirmed on all two
thousand one hundred and eight recorded roots.

**30 — PTF.** Columns carry a step, so the relaxation cannot mix configurations without
paying the transition. Hence at least *q*, and it can be strictly greater — the only
construction here that provably exceeds the counting bound.

**31 — pricing.** Choosing the entering configuration is NP-hard, and PTF prices coupled
pairs, so nodes are expensive. Measured: PTF exceeds *q* on two of two hundred and
thirty-two roots, five to six, where the optima are twelve and thirteen. Sound; too rare
and too small to matter yet. Nothing above nine jobs closed — a Python pricer against
compiled solvers.

### Slide 32 · Per-family results
Denominators are one thousand four hundred and ten for every row, so columns are
comparable. Laporte three and four are closed by almost everything; Catanzaro, Crama and
Laporte five separate the methods.

### Slide 33 · The ablation
Reference is Benders with fractional separation at six hundred and fifty-five. Removing
it adds sixty-nine; the hybrid incumbent adds thirty-one; the conflict row costs one;
Pareto lifting costs thirty-seven.

### Slide 34 · Validation ledger
Three hundred and forty-nine thousand loading checks against an independent dynamic
program; nine hundred and eighty-eight instances proved by two methods; forty-one
thousand pairwise comparisons, none disagreeing.

---

## Questions to expect

**"What does your approximation result guarantee?"** It bounds the best value the
construction can attain over the choices the procedure leaves open — not a guarantee for
one deterministic tie-breaking implementation.

**"Why isn't this implied by Crama and van de Klundert?"** Their *b*-approximation is the
starting point. This refines it to a bound depending on *b*, *K-star* and *q*, adds
zero-gap classes, and separates the walk reading from the KTNS-refined one.

**"Does ninety-four versus forty prove *q* causes difficulty?"** No. Strong
method-specific association; the Catanzaro control shows the loose instances are not
intrinsically hard.

**"Did the Benders implementation work first time?"** No — slide 17. The depot term was
omitted, one hundred and ninety-three violations were found, it was fixed and the
campaign re-run.

**"Why is branch-and-price only in backup?"** Because its conclusions rest on the root
relaxation value, which slide 24 already reports; its solve times measure a Python
pricer, not the formulation.
