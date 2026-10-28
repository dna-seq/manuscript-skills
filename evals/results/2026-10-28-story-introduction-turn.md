# A turn in the Introduction that a full run let through: before and after 0.38.0

Date: 28 October 2026. Skills: manuscript-story as of 0.35.0 (commit 07952a3, unchanged through 0.37.0;
"before") and at 0.38.0 (this release, "after"). Model: Claude Opus 5.5 for every agent, each a fresh Claude
Code subagent in its own folder outside both repositories. Grader: the session that wrote the change, against
the rubric of `story-introduction-turn-seeded` in [manuscript-story.yaml](../manuscript-story.yaml); this is
not a blind evaluation.

## The case

Paper 1 v0.6 (Just-DNA-Lite). The Introduction's first three paragraphs argue about personal-genome
annotation in general and the third ends on the Table S7 comparison of 23 tools. The fourth opens "Recent
progress in the genetics of longevity illustrates the need for such extensible annotation tools." Nothing
says why longevity; the reason, Generation I being built around longevity, is in Section 3 only, and "such
extensible" points back at nothing. In v0.2 and v0.3 the third paragraph ended on "ease of use,
transparency, and extensibility"; a revision replaced that sentence. The manuscript-improve run of
2026-10-27 flagged none of this: its three readers reported no stumble there, and its story stage marked
*Connected sentences* as holding ("The Introduction's second paragraph now opens on direct-to-consumer
sequencing, which follows from the consumers of the first").

## What was run

- **Readers**: the informed-outsider seat on the reading copy that run's readers read (paper, supplement and
  figures), with the run's own brief (before) and the brief 0.38.0's reader panel gives (after: the "why is
  this here" stumble and the instruction to note a paragraph whose topic could not be predicted). Two each.
- **Story tests**: the skill folder (SKILL.md and references, before or after), the same reading copy, and
  v0.2 (the earliest version the project holds) and v0.5 (the previous one); a reader review with the story
  entry, drift and every story test that does not need the panel. Two each.
- **The eval case** staged by `evals/stage.py`: the seeded fixture with the old and the new skill, and the
  clean control with the new skill. One each.

The answers and briefs are kept with the authors' session notes, not in this repository: they quote the
draft at length.

## Results

| Arm | Runs | Turn to longevity reported as unexplained | "such" with no referent | Section 3's reason brought forward | Broken link traced to the first draft |
|---|---|---|---|---|---|
| The 2026-10-27 run (0.35.0): three readers and the story stage | 4 | 0 | 0 | 0 | 0 |
| Readers, before | 2 | 0 | 0 | 0 | — |
| Readers, after | 2 | 0 | 0 | 0 | — |
| Story tests, before | 2 | 0 | 0 | 0 | 0 |
| Story tests, after | 2 | 2 (findings 1 of 21 and 2 of 17) | 2 | 2 | 2 |
| Eval case, seeded, before | 1 | 0 | in one test note only | 0 | 0 (called the lost sentence "the biggest improvement") |
| Eval case, seeded, after | 1 | 1 (the report's main problem) | 1 | 1 | 1 |
| Eval case, clean control, after | 1 | 0 ("The turn to longevity now holds") | 0 | — | — |

- **Story tests separate the versions.** Both runs before looked at the fourth paragraph and missed the
  defect: each said its first sentence promises a need the heritability sentence does not show, and proposed
  reordering the paragraph or adding a fact from Section 3.1. Both runs after failed *Connected paragraphs* on it, quoted the paragraph's
  end and the opening, asked why longevity and which tools "such" means, quoted "That system was built around
  longevity", and found v0.2's "extensibility" ending. Both filled the story entry's new `origin` with
  Generation I. Neither supplied a reason the paper does not give.
- **The eval case separates them too, and the control holds.** Seeded with the new skill passes every rubric
  item; with the old skill it fails three of the four about the turn, and its one hit is a clause in a test
  note. The clean control raised no false alarm on the turn.
- **Readers do not.** The new category was used (four and five times per reader, against none before), on
  the sequencing-cost paragraph by both readers and on later sections, but no reader stopped at the turn to
  longevity. The Abstract names longevity modules, so a reader expects the topic and does not ask why the
  Introduction turns to it. One reader said the clearest reason "why longevity and disease modules sit
  together" was Figure S1, in the supplement. The reader panel now says that the readers' silence is not a
  pass and that the story test reads every paragraph break.

## Limits

One paper, one defect, and one model family. The grader wrote the change. The story-test arms ran without the
reading-measures script or a reader panel, as a narrowed stage, and with the earliest version supplied; a full
manuscript-improve run still has to find the earliest version itself. No `claude plugin eval` run yet.
