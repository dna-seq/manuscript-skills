---
name: manuscript-mark-people
description: >-
  Find the people in a manuscript repository and build the `humans` list of its rev-marks.toml, so
  that manuscript-revision-marks can tell a person's review from an AI's or agent's edit. Reads git
  authors, committers and Co-authored-by trailers, the names already in revision marks, and author
  lists (LaTeX \author, Markdown front matter, CITATION.cff, AUTHORS, CODEOWNERS); separates people,
  AI models and bots, and handles nobody explains; proposes the list for the authors to confirm and
  writes only what they confirm. Use when setting up revision marks in a project, when lint warns of
  an unclassified name, or when a co-author joins. Use manuscript-revision-marks for the marks
  themselves.
---

# Who is a person in this project's revision marks

`manuscript-revision-marks` counts a passage as reviewed only when the latest name in its `by=` is a
person's, and it counts every name it cannot place as an agent. This skill builds the list that says
who the people are. **It never decides that a name is a person**: it shows the evidence, the authors
confirm, and only the confirmed names are written.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run. This applies to direct invocations too.

## Steps

1. **Survey**, read-only (relative to this skill directory):

   ```bash
   uv run --script scripts/people.py PATH/IN/THE/REPO
   ```

   It prints the people it found, with the evidence for each (git author, a trailer, `\author` in
   main.tex) and the handle each signs with or would most likely sign with; the agents (AI vendors'
   addresses, bot accounts, names on the shared agent list); the `by=` handles nobody explains; and a
   proposed `humans` list. Test fixtures, examples and placeholder names ("Anonymous") are skipped.
   Nothing leaves the machine.

2. **Confirm with the authors**, one batch: the proposed handles, each with its evidence, and the
   unexplained handles (`robi`, `validator`) with where they appear. Ask which are people. A handle
   for a person who has not signed a mark yet is a guess (`would sign as anna?`): ask which handle
   they use. Do not confirm a name yourself, and do not treat silence as a yes.

3. **Write** only the names they confirmed:

   ```bash
   uv run --script scripts/people.py PATH/IN/THE/REPO --write --confirm anna,tom
   ```

   The names are merged into `rev-marks.toml` at the repository root; other keys, comments and names
   already listed stay. A name the survey did not find is refused unless the authors spelled it out
   (`--force-name`).

4. **Check** with `manuscript-revision-marks`: `rev_marks.py lint PAPER.md` should no longer warn of
   the confirmed names, and `report --unreviewed` now shows only the passages whose latest round is an
   agent's or an unconfirmed name's.

Mention the other `rev-marks.toml` key once, without deciding it: `unknown` (whether an unlisted name
counts as an agent, the default, or a person).

## Files

- `scripts/people.py`: the survey and the confirmed write (standard library and git).
- The agent list it uses is `../manuscript-revision-marks/references/agent-names.toml`.
