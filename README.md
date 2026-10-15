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
  - It copy-edits prose so it stops reading as AI slop, following a catalogue of about 70 general and
    manuscript-specific patterns, each with a bad example, a fix and when to leave it. Every number,
    citation, identifier, term, hedge and negation must survive, and `guard.py` checks that they did.
  - `style_profile.py` ranks paragraphs by density of named smells and compares the style with a sample of the
    authors' own writing. It is not a detector and reports no probabilities.
  - Reflection mode alternates a critic agent (reads cold, names what still reads as machine-written) and a
    writer agent (fixes exactly that) for at most two rounds, with the guard after each pass.

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
Check this manuscript before I submit it to my target journal.
Verify every reference in this manuscript and tell me which ones don't exist or don't match.
Rank life-science and bioinformatics journals by how strict their AI policy is for this manuscript.
Adapt this manuscript to the requirements of the journal I choose.
Copy-edit this section so it doesn't read as AI-generated, without changing any claim.
Write the shortest AI-use statement my target journal accepts.
```

The scripts also run on their own:

```bash
uv run --script skills/manuscript-integrity-check/scripts/scan.py paper.md --online --venue <venue-key> --git
uv run --script skills/manuscript-journal-adapt/scripts/venues.py rank --ai-use revision --min-jif 5   # also lists the venue keys
uv run --script skills/manuscript-journal-adapt/scripts/venues.py show <venue-key>
uv run --script skills/manuscript-journal-adapt/scripts/guard.py paper.md --against HEAD
uv run --script skills/manuscript-journal-adapt/scripts/style_profile.py paper.md --sample my_earlier_paper.md
```

LaTeX manuscripts work too: the scan reads the `.bib` named in `\bibliography{…}`, resolves its DOIs,
PMIDs and arXiv ids, and checks every `\cite` key.

## Optional: free AI-text detectors

Only when you want a detector's view, and only free ones. A score is a hint about where to reread, never
evidence and never a target.

```bash
uv run --script skills/manuscript-journal-adapt/scripts/detector_setup.py check        # what can run here
uv run --script skills/manuscript-journal-adapt/scripts/detect.py paper.md --sample my_2021_paper.md
```

`check` reports a Hugging Face token, GPU, memory, disk and cached models, recommends a detector (local
ModernBERT by default, so the manuscript stays on your machine) and lists the page for any missing token;
`detector_setup.py open hf-token` opens it, and the skill asks before doing so. `detect.py` scores windows of
120 to 400 words, marks each flagged, not flagged or not assessed, and calibrates its threshold on your own
earlier writing. The hosted free tier (AI or Not) runs only with `--allow-remote`. `detect.py` needs torch and
transformers (a few GB on first run), so it is not part of the pre-commit hook.

## Pre-commit hook

Fail a commit on desk-reject triggers (chatbot leftovers, placeholders, a missing AI disclosure where AI
is mentioned, a venue length limit exceeded by 20%+), and see the paragraphs with the densest smells.
Offline: no reference resolution and no third-party detectors.

```yaml
# .pre-commit-config.yaml in the manuscript repository
repos:
  - repo: https://github.com/dna-seq/manuscript-skills
    rev: main
    hooks:
      - id: manuscript-check
        files: ^paper/.*\.(md|tex)$
        args: [--venue, <venue-key>]      # optional; add --strict or --max-smells 8 to be stricter
```

## What these skills will not do

They do not edit text to lower an AI-detector score, insert errors to look human, or paraphrase through
other tools: detectors are unreliable evidence either way, and those tricks make the paper worse. They do
not invent references; every suggested citation is resolved first. And they write AI disclosures as short as
the venue allows, but never smaller than the use was, because version history and public repositories can
contradict an understated statement.

## Limits

- The venue data covers about twenty life-science, bioinformatics and genomics journals plus the main
  preprint servers and ML conferences; add others to `venues.yaml` from their author guidelines. A venue marked `null` for a field was not researched there; read its page.
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
