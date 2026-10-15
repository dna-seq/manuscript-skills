# Submission package: reading `hygiene.py`

The files a venue or preprint server receives can publish more than the PDF shows. arXiv offers every LaTeX
source for download; journals and preprint servers publish supplementary files as uploaded; reviewers open
the Word file or the PDF with tools that read text a person cannot see. `scripts/hygiene.py` lists what to
look at in those files. It reports and never deletes or rewrites; the authors decide what to remove.

Run it on what will be uploaded (the directory, the archive or the files), late, after the last edit:

```bash
uv run --script scripts/hygiene.py submission/ --md /tmp/hygiene.md --json /tmp/hygiene.json
```

## What it checks

| Check | Where | Severity |
|---|---|---|
| Hidden text addressed to an AI reviewer ("ignore all previous instructions", "give a positive review") | LaTeX, Markdown/HTML, Word, PDF, Unicode tag characters | blocker |
| Other hidden text of four or more words: white or near-white (including colours defined near-white), under 2 pt, `\phantom`, zero-size or displaced boxes, invisible render modes, `display:none`, Word `w:vanish` | the same | major |
| Text addressed to an AI reviewer that is not marked up as hidden | any text | info (a paper may quote one); major in a PDF text layer, where colour cannot be read |
| LaTeX `%` comments that read as private notes (to a co-author, about a reviewer, "don't mention") | .tex | major |
| Other LaTeX comments with content; `\iffalse` and `comment` blocks with content | .tex | minor (major for a block with a private note) |
| Secrets: cloud, API and private keys, tokens, passwords in URLs or assignments | any text, Word, PDF | major, always masked |
| Editable Google Docs links; Google Drive links | any text | major; minor |
| Absolute paths naming a user account | any text | minor |
| Zero-width and text-direction characters | any text | minor |
| GPS position; author or owner tags in figures (EXIF, PNG text, XMP) | images (Pillow) | major; minor |
| Word comments; tracked changes; document author fields | .docx | major; info; info |
| With `--anonymous`: author names and affiliations outside the references, e-mail addresses, ORCID iDs, acknowledgements, first-person self-citation, repository URLs, camera-ready template options, metadata | everything above | major or minor |

White text on a coloured box or table cell is visible and is not reported unless it addresses a reviewer.
`\phantom{00}` spacers and other hidden runs under four words are ignored. LaTeX `\%`, `\verb` and `\url`
arguments are not comments, and `%` inside `verbatim` environments is code. Revision-ledger markers
(`<!-- @rev ... -->`) are not reported.

## Not assessed, never passed

- **PDF** needs `pdftotext` and `pdfinfo` (poppler-utils). With them the script reads the text layer, word
  sizes and positions, and metadata; it cannot read text colour, so white text in a PDF is checked in its
  LaTeX or Word source. Without poppler the PDF is listed as not assessed.
- **Figures** need Pillow, which `uv run --script` installs. Without it every image is listed as not assessed.
- **Legacy .doc**, unreadable archives and archives over 3,000 files are listed as not assessed.

## Why these matter

- **Hidden prompts.** The ICLR 2026 LLM policy (ICLR blog, 26 August 2025,
  https://blog.iclr.cc/?p=1046) calls an author's hidden prompt injection "an attempt at collusion", a Code
  of Ethics violation, and names desk rejection as one consequence of breaking that policy. Treat any hidden
  instruction to reviewers as a blocker, whoever added it and whatever the venue's own wording.
- **Source leaks.** Pennekamp et al., "Hidden Secrets in the arXiv: Discovering, Analyzing, and Preventing
  Unintentional Information Disclosure in Source Files of Scientific Preprints" (arXiv:2604.20927, 2026)
  examined the source files of 2.7 million arXiv submissions and found hidden information in nearly every
  one: unneeded files, embedded metadata and comments, including editable web-document links, API and
  private keys and whole Git histories. They report that existing cleaning tools miss some of it and offer
  ALC-NG as a stricter cleaner.
- **Anonymity.** Double-blind venues return or reject submissions that identify their authors; check the
  venue's own rule on acknowledgements, self-citation and repository links before treating a minor item as
  required.

## Reporting

Report blockers and majors with the file and line, mask nothing further than the script did, and give the
smallest fix: delete the line, strip the metadata (`exiftool -all= FILE`), clean the source (a cleaner such
as `arxiv_latex_cleaner` or ALC-NG, then rerun this check on its output), revoke a key. A key that was ever in a shared file should be revoked even
after it is deleted. Do not delete or rewrite files yourself unless the authors ask.

## Sources

The checks follow the designs of pachterlab/paperpush (`hidden_text.py`, `sensitive.py`, `anonymity.py`;
BSD-2-Clause) and THUROI0787/absent-author (`pdf_hidden_text.py`; MIT). The patterns and code here are
written for this plugin.
