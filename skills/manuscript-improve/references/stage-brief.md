# Stage brief (the template a coordinator fills in for each stage agent)

Each stage of a `manuscript-improve` run that another agent carries out gets this brief, with the `{...}`
fields filled in and nothing in it paraphrased. A brief the coordinator wrote itself in the Paper 1 v0.6 run
carried four errors into the run (a wrong finding prefix, evidence as a sentence, proposals without `kind`, a
report name the host refuses), each found only when the dashboard was assembled hours later. Add the
paper-specific facts under "This paper" and the stage's own instructions under "This stage"; keep the rest.
Panel seats (referees, readers, the defender, critics) never get this brief: theirs is their skill's template.

---

You are the `{SKILL}` stage (finding and proposal prefix `{PREFIX}`) of a manuscript-improve run of the
manuscript-skills plugin, version {VERSION}. Follow `{PLUGIN}/{SKILL}/SKILL.md` for the whole paper and its
supplement, and this brief where they meet. The coordinator starts any panel agent your skill needs and
assembles the run.

## Paths

- Plugin skills: `{PLUGIN}` (run each skill's scripts from its folder with `uv run --script`; change nothing
  there).
- The run: `{RUN}`; your folder is `{RUN}/{SKILL}/`. Write everything there.
- The manuscript and its supplement as the run took them (what you quote): `{RUN}/inputs/{INPUTS}`; their
  clean copies (without revision marks, what you read and what before-texts are copied from):
  `{CLEAN}`.
- The working copies (the authors' files; only an editing stage changes them): `{MASTERS}`.
- The project's code, data and benchmarks (read-only): `{CODE}`.

## Settings

{SETTINGS: the run's resolved settings in plain words, from `project.py resolve` and the authors' answers:
`edits`, `versions`, `reports`, `peer_review`, other models, the journal or the ladder and what may be adapted
before the choice, the paper's stage of work}

## Rules

1. **Proposals, in full.** A review stage edits nothing; each correction it can settle is a proposal in
   `findings.json` `changes`, with every field of the change record
   ([data contract](../../manuscript-dashboard/references/data-contract.md#changes-and-evidence)): `id`
   (`{PREFIX}-C1`), `kind` ("Proposed edit"), `section`, `summary`, `status: "proposed"`, `before` copied
   exactly from the clean working copy and occurring there once (or `before: null` and an `anchor` for an
   addition), `after`, `why` (what was wrong and why this wording fixes it), `finding_ids`, `evidence` as a
   list, `[{"path": "stage-report.md", "quote": "the report's sentence that gives the reason"}]`, and
   `comment` for a question to the authors, never a placeholder in `after`. A proposal for the supplement
   names it: `"document": "{SUPPLEMENT_NAME}"`.
2. **Quotes.** A finding's `quote` is copied word for word from the manuscript as the run took it, at least
   three words, from a stretch with no revision mark inside it.
3. **Check, then finish.** Before `finish`, run
   `uv run --script {PLUGIN}/manuscript-dashboard/scripts/stage_check.py {RUN} --skill {SKILL}` and fix what it
   lists in the next attempt (`findings.2.json`); `finish` refuses the same problems. Never change a file
   after registering it.
4. **Register** every output with `runs.py add` and capture commands with `runs.py exec`
   (`{PLUGIN}/manuscript-integrity-check/scripts/runs.py`). A command waits up to a minute for another stage's
   write; on exit 3 after that, retry once the other stage is done.
5. **File names.** Your report is `stage-report.md`. Claude Code refuses a delegated agent any Markdown file
   whose name starts with `report`, `summary`, `findings` or `analysis`; `findings.json` is not Markdown and
   is allowed. When the host refuses a file anyway, return its full text in your final message and say so;
   the coordinator saves it unchanged.
6. **Panels.** You cannot start agents. Where your skill runs a referee, reader, defender, critic or
   sceptic, prepare its workspace and brief as the skill says, save them in your folder, and return what must
   be started (seat, workspace, brief); never read as the seat yourself.
7. **Independence.** Do not open other runs' folders, earlier dashboards or reviews of this paper, other
   stages' folders in this run, or the coordinator's notes. {READABLE: the files about the paper you may read}
8. **Check the project before asking.** A number, version, default or behaviour that the code, the data or
   the run logs settle is corrected from them (cite the file and line in the evidence), never asked.
9. **No task list.** A delegated agent has no task list or wrap-up of its own in the app; do not call those
   tools.
10. **Writing.** For the authors: plain words, full sentences, quotes with their section, links for outside
    sources, no internal codes standing alone.

## Editing stages also

- Lint the marks before the first edit (`rev_marks.py lint`), and write clean copies of the working copies
  before and after the pass (`rev_marks.py strip ... --out`): `{CLEAN_PREFIX}before-{STAGE}.md` and
  `after-{STAGE}.md`, with `-supplementary` beside them.
- Apply your edits with `runs.py apply {RUN} --skill {SKILL} --edits EDITS.json --by {AGENT}` (an edit to the
  supplement: a second list with `--document {SUPPLEMENT_NAME}`). EDITS.json is a list of
  `{"before": ..., "after": ..., "reason": ..., "comment": ...}`, clean text copied from the clean copy, one
  item per consequential edit (routine fixes may share an item per paragraph); an addition is the passage it
  follows, before and after. It finds each edit wherever the revision marks sit, marks it as
  [manuscript-revision-marks](../../manuscript-revision-marks/SKILL.md) says, records it and refuses the whole
  list, changing nothing, when one edit cannot be placed: lengthen a before-text that occurs twice, split an
  edit at a mark it would swallow. An edit a finding asked for may name the segment it opens (`"segment":
  "IC3"`, an id the project's ledger accepts). Write no edit script of your own.
- After the pass: the claim guard and the smell check on before and after, as your skill says, and fix what
  they list before you finish.
- Keep the length: an addition no confirmed finding and no requirement every venue shares asks for comes with
  a cut of about its size in the same section, or stays a proposal. `finish` records the paper's length after
  your pass; give its change in your final message.

## This paper

{PAPER: what every stage needs and no file says: the authors' standing preferences, the ethics position, how
AI was used, the venues being considered}

## This stage

{STAGE: what this stage covers in this run, and anything the coordinator needs back}

Your final message to the coordinator: under 250 words, with the status, the counts (confirmed, candidate,
dismissed, proposals), the three most consequential findings in one line each, anything that must be
started, and the paths of your report and findings; an editing stage adds its most consequential edits, before
and after, one line each.
