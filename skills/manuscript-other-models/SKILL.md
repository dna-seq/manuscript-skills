---
name: manuscript-other-models
description: >-
  Run the simulated referees, readers, critics and skeptics of the other manuscript skills on more than one
  AI model, through command-line agents the authors already use and pay for (Codex CLI, Claude Code, Gemini
  CLI) instead of API keys: from Claude Code a seat can run on Codex, from Codex on Claude Code. Each seat is
  a fresh session in a throwaway copy of its workspace, recorded with the model that read it. Use only when
  the authors ask for more than one model ("also run the referees on Codex", "a second opinion from GPT",
  "an ensemble review") or saved that choice for the project, to see which models are available here, or to
  check that a CLI is signed in. The panels themselves belong to manuscript-peer-review, manuscript-story,
  manuscript-deslop and manuscript-reference-check.
---

# Seats on other models

Seats on one model share its blind spots: three referees on the same model tend to miss the same things.
The same seats on a second model family catch some of what the first misses. That is all it buys. It does
not make the seats independent, and agreement between models is not confirmation: the defence pass and the
quote still decide every finding.

This skill runs only when the authors ask for it. Another skill uses it only when the authors ask, in the
conversation, for more than one model, or when `other_models` is saved for the project. Every seat on
another model sends the reading copy of the manuscript to that model's provider, under the authors' own
account. Naming the CLI is agreement to that provider; when the authors ask for "another model" without
naming one, show what Step 1 finds and ask which.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain the evidence and failures in the linked run. A seat on another model belongs to the skill whose panel it sits on, so its evidence goes in that skill's subfolder; `detect` and `check` send no manuscript and need no run.

## Step 1: see what is available

Relative to this skill's directory:

```bash
uv run --script scripts/models.py detect
uv run --script scripts/models.py check codex --model gpt-5.6-sol
```

`detect` lists the CLIs installed here (Claude Code, Codex CLI, Gemini CLI), which one this session runs in
(the host), which are another model family, and the models each offers. `check` makes one tiny call in an
empty folder, without the manuscript, and says whether the CLI is signed in and accepts the model, in the
CLI's own words. Run it once before the first seat on each model.

- **Not signed in**: the authors sign in themselves (`codex login`, `claude` then `/login`, `gemini`). Never
  type a credential or set an API key for them. A CLI that works in their terminal only through an API key
  reports "not signed in" here too: `check` and `run` leave provider keys out, so that the seats use the
  CLI's own sign-in and nobody's API account is billed unasked.
- **A model refused**: Codex's configured default can be one its ChatGPT sign-in refuses; pass one it lists
  with `--model`.
- **From inside Codex**, its sandbox has no network for commands: run `check` and `run` with escalated
  permissions (Codex asks the authors to approve), or the other CLI cannot reach its model. `detect` says
  so. A Claude Code session with its sandbox switched on needs the same.

A second model of the host's own family (Claude Sonnet from a Claude Opus session) is another model, not
another family; say so when the authors choose it.

## Step 2: record the choice

A choice made in the conversation applies to this run. When the authors want it for every run of this
paper, save it in the project:

```bash
uv run --script ../manuscript-integrity-check/scripts/project.py configure ROOT --other-model codex/gpt-5.6-sol
```

Each `--other-model` is a CLI, or a CLI and model as `CLI/MODEL`; repeat it for several. `--one-model`
forgets them. Saved models are the authors' standing agreement to send the reading copy to those providers.

## Step 3: decide which seats run where

- **Panels: every seat also on each chosen model.** The referees of manuscript-peer-review, the quick-pass
  seats and the readers of manuscript-story run as their skill says, on the host, and once more on each
  chosen model, with the model in the seat name: `skeptic@codex`, `skimmer@claude`,
  `custom:clinician@gemini`. Three referees and one other model make six referee reports. The authors can
  name fewer ("only the skeptic on Codex"); say what each extra seat costs, since every one reads the whole
  paper.
- **Checkers that look for what the writer missed run on the other model instead.** The critic of the
  deslop and prose-edit reflection loops and the reference-check skeptic run on the chosen model rather
  than the host: the writer's own family is the one most likely to miss its own habits. With several
  models chosen, the critic takes them in turn, one per round.
- **The coordinator's work stays on the host**: the defender, merging, adjudication, the report and every
  edit to the manuscript.

## Step 4: run each seat

Prepare each seat's workspace and brief exactly as its skill says for a seat on the host, in a new folder:
the same reading copy, figures and files, never a folder another seat has worked in. The script refuses a
workspace a seat already ran in (it holds `seat-run.json`), but it cannot tell a host seat's files from the
authors'. The brief is the skill's template, filled the same way, saved outside the workspace
(`briefs/skeptic@codex.md`). It names the seat without its model ("You are the skeptic"): the seat need
not know other models read the paper, and the coordinator adds `@codex` when merging (Step 6). It names
the workspace by its absolute path, as the template says ("Work only from the files in
/abs/path/to/WS"); the script replaces that path with the copy's and sends the brief otherwise as it is:

```bash
uv run --script scripts/models.py run codex --workspace WS --brief BRIEF --model gpt-5.6-sol --timeout 3600
```

`run` copies the workspace to a new temporary folder outside every project, starts a new session of the
CLI there (never a resumed or forked one) with the brief as its whole prompt, and lets it write only in that
copy: Claude Code has its file tools and no shell, Codex its `workspace-write` sandbox without network,
Gemini its `auto_edit` mode. Provider key variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`,
`GOOGLE_API_KEY` and the like) are left out of the environment the CLI starts with, so it uses its own
sign-in. When the session ends, the files it created are copied back into the workspace
(`criteria.md`, `findings.json`, a reader's report); a file it was given and changed is reported and left
as it was. Its last message is saved as `seat-answer.md`, which is the seat's answer when its brief asks for
an answer rather than a file. `seat-run.json` records the CLI and its version, the model, the exact
command, the exit status, the duration, the files returned, where the prompt as sent, the CLI's output
and its errors were saved, how far the seat was kept to its copy (`read_isolation`), and the sign-in
route: the names of the key variables left out and of any setting that sends the CLI's requests another
way (a gateway, a cloud account), never their values.

Working in a copy keeps the project's own instructions (CLAUDE.md, AGENTS.md, GEMINI.md), its git history
and the agent's memory of the project away from the seat. The authors' personal instructions for the CLI
(in their home folder) still load. The copy limits what a seat can change, not always what it can read:

- **Writes** stay in the copy for every CLI, and only new files come back.
- **Reads** are limited by the CLI only for Claude Code, which refuses a file outside the copy
  (`read_isolation: enforced`). Codex and Gemini limit writes, not reads: the brief's "work only from the
  files in <the copy>" is the only thing that keeps them there (`read_isolation: instruction-only`). A seat
  that reads further could see the project, the run and other seats' files, if it looked for them.
- The host's own subagent seats have no copy and no CLI limit at all; for them too the brief's absolute
  path is the boundary. In a test run, Claude Code subagent referees ran the panel's own checker from the
  plugin folder, which the brief now forbids.

Start the seats on other models together with the host's own seats (in Claude Code as background
commands; in Codex with a long command timeout), and receive every result before merging. Exit 0 means
the seat answered; 1 that it ran and failed, with the reason in `seat-run.json` (a rate limit, a refused
model, no answer); 2 a bad argument, a missing CLI or a used workspace; 3 a timeout. Retry a failed seat
once, in a fresh workspace. A seat that still fails is missing on that model: record it with `runs.py
issue` and name it under "What this review did not have". Never read it on the host instead and label it as
the other model. A seat on another model is never resumed, so asking it again for something its brief asked
(a missing report) means running it again in a fresh workspace, or recording that it gave none.

## Step 5: record it in the run

Register each seat's output as its skill says, with its model, and its `seat-run.json` beside it:

```bash
uv run --script ../manuscript-integrity-check/scripts/runs.py add RUN --skill manuscript-peer-review \
  --file WS/findings.json --role referee --seat skeptic@codex --isolation fresh-agent \
  --model codex/gpt-5.6-sol --name referees/skeptic@codex/findings.json
uv run --script ../manuscript-integrity-check/scripts/runs.py add RUN --skill manuscript-peer-review \
  --file WS/seat-run.json --role other --name referees/skeptic@codex/seat-run.json
```

A session started by `run` is a fresh agent whose whole context is its brief: `--isolation fresh-agent`.
Give the host's seats `--model` too (the host's model id), so the run and the dashboard show which model
read every seat.

## Step 6: merge and report

- **Merge as the skill says.** Set `seat` to `SEAT@CLI` on every finding, strength and report from a seat on
  another model, and add the CLI's letter to its ids' prefix (C Claude Code, X Codex, G Gemini: the
  skeptic's `SK-3` on the host, `SKX-3` on Codex), so the copies of a seat cannot collide and the dashboard
  still links them (two or three capitals, a hyphen and a number); update the ids each recommendation rests
  on to match. Group findings by root cause; a group names every seat that raised it, with its model.
- **The defender sees no seat or model names**, as it sees no counts.
- **Count nothing as corroboration.** A concern three models raised is not confirmed by that; one only one
  model raised is not weaker for it. The verdict comes from the quote and the defence.
- **Say which models read the paper**, in words, in the report's opening or "What this review did not
  have": "Three referees on Claude Opus 5.5 and the same three on GPT-5.6-Sol through Codex CLI." Seat
  names stay in parentheses. For a seat whose reads only its brief kept in its copy (Codex, Gemini), say so
  in "What this review did not have": "the referees on Codex were told to read only their copy of the
  paper; Codex limits what they write, not what they read." Note a concern only another model raised when
  it changed what the authors should fix first.
- Never call the models independent reviewers, and never present one model as the more reliable one.

## What it does not do

It uses no API keys of its own and no hosted gateway, and passes none on: provider key variables are left
out of every CLI's environment, so each CLI uses its own sign-in, and the record names what was left out.
A setting that sends a CLI's requests another way (a base URL, a cloud account) is kept, because the
authors may rely on it, and named in the record. It never edits the manuscript or the project, and it
cannot stop a Codex or Gemini seat from reading outside its copy; it tells the seat not to, and the record
says so. Other CLIs (Cursor Agent, OpenCode, GitHub
Copilot) are not wired yet: each needs an adapter in `scripts/models.py` (its command line, how its answer
is read, the variable its sessions set) and a test with a fake CLI. The relays in
[amElnagdy/delegate-skills](https://github.com/amElnagdy/delegate-skills) show the flags for many of them.

## Files

- `scripts/models.py`: `detect`, `check` and `run` (Python standard library and Typer).
