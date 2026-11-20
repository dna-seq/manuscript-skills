# Roadmap

Open work only. Each item says what it is, why it is not built yet, and the shape it would take. An item is a
heading `## RM<n> — <title>` with its state and its owner under it, which the lead keeps true
([docs/seats/LEAD.md](seats/LEAD.md)); a built item leaves this file in the commit that lands it.

## RM3 — Reply to co-authors inside the Google Doc

**State:** blocked: the maintainer posts one round's replies from the desktop (no Docs connector on the server)
**Owner:** lead

Built in 0.72.0: `comments.py replies` plans the reply in each co-author's thread from the ledger's `why`, posts
nothing twice, never reopens or resolves a thread, and `--record` notes each reply found in the ledger. Tested only
on a model Doc: the server has no Google Docs connector, so it is not done until the maintainer runs it once on a
real round from the desktop (plan, `update_doc`, read again, `--record`) and the replies read as they should in the
Doc.

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
