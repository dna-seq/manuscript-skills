# Roadmap

Open work only. Each item says what it is, why it is not built yet, and the shape it would take.

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
