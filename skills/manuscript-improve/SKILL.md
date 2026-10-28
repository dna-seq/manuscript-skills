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

- **Every change that needs no decision of the authors** (`apply`, the default): apply the routine and
  evidence-backed fixes and the substantive revisions within the authors' direction (restructuring, a new
  emphasis, additions, the deslop and story cuts). What stays a proposal or a decision is only what needs the
  authors: a fact only they have (the question is the proposal's comment), a change of direction, which
  figures the paper has, new analyses or data, a policy conflict, and a claim widened with nothing asking for
  it (the claim guard restores it). The authors read the applied changes in the changes workbook and the
  decisions in the Word review, not as one comment each.
- **Routine and evidence-backed fixes** (`conservative`, more caution): apply corrections that keep the
  meaning, the corrections that the evidence for a confirmed finding settles (a number, a citation, a claim
  reworded to what the evidence shows), and the story stage's edits that keep the paper's direction;
  substantive revisions no confirmed finding requires are proposals in the corrected version.
- **Proposals only** (`propose`, most caution): no change to the manuscript; every fix is a proposal the
  authors approve one by one, and the Word review is the whole review (every edit tracked, every problem a
  comment). This is the only mode with per-item approval.
- **Report only** (`none`): no change to the manuscript and no rewritten text. The review stages run as
  usual; the prose edit, deslop, story and journal-adaptation stages give their audits instead of edits; the
  revise stage, the corrected version and its verification and re-check are skipped. The run ends with the
  adjudicated findings, each with the kind of change that would fix it, the dashboard and its Word version.

"Fix everything", "apply all" or "accept all" applies the whole corrected version for this run, except the
[held decisions](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
(a change of direction, which figures the paper has, a venue's rules before the choice, new analyses or
data, facts only the authors have, a policy conflict), which are listed once at the end and hold nothing
else up.

The same update says which files the run will keep, from the `keep` setting: every intermediate file
(`everything`, the default), or the results with the rest packed into one archive (`results`), and how to
change it ("say 'keep only the results'"). When the preferences are still unanswered on first use, the
first update asks them as the [project contract](../manuscript-integrity-check/references/project-workflow.md#ask-once-for-a-manuscript-project)
describes and the run carries on with the defaults.

Every mode but report only ends with the corrected version as a separate file (see the end of this skill),
so the authors can read the whole improved paper and accept it in one step. A request to use this skill or
"improve the manuscript" does not change the mode.

The `versions` setting says where the applied edits go, and the first update names it too: into the
manuscript file (`in-place`, the default), or, with `immutable`, into the new version that
`runs.py version RUN` makes beside it before the first applied edit (`paper_v2.docx` becomes
`paper_v3.docx`), so that no earlier file changes. The working copy below is that new version.

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
| Take in the co-authors' comments (first, where the project keeps its rounds on Drive or the previous round has a `comments.yaml`) | [manuscript-coauthors](../manuscript-coauthors/SKILL.md) pulls the comments and suggested edits the co-authors left on the previous round's Google Docs into that round's ledger, says for each whether this round already answers it, and writes a `CA` finding for every comment still open, with what could be done; the later stages fix them like any other problem. After the corrected version is built it checks the ledger against it again (`comments.py status`, then `findings`), so the dashboard's "Co-authors' comments" section shows each comment as addressed, partly addressed, declined with the reason, or still open. A request to improve the paper covers this; it needs no separate ask. |
| Review the draft and evidence | [manuscript-integrity-check](../manuscript-integrity-check/SKILL.md) identifies scientific and submission problems, including numbers and their arithmetic; [manuscript-reference-check](../manuscript-reference-check/SKILL.md) verifies the identity of every reference and checks support for claims in its priority order (load-bearing claims, borrowed numbers, "first" claims); [manuscript-reporting-check](../manuscript-reporting-check/SKILL.md) checks the reporting guidelines that fit the study design, statistics reporting, and whether data, code and software are available. Integrity-check's upload check runs once on the draft's source and supplementary folder too, for the two findings that are urgent at any stage (text hidden for AI reviewers, a leaked secret). Run each mechanical check once and reuse it. |
| Anticipate referees (project policy; automatic by default for this full workflow) | [manuscript-peer-review](../manuscript-peer-review/SKILL.md) gives referee-style judgement on contribution, design and claims, reusing the checks above rather than repeating them. Only its choices between new work and a narrower claim are the authors' decision; its fixable-in-text items, a claim narrowed to its evidence among them, feed the revision stage under the `edits` setting, each with the placement that costs readers least. |
| Review the figures and tables | [manuscript-figures](../manuscript-figures/SKILL.md) reviews every figure and table in the paper and its supplement: it renders each figure at its printed size and looks at it (legibility at the column width, colour for colour-blind readers, clutter, resolution), measures each table (width at the table font, units, precision, empty cells), checks each against its caption, the text and the code that draws it, and recommends what to keep, change, move to or from the supplement or add, each with its reason. Main-text items get the full review, supplementary ones a lighter one. It uses the chosen journal's figure rules, or what the ladder's venues share, once journal fit has named them; before journal fit has run, it measures against the common defaults (single- and double-column widths, 6 pt, 300 dpi) and reruns the measurement once the journal's rules are named. Which figures the paper has is the authors' decision; caption and citation fixes join the revision like any text edit. A figure-led paper is offered the figures referee in the panel, and every referee and reader sees the figures as images. |
| Establish policy and journal fit | [manuscript-policy-fit](../manuscript-policy-fit/SKILL.md) resolves study-specific scope and applicable requirements when relevant. [manuscript-journal-select](../manuscript-journal-select/SKILL.md) gives a preprint ladder and a journal ladder ordered by the authors' priorities, and what every venue on them asks for, if no target is settled or the author requests alternatives. Reuse an existing choice after rerunning its ladders against today's catalogue and reading the venue rules nobody has read ([Reusing an earlier selection](../manuscript-journal-select/SKILL.md#reusing-an-earlier-selection)). |
| Revise the paper | Correct supported defects within the authorised scope and use [manuscript-prose-edit](../manuscript-prose-edit/SKILL.md) for clarity and author voice. Preserve results and qualifications; distinguish substantive claim corrections from language changes. Under the default, a correction the evidence for a confirmed finding settles is applied and shown; a correction that needs a fact only the authors have is a proposal with that question as its comment, never a placeholder. Insert facts the authors supply under the prose-edit contract's "Author-supplied content" rule (§1). |
| Remove formulaic phrasing | [manuscript-deslop](../manuscript-deslop/SKILL.md) reads the whole revised paper for formulaic LLM phrasing, boilerplate and empty rhetoric and removes it under the edit policy. The prose edit's smell check only keeps its own edits from adding patterns; this stage removes the ones the draft already had. Run it after the prose edit and before the story check, on the same working copy. Its findings are writing findings, never scientific errors. |
| Check how it reads | [manuscript-story](../manuscript-story/SKILL.md) reads the revised paper as its readers do, against the version before this workflow, and repairs the story within the paper's direction (the one the authors recorded or, until they confirm one, the one the text has now): a stake in the opening, one headline per result, real output shown, caveats kept but placed where they cost readers least. A change of direction is only offered as options. Run it after the deslop stage, and whenever referee-driven changes have accumulated. |
| Prepare for the chosen journal | Use [manuscript-journal-adapt](../manuscript-journal-adapt/SKILL.md) for the actual article type and submission stage: scope, length and abstract format, required sections and the reporting checklist that journal asks for. Statements whose contents depend on final code and results are drafted now only where they can read complete; otherwise they are held, with their questions as comments, until the facts exist. Resolve the target before making incompatible journal-specific changes; before that, only the requirements every venue on the ladders shares are adapted. |
| Verify the revision | Recheck affected claims, references, cross-section consistency and applicable submission requirements. Compare against the retained version (the clean copies for a marked manuscript), from this skill's folder, for the working copy and again for the corrected version (`proposed<ext>`): `uv run --script ../manuscript-prose-edit/scripts/guard.py ORIGINAL FINAL --revision --relocated-in RUN/manuscript-story --authorised RUN/manuscript-improve/requested-claims.yaml`, adding one `--moved-to FILE` for each supplement or response-letter file a stage moved text into. A caveat may move only where the story stage moved it, within its section; a scope qualifier never leaves an Abstract or Introduction claim. `requested-claims.yaml` lists each claim change that a confirmed finding or the authors' own request asked for, and each declaration (consent, ethics, competing interests, funding, contributions) whose facts the authors supplied (`passage`: at least three words in a row copied exactly from the sentence; `finding`: the finding id, or `comment`: a referee's comment id, or "authors' request"); write it from the findings yourself, and leave it as an empty list when nothing asked for a stronger claim. Exit 1 means a claim widened or a declaration changed with nothing asking for it: hold that proposal in the next attempt of the choices file (`"why": "widened claim, wording restored"`), or for an applied edit record the reverse change (`runs.py change` with the widened passage as before and the original wording as after; revise.py lists the pair as restored), rebuild as the next attempt and list each restoration in the summary. This needs nothing from the authors; those who want to approve every change themselves choose `edits: propose`. Run the required smell check on the revised text with every stage's reviewed exceptions, `uv run --script ../manuscript-deslop/scripts/style_profile.py FINAL --before ORIGINAL --check --keep-file RUN`, and read it against the pattern list the check prints. Compare how it reads with `uv run --script ../manuscript-story/scripts/reader_metrics.py FINAL --before ORIGINAL` and show the authors what moved; when the corrected version reads worse than the original, find the stage that caused it. Check that the title, Abstract and Conclusions still claim no more than the body: `uv run --script ../manuscript-prose-edit/scripts/guard.py FINAL --summary`; a sentence it fails is brought down to the body or given the body's qualifier, as a recorded edit. Check that no edit put a detail in the wrong section: `uv run --script ../manuscript-integrity-check/scripts/section_roles.py FINAL --before ORIGINAL`. Exit 1 lists each passage the edits made a candidate, such as a measured count, a range or the configuration of a comparison brought into the Abstract or the Introduction "to make it concrete", or a result moved into Methods; read each against the shared [section roles](../manuscript-integrity-check/references/section-roles.md) and, unless the venue's layout makes it right, hold or reverse that edit as for a widened claim, keeping a rounded figure and a pointer where the stage wanted the fact. Candidates the original already had are findings for the review stages, not failures of the revision. Then the corrected version gets its independent re-check ("Build the corrected version", step 7). The corrected version is built once the dashboard has collected and adjudicated the findings, and verified here before the dashboard is rendered (see "Build the corrected version" below). |
| Show what the workflow found and did (always, last) | [manuscript-dashboard](../manuscript-dashboard/SKILL.md) collects every stage's `findings.json`, merges the problems several skills found and dismisses what did not hold; once the corrected version is built and verified, it renders the dashboard: problems by kind, severity, stage and section, the annotated manuscript, the corrected version as track changes, machine-writing patterns by type in each version, coverage, edits as diffs, the panels, and what could not be checked. |
| Finish for submission, once the code, data and results are final | Archive the release and quote its DOI and version, finalise the data availability statement, declarations, AI-use statement and cover letter with manuscript-journal-adapt, upload the clean copy of a marked manuscript (never the marked master), and run the submission-package check in manuscript-integrity-check on the upload files. Do this when the authors say they are about to submit; until then these items are listed last and are not blockers for the draft. |
| After a decision | [manuscript-reviewer-response](../manuscript-reviewer-response/SKILL.md) plans the revision from the decision letter in the referees' own numbering, drafts the response letter and verifies that the revision addresses each comment. This is a separate request, after real reviews arrive. |
| Track who revised what (where the manuscript keeps revision marks) | [manuscript-revision-marks](../manuscript-revision-marks/SKILL.md) keeps the `@rev` marks current through every stage under the shared [marks rule](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review) (each applied edit bumps or opens its segment; routine fixes share one "copy edit" round per section), lists the AI edits no person has reviewed and the prose no round has read, and builds the PDF from the clean copy against the page limit; [manuscript-mark-people](../manuscript-mark-people/SKILL.md) sets up who counts as a person, asking its one question among the end-of-run decisions. Every comparison of versions in this workflow (the claim guard, `revise.py`, the change records) reads the clean copies. Never introduced into a project that does not use marks unless the authors ask. |

**Simulated referees and readers are independent, and the coordinator starts them.** Every referee seat,
reader, defender and critic (the deslop reflection loop's) is a fresh agent whose whole context is its
brief, never a fork of this conversation, as [Independent readers and referees](../manuscript-integrity-check/references/project-workflow.md#independent-readers-and-referees) requires.
Delegated agents often cannot start agents of their own, so start the seats, readers and critics from this
session even when another agent prepares the stage's workspaces and briefs; a stage agent never reads as the panel itself because it could not start one. Give
them nothing from this run: not the findings so far, not the authors' messages, not what the run changed.
When the authors asked for more than one model, or the project saves `other_models`, the coordinator also
starts each seat on each chosen model, and the critics on the chosen model, with
[manuscript-other-models](../manuscript-other-models/SKILL.md), at the same time as the host's seats.

**Brief each stage from the template.** A stage another agent carries out gets [the stage brief](references/stage-brief.md) with its fields filled in: the paths, the resolved settings, the stage's prefix and the paper's facts. Never write a stage's rules in your own words; a paraphrase of the contracts is how a run's records stop meeting them.

**One stage edits the working copy at a time.** The review stages (integrity, references, reporting, figures, policy fit, peer review) may run side by side, so in this workflow they do not edit the working copy: each records the corrections it can settle as proposals in its `findings.json` (`changes`, each with every field of the change record: its id and kind, the section, the before, the after, the why, the finding it rests on, its evidence as a list, and the file it changes when that is the supplement), and the revise stage applies them under the `edits` setting before the prose edit, recording each with `runs.py change`. The editing stages then run one after another on the same working copy.

**Record where the run stands** ([progress records](../manuscript-integrity-check/references/project-workflow.md#progress-records)),
so the authors can follow a run of several hours without asking. Start the run with `--skill manuscript-improve`
and one `--plan` for each stage it means to run, in order, with your own steps among them (`revise` before the
prose edit; `corrected`, `recheck` and `handover` at the end); when you choose the stages only after reading
the paper, give the plan with `runs.py begin RUN --skill manuscript-improve --plan ...`. Run
`runs.py begin RUN --skill SKILL` as each stage starts, before you brief its agent, and record your own steps
with `runs.py stage RUN --name revise|corrected|recheck|handover --status running`, then `completed` (or
`partial`, `blocked` or `not_run` with `--reason`). A report-only run records `revise`, `corrected` and
`recheck` as `not_run` with the reason, and a planned stage the run leaves out is finished `not_run` with its
reason.

Stages that write proposals (figures, policy fit, story, prose edit, deslop, journal adaptation) work from the review stages'
confirmed findings: run them after those stages, or reconcile their proposals with the findings before
handover, so that no proposal restates what a check refuted (a feature the code lacks, a peak that was
not measured). They copy each proposal's before-text from the current working copy, and an addition names
the passage it follows (`anchor`), so the corrected version can place it. A stage that edits a passage
another stage has a pending proposal for adds its version as a proposal instead of applying it. Where two
stages rewrite the same passage, the dashboard lists them as competing; pick one per passage in
`revision-choices.json` (`prefer`) rather than stacking edits, and keep the others visible as alternatives.
The authors choose per passage only under `edits: propose` or when they asked to review each change. Policy fit's venue-specific part runs after journal selection has
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
Then stop before the next unit. Whenever the run stops until the authors answer (a checkpoint, an interview,
a question that blocks the next stage), record it first with `runs.py wait RUN --question TEXT`, one per
question, and `runs.py resume RUN` when the work goes on; the decisions listed at handover are not a wait. A request to change one step does not discard previously accepted edits or
settled decisions. Revisit dependent work only when the new decision changes it.

**Finish all independent work before yielding for decisions.** A pending approval or missing fact blocks
only dependent work. Follow the shared rule in
[Minimum useful work](../manuscript-integrity-check/references/author-priorities.md#minimum-useful-work):
collect decisions, continue every applicable check and permitted edit across the requested scope, and
prepare exact proposed text with its evidence. Use asynchronous questions when supported; otherwise
defer blocking question tools until the independent work is finished. Do not turn the `apply` or
`conservative` policy into a sequence of question-and-answer stops. The authors' questions are only the held decisions
and the facts only they have, asked once, together, at the end; a failed check (the claim guard, the smell
check, a story test, the run validation) is yours to fix, never a question. At handover, distinguish
completed work from the pending proposals and their dependent steps. Silence never grants approval. Do
not invent data, citations, approvals or accounts of AI use.

**Keep the paper whole and worth reading.** The run improves the authors' paper; it does not rewrite it
into another one. No applied edit or proposal drops a result, number, caveat or citation the evidence
does not refute, and the authors' voice, their direction and what makes the paper readable (its stake,
its worked example, one headline per result) survive every stage. The final checks below measure it:
the claim guard for lost caveats and strengthened claims, the smell check for machine phrasing, and the
reader metrics for how it reads against the original. When the corrected version reads worse than the
original on the reader metrics, find the stage that caused it. Restore or drop its style and story edits that
cost readability; a correction a confirmed finding asked for stays, and its sentence is split or tightened
instead, or listed for the authors when it cannot be without changing what it says.

## Finish with a reviewable result

**Build the corrected version.** The working copy holds only what the mode applied; the authors also get
the whole improved paper to read, and can accept it in one step. It is built from the adjudicated
inventory, so the end of a run goes in this order:

1. Every stage has recorded its applied edits (`runs.py change`, routine ones grouped per paragraph or
   section), with any question for the authors in `--comment`, never in the text.
2. Collect the draft inventory (`RUN/manuscript-dashboard/findings.draft.json`).
3. Adjudicate in `merges.json`; with a reference review, freeze, match and write `reference.json` with
   `matched_by` (manuscript-dashboard, steps 1 to 3).
4. Collect the adjudicated `findings.json` once, with `--merge` (and `--reference`).
5. Write `revision-choices.json` and run `revise.py` into `revision/` (`runs.py stage RUN --name corrected
   --status running` first), with the supplement's two clean texts when the run took one in, so the supplement
   gets its corrected version from its own changes.
6. Verify `revision/proposed<ext>` with the checks of the "Verify the revision" row. Fix a failure by
   holding the proposal or recording the reverse change; when a change was recorded, collect again as
   `findings.2.json` and rebuild into `revision.2`. Then `stage --name corrected --status completed`; a
   rebuild after the re-check sets it `running` again.
7. Re-check it independently, between `stage --name recheck --status running` and `completed`. The stages' own agents are the ones most inclined to see their fixes as
   done, so one fresh agent that took no part in the review or the edits reads each confirmed problem against
   the corrected version, and the number, reference and section-roles checks run again on it (from this skill's
   folder):

   ```bash
   uv run --script scripts/recheck.py prepare --inventory RUN/manuscript-dashboard/findings.json \
       --revision RUN/manuscript-improve/revision --original ORIGINAL --into RUN/manuscript-improve/recheck \
       [--supplement-original SUPPLEMENT_ORIGINAL]
   uv run --script scripts/recheck.py numbers --original ORIGINAL \
       --proposed RUN/manuscript-improve/revision/proposed<ext> --json RUN/manuscript-improve/recheck/numbers.json
   uv run --script scripts/recheck.py check RUN/manuscript-improve/recheck/answer.json \
       --numbers RUN/manuscript-improve/recheck/numbers.json --out RUN/manuscript-improve/recheck.json
   ```

   `prepare` writes the agent's folder: the reviewed text, the corrected version, the content changes between
   them, each confirmed problem with its quote, what would settle it and who raised it, and `brief.md`, its
   whole prompt. No change reasons, summaries or adjudication go in. Start the agent as
   [Independent readers and referees](../manuscript-integrity-check/references/project-workflow.md#independent-readers-and-referees)
   describes, on the other model when `other_models` is set ([manuscript-other-models](../manuscript-other-models/SKILL.md)),
   and register its folder with `runs.py add --role seat --seat recheck`. For each problem it says whether the corrected version fixed it fully or in part, left it open, made it worse or could not settle it, with a quote from the corrected version, and labels
   each new problem introduced by the edits or missed earlier. `check` exits 1 when the answer breaks the
   contract (a quote not in the corrected version, a problem unanswered, a label the texts contradict):
   correct the quote from the text or mark the problem could not check; never ask the agent to judge again.
   It exits 3 when an edit made a problem worse, introduced one, or introduced a number, reference or
   section-roles candidate: hold or reverse those edits as in step 6 and rebuild. Reversing an applied correction that a
   confirmed finding asked for would bring the error back: keep it, fix a slip it left (a tense, a missing
   abbreviation) with a recorded routine edit, and list what remains for the authors with the end-of-run
   items. Nothing here goes to the authors as a question.

   The rebuilt version then gets one second re-check, which reads only what the fixes changed: `prepare
   --since RUN/manuscript-improve/recheck.json --previous RUN/manuscript-improve/revision` (the folder the
   first re-check read) with the rebuilt `--revision` and `--into RUN/manuscript-improve/recheck.2`, a fresh
   agent again, `numbers` with the first re-check's corrected version as `--original`, and `check ... --out
   RUN/manuscript-improve/recheck.2.json`. It judges again each problem the first found made worse, each new
   problem it found introduced, and each whose quoted passage the fixes changed; the rest keep the first's
   verdict (`carried_over`). When it exits 3 there is no third: hold or reverse those fixes, rebuild, and
   finish the stage `stage --name recheck --status partial --reason ...` with what stays unchecked.
   `runs.py validate --final` refuses a handover whose newest re-check read another build than the corrected
   version unless that reason is recorded. The dashboard reads the newest `recheck*.json` beside the revision
   folder.
8. Render the dashboard and the Word file from the same attempts.
9. Write the summary, run the smell check on it and register it; `finish` every stage, run
   `validate --final`, then `runs.py handover` (between `stage --name handover --status running` and
   `completed`) and, when `keep` is `results`, `pack`.

Write `RUN/manuscript-improve/revision-choices.json`: for each group of competing proposals, the one you
recommend (`prefer`); the proposals to hold back with the reason (`hold`: a held decision such as a
statement for a journal not yet chosen, a proposal whose substance is a fact only the authors have, or a
claim restored after the guard); and an anchor for an addition its stage left without one. Every key is
optional; revise.py refuses any other key or shape and says what the file should hold:

```json
{
  "prefer": ["ST-C3"],
  "hold": [
    {"id": "JA-C18", "why": "Waits for the choice of journal."},
    {"id": "ST-C7", "why": "widened claim, wording restored"}
  ],
  "anchor": [{"id": "JA-C1", "after": "verbatim passage the addition follows"}]
}
```

No placeholder goes into the text
([Questions for the authors are comments, never text](../manuscript-integrity-check/references/author-priorities.md#questions-for-the-authors-are-comments-never-text)):
a question about a proposal is its `comment`, one about existing text a decision in the report. ORIGINAL is
the run's snapshot of the manuscript before the workflow (`RUN/inputs/01-<name>`); WORKING is the working
copy, the manuscript with every applied edit (with `versions: immutable`, the new version `runs.py version`
made). For a manuscript with revision marks, give both as clean
copies (`../manuscript-revision-marks/scripts/rev_marks.py strip FILE --out RUN/manuscript-improve/clean/original.md`,
and the same for the working copy after each stage), and use the clean copies for every comparison below.
Then run, from this skill directory:

```bash
uv run --script scripts/revise.py ORIGINAL WORKING RUN/manuscript-dashboard/findings.json \
  --choices RUN/manuscript-improve/revision-choices.json --output-dir RUN/manuscript-improve/revision \
  [--supplement-original SUPPLEMENT_ORIGINAL --supplement-working SUPPLEMENT_WORKING]
```

A change to the supplement names it (`document`), and the manuscript's corrected version leaves it alone. With
the supplement's clean texts, revise.py builds the supplement's corrected version from its own changes by the
same rules and choices (`supplement-proposed<ext>`, `supplement-revised<ext>`, `supplement-changes.md`, and
`supplement` in `revision.json`), and `runs.py handover` puts it beside the supplement as
`SUPPLEMENT_STEM.proposed<ext>`.

It locates every applied edit in the working copy and stops when undoing them does not give the original,
so an unrecorded edit cannot hide. It then applies the chosen proposals in manuscript order:
`proposed<ext>` (the manuscript's own extension, `proposed.md` or `proposed.tex`) is the corrected version,
`revised<ext>` the working copy as revise.py read it, `changes.md` the same as CriticMarkup with the
questions for the authors as comments, and `revision.json` what was applied, held, restored, left as an
alternative or not placed, each with its reason, and the questions. A `[AUTHORS: ...]` note a stage left in a
proposal is lifted out of its text into a comment; a proposal that was only a question is listed, not
placed. revise.py lists two kinds of notes still in a text. `notes_in_working_copy` are the notes the run's
applied edits left in the working copy; the corrected version already has them as comments. Remove each
from the working copy with a recorded `runs.py change` and say so in the summary; better, put such a
question in the change's `--comment` so no note enters the text. `notes_in_text` are the authors' own draft
notes: list them for the authors with the end-of-run items; the run never deletes them. The dashboard marks
each questioned passage in yellow and lists the questions. A proposal is never dropped silently; one that
cannot be placed is listed, and the authors see it. The corrected version is a proposal too: the working
manuscript changes only as the mode allows, the authors accept, or "fix everything" asks. Run the
verification checks on `proposed<ext>` as well, and give the dashboard the folder
(`--revision RUN/manuscript-improve/revision`), so its Corrected version tab shows the track changes.
`runs.py handover RUN` puts the corrected version beside the manuscript as `<manuscript stem>.proposed<suffix>`
(`paper.proposed.md`, `paper.proposed.tex`), never over their file or a different earlier copy.

A step done again never overwrites the first. The next attempt of a file takes a number before its
extension (`findings.2.json`, `revision-choices.2.json`, `manuscript-review.2.docx`), of a folder after its
name (`revision.2`, `dashboard.2`). Each script refuses an existing output and names the next free one. Keep
the chain together: revise.py builds from the newest adjudicated inventory, and the dashboard and the Word
file take that inventory and the revision built from it (they refuse another). `runs.py handover` and
`pack` use the newest attempt.

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
statement, the cover letter, building the upload files from the clean copy, the upload check) are not blockers for a draft
and do not count against its readiness unless the authors say they are about to submit.

Make the original-to-final comparison accessible. In an iterative workflow, state the current accepted
version and next requested step using the conversation or existing project conventions; no new tracking
files are required.

Every finding-producing stage (all but the dashboard, this coordinator, other-models and mark-people) writes
`findings.json` beside its report, as
[stage findings](../manuscript-dashboard/references/stage-findings.md) describes, including the stages run
by reviewer agents. The last step of every run of this workflow is
[manuscript-dashboard](../manuscript-dashboard/SKILL.md) on the same run: collect the stages' findings,
merge what several skills found into one record each, dismiss what did not hold, and render the
dashboard, with the corrected version, into `RUN/manuscript-dashboard/`, an annotated Word document for
readers who work in Word or Google Docs (`export_docx.py`; under `apply` and `conservative` the default
`--detail decisions`: the applied edits already in the text, comments only for the questions, the proposals,
the decisions and the open major problems; under `propose`, `--detail everything`), and the changes workbook
(`export_changes.py`: every applied edit with its before, after and reason, what needs the authors, the open
problems and the held proposals), all handed over beside the manuscript as `<manuscript stem>.dashboard.html`,
`<manuscript stem>.review.docx` and `<manuscript stem>.changes.xlsx` (`runs.py handover RUN`; a different Word file, workbook or corrected version already there is kept, and this
run's goes beside it under a dated name; replacing it is an optional end-of-run decision). Link the dashboard first in the
summary and the corrected version second: they are how the authors and their colleagues see what the
workflow caught, changed and left open, with the actual coverage. Reuse the evidence rather than rerunning the review. A stage that could not run still appears,
with its reason; its unfound problems are unknown, not zero. `runs.py validate RUN --final` requires the
adjudicated inventory, the corrected version, the dashboard and the Word file, unless the dashboard or
improve stage was finished `partial` or `blocked` with its reason. When `keep` is `results`, pack the run
(`runs.py pack RUN`) after the final validation, as the very last step: the dashboard, the corrected
version and the reports stay in place and the rest goes into `evidence.zip`.

Optional detector checks keep their companion skill's request boundary. Formal referee simulation uses
project `peer_review`: `auto` by default in this full workflow, `on-request` only on request, or `off`;
record a skipped stage with its reason. A focused edit never activates this full workflow or its panel.
Completing this workflow prepares the manuscript; it does not authorise submitting, emailing or publishing.
