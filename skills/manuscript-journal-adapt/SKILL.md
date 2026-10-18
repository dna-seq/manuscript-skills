---
name: manuscript-journal-adapt
description: >-
  Adapt manuscripts to a chosen journal and draft concise AI-use statements while preserving scientific
  meaning. Use for venue formatting, required sections, submission materials, disclosure drafting and
  target-policy updates.
  Use manuscript-prose-edit for language editing and manuscript-reference-check for citation verification.
  Use manuscript-journal-select for journal shortlists and requirements-based venue comparisons,
  manuscript-policy-fit for clinical-scope, ethics and privacy ambiguity or author
  self-published biomedical data, manuscript-reporting-check to verify reporting checklists and
  availability statements, manuscript-reviewer-response for response letters to referees, and
  manuscript-integrity-check for full audits.
---

# Adapt manuscripts to a chosen venue

**Help the authors get a sound manuscript published, with the least avoidable delay and effort.** Read
`../manuscript-integrity-check/references/author-priorities.md` for shared priorities, scope and disclosure
rules. Editorial paperwork is a constraint to handle pragmatically, not a goal of its own.

Choose the requested mode: **adapt** to a chosen venue or **draft a disclosure**.
They are independent services, not a mandatory sequence. For prose editing, use `manuscript-prose-edit`.
Use `manuscript-integrity-check` for an audit when requested or a concrete concern warrants it.

For edits intended to reduce clinical, ethics, privacy or regulatory misclassification, use
`manuscript-policy-fit` to establish which conditions actually apply, then preserve those facts during
adaptation. An author's deliberately public personal genome is a distinct case from recruited patient
data; neither human origin nor voluntary release alone settles every venue requirement.

Apply the requested task across the whole paper unless the author specifies a narrower scope.
Follow the shared [workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
for requested section or stage review, before/after comparisons and optional interviews.

## AI-use context (only when the decision needs it)

Use the conversation and manuscript first. Ask what AI did only when the venue verdict or disclosure
depends on an unanswered fact; a routine copy edit can proceed without a provenance interview.

Classify it as **polish** (spelling, grammar, clarity of author-written text), **revision** (substantive
rewording and restructuring of author-written text) or **drafting** (the model wrote new sentences or
sections).

Do not reconstruct AI use from version history unless the authors ask for that inventory. Many manuscripts
live in Google Docs or Word, not git, and an AI co-author trailer on a commit often marks automation (pulling
co-authors' comments from a connected drive, syncing, formatting, conversion), not text the model wrote.
If the authors do want an inventory, read their own revision markers or tracked changes first, and treat a
trailer as a question to put to them, never as the answer.

## Journal selection

Use `../manuscript-journal-select/SKILL.md` for journal shortlists and requirements-based comparisons.
That skill uses the shared database and the helpers in this directory, checks validation affordability
before softer preferences, and compares open science/source policies, editorial receptiveness, costs
and review speed. The `rank` helper's AI-friction score is only one input to that decision.

## Adapt to a venue

```bash
uv run --script scripts/venues.py show <venue-key>                 # the checklist
uv run --script ../manuscript-integrity-check/scripts/scan.py PAPER.md --venue <venue-key>
```

Apply the relevant checklist items within the authorised task: abstract restructured to the venue's headings and
length; body length (a return rule for overlength papers applies only when the venue entry records one
from the current page); required sections (data and code availability, archived software DOI, competing
interests, author contributions); the venue's reference style (identity and support stay with
`manuscript-reference-check`); AI disclosure in **every** place the venue names with the fields it asks
for, drafted from `../manuscript-integrity-check/references/disclosure-templates.md` with what the authors
say the tools did, never guessed; figure rules; required cover-letter points. Separate requirements for
initial submission from those for revision or acceptance; use free-format submission when allowed. When
the venue's page does not say what counts toward a word limit (abstract headings, the Contact line,
tables, figure legends), give the count both ways and say which one the page leaves open. This
skill owns drafting and placing AI-use statements; `manuscript-integrity-check` only checks that they are
present.

Fitting the abstract or body to a limit shortens and restructures; it never adds a result, number or
claim that the abstract did not already make, and it keeps qualifiers such as "in these configurations"
or "does not provide diagnoses". If a stronger abstract needs a result from the body, propose it to the
authors as a content change rather than inserting it. Cutting a qualifier is a claim change, not a trim.

This skill formats and places the venue's statements and checklists. `manuscript-reporting-check` verifies
their content: that accessions, archives and repositories resolve and that a required reporting checklist
is complete. Before upload, the submission-package check in `manuscript-integrity-check` finds LaTeX
comments, hidden text and leaked secrets in the files the venue will publish. For a revised submission,
`manuscript-reviewer-response` owns the response letter; apply only the venue's revision-stage formatting
here. A request to adapt the manuscript covers
routine formatting and content-preserving reorganisation. Apply these and show a diff. Flag changes to
scientific meaning or decisions needing facts the authors have; do not require a second approval for
every heading, paragraph move or disclosure already authorised.

## Preserve meaning during adaptation

For content-preserving edits, consult the shared
[prose-edit contract](../manuscript-prose-edit/references/prose-edit-contract.md) and review the diff.
`../manuscript-prose-edit/scripts/guard.py BEFORE AFTER` flags selected changes to numbers, citations,
identifiers, terms and wording, and claims that an edit strengthened; it does not prove semantic
equivalence. For an adaptation that deliberately changes content, `guard.py BEFORE AFTER --revision`
lists each change with its section and line. Revision markers in the text stay as they are; strip them
only for the upload files when the authors want that (see author-priorities). Resolve false positives in context
and rerun only checks affected by the adaptation. Use `manuscript-prose-edit` for broader language editing
when requested; venue adaptation does not require style profiling or detector checks.

## Disclosure (when required or requested)

Follow `../manuscript-integrity-check/references/author-priorities.md` and consult the relevant part of
`../manuscript-integrity-check/references/disclosure-templates.md`. Check exemptions before adding a
statement, use known facts and only required fields (dates only where the venue asks for them; never
reconstruct them from revision markers or version history), and do not create a per-pass record. When the
authors ask whether a target's AI policy has changed, this skill answers it: run
`scripts/policy_watch.py check --venue KEY`, then read the live page for anything it could not reach.

When the chosen journal restricts the use the authors describe (a ban on AI drafting, for example), adapt
the manuscript and draft the statement as asked, under
[authors first, journals second](../manuscript-integrity-check/references/author-priorities.md#the-author-decides-authors-first-journals-second).
Add at most one sentence naming the conflict and its practical consequence, with the URL of the policy
page, and list it with the authors' other decisions. Do not put it first, offer options they did not ask
for, or come back to it. The statement describes the use that happened: rewriting AI-drafted passages by
hand afterwards does not undo that use, so never present a rewrite as a way to satisfy the ban.

## Report the adaptation

Write the report as [Writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)
describes. Quote each journal rule you applied with the URL of the page it is on and the date it was read
(`show` prints both), and say when a rule rests on the catalogue because the live page could not be read.
Show each change as the passage before and after with its section; `guard.py BEFORE AFTER --revision`
prints this. Spell out acronyms at first use and write full sentences.

List what is left in the order of
[Order the work by when it can be done](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done),
under its four labels. `show` already separates what can be done once the journal is chosen from what
waits until the code, data and results are final: the archived release and its DOI, versions quoted in the
text, the final placement of the AI-use statement, the cover letter, removing revision markers and the
upload check. Those last items are not blockers for the current draft. Put the authors' decisions,
including any policy conflict, together in one place.

## Shared resources and maintenance

- `scripts/venues.py`: `rank`, `show` and `peers` (PEP 723; `uv run --script`). Reads the shared
  `../manuscript-integrity-check/references/venues.yaml`; `peers` queries OpenAlex (set `OPENALEX_MAILTO`
  for its polite pool). Keep the companion skills together.
- [policy-maintenance.md](references/policy-maintenance.md): read when updating the shared catalogue or
  policy snapshots. `scripts/policy_watch.py` checks cited policy pages for changes in AI passages;
  maintenance is separate from adapting an individual manuscript.
