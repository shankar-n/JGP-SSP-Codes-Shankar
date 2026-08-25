# Your academic writing voice, measured from your own papers

**Built 2026-08-25** from `references/my_works/`. This replaces the earlier style profile,
which was derived from your emails to your advisors — a bad proxy for academic prose, and
material that was not yours alone to publish.

## What was usable

| file | usable? | why |
|---|---|---|
| `Toda_sadhana.pdf` | **yes** — 6,521 words | you are first author; full journal manuscript |
| `spcom_template.pdf` | **yes** — 3,711 words | you are first author; full conference paper |
| `Mastication…ALS…pdf` | no | a one-page **poster**, telegraphic bullets, and you are third of six authors with the corresponding address belonging to the first |

## How it was measured, and where the measurement is weak

Both papers are two-column. Plain `pdftotext` interleaves the columns, which fabricates
sentences by splicing halves of two real ones. My first pass did exactly that and produced
nonsense — "longest sentence, 69 words" turned out to be an author list glued to an
abstract. The numbers below come from cropping each column separately, de-hyphenating
line breaks, and dropping references, captions and table rows.

Two caveats that survive:

- SPCOM is clean. Sadhana's first page has a single-column abstract on a two-column
  page, so a few sentences there are still spliced. Its body is fine.
- Raw punctuation counts on the report side are inflated by LaTeX residue: `detex` leaves
  `ssec:disc-locality` and `\citet` remnants behind, and every one carries a colon. The
  raw count said the report uses colons twelve times more often than you do. Counting only
  *prose* colons — a clause, a colon, a lower-case continuation — gives 71 instances in
  21,900 words, which is 3.2 per thousand against your 1.9. A mild preference, not a tic.
  I am recording the corrected figure, not the raw one.

## The comparison

| | your papers | this report |
|---|---|---|
| mean sentence length | 25.1 words | 19.5 |
| median | 23 | 17 |
| standard deviation | 12.6 | 11.6 |
| sentences ≤ 10 words | **9%** (SPCOM: 3%) | **24%** |
| sentences ≥ 35 words | 19% | 10% |
| passive constructions / 1000 w | 16.4 | 10.2 |
| *we / our / us* / 1000 w | **4.9** | **0.0** |
| nominalisations / 1000 w | 29.9 | 47.3 |
| hedges / 1000 w | 2.0 | 1.7 |
| prose colons / 1000 w | 1.9 | 3.2 |

### The three differences that are real

**Short sentences.** You almost never write one. Three per cent of your SPCOM sentences
are ten words or shorter; the report is at twenty-four. It opens Section 1.2 with
"Loading is easy." and "Ordering is hard." — two sentences you would not have written.

**First person.** You use *we* about five times per thousand words. The report uses it
zero times in twenty-two thousand.

**Passive voice.** You use it about 60% more often than the report does.

### What is not a real difference

Hedging is nearly identical. Sentence-length variance is nearly identical — both texts
mix long and short, yours just centred higher. Nominalisation is *higher* in the report
than in your papers, which is the opposite of the usual complaint about generated prose.

## What to do about it

**Nothing, for two of the three.**

The first-person gap is a genre difference, not a style difference. Your papers have six
authors, where *we* is literal. This report has one. *We* in a single-author internship
report is either a royal we or a false plural, and every alternative — "the author",
"this study" — is worse. The impersonal register is correct here.

The short-sentence habit is the report's main readability asset, and it is doing real
work: it puts the load-bearing claims on their own line where a jury cannot miss them.
Rewriting toward your published rhythm would mean sentences like the SPCOM abstract's

> The proposed database is suited for a number of research studies including the effect of
> speaking rates on the acoustic and articulatory aspects of coarticulation in Toda,
> analysis of labial kinematics during consonant production at different speaking rates,
> and acoustic-articulatory analysis of front rounded vowel in Toda.

— forty-seven words, three stacked prepositional phrases. That is normal for the field and
it passed review, but it is not better writing, and it is not what a defence rewards.

**The one thing worth knowing** is that if an advisor who has read your speech-processing
papers reads this report, the prose will not sound like the same person. That is not a
problem to fix in the text; it is a thing to be able to say out loud if asked. The honest
answer is that you were writing to a different brief in a different field, and the
declaration in Section 9 already states that an AI assistant drafted and copy-edited the
prose. Those two facts together are a complete answer.

## For a future session

If you want drafts in your voice, the profile is: sentences centred around 23–25 words
with real variation, *we* where there are co-authors, comfortable with the passive,
prepositional stacking rather than subordination, references carried inline as bracketed
numerals mid-clause, and section openers that state the object of study before the claim
("Toda is an under-documented endangered Dravidian language spoken in…").
