# Stage findings: the file every skill writes for the dashboard

Besides its report for the authors (`stage-report.md`; `report.md` in runs before 0.33), each finding-producing skill in a run writes
`findings.json` in its own run folder, `RUN/<skill>/findings.json`, even when it found nothing (an empty
`findings` list with what it covered, and `not_checked` for what it could not). `runs.py validate --final`
refuses a finished stage without it. `scripts/collect.py` merges these into one inventory, so a
problem two skills found is counted once and nothing a skill recorded is dropped. The report stays the
authors' document; this file is the same findings in a form a script can count. Four skills write none:
manuscript-dashboard (it reads them), manuscript-improve (its findings are the dashboard's adjudicated
inventory), manuscript-other-models (its seats report into the panel that ran them, whose `not_checked` lists
a seat that failed) and manuscript-mark-people (it writes a people list).

```json
{
  "skill": "manuscript-integrity-check",
  "findings": [
    {
      "id": "IC-1",
      "category": "Numbers and statistics",
      "section": "5.1 Annotation Speed",
      "quote": "verbatim passage from the manuscript, at least three words, or null for an absence",
      "looked_in": ["only for an absence: where you searched"],
      "summary": "the problem in at most fifteen words",
      "detail": "what is wrong and why it matters for the paper, one to three sentences",
      "action": "the smallest change that fixes it",
      "severity": "blocker | major | minor | info | unknown",
      "stage": "now | writing | journal | final",
      "confidence": "confirmed | candidate",
      "decision": false,
      "evidence": [{"path": "stage-report.md", "quote": "a verbatim sentence from that file that states this finding"}]
    }
  ],
  "changes": [],
    "dismissed": [{"summary": "a flag you looked at and rejected", "why": "the reason",
                 "claims": ["CC4"]}],
  "not_checked": [{"check": "what could not run", "why": "the reason", "leaves_open": "what stays unknown"}]
}
```

`runs.py finish` checks the stage's newest `findings.json` against these rules with
`scripts/stage_check.py` and refuses to finish until it meets them, naming each record and field: the shape
collect needs (a change's `kind` and its evidence as a list of `{path, quote}`), the prefix, each evidence
quote in its file, each finding's `quote` in the manuscript (a revision mark inside it is named), and each
proposal's before-text once in its file. Run it yourself before finishing:
`uv run --script ../manuscript-dashboard/scripts/stage_check.py RUN --skill SKILL`. Fix a refused record in
the next attempt (`findings.2.json`), never in a registered file.

## Rules

- IDs start with the skill's prefix and are unique within the file: IC integrity-check, RF
  reference-check, RP reporting-check, PR peer-review, PF policy-fit, JS journal-select, JA
  journal-adapt, PE prose-edit, DS deslop, ST story, FG figures, IM improve, RR reviewer-response, RM
  revision-marks, MP mark-people, CA coauthors. Collect namespaces a clash it still finds (`RP.RC-1`) rather
  than lose a record.
- One record per distinct problem. Group a root cause with its symptoms; never one record per scanner
  hit. Repeats across skills are expected: the merge step joins them. Peer review's records end their `detail` with the
  referee concern IDs they merge ("(EV-1, SK-3)"), which the dashboard links to the referees' reports.
- `quote` is copied from the authoritative manuscript exactly, never paraphrased. An absence has
  `quote: null` and says in `looked_in` where the skill searched; collect adds the places to the finding's
  detail.
- A dismissal that clears a passage against the project's code names its one entry in the integrity check's
  code-claims ledger (`claims`), where the file and line are; several passages are several dismissals.
- `confidence: confirmed` means the skill verified the problem against the manuscript, the project's
  code or files, or a source it read; `candidate` means it needs the authors or a check that could not
  run. A simulated reader's concern is confirmed only as reader feedback, never as a scientific error.
- `severity`, one scale for every skill and script, with the words the authors see:

  | Value | The authors read | Meaning |
  |---|---|---|
  | `blocker` | Blocker | a confirmed scientific defect or a verified submission barrier |
  | `major` | Major | would change a referee's view or a reader's trust |
  | `minor` | Minor | worth fixing, at low stakes |
  | `info` | Optional | a style preference, possible improvement or additional experiment |
  | `unknown` | Could not be checked | the check could not run or the evidence is missing |

  Words other scripts and seats use map onto it: `optional` → `info`, `uncertain` and `not_assessed` →
  `unknown`, `serious` → `blocker`, `important` → `major`. Collect applies the same mapping.
- `quote`: at least three words, as many as it takes to find the passage once in the manuscript.
- `stage` follows [Order the work by when it can be done](../../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done):
  `now` (the science and the evidence), `writing`, `journal` (depends on the chosen journal), `final`
  (archives, declarations, versions: before submission only).
- `decision: true` marks a choice only the authors can make: the held decisions of
  [author priorities](../../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
  (a change of direction, which figures the paper has, a venue's rules before the choice, new analyses or
  data, a fact only they have, a policy conflict) and the choice between more evidence and a narrower
  claim. A correction the evidence settles is not a decision, and neither is a failed check.
- `evidence[].path` is relative to the skill's run folder, or absolute; each `quote` must occur verbatim
  in that file. Cite the report's sentence for the finding, and add the code file, command output or
  source page when that is what settles it. Collect refuses an inventory whose quotes are not in their
  files.
- `changes` uses the inventory's change record ([data-contract.md](data-contract.md#changes-and-evidence))
  for proposals a skill drafted; applied edits are recorded with `runs.py change` and collected from the
  run manifest. A proposal's `before` is copied from the working copy exactly; an addition has `before:
  null` and `anchor`, the verbatim passage it goes after, so the corrected version can place it. A move is
  two records with the same summary: the deletion where the text was (`after: null`) and the addition, with
  its anchor, where it goes. A record whose before and after are the same text changes nothing. A proposal
  for another file than the manuscript (a supplement) names it in `document`, the file's name as the run
  took it in; its before-text or anchor occurs exactly once in that file's clean text. Change
  IDs take the skill's prefix and a C (`PE-C1`, `ST-C4`), so the Word export can sign each tracked change
  with its stage.
- Every change gives `why`: one to three sentences on what was wrong with the passage and why this wording
  fixes it, naming the rule, check or finding it rests on ("The Abstract gives 6.1 million variants; Table 2
  and the Methods give 6,138,868, so the Abstract now quotes the measured count"). The `summary` is a title;
  the dashboard shows `why` beside every edit, and an edit with neither `why` nor a linked finding says so.
  Its evidence quote is the report's sentence that gives the reason, not a heading.
- A question the authors must answer about a proposal goes in its `comment` ("add the postal code"), and
  the proposal reads complete without the answer. Never a placeholder in `after`: `[AUTHORS: ...]`, `[TODO]`,
  `XX` or a stand-in value could reach a submission
  ([author priorities](../../manuscript-integrity-check/references/author-priorities.md#questions-for-the-authors-are-comments-never-text)).
- Categories, in these words: References; Claims and evidence; Numbers and statistics; Methods and
  reproducibility; Text versus code; Reporting and availability; Figures and tables; Writing and
  clarity; Story and structure; Misplaced detail; Ethics, privacy and scope; Journal fit; Submission package.
  Misplaced detail is a passage in a section whose job is another's: procedure or a measured result in the
  Abstract or the Introduction, a result in Methods, procedure in Results, a result first stated in the
  Discussion, a contribution framed by how its data were prepared. Its summary names the direction and its
  `action` the section the detail moves to and what stays behind
  ([section roles](../../manuscript-integrity-check/references/section-roles.md#the-finding-misplaced-detail)).
- Three stages add an object of their own beside the findings, which collect carries into the inventory:
  manuscript-story's `story` (its SKILL.md, "What goes to the dashboard"), manuscript-figures' `figures`
  (its SKILL.md, section 4; [data contract](data-contract.md#figures)), with image paths relative to the
  stage's folder, and manuscript-coauthors' `coauthors`, the co-authors' comments on the previous release and
  how this one answers each ([data contract](data-contract.md#co-authors-comments)), with its ledger named,
  never located.
