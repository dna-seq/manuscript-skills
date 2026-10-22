---
name: manuscript-visualize
description: >-
  Turn saved manuscript review findings and revisions into evidence-linked infographics for colleagues.
  Use to visualize what manuscript-improve or a focused manuscript skill caught, changed or left open,
  with counts by problem type, severity and resolution. Creates shareable HTML, SVG and PNG using
  Vega-Lite. Scientific results figures and new manuscript reviews belong to their own workflows.
---

# Visualize what the review found and changed

Make the existing work understandable to a colleague who did not follow the chat. Show the supported
findings, applied and proposed edits, remaining work and review coverage. Use the saved run and its
evidence; a request for an infographic does not ask for another review or manuscript edit.

Read the shared [author priorities](../manuscript-integrity-check/references/author-priorities.md) and
reuse the [project and run](../manuscript-integrity-check/references/project-workflow.md). Save the
infographic inputs, outputs and interpretation under `RUN/manuscript-visualize/`. Use the run index,
`run.json`, companion reports, adjudications, source snapshots and before/after comparisons to establish
what actually happened. Older reports without a run manifest can still be visualized: state their
scope and unknown coverage rather than inventing a complete run.

## Build an evidence-backed inventory

Follow [the data contract](references/data-contract.md) to write `findings.json`. Read the underlying
reports; the run manifest's command failures and operational `issues` are not a list of manuscript
defects, and a recorded comparison does not prove that its edit was applied.

- Give each distinct underlying problem one finding ID. Merge repeated reports of the same problem
  across skills or reviewer seats, keeping their attribution and evidence. Do not sum every raw flag,
  citation mention, style hit or rerun into "problems caught". Distinct errors need distinct evidence.
- Separate adjudicated findings, candidates needing verification and dismissed flags. A count of reader
  concerns remains reader feedback, not a count of established scientific errors. Keep original
  severity when supplied; use `unknown` when it was not assessed.
- Record each applied or proposed edit once, with exact before/after text and evidence. Link edits to
  finding IDs when they address them; multiple edits can address one finding, and one edit can address
  several. Call a finding addressed only after checking the revision and its supporting evidence.
- State the manuscript/version, run and scope. Keep partial, blocked and unrun work visible. Missing
  findings from an unrun stage are unknown, not zero. Selected examples must say "selected" prominently.
- Preserve disagreements and limitations. These counts describe observed output on this run; they do
  not measure sensitivity, recall, scientific quality, publication readiness or acceptance probability.

Each finding, edit and coverage statement needs a local evidence path and an exact supporting quote.
Use saved evidence copies for remote sources. The renderer checks that files and quotations exist; the
agent must still check that they support the interpretation and that deduplication is correct.

## Render the infographic

Run from this skill directory, with paths pointing into the established run:

```bash
uv run --script scripts/infographic.py RUN/manuscript-visualize/findings.json \
  --output-dir RUN/manuscript-visualize/infographic
```

The renderer produces:

- `infographic.html`: a self-contained report with the Vega-Lite chart, searchable evidence and exact
  before/after passages. It opens offline and can be shared as one file.
- `infographic.svg` and `infographic.png`: a concise graphic suitable for slides and messages, with
  scope and coverage visible in the image.
- `infographic.vl.json` and `summary.json`: the editable chart specification and derived counts.

Use bars with integer counts and a zero baseline. The default graphic separates confirmed findings,
addressed findings, applied edits and candidates, with breakdowns by problem type, severity and status.
Retain those distinctions if changing the design. Use direct labels and enough room for the actual
categories. Avoid a single "quality score", exaggerated percentage improvements and decorative charts
that make overlapping counts appear additive.

For a before/after comparison, require comparable reviewed versions and scope, with each remaining
finding rechecked. An edit inventory alone supports a chart of edits, not a fall in manuscript errors.
Do not invent a baseline or assume that an issue absent from a later report was fixed.

## Check and deliver

Reconcile every displayed total with `summary.json` and the normalized records. Inspect the PNG at its
intended display size and the HTML in an available browser. Check long labels, empty categories, partial
coverage, evidence search and the before/after comparisons. Fix layout or runtime errors before handover.
If no browser is available, retain the image check and state that interactive behavior was not checked.

Write a short `report.md` naming the run and coverage, explaining what the main counts mean and linking
the infographic and evidence inventory. The shared report check is required; run
`../manuscript-deslop/scripts/style_profile.py REPORT.md --report --check` and read its pattern list.
Register the report, infographic, normalized data and summary in the existing run with `runs.py add`;
keep failed attempts too. Return a preview and links to the shareable outputs. Creating the files does
not send them to colleagues or publish them.

