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
[author priorities](../manuscript-integrity-check/references/author-priorities.md). This skill reports;
it edits only when the request includes edits, and then through `manuscript-prose-edit`'s
[contract](../manuscript-prose-edit/references/prose-edit-contract.md#1-the-contract). A reporting gap
is filled only with facts the authors give (an n, a version, the correction used), inserted under that
contract's author-supplied content rule; never with a value inferred here. Working files (audit tables,
JSON output) go to a scratch location (`SCRATCH` below), not beside the manuscript, unless the project
keeps them.

Apply the requested task across the whole paper unless the author specifies a narrower scope.
Follow the shared [workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
for requested section or stage review, before/after comparisons and optional interviews.

Three services, usable alone or together: **guidelines** (choose the guidelines that fit the design and
audit their items), **availability** (data, code and software), **statistics reporting**. A request for
one does not trigger the others.

## Ground rules

1. **Report what the authors did not report; never invent it.** No accession, DOI, tag, licence, n,
   test, correction, software version or access route that the manuscript or the authors did not give.
   Where a fact is needed, write `author input needed` and ask.
2. **A reporting gap is not a new experiment.** Ask the authors to report what they did. If they did not
   do it, offer the options (report it as a limitation, run an analysis the existing data allow, narrow
   the claim) and leave the choice to them. An unaffordable venue requirement is a venue question for
   `manuscript-journal-select`.
3. **The venue decides what is required.** Report what a missing item costs (a return, an office query,
   a referee question) only when the target venue requires the guideline or its form, verified on its
   live page. Otherwise a gap is advice, ranked by what it does to the reader's ability to judge the
   result. Never demand a checklist the venue does not ask for.
4. **A check that could not run did not pass.** Use the shared words in
   [manuscript-record.md](../manuscript-integrity-check/references/manuscript-record.md#shared-outcome-words):
   `not_assessed` with the reason, `unverified` for a fact that could not be confirmed. A supplement you
   did not receive makes an item `unclear (material not supplied)`, not `missing`.
5. **Controlled access is legitimate.** dbGaP, the EGA, a gated dataset or a GEO series private until
   publication is `restricted`, not a defect. Whether consent or privacy rules restrict sharing is
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
uv run --script scripts/guidelines.py items strega --manuscript PAPER.md --md SCRATCH/strega-audit.md
```

The table lists every item to check (an extension with its base's items) with empty state and location
columns. Give each item one state: `present`, `partial`, `missing`, `not_applicable` or `unclear`
(material not supplied), with a verbatim quote and location, or where you looked for an absent item.
Read [item-audit.md](references/item-audit.md) for evidence rules, severity and the report. Items in
`guidelines.yaml` are paraphrases. When a venue wants its official form, prepare the answers keyed by the
form's item numbers (where in the manuscript, a short quote) for the authors to transfer; never reproduce
the form's text.

## 3. Check availability

```bash
uv run --script scripts/check_availability.py PAPER.md --venue KEY --md SCRATCH/avail.md --json SCRATCH/avail.json
uv run --script scripts/check_availability.py PAPER.md --venue KEY --online
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
repository behind them. Read every finding in context and discard false positives. Then do what the
script cannot: check that every dataset behind a result has a location, that a resolving accession is the
right dataset, and what the venue's live page asks. Read [availability.md](references/availability.md).

## 4. Check statistics reporting

Read [statistics-reporting.md](references/statistics-reporting.md) and work through the analyses that
carry the claims: n as the independent unit, biological versus technical replicates, the test for each
comparison, multiple-testing correction, effect sizes with intervals, SD versus SEM versus CI, software
versions and seeds. Arithmetic (GRIM, P values recomputed from test statistics, numbers that disagree
between sections) is **manuscript-integrity-check's numbers check**
(`../manuscript-integrity-check/scripts/number_check.py`); run or reuse it rather than recomputing here.

## The report

Lead with the readiness of reporting and availability for the target venue and the smallest next steps.
Then findings by the shared severities (blocker only for a verified venue requirement; major; optional;
uncertain or not assessed), each with location, what is missing or wrong, the rule and its source with
its date (guideline item, venue page), and the change to make. Group by root cause, not by checklist
row. End with `author input needed` questions and what was not assessed. Give the full item table when the
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
- `scripts/check_availability.py`: extraction, offline flags, `--online` resolution, venue rules.
- `references/guidelines.yaml`: 16 guidelines and standards plus 5 venue checklists, each with version,
  design keys, condition, EQUATOR page or defining DOI, licence and the date it was checked
  (2026-10-15), items paraphrased with their official numbers.
- `references/guideline-selection.md`, `references/item-audit.md`, `references/availability.md`,
  `references/statistics-reporting.md`: read when the step above says so.
