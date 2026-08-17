# §3 review — literature integration, lower bounds, language

**Date**: 2026-07-20 · **Target**: `report/JGP-SSP_report.tex` §3 (L588–1165), §2.7 (L522–585)
**Status**: review memo. Nothing has been applied to the `.tex`. Every proposed edit is quoted with a line number so you can check it against the source before approving.

**Rigour flags used below**
- `[V]` = I verified this computationally in this session; script named.
- `[S]` = sourced from `skills/ssp-literature/SKILL.md` or the repo; source named.
- `[P]` = my proposal / analysis. Not verified. Treat as a claim to check, not a result.
- `[?]` = I could not check it; you need to.

---

## 0. Summary

Five things, in descending order of how much they matter.

1. **One substantive error.** §3.8's closing inference ("production instances sit far on the collapsed side") is not licensed by Theorem `thm:collapse`. The theorem's certificate is `ρ_c ≤ H−Z*`, and `H−Z*` is unbounded by your own Prop `prop:unbounded`. I checked whether the conclusion is merely unsupported or actually false: **it is unsupported but true on that family**, because the real threshold is `ρ_c = 1` for every `g` while the gap grows like `g`. `[V]` The bound is arbitrarily loose. There is a sharper theorem here that fixes the passage and strengthens the result — §5 of this memo.

2. **A misclassification in §2.7.** `\citet{Ghiani2010}` is filed under **Heuristics** (L553–556). Ghiani, Grieco & Guerriero (2010) is an exact branch-and-cut with a dynamic lower-bounding scheme. `[S: skills/ssp-literature/SKILL.md]` This is both a citation error and a lost opportunity — it is the closest thing in the SSP literature to the lower-bound question you are asking in Q2.

3. **You are right about the literature, but the fix is not the one implied.** Burger and Crama did not "do the same heuristic" — they are two different families, and only one of them is what §3 analyses. The honest content of the new subsection is a *separation*, not a replication. §2 below.

4. **The empirical hole is bigger than you think.** `precompute_jgp_gsp.py` exists and has never been run — `src/BBC/jgp_gsp_costs.csv` does not exist. `[V: ls]` So the report develops a worst-case theory of a heuristic and never once measures that heuristic's actual gap, despite having exact optima for 806 instances sitting in `raw_results.csv`. §3 below.

5. **Language: 14 locations.** Mostly register (informal verbs, editorialising), two logical overreaches, one counting error. Full table in §6. It is not as bad as you fear — the density of problems rises sharply in §3.4 (`ssec:law`), which reads as if it were written under argumentative pressure.

---

## 1. The counting error, first, because it is free

**L607**: "The section proceeds in six steps."

§3 has **seven** subsections. `[V: awk over L588–1165]` The sentence then describes seven things. Change "six" to "seven".

---

## 2. Literature integration in §3 (your Q1)

### 2.1 The distinction the section must draw

Your instinct is right that §3 is under-connected to the literature, but the framing "other authors used the heuristic, why not use theirs" needs splitting, because two different families are in play and conflating them would introduce an error rather than fix one.

| Family | Who | What it does | Does §3's theory apply? |
|---|---|---|---|
| **Group-then-sequence** (JGP+GSP) | Burger 2015; Salonen 2006; the JGP-seeded metaheuristics of Mecler 2021 | solve JGP → K* batches → order batches (TSP) → flatten → KTNS | **Yes.** This is exactly `H`. Theorem `thm:grouping` and everything downstream is about this method. |
| **Sequence-first / TSP-construction** | Crama et al. 1994 (4 construction + 2 refinement heuristics); Tang & Denardo 1988's 3-step heuristic | build a job sequence directly on a TSP surrogate with arc weights `max(0,\|T_i∪T_j\|−b)`, then KTNS, then local search | **No.** These never form groups. `H = min{γ(P) : \|P\|=K*}` is not their cost. |

`[S: skills/ssp-literature/SKILL.md — Crama 1994 "11 heuristics ... construction (4 TSP-based) and refinement (adjacent swap, 2-opt)"; Tang & Denardo "Heuristic: 3 steps — Hamiltonian path on LB(i,j) weights; KTNS; adjacent swaps"]`

So: **Crama's heuristics cannot be folded into §3's analysis.** A worst-case analysis of nearest-neighbour-plus-KTNS would be a genuinely different theorem. What they *can* do is serve as reference upper bounds in §5 and as warm starts for BBC — which is §3 of this memo, and is worth doing.

What this means for the section: §3 does not need to *replicate* the literature. It needs to (a) say plainly which heuristic family it analyses and which it does not, (b) stop asserting a universal negative it cannot defend, and (c) connect Burger's *enumeration* machinery to §3.7 `ssec:grouping-sel`, where it is directly relevant and currently unmentioned.

### 2.2 The overclaim to retire

**L566–569**:
> "What the literature does not contain is a *worst-case* analysis of the decomposition---bounds on its gap or ratio, extremal instances, or conditions for exactness. To our knowledge no worst-case guarantee has been published for *any* SSP heuristic; the decomposition in particular had only ever been assessed empirically."

The first sentence is defensible. The second is a universal negative over every heuristic ever published for the SSP, and I cannot verify it — the survey `[S: Calmels2018]` classifies a large heuristic literature that neither of us has swept for approximation results. `[?]` Recommend deleting the universal claim and keeping the specific one. It costs you nothing: the contribution is the decomposition analysis, not a literature-wide absence.

**Proposed replacement (L565–570):**

```latex
consistent with earlier reports they survey. What the literature does not contain is a
\emph{worst-case} analysis of this decomposition---bounds on its gap or ratio, extremal
instances, or conditions for exactness. Its record is empirical: strong, repeatedly
confirmed, and silent on how badly it can do. Section~\ref{sec:gap} supplies the
worst-case side.
```

### 2.3 Fix the Ghiani misclassification

**L553–556** currently:
```latex
\paragraph{Heuristics.}
Constructive and metaheuristic upper bounds include the branch-and-bound and
bounding ideas of \citet{Ghiani2010} and the hybrid genetic search of
\citet{Mecler2021}, which seeds its population from JGP solutions.
```

**Proposed replacement** — moves Ghiani to the exact paragraph and gives the constructive heuristics the sentence they currently lack:

```latex
\paragraph{Heuristics and upper bounds.}
\citet{Tang1988} pair their loading rule with a three-step heuristic: a short
Hamiltonian path on the pairwise weights $w_{ij}=\max(0,\lvert T_i\cup T_j\rvert-b)$,
then KTNS, then adjacent-swap improvement. \citet{Crama1994} systematise this into
four travelling-salesman construction rules and two refinement rules, establishing the
sequence-first family that remains the standard source of upper bounds; the hybrid
genetic search of \citet{Mecler2021} seeds its population from JGP solutions instead.
These methods do not group, and are therefore outside the scope of the analysis in
Section~\ref{sec:gap}, which concerns the group-then-sequence decomposition; they enter
this report as the reference upper bounds of Section~\ref{ssec:bench}.
```

and append to the **Exact formulations** paragraph (after L530):

```latex
\citet{Ghiani2010} recast the problem as a nonlinear least-cost Hamiltonian cycle
problem and solve it by branch-and-cut, exploiting the reversal symmetry of a sequence
and---of interest to the bounding question of Section~\ref{ssec:lb}---recomputing the
arc lower bounds $w_{ij}$ dynamically at each node from the partial sequence.
```

`[S: skills/ssp-literature/SKILL.md — Ghiani entry: "Frames SSP as a nonlinear least-cost Hamiltonian cycle problem, then develops a B&C exploiting the symmetry property"; "c^LB_ij updated dynamically at each B&B node using partial sequence information and a Tailored KTNS with O(cn) complexity per arc"]`

### 2.4 Drafted new subsection for §3

Insert immediately after the §3 opener (after L617, before `\subsection{The gap is the price...}`). It does three jobs: scopes the analysis, states what the empirical literature established and why it cannot answer this question, and flags Burger's enumeration as the precursor to §3.7.

```latex
\subsection{What the empirical record does and does not settle}\label{ssec:lit-gap}
The decomposition analysed here is not a construction of this report. It is the method
used in practice, and its reputation rests on a body of measurement that should be
stated precisely before it is extended.

\citet{Burger2015} solve an industrial colour-printing problem that they first prove
equivalent to the SSP---ink cartridges are the tools, the cartridge rack the
magazine---by exactly the two-phase decomposition of Section~\ref{ssec:jgp}, modelling
the grouping phase as unicost set covering and the sequencing phase as a travelling
salesman problem. They measure the decomposition's suboptimality directly against exact
optima and find it small, endorsing the earlier finding of Salonen et al.\ that it
performs remarkably well. The same confidence is visible downstream: the strongest
metaheuristics for the SSP seed their populations from JGP solutions
\citep{Mecler2021}.

Three limits of that record motivate what follows. First, it is an average over an
instance distribution, and the quantity at issue---how far the method can be from the
optimum---is a supremum; no amount of favourable sampling bounds it, and
Section~\ref{ssec:unbounded} exhibits instances on which the gap grows without bound.
Second, the measurements are reported per instance family, so they cannot say
\emph{which structural feature} of an instance makes the decomposition exact; that is
the question Sections~\ref{ssec:ratio}--\ref{ssec:clutter} answer. Third, and most
directly, \citet{Burger2015} already found the pressure point: needing a
minimum-cardinality grouping but facing many of them, they enumerate the optimal
groupings via Stirling numbers of the second kind and sequence each. That is a search
\emph{within} the minimum-cardinality class. Theorem~\ref{thm:grouping} shows the
optimum need not lie in that class at all, which both explains why the enumeration
helps and bounds how much it can ever help---the subject of
Section~\ref{ssec:grouping-sel}.

A scope note. The other established heuristic family builds a job sequence directly on
the pairwise weights $w_{ij}$ and repairs it by local search \citep{Tang1988,Crama1994},
never forming groups. Nothing proved in this section applies to it: the quantity $H$ is
defined by a grouping. Those methods appear in this report as the reference upper bounds
of Section~\ref{ssec:bench}, and a worst-case theory for them remains open.
```

**Citation warning** `[S: skills/ssp-literature/SKILL.md, verification table]`: **Salonen et al. (2006) is not in `references/` and not in `references.bib`.** The skill file explicitly flags it — "Referenced in Burger et al. (2015) as endorsing JGP+GSP but paper itself not in `references/`. Verify before citing directly." The draft above therefore cites it *indirectly* ("endorsing the earlier finding of Salonen et al.") without a `\citep`, which is honest and needs no bib entry. Do not upgrade it to a direct citation without obtaining the paper.

---

## 3. The measurement that was never run (your Q1, option C)

### 3.1 What is missing

| Artefact | Status |
|---|---|
| `src/BBC/precompute_jgp_gsp.py` | exists, complete, documented `[V]` |
| `src/BBC/jgp_gsp_costs.csv` | **does not exist** — never run `[V: ls]` |
| `src/BBC/raw_results.csv` | exists, 4716 rows, 806 instances with exact optima `[S: VERIFIED_FACTS 2026-07-18]` |
| `src/SSP/heuristics.py` — `nearest_neighbor`, `adjacent_swap_ls`, `greedy_ffd` | exist; imported **only** by `main-notebook.py` and `viz.py` `[V: grep]` |
| Heuristic column anywhere in §5 | none `[V: grep]` |

So the report proves worst-case bounds on `H` and never reports a single measured value of `H`. The exact optima to compare against are already on disk. This is the cheapest high-value addition available to the report, and it is what your question was really pointing at.

### 3.2 The run

**Step 1 — JGP+GSP costs.** No code change needed.

```bash
source ~/miniforge3/etc/profile.d/conda.sh && conda activate ssp_env
cd src/BBC && python precompute_jgp_gsp.py --sets primary   # then --sets secondary
```
Writes `jgp_gsp_costs.csv` with `jgp_gsp_gap` populated wherever `raw_results.csv` already holds the optimum. Needs PySCIPOpt only (ARF MILP), not CPLEX — so it can run on a login node or locally, not necessarily via SLURM. `[P — check the JGP MILP time on the 40-job Catanzaro instances before committing to a serial run; if it drags, wrap in the existing `run_campaign.sbatch` array]`

**Step 2 — Crama/Tang reference heuristics.** Small new module, `src/BBC/precompute_heuristics.py`, reusing `src/SSP/heuristics.py` unchanged. Per instance record, all in the empty-start convention via `compute_ktns`:

| column | meaning |
|---|---|
| `nn_cost` | `nearest_neighbor` on the `w_ij` surrogate → KTNS |
| `nn_ls_cost` | `adjacent_swap_ls` applied to the above |
| `ffd_cost` | `greedy_ffd` |
| `jgp_gsp_cost` | from step 1 |
| `best_heur_cost` | min of the above |
| `opt` | join from `raw_results.csv` where known |

**Step 3 — BBC warm start.** `branch_and_benders_cut_cplex.py` currently sets no MIP start `[V: grep found no `MIP_start`/`add_mip_start`]`. Feeding `best_heur_cost`'s sequence as an incumbent is a contained change and is the standard reason these heuristics exist. **Caveat** `[P]`: this changes BBC timings, so it invalidates comparability with the merged corrected-master results (jobs 14616/14624). Either do it as a clearly-labelled separate ablation column, or defer it until after the deck rebuild that CLAUDE.md already lists as pending. **I would not touch the solver before the deck is rebuilt.**

### 3.3 What it buys the report

A new table in §5 and two sentences in §3:

- **`tab:heur`** — per family: mean and max of `(H − Z*)` and `H/Z*` over the instances with known optima, plus the share with zero gap. This is the first empirical measurement of the gap in the report, and it lets §3 stop leaning on `\citep{Burger2015}` for its only empirical anchor.
- **The tightness cross-tab.** You already have the 387/419 bound-tight/bound-loose split `[S: VERIFIED_FACTS 2026-07-17]`. Crossing zero-gap against bound-tight tests the report's central thesis — L189–191 asserts "where it is tight, exact configuration methods close at the root **and the heuristic tends to be exact**". The second half of that sentence is currently **unmeasured**. `[?]` This experiment either confirms the connecting thread of the report or breaks it. It is the single most informative number you are missing.
- Reference upper bounds let §5 say how much of the exact solvers' advantage is real, which is standard practice and currently absent.

---

## 4. Improving the lower bound (your Q2)

### 4.1 Where you are

`Z* ≥ max(K*−1, |U|−b)` (Cor `cor:lb`), and §5 measures the second at 48.0% tight among solved instances. The report's own diagnosis is that everything is bound-limited: `daSilva2024`'s LP collapses to exactly `|U|−b`, the configuration relaxation collapses to the same on most instances `[S: Moreira2026]`, and PCF′'s root bound equals the optimum on 93/94 solves `[S: VERIFIED_FACTS]`. So the bound *is* the problem, and you are asking the right question.

### 4.2 What the SSP literature already does — and what §2.6 omits

`[S: skills/ssp-literature/SKILL.md]`

1. **Pairwise arc bound** (Tang & Denardo 1988): `w_ij = max(0, |T_i ∪ T_j| − b)` switches when `j` immediately follows `i`. Summed over consecutive pairs, a min-weight Hamiltonian path on `w` is a valid lower bound on `Z*`. **This is your BBC master.**
2. **Dynamic arc bounds** (Ghiani 2010): recompute `w_ij` at each B&B node from the partial sequence via a tailored KTNS in `O(bn)` per arc. Strictly dominates static `w_ij` and costs almost nothing.
3. **Reversal symmetry** (Ghiani 2010, Property 1): a sequence and its reversal cost the same. Halves the search space; not a bound but multiplies the value of any bound.
4. **Partial-sequence combinatorial bounds** (Laporte 2004, the B&B not the B&C): partial KTNS on the fixed prefix plus a bound on the remainder. **Their B&B beat their own LP-based B&C** precisely because the LP bound was weak — the same pathology you are documenting.
5. **Polyhedral strengthening** (Catanzaro 2015): overlap and linear-ordering inequalities, a TU submatrix argument, 1-arc inequalities.

**§2.6 (`ssec:lb`, L444–494) presents only the two structural bounds and never mentions 1, 2 or 4.** That is a real omission — the pairwise bound in particular is *already implemented in your master* and deserves to be stated where the bounds are introduced. `[P]` I would add a short paragraph there.

### 4.3 How the same problem is solved elsewhere

| Domain | Technique | Transfer to SSP |
|---|---|---|
| **TSP** | Held–Karp / 1-tree Lagrangian ascent on node potentials: replace `w_ij` by `w_ij + π_i + π_j`, maximise the 1-tree bound by subgradient ascent | **Direct.** Your master already relaxes to a Hamiltonian path on `w`; the ascent is a bolt-on that never weakens the bound and needs no new cut separation. Strongest effort/payoff ratio on this list. |
| **Bin packing / cutting stock** | Dual-feasible functions lift the trivial volume bound; Gilmore–Gomory set-covering LP dominates combinatorial bounds | `|U|−b` **is** a volume bound. A DFF-style lift is the textbook response. `[P — speculative; I know of no SSP paper doing this]` |
| **Vehicle routing** | State-space relaxation, ng-routes: relax the "visited set" to a bounded memory | Applies to a DP over (position, magazine state): relax the magazine state to a bounded neighbourhood. `[P — plausible, unexplored]` |
| **Offline caching** | KTNS *is* Belady's MIN rule `\citep{Belady1966}`; the SSP is caching where the request sequence may be reordered | The caching literature's lower-bound arguments are stated for a fixed sequence. Whether any survive reordering is a real question. `[P]` |
| **General IP** | Lagrangian relaxation of the coupling constraint | Relax LSS's magazine capacity `Σ_t y_jt ≤ b`; the residual decomposes per tool. `[P]` |

### 4.4 The problem-specific route I would take first

Your own Lemma `lem:costid` gives `Z* = q + R_opt` with `q = |U|−b`. So:

> **Any lower bound on `R_opt` is exactly a strengthening of the coverage bound.**

That is the cleanest statement of the lower-bound question for this problem, and §3 already contains it without drawing the consequence. It converts "improve the bound" into "certify that some tool must be evicted and reloaded", which is combinatorial and local.

A concrete first candidate `[P — not proved, this is a conjecture to test]`: `R_opt = 0` requires a job order in which every tool's required positions can be covered by one contiguous interval, with at most `b` intervals overlapping at any position. That is a consecutive-ones / interval-thickness condition on the tool–job matrix. If so, a certificate of failure of that condition forces `R_opt ≥ 1`, and a quantitative version — how far the matrix is from C1P — would lower-bound `R_opt` directly. **Verify before believing:** implement a brute-force check on the enumerated `b=3` families that `R_opt = 0` coincides with the C1P-with-thickness-`b` condition. If it holds, the connection to pathwidth/interval graphs brings a large existing literature with it. If it fails, you have a counterexample and lose nothing.

**Ranked recommendation**

| # | Candidate | Effort | Expected payoff | Risk |
|---|---|---|---|---|
| 1 | Held–Karp ascent on the BBC master's `w` | low | medium–high | very low — cannot weaken the bound |
| 2 | Ghiani-style dynamic `w_ij` at BBC nodes | low | medium | low |
| 3 | `R_opt ≥ 1` certificates via the C1P condition | medium | high if true | **unproved** — test first |
| 4 | Laporte-style partial-sequence bound in the master | medium | medium | low |
| 5 | DFF lift of `|U|−b` | high | unknown | speculative |

1 and 2 are engineering on machinery you already have. 3 is the research contribution, and it is the one that belongs in §3 rather than §4.

**Bib gaps** `[V: grep over references.bib]`: no Held & Karp entry (`Applegate2006` is present and covers the material, but cite the original for a bound you actually use); no DFF reference. `Belady1966` is already there and currently uncited in the report `[?]` — worth checking.

---

## 5. The substantive error: §3.8's setup-cost inference

### 5.1 What the text claims

**L1128–1132** (`cor:manufacturing`) is correctly scoped to ring-like instances. **L1144–1153** then generalises:

> "and since real tooling reports setup-to-switch ratios $\rho\approx3$--$60$ (Corollary~\ref{cor:manufacturing}), production instances sit far on the collapsed side."

The theorem gives `ρ > H−Z* ⟹ collapse`, i.e. `ρ_c ≤ H−Z*`. But `H−Z*` is unbounded (Prop `prop:unbounded`: gap `= g` on `g` disjoint ring copies). On `R_61` the theorem's certificate reads `ρ > 61`, which `ρ≈3–60` does not satisfy. **The stated inference does not follow from the stated theorem.**

### 5.2 Is it also false? No — and that is the interesting part

I computed the true threshold. `[V: /tmp/v/rho.py exhaustive for g=1; /tmp/v/sep2.py closed form, cross-checked against it]`

```
g=    1  K*=    3  H=    4  Z*=    3  gap=    1  rho_c=1.0000
g=    2  K*=    6  H=   11  Z*=    9  gap=    2  rho_c=1.0000
g=   61  K*=  183  H=  424  Z*=  363  gap=   61  rho_c=1.0000
g= 1000  K*= 3000  H= 6997  Z*= 5997  gap= 1000  rho_c=1.0000
```

`H = 7g−3` and `Z* = 6g−3` reproduce Prop `prop:unbounded` exactly, which is an independent check on that proposition. `[V]` And `ρ_c = 1` for **every** `g`, while the gap grows without bound. The theorem's bound is arbitrarily loose.

The reason is structural and worth stating: the copies decide independently, so buying one extra configuration costs `ρ` and saves exactly `1` switch, regardless of `g`. **What governs the collapse is the marginal rate at which extra configurations buy switches, not the total gap.**

### 5.3 Proposed strengthening

Let `γ*(p) = min{γ(P) : |P| = p}`, non-increasing in `p`. The augmented optimum minimises `ρ(p−1) + γ*(p)`, so minimum-cardinality groupings are optimal exactly when

```
ρ  ≥  ρ_c  :=  max_{p > K*}  [ γ*(K*) − γ*(p) ] / (p − K*)
```

Since `γ*(K*) − γ*(p) ≤ H − Z*` and `p − K* ≥ 1`, this recovers `ρ_c ≤ H−Z*` — the current theorem is the `p = K*+1` term. `[P — the derivation is elementary and I am confident, but it is unproved in the sense of not having been written out formally; check it]` Verified against both datasets: on the 6-ring `γ* = (4,3,3,3)` gives `max{1, ½, ⅓} = 1` ✓, matching the exhaustive computation. `[V]`

**Proposed replacement for the closing passage (L1144–1153):**

```latex
\noindent Together with Theorem~\ref{thm:collapse} this pins both ends of the
spectrum: for $\rho<1/(n-1)$ the augmented problem \emph{is} the SSP, and once $\rho$
exceeds the gap its optima use minimum-cardinality groupings. The gap is, however, a
crude certificate. Writing $\gamma^*(p)=\min\rset{\gamma(\mathcal{P}):
\lvert\mathcal{P}\rvert=p}$, the augmented optimum minimises $\rho(p-1)+\gamma^*(p)$, so
the exact threshold is
\[
  \rho_c=\max_{p>\Kst}\frac{\gamma^*(\Kst)-\gamma^*(p)}{p-\Kst}
  \ \le\ H-\Zst,
\]
the maximum \emph{rate} at which additional configurations buy switches rather than
their total. The two can be far apart: on the $g$-fold ring family of
Proposition~\ref{prop:unbounded} the gap is $g$ while $\rho_c=1$ for every $g$, since
the copies decide independently and each extra configuration saves exactly one switch.
The collapse is therefore governed by a local trade-off, and instances whose gap is
large need not have a large threshold. Reported tooling ratios of $\rho\approx3$--$60$
\citep{Privault1995,Privault2000} exceed the thresholds of every family computed here
by a wide margin; whether a family exists with $\rho_c$ in that range is open, and is
the form in which the question should be put to practice.
```

This is longer than what it replaces, but it converts an unsupported assertion into a sharper theorem plus an honest open question — and the `ρ_c = 1` versus `gap = g` separation is a genuinely quotable result.

`[?]` **Before you accept this**: my `γ*` values for `R_g` rest on a decomposition argument (copies are tool-disjoint, so inter-copy transitions always cost `b`) that I verified exhaustively only at `g=1`. Re-verify at `g=2` with a proper enumeration if you want to state it in the report. Script: `/tmp/v/rho.py`, which will need re-committing as `plans-genai/_verification/verify_rho_c.py`.

---

## 6. Language audit

Ordered by line. "Register" = it reads as unscientific; "overreach" = the claim exceeds the evidence; "precision" = it is wrong or ambiguous as written.

| Line | Current | Type | Problem | Proposed |
|---|---|---|---|---|
| 566–569 | "no worst-case guarantee has been published for *any* SSP heuristic" | overreach | unverifiable universal negative | see §2.2 |
| 553–556 | Ghiani under "Heuristics" | precision | it is an exact B&C | see §2.3 |
| 607 | "six steps" | precision | there are seven | "seven steps" |
| 655 | "This already disposes of the $k$-rings" | register | "disposes of" | "This settles the $k$-rings" |
| 668 | §3.2 title "The gap is real and unbounded" | register | "real" is colloquial | "The gap is attained, and unbounded" |
| 669 | "whether it actually occurs" | register | | "whether it is attained" |
| 704–705 | "Perfectness of the conflict graph and the size of the gap are therefore **independent**." | **overreach** | two examples show neither property implies the other; "independent" imports a stronger (statistical) claim you have not made | "Neither perfectness nor imperfectness of the conflict graph implies anything about the gap." |
| 782 | "The theorem's cap is far above the worst case actually observed" | register | "cap" in prose | "The bound is far above the worst case observed" |
| 801–803 | "What remains afterwards is not a broken conjecture but a sharper question" | register | defensive editorialising; the reader was not accusing you | "What remains is the sharper question of whether the bound below is the exact worst case." |
| 896–898 | "it is unconditional and, to our knowledge, the first quantitative worst-case bound" | overreach | priority claim | keep "to our knowledge", or drop "first" and let the result stand |
| 928–929 | "In **exhaustive sampling** the gap is in fact $0$" | precision | contradiction in terms | "In every instance enumerated, the gap is $0$ whenever $\Zst\le3$" |
| 931 | "The heuristic admits two **readings**" | register | | "two cost models, and separating them matters here" |
| 950–953 | italicised "*the KTNS step **beats** the walk on this very witness*" | register | emphasis-by-italics inside a proposition; "beats" | de-italicise; "the KTNS evaluation is strictly cheaper than the walk value on this instance" |
| 961–963 | "Second, and **more importantly**, ... is *reopened*" | register + precision | editorial ranking; "reopened" is undefined jargon at first use | "Second, the candidate condition $\mathrm{gap}\le\Kst-2$ remains open for the heuristic itself: the counterexample refutes it only in the walk model." |
| 963–966 | "directed **hunts** across $b\in\{3,4,5\}$" | register | | "directed searches"; and cite the protocol (`VERIFIED_FACTS` 2026-07-18: 42 cells, 520 perturbations) so the claim is checkable |
| 966–969 | "a structural phenomenon **awaiting characterisation**" | register | flowery | "and the advantage of the KTNS rule over the walk model is itself uncharacterised" |
| 1092–1094 | "**locates** a first provable obstruction family ... in **exact parallel** to odd holes" | register + overreach | "exact parallel" overstates an analogy | "gives a first provable obstruction family for the set-covering relaxation ..., analogous to the role of odd holes in perfection theory" |
| 1144–1153 | "production instances sit far on the collapsed side" | **overreach** | see §5 | see §5.3 |

**Pattern worth noting.** Ten of the eighteen sit in §3.4 (`ssec:law`, L791–1000), and they cluster around the `K*−2` refutation. That passage argues *with* the reader — "not a broken conjecture but a sharper question", "more importantly", "reopened". A refutation of your own prior conjecture is a good result and reads better stated flatly. The rest of §3 is clean; §3.1–3.3 and §3.6 need almost nothing.

---

## 7. What I did not check

- Whether the enumeration counts at **L788** (10,691 + 6,065) are consistent with the **21,569** at L492. Different families and `m` ranges, so probably fine, but they are the kind of number a referee cross-adds. `[?]`
- The `[?]` items flagged inline: the Salonen citation; whether `Belady1966` is cited anywhere; the C1P conjecture in §4.4; `γ*` for `R_g` at `g≥2`.
- Anything in §4 or §5 beyond what was needed for context.

## 8. Suggested order of work

1. Free fixes: "six"→"seven", "independent", Ghiani reclassification, the register table. Low risk, no new content.
2. Run `precompute_jgp_gsp.py`. It needs no code and answers the report's own unmeasured thesis (§3.3).
3. Apply the `ρ_c` strengthening (§5.3) after re-verifying at `g=2`.
4. Insert `ssec:lit-gap` (§2.4).
5. Add the pairwise/dynamic bounds paragraph to `ssec:lb`; then Held–Karp ascent as an experiment.
6. Crama heuristics into the harness and BBC warm start — **after** the pending deck rebuild, since it perturbs timings.

**Token note.** Items 1 and 4 are pure text edits and can be applied in one pass. Item 2 is a shell command. Items 3, 5, 6 each want a verification script committed under `plans-genai/_verification/`; consider a `skills/ssp-report-editor` skill holding the register conventions above so future passes do not re-derive them.
