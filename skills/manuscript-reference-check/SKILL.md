---
name: manuscript-reference-check
description: >-
  Verify a manuscript's citations and reference list: that each entry is the work it names (identifier,
  title and authors), whether it was retracted, withdrawn or has an expression of concern, whether a cited
  preprint has since been published, whether in-text citations and the bibliography agree, and whether each
  cited source actually says what the sentence claims (confirmed, partial, rejected or blocked, with the
  supporting passage quoted). Use for reference checks, citation fact-checking, claim-to-source verification
  and bibliography repair, including data and software citations in the reference list. Use
  manuscript-integrity-check for a full submission audit (it calls this skill for references),
  manuscript-peer-review for a simulated referee panel (it sends "missing prior work" claims here to verify),
  manuscript-reviewer-response for answering referees (citations added in a revision are verified here),
  manuscript-reporting-check for accessions, DOIs and links in availability statements and Methods, and
  manuscript-prose-edit for language editing.
---

# Verify references and their support for claims

Read the shared [author priorities](../manuscript-integrity-check/references/author-priorities.md). Use
the supplied manuscript, bibliography or citations and existing context. A reference check does not
require a target journal, AI-use history or a full submission-readiness review. Apply reference fixes
when the request includes them; for review-only requests, report findings without rewriting paragraphs.

Apply the requested task across the whole paper unless the author specifies a narrower scope.
Follow the shared [workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
for requested section or stage review, before/after comparisons and optional interviews. When
`manuscript-record.yaml` exists beside the manuscript, reuse a recorded reference check whose material is
unchanged and add open issues there ([shared record](../manuscript-integrity-check/references/manuscript-record.md)).

## 1. Check identities and citation consistency

The scanner is shared with full integrity audits, so both use one implementation. Commands are relative to
this skill directory:

```bash
uv run --script ../manuscript-integrity-check/scripts/scan.py PAPER.md --references-only --online \
    --md /tmp/references.md --json /tmp/references.json
```

Omit `--online` for the offline citation and bibliography consistency checks. Markdown, plain text, LaTeX
with its linked `.bib` files, and standalone `.bib` files are supported; export Word or Google Docs first,
or use a document tool. Run against the source the authors edit.

Online, the scanner resolves DOI (Crossref, DataCite, doi.org), PMID and arXiv identifiers and compares
title and authors, including authors beyond the first. It checks retractions and expressions of concern in
two registries and records the result per reference as `retracted`, `concern`, `none_found` or
`not_checked`, with its source. It finds cited preprints that have since been published, and withdrawn
arXiv, bioRxiv and medRxiv preprints. Entries without an identifier, and identifiers that do not
resolve, are searched in Crossref; supplementary reference lists are read too. Entries run together in one
paragraph are read as one entry, so when the scanner garbles an entry or reports a cited work as missing, look
at how the list is written before reporting it. Read [identity-checks.md](references/identity-checks.md) for
the JSON fields and the usual false alarms before reporting any identity finding.

- Open the record a finding names and compare before reporting it. Registries cut author lists short and
  spell names their own way; versions differ. An author difference is a question for the authors, never
  evidence of fabrication.
- A failed lookup does not establish fabrication, and `not_checked` is not clean. Try another
  authoritative route (publisher page, PubMed, the repository) and report what remains as "could not be
  verified", with the reason and what was searched.
- For a published preprint, recommend the published version only after checking that it still reports
  what the manuscript borrows; numbers and author lists change between versions.
- An arXiv entry whose comment names a venue ("Accepted by EMNLP 2023") is a published preprint even with no
  DOI or journal reference on record: find the venue's version before reporting it as unpublished.
- Do not demand identifiers a work does not have, or present a candidate Crossref match as confirmed
  before comparing its metadata.

[paper-preflight](https://github.com/amos689/paper-preflight) is an optional independent cross-check the
authors can run (`uvx paper-preflight check path/to/paper`); it adds dblp, OpenAlex, book, software and
dead-link checks. It is not required. [identity-checks.md](references/identity-checks.md) says how to
merge its findings with these.

## 2. Check that the sources support the claims

Follow [claim-support.md](references/claim-support.md). In short:

1. **Choose and count.** Check every cited claim, or, in a long paper, first the claims the conclusions
   rest on, the Abstract's claims, borrowed numbers and "first"/"novel"/"only" claims (these follow the
   [priority-claim rule](references/claim-support.md#priority-and-absence-claims)). Record coverage as
   "checked N of M cited sentences", where M counts the sentences that carry at least one citation in any
   style (numbered, author-year or `\cite` keys), and say how the N were chosen.
2. **Locate the passage** in the source's full text and write a claims file (claim, location, reference,
   the verbatim passage, the source's text file or identifier).
3. **Run the mechanical gate on every quoted passage:** `uv run --script scripts/support.py claims.yaml
   [--online]`. It takes minutes for ten claims; skip it only when the report quotes nothing. The text need
   not be saved first: give the source as `doi:`, `pmid:`, `pmcid:` or `arxiv:` and run with `--online`,
   which fetches legal open-access text (Europe PMC, bioRxiv/medRxiv, arXiv); paywalled sources stay
   unavailable. A quote taken from a search snippet or a fetch tool's summary is not verbatim and does not
   count until support.py locates it in the source text. It reports `quote_located`, `quote_not_found`,
   `numbers_missing`, `polarity_mismatch` or `source_unavailable`; it never reports support.
4. **Read, then challenge what matters:** `confirmed` needs a verbatim passage that carries the claim as
   written; `partial` supports a weaker or narrower claim (give the narrowed wording); `rejected` means the
   source does not say it or says otherwise; `blocked` means the source could not be read and never counts
   as support. Send every `confirmed` on a load-bearing claim to one batched skeptic subagent whose default
   is reject; a `rejected` stands only after a second independent search of the source finds no support;
   `partial` and `blocked` need neither. Start these subagents yourself: they are part of this check, and the
   user need not ask for them. Only where the host cannot start subagents, do both in-context and say so.
5. **Name the traps:** a review cited for a primary study's number, a borrowed number that differs from the
   source, a retracted work used as evidence (citing it to discuss the retraction is fine), a population or
   setting the source did not study, and an abstract read in place of the full text.

Never invent a source or fill missing metadata from memory. Verify replacement references and corrected
identifiers with the same checks before proposing them. Bibliography repairs can be written out in full
during a review; changing a substantive claim requires authorisation to edit that claim.

## Requests from other skills

- **manuscript-integrity-check** (Step 2 of a full audit): run both parts on the claims that carry the paper
  and return the findings for its report.
- **manuscript-peer-review**: a "missing prior work" concern names works. Verify that each exists (identity
  check on a small reference list or `.bib` of just those works) and that it does what the concern says;
  return `verified` or `unverified` for each.
- **manuscript-reviewer-response**: verify every citation added or replaced in a revision, identity and
  support, before it enters the response letter.
- **manuscript-reporting-check** checks accessions, DOIs and links in availability statements and Methods
  (its `scripts/check_availability.py`); data and software citations in the reference list stay here.

## Report the actionable result

Write for the authors as [Writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors) says, and order the report
by [when each fix can be done](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done). Fix now: claims a source does not
support or only partly supports, borrowed numbers that differ from the source, retracted works used as
evidence, references that point to another work or do not resolve, and a published preprint whose numbers
the manuscript borrows. Once the journal is chosen: missing identifiers and reference style.

Write each finding as a short paragraph. Quote the manuscript sentence, or the reference-list entry, as it
stands and name its section. Give the cited work as a link (`https://doi.org/...`,
`https://pubmed.ncbi.nlm.nih.gov/<PMID>/`, `https://arxiv.org/abs/<id>`). Quote the source's passage or the
registry record and say where it sits. Say the outcome in words: "supported", "only partly supported: the
source says ...", "not supported: the source says ...", or "could not be checked: the full text is
paywalled". End with the smallest correction. For example:

> **The Introduction gives a number the source does not report.** The manuscript says "A further 29% of
> studies in that decade included only East Asian ancestry participants [1]." The cited study, Duncan et
> al. 2019 (https://doi.org/10.1038/s41467-019-11112-0), says in its abstract that "another 19% included
> only East Asian ancestry participants", so the sentence is not supported as written. Change 29% to 19%.

Then say in sentences how much was checked ("We checked 8 of the 30 sentences that cite a source, chosen
because the conclusions rest on them"), which sources could not be read and why, and what the retraction
search covered. Report heavy self-citation only when useful, without inventing a threshold. The mechanical
reports alone never establish that a citation supports its sentence.

## Files

- `scripts/support.py`: the mechanical quote, number and polarity gate for claim support, with optional
  open-access fetching (PEP 723; `uv run --script`).
- `references/claim-support.md`: the claim-support protocol, the claims-file format and the report.
- `references/identity-checks.md`: the scanner's reference fields, false alarms, and paper-preflight.
- `../manuscript-integrity-check/scripts/scan.py`: the shared identity and consistency scanner.
