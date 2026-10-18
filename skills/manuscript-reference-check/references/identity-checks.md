# Identity checks: what the scanner records and how to read it

`../manuscript-integrity-check/scripts/scan.py --references-only` is the one implementation of the
reference identity checks; a full integrity audit runs the same code. This page explains its JSON, how to
read its findings without accusing anyone, and how to merge an independent paper-preflight run.

## What `--online` does for each entry

1. **Identity.** A DOI goes to Crossref, then DataCite (datasets, software, Zenodo and other data DOIs),
   then doi.org for any other registration agency. A PMID goes to PubMed, an arXiv id (or a
   `10.48550/arXiv.` DOI) to arXiv. An entry with no identifier, or with one that does not resolve, is
   searched in Crossref by its text; the best match is a candidate, never a confirmation. For an
   identifier that does not resolve, a strong candidate (same title and first author) makes the finding
   major with the candidate DOI, since a typo is the usual cause; no good match leaves a blocker to check
   by hand. The resolved title and authors are compared with the entry; a different title or first author
   makes the entry a `mismatch`. An entry that names no author gets an info note, not a mismatch.
2. **Retraction, in two registries.** Crossref (which carries the Retraction Watch database) or PubMed
   answers first; unless that already found a retraction, Europe PMC answers second (PubMed's records,
   including papers with no DOI). A notice from either wins. Crossref and PubMed each miss retractions the
   other records, so one clean answer does not end the search.
3. **Preprints.** A preprint that has been published is found from Crossref's `is-preprint-of` relation,
   the bioRxiv/medRxiv record's `published` DOI, or arXiv's DOI and journal reference. An arXiv comment
   that names a venue ("Accepted by EMNLP 2023") triggers a Crossref title search; that result is a
   candidate to confirm (`published_version.source` is `arxiv:comment` or `crossref:title-search`, with
   the comment in `published_version.comment`), not a registry link. The published record is then read
   and compared (title similarity, shared authors, its own retraction state).
4. **Withdrawals.** arXiv records a withdrawal in the version comment; bioRxiv and medRxiv in the latest
   version's title or abstract. A comment saying a withdrawal was a mistake is not a withdrawal.
5. **Authors beyond the first.** Where the record lists authors, the citation's author list (the text
   before its title) is compared with it: names on the record missing from the middle of the citation's
   list, names in the citation not on the record, a list shortened without "et al.", and differing initials.
6. **Every identifier, and the url.** A BibTeX entry that carries several identifiers (a DOI and a PMID,
   an arXiv eprint, a `url` on doi.org, arxiv.org or PubMed) has each one resolved: one that does not
   resolve, or that names a different work than the first, is major. A `url` that is none of these is
   checked by its status (HEAD, then GET): dead is major; refused (401, 403) or unanswered is a note to
   open by hand. A DOI that neither Crossref nor DataCite holds gets its title from doi.org's record of
   the agency that registered it (mEDRA, JaLC, ...); an agency that gives no record is not assessed.
7. **Titles, strictly.** Above the fuzzy match, a BibTeX entry's title is also compared exactly once LaTeX,
   HTML, accents, case and punctuation are set aside; a difference is minor, with a hint when one title is
   the other plus a subtitle. An entry with an identifier but no title field is a minor finding naming the
   work the identifier points to.
8. **Identifiers in the text.** Outside the reference list, `doi:`, doi.org and arXiv links, `PMID`,
   `arXiv:` and bare URLs in the prose (not in code, comments or verbatim) are resolved and listed with
   the title each resolves to (`inline_ids` in the JSON, "Identifiers in the text" in the report) for a
   person to read against the sentence; no match is attempted. One that does not resolve is major.

Offline, two checks still run: a BibTeX entry that does not parse is a major finding (it was not read,
and the entries after it may be missing), and a sentence with a number and a live cue ("currently", "as
of", "to date", "now") but no year is flagged `undated`.

**Exit codes** (`scan.py`): 0 clean; 1 a blocker; 3, with `--online`, no blocker but at least one lookup
that did not answer (an entry, a further identifier, a url or an identifier in the text), so the run is
not clean; 2 usage. **`--unidentified strict`** (the default) keeps an entry with no identifier at minor
or above even when Crossref finds a close match, which stays a candidate to confirm; `--unidentified lax`
lets a close match fall to info. PubMed requests name the tool and nothing personal; Crossref's polite
pool header carries a placeholder address, never a person's.

## The JSON fields per reference

Earlier fields keep their names and meaning; these were added.

| Field | Values |
|---|---|
| `status` | `resolved`, `mismatch`, `unresolved` (the registry answered that the identifier does not exist), `retracted`, `concern`, `no_identifier`, `lookup_failed` (no registry answered), `not_checked` (offline) |
| `retraction` | `retracted`, `concern`, `none_found` (the registries asked hold no notice), `not_checked` (offline, arXiv, DataCite, no identifier, or no registry answered). `not_checked` is never clean. |
| `retraction_source`, `retraction_notice` | which registry answered (`crossref (retraction-watch)`, `crossref+europepmc`, `pubmed`, `europepmc`) and the notice's DOI or citation |
| `is_preprint`, `published_version` | the published version's DOI, venue, year, how it was found, `title_similarity`, `shared_authors`, its `retraction`, and whether its record was read (`metadata_checked`) |
| `withdrawn`, `withdrawn_source` | `true`/`false` where arXiv or bioRxiv/medRxiv was asked; `null` = not checked |
| `resolved_authors`, `author_check`, `author_notes`, `author_severity` | the record's list; `consistent`, `differs` or `not_compared`; what differs; `minor` or `info` |
| `lookup_notes` | which registry did not answer, and what was therefore not checked |
| `cited_title`, `title_check` | a BibTeX entry's title as cited; `same`, `differs` (passes the fuzzy match, not the strict one), `no_title`, `not_compared` |
| `other_ids`, `other_id_checks` | the entry's further identifiers (`pmid:123`), and for each its `state` (`ok`, `dead`, `unknown`), `title`, `why` and `same_work` |
| `url`, `url_status` | a BibTeX `url` that is no DOI, arXiv or PubMed link, and its answer: `ok HTTP 200`, `dead HTTP 404`, `blocked HTTP 403`, `unknown: ...` |

The report also carries `inline_ids`: each identifier in the text with its `line`, `kind`, `id`, `state` and
`title`.

The Markdown report adds a line with the counts per retraction state. Report a `not_checked` entry to the
authors as "the retraction status could not be checked", with the reason (arXiv keeps no retraction record;
no registry answered), and check by hand any that carry the argument.

## Reporting an identity finding to the authors

Quote the reference-list entry as it stands, give the record it should match as a link
(`https://doi.org/...`, `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`, `https://arxiv.org/abs/<id>`), and say in
a sentence or two what differs and what to change, as [Writing for the authors](../../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)
asks. For example: "The entry for Tandy-Connor et al. 2018 gives the DOI 10.1038/gim201838, which does not
resolve. The article is at https://doi.org/10.1038/gim.2018.38, with the same title, journal, volume and
pages, so the DOI is missing a dot." The scanner's status names and paper-preflight's rule codes may follow
in parentheses; they never stand alone.

## Reading findings without false accusations

Registries are wrong too, and versions differ. Before reporting an identity finding, open the record the
message names and compare. These are the usual false alarms (the paper-preflight project documents the
same causes from its measurements on real papers):

- **A registry list that stops short.** Crossref lists only "Ng" for the SIFT paper (Ng and Henikoff,
  *Nucleic Acids Res* 2003). The scanner notes a record shorter than the citation but does not flag it.
- **Versions.** Titles, author lists and numbers change between a preprint and its publication, and between
  editions. The PGS Catalog preprint has 12 authors, its journal version 13.
- **Names.** Transliterations (Müller, Mueller, Muller), dropped diacritics (Varré, Varre), particles (van der,
  de la), initials against given names, two-letter surnames (Ng, Li, Xu), group authors and consortia.
- **Dates.** Online-first against issue year; a conference paper dated by the meeting.
- **Works the indexes miss.** Theses, reports, standards, software manuals, regional journals, very new and
  very old works. No identifier and no Crossref match is `unverified`, not fabricated: search PubMed and the
  publisher by title, journal, volume and pages before calling a reference invented.
- **A preprint cited on purpose,** for content the published version dropped. Say so and keep it.
- **A retracted work cited to discuss the retraction.** Correct as it stands.

A failed lookup (`lookup_failed`, a timeout, a 429) is never evidence against a reference. A difference in
authors is a metadata question for the authors to check against the publisher's page, never evidence of
fabrication. Reserve "possibly fabricated" for an identifier that does not resolve or a work no source holds
after searching by title and by journal, volume and pages, and still say what was searched.

## An optional independent cross-check: paper-preflight

[paper-preflight](https://github.com/amos689/paper-preflight) (MIT) is an independent, deterministic reference
checker with no language model in its verdicts. Its README reports, for version 1.0, 0.79 false alarms per 100
references on three held-out weeks of arXiv papers (cs, stat, q-bio, quant-ph, astro-ph). That is its own
measurement; a life-science bibliography may differ. It is not a dependency of this skill: offer it when
the authors want a second opinion, a SARIF report for CI, or checks this scanner lacks.

```bash
uvx paper-preflight check path/to/paper            # a project directory, main .tex, .bib, .docx, .md/.qmd, .typ,
uvx paper-preflight check references.txt           # or a plain reference list; '-' reads stdin
uvx paper-preflight check path/to/paper --format json > preflight.json
uvx paper-preflight explain REF015                 # what a rule checks and when it can be wrong
```

Exit codes: 0 nothing at or above `--fail-on`; 1 blocking findings; 2 a source was unavailable, so the run is
incomplete; 3 usage error; 4 internal error. `--offline` uses only its local cache. It sends the cited works'
metadata to public registries; the manuscript stays local (per its README). Its MCP server
(`uvx --from "paper-preflight[mcp]" paper-preflight mcp`) offers the same check and `preflight_cited_passages`,
which returns the best passages of a cited work for an agent to judge by the protocol in `claim-support.md`.

What it adds: dblp, OpenAlex and (with a key) Semantic Scholar beside Crossref, DataCite, arXiv and PubMed;
books through Open Library; GitHub, PyPI, CRAN and OpenML existence for software and data in the reference
list (REF019; Hugging Face is consulted but never reported missing, since it hides private repositories); dead links without an archived copy (REF021); invented venues (REF020); year, venue
and title field differences (REF012 to REF014); identifiers written so that links break (REF017); duplicate
and near-duplicate entries (CIT002, CIT004); and `bib fix`, which proposes `.bib` edits as a diff.

### Merging its findings with ours

- Key both reports by reference (line or cite key, then DOI). One root cause gives one finding.
- Positive evidence outranks an abstention: a retraction notice from either tool stands; an entry one tool
  resolved and the other could not find is resolved, with a note.
- REF090 ("cannot determine") and an incomplete run (RUN001, exit 2) mean the entry could not be checked;
  never count them as passed.
- REF015 (preprint published) is our `published_version`; REF018 (arXiv withdrawn) is our `withdrawn`;
  REF004 and REF005 our retraction states; REF010 and REF011 our author differences: a question to check,
  not fabrication.
- REF003 (not found in any source, every source answered) is strong evidence, not proof; check by title,
  journal, volume and pages before reporting a reference as invented.
- Its `support` "confirmed" is a located passage, to be read like `quote_located`; its "could not confirm"
  is never `rejected`.
- Apply `bib fix` changes only when the authors ask, as a reviewed diff, and verify each changed field.

## Boundaries

- Reference-list entries, including data and software citations there, belong here. Accessions, DOIs and
  links in availability statements and Methods belong to manuscript-reporting-check
  (`../../manuscript-reporting-check/scripts/check_availability.py`).
- Journal reference style (punctuation, abbreviations, ordering) belongs to manuscript-journal-adapt.
