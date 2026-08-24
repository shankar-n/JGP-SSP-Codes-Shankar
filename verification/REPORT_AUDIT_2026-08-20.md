# Report revision audit — JGP-SSP_report.tex — 2026-08-20

Scope: full read of `report/JGP-SSP_report.tex` (2,765 lines, 57 pp compiled, full version with §3 included), cross-checked against `verification/VERIFIED_FACTS.md`, `verification/verify_19971.out`, `RESEARCH_PLAN.md`, `CLAUDE.md`, `references.bib`, `src/BBC/benchmark_config.py`, and the instance directories. Line numbers refer to the current tex (mtime 2026-08-18). This is an audit + plan, no edits made.

Build health: compiles clean (1 overfull box, no undefined/multiply-defined references; all 47 cited keys resolve in `references.bib`).

---

## 1. Errors and contradictions found (first verification pass)

These are defects independent of style; they should be fixed regardless of the other passes.

**E1 — Abstract, l.111: strict inequality is wrong.** "ratios such as $H/Z^*<4/3$ at $b=3, K^*\le3$". Prop. 43route (l.1386) proves $\le 4/3$, and the 6-ring *attains* 4/3 at $b=3, K^*=3$. Must be $\le$.

**E2 — Frame overclaim in abstract (l.109–110) and Contributions (l.355–357).** Both say an explicit instance "refutes the natural guess gap ≤ K*−2" with no qualifier. Per prop:refute (l.1354) and the 2026-07-17 frame audit, the refutation holds only for the walk value $H_{\text{walk}}$; for the heuristic as defined (KTNS-evaluated $H$) the same witness has gap 1 and the conjecture is reopened. As written, the abstract asserts a false statement about $H$ (gap is defined via $H$ at l.566). Every mention of the refutation must carry the walk qualifier.

**E3 — l.451: "the 6-ring is thus the smallest instance on which grouping-then-sequencing is provably sub-optimal."** Contradicted inside the report itself: $I_1$ of prop:noclutter (l.1518) has $n=4$, $b=4$, gap 1; witness W1 (l.1358) has $n=5$. "Smallest" needs a defined order and family (e.g. "smallest instance in the two-tools-per-job family at $b=3$") or should be dropped.

**E4 — prop:oddring (l.1555) fails at $k=3$.** For the 3-ring the whole job set is one group, so $K^*=1 \ne \lceil 3/2\rceil$, and the proof's "the maximal groups are the adjacent edge pairs" is false there. Needs the hypothesis $k\ge4$ (the interesting content is odd $k\ge5$; even-$k$ tightness holds from $k=4$).

**E5 — §6.1, l.2437: "the gap has a matching lower bound (Corollary cor:lb)".** cor:lb lower-bounds $Z^*$, not the gap. Mis-statement; rewrite (presumably "the optimum has matching lower bounds").

**E6 — $H$ is formally defined twice, with different meanings.** l.564 defines $H$ as the KTNS-evaluated cost of the heuristic (step 3). l.1050 (cor:gap) redefines $H=\min\{\gamma(\mathcal P):|\mathcal P|=K^*\}$ — the walk value. l.1346–1352 then introduces $H_{\text{walk}}$ for exactly the l.1050 quantity and says $H\le H_{\text{walk}}$. So cor:gap, lem:costid's "$H=q+R_H$", and §3.1–3.3 are literally about $H_{\text{walk}}$ while using the symbol $H$. Fix: one definition each for $H$ and $H_{\text{walk}}$ in §2/§3.1, restate cor:gap and the early §3 results in the correct symbol, and annotate every numeric $H$ (tab:rings etc.) with its frame (on rings the two coincide — say so once).

**E7 — Result-status labelling is inconsistent (three different classifications).**
- §3 Status paragraph (l.963–970): definitive = refutation + zero-gap + unbounded-gap constructions only.
- §6.1 (l.2432–2451): definitive additionally includes thm:grouping, cor:gap, cor:lb, cor:zerogap.
- prop:genk (l.1286) is typeset as a Proposition **with a printed proof**, then l.1310–12 says it "is stated here as a conjecture". Same tension for prop:k3, prop:hk3, thm:uncond, cor:z3, thm:collapse: theorem-environments with proofs, described elsewhere as evidence-backed conjectures.
One scheme must be chosen and applied uniformly (see Decision D3 below), and the abstract / §3 opener / §6.1 lists must be generated from the same partition.

**E8 — Stale July text contradicting the interim framing.**
- Contributions bullet 3 (l.368–374): "a complete benchmark … quantifying the coverage bound's tightness (48.0% among solved instances) and demonstrating mechanically…" — contradicts §5.2 (l.2364–2375: campaign still running, snapshot only, "no cross-method ranking … can responsibly be drawn").
- §7 "The corrected Benders master" (l.2574–2594): "The full re-run … is complete, and its outcome is reported in Section ssec:results: the solve counts multiply, every remaining timeout still carries an optimal incumbent, and the configuration solves nothing outside the bound-tight class" — §5.2 reports none of this. It also collides with §5.2's own provisional observation (l.2381–2386) that on the snapshot "the coverage bound is strictly below the optimum [on most solved instances] and the gap is closed by branching". The two describe different runs/protocols, but the document as compiled contradicts itself.
- These sentences date from the 07-17/07-18 numbers (verified then by `verify_19971.out`), which per `RESEARCH_PLAN.md` are not to be carried into the new-protocol report. Either strip all completed-campaign claims until the re-run lands, or reinstate them everywhere with an explicit "previous protocol" label — not the current mixture.

**E9 — Abstract l.127: "1,421 standard instances".** Recount from the harness globs (`benchmark_config.py`: Catanzaro Tabela1C 195 + Crama 160 + Laporte T3/T4/T5/T7 = 1,090) gives 1,445 `.txt` files. The 24-file difference is unexplained (non-instance files? load errors?). Re-derive the number from `expand_sets()` output, or drop the count.

**E10 — Numbers with no ground-truth entry.**
- RL prototype "raises the bound about 60% more per episode" (l.2255–57): no entry in VERIFIED_FACTS; verify from the training logs or cut (also a candidate under directive "no conclusion → omit").
- cor:manufacturing $\rho\approx3$–60 (l.1605–09, Privault 1995/2000): literature values, unverified in-project; re-check the two papers before keeping a corollary that rests on them.
- Directed-hunt ranges l.1377–81 claim "$b\in\{3,4,5\}$ and $K^*\in\{3,4,5\}$"; VERIFIED_FACTS (07-18) records 42 cells with $b\in\{4,5\}$ + the earlier $b=3, K^*=4$ map. The $K^*=5$ and $b=3$ full-range claims need the hunt output as source, or restate as recorded.
- prop:sspmf-lp (l.1765): "relaxation … equals $|U|-b$", attributed to da Silva. Their own theorem is $M-C$ in their convention; VERIFIED_FACTS flags the convention divergence as unverified. Either verify the identification (used-tools hypothesis) against the paper or state it in their terms.

**E11 — Bibliography quirks (rendered output is affected).**
- `daSilva2024` has `year = {2021}` in the bib, so citations render "[2021]" while CLAUDE.md and the key say 2024; tab:lineage row says 2021. Confirm the actual publication year and align key/text/table.
- `Calmels2018` has `year = {2018}`; the survey is commonly cited as IJPR 2019 (online 2018). Check which the journal version carries.
- 16 unused bib entries (harmless; prune optional).

**Checks that PASSED replay** (first pass, to be redone systematically in the verification pass): lb1/lb2/conv proofs; KTNS figure cell-by-cell vs the magazine trace; tab:rings vs VERIFIED_FACTS; prop:unbounded arithmetic; lem:costid; lem:transcap; thm:uncond algebra; cor:zerogap/smallZ/z3 case logic; prop:hk3 cost split; lem:overlap counting; prop:k3 corner analysis ($b\ge5$ necessity); prop:genk Jensen computation; thm:collapse and lem:lowrho; prop:chromK star; prop:nonmatroid; blocking identity; W1, $I_0/I_1$, $K^*=4$ witness, MTZ counterexample, sliding-window ring, PTF 2.10 vs 2, TSP(w) 24.6%/4.9/1% — all match VERIFIED_FACTS; PCF/PCF′/PTF row logic and pricing reduced-cost shape; Benders subproblem TU/dual-cut shape; §5.1 3600 s time limit matches `benchmark_config.py` (the 600 s in RESEARCH_PLAN's TODO block is the stale one).

---

## 2. Directive: no instance enumeration mentioned

Inventory of enumeration/census mentions: l.112 ("several thousand instances we tested"), l.127 (1,421), l.722–724 (21,569 / 2,410 census + it also silently drops the $m\le5,n\le5$ family bounds VERIFIED_FACTS records), l.967–968 ("exhaustive tests on several thousand instances"), l.1201–1204 (10,691 / 6,065), l.1342 ("in exhaustive sampling"), l.1374/1377–81 (directed search / directed hunts), l.356/2447 ("every instance we tested"), plus "certified/exhaustive evaluation" phrases inside prop:refute (l.1360, 1366).

Needs your decision on scope (see D1): counts only vs. all enumeration-based evidence sentences vs. also the explicit witness tuples. Note the interaction: if all evidence sentences go, conj:43 and the "reopened conjecture" discussion lose their stated support and must be reworded to bare conjecture statements.

## 3. Directive: things with no conclusion omitted

Candidates, in decreasing order of confidence that you mean them:
- §4.5 RL cut-selection prototype (l.2215–2271): built, never evaluated on the SSP; explicitly "gated". Companion paragraph in §6.2 (l.2483–2509) and mention in §7 (l.2614–18).
- §5.2 "provisional observations" (l.2377–2390) + the four commented-out placeholders (l.2392–98): §5.2 itself says nothing can be concluded.
- §4.3 fractional-Benders paragraph (l.1913–27) ends on "the question the re-run settles…" — no conclusion; could move to §7 as one line.
- §4.3 conflict-graph bound (l.1946–62): kept "because it is exactly the lever the structural analysis predicts", no measured effect.
- rem:bdep (l.1405–14) and the open-question tail of prop:refute discussion: open problems — arguably legitimate content for a theory section / §7.
- §6.2 "Beyond the project horizon" (three paragraphs): future work; conventional to keep in an internship report.
Needs your selection (D2).

## 4. Directive: uniform terminology and conventions

Proposed canonical-terms table (to approve/amend before the mechanical pass):

| Concept | Current variants (count) | Proposed canonical |
|---|---|---|
| the heuristic | two-phase (14), group-then-sequence (5), grouping-then-sequencing (1), decomposition heuristic (1), standard heuristic (2) | "the two-phase heuristic" after one defining sentence |
| job group | group (body), batch (abstract, 4) | group |
| cost convention | empty-start default in §1–2 (ring: 6/7), free-initial default in §3 (ring: 3/4), mixed in figures | one global default (suggest free-initial for all theory statements; empty-start only in Def. 2.1 + §5 metric), every displayed number tagged once |
| heuristic value symbols | $H$ (two conflicting definitions, E6), $H_{\text{walk}}$ | $H$ = KTNS-evaluated, $H_{\text{walk}}$ = walk value, defined once each |
| tool-count symbol | $m$ (defined l.402, used ~4×), $|T|$ (11×) | pick one ($|T|$ suggested; then delete $m$) |
| baselines | F4 (5) vs CATZ-F4 (2); LSS, SSPMF never expanded | expand LSS/SSPMF at first use; one form each thereafter ("F4") |
| Benders cut families | Benders optimality cuts / LP-dual cuts / LP-dual strategies; combinatorial KTNS cuts / comb-cut | "LP-dual cuts" and "combinatorial KTNS cuts", fixed at first use |
| campaign | campaign / benchmark / computational study / uniform-protocol campaign | "the campaign" after one definition in §5.1 |
| setup-cost term | changeover (l.359, 1578) vs configuration change | configuration change |
| GSP | "Group Sequencing Problem" named once (l.558), never used again | either use GSP consistently or unname it |
| symbol collisions | $\rho$ (setup ratio §3.6) vs $\rho_t^k$ (PCF′ pricing rewards); $\gamma$ (grouping cost) vs $\gamma_k$ (duals of (G)); $\pi$ (permutation) vs $\pi_j$ (duals); $\theta$ (Benders) vs $\theta$ (RL policy) | rename the §4.4 duals and the RL parameter vector |
| result status in §3 | Theorem/Prop-with-proof yet "stated as a conjecture" (E7) | one scheme per D3 |

## 5. Directive: fewer adjectives, more precision

Quantified tics: "exactly" ×66, "precisely" ×12, "deliberately" ×5, "worth (stating/having/naming)" ×4, "The intuition is that…" ×3, plus one-off rhetoric: "machine time is money" (l.246), "folklore that has never been checked" (l.249), "The manoeuvre is worth stating without notation" (l.1788), "astronomically many" (l.2130), "That last fact is the ceiling … climbed to the coverage bound and stopped" (l.799–804), "and this is the useful part" (l.1159), "The integrality is the whole of the difficulty" (l.1727), "the decisive contrast" (l.1801), "is telling" (l.2409), "not decorative" (l.2118), "single act of foresight" (l.537). The "…, in words / in brief / What X does" primer paragraphs (l.1718–1750, 1787–1801, 1994–2012, 2128–2144) are a stylistic choice: they add ~2 pp of tutorial prose. Trim level needs your call (D4); a full flatten should return roughly 5–7 pp of the current 57.

## 6. Directive: deep line-by-line verification — proposed method

Two tracks, both producing artifacts you can inspect:

**(i) Mathematical replay.** Every definition, statement and proof re-derived step-by-step, section by section, with a written check-log (claim → derivation → verdict / issue). First pass done for §2–§3 core and the §4 formulations (results above: E1–E7 found, 24 checks passed); remaining: appendix proofs in full detail, §4 dual accounting line-by-line, all figure/table captions vs. body.

**(ii) Independent computational re-verification, runnable here (no CPLEX needed).** A standalone brute-force verifier (pure Python + an LP via SciPy/HiGHS for the PTF value) recomputing every small-instance claim in the report from scratch: rings k=3..8 in both frames, unbounded family g=1..4, W1/W2 (walk and KTNS values), $I_0/I_1$, the $K^*=4$ witness, star, non-matroid, MTZ counterexample, sliding-window ring, zero-gap classes on random samples, PCF/PTF LP values on the 6-ring and the 2.10 witness. Deliverable: a script committed to `verification/` whose output lists each report claim with PASS/FAIL — independent of the earlier `verify_*` scripts. Campaign-scale numbers stay out of the report until the new-protocol run merges; then they enter only via a `verify_everything.py`-gated recomputation (per your RESEARCH_PLAN TODO).

---

## 7. Proposed procedure

- **Pass 0 (you):** answer D1–D4 below; approve/amend the terms table (§4).
- **Pass 1 — correctness:** fix E1–E11 (errors, frame qualifiers, stale July text, one status scheme). Diff for your review.
- **Pass 2 — terminology:** apply the approved table mechanically; grep-audit afterwards. Diff.
- **Pass 3 — style:** adjective/rhetoric trim at the agreed level, section by section (§3 last, since it is under your proof verification). Diff per section batch.
- **Pass 4 — omissions:** enumeration mentions (per D1) and no-conclusion items (per D2). Diff.
- **Pass 5 — verification:** tracks (i) and (ii) above; check-log + verifier script delivered.
- **Pass 6 — closure:** rebuild both draft-switch versions, page/log check, final consolidated diff.

Token economy: passes 1–2–4 are cheap (surgical edits). Pass 5(i) is the heavy one — recommend it as a separate focused session (or a subagent run with the check-log as its only deliverable) so this session's context stays lean. Pass 5(ii) is cheap and durable (script re-runs anytime). Recommend adding the approved conventions table to CLAUDE.md (or a `skills/report-conventions` note) so any future session inherits it instead of re-deriving.

## 8. Decisions needed

- **D1 — enumeration scope:** (a) remove counts, keep qualitative "verified by exhaustive check" phrases; (b) remove all enumeration-evidence sentences; (c) additionally remove explicit witness tuples. Also: keep or drop the benchmark-size count (1,421/E9)?
- **D2 — omissions:** which of §3's open-question remarks, §4.5 RL, §5.2 provisional observations, §4.3 open-ended paragraphs, §6.2 horizon paragraphs go?
- **D3 — status scheme for §3:** (a) demote unverified results to Conjecture environments with "supporting argument" in place of Proof; (b) keep Theorem/Proposition but add a uniform marker (e.g. †) + one status sentence, applied identically in abstract/§3/§6.1; (c) leave labels, rely on the circulation switch.
- **D4 — trim level:** light (kill tics and one-off rhetoric only) vs. full (also compress the tutorial primer paragraphs).
