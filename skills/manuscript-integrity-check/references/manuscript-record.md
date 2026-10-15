# Shared manuscript record (optional)

The skills share one optional record per manuscript so that a multi-step job can reuse completed checks,
keep the chosen venue and the paper's locked claims in one place, and pass open issues from one skill to
the next. It is a coordination aid, not a log: it holds the current state, never a history of passes.

## When to use it

- Create it only when the work spans several sessions (for example review this week, adaptation next
  week, a response to referees months later), or when the authors ask for one. Within one session the
  conversation carries the state, even when several skills run; a single task never needs it.
- If the project already keeps an equivalent (a checklist, a submission tracker, a section in its
  CLAUDE.md or AGENTS.md), use that instead of creating a second record.
- Read it at the start of a task when it exists. Update only the entries your skill owns. Never store
  genomes, medical records, private approvals, reviewer identities or detector scores in it.

## Location and format

`manuscript-record.yaml` beside the manuscript source the authors edit (same directory). It is the
authors' file; do not commit it unless they want it versioned. Unknown fields are kept as written.

```yaml
manuscript: paper.md                 # the source the authors edit
updated: 2026-10-15

venue:                               # set by manuscript-journal-select or manuscript-journal-adapt
  key: bioinformatics                # venues.yaml key when there is one
  article_type: original-paper
  stage: initial-submission          # initial-submission | revision | resubmission | accepted
  checked: 2026-10-15                # when its requirements were read from primary sources
  sources: [https://academic.oup.com/bioinformatics/pages/author-guidelines]

study:                               # set by whichever skill first establishes it; the authors confirm
  designs: [software-tool, public-data-reanalysis]   # keys from the list below; mixed studies list several
  domains: [genomics]                # free keys; a skill's domain modules say which keys they serve
  human_data: author-self-released   # manuscript-policy-fit's classification, when it has run

claims:                              # load-bearing claims; edits must not strengthen them
  - id: C1
    text: "Annotation of a 30x genome completes in under 10 minutes on a laptop."
    location: "Results, Performance"
    evidence: "Table 2"
non_claims:                          # what the paper explicitly does not claim
  - "No clinical or diagnostic utility is claimed."

terminology:
  preferred: {"polygenic score": ["PRS", "polygenic risk score"]}

checks:                              # completed checks, reusable while their material is unchanged
  - skill: manuscript-reference-check
    scope: all references
    manuscript_sha256: 3f1c...       # sha256 of the manuscript file when checked
    date: 2026-10-15
    output: references.json          # only an output saved with the project; never a scratch path
    summary: "41 resolved; 2 metadata mismatches; 1 unverified (paywalled)"

open_issues:                         # findings handed from one skill to another
  - id: I1
    from: manuscript-peer-review
    location: "Methods, Benchmark"
    summary: "No comparison with the two most-used existing annotators."
    route: author-required           # fixable-in-text | author-required | venue | policy
    status: open                     # open | resolved | waived (an author decision, recorded as such)
```

## Reusing a check

A recorded check can be reused when the manuscript's sha256 is unchanged, or when the changed sections
lie outside the check's scope, and when any external source it relied on (a venue page, a reference
record) is still current for the task. Otherwise rerun only the affected part. State in the result which
checks were reused and from when.

## Study-design keys

Skills choose reporting guidelines, reviewer seats and claim checks from the design, not from the
discipline label. Use these keys; list several for a mixed study.

| Key | Covers |
|---|---|
| `software-tool` | A tool, pipeline, library or web service and its evaluation |
| `method-benchmark` | A new method compared with existing ones on shared data |
| `database-resource` | A dataset, database, atlas or curated resource |
| `public-data-reanalysis` | New analysis of existing public or controlled-access data |
| `observational-human` | Cohort, case-control or cross-sectional study of people |
| `genetic-association` | GWAS, candidate-gene, rare-variant or QTL association study |
| `mendelian-randomization` | Causal inference from genetic instruments |
| `polygenic-score` | Development, validation or application of polygenic scores |
| `prediction-model` | Diagnostic or prognostic model, including machine-learning models |
| `randomized-trial` | Randomised or other interventional trial in people |
| `animal-experiment` | In vivo experiments in animals |
| `in-vitro-experiment` | Cell, tissue or biochemical laboratory experiments |
| `omics-profiling` | Sequencing, expression, epigenomic, proteomic or metabolomic profiling |
| `microbiome-metagenomics` | Microbial community or metagenomic studies |
| `systematic-review` | Systematic review or meta-analysis |
| `case-report` | Report of one or a few individuals |
| `qualitative` | Interviews, focus groups and other qualitative research |
| `simulation-theory` | Simulation, mathematical modelling or theory without new data |
| `ai-generated-science` | An AI system produced the scientific content (see `ai-science-design.md`) |

## Shared outcome words

Use the same words across skills so that results combine:

- A check that could not run is `not_assessed`, with the reason. It never counts as passed, and a script
  that exits 0 with `not_assessed` checks has not given a clean result.
- An external fact that could not be confirmed is `unverified`, with what was tried.
- Finding severity follows `author-priorities.md`: blocker, major, optional, uncertain / not assessed.
  Scripts also print `minor` and `info`; in a report to the authors, `minor` is optional and `info` is
  a note to read in context, never a finding by itself.
- Issue status is `open`, `resolved` or `waived`. Only the authors waive.
