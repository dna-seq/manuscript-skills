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
`references/author-priorities.md` for the shared priorities, scope and disclosure rules, and in particular
its sections on [authors first, journals second](references/author-priorities.md#the-author-decides-authors-first-journals-second),
[ordering the work by stage](references/author-priorities.md#order-the-work-by-when-it-can-be-done) and
[writing for the authors](references/author-priorities.md#writing-for-the-authors): the report follows all
three. This skill reports checkable problems; apply fixes too when the user's request already includes them.
Referee judgement (is the contribution enough, which comparison would a referee demand) is
`manuscript-peer-review`'s.

Apply the requested task across the whole paper unless the author specifies a narrower scope.
Follow the shared [workflow controls](references/author-priorities.md#scope-iteration-and-review)
for requested section or stage review, before/after comparisons and optional interviews.

Before work, follow the shared [project setup and run-output contract](references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run. This applies to direct invocations too.

## Ground rules (read before anything else)

1. **Improve publication prospects.** Concentrate on evidence, clarity, fit and actual submission barriers.
   Style and detector signals do not establish authorship or misconduct. Do not invent compliance or
   suggest changing prose merely to obtain a detector score.
2. **Keep review and editing distinct.** For a review-only request:
   - each finding quotes the passage it concerns with its section, says **what is wrong**, **which rule**
     (with its page and the date it was read), and **what kind of change** ("cut the phrase", "give the
     measured number from Table 2", "add the DOI after checking it at https://doi.org/10.xxxx");
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
   If you could not verify it, say so and what you tried. A failed lookup does not establish fabrication; try
   an alternate authoritative record when the citation matters.
4. **A check that could not run did not pass.** Say in the report that it could not be checked and why
   (offline, paywalled, no figures supplied); `not_assessed` is the word for the shared record and script
   JSON, not for the authors. Detector-style signals (vocabulary density, em-dashes) are risk indicators, never
   evidence of AI authorship; COPE and ICLR both warn against acting on them without proof.
5. **Verify applicable policies.** The reference notes are dated research, not universal rules. Before
   treating an obligation as binding, verify the selected journal, article type and submission stage
   against a current primary source using available tools. Reuse a current check in the same task. If
   access fails, label the rule unconfirmed and continue other work; do not make the author retrieve every
   blocked page. SECONDARY items and vendor claims do not establish requirements.
6. **Separate rules from verifiability.** Use `references/requirement-checkability.md` for policy
   decisions. Check observable submission artifacts; distinguish them from author-reported process,
   editorial judgement and unknown enforcement. The author decides how to handle a policy conflict;
   report their chosen disposition and continue without treating journal policy as an assistant veto. In
   the report, a conflict between what the authors did or asked for and a journal's policy (an AI-drafting
   ban, for example) is one sentence among the decisions for the authors, never a required fix or a blocker.

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

Select the steps the request needs and run each once over unchanged material. Script outputs that only feed
the report belong in this skill's run folder (`/tmp` in examples is illustrative, not a delivery path);
the `reports` setting controls presentation in chat, and a full list the authors are to open goes beside the manuscript
([where files go](references/author-priorities.md#minimum-useful-work)). Paths are relative to this skill's directory: `scripts/`
holds `scan.py`, `number_check.py`, `hygiene.py`, `precommit.py` and `settings.py` (the plugin-wide settings); `venues.py` and `policy_watch.py` are in
`../manuscript-journal-adapt/scripts/`, and the other skills' scripts are in their own `scripts/` folders.

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
not run goes in the report's list of what could not be checked, with what it leaves open. When the authors say
they are about to submit, pass `--final` to both `scan.py` and `check_availability.py`, so the end-stage items
count. A narrower request runs only what it needs.

### Step 1: mechanical scan

```bash
uv run --script scripts/scan.py PAPER.md --venue <venue-key> --md /tmp/scan.md --json /tmp/scan.json
```

Add `--online` only when the request covers references (a full audit, a citation check): it resolves every DOI,
PMID and arXiv id, compares titles and authors, records retraction status and flags preprints since published or
withdrawn (`../manuscript-reference-check/references/identity-checks.md`). `--venue KEY` checks length limits;
`--git` only when the authors ask. With `--online`, unidentified reference entries are searched by their text
(`--search-unidentified`, on by default); that sends bibliographic strings, not the manuscript, to Crossref.
Turn it off with `--no-search-unidentified` only when the authors ask. It finds chatbot leftovers, placeholders (also in HTML comments), missing
declarations, AI mentions without a disclosure, citation mismatches, overclaim words, stock and tortured phrases,
vocabulary densities, percentages that disagree with their counts and Abstract figures that never reappear (a
missing software archive is only a hint for `manuscript-reporting-check`). It reads Markdown, LaTeX (with the
`.bib` it uses) and plain text. Its Markdown groups the findings under the four stage labels of The report and
treats the paper as work in progress: the end-stage items (statements, archives, placeholders) are listed last
and left out of its readiness line and exit code. Add `--final` only when the authors say they are about to
submit, and those items count too. Exit code 1 means a blocker candidate among the counted findings; with
`--online`, 3 means none, but a lookup did not answer, so the run cannot be called clean. Read every
serious and important finding in context and omit false positives (a module named "Superhuman", "discovery" as a
software term). Severities, stages and the readiness line are provisional: the report judges readiness itself
(see The report). AI mentions, style counts and absent generic declarations are not by themselves a submission
barrier.

Script line numbers count lines of the source file. In a file that keeps each paragraph on one line they name a
paragraph, and in LaTeX a reference finding may point at a line of the `.bib`; either way, locate the finding by
quoting the sentence (or naming the entry by first author, year and key) and give the line only in parentheses.

Length against a venue limit is approximate. The abstract count takes every word from the Abstract heading to
the next heading, so in a structured abstract it includes the part labels and the Availability, Contact and
Supplementary lines (the scan also gives the words after each label, so leave out the parts the journal does not
count); in LaTeX it also counts command names. The body count takes every word before the reference list, with
the abstract, title, author block, headings, tables, captions and declarations included, HTML comments removed
and separate supplementary files not read. Journals usually count less (many leave out tables, legends and
references), so treat both as upper estimates and check the journal's own counting rule before asking for cuts.

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
their t, F, χ², r or z and df (the script calls it "gross" when significance at α flips), table column totals that
disagree with their cells, and SEMs that disagree with SD/√n; results it cannot read are listed as not checked.
Read `references/number-checks.md` first (coverage, legitimate explanations). Report candidates, with their
arithmetic, as questions for the authors, never as errors or misconduct, and describe each check by what it
tests, its name in parentheses ("a mean of 3.50 is impossible for whole-number answers from 19 people, since
66/19 = 3.47 and 67/19 = 3.53 (GRIM test)").

A software or benchmark paper often has nothing the script can test (no means of whole-number data, no test
statistics, no SD column), and an empty result is then "nothing to test", not a clean result. Recompute by hand
from the printed values, as [benchmark arithmetic](references/number-checks.md#benchmark-arithmetic-by-hand)
describes: each ratio from the two numbers it divides (and whether it is a ratio of medians or of means), each
mean, SD and SEM from the listed runs, stage times against the total, and counts against the rows they summarise.
Put what disagrees under "Fix now" with its arithmetic, and say in one sentence what you recomputed and found
consistent.

Before reporting a number that matches no table, or a quoted version or software behaviour, look in the
project's own files when the paper has a repository: benchmark result tables, run logs, `pyproject.toml` or
release tags, the code that writes the output. Report what they settle and why the text differs (a figure
from a wider set of runs than the table it cites, a version later superseded), as the
[project check](references/author-priorities.md#minimum-useful-work) describes. Ask the authors only what the
files leave open.

### Step 4: reporting, availability and venue requirements

Ethics, privacy, clinical-scope and regulatory applicability (including authors' own public genomes) are
`manuscript-policy-fit`'s; a human-data mention or a missing declaration alone does not mean new approval.

Use `manuscript-reporting-check` for the reporting guidelines of the study design
(`../manuscript-reporting-check/scripts/guidelines.py`) and data, code and software availability
(`../manuscript-reporting-check/scripts/check_availability.py --online`); keep only the venue's requirements here.

Look the venue up, with its notes in `references/journal-policies/` and `references/publisher-policies.md`
(journals) or `references/venues-and-preprints.md` (arXiv, bioRxiv/medRxiv, ML conferences), then re-check the
live page (ground rule 5; `policy_watch.py` shows whether its AI passages moved since they were last read):

```bash
uv run --script ../manuscript-journal-adapt/scripts/venues.py show KEY
uv run --script ../manuscript-journal-adapt/scripts/policy_watch.py check --venue KEY
```

Then check the items in `references/venue-requirements.md`: an AI-use statement in every place the venue asks,
with only the fields it requires (report gaps; `manuscript-journal-adapt` drafts and places it), no AI author
or AI output cited as a source, required availability statements, length and structure limits
(`over_limit_return` in `venues.yaml`), costly validation requirements as an early feasibility question for the
authors under their budget (`manuscript-journal-select` for alternatives), figure rules and preprint overlap. A
required comparison with existing methods is judged by what every benchmark in the paper actually compares
against (`references/claim-evidence.md`, improvement over existing methods), never by whether the baseline was
the authors' own earlier system. When `policy_watch.py` cannot reach the page, read it with a web-fetch tool;
when that stops short of the section you need, use the latest complete Internet Archive copy, and say which copy
each quoted rule rests on.
Scope, length, structure and the abstract format go under "Once you have chosen the journal"; the AI-use
statement, declarations, archives and the data availability statement go under "Before submission, once the
code is final". Without a chosen venue, skip the venue lookup and say which checks wait for the choice.

### Step 5: claims and calibration

This step owns claim calibration; `manuscript-peer-review` reuses its result. Use `references/claim-evidence.md`:
list the load-bearing claims (reuse `claims:` in the record), give each its type and rungs, find its evidence,
and report only claims above it, with the smallest remedy: narrower wording the authors decide, the supporting
evidence, or a venue for the narrower claim. Describe the gap in plain words ("the sentence says numeracy caused
better comprehension; the study measured a correlation in one sample"); its name from the reference file
(association to causation, surrogate to outcome, sample to population) may follow in parentheses. "First",
"novel" and "only" follow
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

Run it on the files that will be uploaded (directory, archive or files) after the last edit. On a draft with no
upload files yet, run it once on the current source and supplementary folder for the two findings that are
urgent at any stage (below), and say it must run again on the final files. It finds LaTeX
comments and commented-out blocks with content, hidden text and prompts aimed at AI reviewers (a blocker,
whoever added it), secrets (masked), local paths, editable Google Docs links, EXIF GPS and author tags in
figures, and with `--anonymous --author NAME` self-identifying text. PDFs without poppler and figures without
Pillow are not assessed. Read `references/submission-package.md`; report, and leave removal to the authors.
These findings belong to "Before submission, once the code is final", with two exceptions that go under "Fix
now" whatever the stage: hidden text addressed to AI reviewers, and a leaked secret (the key should be revoked
now).

### Referee judgement and revisions

For independent reviewer passes or a simulated referee review, use `manuscript-peer-review`: its quick pass
runs a desk editor and a reviewer of evidence and statistics in isolation, each point quoting the manuscript and
checked against it before it is merged here. In the report, say in plain words which reviewer raised a point
("the statistics reviewer"), not the internal role name. For real referee reports, use
`manuscript-reviewer-response`; rerun Steps 1, 3 and 7 on the revised files.

## The report

Return a concise report written for the authors; save a separate file when requested or established by the
project. It follows [Writing for the authors](references/author-priorities.md#writing-for-the-authors) and
[Order the work by when it can be done](references/author-priorities.md#order-the-work-by-when-it-can-be-done).
The script reports are working material: their Markdown quotes the passages and groups them by stage, but check
each placement against the paper and the request, rewrite rather than paste, and do not send the authors to a
JSON file or to these reference files.

**Stage and readiness.** Judge the stage from the request and the manuscript: TODO markers, missing sections and
"draft" banners mean work in progress; when unsure, assume work in progress. Open with a few sentences on where
the paper stands and the smallest next steps. For a draft, readiness rests on the current-work groups only; the
end-stage items are not counted and not called blockers unless the authors say they are about to submit.

**The findings, in four groups**, each under its label and current work first:

1. **Fix now**: the science and the evidence. Claims beyond the results (Step 5), numbers that disagree (Step 3),
   wrong or unsupported citations (Step 2), missing methods or comparisons the conclusions need, chat markup or
   a placeholder standing where a citation should be, and hidden text addressed to AI reviewers or a leaked
   secret whenever they are found (Step 7).
2. **Then the writing**: structure, clarity, terminology, claims reworded to match the evidence, text left over
   from a chat interface.
3. **Once you have chosen the journal**: scope and fit, length, required sections, the abstract format, the
   journal's reporting checklist and reference style (Step 4).
4. **Before submission, once the code is final**: archive DOIs and release tags, version numbers quoted in the
   text, the data availability statement and other declarations, the AI-use statement, cover-letter points,
   revision markers and TODO comments, and the upload check (Step 7). Keep this list short for a draft.

Leave out a group with nothing in it. Within a group, put blockers (a confirmed scientific defect, or a verified
submission barrier) first, then major findings, then optional ones with their benefit and effort, and put an item
after the one it depends on ("after the benchmark is rerun, update the numbers in the Abstract"). Group findings
with one root cause and omit irrelevant checks.

**Each finding** is a short paragraph of full sentences: the quoted sentence, table row or line with its section
(the line number, if any, in parentheses), what is wrong and why it matters for the paper, and what to do. Give a
journal rule with what it says, its page as a URL and the date it was read, and keep journal rules apart from
methodological advice and preferences. A source the authors need to open is a full URL (`https://doi.org/...`,
`https://pubmed.ncbi.nlm.nih.gov/<PMID>/`, the journal's page). A number candidate shows its arithmetic. Script
status words (`not_assessed`, `unverified`, `gross`), the scan's check names and the rule IDs in the reference
files never stand alone; describe the problem in plain words, and name the skill behind a merged finding in
parentheses.

**After the groups:**

- **Decisions for the authors**: choices only they can make, a sentence or two each (a narrower claim or more
  evidence, a venue trade-off, how to read an unclear rule). A conflict between the authors' work or request and
  a journal's policy goes here, once, in one sentence naming the conflict and its practical consequence
  ("Bioinformatics asks authors not to have LLMs draft sections; if an editor asks, this would need
  disclosure"). It is never a required fix or a blocker, and it is not repeated elsewhere in the report.
- **What could not be checked**: each material check that could not run, why, and what it leaves open.
- **Corrected, or ready to apply**: corrections a registry or the project's files settle (published version
  of a preprint, a title, a year, a DOI, a miscount), given as one or two sentences of counts by kind and
  whether any changes what a sentence claims; the itemised list is the patch or diff, shown on request. They
  never appear in the groups above or as questions. A reference that cannot be found anywhere, or whose
  identifiers belong to another work, is not in this class: it goes under "Fix now" with how serious it is
  (see [what needs no decision](references/author-priorities.md#minimum-useful-work)).
- **Questions**, only for facts the next step needs that neither the manuscript, the conversation nor the
  project's files answer.

Before handing the report over, run the smell check on it and read it against the pattern list the check
prints (`uv run --script ../manuscript-prose-edit/scripts/style_profile.py REPORT.md --report --check`, as
[Writing for the authors](references/author-priorities.md#writing-for-the-authors) requires; never a
separately installed `humanizer` skill), and fix what reads as notes or stock phrasing without changing any
fact, quote or number. With the shared record,
update its `checks` and `open_issues` instead of adding a log.

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
