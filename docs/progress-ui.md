# Progress view for a run (prototype)

A `manuscript-improve` run takes two to four hours, and until now the authors followed it only through chat
messages. The prototype is a Claude Code mod (a plugin hooks module) that reads the run folder and shows
where the run stands, without anyone asking. It reads; it never writes in the run folder or the manuscript.

Status: a dev mod, tested against the Paper 1 v0.6 run of 2026-10-27, not shipped. Its source is in the
Claude Code session's mods folder (`~/.claude/dev-mods/<session>/manuscript-run/`) until the decision to
ship it, below.

## What the authors see

- **Status line**: `Paper 1 v0.6 · 9 of 18 stages · deslop running · 86 edits applied · 48 held`.
- **Pane "Manuscript run"**: one bar per phase (review; editing: revise, prose edit, deslop, story, journal
  adaptation; assembly: dashboard, corrected version, re-check, Word review, changes workbook, handover);
  each stage's state, elapsed time and counts (findings, proposals, applied edits, decisions held for the
  authors); a button to open each stage's report; the referees' recommendations as seats by journals once
  peer review has them; the settings the run started with and where each came from (`edits: apply
  (project)`, `versions: in-place (default)`), with what each means; and buttons that open what the authors
  can read while the run goes on: the run index, the manuscript being edited, the newest edit's
  before/after, and later the dashboard, the corrected version, the Word review and the changes workbook.
- **Band above the prompt**, only while the run waits for the authors, with a button that opens the
  decisions at the top of the pane.
- **Toast** when a stage finishes (`Prose edit finished: 5 findings · 1 proposals · 30 edits · 3 held`),
  and a native notification when the run ends or starts waiting for the authors. In the desktop app the
  native notification is not available to mods yet, so it shows as a longer toast.
- **`/manuscript-status [path]`** opens the pane and answers with the same state as text; `forget` stops
  watching. A tool, `show_run`, does the same for the model, so a coordinator that starts a run can open
  the pane for the authors.

The pane, band, status line and toasts draw in the terminal and in the desktop app alike.

## Which run it shows

The newest run folder under the output folder of the nearest `.manuscript-skills.yaml` (its `output_dir`,
`reviews` by default), from the session's folder upwards; or the run, project or output folder given to
`/manuscript-status`; or the run a `runs.py` command names (a `tool.call` hook on Bash commands that run
`runs.py`). The choice is remembered across sessions. It refreshes every 15 seconds and right after each
`runs.py` call, re-reading `run.json` only when its size or modification time changed.

## What it reads, and what it has to guess today

It reads `run.json`; each stage's newest `findings*.json` (counts and the findings marked `decision: true`);
the peer-review adjudication (its `reports[].recommendations`); the newest `revision*/revision.json`
(questions for the authors); and the names of the files in `manuscript-dashboard/` and
`manuscript-improve/`, to see which deliverables exist. Everything else it would need is not recorded yet:

| What the view shows | How it is found today | The problem |
| --- | --- | --- |
| a stage has started | its entry appears with its first record (`add`, `exec`, `change`) | a stage that has started but recorded nothing yet shows as next, not running |
| elapsed time | review stages from the run's start, editing stages from the end of the one before, to the last record; shown with `~` | `finish` records no time, and nothing records a start |
| the revise stage | `manuscript-improve/stage-brief-revise.md` and `revise/report.md` registered under the coordinator | an internal stage of the coordinator has no entry of its own |
| corrected version, re-check, handover | files in the run folder (`revision*/proposed*`, `recheck.json`) and `handover` in `run.json` | not recorded as stages, so they have no status or time |
| decisions held | findings with `decision: true`, added up over the stages | the same problem found by two stages counts twice until the dashboard's inventory exists |
| the run waits for the authors | the coordinator finished and decisions remain | a run that stops mid-way for an answer records nothing |
| how many stages there are | the stages the full workflow has, whether or not this run will reach them | a stage the run will skip counts until it is skipped |

## Records `runs.py` could add

All optional, so older runs and the view's fallbacks keep working.

1. **Start and finish times.** `ensure_skill` writes `started_at` when it creates an entry, and
   `runs.py begin RUN --skill NAME` writes it before a stage records anything (idempotent: an existing
   `started_at` stays). `finish` writes `finished_at`. The view then shows elapsed time without `~`.
2. **The coordinator's own stages.** `runs.py stage RUN --name revise --status running|completed|...`
   keeps `skills["manuscript-improve"]["stages"][name] = {status, started_at, finished_at, reason}` for
   revise, corrected version, re-check and handover, so they read like the other stages.
3. **Waiting for the authors.** `runs.py wait RUN --question TEXT` (repeatable) writes `waiting = {since,
   questions}` at the top of `run.json`; `runs.py resume RUN` clears it. The view already reads `waiting`.
4. **The plan.** `start` (or `begin` on the coordinator) writes `plan`, the stages this run means to run,
   so the count is right from the start and a skipped stage is known before it is reached.
5. **Counts at finish.** `finish` already reads the stage's `findings.json`; it could store `counts =
   {findings, proposals, decisions}` in the entry, so the view needs `run.json` alone until the dashboard.

## Shipping it in the plugin

A Claude Code plugin loads hooks modules from `hooks/hooks.json` at its root:
`{ "modules": ["./progress/register.tsx"] }`, with the module, its view model and tests in
`hooks/progress/` and the state contract named in `.claude-plugin/plugin.json` as `"types"`. Then every
session with the plugin shows the pane, and the `runs.py` hook works in the session that runs the
workflow. Before shipping:

- the function-hooks API is early access and changes between Claude Code releases; check what an older
  Claude Code does with a `hooks/hooks.json` that holds `modules` (it should ignore it, not refuse the
  plugin), and pin the minimum version in the README;
- run `claude plugin validate` and `claude plugin test` in CI beside the Python tests;
- decide whether the pane opens by itself when a run is found or only on `/manuscript-status`.

**Codex users would not see it.** Codex has no equivalent of these hooks or panes; there the run's state
stays in the chat and the run index (`README.md` in the run folder). A `runs.py status RUN` command that
prints the same summary as `/manuscript-status` would give both hosts one text view, and the mod could
show that command's output.
