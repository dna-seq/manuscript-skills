---
name: manuscript-prose-edit
description: >-
  Edit manuscript prose for clarity, grammar, consistency and author voice while preserving scientific
  meaning. Use for language editing, copy editing, humanizing repetitive or generic writing, and requested
  style or AI-text detector checks. Use manuscript-journal-adapt for venue formatting and AI-use statements,
  manuscript-reference-check for citation verification, and manuscript-integrity-check for a full audit.
---

# Edit manuscript prose

Improve the requested text while preserving its claims, evidence and author voice. Read the shared
[author priorities](../manuscript-integrity-check/references/author-priorities.md). Use the manuscript and
conversation first; an ordinary prose edit does not require a target journal, provenance interview,
writing samples or a full audit.

## Edit and check the result

Read [prose-edit-contract.md](references/prose-edit-contract.md) for the editing procedure and preservation
rules. Consult the relevant entries in [llm-smells.md](references/llm-smells.md) for concrete writing
problems and false positives, and [section-guide.md](references/section-guide.md) when a section's purpose
matters. The catalogue is diagnostic help, not a checklist to exhaust.

For a long draft, `scripts/style_profile.py PAPER.md [--sample AUTHORS.md]` can locate repetitive or
generic prose. Use available author samples when voice matching helps; do not require samples for an
ordinary edit. The optional installed `humanizer` catalogue can help, subject to this skill's contract.

Make the authorised edits, preserve scientific meaning and review the diff in context. For file edits:

```bash
uv run --script scripts/guard.py BEFORE.md AFTER.md
uv run --script scripts/style_profile.py PAPER.md --sample AUTHORS.md
```

The guard checks counts of selected numbers, identifiers, citations and term patterns and flags selected
wording changes. It does not prove semantic equivalence. Resolve false positives yourself when meaning
is unchanged and rerun only checks affected by the edit. Return the edited text or a concise file-change
summary and unresolved content questions; detailed change tables are on request.

For a claim that needs source verification, use `manuscript-reference-check`. Use `manuscript-policy-fit`
when an edit depends on clinical, ethics, privacy or regulatory applicability. Venue formatting and
required AI-use statements belong to `manuscript-journal-adapt`; editing prose alone does not trigger them.

## Optional independent reflection

Use [reflection-mode.md](references/reflection-mode.md) only when the user requests reflection mode or
independent agents. It alternates critic and writer subagents for at most two rounds, with the guard
after each pass. It is optional for every section.

## Requested detector checks

Only when the user asks for a detector check, run `scripts/detector_setup.py check` first. It reports
whether a Hugging Face token is configured, GPU, memory and disk availability, ready or downloaded free
detectors, and a recommendation (local `modernbert` by default; text stays on the machine). If the user
wants a detector needing a token or access, give the page from the report; an explicit request to open
it is sufficient.

Then run `scripts/detect.py PAPER --detector <key> --sample AUTHORS.md`, omitting the sample if none is
available. A hosted detector needs `--allow-remote` and the author's consent for this text. Read
[detector-apis.md](references/detector-apis.md) for setup and output, and
[detector-evidence.md](references/detector-evidence.md) for limitations. Treat flagged windows as places
to reread; use them in a critic pass only if that mode was requested.

Edit for a concrete writing problem, never for a detector threshold. Do not insert errors, manufacture
variation or change scientific meaning to influence a score. Leave a flagged passage unchanged when
there is no identifiable problem. A detector result is not evidence of authorship.

## Shared tools

Commands are relative to this skill directory. Keep the plugin's companion skills together:
`style_profile.py` also reads the shared vocabulary CSV under `manuscript-integrity-check/references/`.
The integrity skill's pre-commit hook uses this skill's style profiler. `guard.py` is also available to
venue adaptation and policy-fit edits; those callers use the same copy of the preservation tool.
