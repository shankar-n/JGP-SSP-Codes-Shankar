# Job Sequencing & Tool Switching (SSP) — project map

**The problem in one line.** One machine with a tool magazine that holds `b` tools;
`n` jobs, each needing a set of tools. Reordering the jobs changes how many tool
swaps you pay. Minimising the swaps is the SSP.

**What this project does.** Two things: (1) a **theory** of how far the standard
"group the jobs, then sequence the groups" heuristic can be from optimal; and
(2) **exact solvers** — a branch-and-Benders-cut solver (BBC) and a branch-and-price
solver (BNP) — plus a benchmark comparing them to the known formulations.

---

## The four things you probably want

| You want… | Open this |
|---|---|
| The report | `report/JGP-SSP_report.pdf`  (source `report/JGP-SSP_report.tex`) |
| The presentation | `report/JGP-SSP_campaigns_slides.pdf` (and `report/JGP-SSP_slides.pdf`) |
| The code | `src/` — see the map below |
| What's planned next | `RESEARCH_PLAN.md` (root) |

## Check it yourself — don't trust the code or me

```
python verification/verify_everything.py
```

This re-derives results from scratch (brute force on small instances) and
recomputes every headline number in the report **straight from the raw result
files**, printing PASS / FAIL for each. Parts A and C run anywhere; Part B (the
solver-correctness check) needs CPLEX, so run it on the cluster.

## Folder / file map

| Where | What it is, and why |
|---|---|
| `report/` | the report, the slide decks, `cover/` logos, and `references.bib` (the bibliography). The deliverables. |
| `src/SSP/` | shared core used by everything: instance loading, the KTNS tool-loading rule, the heuristics, the compact formulations. `utils.py` is the base. |
| `src/BBC/` | the branch-and-Benders-cut solver + the benchmark campaign (`benchmark_runner.py`, `benchmark_config.py`, `cluster/`). New this summer: `conflict_cuts.py`, `hgs_heuristic.py`, `test_new_features.py`. |
| `src/BNP/` | the branch-and-price solver (position formulations PCF′ / PTF). Start at `src/BNP/README_RESUME.md`. |
| `data/` | the benchmark instances (Catanzaro, Crama, Laporte, …). |
| `references/` | the papers, as PDFs. |
| `verification/` | `verify_everything.py` (run this to check the project) and `VERIFIED_FACTS.md` (a dated log of what was checked when). |
| `skills/` | distilled reference notes on the literature and the BBC solver. |
| `tools/` | PORTA / LRS polytope tools (Windows). |
| `RESEARCH_PLAN.md` | what's done and what's next, through the Sept-2 presentation. |
| `report_s3_review.md` | drafted (not-yet-applied) improvements to the report's §3. |
| `_archive/` | old exploratory drafts and build files, moved out of the way. Git-ignored, still on disk if ever needed. |

## Build / run

- **Report:** `cd report && pdflatex JGP-SSP_report && bibtex JGP-SSP_report && pdflatex JGP-SSP_report` (run pdflatex twice at the end). The §3 theory is toggled at the top of the `.tex` (`\includecomment{gaptheory}` = in).
- **Cluster campaign:** see `src/BBC/cluster/SLURM_RUNBOOK.md`, then `sbatch cluster/run_campaign.sbatch` from `src/BBC/`.

## Note on the cleanup (2026-08)

Years of exploratory drafts, superseded plans, per-proof check scripts, and LaTeX
build files were moved to `_archive/` — recoverable, just not in your way. The old
`plans-genai/` folder is gone; its one load-bearing file (`references.bib`) now lives
in `report/`. **Nothing the report or code needs was lost:** the report compiles and
`verify_everything.py` passes.
