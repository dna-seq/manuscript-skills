# Reflection mode: a critic agent and a writer agent

One editor rereading its own output misses what it wrote; a second reader with fresh context finds it. In
reflection mode the orchestrator (the session running this skill) alternates two subagents over one
section at a time:

- the **critic** reads the section cold and reports what still reads as machine-written or unsupported;
- the **writer** fixes exactly those points under the contract;
- the **guard** checks after every writer pass that no content changed.

Use it for the sections reviewers read first (abstract, introduction, discussion, cover letter) or after
a draft written with heavy AI help. A plain single pass (`humanize-contract.md`) is enough for Methods and
routine sections.

## Loop

```
profile.py SECTION                       → ranked smells (and optional detector notes, below)
round 1:  writer(section, smells)        → draft-1 + change table
          guard.py section draft-1       → protected changes? revert them
          critic(draft-1)                → findings
round 2:  writer(draft-1, findings)      → draft-2
          guard.py section draft-2
          critic(draft-2)                → findings
stop
```

**Stop** after round 2, or earlier when the critic returns no finding of severity `high` and at most two
of `medium`. Do not run a third round: by then edits remove meaning and voice faster than they remove
smells. Hand whatever the critic still lists to the authors, with the change tables of both rounds and the
guard reports.

**The stopping rule is about content, never about a score.** A detector number may point the critic at a
paragraph (below); it never decides whether to loop again.

## Spawning the agents

Give each agent only what it needs. The critic must not see the writer's reasoning or the change table,
only the text, so that it reads as a reviewer would.

### Critic prompt

```text
You are a reviewer reading one section of a {field} manuscript for {venue}. You have not seen earlier
drafts. Read the section and list every passage that reads as machine-written or unsupported.

Use the catalogue at {path}/llm-smells.md: for each finding give the smell id (A1, B5, H3, ...), the exact
quoted phrase, and one sentence on why it reads that way here. Also list, with id "CLAIM":
- claims with no number, citation or result behind them;
- terms used for one thing under different names;
- sentences whose certainty seems higher than the evidence given.
Respect each entry's "Leave it when". Do not flag field terms in their technical sense, passive voice in
Methods, or a single connector.

{optional: "A third-party detector rated these paragraphs as most AI-like: L.., L.. . Treat this as a hint
of where to look, not as a finding: report only what you can name with a catalogue id or as CLAIM."}

Do not rewrite anything. Output JSON: [{"id": "...", "quote": "...", "why": "...",
"severity": "high|medium|low"}]. "high" = a reviewer would comment on it; "low" = style only.
Section:
<<<
{text}
>>>
```

### Writer prompt

```text
You are a scientific copy editor, not an author. Edit the section below to fix exactly the findings
listed, under the contract in {path}/humanize-contract.md (section 1). In short: keep every claim,
number, citation, hedge, negation, limitation and technical term; add nothing; do not merge or split
paragraphs; match the authors' voice from the sample if one is given.

For a finding you cannot fix without a fact the authors must supply (a "CLAIM" with no anchor), do not
invent one: leave the sentence and add it to "flagged".

Output: the edited section; then a table | # | original | revision | reason (finding id) |; then
"flagged": the sentences that need the authors, each with the question to ask.

Authors' sample (may be empty):
<<<
{sample}
>>>
Findings:
{findings}
Section:
<<<
{text}
>>>
```

## Orchestrator duties

1. Split the manuscript into sections and run the loop on one section at a time.
2. After each writer pass, run `guard.py` on the section. Revert every protected change the authors did
   not ask for; read every watched change yourself.
3. Merge the round-1 and round-2 change tables, and the flagged sentences, into one report for the
   authors.
4. Never pass the critic's findings straight to the manuscript: the writer applies them, the guard checks
   them, the authors accept them.

## Optional detector notes

If the authors have set up an AI-text detector (see `detector-apis.md`, when present, for which ones are
free and what they do with the text), its per-paragraph scores can go to the critic as a hint. Three rules:

- **Opt-in and confidentiality.** Sending an unpublished manuscript to a third party may breach the
  authors' and their co-authors' confidentiality, and some detectors keep or train on what they receive.
  Run a remote detector only when the authors say so for this text, and prefer one that runs locally.
- **A hint, not a target.** A high score means "the critic should look here". The fix is still a named
  smell or an unsupported claim; if the critic finds none, the paragraph stays as it is.
- **Never loop on the score.** Detector scores move with ordinary professional editing of human text
  (0% to 100% false positives across 13 detectors; Park et al. 2026), so chasing one degrades the paper.
