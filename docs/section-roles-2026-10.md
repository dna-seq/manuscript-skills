# Section roles: why detail drifted into the Introduction, and the check that stops it (October 2026)

## What happened

On 28 October 2026 the authors of Just-DNA-Lite's Paper 1 (v0.6) found that the first item of the
Introduction's Key features list, "A cleaned PGS Catalog, ready to use", presented the just-prs scoring
engine as a tidied copy of the PGS Catalog, and that the item and its neighbours carried detail whose place
is elsewhere:

- Methods detail in the Introduction: a Parquet mirror, normalized genome-build labels, performance metrics
  parsed into numbers.
- Results in the Introduction: 860 scores withheld, 847 of them for failing a scale check; the registry's
  count on 26 October 2026; annotation in 33 to 65 s, 128 to 231 times faster, a median of 0.08 s per score; a
  comparison with PLINK2 whose fairness depends on thread counts stated in the same item.
- Results in Methods: the file-level audit's counts (6,910 of 6,991 files) and the reference-distribution
  audit's counts (6,117 of 6,977 passed) in Section 3.2, and the ancestry classifier's leave-one-out accuracy
  (99.65%) at the end of Section 3.2.2.
- Methods detail in the Abstract: each score "passes its reference-distribution audit".

They repaired it by hand (just-dna-lite commit bc27fe5; the reasons for each move are in
`docs/manuscript/v0.6/changes-from-v0.5.md`, section 5 of that repository): the feature now says what just-prs
adds to the Catalog's models, Section 3.2 states the audits as rules and points to the counts, and new Sections
4.3 and 4.4 hold the counts and the accuracy. No number changed and no caveat was dropped. The rule they stated:
the Introduction says what a contribution does and why it matters, with at most a rounded figure and a pointer;
Methods hold procedure, data preparation, thresholds and rules; Results hold measured outcomes beside the
configuration that makes them fair; the Discussion interprets, compares and bounds.

## How the plugin let it through

The detail arrived through the plugin's own rounds. The record of v0.6 says an interim Abstract "that listed
four features with their numbers was replaced; the numbers stay in the Key features list (F1) and the body":
the numbers left the Abstract for the Introduction rather than for Results. Nothing in the plugin said where a
detail belongs, and several rules pushed the other way:

- manuscript-story's edits that keep the direction include "a stake or hook ... built from facts the paper
  already has" and "one number the reader keeps", with no word on which section the fact comes from or how
  much of it travels. A story stage asked to make an opening concrete reaches for the measured facts.
- manuscript-prose-edit's section guide said what each section needs, but not what it must not hold, and had
  no entry for a feature or contribution list.
- The claim guard protects every number and caveat wherever it stands, so a count copied into the
  Introduction passes, and so does a sentence moved word for word from Results into Methods.
- manuscript-improve's re-check runs the number and reference checks again on the corrected version; neither
  looks at sections.
- No finding category fitted: the nearest were *Story and structure* and *Writing and clarity*, so a reviewer
  that noticed a result in Methods had nowhere obvious to put it.

## What changed (release 0.40.0)

- **One shared rule**: `skills/manuscript-integrity-check/references/section-roles.md` says what each section
  holds and does not hold, what a rounded figure is, how a contribution is framed (by what it adds to its data
  source, never as a cleaned copy), how the roles map onto IMRaD, methods-last layouts (Cell Press STAR
  Methods and others), software and resource papers and structured abstracts, and how to move a detail
  without losing a number or a caveat. Every skill links to it instead of restating it.
- **A finding kind**: *Misplaced detail*, in the shared category list, with its directions, severity, stage
  and the rule that moving a detail is not an author decision.
- **A check**: `skills/manuscript-integrity-check/scripts/section_roles.py` lists candidate passages per
  section, and with `--before` exits 1 when an edit made a passage a candidate.
- **Where it is used**: integrity-check runs it in Step 5 and reads the candidates; prose-edit's contract and
  section guide forbid "making it concrete" with measured detail; story keeps each detail in its section and
  runs the check in its science gate; journal-adapt maps a paper's headings to roles before it restructures
  for a venue; peer-review's claims and reproducibility seats ask where results and procedures sit, and its
  findings map to the new category; manuscript-improve's verify stage runs `section_roles.py FINAL --before
  ORIGINAL`, and `recheck.py numbers` carries the same candidates as a third check beside numbers and
  references, so an edit that brings detail forward exits 3 like one that introduces a number error.
- **The classifier** of section kinds is reader_metrics.py's, shared with manuscript-story; it now also
  reads "Use cases", "Usage examples" and "Database content" as Results.

## How the check was calibrated

The check looks for measurements (counts out of totals, ranges and medians with units, decimal percentages,
past-tense outcomes such as "were withheld", dated counts of what a resource held, a metric with its value),
the configuration of a comparison (threads, a benchmark configuration) and procedure (preparation steps in
the passive, storage formats, a gate a result passes, analysis parameters). Three choices keep it quiet where
the detail is in its place:

- A number governed by a comparator ("at least four of the seven", "10% or more") is a rule, not a
  measurement. Data versions and the size of a method's input stay in Methods.
- Outside Methods, a sentence that cites other work is background. In Methods a cited source is often the data
  the procedure ran on, so the file-level audit's sentence, which cites the PGS Catalog, is still read.
- The Abstract gives the main results with their numbers and setup. It is listed only for procedure, the
  bookkeeping of a filter or an audit, or a sentence of three or more measurements.

Measured on Paper 1 v0.6: the version before bc27fe5 gives 12 candidates, each a passage the authors moved
(one sentence of the first Key feature is listed both as Methods and as Results detail); the repaired version
gives none. On the other 38 manuscript files among the plugin's evaluation fixtures it lists one passage, in
both versions of one fixture: a genotyping exclusion count in Methods ("31 were excluded for a call rate below
97%"), which STROBE would report in Results. Before the Abstract rule was relaxed it also listed an Abstract
that gives a laptop's cores beside a timing, in two files. A candidate is a passage to read, never a finding;
the skill that runs the check decides.

`--before` compares candidates, a passage with its direction, not text. The accuracy sentence of Section 3.2.2
moved word for word to Section 4.4; comparing text alone would have missed a move in the wrong direction.

## Tests and the evaluation case

- `tests/test_section_roles.py` uses the before and after versions as ground truth: every passage the authors
  moved is listed with its direction, the repaired version lists nothing, the edit that brought the detail
  forward is caught by `--before` and by `recheck.py`, and the rules, input sizes, data versions, rounded
  figures, cited background and plans are left alone.
- `evals/manuscript-integrity-check.yaml` has a paired case, `integrity-section-roles-seeded` and
  `integrity-section-roles-clean`, on the two versions trimmed to the Abstract, the Introduction's overview
  and Key features, Section 3.2 with 3.2.2, the opening of Section 4 and the Conclusion. Its first run
  ([evals/results/2026-10-28-integrity-section-roles.md](../evals/results/2026-10-28-integrity-section-roles.md))
  passed the seeded case with the new skill (8 of 8 rubric items) where the skill before it and no skill held 3;
  the clean control reported three passages the authors had left on purpose, two of them gaps in this
  reference.

## Limits

- The check reads words, not meaning. A measurement written in words ("about half of the scores failed"), a
  result in a table or a figure, and procedure without a preparation verb are not listed. Framing (a tool
  presented as its data) is the reading's to find: no pattern tells a cleaned copy from an engine.
- Section kinds come from headings. A paper whose headings name neither a role nor a parent with one (a
  section called "The registry") is read as "other" and not checked.
- A Conclusion repeats results by design and is checked only for numbers no Methods or Results section has.
