# Roadmap

Open work only. Each item says what it is, why it is not built yet, and the shape it would take.

## Read the paper as a scientist outside the field (not built)

Two co-authors' comments on Paper 1 v0.7 matched against the run that produced it
([docs/coauthor-gaps-2026-11.md](coauthor-gaps-2026-11.md)) show the largest gap: 27 comments by a senior co-author
from outside the field on text that reader could not follow (terms used before they are defined, sentences that do not parse, numbers without their reason), three of
them on passages the run wrote for its own simulated referees. The story stage's readers read for the story, the
prose stage reads only what it edits, and the re-check asks whether an edit is accurate, not whether it reads. The
shape: a reader seat for an expert outside the field that reads Sections 2 to 4 and every applied edit longer than a
sentence, sentence by sentence, and lists each term before its definition, each sentence it cannot parse and each
number given without its reason, for the prose stage to fix; and a list-only parse pass over the whole text. The
same note orders the smaller misses by skill (limits stated without their cost, who the users are against the
scope, reasons for a method's constants, authorship criteria). `comments.py gaps` measures each round against the
next co-authors' reading.

## Shade unreviewed AI edits inside a Google Doc (Codex only; not built)

`manuscript-revision-marks` shows which passages an AI or agent wrote that no person has reviewed since,
in its HTML heat map and its review draft PDF (`typeset.py pdf --draft`). Many co-authors read and
comment in a Google Doc instead, so the same shading belongs there.

**Why Codex only.** Claude's Google Drive connector reads, creates and replaces whole files; it cannot
style a range of text in an existing document, so it cannot shade a passage in place. Codex's Google
Docs integration is richer and can edit an existing document, so the hook would ship in the Codex
plugin only (`.codex-plugin/`), and the Claude skill would keep pointing to the PDF draft.

**Shape.**

- The master stays in the repository; the Google Doc is a reading and commenting copy built from the
  clean twin, never a second master (marks are never written into it).
- For each unreviewed segment (`rev_marks.py report --unreviewed`, same `rev-marks.toml`), find its
  text in the document by the clean twin's text and set a background colour on that range; clear the
  colour on segments a person has since signed.
- A segment whose text no longer matches the document (someone edited the copy) is reported, never
  guessed at. Comments in the document already come back to the master as review items:
  `manuscript-coauthors` (0.42.0) pulls them into the round's `comments.yaml` from a .docx export.
- Same rules as the draft: the policy decides who is a person, an unlisted name is shaded, and the
  shading is never a sign-off.

**Before building it:** confirm on a live Codex session which document operations its Google Docs
integration offers (range lookup, background colour, comments), and add an eval case with a fixture
document.

## Reply to co-authors inside the Google Doc (not built)

`manuscript-coauthors` records how each co-author comment was answered (the ledger's `why`, the changelog,
the dashboard), but the reply in the Doc's own thread is posted by hand: Claude's Drive connector reads a
Doc's comments and cannot write one. With a connector or the Drive API's `comments.replies.create` behind an
explicit authors' request, the ledger's `why` for each answered comment could be posted as a reply on its
thread, once, with the round it was answered in. A Google .docx export also says nothing of resolved
threads; the API's `resolved` field would fill the ledger's `resolved`.
