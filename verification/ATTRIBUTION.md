# Who contributed what — source material for §1.3 and Chapter 9

Recorded 2026-08-20 from Shankar's own account and his email record. This feeds two places in the report: the statement of work in §1.3, and the declaration on AI use in Chapter 9. It is also the map of what he can defend without preparation.

## Research directions — set by the advisors

| Direction | Origin | Evidence |
|---|---|---|
| **The configuration-based approach as the project's frame** | Colares and Wagler | "a novel magazine 'configurations' based approach proposed by Prof. Colares and Prof. Wagler" (email to Chicoisne) |
| **The SSP ↔ GTSP reduction** | Colares | Shankar's account; email: "I embarked on proving an equivalence between two problems and establishing a full reduction" |
| **Branch-and-Benders-cut** | **Colares**, based on **Layth Kashou's internship report** | Shankar's account. Confirms why `Kashou2025` is the report's "immediate template" — it is the actual origin, not a post-hoc literature parallel. `references/Master_ROAD_2025_12.pdf` is Kashou's report. |
| **Position-based formulations** | **Colares** — the goal being branch-and-price over the configuration formulation | Shankar's account. **Needs one clarification:** the June working note credits Shankar with the specific device of a *fixed, polynomial row set* so that column generation only adds columns to existing rows. Colares proposed position-based formulations; who proposed the fixed-row-set refinement should be settled before §1.3 is written. |
| **Gap analysis (JGP+GSP versus SSP optimum)** | **Wagler** | Shankar's account; her emails direct the worst-case-example programme |
| **Blocker / clutter theory** | **Wagler** (more mathematically oriented) | Shankar's account |
| **PORTA enumeration of integral JGP solutions** | **Wagler**, explicitly requested | "as you suggested, I enumerated all integral solutions of the JGP using Porta" |
| **Worst-case examples at fixed $K^*$; instances where the gap is attained; a tighter upper bound than $b(K^*-1)$** | Wagler | His email to her lists these as her programme |
| **MTZ in place of GSECs, aiming at column generation** | Colares | "Following discussions with Prof. Colares … try a new formulation replacing GSECs with MTZ-style constraints" |
| **Lazy cuts first, user cuts second** | Colares | "Like you had suggested, I am planning on experimenting computationally the two pathways: Lazy cuts or User cuts" |

## Carried out by Shankar

- PORTA enumeration on the 6-ring; identifying that the SSP-optimal configurations differ from the JGP-optimal ones, and that copy-pasting tool-disjoint constructions grows the gap.
- A **Golang enumerator** for integral JGP solutions, written because PORTA was too slow beyond about eight jobs.
- **Modifying Felipe Otiai's instance generator** to produce smaller instances with greater tool overlap, in the regime $b \approx |T|/2$, $|T|\times|J| \le 60$ — a regime he chose himself from conjectures formed while studying the problem.
- Implementation of the branch-and-Benders-cut solver, the branch-and-price prototypes, the three reimplemented baselines, the campaign harness and the SLURM pipeline.
- Diagnosing that the tool-coverage bound was missing from the Benders master and re-running the campaign after adding it.
- Running the campaigns on the LIMOS cluster and the cross-solver agreement checking.

## AI-assisted

- **Most of the ideas in the gap-theory chapter** (the current §3) — Shankar's own statement. The *questions* are Wagler's; the specific propositions, proofs and constructions were developed with AI assistance.
- Drafting of the LaTeX documents and the report.
- The verification scripts under `plans-genai/_verification/`.

## Consequences for the report

1. **§1.3 must separate three things**: directions set by the advisors, work carried out, and results obtained with AI assistance. The current draft's Contributions list does none of this.
2. **`Kashou2025` should be introduced as the origin of the method, not as a parallel found in the literature.** The current §2.7 presents it as an independently discovered template. Saying that Colares proposed the approach after Kashou's internship is both true and stronger.
3. **The gap chapter is the one where Shankar's ownership is thinnest and the errors were densest.** Those two facts are related. It is also the chapter where the audit found real new results, which gives him something to own.
4. **The PORTA work is Wagler's request and Shankar's execution** — it deserves to be visible in the report rather than buried, since it is where the whole gap programme started.
