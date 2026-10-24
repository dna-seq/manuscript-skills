---
name: manuscript-mark-people
description: >-
  Find the people in a manuscript repository and build the `humans` list of its rev-marks.toml, so
  that manuscript-revision-marks can tell a person's review from an AI's or agent's edit. Reads git
  authors, committers and Co-authored-by trailers, the names already in revision marks, and author
  lists (LaTeX \author, Markdown front matter, CITATION.cff, AUTHORS, CODEOWNERS); separates people,
  AI models and bots, and handles nobody explains; proposes the list for the authors to confirm in
  one question that blocks nothing, and writes only what they confirm. Use when setting up revision marks in a project, when lint warns of
  an unclassified name, or when a co-author joins. Use manuscript-revision-marks for the marks
  themselves.
---

# Who is a person in this project's revision marks

`manuscript-revision-marks` counts a passage as reviewed only when the latest name in its `by=` is a
person's, and it counts every name it cannot place as an agent. This skill builds the list that says
who the people are. **It never decides that a name is a person**: it shows the evidence, the authors
confirm, and only the confirmed names are written. **The confirmation never blocks anything**: it is
one question among the end-of-run decisions, and until it is answered every name not yet listed counts
as an agent, so a passage can only read as unreviewed by mistake, never as reviewed. A wrongly listed
name would hide an AI's unreviewed edits; a missing one costs a passage shown as unreviewed a little
longer.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run. This applies to direct invocations too.

## Steps

1. **Survey**, read-only (relative to this skill directory):

   ```bash
   uv run --script scripts/people.py PAPER.md            # the manuscript, or any folder in its repository
   ```

   It prints the people it found, with the evidence for each (git author, a trailer, `\author` in
   main.tex) and the handle each signs with or would most likely sign with; the people whose name or
   address is also an agent's name (Devin, Yi, Luna), listed apart; the agents, each with what makes it
   one (an AI vendor's or bot's address, a bot account, a login on the shared agent list); the `by=`
   handles nobody explains; and the question to put to the authors. A git author or a listed author
   whose address is no AI vendor's or bot's is a person even when a word of the name is an agent's.
   Test fixtures, examples and placeholder names ("Anonymous") are skipped. Outside a git repository,
   or without git, it reads the `by=` handles and author lists and says that git history was not read.
   Nothing leaves the machine.

2. **Ask once, never blocking.** Put the survey's question among the end-of-run decisions and carry on
   with the rest of the work: the names, each with its evidence, and the unexplained handles (`robi`,
   `validator`) with where they appear. Pre-selected are only the names whose evidence converges: they
   sign `by=` entries, commit in git and are listed authors, and the handle is no agent's name. Every
   other name is offered unselected: a handle for a person who has not signed a mark yet is a guess
   (`would sign as anna?`), and a handle that is also an agent's name (`devin`) would count every round
   signed so as a person's. Show the people whose name matches an agent name: they are people the
   agent list would otherwise misread. Do not confirm a name yourself, and do not treat silence as a
   yes; an unanswered question leaves the list as it is.

   One statement confirms a handle without the question: the authors saying that a named co-author
   reviewed or approved passages (an "accept all" relayed from them). `manuscript-revision-marks` then
   writes that one handle in the same step as the person's round.

3. **Write** only the names they confirmed:

   ```bash
   uv run --script scripts/people.py PAPER.md --write --confirm anna,tom
   ```

   The names are merged into the `rev-marks.toml` that `manuscript-revision-marks` reads for the
   manuscript: the nearest one from it up to the repository root (`--config` names another), or a new
   one at the repository root (outside git, beside the manuscript). Other keys, comments and names
   already listed stay. A name the survey did not find is refused unless the authors spelled it out
   (`--force-name`). A malformed `rev-marks.toml` is exit 2 and is never rewritten.

4. **Check** with `manuscript-revision-marks`: `rev_marks.py lint PAPER.md` should no longer warn of
   the confirmed names, and `report --unreviewed` now shows only the passages whose latest round is an
   agent's or an unconfirmed name's.

Mention the other `rev-marks.toml` key once, without deciding it: `unknown` (whether an unlisted name
counts as an agent, the default, or a person).

## Files

- `scripts/people.py`: the survey and the confirmed write (standard library and git).
- The agent list it uses is `../manuscript-revision-marks/references/agent-names.toml`.
