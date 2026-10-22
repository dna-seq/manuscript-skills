---
name: manuscript-story
description: >-
  Make a manuscript more engaging while preserving its science, journal fit and the authors' chosen
  direction. Use when the paper is boring, harder to read after revisions, needs stronger
  storytelling, or should be compared with an earlier version. Run fresh skimmer, potential-user and
  informed-outsider readers; compare reading measures and relevant neighboring papers; edit
  openings, result headlines, real worked examples, caveat placement and the ending. Show
  consequential before/after passages and retain the readers' actual reports and disagreements.
  Propose changes of theme or audience as author decisions. Use manuscript-prose-edit for language-
  only editing and manuscript-peer-review for scientific referee simulation.
---

# Tell the paper's story to its readers

A paper is written for its readers; a referee is one of them. Rounds of revision aimed at referees add
caveats, defensive detail and benchmark tables until the paper is harder to read than its first draft,
and each addition is paid for by every later reader. This skill works for those readers. It reads the
paper as they do, says where they lose interest and why, and edits the story so they keep reading,
while the science, the journal's requirements and the authors' chosen direction stay as they are.

Read the shared [author priorities](../manuscript-integrity-check/references/author-priorities.md),
including [readers first, referees second](../manuscript-integrity-check/references/author-priorities.md#readers-first-referees-second),
the project-resolved settings (`uv run --script ../manuscript-integrity-check/scripts/project.py resolve SOURCE --json`)
and, when it exists, the [manuscript record](../manuscript-integrity-check/references/manuscript-record.md):
its `story`, `venue`, `claims` and `non_claims` entries bind this skill.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run. This applies to direct invocations too.

## What the authors can ask for

- **A reader review** (report only, no edits): how the paper reads now and how that changed since an
  earlier version, from the reading measures, the reader panel and the story tests, with the passages
  quoted. Use it for "how boring is it" and "compare v0.5 with v0.2".
- **A story edit**: the review, then the edits that keep the paper's direction, applied as the `edits`
  setting allows, and the direction changes as options.
- **Direction options**: two or three ways to point the paper, each drafted far enough to judge.
- **A comparison** with named papers or with the closest neighbours and exemplars the skill finds.

Work across the whole paper unless the authors name a part. Every mode ends with the three gates (below)
whenever text changed.

## 1. Establish the direction and the readers

The direction is what the paper is about to its reader: the theme that leads the title, the first
sentences of the Abstract and the end of the Introduction, and the order of the others. The same platform
can lead with privacy, with a biological question, with openness or with speed; that choice is the
authors'. Read it from the record's `story` entry. When there is none, draft one from the title, the
Abstract, the Introduction's last paragraph and the conversation, show it to the authors with the
passages it rests on, and until they confirm it, treat the direction the text has now as the direction.
Record what they confirm, in their words ([story-contract.md](references/story-contract.md#the-story-entry)).

**Check for drift.** Compare the recorded direction with the title, the Abstract's first sentence, the
Introduction's last paragraph and the Conclusion, and, when earlier versions exist, how those passages
changed. A lead theme that disappeared or was replaced over revisions without an author decision is
drift: report it with the before and after text and offer to restore it or to record the new direction.

## 2. Read as readers do

1. **Reading measures.** Run `scripts/reader_metrics.py` on the manuscript, with `--before` an earlier
   version when one exists (an earlier release, the pre-revision copy, git): sentence length, caveats
   by kind of section and at sentence ends, first person, acronyms, the share of each kind of section.
   They are proxies; they point to passages to read.

   ```bash
   uv run --script scripts/reader_metrics.py PAPER.md --before EARLIER.md --md reading.md
   uv run --script scripts/reader_metrics.py v1.md v2.md v3.md --label v1 --label v2 --label v3
   ```

2. **The reader panel.** Three readers who have never seen the paper read it as its audience would
   ([reader-panel.md](references/reader-panel.md)): a skimmer, a potential user and an informed
   outsider. Each says where they stopped, the one sentence they would tell a colleague, what they
   wanted and did not get, and the terms that stopped them. Use independent agents when the harness
   offers them; give each only the manuscript and its seat.
3. **The story tests** ([story-tests.md](references/story-tests.md)): the stake, the gap, the one idea,
   a headline per result, a worked example of real output, where the caveats sit, what the paper argues
   against, how it ends, and whether it tells how the authors did the project or why a reader should
   believe the result.

## 3. Compare with other papers

When the authors ask, or when the Introduction does not position the paper against its nearest
neighbours, compare as [comparisons.md](references/comparisons.md) sets out: three to five **neighbours**
a reader is likely to know (the paper's own closest citations, the predecessors the authors name, their
own earlier versions), for the one sentence of difference a reader wants and any neighbour the paper
never cites; and two or three **exemplars**, well-told papers of the same format or venue, for story
devices only. Every paper named is identity-checked with `manuscript-reference-check`. The result is a
positioning sentence, the missing citations and a short list of devices, never a new related-work section.

## 4. Edit the story

The contract is in [story-contract.md](references/story-contract.md). In short:

- **Edits that keep the direction** may be applied under `edits: conservative` and `edits: apply`, and
  are proposed under `edits: propose`: a stake or hook that serves the recorded direction, a headline
  sentence before a result's numbers, connected sentences, a worked example drawn from the authors' own
  outputs, caveats moved to where they cost the reader least, repetition and defensive detail moved to
  the supplement or the response letter, an ending on what the reader can do. Each still shows as exact
  before/after text in the chat.
- **Direction changes are always proposals**, whatever the setting: a different lead theme or order, a
  theme added or dropped as a main claim, other readers, a new title, a different thing the paper argues
  against. Offer two or three options, each with a draft title, the Abstract's first two sentences, the
  readers and venues it suits and what it costs, and apply none until the authors choose.
- **Never invent.** A worked example is real output from the authors' files or a run they made; a hook
  fact or number has a verified source; a quote is verbatim. Missing material is a question for the
  authors, not a gap to fill.
- **Keep every caveat.** Sort each one: a doubt about the central claim stays beside it, as the last
  sentence of that result; a scope condition moves to Limitations or Methods; defensive detail for a
  referee moves to the supplement or the response letter. Delete only filler that carries no
  qualification. Rewriting a caveat while moving it is a claim change the authors must see.

Sentence-level work follows the [prose-edit contract](../manuscript-prose-edit/references/prose-edit-contract.md),
including its claim ceiling: a story edit never raises a claim's certainty, causality, novelty,
generality or scope. "More engaging" is never "more certain".

## 5. The three gates

No story edit is handed over until all three have run on the edited text, in this order, and every
failure is fixed or turned into a decision for the authors:

1. **Science.** `../manuscript-prose-edit/scripts/guard.py BEFORE AFTER --relocated` (add `--moved-to`
   for each supplement or letter text moved into). A caveat that reappears in a new or changed sentence
   elsewhere is reported as moved, not lost; anything else the guard protects still fails. The record's
   `claims` and `non_claims` hold. Every new citation passes `manuscript-reference-check`.
2. **The journal.** Read the venue from the record (or the ladder's shared requirements when no journal
   is chosen) and check the edit against it: article type, word, figure and reference limits, abstract
   headings, required sections ([manuscript-journal-adapt](../manuscript-journal-adapt/SKILL.md) owns
   these facts; read them, do not re-derive them). Then screen for what editors reject on sight
   ([screening signals](../manuscript-integrity-check/references/screening-signals.md), sections 2.8 and
   3): hype and promotional wording, unsupported "first", "only" or "no existing tool" claims, a lay
   register in a technical venue, health or treatment advice in a paper about people's data (hand clinical
   or privacy scope to `manuscript-policy-fit`).
3. **AI-written prose.** `../manuscript-deslop/scripts/style_profile.py AFTER --before BEFORE --check`,
   then read the edit against the pattern list it prints. Storytelling is where marketing voice and
   manufactured vividness creep in.

When the gates disagree with the story, the science comes first, the journal's format second and the
story third. Do not drop the story element silently: offer it where it fits (a report figure that
replaces a figure rather than adding one, the hook under the structured Abstract's first heading, the
lineage in two sentences instead of a paragraph) and list the choice with the authors' decisions.

## What to show the authors

Write as [Writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)
says. Lead with the reader's view: the recorded direction (and any drift), the panel's one-sentence
takeaways side by side with the sentence the authors want readers to remember, and the measures that
moved, in plain words with the passages they point to. Then each applied change quoted before and after
with its section; then the direction options and other decisions together in one place. Group what
remains under the labels of
[Order the work by when it can be done](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done).
Say what the gates found in their own plain words. Never give a "story score", a predicted citation count
or an acceptance chance.

## Boundaries

This skill does not judge the science (manuscript-peer-review), verify citations
(manuscript-reference-check), copy-edit (manuscript-prose-edit) or format for a venue
(manuscript-journal-adapt); it calls on them where a story edit touches their ground. It never changes the
paper's direction without the authors, never adds a claim, number, example or quotation the authors did
not supply or a source does not support, and never trades a caveat for readability.
