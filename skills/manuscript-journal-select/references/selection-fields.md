# Recording selection evidence in the shared venue database

The plugin keeps one store of venue facts, the catalogue
`../../manuscript-integrity-check/references/venues.yaml`, and every venue fact any task reads goes into it
with the page it was read on (`source`) and the date (`checked`): journal selection, adaptation, policy fit,
the referees' venue briefs and the figure rules alike. A later run then reads a page only for the facts that
have grown old. Report what you read in the result as plain sentences as well, each with the URL of its page and
the date read (the field names are for the catalogue, not for the authors). Preserve existing fields; research
only decision-changing gaps for the requested comparison. Missing or `null` means unresearched, never no rule,
zero cost, permissive policy or fast review.

## Where a fact goes

`venues.py where` names the file. In the plugin's own repository checkout it is the shipped `venues.yaml`:
edit it in place, keeping its comments. In an installed plugin the shipped file sits in a cache that an update
replaces, so the facts go into the user's own catalogue, `venues.yaml` beside `settings.yaml`
(`~/.config/manuscript-skills/` on Linux, `~/Library/Application Support/manuscript-skills/` on macOS,
`%APPDATA%\manuscript-skills\` on Windows, or `$MANUSCRIPT_SKILLS_CONFIG`), which updates never touch: write
them to a facts file in the catalogue's form (`venues: {KEY: {...}}`) and run `venues.py save FACTS.yaml`, which
merges them in. `venues.py` lays the user's catalogue over the shipped one, and the manuscript record over both,
field by field, the newest `checked` winning; on the same date the later layer wins. A mapping merges key by
key, so a partial `limits` keeps the other limits (its date is the newer one only when it covers every key of the
older); a list replaces the older list. A venue the catalogue lacks is added with a `name` (and the
publisher entry it `inherits`, when there is one).

The same field names serve every layer:

- selection and guidelines: `review_speed`, `publication_costs`, `open_science`, `limits`,
  `abstract_headings`, `required_sections`, `submission_rules` (an addition every other venue's version can
  carry, such as alt text, gets `free_for_others: true`), `software`, `other_desk_rules`,
  `validation_requirements`, `excluded_study_designs`, `editorial_profile`, `article_types`, `jif` with
  `jif_year`;
- the AI policy: `writing_help`, `exempt`, `prompts`, `tracking`, `screening`, `disclosure_places`,
  `disclosure_fields`, `disclosure_neutral`, `extra_burden`, `image_rules`, `reviewer_ai`, `ai_policy_url`;
- what the journal asks its referees (`reviewer_form`) and its rules for figures (`figure_rules`), described in
  the header of `venues.yaml`;
- preprint servers: `transfers` and `transfers_checked`;
- `not_read`: one sentence saying why the venue's author guidelines could not be read, with the date and every
  route tried (`common` gives the reason instead of a bare gap). The authors' own browser comes before it: a page
  that blocks scripts and the built-in browser usually opens in their Chrome through Claude in Chrome.

## The date of each fact

Date each fact independently: an AI-policy check does not refresh fees or review statistics. A mapping or a
list of records carries its own `checked` and `source`; any other field takes them from the venue's
`provenance` (`provenance: {jif: {source: URL, checked: 2026-10-27}}`), and without either it takes the
venue's `checked`, else the file's. An impact factor read on the journal's or publisher's own page or in Journal
Citation Reports is recorded with its `jif_year`. A value found only on a third-party site (an aggregator) may be
recorded too, without `jif_year` and with that site in its `provenance`: it is not verified, so it counts against
an impact-factor floor but `ladder` places it below every verified impact factor at the reach step, and the
tables print it as not verified.

## Re-read only what is old

Before a run reads a venue's pages, `venues.py stale --record REC` (or `stale KEY KEY`) lists the facts of the
ladder's venues that are due, grouped by the page to re-read: an AI-policy field after 60 days, an impact factor
(verified or not) once Journal Citation Reports has released newer figures (each June), and any other
fact (fees, review speed, article types, limits, preprint rules, transfers, referee forms, figure rules) after a
year. Read only those, and the fields nobody has recorded yet that the comparison needs. A fact found unchanged
keeps its value and only its date moves; a changed one is replaced by the new value with the new date and page.
`ladder` ends with a pointer to `stale` when any of its venues have facts due.

## What stays in the manuscript record

The record (`../../manuscript-integrity-check/references/manuscript-record.md`) holds what belongs to this
paper and its authors: `priorities` (with `jif_floor`, `budget_eur`, `validation_available`), `ladders`,
`ai_use`, `study.designs` with `study.confirmed`, and `cost_routes`, the routes that pay a fee for these
authors (a university fund, a national agreement as it applies to the corresponding author, a library's
agreement): `cost_routes: {KEY: {author_cost_eur, route, source, checked}}`. `ladder` compares
`author_cost_eur` when it is given, else a fee listed in euros. The venue's own fee, with the waivers and
discounts anyone can use, goes into the catalogue's `publication_costs`. Older records kept venue facts under
`venue_facts`; `ladder` and `common` still lay them over the catalogue, by date (an entry without dates takes
the record's `updated`), and a run that finds them moves the venue facts into the catalogue, leaving only cost
routes in the record.

When `policy_watch.py check` exits 1 during a task (an AI passage changed, or a page is gone), read each changed
passage it quotes. If the rule itself moved, write the new rule into the catalogue `where` names (the AI-policy
fields above, with the page and the date), rerun `ladder` and `common`, and say in the report, in one sentence,
that the rule changed. A page that is gone is looked for at its new address and read there. Do not pass
`--update` during an author's task: the snapshots are maintenance. Exit 3 means some pages could not be read;
read those with your own browser tool before any archived copy, and an archived copy is never the current rule.

`review_speed`, `publication_costs`, `editorial_profile`, `submission_rules`, `transfers` and
`transfers_checked` describe one journal or server and are never inherited from the entry it `inherits`.

## Expensive validation and scope restrictions

`validation_requirements` is a list of scoped rules, and a list that was read is the journal's complete rules:
record every validation or evidence rule its article-type, aims and author-guideline pages state, for every kind of
paper, and `[]` (dated in `provenance`) when they state none. Both are findings: a design none of the recorded rules
covers fits, with the page named. A missing list means nobody read it, and the ladder can only say "Could not be
checked"; `stale` lists it until it is read. Record:

- `applies_to`: normalised study designs used by the helper: `software`, `public-data`, `bioinformatics`,
  `mr`, `bibliometric`, `public-health-database` or `other`. Describe the precise scope in prose as well;
  classification of an ambiguous manuscript remains an editorial/author judgement. The shared record's
  design keys map onto these, and `ladder` maps them itself when it reads `study.designs`:
  `software-tool`, `database-resource` and `method-benchmark` map to `software` (a tool or resource paper,
  not a biological finding; give `--study-design` for a benchmark whose contribution is a finding);
  `public-data-reanalysis` to `public-data`; computational biological findings (`omics-profiling`,
  `genetic-association`, `polygenic-score`) to `bioinformatics`; `mendelian-randomization` to `mr`; anything
  else to `other`. A mixed study is judged under each design, and a venue that one design would rule out and
  another would not "Depends" on how its editors read the paper. Until the authors confirm the design
  (`study.confirmed`), a rule can make a venue "Depends", never "Does not fit". A publisher rule about
  "predominantly bioinformatics findings" does not by itself cover a software paper; read its scope.
- `strength`: `required`, `conditional` or `recommended`. Only an explicit applicable requirement with
  no available accepted alternative supports an automated "Does not fit the stated constraints".
- `accepted_any`: alternative routes, using `independent-cohort`, `wet-lab`, `multi-database`,
  `primary-analysis` or `benchmark` (a software or method paper compared with existing methods on shared data, the
  route methods journals name). These are alternatives for that rule, not requirements to do all of them.
  Multiple applicable rules must each be satisfied; leave ambiguous alternatives unspecified.
- `description`: exact practical condition, submission stage, exceptions and any interpretation still
  needed. Record whether an existing public dataset could suffice, whether that is unstated, and whether
  primary data collection is actually required. Do not invent a requirement for a private cohort.
- `source`, `checked`: direct primary URL and read date, plus a short decisive quote when useful.
- `id`: a short name for the rule, unique within the venue. The manuscript record's `conditions` name the rule
  they checked the paper against by it (`conditions.VENUE.RULE_ID: {met: true | false | partly, evidence,
  checked}`); a met condition fits, with the passage that shows it.

Use `excluded_study_designs` for explicit prohibitions, with source/date in the editorial profile.
Do not replace a conditional standard with an absolute ban. Put every new primary URL in the entry's
`sources` too so it remains discoverable. The AI watcher does not monitor all selection requirements.

The CLI `--validation-available` (or the record's `priorities.validation_available`) states what is already
available or affordable, not a promise to run new experiments. `none` means none of the additional routes
is available; it cannot be combined with other routes. An omitted option means unknown. The ladder's
`validation_fits` covers recorded validation only; its `fits` also weighs a conflict with the established AI
use and the fee against the budget.

## What preprint servers decline and where they send papers

A server's `screening_rules` play the part of a journal's validation requirements on the preprint ladder, read the
same way (`[]` when its pages state none). Each rule has `applies_to` (designs, and what the paper reports:
`health` for health-related information about people, `clinical` for clinical research, `human-data` for data
that identify a person), `outcome` (`declined`, `redirected` with `redirect_to` the other server's key, or
`condition` for something the paper must have, such as results beyond a tool announcement), `strength`
(`required` only when the page says the server does not post such papers; "may" is `conditional`),
`description` with the page's decisive words quoted, `source` and `checked`. Record the redirects on both sides:
a pair that send a paper to each other (bioRxiv and medRxiv for a personal-genome tool paper) is how a paper ends
up posted nowhere, and the ladder names it only when both servers' rules are recorded. The plain-word scope notes
stay in `other_desk_rules` and `fit_note`.

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
rank. Missing timing stays unknown. A venue that publishes no figure gets `review_speed: []`, dated in its
`provenance`, so a later run does not look again within the year. These metrics are not inherited from other
venues.

Look before recording unknown: many publishers post timing on the journal's own pages. BMC and Springer
Nature journal home pages show median days from submission to first decision and to acceptance; PLOS
publishes turnaround metrics per journal; some OUP and Frontiers journals state averages in their "about"
or author pages. Record what the source states, with its population and period.

`publication_costs` records researched APC/other fees with `amount`, `currency`, `fee_year`, applicable
article type, tax caveats where material, waiver/agreement routes (`route`, in words), `source` and
`checked`. What these authors would pay after the agreements, funds and waivers that cover them is the
record's `cost_routes.KEY.author_cost_eur`; `ladder` compares that figure, else a fee listed in euros, and
shows a fee in another currency without comparing it. An unresearched fee is not zero. Validation budget
and publication budget are separate constraints.

## Preprints and direct transfer

`open_science.preprints` records a journal's rule on manuscripts already posted as preprints: whether posting
affects consideration, licence conditions, what must be disclosed at submission and what must be updated after
acceptance. A preprint server's `transfers` lists the catalogue keys of the journals it transfers manuscripts
to directly; `transfers_checked` lists the journals its list was read for, so that a journal absent from
`transfers` but checked is a "no" and one not checked stays unknown. The ladder CSV writes `none` when the
list was read and names none of the ladder's journals, and leaves the cell empty when that is not known. Record a server's scope exclusions
(tool announcements without data, papers sent to another server) in `other_desk_rules` and `fit_note`.

## Verified examples and cautions

The Frontiers entry records its cohort/biological validation rule and the bibliometric exception; its
Bioinformatics journal entry separately records design exclusions. The PLOS entry records the public
health-database editorial as conditional, including computational additional-work routes. Do not apply
that editorial as a blanket wet-lab ban on software papers.

Current primary pages were checked on 2026-10-15, and the journals of one ladder again on 2026-10-19,
2026-10-27 and 2026-10-28; see their exact URLs, conditions and dates in the database. The plugin ships the
screening rules of the common preprint servers and the validation requirements of the journals its ladders have
used; elsewhere they are read when a ladder needs them, never filled with guesses.
