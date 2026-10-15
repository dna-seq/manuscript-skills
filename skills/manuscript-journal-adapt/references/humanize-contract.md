# The copy-editing contract for manuscript prose

What editors and screeners flag in 2026 is substance: invented or mismatched references, generic claims that
no result supports, implications nobody measured, terminology that drifts, declarations that tell different
stories. Smooth prose alone is not the problem, and AI-text detectors are poor evidence of authorship (see
`detector-evidence.md`). So "humanizing" a manuscript here means making each sentence specific, supported
and in the authors' voice. It never means making text harder for a classifier to recognise.

## The contract (state it before every pass, and keep to it)

**Role.** A scientific copy editor, not an author.

**Primary rule.** The scientific meaning stays exactly as the authors wrote it.

**You may:**
- delete stock phrases, filler transitions and significance inflation;
- replace an inflated word with the plain one ("utilize" → "use", "plays a crucial role in" → "affects", or
  better, say how);
- shorten, split or reorder sentences inside a paragraph for clarity;
- make a technical term recur unchanged where the draft varies synonyms for it;
- fix grammar, spelling, punctuation and the house style (for example, no em-dashes);
- match the authors' voice from their own writing samples;
- flag a vague sentence and ask the authors for the missing specific.

**You may not:**
- add a fact, number, citation, mechanism, implication, limitation or example;
- change a number, unit, statistic, identifier, citation or technical term (the guard checks these);
- strengthen certainty: drop a hedge ("may", "suggests", "in some cohorts"), turn association into causation,
  or remove a limitation;
- change a negation;
- merge or split paragraphs, or move content between sections (that is restructuring: list it separately);
- insert errors, typos or awkward phrasing on purpose, cycle synonyms, or vary sentence length to change
  "burstiness" or "perplexity";
- translate round-trip or paraphrase through another tool;
- edit with the goal of changing an AI-detector score, or run a detector to decide what to rewrite.

**For every nontrivial change**, show `original → revision → reason`.

**When unsure**, flag the sentence for the authors instead of rewriting it.

## What to look for

Run `manuscript-integrity-check/scripts/scan.py` first: its stock-phrase, vocabulary-density, participle-tail,
em-dash and overclaim findings are the target list, each with its source. Then read for what a scanner
cannot see:

| pattern | example | fix |
|---|---|---|
| significance inflation | "This represents a pivotal advance in the evolving landscape of genomics." | Cut, or state what changed and by how much, from the paper's own results |
| empty implication | "These findings have important implications for personalised medicine." | Ask the authors which implication, for whom, with what limit; cut if none |
| participle tail | "…in 40 s, highlighting the efficiency of the approach." | End the sentence at the result; the reader judges efficiency |
| copula avoidance | "The module serves as a container for…" | "The module is a container for…" |
| tripartite rhythm | "fast, transparent, and extensible" in every paragraph | Keep the list only where all three are argued; otherwise name the one that is |
| synonym drift | "module" / "annotation package" / "plugin" for one object | Pick the paper's defined term and use it everywhere |
| hedging everything, or nothing | "may potentially suggest" / "proves" | One hedge sized to the evidence: keep the authors' level of certainty |
| boilerplate limitations | "Further research is needed." | Ask for the two limitations that actually threaten the inference |
| mini-conclusions | every paragraph ends "Overall, …" | Cut the restatement |
| chat leftovers | "Certainly, here is…", "[insert reference]" | Delete; check what the passage was meant to say |

The installed `humanizer` skill (blader/humanizer, from Wikipedia's "Signs of AI writing") has a longer
catalogue of general patterns. Use it for spotting, but this contract wins where they differ: humanizer allows
merging paragraphs, adding personality and dwelling where a human would; a manuscript copy edit does none of
that.

## Voice

Ask for, or find, two to five paragraphs the authors wrote themselves, ideally from before any AI help: an
earlier paper, a thesis chapter, a grant text, the oldest revision in version history. Note sentence length,
how they open paragraphs, their hedging words, their technical vocabulary, whether they use "we". Match
those habits; do not "improve" them. Without a sample, use plain technical register: short declarative
sentences, "we" for the authors' actions, numbers instead of adjectives.

## After the pass

1. `guard.py BEFORE AFTER` (or `guard.py FILE --against <ref>`). A protected change is reverted or explained
   to the authors; every watched change (hedges, negations, causal verbs, comparatives) is read.
2. If the project marks revised segments, mark these the way it already does. Nothing else is recorded.
3. Re-run the integrity scan.
4. The authors read the result without the AI session open. A skeptical co-author should be able to defend
   every paragraph.
