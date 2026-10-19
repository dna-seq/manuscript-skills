---
name: manuscript-reporting-check
description: >-
  Check a manuscript against the reporting guidelines that fit its study design (STROBE, STREGA,
  STROBE-MR, STARD, TRIPOD+AI, PRISMA 2020, CONSORT 2025, ARRIVE 2.0, CARE, the PGS reporting standard,
  MDAR, and the MINSEQE, MIAME, MIxS and DOME standards for omics and machine learning), verify its data,
  code and software availability (accessions, DOIs, repositories, releases, licences, packages and
  containers), and audit how it reports its statistics. Use for reporting-guideline or checklist audits,
  data or code availability checks and statistics-reporting reviews. Use manuscript-integrity-check for a
  full submission audit (it calls this skill for these checks), manuscript-journal-adapt to draft or
  format the venue's availability statement, manuscript-policy-fit to decide whether ethics, consent or
  privacy rules apply, manuscript-reference-check for the reference list including data citations, and
  manuscript-peer-review for a simulated referee panel.
---

# Check reporting, availability and statistics

Help the authors give readers, editors and referees what they need to judge and reuse the work, with
the least avoidable effort. Read the shared
[author priorities](../manuscript-integrity-check/references/author-priorities.md), in particular
[authors first, journals second](../manuscript-integrity-check/references/author-priorities.md#the-author-decides-authors-first-journals-second),
[the order of work](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done) and
[writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors).
This skill reports; it edits only when the request includes edits, and then through `manuscript-prose-edit`'s
[contract](../manuscript-prose-edit/references/prose-edit-contract.md#1-the-contract). A reporting gap
is filled only with facts the authors give (an n, a version, the correction used), inserted under that
contract's author-supplied content rule; never with a value inferred here. The audit tables and the
availability report are for the authors: they go beside the manuscript, or where the authors say (`OUT`
below), and the reply gives their paths. JSON output only feeds the report and goes to a scratch location
(`SCRATCH` below).

Apply the requested task across the whole paper unless the author specifies a narrower scope.
Follow the shared [workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
for requested section or stage review, before/after comparisons and optional interviews.

Three services, usable alone or together: **guidelines** (choose the guidelines that fit the design and
audit their items), **availability** (data, code and software), **statistics reporting**. A request for
one does not trigger the others.

## Ground rules

1. **Report what the authors did not report; never invent it.** No accession, DOI, tag, licence, n,
   test, correction, software version or access route that the manuscript or the authors did not give.
   Where a fact is needed, ask for it among the questions at the end of the report.
2. **A reporting gap is not a new experiment.** Ask the authors to report what they did. If they did not
   do it, offer the options (report it as a limitation, run an analysis the existing data allow, narrow
   the claim) and leave the choice to them. An unaffordable venue requirement is a venue question for
   `manuscript-journal-select`.
3. **The venue decides what is required; the authors decide what to do about it.** Report what a missing
   item costs (a return, an office query, a referee question) only when the target venue requires the
   guideline or its form, verified on its live page. Otherwise a gap is advice, ranked by what it does to
   the reader's ability to judge the result. Never demand a checklist the venue does not ask for. When the
   authors choose not to meet a journal rule (data kept on request, a form left out), do the rest of the
   work, name the conflict once in one sentence with its practical consequence among their decisions, and
   never list it as a blocker or a required fix.
4. **A check that could not run did not pass.** The record and the JSON use the shared words of
   [manuscript-record.md](../manuscript-integrity-check/references/manuscript-record.md#shared-outcome-words)
   (`not_assessed` with the reason, `unverified` for a fact that could not be confirmed); the report says
   what happened in plain words ("could not be checked: Hugging Face gives the same answer for a private
   and a missing repository"). A supplement you did not receive makes an item unclear (material not
   supplied), not missing.
5. **Controlled access is legitimate.** dbGaP, the EGA, a gated dataset or a GEO series private until
   publication is restricted access, not a defect. Whether consent or privacy rules restrict sharing is
   `manuscript-policy-fit`'s call; this skill checks that the statement gives the route.
6. **Network lookups send only public identifiers** (accessions, DOIs, repository and package names),
   behind `--online`. Manuscript text never leaves the machine.

## Inputs

Use what is in context first. The manuscript source (Markdown, LaTeX or text; convert Word or a Google Doc
export with `pandoc -t gfm`), the supplement when the audit needs it, the target venue and article type if
known, and the study designs. Read `manuscript-record.yaml` beside the manuscript when it exists: it
holds the venue, the designs and earlier checks. Do not require it for a single task.

## 1. Choose the guidelines

Classify the study with the design keys of
[manuscript-record.md](../manuscript-integrity-check/references/manuscript-record.md#study-design-keys)
(`guidelines.py designs` lists them; `select` accepts no others), several for a mixed study, from the
Methods rather than the field. Then:

```bash
uv run --script scripts/guidelines.py select --design genetic-association --design observational-human --venue KEY
uv run --script scripts/guidelines.py select --record manuscript-record.yaml
```

It lists the guidelines that apply, those whose condition you confirm first (`applies_if`: STARD only for
diagnostic accuracy, DOME only when a supervised model is trained or evaluated, PRS-RS only when a score is
developed, validated or its performance reported, not when published scores are only applied), the base of
every extension, venue checklists for that venue only (Nature Portfolio Reporting Summary, Cell Press STAR
Methods, EMBO Press and eLife MDAR-based forms), the venue's recorded checklist rule, and a note for
designs that have no guideline. A software tool, database, benchmark or simulation has no EQUATOR
guideline: say so and let the availability and reproducibility checks carry the weight. Read
[guideline-selection.md](references/guideline-selection.md) for mixed designs, the three venue cases and
licences.

## 2. Audit the items

```bash
uv run --script scripts/guidelines.py items strega --manuscript PAPER.md --md OUT/strega-audit.md
```

The table lists every item to check (an extension with its base's items, each number in parentheses after
the item) with empty columns to fill. Give each item one state: present, partial, missing, not applicable
or unclear (material not supplied), with a verbatim quote and its section, or where you looked for an
absent item, and say when it can be fixed: a missing item that shows missing science (an analysis,
comparison, correction or method the conclusions need) is for now; the rest of a checklist waits until
the journal is chosen. A guideline you considered and found not to apply needs no table: say so in one
sentence with the reason. Read [item-audit.md](references/item-audit.md) for evidence rules, severity and
the report. Items in `guidelines.yaml` are paraphrases. When a venue wants its official form, prepare the
answers keyed by the form's item numbers (where in the manuscript, a short quote) for the authors to
transfer; never reproduce the form's text.

## 3. Check availability

```bash
uv run --script scripts/check_availability.py PAPER.md --venue KEY --md OUT/availability.md --json SCRATCH/avail.json
uv run --script scripts/check_availability.py PAPER.md --venue KEY --online
uv run --script scripts/check_availability.py PAPER.md --venue KEY --final    # the authors are about to submit
```

It finds the availability statements, extracts and classifies every accession, DOI, repository, package,
container, model and RRID outside the reference list (also Zenodo record numbers and Hugging Face
repositories named in prose, and anonymised review links), flags statements that name nothing, "available
upon request" without a reason, malformed accessions, code links with no release or archive, and the
venue's recorded rules (read from `../manuscript-integrity-check/references/venues.yaml` through
`../manuscript-journal-adapt/scripts/venues.py`, never hard-coded). `--online` resolves each identifier
against its archive: `resolves`, `not_found`, `restricted` or `not_assessed`, plus missing licences,
missing releases and cited versions that do not exist, for the authors' own code only; a tool the paper
compares or cites is checked for existence. Anonymised review links are never looked up: do not infer the
repository behind them. Its Markdown report is written for the authors: findings grouped by when they
can be fixed and quoted with their section, end-stage findings (archives, release tags, licences, the
statement's wording) not counted against a draft unless `--final` says the authors are about to submit.
Read every finding in context and discard false positives. Then do what the script cannot: check that
every dataset behind a result has a location, that a resolving accession is the right dataset, and what
the venue's live page asks. Read [availability.md](references/availability.md).

## 4. Check statistics reporting

Read [statistics-reporting.md](references/statistics-reporting.md) and work through the analyses that
carry the claims: n as the independent unit, biological versus technical replicates, the test for each
comparison, multiple-testing correction, effect sizes with intervals, SD versus SEM versus CI, software
versions and seeds. Arithmetic (GRIM, P values recomputed from test statistics, numbers that disagree
between sections) is **manuscript-integrity-check's numbers check**
(`../manuscript-integrity-check/scripts/number_check.py`); run or reuse it rather than recomputing here.

## The report

Lead with one paragraph on readiness (for the target venue when there is one; for a draft, what the current
work needs) and the smallest next steps. Then the findings under these headings, in this order, leaving
out empty ones (the [order of work](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done)):

1. **Fix now**: what the conclusions need and the paper lacks (a missing analysis, method, correction or
   comparison, from the item audit or the statistics check) and data the results rest on that nobody can
   reach (a malformed or non-existent accession, a dataset deposited nowhere).
2. **Then the writing**: what was done but is reported unclearly (an undefined error bar, a test not named
   for its comparison, an accession written with a stray space).
3. **Once you have chosen the journal**: the journal's reporting checklist and its form, and its own
   availability format (the software's location in the abstract).
4. **Before submission, once the code is final**: archive DOIs and release tags, versions quoted in the
   text, licence files, final accession numbers and the wording of the availability statement.

Within a group, order by the shared severities and put an item after the one it depends on. An end-stage
item is not a blocker and does not count in a draft's readiness unless the authors say they are about to
submit. A blocker is a confirmed scientific defect, or a submission barrier verified on the journal's live
page when the authors are about to submit; a journal rule the authors have chosen not to follow is one
sentence among their decisions, not a finding.

Write each finding as the shared rules for
[writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors) ask: quote the sentence or table row it concerns and name its section (a line number in parentheses at most),
say what is missing or wrong and why it matters for the paper, cite the rule with its source as a URL and
the date it was read (a guideline item, a journal page), and give the change to make. Accessions, DOIs,
repositories and releases are full URLs. Item numbers, check codes and state words follow a plain
description in parentheses at most. Group by root cause, not by checklist row. End with the questions only
the authors can answer and what was not assessed, with the reason. Give the full item table when the
authors or the venue want it; otherwise offer it.

When the project keeps `manuscript-record.yaml`, add a `checks` entry for this skill (scope, manuscript
sha256, date, one-line summary, saved JSON output) and hand open gaps on as `open_issues` with a route:
`fixable-in-text` (report what was done), `author-required` (a fact or decision only they have), `venue`
or `policy`.

## Hand-offs

| Situation | Skill |
|---|---|
| A full submission audit | `manuscript-integrity-check` (calls this skill for reporting and availability) |
| Drafting or formatting the availability statement for a venue | `manuscript-journal-adapt` (this skill checks its content) |
| Whether ethics approval, consent, registration or privacy rules apply | `manuscript-policy-fit` (this skill checks only that a required declaration is present) |
| Reference-list entries, including data and software citations there | `manuscript-reference-check` |
| Number arithmetic and statistics recomputation | `manuscript-integrity-check`'s numbers check |
| A simulated referee panel | `manuscript-peer-review` (its adjudication reuses these findings, listed as belonging to other checks) |
| Answering a referee who asked for a checklist or deposit | `manuscript-reviewer-response`, with this skill for the check |
| A venue whose required checklist or deposit the authors cannot meet | `manuscript-journal-select` |

## Files

- `scripts/guidelines.py`: `select`, `items`, `designs`, `list`, `validate` (PEP 723; `uv run --script`).
- `scripts/check_availability.py`: extraction, offline flags, `--online` resolution, venue rules, a stage
  for every finding and a Markdown report for the authors (`--final` when they are about to submit).
- `references/guidelines.yaml`: 16 guidelines and standards plus 5 venue checklists, each with version,
  design keys, condition, EQUATOR page or defining DOI, licence and the date it was checked
  (2026-10-15), items paraphrased with their official numbers.
- `references/guideline-selection.md`, `references/item-audit.md`, `references/availability.md`,
  `references/statistics-reporting.md`: read when the step above says so.
