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

The steps, in order (each has its section below):

1. Read the priorities the record or the conversation already states; do not stop to ask for missing ones.
2. Build the pool: `rank` and the authors' own candidates, narrowed by subject, article type and feasibility.
3. Do the lookups: read each shortlisted venue's pages and write what you read into the record's `venue_facts`.
4. Run `ladder` for both ladders and `common` on every venue of both. Without stated priorities the ladder
   uses its default order, labelled as such.
5. Move a position where judgement outweighs the sorted order, and record the chosen order in `ladders`.
6. Write the files, register them in the run, and report; the priorities question, when it is still open,
   goes among the end-of-run decisions, and an answer re-ranks the ladders.

Use `manuscript-policy-fit` for study-specific clinical-scope, ethics, privacy and regulatory applicability,
including authors' voluntarily public personal genomes or biomedical records. Incorporate the actual
requirements and exceptions into the ladders; wording ambiguity alone does not establish a need for
new oversight, recruitment or clinical validation.

Apply the requested task across the whole paper unless the author specifies a narrower scope.
Follow the shared [workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
for requested section or stage review, before/after comparisons and optional interviews.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run. This applies to direct invocations too. End with its [end-of-stage checklist](../manuscript-integrity-check/references/project-workflow.md#end-of-stage-checklist): `report.md`, the smell check on it, `findings.json` with the prefix `JS` (venue trade-offs and policy conflicts as `decision: true` findings in the "Journal fit" category), and any applied edit recorded with `runs.py change` (a selection request alone edits nothing).

## Priorities: never a stop, recorded when stated, re-ranked when they change

A ladder needs an order of preference, and only the authors can give it, but a missing answer never holds
up the work. Use the manuscript, the conversation and the shared record first. Do the venue lookups before
anything depends on the order: they are the same whatever the authors answer. Until the authors state their
order, `ladder` uses its default and says so at the top of the ladder ("A default order, not yours yet"):

- **Journals:** speed to a first decision, then reach (journal impact factor), then a light AI-policy
  burden, then a low cost. A fast first decision makes a rejection cost weeks rather than months and keeps
  the next journal within reach; reach is what most authors weigh next; the AI-policy points count
  paperwork, not the chance of acceptance; cost comes last because the authors' budget decides it.
- **Preprint servers:** a direct transfer to a journal high on the journal ladder, then speed, then the
  AI-policy burden (posting is usually free).

Authors who post a preprint first can also order journals by whether their server sends the manuscript there
directly (`transfer` on the journal ladder: the server is `--server KEY` or the first rung of the record's
preprint ladder). Use it when the authors ask for a preprint-friendly journal ("bioRxiv-friendly"): every
journal checked accepts a posted preprint, so what differs is whether the server transfers to it and the
licence its rule allows. Read the server's live transfer list for every journal on the shortlist and record
it (`transfers`, with the journals it was read for in `transfers_checked`); a journal it was not read for is
not known, never "no".

An unknown budget is never read as "cost does not matter": until the authors state one, every fee they
would pay is shown and makes that journal "Depends" on whether they can pay it. Never save the default to
the record's `priorities`. Put one question among the end-of-run decisions, never as a stop before the
ladders, covering only what is still unknown:

- what matters most for each ladder, in order: speed to a decision, reach (journal impact factor), a light
  AI-policy burden, low cost, a direct transfer from their preprint server (and for the preprint ladder, a
  direct transfer to the first journals);
- an impact-factor floor, if any, and who pays the publication fee: only institutional agreements and funds,
  a grant (up to what amount), or nobody;
- whether to preprint, and where they lean.

When they answer, record it and run `ladder` and `common` again: the facts already read are reused, and only
a venue new to the ladder needs new lookups. This question is not the interview. The interview
(`references/interview.md`) runs only when the authors ask to be interviewed, and covers what AI did in each
section, the AI-policy burdens they refuse and whose venues to consider. Ask nothing else unless it changes
the ladders: subject, article type, validation done or affordable, deadline, licence or funder constraints.
Do not make the author supply a complete questionnaire.

Record what the authors state in the shared record (`../manuscript-integrity-check/references/manuscript-record.md`),
`manuscript-record.yaml` beside the manuscript (`<stem>.record.yaml` only when several manuscripts share the
folder): `priorities` (one order for each ladder, plus `jif_floor`, `budget_eur` in euros and
`validation_available` when they state them), `ai_use` (polish, revision or drafting) once the
conversation establishes it (AI wrote or rewrote whole passages of the Results or Discussion is `drafting`;
a writing rule that forbids the established use then counts as severe at the AI step, so a journal that
reserves those sections for the authors sorts below one that allows the use), the study design under `study.designs` with `study.confirmed` once the authors
confirm it, and the facts read for this manuscript under `venue_facts`. `ladder` reads all of these; an
option on the command line wins over the record. When the project keeps an equivalent planning document,
report the ladders there too, edited in place.

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
$V rank --study-design public-data --validation-available none --ai-use polish
$V rank --preprints                                               # preprint servers
$V show <venue-key>                                               # one venue's checklist
$V peers "First Last" --since 2019                                # where named colleagues publish
R=DIR/manuscript-record.yaml                                      # DIR: beside the manuscript, or where the authors say
# The journal ladder; repeat --only for each venue. Design, validation, AI use, impact-factor floor and budget
# come from the record; the options below override it for one run.
$V ladder --only KEY1 --only KEY2 --only KEY3 --record $R
$V ladder --only KEY1 --only KEY2 --record $R --study-design software --validation-available none \
   --ai-use polish --min-jif 3 --budget-eur 3000
$V ladder --only KEY1 --only KEY2 --only KEY3 --record $R --format csv > DIR/STEM.journal-ladder.csv
$V ladder --preprints --journal KEY1 --journal KEY2 --record $R --format csv > DIR/STEM.preprint-ladder.csv
$V common KEY1 KEY2 KEY3 SERVER1 --record $R > DIR/STEM.venue-requirements.md   # what every venue asks for
```

`rank` gives a first pool from the whole catalogue, ordered by AI friction and the recorded validation
rules; the recommendation comes from the full comparison below, and neither says anything about the chance of
acceptance. Use its field/type, JIF, OA, named-peer and `--refuse` filters
only for the author's actual preferences. Venues that require records of AI use beyond one acknowledgement
are listed like any other, with that burden in their points; `--refuse tracking` leaves them out only when
the authors rule that burden out. A filter never silently drops a venue the authors listed: `ladder` names
each listed venue a filter left out, with the reason (on standard error with `--format csv`). Unknown data
are not favourable evidence.

What AI did to the text is `unknown` until the conversation or the record establishes it: the ladder then
says what each AI rule would mean for each kind of use and assumes no conflict. Ask what AI did only when a
rule on the ladder turns on it (a drafting ban, a rule reserving the results and discussion), as one of the
end-of-run decisions. A study design in the record that the authors have not confirmed (`study.confirmed`
absent) can make a journal "Depends", never "Does not fit"; a design given with `--study-design` counts as
stated.

For the shortlist, read current journal-specific author instructions, scope and article-type pages, plus
applicable publisher requirements. Search specifically for validation, computational/public-data/MR
restrictions, code/licence/data rules, fees and the agreements that cover the corresponding authors'
institutions, turnaround metrics and the preprint policy; an AI-policy page alone is insufficient. For each
preprint server, read what it declines (tool announcements without data, health-related papers it sends to
another server), its AI rule and the journals it transfers to directly. The existing `policy_watch.py`
compares AI passages and does not establish that these other policies are unchanged; still run it for the
venues the result recommends, with the scripted routes only and without `--update`
(`uv run --script ../manuscript-journal-adapt/scripts/policy_watch.py check --venue KEY --routes httpx,chrome`),
then read with your own browser tool whatever it could not reach, before any archived copy. An archived copy
is dated by its capture and is not the current rule: say so, and read the live page when a decision rests
on it. During an author's task nothing writes into the plugin's references (no `--update`, and `record`
without `--update`). When the watcher exits 1 (a passage changed or a page is gone), read the changed
passage it quotes: if the rule moved, record the new rule in the venue's `venue_facts` with the page and
the date (the AI fields are listed in `references/selection-fields.md`), rerun `ladder` and `common`, and
tell the authors in one sentence that the catalogue's entry is out of date; a page that is gone is found
again at its new address. Publisher sites often block scripts and load fees,
agreement lists and review times by script, so follow the shared
[rule for blocked pages](../manuscript-integrity-check/references/author-priorities.md#minimum-useful-work):
the authors' own browser, when a browser-control tool is connected, reads what the other routes cannot. Whenever a selection task checks a decision-changing
requirement, state in the result, in plain sentences, its scope, accepted alternatives, the URL of the
page it is on and the date read; `references/selection-fields.md` lists what to capture. Do not
leave an expensive validation condition buried in background notes.

Write what you read into the record's `venue_facts` for this manuscript (review times, fees with the route
that pays them, preprint rules, the author-guideline fields the catalogue lacks), each with its source and
date; `ladder` and `common` lay these facts over the catalogue, mappings such as `limits` key by key. A page
that could not be read goes in as `not_read`, one sentence with the reason and the date; `common` then says
"the page could not be read" with that reason instead of sending the authors to look. Write facts into the
plugin's `venues.yaml` only when the task is maintaining this repository; during an author's task the
catalogue is read-only (it sits in the plugin cache). This does not require refreshing unrelated entries.

When `manuscript-policy-fit` finds a venue-specific rule (a server that declines tool announcements without
results, a journal's rule on identifiable individuals), it records the rule in that venue's `venue_facts`
under `other_desk_rules`, with the page and the date read. Rerun `ladder` and `common` after it, so the rule
reaches both ladders and the requirements file.

## Feasibility before preference

Identify each material requirement early, with its source/date, scope, strength, accepted alternatives
and exceptions. Distinguish explicit requirements, recommendations, published practice and judgement.
A publisher rule may apply only to one design, article type or journal. Check both what is required and
what work the author actually has; do not equate a policy mentioning cohorts with compulsory recruitment.

Give each candidate a practical verdict, in these words and always with the reason (the ladder's "Fits"
column prints them; the CSV keeps the same words, and the codes go, conditional, unknown and no-go stay
inside the scripts):

- **Fits**: no known conflict with the author's constraints after relevant checks, including known
  costs within the stated budget. This is not a guarantee of acceptance.
- **Depends on** the condition, named: a plausible affordable route exists, or applicability or a waiver
  needs checking (a publication fee above the budget, or not yet weighed against one, unless a waiver or
  institutional agreement applies; a validation rule under a study design the authors have not confirmed).
  State the exact condition and who can resolve it. An AI-policy conflict with the authors' established
  use is "Depends", with the rule quoted and its page linked: how to handle journal policy is the authors'
  decision, listed with their other decisions.
- **Does not fit the stated constraints**: a confirmed scope restriction, expense or required
  validation has no available route. Say why before ranking softer preferences. The author can still
  choose to try. A journal's AI policy never puts a venue here.
- **Could not be checked**: a material requirement or cost remains unresearched or unavailable, with the
  reason ("its validation rules have not been researched"). Keep this visible rather than silently treating
  it as permissive.

The ladder's `fits` is the whole verdict: the recorded validation rules, a conflict between a journal's AI
rule and the established AI use, and the fee against the budget. `validation_fits` is the validation rules
alone, which `ladder` sorts by. Do not let a favourable AI policy, JIF or claimed speed compensate for an
infeasible validation requirement; `ladder` sorts by feasibility before any priority for this reason. Show
infeasible candidates separately or explain their exclusion. Do not treat a second public dataset as
automatically satisfying an independent-clinical-cohort rule; check the rule and dataset.

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
deadline. A desk-inclusive median is short at a selective journal because most submissions are returned
unreviewed, so speed first can put such a journal at the top of the ladder for the wrong reason. Before the
ladder is handed over, judge each rung's editorial bar against what the paper shows now (a stated "clear
advance over the state of the art in a side-by-side demonstration", a field-level advance, a scope it reads as
outside): a journal the paper does not yet meet goes below the journals that would send it to referees, with
the reason and what would move it back up. Simulated referees (manuscript-peer-review) take the top rungs, so
an unjudged top three becomes a review against journals the authors would not choose. Journal-level timing and editorial assessments must not be copied from a publisher or sibling.

## What the ladders have in common

Run `common` on every venue of both ladders. It reports:

- **Adapt now**: requirements one version of the manuscript can meet for every venue at once (a section only
  one venue requires usually costs the others nothing, and so does a rule the catalogue marks as an addition
  every version can carry, such as alt text or a dataset citation), with the venues that ask for each. A
  length limit, a set of abstract headings or the body's structure is here only when every venue's is known
  and the same. The body's headings (Background or Introduction, Methods or Implementation, Results,
  Discussion, Conclusions) and their order are one structure per venue, compared whole: each heading names a
  part every version has, so two venues that name or order them differently disagree, and a part of the
  abstract one venue asks for changes the abstract's form. These shared demands are the ones to adapt before
  the choice.
- **Choose per venue**: where the venues disagree, or where only some venues' rule is known (abstract
  headings, length limits, the body's sections and their order, reference style). They are the authors'
  decisions for later, listed once: they wait for the choice, or follow the first rung, and are never applied
  before it. Writing to the shortest limit is an option to offer, with its cost, never a default.
- **At the end**: software archiving and the AI-use statement, written once with every field any venue asks
  for and placed wherever each venue asks.
- **The AI writing rules on the list**, and the strictest of them (every one of equal strictness, when they
  tie), with what it means for the AI use the authors described. Name it once as the authors' decision; a
  statement describes the use that happened, so never offer a rewrite as a way to satisfy a stricter rule.
- **Not researched yet**: the fields no reading covers, per venue, with the reason when the page could not
  be read. This is your work, not the authors': read those fields from the live author guidelines, add them
  to `venue_facts` (or `not_read` with the reason when the page stays unreadable) and run `common` again;
  never report a venue as having no rule.

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

Do the lookups yourself; do not ask the author to research policy pages, and never hand them a field to
fill in the record. Stop once both ladders are usable. Pass the chosen venue and verified requirements to
`manuscript-journal-adapt`; a selection request alone does not trigger manuscript rewriting, new experiments
or a full integrity audit. Store the ladders, the chosen venue, article type and check date in the record.

Give, in this order: the preprint ladder; the journal ladder as a table (position, venue and article type,
verdict and the rule that decides it, comparable speed, impact factor, AI burden and its red flags, cost
and who pays, preprint rule) with one or two sentences per venue on fit and what would move it; what every
venue asks for (adapt now, choose per venue, at the end); then the authors' decisions together (their order
of priorities while the default stands, a fee route or budget, a validation tradeoff, what AI did when a rule
on the ladder turns on it, a journal policy that conflicts with their actual use, the strictest AI rule on
the list, each named once with its practical consequence). Recommend a first choice and its fallbacks, with
the main uncertainty. Follow the author's priorities rather than assigning universal weights or a fake
precision score; the ladder is an order of preference and says nothing about the chance of acceptance.

Write it as [Writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)
describes. Call a rung a position or a choice ("the first choice", "second on the ladder"). Quote the rule
that decides each venue with the URL of the page it is on and the date it was read. Use plain words for the
catalogue's terms: describe a study design ("a software paper", "a reanalysis of public data") and a policy
rule ("asks authors not to have AI draft text") rather than showing a design key, field or flag name such as
`public-data`, `banned_drafting` or `drafting-ban`. Give the AI-policy burden in words, as the ladder table
does (light, moderate, heavy or severe, with what the policy asks for), and name every red flag as a
sentence: AI drafting banned for the whole paper, prompts or a record of AI changes required, an AI-text
detector run on submissions, declared use held against the paper. The points and the red-flag icons stay in
the CSV and the dashboard. A rule that reserves only some sections (the results and discussion) is named
with those sections. Spell out acronyms at first use (article processing charge, journal impact factor) and
write full sentences; a table is fine when every cell is a readable phrase. If the result also lists work on
the manuscript (concerns the referees raised, a missing statement), group it under the four labels of
[Order the work by when it can be done](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done):
science fixes first, archiving and declarations last, and none of it an obstacle to choosing.

## Where the outputs go

Write four files, named after the manuscript (`STEM` is its file name without the extension), in the folder
the authors name; without one, beside the manuscript source, or beside the project's venue planning document
when it keeps one:

| File | What it holds |
|---|---|
| `manuscript-record.yaml` (`STEM.record.yaml` only when several manuscripts share the folder; an existing record keeps its name) | The authors' priorities and every venue fact read for this manuscript, with source and date |
| `STEM.journal-ladder.csv` | The journal ladder in fixed columns |
| `STEM.preprint-ladder.csv` | The preprint ladder in the same columns |
| `STEM.venue-requirements.md` | What every venue on the ladders asks for (`common`) |

The CSV columns are fixed: the sorted rung and the chosen rung from the record, the whole verdict and its
reason (`fits`) beside the validation verdict alone (`validation_fits`), days to a first decision with its
source and date, impact factor, AI-policy points, the AI policy aspect by aspect (drafting, prompts, a record
of AI changes, AI-text detection, where to declare, whether declared use counts against the paper, extra
work), each as `level: words` with `red` for a red flag, and the policy page, fee with its route and source,
preprint rule or direct transfers (for a server, the journals it transfers to, `none` when the list was read
and names none of the ladder's journals; for a journal, the authors' preprint server when it transfers there
directly, `none` when its checked list leaves the journal out; empty when not known), the facts taken from the record, the priorities used and whether they are the
authors' or the default (`priorities_source`), the AI use and the study designs read. An empty cell means not
known, never zero. Regenerate the CSV and the requirements file from the record instead of editing them, so a
re-rank shows in the diff. When the project keeps a venue planning document, update its ladder section in
place as well. The reply names every path, relative to the project. These files are the skill's output,
written without asking; a scratch location is for fetched pages only.

Register the same files in the run, so the dashboard's Journals tab finds them, and write `top3.json` there
for the journals you recommend (the chosen one first, with its fallbacks):

```bash
RUNS="uv run --script ../manuscript-integrity-check/scripts/runs.py"
S=manuscript-journal-select
$RUNS add RUN --skill $S --file DIR/STEM.journal-ladder.csv --role other --name STEM.journal-ladder.csv
$RUNS add RUN --skill $S --file DIR/STEM.preprint-ladder.csv --role other --name STEM.preprint-ladder.csv
$RUNS add RUN --skill $S --file DIR/STEM.venue-requirements.md --role other --name STEM.venue-requirements.md
$RUNS add RUN --skill $S --file $R --role other --name manuscript-record.yaml   # the record's own file name
```

`RUN/manuscript-journal-select/top3.json` is a JSON list, best first, of at most three entries:
`[{"key": "bmc-bioinformatics", "name": "BMC Bioinformatics", "article_type": "software article", "why": "one
sentence on why it is recommended, in plain words", "url": "https://bmcbioinformatics.biomedcentral.com/submission-guidelines"}]`.
`key` is the ladder's venue key, `url` the venue's author guidelines. Write it in that folder and register
it like the others (`$RUNS add RUN --skill $S --file RUN/$S/top3.json --role other --name top3.json`).

After a rejection, `manuscript-reviewer-response` helps decide between revising for the same journal and
submitting elsewhere. When choosing the next venue, step down the ladder and carry over the referees'
concerns that still apply, such as a validation requirement the paper cannot meet, rather than ranking
from scratch.
