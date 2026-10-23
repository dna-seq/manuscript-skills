# Project setup and inspectable skill runs

Read this when starting any manuscript skill, including one invoked directly. It governs saved project
choices and delivery; the skill still governs its scientific work. Commands below are relative to
`manuscript-integrity-check/`; use the equivalent sibling path from another skill.

## Ask once for a manuscript project

Run `uv run --script scripts/project.py resolve AUTHORITATIVE_SOURCE --json`. For a connected document,
also give `--project LOCAL_PROJECT_FOLDER`. Use the authoritative source, not a temporary reading copy.

On first use, ask one short batch only for the missing `questions` returned by the resolver:

- Which folder/files or connected documents are the authoritative manuscript and supplements?
- Which code repositories are connected? None or unknown is a valid answer. Do not require code for a
  prose-only task. A code location is context, not permission to edit it.
- Where should the review outputs go? Recommend a concrete `reviews/` folder in the manuscript's folder,
  with the resolver's reason: the runs stay with the paper, where the authors and co-authors look, and
  later runs and the next revision reuse them. For cloud storage, establish its URL and a local working
  folder; the helper does not upload files.
- How should the skills work? These are the resolver's `preferences`, the settings nobody has chosen for
  this project or globally: `edits`, `reports` and `keep`. Ask them as one question that names each
  recommended answer with its `why` (routine fixes applied and the rest proposed; reports saved as files
  with the headline in the chat; every intermediate file kept, because later steps and the dashboard read
  them and every finding can be traced back), so that "yes" accepts them all and the authors change only
  what they want. Save what they answer with `configure --edits ... --reports ... --keep ...`.

Use answers already supplied in the conversation or project instructions. Show inferred locations in
the batch rather than asking the author to rediscover them. Continue independent read-only work while
required answers are pending. Preferences never hold up a run: until they are answered the defaults
apply, unsaved, and the next run asks again. "Use your recommendations" is an answer, saved like any
other. Do not silently turn a guess into a saved author choice; setup copies only the choices saved
globally, never the defaults.

Save stated choices with `project.py configure PROJECT_FOLDER --manuscript SOURCE --code CODE_FOLDER
--output-dir reviews --edits conservative --reports file --keep everything`, giving only the settings the
authors answered. Repeat `--manuscript` for supplements and `--code` for multiple repositories;
use `--no-code` or `--unknown-code` when that is the answer. Locations are relative to PROJECT_FOLDER. A supplied manuscript folder needs its main source file
identified before a run can snapshot it; code locations may be folders.
`--document URL` records a connected document, and `--output-url URL` a cloud destination. A remote
authoritative manuscript can itself be a `--manuscript URL`; preserve its exported reading copy in the
run evidence and record the connected version when available.

The local `.manuscript-skills.yaml` is the project configuration, not another manuscript version or
the scientific shared record. Every skill finds the nearest one or uses an explicit `--project`.
It records manuscript sources, code locations, the output root and choices for this project. Keep it
outside run folders. It preserves unrelated keys when updating an explicit choice.

## Reuse choices and resolve actual conflicts

Precedence: explicit current conversation instructions, project choices/instructions, global settings,
then defaults. `project.py resolve ... --reports chat --edits propose --keep results` applies a conversation
override without saving it; the same options on `configure` save an explicit lasting project choice.
Project setup copies the choices saved globally into the new project, so a later global change does not
silently alter an existing manuscript's choices; it never copies a default nobody chose. A global change is
for other projects unless explicitly applied here.

Do not repeat setup for another skill, a resumed run or a new revision of the same paper.
When the author explicitly identifies a new revision as this same manuscript, update the relevant source
with `configure` while retaining other sources and saved choices; do not create a new project or ask
for the same code/output answers again. Re-ask only
when the author explicitly wants a change or the resolver finds a material inconsistency: a missing
source, a requested paper outside the mapping, or an inaccessible destination. State the exact conflict
and ask only the necessary question. A blocked URL or disagreement between reviewers is a finding to
record, not a reason to restart setup. Independent checks continue while a mapping conflict is resolved.

`peer_review` is a project setting: `auto` (default) runs formal referees for a whole-manuscript
improvement workflow; `on-request` runs them when requested; `off` skips that optional stage. A focused
skill never expands into full peer review because of this default. A story task still runs its
readers (the default three, or the readers saved for the project). Explicitly asking for referees overrides `off` for that invocation. Save a lasting choice with
`configure PROJECT_FOLDER --peer-review on-request`, not a made-up global YAML key.

Who reads the paper is the authors' choice too: `configure PROJECT_FOLDER --reader "clinician: a hospital
physician who orders genetic tests" --reader ...` saves the story panel's readers, and `--referee` adds
up to two custom referee seats; `--default-panels` returns to the default seats.

For linked papers use `--related-manuscript LOCATION` and record their relationship in the scientific
shared record. Companions keep their own project choices. Read both when publication order, overlapping
claims, cross-citations, shared releases or preprint updates depend on the relationship.

## One run, one folder per applied skill

Start a run after its destination is established:

```bash
uv run --script scripts/runs.py start SOURCE --skill manuscript-story
```

The command prints the absolute run directory, `RUN` below. It saves source snapshots/hashes, effective
settings and a run index. Reuse RUN for every companion skill and for a continuation; a new execution
gets a unique directory. Add each newly applied skill with its first artifact or command. Only the
coordinating agent updates the manifest; reader/referee agents write their own reports and the parent
registers them sequentially. The helper also locks the manifest: a concurrent writer exits 3 without
changing evidence. Retry after the active operation ends. Interrupted command logs are retained and
registered by the next attempt, with their unknown original exit status clearly stated.

Write conclusions, checks and failed attempts under `RUN/SKILL/`, not in a disposable scratch folder.
Each skill gets a generated `README.md` linking its evidence and showing its status. Save the actual
author-facing report as `report.md` or another descriptive filename. Only the skill-root `README.md`
is reserved; source READMEs can be retained under evidence subfolders. Beside the report, write the same
findings as `findings.json` ([stage findings](../../manuscript-dashboard/references/stage-findings.md)):
one record per distinct problem with its verbatim passage, severity, stage and evidence, plus what was
dismissed and what could not be checked. `manuscript-dashboard` counts the run from these files and
never infers that a skill without one found nothing. Register outputs, including files
already written there:

```bash
uv run --script scripts/runs.py add RUN --skill manuscript-story --file REPORT --role report --name report.md
uv run --script scripts/runs.py add RUN --skill manuscript-story --file READER --role reader --seat skimmer --isolation fresh-agent --name readers/skimmer.md
uv run --script scripts/runs.py exec RUN --skill manuscript-story -- uv run --script METRICS SOURCE
uv run --script scripts/runs.py issue RUN --skill manuscript-story --kind contradiction --message 'Explain the actual disagreement and its consequence.'
```

Use `--seat potential-user` and `--seat informed-outsider` for the other story readers. For formal peer
review, retain three distinct `referee` reports with their seat names, plus `defence` and `adjudication`
artifacts. For the documented two-seat quick pass, use `seat` artifacts named `desk-editor` and
`evidence-statistics` with defence and adjudication, then `finish ... --review-mode quick`; these are
findings, not fabricated full referee reports. `--review-mode invited` labels invited-referee work.
Preserve reader/referee task briefs and the reading copy. Register reusable checks as `check`
and source/edited comparisons as `comparison`. Preserve blocked sources, disagreements, failed commands,
their interpretation and any later resolution. `exec` records attempt metadata before launch and streams stdout/stderr directly to durable files;
it records the true exit code on completion. Interrupted attempts keep their partial output and unknown exit status; it never treats a zero exit code as scientific validation. Retain a failed attempt when rerunning
successfully. Evidence cannot be silently overwritten; register the next attempt under a new filename.

When a stage runs as a delegated agent, the host may refuse to let it create report files (one harness
answers "subagents should return findings as text"). Then the agent returns the finished report as text,
or leaves it in scratch, and the coordinator saves it unchanged under the stage's folder and records an
issue saying so; it never rewrites the report while copying it. Stages that run at the same time and
browse each open their own browser tab: a shared tab navigated by another stage loses the page a
stage was reading.

Large downloads and unrelated intermediates can still use scratch. Anything needed to inspect or
reproduce a reported conclusion belongs in the run folder: actual seat reports, check outputs, source
identifiers, coverage, contradictions and failures. Do not retain credentials or unrelated personal
data. A concise combined workflow summary links the per-skill folders; it does not replace them.
The `reports` setting controls how much report text is also shown in chat; run evidence stays inspectable.
The `keep` setting decides only what stays visible once the run ends (see the handover below); a run
records the same evidence whichever it is.
Stable project documents, such as the scientific record and venue planning document, remain in place;
register the version used or produced in this run rather than moving their authoritative masters.

## Independent readers and referees

A simulated referee, reader, defender or critic is worth running only if it has not watched the work it
judges being done. The coordinator has: it read the authors' messages, the record, the other stages'
findings and its own edits. Whatever of that reaches a seat (a summary of the paper, a list of known
problems, a hint where to look, what the authors meant, what the run changed) makes the seat repeat the
coordinator instead of reading the paper. These rules hold in every skill that runs a panel
(`manuscript-peer-review`, `manuscript-story`, the deslop reflection loop) and are not optional:

1. **A fresh agent per seat.** Each seat runs as a new agent whose whole context is its brief: in Claude
   Code, the Agent tool with a general-purpose agent, never a `fork` (a fork inherits this conversation)
   and never a message to an agent that has already worked on this paper; in other hosts, their
   equivalent of a new agent. One agent per seat: a reader is never reused as another reader, a referee
   never as the defender.
2. **The session that can start agents starts them.** A delegated agent often cannot start agents of its
   own (Claude Code's subagents cannot). In `manuscript-improve` the coordinator starts every referee seat,
   reader, defender and critic itself, even when it delegates the rest of those stages; a stage agent that
   cannot start agents prepares the workspaces and briefs and hands them back, and never reads as the
   seats itself.
3. **The brief is the skill's template, filled, and nothing else**: the journal, article type, study
   design, remit, or the reader's description in the authors' words. Give paths to the workspace files,
   never extracts the coordinator chose. Save each brief exactly as sent beside the seat's report.
4. **The workspace is all the seat may read.** It holds the reading copy and what the seat's brief lists,
   and the brief tells the seat to open nothing else: no other file of the project or the run, no git
   history, no search for other reviews of this work.
5. **Record how each seat ran.** Register its output with `--isolation fresh-agent`, or `--isolation
   one-agent` under the fallback below. `runs.py validate` refuses a completed story or peer-review stage
   whose reader, referee, seat or defence output does not say, and the dashboard shows which seats were
   not independent. For a run registered before this rule, `runs.py isolation RUN --skill SKILL --path
   PATH --isolation fresh-agent --basis "..."` records how an output already in the run was produced,
   with what shows it; a record already made is never changed.
6. **Fallback only when the host cannot start agents at all**, or when a seat still fails after one retry
   (that seat alone falls back), not because a stage was delegated, is slow or runs in the background (a
   host that reports completion can run seats in the background). Then one agent reads once per seat, in
   order, writes each seat's answer before taking the next and never revises an earlier one. Record
   `--isolation one-agent`, label each such seat "read by one agent in turn, not independent" in the
   report, and never count agreement between such seats as corroboration.

## Before/after and honest handover

Show exact consequential before/after text, the section and a reason promptly in chat, including full
additions and deletions. Save it as well with `runs.py change RUN --skill SKILL --section SECTION
--reason REASON --before BEFORE_FILE --after AFTER_FILE --shown-in-chat`. The reason is one to three
sentences, what was wrong and why the new wording fixes it, its first a short title: the dashboard shows the
first as the edit's summary and the whole as its reasoning. Omit `--before` for an addition,
`--after` for a deletion. `shown RUN --skill SKILL --number N` can acknowledge an existing change after
showing it. These flags are agent attestations: the script cannot see or verify the conversation.
A diff link does not satisfy the chat requirement. Classify genuine routine-only changes with a
specific `--routine-only-reason` when finishing, rather than fabricating consequential excerpts.

Finish each skill with `runs.py finish RUN --skill SKILL --status completed`. Use `partial`, `blocked`,
`not_run` or `reused` with `--reason` giving actual coverage, the obstacle or the reused source. Completed
story and peer-review runs require their respective reader/referee evidence. A report is not complete
because an internal agent finished thinking, a PDF built or a Google Doc synchronized.

Before handover run `runs.py validate RUN --final`. It detects missing/tampered evidence, incomplete
statuses, missing panel artifacts, changed manuscript snapshots without a change explanation and
unacknowledged before/after records. It does not prove scientific correctness, independence of seats,
completeness of edit classification or actual delivery in chat. Review those directly. Partial work can
have a valid handover while the manifest still says `workflow_complete: false`.

When the effective `keep` is `results`, the last step, after the final validation and after the dashboard
is rendered, is `runs.py pack RUN`. It refuses a run that does not validate; it leaves `run.json`, the
README files, every registered `report`, the dashboard (`manuscript-dashboard/*.html` and `*.docx`) and the
corrected version (`manuscript-improve/revision/proposed.md` and `changes.md`), plus any `--keep PATTERN`,
and moves everything else into `evidence.zip`, recording each file's hash. `validate` checks packed files
inside the archive. Every other writer refuses a packed run (exit 3): run `runs.py unpack RUN` first to
continue it, add evidence or collect the dashboard again. With `everything`, never pack.

Link the run index and each important report in the reply, state remaining gaps and show consequential
excerpts as the work proceeds. Never label an incomplete reference audit or missing panel complete.
