# Invited-referee mode

Use this when the authors of the request are not the manuscript's authors: they have been invited to
referee someone else's submission, or an editor asked them to. Read this file before opening the
manuscript.

## Before reading the manuscript

1. **Authorisation.** Ask the user to confirm, in one message, that they are the invited referee (or a
   co-reviewer the editor has approved), and that the venue's reviewer guidance permits using an AI
   assistant on the manuscript. Check what is known: `../manuscript-journal-adapt/scripts/venues.py show
   KEY` prints the recorded `reviewer_ai` rule (`banned`, `restricted` to publisher-approved tools,
   `allowed`, or not researched), and `../manuscript-integrity-check/references/publisher-policies.md`
   quotes several publishers' reviewer rules. Re-read the venue's current reviewer page when it matters.
2. If the venue bans AI tools for reviewers, or allows only tools this assistant is not, say so once and
   do not process the manuscript. Offer what does not need it: general guidance on structuring a
   referee report, or a review of the user's own draft report text with the manuscript's content
   removed. If the rule is unknown, the user decides after checking; record their confirmation.
3. **Confidentiality.** The manuscript is someone else's unpublished work.
   - Nothing from it leaves this session: no web searches containing its text, no hosted detectors, no
     other model providers, no uploads, no sharing of its figures or data.
   - Looking up public identifiers of works it cites is fine, as is a literature search phrased in
     general terms that contains no manuscript text. Run `scan.py --references-only --online
     --no-search-unidentified` so that no reference text is sent as a search query.
   - Do not create `manuscript-record.yaml` or other persistent notes for it; keep working files in a
     scratch location and offer to delete them when the report is done.
   - Do not try to identify anonymous authors, and do not contact anyone.
4. **Code and data shared for review** are confidential too. Install or run them only when the user
   asks and the venue's review process provides them for that purpose, in a sandbox as described in
   [software-and-methods.md](domains/software-and-methods.md#running-the-authors-code).

## Running the panel

Seats, isolation, the finding contract and adjudication are the same as for an own draft. The fairness
filter matters more here, because the report goes to authors who cannot answer back before the editor
reads it. Use the tone a referee would want to receive: specific, neutral, and constructive about how to
fix what is wrong.

## The draft report

The output is a draft for the user to edit, check against the manuscript and sign. Every statement in
it becomes theirs.

```markdown
# Draft referee report: <manuscript title or id>
Draft prepared with an AI assistant for <referee>'s editing. Not for submission without their review.

## Comments to the authors
**Summary.** <What the submission claims and how it supports the claims, in the referee's own words,
three to five sentences.>

**Strengths.** <Specific, with locations.>

**Major concerns.** <Numbered. Each: location and quote, what is wrong, which claim it affects, and what
would resolve it (including narrowing the claim).>

**Minor concerns.** <Numbered, same form, shorter.>

**Questions for the authors.** <Points that could change the assessment once answered.>

## Confidential comments to the editor
<Only what belongs here: a concern for the editor's attention (possible overlap with published work,
an ethics question), the limits of the referee's expertise, any conflict of interest. Nothing that
should have been said to the authors.>

## Recommendation
<Omitted unless the referee asked. When asked, give the options with the reasons for each and let the
referee choose; never a probability.>

## What this draft did not have
<Missing supplements, code not run, sources not read.>
```

Keep comments to the authors and to the editor strictly separate: nothing in the editor section that
the authors would need to improve the paper, and no hidden assessment that contradicts the comments to
the authors. Remind the user once that some venues ask referees to declare AI assistance; whether and
how to declare it is their decision under the venue's rules.

## After the review

When the user is the author receiving reviews rather than a referee writing one, use
manuscript-reviewer-response instead.
