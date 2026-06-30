# Branch-and-Price for PCF′ / PTF — build log & resume point

> Companion to `plans-genai/10b_position_branch_and_price.tex` (Part X cont.).
> **Common SSP code is reused from `src/SSP/` as-is** (no duplication); B&P-specific
> code lives here in `src/BNP/` (parallel to `src/BBC/`).
> AI-assisted scaffold — verify before trusting.

---

## STATUS (2026-06-22)

**P0 DONE & verified** — compact full-enumeration models (PuLP/CBC), see
`plans-genai/_verification/`:
- **PCF′** (`verify_pcf_prime.py`): IP=Z*, plain LP=0, LP+(T)=|U|−b, all matching PCF, on 6-ring + 6 random.
- **PTF** (`verify_ptf_pricing.py`): IP=Z* on 5 instances; LP tight (=3) on 6-ring.
- **Pricing reduced costs vs solver ground truth** (`verify_pricing.py`, `verify_ptf_pricing.py`):
  - PCF′ `eq:rc-pcf`/`eq:rho`: **had a sign bug (per-tool signs flipped) → CORRECTED & re-verified.**
  - PTF `eq:rc-ptf`: **correct as printed** (matches to <1e-9, cross-checked CBC `.dj`).

**P1 DONE (2026-06-22).** PCF′ column generation at the root, verified two ways: a manual CG
loop (PuLP) and the real **PySCIPOpt `Pricer`** (`src/BNP/pcf_prime_bp.py`, which also gives the root LP) both reach the
compact LP value — root LP = 3.000 = |U|−b on the 6-ring, generating ~18/120 columns. The
corrected reduced-cost signs hold in live code and SCIP's dual convention matches.

**P2 DONE (2026-06-22).** Exact branch-and-price (`src/BNP/pcf_prime_bp.py`): integer presence
vars `a_{t,p}` linked to columns, SCIP branches on `a` (robust — the pricer keeps its form),
pricer uses the link duals. **IP == Z\*** (brute KTNS) on the 6-ring (IP=3, root node, 7/120
columns) + 3 random instances. (The node-count-vs-compact symmetry win isn't illustrative yet —
these instances close at the root, nodes 1–2; it needs a larger instance, deferred to P4.)

**P3 DONE (2026-06-22).** Exact PTF branch-and-price (`src/BNP/ptf_bp.py`): coupled-pair pricer on
the real→real arcs (⊥-arcs static), robust `a_{t,p}` branching. Root CG reaches the compact PTF LP
via a strict arc subset (6-ring: 13/1900 real arcs), and **B&P IP == Z\*** on the 6-ring (IP=3, 18
arcs) + 3 randoms.

**P4 DONE (2026-06-22, SCIP-only).** PCF′ vs PTF B&P benchmark (`run_benchmark.py`,
`P4_benchmark_results.md`). Key finding: **Z\* = |U|−b on all rings + 16/16 randoms** (the cheap
PCF′ bound is tight; gaps rare — 3/4000). On the rare **gap instances** (Z\* > |U|−b, e.g.
`data/Shankar/gap-ptf-wins.txt`) PTF's root LP strictly exceeds |U|−b and cuts the B&P tree
**10×–300×** (PCF′ 299–559 nodes → PTF 1–25); where tight, PCF′ (cheaper pricer) wins. Both codes
agree on every IP. OP-X7: the stronger bound pays *iff* the gap opens.

**P5b DONE (2026-06-22): MILP pricers in.** Both `pcf_prime_bp.py` and `ptf_bp.py` now enumerate
b-subsets / arc-pairs when binom(|T|,b) is small, else solve the coverage-bonus MILP (PCF′) /
coupled-pair MILP (PTF) of 10b §4–5 in an in-process SCIP sub-model. Each MILP oracle was checked
EQUAL to enumeration on random duals (PCF′ 100 draws; PTF 60 over all step regimes), and both the
enumerate and MILP paths give IP=Z* on the 6-ring. **PTF ⊥-arc fix (same day) — DONE.** PTF's master no longer enumerates the ⊥-arcs: the cons/abs
rows are created explicitly (polynomial) and the (C,⊥) arcs are priced by a single-set MILP (the
PCF′ pricer — the head ⊥ is tool-less). Oracle: (C,⊥) MILP == enumeration (40 draws); B&P IP=Z* on
6-ring + randoms, both enumerate and MILP paths. **So both PCF′ and PTF now have O(n|T|)-row masters
and scale** (the limit is now pricing-MILP speed, not master construction). Only remaining gap:
MILP-in-callback speed at scale is untested (small instances use enumerate, so no regression).

**P5c DONE (2026-06-22): loaders.** `instance_loader.py` parses all four families uniformly
(token-based: J, T, b, then the T×J matrix; handles Crama's 3-line header and Otiai's huge rows),
verified tokens-3==T·J and |Tj|<=b. Sizes (1735 files): Catanzaro 195, Crama 160, Laporte 1350,
Otiai 30. Most are MILP-regime (|V|>4000); **Otiai is far beyond exact B&P** (J 200–400, |V|~1e57),
so those time out. `iter_instances(family, max_jobs=, max_nv=)` filters to a tractable subset.

**P5d DONE (2026-06-22): standalone campaign harness** (mirrors BBC; does NOT touch `src/BBC/` —
only read it as a template). `bnp_benchmark_config.py` (grid PCFp/PTF, instance sets + time limits,
`MAX_JOBS` cap, early-stop, CSV schema) + `bnp_benchmark_runner.py` (resumable, easiest-first,
per-solver early-stop, each solve in a timeout-guarded subprocess; computes `obj_ktns` from the
returned sequence exactly like BBC) + `cluster/` (`run_bnp.sbatch` array shards, `merge_results.sh`,
`README_BNP_CLUSTER.md` — SCIP venv, no CPLEX). Sequence extraction added to both B&P modules.
**Pilot validated**: ran real Catanzaro instances, PCF′ solved, `obj_ktns` correct (A0-0 = 6 =
obj + min(b,|U|)), CSV written. Submit:  `sbatch src/BNP/cluster/run_bnp.sbatch`.

**NEXT (cluster / refinements):** run the array, then compare PCF′ vs PTF (and offline vs BBC) on
`obj_ktns` / `root_lp_bound` / solve-rate. Open refinements: a reliable root-LP value
(`getDualboundRoot` is junk at root-closed nodes — clamped to None for now), `gap_pct` on timeouts,
faster pricing for the larger regime.

**SEPARATE — not part of this:** the BBC paper campaign (CPLEX, `benchmark_runner` + SLURM) is
independent and on its own critical path. Its results can be compared to the B&P numbers *later, at
the analysis level* — the harnesses are NOT coupled.

---

## Verified pricing formula — DO NOT RE-DERIVE (encode as-is)

PCF′ pricing, per position `p` (0-indexed, p=0..n-1): choose a b-subset `C` maximizing
`Σ_{t∈C} rho[t,p] + Σ_{j: Tj⊆C} pi[j]`; a column prices in iff `beta[p] − (that max) < 0`.

```
beta[p]  = -alpha[p] - gamma[p-1]*(p>=1) + gamma[p]*(p<=n-2)
rho[t,p] = -mu[t,p]*(p>=1) + mu[t,p+1]*(p<=n-2) + lam[t]*(p==0 and t in U)   # CORRECTED signs
```
Duals (LP solver's own values, identity-checked — convention-free):
`alpha`=[P′] (Σ_C y≤1 per pos), `gamma`=[G] (contiguity), `pi`=coverage(j),
`mu`=(W)(t, p≥1), `lam`=(T)(t∈U). PTF pricing: use `eq:rc-ptf` as printed (verified).

---

## Folder layout
```
src/SSP/   COMMON, reused as-is: utils.load_ssp_instance(path)->(J,T,C,A,T_j),
           compute_ktns(seq,...), heuristics.*, instance generators
src/BBC/   existing exact solver (UNTOUCHED)
src/BNP/   THIS WORK:
           README_RESUME.md   <- this file (live status/plan)
           pcf_prime_bp.py    <- PCF′ root CG + exact B&P (the single PCF′ module; a-branching, link-dual == eq:rho)
           ptf_bp.py          <- P3: PTF exact B&P (coupled-pair pricer, a-branching)
           run_benchmark.py   <- P4: PCF' vs PTF comparison harness + gap search
           P4_benchmark_results.md  <- P4: writeup (tight bound on rings; PTF wins on gap instances)
plans-genai/10b_position_branch_and_price.tex          theory
plans-genai/_verification/verify_{pcf_prime,pricing,ptf_pricing}.py   P0 checks (reproducible)
```

## Environment / gotchas
- Solver for B&P: **PySCIPOpt** (`Pricer` plugin) — **installed: pyscipopt 6.2.1** (bundles SCIP;
  if a fresh sandbox lacks it: `pip install pyscipopt --break-system-packages`). P0 checks used PuLP/CBC.
- **Sandbox Linux mount truncates just-edited large files** — run scripts from `/tmp`, and don't
  trust `bash` reading back a file written via the Write tool; the Windows-side file is authoritative.
- Test instance: `data/Shankar/shankar-example.txt` = 6-ring (J=6,T=6,b=3, Z*=3, |U|−b=3).

## Milestones (next-session checklist)
- [x] P0 compact sanity (PCF′ + PTF) + pricing-formula verification
- [x] **P1** PCF′ CG at root — manual CG + PySCIPOpt `Pricer` both reach |U|−b (6-ring 3.000, ~18/120 cols)
- [x] **P2** PCF′ exact B&P (`pcf_prime_bp.py`): branch on `a_{t,p}`; IP == Z* on 6-ring (root, 7/120 cols) + 3 randoms
- [x] **P3** PTF exact B&P (`ptf_bp.py`): coupled-pair pricer + `a` branching; root CG reaches compact LP; IP == Z* on 6-ring + 3 randoms
- [x] **P4** PCF′ vs PTF B&P benchmark (SCIP): bound tight (Z*=|U|−b) on rings+randoms; PTF cuts nodes 10–300× on gap instances
- [ ] **P4-cluster** CPLEX BBC/SSPMF baselines + Tabela1C campaign (SLURM); record `obj_ktns`

## To resume (paste into a fresh session)
> "Resume the B&P build: read `src/BNP/README_RESUME.md` and `plans-genai/10b...tex` §3–§4,
> load the `ssp-bbc-expert` skill, and continue at **P5** (heuristic + exact-fallback pricers in
> `src/BNP/`, replacing the enumerate-all pricers; then the wide benchmark). Isolate heavy solver runs in a subagent."
