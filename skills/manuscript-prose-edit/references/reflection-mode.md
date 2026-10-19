# Reflection mode: a critic agent and a writer agent

One editor rereading its own output misses what it wrote; a reader with fresh context finds it. In
reflection mode the orchestrator (the session running this skill) alternates subagents over one section at a
time:

- the **writer** edits under the contract and fixes the findings the orchestrator accepted;
- the **guard** runs after every writer pass and checks that no content changed;
- the **critic** is a new subagent every round. It reads only the current text, cold, and reports what still
  reads as machine-written, unclear or unsupported, each finding under a catalogue ID.

Use it when the author requests reflection mode or independent agents. It can help with an important
section that still has concrete writing problems; section type or past AI use does not make it
mandatory. A single pass is the default for any section. Follow the shared author-priority rules and
the output defaults in `prose-edit-contract.md`.

Cover the whole paper unless the author narrows the task. Section-sized agent tasks are internal chunks,
not automatic author-review stops. If the author requests section or stage checkpoints, show the relevant
before/after comparison and pause at those boundaries; otherwise finish all sections in scope.

## Loop

```
style_profile.py SECTION                      → ranked smells (and optional detector notes, below)
round 1:  writer(section, smells)             → draft-1 + change table
          guard.py SECTION draft-1            → revert protected changes the authors did not ask for
          style_profile.py draft-1 --before SECTION --check → fix added patterns and clusters
          critic A (new subagent)(draft-1)    → findings; the orchestrator accepts or rejects each
          no accepted finding → stop
round 2:  writer(draft-1, accepted findings)  → draft-2 + change table
          guard.py SECTION draft-2
          style_profile.py draft-2 --before SECTION --check
          critic B (new subagent)(draft-2)    → findings; accepted ones go to the authors, not to a round 3
stop
```

The guard always compares against the original section, so drift that builds up over two passes is caught.

**Stop** after a round in which the orchestrator accepts no critic finding, and never run more than two
rounds. A finding the critic repeats after the writer tried to fix it is a content question: it goes to the
authors, it does not earn another round. Catalogue hits alone do not justify a round; neither does a
detector score.

## Isolation: what each agent may see

The critic must read the section as a reviewer would, so it gets **only**:

- the current text of the section;
- the field, the venue if known, and the paths to `llm-smells.md` and `claim-ladders.md`.

It never sees the authors' self-assessment (a cover letter's claims, "we think this section is clear", the
contribution they hope a reader takes away), the writer's notes or change table, earlier drafts, earlier
critic findings, or what the previous round fixed. A critic that knows what was fixed looks for confirmation
instead of problems. Spawn a new subagent for each round rather than continuing the previous critic.

The writer gets the section, the accepted findings, the contract and the authors' writing sample if one exists.
It does not need the critic's identity or rejected findings.

## Traceability without a log file

Every critic finding carries an ID from the catalogue (`llm-smells.md`: A1, B5, C16, H3, I1, ...) or
`CLAIM`. The writer's change table cites the ID for every change. The summary to the authors groups the
changes by what they are, with the ID only in parentheses ("participle tails cut in 4 places (A9); one
name kept per object in 2 places (B7); 'drives' kept and flagged (I1)").
That ID is the provenance of each fix. Do not write a ledger, transcript or per-round log file: the
author priorities rule them out, and the diff plus the grouped summary are the record.

## Spawning the agents

### Critic prompt

```text
You are a reviewer reading one section of a {field} manuscript for {venue}. You are seeing this text for
the first time and know nothing about how it was written or edited. Identify concrete problems with clarity,
support, consistency or register. Do not speculate about authorship or treat every catalogue hit as a defect.

Use the catalogue at {path}/llm-smells.md: for each finding give its id (A1, B5, H3, ...), the exact quoted
phrase, and one sentence on why it is a problem here. For claims, use these ids, naming rungs from
{path}/claim-ladders.md:
- I1: the verb is stronger or weaker than the design supports (give both rungs, e.g. "association → causation");
- I2 or I6: a hedge or scope that does not match the evidence, or differs from the same claim elsewhere;
- B7: one object under several names;
- C16: a run of short declarative sentences with no stated relation (name the missing link);
- CLAIM: a claim with no number, citation or result behind it.
Respect each entry's "Leave it when". Do not flag field terms in their technical sense, passive voice in
Methods, "we", or a single connector. Never ask for a claim to be made stronger.

{optional: "A third-party detector rated the paragraphs that begin with these words as most AI-like: '...',
'...'. Treat this as a hint of where to look, not as a finding: report only what you can name with an id."}

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
listed, under the contract in {path}/prose-edit-contract.md (section 1). In short: keep every claim,
number, citation, hedge, negation, limitation and technical term; add nothing; do not merge or split
paragraphs; match the authors' voice from the sample if one is given.

A finding about claim strength (I1, I2, I6) or a missing anchor (CLAIM) is not yours to fix: do not move
the claim up or down, and do not invent an anchor. Leave the sentence and add it to "flagged" with the
current wording, the proposed wording and the question for the authors.

Output: the edited section; then a table | # | original | revision | finding id |; then
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
2. Review each critic finding rather than passing it on mechanically. Accept a finding when it names a
   concrete problem the contract lets the writer fix; reject it when the catalogue entry's "Leave it when"
   applies, when it is a field convention, or when fixing it would change a claim (send that to the authors).
3. After each writer pass, run `guard.py SECTION DRAFT` against the original section. Revert every protected
   change the authors did not ask for, and read every warning yourself. Then run the smell check
   (`style_profile.py DRAFT --before SECTION --check`, contract §5.3) and fix what it lists before the critic
   reads the draft; give each critic the check's reading list along with the text.
4. Merge the change tables into one summary for the authors: the changes grouped by what they are, in plain
   words with the finding IDs in parentheses (as under "Traceability" above), then the flagged sentences,
   each quoted with its section and ordered by when the authors can act, claim questions first under "Fix
   now" (`author-priorities.md`, "Order the work by when it can be done"). Apply authorised copy edits and
   show a diff; ask the author only about unresolved facts or changes in scientific meaning.

## Optional detector notes

If the authors want a detector's view, run `detector_setup.py check` and `detect.py` (see `detector-apis.md`
for which free detectors exist and what they do with the text); its flagged windows can go to the critic as
a hint. Three rules:

- **Opt-in and confidentiality.** Sending an unpublished manuscript to a third party may breach the
  authors' and their co-authors' confidentiality, and some detectors keep or train on what they receive.
  Run a remote detector only when the authors say so for this text, and prefer one that runs locally.
- **A hint, not a target.** A high score means "the critic should look here". The fix is still a named
  smell or an unsupported claim; if the critic finds none, the paragraph stays as it is.
- **Never loop on the score.** Detector scores move with ordinary professional editing of human text
  (0% to 100% false positives across 13 detectors; Park et al. 2026), so chasing one degrades the paper.

The loop's isolation and stopping rules adapt the independent red-team of SNL-UCSB/paper-writing-skill (MIT:
a reviewer that never sees the author's self-assessment, rule IDs as provenance, stopping when a round makes
no progress) and the fresh reviewer per round of wanshuiyin/Auto-claude-code-research-in-sleep (MIT), without
their on-disk ledgers or score-driven loops.
