---
name: manuscript-integrity-check
description: >-
  Review a manuscript for concrete scientific and submission problems, prioritising publication and low
  author burden: unfinished content, claims beyond their evidence, numbers and statistics that do not add
  up, venue requirements, and submission files that leak comments, hidden text, secrets or metadata. Use for
  a manuscript audit, submission-readiness review, a check that the numbers add up, or pre-upload file check.
  Use manuscript-reference-check for citations and source support, manuscript-reporting-check for reporting
  guidelines, availability and statistics reporting, manuscript-peer-review for simulated referees,
  manuscript-reviewer-response for real referees, manuscript-prose-edit for language editing,
  manuscript-journal-select for journal choice, manuscript-journal-adapt for venue formatting and AI-use
  statements, and manuscript-policy-fit for clinical-scope, ethics, privacy and regulatory applicability,
  including authors' voluntarily public personal genomes or biomedical data.
---

# Manuscript integrity check

Help the authors publish a sound manuscript in a suitable journal with the least avoidable work. Read
`references/author-priorities.md` for the shared priorities, scope and disclosure rules. This skill reports
checkable problems; apply fixes too when the user's request already includes them. Referee judgement (is the
contribution enough, which comparison would a referee demand) is `manuscript-peer-review`'s.

Apply the requested task across the whole paper unless the author specifies a narrower scope.
Follow the shared [workflow controls](references/author-priorities.md#scope-iteration-and-review)
for requested section or stage review, before/after comparisons and optional interviews.

## Ground rules (read before anything else)

1. **Improve publication prospects.** Concentrate on evidence, clarity, fit and actual submission barriers.
   Style and detector signals do not establish authorship or misconduct. Do not invent compliance or
   suggest changing prose merely to obtain a detector score.
2. **Keep review and editing distinct.** For a review-only request:
   - findings say **where**, **what is wrong**, **which rule** (with source), and **what kind of change**
     ("cut the phrase", "give the measured number from Table 2", "add the DOI 10.xxxx after checking");
   - mechanical fixes are fine to write out in full: a corrected DOI, a deleted chatbot leftover, a missing
     identifier, a reference entry rebuilt from Crossref metadata;
   - do not replace paragraphs unless editing is also requested. For authorised edits, use the prose-edit
     skill's content-preservation contract and apply the selected venue's disclosure exemptions;
   - preserve existing revision markers, but do not audit provenance or create a ledger unless requested;
     `manuscript-revision-marks` lints them and lists the prose no review round has touched.
     A later human edit does not automatically resolve a journal's restriction on earlier AI drafting.
3. **Never invent a source.** Verify suggested citations against authoritative records, using an available
   DOI, PMID, arXiv identifier or primary publisher/library record. Reuse a current verification of an
   unchanged reference; do not demand an identifier that the work does not have.
   If you could not verify it, say "unverified". A failed lookup does not establish fabrication; try an
   alternate authoritative record when the citation matters.
4. **A check that could not run did not pass.** Mark it `not_assessed` with the reason (offline, paywalled,
   no figures supplied). Detector-style signals (vocabulary density, em-dashes) are risk indicators, never
   evidence of AI authorship; COPE and ICLR both warn against acting on them without proof.
5. **Verify applicable policies.** The reference notes are dated research, not universal rules. Before
   treating an obligation as binding, verify the selected journal, article type and submission stage
   against a current primary source using available tools. Reuse a current check in the same task. If
   access fails, label the rule unconfirmed and continue other work; do not make the author retrieve every
   blocked page. SECONDARY items and vendor claims do not establish requirements.
6. **Separate rules from verifiability.** Use `references/requirement-checkability.md` for policy
   decisions. Check observable submission artifacts; distinguish them from author-reported process,
   editorial judgement and unknown enforcement. The author decides how to handle a policy conflict;
   report their chosen disposition and continue without treating journal policy as an assistant veto.

## Inputs to use when relevant

Use existing context first. A focused check does not need every input below.

- **The manuscript**: the source the authors edit (Markdown, LaTeX or text; convert `.docx` or a Google Doc
  export with `pandoc -t gfm`), revision markers left in. Step 7 uses the files that will be uploaded.
- **What AI did**, when a disclosure or policy decision depends on it: the authors' account, not git (a
  co-author trailer often marks automation; `scan.py --git` counts are a question for the authors).
- **Target venue(s)**, inferred from the text, the folder or the conversation; a general review can proceed
  without one.
- **Paper type and study design**: a system or tool, a finding, or an evaluation; the design keys in
  `references/manuscript-record.md`; and whether AI produced scientific content (AI-assisted coding alone does
  not make a conventional study an AI-scientist benchmark). This decides which steps apply.
- **The shared record** (`references/manuscript-record.md`): if `manuscript-record.yaml` exists, read its
  venue, designs, claims, completed checks and open issues first; reuse a check whose `manuscript_sha256`
  (the file's sha256, e.g. `sha256sum PAPER`) is unchanged, and say so. Afterwards record your checks and
  hand on open issues with a `route`. Create it only when the work spans several sessions or the authors ask.

## Workflow

Select the steps the request needs and run each once over unchanged material. Script outputs go to a scratch
location (`/tmp` below), not beside the manuscript.

| Request | Steps |
|---|---|
| Full submission audit | 1 to 7, as relevant to the paper and venue |
| "Check our numbers" (values, arithmetic, p-values) | 3 (`number_check.py`) |
| Statistics reporting (n per analysis, tests, intervals) | `manuscript-reporting-check` §4 |
| "Are the claims overstated?" | 5 |
| "Anything we shouldn't upload?" | 7, and 1 offline for leftovers |
| Citations only | `manuscript-reference-check` |

A full audit runs at least Step 1 with `--online`, claim support for the load-bearing claims (Step 2),
`../manuscript-reporting-check/scripts/check_availability.py PAPER --online` and `number_check.py`; whatever could
not run goes under not assessed with what it leaves open. A narrower request runs only what it needs.

### Step 1: mechanical scan

```bash
uv run --script scripts/scan.py PAPER.md --venue <venue-key> --md /tmp/scan.md --json /tmp/scan.json
```

Add `--online` only when the request covers references (a full audit, a citation check): it resolves every DOI,
PMID and arXiv id, compares titles and authors, records retraction status and flags preprints since published or
withdrawn (`../manuscript-reference-check/references/identity-checks.md`). `--venue KEY` checks length limits;
`--git` only when the authors ask. It finds chatbot leftovers, placeholders (also in HTML comments), missing
declarations, AI mentions without a disclosure, citation mismatches, overclaim words, stock and tortured phrases,
vocabulary densities, percentages that disagree with their counts and Abstract figures that never reappear (a
missing software archive is only a hint for `manuscript-reporting-check`). Exit code 1 means a blocker; with
`--online`, 3 means no blocker but a lookup did not answer, so the run is not clean. Read every
blocker and major finding in context and omit false positives (a module named "Superhuman", "discovery" as a
software term). Severities are provisional; AI mentions, style counts and absent generic declarations are not by
themselves a submission barrier.

### Step 2: references

Use `manuscript-reference-check`, reusing its recorded result for unchanged references; Step 1 ran its identity
and consistency checks. A full audit also checks claim support: locate the passage behind each claim the paper
rests on (borrowed numbers first), run `../manuscript-reference-check/scripts/support.py` on those quotes and read
them as its protocol says. Report a borrowed number as the source states it.

### Step 3: numbers and statistics

```bash
uv run --script scripts/number_check.py PAPER.md --md /tmp/numbers.md --json /tmp/numbers.json
```

It finds one quantity stated with different values across sections (sample sizes, headline metrics), means and
SDs impossible for whole-number data with their n (GRIM, GRIMMER, percentages of n), p-values that disagree with
their t, F, χ², r or z and df ("gross" when significance at α flips), table column totals that disagree with their
cells, and SEMs that disagree with SD/√n; unreadable results are not assessed. For software and benchmark papers,
recompute ratios and derived columns by hand. Read `references/number-checks.md` first (coverage, legitimate
explanations). Report candidates, with their arithmetic, as questions for the authors, never as errors or
misconduct.

### Step 4: reporting, availability and venue requirements

Ethics, privacy, clinical-scope and regulatory applicability (including authors' own public genomes) are
`manuscript-policy-fit`'s; a human-data mention or a missing declaration alone does not mean new approval.

Use `manuscript-reporting-check` for the reporting guidelines of the study design
(`../manuscript-reporting-check/scripts/guidelines.py`) and data, code and software availability
(`../manuscript-reporting-check/scripts/check_availability.py --online`); keep only the venue's requirements here.

Look the venue up with `../manuscript-journal-adapt/scripts/venues.py show KEY`, its notes in
`references/journal-policies/` and `references/publisher-policies.md` (journals) or
`references/venues-and-preprints.md` (arXiv, bioRxiv/medRxiv, ML conferences), then re-check the live page
(ground rule 5; `../manuscript-journal-adapt/scripts/policy_watch.py check --venue KEY` shows whether its AI
passages moved). Then check the items in `references/venue-requirements.md`: an AI-use statement in every place
the venue asks, with only the fields it requires (report gaps; `manuscript-journal-adapt` drafts and places it),
no AI author or AI output cited as a source, required availability statements, length and structure limits
(`over_limit_return` in `venues.yaml`), costly validation requirements as an early venue no-go under the
author's budget (`manuscript-journal-select` for alternatives), figure rules and preprint overlap.

### Step 5: claims and calibration

This step owns claim calibration; `manuscript-peer-review` reuses its result. Use `references/claim-evidence.md`:
list the load-bearing claims (reuse `claims:` in the record), give each its type and rungs, find its evidence,
and report only claims above it, by gap name (association to causation, surrogate to outcome, sample to
population) with the smallest remedy: narrower wording the authors decide, the supporting evidence, or a venue
for the narrower claim. "First", "novel" and "only" follow
[priority and absence claims](../manuscript-reference-check/references/claim-support.md#priority-and-absence-claims).
Leave calibrated claims and stated non-claims alone. Limitations should name a risk and its consequence. Report
stock phrases and vocabulary density only when they impair clarity or break the house style (CLAUDE.md /
AGENTS.md).

### Step 6: AI-generated science (only when AI produced scientific content)

Use only the claim-relevant parts of `references/ai-science-design.md`. Distinguish an evaluation of an
AI system from a biological finding obtained with AI assistance. Do not prescribe pre-registration,
extra cohorts, fixed run counts, ablations or human-rating studies as a package. When evidence is
insufficient, identify the inference at risk and offer narrower wording or an appropriate venue as well
as additional work. Ask authors for new analyses only when the missing evidence warrants them.

### Step 7: submission package

```bash
uv run --script scripts/hygiene.py submission/ --md /tmp/hygiene.md --json /tmp/hygiene.json
```

Run it on the files that will be uploaded (directory, archive or files) after the last edit. It finds LaTeX
comments and commented-out blocks with content, hidden text and prompts aimed at AI reviewers (a blocker,
whoever added it), secrets (masked), local paths, editable Google Docs links, EXIF GPS and author tags in
figures, and with `--anonymous --author NAME` self-identifying text. PDFs without poppler and figures without
Pillow are not assessed. Read `references/submission-package.md`; report, and leave removal to the authors.

### Referee judgement and revisions

For independent reviewer passes or a simulated referee review, use `manuscript-peer-review`: its quick pass
runs a desk-editor and an evidence-and-statistics seat in isolation, each point quoting the manuscript and
adjudicated before it is merged here, marked with its seat. For real referee reports, use
`manuscript-reviewer-response`; rerun Steps 1, 3 and 7 on the revised files.

## The report

Return a concise report; save a separate file when requested or established by the project. Lead with
the paper's readiness and the smallest next steps, then:

1. **Blockers**: confirmed defects or verified applicable submission barriers.
2. **Major**: concrete threats to validity or the paper's prospects.
3. **Optional**: useful improvements, with their likely benefit and effort.
4. **Uncertain / not assessed**: material checks that could not run, and their consequence.

Each finding: location (`file:line` or section), what is wrong, the rule with its source and date, and the
suggested change; a number candidate carries its arithmetic. Distinguish journal rules from methodological
advice and preferences, name the skill behind a merged finding, group findings with one root cause and omit
irrelevant checks. Add cover-letter points only when needed. With the shared record, update its `checks` and
`open_issues` instead of adding a log.

When fixes are authorised, use `manuscript-prose-edit` (its preservation contract and `guard.py`) for language,
`manuscript-journal-adapt` for formatting and AI-use statements and `manuscript-reference-check` for reference
repairs; follow the project's revision-marking rules. Add no per-pass log.

## Files

- Scripts (PEP 723, `uv run --script`, offline unless `--online`): `scan.py`, the mechanical scan;
  `number_check.py`, ledger, GRIM/GRIMMER, statistics and tables (`references/number-checks.md`); `hygiene.py`,
  the package check (`references/submission-package.md`); `precommit.py`, the hook (`--hygiene`: advisory).
- `references/claim-evidence.md`: claim types, the evidence each needs, inference gaps, design ceilings.
- `references/manuscript-record.md`: the optional shared per-paper record, study-design keys, outcome words.
- `references/venue-requirements.md`: the Step 4 checklist for the chosen venue.
- `references/publisher-policies.md`, `references/venues-and-preprints.md`, `references/target-journals.md`:
  publisher, preprint-server, conference and target-journal policies with their 2026 enforcement notes.
- `references/screening-signals.md`: the tools editors run and every signal with its source; detector reliability.
- `references/journal-policies/`: per-publisher notes with the verbatim AI-policy text, URL, read date and fetch
  route behind each `venues.yaml` entry; `references/policy-snapshots/`: their AI passages as `policy_watch.py`
  last read them, with `index.yaml` (read date, route, failed attempts).
- `references/ai-science-design.md`, `references/notes-factcheck.md`: design review for AI-scientist papers.
- `references/venues.yaml`: machine-readable venue rules, shared with `manuscript-journal-adapt/scripts/venues.py`.
- `references/disclosure-templates.md`, `references/requirement-checkability.md`: AI-use statements per venue
  (`manuscript-journal-adapt` drafts from them); observable requirements versus process claims.
- `references/kobak_2024_style_words.csv`: the 379 excess style words of 2024 (Kobak et al., *Sci Adv* 2025).
