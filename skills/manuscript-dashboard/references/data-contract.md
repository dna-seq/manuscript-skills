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
| `manuscript` | `title`, `version`, `sha256`, `sections` in manuscript order, for the heat grid, and `path`, the reviewed text relative to the inventory, for the manuscript view. |
| `signals` | raw output screened before adjudication: `skill`, `check`, `count`, `note` (scanner hits by check, referee proposals, reader concerns). |
| `dismissed` | flags examined and rejected: `skill`, `summary`, `why`. Counted with dismissed findings, never as problems. |
| `not_checked` | checks that could not run: `skill`, `check`, `why`, `leaves_open`. |
| `decisions` | choices only the authors can make, as the adjudication wrote them: `id`, `summary`, `finding_ids`. The dashboard lists these and then every finding with `decision: true` that none of them links; one written decision never hides the stages' own. |
| `panel` | `readers` (`seat`, `takeaway`, `stopped_at`, `next`, `left`, `dips`, `path`, `round`, `isolation`, `model`), the simulated reviewers' `recommendations` (`seat`, `venue`, `recommendation`, `reason`) and `reviewers` (`seat`, `summary`, `strengths`, `isolation`, `model`, and `concerns`: `id`, `severity`, `location`, `concern`, `suggestion`, `route`, `placement`, `cost`, `defence`, `verdict`, `verdict_evidence`, `finding_ids`). |
| `reference` | a review to compare with; [below](#reference-review). |
| `figures` | optional, from `manuscript-figures`; [below](#figures). |
| `story` | optional, from `manuscript-story`: the direction, the story tests and the options only the authors can choose; [below](#story). |
| `coauthors` | optional, from `manuscript-coauthors`: the co-authors' comments on the previous release and how the next one answers each; [below](#co-authors-comments). |
| `todo` | optional, from collect: the authors' to-do marks file beside the manuscript (`STEM.todo.json`) and every mark in it; [below](#to-do). |
| `reference_list` | optional, the manuscript's reference list as the reference check left it (scan.py's JSON in the reference-check folder, else the integrity-check one): one record per entry with `n` (its place in the list), `line`, `text`, `state` (its worst: `fine`, `corrected`, `unverified`, `not-checked`, `wrong` or `retracted`), `link` (doi.org, PubMed or arXiv) and `notes` (what the scanner found, in its words). The Overview shows it as one cell per entry. |
| `venues` | the journal and preprint ladders from manuscript-journal-select, one record per rung: `ladder`, `rung`, `name`, `key`, `chosen`, fit, impact factor, first-decision days, fee, preprint rule, AI-policy points and `ai_policy` (`aspects`: `drafting`, `prompts`, `records`, `detection`, `declaration`, `counted` and `extra`, each with `level` `good`, `warning`, `red` or `unknown` and `text`; `reasons`, `url`, `source`). |

Coverage statuses are `completed`, `partial`, `blocked`, `not_run`, `reused`, `in_progress` (the stage was
still running when the inventory was collected; its evidence quotes its README's title, which does not change
when it finishes) and `unknown`. A completed command is not evidence that its skill covered the whole
manuscript. Coverage needs at least one record, and each finding's `skills` must appear in it. `collect.py`
leaves manuscript-improve out while it is still running (it is the run collecting itself), unless it recorded
findings of its own.

## Findings

Each finding has `id`, `category`, `section`, `summary`, `severity`, `assessment`, `resolution`,
`skills` and `evidence`, and in version 2 optionally `stage`, `quote`, `detail`, `action`, `decision` and
`sources`. Use the category names of [stage findings](stage-findings.md#rules).

- `severity`: `blocker`, `major`, `minor`, `info` or `unknown`, shown as Blocker, Major, Minor, Optional and
  Could not be checked ([stage findings](stage-findings.md#rules) has the mapping: a referee's `optional` is
  `info`, `uncertain` is `unknown`). Map an existing report's equivalent labels explicitly; do not infer a
  major scientific problem from a style hit.
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
`before`, `after`, `anchor`, `why`, `comment`, `evidence` and, for a change to another file than the
manuscript, `document`: that file's name as the run took it in (`paper-supplementary.md`), empty for the
manuscript. The corrected version is built from the manuscript and leaves another file's changes alone;
`collect.py` replays an applied edit on its own file, so a sentence the supplement repeats from the
manuscript is never changed in the wrong copy. `comment` is a question for the authors about the edit, shown
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
  "evidence": [{"path": "../manuscript-reference-check/stage-report.md", "quote": "One citation names the wrong paper."}]
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
  "matched_by": "the coordinating agent, after the inventory was frozen",
  "items": [{"id": "C16", "origin": "reviewer", "kind": "comment", "summary": "...", "category": "Text versus code",
             "section": "3.2", "substantive": true}],
  "matches": [{"reference_id": "C16", "finding_ids": ["IC-4"], "match": "full", "note": "Same percentile method."}]
}
```

`matched_by` (optional) says who matched the items to the run's findings; the dashboard shows it beside the
comparison. Each item is one problem the reference raised, with the same category words. `substantive` is false
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
confirmed findings no item matches. Give the reference to collect together with the merge file
(`--merge merges.json --reference reference.json`): the matches name the IDs the adjudication keeps.

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
is "figures" or "figures and tables", and `source`), `items` (one per figure or table: `id`, `kind` of
`figure` or `table`, `part` of `main` or `supplement`, `caption`, `image` (a figure's), `verdict` of `keep`,
`change`, `merge`, `move-to-supplement` or `move-to-main-text`, `merge_with` (with `merge` only, and then
required: the IDs of the other items it joins into one figure or table), `message`, `why`, `recommendations` each with `kind`
`content` or `visual`, `change` and `why`, `proposed_image`, `code` and `finding_ids`) and `new` (figures to add:
`title`, `kind`, `shows`, `why`, `placement`, `source`, `replaces`, `finding_ids`). `collect.py` makes the image
paths relative to the inventory and follows each finding link to the record kept after merging; the renderer
embeds the images, so the dashboard stays one file, and says when one could not be found or is over 8 MB.
`summary.json` counts the verdicts, the new figures and the main-text display items now and if the authors
accept every move, merge and addition (tables count when the venue counts figures and tables together; a
group of items joined by merges counts once). Which
figures and tables the paper has is the authors' decision: moves, merges and additions are listed as
decisions, never counted as applied.

## Co-authors' comments

`coauthors` is optional and comes from `manuscript-coauthors`' `findings.json`: `round` (the release the
co-authors commented on, such as "0.5"), `next_round` (the release that answers them, or null while it is
not written), `source` (the ledger's file name, never a path) and `items`, one per comment or suggested edit,
in the ledger's order: `id` (unique; `C<n>` for a comment, `S<n>` for a suggestion), `kind` of `comment` or
`suggestion`, `author`, `date`, `where` (the manuscript heading), `anchor` (the text the comment is attached
to in the Doc), `comment` (verbatim), `replies` (each `author`, `date`, `text`), `edits` (a suggestion's
own: `deleted`, `inserted`), `resolved` (true, false, or null when the export does not say), `status` of
`addressed`, `partly`, `open`, `declined` or `not-on-point`, `change` of `changed`, `unchanged`, `removed`,
`moved` (no counterpart in place, but a revision-mark segment named for the comment holds it
elsewhere; its text is `after`), `not-located` or null, `before` and `after` (the paragraph in each release, or null), `now` (the verbatim
passage of the new release that answers it), `why` (what was done and why, or why not), `next` (what could
still be done), `rev_ids` (the revision-mark segments of the new release that hold the answer) and
`finding_ids` (the `CA-n` findings for a comment not fully answered). The renderer rejects two items with
one ID, a `declined` or `not-on-point` item without `why`, an `open` or `partly` one without `next`, an
`addressed` or `partly` one without `now`, edits on a comment, and a link to a finding the inventory does
not have. `collect.py` takes the object from the stage's newest `findings.json`, keeps the ledger's name
only and follows each finding link to the record kept after merging (a dismissed one is dropped).
`summary.json` counts the items by status and by co-author and how many are answered: addressed, or
declined or set aside with the reason given. The Co-authors' comments tab (`#coauthors/C40` opens one) shows
each comment with its thread, the before-and-after word diff, the reason and what could still be done, and
links to its findings and to the passage's edit history in the manuscript.

## Story

`story` is optional and comes from `manuscript-story`'s `findings.json`: `direction`, `confirmed` (the authors
confirmed it), `drift`, `tests` (each with `test`, `result` of `holds`, `partly`, `fails` or `not-run`, `note`,
`finding_ids` and `change_ids`) and `options` (each with `title`, `summary`, `readers` and `cost`). The Story
tab shows it with the story stage's findings and edits; without it the tab shows those alone.

## To-do

`todo` is what collect found of the marks the authors made in the dashboard's To-do tab: `file` (the file's name,
never its folder; the name the tab saves under while there are no marks yet), `schema_version` (`1`), `manuscript`
(the manuscript's file name) and `marks`. The file beside the manuscript holds the same fields but `file`, and the
marks of every run of the paper, the oldest first. Each mark is on one item of one run, at most once:

| Field | Meaning |
|---|---|
| `run_id`, `kind`, `id` | The item: its run, its kind (`decision`, `question` for an applied edit that asks the authors something, `proposal`, `problem`) and its ID in that run. |
| `mark` | `approved`: do it, or keep the edit. `redundant`: drop it, undo the edit, and do not raise it again. |
| `reason`, `marked_at` | The authors' reason or answer (optional) and when they marked it (ISO 8601); of two marks on one item, the later wins. |
| `summary`, `section`, `category`, `quote`, `action`, `before`, `after`, `anchor`, `finding_ids` | What the item said, so a later run whose IDs are its own recognises it. |

The tab's items are computed, never stored (`dashboard.todo_items`): the decisions, the applied edits that ask a
question, the proposals in this version or waiting for an answer (a held proposal is not one) and the open blocker
or major problems none of those and no edit in the text answers. An item restates a mark when it says word for word
what the marked item said (`dashboard.restates`): an edit with the same text before and after, a decision with the
same summary, a problem about the same passage with the same category or summary, or about no passage with the
same summary; spacing, case and a final full stop aside. An item restating an earlier run's redundant mark, with no
mark of its own run, is set aside; `summary.json`'s `todo` counts the items, the open, approved and redundant ones,
the set-aside ones and the items by kind.
