---
name: manuscript-revision-marks
description: >-
  Keep and use revision marks inside a Markdown or LaTeX manuscript: which passages were rewritten, in
  how many rounds and by whom (`<!-- @rev ID rounds=N by=name:date -->` or `% @rev` comment lines),
  the clean copy without them that reviews and builds read, the blind spots no round has touched,
  the passages an AI or agent wrote that no person has reviewed since, and a heat map of the revision. Use when a manuscript already carries @rev marks, when the authors ask to
  record who revised what (accountability or traceability of AI-assisted edits), to lint, strip, bump
  or report marks, to list the prose nobody has reviewed, or to see which AI edits still await a
  person. Also builds the PDF from the clean copy (Markdown or LaTeX, pandoc and tectonic) and measures
  it against a page cap. Use manuscript-mark-people to build the project's list of people. Use manuscript-reviewer-response for the
  review ledger and the response letter (a mark can carry a ledger item's id), manuscript-prose-edit for
  the edits themselves, and manuscript-integrity-check before upload.
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

## The format

```markdown
<!-- @rev C3 rounds=2 by=anna:2026-09-25,claude:2026-10-10 -->
The rewritten text.
<!-- @/rev C3 -->
```

In a `.tex` file each mark is a comment line of its own: `% @rev C3 rounds=2 by=...` and `% @/rev C3`.

- **The id** is the comment the passage answers: `C3`, `N1`, `C3a`, or a review-ledger item from
  `manuscript-reviewer-response` such as `R1.2`, `R2.W1`, `R1.4a`. One comment answered in several
  places takes `C3a`, `C3b` (grouped as `C3`). Ids are unique per file.
- **`rounds=`** counts the passes over the passage; **`by=`** lists `name:YYYY-MM-DD` for each, in
  order. Both are required; nothing else is allowed.
- Segments with different ids nest; marks inside code (Markdown) or verbatim (LaTeX) are examples.
- **The clean twin** is `<stem>.clean.md` (or `.clean.tex`) beside the master: the file exactly as it
  was before any mark went in, byte for byte. Reviews, checks and builds read the twin, never the marked
  master; only the master is edited.
- **A blind spot** is a prose line (paragraph, list item, table row) that no segment overlaps.
- **An unreviewed segment** is one whose latest `by=` name is not a person's: an AI model or agent
  harness, or a name nobody has classified. Its text has not been read and accepted by a person since
  the agent wrote it.

## Who is a person: rev-marks.toml

The project lists its people in `rev-marks.toml` at the repository root (the tool looks from the
manuscript up to the git root). Every key is optional:

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
the people it finds in the repository for the authors to confirm.

**A person's round.** When the authors say a person has reviewed or approved passages, including a
bulk "accept all" relayed from a co-author, record it with `bump --by <their handle>`. How co-authors
discuss and agree on the text happens outside these skills; the marks only record what the authors
report.

## Commands

Relative to this skill directory; standard library only (`uv run --script`, no dependencies):

```bash
uv run --script scripts/rev_marks.py lint PAPER.md [--strict]       # exit 1 on an error (or warning)
uv run --script scripts/rev_marks.py strip PAPER.md                 # write PAPER.clean.md
uv run --script scripts/rev_marks.py strip PAPER.md --check         # exit 1 if the twin is missing or stale
uv run --script scripts/rev_marks.py report PAPER.md --blind --unreviewed --html $SCRATCH/heatmap.html
uv run --script scripts/rev_marks.py bump PAPER.md C3 --by claude   # an agent's round, dated today
uv run --script scripts/rev_marks.py bump PAPER.md C3 --by anna    # anna reviewed it, as the authors say
```

`lint` and `report` take `--config PATH` and `--unknown agent|human`. The heat map shades each
segment by its rounds and outlines and hatches the unreviewed ones. Exit codes: 0 clean, 1 errors (a
malformed or unpaired mark, a stale twin, an unknown id), 2 usage or a malformed `rev-marks.toml`, 3
could not run. `strip` and `bump` refuse a file whose marks do not lint, so a half-recognised mark
never reaches the twin.

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
- A failed build deletes the PDF an earlier build left, so a stale PDF never reads as current.
- Every glyph the fonts lack (XeTeX drops it silently) is a warning with its code point; `--strict`
  makes it exit 1. Markdown builds use DejaVu fonts, which carry ≥, ↔ and superscript minus.
- A file of the target's name that the tool did not write (a hand-written `PAPER.tex` beside
  `PAPER.md`) is never overwritten: exit 2.
- `--template` passes a venue's pandoc LaTeX template (Markdown only). A template that reads `mainfont`
  gets DejaVu, which may not be the venue's face; one that sets its own fonts ignores it. A Markdown
  master is expected to have one `#` title heading and `##` sections (the build shifts headings up one
  level); with several `#` headings, a level is lost.

**The review draft.** `typeset.py pdf PAPER.md --draft` (or `.tex`) builds `PAPER.draft.pdf` from the
marked master with every unreviewed segment shaded, by the same rule and `rev-marks.toml` as `report
--unreviewed` (`--config`, `--unknown` work here too): a whole paragraph in a shaded box with a side
rule, a run inside a paragraph highlighted, or coloured where it carries math, citations or other
commands (and always coloured inside a LaTeX paragraph). Give it to the person reviewing: what is
shaded is what no person has accepted since an agent wrote it. It never writes the submission PDF and
takes no `--cap`; inline marks that enclose more than one paragraph are not shaded, and it says so.

The build needs `pandoc` and `tectonic` on PATH (or `TYPESET_PANDOC` and `TYPESET_TECTONIC` naming them);
uv does not install them, and without them the build exits 3 naming what is missing. Tectonic downloads
its TeX bundle on first use and caches it where `TECTONIC_CACHE_DIR` says.

## How to work with marks

1. **Before the first edit**, lint the master and check the twin (`strip --check`), and build once with
   the venue's `--cap` when there is a page limit. Say in the first message if any of these fails or
   cannot run, and whether another writer's uncommitted changes sit in the master.
2. **Applying an item** is one change: the edit inside its segment (open a new segment with the item's
   id, `rounds=1`, if none exists), `bump` when an existing segment gets another round, `strip` to
   refresh the twin, the build and its measured length when there is a cap, and the record's status
   (the review ledger, when there is one). A wording edit
   outside any segment is still a revision: mark it or say why not.
3. **Name who did it.** The `by=` entry names who made this round's text: the author's handle, or the
   agent's name when an agent wrote it (your model's name, such as `claude`). Never sign an agent's
   round with a person's name; when the authors say the person approved the passage, add the person's
   round with `bump`.
4. **Hand reviews the twin.** A simulated referee (`manuscript-peer-review`), a reference or number
   check, or a co-author reads the clean copy, as an editor would.
5. **Close the pass** with `report --blind --unreviewed`: the segments touched, the paragraphs no
   round has read, and the agent-written passages no person has accepted since. Both lists are where
   an unchecked claim can still hide; give them to the authors as one state line, with the heat map
   or the review draft (`typeset.py pdf --draft`) when they will read the paper to sign off.
6. **For upload**, the files the venue receives are the twins or a build from them. The
   submission-package check (`manuscript-integrity-check`) deliberately ignores marks, so confirm with
   `report UPLOAD_FILE` that the uploaded file carries no segment.

Never edit the twin: the next `strip` overwrites it. Never strip marks from the master unless the
authors ask to retire them.

## Files

- `scripts/rev_marks.py`: lint, strip, report and bump.
- `scripts/typeset.py`: the PDF build from the clean twin, measured against a page cap, the review
  draft, and the LaTeX reading copy.
- `scripts/unreviewed.lua`, `scripts/unreviewed-preamble.tex`: how the draft shades a segment.
- `references/agent-names.toml`: the AI model and agent names, shared with `manuscript-mark-people` and
  `manuscript-integrity-check`'s scan.
