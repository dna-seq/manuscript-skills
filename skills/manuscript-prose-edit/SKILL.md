---
name: manuscript-prose-edit
description: >-
  Edit manuscript prose for clarity, grammar, consistency and author voice while preserving scientific
  meaning and claim strength. Use for language editing, copy editing, reducing repetitive or generic
  writing, checking that an edit or a revision did not change numbers, citations or claims, and requested
  style or AI-text detector checks. Use manuscript-journal-adapt for venue formatting and AI-use statements,
  manuscript-reference-check for citation verification, manuscript-integrity-check for a full audit,
  manuscript-peer-review for referee-style critique of the science, and manuscript-reviewer-response for
  answering referees.
---

# Edit manuscript prose

Improve the requested text while preserving its claims, evidence and author voice. Read the shared
[author priorities](../manuscript-integrity-check/references/author-priorities.md). Use the manuscript and
conversation first; an ordinary prose edit does not require a target journal, provenance interview,
writing samples or a full audit.

Apply the requested task across the whole paper unless the author specifies a narrower scope.
Follow the shared [workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
for requested section or stage review, before/after comparisons and optional interviews.

## Edit and check the result

Read [prose-edit-contract.md](references/prose-edit-contract.md) for the editing procedure and preservation
rules. Consult the relevant entries in [llm-smells.md](references/llm-smells.md) for concrete writing
problems and false positives, and [section-guide.md](references/section-guide.md) when a section's purpose
matters. The catalogue is diagnostic help, not a checklist to exhaust.

For a long draft, `scripts/style_profile.py PAPER.md [--sample AUTHORS.md]` can locate repetitive or
generic prose. Use available author samples when voice matching helps; do not require samples for an
ordinary edit. The optional installed `humanizer` catalogue can help, subject to this skill's contract.

Make the authorised edits, preserve scientific meaning and review the diff in context. The contract's
**claim ceiling** holds for every request, including "make it punchier" or "sound more confident": improve
the prose, never raise a claim's certainty, causality, novelty, generality or scope
([claim-ladders.md](references/claim-ladders.md)). Narrowing a claim is a claim correction the authors must
see. For file edits:

```bash
uv run --script scripts/guard.py BEFORE.md AFTER.md [--json report.json] [--md report.md]
uv run --script scripts/style_profile.py PAPER.md --sample AUTHORS.md
```

The guard keeps its whole-text counts of numbers, citations, identifiers and terms, and also aligns the
sentences of the two versions (split, merged and moved sentences included). For each sentence it reports,
with section and line, a claim that rose or fell on the causal or evidential ladder, novelty or generality
wording, a scope qualifier, limiting or concessive word ("only", "albeit", "despite"), null result or
evidence-status word that disappeared, and a number, citation or identifier the sentence did not have. Exit 1
marks a protected change: a count change, a stronger claim, a lost qualifier or a token new to its paragraph.
Lowered claims and moved tokens are warnings. After an authorised claim correction, `--allow-strengthening`
lists the claim changes as authorised instead of failing; numbers and citations still fail. The guard does not
prove semantic equivalence. Resolve false positives yourself when meaning is unchanged and rerun only checks
affected by the edit. Revision markers
(`<!-- @rev ... -->`) stay where they are and are added or updated only as the project's written rules say
([author priorities](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review));
the guard ignores them. Where the project keeps them, an applied edit bumps or opens its segment through
`manuscript-revision-marks`, signed with the name of whoever wrote the round. Return the edited text or a concise file-change summary, the warnings that stand and
unresolved content questions; detailed change tables are on request.

For a claim that needs source verification, use `manuscript-reference-check`. Use `manuscript-policy-fit`
when an edit depends on clinical, ethics, privacy or regulatory applicability. Venue formatting and
required AI-use statements belong to `manuscript-journal-adapt`; editing prose alone does not trigger them.

## Revision inventory

When content changes are expected (a revision after review, a co-author's version, a venue adaptation, the
contract's author-supplied content), list them instead of failing on them:

```bash
uv run --script scripts/guard.py ORIGINAL.md REVISED.md --revision --json inventory.json
uv run --script scripts/guard.py REVISED.md --against v1-submitted --revision
```

It reports every number, citation, identifier, claim-strength, scope, null-result and evidence-status change
with section and line, in the same JSON fields as an edit (`sentence_changes`, `alignment`, `summary`), and
always exits 0. `manuscript-reviewer-response` checks each listed change against the response letter;
`manuscript-journal-adapt` and `manuscript-policy-fit` use it to show what their authorised edits changed.
Present the changes; do not judge them as errors, since the authors chose them.

## Optional independent reflection

Use [reflection-mode.md](references/reflection-mode.md) only when the user requests reflection mode or
independent agents. A new critic subagent each round reads only the current text, never the authors'
self-assessment, the writer's notes or what the last round fixed, and cites a catalogue ID for each finding
so every fix is traceable without a log file. The guard runs after each writer pass. The loop stops after a
round with no accepted finding, and after two rounds at most.

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
venue adaptation, policy-fit edits and reviewer responses; those callers use the same copy of the
preservation tool and the same ladders.
