---
name: manuscript-revision-marks
description: >-
  Maintain revision marks in Markdown and LaTeX manuscripts: which passages were rewritten, how
  often, by whom, and which AI edits still await human review. Use when marks already exist or the
  authors request traceability, linting, clean reading copies, revision reports, blind spots or a
  heat map. Build PDFs from clean copies and measure page limits. Marks are opt-in and do not
  establish what kind of AI use occurred. Use manuscript-mark-people to identify confirmed human
  reviewers and manuscript-reviewer-response for the response-letter ledger.
---

# Revision marks: who revised what, and what nobody has read

A mark records an accountability fact the manuscript otherwise loses: this passage was rewritten for
comment C3 (or ledger item R1.2), in two rounds, by these people or agents, on these dates. The marks
live in the master the authors edit; everything a reader, referee or build sees comes from the clean
copy without them.

**Marks are opt-in.** Use them when the manuscript already carries them, the project's own rules ask for
them, or the authors ask. Never introduce them into a project that does not use them (the shared
[author priorities](../manuscript-integrity-check/references/author-priorities.md) say why). The marks
record what happened; they never establish what kind of AI use took place, and an AI-use statement is
drafted from the authors' account (`manuscript-journal-adapt`).

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run. This applies to direct invocations too.

## The format

```markdown
<!-- @rev C3 rounds=2 by=anna:2026-09-25,claude:2026-10-10 -->
The rewritten text.
<!-- @/rev C3 -->
```

In a `.tex` file each mark is a comment line of its own: `% @rev C3 rounds=2 by=...` and `% @/rev C3`.

- **The id** names what the passage answers:
  - a comment: `C3`;
  - a review-ledger item from `manuscript-reviewer-response`, as the ledger writes it: `R1.2`, `R2.W1`,
    `Ed.P1`, `R2.P3b`;
  - a finding, when a finding of the run asked for the edit: its id, `IC-1`, `RF-3`. When an earlier
    run's segment in the file already holds that id, add the run's date as a last part: `IC-1.20261024`;
  - `N1`, `N2`, … (the next free number) for a revision nothing asked for: the authors' own rewrite, or a
    section's copy-edit round (below).

  An id opens with a capital letter, holds letters, digits, hyphens and dots, and has a digit somewhere.
  One comment answered in several places takes `C3a`, `C3b` (grouped as `C3`). Ids are unique per file.
- **A round** is one pass over the passage, writing it or approving it. **`rounds=`** counts them;
  **`by=`** lists `name:YYYY-MM-DD` for each, in order: whoever wrote or approved that round. Both are
  required; nothing else is allowed.
- Segments with different ids nest; marks inside code (Markdown) or verbatim (LaTeX) are examples.
- **The clean twin** is `<stem>.clean.md` (or `.clean.tex`) beside the master: the current master with
  its marks removed, byte for byte. Reviews, checks and builds read the twin, never the marked master;
  only the master is edited.
- **A blind spot** is a paragraph that no segment overlaps. A paragraph is a run of lines no blank line
  separates (a list or a table without blank lines is one); headings, YAML front matter, code and an
  image alone on its line are not prose.
- **An unreviewed segment** is one whose latest `by=` name is not a person's: an AI model or agent
  harness, or a name nobody has classified. Its text has not been read and accepted by a person since
  the agent wrote it.

## Who is a person: rev-marks.toml

The project lists its people in `rev-marks.toml` at the repository root (the tool looks from the
manuscript up to the git root and takes the nearest; `manuscript-mark-people` reads and writes the same
one). Every key is optional:

```toml
humans = ["anna", "tom"]   # people; outranks the agent list (a co-author named Claude or Luna)
agents = ["lab-bot"]       # more agent names or fnmatch patterns
unknown = "agent"          # what a name in neither list counts as; "human" to flip
```

The shipped [agent list](references/agent-names.toml) names AI model families (from the Artificial
Analysis Intelligence Index) and coding harnesses, with patterns for versioned names (`claude-*`,
`gpt-*`, `seat-*`, `*-bot`). **A name on neither list counts as an agent by default**, so an edit signed
by a model the list does not know yet still shows as unreviewed rather than passing as a person's;
`lint` warns once per such name. Build or extend `humans` with `manuscript-mark-people`, which proposes
the people it finds in the repository; the authors confirm them in one question among the end-of-run
decisions, and nothing waits on the answer.

**A person's round.** When the authors say a person has reviewed or approved passages, including a
bulk "accept all" relayed from a co-author, record it with `bump --by <their handle>` on each passage
it covers. That statement also confirms the handle as a person's: when it is not yet in `humans`, add
it in the same step, before the bumps, or every bumped passage would still read as unreviewed:

```bash
uv run --script ../manuscript-mark-people/scripts/people.py PAPER.md --write --confirm tom --force-name
```

(`--force-name` because the authors named the handle; the survey need not have found it.) It confirms
that one handle, nobody else. How co-authors discuss and agree on the text happens outside these
skills; the marks only record what the authors report.

## Commands

Relative to this skill directory; standard library only (`uv run --script`, no dependencies):

```bash
uv run --script scripts/rev_marks.py lint PAPER.md [--strict]       # exit 1 on an error (or warning)
uv run --script scripts/rev_marks.py strip PAPER.md                 # write PAPER.clean.md
uv run --script scripts/rev_marks.py strip PAPER.md --check         # exit 1 if the twin is missing or stale
uv run --script scripts/rev_marks.py report PAPER.md --blind --unreviewed --html PAPER.heatmap.html
uv run --script scripts/rev_marks.py bump PAPER.md C3 --by claude   # an agent's round, dated today
uv run --script scripts/rev_marks.py bump PAPER.md C3 --by anna    # anna reviewed it, as the authors say
```

The heat map is for the authors: write it beside the manuscript (or where they say), give its path, and
register it in the run, as the review draft and the build below are:

```bash
uv run --script ../manuscript-integrity-check/scripts/runs.py add RUN --skill manuscript-revision-marks \
  --file PAPER.heatmap.html --role other --name PAPER.heatmap.html
```

`lint` and `report` take `--config PATH` and `--unknown agent|human`. The heat map shades each
segment by its rounds and outlines and hatches the unreviewed ones. Exit codes: 0 clean, 1 errors (a
malformed or unpaired mark, a stale twin, an unknown id), 2 usage or a malformed `rev-marks.toml`, 3
could not run (a PDF or Word file among them: marks are read from the source). `strip` and `bump`
refuse a file whose marks do not lint, so a half-recognised mark never reaches the twin. `strip --out
FILE` writes the clean copy elsewhere (an improvement run's comparisons use it) and refuses the master
itself.

## Build the PDF and measure it

```bash
uv run --script scripts/typeset.py pdf PAPER.md --cap 8        # Markdown: pandoc to PAPER.tex, then tectonic
uv run --script scripts/typeset.py pdf PAPER.tex --cap 8       # LaTeX: tectonic alone
uv run --script scripts/typeset.py md PAPER.tex                 # LaTeX to a Markdown reading copy
```

- A marked master is built from its clean twin, and only when the twin is current; otherwise the
  build refuses and names the `strip` command. Marks never reach the PDF.
- The page count is read from tectonic's log and checked against `--cap` (the venue's page limit):
  over the cap is exit 1 with the count; a log with no page count under `--cap` is exit 3, never a
  pass. Report the measured length after every applied change that can move it, not a word estimate.
- The tool replaces or deletes only a PDF it wrote: each one gets a record beside it,
  `PAPER.pdf.typeset.json`, with its checksum. A PDF at the target without one, or changed since (the
  authors' own `main.pdf` beside `main.tex`), is never touched: exit 2 before anything runs. Build
  to another file then, `--out PAPER.typeset.pdf`, and measure that.
- A build that runs and fails deletes the PDF an earlier build of the tool left, so a stale PDF never
  reads as current. A build refused before it starts (marks that do not lint, a stale or missing clean
  twin) or one that could not run (a binary absent, tectonic unable to download its TeX bundle: exit 3,
  never a finding) leaves it and says it may not match.
- Every glyph the fonts lack (XeTeX drops it silently) is a warning with its code point; `--strict`
  makes it exit 1. Markdown builds use DejaVu fonts, which carry ≥, ↔ and superscript minus.
- A file of the target's name that the tool did not write (a hand-written `PAPER.tex` beside
  `PAPER.md`) is never overwritten: exit 2. `--out` always names a `.pdf`.
- The PDF stays beside the manuscript (or at `--out`); register it in the run like the heat map
  (`runs.py add ... --role other --name PAPER.pdf`), and its log with `--role check`. The stage's report is
  still its own `report.md` (the end-of-stage checklist); the heat map and the PDF are documents beside it.
- `--template` passes a venue's pandoc LaTeX template (Markdown only). A template that reads `mainfont`
  gets DejaVu, which may not be the venue's face; one that sets its own fonts ignores it. A Markdown
  master is expected to have one `#` title heading and `##` sections (the build shifts headings up one
  level); with several `#` headings, a level is lost.

**The review draft.** `typeset.py pdf PAPER.md --draft` (or `.tex`) builds `PAPER.draft.pdf` from the
marked master with every unreviewed segment shaded, by the same rule and `rev-marks.toml` as `report
--unreviewed` (`--config`, `--unknown` work here too): a whole paragraph in a shaded box with a side
rule, a run inside a paragraph highlighted, or coloured where it carries math, citations or other
commands (and always coloured inside a LaTeX paragraph). Give it to the person reviewing: what is
shaded is what no person has accepted since an agent wrote it. It never writes the submission PDF (an
`--out` naming `PAPER.pdf` is refused, exit 2) and takes no `--cap`; inline marks that enclose more
than one paragraph are not shaded, and it says so.

The build needs `pandoc` and `tectonic` on PATH (or `TYPESET_PANDOC` and `TYPESET_TECTONIC` naming them);
uv does not install them. Without one, the build exits 3 naming what is missing, with its install routes
(conda-forge on any platform, Homebrew, winget or Chocolatey for pandoc on Windows, or the release
binaries). Say it once in the report ("page count not measured: tectonic absent"), never as a finding,
and go on with the rest; give the heat map in place of the review draft. Tectonic downloads its TeX
bundle on first use and caches it where `TECTONIC_CACHE_DIR` says; a failed download is the same "could
not run", not a fault in the paper.

## How to work with marks

1. **Before the first edit**, lint the master and check the twin (`strip --check`), and build once with
   the venue's `--cap` when there is a page limit. Say in the first message if any of these fails or
   cannot run, and whether another writer's uncommitted changes sit in the master.
2. **Applying an item** is one change: the edit inside its segment (open a new segment with the item's
   id, `rounds=1`, if none exists), `bump` when an existing segment gets another round, `strip` to
   refresh the twin, the build and its measured length when there is a cap, and the record's status
   (the review ledger, when there is one). **When the master carries marks, every applied edit is
   marked**, whichever skill applied it: inside a segment it is that segment's next round (one `bump`
   per pass, however many edits it holds); elsewhere it opens a segment with the id of what asked for it.
   Routine fixes (spelling, grammar, formatting) in passages no segment holds are grouped: one copy-edit
   segment per section, with the next free `N` id, `rounds=1`, signed by whoever made the fixes, around
   the whole paragraphs from the first fix to the last, and taking in whole any segment it would
   otherwise cut. That is what "a wording edit outside any segment is still a revision: mark it or say
   why not" allows for routine edits; no applied edit stays unmarked in a marked master. A manuscript
   without marks never gets them unless the authors ask.
3. **Name who did it.** The `by=` entry names who made this round's text: the author's handle, or the
   agent's name when an agent wrote it (your model's name, such as `claude`). Never sign an agent's
   round with a person's name; when the authors say the person approved the passage, add the person's
   round with `bump`.
4. **Hand reviews the twin.** A simulated referee (`manuscript-peer-review`), a reference or number
   check, or a co-author reads the clean copy, as an editor would. Comparisons read clean copies too:
   the guard, `revise.py` and the before/after records of an improvement run compare `strip --out`
   copies of the retained original and of the working master, so a bump alone is no change to the text.
5. **Close the pass** with `report --blind --unreviewed`: the segments touched, the paragraphs no
   round has read, and the agent-written passages no person has accepted since. Both lists are where
   an unchecked claim can still hide; give them to the authors as one state line, with the heat map
   or the review draft (`typeset.py pdf --draft`) when they will read the paper to sign off.
6. **For upload**, the files the venue receives are always the twins or a build from them, never the
   marked master: no question to the authors. Confirm with `report UPLOAD_FILE` that a Markdown or
   LaTeX upload carries no segment. `report` cannot read a PDF (exit 3): a PDF that `typeset.py` built
   carries no marks, since the build reads the twin; for one built elsewhere, check the source it was
   built from, or extract its text where a tool is installed (`pdftotext`) and search it for `@rev`.
   `manuscript-integrity-check`'s upload check (`hygiene.py`) also reports any mark left in an upload file.

Never edit the twin: the next `strip` overwrites it. The authors' choice covers only retiring the marks
from the master for good; strip them from the master only when they ask for that.

## Files

- `scripts/rev_marks.py`: lint, strip, report and bump.
- `scripts/typeset.py`: the PDF build from the clean twin, measured against a page cap, the review
  draft, and the LaTeX reading copy.
- `scripts/unreviewed.lua`, `scripts/unreviewed-preamble.tex`: how the draft shades a segment.
- `references/agent-names.toml`: the AI model and agent names, shared with `manuscript-mark-people` and
  `manuscript-integrity-check`'s scan.
