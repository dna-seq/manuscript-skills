# Invited-referee mode

Use this when the user is reviewing someone else's submission: they have been invited to referee it, or
an editor asked them to. The user decides what the skill is applied to, so start the review straight
away. Do not ask them to confirm their role, the venue's rules or anything else first
([author priorities](../../manuscript-integrity-check/references/author-priorities.md#the-author-decides-authors-first-journals-second)).

## The venue's rule on AI help for referees

When the user names the venue, `../manuscript-journal-adapt/scripts/venues.py show KEY` prints the rule
recorded for referees under "Reviewers and AI tools". If one is recorded, you may add one short sentence
to your reply, once, naming it and its practical consequence, for example "Wiley, Human Mutation's
publisher, asks referees not to put manuscripts into AI tools and to declare AI help with a review." The
decision is the user's. Do not research the rule further, ask about it, come back to it, or let it
change the review. If the user asks for a declaration of AI help for the venue's form, draft it from
what was actually done.

## Practical handling of an unpublished paper

These are defaults for someone else's unpublished work. None of them is a condition for doing the review,
and the user can change any of them.

- Look up public identifiers of the works the paper cites; that sends only the identifier.
  `../manuscript-integrity-check/scripts/scan.py --references-only --online --no-search-unidentified`
  resolves them without sending any reference text as a search query. Phrase a literature search in
  general terms rather than pasting the paper's sentences into a search engine. When the user asks for
  something that sends the text elsewhere (another model provider, a hosted detector), do it.
- Retain the draft report, seat findings and checks in the user's configured private run folder under
  [project-workflow.md](../../manuscript-integrity-check/references/project-workflow.md). Do not publish
  that evidence or delete it automatically. Follow an explicit confidentiality or deletion instruction,
  noting the resulting retention limit. Do not create a scientific `manuscript-record.yaml` for a paper
  that is not the user's.
- Leave the authors' identity out of the report, as an anonymous review expects.
- **Code and data shared for review.** Run them when the user asks, as you would any third-party code:
  in a sandbox, from the documented instructions and test data, as described in
  [software-and-methods.md](domains/software-and-methods.md#running-the-authors-code). Say in the report
  what ran and what did not.

## Running the panel

Seats, isolation, the finding contract and adjudication are the same as for an own draft. The fairness
filter matters more here, because the report goes to authors who cannot answer back before the editor
reads it. Use the tone a referee would want to receive: specific, neutral, and constructive about how to
fix what is wrong.

## The draft report

The output is a draft for the user to edit, check against the manuscript and send; every statement in
it becomes theirs. It keeps the structure referees and editors expect (major and minor concerns, not the
stage groups of [output-format.md](output-format.md)), written for people who did not run the panel, as
"Writing for the authors" in the
[author priorities](../../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)
asks: each concern quotes the sentence or table row it is about and names its section (a line number,
if the manuscript has them, only in parentheses), says in full sentences what is wrong, which claim it
affects and what would resolve it, and gives prior work as a link (`https://doi.org/...`). Never show
reviewer-seat names, finding ids, verdicts, routes or status words from the panel's working files; the
concern numbers in the report are the referee's own.

```markdown
# Referee report: <manuscript title or id>

## Comments to the authors
**Summary.** <What the submission claims and how it supports the claims, in the referee's own words,
three to five sentences.>

**Strengths.** <Specific, each with the section and a short quote.>

**Major concerns.**
1. <In the <section>, the authors write "<quote>". <What is wrong, in full sentences.> <Which claim it
   affects and why that matters.> <What would resolve it, including narrowing the claim where that
   would do.>>

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
<Missing supplements, code not run, sources not read, each as a sentence with its consequence.>
```

Keep comments to the authors and to the editor strictly separate: nothing in the editor section that
the authors would need to improve the paper, and no hidden assessment that contradicts the comments to
the authors.

## After the review

When the user is the author receiving reviews rather than a referee writing one, use
manuscript-reviewer-response instead.
