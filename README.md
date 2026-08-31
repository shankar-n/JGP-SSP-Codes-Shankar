# JGP-SSP: Job Grouping and Tool Switching

Research code, proofs, benchmark results, and presentation material for an internship
study of the Job Sequencing and Tool Switching Problem (SSP).

The project studies two linked questions: when the usual group-then-sequence heuristic
loses against the integrated SSP, and why a branch-and-Benders-cut implementation has
difficulty certifying solutions. The report proves an unbounded additive heuristic gap
on a connected instance family and analyses a completed campaign of 1,410 canonical
instances across 12 configurations (16,920 primary runs).

The computational comparison concerns the implementations in this repository. It is
not a literature-wide state-of-the-art ranking: stronger published formulations were
outside the implementation scope, and effective solver thread counts differ.

## Repository map

- [`report/JGP-SSP_report.pdf`](report/JGP-SSP_report.pdf) - final report.
- [`report/JGP-SSP_defence.pdf`](report/JGP-SSP_defence.pdf) - defence slides.
- [`report/JGP-SSP_defence_script.txt`](report/JGP-SSP_defence_script.txt) - slide-by-slide speaking script.
- [`src/SSP/`](src/SSP/) - compact SSP formulations and shared utilities.
- [`src/BBC/`](src/BBC/) - Benders implementation, cluster workflow, results, and provenance.
- [`src/BNP/`](src/BNP/) - position-indexed and branch-and-price prototypes.
- [`verification/`](verification/) - independent theorem and campaign checks.
- [`report/README_BUILD.md`](report/README_BUILD.md) - report build and audit notes.
- [`REPO_HYGIENE.md`](REPO_HYGIENE.md) - public-release and local-archive policy.

## Verification

From the repository root:

```text
python verification/analyse_campaign_results.py --check
python verification/verify_report_independent.py
python verification/test_resume_keys.py
python -m unittest src.SSP.test_legacy_regressions
```

The comparison uses one fixed primary protocol and counts every non-optimal outcome as
unsolved. Higher-resource sensitivity runs and raw scheduler diagnostics are kept in
the local research archive, not mixed into the published comparison. Rerunning the
optimisation campaign requires the solver environments described in the report,
including CPLEX 22.1.1 for the primary methods.

## License

Code is released under the [MIT License](LICENSE). Benchmark instances and cited
third-party material remain subject to their original terms.
