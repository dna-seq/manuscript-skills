---
name: manuscript-prose-edit
description: >-
  Edit manuscript prose for clarity, grammar, consistency and author voice while preserving scientific
  meaning and claim strength. Use for language editing, copy editing, reducing repetitive or generic
  writing, checking that an edit or a revision did not change numbers, citations or claims, and requested
  style or AI-text detector checks. Use manuscript-deslop for a focused check or cleanup of formulaic LLM
  phrasing, manuscript-journal-adapt for venue formatting and AI-use statements,
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
for the saved `edits` policy, requested section or stage review, before/after comparisons and optional
interviews. Read the settings before editing. Collect substantive proposals while finishing all
independent checks and permitted edits; a pending answer blocks only work that depends on it.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run. This applies to direct invocations too.

## Edit and check the result

Read [prose-edit-contract.md](references/prose-edit-contract.md) for the editing procedure and preservation
rules, and [section-guide.md](references/section-guide.md) when a section's purpose matters. Apply
[manuscript-deslop](../manuscript-deslop/SKILL.md) for the pattern check: it owns the catalogue,
false-positive exceptions and style profiler. **The smell check is required for every edit**, including a
short pasted passage saved as before/after files. Run its counts before and after editing, then read the
edit against the full catalogue list. Resolve added patterns and clusters, or record a reviewed exception
with `--keep ID` and explain the retained sentences to the authors. A sentence that works can stay.

Use available author samples (`--sample`) when voice matching helps; do not require samples for an
ordinary edit. Use this plugin's deslop workflow for these checks; other installed humanizers can have
rules that conflict with scientific writing or the preservation contract.

Make the authorised edits, preserve scientific meaning and review the diff in context. The contract's
**claim ceiling** holds for every request, including "make it punchier" or "sound more confident": improve
the prose, never raise a claim's certainty, causality, novelty, generality or scope
([claim-ladders.md](references/claim-ladders.md)). Narrowing a claim is a claim correction the authors must
see. For file edits:

```bash
uv run --script ../manuscript-deslop/scripts/style_profile.py BEFORE.md # before editing: where the patterns are
uv run --script scripts/guard.py BEFORE.md AFTER.md [--json report.json] [--md report.md] [--moved-to FILE]
uv run --script scripts/guard.py AFTER.md --against HEAD                # in git: the last commit is BEFORE
uv run --script ../manuscript-deslop/scripts/style_profile.py AFTER.md --before BEFORE.md --check [--keep ID] [--sample AUTHORS.md]
```

Retain the before/after copies, guard JSON, style reports and adjudication in this skill's run folder under the shared [project-output contract](../manuscript-integrity-check/references/project-workflow.md). Link the report and consequential comparisons; preserve flags and failed checks even when a later revision resolves them.

The guard keeps its whole-text counts of numbers, citations, identifiers and terms, and also aligns the
sentences of the two versions (split, merged and moved sentences included). For each sentence it reports,
with section and line, a claim that rose or fell on the causal or evidential ladder, novelty or generality
wording, a scope qualifier, limiting or concessive word ("only", "albeit", "despite"), null result or
evidence-status word that disappeared, and a number, citation or identifier the sentence did not have. Exit 1
marks a protected change: a count change, a stronger claim, a lost qualifier or a token new to its paragraph.
Lowered claims and moved tokens are warnings. When something asked for a claim change (the authors' request, a
confirmed finding, a referee's comment), list each one in a small file (`passage`: words from the sentence,
`finding`: what asked for it) and pass `--authorised FILE`: those changes are marked with what asked for them, and
any other claim that widened still fails, so restore its wording yourself; the authors are not asked. Numbers and
citations never pass this way. `--allow-strengthening` authorises every claim change at once, only for a request
that covers the whole text. With `--relocated`, a
scope qualifier, limiting or concessive word, null result or evidence-status word that left its sentence is a
warning instead of exit 1 when a new or changed sentence, in the edited text or a `--moved-to` file, holds the
same marker; a caveat reworded on the way, or one that no such sentence holds, still exits 1, and so does any lost
number, citation or identifier. Use it only when the edit moves caveats on purpose (manuscript-story does). The
guard does not prove semantic equivalence. Resolve false positives yourself when meaning is unchanged and rerun only checks
affected by the edit. Revision markers
(`<!-- @rev ... -->`) stay where they are and are added or updated only as the project's written rules say
([author priorities](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review));
the guard ignores them. Where the project keeps them, an applied edit bumps or opens its segment through
`manuscript-revision-marks`, signed with the name of whoever wrote the round. Return the edited text or a concise file-change summary, the warnings that stand, the
patterns kept on purpose and unresolved content questions; detailed change tables are on request.

For a claim that needs source verification, use `manuscript-reference-check`. Use `manuscript-policy-fit`
when an edit depends on clinical, ethics, privacy or regulatory applicability. Venue formatting and
required AI-use statements belong to `manuscript-journal-adapt`; editing prose alone does not trigger them.

If the chosen journal restricts AI drafting or editing, still make the edit the authors asked for, at full
strength. Add at most one sentence naming the restriction and its practical consequence, and do not raise it
again ([authors first, journals second](../manuscript-integrity-check/references/author-priorities.md#the-author-decides-authors-first-journals-second)).
The claim ceiling is not such a restriction: it protects the science and holds for every request.

## What to show the authors

Follow [Writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors).
For each change or flagged sentence, quote the sentence as it stands (before and after, for a change) and name
its section ("Discussion, Limitations"; "section 5.1, Limitations of Variant Annotation"). A line number may
follow in parentheses; a bare "L318", a file:line or a revision-marker ID never stands in for the quote. Say
what the guard found in its own plain words ("no number, citation or claim strength changed"; "the limiting
word 'albeit' was dropped from the Conclusion"), not "protected change", "rung", "watched" or an exit code, and
do not send the authors to `guard.json` or to this skill's reference files. A catalogue ID may follow a plain
description in parentheses ("participle tails cut in four places (A9)"), never replace it.

List what the edit could not settle by when it can be done
([Order the work by when it can be done](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done)),
using that section's group labels and leaving out empty groups. A claim that outruns its evidence, a number or
citation the sentence needs and the text does not give, or a qualifier that may be missing goes under "Fix now"
with the question for the authors. The prose changes themselves, and choices of wording left to the authors,
belong to "Then the writing". Word limits and required sections wait for "Once you have chosen the journal".
Stripping revision markers, the declarations and the AI-use statement are end-stage work for "Before
submission, once the code is final" and are never called blockers for a draft.

## Revision inventory

When content changes are expected (a revision after review, a co-author's version, a venue adaptation, the
contract's author-supplied content), list them instead of failing on them:

```bash
uv run --script scripts/guard.py ORIGINAL.md REVISED.md --revision --json inventory.json
uv run --script scripts/guard.py REVISED.md --against v1-submitted --revision
uv run --script scripts/guard.py ORIGINAL.md MAIN.md --revision --moved-to SUPPLEMENT.md  # text moved to another file is moved, not removed; repeat --moved-to per file
```

It reports every number, citation, identifier, claim-strength, scope, null-result and evidence-status change
with section and line, in the same JSON fields as an edit (`sentence_changes`, `alignment`, `summary`), and
exits 0, except with `--authorised`: a claim that widened with no matching entry then exits 1. `manuscript-reviewer-response` checks each listed change against the response letter;
`manuscript-journal-adapt` and `manuscript-policy-fit` use it to show what their authorised edits changed.
Present the changes; do not judge them as errors, since the authors chose them. A whole-paper revision can
list hundreds of changes: give the authors the claim changes first, each quoted with its section, then the
number, citation and identifier changes grouped by section, and write the full Markdown report beside the
revised manuscript (`<manuscript stem>.changes.md`, or where they say) and give its path. A count of changes
alone tells them nothing they can check.

## Optional independent reflection

Use [reflection-mode.md](../manuscript-deslop/references/reflection-mode.md) only when the user requests reflection mode or
independent agents. A new critic subagent each round reads only a saved copy of the current text in its
own workspace, never the authors' self-assessment, the writer's notes or what the last round fixed, and
cites a catalogue ID for each finding so every fix is traceable. Each critic's brief and output are kept
and registered like any seat's (`runs.py add --role critic --isolation fresh-agent`); when the authors chose
another model, the critic runs on it ([manuscript-other-models](../manuscript-other-models/SKILL.md)). The summary for the authors describes each kind of change in
plain words, with the ID only in parentheses. The guard runs after each writer pass. The loop stops after a
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
[detector-evidence.md](references/detector-evidence.md) for limitations. Treat flagged passages as places
to reread; use them in a critic pass only if that mode was requested. Tell the authors what a score measures,
with the detector's name in parentheses ("the detector's estimate that a model wrote the passage was 0.91
(ModernBERT detector)"), and quote each flagged passage's opening with its section.

Edit for a concrete writing problem, never for a detector threshold. Do not insert errors, manufacture
variation or change scientific meaning to influence a score. Leave a flagged passage unchanged when
there is no identifiable problem. A detector result is not evidence of authorship.

## Shared tools

Commands are relative to this skill directory. Keep the plugin's companion skills together:
`manuscript-deslop` owns the style profiler and catalogue, shared with the integrity skill's pre-commit
hook and this skill's optional detectors. `guard.py` is also available to
venue adaptation, policy-fit edits and reviewer responses; those callers use the same copy of the
preservation tool and the same ladders. They and every report to the authors also run the smell check
(`../manuscript-deslop/scripts/style_profile.py TEXT --check`, with `--report` for a report), against the same catalogue.
