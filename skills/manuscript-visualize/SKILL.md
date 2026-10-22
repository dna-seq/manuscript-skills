---
name: manuscript-visualize
description: >-
  Turn a manuscript run's saved findings, evidence and revisions into an offline dashboard for the
  authors and colleagues: distinct problems by kind, severity, stage, section and skill, what each
  skill covered, the funnel from raw signals to confirmed problems, edits as before/after diffs, the
  reader and referee panels, and, when a reference review exists (a human referee's comments on the
  same version), which of its problems the run caught and missed. Also writes SVG and PNG for slides.
  manuscript-improve calls it as its last step; use it directly to visualize an earlier run or a
  focused skill's results. New reviews and scientific result figures belong to their own workflows.
---

# Visualize what the review found and changed

Make the existing work understandable to someone who did not follow the chat: the problems the run
found, counted once each, with the passage, the evidence and what to do; the edits made and proposed;
what each skill covered and what could not be checked. Use the saved run and its evidence; a request for
a dashboard does not ask for another review or another edit.

Read the shared [author priorities](../manuscript-integrity-check/references/author-priorities.md) and
reuse the [project and run](../manuscript-integrity-check/references/project-workflow.md). Save the
inventory, the adjudication, the outputs and the report under `RUN/manuscript-visualize/`. Older reports
without a run manifest can still be shown: write the inventory by hand ([data contract](references/data-contract.md))
and state their scope and unknown coverage rather than inventing a complete run.

## 1. Collect the inventory

Every skill of the run writes `findings.json` beside its report ([stage findings](references/stage-findings.md)).
Collect drafts the inventory from those files and the run manifest:

```bash
uv run --script scripts/collect.py RUN --output RUN/manuscript-visualize/findings.draft.json --version v0.3
```

It takes coverage from `run.json`, the manuscript's title and sections from its snapshot, each skill's
findings, dismissed flags and unrun checks, the check outputs as raw signal counts, the readers' reports
and the referees' recommendations. A change recorded with `runs.py change` counts as applied only when
the revised manuscript holds its after-text and no longer holds its before-text. A skill that wrote no
`findings.json` contributes its coverage and nothing else: read its report and add its findings by hand,
or record why it has none. A missing file never means the skill found nothing.

## 2. Adjudicate: one record per problem

Read the draft against the reports. Collect never decides what is the same problem or what holds;
write those decisions in `RUN/manuscript-visualize/merges.json` and collect again under a new name with
`--merge`:

```json
{
  "merge": [{"keep": "IC-3", "ids": ["RC-2", "ST-5"], "summary": "optional better wording"}],
  "update": [{"id": "RP-4", "assessment": "confirmed", "evidence": [{"path": "../manuscript-integrity-check/report.md", "quote": "..."}]}],
  "dismiss": [{"id": "SC-7", "why": "A module name, not hype."}],
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
  A proposal does not address anything.
- Keep original severities; use `unknown` where a skill did not assess one.

The merge file is part of the evidence: it shows each counting decision. The renderer checks files,
quotes and links; whether the deduplication and the verdicts are right is the adjudicator's job.

## 3. Compare with a reference review (when one exists)

When the same version was reviewed independently (a human referee's comments, an earlier panel), add
it as a reference ([data contract](references/data-contract.md#reference-review)) and match each of its
items to the run's findings: `full` when a finding names the same problem, `partial` when it names part
of it. Freeze the run's inventory before reading the reference, so the comparison cannot shape the
findings, and record who matched them. When the reference reviewed an earlier version, run the review
blind: give the stages that version, the code as of its date and no later versions, reviews or history,
and pin outside sources to that date (a release tag, an archived page); a finding that rests on a later
page cannot count as a match. Collect with `--reference reference.json`. The dashboard then
shows what was caught, partly caught and missed, by kind of problem, and the confirmed findings the
reference lacks. Those are not false alarms by default: one review is one reading, not ground truth.

## 4. Render

```bash
uv run --script scripts/infographic.py RUN/manuscript-visualize/findings.json \
  --output-dir RUN/manuscript-visualize/dashboard
```

- `dashboard.html`: one self-contained file that opens offline: headline counts, coverage per skill,
  the funnel from raw signals to confirmed problems, cross-filtered charts by kind, severity, stage and
  skill, a heat grid of where in the manuscript the problems sit, the problems found by several skills,
  a sortable, searchable table with every passage and evidence excerpt, word-level diffs of the edits,
  the reader and referee panels, the comparison with the reference review, and what could not be
  checked. Evidence keeps file names only, never local paths. It follows the system light or dark theme.
- `infographic.svg` and `.png`: the static summary for slides, with scope and coverage in the image
  (`--no-static` skips them).
- `infographic.vl.json` and `summary.json`: the chart specification and every derived count.

Counts come from the records, never from supplied totals: confirmed problems, candidates, dismissed
flags, applied and proposed edits are separate units, and a problem found by three skills is one
problem. Do not add a quality score, an improvement percentage or a detection rate without a reference.

## 5. Check and deliver

Reconcile every displayed total with `summary.json`. Open the dashboard in an available browser: every
tab, the filters, a row's evidence, an edit's diff, both themes and a phone-width window; fix layout or
runtime errors before handover. Inspect the PNG at its display size. If no browser is available, say
that interactive behaviour was not checked.

Write a short `report.md`: the run and its coverage, what the main counts mean, the problems that
matter most, what the comparison shows when there is one, and links to the dashboard, the inventory and
the merge file. The shared report check is required: run `../manuscript-deslop/scripts/style_profile.py REPORT.md --report --check`,
and read it against its pattern list. Register the report, the inventory, the merge file and the outputs
with `runs.py add`; keep failed attempts too. Creating the files does not send them to anyone.
