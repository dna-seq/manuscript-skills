---
name: manuscript-journal-select
description: >-
  Select where to preprint and where to publish a manuscript, as two ladders ordered by the authors' own
  priorities (speed, reach, AI-policy burden, cost), after checking subject, article type, available validation
  and budget, open-source and open-science preferences, editorial receptiveness, review speed and AI-policy
  burden; and list the requirements every venue on the ladders shares, so that those sections can be adapted
  before the choice. Use for journal shortlists, preprint server choice, requirements-based venue comparisons or
  a submission sequence, especially for in-silico-only work, and when asked to interview the authors to pick a
  journal or preprint server by how strict or hostile its AI policy is, or to see where named colleagues
  publish. Reuse the shared venue database; use manuscript-journal-adapt after selection.
---

# Choose where to preprint and where to publish

Help the authors publish sound work within their actual resources. Read
`../manuscript-integrity-check/references/author-priorities.md`. The author decides tradeoffs and policy
interpretations; journal requirements are information for that decision, not assistant prohibitions.
For policy-verification limits, consult
`../manuscript-integrity-check/references/requirement-checkability.md` when needed.

The result is two ladders and one shared list:

- **The preprint ladder**: the server to post on first, and the fallback if it declines the paper.
- **The journal ladder**: the journals in the order the authors would try them, each rung with its verdict,
  the rule that decides it and what would move it up or down.
- **What every venue on the ladders asks for**: the requirements one version of the manuscript can meet now,
  where the venues disagree, and what waits for the final code and data.

These are files the authors keep and rerun, so they go where the authors can open them (see "Where the
outputs go" below), never to a scratch location.

Use `manuscript-policy-fit` for study-specific clinical-scope, ethics, privacy and regulatory applicability,
including authors' voluntarily public personal genomes or biomedical records. Incorporate the actual
requirements and exceptions into the ladders; wording ambiguity alone does not establish a need for
new oversight, recruitment or clinical validation.

Apply the requested task across the whole paper unless the author specifies a narrower scope.
Follow the shared [workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
for requested section or stage review, before/after comparisons and optional interviews.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run. This applies to direct invocations too.

## Priorities: ask once, record them, re-rank when they change

A ladder needs an order of preference, and only the authors can give it. Use the manuscript, the
conversation and the shared record first. When the record or the conversation does not already state them,
ask one short batch, with the environment's question interface when there is one:

- what matters most for the journal ladder, in order: speed to a decision, reach (journal impact factor),
  a light AI-policy burden, low cost;
- an impact-factor floor, if any;
- who pays the publication fee: only institutional agreements and funds, a grant, or nobody;
- whether to preprint, and where they lean.

These are the facts that change the order, so the batch is part of every selection. It is not the interview.
The interview (`references/interview.md`) runs only when the authors ask to be interviewed, and covers what
AI did in each section, the AI-policy burdens they refuse and whose venues to consider. Ask nothing else unless
it changes the ladders: subject, article type, validation done or affordable, deadline, licence or funder
constraints. Do not make the author supply a complete questionnaire.

Record the answers in the shared record (`../manuscript-integrity-check/references/manuscript-record.md`),
written beside the manuscript: `priorities` (one order for each ladder), and the facts read for this
manuscript under `venue_facts`. When
the authors change a priority, update the record and run the ladder again: the facts already read are
reused, and only a venue new to the ladder needs new lookups. When the project keeps an equivalent planning
document, report the ladders there too, edited in place.

An author's in-silico-only budget is a real constraint, so distinguish existing/public independent
validation data, collecting a new cohort, and laboratory work: computational replication may be affordable
even when recruitment or experiments are not. Do not infer access to a second dataset or collaborators.
Capture any resource ceiling once and reuse it; recommend feasible venues rather than expanding the study
just to fit an expensive journal. APC waivers, institutional agreements and zero-APC routes can matter.

## Reuse the database and verify decision-changing requirements

Read `../manuscript-integrity-check/references/venues.yaml` through the existing helpers, or inspect a
specific entry. Keep these skills together; do not create a second journal database.

Commands below are relative to this skill directory:

```bash
V="uv run --script ../manuscript-journal-adapt/scripts/venues.py"
$V rank --field bioinformatics --type software                    # a first pool, by AI-policy burden
$V rank --study-design public-data --validation-available none
$V rank --preprints                                               # preprint servers
$V show <venue-key>                                               # one venue's checklist
$V peers "First Last" --since 2019                                # where named colleagues publish
R=DIR/STEM.record.yaml                                            # DIR: beside the manuscript, or where the authors say
$V ladder --only KEY --only KEY ... --record $R                   # the journal ladder, by the recorded priorities
$V ladder --only KEY ... --record $R --format csv > DIR/STEM.journal-ladder.csv
$V ladder --preprints --journal KEY ... --record $R --format csv > DIR/STEM.preprint-ladder.csv
$V common KEY KEY ... --record $R > DIR/STEM.venue-requirements.md  # what every venue on the ladders asks for
```

`rank` gives a first pool from the whole catalogue, ordered by AI friction and the recorded validation
rules; the recommendation comes from the full comparison below, and neither says anything about the chance of
acceptance. Use its field/type, JIF, OA, named-peer and `--refuse` filters
only for the author's actual preferences. The helper excludes mandatory AI record-keeping venues by default;
explain that omission and use `--include-tracking` when the author wants them considered. Unknown data are
not favourable evidence.

For the shortlist, read current journal-specific author instructions, scope and article-type pages, plus
applicable publisher requirements. Search specifically for validation, computational/public-data/MR
restrictions, code/licence/data rules, fees and the agreements that cover the corresponding authors'
institutions, turnaround metrics and the preprint policy; an AI-policy page alone is insufficient. For each
preprint server, read what it declines (tool announcements without data, health-related papers it sends to
another server), its AI rule and the journals it transfers to directly. The existing `policy_watch.py`
compares AI passages and does not establish that these other policies are unchanged; still run it for the
venues the result recommends (`uv run --script ../manuscript-journal-adapt/scripts/policy_watch.py check --venue KEY`)
and read the live page for anything it could not reach. Publisher sites often block scripts and load fees,
agreement lists and review times by script, so follow the shared
[rule for blocked pages](../manuscript-integrity-check/references/author-priorities.md#minimum-useful-work):
the authors' own browser, when a browser-control tool is connected, reads what the other routes cannot. Whenever a selection task checks a decision-changing
requirement, state in the result, in plain sentences, its scope, accepted alternatives, the URL of the
page it is on and the date read; `references/selection-fields.md` lists what to capture. Do not
leave an expensive validation condition buried in background notes.

Write what you read into the record's `venue_facts` for this manuscript (review times, fees with the route
that pays them, preprint rules, the author-guideline fields the catalogue lacks), each with its source and
date; `ladder` and `common` lay these facts over the catalogue. Write them into the plugin's `venues.yaml`
only when the task is maintaining this repository; during an author's task the catalogue is read-only (it
sits in the plugin cache). This does not require refreshing unrelated entries.

## Feasibility before preference

Identify each material requirement early, with its source/date, scope, strength, accepted alternatives
and exceptions. Distinguish explicit requirements, recommendations, published practice and judgement.
A publisher rule may apply only to one design, article type or journal. Check both what is required and
what work the author actually has; do not equate a policy mentioning cohorts with compulsory recruitment.

Give each candidate a practical disposition. The report uses the plain label (the words `rank` prints in
its validation column); the internal name may follow in parentheses:

- **Fits** (GO): no known conflict with the author's constraints after relevant checks, including known
  costs within the stated budget. This is not a guarantee of acceptance; say so when the helper's "Fits"
  covers only the recorded validation rules.
- **Depends** (CONDITIONAL): a plausible affordable route exists, or applicability/waiver needs checking
  (for example a publication fee above the budget unless a waiver or institutional agreement applies).
  State the exact condition and who can resolve it. An AI-policy conflict with the authors' actual use is
  "Depends", with the rule quoted and its page linked: how to handle journal policy is the authors'
  decision, listed with their other decisions.
- **Does not fit the stated constraints** (NO-GO): a confirmed scope restriction, expense or required
  validation has no available route. Say why before ranking softer preferences. The author can still
  choose to try. A journal's AI policy never puts a venue here.
- **Not known** (UNKNOWN): a material requirement or cost remains unresearched/unavailable. Keep this
  visible, with the reason, rather than silently treating it as permissive.

Do not let a favourable AI policy, JIF or claimed speed compensate for an infeasible validation requirement.
`ladder` sorts by feasibility before any priority for this reason. Show infeasible candidates separately or
explain their exclusion. Do not treat a second public dataset as automatically satisfying an
independent-clinical-cohort rule; check the rule and dataset.

## Connected manuscripts and publication order

When the project records related manuscripts, read their current contribution, evidence and publication
status before recommending an order. Keep each paper's venue choices and constraints separate. Explain
what one paper assumes from the other, how their claims differ, which cross-citations should be preprint
or published versions, and which shared code/data releases each needs. Recommend a concrete sequence for
preprints, submissions and subsequent version updates, with parallel steps where independence permits.
Check the shortlisted venues' overlap, prior-publication and preprint rules before treating a dependency
as a submission barrier. Do not invent a need to await acceptance when a citable preprint is sufficient.
Save the sequence and unresolved conflicts in the selection run and scientific shared record. This is
planning, not authorization to submit, upload a preprint or rewrite either paper.

## The two ladders

**The journal ladder.** Order the feasible candidates by the authors' priorities, in their order: `ladder`
sorts by feasibility, then by each priority in turn, puts a value nobody has read below every known value at
its step, and passes a tie to the next priority. It compares speed only as days to a first decision, and a
fee only in euros (as listed, or `author_cost_eur` after an agreement, fund or waiver the authors can use).
Then judge what the numbers cannot: scientific fit and realistic prospects, the bar a software paper must
clear, the length the manuscript would have to lose. Move a rung when one of these outweighs the sorted
order, say why, and record the chosen order in the record's `ladders`. Each rung states its verdict, the rule that decides it (quoted, with its page and the
date read), its comparable figures and what would move it.

**The preprint ladder.** Order the servers by the authors' preprint priorities with
`ladder --preprints --journal KEY ...`, the journals given in their ladder order. The `transfer` priority puts
first the server that transfers directly to the highest rung. Before order, check scope: a server that would
decline the paper (a tool announcement without results, a paper it sends to a clinical server, content it
screens out) is not a rung, whatever its AI policy. Then check the two ladders against each other: every
journal on the journal ladder must accept a manuscript already posted on the chosen server, with the licence
chosen for the preprint. Name any journal whose rule conflicts, and the licence that keeps every rung open.

Never advertise a short desk-inclusive first-decision median as the duration of external peer review.
Compare like metrics and populations, retain unknowns, and do not promise a decision by the author's
deadline. Journal-level timing and editorial assessments must not be copied from a publisher or sibling.

## What the ladders have in common

Run `common` on every venue of both ladders. It reports:

- **Adapt now**: requirements one version of the manuscript can meet for every venue at once (a section only
  one venue requires usually costs the others nothing), with the venues that ask for each.
- **Choose per venue**: where the venues disagree (abstract headings, length limits, section order, reference
  style). These wait for the choice, or follow the first rung; writing to the shortest limit is an option to
  offer, with its cost, never a default.
- **At the end**: software archiving and the AI-use statement, written once with every field any venue asks
  for and placed wherever each venue asks.
- **The AI writing rules on the list**, and the strictest of them. Name it once as the authors' decision.
- **Not researched yet**: the fields no reading covers, per venue. Read them from the live author guidelines,
  add them to `venue_facts` and run `common` again; do not report a venue as having no rule.

When the authors want to adapt before choosing, pass the "Adapt now" part to `manuscript-journal-adapt`. It
edits the manuscript in place; the per-venue part waits.

## Compare viable candidates on the author's priorities

| Dimension | Assess with evidence |
|---|---|
| Scientific fit and realistic prospects | Contribution, scope, article type, relevant recent papers and acceptance criteria |
| Open source and open science | Submitted-software source/licence requirements; data and code availability; reproducibility artifacts; preprints; open review; acceptance of justified privacy/access restrictions |
| Editorial conservatism or receptiveness | Stated novelty/soundness threshold; support for methods, replication, negative results, interdisciplinary or unconventional work; actual relevant published examples |
| Review speed | Desk-inclusive first decision, first decision after external review, acceptance and online-publication times separately, with statistic, population, period and source |
| Total author cost and effort | APC currency/year and waivers, the agreements and funds that cover the corresponding authors, validation expenses, deposits, format work, deadlines and maintenance commitments |
| AI-policy burden and verifiability | Actual kind of assistance, exemptions, disclosure/record requests and evidence of enforcement; use the shared `requirement-checkability.md` |

Open access does not establish support for open-source software, and a software-sharing mandate is not
the same as an affordable APC. Do not describe a journal as generally open-minded or conservative from
prestige, publisher identity or one anecdote. State the evidence, the particular kind of receptiveness
and confidence; label interpretive judgements as such.

## Deliver the ladders, not more homework

## Where the outputs go

Write four files, named after the manuscript (`STEM` is its file name without the extension), in the folder
the authors name; without one, beside the manuscript source, or beside the project's venue planning document
when it keeps one:

| File | What it holds |
|---|---|
| `STEM.record.yaml` (or the existing `manuscript-record.yaml`) | The authors' priorities and every venue fact read for this manuscript, with source and date |
| `STEM.journal-ladder.csv` | The journal ladder in fixed columns |
| `STEM.preprint-ladder.csv` | The preprint ladder in the same columns |
| `STEM.venue-requirements.md` | What every venue on the ladders asks for (`common`) |

The CSV columns are fixed: the sorted rung and the chosen rung from the record, verdict and its reason, days to a first decision with its source and date,
impact factor, AI-policy points, the AI policy aspect by aspect (drafting, prompts, a record of AI changes,
AI-text detection, where to declare, whether declared use counts against the paper, extra work), each as
`level: words` with `red` for a red flag, and the policy page, fee with its route and source, preprint rule
or direct transfers, the facts taken from the record and the priorities used. An empty cell means not known, never zero. Regenerate the CSV
and the requirements file from the record instead of editing them, so a re-rank shows in the diff. When the
project keeps a venue planning document, update its ladder section in place as well. The reply names every
path, relative to the project. These files are the skill's output, written without asking; a scratch
location is for fetched pages only.

Give, in this order: the preprint ladder; the journal ladder as a table (rung, venue and article type,
verdict and the rule that decides it, comparable speed, impact factor, AI burden and its red flags, cost
and who pays, preprint rule) with one or two sentences per rung on fit and what would move it; what every venue asks for
(adapt now, choose per venue, at the end); then the authors' decisions together (a fee route, a validation
tradeoff, a journal policy that conflicts with their actual use, the strictest AI rule on the list, each
named once with its practical consequence). Recommend a first rung and its fallbacks, with the main
uncertainty. Follow the author's priorities rather than assigning universal weights or a fake precision
score; the ladder is an order of preference and says nothing about the chance of acceptance.

Write it as [Writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)
describes. Quote the rule that decides each venue with the URL of the page it is on and the date it was
read. Use plain words for the catalogue's terms: describe a study design ("a software paper", "a
reanalysis of public data") and a policy rule ("asks authors not to have AI draft text") rather than
showing a design key, field or flag name such as `public-data`, `banned_drafting` or `drafting-ban`; the
name may follow in parentheses. Give the AI-policy burden as `rank` does, in points with the reason in
words, and name every red flag (⚑): AI drafting banned for the whole paper, prompts or a record of AI
changes required, an AI-text detector run on submissions, declared use held against the paper. A rule that
reserves only some sections (the results and discussion) is named with those sections. The review
dashboard shows the same flags as icons. Spell out acronyms at first use (article processing charge, journal impact factor) and write full
sentences; a table is fine when every cell is a readable phrase. If the result also lists work on the
manuscript (concerns the referees raised, a missing statement), group it under the four labels of
[Order the work by when it can be done](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done):
science fixes first, archiving and declarations last, and none of it an obstacle to choosing.

Do the lookups yourself; do not ask the author to research policy pages. Stop once both ladders are usable.
Pass the chosen venue and verified requirements to `manuscript-journal-adapt`; a selection request alone
does not trigger manuscript rewriting, new experiments or a full integrity audit. Store the ladders, the
chosen venue, article type and check date in the record.

After a rejection, `manuscript-reviewer-response` helps decide between revising for the same journal and
submitting elsewhere. When choosing the next venue, step down the ladder and carry over the referees'
concerns that still apply, such as a validation requirement the paper cannot meet, rather than ranking
from scratch.
