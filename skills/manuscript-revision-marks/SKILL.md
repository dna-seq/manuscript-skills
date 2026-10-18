---
name: manuscript-revision-marks
description: >-
  Keep and use revision marks inside a Markdown or LaTeX manuscript: which passages were rewritten, in
  how many rounds and by whom (`<!-- @rev ID rounds=N by=name:date -->` or `% @rev` comment lines),
  the clean copy without them that reviews and builds read, the blind spots no round has touched, and a
  heat map of the revision. Use when a manuscript already carries @rev marks, when the authors ask to
  record who revised what (accountability or traceability of AI-assisted edits), to lint, strip, bump
  or report marks, or to list the prose nobody has reviewed. Use manuscript-reviewer-response for the
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

## Commands

Relative to this skill directory; standard library only (`uv run --script`, no dependencies):

```bash
uv run --script scripts/rev_marks.py lint PAPER.md [--strict]       # exit 1 on an error (or warning)
uv run --script scripts/rev_marks.py strip PAPER.md                 # write PAPER.clean.md
uv run --script scripts/rev_marks.py strip PAPER.md --check         # exit 1 if the twin is missing or stale
uv run --script scripts/rev_marks.py report PAPER.md --blind --html $SCRATCH/heatmap.html
uv run --script scripts/rev_marks.py bump PAPER.md C3 --by anna     # one more round, dated today
```

Exit codes: 0 clean, 1 errors (a malformed or unpaired mark, a stale twin, an unknown id), 2 usage,
3 could not run. `strip` and `bump` refuse a file whose marks do not lint, so a half-recognised mark
never reaches the twin.

## How to work with marks

1. **Before the first edit**, lint the master and check the twin (`strip --check`). Say in the first
   message if either fails, and whether another writer's uncommitted changes sit in the master.
2. **Applying an item** is one change: the edit inside its segment (open a new segment with the item's
   id, `rounds=1`, if none exists), `bump` when an existing segment gets another round, `strip` to
   refresh the twin, and the record's status (the review ledger, when there is one). A wording edit
   outside any segment is still a revision: mark it or say why not.
3. **Name who did it.** The `by=` entry names who made this round's text: the author's handle, or the
   agent's name when an agent wrote it. Never sign an agent's round with a person's name.
4. **Hand reviews the twin.** A simulated referee (`manuscript-peer-review`), a reference or number
   check, or a co-author reads the clean copy, as an editor would.
5. **Close the pass** with `report --blind`: the segments touched, and the paragraphs no round has read.
   The blind spots are where an unreviewed claim can still hide.
6. **For upload**, the files the venue receives are the twins or a build from them. The
   submission-package check (`manuscript-integrity-check`) deliberately ignores marks, so confirm with
   `report UPLOAD_FILE` that the uploaded file carries no segment.

Never edit the twin: the next `strip` overwrites it. Never strip marks from the master unless the
authors ask to retire them.

## Files

- `scripts/rev_marks.py`: lint, strip, report and bump.
