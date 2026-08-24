# The new report: structure, style contract, and what I need from you

## 1. What kind of document this is

A research internship report for the university: **comprehensive** (it records everything done over the internship), **technically rigorous** (every claim carries its status and its evidence), **written in plain English** (short sentences, no metaphor standing in for a technical term), and **in your voice**.

Three principles decide every editorial question:

1. **Every claim states what kind of claim it is** — proved, verified computationally, observed on data, conjectured, or cited. A reader should never have to guess.
2. **Every number states where it came from** — which instance family, which parameter range, which script, which paper's table.
3. **Nothing is described as more than it is.** Work that was done but produced no conclusion is reported as work that was done.

---

## 2. Proposed structure

### Front matter
- Title page *(exists, keep)*
- Acknowledgements
- Abstract — English **(decided: English only, no French résumé)**
- Contents
- **Notation and conventions table** *(new)* — every symbol, defined once, in one place. This is where the terminology problem gets solved structurally rather than by discipline.

### 1. Introduction
- 1.1 The industrial problem: a machine, a limited magazine, jobs that need tools
- 1.2 The internship: the lab, the advisors, the objectives as they were set
- 1.3 What was done, and what this report claims
- 1.4 How to read this report

*Job of this chapter: a reader who stops here can state your problem and your contribution correctly. No argument, no thesis-selling.*

### 2. The problem and the tools used to attack it
- 2.1 The Job Sequencing and Tool Switching Problem: definition and notation
- 2.2 Loading tools for a fixed order: the KTNS rule
- 2.3 The Job Grouping Problem and the two-phase heuristic
- **2.4 Two ways to measure the heuristic** *(new, and the structural fix)* — the walk value $H_{\text{walk}}$ versus the value $H$ the method actually returns after its KTNS step, with the instance where they differ
- 2.5 Configurations, clusters, and the generalised-TSP view
- 2.6 Two lower bounds: grouping and coverage
- 2.7 Cost conventions and how to convert between them
- 2.8 Background on integer programming **(decided: keep and expand)** — integer linear programs and what makes them hard; the linear relaxation and the integrality gap; branch-and-bound; cutting planes and branch-and-cut; linear-programming duality and what the dual prices mean; Benders decomposition, with the logic-based and combinatorial variants; column generation, pricing, and branch-and-price. Each with a small worked example on an SSP instance rather than a generic one.

*Expanded per your choice. This section does double duty: it makes the report self-contained for a jury member outside combinatorial optimisation, and it is the section you revise from before the defence. Worked examples are on SSP instances so that studying it is also studying your own problem.*

### 3. State of the art
- 3.1 Origins: KTNS, and why the ordering is hard
- 3.2 The compact-formulation ladder: Laporte → Catanzaro → da Silva, and where it stops
- 3.3 The configuration view: set covering, branch-and-price, and the group's own work
- 3.4 Heuristics and metaheuristics
- 3.5 The decomposition in industrial practice
- 3.6 Recent exact developments
- 3.7 Benders decomposition: the methodology this work borrows
- 3.8 What is open, and which of those openings this internship attacks
- Table: the exact-method lineage

*Rewritten from the sources. Every claim will be what the paper says, with the paper's own qualifications.*

### 4. How far can the two-phase heuristic be from optimal?
- 4.1 The two frames, and why the distinction matters
- 4.2 The gap is exactly the price of using the fewest groups
- 4.3 Instances where the gap is zero, and worst-case guarantees for every instance
- 4.4 The extremal analysis at $K^*=3$
- **4.5 When does the KTNS step close the walk gap?** *(new)* — the ring family, the census, the open question
- 4.6 What the gap does not depend on: independence systems, clutters, matroids
- 4.7 The setup-cost spectrum: from the SSP to the JGP
- 4.8 Which grouping to choose — an open algorithmic question

### 5. Exact methods
- 5.1 Compact baselines and the coverage ceiling
- 5.2 A branch-and-Benders-cut algorithm
- 5.3 Strengthening it: four accelerations
- 5.4 Position-indexed formulations: PCF, PCF′, PTF
- 5.5 Pricing and branch-and-price
- 5.6 A learned cut-selection prototype

### 6. Computational study
- 6.1 Instances, protocol, hardware
- 6.2 Validation: how correctness was established before any result was recorded
- 6.3 Compact baselines
- 6.4 Branch-and-Benders-cut, and the acceleration ablation
- 6.5 Branch-and-price
- 6.6 How tight is the coverage bound across the standard suites?
- 6.7 What the campaign establishes

### 7. Discussion
- 7.1 Bound-limited or implementation-limited?
- 7.2 Where the theory and the measurements agree
- 7.3 Limitations and threats to validity

### 8. Conclusions and further work

### 9. Declaration on the use of AI tools

### Appendices
- **A. Proofs**
- **B. How every claim in this report was checked** *(new)* — the independent verifier, what it covers, how to run it. This is what makes the AI declaration credible instead of merely present.
- **C. Reproducibility** — repository layout, how to re-run the campaign
- **D. Full result tables**

---

## 3. Why this structure differs from the current one

| Change | Reason |
|---|---|
| Notation table added | Fixes the terminology drift structurally instead of by vigilance |
| §2.4 added (the two frames) | The single highest-value correction; everything in Chapter 4 depends on it |
| Related work becomes its own chapter | It was a subsection carrying nine of the sixteen source problems; it deserves the room to be accurate |
| §4.5 added | New result from the audit, and the most interesting thing in the chapter |
| Discussion separated from Conclusions | Lets the interpretation be argued explicitly and challenged, instead of being smuggled into descriptive sections |
| Verification appendix added | Turns "I checked everything" from an assertion into something a reader can run |
| Introduction rewritten to inform, not persuade | The current one argues a thesis before earning it |

---

## 3b. Style profile, from Shankar's own writing

Derived from his emails to Wagler, Colares and Chicoisne. These are the habits the report should keep.

- **Plain vocabulary, no figurative language.** His own writing contains no metaphors at all. The current report is full of them. His emails are already closer to the target register than the report is.
- **Motivation stated inline, after the fact**, using *since* or *as*: "I implemented a Golang program … since Porta became very slow even for small instances."
- **Parenthetical clarification** rather than a second sentence: "(current loose bound: number of configurations × (number of optimal groups − 1))".
- **Explicit enumeration** when listing directions: "First … Second … Thirdly …".
- **Status stated honestly and without hedging language**: "implementation almost complete", "I have not yet worked on the Tool Setup Time Variant, as I was occupied with the previous questions".
- **Connective openers**: "Based on this", "Following discussions with", "As a natural next step".
- Sentences are moderate in length but built from short clauses joined by *and* or a comma. In the report these become separate sentences, which is what he has asked for.

Stated preferences to hold to: short sentences; simple English; formal rather than casual; **explain in great detail, assuming a reader who knows nothing** (his advisors do not know what he has done either); direct; examples wherever possible; and illustrations — figures and tables — used generously.

The last two points change the plan: figures and worked examples are not decoration in this report, they are a requirement. Every non-obvious definition gets an example, and every mechanism that can be drawn, is drawn.

## 4. Style contract

Hold me to these. If a draft breaks one, say so and I will fix it rather than defend it.

**Sentences.** Short. One idea each. If a sentence needs a dash to hold two thoughts together, it is two sentences.

**Terms.** Every technical term defined at first use, in the notation table, and used identically thereafter. No synonyms for defined objects — the heuristic has one name, the campaign has one name, a relaxation *value* is never a relaxation that "collapses" or "goes slack".

**No metaphor for technical content.** "The relaxation value equals $|U|-b$", not "the literature climbed to the coverage bound and stopped".

**Claim status is explicit.** Theorem, Proposition, Lemma for proved statements. Conjecture for statements supported by computation. "We observed" for data. "X et al. report" for the literature.

**Numbers carry provenance,** in the sentence or in an immediate reference.

**No self-assessment adjectives.** Not "striking", "powerful", "elegant", "remarkable". If a result is important, the reader will see it from what it says.

**Voice — DECIDED: impersonal reporting register. No "I", no "we".** This is a clean and defensible choice, and it is what the current draft half-does already. It resolves into two consistent modes:

- *Narrative and experimental reporting* uses the passive or an impersonal subject: "A branch-and-Benders-cut solver was implemented", "The campaign was run on the LIMOS cluster", "Three compact formulations from the literature serve as baselines."
- *Mathematical development* uses the standard impersonal constructions of the field: "Proposition 4.2 shows", "It follows that", "The proof proceeds by two constructions", "Restricting to full magazines loses no optimality."

One consequence to handle deliberately: an impersonal register hides who did what. Since a jury will want to know exactly that, §1.3 becomes an explicit statement of what was carried out during the internship, and the AI declaration in Chapter 9 carries the rest. Those two places are where authorship is made concrete; everywhere else the prose stays impersonal.

A second consequence: passive voice invites vagueness ("it was observed that…"). The rule that prevents this is the claim-status rule above — every sentence still names what kind of claim it is and where the evidence sits, so nothing hides behind the passive.

**Spelling.** British, as the current draft has it (minimise, behaviour). Say if you prefer otherwise.

**Figures.** Every figure earns its place by showing something the text cannot say compactly. Each gets a caption that states what to look at and what to conclude — not a re-telling of the body text. I will propose keep/redraw/cut for each of the existing ones.

---

## 5. What I need from you

Answer what you can; anything you leave out, I will flag as an assumption rather than guess silently.

**A. University requirements.** *(Partly settled: English only, existing cover page retained.)* Still open: page limits, a report deadline separate from the 2 September presentation, any departmental template or mandated section order.

**B. Writing samples — still the most important item.** Two or three things you wrote yourself: an email to your advisors, notes, an earlier report or assignment, anything in your own English.

Note the tension you have created, and how it resolves. An impersonal reporting register deliberately removes the most obvious markers of a personal voice. What remains, and what samples let me calibrate, is: how long your sentences run; how much you explain before stating a result; how direct you are; whether you prefer a worked example or a general statement first; which words you reach for. Those are real and they are yours. Without samples I default to plain technical prose — correct, but it will read as anyone's.

**C. The internship framing.** Official title, dates, and the objectives as they were actually set — what did Colares, Wagler and Chicoisne ask you to do at the start, and did that change?

**D. Your account of the work.** Which ideas were yours, which came from the advisors, which came from the AI. What you implemented, derived, or debugged yourself. This matters for two reasons: the contribution statement has to be accurate, and it tells me which parts you can defend without preparation.

**E. The six open items** in `SESSION_STATE.md` — the ρ source, F5, the Colares citation, the Moreira attribution, "I" or "we", and which figures to keep.

**F. Anything the advisors have already said about the current draft** — comments, corrections, things they liked or objected to.

---

## 6. Order of writing

1. **Chapter 2 (Preliminaries) and the notation table** — first, because every other chapter inherits its vocabulary. Nothing can be written consistently until this is fixed.
2. **Chapter 4 (the gap theory)** — the corrected frame, the repaired unboundedness result, the new §4.5.
3. **Chapter 6 (computational study)** — the campaign data is landing now and has real conclusions.
4. **Chapter 3 (state of the art)** — rewritten from the sources.
5. **Chapter 5 (exact methods)** — mostly correction, since the code corroborates it.
6. **Chapters 1, 7, 8 and the abstract** — last, because they summarise everything above.
7. **Appendices B and C** — the verification and reproducibility material.

Each chapter arrives as a draft you read before the next one starts. If the voice is wrong in Chapter 2, we fix it there and every later chapter inherits the fix.

I will update `SESSION_STATE.md` after each chapter so a fresh session can resume by reading one file.
