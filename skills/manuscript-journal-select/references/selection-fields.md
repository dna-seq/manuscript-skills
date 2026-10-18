# Recording selection evidence in the shared venue database

This file guides maintenance of the plugin's catalogue,
`../../manuscript-integrity-check/references/venues.yaml`. During an author's task, report newly
researched facts in the result as plain sentences that cover the points below, each with the URL of its
page and the date read (the field names are for the catalogue, not for the authors), and in the shared
manuscript record's `venue` entry when one exists;
write them into `venues.yaml` only when the task is maintaining this repository, following
`../../manuscript-journal-adapt/references/policy-maintenance.md`. In an installed plugin the catalogue
sits in a cache that an update replaces. Preserve existing fields; research only decision-changing gaps
for the requested comparison. Missing or `null` means unresearched, never no rule,
zero cost, permissive policy or fast review. Date each new fact independently; an AI-policy check date
does not refresh fees or review statistics.

## Expensive validation and scope restrictions

`validation_requirements` is a list of scoped rules. Record:

- `applies_to`: normalised study designs used by the helper: `software`, `public-data`, `bioinformatics`,
  `mr`, `bibliometric`, `public-health-database` or `other`. Describe the precise scope in prose as well;
  classification of an ambiguous manuscript remains an editorial/author judgement. The shared record's
  design keys map onto these: `software-tool`, `database-resource` and a `method-benchmark` whose
  contribution is the method map to `software` (a tool or resource paper, not a biological finding);
  `public-data-reanalysis` to `public-data`; computational biological findings (`omics-profiling`,
  `genetic-association`, `polygenic-score` without new data) to `bioinformatics`;
  `mendelian-randomization` to `mr`; anything else to `other`. A publisher rule about "predominantly
  bioinformatics findings" does not by itself cover a software paper; read its scope.
- `strength`: `required`, `conditional` or `recommended`. Only an explicit applicable requirement with
  no available accepted alternative supports an automated resource NO-GO.
- `accepted_any`: alternative routes, using `independent-cohort`, `wet-lab`, `multi-database` or
  `primary-analysis`. These are alternatives for that rule, not requirements to do all of them.
  Multiple applicable rules must each be satisfied; leave ambiguous alternatives unspecified.
- `description`: exact practical condition, submission stage, exceptions and any interpretation still
  needed. Record whether an existing public dataset could suffice, whether that is unstated, and whether
  primary data collection is actually required. Do not invent a requirement for a private cohort.
- `source`, `checked`: direct primary URL and read date, plus a short decisive quote when useful.

Use `excluded_study_designs` for explicit prohibitions, with source/date in the editorial profile.
Do not replace a conditional standard with an absolute ban. Put every new primary URL in the entry's
`sources` too so it remains discoverable. The AI watcher does not monitor all selection requirements.

The CLI `--validation-available` states what is already available or affordable, not a promise to run
new experiments. `none` means none of the additional routes is available; it cannot be combined with
other routes. An omitted option means unknown. A GO from this helper covers recorded validation only.

## Open science and open source

`open_science` holds a short `summary`, `source`, `checked` and any researched details:

- `source_code`: required, encouraged, optional, restricted or unknown; relevant article types.
- `software_licence`: accepted/required licence and limits on commercial or academic reuse.
- `data_and_artifacts`: deposition, reproducibility and legitimate access exceptions.
- `preprints`, `open_peer_review`: actual policy, including optional versus mandatory.

Keep `oa` as the existing access-model field. A CC-BY article licence says nothing by itself about the
required licence for the submitted software. Neither full OA nor a publisher's slogan establishes the
cost or the journal's broader attitude to open science.

## Editorial receptiveness

`editorial_profile` holds `summary`, `source`, `checked`, `evidence_kind` and optional evidence:
novelty versus technical-soundness criteria, explicit exclusions, relevant article types, support for
replications/negative findings, and examples of unconventional or computational work.

Use a domain-specific description, e.g. receptive to interdisciplinary methods but restrictive about
unvalidated public-data associations. Separate published policy from your inference from article
examples. Do not turn conservatism/openness into a universal numerical personality rating. Absence of a
statement about a design means unknown. Journal-specific editorial profiles are not inherited.

## Review time and cost

`review_speed` is a list of metric records, each with:

- `metric`: submission-to-first-decision (desk-inclusive or definition unknown), first externally
  reviewed decision, submission-to-acceptance, acceptance-to-publication, or reviewed-preprint posting.
- `days`, `statistic`: the published value and median/mean/range. Retain any stated uncertainty.
- `population`, `period`: all submissions, externally reviewed papers or accepted papers; measurement
  interval/year. Mark either unknown when omitted by the source.
- `source`, `checked`, `evidence_kind`: official statistic, target/service promise, or an inference
  from a stated sample. Label a sample's selection bias; accepted-paper dates omit rejected papers.

Never combine desk-inclusive and external-review timing or a target and an observed statistic into one
rank. Missing timing stays unknown. These metrics are not inherited from other venues.

Look before recording unknown: many publishers post timing on the journal's own pages. BMC and Springer
Nature journal home pages show median days from submission to first decision and to acceptance; PLOS
publishes turnaround metrics per journal; some OUP and Frontiers journals state averages in their "about"
or author pages. Record what the source states, with its population and period.

`publication_costs` records researched APC/other fees with `amount`, `currency`, `fee_year`, applicable
article type, tax caveats where material, waiver/agreement routes, `source` and `checked`. An unresearched
fee is not zero. Validation budget and publication budget are separate constraints.

## Verified examples and cautions

The Frontiers entry records its cohort/biological validation rule and the bibliometric exception; its
Bioinformatics journal entry separately records design exclusions. The PLOS entry records the public
health-database editorial as conditional, including computational additional-work routes. Do not apply
that editorial as a blanket wet-lab ban on software papers.

Current primary pages were checked on 2026-10-15; see their exact URLs and conditions in the database.
The new fields are intentionally incomplete elsewhere. Fill them from sources when comparing actual
candidates, rather than populating every journal with guesses.
