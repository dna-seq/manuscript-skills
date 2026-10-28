---
name: manuscript-dashboard
description: >-
  Turn a manuscript run's saved findings, evidence and revisions into an offline dashboard for the
  authors and colleagues: distinct problems by kind, severity, stage, section and skill, what each
  skill covered, the funnel from raw signals to problems, the annotated manuscript, the corrected
  version as track changes, machine-writing patterns by type, edits as before/after diffs, the figures
  with their verdicts and recommendations, the simulated reviewers' concerns and suggestions and the
  readers' paths, the co-authors' comments on the previous release and how this one answers each, a
  to-do list the authors mark approved or redundant for the next run, and, when a reference review
  exists (a human referee's comments), which of its problems the run caught and missed.
  manuscript-improve calls it as its last step; use it directly to visualize or show colleagues an
  earlier run or a focused skill's results. Formerly manuscript-visualize. New reviews and scientific
  result figures belong to their own workflows.
---

# A dashboard of what the review found and changed

Make the existing work understandable to someone who did not follow the chat: the problems the run
found, counted once each, with the passage, the evidence and what to do; the edits made and proposed;
what each skill covered and what could not be checked. Use the saved run and its evidence; a request for
a dashboard does not ask for another review or another edit.

Read the shared [author priorities](../manuscript-integrity-check/references/author-priorities.md) and
reuse the [project and run](../manuscript-integrity-check/references/project-workflow.md), ending with its
[end-of-stage checklist](../manuscript-integrity-check/references/project-workflow.md#end-of-stage-checklist)
(this skill writes no `findings.json` of its own). Save the inventory, the adjudication, the outputs and the
report under `RUN/manuscript-dashboard/`. Older reports without a run manifest can still be shown: write the
inventory by hand ([data contract](references/data-contract.md)) and state their scope and unknown coverage
rather than inventing a complete run.

The files of this skill, in `RUN/manuscript-dashboard/`:

| File | What it is |
|---|---|
| `findings.draft.json` | The draft inventory: every stage's records, not yet merged or judged. |
| `merges.json` | The adjudication: merges, corrections, dismissals, decisions. |
| `reference.json` | The reference review and its matches, when there is one. |
| `findings.json` | The adjudicated inventory, collected with `--merge` (and `--reference`); revise.py, the dashboard and the Word file read this one. |
| `dashboard/` | The rendered dashboard and `summary.json`. |
| `manuscript-review.docx` | The annotated Word document: by default only what needs the authors. |
| `manuscript-changes.xlsx` | The changes workbook: every applied edit, what needs the authors, the open problems and the held proposals (and the co-authors' comments, when the run tracked them). |

**Second attempts.** Nothing is overwritten, and every script here (and revise.py) refuses an existing output
and names the next free one. The next attempt of a file takes a number before its extension
(`findings.json`, `findings.2.json`, `findings.3.json`; `merges.2.json`; `manuscript-review.2.docx`); of a
folder, after its name (`dashboard`, `dashboard.2`; manuscript-improve's `revision`, `revision.2`). Keep the
chain together: revise.py builds from the newest inventory, the dashboard and the Word file take that
inventory and the revision built from it (both refuse a revision built from another inventory). Collect reads
each stage's newest `findings.json` attempt, and `runs.py handover` and `pack` take the newest attempt of
each deliverable. Register each attempt under its own name.

## 1. Collect the inventory

Every finding-producing skill of the run (all but this one, manuscript-improve, manuscript-other-models and
manuscript-mark-people) writes `findings.json` beside its report ([stage findings](references/stage-findings.md)).
Collect drafts the inventory from those files and the run manifest. A run whose evidence was packed
(its index names `evidence.zip`) is unpacked first with `../manuscript-integrity-check/scripts/runs.py
unpack RUN`, and packed again at the end when the project's `keep` is still `results`.

```bash
uv run --script scripts/collect.py RUN --output RUN/manuscript-dashboard/findings.draft.json --version v0.3
```

It takes coverage from `run.json`, the manuscript's title and sections from its snapshot, each skill's
findings, dismissed flags and unrun checks, the check outputs as raw signal counts (for the simulated
referees, what they proposed before adjudication, counted once), the readers' reports, the simulated
reviewers' recommendations, concerns and suggestions (with the criteria each wrote before reading, from the
finding check's `criteria`, and where each expectation is written, from `norm_source`), the reference list's
state per entry (the reference scanner's JSON in the reference-check or integrity-check folder), journal
selection's ladders and record, and the authors' to-do marks: `STEM.todo.json` beside the manuscript, which the
dashboard's To-do tab saves ([below](#the-authors-to-do-marks); `--todo FILE` names another), every mark of every
run, as the inventory's `todo`. Its output lists, under `todo.restated`, each earlier mark that this run's
problems, decisions or edits repeat word for word, for the adjudication. A stage
still running shows as in progress; manuscript-improve itself, which is running while it collects, is left
out of the coverage unless it recorded findings of its own. A manuscript that exists only as a connected
document has no local text to quote: a run started with its reading copy (`runs.py start --reading-copy`)
has one; for an older run, export a reading copy, register it in the run and pass it with `--manuscript COPY`.

Applied or proposed: collect replays the changes recorded with `runs.py change` on the reviewed text, in
the order the skills recorded them. When the replay ends on the revised manuscript, every change that found
its before-text counts as applied, including an edit a later stage edited again. Otherwise a change counts
as applied only when the revised manuscript holds its after-text and no longer holds its before-text. A
skill that wrote no `findings.json` contributes its coverage and nothing else: read its report and add its
findings by hand, or record why it has none. A missing file never means the skill found nothing.

## 2. Adjudicate: one record per problem

Read the draft against the reports. Collect never decides what is the same problem or what holds;
write those decisions in `RUN/manuscript-dashboard/merges.json`:

```json
{
  "merge": [{"keep": "IC-3", "ids": ["RF-2", "ST-5"], "summary": "optional better wording"}],
  "update": [{"id": "RP-4", "assessment": "confirmed", "evidence": [{"path": "../manuscript-integrity-check/stage-report.md", "quote": "..."}]}],
  "dismiss": [{"id": "DS-7", "why": "A module name, not hype."}],
  "decisions": [{"id": "D1", "summary": "Narrow the speed claim or rerun the benchmark", "finding_ids": ["IC-3"]}],
  "change_links": [{"change": "prose-edit.C1", "finding_ids": ["IC-2"]}],
  "addressed": ["IC-2"]
}
```

- **Merge** records that describe one underlying problem, keeping every skill and source ID. Do not
  merge two problems that share a sentence, and do not split one problem into its symptoms. The merged
  record keeps the most serious severity and the earliest stage unless the merge says otherwise.
- **Confirm** a candidate only on evidence you add to it (a recomputation, the code, the source). A
  simulated reader's concern stays reader feedback; a style hit never becomes a scientific error.
- **Dismiss** with a reason; dismissed flags stay listed and are never counted as problems.
- A finding is **addressed** only when an applied edit is linked to it and you checked the revision.
  A proposal does not address anything. Once the corrected version has its independent re-check
  (`recheck.json` beside the revision folder, from manuscript-improve's `recheck.py`), the page shows that
  verdict instead: fully or partly addressed, still open, made worse, or could not check; the inventory
  file keeps its own resolution.
- Keep original severities; use `unknown` where a skill did not assess one. The authors read the
  severities as Blocker, Major, Minor ("worth fixing, low stakes"), Optional (`info`: a style preference,
  possible improvement or additional experiment) and Could not be checked (`unknown`); collect maps a
  referee's `optional` to `info` and `uncertain` to `unknown`.
- **Decisions** you write join the stages' own: the dashboard lists every decision in `merges.json`, then
  each finding marked `decision: true` (a figure to add or move, a direction, new work) that none of them
  links, so writing one decision never hides the others.
- **What the authors marked redundant stays dismissed.** For each mark collect lists in `todo.restated`, and each
  problem or decision you recognise in `todo.marks` reworded, dismiss this run's record when the mark is
  `redundant`, with their reason as the why ("Marked redundant by the authors in run R1: the code changed."), and
  hold a repeated redundant proposal in revise.py's choices (`hold`, the same why). The To-do tab already sets
  aside the word-for-word repeats; the dismissal keeps them out of the counts and the Word review too. An
  `approved` mark is the authors' answer: the item is done or kept, not a problem to raise again.

Then collect the adjudicated inventory, `findings.json`, with `--merge` (with a reference review, read step 3
first: the two go in one collect):

```bash
uv run --script scripts/collect.py RUN --output RUN/manuscript-dashboard/findings.json \
  --merge RUN/manuscript-dashboard/merges.json --version v0.3
```

A collect without `--merge` warns when a merge file lies beside its output: that inventory has none of the
merges, dismissals or decisions, so never render or revise from it.

The merge file is part of the evidence: it shows each counting decision. The renderer checks files,
quotes and links; whether the deduplication and the verdicts are right is the adjudicator's job.

## 3. Compare with a reference review (when one exists)

When the same version was reviewed independently (a human referee's comments, an earlier panel), add
it as a reference ([data contract](references/data-contract.md#reference-review)) and match each of its
items to the run's findings: `full` when a finding names the same problem, `partial` when it names part
of it. Freeze the run's inventory before reading the reference (the draft and a finished `merges.json`), so
the comparison cannot shape the findings, and match against the IDs the adjudication keeps (a merged record
answers to the ID it was merged into; a dismissed flag cannot be a match). Record who matched them in the
reference file's `matched_by` ("the coordinating agent, after the inventory was frozen", or a co-author's
name); the dashboard shows it. When the reference reviewed an earlier version, run the review blind: give
the stages that version, the code as of its date and no later versions, reviews or history, and pin outside
sources to that date (a release tag, an archived page); a finding that rests on a later page cannot count as
a match. Then collect once with both files, before revise.py builds the corrected version:

```bash
uv run --script scripts/collect.py RUN --output RUN/manuscript-dashboard/findings.json \
  --merge RUN/manuscript-dashboard/merges.json --reference RUN/manuscript-dashboard/reference.json --version v0.3
```

A collect with `--reference` alone drops the adjudication, and the corrected version built from the earlier
inventory no longer matches. A reference that arrives after the corrected version was built: collect the next
attempt with both (`findings.2.json`), rebuild the corrected version from it (`revision.2`) and render again
(`dashboard.2`, `manuscript-review.2.docx`). The dashboard then shows what was caught, partly caught and
missed, by kind of problem, and the confirmed findings the reference lacks. Those are not false alarms by
default: one review is one reading, not ground truth.

## 4. Render

```bash
uv run --script scripts/dashboard.py RUN/manuscript-dashboard/findings.json \
  --output-dir RUN/manuscript-dashboard/dashboard --revision RUN/manuscript-improve/revision
```

`--revision` is the corrected version that manuscript-improve builds from this inventory with its
`revise.py`; the renderer refuses one built from another inventory. Leave it out for a run without one. A
second rendering goes to `dashboard.2`; give it an inventory and the revision built from that same inventory.

- `manuscript-dashboard.html`: one self-contained file that opens offline, on the Overview, and can be sent to
  anyone as it is: data, styles and scripts are inside it, and the manuscript's local images are embedded
  (an image it could not find keeps its path and says so). Which skill found something is shown by an
  icon, with its name in the tooltip and a legend. Its tabs: the To-do list ([below](#the-authors-to-do-marks));
  headline
    counts, coverage per skill, the reference list at a glance (one cell per entry, coloured by its worst state:
  retracted, points to another work, a detail to correct, no identifier, could not be checked, or fine), the funnel from
  raw signals to confirmed problems and the machine-writing patterns by type in each version of the text; the problems, cross-filtered by kind, severity, stage and
  skill, and AI-related or not, with a heat grid of where they sit and a sortable, searchable table with
  every passage and evidence excerpt; the manuscript with every quoted problem highlighted by severity and its
  comment beside it (short until selected, so each stays beside its passage; nothing is added to the text), and,
  for a manuscript with [revision marks](../manuscript-revision-marks/SKILL.md), the marks' history in the same
  margin instead of in the text: each revised passage's rounds, who wrote or approved them and when, and whether a
  person has read it since the last AI round; the corrected version as track changes, with what was held back or could not be
  placed, and the questions for the authors as comments beside the passages (marked in yellow, hidden with
    one click; none is in the text), with how the claims moved: each claim the run changed placed on the causal
  and the evidential ladder, before and after, marked as moved toward the evidence, stronger as a finding
  asked, or stronger with nothing asking for it (from `requested-claims.yaml` beside the revision folder), and
    each title, Abstract or Conclusions sentence that claims more than the body (`guard.py --summary`), and
  the independent re-check: each confirmed problem's verdict against the corrected version, by who raised it,
  the new problems it found (introduced by the edits or missed earlier) and the number, reference and
  section-roles checks run again on the corrected version (a re-check of an earlier build says so); the
  comparison with the reference review; the co-authors' comments on the previous release, from
  manuscript-coauthors (each comment or suggested edit with its thread, where it sits and the text it is
  attached to, its status by co-author, the before-and-after word diff, the passage that answers it, why and
  what could still be done, with links to its problems and to the passage's edit history; `#coauthors/C40`
  opens one); the journals, with each venue's AI policy as icons
  (a red flag ⚑ for a drafting ban, required prompts or records of AI changes, a detector, declared use
  held against the paper); word-level diffs of the edits, each with why it was made and its evidence; the
  figures (each one as rendered, with its verdict, problems and recommended changes, a redrawn draft beside
  it when there is one, the figures to add and the venue's limit; `#figures/Figure%202` opens one); the
  story (the direction, the story tests, the edits that keep the direction and the narrative changes only
  the authors can choose); the
    simulated reviewers (their recommendation per journal, every concern with its suggestion and the
  adjudication's verdict, grouped by who can act, where each expectation comes from (the journal, a reporting
  guideline, the field's checklist or the reviewer's own), and each reviewer's criteria written before reading:
  raised, checked with nothing found, or not covered); the readers' paths by section and subsection, in a tab
  of their own; whether each reader and reviewer ran as a fresh agent, and on which model; and what
  could not be checked. Each tab has an address, so
  `manuscript-dashboard.html#manuscript` opens the annotated paper itself, and `#manuscript/IC-1` the
  paper at that problem (`#findings/IC-1` its row, `#revised/PE-C3` that change, `#todo/D1` that to-do). Evidence keeps file names only, never
  local paths. It follows the system light or dark theme.
- `summary.json`: every derived count, with the evidence files' hashes.

The pattern counts come from the deslop checker (`../manuscript-deslop/scripts/style_profile.py`) run on
the reviewed text, the working copy and the corrected version. A count is a place to look, never a
verdict; say so wherever the counts are quoted.

Counts come from the records, never from supplied totals: confirmed problems, candidates, dismissed
flags, applied and proposed edits are separate units, and a problem found by three skills is one
problem. Do not add a quality score, an improvement percentage or a detection rate without a reference.

### The annotated Word document

Some readers want the paper itself, annotated, in the editor they already use. Write it beside the dashboard:

```bash
uv run --script scripts/export_docx.py RUN/manuscript-dashboard/findings.json \
  --revision RUN/manuscript-improve/revision --output RUN/manuscript-dashboard/manuscript-review.docx
```

By default (`--detail decisions`) the document holds only what needs the authors, so they do not page through
a comment for every obvious fix. The text is the corrected version: an applied edit that asks nothing is
already in it. The proposals, and the applied edits that carry a question, are tracked changes signed by the
stage that made them (Story, Prose edit, Journal adaptation), so the authors accept or reject each one in Word.
The margin holds each question for the authors on its edit, each proposal's reasoning, each decision only the
authors can make (on the passage of the first problem it covers) and each open blocker or major problem that no
edit, proposal or decision answers. Everything else is in the changes workbook and the dashboard.

`--detail everything` is the whole review, the document for authors who approve every change (`edits:
propose`, or when they ask for it): every edit a tracked change, each problem as a comment on the passage it
quotes (problems whose passage is not in the text share one comment on their section's heading), the questions
for the authors on their edit, one comment per edit, and each edit's reasoning (`--no-reasons` leaves those out,
`--no-problems` the problems). In both, each comment opens with what it says and the problem's or edit's ID
follows in parentheses. Nothing is added to the text: an image that could not be embedded is named in a comment
where it stands. Without `--revision` it annotates the reviewed version.

The paragraphs are justified, as the paper is typeset, so neither the Word file nor the Google Doc made from it
needs reformatting: body text, list items and quotes are justified; headings, tables, code and a paragraph
broken into lines by hand (an author block) stay left-aligned. A Google Doc this workflow writes any other way,
through a Google Docs or Drive connection, justifies its paragraphs the same way.

### The changes workbook

The applied edits are checked in a workbook, filtered by stage, section or problem, not one comment at a time:

```bash
uv run --script scripts/export_changes.py RUN/manuscript-dashboard/findings.json \
  --revision RUN/manuscript-improve/revision --output RUN/manuscript-dashboard/manuscript-changes.xlsx
```

Sheets: **Applied** (every edit in this version: stage, section, before, after, why, the problems it answers),
**For you** (the decisions, questions and proposals the Word review comments on: the To-do tab's items but the
open problems), **Open problems** (every
problem no applied edit answers, all severities), **Held** (the proposals left out of this version, with
why) and, when the run tracked them, **Co-authors' comments** (each comment on the previous release: its
author, kind, section, status, the passage before and now, why, and what could still be done). It opens in Excel, LibreOffice and Google Sheets; a Google Sheet is made by uploading it to Drive, which
waits for the authors to ask, like the Word file.
For a Google Doc, upload the file to Google Drive and open it with Google Docs: comments stay comments,
tracked changes become suggestions and the paragraphs stay justified. Uploading is sending the paper somewhere, so it waits for the authors to ask.

### The authors' to-do marks

The **To-do** tab, after the Overview, lists what the run leaves for the authors: each decision only they can
make, each applied edit that asks them something, each proposal in this version or waiting for their answer, and
each open blocker or major problem none of those and no edit in the text answers (`dashboard.todo_items`, the
same items the Word review comments on and the workbook's **For you** sheet lists). The authors mark each one
**Approve** (the next run does it, or keeps the edit) or **Redundant** (dropped, an applied edit undone, and not
raised again), with an optional reason or answer, and the list shrinks as they go; its count is on the tab and on
the Overview. Each mark is kept in the browser at once, so closing the page loses nothing; **Save the marks to
the file** writes `STEM.todo.json` beside the manuscript: Chrome and Edge write the file itself, chosen once and
remembered, and save each later mark as it is made; other browsers download it, to be put beside the manuscript.
**Load marks from a file** reads one back. The file holds every run's marks (`run_id`, `kind`, `id`, `mark`,
`reason`, `marked_at`, and what the item said: summary, section, passage, before and after), so a later run
recognises an item after its IDs have changed; an item that repeats one an earlier run's authors marked
redundant is set aside under its own fold with their reason ([data contract](references/data-contract.md#to-do)).

The next run reads the file: collect carries it ([step 1](#1-collect-the-inventory)), the adjudication dismisses
what was marked redundant ([step 2](#2-adjudicate-one-record-per-problem)), and manuscript-improve's first stage
does what was approved. The marked edits become the list `runs.py apply` takes:

```bash
uv run --script scripts/todo.py edits STEM.todo.json --text WORKING_COPY --output RUN/manuscript-improve/todo-edits.json
uv run --script scripts/todo.py show STEM.todo.json   # the marks by run, approved first
```

An approved proposal is made where its text before occurs once (an addition after its anchor); an edit marked
redundant is undone where its text after occurs once; one already as marked needs nothing, and one whose text is
not there exactly once is listed as not placed, never guessed. `--run R1` takes one run's marks. The approved
decisions and problems, and every approved item with the authors' note, come back as `for_the_stages`.

The Decisions pane in Claude Code answers the same decisions while a session watches the run, and sends the
answers to Claude as a message; the marks file is where an answer outlasts the session.

## 5. Check and deliver

Reconcile every displayed total with `summary.json`. Open the dashboard in an available browser: every
tab, the filters, a row's evidence, an edit's diff, both themes and a phone-width window; fix layout or
runtime errors before handover. If no browser is available, say that interactive behaviour was not
checked.

Write a short `stage-report.md`: the run and its coverage, what the main counts mean, the problems that
matter most, what the comparison shows when there is one, and links to the dashboard, the inventory and
the merge file, and the annotated Word document when it was written. The shared report check is required:
`uv run --script ../manuscript-deslop/scripts/style_profile.py RUN/manuscript-dashboard/stage-report.md --report --check`,
then read the report against the pattern list it prints. Register the report, the inventories, the merge
file and the outputs with `runs.py add`, giving each output its path inside this skill's folder with
`--name`, because several attempts and folders hold files of the same name (without it, each file is
copied to the folder's root and the second `summary.json` is refused as already registered):

```bash
uv run --script ../manuscript-integrity-check/scripts/runs.py add RUN --skill manuscript-dashboard \
  --file RUN/manuscript-dashboard/dashboard/manuscript-dashboard.html --role other --name dashboard/manuscript-dashboard.html
uv run --script ../manuscript-integrity-check/scripts/runs.py add RUN --skill manuscript-dashboard \
  --file RUN/manuscript-dashboard/dashboard/summary.json --role other --name dashboard/summary.json
```

and the same for `findings.draft.json`, `merges.json`, `findings.json`, `manuscript-review.docx` and
`stage-report.md` (`--role report`); keep failed attempts too. Creating the files does not send them to anyone.

Once every stage is finished and `runs.py validate RUN --final` passes, hand the dashboard, the Word
document and the corrected version over beside the manuscript, where the authors open the paper:

```bash
uv run --script ../manuscript-integrity-check/scripts/runs.py handover RUN
```

It copies the newest attempt of each: the dashboard as `<manuscript stem>.dashboard.html`, the Word file as
`<manuscript stem>.review.docx` and the corrected version as `<manuscript stem>.proposed<extension>`
(`paper.dashboard.html`, `paper.review.docx`, `paper.proposed.md`). The dashboard replaces the previous
run's (with `versions: immutable` it is kept like the others, and `--replace` options are refused); each run
folder keeps its own. A report-only run (`edits: none`) has no corrected version to hand over. A Word file or corrected version already there that differs is never
replaced, because the authors may have worked in it: the new one goes beside it under a dated name
(`paper.review.20261024.docx`) and the command says so. Whether to replace the earlier file is one of the
optional decisions at the end of the run, never a question that stops it; once the authors say so, rerun
handover with `--replace-docx` (the Word file) or `--replace-proposed` (the corrected version). A connected manuscript started with its reading copy hands over to the project folder, named after the reading copy; `--to FOLDER --stem NAME` override that. Link the copies
beside the manuscript in the reply.
