# Grounding audit — `mid_internship_report.tex`

Every quantitative / "verified" / novelty claim in the report, mapped to what backs
it. **P** = proved in the report; **V** = numerically verified (script named);
**L** = from the literature (citation); **⚠** = weakly grounded, needs work.

## Preliminaries (§2)
| Claim | Status | Source |
|---|---|---|
| KTNS optimal for fixed order, $O(n\lvert T\rvert)$ | L | Tang & Denardo 1988 |
| KTNS $=$ Bélády optimal caching | L | Belady 1966 (standard equivalence) |
| $Z^*\ge K^*-1$ (grouping bound) | P | Prop. (report) §2.5; `VERIFIED_FACTS` LB1 |
| $Z^*\ge \lvert U\rvert-b$ (coverage bound) | P | Prop. (report) §2.5; `VERIFIED_FACTS` LB2; $=$ da Silva $M{-}C$ |
| empty-start $=$ free-initial $+\min(b,\lvert U\rvert)$ | P/V | Prop. (report); `VERIFIED_FACTS` "CONVENTIONS" |

## Gap theory (§3)
| Claim | Status | Source |
|---|---|---|
| $Z^*=\min$ GTSP cost over **all** groupings (grouping exactness) | P/V | report appendix proof; `VERIFIED_FACTS` OP4 (1,306 instances, 0 violations) |
| 6-ring $Z^*=3$, $H=4$, $K^*=3$, gap $1$ (free-initial) | V | `VERIFIED_FACTS` "Documented examples"; `ssp_verify.py` |
| ring table $k=3..8$ | V | `VERIFIED_FACTS` "Rings k=3..8" |
| unbounded gap: $g$ rings, $Z^*=6g{-}3$, $H=7g{-}3$, gap $=g$ | P/V | report appendix proof; `VERIFIED_FACTS` "Gap growth" (verified $g=1..4$) |
| $H/Z^*\le b$ ($b$-approximation) | P | report §3.3 (Prop. $H\le b(K^*{-}1)$ + Cor. bound) |
| $H/Z^*\le 4/3$ for $b{=}3$ (conjecture) | V (conj.) | `VERIFIED_FACTS` OP1 — 10,691 + 6,065 instances, max $=4/3$, no counterexample |
| gap $\le K^*-2$ (conjecture) | V (conj.) | `VERIFIED_FACTS` OP11 — ~1,380 instances, 0 violations |
| extremal ratio non-decreasing in $b$; $3/2$ at $b{=}5$ | V | `VERIFIED_FACTS` OP2 (corrected) |
| setup-collapse $\rho_c\le H-Z^*$; ring $\rho_c=1$ | P | report §3.4 proof; `VERIFIED_FACTS`/`07` ($R(\rho)$, $\rho_c{=}1$) |
| manufacturing $\rho\approx 3$–$60$ | L | Privault & Finke 1995/2000 |
| conflict graph: prism (perfect)→gap 1, $C_5$ (imperfect)→gap 0 | V | `VERIFIED_FACTS` "Conflict-graph corrections" (note: earlier "$2K_3$" claim was **wrong**, corrected to the prism) |

## Exact methods (§4)
| Claim | Status | Source |
|---|---|---|
| SSPMF LP relaxation $=\lvert U\rvert-b$ | L/V | da Silva 2024; `VERIFIED_FACTS` (SSPMF root LP, c21 convention note) |
| BBC loading subproblem TU $\Rightarrow$ integral $=$ KTNS | P/V | report §4.2; `verify_bbc2.py` (DSP $=$ `compute_ktns` 60/60) |
| BBC depot-dual cut bug fixed | V | `VERIFIED_FACTS` BBC audit (`verify_bbc_audit.py`) |
| PCF exact; plain LP $=0$; with (T) LP $=\lvert U\rvert-b$ | P/V | `10`/`10b`; `verify_posform.py` |
| PTF exact; LP $>\lvert U\rvert-b$ ($2.10$ vs $2$); tight on ring | P/V | `10b` Prop.; `verify_posform_f2.py` |
| PCF′ exact; LP $=\lvert U\rvert-b$ (symmetry, not strength) | P/V | report appendix proof; `10b` §2; `verify_pcf_prime.py` (6-ring) |
| PCF′ reduced cost $\bar c(C,k)=\beta_k-\sum\rho-\sum\pi$ | V | `verify_pricing.py` — **sign-corrected** version (earlier draft bug caught) |
| PTF reduced cost (coupled pair, McCormick) | V | `verify_ptf_pricing.py` (signs correct as printed) |
| branch-and-price returns $Z^*$ on ring + randoms | V | `pcf_prime_bp.py`, `ptf_bp.py` (P2/P3) |
| cluster-aggregated MTZ not exact (4-job counterexample) | P/V | `VERIFIED_FACTS` OP6-resolved; per-config MTZ exact |

## Computational study (§5)
| Claim | Status | Source |
|---|---|---|
| KTNS vs exact state-DP, 8,000 seqs, 0 disagreements | V | `VERIFIED_FACTS` header (`run_study.py`) |
| cross-solver agreement vs brute on small instances | V | `test_solver.py` (BBC/LSS/SSPMF/CATZ vs brute) |
| instance sizes (Catanzaro/Crama/Laporte) | L | benchmark sets (Catanzaro 2015 / Crama / Laporte) |
| campaign results (tables) | — | **deferred** (runs in progress) |

## ⚠ Weakly grounded — fix before circulating
| Claim in report | Problem | Action |
|---|---|---|
| "the literature has not analysed the worst-case behaviour of the standard heuristic" (§6) | Novelty claim resting only on an internal lit-dive (Calmels 2018 survey). A C&OR-2018 paper reportedly proves a **3/2** worst-case ratio for *some* SSP heuristics. | Verify via a literature check; restate precisely as "no worst-case analysis of the **JGP+GSP decomposition specifically**", and cite the 3/2 result as related. |
| "reconciled with worst-case approximation guarantees reported elsewhere" (§6) | Vague; the 3/2 paper is **not** in `references.bib`. | Obtain + cite it, or drop the forward reference. |
| Otiai/Moreira characterisations (§2.7, §5.4) | Paraphrased from the theses; accurate but worth a direct page/table ref when those become available. | Pin to specific results/tables in the theses. |
| Colares 2026 as source of the configuration/GTSP view | `Colares2026Exact`/`Tool` cited; the exact contribution boundary vs this work is unsettled. | Delineate the novelty vs Colares et al. explicitly (see report review). |

## Note on provenance
`plans-genai/10b…tex` self-identifies as an AI-assisted draft, **not** ground truth.
Only its *verified* content (the rows above marked V, backed by `verify_*.py`) was
imported into the report; its implementation plan and open problems (OP-X5/6/7) were
not.
