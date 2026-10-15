# Humanizing manuscript prose: the contract and the process

What editors and screeners flag is substance: invented or mismatched references, generic claims no result
supports, implications nobody measured, terminology that drifts, declarations that tell different stories.
Smooth prose alone is not the problem, and AI-text detectors are poor evidence of authorship
(`detector-evidence.md`). So humanizing a manuscript means making each sentence specific, supported and in
the authors' voice. It never means making text harder for a classifier to recognise.

This file is the procedure. `llm-smells.md` is the catalogue of patterns (with examples) the procedure
looks for; `section-guide.md` says what each part of a paper needs.

---

## 1. The contract

State it to yourself before every pass and check against it at the end.

**Role.** A scientific copy editor, not an author.

**Primary rule.** The scientific meaning stays exactly as the authors wrote it: every claim, number,
citation, hedge, negation and limitation.

**You may:**
- delete stock phrases, filler, connectors used as glue, significance inflation and mini-conclusions;
- replace an inflated word with the plain one, or better, with what it stood for;
- shorten, split, merge or reorder sentences inside a paragraph;
- move a number from later in the paragraph into the sentence that makes the claim;
- make a technical term recur unchanged where the draft varies synonyms for it;
- convert a bullet list inside running text into a sentence, when the items are already in the text;
- fix grammar, spelling, punctuation and the house style;
- match the authors' voice from their own writing;
- flag a vague sentence and ask the authors for the missing specific.

**You may not:**
- add a fact, number, citation, mechanism, implication, limitation, example or comparison;
- change a number, unit, statistic, identifier, citation or technical term;
- strengthen certainty: remove a hedge, turn an association into a cause, drop a qualifier such as
  "in some cohorts", or remove a limitation;
- change a negation;
- move content between paragraphs or sections, merge or split paragraphs, or reorder sections (that is
  restructuring: list it separately for the authors);
- insert errors, typos or deliberately awkward phrasing; cycle synonyms; vary sentence length to hit a
  "burstiness" target; inject unlikely words for "perplexity";
- invent "plausible specifics" (a scale, a frequency, an anecdote) to make a paragraph sound grounded;
- paraphrase through another tool or a round-trip translation;
- edit with the goal of changing an AI-detector score, or run a detector to decide what to rewrite.

**When unsure**, flag the sentence for the authors instead of rewriting it.

---

## 2. Invocation modes

- **Passage mode** (text pasted into the conversation). Deliver the edited passage, then the change table
  (section 6), then the sentences flagged for the authors.
- **File mode** (a path). Edit the file in place, prose only: never touch equations, code, tables of data,
  citation keys, labels, cross-references, URLs or front matter. Run the guard (section 5), then report a
  summary: what kinds of change, how many, which sentences need the authors. Offer the full change table
  rather than pasting it.
- **Embedded mode** (another task uses this as a step, e.g. while adapting a manuscript to a venue). Run
  the whole loop, return only the edited text and the guard result.

In every mode: edit one section at a time, never a whole paper in one pass; the context needed to keep
the meaning exact is the section and the results it rests on.

---

## 3. Before editing

### 3.1 Read the whole section, and what it rests on

Know the section's job (`section-guide.md`), the venue and its register, the results and tables the
section cites, and the paper's defined terms. Write down the paper's term for each key object (module,
cohort, score, pipeline) before editing, so synonym cycling can be undone consistently.

### 3.2 Writer profile (when the authors give samples, or have earlier papers)

Ask for, or find, two to five paragraphs the authors wrote themselves, ideally from before any AI help:
an earlier paper, a thesis chapter, a grant, the oldest revision in version history. Note, as five to ten
short hypotheses:

1. **Sentence length.** Typical range; whether they use short sentences for results.
2. **Word level.** Plain or elevated; "use" or "utilize"; "show" or "demonstrate".
3. **Paragraph openings.** Straight to the result, or context first.
4. **Hedging vocabulary.** Which hedges they use ("suggests", "is consistent with", "we cannot exclude").
5. **Person and voice.** "We" for the authors' actions, or passive throughout; tense conventions
   (present for established facts, past for this study's results).
6. **Numbers.** Inline with the claim, or in parentheses after it; their precision habits.
7. **Connectors.** Explicit ("However,", "Therefore,") or carried by order.
8. **Punctuation.** Semicolons, parentheses, dashes; British or American spelling.
9. **Recurring phrases and lab vocabulary.** Keep them, even when slightly odd.

Match those habits. Do not upgrade casual words or regularise a deliberate quirk. A sample outranks the
style defaults in `llm-smells.md`: if the authors use semicolons or the occasional dash, keep them at
their frequency.

Without a sample, use the plain technical register: short declarative sentences, "we" for the authors'
actions, numbers instead of adjectives in Results (one headline number at most in the abstract), present tense for established facts and past tense for this
study's results.

### 3.3 Inventory

Before rewriting, list what is there, with counts, per paragraph:

- smells from `llm-smells.md`, by entry (A1, B1, C5, H1, …), each with the quoted phrase;
- **anchors**: numbers, named methods, datasets, genes, cohorts, citations. A paragraph with no anchor
  making a claim is a question for the authors, not something to fill;
- defined terms and the synonyms used for them;
- every hedge, negation and causal verb (these must survive).

Running the integrity scan first (`../../manuscript-integrity-check/scripts/scan.py`) gives the
mechanical part of this list.

---

## 4. Rewriting

1. **Re-derive, do not word-swap.** Read a sentence, state to yourself what it claims and on what
   evidence, then write that claim plainly. Swapping "utilize" for "use" inside an unchanged sentence
   leaves the shape that reads as AI (the participle tail, the connector, the mini-conclusion). This
   matters most when the text was drafted by a model, and above all when you drafted it earlier in the
   same conversation: treat your own earlier output as foreign text.
2. **Cut before you rewrite.** Many smells are whole sentences that carry nothing (A8, B5, C4, H1, H12,
   H14). Delete them; then edit what is left.
3. **Put the anchor in the claim, in Results.** If a Results paragraph says "substantially faster" and
   Table 2 says 4.2×, the number moves into the sentence (E1). If no anchor exists, flag it; never supply
   one. Do the opposite in the Abstract, Introduction and Discussion: a run of metrics there (A12) is a
   smell. Moving figures out of the abstract changes what the abstract says, so propose it to the authors
   as a restructuring item instead of doing it.
4. **Size paragraphs to content.** Long where the argument needs it, short where a result is one line.
   Do not pad a paragraph that became short after cuts: a shorter, specific paragraph is the goal.
5. **Keep each hedge at its strength.** "may", "suggests", "in this cohort", "we cannot exclude" stay.
   Remove only stacked duplicates ("may potentially" → "may").
6. **Keep the terms.** One name per object, the paper's own.

---

## 5. After rewriting

### 5.1 The literal gate

Re-read the edited text itself, not your memory of it, and write a count for each item, quoting every
hit. Write zeros explicitly. A gate entry without a count was not run.

- em dashes (and spaced or double-hyphen dashes): count; fix all unless the authors' sample uses them;
- B1 vocabulary: quote each hit; keep only technical uses (B1 "Leave it when");
- B5 filler and C4 signposting phrases: count;
- C1 and H4 negation and comparison pivots ("not only", "not just", "it is not X, it is Y", "more X than
  Y"): count;
- C5 sentence-initial connectors: count consecutive runs;
- A9 participle tails: count;
- A8 and H1 paragraph-final restatements and aphorisms: count;
- H2 announcement colons and thesis-first openers: count;
- mixed quote styles, Markdown residue, emojis: count.

Fixing hits regenerates prose, and regenerated prose reintroduces the same tells, so re-scan the sentences
you just rewrote.

### 5.2 The scaffolding audit

Go through section H of `llm-smells.md` pattern by pattern (H1 to H18) over the edited section. Then ask
once: **"What still makes this read as machine-written?"** List the two or three residual patterns, fix
them, and run the gate again. Stop after one loop: further loops over-edit into choppy, voiceless prose.

A flagged residual is removed, not justified. "It reads thin without it" means the paragraph was padded;
let it be short. The exception is content: if removing the scaffolding would remove a claim, keep the
claim in plain words.

### 5.3 The guard

```bash
uv run --script scripts/guard.py BEFORE.md AFTER.md        # or: guard.py FILE --against <git ref>
```

Exit code 1 means a protected item changed (a number, citation, identifier, term, URL or code span):
revert it, or show it to the authors as a proposed content change. Read every watched change (hedges,
negations, causal verbs, comparatives) and confirm the claim is the same.

### 5.4 Reading checks

- Read the passage aloud, or as a reviewer would: does each sentence say something the reader needs?
- Does every claim still point to its evidence (a number, a table, a citation)?
- Is the length right? An edited section often comes out 10 to 30% shorter. That is the point; do not
  pad it back. If it came out more than half shorter, the original was mostly filler: say so to the
  authors and list the claims that now need anchors.

---

## 6. Output

For every nontrivial change, in passage mode or on request in file mode:

| # | original | revision | reason (smell id) |
|---|---|---|---|
| 1 | "These findings have important implications for personalized medicine." | (deleted) | A3 empty implication |
| 2 | "…was significantly faster…" | "…was 4.2 times faster (40 s vs 168 s; Table 2)…" | B3, E1: number from Table 2 |

Then **Flagged for the authors**: each sentence that needs a fact only they have, with the question
("Which cohort does 'larger cohorts' mean here, and is it planned?").

Then the guard result. No preamble before the edited text, no narrative of what you did beyond the table.

---

## 7. Register by text type

| text | register notes |
|---|---|
| Abstract | Structured if the journal says so; one claim per sentence; one or two headline numbers, not the metric table (A12); no hype, no field-landscape opener |
| Introduction | The gap and the aim; citations to specific prior work; no textbook padding |
| Methods | Passive voice is fine; exact parameters, versions, thresholds and the reason for each non-default choice |
| Results | Past tense; the number first; figures cited, not described |
| Discussion | Interpretation tied to results; the two limitations that matter; no send-off |
| Figure captions | What is plotted, n, error bars, statistics; not "This figure illustrates" |
| Cover letter | Short and specific; what the paper shows, why this journal, required declarations (H16) |
| Response to reviewers | One thank-you; per point, what changed and where (G3) |
| Plain-language summary | Short sentences, everyday words, no semicolons; still no invented facts |

Details per section: `section-guide.md`.

---

## 8. What this procedure refuses, and why

| refused | why |
|---|---|
| Optimising against an AI detector, best-of-N selection by detector score | Detector scores track style and change with ordinary professional editing (0% to 100% false positives across 13 detectors on human text, Park et al. 2026); optimising for them changes nothing an editor checks and can make permitted AI use look like concealment |
| Perplexity injection, burstiness targets, deliberate misfires or errors | They make the paper worse to read; several journals reject for poor grammar outright |
| Invented "plausible specificity" | It is fabrication; a reviewer who checks one invented detail stops trusting the paper |
| Round-trip paraphrase or translation | Semantic drift: a lost negation or qualifier turns a correct sentence false |
| Rewriting hedges, limitations or causal language to sound more confident | It changes the scientific claim |
