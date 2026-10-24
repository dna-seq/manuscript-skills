# Submission package: reading `hygiene.py`

The files a venue or preprint server receives can publish more than the PDF shows. arXiv offers every LaTeX
source for download; journals and preprint servers publish supplementary files as uploaded; reviewers open
the Word file or the PDF with tools that read text a person cannot see. `scripts/hygiene.py` lists what to
look at in those files. The script itself only reports; what the agent then changes follows the `edits` setting
(see [Reporting](#reporting)).

Run it on what will be uploaded (the directory, the archive or the files), late, after the last edit, with
`--final` once the authors say they are about to submit:

```bash
uv run --script scripts/hygiene.py submission/ --final --md RUN/manuscript-integrity-check/hygiene.md \
    --json RUN/manuscript-integrity-check/hygiene.json
```

Exit codes: 0 nothing that counts now; 1 text hidden for AI reviewers or a leaked secret, at any stage, and with
`--final` any blocker or major finding; 2 usage error. On a draft (no `--final`), the other findings are listed
under "Before submission, once the code is final" and do not change the exit code.

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
| Revision marks (`<!-- @rev ... -->`, `% @rev ...`), with the editors their `by=` entries name | LaTeX, Markdown, HTML, text | major |
| With `--anonymous`: author names and affiliations outside the references, e-mail addresses, ORCID iDs, acknowledgements, first-person self-citation, repository URLs, camera-ready template options, metadata | everything above | major or minor |

White text on a coloured box or table cell is visible and is not reported unless it addresses a reviewer.
`\phantom{00}` spacers and other hidden runs under four words are ignored. LaTeX `\%`, `\verb` and `\url`
arguments are not comments, and `%` inside `verbatim` environments is code. Revision marks are reported once per
file, as revision marks rather than comments: the files a venue receives are always the clean copy or a build from
it (`manuscript-revision-marks` writes it), never the marked master, whose marks say who revised each passage, an
AI model included.

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

Report blockers and majors by quoting the line as the script shows it (masked secrets stay masked) and naming
the file and the section or figure it sits in, with the line number only in parentheses. Give the smallest fix in
a full sentence: delete the line, strip the metadata (`exiftool -all= FILE`), clean the source (a cleaner such as
`arxiv_latex_cleaner` or ALC-NG, then rerun this check on its output), upload the clean copy without revision marks.

What the agent changes follows the `edits` setting, with these rules:

- **Cleaned copies only at the end.** Clean copies of the upload files (comments stripped, metadata removed,
  marks gone) are made only when the authors say they are about to submit, beside the originals, never on a draft
  (they would go stale and add files to track); the originals and the master are never rewritten for this.
- **Hidden text for AI reviewers at any stage.** Remove it from the master under `edits` (shown before and after,
  and recorded) whenever it is found; under `propose` it is the first proposal.
- **A leaked key needs the authors.** Deleting it from the files does not undo the exposure: a key that was ever in
  a shared file must be revoked or rotated by its owner. Say this once, plainly; it is the one step the agent
  cannot take.

These findings go in the report's last group, "Before submission, once the code is final", because the upload
files are cleaned once, after the last edit; for a draft they are not blockers. Two go under "Fix now" whatever
the stage: hidden text addressed to an AI reviewer, and a leaked secret. `precommit.py --hygiene` fails a commit on
the same two and keeps ordinary draft comments advisory.
Describe a check by what it found ("a LaTeX comment that reads as a note to a co-author"), not by the script's
check name.

## Sources

The checks follow the designs of pachterlab/paperpush (`hidden_text.py`, `sensitive.py`, `anonymity.py`;
BSD-2-Clause) and THUROI0787/absent-author (`pdf_hidden_text.py`; MIT). The patterns and code here are
written for this plugin.
