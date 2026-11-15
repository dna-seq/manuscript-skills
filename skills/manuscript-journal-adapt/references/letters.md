# Cover letters and presubmission inquiries

Two letters to an editor, drafted by `scripts/letter.py` from a short file of what each says, and checked the
way an edit is checked: every claim about the paper traced to the manuscript and no stronger there, every
declaration from the authors or the manuscript's own words, and no templated phrasing. Nothing is invented; what
nobody supplied stays in the letter as a marked gap, `[TO FILL: ...]`, for the authors.

- **A cover letter** goes with one submission to one journal, once the journal is chosen. It is an end-stage item
  ([Order the work by when it can be done](../../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done)):
  its declarations need the final preprint, data and AI-use facts.
- **A presubmission inquiry** is a short email asking an editor one question before the authors submit: whether a
  paper fits an article type or section. Use it when the answer changes where or how the paper is submitted and no
  page settles it, such as a database paper with new analyses at a journal that takes databases only in a separate
  issue. It costs the authors an email and days, not a desk rejection after weeks. Some journals say they do not
  answer inquiries; `needs` says so when the catalogue records it, and the check fails on it.

The authors send either letter. Drafting it is this skill's work; sending it is theirs.

## Steps

1. **What the venue asks.** `uv run --script scripts/letter.py needs VENUE` lists, from the venue catalogue: each
   declaration the venue places in the cover letter (the AI-use statement when its `disclosure_places` name the
   cover letter; competing interests, preprint, data availability, funding or suggested and excluded reviewers when
   a rule of its pages names the cover letter), the other points its pages ask the letter to make (iScience: "the
   conceptual advance" and "the significance of the work"), the journal's own words on its scope and on each article
   type, and whether it answers presubmission inquiries, each with its page and the date it was read.
2. **Read what the catalogue lacks.** When `needs` says the scope or article-type words, or the cover-letter rules,
   are not recorded, read the journal's author guide (run `scripts/venues.py stale VENUE` first, as for any venue
   fact) and record what it says, verbatim, with its page and date: the journal's words on what it publishes and on
   the article type as `scope` (`quote`, `article_types`, `presubmission`, `presubmission_quote`, `source`,
   `checked`), and each rule that names the cover letter in `submission_rules`. In this repository's checkout that
   is the shipped `venues.yaml`; in an installed plugin `scripts/venues.py save FACTS.yaml` (`where` names the file).
   Never quote a journal from memory.
3. **Write the letter's file** (`LETTER.yaml`, kept in the run's stage folder; fields below).
4. **Draft and check.** `uv run --script scripts/letter.py write LETTER.yaml --paper PAPER.md --run RUN` writes the
   letter, its claims file and its JSON beside the stage report. Fix every problem it lists in `LETTER.yaml` and run
   it again; exit 0 means every check passed, with the gaps still listed. Add `--verify-related` when the letter names
   a related paper (it asks Crossref for the paper's journal and year).
5. **Report.** In the stage report, link the letter and its claims file, quote the journal's words the letter
   uses with their page and date, and put each gap among the questions for the authors, asked once. A cover letter
   with gaps is not a problem with the draft: the gaps are facts only the authors have.

## What the paper shows

Two or three sentences (one to three in an inquiry), each taken from the Abstract or the Results and saying no
more than the sentences it comes from: the same verbs, the same quantifiers ("most", not "all"), the same scope and
qualifiers, numbers the manuscript states. List each sentence's source passages under `from`: at least three words
in a row, copied from the manuscript, as many passages as the sentence combines. A sentence without `from` is matched
to its closest Abstract or Results sentence, which is weaker; one that matches nothing is untraced. The claim guard
(`manuscript-prose-edit/scripts/guard.py`) compares each sentence with its sources and the check fails on a raised
claim, novelty or generality wording, a dropped scope, limitation, null-result or evidence-status marker, a raised
quantifier, or a number, citation or identifier the sources lack. A sentence that rests on the Introduction explains
background the editor knows (G6).

Points a venue asks the letter to make (the background, the conceptual advance, the significance) go under
`points`, traced the same way; they may come from the Introduction or the Discussion.

## Why this journal

The letter quotes the journal's own words on the article type (or, failing that, its scope) from the catalogue,
and the claims file gives the page and the date they were read. `fit.because` adds one sentence that links the paper
to them, traced like the others. A recent paper the journal published that is close to this one may follow, only
once its identity is verified (`related.verified` says how, by manuscript-reference-check's identity check), and
with `--verify-related` only when Crossref places it in this journal within the last three years. Without one, the
letter keeps an optional gap; never name a paper from memory.

## Declarations

Each declaration the venue asks for in the cover letter is either in `declarations` or a gap. A declaration's text
comes from the manuscript's own statements (`from`, copied passages: a name or a number they lack fails the check
and the letter keeps a gap instead) or from what the authors said (`given_by`: "the authors' message of
2026-11-15"). That holds above all for competing interests, funding and the preprint: never a funder, grant,
DOI or "no competing interests" nobody supplied.

- `ai_use`: the short template of
  [disclosure-templates.md](../../manuscript-integrity-check/references/disclosure-templates.md#keep-it-short),
  with the fields `needs` lists for the venue, saying what the manuscript's own AI-use statement says (or what the
  authors said). The letter and the manuscript never describe the use differently.
- `competing_interests`, `funding`: the manuscript's statements, or the authors' words. A section that still reads
  "to be completed" is a gap.
- `preprint`: the server and DOI, from the manuscript or the authors.
- `data_availability`: a sentence from the manuscript's statement, when the venue asks for it in the letter.
- `reviewers`: `suggested` and `excluded` lists (`name`, `affiliation`, `email`, `reason`) with `given_by`; only
  the authors name reviewers, and the run never looks up or proposes people for them.
- `other`: anything else the venue asks for, as `{label, text, from | given_by}` (a conformity statement, an
  editor among the authors).

## The letter's file

```yaml
kind: cover                  # cover | inquiry
venue: mbe                   # the catalogue key
article_type: Resources      # the journal's own name for the type
title: null                  # default: the manuscript's title
editor: null                 # default: "Dear Editor"; a name only if the authors give one
shows:                       # what the paper shows: 2-3 sentences (1-3 in an inquiry)
  - text: "MitoAge 2 re-derives every value from fixed source versions and holds 2,335 species, 1,413 of them new."
    from: ["MitoAge 2 re-derives every value from fixed source versions", "It holds 2,335 species, 1,413 of them new"]
points: []                   # sentences the venue asks for (background, significance), traced the same way
fit:
  use: auto                  # auto | article_type | scope: which of the journal's words to quote
  because: {text: "...", from: ["..."]}   # one sentence linking the paper to them
related: null                # {citation, doi, verified: "how", why: {text, from}}
declarations:
  ai_use: {text: "...", from: ["..."]}
  competing_interests: {text: "...", given_by: "the authors' message of 2026-11-15"}
question: null               # an inquiry: the one question, ending with "?"
accept: null                 # an inquiry: what the authors will take as an answer
closing: null                # one line; default "Yours sincerely,"
signature: null              # the corresponding author's name, affiliation and email; else a gap
```

An inquiry has `question` and `accept` and needs no declarations. It opens with the question, then what the paper
shows, then the journal's words the question turns on (the rule that sends databases to a separate issue, say), then
what the authors will accept as an answer ("A yes or no is enough: ..."), and the manuscript's Abstract, copied
without notes to the authors.

## The check for letters

Besides the claims, `write` fails on the letter smells of
[llm-smells.md](../../manuscript-deslop/references/llm-smells.md) at their first use (a letter is short, so one use
is noticed): G5 templated openings and closings ("We are pleased to submit", "of great interest to your
readership", "We look forward to hearing from you", "Please do not hesitate to contact us"), G1 chat leftovers, and
the A1, A3, A4 and A5 inflation, implication, promotional and priority patterns. The journal's quoted words are not
counted. It also fails on a closing of more than one line, on what-it-shows sentences from the Introduction (G6), on
a cover letter longer than a page (450 words before the closing) and on an inquiry longer than 300 words besides
its abstract. The letter's order is fixed against G6: what is submitted, as which type, or the question, comes
first.

## Outputs

Beside the stage report, `RUN/manuscript-journal-adapt/`:

- `cover-letter.VENUE.md` or `presubmission-inquiry.VENUE.md`: the letter.
- `....claims.md`: not for sending. Each sentence about the paper with the manuscript's sentences it rests on (section
  and line), the journal's words with their page and date, each declaration with its source and the venue's rule
  for it, the points to check by hand, the gaps and the problems.
- `....json`: the same as data (`passed`, `problems`, `gaps`, `traced`, `declarations`, `quoted`, `needs`).

## Example: MitoAge 2's inquiry to Nucleic Acids Research

NAR takes databases in its annual Database issue; the authors want to ask whether MitoAge 2, a database with new
analyses of which lifespan correlations survive within lineages, could go to review as a regular research article.
`letter.py needs nar` shows that the catalogue records NAR's AI rule (cover letter, Acknowledgements, Methods if
integral) but not its words on article types or inquiries, so the run reads NAR's author guide, records `scope`
(the article types and what it says of databases, and whether it answers inquiries) with the page and date, and
writes:

```yaml
kind: inquiry
venue: nar
article_type: research article
question: "Would Nucleic Acids Research consider MitoAge 2 for review as a regular research article rather than for the Database issue?"
shows:
  - text: "MitoAge 2 re-derives every value from fixed source versions and holds 2,335 species, 1,413 of them new."
    from: ["MitoAge 2 re-derives every value from fixed source versions", "It holds 2,335 species, 1,413 of them new"]
  - text: "Most lifespan correlations that pass the false discovery rate fail on phylogenetically independent contrasts: summed over 32 overlapping taxonomic scopes, 896 of 4,299 keep their sign and significance."
    from: ["Most lifespan correlations that pass the false discovery rate fail on contrasts: summed over 32 overlapping taxonomic scopes, 896 of 4,299 keep their sign and significance"]
fit:
  use: article_type
accept: "A yes or no is enough: with a yes we submit it as a research article; with a no, to the Database issue or to another journal."
```

Then `letter.py write nar-inquiry.yaml --paper docs/manuscript/mitoage2.md --run RUN`.
