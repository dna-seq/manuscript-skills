# Behavioural evaluations

Script behaviour is tested by `pytest` under `tests/`. These cases test the skills themselves: whether an
agent following a SKILL.md does the right thing on a realistic request. They are graded by a person; there
is no automated runner yet.

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
```

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

A clean control matters as much as the seeded fixture: a skill that flags the repaired version as heavily
as the seeded one is not detecting the defects.

The case design follows Boom5426/Nature-Paper-Skills (hidden rubrics, fresh sessions, before and after
runs) and the seeded-defect manuscripts with clean controls used by several reviewer-simulation projects
surveyed in `docs/skill-landscape-2026-10.md`. Staging under neutral names outside the checkout follows the
reviewer evaluations of Imbad0202/academic-research-skills (idea only). `tests/test_evals.py` checks that no
case's staged file names, prompt or file comments give its condition away.
