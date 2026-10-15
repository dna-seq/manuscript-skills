---
name: manuscript-journal-adapt
description: >-
  Adapt manuscripts to a chosen journal, draft concise AI-use statements, and copy-edit or humanize prose
  while preserving scientific meaning. Use for venue formatting, policy updates, language editing and
  disclosure drafting. Use manuscript-journal-select for journal shortlists and requirements-based venue
  comparisons, manuscript-policy-fit for clinical-scope, ethics and privacy ambiguity or author
  self-published biomedical data, and manuscript-integrity-check for audits and reference verification.
---

# Journal adaptation and copy editing for AI-assisted manuscripts

**Help the authors get a sound manuscript published, with the least avoidable delay and effort.** Read
`../manuscript-integrity-check/references/author-priorities.md` for shared priorities, scope and disclosure
rules. Editorial paperwork is a constraint to handle pragmatically, not a goal of its own.

Choose the requested mode: **adapt** to a chosen venue, **copy-edit**, or **draft a disclosure**.
They are independent services, not a mandatory sequence. Use `manuscript-integrity-check`
for an audit when one is requested or a concrete concern warrants it.

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

## Keeping the venue data current

`scripts/policy_watch.py` watches every page `venues.yaml` cites (`url`, `ai_policy_url`, `sources`). It
reduces each page to the passages about AI and compares them with the snapshot in
`../manuscript-integrity-check/references/policy-snapshots/`; snapshots are plain text under git, so
`git log -p` on one is the history of that policy.

```bash
uv run --script scripts/policy_watch.py check --venue aging-cell          # one venue, report only
uv run --script scripts/policy_watch.py check --stale-days 30 --update    # everything not read for 30 days
uv run --script scripts/policy_watch.py list                              # what is watched, when last read
uv run --script scripts/policy_watch.py record URL saved.html            # a page the scripts cannot reach
```

It tries plain HTTP, then headless Chrome, then the newest Wayback copy. A page none of them can read is
`not_assessed`, never `unchanged`. An archived snapshot is historical evidence, not verification of the
current rule. Try available browsing tools for blocked pages; ask the author for a copy only if this is
the remaining obstacle to a material decision. Do not treat a paraphrased fetch as an exact quotation.
`changed` means the AI passages differ: read the diff, decide whether the rule moved (a reworded sentence
can be nothing; a new requirement is not), then update the venue's fields, its `checked` date and its
section in the reference notes. Exit code 1 when anything changed or disappeared, so the command can run
on a schedule.

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

## Copy-edit ("humanize")

Read `references/humanize-contract.md` for the single copy-edit procedure. Consult only relevant entries
in `references/llm-smells.md`; the catalogue is diagnostic help, not a checklist to exhaust.
`scripts/style_profile.py PAPER.md [--sample AUTHORS.md]` can locate repetitive or generic prose in a long
draft. Use available author samples when voice matching helps; do not make the author supply samples to
obtain an ordinary edit. The optional installed `humanizer` catalogue can help, subject to this contract.

Preserve scientific meaning and review the diff. For file edits, `scripts/guard.py BEFORE AFTER` checks
counts of selected numbers, identifiers, citations and term patterns and flags selected wording changes;
it does not prove semantic equivalence. Resolve false positives yourself when meaning is unchanged.
Re-run only checks affected by the edit. Return the edited text or a concise file-change summary and any
unresolved content questions; detailed change tables are on request.

**Reflection mode** (`references/reflection-mode.md`) uses critic and writer subagents for at most two
rounds when the user requests that mode or independent agents. It is optional for every section.

**Detector check** (only when the user asks for one): run `scripts/detector_setup.py check` first. It reports
whether a Hugging Face token is configured, the GPU, memory and disk, which free detectors are ready or
already downloaded, and recommends one (local `modernbert` by default; the text stays on the machine). If
the user wants a detector that needs a token or access, give the page from the report; an explicit request
to open it is sufficient. Then `scripts/detect.py PAPER --detector
<key> --sample <the authors' earlier writing>`; a hosted detector needs `--allow-remote` and the authors'
consent for this text. Feed flagged windows to the critic as places to look (`references/detector-apis.md`).

Edit for a concrete writing problem, never for a detector threshold. Do not insert errors, manufacture
variation or change scientific meaning to influence a score. A flagged passage with no identifiable
problem stays unchanged. See `references/detector-evidence.md` for the limitations of these tools.

## Disclosure (when required or requested)

Follow `../manuscript-integrity-check/references/author-priorities.md` and consult the relevant part of
`../manuscript-integrity-check/references/disclosure-templates.md`. Check exemptions before adding a
statement, use known facts and only required fields, and do not create a per-pass record. Drafting-ban
policies need a separate compatibility decision; do not prescribe an author rewrite as a guaranteed cure.

## Files

- `scripts/venues.py`: `rank` (with the interview filters), `show` and `peers` (PEP 723; `uv run --script`).
  Reads `../manuscript-integrity-check/references/venues.yaml`, so keep the companion skills together. `peers`
  queries OpenAlex (set `OPENALEX_MAILTO` for its polite pool).
- `scripts/policy_watch.py`: fetches every cited policy page, compares its AI passages with the snapshot,
  reports changed, unchanged, gone or not assessed, and stores new snapshots with `--update`.
- `scripts/guard.py`: before/after drift check of numbers, citations, identifiers, terms, URLs, code
  (protected) and hedges, negations, causal verbs, comparatives (watched).
- `scripts/style_profile.py`: smell density per paragraph and style measures, optionally against the authors' own
  writing; not a detector and not a probability.
- `references/humanize-contract.md`: the contract, invocation modes, writer profile, inventory, rewriting,
  the literal gate, the scaffolding audit, output format, register by text type.
- `references/llm-smells.md`: the catalogue of smells with examples, false positives, signs of human writing.
- `references/smell-patterns.yaml`: the machine-detectable part of the catalogue, read by `style_profile.py`.
- `references/reflection-mode.md`: the critic and writer agents, their prompts, the stopping rule.
- `references/section-guide.md`: what each part of a paper needs, from title to response letter.
- `scripts/detector_setup.py`: environment check, detector recommendation, token pages (opens one only when asked).
- `scripts/detect.py`: window-by-window scores from a free detector, three states, calibrated on the authors'
  own writing; heavy (torch, transformers), so it is not part of the pre-commit hook.
- `references/detector-apis.md`: the free detectors, what each needs, their evidence, how the skill uses them.
- `references/detector-evidence.md`: what 2026 evidence says about AI-text detectors, disclosure rates and
  humanizer tools
  (which open-source humanizers are fit for manuscripts, and which are detector-evasion tools).
