# Code audit, and the campaign result that just landed

2026-08-20.

## Part 1 — Does the code corroborate the report?

Substantially yes. This was the one part of the audit I had not done, and it comes out well.

**`compute_ktns` is correct.** I ran it against my independent KTNS and against the exact dynamic program over magazine states, on **83,670 (instance, sequence) pairs**: **zero disagreements**. The tool-loading oracle every other result in the project depends on is right.

**The Benders master is richer than the report says it is.** The report (§4.2) states the initial row as $\theta \ge \sum_{ij} w_{ij}x_{ij}$. The code builds
```
θ ≥ Σ w_ij x_ij + Σ_j |T_j| x_{d,j}
```
with an explicit comment explaining why the depot term belongs there (the subproblem charges insertions from an empty magazine, so the first job always costs at least $|T_{\sigma(1)}|$). The code also carries the coverage row `theta_coverage` ($\theta \ge |U|$) and the triplet bounds. **The report understates its own solver** — this is a defect in the writing, not in the work.

**The position formulations match the report exactly.** `pcf_prime_bp.py` builds precisely the families §4.4 describes — `Pp` ($\sum_C y \le 1$), `G` (contiguity), `Cov`, `W`, `T` (counting rows), plus the `Link` rows defining the aggregated presence variables $a_{t,p}$ the report says it branches on. `ptf_bp.py` has the per-step selection row, the tool-level flow-consistency rows, the coverage rows, a diagonal-free constraint ($C \ne C'$), and a pricer that linearises $x'_t(1-x_t)$ by exactly the McCormick construction §4.4 describes. The four named accelerations (heuristic pricing, multiple pricing, warm start, stabilisation) are all real switches.

**What I did not check:** the CPLEX callback logic in detail (it needs CPLEX to exercise), and the analysis scripts.

## Part 2 — Your campaign finished while we were talking, and it settles the report's main open question

`src/BBC/results/` is being written as I read it — 110 shard files, ~13,800 rows, timestamps through 11:00 today, on the clean protocol (all families, one time limit). **Numbers below will move as the remaining runs land**, but the signal is unambiguous.

### The fractional Benders cuts now fire — and they make the solver worse

The report says the fractional separation was inert because a bad solver call discarded every cut, that the call is now fixed, and that "the question the re-run settles is whether the dual bound they produce rises above the coverage value."

It has been settled.

| | cuts generated | solved (1,247 common instances) |
|---|---|---|
| `BBC-LP` (no fractional) | 0 | **697** |
| `BBC-LP+F` (fractional on) | 61,028,468 | **628** |

Sixty-one million fractional cuts enter the master, and the result is **69 fewer instances solved**. The dual bound is strictly higher on **3 of 1,247** instances; identical on 1,075.

This is a clean negative result, and it is the strongest form of the report's own thesis. It is no longer "we could not test whether fractional cuts break the coverage ceiling" — it is "we tested it at scale, the cuts are generated in enormous numbers, and the bound does not move." The bound-limited diagnosis is now *measured*, not inferred.

### The acceleration ablation, on common instances against `BBC-LP+F`

| acceleration | effect |
|---|---|
| `+H` hybrid genetic warm start | **+29 solved** — the only one that helps |
| `+C` conflict-graph bound | −2 (neutral, exactly as §4.3 predicts: "its reach is narrow") |
| `+ACC` all combined | −7 |
| `+P` Papadakos Pareto lifting | **−37** — the most expensive and the least useful |

A coherent story: the only thing that helps this solver is a better *incumbent*, and every attempt to strengthen the *bound* costs more than it returns. That is precisely what "bound-limited rather than implementation-limited" means, and now it has an ablation behind it.

### Overall solved counts (mid-flight; denominators differ because runs are still landing)

| solver | solved / attempted |
|---|---|
| SSPMF | 852 / 901 |
| LSS | 803 / 1,235 |
| BBC-K | 701 / 1,301 |
| BBC-LP+T | 701 / 1,301 |
| BBC-LP | 699 / 1,301 |
| BBC-LP+F+H | 657 / 1,265 |
| BBC-LP+F | 628 / 1,247 |

SSPMF remains the strongest single method — da Silva's claim replicates on your data, which is itself a reportable finding.

### What this means for §5

§5 is no longer blocked. When the last shards land it can be written with actual conclusions rather than placeholders:

1. Fractional Benders cuts are now active and measurably counterproductive — the mechanism is confirmed, the hypothesis is refuted, and that refutation *supports* the bound-limited reading.
2. The acceleration ablation separates primal from dual improvements cleanly, with a sign on each.
3. SSPMF is reproduced as the strongest compact model.
4. Everything must be re-derived from these CSVs; carry over no number from the old protocol (your own `RESEARCH_PLAN` says this).

## Part 3 — What was actually done, since it is worth stating plainly

- **95 commits, 14 April to 18 August.** Four months of version history.
- **~500 KB of source across 37 modules**: a branch-and-Benders-cut solver with generic callbacks, three reimplemented literature baselines (LSS, Catanzaro F4, SSPMF), two novel branch-and-price formulations with their pricers, a hybrid genetic heuristic, conflict-graph cuts, an RL cut-selection prototype, instance generators, PORTA and Concorde wrappers, a resumable campaign harness with SLURM job arrays.
- **A tool-loading oracle verified on 83,670 cases against two independent implementations.**
- **Cross-solver agreement**: zero disagreements on canonical cost across every instance solved by more than one method, in both the old and new campaigns.
- **A cluster campaign** of ~13,800 runs across 11 configurations on the LIMOS SLURM cluster, now producing a clean negative result on a question the literature has not answered.
- **Theory** addressing all four questions your advisors posed, of which the substantive statements verified independently today (40 of 53 checks; the 13 failures are one labelling error, repairable, with the repair already found).
- **A verification culture that partly worked**: the June audit caught and fixed over fifty errors in the working documents. What failed was propagating those fixes into the report.

That is not nothing. It is a substantial internship whose *presentation* has drifted from its *substance*. Those are different problems, and only the second one is hard.
