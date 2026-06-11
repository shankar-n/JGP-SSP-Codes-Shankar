# Consolidated Work Plan (2026-06-10, Claude-Fable; for Shankar's revision)

Single source of truth for what remains. Ordered within sections by priority.
[S] = Shankar must do / decide; [C] = Claude session task; [S+C] = joint.

---

## A. Part X completion: pricing + column generation (TOP, Shankar's priority)

A1. [C] **Formal dual derivation for PCF.** Duals mu_k (P_k), pi_j (C_j),
    sigma_tk (W_tk), tau_t (T_t). Derive reduced cost of y_C^k EXACTLY
    (the sign bookkeeping of sigma across W_{t,k} and W_{t,k+1} is the flagged
    TODO in Part X — resolve it first, it determines the pricing objective).
    Deliverable: new Part X subsection "Pricing for PCF" with the LP dual,
    reduced-cost lemma, and proof.
A2. [C] **PCF pricing problem.** Per position k: choose C (b tools) maximising
    tool-score(sigma,tau,k) + coverage bonuses pi_j [T_j subset C] minus mu_k —
    a set-union-knapsack (same class as JGP pricing; reuse SUKP machinery from
    Part II / Felipe line). Note: price all k jointly (scores differ only via
    sigma). Deliverable: MILP formulation + greedy heuristic + exact fallback.
A3. [C] **PTF pricing problem.** Columns are pairs (C,C') per step: quadratic
    set-selection with cost d(C,C') and dual rewards on head/tail/insertions.
    Harder; design exact MILP (2b binary tool vars + linking) + heuristic.
A4. [C] **CG/B&P algorithm spec**: RMP seeding (columns from KTNS trajectories
    of greedy_ffd / warmstart_from_jgp / nearest_neighbor); degenerate-dual
    stabilisation (the n step rows are near-identical — dual smoothing or
    boxstep); branching rule design (branch on a_t^k aggregates or job-position
    assignment — NOT on single y columns); symmetry breaking (reversal anchor +
    SSPMF-style position fix) BEFORE any benchmark.
A5. [S+C] **Prototype**: posform_cg.py (CPLEX-CE-compatible sizes first;
    validate root bounds vs verify_posform*.py; then full CPLEX). Battery:
    OP-X1 root-bound study PTF vs PCF+T vs LSS(+ineqs) vs fixed-SSPMF on a
    Tabela1C subset. (Catanzaro F3/F4 are NOT implemented — decide [S] whether
    to implement for the comparison or cite paper values with convention care.)

## B. Verification backlog

B1. [S] TODO_VERIFY_INDEX.md pass (priorities in header). Highest value:
    Part IV per-config MTZ proof + lem:parasitic; Part V cost identity /
    thm:uncond / grouping-exactness repair; Part X both exactness proofs
    (PTF ">=" direction subtlety flagged); BBC AUDIT-FIX diffs; SSPMF c21 fix.
B2. [S] Local pdflatex sweep 01–10 (sandbox verified only 04, 05, 08 + the
    pre-rewrite 10; 07 needed the warnbox fix — confirm it compiles now).
B3. [S] On full CPLEX: re-run test_solver.py; random cross-check battery
    BBC vs LSS vs fixed-SSPMF ([C] writes the script next session — extend
    test_solver with ~50 random small instances, all three solvers, assert
    agreement; this is the regression net the repo lacked).
B4. [C] Obtain+read the C&OR-2018 3/2-ratio paper ([S] downloads PDF into
    references/): what bound is the ratio against? sound? convention?
    Reconcile with Part V ratio theory.
B5. [S] Advisor: Colares overlap (Parts II/III/X scope), 3/2 paper,
    serving-angle go/no-go.

## C. Open problems to attack (ordered by value/feasibility)

C1. OP11, K*=3 case: gap <= 1 for ALL b. Timebox 2 weeks. Attack sketch:
    cost identity (gap = excess re-insertions) + pairwise unmergeability;
    show some JGP-optimal grouping admits an order where at most one bridge
    tool is lost; start from the verified structure of positive-gap instances
    (ring/prism, |U|=6) and the b=4/b=5 witnesses. Counterexample search at
    b>=6 in parallel (extend verify_ratio_section.py).
C2. OP-X1: characterise/measure the PTF LP bound (needs A5 data first).
C3. OP1 route (prop:43route): extend the "positive gap => K*=3 and Z>=3"
    check beyond the edge family computationally; if it survives ~50k mixed
    instances, attempt proof; combined with C1 this yields the b=3 4/3 theorem.
C4. OP-X2: PORTA facet runs for PCF/PTF on b=3,|T|<=6 (tooling exists in repo).
C5. (stretch) OP-X4 ordering-certificate lower bound; OP9 general-f collapse.

## D. Code: change / verify / refactor

D1. DONE 2026-06-10 (re-verify on full CPLEX [S]): BBC depot-dual cut fix;
    dual_bound API fix; SSPMF c21 fix (default flipped); NN infinite loop;
    raw_results.csv archived.
D2. [C] Regression battery script (see B3). HIGH — the repo had no
    cross-solver random testing, which is how SSPMF stayed broken.
D3. [C] posform_cg.py implementation (A5).
D4. [S] Cluster runs AFTER B3 passes: precompute_jgp_gsp; benchmark_runner
    (verify benchmark_config grid: no config may set use_constraint_21=True).
D5. Refactors (LOW, batch later): thread_up builds DSP even when
    worker_lp_reuse=False (waste); convergence_log "dual" label misleading;
    convention helper util (empty<->free shift) used by analysis scripts;
    stale dispatcher docstring; smoke-test instance path.

## E. Writing

E1. Midway report: assemble AFTER B1-B3 + first benchmark data. Skeleton:
    problem + verified foundations (01-03) -> formulations (04, X) -> gap
    theory (05-07) -> solver + corrected benchmarks (08, D4) -> open problems
    (09) -> plan. The verification campaign itself (bugs found, conventions
    unified) is honest "work done" content.
E2. Research-directions discussion (11_research_directions.md v2 + lit-dive
    results) -> advisor meeting before committing.

## Suggested order of Claude sessions
1. A1+A2 (PCF dual derivation + pricing, written & verified) + D2 script.
2. A3+A4 (PTF pricing + CG spec); B4 if PDF available.
3. D3 prototype + A5 small-scale study.
4. C1 proof attempt session(s), informed by A5 structure.
5. E1 report assembly (after Shankar's B1-B3 + D4 data).
