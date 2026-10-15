# Manuscript Skills

**The primary objective is to help authors get a scientifically sound manuscript published in a suitable
journal, with the least avoidable delay, expense and work.** Making editors or administrators happy is
not an independent goal. These skills improve the paper, identify real submission barriers, help choose
a journal with manageable policies, and handle required paperwork pragmatically.

The author decides how to handle ambiguous or burdensome journal rules. Explain a material risk once,
then continue under that decision without scolding or acting as a policy gatekeeper. Use supported
exemptions, concise disclosures and suitable alternatives; distinguish the chosen approach from verified
compliance. See [author priorities](skills/manuscript-integrity-check/references/author-priorities.md) and
[what requirements can actually be checked](skills/manuscript-integrity-check/references/requirement-checkability.md).

Skills for Claude Code and Codex:

- **`manuscript-journal-select`** builds a requirements-based shortlist from the shared venue database.
  - It checks whether required cohorts, experiments or other validation are available or affordable before
    ranking preferences. In-silico-only work is a legitimate resource constraint.
  - It compares scientific fit, open-source/open-science policies, editorial receptiveness, review speed,
    APCs and AI burden, with sources and explicit unknowns.
  - It separates desk decisions from external peer review and records validation alternatives and design
    exclusions; an attractive AI policy cannot compensate for infeasible validation.
- **`manuscript-integrity-check`** reports problems and the rule behind each; it does not rewrite the paper.
  - It resolves every DOI, PMID and arXiv id (title and first author must match; retractions and expressions
    of concern are flagged) and finds the DOI for references that have none.
  - It finds chatbot leftovers, placeholders, missing declarations, AI use with no disclosure, citation and
    bibliography mismatches, venue length limits, overclaiming and overused vocabulary.
  - For papers where an AI system produced results, it reviews the study design: the full count of attempts,
    baselines, contamination controls, human re-analysis.
- **`manuscript-policy-fit`** reduces avoidable clinical, ethics, privacy and regulatory misclassification.
  - It distinguishes wording ambiguity and venue scope from requirements the actual study triggers,
    checks current primary policies, and uses applicable exceptions and concise statements.
  - It explicitly covers authors voluntarily publishing their own genomes or biomedical records,
    distinguishing personal self-release from recruited patient data and new self-experimentation.
  - It compares preprint/journal requirements, handles bioRxiv/medRxiv referral loops, and drafts precise
    scope clarifications and reviewer replies. Accurate wording preserves the study's real facts.
- **`manuscript-journal-adapt`** changes text under a content-preservation contract, with a guard script
  that helps catch selected changes. A passing guard does not prove semantic equivalence.
  - It turns the chosen venue's actual rules into an adaptation checklist.
  - It copy-edits prose so it stops reading as AI slop, following a catalogue of general and
    manuscript-specific patterns, each with a bad example, a fix and when to leave it. Every number,
    citation, identifier, term, hedge and negation must retain its meaning. `guard.py` flags selected
    token-count changes; the agent also reviews the diff in context.
  - `style_profile.py` ranks paragraphs by density of named smells and compares the style with a sample of the
    authors' own writing. It is not a detector and reports no probabilities.
  - Optional, requested reflection mode alternates a critic agent (reads cold, identifies concrete writing problems) and a
    writer agent (fixes exactly that) for at most two rounds, with the guard after each pass.

The policy catalogue contains dated research notes, inherited publisher defaults and partially researched
entries. Verify the actual shortlisted or target journal's current requirements before relying on them.
A focused edit does not require a policy interview, full audit, writing samples or a new log.

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
install on first use. Reference checking needs network access (Crossref, PubMed E-utilities, arXiv);
mechanical manuscript checks run offline. Live policy checks, peer-publication lookups and hosted detectors
also need network access. The installed [humanizer](https://github.com/blader/humanizer) skill is optional:
`manuscript-journal-adapt` uses its pattern catalogue for spotting when it is present.

## Try it

```text
Check this manuscript before I submit it to my target journal.
Verify every reference in this manuscript and tell me which ones don't exist or don't match.
Rank life-science and bioinformatics journals by how strict their AI policy is for this manuscript.
Choose journals for this in-silico-only paper: no wet-lab budget, open-source support and review speed matter.
Adapt this manuscript to the requirements of the journal I choose.
Copy-edit this section so it doesn't read as AI-generated, without changing any claim.
Write the shortest AI-use statement my target journal accepts.
Check whether this software paper's wording could be mistaken for clinical research.
I publicly released my own genome. Clarify its use without implying a recruited patient cohort.
Compare the ethics and privacy requirements of suitable preprint servers for this manuscript.
Draft a scope clarification after bioRxiv and medRxiv referred this paper to each other.
```

The scripts also run on their own:

```bash
uv run --script skills/manuscript-integrity-check/scripts/scan.py paper.md --online --venue <venue-key>
uv run --script skills/manuscript-journal-adapt/scripts/venues.py rank --ai-use revision --min-jif 5   # also lists the venue keys
uv run --script skills/manuscript-journal-adapt/scripts/venues.py rank --study-design public-data --validation-available none
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
`detector_setup.py open hf-token` opens it when requested. `detect.py` scores windows of
120 to 400 words, marks each flagged, not flagged or not assessed, and calibrates its threshold on your own
earlier writing. The hosted free tier (AI or Not) runs only with `--allow-remote`. `detect.py` needs torch and
transformers (a few GB on first run), so it is not part of the pre-commit hook.

## Pre-commit hook

An optional hook reports mechanical findings and paragraphs with dense style patterns. Use `--advisory`
to keep drafting and committing without a submission-readiness gate. Without it, chatbot leftovers and
recorded venue return limits fail a commit; `--strict` also gates major findings. AI mentions and metric
counts cannot establish a policy violation. Offline: no reference resolution or third-party detectors.

```yaml
# .pre-commit-config.yaml in the manuscript repository
repos:
  - repo: https://github.com/dna-seq/manuscript-skills
    rev: main
    hooks:
      - id: manuscript-check
        files: ^paper/.*\.(md|tex)$
        args: [--advisory, --venue, <venue-key>] # omit --advisory only if you want a commit gate
```

## What these skills will not do

They do not edit text to lower an AI-detector score, insert errors to look human, or paraphrase through
other tools: detectors are unreliable evidence either way, and those tricks make the paper worse. They do
not invent references; suggested citations are verified first. Disclosures use accurate known facts and
only the fields and placements actually needed. The skills distinguish checkable artifacts from
author-reported process and editorial judgement, and do not demand private histories or fabricate them.

## Limits

- The [ethics/scope policy notes](skills/manuscript-policy-fit/references/venue-policies.md) distinguish
  retrieved policy text, indexed excerpts and research entry points. They require live target checks;
  the AI-policy ranking does not measure ethics/privacy burden. Personal self-release can support a
  different analysis from recruited research, but is not a universal legal or venue exemption.
- The venue data covers life-science, bioinformatics and genomics journals plus the main
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
