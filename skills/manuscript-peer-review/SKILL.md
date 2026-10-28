---
name: manuscript-peer-review
description: >-
  Simulate journal referee reports on an author's draft, with independent referees, manuscript
  quotations, a defence pass and an ordered revision list. Use for pre-submission red-teaming,
  Reviewer 2, desk-editor or methods-reviewer passes, or drafting a report when the user is an
  invited referee. The full panel has three referees plus a defender; a requested quick pass uses
  two seats. Keep simulated reports separate from real editorial reviews. Use
  manuscript-reviewer-response for responding to real referees and manuscript-integrity-check for
  mechanical submission checks.
---

# Simulated peer review

Give the authors the referee reports they would otherwise receive after submission, while they can
still act on them, and the list of what to fix that those reports imply. Read the shared [author priorities](../manuscript-integrity-check/references/author-priorities.md)
and, when it exists, the
[manuscript record](../manuscript-integrity-check/references/manuscript-record.md).

This is a simulation of what careful referees at a named journal could raise, not a prediction of the
editor's decision. Each simulated referee gives the recommendation a referee gives (accept, minor
revision, major revision or reject) with the concerns it rests on. Never give scores, ratings, an
acceptance probability, an average of the recommendations or a predicted editorial decision. This skill
reports; it never edits the manuscript.

Apply the review to the whole paper unless the authors name a narrower scope, and follow the shared
[workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review).

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run, ending with its [end-of-stage checklist](../manuscript-integrity-check/references/project-workflow.md#end-of-stage-checklist) (report, smell check, `findings.json`, `finish`). This applies to direct invocations too.

## What this skill judges, and what it reuses

Referee judgement: is the contribution clear and new; does the design answer the question; do the
results support the claims as stated; which alternative explanations, missing controls and missing
comparisons would a referee raise; where would wording invite a misreading.

Checkable problems belong to other skills. Reuse their results; do not re-run them here:

| Check | Skill |
|---|---|
| Unfinished content (TODO markers, placeholders), leftovers, declarations, venue limits | manuscript-integrity-check, Steps 1 and 4 |
| Numbers that disagree across sections, impossible means, p-values that do not match (`number_check.py`) | manuscript-integrity-check, Step 3 |
| Claim calibration: claims above their evidence, named by gap | manuscript-integrity-check, Step 5 |
| Citation identity, retractions, source support; "first", "novel" and "only" claims ([claim-support.md](../manuscript-reference-check/references/claim-support.md#priority-and-absence-claims)) | manuscript-reference-check |
| Reporting guidelines, data, code and software availability, statistics reporting | manuscript-reporting-check |
| Ethics, consent, privacy and clinical-scope applicability | manuscript-policy-fit |
| How each figure reads in print (legibility, colour, layout), captions, citation order, the code that draws it | manuscript-figures |

When `manuscript-record.yaml` lists one of these as a current check (same manuscript sha256, or the
changed sections lie outside its scope), or its findings are in the conversation, cite its result where a
referee would raise the same point, and say why where the panel judges it differently. Whether the
results support the claims stays referee judgement, with integrity's Step 5 as its starting point. A
confirmed point in another check's remit (a number that disagrees, a missing statement or archive, a
TODO, a citation's identity, an ethics or consent point, a figure's legibility) goes in Part 2 of the result, in a short "Also found, belongs to other
checks" list naming its skill (or, when it waits for the end, such as a declaration or an archive
record, in the end-stage group), never among the ranked items; a referee's report may still mention it,
as real referees do. When a check has not run, say so under "What this review did not have" and offer
it; do not run it here. The one check this skill runs is resolving prior-work identifiers (step 4);
the editor's desk screen (step 2) only reads the draft against the journal's recorded rules.

## Choose the mode

- **Own draft** (default): simulate submitting the authors' manuscript to a journal, and give them the
  referees' reports and their list of what to fix ([output-format.md](references/output-format.md)).
- **Invited referee**: the user is reviewing someone else's submission. Start the review without asking
  them to confirm anything, and follow [invited-referee.md](references/invited-referee.md): a draft
  referee report for the user to edit, with comments to the authors and to the editor kept apart, no
  recommendation unless asked, and at most one sentence on the venue's rule on AI help for referees.
- **Quick pass**: when manuscript-integrity-check or manuscript-improve asks for independent desk-editor
  and methods-reviewer passes, run two seats as described in [seats.md](references/seats.md#quick-pass-for-an-integrity-audit).
- **After real reviews arrive**: use manuscript-reviewer-response. A simulated review is never presented
  as, or mixed with, real referees' comments.

## Step 1: establish the paper

Read the whole manuscript and any supplementary files supplied (convert `.docx` or a Google Doc export
with `pandoc -t gfm`). Read `manuscript-record.yaml` when it exists. Write down, for your own use:

- the question, the headline claims (C1, C2 ...) with their locations and the evidence each rests on,
  and the stated non-claims;
- the study designs (record keys), domains, venue and article type, where known.

This claim map is for adjudication. It is never given to the seats, and its ids never stand alone in the
report: name the claim in words, with its id in parentheses if at all.

For the editor's desk screen (step 2), also note the length of the body and the abstract, counted as the
journal counts them, from a current integrity-check or journal-adapt result when one exists.

## Step 2: choose the journal and the panel

**The journal.** Referees judge against a journal's scope, bar and article type, so simulate a
submission to a real one. Take the first that applies, without asking:

1. the journal the authors name in the request;
2. `venue` in `manuscript-record.yaml`, or the chosen journal in the project's own planning document;
3. the journal ladder (`ladders.journals` in the record, or the project's equivalent): the **top three
   rungs**. The result says, for the authors, why these three lead (the recorded priorities and the date of
   the ladder), so a reader who expected other journals sees where the order came from; when the ladder
   records no judgement of their editorial bar against the paper (every rung's fit not known), say that too
   and offer to rerun after manuscript-journal-select has judged it;
4. otherwise a generic journal in the paper's field, for the article type the manuscript reads as. Say
   so at the top of the result and offer to rerun for a named journal or for the top of a ladder from
   manuscript-journal-select.

For each journal, write the referees' `venue.md` (one file in the run folder, `$WORK/venue.md`, with one
section per journal). Take its facts from
`../manuscript-journal-adapt/scripts/venues.py show KEY`: the journal's name and the article type, its
fields and article types, its editorial profile, the rules its editors check on arrival, its validation
and software requirements, its length limits and what it asks its referees (`reviewer_form`: the questions
on its form and its recommendation options, quoted). `venues.py stale KEY` lists the facts old enough to
re-read; read only those, and what the catalogue lacks: the journal's guidelines for reviewers when no
`reviewer_form` is recorded (a page among the entry's `sources`, or the publisher's guidelines for
reviewers), and for a journal not in the catalogue its author guidelines and guidelines for reviewers. Write
every fact you read into the venue catalogue with its page and date (`venues.py where` names the file;
[selection-fields.md](../manuscript-journal-select/references/selection-fields.md) gives the fields), a form
that is not public as a `reviewer_form` with only a `note` saying so, so the next run reuses the reading.
Leave out the authors' priorities and why they chose or ranked the journal. Record what each brief was read
from and when; the result says so, or that the guidelines for reviewers could not be found.

**The editor's desk screen.** Before the referees, read the draft against the journal's checkable desk
rules: article type, length (a current recorded result, or the word count from step 1), required
abstract headings, an excluded study design, a required item such as a cover letter. A rule the draft
fails is reported first in Part 1 of the result, quoted with its page. A rule that needs judgement
("papers of less significance") is left to the referees.

**The panel.** By default run **three seats plus the defender**, chosen from the study design with
[seats.md](references/seats.md#choosing-the-panel): the design's main seat, the skeptic and the champion.
Add the domain modules whose trigger cues match and whose exclusion cues do not:

- [domains/genomics.md](references/domains/genomics.md)
- [domains/software-and-methods.md](references/domains/software-and-methods.md)
- [domains/human-data-and-clinical.md](references/domains/human-data-and-clinical.md)
- [domains/ai-systems.md](references/domains/ai-systems.md)

When the simulation covers three journals, the same three seats each read the paper once and give a
recommendation for each journal: the science they judge does not change between journals; the bar, the
scope and the article type do. A separate panel per journal is the fuller option
([options.md](references/options.md#a-separate-panel-for-each-journal)).

Run it without asking, state the journal and the panel at the top of the output, and offer the
five-seat panel (two more whole-paper reads). Ask first only when the authors want to choose the panel:
then one short message with the journal, the seats, the modules and why, and the cost (each seat reads
the whole paper).

## Step 3: run the seats in isolation

- Seat workspaces, merged findings, defence, adjudication and check outputs go under this skill's
  durable run folder (`$WORK` below). Register the actual reports and task briefs under the shared
  run-output contract. The `reports` setting controls how much is also presented in chat (step 7).
- Give each seat its own workspace holding only: a reading copy of the manuscript with HTML comments,
  LaTeX comments and revision markers removed, as an editor would see it; the supplementary files; the
  figures as images (`figures/`, from `../manuscript-figures/scripts/figures.py workspace`), so the seat
  looks at them as a referee does; a copy of [finding-schema.md](references/finding-schema.md); `venue.md` from step 2; and the questions
  of any domain module loaded for that seat, as `domain-questions.md` (no other seat sees them). Nothing else: no
  `manuscript-record.yaml`, no other seat's output, no cover letter, earlier reviews, notes or the
  authors' view of their paper. Quotes are still checked against the original, where comments are not
  quotable either.
- Build the workspaces and fill in the briefs with one command, from this skill directory, never by hand:

  ```bash
  uv run --script scripts/workspaces.py seats "$WORK" --paper PAPER.md --supplement SUPPLEMENT.md \
      --files SUPPLEMENTARY_FOLDER --venue "$WORK/venue.md" --journal "JOURNAL=ARTICLE TYPE" \
      --design "DESIGN KEYS" --seat MAIN_SEAT --seat skeptic --seat champion --module SEAT=MODULE[,MODULE]
  ```

  Give the manuscript and its supplement where they are, beside their figures (the run's snapshot in
  `RUN/inputs/` cannot find them), and `--journal` once per journal. Each seat's remit is its section of
  [seats.md](references/seats.md), with the default panel's additions (the main seat also takes
  reproducibility, the skeptic claims and novelty, unless those have seats of their own). A seat without a
  section there (software-methods, a domain seat, a custom seat) needs `--remit SEAT=TEXT`, a sentence or two
  in the remit's words, and a custom seat `--prefix SEAT=XY`. It writes `$WORK/seats/SEAT/` and the brief
  `$WORK/briefs/SEAT.md`, and prints what each workspace holds, the supplementary files it left out (those
  neither the paper nor its supplement names; `--file` or `--all-files` adds them) and any figure without an
  image. Run it through `runs.py exec` so its output is kept, read the left-out files and the warnings,
  register the briefs, and start each seat with its brief file unchanged. A seat run again gets a new
  workspace (`SEAT.2`) from the same command; the first stays as it was.
- **Independence is required**, as [Independent readers and referees](../manuscript-integrity-check/references/project-workflow.md#independent-readers-and-referees) sets out: a fresh session
  per seat whose only context is its brief, free of the authors' standing instructions and memory, started by
  the session that can start agents (in
  manuscript-improve, the coordinator itself), the brief filled from the template and nothing else, and
  `--isolation` recorded for every seat and the defender.
- Start each seat as a fresh session with the seat brief from
  [seats.md](references/seats.md#the-seat-brief): `models.py run` on the host's own CLI
  ([manuscript-other-models](../manuscript-other-models/SKILL.md), with `--model` the host's model id), so the
  authors' standing instructions and memory stay out of it; a host subagent only when that cannot run, said
  in the report. Never a fork of this conversation. Launch all seats at once, so that they run in parallel
  (each `run` in the background), and receive every result before merging: as blocking calls, or in the
  background where the host reports each one's completion (a coordinator running other stages meanwhile). Never merge, adjudicate or end the workflow while a seat is still running. Retry a seat that fails to start (for example at a concurrency
  limit). Before merging, check that each seat's `findings.json` exists, parses and ends with its
  `report`; ask a seat that left the report out again (below), and never write one for it.
- **Other models, when chosen, start now.** When the authors asked for more than one model, or the
  project saves `other_models`, start every seat on each chosen model as well, in the same message as
  the host's seats, with [manuscript-other-models](../manuscript-other-models/SKILL.md): each in a fresh
  workspace of its own, from the same brief. This is not optional, and their findings are merged in step 4
  with the others.
- **Asking a seat again.** Only that seat's own agent is asked again, by resuming it, and only for what
  its brief already asked: its report, a coverage line, a missing field, a misquote to correct. The
  message names the step of the brief and adds nothing else (no other seat's output, no finding, no
  hint). When the host cannot resume that agent (it has ended, or it is a seat on another model, whose
  sessions are never resumed), run the seat again as a fresh agent in a new workspace with the same
  brief when what is missing is worth a whole-paper read (a report); its new output replaces the earlier
  one in the merge, and both stay in the run. Otherwise record that the seat gave none ("no
  recommendation", "no coverage line for C3"). Never let another agent or the coordinator fill it in.
- **Fallback.** Only when the host cannot start subagents at all, or a seat still fails after a retry,
  run that seat (or every seat) as a sequential pass: write its criteria first, then one pass from the
  reading copy, without rereading earlier passes until all are done. A stage that was delegated to an agent
  which cannot start agents is not this case: it hands the prepared workspaces back to the coordinator.
  Record `--isolation one-agent`, label those seats "read by one agent in turn, not independent" in the
  output, and never count their agreement as corroboration.

## Step 4: check the finding contract and resolve prior work

Merge the seats' JSON into one file, `$WORK/findings.merged.json`, keeping each finding's `seat` and
putting each seat's `report`, with its `seat`, in `reports`. Every id carries its seat's prefix
([finding-schema.md](references/finding-schema.md#finding-ids); a seat on another model adds its CLI's
letter, `SKX-1`): renumber any that do not, and the ids each recommendation rests on with them. Then run
(from this skill directory):

```bash
uv run --script scripts/check_findings.py "$WORK/findings.merged.json" PAPER.md --supplement SUPPLEMENT.md \
    --criteria SEAT=SEAT_WORKSPACE/criteria.md --venue "$WORK/venue.md" \
    --md "$WORK/check.md" --json "$WORK/check.json"
```

Pass each seat's `criteria.md` with `--criteria SEAT=PATH`, once per seat. The check matches each finding to the criterion
its seat wrote before reading and warns, without holding anything back, on a major finding outside them, a
criterion copied from the manuscript (written after reading) and a criterion with neither a finding nor a line
saying what was checked; ask that seat again for the line (step 3). `--venue` checks that a finding resting on what the
journal expects quotes `venue.md` word for word; a demand for replication, more samples or an external cohort
that says nowhere where its expectation is written is a warning, and adjudication treats it as the referee's
own expectation.

`PAPER.md` stands for the manuscript as Markdown, LaTeX or plain text; a `.tex` source is checked as it
is, with its markup and comments handled ([finding-schema.md](references/finding-schema.md#what-the-script-checks)).
Pass every supplementary file the referees quote, whatever its format: any text file is read (YAML, JSON,
TOML, CSV, BibTeX, HTML, a curation or config file). Only a binary file (a spreadsheet, a Word file, a
PDF) is refused, and the report names it.

Each finding needs a seat, a location, a verbatim quote (or, for something missing, where the seat
looked), the concern, the claim it affects and how (validity, support, scope, reproducibility or
interpretation), a severity, what would change the seat's mind, and a proposed route. A finding that
cannot quote is not a finding. Each report needs a summary and, per journal, a recommendation with its
reason and the seat's own findings it rests on. The script lists failures as "not yet findings";
correct a misquote from the manuscript or ask the seat again (step 3), and never drop one silently.

Then resolve every prior work the findings name, including works the manuscript itself cites with an
identifier. This is the one check this skill runs
([adjudication.md](references/adjudication.md#3-prior-work-claims)): `verified` means the identifier
resolved to the named work; only an identifier that could not be resolved, or a work without one, stays
`unverified`.

## Step 5: adjudicate

Follow [adjudication.md](references/adjudication.md):

1. Apply the claim-consequence gate and, with the prior work resolved in step 4, the fairness filter
   (no "not novel" without a named, resolved prior work; no "run experiment X" unless the claim needs it;
   no "not state of the art" as such).
2. Run the defence pass exactly as
   [adjudication.md, section 5](references/adjudication.md#5-defence-pass) says (what the defender is
   given and what it never sees), and keep the map from the renumbered ids it saw to the originals.
3. Set a verdict with `verdict_evidence` on every finding, and record what the defence returned for it
   as `defence_outcome`. A premise the quoted text does not support is refuted. A partly answered
   finding is narrowed to the part left open (`narrowed`, with the referee's words in
   `original_concern`), then confirmed, or downgraded when that part no longer threatens the claim. A
   refuted finding whose answer sits far from its claim is kept as a misread risk for the writing.
   Agreement between seats is not confirmation.
4. Merge by root cause (the script's groups are a starting point), route each confirmed finding (fixable
   in text, author-required, venue, policy, or dropped with a reason; author-required work is never
   patched), triage it (substance, misread risk, polish), set its severity by the consequence for the
   claim it affects (a sentence about platform support is not major), and set the stage at which the
   authors can act on it ([adjudication.md](references/adjudication.md#8-merging-triage-and-ranking)):
   archive records, release tags and declarations wait until the code is final and are never blockers
   for a draft; a `policy` point, like a point in another check's remit, is listed with the other checks.
5. Read each referee's recommendation against the verdicts
   ([adjudication.md](references/adjudication.md#9-the-referees-recommendations)): when the defence
   refuted or narrowed what it rests on, its report says so in one sentence; the recommendation stays as
   the referee gave it.
6. Write the adjudicated findings, with the `reports`, to `$WORK/findings.adjudicated.json` and rerun
   the step 4 command on it, with the same supplementary files, criteria and `venue.md`, plus
   `--adjudicated`; every reported finding and report must pass.

## Step 6 (optional): robustness check

Offer it when the stakes justify the cost ([options.md](references/options.md)): a meaning-equivalent
rewrite of the sections behind confirmed findings, to separate substance from wording (a changed verdict
marks a misread risk). When the authors chose no other model, the report may also offer seats on another
model for a later run, recorded and never called independent, and only with consent to send the
manuscript to another provider; models already chosen ran from step 3.

## Step 7: give the result

Follow [output-format.md](references/output-format.md). Open with where the paper lands (each
referee's recommendation, per journal), the overall picture, and the journal and panel in plain words
(offering the five-seat panel after a three-seat run).

**Part 1, the referees' reports**, as the journal would send them: the editor's desk screen when one of
its rules stops or risks the draft, then one report per referee in the form referees write: the
recommendation with its reason, a summary of the paper and the referee's view, strengths, major
concerns, minor concerns and questions for the authors. Only concerns confirmed or narrowed in
adjudication appear, in the referee's voice, each quoting the manuscript with its section (a line number
only in parentheses).

**Part 2, what to fix, in order**: the concerns of all the referees merged by root cause, under the
headings of the
[author priorities](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done):
"Fix now: the science and the evidence", "Then the writing", "Once you have chosen the journal", then
"Also found, belongs to other checks" for current points another skill handles, and last "Before
submission, once the code is final", ranked within each by consequence for the claims and then by cost.
Each item says the problem in a sentence, names the referees and concern numbers that raised it, and
ends with what to do: a text fix, or new work with the cheaper alternative of narrowing the claim. When
the authors asked which concerns they can fix in the text and which need new work, open Part 2 with
that split.

Close with "What this review did not have" (supplementary data not supplied, paywalled sources, the
journal's guidelines for reviewers not found, code not run, sequential passes, prior work that could not
be resolved). Write it as
[Writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)
asks: the panel's working vocabulary (seat names, finding and claim ids, verdicts, routes, status
tokens) appears only in parentheses after a plain description. Keep it proportionate: each referee
report about a page, Part 2 a page or two with one item per root cause. The full record of every finding
is available on request, in the same plain form.

**Where the review goes** follows the saved manuscript-project destination. Retain it and all
seat/defence/adjudication outputs in this skill's run folder. Beside the report, write `findings.json`
in the [stage-findings format](../manuscript-dashboard/references/stage-findings.md), one record per root
cause as in Part 2, mapped from the adjudicated findings as the table in
[output-format.md](references/output-format.md#the-stages-findings-for-the-dashboard) says (refuted and
dropped concerns under `dismissed`, the choice between new work and a narrower claim as `decision: true`, what
the review did not have under `not_checked`). Each record's `detail` ends with the ids of the concerns it
merges, in parentheses ("(EV-1, SK-3)"), so that the dashboard links each referee's concern to it; the
referees' reports stay in `findings.adjudicated.json`. The `reports` choice controls chat:
`file` gives links, the journal recommendations and urgent findings; `chat` and `both` show the whole
report too. See [output-format.md](references/output-format.md#saving-and-the-shared-record).

## Hand-offs

- Fixable-in-text concerns go to manuscript-prose-edit with their placement, so the fix lands where it
  costs readers least, and follow the authors' `edits` setting like any correction
  ([author priorities](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)):
  under `apply` (the default) and `conservative`, the fix that a confirmed concern's evidence settles is
  applied and shown before and after, including a claim narrowed by rewording to what its evidence shows;
  under `propose` it is a proposal. A claim is narrowed only on a confirmed concern, and never by deleting
  it. Only the choice between new work and a narrower claim on an author-required concern is the authors'
  decision (`decision: true`), listed once with the other held decisions. A concern about how the paper reads (no stake, no example of output, caveats crowding the results) goes
  to manuscript-story, which also offers a reader panel as the counterpart of these referees.
- Author-required work stays with the authors. Never invent an analysis, result, number or citation to
  close a concern.
- Venue routes go to manuscript-journal-adapt or manuscript-journal-select; policy routes to
  manuscript-policy-fit; reporting gaps to manuscript-reporting-check; citation problems to
  manuscript-reference-check; a figure's legibility, colour or layout to manuscript-figures.
- When `manuscript-record.yaml` exists, add confirmed concerns to `open_issues` and record the review
  under `checks` ([output-format.md](references/output-format.md#saving-and-the-shared-record)).
- When real referee reports arrive, use manuscript-reviewer-response. The simulated concerns stay in
  `open_issues` as the authors' own record; they are never quoted as a referee's words.

## Files

- `scripts/check_findings.py`: verifies quotes, required fields, allowed values, prior-work identifiers,
  quotes of `venue.md` behind a field's expectation, and each referee's report; warns on a finding that bundles
  several problems or asks for what the field expects without saying where it is written; names finding
  ids the dashboard cannot link; groups findings and counts seats; after adjudication, requires what the
  defence returned for each finding, flags recommendations whose findings the defence refuted or
  adjudication narrowed, and sorts each referee's findings into its report's sections; Markdown and JSON
  output; no scores.
- `scripts/workspaces.py`: builds each seat's workspace (the reading copy without comments or revision
  marks, the supplementary files the paper names, the figures as images, `finding-schema.md`, `venue.md`,
  `domain-questions.md`) and fills in its brief from seats.md; builds the defender's workspace with the
  findings stripped of who raised them, and the map back to their ids.
- `references/seats.md`: panel choice by study design, seat remits, the quick pass, the seat brief (with
  `venue.md` and the referee's report).
- `references/finding-schema.md`: the finding fields, the referee's report, the contract and the script's
  checks.
- `references/adjudication.md`: gates, fairness filter, defence pass, verdicts, routes, triage, the
  referees' recommendations.
- `references/output-format.md`: the two-part output for the authors' own draft (the referees' reports,
  then what to fix) and the record update.
- `references/invited-referee.md`: reviewing someone else's paper: the draft referee report and practical
  handling of an unpublished paper and its code.
- `references/options.md`: robustness check, model diversity, a separate panel per journal.
- `references/domains/`: genomics, software and methods, human data and clinical claims, AI systems.
