---
name: manuscript-coauthors
description: >-
  Run rounds of a manuscript with co-authors who comment on Google Docs: remember the shared Drive folder
  and how each release (v0.5/, v0.6/) goes there, pull the comments and suggested edits on a round into a
  ledger with stable ids (C12, S3), say how the next round answers each (addressed, partly, declined, or
  open with what could be done), feed the dashboard's "Co-authors' comments" section, write the changelog
  for co-authors who only read the previous round (Why from the comments, and what changed since the draft
  they saw), and push the release to Drive. Use when the authors mention co-authors' comments on a Google
  Doc or Drive, "check the comments", "release v0.7" or "push the round to Drive", or when the project's
  settings say its rounds live on Drive. Use manuscript-reviewer-response for journal referees,
  manuscript-revision-marks for the @rev marks, and manuscript-improve to revise the paper.
---

# Rounds with co-authors on Google Drive

Many papers are written in rounds: the authors keep the master in git (`v0.5/paper.md`), put each release on a
shared Drive folder as Google Docs, and co-authors comment there. The next round has to answer those comments,
and a co-author who read only v0.5 has to see what changed and whether their comment was taken up. Without a
record, comments are retyped by hand, some are forgotten, and the changelog's "why" is reconstructed from
memory. This skill keeps that record: every comment of a round, its id, where it sits, and what the next round
did with it.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md):
resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill's report,
evidence and failures in its subfolder of the linked run. This applies to direct invocations too. End with its
[end-of-stage checklist](../manuscript-integrity-check/references/project-workflow.md#end-of-stage-checklist):
`stage-report.md`, the smell check on it, `findings.json` with the prefix `CA` (written by `comments.py
findings`), and any applied edit recorded with `runs.py change`. Read the shared
[author priorities](../manuscript-integrity-check/references/author-priorities.md): nothing here asks the authors
to approve comments one by one.

Commands are relative to this skill's folder (`uv run --script`).

## The settings: asked once, kept in the project file

The project file (`.manuscript-skills.yaml`) keeps a `coauthors` block. When the authors first mention
co-authors on Drive and the block is missing, ask in one batch, with what you can infer already filled in (a
Drive link in the project's README, an rclone remote from `rclone listremotes`, the round folders on disk):

- how a release reaches Drive: `rclone` (into the shared folder by its id; the recommended route, since it
  also reads the comments back), `folder` (the local folder Drive for desktop syncs) or `connector` (by hand
  through a Drive connector);
- the shared folder's link, and for rclone the remote's name;
- how the round folders are named (`v{round}` by default), the same in the repository and on Drive;
- the project's own .docx build, if it has one (`{file}` stands for the master); without one, pandoc builds
  the Doc from the clean copy, which loses table borders and column widths;
- what a release uploads: the masters that go up as Google Docs (`PATH=Title`, with `{round}` and
  `{previous}`), and the files that go up as they are (PDFs, data, scans).

Save the answers, then show them back:

```bash
uv run --script ../manuscript-integrity-check/scripts/project.py configure PROJECT --drive rclone \
  --drive-remote gdrive --drive-folder-id https://drive.google.com/drive/folders/ID \
  --release-doc "paper.md=1. Paper title (v{round})" --release-doc "changes-from-v{previous}.md=Changes from v{previous} to v{round}" \
  --release-file "build/*.pdf" --release-build "uv run manuscript build {file} --no-pdf"
uv run --script scripts/rounds.py show --project PROJECT
```

`rounds` in the block is kept by `rounds.py`: each round's base commit, release date, Doc links and the dates
it went to the co-authors. A project with one project file per round folder carries the block into each new
round (`rounds.py open` copies it). Never invent a folder id or a Doc link: take them from the authors, a
README, `rclone lsjson` or a connector's `search_files`.

## 1. Pull the comments

The comments of round X.Y go to `vX.Y/comments.yaml`, beside the round. That ledger is the authors' record,
kept in git with the paper; the run gets the exports and a copy as evidence.

- **rclone:** `rounds.py pull 0.5 --out RUN/manuscript-coauthors/exports --go` exports each recorded Doc of
  the round as .docx and merges its comments. Without `--go` it prints the commands.
- **A Drive connector:** find the Doc (`search_files`, `title contains '…'`), download it as .docx
  (`download_file_content` with `exportMimeType`
  `application/vnd.openxmlformats-officedocument.wordprocessingml.document`) into the run's `exports/`, then
  `comments.py import EXPORT.docx --ledger v0.5/comments.yaml --master v0.5/paper.md --doc LINK`. When only
  the text view is available (`read_file_content` with `includeComments`), write each thread as an item (author,
  date, the commented words as `anchor`, a dozen words on each side as `context_before`/`context_after`,
  `comment`, `replies`) and merge them with `comments.py add ITEMS.yaml --ledger … --master …`.
- **By hand:** File › Download › Microsoft Word, then `import` as above.

What the import does, so you can say it plainly: each comment and reply is read with its author and date; a
reply is a comment on exactly the range of an earlier one; a comment over several ranges counts once; the
suggested edits of one person in one paragraph are one item (`S3`), shown as "replace X with Y". Ids are
`C<n>` and `S<n>` in paper order, continuing past every id the project used (earlier rounds' ledgers, the
master's `@rev` marks), and a later pull keeps every id and adds only what is new. A Google .docx does not say
whether a thread was resolved, so `resolved` stays empty unless a connector showed it; never treat a resolved
thread as answered without checking the text. Report how many comments and suggestions arrived, from whom,
and any anchor not found in the master (`not_located`): the Doc and the master have drifted there, and that
comment is placed by hand.

Comments are the co-authors' own words: quote them exactly, never summarise one into a different request, and
keep them local (the ledger and the run), like the manuscript.

## 2. Decide what each comment needs

For each item, write in the ledger:

- `status`: `open` (not answered yet), `addressed`, `partly`, `declined` (the authors chose not to, for a
  reason) or `not-on-point` (praise, a question already answered, a remark that asks for nothing). A reply in
  the thread can settle it ("working on it" does not; "fixed in v0.6" needs the check below).
- `next` for `open` and `partly`: the smallest change that would answer it, in plain words ("Name the four
  modules in Table 1"). A question only the authors can answer (a fact, a co-author's permission, a change of
  direction) is still `open`, with `decision: true` and the question in `next`.
- `why` for `declined` and `not-on-point`, and for an addressed comment what was done: this is what the
  co-author reads in the changelog and the dashboard. It comes from the record (the authors' words, the
  commit, the edit that answered it), never from a guess.
- optionally `category`, `severity`, `stage` on the dashboard's scales ([stage findings](../manuscript-dashboard/references/stage-findings.md));
  unset, an open comment is a minor "Writing and clarity" problem for the writing stage.

Routine, evidence-settled comments (a typo, a missing reference the comment names, an ambiguous word) are
answered, not asked about. Hand the substantive ones to `manuscript-improve`, or answer them in its run: every
open comment becomes a `CA` finding the later stages fix.

## 3. Answer them in the next round

Edit the next round's master (open it first, step 6). Where the master carries revision marks, the segment that
answers a comment takes the comment's id (`@rev C12`, `C12a`, `C12b` for several places; see
manuscript-revision-marks), so the changelog and the dashboard link the passage to the comment.

Then check the ledger against the new round:

```bash
uv run --script scripts/comments.py status v0.5/comments.yaml --new v0.6/paper.md [--strict]
```

For each comment it says whether its paragraph changed, moved (its paragraph is gone, a segment named for it
is elsewhere), was removed or reads the same, and checks the ledger: `addressed`/`partly` need `now`, the
new round's passage that answers it, copied verbatim; `declined`/`not-on-point` need `why`; `open`/`partly`
need `next`. Its hints are where to look again: an open comment whose paragraph changed, an addressed comment
whose paragraph did not. Fix every problem it prints; `--strict` exits 1 while any remains.

## 4. The stage's findings and the dashboard

```bash
uv run --script scripts/comments.py findings v0.5/comments.yaml --new v0.6/paper.md \
  --out RUN/manuscript-coauthors/findings.json
```

It refuses while the ledger has problems, then writes `findings.json` (a `CA` finding for each comment not
fully answered, its action the ledger's `next`) with the `coauthors` object, and `comments.md`, the digest the
findings cite. The dashboard shows them as its "Co-authors' comments" section: every comment with its
replies, the passage before and after, why, and what could still be done ([data contract](../manuscript-dashboard/references/data-contract.md)).

## 5. The changelog for co-authors

A co-author who read only v0.5 gets the round's changelog. Build it from the round's base (the previous master
as it was when this round opened) and the comments it answers:

```bash
git show BASE:v0.5/paper.md > OLD.md
git show LAST_CIRCULATED:v0.6/paper.md > SEEN.md      # when this round already went to the co-authors
uv run --script scripts/comments.py changelog --base OLD.md --new v0.6/paper.md --seen SEEN.md \
  --ledger v0.5/comments.yaml --base-name v0.5 --new-name v0.6 --seen-name "the 26 October draft"
```

The base is `rounds.<round>.base` and the last circulated commit the last entry of `rounds.<round>.circulated`
(`rounds.py show`). Every row whose segment answers a comment gets its Why: who asked, what, and the ledger's
`why`. The rest follow manuscript-revision-marks' "Changelog between rounds": Why from the record or left for
the authors, every row kept, and the changelog **extended** on each iteration of the round, never rewritten.

## 6. Open the next round and release it

```bash
uv run --script scripts/rounds.py open 0.7                 # copy v0.6/ to v0.7/, without its runs, build and comments
uv run --script scripts/rounds.py push 0.7                 # what would be built and uploaded
uv run --script scripts/rounds.py push 0.7 --go            # build the Docs and upload the release
uv run --script scripts/rounds.py record 0.7               # the new Docs' links, read back (rclone), or --doc NAME=LINK
uv run --script scripts/rounds.py circulated 0.7           # the round went to the co-authors again, as of HEAD
```

- `open` copies the released round, leaving behind its reviews, build, comments and dashboards, records the
  base commit, and lists the lines that still name the old round (the draft label) for you to change.
- Run `push --go` when the authors ask to release or send the round: the upload is the release. It never
  replaces a file already in the round's Drive folder: replacing a Doc keeps its link but can detach the
  co-authors' comments from their text. Before `--replace`, pull that Doc's comments (step 1) and ask.
- After the upload, open the Docs (or their PDF export) and look at every figure and table page before calling
  the round released; a Drive-for-desktop upload stays a Word file until it is saved as a Google Doc.
- Replies to co-authors inside the Doc are the authors' to post: no connector here writes Doc comments. The
  changelog's Why and the dashboard carry the answers.

## What to tell the authors

One short state line per round: comments pulled (by co-author), how many are answered, partly answered,
declined and still open, and the open ones that need the authors (`decision: true`), each quoted with what
could be done. Give the paths of the ledger, the changelog and the dashboard. Say what could not be done (a
Doc that could not be exported, anchors not found) once, plainly.

## Files

- `scripts/comments.py`: import, add, status, findings and changelog: the ledger of a round's comments.
- `scripts/rounds.py`: show, open, push, record, circulated and pull: the rounds on Drive.
- The settings live in the project file and are saved by `manuscript-integrity-check/scripts/project.py configure`.
