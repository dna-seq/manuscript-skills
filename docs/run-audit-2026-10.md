# What the Paper 1 v0.6 run broke, and what to fix next (audit, October 2026)

The `manuscript-improve` run on Paper 1 v0.6 of just-dna-lite (run `20261027T125139Z-488af17b`, started on
plugin 0.29.1 on 27 October 2026) finished, but only because the coordinator wrote five scripts of its own,
every editing stage wrote another, and the assembly took several attempts. This note reads the run's
records to find which plugin rules and scripts caused that, checks each cause against the plugin as it stands
on 28 October (release 0.38.0, commit `44e0e53`, plus the uncommitted work of a parallel session), and orders
what is still open.

## In short

- **The end of the run is where the plugin fails, and nothing there has changed since 25 October.**
  `collect.py` and `revise.py` last changed before the v0.5 run, which hit the same problems. Run on a copy
  of the v0.6 run today, without the run's wrapper, `collect.py` crashes on one proposal's evidence; once
  that and the missing `kind` fields are patched by hand, it counts 50 of the 129 applied main-text edits as
  proposals and draws the supplement's 59-entry scan as the paper's reference list, 33 entries of it marked
  wrong.
- **Stage outputs are checked five hours too late.** Each stage's `findings.json` is validated only when the
  dashboard collects everything, so a contract error made at 13:00 surfaced at 20:13, when the stage agent
  that made it was long gone.
- **The coordinator writes its own stage briefs, and they drift from the contracts.** Four of the run's
  errors trace to the 30 kB of briefs and the prompts it wrote: the reference check's prefix (`RC`, where every plugin file
  says `RF`), evidence as "a sentence of your report", proposals without `kind`, and `report.md` as the
  report's name.
- **No tool applies an edit to a manuscript that carries revision marks.** Five run scripts totalling about
  1,100 lines did it instead, one per editing stage, and one of them crashed mid-stage.
- **The re-check judged a version the authors never received.** Its verdicts belong to the first corrected
  version; the slips it found were fixed and the version rebuilt, and the plugin's rule "There is no second
  re-check" left the handed-over text unchecked. The dashboard marks it stale and nothing stops the handover.
- **Verbatim duplication is low; the conflicts are between a rule and the script that should enforce it.**
  Only four sentences appear in three or more skill files, all of them pointers to the shared references.
  The damaging conflicts are rules that a script contradicts (clean copies), two rules that cancel each other
  (fix and rebuild, but no second re-check) and promises the host cannot keep (a seat's "whole context is its
  brief").

## How this was checked

- The run folder: `run.json` (every stage's status, issues, commands and exit codes), each stage's report,
  findings and command output, the coordinator's four stage briefs and its `tools/` folder.
- The coordinator's session transcript and its 23 delegated agents' transcripts: 49 failed tool calls, every
  user message and the long idle gaps.
- The current plugin, read file by file. `collect.py` and `scan.py` were run on a copy of the run in a scratch
  folder, never on the run itself.
- A second opinion from Codex (read-only, given the same evidence and none of these conclusions). It ran on
  `gpt-5.6-sol`, not the authors' configured `gpt-6.1-sol`: the Codex CLI here was 0.152.0, too old for the
  newer model, and its refusal read "not supported when using Codex with a ChatGPT account" although the
  sign-in was a work workspace. Updated to 0.165.0, the same sign-in accepts `gpt-6.1-sol` (see the 0.43.0
  section below). It found the stale re-check, which this audit had missed, and agreed on version drift, seat
  isolation, the contract drift, the replay and the reference list. It could not run scripts in its sandbox,
  and it missed the edit scripts, the main-text-only revision, the bibliography insertion, the scanner bug, the
  lock and the length. Where we disagree is said below.

## What went wrong, and whether it is fixed

| What happened | What it cost | Cause in the plugin | Now |
|---|---|---|---|
| Every delegated agent's `report.md` was refused ("Subagents should return findings as text"), 15 times | a lost turn and a resent report per agent, about 11 agent-minutes | the report's file name | **Fixed** in 0.33.0 (`stage-report.md`, readers' `answer.md`); `runs.py save-report` is written but not committed |
| Pandoc's `{width=100% alt=...}` printed under every figure of the Word review | a re-render after the Google Doc was checked | the dashboard's Markdown reader | **Fixed** in 0.33.1 |
| Journal selection redone twice on 28 October; Genomics' guide read in the authors' Chrome | two extra attempts of the ladders | unread venue rules counted as fitting | **Fixed** in 0.35.0 and 0.37.0 |
| 28 of 43 agent-minutes of the night-before journal research spent fetching pages | about half an hour | no venue memory between runs | **Fixed** in 0.30.0 (dated venue catalogue) |
| The story readers passed an Introduction that turned to longevity without saying why | a missed finding | readers' silence read as a pass | **Fixed** in 0.38.0 |
| `collect.py` crashed or refused the inventory (string evidence, 12 proposals without `kind`, one supplement finding) | the first assembly attempt, a wrapper script | no stage-time validation; brief drift | **Open** (items 1, 4, 5) |
| 50 applied edits counted as proposals; the deslop stage's Supplement S12 edit replayed into Section 2.1 | a second wrapper; revise.py could not undo to the original | replay on marked text, change records without their file | **Open** (item 1) |
| The supplement's scan drawn as the paper's reference list | a failed rendering, a third wrapper | scanner and collector, both | **Open** (item 7) |
| Re-check verdicts belong to the first corrected version, not the one handed over | an unchecked deliverable | "There is no second re-check" | **Open** (item 3) |
| 15 supplement edits held by hand; 16 problems the re-check could not check, supplement fixes among them | manual choices file, blind spots | revise.py and recheck.py take one file | **Open** (item 2) |
| Each editing stage wrote its own edit script | about 1,100 lines, one crash, the run's `routine_fix.py` and `undo_check.py` | no edit tool for marked manuscripts | **Open** (item 6) |
| The plugin moved from 0.29.1 to 0.31.1 mid-run; a story agent hit `KeyError: 'venue_facts'` when the record format changed | a contradiction recorded in the run | no version pinned per run | **Open** (item 8) |
| An added reference appended to the previous entry's paragraph | a proposal held by hand (also in v0.5) | revise.py's insertion rule | **Open** (item 9) |
| The sceptical referee left out the Generation I objection "following the user's memory rule" | a referee that was not independent | host agents load the authors' standing instructions | **Partly fixed**, uncommitted (item 10) |
| Running text grew from about 6,880 to 7,470 words; the re-check rated the length problem worse | further from every venue's limit | no stage owns length | **Open** (item 11) |
| Stages competing for the run's lock exited with code 3; every brief had to say "retry ten times" | noise in every stage | the lock waits zero seconds | **Open** (item 12) |
| The story stage's supplement guard flagged numbers that had moved in from the main text (exit 1) | an explanation written by hand | guard has `--moved-to`, no `--moved-from` | **Open**, minor (item 13) |
| Stage agents called the app's task-list tool five times and were refused | noise | the brief does not say subagents have no task list | **Open**, minor (item 14) |

Not the plugin's doing: the story stage's four-hour gap (15:03 to 19:20 UTC) was the session's usage limit
("You've hit your session limit · resets 7:10pm"), after which the run resumed from its records as designed;
and Chrome timeouts during journal research. (This note first counted Codex refusing its configured model
here as well; that was an outdated Codex CLI, and the plugin's advice for it pointed at the weaker model.
0.44.0 fixes the advice.)

## The open items, most costly first

### 1. The assembly replays edits on marked text and does not know which file an edit belongs to

`manuscript-improve/SKILL.md` says "Every comparison of versions in this workflow (the claim guard,
`revise.py`, the change records) reads the clean copies", but `collect.py` replays the recorded clean
before/after texts on the marked snapshot and the marked master. An edit that a later stage edited again, or
whose span crosses a `<!-- @rev ... -->` mark, then counts as not applied. Change records carry no file, so
the replay ran every recorded change against the main text and applied the deslop stage's Supplement S12 edit
(a dangling "also") to the identical sentence in Section 2.1; the story stage's 2.1 edit then found no
before-text and the replay could not reach the revised manuscript.

**Change.** Strip marks in `collect.py` with `rev_marks.strip_marks` before the replay (the run's
`collect_clean.2.py` shows it works). Give each change record its file: `runs.py change --file
main|supplement|<input id>`, defaulting from the registered inputs, and replay per file. Refuse a before-text
that occurs more than once instead of taking the first.

**Test.** A fixture with a mark inside an edited sentence, a sentence edited twice by two stages, and one
sentence identical in the main text and the supplement. Acceptance: on a slimmed copy of the v0.6 run,
`collect.py` alone reports 129 applied main-text edits and 15 supplement edits.

### 2. The corrected version and the re-check cover only the main text

`revise.py` and `recheck.py prepare` each take one original and one working text. In this run the 15
supplement edits had to be held by hand ("the corrected version is built from the main text only"), and the
re-check left 16 problems unchecked, the supplement-only fixes among them, because it read only the main text.

**Change.** Let both scripts take the supplement as a second pair (`--supplement ORIGINAL WORKING`), build
`proposed-supplementary.md`, and give the re-check agent both texts.

### 3. The handed-over version was never re-checked

`recheck.json` records the sha256 of the first corrected version (`9e30ace…`). The re-check found 11 slips;
they were fixed as recorded edits and the version rebuilt, and revisions 2 to 5 and the handed-over
`paper1-just-dna-lite.proposed.md` are all `92907bb…`. The final dashboard says the re-check is not current.
Two rules cancel out: the re-check's exit 3 says "hold or reverse those edits and rebuild", and the same
message and `manuscript-improve/SKILL.md` say "There is no second re-check".

**Change.** After exit 3, allow one narrow second pass that reads only the passages the fixes touched (the
change records made after the re-check), and make `runs.py validate --final` refuse a handover whose re-check
hash differs from the corrected version's unless that pass ran or a reason is recorded.

### 4. Stage findings are validated only at assembly

`runs.py finish` checks that `findings.json` parses and has a findings list. The real contract is enforced by
`collect.py`'s models hours later: one proposal whose `evidence` was a string crashes it with a bare
`TypeError: string indices must be integers` traceback, and 12 proposals without `kind` fail the whole
inventory.

**Change.** Have `finish` validate the stage's `findings.json` with the same models `collect.py` uses, and
check that each `quote` occurs verbatim in the marked snapshot and each `before` exactly once in the working
copy (the run's `check_quotes.py`, which every stage was told to run, becomes part of `finish`). When
`collect.py` meets a bad record anyway, it names the file, the record's id and the field.

### 5. The coordinator's stage briefs paraphrase the contracts

The plugin tells the coordinator to brief each stage but gives it no brief, so it wrote 30 kB of its own:
`stage-brief-common.md`, `-editing`, `-revise` and `-assembly`. They carried the four errors above. The
improve skill's own one-line summary of a proposal ("the before, the after, the why and the finding it rests
on") also leaves out `kind` and the evidence.

**Change.** Ship the brief: a template in `manuscript-improve/references/` (or a `brief` command) that fills
in the run's paths, the resolved settings, the stage's prefix and the change contract from the plugin's own
files, so the coordinator adds only what is specific to the paper. Fix the summary sentence to name every
required field.

### 6. Applying an edit to a manuscript with revision marks is left to each stage

The editing brief describes a long procedure: find the clean before-text in the marked master, choose a span
with no mark inside, bump the enclosing segment or open a new one whose id matches the project's ledger
pattern, write before and after files from fresh clean copies, record each with `runs.py change`, then undo
every record to prove the chain. Each stage implemented it: the revise stage in 480 lines, the prose edit in
321, the story stage in 134 (which crashed once), the re-check fixes in 172, plus the run's `routine_fix.py`
and `undo_check.py`.

**Change.** One command, for example `rev_marks.py apply MASTER EDITS.json --run RUN --skill SKILL --by
claude`, that takes clean before/after pairs, places each in the marked master even across a mark, bumps or
opens the right segment, writes the change records and runs the undo check. `revise.py` already contains the
undo logic.

### 7. The dashboard's reference list comes from the wrong scan, and the scanner overruns

Two bugs together. `scan.py` ends a reference list only at the next Markdown heading; the supplement's
"References for Table S7" is followed by sections that open with a bold line ("**S8. Software
repositories.**"), so the current scanner still parses 59 entries where the list has 27, absorbing tables and
paragraphs down to the end of S13. And `collect.reference_list` takes the first scan in sorted order, where
`references-supplementary.json` sorts before `references.json`.

**Change.** End a reference list at a bold section line, a table or a run of paragraphs with no year or
identifier. Record in each scan which input it read, and have the collector draw the main text's list (and
the supplement's separately, if shown at all).

### 8. The plugin changes under a running run

The run used the source checkout, and other sessions committed to it during the run (0.29.1 to 0.31.1), and
again during this audit (0.37.0 to 0.38.0, with uncommitted changes to `runs.py`, `recheck.py` and
`scan.py`). The record format changed under the story stage.

**Change.** `runs.py start` records the plugin's version, commit and whether the tree is clean; each later
`runs.py` call warns or refuses when they differ. In practice: run from an installed or tagged copy, and develop
the plugin in a worktree, never in the checkout a run uses.

### 9. An added bibliography entry joins the previous entry's paragraph

`revise.py`'s `insertion_point` appends anything that is not a block (a heading, table, list or several
lines) to the anchor's paragraph with a space. In a bibliography with one entry per paragraph, a new entry
becomes the tail of the one before. The v0.5 and v0.6 runs both held such proposals by hand.

**Change.** When the anchor paragraph sits in a references section, or both it and the addition look like
reference entries, insert the addition as a new paragraph.

### 10. Simulated referees carry the authors' standing instructions

The run recorded that host agents start with the user's global instructions and the project's memory, and the
sceptical referee said it did not raise the authors' earlier prototype against "no existing tool"
"following the user's memory rule". The uncommitted `seat_copy.py` moves seat workspaces outside the project,
which keeps the project's `CLAUDE.md` away, but host subagents still start with what the session loaded.
`manuscript-improve/SKILL.md` still promises "a fresh agent whose whole context is its brief", and
`manuscript-other-models/SKILL.md` still says host seats have no copy, which the uncommitted
`workspaces.py` now contradicts. `models.py` and `seat_copy.py` each make their own temporary copy.

**Change.** Commit `seat_copy.py` with the story readers, the reference sceptic and the deslop critics on it,
not only peer review and the re-check; let `models.py` use it. State the limit plainly where the promise is
made. To remove the leak itself, run the panels as separate processes (`models.py run claude`, which starts
`claude -p` in the copy) when the authors want referees free of their standing instructions.

### 11. No stage owns the paper's length

Under `edits: apply` the stages add: conditions beside the speed ratios, a lead for Section 4, Background and
Significance subsections for the journals, story additions. Each is justified; together they took the running
text from about 6,880 to 7,470 words, and the re-check rated the length problem worse. The cut is deferred to
the journal choice, but nothing records the growth along the way.

**Change.** `manuscript-improve` records the starting word count; each editing stage reports its change in its
summary (the reader metrics already measure the text); an addition that no confirmed finding asked for is
offered with a cut of the same size, or held.

### 12. The run's lock gives up at once

`runs.py` takes `.writer.lock` with a zero timeout and exits 3 when another stage is registering a file, which
happens constantly while six review stages run side by side. **Change:** wait up to about a minute before
giving up.

### 13. The claim guard cannot see text that moved in from another file (minor)

`guard.py` accepts `--moved-to` for the file text left, but not the file it came from, so the supplement's
guard reports numbers moved in from the main text as new. Codex reads this as a safeguard working; it is, but a
`--moved-from` option would spare the stage explaining a correct move. The dashboard's refusal to overwrite
`dashboard.4`, which another session had rendered, is by design, as Codex also says.

### 14. Stage briefs do not say that delegated agents have no task list (minor)

Five stage agents called the app's task-list tool and were refused. One line in the brief template (item 5).

### Already designed, not built: a source cache

`docs/cacheability.md` shows that a source cache would have prevented one wrong finding: v0.5 had read the
open-access full text of Mordaunt et al. 2024 naming equipment, v0.6 saw only the abstract and proposed
deleting "equipment" from the paper. Its design (cache the fetched texts by work, never the verdicts) stands.

## Fixed in 0.44.0

Checked on a copy of the v0.6 run, with the masters as they stood at the run's end (just-dna-lite
`c176c69`): with the stage files as the run wrote them, `collect.py` now names every record it cannot read
(the 12 missing `kind` fields and 4 evidence sentences) instead of failing on the first; with those records
fixed, it counts all 129 main-text and 15 supplement edits as applied, puts the Supplement S12 edit in the
supplement and draws the main text's 31 references, and `revise.py` with the run's own adjudication and
choices builds a corrected version byte for byte the one the run handed over. The run needed three wrapper
scripts for that.

- Item 1: `collect.py` replays the change records on clean copies, each on its own file (`document`, named by
  `runs.py change --document`, or for older records inferred from where the text is and a "Supplement"
  section); an addition no longer spoils the replay. `revise.py` leaves another file's changes alone and lists
  them as `other_files`; the changes workbook counts them as applied.
- Item 4: `scripts/stage_check.py` (manuscript-dashboard) checks a stage's findings; `runs.py finish` refuses
  until they meet the contract, and `collect.py` lists what it cannot read. On the v0.6 run it would have
  flagged, at each stage's finish, the 16 records above, the `RC` prefix, and four supplement proposals the
  coordinator held back by hand.
- Items 5 and 14: `manuscript-improve/references/stage-brief.md`, the brief the coordinator fills in; it
  also tells a delegated agent that it has no task list.
- Item 7: the scanner ends a reference list at a bold section line or a table and skips revision-mark lines
  (27 entries in the v0.6 supplement, was 59); the collector draws the scan of the manuscript.
- Item 8: `runs.py start` records the plugin (version, commit, uncommitted changes), and `finish` records it
  as an issue when a stage finishes on another.
- Item 12: `runs.py` waits up to a minute for another stage's write.
- Codex (`manuscript-other-models`): `detect` and `check` say how Codex is signed in (a work workspace, a
  personal plan or a stored key) and when its model list came from another CLI version; a refused model is
  answered with "update the CLI, then check the sign-in", never a quiet older model; a seat is started with
  its model named (`codex exec -m gpt-6.1-sol`), the configured default included.

## Fixed in 0.45.0

- Item 2: `revise.py --supplement-original --supplement-working` builds the supplement's corrected version from
  its own changes by the same rules and choices (`supplement-proposed`, and `supplement` in `revision.json`);
  `recheck.py prepare --supplement-original` gives the re-check agent both versions of the supplement, and its
  quotes may come from either file; `runs.py handover` puts the supplement's corrected version beside the
  supplement. On the v0.6 copy the supplement's 15 applied edits undo exactly to the reviewed supplement, and the
  re-check would have read 37 supplement changes its first run never saw.
- Item 3: after the first re-check's exit 3, the rebuilt version gets one narrow second re-check (`prepare
  --since ... --previous ...`): the problems the first found made worse, the new ones it found introduced, and
  those whose quoted passage the fixes changed; the rest keep the first's verdict. `runs.py validate --final`
  refuses a handover whose newest re-check read another build, unless the re-check stage records why.

## Fixed in 0.46.0

- Item 6: `rev_marks.py apply` and, in a run, `runs.py apply` take a stage's edits as clean before/after pairs,
  find each in the clean text however the marks sit, change only the words that differ, bump each touched
  segment once for the pass, open or grow the section's copy-edit segment (or an edit's own) for edits no segment
  holds, taking in whole a segment it would cut, write the change records and replay them to prove the result.
  On the v0.6 run's marked snapshots all 144 recorded edits apply this way, with no lint error, ending on the
  run's clean main text and supplement exactly; the four that no segment held open N11 to N14, after the
  master's N10. The five scripts the run's stages wrote for this are no longer needed.
- Item 9: `revise.py` puts a reference entry added after another, in a list of one entry per paragraph, in a
  paragraph of its own.

## Fixed in 0.47.0

- Item 10: every panel seat (referees, readers, the defender, critics, the sceptic, the re-check) runs as a
  separate session through `models.py run`, on the host's own CLI as well, in a copy outside every project, and
  that session leaves the authors' own setup out: Claude Code reads no user settings (`--setting-sources
  project,local`), so not their CLAUDE.md, hooks or plugins, and Codex no user config (`--ignore-user-config`),
  so not its plugins, skills or MCP servers, its configured model and effort passed on the command line. Checked
  on this machine: asked whether any instruction or memory says to push to main without asking, or that the
  authors' own prototype is not prior art, a seat started this way answers no; the same question from inside the
  project, user settings left out, still finds the memory rule; a Codex seat lists 15 bundled skills instead of 77
  entries. `seat-run.json` records what reached each seat (`standing_instructions`); Gemini CLI still loads the
  user's GEMINI.md. A host subagent is the fallback, and the report then says its seats carried the authors'
  instructions and memory. The wording that promised "whole context is its brief" now says what is true.
- Item 11: `runs.py start` records each input's length (words of the clean running text up to the references),
  `finish` and `stage --name revise` record it after every stage that edits, and the run index shows each with
  its change since the run began. The improve skill and the stage brief ask that an addition nothing asks for
  come with a cut of its size, or stay a proposal, and that the summary give the length before and after.

Still open: item 13, and the source cache.

## Suggested order

1. **Before the next run** (small, each removes a run-local script): items 4, 1, 7, 12 and 5, then pin the
   version (item 8). Acceptance: a slimmed copy of the v0.6 run collects, revises and renders with the
   plugin's scripts alone.
2. **Next:** the edit tool (6), the supplement in `revise.py` and `recheck.py` (2), the second re-check and its
   gate (3), the bibliography insertion (9).
3. **Then:** seat isolation (10), the length record (11), `--moved-from` (13), the source cache.

The parallel session's uncommitted work (`save-report`, `seat_copy.py`, the re-check workspace outside the
project, venue lengths) touches items 10 and the report names; whoever takes items 3 and 12 should start from
it rather than beside it.
