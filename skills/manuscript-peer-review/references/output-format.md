# Output for the authors' own draft

Lead with what the authors should do next. When they asked which concerns they can fix in the text and
which need new work, open with that split: two short lists, each line naming a concern by its number
below. Keep the output proportionate, a page or two: the strengths, the confirmed concerns that matter,
the author-required list and what the review did not have. Offer the full adjudication record (every
finding with its verdict) on request or as a saved file.

Never include scores, ratings, an overall recommendation or an acceptance probability. A decision
distribution appears only when the authors asked for it ([options.md](options.md)).

## Template

```markdown
# Simulated referee review: <short title>

<Only when the authors asked for the split:
Fixable in the text: concerns <numbers>. Need new analysis or data: concerns <numbers>, each with a
cheaper alternative of narrowing the claim.>

<One or two sentences: the paper's main claim as the panel read it, and the overall picture, e.g.
"The tool and its speed claim are well supported; the accuracy claim is not yet, because the benchmark
omits the predictors referees will expect and its split can leak gene identity.">

Panel: <seats> and a defender, <independent subagents | sequential passes by one agent, not
independent>. <After a three-seat panel: A five-seat panel would add <seats> (two more whole-paper
reads); ask if you want it.>
Domain modules: <modules and why, or none>. Checks reused: <skill, date, scope> (or none).
This is a simulation of what careful referees could raise, not a prediction of the editor's decision.

## Main strengths
- <strength> (<location>: "<short quote>"). Raised by <seats>.

## Concerns to address before submission
Ranked by consequence for the paper's claims, then by the cost of addressing them.

1. **<one-line concern>** (<substance | misread risk>, <severity>; raised by <k> of <n> seats)
   - Where: <location>, "<quote>" (or: not found in <places looked>)
   - Why it matters: <the claim at stake and what could change: validity, support, scope,
     reproducibility or interpretation>
   - What would change a referee's mind: <the evidence or wording>
   - Route: <fixable in text | author-required | venue | policy> (<cost>; <skill that takes it>)
   - <For a downgraded finding: what was narrowed, and why.>

## Author-required work
- [ ] <the analysis, data or experiment>, protecting claim <id or text>. Cheaper alternative: <narrow
  the claim to ...>. Cost: <reanalysis | new data>.

## Polish
<At most a few lines; collapse the rest into "N further polish points in the full record".>

## Also found, belongs to other checks
<Only when the panel confirmed points in another check's remit; omit when empty.>
- <point> (<location>). Belongs to <skill>; <its recorded result agrees | differs, because ... | not
  run: offer it>.

## Not yet findings
<Only if any remain: what each lacks (a verifiable quote, a checked identifier). Omit when empty.>

## What this review did not have
- <each missing input and its consequence, e.g. "Supplementary Table S1 was not supplied, so the test
  set's composition was judged from the Methods alone.">
```

## Content rules

- **Strengths first**, each with a quote. If the panel found few, say so plainly; do not pad.
- **Count seats, do not vote.** "Raised by 3 of 5 seats" describes the panel; agreement is not
  evidence. A concern raised by one seat and confirmed by the text outranks one raised by four seats
  and downgraded.
- **Group by root cause.** One concern per underlying problem, with every location it affects. The
  script's groups are a starting point; merge the groups that share a root cause.
- **Calibrate severity** by the consequence for the claim, as in
  [adjudication.md](adjudication.md#8-merging-triage-and-ranking): a sentence about platform support or a
  missing version number is not major unless a headline claim depends on it.
- **Separate the authors' work from what an editor or venue asks.** Venue and policy routes are listed
  with the skill that handles them, not as scientific defects.
- **Refuted and dropped findings** do not appear as concerns. Mention their number in one line, and list
  any misread risks they revealed under the concerns.
- **Reused checks and other remits.** Where an integrity, reference or reporting check already recorded
  a point a referee would raise, cite it ("integrity-check, 2026-10-15: no archived software record")
  instead of presenting it as new, and say why when the panel judges it differently. A confirmed point
  in another check's remit (a number that disagrees, an availability or declaration statement, a TODO,
  a citation's identity) goes under "Also found, belongs to other checks", never among the ranked
  concerns. Where those checks were not run, say so under "What this review did not have" and offer
  them; do not run them inside this review.
- **What this review did not have** is always present. Typical lines: supplementary files or data not
  supplied; figures available only as images or not at all; code not run; cited sources paywalled or
  not read; prior-work identifiers that could not be resolved; seats run sequentially by one agent; one
  model family; no domain module for the paper's field; the venue unknown, so the desk-editor judgement
  is generic.

## Saving and the shared record

Seat workspaces, the merged findings and the check output are working files: keep them in a scratch
directory, not beside the manuscript, unless the project already keeps such files. Save the review only
where the authors keep project files or ask for it; never inside the manuscript source. When
`manuscript-record.yaml` exists, add each confirmed concern to `open_issues` (`from:
manuscript-peer-review`, its location, a one-line summary, `route`, `status: open`) and one `checks`
entry for the review (scope, manuscript sha256, date, output path, a one-line summary). Only the authors
set an issue to `waived`.
