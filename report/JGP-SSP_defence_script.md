# Defence script — Job Sequencing and Tool Switching

**Shankar Narayanan · LIMOS, ISIMA / Université Clermont Auvergne · 2 September 2026**

Main talk: **slides 1–35, target 29:20** for a 25–30 minute slot.
Quoted paragraphs are the verbatim speech. *Italic lines are delivery cues, not spoken.*
Slides 36–37 are references; 38–48 are backup. Neither is part of the timed talk.

**Slides 3, 10, 13, 20, 25 and 30 are section dividers.** Each carries one line. Read it,
do not elaborate, move on — about 10 seconds each, 1:00 in total.

Running total after each slide, so you can tell mid-talk whether you are ahead or behind.

---

## Part 1 — The problem (slides 1–9, 7:10)

### Slide 1 · Title — 0:35 *(0:35)*
> Good morning. This internship was carried out at LIMOS under Professor Colares and
> Professor Wagler, with Doctor Chicoisne as academic supervisor. The subject is a
> scheduling problem that comes from flexible manufacturing: the job sequencing and tool
> switching problem. I will spend the first part of the talk making sure the problem
> itself is clear, then give one structural result about the heuristic that industry
> actually uses, and spend the rest of the talk on the exact method that was the main
> computational work.

### Slide 2 · Outline — 0:20 *(0:55)*
> Six parts. The problem and the two questions; the structural results, which I will keep
> short; then the branch-and-Benders-cut algorithm and its strengthenings, which is where
> most of the time goes; the computational results; and what they say about the limits of
> the approach.

*Do not read the list aloud item by item. Point at it once and move on.*

### Slide 4 · A machine, a magazine, and a set of jobs — 1:10 *(2:15)*
> Here is the whole setting, and it needs no mathematics.
>
> A machine makes many different parts. Each part is a job, and each job needs its own
> small set of tools — a particular drill, a particular cutter. The tools the machine can
> reach are held in a carousel called the magazine, and the magazine is small. In the
> picture it holds two tools; in a real machine it might hold twenty or thirty, against
> hundreds in the workshop.
>
> To run a job, every tool that job needs must be sitting in the magazine at that moment.
> So between jobs you often have to take a tool out and put another one in. That stops
> the machine. The stop is what costs money, not the metal cutting, and so the quantity
> to minimise is simply the number of tool insertions over the whole batch.
>
> There are two decisions: in what order to run the jobs, and what to keep loaded at each
> step. Almost everything in this talk follows from the fact that those two decisions are
> completely different in difficulty.

*This is the slide that decides whether the rest lands. Do not rush it. Point at the
grey box when you say "magazine", and at a red arrow when you say "stops the machine".*

### Slide 5 · Why the order matters — 1:00 *(3:15)*
> Now watch what the order does. Same three jobs, same magazine of two, same rule for
> deciding what to keep.
>
> On the top row the jobs run one, two, three. Job one needs tools a and b; job two needs
> b and c, so b is already there and only c comes in; job three needs c and d, so only d
> comes in. Four insertions, and that is optimal.
>
> On the bottom row the only change is that job two runs last. Now tool b is thrown out
> to make room for job three, and then has to come back for job two. Five insertions —
> one wasted.
>
> That extra event, a tool that leaves the magazine and later returns, is called a
> reinsertion, and it is the single object this whole talk is about. Every question I ask
> is some version of: where do reinsertions come from, and can we prove a schedule has as
> few as possible?

### Slide 6 · Schedules as walks through configurations — 1:10 *(4:25)*
> One more picture, and then the notation, which is all I will need.
>
> Call a full magazine a configuration. Then a schedule is nothing but a walk: you stand
> in one configuration, you run whichever jobs that configuration can serve, you step to
> the next configuration, and the price of that step is the number of tools that enter.
> The picture shows two walks over the same instance — the top one visits four
> configurations and costs three; the bottom one visits three and costs four. Fewer stops
> is not the same as fewer insertions, and that gap is the subject of the next part.
>
> Now the notation, which is four symbols. Let b be the magazine capacity. Let T-sub-j be
> the set of tools that job j needs. Let U be the set of tools the instance actually uses.
> And let Z-star be the smallest number of insertions any schedule can achieve — the thing
> we are trying to compute.
>
> There is an elementary lower bound on Z-star, and it will govern the entire second half
> of the talk. At most b tools can be sitting in the magazine before the first job. Every
> other tool that the instance uses has to enter at some point. So the number of
> insertions is at least the number of used tools minus the capacity. Call that number q.
> It is a counting argument, nothing more.

*Say "q" as "the count q" the first few times so the audience keeps hold of it.*

### Slide 7 · One decision is easy, the other is not — 1:00 *(5:25)*
> With that in place, here is why this problem is interesting.
>
> If somebody hands you the order, the loading is easy. There is a rule: when a tool has
> to come into a full magazine, throw out the tool whose next use lies furthest in the
> future. Keep the tool needed soonest. Tang and Denardo proved in 1988 that this rule is
> not just good, it is optimal, and it runs fast.
>
> Choosing the order is the opposite. Crama and co-authors proved in 1994 that it is
> NP-hard for every magazine capacity of two or more. Not for large capacity — for every
> capacity.
>
> The histogram is one eight-job benchmark instance with all forty thousand three hundred
> and twenty of its orders enumerated. The optimum is thirteen, and only one hundred and
> eighty orders out of forty thousand reach it. The dashed line on the left is the count
> q, which is ten — three short of the truth, and no ordering ever gets down to it.
>
> An easy inner problem inside a hard outer one is exactly the shape decomposition methods
> are built for. Hold on to that; it is why the second half of the talk exists.

### Slide 8 · Where the literature stops — 1:00 *(6:25)*
> Two lines of work, and each leaves something open.
>
> On the practical side, industry does not attack this problem directly. It first packs
> the jobs into as few magazine-feasible batches as it can, then orders the batches.
> Crama and van de Klundert proved this construction is a b-approximation, and Burger and
> co-authors measured it against exact optima on an industrial printing press and found it
> does well. What nobody has given is an account that depends on the instance in front of
> you — when does this construction actually lose, and by how much?
>
> On the exact side there are four decades of integer programming models: tool-state,
> arc-flow, multicommodity. Of the three I reimplemented as baselines, the strongest has a
> linear relaxation equal to exactly that elementary count q. So the models are only as
> good as the counting argument. What is missing is a certificate for the instances where
> q is not the answer.

### Slide 9 · The two questions — 0:45 *(7:10)*
> So, two questions.
>
> First, the structural one. The grouping construction insists on the fewest possible
> groups. What does that insistence cost, once the resulting job order is reloaded
> optimally by the KTNS rule at the end? That question needs no solver at all — it is a
> question about the construction.
>
> Second, the algorithmic one. Can an exact loading oracle carry a decomposition past the
> counting bound q?
>
> And notice both questions live on the same picture. One restricts which walks the
> construction is allowed to use. The other asks what a solver can prove about all of them.

---

## Part 2 — Structural results (slides 10–12, 3:10)

*Divider slide 10, then two slides. This is the part of the work I would lead with if I
only had five minutes.*

### Slide 11 · The standard worst-case example is not a worst case — 1:30 *(8:50)*
> This is the result I would put first, and it needs no notation at all.
>
> The construction produces groups of jobs. But what does it actually return? There are two
> honest answers, and the literature has not separated them.
>
> On the left is the picture the literature draws: pick one magazine per group, hold it
> while that group runs. Every published worst-case example for this method is built on this
> picture. On this instance it pays one extra insertion — a gap.
>
> On the right is what the method as specified actually does. It takes the job order the
> grouping induces, throws the grouping away, and reloads from scratch with the optimal
> rule. On the same instance it pays nothing extra. It is optimal.
>
> And this instance is not an arbitrary one. It is *the* example the field reaches for
> whenever it wants to show this heuristic losing. Under the method people actually run, it
> does not lose.
>
> So a worst case proved about the left-hand picture and reported as a result about the
> heuristic is simply not a result about the heuristic. Separating the two is a
> precondition for everything else I say about this method.

*If pressed on how much slack this hides: on the whole ring family at capacity three, from
three jobs to nine, the left-hand value separates from the optimum and the right-hand value
never does. Table is in the report.*

### Slide 12 · So the loss is real — but you need a different construction — 1:30 *(10:20)*
> The obvious next question is whether the loss was ever real, or whether the whole
> worst-case story was an artefact of drawing the wrong picture. It is real. But you need a
> genuinely different construction, and the left-hand panel is it.
>
> Take the smallest four-job instance that has a gap at all and make $g$ private copies of
> it. Then add one tool that every single job needs, and one marker tool per copy that every
> job of that copy needs. Capacity six.
>
> Those two additions force the grouping. $C_i$ and $D_i$ already fill all six slots, so
> each must sit alone. $A_i$ and $B_i$ together need exactly six, so they fit — but $A_i$
> with any job from a *different* copy needs seven, because their private tools and their
> markers are disjoint. So there is exactly one minimum grouping, and no clever cross-copy
> grouping can rescue it.
>
> The right-hand panel is what that costs. The optimum is $8g-5$, the heuristic returns
> $9g-5$, and the two lines pull apart at exactly one insertion per copy. The loss is $g$,
> and it never stops growing.
>
> Two things to notice. Every job contains the shared tool, so the instance is connected —
> this is not the cheap trick of gluing $g$ separate problems side by side. And the ratio
> tends to nine eighths, so the additive loss is unbounded while a constant-factor guarantee
> survives. That combination is the honest statement.
>
> And where does the loss come from? Exactly one place. Allow every feasible grouping,
> of any size, and the construction becomes exact. The loss is the price of insisting on the
> fewest groups, and nothing else in the method is at fault.

*Verified by exhaustive enumeration at $g=1$ and $g=2$ by a program sharing no code with
the solvers.*

## Part 3 — The branch-and-Benders-cut algorithm (slides 13–19, 6:20)

### Slide 14 · The decomposition — 1:00 *(11:30)*
> Now to the main computational work, and it starts from the observation I flagged
> earlier: an easy problem sitting inside a hard one.
>
> The hard part is the order. That goes into a master problem. The easy part is the
> loading, and instead of modelling it, we hand it to an oracle that solves it exactly.
>
> The loop is this. The master proposes an order, together with an optimistic guess theta
> for what that order will cost to load. The subproblem returns the true loading cost of
> that order. If theta was too low, we add one inequality that lifts it — and, crucially,
> that inequality is valid for every order, not only the one we just tried. Repeat until
> theta agrees with reality; then the order in hand is a certified optimum.
>
> Because the subproblem is solved exactly rather than relaxed, this sits in the
> logic-based and combinatorial Benders lineage of Hooker and Ottosson and of Codato and
> Fischetti.

### Slide 15 · The master problem — 1:10 *(12:40)*
> The master is a Hamiltonian path model. Introduce a depot with no tool requirement to
> mark the start and the end, and let x-i-j be one when job j runs immediately after job
> i. The assignment constraints and the subtour elimination constraints make the x
> variables describe a path through the jobs, and the objective is just theta.
>
> One convention point, because it will come back. The theory in the first half uses a
> free initial magazine, where the count is q equals U minus b. The solver charges the
> first fill, so in the solver's convention the same coverage argument reads theta is at
> least the size of U. Same argument, shifted by b.
>
> Two families of rows bound theta before any cut is generated. The coverage row I just
> gave. And a pairwise row: between two consecutive jobs, at least the excess of their
> combined requirement over the capacity must be switched — that is the classical Tang and
> Denardo bound — plus the first job's whole requirement on the depot arc.
>
> Both of these are visible to the linear relaxation from the start. Remember that.

### Slide 16 · The subproblem: loading for a fixed order — 1:00 *(13:40)*
> The subproblem has to be written in the master's own variables, or the inequality it
> produces cannot be added back.
>
> So: fix a candidate order x-bar. Let y-j-t say that tool t occupies the magazine while
> job j runs, and let z-j-t charge an insertion of t at j. Then the first row says every
> tool a job needs is present. The second says the magazine holds at most b. The third is
> the only place the master's variables appear: if the master selected the arc from i to j,
> and a tool is present at j but absent at i, it had to be inserted. And the fourth does
> the same for the first job, charging its entire requirement, because the machine starts
> empty.
>
> The Greek letters in the right margin are the dual variables. They are what the cut is
> built from, and they are the only reason I am showing you this model at all.

### Slide 17 · Why the oracle is exact — 1:00 *(14:40)*
> This is the slide that makes the method honest, so I want to be precise.
>
> Once x-bar fixes a path, the master's variables sit only on the right-hand side. What
> remains is a linear program in y and z alone. Its constraint matrix has the
> consecutive-ones property along that path, and is therefore totally unimodular. So the
> linear program is integral, and its optimum is exactly the KTNS value of the order.
>
> The consequence is that the loading is never approximated and never relaxed. Every
> incumbent order the solver holds has been evaluated at its true cost. It is an oracle,
> not a price.
>
> What remains in question — and this is the whole rest of the talk — is whether the
> master accumulates a strong enough lower bound to prove that no better order exists.

### Slide 18 · The optimality cut — 1:00 *(15:40)*
> Here is the cut in full. Take any optimal dual solution of that loading program and
> substitute; weak duality gives you this inequality on theta.
>
> Three properties, and each matters later.
>
> It is globally valid. The dual feasible region does not depend on x-bar at all — only
> the objective does — so the same dual point certifies a bound for every order. One
> subproblem solve buys information about the whole space.
>
> It is tight at the order we priced. So the method makes progress at every iteration.
>
> And it is affine in x. That means we can separate it at a fractional point, before an
> integral order exists, with no extra argument needed. That will become one of the
> strengthenings.
>
> Now look at the shape of it. Collect terms and the coefficient on x-i-j is a sum of
> duals over tools. Every cut this master ever receives is supported on arcs. Please hold
> on to that observation — it is the punchline of the talk.

### Slide 19 · A defect found and corrected — 1:00 *(16:40)*
> I want to show one thing that went wrong, because it changed the results and because it
> is the kind of error that hides.
>
> The depot term in that cut is non-positive. So if you drop it, the cut gets tighter, not
> looser. An implementation that omits it looks correct — it produces plausible answers on
> most instances, and it never crashes. But degenerate dual optima put weight on depot
> arcs the order does not even use, and the over-tight cut then removes genuinely optimal
> points. The solver returns a number that is too high and calls it proven.
>
> It was caught by testing cuts against brute-force optima: one hundred and ninety-three
> violated optimal points before the term was restored. The term went back in, the cut was
> rederived from the implementation rather than from my draft, and the entire campaign was
> re-run.
>
> This is why the validation I will refer to later runs against an independent enumeration
> and an independent dynamic program, rather than against agreement with my own solver.

*Do not apologise for this slide. A jury reads it as evidence the work was checked.*

---

## Part 4 — Strengthening the solver (slides 20–24, 3:55)

### Slide 21 · Four strengthenings — 0:50 *(17:40)*
> Four strengthenings, all classical, all from the Benders toolbox surveyed by Rahmaniani
> and co-authors. Each was implemented as an independent switch and checked against brute
> force before any campaign run, so that a strengthening can never silently return a wrong
> answer.
>
> But look at the middle column, because it is the reason this table is on the slide.
> Fractional separation and the conflict-graph row aim at the dual bound. The root
> heuristic aims at the primal side — at the incumbent. Pareto lifting does not add
> information at all; it chooses among cuts we could already generate.
>
> Three different targets. Watch which kind helps.

### Slide 22 · Fractional Benders cuts — 1:05 *(18:45)*
> The first one, and the most instructive failure in the whole project.
>
> The intention is standard. An integer-only scheme learns about loading cost only once an
> order is fully committed. A fractional cut extracts the same dual information from a
> partial order and removes it from the relaxation immediately. It is the textbook remedy
> for tailing-off, and it is legitimate here because the cut is affine in x.
>
> And locally, it does exactly what it should. Sixty-seven million cuts were generated.
> The median node count fell from seventy-seven thousand to three thousand seven hundred —
> a factor of twenty. The tree really does shrink.
>
> Now the number that matters. Across fourteen hundred and four paired runs, the dual bound
> at termination was higher on **zero** instances. Not one.
>
> I want to be careful about what I lean on here. This regime also disables presolve in my
> implementation, so the sixty-nine certified instances it loses is a confounded figure and
> I do not use it as evidence. But whether these cuts ever *raise the bound* is not
> confounded — presolve does not generate bound-improving cuts. If fractional separation
> genuinely strengthened this relaxation it would have to win somewhere. It wins nowhere.
>
> A correct remedy, applied competently, to the wrong obstacle.

*If pushed: the missing control is the base solver with presolve disabled and no
fractional cuts. It was never run. One more configuration would settle it.*

### Slide 23 · A strong incumbent at the root — 0:55 *(19:40)*
> The second one is the only strengthening that aims at the primal side.
>
> A branch-and-bound search prunes in proportion to how good its incumbent is, so a
> compact form of the hybrid genetic search of Mecler and co-authors is run once at the
> root — constructive seeds, a variable-neighbourhood local search, order crossover with a
> diversity guard, and every candidate scored by the exact loading oracle.
>
> The resulting order is then used twice. As a warm start, it gives the solver an
> incumbent from node zero. And it seeds a cut: solve the loading dual once for that
> heuristic order and add its cut before the first relaxation. That is the initial cut pool
> acceleration.
>
> It gains thirty-one instances. It is the only one of the four that gains anything, and it
> is the only one aimed at the incumbent rather than the bound.

### Slide 24 · The conflict-graph row, and Pareto lifting — 0:55 *(20:35)*
> The remaining two, quickly, because they behave the same way.
>
> The conflict-graph row looks for combinatorial structure the linear relaxation cannot
> see. Jobs that cannot share a magazine form edges of a graph; a colouring lower bound on
> that graph forces a number of configurations and hence a number of switches. It is the
> simplest of the Atamtürk conflict-graph inequalities. Its reach is narrow by
> construction, because on most instances the coverage row already dominates it. Measured
> effect: minus one instance.
>
> Pareto lifting attacks a real weakness. The loading dual is degenerate, so it has many
> optima, and the cuts they yield are not equally strong. Magnanti and Wong say to pick the
> deepest at an interior core point; Papadakos makes that practical. Measured effect: minus
> thirty-seven.
>
> A deeper cut, selected properly, from the same family. Which tells you the problem is the
> family, not the selection.

---

## Part 5 — Computational results (slides 25–29, 4:25)

### Slide 26 · How far each method gets — 1:00 *(21:45)*
> The campaign. Fourteen hundred and ten canonical instances, twelve configurations,
> sixteen thousand nine hundred and twenty planned outcomes, all present. One hour per run.
> And a fixed denominator: every planned pair counts once, and any outcome that is not a
> proven optimum counts as not closed. Nothing is dropped because it went badly.
>
> Here is the result on the full denominator, and it does not go the way I hoped. Every
> compact baseline certifies more than every Benders regime. The multicommodity model closes
> one thousand and twenty-eight; my best Benders configuration closes seven hundred and
> twenty-four.
>
> And the caveats run against me, not for me. Benders had one effective solver thread and the
> compact models had four. Catanzaro's Formulation 4 stands in for the stronger Formulation 5
> its own authors recommend.
>
> But that number hides something, and the next slide separates it out.

*Do not soften this. Owning it here is what makes the diagnosis credible later.*

### Slide 27 · Half the benchmark cannot tell the methods apart — 1:10 *(22:55)*
> Look at where the margin comes from. Laporte3 and Laporte4 are six hundred and seventy of
> the fourteen hundred and ten instances — nearly half — and all three compact models close
> a hundred per cent of both. Those families contribute six hundred and seventy to every
> compact count and cannot distinguish between methods at all. They are denominator, not
> evidence.
>
> Restrict to the seven hundred and forty instances where the methods actually separate, and
> the ordering changes. The multicommodity model still leads at forty-eight per cent. But my
> best Benders regime is at twenty-eight point eight, ahead of Catanzaro's Formulation 4 at
> twenty-seven point eight and well ahead of the tool-state model at twenty-two. And it does
> that on one solver thread against their four.
>
> I want to be careful: this does not overturn the previous slide. The full-denominator
> comparison is the one I committed to in advance, and on it the compact models win. What
> this slide does is locate the margin. The statement that survives both readings is that the
> multicommodity model certifies more than anything I built — on either denominator.

*Every number here is arithmetic on the per-family table already in the report. Nothing new
was run.*

### Slide 28 · Solving times — 0:55 *(23:50)*
> Now restrict to the five hundred and thirty-one instances that every method solves, so we
> are comparing like with like. The picture inverts. The Benders medians sit orders of
> magnitude below the compact ones — note the axis is logarithmic, so those are factors of
> hundreds, not percentages.
>
> But look at the whiskers. The distribution is not slow; it is bimodal. This method closes
> an instance almost immediately, or it does not close it within the hour. There is very
> little in between.
>
> That shape is the signature of a bound that is either exactly right or of no use at all.
> Which is exactly what the next slide measures.

### Slide 29 · What separates the two cases — 1:10 *(25:00)*
> So take the eleven hundred and seven instances whose optimum we know, and split them by a
> single structural property: is the elementary count q equal to the optimum, or not?
>
> Where q is exact, the Benders solver certifies ninety-four per cent. Where it is loose by
> one single unit, it certifies thirty-one per cent. And after that there is no trend at
> all — once the bound is wrong, by how much stops mattering. It is not degradation. It is a
> cliff.
>
> Now, the tempting conclusion is that the loose instances are simply harder. That
> conclusion is wrong, and I have two measurements against it. Formulation 4 moves the
> other way — it closes a larger share of the loose instances than of the tight ones, and
> it closes all forty-five of the very loosest, at a median of ninety-three seconds. And
> the multicommodity model, whose relaxation is also exactly q, loses only thirteen points
> across the same split.
>
> So what loses fifty-four points is not the instances. It is a master that carries q and,
> at the root, almost nothing else. The two side panels say the same thing twice: on
> eighty-seven per cent of runs the root relaxation is exactly the coverage row, and in two
> hundred and twenty-three of three hundred and eighty-three time-limited runs the solver
> was already sitting on the right answer and could not prove it.

---

## Part 6 — Limitations and conclusions (slides 30–35, 4:20)

### Slide 31 · The cost is not a local quantity — 1:05 *(26:15)*
> Why does the bound not move? I think there is a structural reason, and here it is.
>
> For each tool, count the separate stretches during which it sits in the magazine. Every
> insertion of that tool begins one such stretch. So the optimum is q plus, summed over
> tools, the number of extra stretches. One stretch per tool recovers the count q exactly —
> and everything above q is a reinsertion.
>
> Now, when does a reinsertion happen? When the jobs that need a tool get pushed apart by
> other jobs whose requirements cannot sit alongside it. That is a statement about the
> global interleaving of the schedule. It is not a statement about which pairs of jobs
> happen to be next to each other.
>
> But look at what the master carries. One row indexed by arcs. Triplet rows that are the
> weak linearisation of a product and are worth nothing at a fractional point. One constant
> coverage row. And every optimality cut it generates — as we saw — supported on arcs too.
>
> So the master learns only adjacency-indexed facts about a cost that is not
> adjacency-indexed. I want to be careful about the status of this: it is the reading the
> measurements support, not a theorem of causation.

### Slide 32 · A family that is not local — 1:00 *(27:15)*
> If that reading is right, the fix is to find an inequality that counts across a span
> rather than an arc. So I derived one.
>
> Over a window of positions, every tool needed inside that window is either already loaded
> when you enter it or is inserted within it. That is valid, it counts across a stretch,
> and screening it over integral schedules showed it had several times the headroom of the
> family the solver carries today. It looked like the answer.
>
> It delivers nothing. Implemented inside the master, it left the root relaxation unchanged
> on all thirty-seven instances where both values were obtained — including instances whose
> gap is ten or eleven. And then the proof of why: the fractional row that implements it is
> implied by transition rows the formulation already has. It is redundant. It could never
> have helped.
>
> That is a negative result, but it is a sharp one. Writing a global inequality down is
> necessary. It is not sufficient — the encoding has to survive fractional mixing, and mine
> did not.

### Slide 33 · What this study does not show — 1:10 *(28:25)*
> Before I conclude, four things this study does not show, ordered by how much each
> threatens what I have just said.
>
> The heuristic census is small — one fixed census at three to five jobs. The connected
> family settles that unbounded gaps exist; it says nothing about how often they occur at
> industrial sizes.
>
> The campaign is one collection, one node type, one time limit, and Formulation 4 rather
> than the Formulation 5 its authors recommend. Both of those run against my conclusion
> rather than for it, and neither touches the relaxation values, which is where the bound
> results live.
>
> The branch-and-price prototypes are Python against compiled solvers, so nothing above
> nine jobs was closed and no conclusion here rests on one of their solve counts — only on
> a root value recorded before any search.
>
> And the learned cut-selection prototype was never run on this problem at all. It was
> trained on knapsack cover cuts. It is an appendix, not a method.

*Do not hurry this slide. Stating the limits yourself is what stops the jury having to
find them.*

### Slide 34 · Conclusions — 0:55 *(29:20)*
> To close.
>
> On the structural side: the grouping construction has two distinct values and the
> literature has been conflating them; minimum cardinality is exactly the restriction
> behind the walk gap; and the method as actually specified has an unbounded additive gap
> even on connected instances, which answers the question that was posed.
>
> On the algorithmic side: the loading oracle works exactly as intended — the solver
> usually has the right answer in hand. What it does not have is a certificate, and every
> strengthening I tried that aimed at the bound was neutral or harmful, while the one that
> aimed at the incumbent helped. The obstacle is the bound, not the search.
>
> And the direction that follows is specific rather than vague: price tool residency over
> spans rather than adjacent arcs, disaggregate theta by position, chain the
> position-transition columns by configuration rather than by tool. The window family shows
> that writing such an inequality is the easy half; making its fractional encoding
> non-redundant is the real problem.
>
> To close, the missing object is a useful fractional certificate for non-local tool
> returns. That is what the next attempt has to build.

### Slide 35 · Thank you

*Advance to this slide and stop talking. Do not read it.*

> Thank you. I am happy to take questions.

---

## References and backup (slides 36–48) — not part of the timed talk

Reach for these only if asked. Know which slide number each lives on.

| If asked about | Go to |
|---|---|
| Results broken down by instance family | 39 · certified optima by family |
| Whether the numbers can be trusted | 40 · how the numbers were made trustworthy |
| Whether a longer time limit changes it | 41 · the cactus plot |
| The window family's headroom measurement | 42 · the ceiling measurement |
| Machine learning / cut selection | 43–44 · the learned policy, and why it would not have helped |
| Branch-and-price, column generation | 45–47 · why reformulate, PCF, PTF, pricing |
| Any citation on any slide | 35–36 · key references (first in the appendix) |

### Questions to expect, and the one-line answer

**"Why is branch-and-price in backup?"**
> Because its prototypes are Python against compiled solvers, so no solve count from them
> means anything. What they were run for is the root relaxation value, which is recorded
> before any search and is unaffected. That value is the point: position-transition is the
> only construction here that provably exceeds q — on two of two hundred and thirty-two
> recorded roots, by one unit.

**"Your method is slower. Why is this a contribution?"**
> Because the campaign identifies which quantity is responsible, and it does so with four
> measurements that are independent of one another and agree. A faster solver would have
> been a better outcome; a located obstacle is still a result, and it names what the next
> attempt has to fix.

**"Your baselines are themselves behind the state of the art — F4 not F5, SSPMF not JGSMF,
and the real frontier is a DP/A* search."**
> All true, and each is stated in the report. But the claim here is a diagnosis, not a
> ranking: what is measured is that the coverage bound governs this family of methods, and
> that survives wherever the family sits against a dynamic-programming search. And on the
> discriminating families my solver is competitive with two of the three baselines anyway.

**"The strictness of Proposition 5.6 — how is it established?"**
> The first clause, that the relaxation is at least q, is proved in Appendix A. The second,
> that it can be strictly greater, is an exhibited witness: two Laporte3 instances where the
> recorded root is 6 against q of 5. I should be clear that the root value comes from the
> prototype and is not recomputed by the independent verifier. The instances and their optima
> are independently checked; the linear-programming value is not. Two runs out of two hundred
> and thirty-two, by one unit — which is why the report calls it of little practical use as
> it stands.

**"Isn't the split by bound tightness just saying hard instances are hard?"**
> No, and that is the measurement I would point to first. Formulation 4 closes all
> forty-five of the loosest instances, and the multicommodity model, whose relaxation is
> also q, loses only thirteen points across the split. The instances are not hard. This
> master is weak on them.

**"Did you use Formulation 5?"**
> No, and that is a limitation I state in the report and on the results slide. F4 stands in
> for it, which makes my baseline weaker than the literature's best — so the margin against
> me is if anything understated.

**"How confident are you in the connected-gap family?"**
> The construction is proved for every g. It is additionally verified by exhaustive
> enumeration at g equals one and two by a program that shares no code with the solvers.

**"If the heuristic helps so much, why not run it without the fractional cuts?"**
> You should ask that, and the honest answer is that I did not. Every strengthening was
> tested on a base that already had fractional separation switched on. Removing fractional
> separation is worth plus sixty-nine instances; the root heuristic is worth plus
> thirty-one. Nobody ran the combination. It is the first thing I would run, and I expect
> it to be the best regime in the table.

**"Why not try other heuristics for the incumbent?"**
> The same gap. One heuristic was implemented — a compact hybrid genetic search — and it is
> the only strengthening that gained anything, which is exactly the signal that the primal
> side is where effort pays. A proper comparison against the published metaheuristics under
> matched budgets was not run, and it is listed as further work in the report.

**"What would you do next, with three more months?"**
> Disaggregate theta by position — the standard strengthening the ablation never tested —
> and rebuild the window family with a non-robust encoding that ties tool presence to job
> coverage, since the redundancy proof rules out the cheap robust version.
