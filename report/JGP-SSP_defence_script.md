# Defence script — Job Sequencing and Tool Switching

**Shankar Narayanan · LIMOS, Université Clermont Auvergne · 2 September 2026**

Main talk: slides 1–29, target 24–25 minutes. Backup: 30–32, for questions only.
Slide 2 is the outline (name the five parts, 15 seconds). Slide 29 is Thank You.

The slides are a guide. What is written here is what to *say*; the slide carries only the
picture and the numbers. Speak the equations slowly. Never read a table cell aloud unless it
is quoted below.

---

## Part 0 — Setting up (slides 1–8, ~7 min)

### Slide 1 · Title — 0:35
Good morning. This internship is about a machine that can hold only a few tools at a time.
Every job needs its own subset of tools, so running a set of jobs means stopping to change
them, and each stop costs production time. I will ask two questions about that: one
structural, one algorithmic.

> *Transition:* let me show you why the order of the jobs is the whole problem.

### Slide 3 · The order decides which tools return — 1:10
Magazine capacity two, machine starts empty. Run the jobs one, two, three and you pay four
insertions. Run them one, three, two and you pay five — because tool *b* is removed and then
comes back. Same jobs, same magazine, same loading rule. Only the order changed.

That returning tool is the object this entire talk is about. Remember the word **reinsertion**.

> *Transition:* so how hard is each of the two decisions?

### Slide 4 · Loading is easy; the order is the hard part — 1:15
For a **fixed** order the best loading is known in closed form: when a tool must go in and the
magazine is full, evict the one needed furthest in the future. That is Keep Tool Needed
Soonest, Tang and Denardo, 1988. Linear time.

The order is the opposite. Forty thousand three hundred and twenty orderings of an eight-job
instance, one hundred and eighty of them optimal, and the problem is NP-hard for every fixed
capacity of two or more. So all the difficulty sits in the sequencing.

> *Transition:* and this is not a toy.

### Slide 5 · Every stop costs production time — 0:50
The same core appears in CNC cells with a tool magazine, in circuit-board assembly with
feeder slots, in colour printing with ink cartridges, and in warehouse picking. A capacity-*b*
resource, jobs needing subsets, a changeover paid between consecutive jobs.

It matters because the sequence is decided once and then paid for on every shift.

> *Transition:* here is what the literature has settled.

### Slide 6 · State of the art — 1:05
Two threads. On the grouping side: Crama and van de Klundert proved in 1999 that the
industrial two-phase method is a *b*-approximation, and Burger and co-authors gave an
industrial study in 2015. On the exact side: Laporte's tool-state model, Catanzaro's
formulations, the multicommodity model, and more recent dynamic-programming work.

Two things the timeline does not contain. A bound on the two-phase loss that depends on the
instance in front of you. And a relaxation that gets past the elementary counting bound.

> *Transition:* those two absences are my two questions.

### Slide 7 · Two questions — 1:00
**Question one, structural.** Industry does not solve this problem. It groups jobs into as few
magazine-fitting batches as possible, then sequences the batches. What does insisting on the
*fewest* groups actually cost — after the final KTNS step is allowed to re-optimise?

**Question two, algorithmic.** Every compact model I surveyed relaxes to the counting bound.
Can a method that never forms that relaxation get past it?

Part one answers the first, and finds an unbounded loss. Part two answers the second, and the
answer is no — for a reason worth naming.

> *Transition:* both halves run on one idea, so let me put it up first.

### Slide 8 · The configuration view — 1:15
A magazine configuration is a set of *b* tools. Make those the nodes of a graph. The cost of
stepping from *C* to *C-prime* is the number of tools you must insert. A schedule is then a
**walk** through configurations, and every job must be served at some node containing its
requirement.

Two consequences. The optimum is a shortest covering walk. And every used tool must enter at
least once, while at most *b* can be loaded before the first job — so the optimum is at least
the number of used tools minus the capacity. Call that **q**, the coverage bound.

Watch *q*. It governs both halves of this talk.

---

## Part I — The structural question (slides 9–15, ~7 min)

### Slide 9 · Grouping commits before it sees the sequence — 1:00
The method has three steps: group into the fewest magazine-fitting batches; order the groups
and the jobs; then re-optimise the loading with KTNS. The commitment happens at step one,
before anything knows what the sequence will cost.

Write **Z-star** for the true optimum, and **H** for the best the construction can reach. The
question is the difference.

> *Transition:* first, is the fewest-groups rule the thing that costs you?

### Slide 10 · Drop the fewest-groups rule and grouping is exact — 1:00
If you allow **all** feasible groupings rather than only the minimum-cardinality ones, the
cheapest walk equals the optimum exactly. So the two-phase construction is not wrong in kind.
The loss enters at exactly one place: the insistence on the fewest groups.

Note the careful bit — that identity is about the fixed-configuration walk value, not about
what the method returns after KTNS re-optimises. They differ, and separating them is what
makes the rest correct.

> *Transition:* so does the loss ever actually occur?

### Slide 11 · Four jobs are enough — 1:00
Yes, and four jobs suffice. Seven tools, capacity four. The only feasible pair is A with B, so
every minimum grouping is forced. The optimum is three; the best the construction reaches is
four. Four jobs are also necessary — with three, every grouping leaves the order free.

> *Transition:* one witness is not a theorem about growth.

### Slide 12 · One shared tool makes the family connected — 1:10
Take *g* private copies of that seed. Add one universal tool in every job, and a private marker
per copy. Now the two large jobs of a copy fill all six slots, small jobs from *different*
copies need seven tools and cannot share, so the minimum grouping is **unique**: three groups
per copy, three *g* in total.

The universal tool is what makes this connected, which matters — a disconnected family would
prove much less.

### Slide 13 · The unrestricted order reaches coverage — 0:50
Unrestricted, you can attain the bound. Process copy by copy in the order B, C, A, D, holding
the universal tool throughout. Every newly loaded tool is a first occurrence, nothing is ever
reinserted, so the optimum equals *q*, which is eight *g* minus five.

### Slide 14 · Every minimum grouping forces one return — 1:00
Now constrain to a minimum grouping. A and B must be consecutive. Counting what can sit in the
free initial magazine, each copy needs one private tool to leave and come back. That is one
forced reinsertion per copy, and the grouped order attains exactly that.

### Slide 15 · The additive gap grows without bound — 1:00
Putting the two together: the optimum is eight *g* minus five, the construction reaches nine *g*
minus five, so the gap is *g*. It grows without bound, on **connected** instances.

Be precise about the two measures. The additive loss is unbounded. The **ratio** tends to nine
over eight, so this family does not disprove a constant-factor bound.

---

## Part II — The algorithmic question (slides 16–22, ~6 min)

### Slide 16 · Two routes past the counting bound — 0:55
The obstacle: every compact model surveyed relaxes to *q* or below. Two classical routes get
around a weak relaxation. **Decompose** — never form the relaxation at all. Or **reformulate** —
optimise over configurations directly. I built both.

### Slide 17 · Order in the master, loading in an exact oracle — 1:05
Benders. The master picks a job order. The loading subproblem for that fixed order is
polynomial, so it is solved **exactly** and returns a cut. The master's bound is therefore
assembled from true subproblem values rather than from a linear relaxation of the loading.

This puts it in the logic-based and combinatorial Benders lineage.

### Slide 18 · The master starts from local and coverage bounds — 0:50
The master is a Hamiltonian path over jobs with a depot marking start and end, minimising a
stand-in theta. It starts with two lower bounds: the coverage bound, and a pairwise bound from
how much two adjacent jobs must differ.

### Slide 19 · The loading LP is integral on a fixed path — 0:55
For a fixed order the loading linear program has the consecutive-ones structure and is totally
unimodular, so its relaxation is integral and its value is exactly the KTNS cost. That is why
the oracle is exact rather than a heuristic price.

### Slide 20 · The dual cut is supported only on arcs — 1:10
From an optimal dual we collect transition prices into arc coefficients, giving a cut that is
tight at the current path and valid for every path. Validity is not the issue.

Here is the issue, and it is the intellectual centre of the talk. A reinsertion depends on a
tool leaving and returning **across a span** of positions. Every coefficient in this cut is
attached to a single adjacency. The cut cannot see the thing that creates the cost.

### Slide 21 · Configurations as columns — 1:10
The other route. PCF puts one configuration at each position. Without the per-tool counting
rows its relaxation collapses to zero; with them it is exactly *q* — proved, and confirmed on
every one of two thousand one hundred and eight recorded roots. PCF-prime removes the symmetry
of empty positions and does not change the value.

PTF is the one that can do better: a column carries a **transition**, so the relaxation cannot
avoid paying for it, and its bound provably can exceed *q*. The price is that pricing is
NP-hard, and PTF prices coupled pairs, so a node costs far more.

### Slide 22 · The campaign — 0:50
Nine Benders regimes and three compact baselines. One thousand four hundred and ten canonical
instances, twelve configurations, sixteen thousand nine hundred and twenty outcomes, one hour
per run against a fixed denominator. Costs rechecked against one common KTNS oracle.

One fairness caveat, stated up front: Benders ran on one solver thread, the compact models on
four, and Catanzaro F4 stands in for the stronger F5.

---

## Results and close (slides 23–28, ~4 min)

### Slide 23 · Every compact baseline certifies more than Benders — 0:55
This does not go my way, and I want to say so plainly. Against the same denominator the
multicommodity model certifies one thousand and twenty-eight, Catanzaro F4 eight hundred and
seventy-six, the tool-state model eight hundred and thirty-three. My best Benders regime
reaches seven hundred and twenty-four. With the thread and F5 caveats, the margin is if
anything understated.

The rest of this section is about *why*, and the reason is not the search.

### Slide 24 · Benders is quick, with a long tail — 0:50
Restricted to the five hundred and thirty-one instances everyone solves, the picture inverts:
the Benders medians are orders of magnitude below the compact ones. So it is not slow. It
either closes almost at once or not within the hour — the signature of a bound that is either
exactly right or useless.

### Slide 25 · Closure drops when the bound misses — 1:10
Group by how far the optimum sits above coverage. Where coverage is exact, ninety-four per
cent. One unit above, thirty-one, and then no trend.

Two guards. It is a fact about this master, not about the instances — Catanzaro F4 moves the
*other* way and closes all forty-five of the loosest. And it is not true of every method whose
relaxation is *q*: the multicommodity model's relaxation is also *q* and it loses only thirteen
points. What loses fifty-four is a master carrying coverage and, at the root, almost nothing
else — eighty-seven per cent of roots sit exactly on that row.

And it is a certificate failure, not a discovery failure: among time-limited runs whose
optimum is known, two hundred and twenty-three of three hundred and eighty-three already hold
it.

### Slide 26 · What next — 1:00
The through-line: cost is coverage plus reinsertions; every inequality either method carries is
attached to one arc or one position; a reinsertion is created across a span.

I tested the obvious repair. A window family counting tools across a stretch of positions is
valid and has a much larger ceiling — but its fractional row turns out to be **implied** by rows
the formulation already has, and it raised none of the thirty-seven roots measured. Being able
to write a global inequality down is necessary; it is not sufficient.

So: disaggregate theta by position; encode job-union structure over a window; test under a
matched protocol. And the grouping result is usable directly — search slightly more than the
minimum number of groups, flatten with KTNS, and use those as seeds.

The work narrows the next experiment. It does not claim a new state-of-the-art solver.

### Slides 27–28 · Key References — 0:15
Leave this up while you take questions.

---

## Backup (only if asked)

### Slide 30 · Certified optima by method and family
Per-family denominators are one six zero, one six zero, three four zero, three three zero,
three four zero and eighty — one thousand four hundred and ten for every row, so the columns
are comparable. Laporte three and four are closed by almost everything; Catanzaro, Crama and
Laporte five are where the methods separate.

### Slide 31 · Fractional cuts spend more and certify less
Reference is Benders with fractional separation at six hundred and fifty-five. Removing it
adds sixty-nine. The hybrid incumbent adds thirty-one; the conflict row costs one; Pareto
lifting costs thirty-seven.

Fractional separation does work locally — median nodes fall from seventy-seven thousand to
three thousand seven hundred, using about sixty-seven million cuts. But across one thousand
four hundred and four paired terminal bounds it is higher **zero** times, equal one thousand
two hundred and twenty-six, lower one hundred and seventy-eight.

### Slide 32 · Proof and validation ledger
For the connected family: capacity limits what sits in the free initial magazine, the seed
forces one reinsertion per copy, and counting first appearances plus those returns gives the
lower bound; the grouped construction attains it.

For the campaign: three hundred and forty-nine thousand loading checks against an independent
dynamic program, nine hundred and eighty-eight instances proved by two methods, forty-one
thousand pairwise comparisons, none disagreeing.

---

## Questions to expect

**"What exactly does your approximation result guarantee?"**
It bounds the best value the construction can attain over the choices the procedure leaves
open. It is not automatically a guarantee for one deterministic tie-breaking implementation.

**"Why isn't this implied by Crama and van de Klundert?"**
Their *b*-approximation is the starting point. This refines it to a bound depending on *b*,
*K-star* and *q*, identifies zero-gap classes, and separates the walk reading from the
KTNS-refined one.

**"Does ninety-four versus forty prove that *q* causes difficulty?"**
No. It is a strong method-specific association, and the F4 control shows the loose instances
are not intrinsically hard.

**"Did your Benders implementation work first time?"**
No. The depot term was initially omitted, which produced invalid cuts; one hundred and
ninety-three violations were found, the term was restored, and the campaign was re-run.
