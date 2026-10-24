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
data; neither human origin nor voluntary release alone settles every venue requirement. When the request
names an ethics, consent or data statement, read policy-fit's instructions and apply them inside this pass;
it is not a second pass for the authors to start. Draft an ethics statement from the committee's letter in
the letter's own words (what it determined, its reference number and date, what it covers). Where the paper
uses data or reports results the letter does not name, say so once among the decisions; the statement
describes what the paper did, and the determination stands.

Apply the requested task across the whole paper unless the author specifies a narrower scope.
Follow the shared [workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
for requested section or stage review, before/after comparisons and optional interviews.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run. This applies to direct invocations too.

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
before softer preferences, compares open science/source policies, editorial receptiveness, costs
and review speed, and orders the result into a preprint ladder and a journal ladder by the authors'
priorities. The `rank` helper's AI-friction score is only one input to that decision.

## Adapt for a ladder before the choice

When the authors want to adapt before they choose, adapt to what every venue on the ladders shares:

```bash
uv run --script scripts/venues.py common KEY KEY KEY --record REC.yaml
```

Apply its "Adapt now" items to the manuscript in place: sections a venue requires (one that a single venue
requires usually costs the others nothing), abstract headings and length limits when every venue states the
same, rules every venue's guidelines share, and single-venue rules that cost the others nothing (alt text,
dataset citations). Apply them as the `edits` setting allows: under report only every item is a proposal,
and under routine fixes a substantial restructuring is one. Leave its "Choose per venue" items (differing abstract formats, section orders, length
limits, reference styles) for the choice, or follow the first rung when the authors ask; offer the shortest
limit as an option with its cost, never as a default. Its "At the end" items wait with the other end-stage
work. Never create a per-venue copy of the manuscript to cover the ladder.

## Adapt to a venue

```bash
uv run --script scripts/venues.py show <venue-key>                 # the checklist
uv run --script ../manuscript-integrity-check/scripts/scan.py PAPER.md --venue <venue-key>
```

Apply the relevant checklist items within the authorised task: abstract restructured to the venue's headings and
length; body length (a return rule for overlength papers applies when the venue entry records one from the
current page, or from the most recent complete copy when the live page could not be read to that section;
say which); required sections (data and code availability, archived software DOI, competing
interests, author contributions); the venue's reference style (identity and support stay with
`manuscript-reference-check`); AI disclosure in **every** place the venue names with the fields it asks
for, drafted from `../manuscript-integrity-check/references/disclosure-templates.md` with what the authors
say the tools did, never guessed; figure rules; required cover-letter points. Separate requirements for
initial submission from those for revision or acceptance; use free-format submission when allowed. When
the venue's page does not say what counts toward a word limit (abstract headings, the Contact line,
tables, figure legends), give the count both ways and say which one the page leaves open. This
skill owns drafting and placing AI-use statements; `manuscript-integrity-check` only checks that they are
present.

**Fill what the material settles; ask only for the rest.** A venue rule often turns on a fact about the
work: whether a component is a trained classifier and on what data (a machine-learning subsection), where a
dataset came from (its URL or accession for the data availability statement), what format the software
writes, which runs a number covers. When the paper has a repository, read its code, configuration and
result files (read-only) and fill the statement or subsection from them, saying which file settled it;
see [check the project before asking](../manuscript-integrity-check/references/author-priorities.md#minimum-useful-work).
Datasets and software the paper uses without a citation, under a data-citation or prior-work rule, are
added within the adaptation once `manuscript-reference-check`'s identity check confirms each record, and
reported as a count, not as a task for the authors.

**Compare like with like before calling a comparison missing.** When the venue asks that new methods be
compared with existing ones, identify what every benchmark in the paper is compared against before judging
any of them. A baseline that is an established tool counts as a comparison with existing methods even when
the authors built on it or ran their earlier system through it (an earlier pipeline running as OakVar
plugins is a comparison with OakVar). Hold every benchmark to the same standard: do not accept one
established tool as the state of the art and call another "only your own earlier version".

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
routine formatting and content-preserving reorganisation. Apply these as the `edits` setting allows
(under `propose` every change is a proposal; under `conservative` a substantial restructuring is one) and
show a diff. Flag changes to
scientific meaning or decisions needing facts the authors have; do not require a second approval for
every heading, paragraph move or disclosure already authorised.

## Preserve meaning during adaptation

For content-preserving edits, consult the shared
[prose-edit contract](../manuscript-prose-edit/references/prose-edit-contract.md) and review the diff.
`../manuscript-prose-edit/scripts/guard.py BEFORE AFTER` flags selected changes to numbers, citations,
identifiers, terms and wording, and claims that an edit strengthened; it does not prove semantic
equivalence. Every passage the adaptation writes or rewrites (a cut abstract, a merged section, a new
statement) also passes the smell check, which is required:
`../manuscript-deslop/scripts/style_profile.py AFTER --before BEFORE --check`, then a read of the new
text against the pattern list it prints (prose-edit contract, §5.3). New text is where an adaptation adds
machine-written prose. For an adaptation that deliberately changes content, `guard.py BEFORE AFTER --revision`
lists each change with its section and line. When text moves to another file (a supplement split off,
a section moved there), pass that file with `--moved-to` so moved text is not reported as removed, and still read
the diff yourself: a guard that passes does not prove nothing was dropped. Revision markers in the text
stay as they are; when the edits add or bump markers, follow the project's written rules for them (its
manuscript README or CLAUDE.md) and run its marker lint if it has one. Strip them
only for the upload files when the authors want that (see author-priorities; `manuscript-revision-marks`
writes the clean copy and builds the PDF from it, measured against a page limit). Resolve false positives in context
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

Text this skill drafts during the adaptation (a shortened abstract, a data availability or ethics
statement, pointer sentences for moved material) is AI use too. Do the drafting the request covers, then
name it once among the uses in the statement's draft, alongside what the authors say their tools did.

When the authors give the tools they used, fill them in the statement at once (tool, developer, the model
versions they name, how one tool checked another) and ask in the report for what they have not said, such
as which parts of the work each tool was used for. A statement that cannot read complete without a
missing fact is held, with its questions as comments; it never goes into the manuscript as a frame of notes
([Questions for the authors are comments, never text](../manuscript-integrity-check/references/author-priorities.md#questions-for-the-authors-are-comments-never-text)).

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
including any policy conflict, together in one place. Questions come last and only for facts that neither
the manuscript, the conversation nor the project's files hold. When the authors answer, apply the answers
to the manuscript and the report in the same turn and drop the questions they settle; do not ask again.

## Shared resources and maintenance

- `scripts/venues.py`: `rank`, `show`, `ladder`, `common` and `peers` (PEP 723; `uv run --script`). Reads the shared
  `../manuscript-integrity-check/references/venues.yaml`; `peers` queries OpenAlex (set `OPENALEX_MAILTO`
  for its polite pool). Keep the companion skills together.
- [policy-maintenance.md](references/policy-maintenance.md): read when updating the shared catalogue or
  policy snapshots. `scripts/policy_watch.py` checks cited policy pages for changes in AI passages;
  maintenance is separate from adapting an individual manuscript.
