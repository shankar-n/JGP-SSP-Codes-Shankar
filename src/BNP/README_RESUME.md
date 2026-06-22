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

**NEXT → P1**: implement PCF′ column generation at the root in PySCIPOpt; assert
CG-root-LP == compact-LP (= |U|−b on the 6-ring). This re-confirms the reduced-cost
signs *in code*. Start file: `src/BNP/pcf_prime_bnp.py`.

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
           pcf_prime_bnp.py   <- PCF′ master+pricer skeleton (verified formula embedded)
           (TODO) ptf_bnp.py, run_bnp.py
plans-genai/10b_position_branch_and_price.tex          theory
plans-genai/_verification/verify_{pcf_prime,pricing,ptf_pricing}.py   P0 checks (reproducible)
```

## Environment / gotchas
- Solver for B&P: **PySCIPOpt** (`Pricer` plugin). Check: `python3 -c "import pyscipopt"`;
  if missing `pip install pyscipopt --break-system-packages` (needs SCIP). P0 used PuLP/CBC only.
- **Sandbox Linux mount truncates just-edited large files** — run scripts from `/tmp`, and don't
  trust `bash` reading back a file written via the Write tool; the Windows-side file is authoritative.
- Test instance: `data/Shankar/shankar-example.txt` = 6-ring (J=6,T=6,b=3, Z*=3, |U|−b=3).

## Milestones (next-session checklist)
- [x] P0 compact sanity (PCF′ + PTF) + pricing-formula verification
- [ ] **P1** PCF′ CG at root (PySCIPOpt RMP + Pricer using formula above); assert root LP == |U|−b
- [ ] P2 PCF′ full B&P: branch on `a_t^k = Σ_{C∋t} y_C^k`; assert IP == brute/BBC; log nodes vs compact
- [ ] P3 PTF CG/B&P: coupled-pair pricer (`eq:rc-ptf`)
- [ ] P4 benchmark vs BBC/SSPMF on a Tabela1C subset; record `obj_ktns`

## To resume (paste into a fresh session)
> "Resume the B&P build: read `src/BNP/README_RESUME.md` and `plans-genai/10b...tex` §3–§4,
> load the `ssp-bbc-expert` skill, and continue at **P1** (PySCIPOpt PCF′ pricer in
> `src/BNP/pcf_prime_bnp.py`). Run heavy solver work in a subagent to save context."
