# Report and defence build notes

The report was rebuilt and received a final source, code, data, and reference audit on
2026-08-29. The authoritative inputs are the split TeX sources,
`references.bib`, the checked-in campaign CSV files, and the verification programs.

## Main files

| File | Purpose |
|---|---|
| `JGP-SSP_report.tex` | Main report and input list |
| `ch0_abstract.tex` to `ch9_declaration.tex` | Report chapters |
| `appA_proofs.tex` to `appD_learned.tex` | Proof, verification, reproducibility, and learned-cut appendices |
| `JGP-SSP_defence.tex` | Defence slide deck |
| `references.bib` | Bibliography |
| `figdata/` | Figure data regenerated from campaign and verification outputs |
| `make_figure_data.py` | Regenerates the figure data |

## Build commands

Run these commands from `report/`:

```text
pdflatex JGP-SSP_report
bibtex JGP-SSP_report
pdflatex JGP-SSP_report
pdflatex JGP-SSP_report

pdflatex JGP-SSP_defence
pdflatex JGP-SSP_defence
```

The verified outputs from the final build are a 96-page report and a 29-slide defence.

## Verification commands

Run these commands from the repository root with the project Python environment:

```text
python verification/analyse_campaign_results.py --check
python verification/verify_report_independent.py
python verification/bound_probe.py --check --output tmp/bound_probe_recomputed.json
python verification/test_resume_keys.py
python src/SSP/test_legacy_regressions.py
python src/BBC/test_solver.py
python report/make_figure_data.py
```

The bound probe intentionally uses the fixed 81-instance sample listed in
`verification/bound_probe_instances.txt`. It is a diagnostic sample, not a complete
benchmark family.

## Final audit corrections

The final audit made the following material corrections.

1. The completed campaign archive contains 17,052 raw rows over 1,421 checked-in files. Eleven
   Catanzaro file identities are non-canonical: ten are byte-identical duplicates and
   one is an ad-hoc test file. All reported aggregates therefore use 1,410 canonical
   instances and all 16,920 planned canonical rows. A hashed pre-recovery copy of every
   affected shard is retained for auditability.

2. The historical campaign resume key used only file name and configuration. Because
   Crama reuses names at different capacities, it silently skipped 58 planned pairs on
   requeue. The BBC and BNP runners now key on family, file name, jobs, tools, capacity,
   and configuration. The 58 missing pairs were rerun under the original envelope.

3. Every coverage calculation uses `|U| - b`, where `U` contains only tools required
   by at least one job. Ten canonical instance identities contain an unused declared
   tool, so the SSPMF theorem requiring every declared tool to be used is not invoked
   for them.

4. The report distinguishes the cost of a fixed-configuration group walk from the
   cost after KTNS post-processing. The high-setup theorem now applies only to the
   explicit configuration-schedule model; it does not claim that ordinary KTNS
   post-processing is exact.

5. Literature-wide rankings were removed. SSPMF is the strongest of the three compact
   baselines reimplemented in this campaign, while the stronger 2024 JGSMF model was
   not implemented. The heuristic review now also includes the 2025 parallel-tempering
   comparison rather than calling the 2021 HGS the unqualified current state of the
   art.

6. The report separates the primary 16-GiB ledger from the 32-GiB LSS sensitivity and
   uses a fixed 1,410-instance denominator. The completed primary ledger has 376 confirmed OOM
   outcomes; the sensitivity changes 245 of the 352 LSS OOMs to time-limit-feasible but
   certifies no new optimum. The 123 exact-envelope recovery jobs (58 absent,
   48 credential expiry, 17 unexplained exits) are merged: 17 certified optima, 91
   time-limit-feasible outcomes, and 15 scheduler-confirmed OOM outcomes.

7. Bibliography identities and metadata were checked against the supplied PDFs,
   including Calmels, Jans, Kashou, Otiai, Pop, and Yanasse.

Catanzaro Formulation 5 and the Akhundov--Ostrowski JGSMF model remain outside the
implemented comparison and are identified as limitations in the report.
