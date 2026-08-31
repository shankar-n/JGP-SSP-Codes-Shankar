# Theorem audit

Audit date: 30 August 2026  
Scope: the preliminaries, gap, exact-method, discussion, proof-appendix, and
independent-verifier sources.

## Verdict

The original draft did **not** merit a blanket mathematical green light. The audited
draft now has a clean separation:

- theorem/proposition/lemma/corollary = proved in the report or explicitly cited;
- observation = exact computation or a fixed empirical measurement;
- conjecture/problem = open.

The two remaining structural conjectures are the \(b=3\) \(4/3\) walk ratio and the
formula for the original tool-disjoint copy family. Neither is used as a conclusion.

## Material corrections made

1. **Cost convention and domain.** \(Z^\ast\) now always means free-initial cost;
   \(Z^\ast_{\varnothing}\) means empty-start cost. The harmless preprocessing
   \(b\leftarrow\min(b,|U|)\) makes full configurations and \(q=|U|-b\ge0\)
   well-defined.
2. **False small-optimum corollary removed.** The former claim
   \(Z^\ast\le3\Rightarrow H_{\rm walk}-Z^\ast\le1\) is false. The report now gives
   an exact counterexample with \((K^\ast,q,Z^\ast,H_{\rm walk})=(3,3,3,5)\).
3. **Connected gap question solved.** A new proved family has
   \[
   |U|=8g+1,\quad K^\ast=3g,\quad Z^\ast=8g-5,\quad H=9g-5,
   \]
   so the actual post-KTNS gap is \(g\) on connected instances.
4. **Smallest seed proved.** Four jobs are necessary and sufficient for a positive
   actual-heuristic gap; the seed has \((K^\ast,Z^\ast,H)=(3,3,4)\).
5. **Executable guarantee clarified.** The ratio bound is uniform over every
   minimum grouping, group order, and within-group order, not merely the best-case
   envelope \(H\). The exact “price of minimum cardinality” identity remains a
   statement about \(H_{\rm walk}\), not \(H\).
6. **Window claim corrected.** The integral window inequality is valid, but its
   implemented fractional max-presence extension is implied by the existing
   transition rows and cannot strengthen PCF/PCF'. The code is retained only for
   reproduction.
7. **PTF report/code mismatch fixed.** The displayed model now includes the
   per-tool counting rows used by the code and proof. Exactness and the lower bound
   \(q\) remain propositions; strict excess on two roots is correctly an Observation.
8. **Claim-status repairs.** The finite W witness, circuit-clutter pair, and
   aggregated-MTZ counterexample are Observations rather than purported proofs.
9. **Blocking statement repaired.** The ring result is stated directly for the JGP
   set-covering formulation; the incorrect claim that \(K^\ast\) is a minimum
   blocker size was removed.
10. **Full graph census run.** Removing the hidden 12-edge cutoff changes the census
    from \(76/151\) to \(80/155\) non-integral graphs; 11 remain bipartite.
11. **Setup-cost novelty scoped.** The collapse threshold is new structural analysis
    of an existing weighted objective; Salonen et al. (2006) already model the
    weighted sum of setup occasions and feeder changes.

## Formal-result ledger

| Result | Status after audit | Basis |
|---|---|---|
| KTNS fixed-order optimality | Green, cited | Tang–Denardo; independently tested against magazine-state DP |
| Grouping and coverage lower bounds | Green | Direct proofs |
| Empty/free convention identity | Green after correction | Exact per-schedule identity plus full-first optimum |
| \(H\le H_{\rm walk}\) | Green | KTNS dominates fixed group magazines |
| Grouping exactness and walk-gap identity | Green | Two constructive directions |
| Cost identity and transition cap | Green | First-use/re-insertion count |
| Instance-sensitive ratio bound | Green, strengthened | Holds for every admitted tie-breaking order |
| Zero-gap classes; \(Z^\ast\le2\) | Green | Bound plus walk lemma |
| \(Z^\ast\le3\) unit-gap claim | **Removed as false** | Permanent exact counterexample added |
| Exact \(K^\ast=3\) walk formula | Green | Three-configuration re-insertion identity |
| \(K^\ast=3\) and general-\(K^\ast\) bounds | Green | Overlap count and random-order/Jensen proof |
| \(b=3,\ K^\ast\le3\) \(4/3\) bound | Green | Unit additive bound and \(Z^\ast\ge3\) |
| General \(b=3\) \(4/3\) ratio | Open conjecture | No proof claimed |
| Four-job seed | Green, newly proved | Feasible-pair classification, explicit optimum, 12 grouped orders |
| Unbounded walk gap | Green | Tool-disjoint ring proof |
| Original disconnected seed copies | Open conjecture | Exact only for \(g=1,2\) |
| Connected unbounded actual gap | Green, newly proved | Unique grouping, coverage schedule, per-copy projection lower bound |
| Hypergraph chromatic interpretation | Green | Circuit-free colour classes |
| Non-matroid example | Green | Exchange-axiom witness |
| Circuit clutter does not determine gap | Exact Observation | Independent exhaustive computation |
| Circuit blocker identity | Green | Complement/transversal equivalence |
| Odd-ring and star cover gaps | Green | Matching primal/dual cover certificates |
| Setup-cost collapse and low-\(\rho\) lemma | Green, scoped | Explicit configuration-block model |
| PCF and PCF' integer optimum/LP values | Green after wording correction | Two-way optimum maps and LP certificates |
| PTF integer optimum and LP \(\ge q\) | Green after adding omitted rows | Flow consistency plus counting rows |
| PTF strict root excess | Exact Observation | Two recorded converged roots |
| Integral window inequality | Green | First-entry argument |
| Fractional window strengthening | **Disproved** | Algebraically redundant |

## What is still empirical

- Ring values, finite witnesses, the 1,260-instance heuristic census, root-bound
  counts, and solver performance are observations, not proofs.
- The primary campaign and the auxiliary LSS sensitivity are separate ledgers. Final
  solve counts use all 16,920 canonical method--instance identities and fixed planned
  denominators; the sensitivity is not merged.
- A solver agreeing with another solver is validation, not a proof of a general
  algorithmic claim.

## Reproduce the mathematical checks

Run:

    python verification/verify_report_independent.py
    python verification/ideal_enum.py 6
    python verification/test_resume_keys.py
    python -m unittest src.SSP.test_legacy_regressions

The verifier uses a magazine-state DP and a job-subset DP independent of the campaign
solvers. Its connected-family checks at \(g=1,2\) supplement, but do not replace, the
general proof.
