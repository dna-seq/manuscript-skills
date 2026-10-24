# Shared manuscript record (optional)

The skills share one optional record per manuscript so that a multi-step job can reuse completed checks,
keep the chosen venue and the paper's locked claims in one place, and pass open issues from one skill to
the next. It is a coordination aid, not a log: it holds the current state, never a history of passes.

## When to use it

- Create it when the work spans several sessions (for example review this week, adaptation next
  week, a response to referees months later), when the authors ask for one, or when journal selection runs:
  the ladders are built from the authors' priorities and the venue facts it holds, and a re-rank reuses them.
  Otherwise, within one session the conversation carries the state, even when several skills run.
- If the project already keeps an equivalent (a checklist, a submission tracker, a section in its
  CLAUDE.md or AGENTS.md), use that instead of creating a second record. The ladder helpers read the
  priorities and venue facts from YAML, so those two still go in a record, kept beside the manuscript or
  beside the project's venue planning document, never in a scratch location.
- Read it at the start of a task when it exists. Update only the entries your skill owns. Never store
  genomes, medical records, private approvals, reviewer identities or detector scores in it.

## Location and format

`manuscript-record.yaml` beside the manuscript source the authors edit (same directory), or
`<manuscript stem>.record.yaml` when several manuscripts share the folder, or where the authors say. Name
its path in the reply. It is the authors' file; do not commit it unless they want it versioned. Unknown
fields are kept as written.

```yaml
manuscript: paper.md                 # the source the authors edit
updated: 2026-10-15

venue:                               # set by manuscript-journal-select or manuscript-journal-adapt
  key: bioinformatics                # venues.yaml key when there is one
  article_type: original-paper
  stage: initial-submission          # initial-submission | revision | resubmission | accepted
  checked: 2026-10-15                # when its requirements were read from primary sources
  sources: [https://academic.oup.com/bioinformatics/pages/author-guidelines]

priorities:                          # set by manuscript-journal-select from the authors' answers; most important first
  journals: [speed, reach, ai]       # speed | reach | ai | cost
  preprints: [transfer, ai]          # the same, plus transfer (a direct transfer to the first journal rungs)
  jif_floor: 3                       # other constraints the authors stated, in their words where useful
  fee: "a grant can pay a normal open-access fee"
  budget_eur: 3000                   # what the authors would pay at most; absent: a fee they pay is "depends"
  validation_available: [primary-analysis]   # none | independent-cohort | wet-lab | multi-database | primary-analysis

ai_use: revision                     # polish | revision | drafting, from the authors' account; absent: unknown

ladders:                             # the current order; rerun `venues.py ladder` when priorities or facts change
  preprints: [biorxiv, arxiv]
  journals: [bmc-bioinformatics, genome-biology, bioinformatics]
  checked: 2026-10-19

venue_facts:                         # facts read for this manuscript on the venues' own pages; venues.py ladder and
  bmc-bioinformatics:                # common lay them over the catalogue, which an author's task never edits
    review_speed:
      - {metric: submission-to-first-decision, days: 5, statistic: median,
         source: "https://link.springer.com/journal/12859", checked: 2026-10-19}
    publication_costs:
      - {amount: 2590, currency: EUR, fee_year: 2026, author_cost_eur: 0,
         route: "the grant pays; Projekt DEAL takes 20% off for the University of Rostock",
         source: "https://link.springer.com/journal/12859/how-to-publish-with-us", checked: 2026-10-19}
    abstract_headings: [Background, Results, Conclusions]
    limits: {abstract_words: 350}    # mappings merge key by key over the catalogue; a list replaces it
  genome-biology:
    not_read: "the author guidelines answered 403 to every route, 2026-10-19"   # why a fact is missing

study:                               # set by whichever skill first establishes it; a draft until the authors confirm
  designs: [software-tool, public-data-reanalysis]   # keys from the list below; mixed studies list several
  confirmed: 2026-10-19              # absent: a draft, so the ladder lowers a venue to "depends", never "does not fit"
  domains: [genomics]                # free keys; a skill's domain modules say which keys they serve
  human_data: author-self-released   # manuscript-policy-fit's classification, when it has run

claims:                              # load-bearing claims; edits must not strengthen them
  - id: C1
    text: "Annotation of a 30x genome completes in under 10 minutes on a laptop."
    location: "Results, Performance"
    evidence: "Table 2"
non_claims:                          # what the paper explicitly does not claim
  - "No clinical or diagnostic utility is claimed."

story:                               # set by manuscript-story from the authors' words; skills never change it alone
  direction: "Privacy: people can read their own genome without uploading it"   # the lead theme
  themes: [privacy, openness, speed] # every theme the paper carries, lead first
  readers: ["bioinformaticians who might run or extend the tool", "biologists curious about their own genome"]
  remember: "A whole genome annotated on your own computer in about half a minute."   # what readers should keep
  confirmed: 2026-10-19              # absent: a draft, which can never license a change of direction

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

- A check that could not run is `not_assessed` (scripts' JSON may say `not_checked`; both mean the same),
  with the reason. It never counts as passed, and a script that exits 0 with `not_assessed` checks has not
  given a clean result.
- An external fact that could not be confirmed is `unverified`, with what was tried.
- Finding severity is one scale, defined in the
  [stage findings](../../manuscript-dashboard/references/stage-findings.md) table: `blocker`, `major`,
  `minor`, `info` (the authors read "Optional") and `unknown` ("Could not be checked"). A script or seat
  that says `optional` means `info`; `uncertain` and `not_assessed` mean `unknown`.
- Issue status is `open`, `resolved` or `waived`. Only the authors waive.

These words belong to the record and to script JSON. A report to the authors says the same thing in plain
words ("could not be checked: the full text is paywalled"; "the authors chose to keep this wording"), quotes
the passage an issue concerns, and groups issues by when they can be fixed
([`author-priorities.md`](author-priorities.md#order-the-work-by-when-it-can-be-done)).
