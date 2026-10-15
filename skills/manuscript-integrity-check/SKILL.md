---
name: manuscript-integrity-check
description: >-
  Pre-submission check of a manuscript against what journal desks, preprint servers and integrity screeners
  reject in 2026: undisclosed or under-documented AI use, hallucinated, mismatched or retracted references,
  chatbot leftovers and placeholders, missing declarations and availability statements, venue length limits,
  overclaiming, and (for AI-scientist or AI-assisted research) missing denominators, contamination controls,
  baselines and human re-analysis. Reports located findings with the rule and its source and says what to
  change; it does not ghost-write the paper. Use when asked to check, screen, review, audit or "de-slop" a
  manuscript or preprint before submission, to draft an AI-use disclosure, to verify references, or to judge
  whether an AI-generated-science paper will pass an editor.
---

# Manuscript integrity check

A desk editor in 2026 reads a manuscript with screening tools open: reference checkers, paper-mill alarms,
AI-text detectors, and the venue's own AI policy. This skill runs the same checks first, on the authors' side,
and tells them what to fix. It **reports and suggests; the authors write.**

## Ground rules (read before anything else)

1. **Fix the substance, never disguise it.** The goal is a paper that is verified, disclosed and calibrated,
   not one that slips past a detector. Never suggest paraphrasing to lower an AI-detector score, never remove
   an honest disclosure, never "humanize" text to hide where it came from. Wikipedia's own guide warns that
   treating the signs as the problem "could just make detection harder"; the signs point at unverified claims.
2. **The authors write the paper.** *Bioinformatics* and *Briefings in Bioinformatics* (ISCB policy) forbid
   drafting papers "from a prompt text" and allow an LLM "as an evaluation technique (to assist in finding
   inconsistencies or other anomalies)". This skill is that evaluation. So by default:
   - findings say **where**, **what is wrong**, **which rule** (with source), and **what kind of change**
     ("cut the phrase", "give the measured number from Table 2", "add the DOI 10.xxxx after checking");
   - mechanical fixes are fine to write out in full: a corrected DOI, a deleted chatbot leftover, a missing
     identifier, a reference entry rebuilt from Crossref metadata;
   - **no replacement paragraphs.** If the user explicitly asks for rewritten text, write it, and say in the
     report that this use must go into the AI-use disclosure (and the supplement, for ISCB venues).
   - When a revision ledger records AI-revised segments, sort them into **refinement** (rewording of text the
     authors wrote; compare with the previous round) and **generation** (new sentences or sections the AI
     wrote). Both must be disclosed; generated segments with no later human round are the ones to hand back
     to an author before an ISCB venue.
3. **Never invent a source.** Every citation the report suggests has been resolved in this session (DOI via
   Crossref/doi.org, PMID via E-utilities, arXiv id via the arXiv API) and its title and first author match.
   If you could not resolve it, say "not found", do not suggest it.
4. **A check that could not run did not pass.** Mark it `not_assessed` with the reason (offline, paywalled,
   no figures supplied). Detector-style signals (vocabulary density, em-dashes) are risk indicators, never
   evidence of AI authorship; COPE and ICLR both warn against acting on them without proof.
5. **Policies move monthly.** The references here were researched on 2026-10-15. Before telling the user a
   rule "requires" something, re-fetch the target venue's author-guidelines page (WebFetch; fall back to
   `google-chrome --headless --dump-dom URL` when Cloudflare blocks it) and quote it. SECONDARY items in the
   references are reports, not rules.

## Inputs to establish

- **The manuscript** (Markdown, LaTeX or text; convert `.docx` with `pandoc -t gfm`). Scan the source the
  authors edit, not a rendered PDF. If the project records who revised what (HTML-comment revision markers
  such as `<!-- @rev ID rounds=N by=name:date -->`, tracked changes, git history with AI co-author trailers),
  pass `--git` and keep the markers in: the scanner strips comments for prose checks but counts AI revisers.
- **Target venue(s).** Infer from the text, the folder or the conversation; ask only if nothing says. The
  disclosure, length and availability rules differ by venue, and one statement does not fit all (ACM no longer
  requires disclosure of writing help; ISCB requires supplementary documentation of it).
- **Paper type**: (a) a system or tool, (b) a finding, (c) an evaluation; and whether AI produced any of the
  scientific content (hypotheses, analyses, effect sizes, curated data, code that does the science) or only
  helped with writing. This decides whether Step 4 applies.

## Workflow

### Step 1: mechanical scan

```bash
uv run --script .claude/skills/manuscript-integrity-check/scripts/scan.py PAPER.md --online \
    --venue bioinformatics --md /tmp/scan.md --json /tmp/scan.json
```

`--online` resolves every DOI, PMID and arXiv id (title and first-author match, Retraction Watch retractions and
expressions of concern via Crossref, PubMed's "Retracted Publication") and looks up references that carry no
identifier in Crossref. `--venue KEY` checks the length limits recorded in `references/venues.yaml`. `--git`
counts commits touching the file that carry an AI co-author trailer. Exit code 1
means at least one blocker. It finds: chatbot leftovers and chat-interface markup (arXiv ban triggers),
placeholders and TODOs (including inside HTML comments, which still ship), missing declarations, AI mentions
without a disclosure, AI-revised ledger segments, citation/bibliography mismatches, overclaim words, stock
phrases, tortured phrases, sourced vocabulary densities, participle tails, em-dashes, abstract numbers that
never reappear, no archived software DOI, leave-one-out validation.

Read every blocker and major finding in context before reporting it: the scanner has false positives (a
module named "Superhuman", "discovery" as a software term, a conference name read as an author-year
citation). Drop what is wrong, keep what is right, and say which you dropped.

### Step 2: references beyond identity

The scanner proves a reference exists. Editors also check that it **supports the sentence** (ICMJE V,
Springer Nature's irrelevant-reference checker, Signals, Paperpal). For each claim that carries the paper
(the abstract's claims, every number taken from another paper, every "first"/"only"), open the cited abstract
(E-utilities `efetch`, Europe PMC, Crossref, or whatever literature tools are connected, e.g. a PubMed MCP
server) and confirm it says what the sentence says. Also flag: citations
of reviews where the original is meant, retracted works cited as support, missing DOIs (SN/BMC ask for them),
data and software cited without a persistent identifier, and heavy self-citation (report the share; no
published threshold exists).

### Step 3: venue compliance

Look the venue up in `references/publisher-policies.md` (journals) or `references/venues-and-preprints.md`
(arXiv, bioRxiv/medRxiv, ML conferences), then re-fetch the live page (ground rule 5). Check:

- **AI disclosure**: present, in every place the venue asks (cover letter, Methods, Acknowledgements, a
  titled declaration, the supplement, figure captions), with the fields it asks for: tool **and version**,
  dates, what it did, which sections, and how the authors verified the output. AI-written **code** that
  changes functionality goes in Methods (Science, Wiley, Elsevier, ACM). Draft the statement from
  `references/disclosure-templates.md`, filled with facts the user confirms; never guess what a tool did.
- **Author list** has no AI; no AI output cited as a primary source.
- **Availability**: code at a stable URL and an archived version with DOI, licence, test data, reproduction
  instructions, data availability statement (Bioinformatics, NAR, GigaScience, Genome Biology, PLOS).
- **Limits and structure**: abstract and body length, abstract headings, article-type rules. *Bioinformatics*
  returns manuscripts 20% or more over the limit without review.
- **Figures**: no AI-generated or AI-altered primary images; AI-assisted plots reproducible from data and code
  and disclosed in the caption; no general-purpose AI graphical abstracts at Elsevier/Cell.
- **Preprint overlap**: declare the arXiv/bioRxiv version; no parallel submission. arXiv caps submissions at
  two a month from 1 Oct 2026, and rejected ones count.

### Step 4: AI-generated science (only when AI produced scientific content)

Run the design review in `references/ai-science-design.md`: one primary contribution; pre-registration; the
full denominator with a flow diagram; case-selection rule; run-to-run variance; baselines including a permuted
control; ablations; independent human re-analysis of every headline number; external validation; blinded
rating with κ; error rates; cost and human hours; a stage-wise human/AI contribution table; artifacts; the
reporting guideline (REFORMS, TRIPOD-LLM, STROBE, ARRIVE). Then the four contamination channels, and wording:
"rediscovery" for known answers, "discovery" only for prospective or independent validation. For public-cohort
papers (NHANES, UK Biobank, FinnGen, MIMIC, FAERS…) apply that file's public-cohort list too.

### Step 5: calibration and voice

Check every priority or utility claim ("first", "novel", "only", "scalable", "seamless", "robust") against a
comparison or measurement in the paper; every "we show" against a result; the limitations for specificity
(a named risk with its consequence, not "further work is needed"). Report stock phrases and vocabulary density
with their source and as minor. Respect the project's house style if it has one (a style guide, or writing rules in CLAUDE.md / AGENTS.md).

### Step 6: optional independent passes

For a submission-ready draft, spawn two reviewer agents that have not seen this conversation, each given
the manuscript and the venue page: a **desk editor** (would you send this out for review? name the reason
you would not) and a **methods reviewer** (what would you ask for?). Merge their points into the report,
marked with who raised them. Do not let them rewrite text either.

## The report

Write it beside the manuscript (e.g. `integrity-check-YYYY-MM-DD.md`) or where the user asks. Lead with the verdict in one or two sentences, then:

1. **Blockers**: desk-reject triggers (fabricated/unresolvable reference, chatbot leftover, no AI disclosure
   where AI was used, over-length by 20%+, an AI author).
2. **Major**: what an editor or reviewer will object to.
3. **Minor**: calibration and style.
4. **Not assessed**: checks that could not run, and why.

Each finding: location (`file:line` or section), what is wrong, the rule with its source and date, and the
suggested change. Group repeated findings (one line for "14 references lack DOIs", with the list). End with
the cover-letter points the venue needs (AI use, how the work differs from formulaic papers, validation).

Applying fixes is a separate step, done only when the user asks: use the `manuscript-journal-adapt` skill
(its contract and `guard.py` keep content intact), follow the project's own revision-marking rules if it
has them, and log the pass, because rewritten prose counts toward the AI-use disclosure.

## Files

- `scripts/scan.py`: the mechanical scan (PEP 723; runs with `uv run --script`, needs network only for `--online`).
- `references/publisher-policies.md`: ICMJE, COPE, WAME, STM, OUP/*Bioinformatics*/NAR/GigaScience, Springer
  Nature/BMC, Elsevier/Cell, Wiley, T&F, Sage, PLOS, Frontiers, MDPI, Science, eLife, BMJ, JAMA, IEEE, ACM;
  2026 enforcement timeline; checkable rule list (§6).
- `references/venues-and-preprints.md`: arXiv, bioRxiv/medRxiv, SSRN, OSF, ICLR, NeurIPS, ICML, ACL/EMNLP,
  AAAI, CVPR; hallucinated-reference audits.
- `references/screening-signals.md`: the tools editors run and every signal with its source; detector
  reliability and false positives.
- `references/target-journals.md`: Genome Research, Database, Scientific Data, CSBJ, iScience, PeerJ, F1000Research,
  Genome Biology/Medicine, PLOS Comp Biol, GigaScience (incl. its 2026 board situation), the EuroTech AI Research
  Summer competition ("EASRP").
- `references/ai-science-design.md`: design review for AI-scientist papers, with the verified evidence base.
- `references/notes-factcheck.md`: claim-by-claim check of a widely shared 2026 research brief on AI-scientist papers.
- `references/venues.yaml`: machine-readable venue rules (AI policy, disclosure, screening, limits) used by `--venue`
  here and by `manuscript-journal-adapt/scripts/venues.py`.
- `references/disclosure-templates.md`: AI-use statements per venue, and the contribution table.
- `references/kobak_2024_style_words.csv`: the 379 excess style words of 2024 (Kobak et al., *Sci Adv* 2025).
