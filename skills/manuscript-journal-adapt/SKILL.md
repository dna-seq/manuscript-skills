---
name: manuscript-journal-adapt
description: >-
  Adapt manuscripts to a chosen journal and draft concise AI-use statements while preserving scientific
  meaning. Use for venue formatting, required sections, submission materials, disclosure drafting and
  target-policy updates.
  Use manuscript-prose-edit for language editing and manuscript-reference-check for citation verification.
  Use manuscript-journal-select for journal shortlists and requirements-based venue comparisons,
  manuscript-policy-fit for clinical-scope, ethics and privacy ambiguity or author
  self-published biomedical data, and manuscript-integrity-check for full audits.
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
length; body length (some venues return a paper 20% over the limit unread); required sections (data and
code availability, archived software DOI, competing interests, author contributions); AI disclosure in
**every** place the venue names with the fields it asks for, drafted from
`../manuscript-integrity-check/references/disclosure-templates.md` with what the authors say the tools did,
never guessed;
figure rules; required cover-letter points. Separate requirements for initial submission from those for
revision or acceptance; use free-format submission when allowed. A request to adapt the manuscript covers
routine formatting and content-preserving reorganisation. Apply these and show a diff. Flag changes to
scientific meaning or decisions needing facts the authors have; do not require a second approval for
every heading, paragraph move or disclosure already authorised.

## Preserve meaning during adaptation

For content-preserving edits, consult the shared
[prose-edit contract](../manuscript-prose-edit/references/prose-edit-contract.md) and review the diff.
`../manuscript-prose-edit/scripts/guard.py BEFORE AFTER` flags selected changes to numbers, citations,
identifiers, terms and wording; it does not prove semantic equivalence. Resolve false positives in context
and rerun only checks affected by the adaptation. Use `manuscript-prose-edit` for broader language editing
when requested; venue adaptation does not require style profiling or detector checks.

## Disclosure (when required or requested)

Follow `../manuscript-integrity-check/references/author-priorities.md` and consult the relevant part of
`../manuscript-integrity-check/references/disclosure-templates.md`. Check exemptions before adding a
statement, use known facts and only required fields, and do not create a per-pass record. Drafting-ban
policies need a separate compatibility decision; do not prescribe an author rewrite as a guaranteed cure.

## Shared resources and maintenance

- `scripts/venues.py`: `rank`, `show` and `peers` (PEP 723; `uv run --script`). Reads the shared
  `../manuscript-integrity-check/references/venues.yaml`; `peers` queries OpenAlex (set `OPENALEX_MAILTO`
  for its polite pool). Keep the companion skills together.
- [policy-maintenance.md](references/policy-maintenance.md): read when updating the shared catalogue or
  policy snapshots. `scripts/policy_watch.py` checks cited policy pages for changes in AI passages;
  maintenance is separate from adapting an individual manuscript.
