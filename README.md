# JGP-SSP: Job Sequencing and Tool Switching

Research code, proofs, benchmark results and presentation material for an internship study
of the Job Sequencing and Tool Switching Problem (SSP), carried out at LIMOS, ISIMA /
Université Clermont Auvergne.

A machine holds `b` tools in a magazine; job `j` requires the tool set `T_j`; running the
jobs in some order forces a tool insertion whenever a required tool is absent. The problem
is to minimise the total number of insertions. For a fixed order the optimal loading is the
Keep Tool Needed Soonest rule and is polynomial; choosing the order is NP-hard for every
fixed capacity `b ≥ 2`.

The study asks two questions. **Structurally**, what does the standard group-then-sequence
heuristic lose against the integrated problem? **Algorithmically**, can an exact loading
oracle carry a decomposition past the elementary counting bound `q = |U| − b`?

## Results

- The two-phase construction admits two distinct values — a walk through one fixed magazine
  per group, and the value obtained after its final loading step. The literature conflates
  them, and they differ on the instances most often used as examples.
- The optimum equals the cheapest walk over *all* feasible groupings, so the loss is exactly
  the price of insisting on the fewest groups. A ratio bound `min(b, K*−1, q)` holds for
  every instance, and zero-gap classes exist at every capacity.
- A connected instance family has an unbounded additive gap, with `Z* = 8g−5` and
  `H = 9g−5`, while its ratio tends to `9/8`.
- A branch-and-Benders-cut solver whose subproblem is an exact polynomial oracle, and
  position-indexed branch-and-price formulations, one of which can exceed the counting
  bound.
- A campaign of 1,410 canonical instances across 12 configurations — 16,920 planned
  outcomes, all present — finds the tested Benders regimes **certificate-limited**: on the
  runs that hit the time limit the incumbent is usually already optimal, and every
  strengthening aimed at the dual bound is neutral or harmful.

The computational comparison concerns the implementations in this repository. It is not a
literature-wide ranking: stronger published formulations were outside the implementation
scope, and effective solver thread counts differ between methods. Both points are recorded
in the report's limitations.

## Repository map

- [`report/JGP-SSP_report.pdf`](report/JGP-SSP_report.pdf) — the report.
- [`report/JGP-SSP_defence.pdf`](report/JGP-SSP_defence.pdf) — defence slides.
- [`report/JGP-SSP_defence_script.md`](report/JGP-SSP_defence_script.md) — slide-by-slide
  speaking script.
- [`src/SSP/`](src/SSP/) — compact SSP formulations and shared utilities.
- [`src/BBC/`](src/BBC/) — the Benders implementation, cluster workflow, campaign ledger
  and provenance.
- [`src/BNP/`](src/BNP/) — position-indexed and branch-and-price prototypes.
- [`verification/`](verification/) — independent theorem and campaign checks.
- [`data/`](data/) — benchmark instances (Catanzaro, Crama and Laporte families).

## Verification

The checks share no code with the solvers: the loading rule is reimplemented and compared
against an exact dynamic program, and the optimum comes from a dynamic program over subsets
of jobs cross-checked by brute-force enumeration on the smallest instances.

From the repository root:

```text
python verification/verify_report_independent.py      # 58 mathematical checks
python verification/analyse_campaign_results.py --check   # every reported figure
python verification/test_resume_keys.py
python -m unittest src.SSP.test_legacy_regressions
```

The comparison uses one fixed primary protocol and counts every non-optimal outcome as
unsolved. Higher-resource sensitivity runs and raw scheduler diagnostics are kept out of the
published comparison. Rerunning the optimisation campaign requires the solver environments
described in the report, including CPLEX 22.1.1 for the primary methods.

## Building the report

```text
cd report
pdflatex JGP-SSP_report && bibtex JGP-SSP_report && pdflatex JGP-SSP_report && pdflatex JGP-SSP_report
```

The defence deck builds the same way from `JGP-SSP_defence.tex`, which inputs
`JGP-SSP_defence_main.tex`. Figures are regenerated from the campaign ledger by
`report/make_defence_figures.py` and `report/make_report_figures.py`.

## License

Code is released under the [MIT License](LICENSE). Benchmark instances and cited
third-party material remain subject to their original terms.
