# What to do next, and how to run it without wasting the cluster

**Written 2026-08-24.** Everything here follows from one measured diagnosis:

> `Z* = Σ_t (blocks of tool t)`. Everything above `q = |U| − b` is a **re-insertion**, and
> a re-insertion is caused by the *global interleaving* of the schedule. But every
> inequality in both solvers is supported on a **local** object — an arc, or a single
> position. That mismatch is why the bound will not move.

Two numbers make it concrete:

- On **87.4%** of Benders runs (9,084 of 10,396) the root LP equals `|U|` *exactly*. The
  pairwise row and the triplet rows contribute nothing.
- The best bound an **arc-supported** family could *ever* certify closes **8.9%** of the
  gap (0% at the median, nothing at all on 46 of 62 loose instances). It is exhausted.

---

## 1. The gate: never run the cluster on an unmeasured idea

This is the rule you asked for, made operational. Three stages, and you only pay for the
next one if the previous one clears its bar.

### Stage 0 — validity and ceiling (laptop, minutes, free)

```bash
python3 src/BNP/window_cuts.py                       # brute-force validity self-test
python3 verification/bound_probe.py optima.json      # ceiling of each cut family
```

`window_cuts.py` checks the inequality at every window of every sequence of a bank of
random instances. **It passed at 1,200,816 integer points with zero violations.**

`bound_probe.py` enumerates all 8! sequences of each 8-job instance and computes, for each
family, the strongest bound it could possibly certify. Result on the 62 Laporte3 instances
whose coverage bound is loose:

| family | mean gap closed | median | no gain on |
|---|---|---|---|
| arc-supported (what both solvers carry today) | 8.9% | 0% | 46/62 |
| **window** | **30.9%** | **40%** | 18/62 |

**Bar to clear: ≥ 25% mean.** The window family clears it. Nothing else tried so far does.

### Stage 1 — pilot, root bound only (one node, ~1 hour)

Do **not** run a full campaign. Run PCF′ with and without the window cuts on a small set
of *loose* instances, with a short limit, and look only at the **root LP value**. That is
the quantity the cuts are supposed to move, it is available in seconds, and it cannot be
confounded by branching or by the Python pricer.

```bash
cd src/BNP
python3 bnp_benchmark_runner.py \
    --sets Laporte3 --jobs 8 --loose-only \
    --configs PCFp,PCFp+WIN --timelimit 120 \
    --out cluster/results/pilot_win.csv
```

Then compare `root_lp_bound` against `q = |U| − b` per instance.

**Bar to clear: the mean root bound must rise by at least 15% of `Z* − q`.**
That is roughly half the ceiling, which is what a linear relaxation realistically
delivers. If it clears, go to stage 2. **If it does not, stop and tell me the numbers** —
the family is right but the encoding is wrong, and the fix is in the model, not the
cluster.

### Stage 2 — full campaign (only after stage 1 clears)

```bash
cd src/BNP/cluster
sbatch --array=0-31 bnp_array.sbatch          # same shape as the finished campaign
```

Then, exactly as before:

```bash
python3 verification/analyse_campaign_results.py --check
```

---

## 2. Direction 1 — window inequalities *(implemented)*

`src/BNP/window_cuts.py`. For a stretch of positions `W = [p, r]`, every tool needed
inside `W` is either already loaded at `p−1` (which holds exactly `b` tools) or inserted
within `W`:

```
Σ_t Σ_{k∈W} w[t,k]  ≥  |{t present somewhere in W}|  −  Σ_t a[t,p−1]
```

linearised with one auxiliary variable per (tool, window).

**Why it is safe.** The row contains only master variables — `w`, `a`, and the new `zw`.
No column variable `y` appears, so its dual never reaches the pricing problem. The
set-union-knapsack oracle and the branching rule are **completely untouched**. This is a
robust cut in the Poggi–Uchoa sense.

**Why short windows are enough.** Measured on the same 62 instances: **84% of the windows
that carry the bound have length ≤ 4**, and 70% have length 2 or 3. So a static pool
works and no separator plugin is needed. `max_len=4` is the default.

**Why it generalises what is there.** The existing per-tool coverage rows `T_t` are
exactly the case `W = [1, n−1]` summed over tools.

### Wiring it in

In `pcf_prime_bp.py`, inside `branch_and_price(...)`, after the master rows are built and
before the first solve:

```python
from window_cuts import add_window_cuts
if accel and accel.get("window_cuts"):
    add_window_cuts(m, a, w, n, T, b, Tj,
                    max_len=accel.get("window_max_len", 4), verbose=True)
```

and in `bnp_benchmark_config.py` add to `ACCEL_KEYS` and `CONFIGS`:

```python
ACCEL_KEYS = (..., "window_cuts", "window_max_len")
{"label": "PCFp+WIN", "solver": "PCFp", "window_cuts": True, "window_max_len": 4},
```

**PTF needs more work.** Its insertion cost lives inside the column objective
`cost(C, D)`, so there are no `w` variables to write the row against. Adding them means
introducing `w[t,p] ≥ a[t,p] − a[t,p−1]` *and* tying `Σ w` to the arc costs — which puts
column variables in the row and makes the cut non-robust. Do PCF′ first; it is where the
headroom is provably largest (root bound `= q` on 100% of runs).

---

## 3. Direction 2 — disaggregate the Benders `θ` *(patch, not yet applied)*

`branch_and_benders_cut_cplex.py` has **one** `theta_idx` and **one** aggregated row
`θ ≥ Σ w_ij x_ij`. Single-cut versus multi-cut is the first item in the Benders
literature on strengthening, and it is the one acceleration your ablation never tested —
you tested fractional cuts, Pareto lifting, conflict rows and a primal heuristic, but not
this.

Replace the single `θ` with `θ_j` per job and `θ = Σ_j θ_j`; generate one cut per `j`
from the same subproblem solve. Same oracle, same duals, finer description of the
epigraph. Cheap to try, and a clean result either way.

**Expected payoff: unknown, which is exactly why it is a one-node pilot and not a
campaign.** Gate it the same way: root bound on 40 loose instances.

---

## 4. The RL work — it was aimed at the wrong bottleneck, and there is now a right one

**Why it cannot help as built.** Cut *selection* chooses among cuts you can already
generate. The measurement says the cuts the Benders master can generate are all
arc-supported and collectively worth ~0% of the gap at the median. **A selector cannot
select a strong cut that does not exist.** That is not a failure of the RL code — the
agent demonstrably learns, 46–73% over random selection on its knapsack testbed. It is a
failure of target.

**Where it becomes useful.** The window family has `O(n²)` members. At `n = 40` that is
~800 windows, and adding all of them statically is 30k rows. So at scale you *must*
choose which windows to separate under a budget — and now you are selecting from a family
that **does** have headroom. That is the same MDP, the same features, the same
`score_cut()` and `ssp_cut_features()` entry points you already exposed. The only thing
that changes is the cut source.

This is the honest re-framing for the talk: *the learning machinery was built and
validated; the family it was pointed at turned out to be exhausted; the family it should
be pointed at is the one this work identifies.* That is a much better story than "built
but never tested."

Two other places learning is established and plausible here, in priority order:

1. **Column selection for the pricer** (Morabit, Desaulniers & Lodi). The report already
   names the coupled-pair oracle as the measured bottleneck for PTF. This is where ML
   actually pays in branch-and-price.
2. **Branching on `a_t^k`.** Standard, modest, well understood.

---

## 5. Other paradigms worth a serious look

Ranked by how directly they attack the *locality* diagnosis rather than by novelty.

### 5.1 State-space relaxation / arc-flow over a DP graph — the strongest untried idea

The whole problem is that arcs and positions cannot carry interleaving information. A DP
state can. Build a layered graph whose nodes are `(position, partial magazine state)` and
whose arcs are transitions; the LP over flows in that graph has a relaxation as strong as
the state is informative. The full state (`position`, exact magazine) is exponential, but
a **relaxed** state — the magazine restricted to a chosen subset of "tracked" tools —
interpolates smoothly between `q` and the optimum, and you choose where to sit.

You already have `references/To read/2010.00558v2.pdf` (arc-flow formulations based on
dynamic programming). This is the paradigm that turned bin-packing and cutting-stock from
weak-LP problems into solved ones.

### 5.2 ng-routes / decremental state-space relaxation — the best transfer from routing

Same idea, refined adaptively. In vehicle routing the relaxation "cheats" by revisiting a
customer; you forbid revisits only within a neighbourhood `ng(i)`, and refine the
neighbourhoods where cheating actually happens. **The SSP's cheat is exactly a tool being
dropped and re-picked.** Define `ng(t)` as the tools that compete with `t` for slots, and
forbid `t` being evicted and re-inserted within its own neighbourhood. Then refine only
where the relaxation still cheats.

This took VRP bounds from useless to near-optimal. It is a direct structural match, and I
have not found it applied to the SSP anywhere in the literature you have.

### 5.3 Lagrangian relaxation by tool — cheap to test, could be checked this week

Decompose by tool: each tool independently chooses a set of positions to occupy,
minimising its own block count. The only coupling is the capacity row `Σ_t a[t,k] ≤ b` at
each position. Dualise those `n` rows. Each tool's subproblem is a trivial interval
problem, so the Lagrangian dual is cheap, and unlike the LP relaxation it *does* see the
per-tool block structure that generates re-insertions. Worth a day's work to find out
whether the dual exceeds `q`.

### 5.4 Benders over positions instead of arcs

Keep the Benders architecture but make the master position-indexed rather than
arc-indexed. The locality obstruction disappears — the window inequality is expressible
directly in the master — while keeping the exact polynomial loading oracle in the
subproblem. This is a hybrid of your two methods, and it is the one that inherits the
strengths of both.

### 5.5 Non-uniform tool costs — where you are alone in the field

Crama et al. prove that with non-uniform tool sizes KTNS stops being optimal but the
**loading LP stays exact**. Every compact model in the literature — LSS, the F-family,
SSPMF — hard-codes uniform switching. **Your Benders subproblem is that LP**, so your
solver extends to non-uniform costs unchanged and none of the baselines do.

Tools occupying different numbers of slots is the real industrial case in printing and
PCB assembly. Nobody has an exact method there. This is the cheapest route from "loses by
300 instances" to "the only method that applies".

Not a bound improvement — a scope claim. But it is the strongest strategic card in the
deck and it costs almost no implementation.

---

## 6. Ordering, if you want one

| | what | cost | why |
|---|---|---|---|
| 1 | Window cuts pilot (stage 1) | 1 hour, 1 node | Measured ceiling 30.9% vs 8.9%. Implemented and validated. |
| 2 | Lagrangian-by-tool probe | 1 day, laptop | Free to test, and it sees the block structure directly. |
| 3 | `θ` disaggregation pilot | 1 hour, 1 node | The one standard Benders strengthening never tested. |
| 4 | ng-relaxation on tools | 1–2 weeks | Highest ceiling of anything here. Real research. |
| 5 | Non-uniform costs | 1 week | Scope, not bound. The only-method-that-applies claim. |
| 6 | Compile the pricer | 1 week | Not a contribution, but until then you cannot separate formulation from implementation above 9 jobs. |

Items 1–3 are all gated one-hour experiments. None of them is a campaign until its gate
clears.
