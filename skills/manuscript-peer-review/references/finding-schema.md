# Finding schema and contract

Every concern a seat raises is written as one JSON finding. It is a proposal until it passes
`scripts/check_findings.py` and the adjudication in [adjudication.md](adjudication.md). A finding that
fails the contract is listed as a "not yet finding" with the reason; it is never dropped silently and
never reaches the report as a concern.

The field names, ids and values below are working vocabulary for the seats, the script and the
adjudicator. The report for the authors says what they mean in words and quotes the manuscript
([output-format.md](output-format.md#content-rules)); an id or value appears there only in parentheses.

## File layout

A seat writes a JSON object with `findings`, `strengths` and its `report` (its summary and
recommendations, written last; [below](#the-referees-report)); a bare list of findings is also accepted.
The orchestrator merges the seats' files into one object, keeping each finding's `seat` and putting
each seat's report, with its `seat`, in the list `reports`.

```json
{
  "findings": [
    {
      "id": "EV-1",
      "seat": "evidence-statistics",
      "location": "Methods, Benchmark",
      "quote": "We assigned ClinVar variants at random to training (80%) and test (20%) sets.",
      "concern": "A variant-level random split puts variants from the same gene in both sets, and three features are gene-level constraint metrics, so test performance can reflect gene membership rather than variant effect.",
      "claim": "Abstract: VarRank 'outperformed existing pathogenicity predictors' on held-out variants.",
      "consequence": "validity",
      "severity": "major",
      "change_my_mind": "Results on a gene-disjoint split, or evidence that performance is unchanged when test genes are excluded from training.",
      "route": "author-required",
      "cost": "reanalysis"
    },
    {
      "id": "CN-2",
      "seat": "claims-novelty",
      "location": "Introduction, paragraph 1",
      "quote": "VarRank is the first tool to combine evolutionary conservation and population allele frequency",
      "concern": "The priority claim is contradicted by prior work: CADD already combines conservation and allele frequency in one score.",
      "claim": "Introduction: the priority claim for VarRank.",
      "consequence": "support",
      "severity": "major",
      "change_my_mind": "A narrower statement of what VarRank does differently, with the comparison that shows it.",
      "route": "fixable-in-text",
      "cost": "text",
      "prior_work": [
        {"citation": "Kircher M et al. Nature Genetics 2014", "identifier": "10.1038/ng.2892", "status": "verified",
         "checked_by": "manuscript-reference-check"}
      ]
    },
    {
      "id": "RP-1",
      "seat": "reproducibility",
      "kind": "absence",
      "location": "Methods, Model",
      "looked_in": ["Methods, Model", "Data and code availability", "Supplementary Table S1 (not supplied)"],
      "quote": "VarRank is a logistic regression on 12 features",
      "concern": "The regularisation and the software used to fit the model are not stated.",
      "claim": "Availability: the benchmark can be reproduced from the released scripts.",
      "consequence": "reproducibility",
      "severity": "optional",
      "change_my_mind": "The fitting library, version and regularisation in Methods.",
      "route": "fixable-in-text",
      "cost": "text"
    }
  ],
  "strengths": [
    {"seat": "champion", "location": "Methods, Model",
     "quote": "Features were standardised on the training set.",
     "note": "Standardising on the training set only avoids one common form of leakage."}
  ],
  "reports": [
    {
      "seat": "evidence-statistics",
      "summary": "The authors present VarRank, a logistic regression on 12 features that ranks missense variants, and claim it outperforms existing predictors on held-out ClinVar variants. The model is simple and clearly described, but the benchmark cannot yet support the comparative claim.",
      "recommendations": [
        {"venue": "bioinformatics", "recommendation": "major-revision", "form_wording": "Major revision",
         "reason": "The headline comparison rests on a split that can leak gene identity into the test set.",
         "rests_on": ["EV-1"]}
      ]
    }
  ]
}
```

## Fields

| Field | Required | Values and meaning |
|---|---|---|
| `id` | yes | Unique within the file. A seat prefix helps (`EV-1`, `SK-3`). |
| `seat` | yes | `claims-novelty`, `evidence-statistics`, `reproducibility`, `champion`, `skeptic`, `desk-editor`, `software-methods`, `genomics`, `human-data-clinical`, `ai-systems`, or `custom:<name>` for a seat the authors added; followed by `@<cli>` for the same seat on another model (`skeptic@codex`). |
| `location` | yes | Section, paragraph, table, figure or supplementary item, as a reader would find it. |
| `kind` | no | `present` (default): the problem is in the text. `absence`: something needed is missing. |
| `quote` | for `present` | Verbatim text from the manuscript or a supplied supplementary file. Copy it; never paraphrase. `...` or `…` may skip words within one passage. At least 3 words or 12 characters. |
| `looked_in` | for `absence` | Non-empty list of the places the seat searched for the missing item. An absence finding may also quote the claim that needs the missing item. |
| `source` | no | File name of a supplementary file the quote comes from. Without it, the manuscript is searched first, then each supplied supplement. |
| `concern` | yes | What is wrong, in one or two sentences a referee would write. One problem per finding: two problems in one passage are two findings, each with its own `change_my_mind`, so that each can be confirmed, refuted and fixed on its own. Findings that share a root cause take one `group` label instead. |
| `claim` | yes | The claim at stake: its text or location, or a claim id from `manuscript-record.yaml`. |
| `consequence` | yes | What resolving the concern could change about that claim: `validity`, `support`, `scope`, `reproducibility` or `interpretation`. This is the claim-consequence gate. |
| `severity` | yes | `blocker`, `major`, `optional` or `uncertain`, as defined in [author-priorities.md](../../manuscript-integrity-check/references/author-priorities.md#findings-and-stopping). A seat proposes it; adjudication may change it. |
| `change_my_mind` | yes | The specific evidence, analysis or wording that would resolve the concern. |
| `route` | yes | Proposed route: `fixable-in-text`, `author-required`, `venue`, `policy` or `dropped`. Adjudication sets the final one. |
| `drop_reason` | with `dropped` | Why the finding goes no further. |
| `cost` | no | `text`, `reanalysis` (existing data), `new-data` (new data, experiments or recruitment) or `unknown`. Used to rank. |
| `hand_to` | no | The skill that takes the work: `manuscript-prose-edit`, `manuscript-reference-check`, `manuscript-reporting-check`, `manuscript-integrity-check`, `manuscript-policy-fit`, `manuscript-journal-adapt`, `manuscript-journal-select` or `manuscript-story`. |
| `placement` | no; with `fixable-in-text` | Where the fix costs readers least: `with-claim` (a doubt about the central claim, said once beside it), `limitations`, `methods`, `supplement` or `response-letter` (defensive detail a referee needs and readers do not). Set in adjudication ([adjudication.md](adjudication.md#7-routes)). |
| `prior_work` | when the concern asserts prior work | List of `{citation, identifier, status, checked_by}`. `status` is `verified` (the identifier resolved to the named work, in this review's lookup or a current manuscript-reference-check result) or `unverified` (the identifier could not be resolved, or the work has none). Identifiers the manuscript itself gives are resolved too. `verified` needs an identifier: DOI, PMID, arXiv id, ISBN or URL. |
| `norm_source` | when the finding asks for what the field or the journal expects | Where that expectation is written: `venue: "<words quoted from venue.md>"`, `guideline: <guideline and item>` (`TRIPOD+AI 12`), `module: <domain module and question>`, or `own: <why this referee expects it>` when it is written nowhere the seat was given. Replication, more samples, an external cohort and a "standard" analysis are the usual cases. |
| `external_claim` | no | `true` forces the prior-work rule; `false` declares that wording such as "existing tools" does not assert prior work (reported as a warning so the adjudicator can look). |
| `criterion` | expected, or `off_criterion` | The id of the criterion in the seat's `criteria.md` the finding falls under (`C2`; a list when it meets two). The criteria were written before the seat read the paper. |
| `off_criterion` | instead of `criterion` | Why a problem none of the seat's criteria anticipated matters anyway. With `--criteria`, the check lists a major or blocking finding outside the criteria for the adjudicator; it is not held back. |
| `group` | no | A label shared by findings the seat or adjudicator knows are one concern. |
| `verdict` | after adjudication | `confirmed`, `refuted` or `downgraded`. |
| `verdict_evidence` | with every verdict | What settled it: the text that shows the problem or answers it, a recomputation from the paper's own numbers, a checked record. For a partly answered finding, the answering text and the part left open. |
| `defence_quote` | with `refuted` | The verbatim text that answers the concern; for a premise the quoted text does not support, the finding's own quote or the passage that shows the premise wrong. `defence_source` names a supplementary file when needed. |
| `triage` | with `confirmed` or `downgraded` | `substance`, `misread-risk` or `polish`. |
| `stage` | no; set in adjudication | When the authors can act on it: `now` (the science and the evidence), `writing`, `journal` (depends on the chosen venue) or `final` (archive records, release tags, version numbers, declarations: once the code is final, never a blocker for a draft). Without it, the script takes `journal` for the `venue` route, else `writing` for a misread risk or polish, else `now`; a finding with a `hand_to` integrity, reference or reporting check is listed with the other checks unless its stage is `final` ([adjudication.md](adjudication.md#8-merging-triage-and-ranking)). |

Strengths have `seat`, `location`, `quote` and `note`, all required; their quotes are checked the same
way.

## The referee's report

Each seat ends its file with `report`, written only after its findings and strengths are complete
([seats.md](seats.md#the-seat-brief)): what a referee puts at the top of a report and in the journal's
recommendation box. The orchestrator builds the report the authors read from it and from the seat's
adjudicated findings; the seat never writes the concerns twice.

| Field | Required | Values and meaning |
|---|---|---|
| `seat` | in a merged file | The referee who wrote it. In a seat's own file it is taken from the findings. |
| `summary` | yes | The paper and the referee's overall view, as the opening paragraph of a referee report: what the authors claim, how they support it, and whether it holds. Three to five sentences. |
| `recommendations` | yes | One entry per journal in `venue.md`, each as below. |
| `recommendations[].venue` | yes | The journal's catalogue key (`bioinformatics`), or its name when it has none. |
| `recommendations[].recommendation` | yes | `accept`, `minor-revision`, `major-revision` or `reject`. |
| `recommendations[].form_wording` | no | The journal form's own label when `venue.md` names one ("Reject and resubmit", "Revise"). |
| `recommendations[].reason` | yes | One or two sentences naming what the recommendation turns on. |
| `recommendations[].rests_on` | yes, except for `accept` | Ids of this referee's own findings that the recommendation rests on. |
| `recommendations[].fit` | no | Scope, article type or the journal's bar, when they change the recommendation for this journal. |

No scores, ratings or acceptance odds anywhere. A quick pass writes no report
([seats.md](seats.md#quick-pass-for-an-integrity-audit)).

## What the script checks

- **Quotes.** Each `quote`, `defence_quote` and strength quote must occur in the manuscript or a
  supplied supplementary file after normalisation: Unicode compatibility forms, curly quotes and
  dashes unified, `--` read as a dash, whitespace and line breaks collapsed, case ignored. A second
  view also removes simple markup: Markdown emphasis, code spans, links, headings and table pipes;
  LaTeX commands, braces, `~`, escaped characters, `\cite`, `\ref` and `\label` with their arguments;
  numeric citation brackets. HTML comments, and LaTeX `%` comments in `.tex` files, are not quotable:
  a referee never sees them. The report gives the line where the quote starts and ends.
- **Status of a quote** is three-valued: `verified`, `not_found` (fails the contract, with the longest
  opening run that does occur, to help correct a misquote), or `not_assessed` when it names a
  supplementary file that was not supplied or is not text (a binary file such as a spreadsheet or a PDF;
  any text file is read, whatever its name). `not_assessed` is not a pass, and the report names each file
  it could not read instead of listing it as searched.
- **Fields.** Required fields present and non-empty; enumerated fields within their values; ids unique;
  `looked_in` for absence findings; `drop_reason` for `dropped`; with `--adjudicated`, a verdict on
  every finding, triage on confirmed and downgraded ones, `verdict_evidence` on every verdict, and a
  verified `defence_quote` on refuted ones.
- **Prior work.** A concern that says the work is not novel, already done, or omits existing tools or
  prior work must name at least one work with an identifier and `status: verified`, or with
  `status: unverified`.
- **Where an expectation is written** (a warning): a finding that asks for replication, more samples, an
  external cohort or what the field "expects" or "requires", and gives no `norm_source`. A `norm_source` that
  does not start with `venue:`, `guideline:`, `module:` or `own:` fails; with `--venue venue.md`, so does a
  `venue:` quote that does not occur in venue.md.
- **One concern per finding** (a warning): a concern that numbers its points, opens a sentence by adding
  another ("Second,", "In addition,", "Another problem"), or runs to four sentences or more. Split it.
- **Fairness warnings** (not failures): a concern resting on state-of-the-art standing, one that asks
  for new work, or one that objects to simplicity. The adjudicator decides; see
  [adjudication.md](adjudication.md#3-fairness-filter).
- **Criteria** (with `--criteria SEAT=PATH`, one per seat; these are warnings and never fail a finding). Each seat's
  `criteria.md` is read for its numbered criteria (`C1.` ...) and the later lines that start with an id (what
  was checked). The check warns on a major or blocking finding that names no criterion of its seat (with
  `off_criterion`, it gives the reason), on a criterion id the seat never wrote, on a criterion that repeats
  twelve or more words of the manuscript in a row (written after reading), and on a criterion with neither a
  finding nor a line saying what was checked.
- **Reports.** Each report names its referee, has a summary, and gives one recommendation per journal
  from the four values, with a reason and the referee's own findings it rests on (a finding another
  referee raised, or one not in the file, fails). A referee who wrote findings but no report is named,
  so that the result says it gave none; a file with no reports at all (a quick pass) is not an error.
  A referee who left out a journal another referee was asked about is named. With `--adjudicated`, each
  recommendation lists the findings it rests on that the defence refuted, adjudication dropped or
  narrowed, or that have not met the contract, and each referee's confirmed and downgraded findings are
  sorted into the sections of its report: `major` and `blocker` as major concerns (except a finding that
  waits until the code is final), `optional` and end-stage ones as minor concerns, `uncertain` as
  questions for the authors.
- **Groups.** Findings that meet the contract are grouped when their quotes overlap in the same file,
  they share a `group` label, their concerns are near-duplicates (at least four shared content words
  and half the combined vocabulary), or they are absence findings at the same location. Each group
  reports its distinct seats. The count describes the panel; it is not evidence that the concern is
  right. To merge groups that share a root cause, give their findings one `group` label and rerun.
  With `--adjudicated`, groups are listed by stage, then severity, then position in the manuscript.

The script does not judge whether a concern is correct, fair or important, whether a recommendation
is proportionate, resolve identifiers, or score anything. Those are adjudication steps.

## Running it

```bash
uv run --script scripts/check_findings.py "$WORK/findings.merged.json" PAPER.md --md "$WORK/check.md" --json "$WORK/check.json"
uv run --script scripts/check_findings.py "$WORK/findings.merged.json" PAPER.tex -s supplement.md -s sections/methods.tex
uv run --script scripts/check_findings.py "$WORK/findings.adjudicated.json" PAPER.md --adjudicated
uv run --script scripts/check_findings.py "$WORK/findings.merged.json" PAPER.md --venue "$WORK/venue.md"
```

`$WORK` is the durable skill-run folder for the review's evidence (SKILL.md, step 3). The merged and
adjudicated files have names of their own because the stage's `findings.json`, for the dashboard, is
written beside them (SKILL.md, step 7). Exit code 0 when every finding, strength and report meets the
contract, 1 when any does not, 2 for unusable input (malformed JSON, a manuscript that is not Markdown,
LaTeX or text). For a multi-file LaTeX project, pass
the `\input` files with `-s` or flatten the project first. Convert `.docx` with `pandoc -t gfm` and
quote the converted text.
