---
name: manuscript-reference-check
description: >-
  Verify manuscript citations and bibliography entries: source identity, identifier and metadata matches,
  retractions, citation consistency, and whether cited sources support the claims. Use for reference
  checks, citation fact-checking or bibliography repair. Use manuscript-integrity-check for a full
  submission audit and manuscript-prose-edit for general language editing.
---

# Verify references and their support for claims

Read the shared [author priorities](../manuscript-integrity-check/references/author-priorities.md). Use
the supplied manuscript, bibliography or citations and existing context. A reference check does not
require a target journal, AI-use history or a full submission-readiness review. Apply reference fixes
when the request includes them; for review-only requests, report findings without rewriting paragraphs.

## Check identities and citation consistency

The bundled scanner provides a focused mode shared with full integrity audits. Commands below are
relative to this skill directory:

```bash
uv run --script ../manuscript-integrity-check/scripts/scan.py PAPER.md --references-only --online \
    --md /tmp/references.md --json /tmp/references.json
```

Omit `--online` for offline citation/bibliography consistency checks. Markdown, plain text, LaTeX with
its linked `.bib` files, and standalone `.bib` files are supported. For Word or Google Docs, use an
available document tool or export first. Run against the source the authors edit where possible.

The scanner resolves DOI, PMID and arXiv identifiers, compares available title and first-author metadata,
checks recorded retractions and expressions of concern, and searches Crossref for entries without an
identifier. It also checks recognised in-text citations and LaTeX citation keys against the bibliography.
It does not check journal formatting or establish that a source supports a sentence.

Read each finding in context and omit false positives. Verify consequential findings against primary
publisher, DOI-registration, PubMed or repository records; reuse a current verification of unchanged
material. A failed lookup does not establish fabrication. Try another authoritative route and label
what remains **unverified** or **not assessed**, with the reason. Do not demand identifiers that the work
does not have, or present a candidate Crossref match as confirmed before comparing its metadata.

## Check support beyond identity

For the claims within scope, open the cited abstract or full text and compare the source with the exact
sentence. Prioritise the claims carrying the paper, the abstract's claims, borrowed numbers and
"first"/"only" claims. Use full text when the abstract does not establish the relevant result, population,
method or limitation. An inaccessible source leaves support unverified.

Distinguish a correct source with overstated wording, a citation to the wrong work, and a claim with no
supporting citation. Check whether an original study is needed instead of a review, and whether data or
software have an appropriate persistent record. Flag retracted work used as evidence; citing a work to
discuss its retraction is a different case. Report heavy self-citation only when useful, without inventing
a universal threshold.

Never invent a source or fill missing metadata from memory. Verify replacement references and corrected
identifiers before proposing them. Bibliography repairs can be written out in full during a review;
changing a substantive claim requires authorisation to edit that claim.

## Report the actionable result

Give the citation or location, what was verified, the identity or support problem, its authoritative
source, and the smallest correction. Distinguish metadata mismatch, retraction/concern, citation
inconsistency, unsupported claim and unresolved lookup. State the coverage and material access limits;
the mechanical report alone does not establish that every citation supports its sentence.

A full `manuscript-integrity-check` audit includes these checks when relevant. Keep the companion skills
together so the focused check and the audit use one scanner implementation.
