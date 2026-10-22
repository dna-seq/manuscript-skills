# Infographic data contract

`scripts/infographic.py` accepts UTF-8 JSON, schema version 1. Relative evidence paths resolve from the
input JSON's directory. Evidence files are read locally; neither manuscript text nor chart data is
sent to a service. Only the Python dependency installation needs network access when uncached.

The input is an adjudicated inventory, not an automatic conversion of every scanner message into an
error. Read the reports and revision before preparing it. The renderer computes totals from records
and rejects duplicate IDs, unknown finding links, unsupported status values, absent evidence and
quotations absent from their source. It cannot establish semantic support or recognize two different
IDs assigned to the same underlying issue; that is the preparing agent's responsibility.

## Top-level fields

| Field | Meaning |
|---|---|
| `schema_version` | `1`. |
| `title` | Descriptive title; avoid a claim about measured detection performance. |
| `run_id` | Existing run identifier, or a descriptive identifier for a report without a manifest. |
| `scope` | Versions and review scope, including whether findings are selected or the review is partial. |
| `coverage` | One record per relevant skill: `skill`, `status`, `note`, `evidence`. |
| `findings` | One record per underlying problem; an empty list means no recorded findings within this stated scope. |
| `changes` | One record per distinct proposed or applied edit, independently of finding counts. |
| `limitations` | Plain-language limitations to retain in the graphic and HTML. |
| `illustrative` | Optional Boolean, default false. Set true for synthetic examples; the graphic labels them. |

Coverage statuses are `completed`, `partial`, `blocked`, `not_run`, `reused` and `unknown`. A completed
command is not evidence that its skill covered the whole manuscript. Coverage needs at least one
record, and each finding's `skills` must appear in it.

## Findings

Each finding has `id`, `category`, `section`, `summary`, `severity`, `assessment`, `resolution`,
`skills` and `evidence`. Use short, consistent category names such as References, Claims and evidence,
Numbers and statistics, Reporting, Availability, Writing, Story and structure, or Policy and journal.
Preserve meaningful distinctions; categories are not fixed by the renderer.

- `severity`: `blocker`, `major`, `minor`, `info` or `unknown`. Map an existing report's equivalent
  labels explicitly; do not infer a major scientific problem from a style hit.
- `assessment`: `confirmed`, `candidate` or `dismissed`. Confirmed means supported by the recorded
  adjudication in the stated kind of review. It does not upgrade a simulated reader's concern into
  evidence from real readers, or a style preference into a scientific error.
- `resolution`: `open`, `addressed` or `unknown`. Addressed requires a confirmed finding and at least
  one linked applied edit with evidence. Do not mark a proposal addressed.
- `skills`: all reporting skills, with the finding counted once even when several skills found it.

## Changes and evidence

A change has `id`, `kind`, `section`, `summary`, `status` (`applied` or `proposed`), `finding_ids`,
`before`, `after` and `evidence`. Use null for the before text of an addition or after text of a deletion;
at least one must contain text. Applied before/after text must occur in its cited evidence files.
An applied edit must be checked against the accepted revision, not inferred from a comparison's
`shown_in_chat` field. Independent prose improvements may have an empty `finding_ids` list.

Every evidence record has `path` and `quote`, both nonempty. The quote must occur verbatim in the
local UTF-8 source. Reference the report's finding and, for an applied edit, the actual retained
before/after comparison or source versions. Use more than one evidence record when needed. The HTML
embeds excerpts and source filenames so colleagues can inspect the basis without access to the local
checkout; `summary.json` also retains source hashes. Full paths and unrelated source contents are not
embedded into the chart.

For example, a report that states "One citation names the wrong paper." could support this finding:

```json
{
  "id": "F1",
  "category": "References",
  "section": "Introduction",
  "summary": "A citation names the wrong paper",
  "severity": "unknown",
  "assessment": "confirmed",
  "resolution": "open",
  "skills": ["manuscript-reference-check"],
  "evidence": [{"path": "../manuscript-reference-check/report.md", "quote": "One citation names the wrong paper."}]
}
```

This is a schema illustration, not a real result. Use the actual report's words, location, assessment
and severity, and include its skill in coverage. Add change records only when there is edit evidence.

## Counting rules

The four headline values are confirmed findings, confirmed findings addressed, applied edits and
candidate findings. Dismissed flags, proposed edits and confirmed findings with unknown resolution
stay separate in the report. Status and category charts count confirmed findings only. Change charts
count edits only. A finding with three sources is one finding, and five applied edits linked to one
finding are five edits but at most one addressed finding.

Do not sum per-skill attribution as independent discoveries, compare unequal scopes, or label the
fraction addressed as a detector's accuracy. Without a known ground truth, a run cannot show how many
problems the skills missed.
