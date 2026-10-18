# Draft mode: writing the response letter

Read this after the authors have revised the manuscript, or when they ask for a draft of one reply. The
letter reports what happened in the manuscript; it is written against the revised text, never ahead of
it.

## 1. Order of work

1. The ledger has a decision for every item (plan mode). An `undecided` item gets a `[TBD: authors'
   decision]` reply, never an inferred one.
2. The manuscript changes are made first, by the authors or, for facts the authors supply, by
   `manuscript-prose-edit` under its author-supplied content rule. Draft a reply only for a change that
   exists; for one that does not exist yet, write `[TBD: ...]` naming what is missing and leave `landed`
   empty.
3. Fill `landed` in the ledger with the location of each change in the revised manuscript.
4. Draft the letter, then run `scripts/check_response.py` (output to a scratch directory) and fix every
   blocking finding.

## 2. The letter

Journal letters have this shape, in Markdown so the check can read it (convert to the journal's format at
the end; `pandoc response.md -o response.docx` keeps blockquotes):

```markdown
# Response to the editor and reviewers

Manuscript [ID], [title].

[Two to five sentences for the editor: the main changes, each with its location; what line numbers refer
to; a note that labels such as R2.P1 or parts (a) and (b) were added by the authors.]

## Editor

<!-- item: Ed.P1 -->
> [The editor's request, verbatim.]

[Reply.]

## Reviewer 1

<!-- item: R1.1 -->
> 1. [The referee's comment, verbatim and complete.]

[Reply.]
```

- One block per ledger item, in the ledger's order, each with its `<!-- item: ID -->` tag. The tag is an
  HTML comment: it disappears when the letter is rendered or converted, and the check uses it to pair
  replies with items.
- The comment is quoted verbatim and complete, as a blockquote: no ellipsis, no corrected grammar, no
  paraphrase. A paraphrase is how half of a request disappears, and a referee who no longer recognises
  their own point will say it was not answered. For an item split from one paragraph, quote that item's part;
  the consecutive blocks together reproduce the paragraph. A fragment of one sentence is quoted as it
  stands, without an ellipsis, and the blocks that share a `sentence` follow one another.
- A `same_as` item gets its own block under the referee's label: answer in a sentence, name the same
  location as the first reply, and refer to it ("as in our reply to Reviewer 2, Weakness 1").
- Do not use headings inside a reply; they end the block. Bold labels such as "**Response:**" are fine.
- A blockquote inside a reply quotes the revised manuscript and is checked against it.
- The opening note to the editor may list the main changes. It never says "we have addressed all
  comments" unless every item is answered and every commitment has landed.

## 3. One reply

**First sentence: the direct answer.** A reader who sees only the comment and this sentence should know
whether the authors did it, did part of it, had already done it, disagree, or cannot. Use the referee's
own nouns. Then the evidence, then the location.

- **Thanks is at most a clause**, and not in every reply. No sentence of thanks on its own, no praise of
  the comment, no default "We agree": agree only when conceding a point, and then say what changed.
- **Evidence**: what was done and what it showed, with numbers that carry their unit, what they are
  compared with and which direction is better. Every number in a reply must be in the revised manuscript,
  or the reply must say it is reported in the letter only.
- **Location**: where the change is in the revised manuscript, as the journal asks for it: section and
  subsection, line numbers, table or figure, always with the section first and never line numbers alone
  ("Results, 'Performance', lines 46-48"). Say what changed there ("Methods now describe ..."), not just
  "see page 5". A reply with no change must say so and why.
- **Links and terms**: give an archive, data set or code release as its full URL (`https://doi.org/...`),
  and spell out at first use an acronym the referee may not know.
- **Length follows the comment**: a one-line minor point gets one or two sentences; an objection to
  validity gets a short evidence run. Work goes into the manuscript; the letter points to it.
- **Use the referee's terms.** If their term is loose, keep it and attach the paper's term in the same
  sentence; never rename what they named. Give a term the referee did not use a short plain gloss.
- **Each reply stands alone.** "See our reply to Reviewer 1, point 2" may follow an answer in the reply's
  own words, never replace it. "As discussed above" names no target and is not a reply.
- **Never claim what did not happen.** No change, analysis, result, citation, approval or location that is
  not in the revised manuscript or the authors' statement. A missing number is `[TBD: what is missing]`.
  A proposed experiment is a proposal: "we will" is for what the journal accepts as future (deposition on
  acceptance), never for a change the reply presents as part of this revision.
- Quote revised text when it is short and settles the point: `The revised sentence reads: "..."`. The
  check confirms the quote occurs in the revised manuscript at the cited lines.

### Already in the paper

Give the location first, and then make it easier to find: a careful referee missed it, so the next reader
will too. Move it, add a cross-reference or a subheading, and say what changed. Never "as stated in the
manuscript" as a rebuke.

### Disagreeing

- State the disagreement as a fact, in the referee's terms, in the first sentence ("There is no overlap
  between the training and test genomes."). Not "We respectfully disagree", not "the reviewer
  misunderstood": address the premise, never the reader.
- Lead with evidence that would have come out differently if the referee were right, then the design
  reason, then independent corroboration. A citation is the weakest support against a specific concern
  about this paper.
- Concede what is true, in its own sentence: usually the text invited the reading.
- Stay within the point raised, state it once, and end with a manuscript change anyway, so the next
  reader does not ask the same question.
- If the evidence does not reach the claim, the right move is to narrow the claim, not to argue.

### Work that cannot be done

Declining is the authors' decision; the reply states it, it does not argue them out of it. One sentence:
what was not done and why, as the authors give the reason. "This is a computational study without a
laboratory component; we did not perform the reporter assay." An in-silico-only budget is a legitimate
constraint; where the study was designed as computational, say so. Where something was done instead (a
public-data replication, a reanalysis, a narrowed claim), the same reply says so, with its result and
location, and the matching manuscript change: the narrowed claim, or one sentence where the gap sets what a
result means. A bare time, cost or capacity reason reads as a refusal, so when nothing was done instead,
offer the authors one such change once; if they decline it too, write the reply they want.
If the alternative has not been run, the reply says what the authors propose and carries a `[TBD]` for
the result; it never reports the result in advance.

### Hand-offs inside a reply

- **Ethics, consent, clinical scope, privacy**: `manuscript-policy-fit` drafts the reply text from the
  facts the authors give. Insert it in the item's block, add the location, and keep its wording; do not
  add approvals, exemptions or consent the authors have not stated.
- **New or replacement citations**: verify each with `manuscript-reference-check` before it enters the
  letter or the manuscript.
- **Reporting checklists, availability statements**: `manuscript-reporting-check`.
- **Language edits to revised text**: `manuscript-prose-edit` under its contract, and new facts the
  authors supply under its author-supplied content rule; rerun the check, since quoted revised text must
  still match.

## 4. Line numbers, anchors and tracked changes

- Ask, or read in the journal's instructions, which version the line numbers refer to: the clean revised
  manuscript, or the version with tracked changes. State it once in the opening note.
- The check compares line numbers with the revised file it is given. For a Markdown or LaTeX source whose
  journal PDF is numbered differently, either give section anchors (`Results, "Performance"`) instead of
  line numbers, or pass the text of the line-numbered PDF (`pdftotext -layout revised.pdf revised.txt`);
  the check recognises printed line numbers. Use `--no-line-check` when neither is possible.
- A marked-up copy, if the journal wants one: `latexdiff original.tex revised.tex > diff.tex` for LaTeX,
  Word's Compare Documents for Word, or `git diff --word-diff` for Markdown kept in git. Formatting the
  revision package for the journal belongs to `manuscript-journal-adapt`.
- Locations name the revised manuscript, not the original. A quote of the original wording is fine when
  the reply says it was replaced ("we replaced 'did not change results' with ...").

## 5. Later rounds

- Quote the round-N comment verbatim, as in round 1. The ledger's `previous` field links it to the earlier
  items it follows up.
- Refer back explicitly and briefly: what round 1 committed to, what is in the manuscript now, and where.
  "In the first round we added the HiFi callset of HG002 (our reply to Reviewer 2, first comment). We have
  now added HG004, a third individual (Table 1)." Do not paste the earlier reply.
- If an earlier commitment did not land, say so plainly and either land it now or explain.
- A referee who is satisfied gets at most a one-line acknowledgement.

## 6. One-shot conference rebuttals

For a rebuttal with no revised manuscript (OpenReview and similar), use `mode: rebuttal` in the ledger
and `--mode rebuttal` for the check.

- The character limit is per reviewer or per paper; check it with `--max-chars`.
- Quotes may be short fragments of the review, still verbatim; the check reports partial quotes as
  advisory in this mode.
- Commitments for the camera-ready are promises and the reply says so ("we will add ... to Section 5");
  `landed: promised` is allowed. Results reported in the rebuttal must exist; never report an experiment
  that has not finished.
- Spend the space on the concerns that decide the outcome, but answer every question at least in one
  line: an unanswered question reads as a concession.

## 7. Reading the check

`scripts/check_response.py` checks structure only. Fix blocking findings (missing or duplicate replies,
non-verbatim quotes, order, missing locations, blanket replies, unlanded commitments, locations or quoted
text that do not exist, open placeholders). Read advisory findings (numbers absent from the manuscript,
locations that differ from the ledger, thanks or agreement as the opening, future tense, changes the
letter never mentions) and decide each one. A clean run means the letter is well formed, not that it
answers the referees: that judgement is verify mode's.

Show the authors the check's Markdown report, or a summary in its style, never its codes or the JSON. The
report already quotes each comment under the referee's number and the letter or manuscript text a finding
concerns, names places in words with line numbers in parentheses, and groups the problems by when they can
be fixed: the changes the referees asked for that are not yet in the manuscript and numbers that disagree
first, then the letter's wording, then the venue's limits, then statements such as code availability. A
revision going back to the journal is a submission, so the last group is still done before sending, after
the others.
