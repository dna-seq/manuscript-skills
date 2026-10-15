---
name: manuscript-journal-select
description: >-
  Select journals for a manuscript using its subject, article type, available validation and budget,
  open-source and open-science preferences, editorial receptiveness, review speed and AI-policy burden.
  Use for journal shortlists, requirements-based venue comparisons or a submission sequence, especially
  for in-silico-only work, and when asked to interview the authors to pick a journal or preprint server by
  how strict or hostile its AI policy is, or to see where named colleagues publish. Reuse the shared venue
  database; use manuscript-journal-adapt after selection.
---

# Select journals the authors can realistically publish in

Help the authors publish sound work within their actual resources. Read
`../manuscript-integrity-check/references/author-priorities.md`. The author decides tradeoffs and policy
interpretations; journal requirements are information for that decision, not assistant prohibitions.
For policy-verification limits, consult
`../manuscript-integrity-check/references/requirement-checkability.md` when needed.

Use `manuscript-policy-fit` for study-specific clinical-scope, ethics, privacy and regulatory applicability,
including authors' voluntarily public personal genomes or biomedical records. Incorporate the actual
requirements and exceptions into the shortlist; wording ambiguity alone does not establish a need for
new oversight, recruitment or clinical validation.

Apply the requested task across the whole paper unless the author specifies a narrower scope.
Follow the shared [workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
for requested section or stage review, before/after comparisons and optional interviews.

## Establish constraints without creating an interview burden

Use the manuscript and existing conversation first. Ask only missing facts that change the shortlist:
subject and contribution, article type, research/validation already done or affordable, APC budget,
deadline, licence/funder constraints, and priorities among speed, reach and editorial fit. Offer a fuller
interview only if requested. Do not make the author supply a complete questionnaire. When the authors ask
to be interviewed, follow `references/interview.md` for questions mapped to `rank` flags. For AI-policy
rankings, reuse that reference's field mapping and score explanations without automatically starting an
interview; use known facts and ask only questions that materially affect the comparison.

Treat an author's in-silico-only budget as a real constraint. Distinguish existing/public independent
validation data, collecting a new cohort, and laboratory work: computational replication may be affordable
even when recruitment or experiments are not. Do not infer access to a second dataset or collaborators.
Capture any resource ceiling once and reuse it; recommend feasible venues rather than expanding the study
just to fit an expensive journal. APC waivers, institutional agreements and zero-APC routes can matter.

## Reuse the database and verify decision-changing requirements

Read `../manuscript-integrity-check/references/venues.yaml` through the existing helpers, or inspect a
specific entry. Keep these skills together; do not create a second journal database.

Commands below are relative to this skill directory:

```bash
uv run --script ../manuscript-journal-adapt/scripts/venues.py rank --field bioinformatics --type software
uv run --script ../manuscript-journal-adapt/scripts/venues.py rank --study-design public-data --validation-available none
uv run --script ../manuscript-journal-adapt/scripts/venues.py rank --study-design public-data --validation-available independent-cohort
uv run --script ../manuscript-journal-adapt/scripts/venues.py show <venue-key>
uv run --script ../manuscript-journal-adapt/scripts/venues.py peers "First Last" --since 2019
```

`rank` supplies a preliminary AI-friction/resource comparison, not a complete recommendation or an
acceptance probability. Inspect the entry's other selection fields and make the full comparison below.
Use optional field/type, JIF, OA, named-peer and `--refuse` filters only for the author's actual preferences.
The helper excludes mandatory AI record-keeping venues by default; explain that omission and use
`--include-tracking` when the author wants them considered. Unknown data are not favourable evidence.

For the shortlist, read current journal-specific author instructions, scope and article-type pages, plus
applicable publisher requirements. Search specifically for validation, computational/public-data/MR
restrictions, code/licence/data rules, fees and turnaround metrics; an AI-policy page alone is insufficient.
The existing `policy_watch.py` compares AI passages and does not establish that these other policies are
unchanged. Whenever a selection task checks a decision-changing requirement, give its scope,
alternatives, source and date in the result in the format of `references/selection-fields.md`; do not
leave an expensive validation condition buried in background notes. Write it into the plugin's
`venues.yaml` only when the task is maintaining this repository; during an author's task the catalogue is
read-only (it sits in the plugin cache). This does not require refreshing unrelated entries.

## Feasibility before preference scoring

Identify each material requirement early, with its source/date, scope, strength, accepted alternatives
and exceptions. Distinguish explicit requirements, recommendations, published practice and judgement.
A publisher rule may apply only to one design, article type or journal. Check both what is required and
what work the author actually has; do not equate a policy mentioning cohorts with compulsory recruitment.

Give each candidate a practical disposition:

- **GO:** no known conflict with the author's constraints after relevant checks, including known costs
  within the stated budget. This is not a guarantee of acceptance; label a helper's narrower
  validation-only GO accordingly.
- **CONDITIONAL:** a plausible affordable route exists, or applicability/waiver needs checking (for
  example an APC above the budget unless a waiver or institutional agreement applies). State the exact
  condition and who can resolve it. An AI-policy conflict with the authors' actual use is CONDITIONAL with
  the rule and options stated: how to handle journal policy is the authors' decision.
- **NO-GO under the stated constraints:** a confirmed scope restriction, expense or required validation
  has no available route. Say why before ranking softer preferences. The author can still choose to try.
- **UNKNOWN:** a material requirement or cost remains unresearched/unavailable. Keep this visible rather
  than silently treating it as permissive.

Do not let a favourable AI policy, JIF or claimed speed compensate for an infeasible validation requirement.
Show infeasible candidates separately or explain their exclusion. Do not treat a second public dataset
as automatically satisfying an independent-clinical-cohort rule; check the rule and dataset.

## Compare viable candidates on the author's priorities

| Dimension | Assess with evidence |
|---|---|
| Scientific fit and realistic prospects | Contribution, scope, article type, relevant recent papers and acceptance criteria |
| Open source and open science | Submitted-software source/licence requirements; data and code availability; reproducibility artifacts; preprints; open review; acceptance of justified privacy/access restrictions |
| Editorial conservatism or receptiveness | Stated novelty/soundness threshold; support for methods, replication, negative results, interdisciplinary or unconventional work; actual relevant published examples |
| Review speed | Desk-inclusive first decision, first decision after external review, acceptance and online-publication times separately, with statistic, population, period and source |
| Total author cost and effort | APC currency/year and waivers, validation expenses, deposits, format work, deadlines and maintenance commitments |
| AI-policy burden and verifiability | Actual kind of assistance, exemptions, disclosure/record requests and evidence of enforcement; use the shared `requirement-checkability.md` |

Open access does not establish support for open-source software, and a software-sharing mandate is not
the same as an affordable APC. Do not describe a journal as generally open-minded or conservative from
prestige, publisher identity or one anecdote. State the evidence, the particular kind of receptiveness
and confidence; label interpretive judgements as such.

Never advertise a short desk-inclusive first-decision median as the duration of external peer review.
Compare like metrics and populations, retain unknowns, and do not promise a decision by the author's
deadline. Journal-level timing and editorial assessments must not be copied from a publisher or sibling.

## Deliver the selection, not more homework

Provide a concise comparison: venue/article type, disposition and decisive validation rule, scientific
fit, open-science/source stance, editorial receptiveness, comparable review timing, cost, AI burden and
sources/dates. Expand only the dimensions that affect the decision. Recommend a first choice and a
sequential fallback where useful, with the main uncertainty and any remaining author decision.

Follow the author's priorities rather than assigning universal weights or a fake precision score.
Do the lookups yourself; do not ask the author to research policy pages. Stop once there is a usable
shortlist. Pass the chosen venue and verified requirements to `manuscript-journal-adapt`; a selection
request alone does not trigger manuscript rewriting, new experiments or a full integrity audit. When the
authors keep a shared record (`../manuscript-integrity-check/references/manuscript-record.md`), store the
chosen venue, article type and check date there.

After a rejection, `manuscript-reviewer-response` helps decide between revising for the same journal and
submitting elsewhere. When choosing the next venue, carry over the referees' concerns that still apply,
such as a validation requirement the paper cannot meet, rather than ranking from scratch.
