# Research plan — now → Sept 2 presentation (preliminary report: tomorrow)

Two milestones:
- **Tomorrow**: *preliminary* internship report — the finished theory (§3) + the
  campaigns as they stand (§5) + an honest "implemented, validation-gated, runs
  pending" account of the accelerations. Submittable as work-in-progress.
- **2 September (defense/presentation)**: *full* research output — corrected +
  accelerated BBC campaign, improved BNP, RL-for-cuts prototype, complete
  re-analysis, and the presentation.

The hard constraint throughout: **I have no CPLEX here — every cluster run is
yours (SLURM).** I can write/validate all code, prep every launch script, and
write the report/deck; I cannot make the runs happen or go faster. Queue +
wall-time on your cluster is the real bottleneck, which is exactly why the full
output is a Sept-2 target, not a tomorrow one.

---

## Current state (so nothing is left out)

DONE and in the repo:
- Full gap theory §3 (worst-case bounds, extremal K*=3 analysis, setup-cost
  spectrum, clutter structure). *Under your line-by-line proof verification.*
- BBC + compact-model campaign (§5), BNP (PCF'/PTF) campaign — the 07-18 numbers.
- **Fractional-cut BUG fixed** (`add_user_cut` `purgeable=` -> TypeError, silently
  swallowed; "structurally inactive" was a masked failure). Report claim corrected
  today; effect pending re-run.
- **Acceleration features implemented + sandbox-validated**: conflict-graph cuts
  (`conflict_cuts.py`), HGS primal heuristic (`hgs_heuristic.py`), Papadakos
  Pareto lifting; wired as flags `use_conflict_cuts/primal_heuristic/pareto_cuts`;
  benchmark configs `BBC-LP+F+{C,H,P}`, `BBC-LP+ACC`; sbatch array extended `0-14`.
- Validation harness `test_new_features.py` (Part A passes in sandbox; Part B is
  the CPLEX gate). Debug driver `debug_fractional_cuts.py`.

PENDING (the research programme below):
P1 validation gate · P2 verbose logging · P3 BBC accel campaign · P4 BNP
improvement · P5 RL for cuts · P6 re-analysis + full report/deck.

---

## Critical path & dependencies

```
P0 (prelim report, tomorrow)   ── independent, do now
P1 gate ─┬─> P2 logging ─┬─> P3 BBC campaign ─┐
         │               └─> P4 BNP accel  ───┼─> P6 re-analysis ─> full report + Sept-2 deck
         └─> (everything empirical blocks on P1)         │
P5 RL ── design starts now, TRAINS on P3's baseline ─────┘
```

---

## The work, phase by phase

### P0 — Preliminary report (TOMORROW) — owner: me tonight, you: verify §3
- [x] Correct the false "structurally inactive" claim (done today).
- [x] Toggle §3 into the compiled document (done today — **you must confirm §3's
      proofs are submission-ready; one-line revert to circulation if not**).
- [ ] Add a short "Implemented accelerations and next steps" subsection so the
      preliminary report shows the full arc (features done, gate + runs pending).
- [ ] Recompile full report (pdflatex x2 + bibtex), sanity-check.
- Effort: ~1-2 h (mine). No cluster needed.

### P1 — Validation GATE (blocks all new empirical results) — owner: you, cluster
- Run `test_new_features.py` Part B (CPLEX): BBC-with-each-flag must return the
  brute-force optimum; flags must fire. A wrong cut is caught here.
- Run `debug_fractional_cuts.py` on a bound-loose instance: confirm the fix —
  `frac cuts added` > 0, `add_failed` = 0, and the **dual bound moves off |U|**.
- Effort: ~30-60 min cluster. **If any "WRONG OPTIMUM" -> stop, send me the log.**

### P2 — Verbose per-instance logging — owner: me (code), you: use it
- A `verbose_log` mode on the BBC solver writing a per-instance trace:
  primal/dual bound trajectory over time, cuts by family (sec/comb/benders/frac/
  conflict/pareto), DSP objective vs theta at each separation, node count,
  incumbent evolution, final sequence, and the stop reason. One file per instance.
- Purpose: debug *why* a particular instance stalls (exactly what you asked for).
- Effort: ~2-3 h (mine); testable in sandbox except the live CPLEX trace.

### P3 — BBC acceleration campaign — owner: me (scripts+analysis), you (cluster)
- Re-run array `0-14` (corrected fractional cuts + `BBC-LP+F+{C,H,P}`, `+ACC`).
- Measure, per config:
  1. Does the fixed fractional cut / Papadakos **raise the dual bound above |U|**
     on bound-loose instances? (this can overturn the "bound-limited" verdict)
  2. HGS primal effect: nodes, time-to-first-incumbent, extra solves from pruning.
  3. Conflict-graph bound: does it help the grouping-dominated instances?
- Deliverable: refreshed `tab:solves`, ablation table, the bound-tightness figures.
- Effort: cluster wall-time (hours-days); my analysis ~1 day once CSVs land.

### P4 — BNP improvement — owner: me (code), you (cluster)
- Honest read: BNP is bound-limited *by proof* (PCF' LP = |U|-b). "Better results"
  = the engineering agenda already named in §5: **warm column pool, dual
  stabilisation, heuristic pricing with exact certification.** These convert the
  bound-tight-but-slow failures (73 for PCF') into solves — a concrete win.
- Longer/research: broaden where PTF's relaxation exceeds |U|-b.
- Re-run BNP; re-measure single-node rates and solves.
- Effort: code ~2-3 days (mine); cluster wall-time (yours).

### P5 — RL for better cuts (the prof's suggestion) — owner: me (design+code),
###      you (training runs) — LONG POLE, prototype-by-Sept-2
- Decide target (I recommend deciding after P3 baseline lands):
  (a) BBC: learn cut-family / Papadakos core-point selection per instance; or
  (b) BNP: **ML column selection for the pricer** (Morabit 2021) — the SCIP/Ecole
      tooling fits PySCIPOpt, and the coupled-pair PTF pricer is the real cost.
- Pipeline: instance features (bipartite LP graph) -> policy -> integrate in the
  cut/column loop. **Imitation learning from a look-ahead oracle first** (cheaper,
  more stable than RL); RL only if time.
- Honest scope: realistic Sept-2 target is a *working prototype with preliminary
  results*, framed as such. Full RL is the riskiest item; do not over-promise it.
- Prereq: the P3 deterministic baseline (as comparison + training signal).
- Effort: 2-4 weeks (mine, design+build); training runs yours.

### P6 — Re-analysis + full report + Sept-2 deck — owner: me (writing/plots), you (verify)
- Re-run the notebook analysis (the appendix cells) on the new CSVs; regenerate
  every table/figure.
- Update §5 (correct the bound-limited narrative if P3 moves the wall), finalise
  §3, refresh remaining-work.
- Build the Sept-2 presentation from the full output.
- Effort: ~2-3 days once P3/P4 land.

---

## Who does what

| I do (no CPLEX needed) | You do (cluster / judgement) |
|---|---|
| all code: logging, BNP accel, RL pipeline, scripts | run every SLURM job (CPLEX) |
| all writing: report, Sept-2 deck | verify §3 proofs before submitting |
| all sandbox validation (cut validity, HGS gap) | launch the P1 gate; send logs if it fails |
| ready-to-launch cluster commands | final research decisions (RL target, scope) |

## Risk flags (honest)
- **RL is the long pole.** Plan for prototype + preliminary results by Sept 2, not
  a finished system. Frame it that way in the deck.
- **The bound wall may not move** even with the fixed fractional cuts + Pareto —
  that is itself a real, reportable result (confirms the |U|-b limit is fundamental).
- **Cluster wall-time** dominates the schedule; start P1 + P3 launches ASAP so runs
  proceed while I build P2/P4/P5.
- **Don't put unvalidated results in the preliminary report.** Only P0 (writing) is
  tomorrow; everything empirical waits for P1 to pass.

## Immediate next actions (tonight)
1. YOU: launch the **P1 gate** on the cluster (`test_new_features.py`) — it unblocks
   everything and runs while I build.
2. ME: finish **P0** (accelerations/next-steps subsection + recompile) so tomorrow's
   report is safe, then start **P2 verbose logging**.
3. Then P3 launch scripts are ready; you kick off the campaign; I move to P4/P5.

---

## TODO — rewrite report §5 methodology (NOT now; only after the re-run)

The experimental protocol was changed (2026-08) to the standard one: run every
instance in every family to a single uniform time limit (600 s), no early-stop,
no primary/secondary tiering. The report's §5 still describes the OLD protocol
(easiest-first + per-config early-stop, primary/secondary suites with two
different time limits, "solved/attempted" denominators). When the new campaign
finishes, §5 must be rewritten:
  - remove ALL mention of early-stop, the retirement rule, "attempted"
    denominators, and the primary-vs-secondary split with its two time limits;
  - state the clean protocol (all instances, one TL, reported per family);
  - replace the solved/attempted tables with per-family solved counts + a cactus
    plot (performance profile) + shifted-geomean times on commonly-solved instances;
  - re-derive every number from the new results/*.csv (verify_everything.py style);
    carry over no old number.
Per Shankar: do this only after the re-run lands.
