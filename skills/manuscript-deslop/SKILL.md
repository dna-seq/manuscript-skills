---
name: manuscript-deslop
description: >-
  Remove formulaic LLM phrasing, boilerplate and empty rhetoric from scientific writing while preserving
  claims and author voice. Use for requests to deslop, remove AI writing patterns, or humanize a
  manuscript, section or report, including audit-only requests. Use manuscript-prose-edit for broader
  grammar and copy editing, and manuscript-story for narrative and structure.
---

# Deslop scientific writing

Find concrete writing problems and remove them within the requested scope. A stock phrase can occur in
human writing too; neither a catalogue hit nor a style score establishes authorship. Keep passages that
already work. The aim is clearer, more specific writing, never zero hits or a detector threshold.

Read the shared [author priorities](../manuscript-integrity-check/references/author-priorities.md) and
follow the [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md).
Reuse established project choices and the current run; retain this skill's before/after copies, findings
and checks under `manuscript-deslop/`. Honour the saved `edits` policy and requested review checkpoints.

## Choose the requested scope

- **Deslop or humanize.** Edit the supplied passage, section or manuscript for identifiable formulaic
  writing. Keep the task focused; a request to deslop does not call for a full manuscript audit.
- **Audit only.** Identify patterns and explain why they cause a problem here. Quote each passage with
  its section and suggest a fix when useful; leave the source unchanged.
- **Check another skill's writing.** Use the same catalogue and checker for an edited manuscript or a
  report. Reuse that skill's scope and run without starting another editing or setup interview.
- **A stage of manuscript-improve.** Cover the whole paper, on the working copy after the prose edit and
  before the story stage. The prose edit's smell check only keeps its own edits from adding patterns;
  this stage removes the ones the draft already had. Apply what the `edits` policy allows (under
  `conservative`, wording changes that keep the meaning) and propose the rest, such as a cut that
  weakens or narrows a claim. Inside a passage another stage has a pending proposal for, do not apply
  an edit: add your version as a proposal for the same passage, so the authors choose one. Write
  `findings.json` as the [stage findings](../manuscript-dashboard/references/stage-findings.md) describe:
  one record per problem (a pattern repeated through a section is one record), category "Writing and
  clarity", severity `minor` or `info`, and every proposed edit as a change record. Record each applied
  edit once, with `runs.py change`, not in `findings.json`.

Respect an explicit choice of another installed skill. This skill handles scientific writing; an
unqualified request to humanize unrelated prose does not by itself select it. Within this plugin,
use this catalogue and checker rather than loading another `humanizer` with different conventions.

## Find and fix the patterns

Use [llm-smells.md](references/llm-smells.md) for the patterns, examples, fixes and "Leave it when"
exceptions. The catalogue covers empty significance claims, stock vocabulary, repeated sentence shapes,
paragraph scaffolding, unsupported rhetorical additions and damage a cleanup pass can cause. Open the
relevant entry before changing a flagged sentence. A single connector, a technical term, passive voice
in Methods or an evidence-tied hedge may be exactly right.

For edits, follow the [prose-edit contract](../manuscript-prose-edit/references/prose-edit-contract.md#1-the-contract).
Preserve claims, uncertainty, scope, null results, numbers, citations, identifiers and technical meaning.
Cut empty language and write the existing claim plainly; never invent a specific to replace a vague
claim. Do not strengthen or narrow claims, add caution, restructure paragraphs or manufacture stylistic
variation without the corresponding author request. Preserve the author's useful habits and terminology;
use a supplied writing sample when helpful, without requiring one. Flag missing facts or substantive
claim corrections for the authors, and continue independent edits.

Commands below are relative to this skill directory. Before editing, save the original and profile it:

```bash
uv run --script scripts/style_profile.py BEFORE.md --json before-style.json
```

Use `--sample AUTHORS.md` when a writing sample exists. An audit-only request can use this profile and
the catalogue reading pass directly; an edit requires both checks below, even for a pasted passage
saved as before/after files:

```bash
uv run --script ../manuscript-prose-edit/scripts/guard.py BEFORE.md AFTER.md --json guard.json
uv run --script scripts/style_profile.py AFTER.md --before BEFORE.md --check --json after-style.json
```

**The smell check is required for every edit and report.** It has two parts:

1. **Counts.** `--check` fails when an edit adds a pattern or repeats one three or more times under a
   heading the edit changed. Fix it, or retain a use whose catalogue exception applies, rerun with
   `--keep ID`, and explain which sentences stayed and why. A count is a prompt for judgement.
2. **Reading.** Read the text against the full catalogue list printed by `--check`. The script catches
   only some patterns and wordings; fix concrete problems found by reading under the same preservation
   rules. Check that removing scaffolding did not break the argument's links or create choppy prose.

Review the diff in context. The guard catches selected content changes; it does not prove equivalent
meaning. Revert unintended drift and show unresolved claim or evidence questions to the authors.

For a report to the authors, use report mode so quotations are preserved and questions are allowed:

```bash
uv run --script scripts/style_profile.py REPORT.md --report --check
```

## Deliver the result

Return the edited passage or a concise file-change summary with consequential before/after quotations
and section names. For an audit, return findings without applying them. Explain patterns and remaining
questions in plain words; catalogue IDs may follow the description in parentheses. Name any reviewed
exceptions and what the checks could not settle. Link the retained report and checks in the run folder.
Keep the report itself subject to the same count and reading checks.

Use [reflection-mode.md](references/reflection-mode.md) only when the author requests reflection mode
or independent agents. Otherwise edit and review directly. Detector checks remain an optional,
explicitly requested workflow in [manuscript-prose-edit](../manuscript-prose-edit/SKILL.md#requested-detector-checks);
never run them as a prerequisite for deslop or edit toward their scores.

## Shared resources

This skill owns the catalogue, [counted patterns](references/smell-patterns.yaml) and
`scripts/style_profile.py`. The profiler reads the shared vocabulary CSV under
`manuscript-integrity-check/references/`. Prose editing, story editing, report checks, the claim guard,
optional detectors and the pre-commit hook use these same resources. Keep companion skills together.
