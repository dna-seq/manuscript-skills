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
| manuscript-coauthors | Rounds with co-authors on Google Drive: the `coauthors` project settings, comments pulled from Google Doc exports into `vX.Y/comments.yaml`, how the next round answers each, the changelog Why from comments, releasing rounds to Drive. |

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
- Bump `"version"` in both `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`; `pyproject.toml`
  stays at 0.1.0. There is no CHANGELOG file: the release notes are the commit message,
  `Release X.Y.Z: <what changed, in plain words>`, then prose paragraphs.
- Mention a new feature here and in the README, so the next session knows it exists.
