---
name: manuscript-improve
description: >-
  Improve a manuscript from draft to submission by coordinating scientific review, reference and
  reporting checks, project-configured simulated peer review, a review of the figures as printed, policy
  fit, journal selection, prose editing, removing formulaic AI phrasing, a check of how the paper reads to
  its readers, and journal adaptation,
  ending with the corrected version of the manuscript and a dashboard of what the run found, changed and
  left open, and later the response to referees. Use for explicit whole-workflow requests or
  requests that combine several services, including optional section-by-section work, stage review with
  before/after comparisons, or an "interview me" decision process. Use an individual manuscript skill for
  one service: "prepare this for journal X" alone belongs to manuscript-journal-adapt.
---

# Improve a manuscript from draft to submission

Help the authors publish sound work within their actual resources. Read the shared
[author priorities](../manuscript-integrity-check/references/author-priorities.md), including
[scope, iteration and review](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review).
This skill coordinates the companion skills; load each when its stage is relevant and keep one set
of findings, verified sources and author decisions across the workflow. When the work spans several
sessions or the authors ask, the optional [shared record](../manuscript-integrity-check/references/manuscript-record.md)
holds the venue, study designs, completed checks and open issues so that later stages reuse them.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run. This applies to direct invocations too.

## Defaults and author controls

Before work, resolve the manuscript project with
`uv run --script ../manuscript-integrity-check/scripts/project.py resolve SOURCE --json`
and follow the effective edit policy and saved output destination. The `edits` setting is the run's mode,
and the first progress update names it in plain words:

- **Report only** (`propose`): no change to the manuscript; every fix is a proposal.
- **Routine fixes** (`conservative`, the default): apply corrections that keep the meaning, and the story
  stage's edits that keep the authors' recorded direction; propose substantive revisions for approval.
- **Every change** (`apply`): apply substantive revisions too, within the authors' direction.

Every mode ends with the corrected version as a separate file (see the end of this skill), so the
authors can read the whole improved paper before they accept it. A request to use this skill or "improve
the manuscript" does not change the mode.

Work across the **whole paper** by default and carry the authorised improvement task through its relevant
stages. Do not substitute an Abstract-only or sampled review. A request for one service belongs to that
focused skill and does not activate this full workflow.

Use the manuscript and conversation first. Establish the contribution, existing validation, available
resources and target journal where known. Ask only for missing facts that change a decision. Interviews,
section-by-section work and stage checkpoints are opt-in; proposal-before-application follows the `edits`
policy or an explicit request. The author can change these controls during the workflow without a new
setup questionnaire. In stage-by-stage mode, each stage still covers the whole paper unless narrowed.

Preserve the Abstract's purpose and the author's chosen emphasis for every paper type. Numerical results
in the body do not by themselves call for a new paragraph of metrics in the Abstract. Follow the shared
author-priority rules on Abstract content and on showing consequential changes: quote the exact
before/after text in the chat as the changes are made, even when the full report goes to a file.

Retain the pre-edit version. Make authorised edits reviewable through a diff or before/after text; when
the author requests comparisons at each section or stage, show them before proceeding. If they request
review before application, keep proposed changes separate from the working manuscript until accepted.
For stages with no text changes, present the findings, choices and their consequences instead.

## Coordinate the work

Use this sequence as a starting point, adapting the order to dependencies and existing work. It follows
[Order the work by when it can be done](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done):
the science and the evidence first, then the writing, then the work that depends on the chosen journal,
and last what waits until the code, data and results are final. A known venue restriction or
unaffordable validation requirement can justify settling journal fit before editing.

| Stage | Companion skills and outcome |
|---|---|
| Review the draft and evidence | [manuscript-integrity-check](../manuscript-integrity-check/SKILL.md) identifies scientific and submission problems, including numbers and their arithmetic; [manuscript-reference-check](../manuscript-reference-check/SKILL.md) verifies the identity of every reference and checks support for claims in its priority order (load-bearing claims, borrowed numbers, "first" claims); [manuscript-reporting-check](../manuscript-reporting-check/SKILL.md) checks the reporting guidelines that fit the study design, statistics reporting, and whether data, code and software are available. Run each mechanical check once and reuse it. |
| Anticipate referees (project policy; automatic by default for this full workflow) | [manuscript-peer-review](../manuscript-peer-review/SKILL.md) gives referee-style judgement on contribution, design and claims, reusing the checks above rather than repeating them. Its author-required items are the authors' decision; its fixable-in-text items feed the revision stage, each with the placement that costs readers least. |
| Review the figures and tables | [manuscript-figures](../manuscript-figures/SKILL.md) reviews every figure and table in the paper and its supplement: it renders each figure at its printed size and looks at it (legibility at the column width, colour for colour-blind readers, clutter, resolution), measures each table (width at the table font, units, precision, empty cells), checks each against its caption, the text and the code that draws it, and recommends what to keep, change, move to or from the supplement or add, each with its reason. Main-text items get the full review, supplementary ones a lighter one. It uses the chosen journal's figure rules, or what the ladder's venues share, once journal fit has named them; before journal fit has run, it measures against the common defaults (single- and double-column widths, 6 pt, 300 dpi) and reruns the measurement once the journal's rules are named. Which figures the paper has is the authors' decision; caption and citation fixes join the revision like any text edit. A figure-led paper is offered the figures referee in the panel, and every referee and reader sees the figures as images. |
| Establish policy and journal fit | [manuscript-policy-fit](../manuscript-policy-fit/SKILL.md) resolves study-specific scope and applicable requirements when relevant. [manuscript-journal-select](../manuscript-journal-select/SKILL.md) gives a preprint ladder and a journal ladder ordered by the authors' priorities, and what every venue on them asks for, if no target is settled or the author requests alternatives. Reuse an existing choice. |
| Revise the paper | Correct supported defects within the authorised scope and use [manuscript-prose-edit](../manuscript-prose-edit/SKILL.md) for clarity and author voice. Preserve results and qualifications; distinguish substantive claim corrections from language changes. Obtain author facts or decisions when a correction depends on them, and insert facts the authors supply under the prose-edit contract's "Author-supplied content" rule (§1). |
| Remove formulaic phrasing | [manuscript-deslop](../manuscript-deslop/SKILL.md) reads the whole revised paper for formulaic LLM phrasing, boilerplate and empty rhetoric and removes it under the edit policy. The prose edit's smell check only keeps its own edits from adding patterns; this stage removes the ones the draft already had. Run it after the prose edit and before the story check, on the same working copy. Its findings are writing findings, never scientific errors. |
| Check how it reads | [manuscript-story](../manuscript-story/SKILL.md) reads the revised paper as its readers do, against the version before this workflow, and repairs the story within the direction the authors recorded: a stake in the opening, one headline per result, real output shown, caveats kept but placed where they cost readers least. A change of direction is only offered as options. Run it after the deslop stage, and whenever referee-driven changes have accumulated. |
| Prepare for the chosen journal | Use [manuscript-journal-adapt](../manuscript-journal-adapt/SKILL.md) for the actual article type and submission stage: scope, length and abstract format, required sections and the reporting checklist that journal asks for. Statements whose contents depend on final code and results are drafted now only where they can read complete; otherwise they are held, with their questions as comments, until the facts exist. Resolve the target before making incompatible journal-specific changes; before that, only the requirements every venue on the ladders shares are adapted. |
| Verify the revision | Recheck affected claims, references, cross-section consistency and applicable submission requirements. Compare against the retained version with `../manuscript-prose-edit/scripts/guard.py ORIGINAL FINAL --revision`, for the working copy and for the corrected version (`proposed.md`), resolve unintended drift and identify what remains unverified. Run the required smell check on the revised text, `../manuscript-deslop/scripts/style_profile.py FINAL --before ORIGINAL --check`, and read it against the pattern list the check prints. Compare how it reads with `../manuscript-story/scripts/reader_metrics.py FINAL --before ORIGINAL` and show the authors what moved. The corrected version is built once the dashboard has collected and adjudicated the findings, and verified here before the dashboard is rendered (see "Build the corrected version" below). |
| Show what the workflow found and did (always, last) | [manuscript-dashboard](../manuscript-dashboard/SKILL.md) collects every stage's `findings.json`, merges the problems several skills found and dismisses what did not hold; once the corrected version is built and verified, it renders the dashboard: problems by kind, severity, stage and section, the annotated manuscript, the corrected version as track changes, machine-writing patterns by type in each version, coverage, edits as diffs, the panels, and what could not be checked. |
| Finish for submission, once the code, data and results are final | Archive the release and quote its DOI and version, finalise the data availability statement, declarations, AI-use statement and cover letter with manuscript-journal-adapt, remove revision markers if the authors want that, and run the submission-package check in manuscript-integrity-check. Do this when the authors say they are about to submit; until then these items are listed last and are not blockers for the draft. |
| After a decision | [manuscript-reviewer-response](../manuscript-reviewer-response/SKILL.md) plans the revision from the decision letter in the referees' own numbering, drafts the response letter and verifies that the revision addresses each comment. This is a separate request, after real reviews arrive. |
| Track who revised what (where the manuscript keeps revision marks) | [manuscript-revision-marks](../manuscript-revision-marks/SKILL.md) keeps the `@rev` marks current through every stage, lists the AI edits no person has reviewed and the prose no round has read, and builds the PDF from the clean copy against the page limit; [manuscript-mark-people](../manuscript-mark-people/SKILL.md) sets up who counts as a person. Never introduced into a project that does not use marks unless the authors ask. |

**Simulated referees and readers are independent, and the coordinator starts them.** Every referee seat,
reader, defender and critic (the deslop reflection loop's) is a fresh agent whose whole context is its
brief, never a fork of this conversation, as [Independent readers and referees](../manuscript-integrity-check/references/project-workflow.md#independent-readers-and-referees) requires.
Delegated agents often cannot start agents of their own, so start the seats, readers and critics from this
session even when another agent prepares the stage's workspaces and briefs; a stage agent never reads as the panel itself because it could not start one. Give
them nothing from this run: not the findings so far, not the authors' messages, not what the run changed.

Stages that write proposals (figures, policy fit, story, prose edit, deslop, journal adaptation) work from the review stages'
confirmed findings: run them after those stages, or reconcile their proposals with the findings before
handover, so that no proposal restates what a check refuted (a feature the code lacks, a peak that was
not measured). They copy each proposal's before-text from the current working copy, and an addition names
the passage it follows (`anchor`), so the corrected version can place it. A stage that edits a passage
another stage has a pending proposal for adds its version as a proposal instead of applying it. Where two
stages rewrite the same passage, the dashboard lists them as competing; give the authors one choice per
passage rather than stacked edits. Policy fit's venue-specific part runs after journal selection has
named the journals.

Select only relevant work within these stages. A software paper does not automatically need clinical
review, a settled journal does not need a new shortlist, and already verified references do not need
repeated lookups. Keep whole-paper coverage even when the work is chunked internally. If the author
chooses section iteration, retain manuscript context and perform applicable cross-section checks after
the selected work; do not report excerpt-level checks as whole-paper readiness.

## Handle decisions and requested pauses

When asked to "interview me", help the author decide among concrete options for the current stage. Use
the journal-selection interview guide for venue decisions and the relevant companion instructions for
scientific or editorial decisions. A request to interview the author about journal choice does not
require interviewing them again about every prose edit.

At a requested checkpoint, give the section or stage covered, the before/after comparison or assessment,
the reason for consequential changes, and decisions still needed, written as the final summary below is.
Then stop before the next unit. A request to change one step does not discard previously accepted edits or
settled decisions. Revisit dependent work only when the new decision changes it.

**Finish all independent work before yielding for decisions.** A pending approval or missing fact blocks
only dependent work. Follow the shared rule in
[Minimum useful work](../manuscript-integrity-check/references/author-priorities.md#minimum-useful-work):
collect decisions, continue every applicable check and permitted edit across the requested scope, and
prepare exact proposed text with its evidence. Use asynchronous questions when supported; otherwise
defer blocking question tools until the independent work is finished. Do not turn the `conservative`
policy into a sequence of question-and-answer stops. At handover, distinguish completed work from the
pending proposals and their dependent steps. Silence never grants approval. Do not invent data,
citations, approvals or accounts of AI use.

## Finish with a reviewable result

**Build the corrected version.** The working copy holds only what the mode applied; the authors also get
the whole improved paper to read. It is built from the adjudicated inventory, so the order at the end of
a run is: collect and adjudicate the findings (manuscript-dashboard, steps 1 and 2), build the corrected
version, verify it, then render the dashboard. Write
`RUN/manuscript-improve/revision-choices.json`: for each group of competing proposals, the one you
recommend (`prefer`); the proposals to hold back with the reason (`hold`: a statement for a journal not
yet chosen, a decision only the authors can make, a proposal whose substance is a fact only they have);
and an anchor for an addition its stage left without one. No placeholder goes into the text
([Questions for the authors are comments, never text](../manuscript-integrity-check/references/author-priorities.md#questions-for-the-authors-are-comments-never-text)):
a question about a proposal is its `comment`, one about existing text a decision in the report. Then run, from this skill directory:

```bash
uv run --script scripts/revise.py ORIGINAL WORKING RUN/manuscript-dashboard/findings.json \
  --choices RUN/manuscript-improve/revision-choices.json --output-dir RUN/manuscript-improve/revision
```

It locates every applied edit in the working copy and stops when undoing them does not give the original,
so an unrecorded edit cannot hide. It then applies the chosen proposals in manuscript order:
`proposed.md` is the corrected version, `changes.md` the same as CriticMarkup with the questions for the
authors as comments, `revision.json` what was applied, held, left as an alternative or not placed, each
with its reason, and the questions. A `[AUTHORS: ...]` note a stage left in a proposal is lifted out of its
text into a comment; a proposal that was only a question is listed, not placed. Any note already in the
working copy (from an applied edit) is listed as `notes_in_text`: delete it there, and say so in the
summary. The dashboard marks each questioned passage in yellow and lists the questions. A proposal is never dropped
silently; one that cannot be placed is listed, and the authors see it. The corrected version is a
proposal too: the working manuscript changes only as the mode allows or the authors accept. Run the
verification checks below on `proposed.md` as well, and give the dashboard the folder
(`--revision RUN/manuscript-improve/revision`), so its Corrected version tab shows the track changes.
Hand the authors a copy beside their manuscript as `<manuscript stem>.proposed.md`, never over their file.

Return the revised manuscript, the corrected version and the proposals with one concise summary for the whole workflow,
linking its run index and each companion skill's report and evidence folder. Retain contradictions,
failed checks and panel reports; the combined summary never replaces per-skill artifacts. Write it as
[Writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)
describes: each main change quoted before and after with its section, the selected journal's applicable
rules quoted with the URLs of their pages, plain words, acronyms spelled out and full sentences. Put the
authors' decisions together in one place, a journal-policy conflict among them, named once.

Group what remains, including checks that could not be completed, under the four labels of
[Order the work by when it can be done](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done),
current-work groups first, merging the companion skills' findings by when they can be done rather than by
skill. End-stage items (archive DOIs and release tags, final versions, declarations, the AI-use
statement, the cover letter, removing revision markers, the upload check) are not blockers for a draft
and do not count against its readiness unless the authors say they are about to submit.

Make the original-to-final comparison accessible. In an iterative workflow, state the current accepted
version and next requested step using the conversation or existing project conventions; no new tracking
files are required.

Every stage writes `findings.json` beside its report, as
[stage findings](../manuscript-dashboard/references/stage-findings.md) describes, including the stages run
by reviewer agents. The last step of every run of this workflow is
[manuscript-dashboard](../manuscript-dashboard/SKILL.md) on the same run: collect the stages' findings,
merge what several skills found into one record each, dismiss what did not hold, and render the
dashboard, with the corrected version, into `RUN/manuscript-dashboard/`, and the same as an annotated Word
document (`export_docx.py`: tracked changes by stage, the problems and questions as comments) for readers who
work in Word or Google Docs. Link the dashboard first in the
summary and the corrected version second: they are how the authors and their colleagues see what the
workflow caught, changed and left open, with the actual coverage. Reuse the evidence rather than rerunning the review. A stage that could not run still appears,
with its reason; its unfound problems are unknown, not zero.

Optional detector checks keep their companion skill's request boundary. Formal referee simulation uses
project `peer_review`: `auto` by default in this full workflow, `on-request` only on request, or `off`;
record a skipped stage with its reason. A focused edit never activates this full workflow or its panel.
Completing this workflow prepares the manuscript; it does not authorise submitting, emailing or publishing.
