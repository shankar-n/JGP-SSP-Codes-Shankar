# The three campaigns, analysed — 2026-08-24

All three finished. This file records what they produced, what had to be corrected in the
analysis before the numbers were trustworthy, and where each figure now lives in the
report.

Everything below is reproduced by `verification/analyse_campaign_results.py`. Run

```
python3 verification/analyse_campaign_results.py --check
```

and it recomputes every figure from the raw shards and compares it against the value the
report states. It printed **"every figure agrees with the report"** and exited 0 on
2026-08-24.

---

## 1. Two analysis bugs found before any number was written down

Both were in the code that *reads* the results, not in any solver. Both changed
conclusions.

### 1.1 The instance key was too short

An instance is `(benchmark_set, instance, J, T, C)`. The Crama collection publishes the
same 40 matrices at four capacities under the same file names, in `Tabela1`–`Tabela4`.
Keying on `(benchmark_set, instance)` merges rows describing genuinely different
instances.

The first pass of this analysis did exactly that and reported **1 cross-method
disagreement**. With the capacity in the key there are **0**, over 41,673 pairwise
comparisons.

`VERIFIED_FACTS.md` records the same failure mode from July, when a triage draft keyed by
instance stem alone and produced 200 fake disagreements on the Laporte sets. It is now
recorded in the report itself — §6.2, Appendix B, Appendix C — so the next person who
writes an analysis pass is warned.

### 1.2 The coverage bound must use |U|, not |T|

Four matrices contain a tool no job requires: Crama `s2n007` (19 of 20 used), `s2n009`
(17 of 20), Laporte3 `L28-7` (24 of 25), Laporte5 `L6-8` (19 of 20). Counted with the
capacities at which they appear, that is **10 of the 1,421 instances**.

On those the counting bound `|T| - b` is not valid. `L28-7` has `|T|=25`, `b=5`, and a
free-initial optimum of **19**, which is `|U| - b = 24 - 5`, not `20`. The PCF′ root LP
returns exactly 19 there, so treating `|T| - b` as the bound would have made it look as
though the relaxation had fallen *below* the counting bound.

All coverage-bound figures in §6 now use `|U|`.

### 1.3 A third trap, avoided

`obj` is **not** comparable across methods. SSPMF and both branch-and-price prototypes
report their native objective in the free-initial convention; the Benders configurations,
`CATZ-F4` and LSS report empty-start. Comparison is on `obj_ktns`, the empty-start KTNS
cost of the returned sequence, which every method records.

This turned out to be a clean confirmation of Proposition 2.x (the convention identity):
`obj_ktns - obj` equals `b` on 1,029 of SSPMF's 1,038 closed instances and is smaller on
the other 9, which are exactly the instances whose optimal sequence starts with a job
needing fewer than `b` tools.

---

## 2. BBC campaign — `src/BBC/results/`, 120 shards

**Scale.** 16,994 runs, 12 configurations, 1,421 instances
(Catanzaro 171, Crama 160, Laporte3 340, Laporte4 330, Laporte5 340, Laporte7 80).
One hour, 16 GB, 4 threads, CPLEX 22.1.1. Early-stop disabled — everything was run.

**Agreement.** 1,115 instances closed by ≥1 method, 999 by ≥2, giving 41,673 pairs of
methods that both proved an optimum. **Zero disagreements.**

**Solved (solved / runs that returned a result).**

| configuration | solved | runs |
|---|---:|---:|
| SSPMF | 1038 | 1417 |
| CATZ-F4 | 885 | 1406 |
| LSS | 844 | 1069 |
| BBC-LP+T | 727 | 1410 |
| BBC-LP | 726 | 1407 |
| BBC-K | 725 | 1395 |
| BBC-LP+F+H | 690 | 1420 |
| BBC-LP+F | 659 | 1418 |
| BBC-LP+F+C | 657 | 1414 |
| BBC-LP+ACC | 656 | 1419 |
| BBC-K+F | 651 | 1378 |
| BBC-LP+F+P | 622 | 1414 |

**Failed runs: 427.** 378 worker crashes, 49 harness failures (`OSError: Key has expired`
closing the log file on the cluster filesystem). 352 of the crashes are LSS, and 239 of
those are Laporte5 — LSS's largest models. So LSS's denominator is 1,069 and its rate is
**not** comparable with the others: the runs it lost are concentrated on the family it
finds hardest. The other 75 are scattered across the nine Benders configurations, at most
26 in any one.

**Fractional cuts (BBC-LP+F vs BBC-LP, 1,415 common).**
67,513,396 cuts generated. Median nodes fall 77,504 → 3,795. Dual bound at termination:
**higher on 0**, equal on 1,228, lower on 176, of 1,404. Solved: 726 → 659, a loss of 67.

This is stronger than the mid-flight reading (which had "higher on 3"). The cuts tighten
the relaxation locally — the node count proves that — and never move the bound that
decides the outcome.

**Ablation vs BBC-LP+F.** +H **+31**; +C −2; +ACC −3; +P **−37**; removing +F altogether
**+67**. Only the primal strengthening helps, and the biggest single win is deleting a
feature.

**Where it stops.** BBC-LP closes 259 of its 726 at the root. Root value recorded on 1,178
of 1,421 runs, optimum also known on 883 of those; root value equals the optimum 294
times — 264 of 497 among runs that closed, only 30 of 386 among runs that did not. Where
it is short, it is short by 16.7% at the median and up to 42.9%.

6,562 Benders runs hit the limit; on 3,874 the optimum is known; on 2,571 (66%) the
incumbent was *already* that optimum. BBC-LP alone: 229 of 386, 59%.

**The coverage bound decides it.** Of the 1,115 with a known optimum, 523 tight / 592
loose. BBC-LP solves 492 (94%) of the tight and 234 (40%) of the loose. SSPMF solves 523
(100%) and 515 (87%).

That SSPMF control is new and it matters. SSPMF's relaxation is also `q`, so if the bound
were the whole story it would collapse the same way. It does not. A compact model gives
the search a full description at every node; the Benders master sees only its cuts.

---

## 3. BNP campaign — `src/BNP/cluster/results/`, 32 shards

2,581 runs, 7 configurations, 469 instances. 30 min on Catanzaro/Crama, 10 min on
Laporte. PySCIPOpt, single-threaded, Python pricer.

**Caveats stated in the report before any count:** the harness has an early-stop rule
(6 consecutive non-optimal results ⇒ skip the rest for that configuration), so
denominators are outcome-dependent; and there is no seed variation.

| configuration | solved | runs | median t (s) | median columns |
|---|---:|---:|---:|---:|
| PCFp+MC | 102 | 422 | 11.4 | 1504 |
| PCFp | 91 | 415 | 23.7 | 1574 |
| PCFp+HP | 73 | 360 | 19.7 | 5173 |
| PTF | 73 | 387 | 2.4 | 1279 |
| PCFp+WS | 64 | 359 | 14.9 | 1610 |
| PCFp+ACC | 60 | 337 | 28.1 | 1221 |
| PCFp+STAB | 44 | 301 | 35.7 | 1133 |

Nothing above 9 jobs closed: all 608 runs on the 30- and 40-job instances hit the limit.

**Agreement with BBC:** 507 proved optima, **0 mismatches**; shift `obj_ktns - obj = b` on
all 507.

**The measurement that actually matters, and the reason this campaign was worth running:**

- **PCF′ root LP = |U| − b on all 2,114 runs. Not one exception.** Proposition on PCF
  confirmed empirically, on six different acceleration settings.
- **PTF exceeds it on 3 of 233 runs.** Catanzaro `A0-0` (2.013 vs q=2), Laporte3 `L11-6`
  (6 vs 5, optimum 12) and `L11-7` (6 vs 5, optimum 13). So the PTF proposition is not
  vacuous — but the advantage is one unit, on three small instances, against gaps of 6–8.
- Root value equals the optimum on 990 of the 1,846 runs where both are known. Same
  phenomenon as §6.5 seen from the other side.
- PCF′ vs PTF on 320 common instances: 73 each. Median nodes 96 vs 2 — PTF's coupled-pair
  pricer is far more expensive per node, and the stronger bound does not pay for it.

This is what replaces the old "runs are in progress" placeholder, and it is a much better
result than a solve-count table would have been: it measures the bound directly, and the
bound is the thing the whole report is about.

---

## 4. RL cut selection — `src/BBC/rl_results/`

**This is not an SSP result and the report now says so three times.**

`rl_cut_select.py` implements the Tang et al. (2020) cut-selection MDP on a
**knapsack cover-cut** environment (`KnapsackCutEnv`), because CPLEX was unavailable in
the development environment. `n` is the knapsack size, not a job count.

One seed, 2,000 episodes, lr 0.2, γ 0.95, evaluated on held-out instances:

| n | learned | random | improvement |
|---:|---:|---:|---:|
| 10 | 1.3855 | 0.8734 | +58.64% |
| 12 | 1.1639 | 0.7014 | +65.93% |
| 20 | 0.7482 | 0.5021 | +49.01% |
| 22 | 0.6692 | 0.4568 | +46.49% |
| 24 | 0.6383 | 0.3888 | +64.17% |
| 26 | 0.5661 | 0.3279 | +72.67% |

Reported in §5.5 as Table 5.3 with an explicit "one training seed per size, no
repetition" and an explicit "it says nothing about the SSP". §7.3 no longer claims SSP
runs are in progress — they never existed.

---

## 5. What changed in the report

| Section | Change |
|---|---|
| Abstract | 1,421 instances / 12 configurations / 16,994 runs; agreement result added; "still running" removed; fractional-cut result strengthened; BNP root-bound result added |
| §5.4 | PTF proposition given its honest reading + new open Problem (is the PTF excess over q bounded?) |
| §5.5 | Table 5.3 with the measured knapsack numbers, and the limits of what they show |
| §6.1 | Crama corrected 40 → 160; total 1,301 → 1,421; 12 configurations; CATZ-F4 named; job/tool ranges added |
| §6.2 | rewritten: the five-part instance key, the agreement result, the convention measurement, the unused-tool finding, the failed runs |
| §6.3 | full solve table (12 rows × 6 families), new times table incl. CATZ-F4 |
| §6.4 | fractional-cut table with node counts; ablation table with the "remove +F" row; root-node and incumbent figures |
| §6.5 | 523/592 split, SSPMF control column added |
| §6.6 | **written from scratch** — was a placeholder |
| §6.7 | six findings instead of five |
| §7.1 | four answers instead of three; numbers corrected |
| §7.3 | limitations rewritten: lost runs, language gap, RL never run on SSP |
| §8 | conclusions and further work updated; the stale "runs in progress" paragraph replaced |
| App. B | third finding recorded: the two analysis bugs |
| App. C | the five-part key and the \|U\| rule documented |

Build: **78 pages, 0 errors, 0 overfull boxes, 0 undefined references or citations**,
all Type 1 Latin Modern fonts.

---

## 6. Still open for Shankar

1. `Calmels2018` — the entry says 2018 but volume 57 is 2019. Check the record.
2. `Colares2026Exact` — Moreira's bibliography lists it as personal communication, 2024.
   Ask Colares how he wants it cited.
3. Catanzaro F5 was not implemented; F4 was used. Their own paper recommends F5. Worth a
   sentence to the advisors if they ask why.
