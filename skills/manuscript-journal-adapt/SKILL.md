---
name: manuscript-journal-adapt
description: >-
  Choose a journal for an AI-assisted manuscript and adapt the manuscript to it (2026 policies). Ranks candidate
  venues by how much friction their AI policy puts on the paper (writing-help rule, disclosure places, prompt
  requirements, AI-detector screening), turns a chosen venue's rules into a checklist (disclosure fields,
  abstract headings, length limits, required sections, software availability), and copy-edits ("humanizes")
  prose so it stops reading as AI slop, under a contract that keeps every number, citation, term, hedge and
  negation intact, verified by a guard script. Use when asked which journal to target, how strict a journal is
  about AI, to adapt or format a manuscript for a journal, to humanize, de-slop or polish AI-assisted manuscript
  text, to restore the authors' voice, or to word the AI-use acknowledgement for a submission.
---

# Journal choice, adaptation and copy editing for AI-assisted manuscripts

Three jobs, usually in this order: **evaluate** venues, **adapt** the manuscript to the chosen one, and
**copy-edit** the prose. The companion skill `manuscript-integrity-check` (same plugin) is the checker; this
one changes text, so it carries the contract and the guard that keep the changes safe.

What keeps editors from treating a paper as AI slop is not undetectable prose. It is a paper whose claims
are specific and supported, whose references resolve, whose terms are consistent, and whose AI use is
disclosed the way the venue asks, narrowly and truthfully. Detector scores are weak evidence and a bad
optimisation target (`references/detector-evidence.md`), so this skill never edits toward one.

## Before any mode: establish what the AI did

The venue verdict depends on it, so read it from the record, not from memory:

- the authors' account;
- version history: `git log --format=%B -- <file> | grep -ci "co-authored-by: .*\(claude\|gpt\|copilot\|gemini\)"`
  counts commits with an AI co-author trailer;
- revision markers or tracked changes that name an AI reviser.

Classify it as **polish** (spelling, grammar, clarity of author-written text), **revision** (substantive
rewording and restructuring of author-written text) or **drafting** (the model wrote new sentences or
sections). Different sections can differ; say which.

## Mode A: evaluate venues

```bash
uv run --script scripts/venues.py rank --ai-use revision            # least friction first
uv run --script scripts/venues.py rank --ai-use drafting --min-jif 5 --software
uv run --script scripts/venues.py rank --strictest-first
```

The table scores **AI-policy friction** only: the writing-help rule (from no disclosure needed, through
disclosure, to an outright ban on drafting from a prompt), prompt requirements, the number of places a
disclosure must appear, AI-detector screening at submission, and extra burdens such as deposited AI outputs. Venues that make authors record AI use beyond one acknowledgement (full prompts, deposited
outputs, kept versions: `tracking: required`) are left out unless `--include-tracking` is given. It does
**not** score scientific fit, scope, selectivity or speed. Combine the two yourself, then re-read the live AI-policy page of the two
or three venues you would recommend (WebFetch; `google-chrome --headless --dump-dom URL` when Cloudflare
blocks it) and update `venues.yaml` if anything moved, with the date. A venue whose entry says `null` was
not researched: read its page rather than assuming it has no rule.

Report: the ranked shortlist, why each is there (fit and friction, separately), what each would require
of this manuscript given its AI use, and the date the policies were read.

## Mode B: adapt to a venue

```bash
uv run --script scripts/venues.py show <venue-key>                 # the checklist
uv run --script ../manuscript-integrity-check/scripts/scan.py PAPER.md --venue <venue-key>
```

Work through the checklist and produce a change list: abstract restructured to the venue's headings and
length; body length (some venues return a paper 20% over the limit unread); required sections (data and
code availability, archived software DOI, competing interests, author contributions); AI disclosure in
**every** place the venue names with the fields it asks for, drafted from
`../manuscript-integrity-check/references/disclosure-templates.md` with what the authors say the tools did,
never guessed;
figure rules; the cover-letter points (AI use, how the work differs from formulaic papers, validation).
Restructuring changes content placement, so present it as a list and apply it only when the authors agree.

## Mode C: copy-edit ("humanize")

Read `references/humanize-contract.md` (the contract and the full procedure) and
`references/llm-smells.md` (about 70 patterns, general and manuscript-specific, each with a bad example, a
fix and when to leave it). In short:

1. **Targets.** `uv run --script scripts/style_profile.py PAPER.md [--sample AUTHORS.md]` ranks paragraphs by
   density of named smells and, given the authors' own writing, shows where the style departs from it.
   The integrity scan adds the mechanical findings.
2. **Voice.** Get two to five paragraphs the authors wrote themselves, ideally from before any AI help, and
   match them.
3. **Edit under the contract.** Wording only: no new facts, numbers, citations, implications or limitations;
   no stronger certainty; no changed negations; no paragraph merges. If the `humanizer` skill (blader/humanizer) is
   installed, use its pattern catalogue for spotting, with this contract overriding it. Do not use
   detector-evasion humanizers (see `references/detector-evidence.md`).
4. **Show** `original → revision → reason` for each nontrivial change, and list the sentences that need the
   authors (a vague claim that needs a real number). Apply what the authors accept.
5. **Guard.** `uv run --script scripts/guard.py BEFORE AFTER` (or `FILE --against <git ref>`). Exit 1 means a
   protected item changed: revert it or have the authors confirm it. Read every watched change (hedges,
   negations, causal verbs, comparatives).
6. **Re-run** the integrity scan and the profile. If the project marks revised segments (its own revision markers), mark the
   edited ones the way it already does; this skill adds no logging of its own.

**Reflection mode** (`references/reflection-mode.md`): for the sections reviewers read first, run a critic
subagent (reads cold, names what still reads as machine-written or unsupported) and a writer subagent
(fixes exactly that under the contract) for at most two rounds, with the guard after every pass. The
stopping rule is about content, never about a detector score.

**Detector check** (only when the user asks for one): run `scripts/detector_setup.py check` first. It reports
whether a Hugging Face token is configured, the GPU, memory and disk, which free detectors are ready or
already downloaded, and recommends one (local `modernbert` by default; the text stays on the machine). If
the user wants a detector that needs a token or access, give the page from the report and **ask before**
running `detector_setup.py open <name>` to open it in a browser. Then `scripts/detect.py PAPER --detector
<key> --sample <the authors' earlier writing>`; a hosted detector needs `--allow-remote` and the authors'
consent for this text. Feed flagged windows to the critic as places to look (`references/detector-apis.md`).

Never: run a detector to decide what to rewrite, insert errors or typos, cycle synonyms or vary sentence
length for "burstiness", paraphrase through another tool or a round-trip translation, or remove hedges and
limitations. They make the paper worse, they create the inconsistencies editors do notice, and they are what
turns permitted AI use into a misconduct question.

## Disclosure is part of the job

The copy-edit pass is AI writing help, so it belongs in the acknowledgement: one statement, written once at
submission from what the authors say the tools did, no per-pass record. Make it the narrowest statement
that is **true** ("suggested sentence-level revisions to text written by the authors; the authors reviewed every
change"). That statement costs little at almost every venue; some publishers say outright that a proper
declaration does not count against a paper, while ICMJE says nondisclosure may be treated as misconduct.
Understating the use is the one choice that turns a non-issue into an investigation, so the statement
should match what actually happened, at the level of kind of help and sections, not sessions. Where the venue forbids LLM drafting (`writing_help: banned_drafting`), document the use in the
supplement as well, and make sure every AI-drafted passage has been rewritten by an author.

## Files

- `scripts/venues.py`: `rank` and `show` (PEP 723; `uv run --script`). Reads
  `../manuscript-integrity-check/references/venues.yaml`, so keep the two skills together.
- `scripts/guard.py`: before/after drift check of numbers, citations, identifiers, terms, URLs, code
  (protected) and hedges, negations, causal verbs, comparatives (watched).
- `scripts/style_profile.py`: smell density per paragraph and style measures, optionally against the authors' own
  writing; not a detector and not a probability.
- `references/humanize-contract.md`: the contract, invocation modes, writer profile, inventory, rewriting,
  the literal gate, the scaffolding audit, output format, register by text type.
- `references/llm-smells.md`: the catalogue of smells with examples, false positives, signs of human writing.
- `references/smell-patterns.yaml`: the machine-detectable part of the catalogue, read by `style_profile.py`.
- `references/reflection-mode.md`: the critic and writer agents, their prompts, the stopping rule.
- `references/section-guide.md`: what each part of a paper needs, from title to response letter.
- `scripts/detector_setup.py`: environment check, detector recommendation, token pages (opens one only when asked).
- `scripts/detect.py`: window-by-window scores from a free detector, three states, calibrated on the authors'
  own writing; heavy (torch, transformers), so it is not part of the pre-commit hook.
- `references/detector-apis.md`: the free detectors, what each needs, their evidence, how the skill uses them.
- `references/detector-evidence.md`: what 2026 evidence says about AI-text detectors, disclosure rates and
  humanizer tools
  (which open-source humanizers are fit for manuscripts, and which are detector-evasion tools).
