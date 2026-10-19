# Verify mode: did the revision address each comment?

Read this when the authors, a co-author or an editor-side reader wants to know whether a revised
manuscript actually answers the referees, before the letter goes out or when a revision comes back. The
response letter is written to persuade, so it is read last and can change a verdict only by pointing to
text that exists.

## Inputs

The decision letter (reviews text), the original manuscript, the revised manuscript, and the response
letter and the ledger if there are any. Supplementary files when the replies point into them. Without the original
manuscript, regressions cannot be told from previously missed problems: say so, and say that those
attributions could not be checked.

## Isolation

The order below matters more than the wording. When subagents are available, run steps 1 and 2 in a fresh
subagent that receives only the reviews, the original and the revised manuscript (and, for step 1, only the
reviews). It must not see the response letter, the ledger's `landed` entries or any author summary of the
revision. Without subagents, finish and write down each step before opening the next input. Model
diversity is optional and never evidence of independence.

**Without a letter** (the authors want to know whether their revision answers the reviews, or the comments
are internal review notes or a blocker list), skip the subagent, step 3 and step 4, but still write the
step 1 criteria before opening the revised manuscript: criteria written after reading the revision drift
toward what it did. Reconcile the guard inventory with the items by hand in step 2, since the script's
reconciliation needs a letter. When a notes file mixes resolved history with the live list, take the part
the request names (usually the live list) and say in one sentence which part you took. Labels you add to
unnumbered notes are visibly the authors' (`E1`, `A1`) and appear in the report only in parentheses after
the quoted note; with no editor, `must_fix` marks objections to validity only.

## Step 1. Criteria, before reading the revision

For each item (must-fix items first; others in lighter form), write down from the referee's own words:

- **fully addressed**: what would be observable in the manuscript if the concern were resolved, for
  example "a comparison with an established annotator on the same genomes, with runtime and agreement
  reported", or "the claim that results did not change is replaced by the measured concordance";
- **partially addressed**: what a genuine but incomplete answer looks like;
- **made worse**: what would make it worse, for example the challenged claim stated more strongly;
- **where it would likely appear**: a guess to navigate by, not a requirement; a fix elsewhere counts;
- **acceptable disagreement**: evidence that would show the concern does not apply. An evidence-backed
  disagreement can count as fully addressed.

Take the criteria from the comment, not from the authors' restatement. If the ledger's `concern` or `asks`
is narrower than the comment, note it. A requirement the comment did not state (a reason for an
exclusion it only asked to list, a format, an extra analysis) is not part of the criterion; mention it as
optional advice if useful. A gap the referee missed is a new issue (step 2), not a moved goalpost.

## Step 2. Evidence, before reading the letter

Read the original and the revised manuscript. Run guard.py's revision mode (see `manuscript-prose-edit`)
for an inventory of what changed, with section and line:

```bash
uv run --script ../manuscript-prose-edit/scripts/guard.py ORIGINAL REVISED --revision \
    --json $SCRATCH/guard.json --md REVISED.changes.md   # the JSON feeds the check; the inventory is for the authors
```

For each item, give one state, with an anchor (a short verbatim quote and its location in the revised
manuscript) and one sentence on what changed against the original:

| State | Meaning |
|---|---|
| `fully addressed` | The revised manuscript meets the criterion, or an evidence-backed disagreement shows the concern does not apply. |
| `partially addressed` | A real change that leaves part of the criterion unmet; name the missing part. |
| `not addressed` | No change in the manuscript that meets any part of the criterion. |
| `made worse` | The revision moved the item away from the criterion: the challenged claim is stronger, the requested information is gone, a new inconsistency touches it. |
| `could not be checked` | The evidence is outside what was supplied (a supplementary file, a figure image, data); say what is missing. Never a pass. |

For items whose evidence type is `answer` or `acknowledge`, the answer itself is the evidence; judge it in
step 3 and say so.

Record new problems found while reading, each with its location, as one of:

- **regression**: introduced by the revision (absent from the original). It can affect the decision.
- **previously missed**: present in the original and unchanged. Report it for the authors, as optional or
  major on its merits, but do not escalate it as a failure of the revision; the referees did not raise it.

Check every changed claim in the guard inventory: a claim that rose on the causal or evidential ladder, a
scope qualifier or null-result marker that disappeared, a new number. Each should be accounted for by an
item (a requested analysis, an authorised claim correction) or it is a candidate regression.

Before freezing, check each verdict's evidence in both versions. Before calling an item `not addressed`,
search the whole revised manuscript for its terms: a new sentence elsewhere can address part of it. Quote
every anchor from the file as printed, not from memory, and look an identifier or number up there before
calling it wrong. File a new problem as previously missed only after finding it in the original; if the
original lacks it, it is a regression. Freeze the states and the new-issue list before step 3.

## Step 3. The letter (skip without one)

Now read the response letter. For each item:

- Does the reply describe what the manuscript shows? A reply that claims a change the manuscript does not
  contain is a finding in its own right, whatever the state.
- The letter can raise a state only by pointing to text that exists in the revised manuscript or the
  supplied supplements (step 2 may have missed it); record the adjustment with its anchor. For an
  `answer` or `acknowledge` item, the reply itself can settle it.
- Evidence that exists only in the letter (an analysis shown to the referee, not added to the paper) can
  support a disagreement, but note that the next reader of the paper will not see it.
- The letter never lowers the bar: "we feel this is outside the scope" without a design or scope reason
  leaves the state where step 2 put it.
- An item the authors declined keeps the state step 2 gave it, and the report lists it among the authors'
  decisions with their reason, not as a failure of the revision.
- Do not add or change new issues after reading the letter; anything noticed only now goes in a separate
  "noticed after the letter" note.

## Step 4. Mechanical checks (skip without a letter)

Run the structural check with the guard inventory:

```bash
uv run --script scripts/check_response.py REVIEWS LEDGER LETTER --revised REVISED --original ORIGINAL \
    --guard-json $SCRATCH/guard.json --md LETTER.check.md
```

It confirms quotes, coverage, order, locations, quoted revised text, numbers and landed commitments, and
lists changes in the guard inventory at locations no reply names. It cannot judge responsiveness; steps
1 to 3 do that.

## Report

Write it for the authors, as
[Writing for the authors](../../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)
asks: quote each comment under the referee's own number (a label you added, such as `E1`, only in
parentheses after the quote), quote the revised text that decides each verdict with its section and any line
number in parentheses, and write each verdict as a sentence. The states are plain words; say "could not be
checked" and why, never a status token.

1. A table in the referees' order: the comment (the referee's number, quoted, shortened with [...] when
   long), whether it is essential, the state, the revised text that decides it with its section, what
   changed, and whether the letter says the same as the manuscript (and if not, how they differ).
2. The work that remains for the comments, with the regressions, grouped by
   [when it can be done](../../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done):
   "Fix now" (essential items not addressed or made worse, regressions in results, numbers or claims, missing
   analyses), "Then the writing" (wording items, claims to reword, replies the manuscript does not bear out),
   "Once you have chosen the journal" (format, length and reporting items), "Before submission, once the code
   is final" (archive DOIs, availability statements, declarations, removing revision markers and TODO
   comments). Give each the smallest change that would meet the criterion; within a group, essential items
   and those that others depend on come first.
3. Previously missed problems, in the same order, each marked as present before the revision.
4. Changes in the guard inventory that no item accounts for, each with its sentence quoted.
5. Decisions for the authors: items they declined, with their reason and its likely consequence said once
   (the referee may raise it again; a declined condition of the editor may cost acceptance), and any
   journal-policy conflict in one sentence. Neither is a failure of the revision.
6. Structural findings from the check, deduplicated against the above, in the words of its Markdown report.
7. What could not be checked, and why.

No acceptance probability, overall score or prediction of the referees' response. When the revision is
about to go back to the journal, essential items that are not addressed, made worse or could not be checked
(other than those the authors declined) mean it is not ready to send: say which and leave the decision to
the authors. When it is still work in progress (internal notes, a draft), the last group of step 2 is not
counted in its readiness.
