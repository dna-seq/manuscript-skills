---
name: manuscript-coauthors
description: >-
  Run rounds of a manuscript with co-authors who comment on Google Docs: remember the shared Drive folder and
  how each release (v0.5/, v0.6/) goes there, pull the comments and suggested edits on a round into a ledger
  with stable ids (C12, S3), carry what was accepted or edited in the Docs back into the masters, say how the
  next round answers each comment, feed the dashboard's "Co-authors' comments" tab, report which comments the
  run that produced the round had caught, missed or written itself, write the changelog for co-authors who
  read only the previous round, and push the release to Drive. Use when the authors mention co-authors' comments on a Google
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
- what a release uploads: the Docs (`PATH=Title`, with `{round}` and `{previous}`: a master is built to .docx
  first, a .docx or .xlsx such as the changes workbook goes up as it is and becomes a Doc or a Sheet), and the
  files that go up as they are (`PATTERN=DEST`: PDFs, data, scans; a DEST ending in `/` is a subfolder of the
  round's folder, such as `Figures/`, otherwise the file's name on Drive). Copy the titles from the round
  already on Drive (`rclone lsjson`), so the next release keeps them.

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
round (`rounds.py open` copies it). For rounds released before the settings existed, record them once from
the git history and Drive: `rounds.py record 0.6 --base COMMIT --released 2026-10-26`, then `rounds.py record
0.6` to read its Docs and Sheets back (rclone lists a Google Doc as "Title.docx"; `record` tells them from Word
files), and `rounds.py circulated 0.6 --commit COMMIT --date 2026-10-26` for the commit the co-authors got. A
round with several Docs (the paper, the supplement, separate tables) pulls each into the same ledger; a comment
on another Doc than the main master keeps that Doc's master (`master:` on the item), and `status` reads the
same file in the next round. Never invent a folder id or a Doc link: take them from the authors, a
README, `rclone lsjson` or a connector's `search_files`.

## Reaching the Google Docs, and saying so without stopping

This skill depends on reading the co-authors' Google Docs, and hosts differ: Codex often has its workspace's
Google Drive connector on, Claude Code has it only once someone connects it (or an organization owner allows it),
and rclone works on any host. Before pulling, find out which way you have, then go on whatever the answer:

1. Look among your own tools for a Google Drive connector (tools such as `search_files`, `read_file_content`,
   `download_file_content`; a deferred one is found by searching your tools for "google drive").
2. Ask the script what the machine has, passing what you found:

   ```bash
   uv run --script scripts/rounds.py routes --connector|--no-connector --host claude|codex [--project DIR]
   ```

   It reports rclone's Google Drive remotes (and whether the configured one exists), the synced folder, what can
   pull the comments (`can_pull`) and what can upload a release (`can_push`).
3. With a route, use it: rclone first (it pulls and pushes), else the connector. A connector that would serve
   better than the saved route (say the project saves `connector` and rclone now works) is worth one line to the
   authors, not a question.
4. With none, **never stop the run or wait for an answer.** Go on with what the run has (the ledger already in the
   round folder, any .docx exports the authors left), record the script's `setup_note` once, and say it once at
   the end:

   ```bash
   uv run --script ../manuscript-integrity-check/scripts/runs.py issue RUN --skill manuscript-coauthors --kind setup \
     --message "<setup_note>"
   ```

   The progress pane lists a `setup` issue under "For a better run (nothing waits for this)" and toasts it when it
   appears; the closing message repeats it in one line. Without a run (a direct request), say it in the reply.
   Put the round's comments down as not pulled in the stage report, so the dashboard does not read their absence
   as none.

## A review that happens in Google Docs: `port`

Many reviewers never touch the plugin: they read the round in Google Docs and comment there. One command
takes what they wrote to the run's dashboard, where the authors work:

```bash
uv run --script scripts/rounds.py port 0.7 --run RUN --gdoc READ.json        # what it would run
uv run --script scripts/rounds.py port 0.7 --run RUN --gdoc READ.json --go   # run it
```

`--gdoc` is the Docs connector's `read_doc` answer (commentsIncluded) saved as JSON, one per Doc; without it,
port pulls through rclone. It then records the commenters as people, writes the co-authors' findings with
every comment not triaged yet shown as open ("Not triaged yet"), and replays the run's own last collect,
corrected-version and dashboard commands (and the Word file and workbook, when the run made them) on the new
inventory, each as its next attempt (`findings.3.json`, `revision.3`, `dashboard.2`). Every step goes through
`runs.py exec`, so the run records it. A run with no dashboard yet stops after the findings. Then triage
(step 2) and port again with `--no-pull` to show the answers. Port never answers a comment: triage stays the
agent's and the authors'.

## 1. Pull the comments

The comments of round X.Y go to `vX.Y/comments.yaml`, beside the round. That ledger is the authors' record,
kept in git with the paper; the run gets the exports and a copy as evidence.

- **rclone:** `rounds.py pull 0.5 --out RUN/manuscript-coauthors/exports --go` exports each recorded Doc of
  the round as .docx and merges its comments. Without `--go` it prints the commands.
- **The Google Docs connector** (Claude's, separate from Drive; the best connector route): `read_doc` with
  `commentsIncluded: true` returns every thread with the exact words it is anchored on, its range, its status
  (open or resolved) and its replies, and every suggestion with its author, status and a "Replace: X with Y"
  summary. Save that answer as JSON (the client saves a large one to a file by itself; write a small one out)
  and merge it: `comments.py import-gdoc READ.json --ledger v0.5/comments.yaml --master v0.5/paper.md --doc
  LINK`. It keeps each thread's exact range, whether it was resolved and by whom (`resolved_by`), each open
  suggestion's inserted and deleted text, and the Doc's own ids, so a later pull by this route or as .docx
  knows each item again. When the assistant has no Docs connector, say once that the authors can turn it on
  (claude.ai: **+ → Connectors → Google Docs**, then start a new Claude Code session; [Anthropic's
  instructions](https://support.claude.com/en/articles/10166901-use-google-workspace-connectors)), and carry on
  with the routes below. What each connector can do is in
  [references/google-docs-connectors.md](references/google-docs-connectors.md).
- **A Drive connector:** find the Doc (`search_files`, `title contains '…'`), download it as .docx
  (`download_file_content` with `exportMimeType`
  `application/vnd.openxmlformats-officedocument.wordprocessingml.document`) into the run's `exports/`, then
  `comments.py import EXPORT.docx --ledger v0.5/comments.yaml --master v0.5/paper.md --doc LINK`. When only
  the text view is available (`read_file_content` with `includeComments`), write each thread as an item (author,
  date, the commented words as `anchor`, a dozen words on each side as `context_before`/`context_after`,
  `comment`, `replies`) and merge them with `comments.py add ITEMS.yaml --ledger … --master …`. That text
  view loses suggested edits: it prints a suggestion's new text and the text it would delete side by side,
  unmarked, so take suggestions from the .docx export or the Docs connector.
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

**Who commented.** The Doc's commenters are people: `import` maps each name to a handle in the project's
`rev-marks.toml` (an alias already listed, an author of the paper by full name, the one author whose
initials and surname start fit a shortened name such as "T Exa", else a new handle), adds it to `humans` and
the Doc's name to its `aliases`, and writes `by:` on each item and reply. Report the `people` list it prints,
with the rule behind each mapping; a wrong one is fixed by editing `aliases`. `--no-people` leaves
`rev-marks.toml` alone; `add` never touches it. A comment or reply that starts with `[ai]` or `[ai:NAME]` is an
agent's: it names nobody, and such a comment is kept as `not-on-point` with the agent in `ai:`.

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

**First carry what was changed in the Docs.** After a round goes out, the authors accept suggestions and edit
the Docs' text themselves. Those edits exist in the Docs only: an export shows no mark of an accepted suggestion,
and the next release, built from the masters, would undo them. `sync` compares each Doc's text as it stands
(pending suggestions left out) with its master as the co-authors got it (the round's circulated commit), with
Markdown and what a Doc never shows set aside, and writes each paragraph that differs as an edit on the next
round's masters:

```bash
uv run --script scripts/rounds.py sync 0.6 --into 0.7 --export RUN/manuscript-coauthors/exports \
  --out RUN/manuscript-coauthors/sync          # one STEM.edits.json per master, and a sync recorded for the round
uv run --script ../manuscript-integrity-check/scripts/runs.py apply RUN --skill manuscript-coauthors \
  --edits RUN/manuscript-coauthors/sync/paper.edits.json --by co-authors   # --document for a supplement's
uv run --script scripts/rounds.py sync 0.6 --into 0.7 --export … --check   # exit 1 while something is left
```

- `--export` is the folder a pull wrote (each Doc as `Title.docx`); without it rclone exports the Docs again. With a
  connector, download each Doc as .docx under its title into one folder and give that.
- Each edit is a whole paragraph as released, and the same paragraph with the Doc's words; a changed word keeps the
  master's markup (Livia^1^ becomes Livia^4^). Its reason names the ledger's suggestions it carries, or says it is
  an accepted suggestion or an author's own edit. Apply them as the authors' own: `--by co-authors` (name them as
  people in `rev-marks.toml`, manuscript-mark-people), never as the agent's.
- A **conflict** is a paragraph the next round's master changed since the release (a run's edit, say): the Doc's
  words cannot simply replace it. Settle each by hand and say so; never drop one silently.
- **Carried** counts paragraphs the master already reads as the Doc does. `--check` passes when nothing is left.
- Items of the ledger the Doc no longer has stay in it: a suggestion the sync carries is answered by that edit
  (its `now` is the carried passage), one it does not was rejected or answered in other words.

Then edit the next round's master (open it first, step 7). Where the master carries revision marks, the segment that
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

## 5. Did the run that produced the round catch them

When a round was produced by a `manuscript-improve` run (its corrected version, released to the co-authors), their
comments are a second reading of the text that run reviewed. Matching each comment against the run's own records
shows what the run caught and what it missed, and where to improve the skills; it is the authors' answer to "did
the review see this?". Do it whenever the comments are on a run's output, once the comments are triaged (step 2).

The run's records are its adjudicated inventory: `RUN/manuscript-dashboard/findings.json`, or the dashboard it
rendered beside the manuscript (`PAPER.dashboard.html` carries the same records, so a run whose folder stayed on
another computer can still be read). First the worksheet, each comment with the run's records nearest to it:

```bash
uv run --script scripts/comments.py gaps v0.7/comments.yaml --inventory v0.7/PAPER.dashboard.html \
  --out RUN/manuscript-coauthors/gaps-worksheet.md
```

It lists, by shared words and the comment's section, the run's applied edits that wrote the commented passage
(**written by the run's edit …**: the anchor is in the edit's new text and not in its old), its problems, dismissed
flags, unchecked items, referees' concerns and story tests. They are candidates: read each before using it, and
look further when nothing fits. Then write one gap record per comment in a YAML file and merge it:

```yaml
run: 20261028T165906Z-154d8220      # the inventory's run
matched_by: the coordinating agent, after the comments arrived
items:
  C46: {verdict: caught, findings: [ST-8], note: Raised and proposed; left for the authors.}
  C109: {verdict: introduced, changes: [improve.C40], miss_reason: judged-differently, owner: manuscript-improve,
         note: The run wrote this sentence for its referees; the re-check passed it as accurate.}
  C62: {verdict: missed, miss_reason: skill-did-not-look, owner: manuscript-integrity-check,
        note: The limitation is stated without what it costs a reader.}
```

```bash
uv run --script scripts/comments.py gaps v0.7/comments.yaml --inventory … --merge RUN/manuscript-coauthors/gaps.yaml
uv run --script scripts/comments.py gaps v0.7/comments.yaml --inventory … --check [--strict]
```

- `caught`: one of the run's problems names the same thing, whatever became of it (often a proposal or a decision
  left for the authors, which is why the co-author met it again). `partly`: a problem names part of it. Both list
  the problems in `findings`. `missed`: none does. `introduced`: the passage commented on was written by the run's
  own applied edits, listed in `changes` (the worksheet finds them).
- Anything not caught in full says why, on the dashboard's scale for a reference review (`no-skill-covers`,
  `skill-did-not-look`, `judged-differently`, `input-missing`, `wording-preference`, `later-decision`), names the
  skill whose remit covers it (`owner`, required for the two reasons that are a skill's) and says it in a sentence
  (`note`). A comment the run looked at and dismissed is `missed` with `judged-differently`: a dismissed flag is
  never a match, and nor is a problem the co-authors stage made from the comment itself.
- Judge every co-author comment except those not on point. An open point a run carried into the ledger (not a
  co-author's comment) may stay unjudged; `--check` lists what is, and `--strict` fails on it.
- The merge writes nothing while one record has a problem (an unknown or dismissed problem, a proposed edit, a
  missing reason) and keeps the ledger to one run (`gap_run`).

The worksheet groups the comments by co-author, and `--check` counts them for each. `findings` (step 4) then
carries each verdict to the dashboard: the Co-authors' comments tab opens with "Did the run that produced vX.Y
catch them?" (caught, missed, written by the run; one bar and one row per co-author, with the skills their misses
point at; why the rest was missed; the misses by the skill whose remit covers them), each comment carries its verdict with links to the run's problems and edits,
and a filter shows the misses. Re-render the dashboard of the run that produced the round (collect, then render)
so the links resolve; in the next run's dashboard the verdicts stay, unlinked. Tell the authors the counts and the
misses that matter most, quoted, in plain words.

## 6. The changelog for co-authors

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
`--out FILE.md` writes the table; `--out FILE.xlsx` writes a real workbook (the table on a Changes sheet, the
record behind each row on its own), which a release uploads as a Google Sheet.

## Sign-off from the review itself

Revision marks count a passage as reviewed only when a person's name is the last in its `by=`, and a co-author
who reads and comments in the Doc records nothing there. Two things they do in the Doc are signs that they have
seen the answer, and are taken as their sign-off: **resolving a thread** (nobody resolves a comment at random;
an open one may be a reminder they keep, so an open thread signs nothing) and **a suggested edit of theirs that
was taken** (the passage now holds their wording). After the comments are pulled through the Docs connector
(`import-gdoc` records `resolved` and who resolved it) and triaged:

```bash
uv run --script scripts/comments.py signoffs v0.5/comments.yaml --new v0.6/paper.md        # what would be signed
uv run --script scripts/comments.py signoffs v0.5/comments.yaml --new v0.6/paper.md --go   # write the names
```

Each resolved thread signs the segments that answer it (`@rev C12a` answers C12, or the segment holding the
item's `now`) with the handle of the person who resolved it; each taken suggestion (`status: addressed`) signs
the segment holding its `now` with the suggester's handle. The round is dated the day the thread was resolved
(`resolved_on`, from the connector), and the ledger keeps each sign-off under its item (`signed`), so a person is
never added twice to a segment, even after someone else has written in it since. A thread an agent closed (`[ai:NAME]`), or a name
that is not a person in `rev-marks.toml`, signs nothing and is listed. The command prints how many passages had
no person's sign-off before and after. The changelog's first line and `rounds.py push` say that count to the
co-authors, so each knows which wording nobody has put their name to yet.

## 7. Open the next round and release it

```bash
uv run --script scripts/rounds.py open 0.7                 # copy v0.6/ to v0.7/, without its runs, build and comments
uv run --script scripts/rounds.py sync 0.6 --into 0.7      # what was changed in the v0.6 Docs: carry it first (step 3)
uv run --script scripts/rounds.py push 0.7                 # what would be built and uploaded
uv run --script scripts/rounds.py push 0.7 --go            # build the Docs and upload the release
uv run --script scripts/rounds.py record 0.7               # the new Docs' links, read back (rclone), or --doc NAME=LINK
uv run --script scripts/rounds.py circulated 0.7           # the round went to the co-authors again, as of HEAD
```

- `open` copies the released round, leaving behind its reviews, build, comments and dashboards, records the
  base commit, and lists the lines that still name the old round (the draft label) for you to change. It also
  reminds you that the old round's Docs may hold edits the new masters lack (step 3). The authors' To-do marks
  (`STEM.todo.json`) go with it, listed under `todo_marks` with how many were copied; marks the authors save
  in the old round's dashboard afterwards stay in the old folder, and the new round's first run merges them
  (manuscript-improve's to-do stage, `todo.py merge`).
- `push --go` first compares the previous round's Docs with that round as released and refuses while the new
  masters lack what was changed there, listing each passage. Without rclone it asks for a recorded `sync` into
  this round instead. `--unsynced-ok` releases anyway, for a change the authors chose to leave out.
- Run `push --go` when the authors ask to release or send the round: the upload is the release. Read the dry
  run first: its `not_found` lists release files that do not exist yet (a PDF built by hand), which `--go`
  would leave out. It never replaces a file already in the round's Drive folder: replacing a Doc keeps its
  link but can detach the co-authors' comments from their text. Before `--replace`, pull that Doc's comments
  (step 1) and ask.
- A build that warns it could not convert or find an image (pandoc builds the Doc without it; an SVG needs
  `rsvg-convert`) stops the push before anything is uploaded, naming the file and the tool.
- After the upload, open the Docs (or their PDF export) and look at every figure and table page before calling
  the round released; a Drive-for-desktop upload stays a Word file until it is saved as a Google Doc.
- Replies to co-authors inside the Doc are posted only when the authors ask for them. The changelog's Why and
  the dashboard carry the answers either way. With the Google Docs connector, a reply goes on the comment's own
  thread (`addCommentReply`), once, naming the round that answered it. It appears under the name of the
  Google account the connector is signed in to, so the reply starts with `[ai:NAME]` (`[ai:claude]`), the
  marker that tells everyone, and the next pull, that an agent wrote it.
  Never resolve a co-author's thread; that is theirs to do. Read the thread back afterwards to confirm the
  reply landed ([references/google-docs-connectors.md](references/google-docs-connectors.md)). Without the
  connector, the authors post the replies by hand.

## What to tell the authors

One short state line per round: comments pulled (by co-author), how many are answered, partly answered,
declined and still open, and the open ones that need the authors (`decision: true`), each quoted with what
could be done. When the comments were matched against the run that produced the round (step 5), how many it
had caught, missed or written itself, and the misses that matter most, each quoted with the skill it points at.
Give the paths of the ledger, the changelog and the dashboard. Say what could not be done (a Doc that could not
be exported, anchors not found) once, plainly.

## Files

- `scripts/comments.py`: import, import-gdoc, add, status, findings, changelog, signoffs and gaps: the ledger of a round's comments, and
  whether the run that produced the round had caught each.
- `scripts/rounds.py`: show, open, sync, push, record, circulated, pull, routes and port: the rounds on Drive,
  the edits made in their Docs carried back into the masters, and a round's comments taken from Google Docs to
  the run's dashboard.
- `references/google-docs-connectors.md`: what Claude's Google Docs and Drive connectors and Codex's Google Drive
  app can read and write in a Google Doc (edits, highlights, suggestions, comments, replies), the exact
  requests, how to verify each by reading back, and how to install the connectors.
- The settings live in the project file and are saved by `manuscript-integrity-check/scripts/project.py configure`.
