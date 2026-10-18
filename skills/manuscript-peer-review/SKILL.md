---
name: manuscript-peer-review
description: >-
  Simulate a panel of journal referees ("Reviewer 2") to red-team the authors' own draft before
  submission: whether the contribution is clear and new, the design answers the question, the results
  support the claims, and which alternative explanations and missing comparisons referees would raise.
  Every concern quotes the manuscript and survives a defence pass before it is reported. Also drafts a
  referee report when the user is reviewing someone else's paper. Use for
  pre-submission red-teaming, simulated or "Reviewer 2" reviews, and desk-editor or methods-reviewer
  passes. Use manuscript-integrity-check for checkable submission problems (references, leftovers,
  declarations, venue rules, numbers), manuscript-reference-check for citations,
  manuscript-reporting-check for reporting guidelines and availability statements,
  manuscript-reviewer-response once real referee reports arrive, and manuscript-policy-fit for ethics,
  privacy and clinical-scope questions.
---

# Simulated peer review

Give the authors the referee judgement they would otherwise meet after submission, while they can still
act on it. Read the shared [author priorities](../manuscript-integrity-check/references/author-priorities.md)
and, when it exists, the
[manuscript record](../manuscript-integrity-check/references/manuscript-record.md).

This is a simulation of what careful referees could raise, not a prediction of the editor's decision.
Never give scores, ratings or an acceptance probability. A decision distribution only when the authors
ask for one, labelled uncalibrated ([options.md](references/options.md)). This skill reports; it never
edits the manuscript.

Apply the review to the whole paper unless the authors name a narrower scope, and follow the shared
[workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review).

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
TODO, a citation's identity) goes in a short "Also found, belongs to other checks" list naming its
skill (or, when it waits for the end, such as a declaration or an archive record, in the end-stage
group), never among the ranked concerns. When a check has not run, say so under "What this review did
not have" and offer it; do not run it here. The one check this skill runs is resolving prior-work
identifiers (step 4).

## Choose the mode

- **Own draft** (default): red-team the authors' manuscript before submission.
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

## Step 2: choose the panel

By default run **three seats plus the defender**, chosen from the study design with
[seats.md](references/seats.md#choosing-the-panel): the design's main seat, the skeptic and the champion.
Add the domain modules whose trigger cues match and whose exclusion cues do not:

- [domains/genomics.md](references/domains/genomics.md)
- [domains/software-and-methods.md](references/domains/software-and-methods.md)
- [domains/human-data-and-clinical.md](references/domains/human-data-and-clinical.md)
- [domains/ai-systems.md](references/domains/ai-systems.md)

Run it without asking, state the panel at the top of the output, and offer the five-seat panel (two more
whole-paper reads). Ask first only when the authors want to choose the panel: then one short message
with the seats, the modules and why, and the cost (each seat reads the whole paper).

## Step 3: run the seats in isolation

- Working files (seat workspaces, the merged findings, the check output) go in a scratch directory
  (`$WORK` below), not beside the manuscript, unless the project already keeps such files.
- Give each seat its own workspace holding only: a reading copy of the manuscript with HTML comments,
  LaTeX comments and revision markers removed, as an editor would see it; the supplementary files; a
  copy of [finding-schema.md](references/finding-schema.md); and the questions of any domain module
  loaded for that seat, as `domain-questions.md` (no other seat sees them). Nothing else: no
  `manuscript-record.yaml`, no other seat's output, no cover letter, earlier reviews, notes or the
  authors' view of their paper. Quotes are still checked against the original, where comments are not
  quotable either.
- Start each seat as a fresh subagent with the seat brief from
  [seats.md](references/seats.md#the-seat-brief), never as a fork of this conversation. Launch all seats
  in one message as blocking (foreground) calls, so that they run in parallel and you receive every
  result (in Claude Code, `run_in_background: false`). Never start them in the background, and never end
  your turn while a seat is running. Retry a seat that fails to start (for example at a concurrency
  limit). Before merging, check that each seat's `findings.json` exists and parses.
- **Fallback.** When the host cannot start subagents, or a seat still fails after a retry, run that seat
  (or every seat) as a sequential pass: write its criteria first, then one pass from the reading copy,
  without rereading earlier passes until all are done. Label those seats "sequential pass by one agent,
  not independent" in the output.

## Step 4: check the finding contract and resolve prior work

Merge the seats' JSON into one file, keeping each finding's `seat`, and run (from this skill directory):

```bash
uv run --script scripts/check_findings.py "$WORK/findings.json" PAPER.md --supplement SUPPLEMENT.md \
    --md "$WORK/check.md" --json "$WORK/check.json"
```

`PAPER.md` stands for the manuscript as Markdown, LaTeX or plain text; a `.tex` source is checked as it
is, with its markup and comments handled ([finding-schema.md](references/finding-schema.md#what-the-script-checks)).

Each finding needs a seat, a location, a verbatim quote (or, for something missing, where the seat
looked), the concern, the claim it affects and how (validity, support, scope, reproducibility or
interpretation), a severity, what would change the seat's mind, and a proposed route. A finding that
cannot quote is not a finding. The script lists failures as "not yet findings"; correct a misquote from
the manuscript or return it to the seat, and never drop one silently.

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
   names and counts. It first tests each finding's premise against its quote, then looks for where the
   paper already answers it.
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
5. Rerun `check_findings.py --adjudicated`; every reported finding must pass.

## Step 6 (optional): robustness and model diversity

Offer these when the stakes justify the cost ([options.md](references/options.md)): a meaning-equivalent
rewrite of the sections behind confirmed findings, to separate substance from wording (a changed verdict
marks a misread risk); seats on other model families, recorded and never called independent, and only
with consent to send the manuscript to another provider.

## Step 7: give the result

Follow [output-format.md](references/output-format.md). When the authors asked which concerns they can
fix in the text and which need new work, open with that split. Then the overall picture, the panel in
plain words (offering the five-seat panel after a three-seat run) and the main strengths with quotes.
Give the confirmed concerns in the order the authors can act on them, under the headings of the
[author priorities](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done):
"Fix now: the science and the evidence", "Then the writing", "Once you have chosen the journal", then
"Also found, belongs to other checks" for current points another skill handles, and last "Before
submission, once the code is final", ranked within each by consequence for the claims and then by cost.
Each concern quotes the manuscript with its section (a line number only in parentheses), says in full
sentences what is wrong and why it matters, and ends with what to do: a text fix, or new work with the
cheaper alternative of narrowing the claim. Close with "What this review did not have" (supplementary
data not supplied, paywalled sources, code not run, sequential passes, prior work that could not be
resolved). Write it as
[Writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)
asks: the panel's working vocabulary (seat names, finding and claim ids, verdicts, routes, status
tokens) appears only in parentheses after a plain description. Keep it proportionate: a page or two, one
concern per root cause. The full record of every finding is available on request, in the same plain
form.

## Hand-offs

- Fixable-in-text concerns go to manuscript-prose-edit only when the authors authorise edits. Narrowing
  a claim is the authors' decision.
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

- `scripts/check_findings.py`: verifies quotes, required fields, allowed values and prior-work
  identifiers; groups findings and counts seats; Markdown and JSON output; no scores.
- `references/seats.md`: panel choice by study design, seat remits, the quick pass, the seat brief.
- `references/finding-schema.md`: the finding fields, the contract and the script's checks.
- `references/adjudication.md`: gates, fairness filter, defence pass, verdicts, routes, triage.
- `references/output-format.md`: the output for the authors' own draft and the record update.
- `references/invited-referee.md`: reviewing someone else's paper: the draft referee report and practical
  handling of an unpublished paper and its code.
- `references/options.md`: robustness check, model diversity, decision distribution.
- `references/domains/`: genomics, software and methods, human data and clinical claims, AI systems.
