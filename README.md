# Manuscript Skills

Get an AI-assisted manuscript past a 2026 journal desk. Editors and integrity screeners now reject papers for
fabricated or mismatched references, leftover chatbot text, missing or vague AI disclosures, formulaic
public-data analyses, and AI-science claims without baselines or a full count of attempts. These skills run
the same checks before you submit, help you pick a journal whose AI policy fits how the paper was written,
adapt the manuscript to that journal, and copy-edit AI-sounding prose without changing what it says.

Two skills, for Claude Code and Codex:

- **`manuscript-integrity-check`** reports problems and the rule behind each; it does not rewrite the paper.
  - It resolves every DOI, PMID and arXiv id (title and first author must match; retractions and expressions
    of concern are flagged) and finds the DOI for references that have none.
  - It finds chatbot leftovers, placeholders, missing declarations, AI use with no disclosure, citation and
    bibliography mismatches, venue length limits, overclaiming and overused vocabulary.
  - For papers where an AI system produced results, it reviews the study design: the full count of attempts,
    baselines, contamination controls, human re-analysis.
- **`manuscript-journal-adapt`** changes text, under a contract that a guard script enforces.
  - It ranks venues by how hard their AI policy falls on the paper and turns a chosen venue's rules into a
    checklist.
  - It copy-edits prose so it stops reading as AI slop. Every number, citation, identifier, term, hedge and
    negation must survive, and `guard.py` checks that they did.

The policy data was read from each venue's own pages on 15 October 2026. Policies changed several times in
2026, so re-read the target journal's page before you submit.

## Install

Claude Code, from the dna-seq marketplace:

```bash
claude plugin marketplace add dna-seq/dna-seq-claude-marketplace
claude plugin install manuscript-skills@dna-seq
```

or straight from this repository:

```bash
claude plugin marketplace add dna-seq/manuscript-skills
claude plugin install manuscript-skills@manuscript-skills
```

Codex: install `manuscript-skills` from the **DNA Seq Genomics** marketplace (see the marketplace README).

The scripts need [`uv`](https://docs.astral.sh/uv/) on PATH and run as `uv run --script …`; their dependencies
install on first use. Reference checking needs network access (Crossref, PubMed E-utilities, arXiv); every
other check runs offline. The installed [humanizer](https://github.com/blader/humanizer) skill is optional:
`manuscript-journal-adapt` uses its pattern catalogue for spotting when it is present.

## Try it

```text
Check this manuscript before I submit it to Bioinformatics.
Verify every reference in paper.md and tell me which ones don't exist.
Which journals are least strict about AI for a software paper whose text Claude helped revise?
Adapt this manuscript to PLOS Computational Biology's requirements.
Copy-edit the Discussion so it doesn't read as AI-written, without changing any claim.
Write the shortest AI-use statement Genome Biology will accept for this paper.
```

The scripts also run on their own:

```bash
uv run --script skills/manuscript-integrity-check/scripts/scan.py paper.md --online --venue bioinformatics --git
uv run --script skills/manuscript-journal-adapt/scripts/venues.py rank --ai-use revision --min-jif 5
uv run --script skills/manuscript-journal-adapt/scripts/venues.py show plos-comp-biol
uv run --script skills/manuscript-journal-adapt/scripts/guard.py paper.md --against HEAD
```

## What these skills will not do

They do not edit text to lower an AI-detector score, insert errors to look human, or paraphrase through
other tools: detectors are unreliable evidence either way, and those tricks make the paper worse. They do
not invent references; every suggested citation is resolved first. And they write AI disclosures as short as
the venue allows, but never smaller than the use was, because version history and public repositories can
contradict an understated statement.

## Limits

- The venue data covers about twenty bioinformatics and genomics journals plus the main preprint servers and
  ML conferences. A venue marked `null` for a field was not researched there; read its page.
- Vocabulary and style signals are risk indicators, not proof of anything. Corpus studies of LLM vocabulary
  cannot identify an individual paper, and word lists also flag non-native writers.
- Checking that a reference *supports* its sentence still needs a reader. The scanner proves the reference
  exists and matches; the skill tells you which claims to check by hand.

## Development

```bash
uv run pytest            # offline tests for scan.py, guard.py and venues.py
claude plugin validate .
```

To update a venue, edit `skills/manuscript-integrity-check/references/venues.yaml` and its sources in the
reference files beside it, change `checked`, and run the tests.

## Licence

MIT. Research and writing aid; not legal or editorial advice. Journal policies are quoted from their own
pages, and those pages govern.
