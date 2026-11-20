# Roadmap

Open work only. Each item says what it is, why it is not built yet, and the shape it would take. An item is a
heading `## RM<n> — <title>` with its state and its owner under it, which the lead keeps true
([docs/seats/LEAD.md](seats/LEAD.md)); a built item leaves this file in the commit that lands it.

## RM3 — Reply to co-authors inside the Google Doc

**State:** blocked: desk #70 (the maintainer posts one round's replies from the desktop; no Docs connector on the server)
**Owner:** lead

Built in 0.72.0: `comments.py replies` plans the reply in each co-author's thread from the ledger's `why`, posts
nothing twice, never reopens or resolves a thread, and `--record` notes each reply found in the ledger. Tested only
on a model Doc: the server has no Google Docs connector, so it is not done until the maintainer runs it once on a
real round from the desktop (plan, `update_doc`, read again, `--record`) and the replies read as they should in the
Doc.
