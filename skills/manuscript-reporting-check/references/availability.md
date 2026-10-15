# Data, code and software availability

What `scripts/check_availability.py` checks, how to read its states, and what remains for you to judge.

## Run it

```bash
uv run --script scripts/check_availability.py PAPER.md --venue KEY --md SCRATCH/avail.md --json SCRATCH/avail.json
uv run --script scripts/check_availability.py PAPER.md --venue KEY --online   # look every identifier up
```

Offline it extracts and classifies; `--online` asks each public archive whether the record exists. Only
public identifiers leave the machine (accessions, DOIs, repository and package names), never manuscript
text. `--github-auth` sends `$GITHUB_TOKEN` to GitHub when the unauthenticated limit (60 requests an hour)
runs out; ask before using it. `--record manuscript-record.yaml` reads the venue from the record. Exit
code 1 means at least one major finding. Write the outputs to a scratch location, not beside the manuscript.

## What it extracts

Outside the reference list (citations there belong to `manuscript-reference-check`), and from comments
removed: GEO (GSE, GSM, GPL, GDS), SRA/ENA/DDBJ runs, experiments, samples and studies (SRR, ERR, DRR,
SRX, SRS, SRP and their E and D twins), BioProject (PRJNA, PRJEB, PRJDB), BioSample (SAMN, SAMEA, SAMD),
ArrayExpress (E-MTAB and other E-XXXX), BioStudies (S-BSST, S-BIAD), dbGaP (phs), EGA (EGAS, EGAD and the
other EGA prefixes), PDB IDs (only next to "PDB" or in an RCSB or PDBe link), GWAS Catalog (GCST), PGS
Catalog (PGS), Zenodo, figshare, Dryad and OSF DOIs and links, Zenodo record numbers in prose ("Zenodo
records 18370498 and 19487816", read as their DOIs), Software Heritage IDs, any other DOI inside an
availability statement, GitHub, GitLab, Bitbucket, Codeberg and SourceForge links (with the release, tag
or commit cited in the link or next to it), anonymised review links (anonymous.4open.science), PyPI, CRAN,
Bioconductor, Bioconda and conda-forge packages (from links, install commands and phrases such as
"Bioconductor package X"), Docker Hub, Quay and GHCR images, Hugging Face datasets, models and Spaces
(from links, and from prose: "Hugging Face dataset org/name", "the org organization on Hugging Face (a,
b)", whose type the lookup tries in turn), and RRIDs.

Look-alikes are left alone on purpose: GSEA, GPL-3.0 and GPLv3 (licences), SRP54, ERP29, DRP1 and SRA1
(gene symbols), PHS 398 (an NIH form), "PDB format" and "PDB 2023".

**Whose identifier it is decides the checks.** Licence, release and cited-version checks run on the
authors' own code: anything in an availability statement, code under an owner a statement names (an
organisation link counts), a package named like one of those repositories, and, when no statement names
code, code outside tables. Everything else (a tool in a comparison table, software the paper only cites,
an ID the text excludes, as in "excluding PGS000085") is `context`: checked for existence only, and a
`not_found` there is optional. The identifier table's `where` column shows which applied; correct it in
your report when the guess is wrong.

## States

| State | Meaning |
|---|---|
| `resolves` | The archive has a public record. The title is shown: check that it is the dataset the paper means. |
| `not_found` | The archive answered that no such record exists (or it was withdrawn, suppressed or made obsolete). |
| `restricted` | The record exists but access is controlled (dbGaP, EGA, a gated Hugging Face repository) or held until publication (a private GEO series, an unreleased PDB entry). Legitimate: not a defect. |
| `not_assessed` | No verdict, with the reason: offline, rate-limited, a refused request, an anonymised review link (never looked up), or an archive that gives the same answer for private and missing records (Hugging Face, Quay). Never counted as resolving. |

A malformed identifier is never looked up. One written with a separator ("GSE 12345") has an obvious
repair and is optional; one that cannot be an accession ("GSE1589O4", with a letter O) is major.

## Findings and what to do with them

- **`no-statement`, `empty-statement`**: no availability statement, or one that names nothing ("All data
  are publicly available."). Major: the reader cannot find anything.
- **`request-only`**: "available from the corresponding author upon request" with no stated reason.
  Major. Read only inside availability statements, and in Methods sentences that name what is shared;
  table rows, appendices and other prose are not availability claims ("loaded on demand" is not one).
  With a stated restriction (consent, third-party licence, a data access committee) it becomes
  `request-route` (optional): check that it says who decides, on what terms, and what remains public.
  Controlled access through dbGaP or the EGA is the standard route for individual-level human data and is
  never a defect; consent and privacy questions go to `manuscript-policy-fit`.
- **`in-article-only`**: "within the article and its supplementary files". Check that the underlying data,
  not only summary tables, are there.
- **`malformed-identifier`, `not-found`, `withdrawn`, `version-not-found`**: the identifier, record or cited
  version does not exist. Before reporting, check the spelling against the archive; a private record at
  submission is fine if the paper says so and reviewers have access.
- **`code-unversioned`** (optional) or **`no-archive`** (major when the venue asks for an archived copy):
  a repository link with no release, tag, commit or archived DOI. Online, the script adds whether the
  repository has any release or tag at all. The fix is a tagged release archived on Zenodo or Software
  Heritage, cited by tag and DOI. A data deposit (genomes on Zenodo) is not the code's archive.
- **`anonymised-code`**: code reachable only through anonymised review links, with no version or archive.
  Legitimate for double-blind review and `not_assessed` (never looked up); by acceptance the authors need
  the public repository, the release tag used and an archived DOI. Major only when the venue's recorded
  rule asks for an archive; then check on its live page whether that applies at submission or at
  acceptance. Do not infer the real repositories, by search or from context: if the authors want them
  checked before submission, ask them, and never name them in text meant for referees or editors.
- **`archive-unidentified`** (uncertain): a statement names an archive or code host ("published on
  Hugging Face") but gives nothing the script could look up there. Find the record or ask the authors.
- **`no-licence`** (online): GitHub or GitLab finds no licence file, so nobody may legally reuse the code.
  Optional advice unless the venue asks for an open-source licence. `licence-unrecognised` means a
  licence file exists but could not be classified: read it.
- **`abstract-availability`**: the venue wants the software location in the abstract (Bioinformatics'
  "Availability and Implementation") and the abstract has none.
- **`access-route`**, **`concept-doi`**, **`summary-statistics`**: optional refinements.

## Venue rules come from venues.yaml

`--venue KEY` reads the venue's `software`, `required_sections`, `other_desk_rules` and `open_science`
entries (in `../../manuscript-integrity-check/references/venues.yaml`) through
`../../manuscript-journal-adapt/scripts/venues.py` and prints them with their read date, plus
what the script derived from them: whether an archived copy, a licence, the location in the abstract or a
reporting checklist is asked for, whether "on request" is refused, and any availability period (the
Bioinformatics Application Note records "software available for 2 years"). These are dated research
notes: verify a rule on the live page before calling a finding a blocker, and record the date. Nothing
about a venue is hard-coded in the script.

When the venue keeps software available for a period, check where the code lives: a personal or lab
server and an unarchived web service are at risk; an archived release (Zenodo, Software Heritage) and a
package repository (CRAN, Bioconductor, PyPI, Bioconda) are not. A web service should not require
registration where the venue says so.

## What the script cannot judge

- Whether every dataset behind a figure or claim is covered. Walk the Results and figure legends and
  check that each dataset used or produced has a location in the statement.
- Whether a resolving accession is the right one: compare the archive's title, organism and sample count
  with the Methods.
- Whether the code in the repository reproduces the results: that is the reproducibility seat of
  `manuscript-peer-review` and, for benchmark numbers, `manuscript-integrity-check`'s numbers check.
- Install and run documentation, test data and per-figure instructions that a venue asks for: open the
  repository's README when the venue requires them.

## Boundaries

- `manuscript-journal-adapt` drafts and formats the venue's availability statement; this skill checks
  what it says and whether what it names exists.
- `manuscript-reference-check` checks the reference list, including data citations there.
- `manuscript-policy-fit` decides whether consent, privacy or ethics rules restrict sharing; this skill
  only checks that the statement gives the route the restriction implies.
- Never invent an accession, DOI, tag, licence or access route. Where the statement needs one the authors
  have not given, write `author input needed`.
