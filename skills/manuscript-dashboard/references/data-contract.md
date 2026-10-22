# Inventory data contract

`scripts/dashboard.py` accepts UTF-8 JSON, schema version 2, which `scripts/collect.py` writes from a
run. Relative evidence paths resolve from the inventory's directory. Evidence files are read
locally; neither manuscript text nor chart data is sent to a service. Only the Python dependency
installation needs network access when uncached.

The input is an adjudicated inventory, not an automatic conversion of every scanner message into an
error. The renderer computes totals from records and rejects duplicate IDs, unknown finding links,
unsupported status values, absent evidence and quotations absent from their source. It cannot establish
semantic support or recognise two different IDs assigned to the same underlying issue; that is the
adjudicator's responsibility ([SKILL.md](../SKILL.md#2-adjudicate-one-record-per-problem)).

## Top-level fields

| Field | Meaning |
|---|---|
| `schema_version` | `2`. |
| `title` | Descriptive title; avoid a claim about measured detection performance. |
| `run_id` | Existing run identifier, or a descriptive identifier for a report without a manifest. |
| `scope` | Versions and review scope, including whether findings are selected or the review is partial. |
| `coverage` | One record per relevant skill: `skill`, `status`, `note`, `evidence`. |
| `findings` | One record per underlying problem; an empty list means no recorded findings within this stated scope. |
| `changes` | One record per distinct proposed or applied edit, independently of finding counts. |
| `limitations` | Plain-language limitations to retain in the dashboard. |
| `illustrative` | Optional Boolean, default false. Set true for synthetic examples; every output labels them. |
| `manuscript` | `title`, `version`, `sha256` and `sections` in manuscript order, for the heat grid. |
| `signals` | raw output screened before adjudication: `skill`, `check`, `count`, `note` (scanner hits by check, referee proposals, reader concerns). |
| `dismissed` | flags examined and rejected: `skill`, `summary`, `why`. Counted with dismissed findings, never as problems. |
| `not_checked` | checks that could not run: `skill`, `check`, `why`, `leaves_open`. |
| `decisions` | choices only the authors can make: `id`, `summary`, `finding_ids`. |
| `panel` | `readers` (`seat`, `takeaway`, `stopped_at`, `next`, `left`, `dips`, `path`, `round`), the simulated reviewers' `recommendations` (`seat`, `venue`, `recommendation`, `reason`) and `reviewers` (`seat`, `summary`, `strengths`, and `concerns`: `id`, `severity`, `location`, `concern`, `suggestion`, `route`, `placement`, `cost`, `defence`, `verdict`, `verdict_evidence`, `finding_ids`). |
| `reference` | a review to compare with; [below](#reference-review). |
| `figures` | optional, from `manuscript-figures`; [below](#figures). |
| `venues` | the journal and preprint ladders from manuscript-journal-select, one record per rung: `ladder`, `rung`, `name`, `key`, `chosen`, fit, impact factor, first-decision days, fee, preprint rule, AI-policy points and `ai_policy` (`aspects`: `drafting`, `prompts`, `records`, `detection`, `declaration`, `counted` and `extra`, each with `level` `good`, `warning`, `red` or `unknown` and `text`; `reasons`, `url`, `source`). |

Coverage statuses are `completed`, `partial`, `blocked`, `not_run`, `reused` and `unknown`. A completed
command is not evidence that its skill covered the whole manuscript. Coverage needs at least one
record, and each finding's `skills` must appear in it.

## Findings

Each finding has `id`, `category`, `section`, `summary`, `severity`, `assessment`, `resolution`,
`skills` and `evidence`, and in version 2 optionally `stage`, `quote`, `detail`, `action`, `decision` and
`sources`. Use the category names of [stage findings](stage-findings.md#rules).

- `severity`: `blocker`, `major`, `minor`, `info` or `unknown`. Map an existing report's equivalent
  labels explicitly; do not infer a major scientific problem from a style hit.
- `assessment`: `confirmed`, `candidate` or `dismissed`. Confirmed means supported by the recorded
  adjudication in the stated kind of review. It does not upgrade a simulated reader's concern into
  evidence from real readers, or a style preference into a scientific error.
- `resolution`: `open`, `addressed` or `unknown`. Addressed requires a confirmed finding and at least
  one linked applied edit with evidence. Do not mark a proposal addressed.
- `skills`: all reporting skills, with the finding counted once even when several skills found it.
- `stage`: `now`, `writing`, `journal`, `final` or `unknown`, as in the authors' order of work.
- `quote`: the manuscript passage, verbatim; `null` for an absence.
- `sources`: the raw records merged into this one, as `{skill, id}`, so each count can be traced.

## Changes and evidence

A change has `id`, `kind`, `section`, `summary`, `status` (`applied` or `proposed`), `finding_ids`,
`before`, `after`, `why`, `comment` and `evidence`. `comment` is a question for the authors about the edit, shown
beside it and never written into the text. `why` is the reasoning in one to three sentences: what was wrong
and why the new wording fixes it; the `summary` is only its title. For an applied edit, `collect.py` takes
`why` from the reason recorded with `runs.py change`, whose first sentence becomes the summary. Use null for the before text of an addition or after text of a deletion;
at least one must contain text. An addition names `anchor`, the verbatim passage it follows, so that
the corrected version can place it; a replacement has no anchor. Applied before/after text must occur in its cited evidence files.
An applied edit must be checked against the accepted revision, not inferred from a comparison's
`shown_in_chat` field. Independent prose improvements may have an empty `finding_ids` list.

Every evidence record has `path` and `quote`, both nonempty. The quote must occur verbatim in the
local UTF-8 source. Reference the report's finding and, for an applied edit, the actual retained
before/after comparison or source versions. Use more than one evidence record when needed. The
dashboard embeds excerpts and file names so colleagues can inspect the basis without the local
checkout; `summary.json` also retains source hashes. Full paths and unrelated source contents are not
embedded.

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

## Reference review

`reference` compares the run with another review of the same version:

```json
{
  "title": "the referee's review",
  "description": "Robi Tacutu's 39 comments and 26 suggested-edit paragraphs on v0.3, recovered from the revision history.",
  "source": {"path": "reference-items.json", "quote": "a verbatim line of that file"},
  "items": [{"id": "C16", "origin": "reviewer", "kind": "comment", "summary": "...", "category": "Text versus code",
             "section": "3.2", "substantive": true}],
  "matches": [{"reference_id": "C16", "finding_ids": ["IC-4"], "match": "full", "note": "Same percentile method."}]
}
```

Each item is one problem the reference raised, with the same category words. `substantive` is false
for wording-only items. For an item the run did not catch in full, `miss_reason` says why and `owner`
names the skill whose remit covers it, so each miss points at the skill to improve:

| `miss_reason` | Meaning |
|---|---|
| `no-skill-covers` | No skill's remit includes this kind of problem. |
| `skill-did-not-look` | A skill's remit covers it and the run did not examine it. |
| `judged-differently` | The run examined the passage and judged it acceptable, or dismissed the flag. |
| `input-missing` | Catching it needed something the run did not have (a file, a source, the authors' knowledge). |
| `wording-preference` | The reviewer's preferred wording; not a defect in the text. |
| `later-decision` | A change of scope or plan made after this version, not a problem in it. |

`miss_note` gives the specific reason in a sentence. A fully matched item has no miss reason. Each item has at most one match record, listing every finding that answers it;
an item without one counts as not caught. A match never rests on a dismissed flag. The renderer counts
matched, partly matched and not caught items overall, by category and among substantive items, and the
confirmed findings no item matches.

## Counting rules

The headline values are confirmed problems, problems to fix now, blockers and major problems,
candidates, applied and proposed edits, and problems several skills found. Dismissed flags, proposed
edits and confirmed problems with unknown resolution stay separate. Status, category, stage and section
charts count confirmed problems by default; the dashboard's filter can show candidates or dismissed
flags instead, never added to them. Change charts count edits only. A finding with three sources is one
finding, and five applied edits linked to one finding are five edits but at most one addressed finding.
The skill chart counts attribution, so its bars add up to more than the total.

Do not sum per-skill attribution as independent discoveries, compare unequal scopes, or label the
fraction addressed as a detector's accuracy. Without a reference, a run cannot show how many problems
the skills missed; with one, the missed count is relative to that reference only.

## Figures

`figures` is optional and comes from `manuscript-figures`' `findings.json`: `limit` (`count`, `counts`, which
is "figures" or "figures and tables", and `source`), `items` (one per figure: `id`, `caption`, `image`,
`verdict` of `keep`, `change` or `move-to-supplement`, `message`, `why`, `recommendations` each with `kind`
`content` or `visual`, `change` and `why`, `proposed_image`, `code` and `finding_ids`) and `new` (figures to add:
`title`, `kind`, `shows`, `why`, `placement`, `source`, `replaces`, `finding_ids`). `collect.py` makes the image
paths relative to the inventory and follows each finding link to the record kept after merging; the renderer
embeds the images, so the dashboard stays one file, and says when one could not be found or is over 8 MB.
`summary.json` counts the verdicts, the new figures and the main-text figures now and if the authors accept
every move and addition. Which figures the paper has is the authors' decision: moves and additions are
listed as decisions, never counted as applied.

## Story

`story` is optional and comes from `manuscript-story`'s `findings.json`: `direction`, `confirmed` (the authors
confirmed it), `drift`, `tests` (each with `test`, `result` of `holds`, `partly`, `fails` or `not-run`, `note`,
`finding_ids` and `change_ids`) and `options` (each with `title`, `summary`, `readers` and `cost`). The Story
tab shows it with the story stage's findings and edits; without it the tab shows those alone.
