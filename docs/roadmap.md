# Roadmap

Open work only. Each item says what it is, why it is not built yet, and the shape it would take. An item is a
heading `## RM<n> — <title>` with its state and its owner under it, which the lead keeps true
([docs/seats/LEAD.md](seats/LEAD.md)); a built item leaves this file in the commit that lands it.

## RM3 — Reply to co-authors inside the Google Doc

**State:** unattended
**Owner:** lead

`manuscript-coauthors` records how each co-author comment was answered (the ledger's `why`, the changelog,
the dashboard). An agent posts the reply in the Doc's own thread only when the authors ask, through the
Google Docs connector's `addCommentReply` (Claude) or the same request through Codex's Google Drive app; the
skill says how, by hand. Not built: a `comments.py` command that posts the ledger's `why` for each answered
comment as a reply on its thread, once, with the round it was answered in, and records the reply's id in the
ledger. A Google .docx export says nothing of resolved threads; the Docs connector's `status` fills the
ledger's `resolved` when the comments are read through it.
Such a command would follow `manuscript-dashboard/scripts/export_gdoc.py`: one batch per plan, guarded by the revision it was read at, each posted item found again by its ID so a repeat posts nothing twice, then a readback.

## RM4 — The smaller misses on Paper 1 v0.7, by skill

**State:** unattended
**Owner:** lead

0.69.0 built the first of the gap note's suggested order: the reader from outside the field, sentence by sentence,
on Sections 2 to 4 and on the run's own passages, and a list-only scan of the body
([docs/coauthor-gaps-2026-11.md](coauthor-gaps-2026-11.md), "Suggested order"). The rest is not built, each a change
in one skill's remit: finish a fix that needs no decision, applying a definition where a term is first used
(manuscript-improve; six caught comments reached the co-authors anyway); who the paper says its users are, against
the scope it claims (manuscript-policy-fit; the one question both co-authors answered, in opposite directions); each
stated limit with its cost, and a claim the stage could not check raised as a problem (manuscript-integrity-check); a
referee who asks the reason for every constant and how complete each curated resource is (manuscript-peer-review);
authorship criteria for each listed contribution (manuscript-journal-adapt); each caption sentence read against its
figure, and vector export for drawn figures (manuscript-figures); and the draft note before the Abstract, which the
scan leaves out with the front matter, read like the body (manuscript-prose-edit). Each is measured as RM1 was:
`comments.py gaps` against the next co-authors' reading.
