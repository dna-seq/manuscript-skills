# Roadmap

Open work only. Each item says what it is, why it is not built yet, and the shape it would take.

## Read the paper as a scientist outside the field (not built)

A senior co-author's comments on Paper 1 v0.7 matched against the run that produced it
([docs/coauthor-gaps-2026-11.md](coauthor-gaps-2026-11.md)) show the largest gap: 27 comments on text the co-author could
not follow (terms used before they are defined, sentences that do not parse, numbers without their reason), three of
them on passages the run wrote for its own simulated referees. The story stage's readers read for the story, the
prose stage reads only what it edits, and the re-check asks whether an edit is accurate, not whether it reads. The
shape: a reader seat for an expert outside the field that reads Sections 2 to 4 and every applied edit longer than a
sentence, sentence by sentence, and lists each term before its definition, each sentence it cannot parse and each
number given without its reason, for the prose stage to fix; and a list-only parse pass over the whole text. The
same note orders the smaller misses by skill (limits stated without their cost, who the users are against the
scope, reasons for a method's constants, authorship criteria). `comments.py gaps` measures each round against the
next co-authors' reading.

## Reply to co-authors inside the Google Doc (not built)

`manuscript-coauthors` records how each co-author comment was answered (the ledger's `why`, the changelog,
the dashboard). An agent posts the reply in the Doc's own thread only when the authors ask, through the
Google Docs connector's `addCommentReply` (Claude) or the same request through Codex's Google Drive app; the
skill says how, by hand. Not built: a `comments.py` command that posts the ledger's `why` for each answered
comment as a reply on its thread, once, with the round it was answered in, and records the reply's id in the
ledger. A Google .docx export says nothing of resolved threads; the Docs connector's `status` fills the
ledger's `resolved` when the comments are read through it.
