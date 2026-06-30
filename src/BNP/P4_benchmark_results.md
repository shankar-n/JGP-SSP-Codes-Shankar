# P4 — PCF′ vs PTF branch-and-price: benchmark & findings (2026-06-22)

> SCIP/PySCIPOpt only. **Scope:** the CPLEX BBC/SSPMF baselines and the full Tabela1C
> campaign need CPLEX + the cluster (per `CLAUDE.md` SLURM setup) and are **not** run here.
> This session compares the two new exact B&P codes (`pcf_prime_bp.py`, `ptf_bp.py`) against
> each other and against brute-force KTNS on small instances — establishing the harness and
> cross-validating both solvers. Brute KTNS is the ground truth where computed; otherwise the
> two B&P codes cross-check (both exact ⇒ their IPs must agree).

## A. Tight instances (Z\* = |U|−b) — the common case

| instance | \|U\|−b | PTF root LP | PCF′ IP / nodes | PTF IP / nodes | check |
|----------|-------:|------------:|----------------:|---------------:|:------|
| 5-ring (b3) | 2 | 2.00 | 2 / 1 | 2 / 1 | agree |
| 6-ring (b3) | 3 | 3.00 | 3 / 1 | 3 / 1 | agree |
| 7-ring (b3) | 4 | 4.00 | 4 / 1 | 4 / 1 | agree |
| disjoint 4+4-ring | 5 | 5.00 | 5 / 9 | 5 / … | agree |
| 16 random (J≤6,\|T\|≤8) | — | =\|U\|−b | =\|U\|−b / 1–3 | =\|U\|−b | agree |

On **every** ring and random instance tried, **Z\* = |U|−b**: the cheap PCF′ root bound is already
tight, both solvers close at/near the root, and PTF's heavier coupled-pair pricer only costs more
(e.g. `rand0`: PCF′ 1 node vs PTF 14 nodes; PTF per-solve time 3–10× PCF′). Gaps are rare — a brute
search found only **3 gap instances in 4000** random (J∈{5,6}, T=5, b=3) draws.

## B. Gap instances (Z\* > |U|−b) — where PTF earns its bound

Three instances, all J=6, T=5, b=3, **|U|−b = 2 but Z\* = 3** (gap 1):

| inst | PCF′ root LP | PCF′ IP / **nodes** | PTF root LP | PTF IP / **nodes** |
|-----:|------------:|--------------------:|------------:|-------------------:|
| [0] | 2 (=\|U\|−b) | 3 / **559** | **2.032** (>\|U\|−b) | 3 / **25** |
| [1] | 2 (=\|U\|−b) | 3 / **439** | **2.060** (>\|U\|−b) | 3 / **17** |
| [2] | 2 (=\|U\|−b) | 3 / **299** | **3.000** (=Z\*, tight) | 3 / **1** |

Instance [2] is saved as `data/Shankar/gap-ptf-wins.txt` (`Tj` =
`[{0,2,4},{0,1},{0,1,2},{0,1,4},{0,1,4},{1,3}]`). On it PTF's LP is *tight* (3.00), so PTF proves
optimality at the **root**, while PCF′ — bound stuck at 2 — explores **299 nodes** to close the
gap-of-1. Both return Z\*=3.

## Findings

1. **|U|−b is tight on a broad sample.** Empirically Z\* = |U|−b on all rings, the disjoint
   double-ring, and 16/16 randoms; gap instances are rare (3/4000). Where the bound is tight,
   PCF′'s symmetry handling closes at the root and there is nothing for a stronger bound to do.
2. **OP-X7 answered (on this sample): the stronger bound pays *iff* the gap opens.** On the three
   gap instances PTF's root LP strictly exceeds |U|−b and the branch-and-price tree shrinks by
   **10×–300×** (299→1, 439→17, 559→25). This is the doc's "the bound is the whole game" (§3.6)
   made concrete, and it confirms the central PCF′↔PTF trade-off: PTF's heavier coupled-pair
   pricer is worth it exactly when Z\* > |U|−b.
3. **PCF′ dominates when tight; PTF dominates when the gap opens.** A practical solver should
   default to PCF′ and switch to PTF (or add PTF-style cuts) when the |U|−b bound is loose.
4. **Both exact codes agree on every instance** (and match brute KTNS where computed) — mutual
   validation of `pcf_prime_bp.py` and `ptf_bp.py`.

## Next — two SEPARATE, uncoupled efforts

**(a) Wide B&P benchmark — this work's own (SCIP, no CPLEX).** Run PCF′ vs PTF on the real instance
families (`Tabela1C`, `Crama`, `Laporte`, `Otiai`) and larger sizes: root LP, IP, nodes, time, and
how often / how far the gap opens. *Scale caveat:* the current pricer enumerates all configs/arcs
(fine for tiny |V| only); a wide run must switch to the coverage-bonus MILP (PCF′) / coupled-pair
MILP (PTF) pricer of 10b §4–5. Also: how large can (Z\* − |U|−b) get, and how far does PTF's LP
track Z\* there? (Part X OP-X1; disjoint-ring families of Part V).

**(b) BBC paper campaign — entirely separate.** The BBC/SSPMF CPLEX campaign runs on its own
(`benchmark_runner` + SLURM, thread-pinned, `obj_ktns`) as part of the BBC paper, NOT this harness.
Its results may be compared against the B&P numbers later, at the analysis level only.
