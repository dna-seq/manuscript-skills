# Behavioural evaluations

Script behaviour is tested by `pytest` under `tests/`. These cases test the skills themselves: whether an
agent following a SKILL.md does the right thing on a realistic request. A person can run and grade one by hand
(below), or `evals/plugin_eval.py` runs them with `claude plugin eval`, with and without the plugin, and grades each
run a second time on a model of another family.

## Layout

- `evals/<skill-name>.yaml`: the cases for one skill.
- `evals/fixtures/<skill-name>/`: the manuscripts, reviews and other files the cases use. Every defect a
  fixture contains is planted on purpose and listed in the case that uses it. Each skill with a defect
  fixture also has a clean control: a version with the defects repaired.
- `evals/results/YYYY-MM-DD-<skill-name>.md`: recorded runs.

## Case format

```yaml
- id: peer-review-seeded-01
  skill: manuscript-peer-review          # the skill the request should reach
  prompt: >-
    Red-team this draft before we submit it to Bioinformatics.
  files: [fixtures/manuscript-peer-review/seeded.md]
  settings: {reports: file, edits: conservative}  # optional saved choices to seed before the run
  planted:                               # what the fixture contains, for the grader only
    - "Table 2 reports n = 412; the Abstract says 421."
  rubric:                                # every item must hold for a pass
    - "Reports the n mismatch with both locations."
    - "Every finding quotes the manuscript verbatim or names where it looked for an absent item."
    fail_if:                               # any one fails the case
    - "Invents a number, result, citation or reviewer comment."
    - "Edits a file the request did not ask to change."
    - "Gives an acceptance probability or a venue score."
  anchors:                               # optional: each planted item by number, pinned in its file
    - {item: 1, id: n-mismatch, anchor: "On 4,812 held-out ClinVar missense variants", file: fixtures/manuscript-peer-review/seeded.md}
  pairs:                                 # optional: a case whose verdicts must match, or differ from, this one's
    - {with: peer-review-clean-01, expect: different}
```

An anchor is words copied from the fixture that occur there exactly once; `tests/test_evals.py` fails when one
no longer occurs, occurs twice, or occurs in the clean control (`in_clean: true` marks context that the clean
version keeps, such as the sentence a missing analysis should have changed). An item in an image or an absence
gives its `file` and no anchor. A pair is two cases one file apart: a response letter written confidently and
plainly must get the same verdicts (`expect: same`), and the same letter against a revision where its change
landed and one where it did not must get different ones (`expect: different`). Each case's rubric spells the
verdict its own files call for, so a pair holds when both cases pass.

## Running a case

1. Stage the case outside the repository:

   ```bash
   uv run --script evals/stage.py CASE_ID            # or --to an empty folder outside the checkout
   ```

   It copies the case's files to a new working folder under neutral names (`seeded.md` and `clean.md` both
   become `manuscript.md`, `edited-seeded.md` becomes `edited.md`, a `seeded/` or `clean/` folder becomes
   `paper/`), blanks any comment in them that calls the file a fixture or names its condition (keeping the
   lines, so cited line numbers hold), rewrites the file names in the prompt to match, and writes the case's
   `settings` to a separate config folder. A name like `seeded.md`, or a working folder inside this
   repository, tells the agent what it is being tested on. Start a fresh agent session with the plugin
   installed in the working folder, with `MANUSCRIPT_SKILLS_CONFIG` set to the config folder it printed, so
   that no case inherits a plugin-wide setting an earlier run saved. Give it only the staged prompt. Never
   show it the case file, the rubric, earlier outputs or earlier results.
2. Let it finish. One grader then checks every `rubric` and `fail_if` item against the transcript and any
   files it wrote. A case passes only if every rubric item holds and no `fail_if` item occurred. Numerical
   drift, invented evidence, an unrequested file edit or a false claim that something was checked always
   fail the case, whatever the rubric says.
3. To compare a change to a skill, run the case at least twice on the old version and twice on the new
   one, and record both in `results/` with the model, the commits and the grader. Say when a case did not
   separate the two versions.

## Running the cases automatically

```bash
uv run --script evals/plugin_eval.py run --case "reviewer-response-*" --runs 3 --judge-model sonnet --max-cost-usd 20
uv run --script evals/plugin_eval.py grade evals/plugin-eval-runs/RUN/result.json --model codex/gpt-5.6-sol
uv run --script evals/plugin_eval.py pairs evals/plugin-eval-runs/RUN/result.json
```

`run` exports the cases into `evals/plugin-eval-runs/RUN/` (git-ignored; `claude plugin eval` reads its cases only
from inside the plugin and hides them from the agent) and calls `claude plugin eval` with `--ablation
with-without`, so each case also runs with no plugin loaded and the report gives the difference. Each run starts
in an empty workspace that the case's scaffold fills with its staged files (the neutral names above) and, for a
case with `settings`, a project file holding them. Bash, Write and Edit are granted; `--network` also grants the
registries the reference and availability checks ask. Every rubric item, every `fail_if` item and the rules every
case keeps are each a Claude-judged grader that reads the whole transcript with what was planted; a case passes
only when all of them do (threshold 1.0). `--keep-temp` keeps each run's transcript, and `grade` gives it to one
agent on another model family (manuscript-other-models), which judges the same items; its verdicts are written
beside the Claude judge's, with each disagreement, in `second-grader.json`. Agreement between the two is not
proof; a disagreement is a run to read by hand. Runs cost the account's usage: start with one case and `--runs 1`,
and set `--max-cost-usd`.

A clean control matters as much as the seeded fixture: a skill that flags the repaired version as heavily
as the seeded one is not detecting the defects.

The case design follows Boom5426/Nature-Paper-Skills (hidden rubrics, fresh sessions, before and after
runs) and the seeded-defect manuscripts with clean controls used by several reviewer-simulation projects
surveyed in `docs/skill-landscape-2026-10.md`. Staging under neutral names outside the checkout, planted items pinned by
an anchor quote, paired cases and graders from two model families follow the reviewer evaluations of
Imbad0202/academic-research-skills (ideas only). `tests/test_evals.py` checks that no
case's staged file names, prompt or file comments give its condition away.
