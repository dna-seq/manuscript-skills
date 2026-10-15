---
name: manuscript-improve
description: >-
  Improve a manuscript from draft to submission by coordinating scientific review, reference and
  reporting checks, optional simulated peer review, policy fit, journal selection, prose editing and
  journal adaptation, and later the response to referees. Use for explicit whole-workflow requests or
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

## Defaults and author controls

Work across the **whole paper** by default and carry the authorised improvement task through its relevant
stages. Do not substitute an Abstract-only or sampled review. A request for one service belongs to that
focused skill and does not activate this full workflow.

Use the manuscript and conversation first. Establish the contribution, existing validation, available
resources and target journal where known. Ask only for missing facts that change a decision. Interviews,
section-by-section work, stage checkpoints and proposal-before-application are opt-in. The author can
request or change these modes during the workflow; follow the shared controls without requiring a new
setup questionnaire. In stage-by-stage mode, each stage still covers the whole paper unless narrowed.

Retain the pre-edit version. Make authorised edits reviewable through a diff or before/after text; when
the author requests comparisons at each section or stage, show them before proceeding. If they request
review before application, keep proposed changes separate from the working manuscript until accepted.
For stages with no text changes, present the findings, choices and their consequences instead.

## Coordinate the work

Use this sequence as a starting point, adapting the order to dependencies and existing work. A known
venue restriction or unaffordable validation requirement can justify settling journal fit before editing.

| Stage | Companion skills and outcome |
|---|---|
| Review the draft and evidence | [manuscript-integrity-check](../manuscript-integrity-check/SKILL.md) identifies scientific and submission problems, including numbers and their arithmetic; [manuscript-reference-check](../manuscript-reference-check/SKILL.md) verifies the identity of every reference and checks support for claims in its priority order (load-bearing claims, borrowed numbers, "first" claims); [manuscript-reporting-check](../manuscript-reporting-check/SKILL.md) checks the reporting guidelines that fit the study design, statistics reporting, and whether data, code and software are available. Run each mechanical check once and reuse it. |
| Anticipate referees (when requested) | [manuscript-peer-review](../manuscript-peer-review/SKILL.md) gives referee-style judgement on contribution, design and claims, reusing the checks above rather than repeating them. Its author-required items are the authors' decision; its fixable-in-text items feed the revision stage. |
| Establish policy and journal fit | [manuscript-policy-fit](../manuscript-policy-fit/SKILL.md) resolves study-specific scope and applicable requirements when relevant. [manuscript-journal-select](../manuscript-journal-select/SKILL.md) recommends feasible journals if no target is settled or the author requests alternatives. Reuse an existing choice. |
| Revise the paper | Correct supported defects within the authorised scope and use [manuscript-prose-edit](../manuscript-prose-edit/SKILL.md) for clarity and author voice. Preserve results and qualifications; distinguish substantive claim corrections from language changes. Obtain author facts or decisions when a correction depends on them, and insert facts the authors supply under the prose-edit contract's "Author-supplied content" rule (§1). |
| Prepare for the chosen journal | Use [manuscript-journal-adapt](../manuscript-journal-adapt/SKILL.md) for the actual article type and submission stage, required statements and materials. Resolve the target before making incompatible journal-specific changes. |
| Verify the revision | Recheck affected claims, references, cross-section consistency and applicable submission requirements. Compare against the retained version with `../manuscript-prose-edit/scripts/guard.py ORIGINAL FINAL --revision`, resolve unintended drift and identify what remains unverified. Before upload, run the submission-package check in manuscript-integrity-check. |
| After a decision | [manuscript-reviewer-response](../manuscript-reviewer-response/SKILL.md) plans the revision from the decision letter in the referees' own numbering, drafts the response letter and verifies that the revision addresses each comment. This is a separate request, after real reviews arrive. |

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
the reason for consequential changes, and decisions still needed. Then stop before the next unit. A
request to change one step does not discard previously accepted edits or settled decisions. Revisit
dependent work only when the new decision changes it.

In the default workflow, continue routine authorised work without approval stops at each section or
stage. Keep substantive scientific decisions with the author and continue independent work while a
material answer is pending. Do not invent data, citations, approvals or accounts of AI use.

## Finish with a reviewable result

Return the revised manuscript or requested proposals, a concise account of the main changes, the
selected journal and applicable requirements where relevant, and remaining material questions or checks
that could not be completed. Make the original-to-final comparison accessible. In an iterative workflow,
state the current accepted version and next requested step using the conversation or existing project
conventions; no new tracking files are required.

Optional detector checks and independent reviewer agents keep their companion skills' request boundaries.
Completing this workflow prepares the manuscript; it does not authorise submitting, emailing or publishing.
