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
As a stage of `manuscript-improve` (or run alone), finish with the [end-of-stage checklist](../manuscript-integrity-check/references/project-workflow.md#end-of-stage-checklist):
record each applied edit with `runs.py change` (routine fixes grouped as one record per paragraph or section) and
write `findings.json` with the `PE` prefix.

## Edit and check the result

Read [prose-edit-contract.md](references/prose-edit-contract.md) for the editing procedure and preservation
rules, and [section-guide.md](references/section-guide.md) when a section's purpose matters. Which section a
detail belongs in is the shared [section roles](../manuscript-integrity-check/references/section-roles.md): an
edit never brings a procedure, a threshold or a measured count into the Abstract or the Introduction to make it
concrete (a rounded figure and a pointer at most), and a measured result it finds in Methods, or procedure in
Results, is reported as *Misplaced detail* with the section it moves to. Apply
[manuscript-deslop](../manuscript-deslop/SKILL.md) for the pattern check: it owns the catalogue,
false-positive exceptions and style profiler. **The smell check is required for every edit**, including a
short pasted passage saved as before/after files. Run its counts before and after editing, then read the
edit against the full catalogue list. The check judges only what the edit added (a pattern, or a third use
under a heading); runs of a pattern the draft already had are the deslop stage's work. When this skill runs on
its own rather than as a stage of `manuscript-improve`, whose deslop stage follows it, do not leave those runs
unmentioned: read them from the before-edit profile and the reading pass, and suggest a cleanup under "Then the
writing" (see [What to show the authors](#what-to-show-the-authors)). Suggest only; the edit removes them only
when the request already covers that wording, as a copy edit for concision does. Resolve what the check lists,
or keep a reviewed use with `--keep ID@HEADING` (`--keep ID` keeps it everywhere), record it in this skill's
run folder with `--record-keeps RUN/manuscript-prose-edit/kept-patterns.txt`, and explain the retained
sentences to the authors. A sentence that works can stay.

Use available author samples (`--sample`) when voice matching helps; do not require samples for an
ordinary edit. Use this plugin's deslop workflow for these checks; other installed humanizers can have
rules that conflict with scientific writing or the preservation contract.

Make the authorised edits, preserve scientific meaning and review the diff in context. The contract's
**claim ceiling** holds for every request, including "make it punchier" or "sound more confident": improve
the prose, never raise a claim's certainty, causality, novelty, generality or scope
([claim-ladders.md](references/claim-ladders.md)). Narrowing a claim to what its evidence shows follows the
`edits` setting like any claim correction: under `conservative` and `apply` it is applied when a confirmed
finding supports it, by rewording (never by deleting the claim) and shown before and after; under `propose` it
is proposed. Only the choice between new work and a narrower claim is the authors'. For file edits:

```bash
uv run --script ../manuscript-deslop/scripts/style_profile.py BEFORE.md # before editing: where the patterns are
uv run --script scripts/guard.py BEFORE.md AFTER.md [--json guard.json] [--md guard.md] [--moved-to FILE]
uv run --script scripts/guard.py AFTER.md --against HEAD                # in git: the last commit is BEFORE
uv run --script scripts/guard.py BEFORE.md AFTER.md --only Discussion   # a request for named sections; repeat --only
uv run --script ../manuscript-deslop/scripts/style_profile.py AFTER.md --before BEFORE.md --check [--keep ID@HEADING] [--record-keeps RUN/manuscript-prose-edit/kept-patterns.txt] [--sample AUTHORS.md]
```

Retain the before/after copies, guard JSON, style reports and adjudication in this skill's run folder under the shared [project-output contract](../manuscript-integrity-check/references/project-workflow.md). Link the report and consequential comparisons; preserve flags and failed checks even when a later revision resolves them.

The guard keeps its whole-text counts of numbers, citations, identifiers and terms (a term added to a paragraph
that already has it, such as a pronoun given its noun, is not counted), and also aligns the sentences of the two
versions (split, merged and moved sentences included). For each sentence it reports, with section and line, a
claim that rose or fell on the causal or evidential ladder, novelty or generality wording, a scope qualifier,
limiting or concessive word ("only", "albeit", "despite"), null result or evidence-status word that disappeared,
a number, citation or identifier the sentence did not have, and a declaration only the authors can make
(consent, ethics approval, competing interests, funding, an author's contribution) that was written, reworded or
removed. Exit 1 marks a protected change: a count change, a stronger claim, a lost qualifier, a token new to its
paragraph or moved to another paragraph, or a declaration. Warnings, which the authors still see: a lowered claim
(protected instead in a negated sentence), an added qualifier, a changed negation, a deleted sentence, and a
token moved within its paragraph or into a `--moved-to` file. A deleted sentence that was only a stock phrase is
not listed; one that said more is listed as "cut as a stock phrase". When the request named sections ("edit the
Discussion"), pass each with `--only`: a sentence changed anywhere else fails, so restore it.

After an edit to the Abstract, the title or the Conclusions, or any edit that changes a claim, check the summary
against the body with `uv run --script scripts/guard.py PAPER.md --summary`: it fails on a summary sentence that
claims more than the body sentences about the same thing, or leaves out a scope, limit, null result or evidence
status the closest one states (deslop's I6). Bring the summary down to what the body shows, or give it the
qualifier; a summary sentence no body sentence is close to is listed for a reading, never failed.

When something asked for a claim change or a declaration (the authors' request, a confirmed finding, a referee's
comment), list each one in a small file and pass `--authorised FILE`. Each entry gives `passage`, at least three
words in a row copied exactly from the sentence before or after the edit, and `finding`, what asked for it (a
referee comment id such as R2.4 may be given as `comment`). Those changes are marked with what asked for them,
and any other widened claim or changed declaration still fails, so restore its wording yourself; the authors
are not asked. Numbers and citations never pass this way. `--allow-strengthening` authorises every claim change
at once (never a declaration), only for a request that covers the whole text.

`--relocated` is for an edit that moves caveats on purpose (manuscript-story's). A scope, limiting or
concessive, null-result or evidence-status marker that left its sentence, or went with a deleted one, is a
warning when another sentence of the same top-level section, about the same thing (at least two content words
in common), states it, whether it gained the marker in the edit or already had it. A scope qualifier or
evidence status lost from the Abstract or the Introduction stays protected, and so does a caveat found only in
another section or a `--moved-to` file, one reworded on the way, and every citation and identifier. A number
moved to a sentence of its section about the same thing, and a new headline that names nothing its paragraph
lacks and claims no more than it, are warnings. `--relocated-in RUN/manuscript-story` limits these moves to that
stage's own changes (manuscript-improve's final check uses it). The guard does not prove semantic equivalence.
Resolve false positives yourself when meaning is unchanged and rerun only checks affected by the edit. Revision
markers follow the shared rule ([author priorities](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review),
"Revision marks"); the guard ignores them. Return the edited text or a concise file-change summary, the warnings that stand, the
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
using that section's group labels and leaving out empty groups. A claim that outruns its evidence goes under
"Fix now", narrowed or proposed as the `edits` setting says (above); the authors decide only between new work
and the narrower claim. A number or citation the sentence needs and the text does not give, or a qualifier that
may be missing, goes there too, as a comment only the authors can answer. The prose changes themselves, and
choices of wording left to the authors, belong to "Then the writing". So do the formulaic patterns the edit left
in place when this skill ran on its own: name each kind in plain words with how often it occurs, quote one
example with its section, and offer a pass with [manuscript-deslop](../manuscript-deslop/SKILL.md) on the same
text. Leave out the uses the edit kept on purpose, which are already explained there, and say nothing when the
draft had no such patterns. Word limits and required sections wait for "Once you have chosen the journal".
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

It reports every number, citation, identifier, claim-strength, scope, null-result, evidence-status and
declaration change with section and line, in the same JSON fields as an edit (`sentence_changes`, `alignment`,
`summary`), and exits 0; with `--authorised` it exits 1 when a claim widened, or a declaration was written,
changed or removed, with no matching entry. `manuscript-reviewer-response` checks each listed change against the response letter;
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
to reread; in reflection mode, when it was requested, they go to the writer in the first round, never to the
critic. Tell the authors what a score measures,
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
