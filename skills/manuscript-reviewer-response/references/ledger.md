# Plan mode: splitting a decision letter and keeping the review ledger

Read this when a decision letter, referee reports or a later-round decision arrive, and before drafting
any reply. The ledger is the response plan, not a log: it holds the current state of each comment, one
entry per item, and the authors' decisions. It is the only record this skill keeps.

## 1. Split the comments into items

**Split wherever a different action would satisfy the referee.** Two clauses are one item only when one
action settles both. If they could be done, refused or half-done separately, they are two items. A useful
test: could the referee write next round, about this clause alone, "the authors did not do this"? If so,
it needs its own reply.

Places where an item usually starts:

- a marker the referee wrote: `1.`, `(b)`, `ii)`, a bullet, "First ... Second ...";
- a request aimed at the authors: "should", "must", "please", "I suggest", "it would help to";
- a question, with or without a question mark ("it is unclear whether", "I wonder whether");
- a statement that something in the paper is wrong: it must be confirmed or corrected, or the referee
  keeps a wrong picture of the paper;
- a different target: another figure, panel, table, dataset, cohort, section or line;
- a different kind of evidence (see the vocabulary below): a request for an experiment and a request for a
  sentence of discussion are two items even when one sentence asks for both.

When one sentence holds several items, each item's `comment` is the verbatim fragment it covers, exactly
as written, even when it starts or ends mid-sentence; a fragment is not an ellipsis. All fragments of the
sentence carry `sentence:` with the id of its first fragment.

Do not over-split:

- **Reasons stay with their request.** "The only baseline is outdated, so the authors should add recent
  ones" is one item.
- **A lead sentence that the following points spell out** is not an item of its own. If it raises
  something the points do not cover, it is.
- **A request repeated within one passage** is one item; quote both sentences.
- **A request repeated under another heading or point** (a weakness restated as a suggestion) keeps its
  own item, so every label the referee wrote gets an answer, with `same_as: [first id]`. Use it only when
  one action settles both: the repeat takes the first item's decision and commitments, and its reply
  answers in a sentence and names the same location. A restatement that adds something is its own item.
- **Praise, the referee's summary of the paper and remarks about their own expertise** are not items. A
  factual error inside the summary is.
- **Alternatives the referee offers** ("add a third genome, or limit the claims") are one item: either
  action satisfies it, and the authors choose.
- **A set with one action** ("units are missing in Figs 2c to 2f") is one item with one commitment per
  element, so each element gets its own `landed` entry and the reply names each one, including any that
  needed no change. Elements that need different answers are separate items.
- **The editor's pointers** to referee comments ("in particular Reviewer 1, point 1") mark those items as
  `must_fix`; they are not new items. The editor's own requests are items.

## 2. Keep the referee's numbering and order

- Use the referee's labels in item ids. Never renumber, reorder or regroup by theme; keep gaps and odd
  labels ("4a", "Minor 3") as written. Nested points take the referee's own markers: point 6 with
  sub-points 1) to 3) becomes `R1.6.1` to `R1.6.3`.
- When the referee numbers within headings ("Weaknesses 1", "Suggestions 2", "Questions 1"), the id is
  the heading initial plus their number (`R2.W1`, `R2.S2`, `R2.Q1`), with the marker as written in
  `label`.
- When the referee numbered nothing, split at their paragraphs, in order, and use labels that are visibly
  the authors' (`R2.P1`, `R2.P2`; under the referee's headings, the heading initial: `R1.W1`, `R1.S1`).
  Parts of one paragraph or numbered point that the authors split get letters (`R2.P2a`, `R1.3b`,
  `R3.W1a`), also marked as the authors'. One scheme per referee; say once, in the letter or the plan,
  which labels the authors added.
- The ledger lists items in the order they appear in the decision letter, usually the editor first, then
  each referee in the journal's order. `check_response.py` checks that order against the reviews text.
- Name referees as the journal does ("Reviewer 1", "Referee #2"). If a referee signed the report, keep the
  name out of the ledger and the shared record.

## 3. Record each item

Fill `concern` and `asks` before drafting anything, and do not edit them afterwards to fit the reply. If a
reply no longer matches its `concern`, change the reply or reopen the decision, not the concern: a
softened restatement is how a reply ends up answering a different question.

| Field | What it holds |
|---|---|
| `id` | The item key used in the letter's tags, e.g. `R1.2`, `Ed.P1`, `R2.P3b`. |
| `referee` | As the journal names them. |
| `label` | The referee's own marker, verbatim (`"2"`, `4b`), or `null` when the authors added the label. |
| `comment` | The referee's words for this item, verbatim, copied from the reviews text. No ellipsis, no corrections. |
| `concern` | One line: what the referee is worried about underneath the request. |
| `asks` | The commitment the referee asks for, in one line. |
| `evidence` | The evidence that would satisfy it, from the vocabulary below; list several when needed. |
| `must_fix` | `true` for the editor's conditions, items the editor singles out, and objections to validity, controls, statistics or a central claim (with no editor, these objections only). The authors may add others. Verify mode writes criteria for these first. |
| `decision` | The authors' decision: `address`, `decline`, `not-on-point`, or `undecided`. |
| `reason` | Required for `decline` and `not-on-point`: the reason as the authors give it (design, scope, data access, a regulatory or ethical limit, time, cost or capacity), or why the comment does not apply. |
| `hand_to` | The companion skill that drafts part of the answer, by name (see SKILL.md). Older ledgers call it `route`; the check reads both. |
| `same_as` | The earlier item this one repeats, e.g. `[R2.W1]`; it takes that item's decision and commitments. |
| `sentence` | For a fragment of one referee sentence: the id of the sentence's first fragment. |
| `commitments` | What will change: `change`, `target` (where it should go) and `landed` (where it went). |
| `previous` | From round 2 on: the earlier items this one follows up, as `ROUND:ID`, e.g. `1:R2.P1`. |

Evidence vocabulary:

| Value | Meaning |
|---|---|
| `new-data` | A new experiment, measurement or data collection (wet lab, new cohort, new sequencing). |
| `new-analysis` | New computation on existing or public data, including a public-data replication. |
| `table`, `figure` | A new or changed display item. |
| `citation` | A new or replaced reference. |
| `methods-text`, `results-text`, `discussion-text` | New or changed text in that section. |
| `statement` | A declaration: data, code or software availability, ethics, consent, funding, competing interests. |
| `wording` | A local wording change anywhere, including a narrowed claim. |
| `answer` | A factual answer in the letter, for a question whose answer the manuscript already gives or that concerns the process. |
| `acknowledge` | Nothing to change beyond noting the point. Use sparingly; most comments that look like this deserve a manuscript change. |

`landed` values: empty or `promised` (or `pending`) means the change is not in the manuscript yet;
otherwise give the location in the revised manuscript in the same form the letter uses, e.g.
`'Results, "Performance", lines 46-48; Table 1'`. In journal mode, `check_response.py` blocks while any
commitment has not landed and checks that each landed location exists; run without a letter (plan mode),
it checks the ledger alone and expects nothing to have landed yet. In a one-shot conference rebuttal
(`mode: rebuttal`), `promised` is allowed and is reported for the authors to state as a promise.

## 4. The authors decide

Present the items to the authors in a compact table (id, the ask in one line, evidence type, must-fix,
proposed handling) and ask for a decision per item:

- **address**, with the target in the manuscript;
- **decline**, with the reason as the authors give it (design, scope, data access, a regulatory or
  ethical limit, or time, cost or capacity), and what was done instead if anything. Record the real
  reason; in the letter, a time, cost or capacity reason is never the whole answer and comes paired with
  what was done instead (a narrowed claim, a scope sentence, a public-data alternative);
- **not on point**, with the reason (the comment rests on a misreading the text should prevent, or
  concerns another paper).

You may propose a decision with its rationale, but the `decision` field stays `undecided` until the
authors confirm it. Never infer a decision from silence, from the ledger's earlier state or from what is
easiest. When two referees ask for incompatible things, show both and let the authors choose; the letter
then explains the choice to both. A "not on point" decision usually still earns a manuscript change: the
text that allowed the misreading.

An in-silico-only budget is a legitimate constraint. For a request that needs `new-data` the authors
cannot produce, list the honest options with their cost: a public-data replication or reanalysis, a
narrower claim, a scope sentence where the gap sets what a result means, citing existing experimental
evidence (verified), or a different venue. Never present a proposed experiment as one that will be done
unless the authors commit to it.

## 5. Revise or submit elsewhere

Help the authors decide after the items and decisions are clear; this is their call. Lay out:

- which items the editor made conditions of acceptance, and whether any of them needs work the authors
  cannot do;
- the must-fix items by evidence type, separating text and reanalysis from new data;
- whether a narrower claim would honestly meet a condition, and whether the editor is likely to accept
  that (an enquiry to the editor before revising is an option for a condition that cannot be met as
  written);
- the deadline in the decision letter;
- what moving costs: reformatting, a new review, and the same substantive points from new referees. The
  ledger carries over as a revision plan either way.

With no editor and no letter to write (contest feedback, or a rejection the authors will revise for
another venue), the plan ends here: the ledger and decisions are the result, no letter is drafted, and the
venue choice goes to `manuscript-journal-select`.

When moving is a real option, hand the facts to `manuscript-journal-select`: the feasibility constraint
(for example "no wet lab; public-data reanalysis is possible"), the article type and the authors'
priorities. Never give an acceptance probability or a score for either path. A transfer or cascade offer
in the decision letter is one more option, with its own scope to check.

## 6. Rounds

The ledger is append-only. A new round adds a `rounds:` entry with its own items; earlier items change
only in `commitments[].landed` and in the optional `status`.

- Before planning round N, list every earlier item whose commitments have not all landed, and every
  earlier item the referee raises again. Each must reappear in round N, linked with `previous`.
- A round-N comment that refers back ("my previous concern about the split") is linked by matching the
  referee's words against the earlier `comment` fields. If nothing matches, the earlier ledger missed an
  item: add it to the earlier round, marked as added late, rather than inventing a link.
- One round-N sentence can follow up several earlier items; list them all in `previous`.
- Journals may add or replace referees between rounds; "Reviewer 3" in round 2 is not necessarily the
  same person as in round 1. Record what the journal says.
- `status` (optional) is `open`, `answered`, `reopened` or `closed`. Only a referee or the editor closes an
  item. "The authors have addressed my comments" closes that referee's answered items; an item that was
  never answered is not closed by a blanket sentence, so flag it.
- A referee who is satisfied needs no reply unless the journal expects one; a one-line acknowledgement is
  enough.

## 7. Example

```yaml
# review-ledger.yaml: a task file kept with the revision files while another round is possible; never sent
manuscript: paper.md
mode: journal                      # journal | rebuttal
rounds:
  - round: 1
    decision: major revision
    reviews: reviews-r1.txt         # the decision letter as received
    original: paper-v1.md
    revised: paper-v2.md
    line_numbers: file lines of paper-v2.md
    plan: revise                    # revise | submit-elsewhere | undecided (the authors' call)
    items:
      - id: R1.2
        referee: Reviewer 1
        label: "2"
        comment: Table 1 reports medians of 3 runs. Please report the spread across runs as well.
        concern: A median of three runs hides how stable the runtime is.
        asks: The spread across runs for each genome.
        evidence: [table, results-text]
        must_fix: false
        decision: address
        commitments:
          - change: Range across the 3 runs in Table 1 and the Performance paragraph
            target: Results, Performance; Table 1
            landed: 'Results, "Performance", lines 46-48; Table 1'
  - round: 2
    decision: minor revision
    reviews: reviews-r2.txt
    items:
      - id: R2.P1
        referee: Reviewer 2
        label: null
        comment: Please add a genome from a third individual, sequenced on any platform, or limit the claims
          about generalisability in the Abstract and Discussion.
        previous: ["1:R2.P1"]
        decision: undecided
```

Splits and repeats, for a referee who numbers within headings:

```yaml
      - id: R2.S2a                 # "2) Add a genome from another platform, and compare it with VEP."
        label: Suggestions 2
        sentence: R2.S2a
        comment: Add a genome from another platform,
      - id: R2.S2b
        label: Suggestions 2
        sentence: R2.S2a
        comment: and compare it with VEP.
      - id: R2.S3                  # restates Weakness 1; one action settles both
        label: Suggestions 3
        same_as: [R2.W1]
        comment: Please test more than two genomes.
```

A full worked ledger for a two-referee decision letter is in the evaluation fixtures
(`evals/fixtures/manuscript-reviewer-response/review-ledger.yaml` in the plugin repository).

## 8. The shared record

When `manuscript-record.yaml` exists (see
`../../manuscript-integrity-check/references/manuscript-record.md`), read the venue, study designs and
claims from it. Add one `open_issues` entry per must-fix item, with `from: manuscript-reviewer-response`,
the location, a one-line summary, the record's `route` category (`fixable-in-text`,
`author-required` for new data or decisions, `venue`, `policy`) and `status: open`; mark it `resolved`
when its commitments land, and `waived` only when the authors decline it. Point to the ledger rather than
copying it. Do not create the record for a single response letter.
