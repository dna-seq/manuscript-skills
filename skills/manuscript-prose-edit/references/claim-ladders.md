# Claim ladders: how strong a sentence's claim is

An edit may change how a claim is worded, never how strong it is. These ladders give the rungs that
`scripts/guard.py` checks sentence by sentence, and the vocabulary a critic or editor uses to name a change
("association → causation", "scope lost: in mice"). The rungs are deliberately general so that other skills can
share them: the overclaiming checks in `../../manuscript-integrity-check/references/claim-evidence.md` use a
matching ladder, and `manuscript-peer-review` and `manuscript-reviewer-response` describe a claim's strength in
the same words. Field conventions can reorder neighbouring rungs; the direction of a move is what matters.

## The two ladders

**Causal force** (what relation the sentence asserts), weakest first:

| Rung | Name | Typical wording |
|---|---|---|
| 0 | compatibility | is consistent with, is compatible with, in line with |
| 1 | association | is associated with, correlates with, is linked to, co-occurs with, is enriched in |
| 2 | prediction | predicts, is predictive of, predictor of, is prognostic for |
| 3 | contribution | contributes to, plays a role in, is involved in, modulates, influences |
| 4 | effect | affects, leads to, results in, induces, promotes, inhibits, prevents, increases the risk of |
| 5 | causation | causes, drives, determines, is responsible for, underlies, mediates |

A sentence with none of these words states a plain relation ("X reduces Y") and counts as rung 4.

**Evidential force** (how certain the sentence is), weakest first:

| Rung | Name | Typical wording |
|---|---|---|
| 0 | possibility | may, might, could, possibly, potentially, likely, appears to, we hypothesise |
| 1 | suggestion | suggests, hints at, points to |
| 2 | indication | indicates, supports the hypothesis, provides evidence for |
| 3 | demonstration | shows, demonstrates, reveals, we found that |
| 4 | proof | proves, establishes, confirms, conclusively, unequivocally, clearly, certainly |

A sentence with none of these words is a plain assertion and counts as rung 3. "Figure 2 shows the layout"
describes a figure and is not a claim; "Figure 2 shows that X" is. "Established a pipeline" and "confirmed
the configuration" are procedures, not proof.

The guard compares the weakest and the strongest rung present in each aligned sentence (including the plain
rung). Strength **rose** when either moved up, **fell** when either moved down, and is **mixed** when one rose
and the other fell. So "may suggest" → "suggests" rose (the hedge went), "suggests that X may" → "X may" did not
change, and "is associated with Y and causes Z" → "is associated with Y and Z" fell.

## Other markers that carry a claim

- **Novelty and generality**: for the first time, the first tool, novel, unprecedented, state-of-the-art;
  always, invariably, universally, in all patients, regardless of, generalisable, broadly applicable. Adding one
  raises the claim. ("Novel" is a field term for a variant not seen before; it is reported only when it changes.)
- **Scope qualifiers**, grouped so that a synonym inside one group is not a change: this study's data and
  setting (in this cohort, in our data, among these participants); conditions (under these conditions, at the
  tested doses); ancestry (European-ancestry samples, of East Asian descent); subsets (in some cohorts, in a
  subgroup); model systems (in mice, in cell lines, in vitro, in vivo, in silico); people (in patients, in
  older adults); data type (on simulated data, in the training set, internally validated). A qualifier that
  disappears lets a claim read as more general than its data. "In this study, we show" → "We show" keeps the
  study as the scope and is not reported.
- **Limiting and concessive words**: only, merely, solely, as few as, just (with a count), limited or restricted
  to; albeit, although, though, even though, even if, despite, in spite of, notwithstanding, and a clause-initial
  while or whilst. They mark a result as resting on little evidence or holding despite a limit ("Albeit tested on
  four genomes, the benchmarks show ..."). A sentence that keeps its claim but loses the word reads as broader
  than the authors wrote. One word in the group standing for another is not a change, and neither is a
  contrastive connector (however, but, yet, whereas) that carries the concession after a restructure ("Although
  X, Y" → "X. However, Y"). "Not only", "the only" and a mid-sentence "while" are not limits.
- **Null results**: no significant, not significant, did not differ, was not associated, no difference, failed
  to replicate, remained unchanged, p > 0.05. Rewording one as another is not a change; losing one is.
  "Not associated" → "independent of" is reported: absence of evidence has become evidence of absence.
- **Evidence status**, how a finding was obtained: self-reported, reported, perceived, predicted, putative or
  candidate, estimated (imputed, inferred, modelled, simulated), observed (measured, detected, validated).
  "Participants reported improvement" → "participants improved" loses the status; "reported" → "observed"
  replaces it. "We report" and "reported in Table 2" are not statuses.

Distinctions an edit keeps even when no marker word changes: observed result, the authors' interpretation and
prior literature; statistical and practical significance; exploratory and confirmatory analysis; internal and
external validation; a sample-specific observation and a population-level statement.

## What each change means for an edit

| Change | In a copy edit (`guard.py`) | In a revision (`guard.py --revision`) |
|---|---|---|
| Rose on a ladder, mixed, or novelty/generality added | protected: exit 1 | listed |
| A scope, null-result or evidence-status marker lost | protected: exit 1 | listed |
| A limiting or concessive word lost | protected when its sentence survives; a warning when the sentence was deleted or its claim narrowed in the same edit (a lowered rung, an added qualifier) | listed |
| Fell on a ladder, or a qualifier or limiting word added | warning: a claim correction the authors must see | listed |
| Any ladder change in a negated sentence | protected: a weaker verb under "not" can make the claim stronger | listed |
| A sentence with a claim deleted, or a new sentence with one | warning, or protected for a new claim at rung 1 or above | listed |
| Any other sentence deleted (a plain statement is a claim too) | warning, unless it reads as a stock phrase an edit may cut | listed |
| Any other new sentence, or a rewritten one that lost or gained words | not listed (the checks above still apply) | listed |
| Negation count changed | warning | listed |

`--authorised FILE` marks as authorised the protected claim changes that something asked for, one entry per
change (a passage from its sentence and the finding, comment or request behind it); the guard still lists them,
with what asked for each, and every other widened claim fails, in a revision inventory too.
`--allow-strengthening` authorises every claim change at once, for a request that covers the whole text. Neither
covers numbers, citations or identifiers.

## Critic and editor vocabulary

Name a claim problem by the catalogue entry in [deslop catalogue](../../manuscript-deslop/references/llm-smells.md) where one exists, and by these ladders. These
names are for the critic and the editor; in anything the authors read, describe the problem first and put the
ID in parentheses.

- **I1** verbs not matched to the design (an association reported with a causal verb): give both rungs.
- **I2** hedge strength not matched to the evidence; **I6** certainty or scope changed between sections or by
  an edit; **B7** one object under several names; **C16** declarative chains with no stated link.
- **CLAIM** a claim with no number, citation or result behind it.

A copy editor never moves a claim on style grounds. Lowering a claim to what its evidence shows is a claim
correction, and it follows the `edits` setting
([author priorities](../../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)):
under `conservative` and `apply`, when a confirmed finding supports it, apply it by rewording (never by deleting
the claim) and show it before and after with its section and the evidence, in plain words ("the sentence says
the variant causes the effect; the study measured an association"); under `propose`, or without a confirmed
finding, propose it with the same text. Only the choice between new work and a narrower claim is a decision for
the authors. A claim that outruns its evidence is listed under "Fix now", ahead of the writing changes
(`../../manuscript-integrity-check/references/author-priorities.md`, "Order the work by when it can be done").

## Limits

The markers are English word lists. The guard compares whole aligned sentences, not clauses, so a hedge that
moves from one clause to another inside the same sentence can pass, and an edit that keeps every marker can
still change a claim (a swapped subject, a changed comparator). A clause-initial "while" is read as a concession
even when it is temporal. Read the diff.

## Sources

The ladder order adapts the Claim-Strength Contract of Yila-AI/awesome-research-skills (Apache-2.0,
https://github.com/Yila-AI/awesome-research-skills), with a rung split into effect and causation and a
separate evidential ladder. The sentence-aligned comparison and the scope, null-result and evidence-status
locks follow the design of xmutfyh/dsh-plugin-writing-guard (MIT), reimplemented here.
