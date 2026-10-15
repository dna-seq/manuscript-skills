---
name: manuscript-integrity-check
description: >-
  Review a manuscript or its references for concrete scientific and submission problems, prioritising
  publication and low author burden. Check citation identity and support, unsupported claims, unfinished
  content, and applicable venue requirements. Use for a requested manuscript audit, reference check or
  submission-readiness review. Use manuscript-journal-select for journal selection and
  manuscript-journal-adapt for editing, formatting and drafting AI-use statements.
  Use manuscript-policy-fit for clinical-scope, ethics, privacy and
  regulatory applicability, including authors' voluntarily public personal genomes or biomedical data.
---

# Manuscript integrity check

Help the authors publish a sound manuscript in a suitable journal with the least avoidable work. Read
`references/author-priorities.md` for the shared priorities, scope and disclosure rules. This skill reports
findings; apply fixes too when the user's request already includes them.

## Ground rules (read before anything else)

1. **Improve publication prospects.** Concentrate on evidence, clarity, fit and actual submission barriers.
   Style and detector signals do not establish authorship or misconduct. Do not invent compliance or
   suggest changing prose merely to obtain a detector score.
2. **Keep review and editing distinct.** For a review-only request:
   - findings say **where**, **what is wrong**, **which rule** (with source), and **what kind of change**
     ("cut the phrase", "give the measured number from Table 2", "add the DOI 10.xxxx after checking");
   - mechanical fixes are fine to write out in full: a corrected DOI, a deleted chatbot leftover, a missing
     identifier, a reference entry rebuilt from Crossref metadata;
   - do not replace paragraphs unless editing is also requested. For authorised edits, use the companion
     skill's content-preservation contract and apply the selected venue's disclosure exemptions;
   - preserve existing revision markers, but do not audit provenance or create a ledger unless requested.
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

Use existing context first. A focused citation or passage check does not need every input below.

- **The manuscript** (Markdown, LaTeX or text; convert `.docx` or a Google Doc export with `pandoc -t gfm`).
  Scan the source the authors edit, not a rendered PDF. If the project marks who revised what in the text
  (HTML-comment revision markers such as `<!-- @rev ID rounds=N by=name:date -->`), keep the markers in: the
  scanner strips comments for prose checks but counts AI revisers.
- **What AI did**, when a disclosure or policy decision depends on it. Use the authors' account; do not reconstruct it from git. Many manuscripts are not in git,
  and an AI co-author trailer often marks automation (syncing co-authors' comments from a drive, formatting)
  rather than writing. `--git` exists for authors who ask for a commit inventory; its count is a question
  to put to them, not evidence.
- **Target venue(s).** Infer from the text, the folder or the conversation; a general review can proceed without one. The
  disclosure, length and availability rules differ by venue, and one statement does not fit all (one publisher no
  longer requires disclosure of writing help, another wants it documented in the supplement).
- **Paper type**: (a) a system or tool, (b) a finding, (c) an evaluation; and whether AI produced any of the
  scientific content or is itself the subject of evaluation. AI-assisted coding alone does not turn a
  conventional study into an AI-scientist benchmark. This decides which parts of Step 4 apply.

## Workflow

Select the checks needed for the request. A full submission audit can use all relevant steps; do not run
this sequence for every small edit or repeat completed checks over unchanged material.

### Step 1: mechanical scan

```bash
uv run --script scripts/scan.py PAPER.md --online \
    --venue <venue-key> --md /tmp/scan.md --json /tmp/scan.json
```

`--online` resolves every DOI, PMID and arXiv id (title and first-author match, Retraction Watch retractions and
expressions of concern via Crossref, PubMed's "Retracted Publication") and looks up references that carry no
identifier in Crossref. `--venue KEY` checks the length limits recorded in `references/venues.yaml`. `--git`
(only when the authors ask) counts commits touching the file that carry an AI co-author trailer. Exit code 1
means at least one blocker. It finds: chatbot leftovers and chat-interface markup (arXiv ban triggers),
placeholders and TODOs (including inside HTML comments, which still ship), missing declarations, AI mentions
without a disclosure, AI-revised ledger segments, citation/bibliography mismatches, overclaim words, stock
phrases, tortured phrases, sourced vocabulary densities, participle tails, em-dashes, abstract numbers that
never reappear, no archived software DOI, leave-one-out validation.

Read every blocker and major finding in context before reporting it: the scanner has false positives (a
module named "Superhuman", "discovery" as a software term, a conference name read as an author-year
citation). Omit false positives from the author-facing report; explain discarded hits only if useful.
Script severities are provisional. Mentions of AI, missing model versions, style counts and absence of
generic declarations do not by themselves establish a submission barrier.

### Step 2: references beyond identity

The scanner can resolve a reference's identity; it does not prove **support for the sentence** (ICMJE V,
Springer Nature's irrelevant-reference checker, Signals, Paperpal). For each claim that carries the paper
(the abstract's claims, every number taken from another paper, every "first"/"only"), open the cited abstract
(E-utilities `efetch`, Europe PMC, Crossref, or whatever literature tools are connected, e.g. a PubMed MCP
server) and confirm it says what the sentence says. Also flag: citations
of reviews where the original is meant, retracted works cited as support, missing DOIs (SN/BMC ask for them),
data and software cited without a persistent identifier, and heavy self-citation (report the share; no
published threshold exists).

### Step 3: venue compliance

For human-data, ethics, privacy, clinical-scope or regulatory applicability questions, use the focused
`manuscript-policy-fit` workflow. Distinguish wording ambiguity from an actual study requirement; do not
infer a need for new approval from human-data mentions or a missing declaration alone. It explicitly
covers authors' own deliberately public genomes and biomedical records.

Look the venue up in `references/publisher-policies.md` (journals) or `references/venues-and-preprints.md`
(arXiv, bioRxiv/medRxiv, ML conferences), then re-fetch the live page (ground rule 5). Check:

- **AI disclosure**: present, in every place the venue asks (cover letter, Methods, Acknowledgements, a
  titled declaration, the supplement, figure captions), with the fields it asks for: tool **and version**,
  dates, what it did, which sections, and how the authors verified the output, **only where required**.
  Check whether AI-assisted **code** needs a Methods description under this venue's policy. Draft from
  `references/disclosure-templates.md`, filled with facts the user confirms; never guess what a tool did.
- **Author list** has no AI; no AI output cited as a primary source.
- **Availability**: apply the venue's requirements for this article and stage. Check relevant code/data
  links and reproduction information; do not demand a DOI, repository deposit or new test dataset when
  neither the paper's reproducibility nor the venue requires it.
- **Limits and structure**: abstract and body length, abstract headings, article-type rules. Some journals
  return manuscripts 20% or more over the limit without review (`over_limit_return` in `venues.yaml`).
- **Validation and affordability**: record actual independent-cohort, biological-validation or other
  expensive study requirements, including scope and permitted computational alternatives. Surface an
  unmet requirement early as a possible venue no-go under the author's budget, and use
  `manuscript-journal-select` to find feasible alternatives. Do not silently turn it into a new experiment
  for the author or confuse an independent existing dataset with new recruitment.
- **Figures**: distinguish primary data, research image processing and illustrations; apply the selected
  venue's actual rules and preserve accurate representation of the data.
- **Preprint overlap**: check the relevant venue's preprint and simultaneous-submission rules. Check a
  preprint server's current limits only if posting there is part of the task.

### Step 4: AI-generated science (only when AI produced scientific content)

Use only the claim-relevant parts of `references/ai-science-design.md`. Distinguish an evaluation of an
AI system from a biological finding obtained with AI assistance. Do not prescribe pre-registration,
extra cohorts, fixed run counts, ablations or human-rating studies as a package. When evidence is
insufficient, identify the inference at risk and offer narrower wording or an appropriate venue as well
as additional work. Ask authors for new analyses only when the missing evidence warrants them.

### Step 5: calibration and voice

Check every priority or utility claim ("first", "novel", "only", "scalable", "seamless", "robust") against a
comparison or measurement in the paper; every "we show" against a result; the limitations for specificity
(a named risk with its consequence, not "further work is needed"). Report stock phrases and vocabulary density
only when they impair clarity or conflict with the requested house style. Do not list every vocabulary
hit in a submission audit. Respect existing style guides and writing rules in CLAUDE.md / AGENTS.md.

### Step 6: optional independent passes

When the user requests independent reviewer passes, optionally use reviewer agents, each given
the manuscript and the venue page: a **desk editor** (would you send this out for review? name the reason
you would not) and a **methods reviewer** (what would you ask for?). Merge their points into the report,
marked with who raised them. Do not let them rewrite text either.

## The report

Return a concise report; save a separate file when requested or established by the project. Lead with
the paper's readiness and the smallest next steps, then:

1. **Blockers**: confirmed defects or verified applicable submission barriers.
2. **Major**: concrete threats to validity or the paper's prospects.
3. **Optional**: useful improvements, with their likely benefit and effort.
4. **Uncertain / not assessed**: material checks that could not run, and their consequence.

Each finding: location (`file:line` or section), what is wrong, the rule with its source and date, and the
suggested change. Distinguish journal rules from methodological advice and preferences. Group repeated
findings and omit irrelevant checks. Add cover-letter points only when needed for this submission.

When fixes are authorised, use the `manuscript-journal-adapt` skill
(its contract and `guard.py` help check content preservation), follow the project's own revision-marking rules if it
has them. Add no per-pass log; update a disclosure only when the venue requires it and its factual
account needs to change.

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
