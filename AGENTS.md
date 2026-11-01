# Working on manuscript-skills

Notes for agents (Codex, Claude Code) changing this repository: what the plugin already does, where the
shared machinery lives, and the conventions every change keeps. The user-facing description is
[README.md](README.md); each skill's contract is its `skills/<name>/SKILL.md`.

## The skills

| Skill | What it owns |
|---|---|
| manuscript-improve | The whole workflow, draft to submission: runs the others as stages and ends with the corrected version and the dashboard. |
| manuscript-integrity-check | Claims, numbers, unfinished content, submission files; also the shared plumbing (`scripts/project.py`, `scripts/runs.py`, `scripts/settings.py`, `references/project-workflow.md`, `references/author-priorities.md`). |
| manuscript-reference-check | Each reference's identity and whether it supports the claim. |
| manuscript-reporting-check | Reporting guidelines, data and code availability, statistics reporting. |
| manuscript-figures | Figures and tables as printed, and their content. |
| manuscript-peer-review | Simulated referees and a defender. |
| manuscript-policy-fit | Clinical scope, ethics, privacy, regulation. |
| manuscript-journal-select | Preprint and journal ladders. |
| manuscript-journal-adapt | A chosen venue's format, statements and AI-use disclosure. |
| manuscript-prose-edit | Language editing under the claim guard. |
| manuscript-deslop | Formulaic LLM phrasing. |
| manuscript-story | Simulated readers, and how the paper reads. |
| manuscript-reviewer-response | Real referees: the ledger, the response letter, verifying the revision. |
| manuscript-dashboard | The offline dashboard, the Word review and the changes workbook, collected from every stage's `findings.json`. |
| manuscript-revision-marks | `@rev` marks: who revised what, unreviewed AI edits, clean twins, PDF builds, and the changelog between rounds (`rev_marks.py changes`, with `--seen`). |
| manuscript-mark-people | Who counts as a person for the marks (`rev-marks.toml`). |
| manuscript-other-models | Panels' seats also run on other CLIs/models, on request. |
| manuscript-coauthors | Rounds with co-authors on Google Drive: the `coauthors` project settings, comments pulled from Google Doc exports into `vX.Y/comments.yaml`, how the next round answers each, what was accepted or edited in the Docs carried back into the masters (`rounds.py sync`), whether the run that produced the round had caught each (the gap report), the changelog Why from comments, releasing rounds to Drive. |

## Features to remember

- **Co-authors' comments and rounds on Drive (0.42.0).** `manuscript-coauthors/scripts/comments.py` reads a
  Google Doc exported as .docx (Google writes replies as comments on the same range, a multi-range comment as
  copies, suggestions as `w:ins`/`w:del`, and no resolved state) into a per-round ledger with project-wide
  stable ids (`C<n>`, `S<n>`, continuing past earlier rounds and the master's `@rev` ids). `status` maps each
  comment to the next round with rev_marks' alignment (changed / unchanged / moved / removed), `findings`
  writes `CA` findings plus the `coauthors` object the dashboard's "Co-authors' comments" tab shows,
  `changelog` fills Why from the ledger. `rounds.py` opens a round folder, pushes a release (rclone,
  a Drive-for-desktop folder, or by hand), records Doc links and circulation commits, and pulls comments back;
  pushes are dry runs without `--go` and never replace a Drive file without `--replace`. Settings: the
  `coauthors` block of `.manuscript-skills.yaml`, saved by `project.py configure --drive ...`.
- **Did the run catch the co-authors' comments (0.51.0).** Co-authors read the version a run handed over, so
  `comments.py gaps` matches each comment against that run's adjudicated inventory (its `findings.json`, or the
  `PAPER.dashboard.html` it rendered, which embeds the same records): a worksheet of candidates (the run's applied
  edits whose new text holds the comment's anchor, then problems, dismissed flags, unchecked items, referees'
  concerns and story tests by shared words and section), then `--merge GAPS.yaml` (checked first: never a dismissed
  flag or a `CA` finding, only applied edits, a reason and an owner for a miss) and `--check [--strict]`. The ledger
  keeps `gap_run`, `gap_matched_by` and a `gap` per item; `findings` carries them as `CoauthorGap`, and the
  Co-authors' comments tab opens with "Did the run that produced vX.Y catch them?" (caught, partly, missed,
  introduced; misses by reason and by owner skill, the reference review's scale). Links are checked only when
  `gap_run` is the inventory's run. First use: Paper 1 v0.7 ([docs/coauthor-gaps-2026-11.md](docs/coauthor-gaps-2026-11.md)).
  0.52.0 groups it by co-author: the worksheet's headings, `--check`'s `by_author`, and the summary's
  `coauthors.gap.by_author` (judged, a count per verdict, `by_owner`), drawn as a bar and a table row per co-author.
- **Setup notes, never a stop (0.52.0).** `rounds.py routes --connector|--no-connector --host claude|codex` reports
  the ways to the Google Docs (rclone remotes of type drive, the synced folder, the connector the agent found among
  its own tools; the script cannot see MCP tools) and, when none can pull, a `setup_note` naming how to connect
  Google Drive in that host or set up rclone. Any skill records such a note as `runs.py issue --kind setup`;
  `model.ts setupNotes` lists them on the view (`setup`), the pane shows them under "For a better run (nothing waits
  for this)", `announce` toasts each once, and `/manuscript-status` prints them. They never set `waiting`.
- **Edits made in the Docs come back into the masters (0.53.0).** Authors accept suggestions and edit the Docs
  after a release; an export shows no mark of that, and the next release, built from the masters, undid it.
  `rounds.py sync PREV --into NEXT [--export DIR] [--out DIR] [--check]` compares each Doc's text (`comments.py
  doc_paragraphs`: pending insertions out, pending deletions in) with its master at the round's last circulated
  commit (`released_text`), word by word after `master_token` sets Markdown aside (emphasis, escapes, superscripts,
  link and image syntax but not an image's caption, comments, raw HTML outside code, list markers at a line's start,
  pandoc's dashes). `doc_edits` groups the differences by released paragraph into `{before, after}` for `runs.py
  apply`; `retoken` keeps the master's markup on a changed word (Livia^1^ to Livia^4^); `suggestions_in` names the
  ledger's suggestions an edit carries (not those still pending). A paragraph the target master changed since is a
  conflict, one it already reads as the Doc does is carried. `--out` records `rounds.<round>.synced` (`project.py`
  validates it). `push --go` runs the comparison for the previous round first (`unsynced`) and refuses while
  anything is left (without rclone it needs a recorded sync into the round; `--unsynced-ok` overrides); `open`
  prints the hint. On Paper 1 v0.7 it found exactly the nine edits made in the Doc and nothing in the three
  supplementary Docs. Tests: `tests/test_coauthors.py` (sync, check, release refusal).
- **The changelog between rounds** lives in manuscript-revision-marks: one changelog per round from the
  round's base, extended on every iteration, `--seen` marking rows new or changed since the draft the
  co-authors last saw. Why comes only from the record (commits, findings, ledgers, the co-authors' ledger).
- **The reference review** (dashboard): a human review of the same version, matched against the run's
  frozen findings (`collect.py --reference`).
- **A decision asked in a session of its own (0.43.0).** In the progress mod's Decisions pane
  (`hooks/progress`) each decision row is one Button; opened, **Ask me in a new session** submits, as the
  person, `sessionRequest()` (`model.ts`): a request that Claude start a session (the desktop app's
  `start_session`) titled `<label> · <id>: <summary>`, with a self-contained brief. A mod cannot start a
  session itself. The answer is recorded as `choice: 'session'`.
- **Papers are named by their own name.** `runLabel(data, title)` takes the short name before the title's
  colon (`paperName()`, at most four words), else the file's name; never the kind of paper, since one author
  may have two software papers.
- **The To-do tab and the authors' marks (0.48.0).** `dashboard.todo_items` is the one list of what a run leaves
  for the authors (decisions, applied edits that ask, proposals, open blocker/major problems nothing answers);
  the Word review's comments and the workbook's "For you" sheet are the same items. The tab marks each approved
  or redundant and saves `STEM.todo.json` beside the manuscript (`MarksFile`/`Mark`; the File System Access API
  where the browser has it, else a download; localStorage meanwhile). `collect.py` carries the file into the
  inventory's `todo` and lists word-for-word repeats (`restates`); `todo.py edits` turns marked edits into the
  list `runs.py apply` takes.
- **How the marks reach a run (0.55.0).** The tab says it in three steps above its counts (mark, save, then ask
  Claude Code or Codex for a run), naming the folder from the page's own address when it was handed over beside
  the manuscript (`STEM.dashboard.html` under the marks file's stem, opened from the disk; no path is written into
  the page), else the folder that holds the manuscript. manuscript-improve's summary and the dashboard's reply say
  the same, and "apply my to-do marks" is an improve run of its to-do stage only. `rounds.py open` reports the marks
  file it copies (`todo_marks`); marks saved in the old round afterwards come in at the new round's first run with
  `todo.py merge INTO --from PREVIOUS` (the later mark wins, as the tab's Load; writes only when something is newer;
  lists `only_here`, since the file keeps no record of a mark taken back).
- **The Decisions pane shares the marks file (0.50.0).** Once the dashboard's inventory exists, the pane lists
  the decisions as `todo_items` does (`summarizeFindings`: the adjudication's `decisions`, D1 and on, then each
  `decision: true` finding none links and not dismissed), so its IDs are the To-do tab's. It reads
  `STEM.todo.json` (`marksPath()`, the same place as `collect.py marks_path`) on every refresh: a decision marked
  there for this run counts as answered and shows its mark and reason. **Go ahead** and **Leave as is** on a
  decision also write `approved`/`redundant` there with `$.fs.write` (`setAnswer`, `todoMark()` = the tab's
  `markOf`), reading the file afresh and keeping every other mark; Undo puts back the mark it replaced, unless
  the tab changed it since; a file that does not parse is never written over. The corrected version's questions
  show a mark but write none (leave as is means "keep the edit" there, "drop it" for a proposal). Before the
  dashboard, the pane neither reads nor writes the file.
- **How much each recommended journal changes the manuscript (0.54.0).** `manuscript-journal-select/scripts/effort.py`
  measures the manuscript as an editor counts it (reusing manuscript-story's `reader_metrics.parse`: body without
  captions, tables or back matter; abstract; main-text figures, tables and boxes; main sections) and sizes each
  change against the catalogue: `limits` (with `body_words_excludes: [methods]` for Cell Reports Methods' STAR
  Methods, and `display_items` in `none_stated`), `figure_rules.display_items` by article type, `abstract_headings`,
  `required_sections` and the record's unmet `conditions`; prose-only structure (Cell Press) comes from `changes` on
  the `top3.json` entry. Rows are none/small/medium/large/unknown, the estimate no change/light/moderate/major.
  `--format json` writes `RUN/manuscript-journal-select/adaptation.json`; `collect.py` attaches it to the journal's
  rung as `adaptation` and the Journals tab shows it per card, in a comparison table and in the ladder table.
  0.56.0: lengths and counts carry `numbers` ("7,963 / 8,000 · −37": the manuscript / the limit · over or under)
  and a short `note` ("advised"), which the cards and the table show instead of a sentence.
- Open work is in [docs/roadmap.md](docs/roadmap.md).

## Shared machinery

- **Project settings**: `.manuscript-skills.yaml`, read and written only through
  `manuscript-integrity-check/scripts/project.py` (`resolve`, `configure`). A new lasting choice is a
  top-level key validated in `read()` and saved by `configure` (see `other_models`, `coauthors`); enum
  preferences shared with the global file are in `settings.py` and are pinned by tests.
- **Runs**: `runs.py` (`start`, `add`, `change`, `finish`, `validate`). Each finding-producing skill writes
  `RUN/<skill>/stage-report.md` and `findings.json` ([stage findings](skills/manuscript-dashboard/references/stage-findings.md)).
- **Finding prefixes** (IC RF RP PR PF JS JA PE DS ST FG IM RR RM MP CA) are listed in six places that must
  agree: `stage-findings.md`, `collect.py` `PREFIX`, `export_docx.py` `PREFIX`/`NAME`,
  `manuscript-peer-review/scripts/check_findings.py` `STAGE_PREFIXES`, `finding-schema.md`, and the
  dashboard's `SKILL` icon map. `tests/test_panels_0_19.py` checks them.
- **Skills that write no findings** are listed in `runs.py` `NO_FINDINGS`, `hooks/progress/register.tsx`
  and `stage-findings.md`.
- **The dashboard** reads stage objects beside the findings (`story`, `figures`, `coauthors`): a new section
  is a pydantic model on `Inventory` (`dashboard.py`), a reader in `collect.py`, a tab in
  `assets/dashboard.html`, and a section in `references/data-contract.md`.

## Conventions

- Scripts are `uv run --script` with inline dependencies; every text read and write is UTF-8, every script
  with `__main__` reconfigures stdout/stderr, POSIX-only calls need a Windows branch, no `/home/<user>/` path
  is committed (`tests/test_portability.py`).
- A `SKILL.md` description is at most 1024 characters, its `name` is its folder, and it routes to its
  siblings with "Use manuscript-X for …" (`tests/test_scripts.py`).
- Writing for authors: plain words, quote rather than point, no per-item approvals by default
  ([author priorities](skills/manuscript-integrity-check/references/author-priorities.md)).
- A new skill also gets `agents/openai.yaml`, a row in the README's task table (and its skill counts), and
  usually an `evals/<skill>.yaml` case.

## Releasing

- Run `uv run pytest` (the whole suite).
- Bump `"version"` in both `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`, and `version` and
  `date-released` in `CITATION.cff` with the version in the README's BibTeX (`tests/test_citation.py` checks
  they agree); `pyproject.toml` stays at 0.1.0. There is no CHANGELOG file: the release notes are the commit message,
  `Release X.Y.Z: <what changed, in plain words>`, then prose paragraphs.
- Mention a new feature here and in the README, so the next session knows it exists.
