# Adjudication

Nothing a seat writes reaches the authors until it has been checked against the paper. Adjudication
turns findings that meet the contract into confirmed, refuted or downgraded concerns, routes the
confirmed ones and triages them. Do it in this order.

## 1. Contract

Run `scripts/check_findings.py` on the merged findings. For each "not yet finding":

- a misquote whose concern stands: correct the quote from the manuscript (the script reports the
  longest opening run it found) and recheck;
- an unchecked prior-work claim: resolve the identifier (section 4);
- a missing field: ask the seat, or fill it from the seat's own text when it is unambiguous;
- anything else: it stays listed as not yet a finding, with the reason. Never drop it silently.

## 2. Claim-consequence gate

Keep a finding only if resolving it could change the **validity, support, scope, reproducibility or
interpretation** of a claim, and the finding names that claim. Map each finding to the claim map from
step 1 of SKILL.md (or the record's claim ids).

Drop, with the reason "no claim consequence", concerns whose only effect is length, section order,
figure style, grammar or prose. Keep a wording or labelling problem only when it creates a
scientifically consequential ambiguity: an undefined unit, a missing denominator, a cohort or variable
label used two ways, a build or version left unstated where it changes a result.

## 3. Fairness filter

These are not referee concerns as stated. Drop them with the reason, or rewrite them into a concern
that passes the gate:

- "Not novel" or "already done" without a named prior work whose identifier was resolved (section 4),
  or marked `unverified`, which the report then says in words ("its identifier could not be resolved").
- "Not state of the art" when the paper does not claim superiority. A paper that claims to be better
  must show it against the obvious comparators; one that claims to be cheaper, faster or more
  transparent must show that instead.
- "Run experiment X" when no claim depends on X. When a claim does need it, always give the cheaper
  alternative of narrowing the claim, and let the authors choose.
- "Too simple" or "incremental". Simplicity is a defect only when a claim depends on more.
- "The authors should have studied a different question", a different organism, population or dataset,
  unless the paper's claims extend to it.
- A stated limitation treated as a defect. It is a concern only when it undermines a claim the paper
  still makes.
- "Better suited to another venue". That is a venue route, not a scientific concern.
- Comparisons with work published after the manuscript was written, or with preprints the authors could
  not reasonably have known, presented as omissions.
- Any suggestion of misconduct, fabrication or AI authorship. That is never a referee finding here;
  checkable integrity problems belong to manuscript-integrity-check.

## 4. Prior-work claims

Resolving prior-work identifiers is the one check this skill runs. Resolve every work a finding names,
including works the manuscript itself cites with an identifier: reuse a current
manuscript-reference-check result for that reference, or put just those works in a standalone `.bib`
and run `../manuscript-integrity-check/scripts/scan.py --references-only --online`. A work's identity is `verified`
when its identifier resolved to the named work, and `unverified` only when the identifier could not be
resolved or the work has none. Never fill an identifier from memory. An `unverified` prior-work concern
can still be confirmed on other grounds, but the report says the work was not resolved. Whether a
resolved work does what the seat says is manuscript-reference-check's question
([claim-support.md](../../manuscript-reference-check/references/claim-support.md#requests-from-other-skills));
priority words in the paper ("first", "novel", "only") are judged as that file's
[traps](../../manuscript-reference-check/references/claim-support.md#priority-and-absence-claims) say.

## 5. Defence pass

Start one fresh subagent, the defender, as a blocking call like the seats, with the reading copy, the
supplementary files and the findings stripped of seat names (renumber ids that name a seat), group
counts and severities, so that numbers cannot sway it. For each finding it first tests the premise:
does the quoted text say what the concern says it says, and is every other statement the concern makes
about the paper true? (A concern that asks to qualify a claim in the Abstract assumes the Abstract makes
that claim.) Then it looks for text that already answers the finding: a method detail elsewhere, a
supplementary note, a stated limitation, a non-claim, a figure legend. It returns, per finding, one of:

- **premise not supported**, with what the quote or the section it describes actually says;
- **answered**, with the verbatim answering text (`defence_quote`) and its location;
- **partly answered**, with the answering text and the part that remains open, stated as a concern of
  its own;
- **not answered**, with where it looked.

Without subagents, do the defence pass yourself after all seat passes, and label it as such.

## 6. Verdicts

Set one verdict per finding, each with `verdict_evidence`:

- **refuted**: the paper answers it, or its premise fails against its own quote or the text it describes.
  Cite the answering text in `defence_quote` (for a failed premise, the finding's own quote or the
  passage that shows the premise wrong) and say which in `verdict_evidence`. A refutation from
  recollection is not a refutation.
- **confirmed**: the premise holds, the quote is there, the concern follows from it, and the defence
  found no answer. `verdict_evidence` gives the text or recomputation that shows the problem and where
  the defence looked.
- **downgraded**: real, but narrower or less severe than raised. Say which.

A **partly answered** finding is never confirmed as raised. Narrow it to the part the defence left open
(rewrite `concern` and `change_my_mind` to that part; the full record keeps the original) and confirm
that part when it still threatens the claim, or downgrade it when it no longer does. Its
`verdict_evidence` names the answering text and the open part. When nearly every finding comes back
partly answered, check that the defender tested each premise and that each open part is a real gap, not
the concern restated.

Agreement between seats is not confirmation: seats share a model and its blind spots, and several can
make the same misreading. Confirmation comes from the text, from recomputing a number from the paper's
own tables, or from a checked external record. The number of seats is reported for information only.

A refuted finding can still be useful. If a careful reader missed the answer, so may a referee: the
answer is usually too far from the claim it qualifies. Record it as a **misread risk** whose fix is to
bring the qualifier next to the claim.

## 7. Routes

Each confirmed or downgraded finding gets one route:

| Route | Meaning | Who takes it |
|---|---|---|
| `fixable-in-text` | Wording, a missing detail the authors already have, or a claim narrowed to its evidence | the authors; manuscript-prose-edit only when the authors authorise edits. Narrowing a claim is the authors' decision, never applied silently. |
| `author-required` | Needs new analysis, data, experiments or runs | the authors. Never patched, never simulated, never filled with invented numbers. |
| `venue` | Fit, article type, length or a venue-required item | manuscript-journal-select or manuscript-journal-adapt |
| `policy` | Ethics, consent, privacy, clinical scope | manuscript-policy-fit |
| `dropped` | Failed the gate, the fairness filter or the defence | nobody; `drop_reason` says why |

Use `hand_to` for the skill when it is not obvious, for example manuscript-reporting-check for a
reporting-guideline gap or manuscript-reference-check for a citation that does not support its
sentence. A confirmed finding in another check's remit (the table in SKILL.md: a number that disagrees,
an availability statement, a missing declaration, a TODO) keeps its route, takes that skill as `hand_to`
and is listed under "Also found, belongs to other checks" in the output, not ranked as a referee
concern; one that waits until the code is final (stage `final`, section 8) is listed in the end-stage
group instead.
Where that check's recorded result judged the same point, agree with it or say why the panel differs.

## 8. Merging, triage and ranking

Merge by root cause. The script's groups (overlapping quotes, shared labels, near-identical wording) are
a starting point: findings about one underlying problem at different locations become one concern that
lists every location.

- **substance**: the work as done does not support the claim as stated.
- **misread risk**: the work is sound, but its wording will trigger a referee (an unqualified priority
  claim, a qualifier far from its claim, a term used two ways, causal phrasing for an association that
  the analysis treats correctly).
- **polish**: everything else that passed the gate.

Set severity by the consequence for the claim, not by the seat's proposal: `major` when the validity or
support of a headline claim is at stake. A line of an availability statement (a platform list, a missing
version number) is `optional` unless a headline claim depends on it.

Set `stage`, when the authors can act on the concern, as "Order the work by when it can be done" in the
[author priorities](../../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done)
describes:

- `now`: the science and the evidence, including new analysis a claim needs (the default for substance);
- `writing`: a misread risk or polish (the default for those triage classes);
- `journal`: depends on the chosen venue (the default for the `venue` route);
- `final`: waits until the code, data and results are final: an archive record or release tag, version
  numbers quoted in the text, the final availability statement, declarations, the AI-use statement.
  A `final` concern is never a blocker for a draft, whatever the seat proposed, unless the authors say
  they are about to submit.

`check_findings.py --adjudicated` applies those defaults when `stage` is absent and sorts its groups by
stage. Within a stage, rank confirmed concerns by consequence first: a threat to a headline claim before
a secondary one, validity and support before scope and interpretation. Then by cost: `text` before
`reanalysis` before `new-data`, and an item that depends on another after it. State the cost in plain
terms ("a sentence", "rerun the benchmark on a gene-disjoint split", "a replication cohort").

The field names and values in this file (verdicts, routes, triage classes, stages, `verified` and
`unverified`) are the panel's working vocabulary. The report says what they mean in words
([output-format.md](output-format.md#content-rules)).

## 9. Recheck

Run `check_findings.py --adjudicated` on the final set. Every finding in the report must pass it.

## Design sources

The design follows ideas surveyed in `docs/skill-landscape-2026-10.md`: the verbatim-quote gate and
verdict routing (Spark-To-Paper-Skills/paperjury, pedrohcgs/claude-code-my-workflow), the
claim-consequence gate (poldrack/ai-peer-review), the triage classes and fairness rules
(xf686/Meet-Reviewer-2), "What this review did not have" and unverified prior work
(amirkiarafiei/open-scholar-peer), and criteria written before reading (Imbad0202/academic-research-skills,
ideas only). No text or code was copied from any of them.
