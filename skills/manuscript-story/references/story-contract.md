# The story contract: what a story edit may change, what it must propose, and what it never does

The story of a paper is what its reader comes away with: why the work matters, what it lets them do, the
one idea and the one number they keep. A story edit changes how the paper tells that, never what it
found, what it claims, or which story the authors chose to tell.

## The story entry

The direction is recorded in the shared [manuscript record](../../manuscript-integrity-check/references/manuscript-record.md)
under `story`. manuscript-story owns the entry; the authors confirm it.

```yaml
story:                                  # set by manuscript-story from the authors' words; the authors confirm it
  direction: "Privacy: people can read their own genome without uploading it"   # the lead theme, as the authors put it
  themes: [privacy, openness, speed]    # every theme the paper carries, lead first, in the order the authors want
  readers:                              # who the paper is for and what each wants from it
    - "bioinformaticians who might run or extend the tool: what it does, what it outputs, how to add to it"
    - "biologists curious about their own genome: what they would see, what it cannot tell them"
  remember: "A whole genome annotated on your own computer in about half a minute, against modules anyone can publish."
  argues_against: "consumer reports that ask for the genome and do not show how a result was reached"   # optional
  example: "the report for one author's published genome"   # the real output the paper shows; optional
  confirmed: 2026-10-19                 # when the authors confirmed it; without it the entry is a draft
```

Until `confirmed` is set, the direction is the one the text has now; a draft entry never licenses a change.

## Two kinds of story edit

### Edits that keep the direction

These change how the paper tells its story, within the recorded direction:

- A stake or hook in the first sentences of the Abstract or the Introduction that serves the recorded lead
  theme, built from facts the paper already has or a verified source.
- A headline sentence, in plain words, before a result's numbers; one number the reader keeps.
- Connected sentences: each follows from the last by cause, contrast or time.
- A worked example of real output (a report row, a figure of what a user sees), built from the authors'
  own files or runs, replacing an abstract description of the same thing.
- Caveats moved to where they cost the reader least (below), and defensive detail moved to the
  supplement or the response letter.
- Repetition cut: the same disclaimer, the same pointer to a companion paper, said once.
- An ending on what the reader can do, or on the open question the paper raises, with the main limit in
  Limitations.
- A lineage or positioning sentence from the comparisons ([comparisons.md](comparisons.md)).

| `edits` setting | Edits that keep the direction | Direction changes |
|---|---|---|
| `conservative` (default) | applied, each shown as before/after text in the chat | proposed as options |
| `apply` | applied, each shown as before/after text in the chat | proposed as options |
| `propose` | proposed | proposed as options |

The shared [author priorities](../../manuscript-integrity-check/references/author-priorities.md#readers-first-referees-second)
record why `conservative` applies these: the authors decided that story edits which keep their direction
and pass the three gates are routine for this skill. A story edit that also changes a claim, a number or
the Abstract's purpose is not routine under any setting: it follows the shared rules for those.

### Direction changes

Always proposed, whatever the setting, and applied only after the authors choose:

- A different lead theme, or a different order of themes, in the title, the Abstract's first sentences,
  the Introduction's last paragraph or the Conclusion.
- A theme added or dropped as a main claim (making the AI-assistant interface the headline; dropping the
  biological application).
- Different readers (a technical venue's audience instead of the curious researcher, or the reverse).
- A new title, or a different thing the paper argues against.
- Any restructuring whose effect is one of the above, such as moving the benchmark to the front.

Offer two or three options, never one. For each give a draft title, the Abstract's first two sentences,
the readers and the venues on the authors' ladder it suits, and what it costs (which theme it demotes,
which readers it loses, which section it shortens). Include "keep the current direction" as an option when
the current text has one. List the options with the authors' other decisions.

## Where caveats go

Keep every caveat. Sort each one by what it does for the reader:

1. **A doubt about the central claim** (the evidence is one genome; the effect is not replicated) stays
   with the claim, as the last sentence of that result or paragraph, said once with its number. The
   Abstract and Introduction carry claims a reader can hold: the direction of the truth, without inline
   caveat clauses; the caveat they need is in the Results or Limitations.
2. **A scope condition** (GRCh38 only; tested on four call sets) moves to Limitations or Methods, where a
   reader who needs it looks for it.
3. **Defensive detail for a referee** (why a design choice is not a flaw, every version of a rerun)
   moves to the supplement or the response letter.
4. **Filler** that qualifies nothing ("it should be noted that") is cut.

Do not end a key sentence on a caveat: the end of a sentence is its stress position, where the reader puts
the emphasis (Gopen & Swan 1990). "The benchmarks, albeit on four genomes, show faster annotation" makes
the reader remember "four genomes". State a limit with its number rather than a hedge; quantified
uncertainty costs little trust, vague verbal hedging costs more (van der Bles et al. 2020; Gustafson &
Rice 2020). When a referee or a co-author asks for an addition, check the paragraph it lands in for what
can now go, and ask of every sentence whether it tells the reader what was found or tells a referee why an
objection does not overturn it. Never move out of the main text evidence that would change a reader's
conclusion.

Moving a caveat is checked by the guard's `--relocated` mode: a caveat that reappears in a new or changed
sentence elsewhere is reported as moved. A caveat rewritten on the way, so that its wording is gone, is a
claim change the authors must see before and after.

## Never invent

- A worked example is real output: from the authors' files, a run they made, or one the skill made with
  their tools and data and showed them. Never a constructed or "illustrative" result presented as real.
- A hook fact, a number or a quotation has a source that `manuscript-reference-check` verified, or is
  already in the paper.
- No reader, user or patient anecdote the authors did not supply. No invented opponent: what the paper
  argues against is named fairly and cited.
- When the story needs something the authors have and the text does not (a screenshot, a user count, a
  download figure), ask for it under "Fix now".

## The gates, and what to do when they disagree with the story

Run in order on the edited text: science (guard with `--relocated`, the record's claims and non-claims,
reference-check for new citations), the journal (format, limits, abstract headings, required sections;
editors' screening signals), AI-written prose (`style_profile.py --check` and a reading against its list).

The order of precedence is science, then the journal's format, then the story. When the story loses, offer
it where it fits instead of dropping it:

| Conflict | Offer instead |
|---|---|
| A report figure would exceed the figure limit | Replace the weakest figure, or put the example in the supplement and one sentence of it in Results |
| A structured Abstract has fixed headings | Put the stake in the first heading (Motivation, Background) |
| The word limit leaves no room for the lineage | Two sentences in the Introduction, the rest in the supplement |
| A hook needs a fact no source supports | Use a fact the paper already establishes, or ask the authors |
| The vivid version raises a claim | Keep the claim at its strength; make it vivid with its number or an example instead |

## What a story edit never does

- Raise a claim's certainty, causality, novelty, generality or scope, or move a caveat away from the claim
  it qualifies.
- Add hype or promotional wording ("revolutionary", "game-changing", "unprecedented"), "first", "only" or
  "no existing tool" claims without the support `manuscript-integrity-check` requires, or advice about
  health, medicines, diet or treatment.
- Manufacture vividness: rhetorical questions, "imagine a world", second-person scenes, a dramatic arc the
  results do not have.
- Change the direction the authors chose, or decide between themes for them.
- Edit to move a reading measure; edit for a concrete reading problem.
