---
name: manuscript-reviewer-response
description: >-
  Answer real referees and editors, and check that a revision answers them. Plan a revision from a
  decision letter (split the comments into items in the referees' own numbering, record what each asks
  for and the authors' decision on each, and weigh revising against submitting elsewhere), draft a
  point-by-point journal response letter that maps every reply to a location in the revised manuscript
  across review rounds, or a one-shot conference rebuttal, and verify before sending that the revised
  manuscript addresses each comment. Use when a decision letter, referee reports or a draft response
  letter are supplied. Use manuscript-peer-review for a simulated review before submission,
  manuscript-policy-fit for replies to ethics, consent, clinical-scope or privacy comments,
  manuscript-reference-check for new citations, manuscript-reporting-check for requested checklists,
  manuscript-prose-edit for language edits, manuscript-journal-adapt for formatting the revision, and
  manuscript-journal-select when deciding whether to submit elsewhere.
---

# Respond to referees and verify the revision

Help the authors answer the editor and referees so that the paper can be accepted with the least
avoidable work, and so that every reply is true of the revised manuscript. Read the shared
[author priorities](../manuscript-integrity-check/references/author-priorities.md). The authors decide
what to do about each comment, whether to revise or go elsewhere, and what the letter says. A request they
decline is their decision: draft the reply they want, and never list the decline as a blocker or argue for
the work again. A journal policy that bears on the revision gets at most one sentence on its practical
consequence, among the decisions.

Everything the authors read from this skill (the plan, the check's report, the verification report)
follows [Writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors):
each comment quoted under the referee's own number, the manuscript or letter sentence a finding concerns
quoted with its section and any line number in parentheses, plain words, full sentences. The ledger is part
of the task, but its ids, field names and vocabulary, and the check's codes and state words, stay out of what
the authors read (an id may follow a quote in parentheses). A list of open work follows
[Order the work by when it can be done](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done):
the science and evidence the referees asked for first, then the writing, then the journal's format, then
statements and packaging at the end. The response letter itself always keeps the referees' order.

Never fabricate. No reply claims a change, analysis, result, citation, approval or location that is not in
the revised manuscript or the authors' own statement; a missing number is `[TBD: what is missing]`; a
proposed experiment is not a completed one. Never invent, paraphrase or reorder a referee's comment, and
never infer an author decision. Drafting the letter does not send it: submitting, emailing or uploading
needs the authors' go-ahead.

Work across the whole decision letter by default. A request about one comment ("draft a reply to Reviewer
2, point 3") is that comment only. Follow the shared
[workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
for item-by-item review, before/after comparisons and interviews.

## Choose the mode

| The authors have | Mode | Result |
|---|---|---|
| A decision letter or referee reports | **Plan** | The review ledger: atomic items in the referees' numbering, what each asks for, the decisions needed; advice on revising or moving |
| Reviews with no editor and no letter to write (contest feedback, a rejection before another venue) | **Plan only** | The ledger and the decisions, no response letter; the venue choice goes to `manuscript-journal-select` |
| A revised manuscript and decisions | **Draft** | A point-by-point letter, each reply with its location in the revised manuscript, checked by the script |
| A revised manuscript and the comments, with or without a letter | **Verify** | A per-item verdict on whether the revision addresses each comment, regressions, and structural findings |
| A conference review with no revision | **Rebuttal** | A one-shot rebuttal within the venue's limit (draft mode, `mode: rebuttal`) |

Modes chain (plan, revise, draft, verify) but each works alone. A single reply needs no ledger file; a
letter of more than a few items, or any second round, does.

## Plan: from the decision letter to decisions

Read [references/ledger.md](references/ledger.md) before splitting.

1. Read the whole decision letter, the editor's comments first. Note any deadline and any condition the
   editor sets for acceptance.
2. **Split each comment into items wherever a different action would satisfy the referee.** Keep reasons
   with their request, do not split a lead sentence from the points that spell it out, and treat praise
   and summaries as no item unless they contain a factual error about the paper. Items split from one
   sentence each quote their verbatim fragment and share a `sentence` link; a request repeated under
   another heading keeps its own item, linked by `same_as` and decided once.
3. **Keep the referees' numbering and order.** Never renumber, reorder or regroup by theme. Numbering
   within headings keeps the heading initial (`R2.W1`, `R2.S2`, `R2.Q1`); unnumbered comments get labels
   that are visibly the authors' (`R2.P1`, or `R1.W1` under a heading), declared once.
4. For each item record, before any drafting: the verbatim comment, the underlying concern, the commitment
   it asks for, and the evidence that would satisfy it (`new-data`, `new-analysis`, `table`, `figure`,
   `citation`, `methods-text`, `results-text`, `discussion-text`, `statement`, `wording`, `answer`,
   `acknowledge`). Mark the editor's conditions and objections to validity as `must_fix` (with no editor,
   objections to validity only).
5. Show the authors the comments in the referees' order, each quoted (shortened with [...] when long)
   under the referee's own number, with what it asks for, the kind of work it needs and whether it is
   essential, in plain words, and ask for a decision per item: **address** (with the target in the
   manuscript), **decline** (with the authors' reason: design, scope, or the time, cost or capacity they
   name), or **not on point** (with the reason). Then list the decisions needed, grouped by when the work
   could be done. Propose if useful, but leave `decision: undecided` until they answer. Flag conflicting
   requests between referees for the authors to resolve.
6. For requests the authors cannot meet (often new experiments in a computational study), list the honest
   alternatives with what each would cost (a rough estimate, labelled as one): a public-data replication or
   reanalysis, a narrower claim, a scope sentence, verified existing evidence, another venue. An
   in-silico-only budget is a legitimate constraint.
7. **Revise or submit elsewhere.** When a condition of acceptance needs work the authors cannot do, set
   out what each path costs and hand the feasibility facts to `manuscript-journal-select` if moving is a
   real option. No acceptance probabilities.

Write the ledger as `review-ledger.yaml` (the format is in the reference) and check it with the script's
plan form (below). It is a task file: keep it with the authors' revision files whenever another round is possible, since a
later round builds on it; use a scratch location only for a one-off check. Name companion skills in `hand_to`: ethics, consent, clinical scope and
privacy to `manuscript-policy-fit`; requested reporting checklists and availability statements to
`manuscript-reporting-check`; new citations to `manuscript-reference-check`. With no letter to write, stop
here.

## Draft: the response letter

Read [references/drafting.md](references/drafting.md). The manuscript changes come first, made by the
authors or by `manuscript-prose-edit` under its author-supplied content rule; the letter describes changes
that exist.

- One block per ledger item, in order, each with an `<!-- item: ID -->` tag, the referee's comment quoted
  verbatim and complete, then the reply.
- **The first sentence answers**: done, partly done, already in the paper, disagree, or cannot. Then the
  evidence, then the location in the revised manuscript (section, line numbers in the version the journal
  asks for, table or figure). Thanks at most a clause; no default "we agree"; the referee's own terms.
- **Disagreeing**: state the fact in the referee's terms, lead with evidence that would have come out
  differently if the referee were right, concede what is true, and still change the text that invited
  the reading. Address the premise, never the referee.
- **Declined or cannot be done**: the authors' decision, in one sentence with their reason, then what was
  done instead and the matching manuscript change (a narrowed claim, a scope sentence, a public-data
  alternative) where there is one. A bare time, cost or capacity reason reads as a refusal, so offer the
  authors such a change once; whether to make it is theirs. Results of an alternative that has not been run
  are `[TBD]`.
- **Places and links**: name the section first and the lines after it ("Results, 'Performance', lines
  46-48"), never lines alone; give archives, data and code as full URLs (`https://doi.org/...`); refer to
  another reply by referee and comment ("our reply to Reviewer 2, comment 3"); spell out an acronym at first
  use.
- **Later rounds**: quote the new comment, refer back to what the earlier round committed to and where it
  is now, and link the item to its predecessors in the ledger (`previous`).
- Insert the reply text `manuscript-policy-fit` drafts for policy items without adding facts; verify new
  citations with `manuscript-reference-check` before they enter the letter; make language edits under
  `manuscript-prose-edit`'s contract; use `manuscript-journal-adapt` for the revision package and any
  required statements, including an AI-use statement if the venue's policy covers the revision.

Fill `landed` for each commitment, then run the check (commands below) and fix every blocking finding.
Run the smell check on the letter as well (required):
`uv run --script ../manuscript-prose-edit/scripts/style_profile.py RESPONSE.md --report --check`. It skips
the quoted referee comments; fix what it lists in the replies and read them against the pattern list it
prints (sycophancy toward referees is entry G3). Manuscript text you drafted for a reply passes the same
check against the original (`style_profile.py REVISED.md --before ORIGINAL.md --check`).
Return the letter, the check's report (or a summary in its style) and the decisions still waiting for the
authors.

## Verify: does the revision address each comment?

Read [references/verification.md](references/verification.md). The order is the safeguard:

1. **Before reading the revision**, write down per must-fix item (then the others) what fully addressed,
   partially addressed and made worse would look like, from the referee's words. A requirement the comment
   did not state is not part of the criterion. This comes first even when there is no letter.
2. **Judge the revision before reading the letter.** Read the original and revised manuscripts and run
   guard.py's revision mode (see `manuscript-prose-edit`) for every number, citation, identifier and
   claim-strength change. Give each item one state: fully addressed, partially addressed, not addressed,
   made worse, or could not be checked (say which evidence was not supplied), with a quote from the revised
   manuscript and its section. Record new problems as **regressions** (introduced by the
   revision) or **previously missed** (present before; report them, do not escalate them). Before
   reporting, check each verdict's evidence in both versions. Use a fresh subagent without the letter
   for this step when there is a letter and subagents are available.
3. **Then read the letter.** It changes a verdict only by pointing to text that exists in the manuscript
   (for a question, the answer itself). Note every reply that claims something the manuscript does not
   show. With no letter, skip this step and step 4.
4. Run the structural check with the guard inventory and reconcile each unexplained change.

Report the per-item table in the referees' order, then the work that remains (essential items not fully
addressed, regressions, changes no reply accounts for) grouped by when it can be done, then the decisions for
the authors (declined items with their reason and its likely consequence, said once), then what could not
be checked and why. A declined item is the authors' decision, never a failure of the revision. No acceptance
probability or overall score.

## The structural check

Commands are relative to this skill directory. Outputs go to a scratch directory (`$SCRATCH`), not beside
the manuscript:

```bash
uv run --script scripts/check_response.py REVIEWS review-ledger.yaml      # plan: the ledger alone
uv run --script scripts/check_response.py REVIEWS review-ledger.yaml RESPONSE.md \
    --revised REVISED.md --original ORIGINAL.md --md $SCRATCH/check.md --json $SCRATCH/check.json
uv run --script ../manuscript-prose-edit/scripts/guard.py ORIGINAL.md REVISED.md --revision \
    --json $SCRATCH/guard.json
uv run --script scripts/check_response.py ... --guard-json $SCRATCH/guard.json   # changes no reply mentions
uv run --script scripts/check_response.py REVIEWS ledger.yaml rebuttal.md --mode rebuttal --max-chars 5000
```

Without a letter it checks the ledger alone: comments verbatim and in the referees' order, `same_as` and
`sentence` links, a reason for every decline; undecided items are listed, not failed. With a letter it
checks that every ledger item has exactly one reply in the referees' order, under a verbatim quote of its
comment, with no orphan replies; that each reply names a location or says nothing changed; that no blanket
reply ("revised accordingly") or `[TBD]` remains; that every commitment has a landed location in the
ledger; that named and landed locations, quoted revised text and stated numbers exist in the revised
manuscript; and, with `--guard-json`, which changes between the versions sit at locations no reply names.
In the JSON each check is `pass`, `fail` or `not_assessed`, with the reason; reply checks are not assessed
when the letter has no reply blocks. The Markdown report says the same in words and is the one to show the
authors: it quotes each comment under the referee's number, quotes the letter or manuscript text a finding
concerns, and groups the problems by when they can be fixed. Never pass its codes or state words on. Exit
codes: 0 no blocking finding among the checks that ran, 1 a blocking finding (any finding with `--strict`),
2 unreadable or malformed input. Exit 0 when a check could not run is not a clean result: say which checks
did not run.

It checks structure only: it cannot tell whether a reply answers the comment or whether a change is
adequate. A clean run is not a good letter; verify mode is the judgement.

## Shared record

When `manuscript-record.yaml` exists, read the venue, designs and locked claims from it, add one
`open_issues` entry per must-fix item (`from: manuscript-reviewer-response`), and mark it resolved when its
commitments land; the ledger holds the detail. Keep referee names and the decision letter's confidential
parts out of both files.
