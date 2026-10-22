---
name: manuscript-peer-review
description: >-
  Simulate journal referee reports on an author's draft, with independent referees, manuscript
  quotations, a defence pass and an ordered revision list. Use for pre-submission red-teaming,
  Reviewer 2, desk-editor or methods-reviewer passes, or drafting a report when the user is an
  invited referee. The full panel has three referees plus a defender; a requested quick pass uses
  two seats. Keep simulated reports separate from real editorial reviews. Use manuscript-reviewer-
  response for responding to real referees and manuscript-integrity-check for mechanical submission
  checks.
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

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run. This applies to direct invocations too.

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

When `manuscript-record.yaml` lists one of these as a current check (same manuscript sha256, or the
changed sections lie outside its scope), or its findings are in the conversation, cite its result where a
referee would raise the same point, and say why where the panel judges it differently. Whether the
results support the claims stays referee judgement, with integrity's Step 5 as its starting point. A
confirmed point in another check's remit (a number that disagrees, a missing statement or archive, a
TODO, a citation's identity) goes in Part 2 of the result, in a short "Also found, belongs to other
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
   rungs**;
4. otherwise a generic journal in the paper's field, for the article type the manuscript reads as. Say
   so at the top of the result and offer to rerun for a named journal or for the top of a ladder from
   manuscript-journal-select.

For each journal, write the referees' `venue.md` (one file; one section per journal). Take its facts from
`../manuscript-journal-adapt/scripts/venues.py show KEY`: the journal's name and the article type, its
fields and article types, its editorial profile, the rules its editors check on arrival, its validation
and software requirements, and its length limits. Add what the journal asks its referees when its
guidelines for reviewers can be read (a page among the entry's `sources`, or the publisher's guidelines
for reviewers): the questions on its form and its recommendation options, quoted. For a journal not in
the catalogue, read its author guidelines and guidelines for reviewers. Leave out the authors'
priorities and why they chose or ranked the journal. Record what each brief was read from and when; the
result says so, or that the guidelines for reviewers could not be found.

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
  LaTeX comments and revision markers removed, as an editor would see it; the supplementary files; a
  copy of [finding-schema.md](references/finding-schema.md); `venue.md` from step 2; and the questions
  of any domain module loaded for that seat, as `domain-questions.md` (no other seat sees them). Nothing else: no
  `manuscript-record.yaml`, no other seat's output, no cover letter, earlier reviews, notes or the
  authors' view of their paper. Quotes are still checked against the original, where comments are not
  quotable either.
- **Independence is required**, as [Independent readers and referees](../manuscript-integrity-check/references/project-workflow.md#independent-readers-and-referees) sets out: a fresh agent
  per seat whose whole context is its brief, started by the session that can start agents (in
  manuscript-improve, the coordinator itself), the brief filled from the template and nothing else, and
  `--isolation` recorded for every seat and the defender.
- Start each seat as a fresh subagent with the seat brief from
  [seats.md](references/seats.md#the-seat-brief), never as a fork of this conversation. Launch all seats
  in one message, so that they run in parallel, and receive every result before merging: as blocking
  calls, or in the background where the host reports each agent's completion (a coordinator running other
  stages meanwhile). Never merge, adjudicate or end the workflow while a seat is still running. Retry a seat that fails to start (for example at a concurrency
  limit). Before merging, check that each seat's `findings.json` exists, parses and ends with its
  `report`; ask a seat that left the report out to add it, and never write one for it.
- **Fallback.** Only when the host cannot start subagents at all, or a seat still fails after a retry,
  run that seat (or every seat) as a sequential pass: write its criteria first, then one pass from the
  reading copy, without rereading earlier passes until all are done. A stage that was delegated to an agent
  which cannot start agents is not this case: it hands the prepared workspaces back to the coordinator.
  Record `--isolation one-agent`, label those seats "read by one agent in turn, not independent" in the
  output, and never count their agreement as corroboration.

## Step 4: check the finding contract and resolve prior work

Merge the seats' JSON into one file, keeping each finding's `seat` and putting each seat's `report`,
with its `seat`, in `reports`, and run (from this skill directory):

```bash
uv run --script scripts/check_findings.py "$WORK/findings.json" PAPER.md --supplement SUPPLEMENT.md \
    --md "$WORK/check.md" --json "$WORK/check.json"
```

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
correct a misquote from the manuscript or return it to the seat, and never drop one silently.

Then resolve every prior work the findings name, including works the manuscript itself cites with an
identifier. This is the one check this skill runs
([adjudication.md](references/adjudication.md#4-prior-work-claims)): `verified` means the identifier
resolved to the named work; only an identifier that could not be resolved, or a work without one, stays
`unverified`.

## Step 5: adjudicate

Follow [adjudication.md](references/adjudication.md):

1. Apply the claim-consequence gate and the fairness filter (no "not novel" without a named, resolved
   prior work; no "run experiment X" unless the claim needs it; no "not state of the art" as such).
2. Run a defence pass: a fresh blocking subagent with the reading copy and the findings, stripped of seat
   names and counts, and without the referees' reports or `venue.md`. It first tests each finding's
   premise against its quote, then looks for where the paper already answers it.
3. Set a verdict with `verdict_evidence` on every finding. A premise the quoted text does not support is
   refuted. A partly answered finding is narrowed to the part left open, then confirmed, or downgraded
   when that part no longer threatens the claim. Agreement between seats is not confirmation.
4. Merge by root cause (the script's groups are a starting point), route each confirmed finding (fixable
   in text, author-required, venue, policy, or dropped with a reason; author-required work is never
   patched), triage it (substance, misread risk, polish), set its severity by the consequence for the
   claim it affects (a sentence about platform support is not major), and set the stage at which the
   authors can act on it ([adjudication.md](references/adjudication.md#8-merging-triage-and-ranking)):
   archive records, release tags and declarations wait until the code is final and are never blockers
   for a draft.
5. Read each referee's recommendation against the verdicts
   ([adjudication.md](references/adjudication.md#9-the-referees-recommendations)): when the defence
   refuted or narrowed what it rests on, its report says so in one sentence; the recommendation stays as
   the referee gave it.
6. Rerun `check_findings.py --adjudicated`; every reported finding and report must pass.

## Step 6 (optional): robustness and model diversity

Offer these when the stakes justify the cost ([options.md](references/options.md)): a meaning-equivalent
rewrite of the sections behind confirmed findings, to separate substance from wording (a changed verdict
marks a misread risk); seats on other model families, recorded and never called independent, and only
with consent to send the manuscript to another provider.

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
seat/defence/adjudication outputs in this skill's run folder. The `reports` choice controls chat:
`file` gives links, the journal recommendations and urgent findings; `chat` and `both` show the whole
report too. See [output-format.md](references/output-format.md#saving-and-the-shared-record).

## Hand-offs

- Fixable-in-text concerns go to manuscript-prose-edit only when the authors authorise edits, each with
  its placement, so the fix lands where it costs readers least. Narrowing a claim is the authors' decision.
  A concern about how the paper reads (no stake, no example of output, caveats crowding the results) goes
  to manuscript-story, which also offers a reader panel as the counterpart of these referees.
- Author-required work stays with the authors. Never invent an analysis, result, number or citation to
  close a concern.
- Venue routes go to manuscript-journal-adapt or manuscript-journal-select; policy routes to
  manuscript-policy-fit; reporting gaps to manuscript-reporting-check; citation problems to
  manuscript-reference-check.
- When `manuscript-record.yaml` exists, add confirmed concerns to `open_issues` and record the review
  under `checks` ([output-format.md](references/output-format.md#saving-and-the-shared-record)).
- When real referee reports arrive, use manuscript-reviewer-response. The simulated concerns stay in
  `open_issues` as the authors' own record; they are never quoted as a referee's words.

## Files

- `scripts/check_findings.py`: verifies quotes, required fields, allowed values, prior-work identifiers
  and each referee's report; groups findings and counts seats; after adjudication, flags recommendations
  whose findings the defence refuted or narrowed and sorts each referee's findings into its report's
  sections; Markdown and JSON output; no scores.
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
