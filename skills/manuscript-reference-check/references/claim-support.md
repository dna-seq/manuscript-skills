# Claim support: does the cited source say it?

A citation can be real, correctly formatted and still wrong, because the cited work does not say what the
sentence claims. Identity checks cannot see this. This protocol decides, claim by claim, whether the source
supports the sentence, and records how much of the paper was checked.

## Outcomes

Every checked claim gets exactly one outcome.

| Outcome | When | Words in the report | What the authors do |
|---|---|---|---|
| `confirmed` | A passage located verbatim in the source carries the claim as written: same quantity, direction, population, conditions and strength. | "supported" | Nothing. Record the passage and where it sits (section, table, page). |
| `partial` | The source supports a weaker, narrower or differently scoped claim, or supports the claim only at second hand. | "only partly supported: the source says ..." | Narrow the sentence to what the source says (give the narrowed wording), or replace the source with one that carries the claim. |
| `rejected` | The source does not say it, or says something else or the opposite, and a second independent re-check found no support (below). | "not supported: the source says ..." or "the source does not say this" | Correct the sentence to what the source says, find a source that carries it, or cut it. |
| `blocked` | The source could not be read: paywalled, not deposited, only an abstract that does not settle the claim, or a decision only the authors can make. | "could not be checked: ..." with the reason | Supply the text (the authors usually have access), or keep the claim marked unverified. |

- `blocked` never counts as support. In the shared outcome words it is `unverified`, with what was tried.
- No verbatim supporting passage, no `confirmed`. "It clearly implies", "it follows from Figure 3" and a
  matching abstract topic are not passages. A number computed from values in the source is `partial` until
  the computation is written down beside the claim.
- `support.py` never outputs an outcome. Its statuses are mechanical signals for the reading below.
- The outcome names and support.py's status names are for this protocol; the report to the authors uses the
  words in the table.

## Choose the claims and record coverage

Check every cited claim when the paper is short or the authors ask for it. Otherwise check, in this order:

1. claims the paper's conclusions rest on (the motivation, the comparison that makes the contribution new,
   a limitation a result depends on);
2. claims in the Abstract;
3. borrowed numbers: any figure, rate, threshold, sample size or effect size taken from a cited work;
4. "first", "novel", "only", "no previous study" and other priority or absence claims (see
   [Priority and absence claims](#priority-and-absence-claims));
5. claims flagged by another skill (a referee's "missing prior work", a citation added in a revision).

Record coverage in the report as "checked N of M cited sentences" and say how the N were chosen. M counts
the sentences that carry at least one citation, whatever the citation style: a numbered "[12]", an author-year
"(Duncan et al., 2019)" or a `\cite{}` key. A citation that supports several sentences is checked for each
sentence. Never describe a sample as a full check.

## Run the mechanical gate

Write the claims file after reading each source and locating the passage, never before. The quote is copied
from the source text, never from memory, an abstract snippet in a search result, a fetch tool's summary of a
page, or the manuscript. When the source is open access, the text need not be saved first: give its
identifier as `source` and run with `--online`. Run support.py on every claim whose report quotes a passage: for up to ten claims it
takes minutes. Skip it only when the report quotes nothing. A quote support.py cannot locate is not yet
verbatim: find it in the source text, or say where it sits (a figure, a supplement the text lacks), before
rating the claim `confirmed`.

```yaml
manuscript: paper.md            # optional, for the record
sources_dir: sources            # optional; relative `source` paths resolve against it
claims:
  - id: C1                      # unique
    location: "Results, Performance (paper.md, line 42)"   # the section, then the line in parentheses
    claim: "The exact sentence from the manuscript, with its citation marker [12]."
    reference: "12"             # the citation key or reference-list number
    quote: "The passage from the source, copied verbatim."   # optional; '...' marks an omission
    source: sources/smith2021.txt    # a text, JATS XML or HTML file, or an identifier:
    # source: doi:10.1038/s41467-019-11112-0   (also pmid:, pmcid:, arxiv:)
    priority: borrowed-number   # optional: load-bearing | abstract | borrowed-number | first-only | other
```

```bash
uv run --script scripts/support.py claims.yaml --json support.json --md support.md
uv run --script scripts/support.py claims.yaml --online   # fetch legal open-access text for identifiers
```

The Markdown report quotes each claim and its passage, gives identifiers as links and says each status in
words; a `location` written as `paper.md:42 (Results)` is shown as "under Results (paper.md, line 42)".
A PDF must be converted first (`pdftotext -layout paper.pdf paper.txt`, or the document tool's text export).
`--online` reads Europe PMC full text for PMC articles, bioRxiv and medRxiv full-text XML, and arXiv HTML,
and caches what it reads (`~/.cache/manuscript-reference-check/sources` by default). It never scrapes a
publisher page; a paywalled source comes back `source_unavailable`, with any free page the index lists
(often an author manuscript) for you to read with your own tools.

| Status | Means | Does not mean |
|---|---|---|
| `quote_located` | The quote occurs verbatim after folding PDF and XML artifacts (whitespace, line-break hyphens, ligatures, typographic quotes and dashes, superscripts). | That the passage supports the claim. |
| `numbers_missing` | A number in the claim is not in the quote (thousands separators, decimals and scientific notation compared by value; years reported apart, unflagged). | That the number is wrong: it may sit in the next sentence, a table, or be a conversion. Read it. |
| `polarity_mismatch` | One side states an increase, an association or a difference and the other a decrease or none, or a negation appears on one side only. | That the claim is reversed: a lexicon cannot read every sentence. Read it. |
| `quote_not_found` | The quote is not in the text. `closest_passage` shows what the source says nearest to it. | That the source lacks the claim: the quote may be misquoted, or in a figure or supplement. |
| `source_unavailable` | No text to check, or only an abstract that does not contain the quote. | Anything about support. It feeds `blocked`. |

`secondary_markers` lists citation markers and phrases ("et al.", "[12]", "as reported by") in the sentence
around a located quote: the number may belong to a primary study the source is reporting.

`support.py` exits 1 when any claim comes back `numbers_missing`, `polarity_mismatch` or `quote_not_found`, 3
when none does but a source was unavailable, and 0 otherwise; a nonzero exit is a prompt to read, not a failure. Its JSON is an object with `summary` (counts by status) and `results`
(one entry per claim, in the order of the claims file).

## The reading, and a skeptic for what matters

Read each claim against its source and give it an outcome (the table above). The bias that matters sits with
two outcomes, so the extra reading is proportionate to them:

- **`confirmed` on a load-bearing claim** (priority `load-bearing`, `abstract`, `borrowed-number` or
  `first-only`): whoever chose the passage is inclined to see support in it. Send all of these, in one batch,
  to a skeptic subagent in a fresh context that has not seen why each passage was chosen. Give it, per claim,
  the claim sentence, the full source text (always, when it is a short page or an abstract with its introduction;
  otherwise the located passage with at least a paragraph either side, cut at sentence ends) and
  the instructions below. Where it returns a stricter outcome, report that outcome unless a passage it missed
  settles the claim. A `confirmed` with priority `other` needs no skeptic read.
- **`rejected`**: stands only after a second independent search of the source (below).
- **`partial` and `blocked`** need neither: a `partial` already tells the authors to narrow the claim, and a
  `blocked` never counts as support.

Start the skeptic yourself; it is part of this check, so the user does not need to ask for subagents. It is a
seat like a referee's and follows [Independent readers and referees](../../manuscript-integrity-check/references/project-workflow.md#independent-readers-and-referees):
a fresh agent whose whole context is its brief (the claims, the sources and the instructions below), the brief
saved and the output registered with `runs.py add --role seat --seat skeptic --isolation fresh-agent`. When
the authors chose another model, the skeptic runs on it instead of the host
([manuscript-other-models](../../manuscript-other-models/SKILL.md)), recorded as `skeptic@CLI` with `--model`. A
delegated stage that cannot start agents hands the brief back to the coordinator, which starts the skeptic.
Only where the host cannot start agents at all, do the skeptic read in-context, starting from the claim, the
reference and the source only, record `--isolation one-agent`, and say in the report that the second reading
was done in the same session and is not independent. The skeptic's instructions:

- Default to `rejected`. Confirm only by quoting the passage that carries the claim, verbatim.
- Check what was measured, on whom and under what conditions, against what the sentence says. A source's
  "we chose X" is not "X is standard practice"; a cohort of European ancestry is not "people".
- For each number: is it printed in the source, or derived? If derived, show the arithmetic or return
  `partial`.
- Is the source the primary record for this claim? A review, textbook or news item is fine for framing an
  idea, not for a measurement, threshold or effect size.
- Do the hedges survive? "Associated with" is not "causes"; "may" is not "does"; a subgroup is not the
  population.
- If the source says the opposite, say so in those terms: that is a correction to the manuscript, not a
  sourcing problem.

**A `rejected` stands only after a second independent search fails to find support.** Give the claim and
the source to another fresh pass (it can join the skeptic batch; without subagents, repeat the reading from
the source's start without the first verdict, using different search terms) and ask it to look anywhere in
the source for support: results, tables, figure legends, methods, supplementary text. If it finds a passage,
the outcome is what that passage supports (`confirmed` or `partial`). Record both passes.

## Traps to check for by name

- **Second-hand citation.** A review cited for a primary study's number (the review's passage carries
  "(Duncan et al., 2019)" or "[12]"). Outcome `partial`: cite the primary study, after checking its own
  text gives the same number, or write "as summarised by".
- **A borrowed number that differs from the source.** Report both values with their locations. A rounded or
  converted value (19.4% as "about one in five") is fine when the wording says so.
- **Retracted or concerned work used as evidence.** Read the retraction state from the identity check
  (`retraction` in the scanner's JSON). A retracted source supports nothing, whatever its text says; cite it
  only to discuss the retraction. An expression of concern belongs beside the citation.
- **Preprint and published versions differ.** Before replacing a preprint with its published version,
  re-check every borrowed number against the published text. Counts, authors and conclusions change: the PGS
  Catalog preprint reports 192 scores from 78 publications, its *Nature Genetics* version 657 from 119.
- **Wrong population, site or conditions.** The quantity is right but measured on another cohort, tissue,
  ancestry or setting.
- **Abstract-only reading.** An abstract may confirm a headline; it rarely settles a number, a population or
  a limitation. If the full text was not read, say so.
- **Absence and priority claims.** "First", "novel", "only" and "no previous study" are claims about a
  literature search, not about one source; a citation to one paper cannot confirm them. Apply
  [Priority and absence claims](#priority-and-absence-claims).
- **Corrections that are worse.** A replacement source or corrected identifier gets the same check as the
  original before it is proposed.

## Priority and absence claims

This is the one rule for "first", "novel", "only", "unprecedented", "no previous study", "no existing tool"
and "unlike existing tools"; manuscript-integrity-check (claim calibration) and manuscript-peer-review (the
claims-novelty seat and adjudication) point here.

- What supports one is a reproducible search the paper reports: where (PubMed, Europe PMC, preprint servers,
  and code registries for software), with what query, on what date, and what counts as the same thing.
- `confirmed` only when the paper reports that search and re-running it finds no earlier work that does the
  same thing. Record the date of the re-run: the claim holds up to it.
- `partial` when no search is reported, or when "first" covers a combination of known parts. Give the
  narrowed wording ("we found no study in PubMed and Europe PMC up to 2026-10 that ...", "the first to
  combine X and Y").
- `rejected` when an earlier work does the same thing: name it, with an identifier resolved by the identity
  check.
- A concern that the work is "not novel" or "already done" names the prior work with a resolved identifier;
  otherwise it is reported `unverified`.

## Requests from other skills

- **"Missing prior work" from manuscript-peer-review.** Verify the named works exist (identity check on a
  small reference list or `.bib` of just those works), then check whether each actually does what the
  referee says the manuscript ignores. Return `verified` or `unverified` per work; never add a work the
  check did not find.
- **Citations added in a revision, from manuscript-reviewer-response.** Check identity and support for each
  new or replacement citation before it enters the response letter; a reply that cites a source which does
  not carry the point weakens the response.

## Report

Follow [Writing for the authors](../../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors).
Each checked claim that needs a change gets a short paragraph in full sentences: the manuscript sentence
quoted with its section, the cited work as a link (`https://doi.org/...`,
`https://pubmed.ncbi.nlm.nih.gov/<PMID>/`, `https://arxiv.org/abs/<id>`), the source's passage quoted with
where it sits, the outcome in the words of the table above, and the smallest change (a corrected number,
narrowed wording, a replacement source to verify, or what would unblock it). For example:

> **The Introduction says more than the cited study shows.** The manuscript says "European ancestry-derived
> polygenic scores performed comparably in African ancestry samples [1]." Duncan et al. 2019
> (https://doi.org/10.1038/s41467-019-11112-0) report the opposite in their abstract: "predictive performance
> of European ancestry-derived polygenic scores is lower in non-European ancestry samples". The sentence is
> not supported. Rewrite it to say that performance was lower, or cut it.

Supported claims can be listed briefly, one sentence each with the passage quoted. Then, in sentences:

- coverage: "We checked 8 of the 30 sentences that cite a source", and how they were chosen;
- how many claims had each outcome, and for each one found not supported, that a second reading of the
  whole source found no support;
- which supported claims an independent second reader checked, and whether that reader was a separate agent
  or the same session;
- second-hand citations, differing numbers and retracted sources as their own short list;
- the claims that could not be checked, with what would unblock each (which document, which section, what
  access).

When the shared record exists (`manuscript-record.yaml`), add rejected, partial and blocked claims to
`open_issues` (`from: manuscript-reference-check`, `route: fixable-in-text` or `author-required`) and the
completed check to `checks`. Changing a claim's wording is the authors' decision; write proposed wording
in the report unless editing was requested.

## Where this design comes from

The outcomes and the default-reject skeptic follow Boom5426/Nature-Paper-Skills
`claim-source-verification` (MIT); the quote and number gate follows poemswe/co-researcher (MIT); the rule
that a flag must survive independent re-checks is a convention from AlterLab-IEU/AlterLab-Academic-Skills.
paper-preflight's `support` command (MIT) retrieves passages for an agent to judge in the same way. The
text and code here are written for this skill; nothing was copied.
