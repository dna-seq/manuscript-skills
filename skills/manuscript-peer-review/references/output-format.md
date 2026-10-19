# Output for the authors' own draft

Lead with what the authors should do next. When they asked which concerns they can fix in the text and
which need new work, open with that split; otherwise give it in one sentence after the overall picture.
Keep the output proportionate, a page or two: the strengths, the confirmed concerns that matter in the
order the authors can act on them, and what the review did not have. Offer the full record of every
finding and what was decided about it on request or as a saved file, written in the same plain form.

Never include scores, ratings, an overall recommendation or an acceptance probability. A decision
distribution appears only when the authors asked for it ([options.md](options.md)).

Everything in the report follows "Order the work by when it can be done" and "Writing for the authors" in
the [author priorities](../../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done):
the content rules below say how they apply here. For someone else's paper, use the referee report in
[invited-referee.md](invited-referee.md) instead.

## Template

```markdown
# Simulated referee review: <short title>

<Only when the authors asked for the split, as the opening: "You can fix concerns 2, 3 and 5 in the
text. Concern 1 needs new analysis (rerunning the benchmark on a split that keeps each gene's variants
on one side); narrowing the claim to what the current benchmark shows is the cheaper alternative.">

<Two or three sentences: the paper's main claim as the panel read it, and the overall picture, e.g.
"The tool and its speed claim are well supported. The accuracy claim is not yet, because the benchmark
omits the predictors referees will expect and its split can leak gene identity." Without the opening
split, one more sentence names the concerns that need new work, if any.>

<The panel in plain words, e.g. "Three simulated referees read the paper, each in its own session: one
judging the software and its methods, a sceptical one and a supportive one (software-methods, skeptic,
champion). A fourth reader then checked every concern against the paper." Say instead when they ran
as sequential passes by one agent, which are not independent. After a three-referee panel, offer the
five-referee one in a sentence (two more whole-paper reads). Name the reviewer questions loaded and why,
and the earlier checks reused with their date.>
This is a simulation of what careful referees could raise, not a prediction of the editor's decision.

## Main strengths
- <The strength as a sentence>, as the <section> shows: "<short quote>".

## Fix now: the science and the evidence
1. **<The concern, as one plain sentence.>** In the <section>, the paper says "<quote>" (line <n>).
   <What is wrong and why it matters for the claim at stake, in two or three sentences.> <What would
   change a referee's mind.> <What to do and what it costs, e.g. "This needs new analysis: rerun the
   benchmark on a split that keeps each gene on one side. The cheaper alternative is to narrow the
   Abstract's claim to the current benchmark." or "A sentence in the Methods fixes this.">
   <"Two of the three simulated referees raised it." For a concern the paper partly answers: which part
   it already answers, with a quote, and what is still open.>

## Then the writing
<Concerns where the work is sound but the wording invites a misreading, then polish worth doing, in the
same form. At most a few polish points; the rest in one sentence ("Six smaller wording points are in
the full record").>

## Once you have chosen the journal
<Points that depend on the venue: scope, article type, length, required sections. Omit when there are
none; when no journal is chosen, say in one sentence that the venue judgement is generic.>

## Also found, belongs to other checks
<Only when the panel confirmed current-work points in another check's remit; omit when empty.>
- <The point as a sentence, with its section and quote.> <Which skill handles it, and what that check
  found: "The integrity check of 15 October 2026 found the same mismatch." | "That check judged it
  differently, because ..." | "That check has not been run; it can be.">

## Before submission, once the code is final
<End-stage packaging the panel noticed, including points another check handles (name it): an archive
record and release tag for the code, version numbers quoted in the text, the final data availability
statement, declarations. A short list of sentences; these are not problems with the current draft. Omit
when there are none.>

## Points the panel could not tie to the text
<Only if any remain after correcting misquotes: each concern in a sentence and what it lacks, e.g. "One
referee wrote that the cohort was recruited twice, but the passage it quoted is not in the manuscript."
Omit when empty.>

## What this review did not have
- <Each missing input and its consequence, e.g. "Supplementary Table S1 was not supplied, so the test
  set's composition was judged from the Methods alone.">
<When the stakes justify it, one sentence offering the robustness check or referees on another model
family, with their cost (options.md).>
```

## Content rules

- **Strengths first**, each with a quote. If the panel found few, say so plainly; do not pad.
- **Group by when the authors can act**, with the four headings above, current work first. A concern
  that threatens the support for a claim goes under "Fix now", including new analysis the claim needs.
  A misreading the wording invites, and polish, go under "Then the writing". Venue routes go under "Once
  you have chosen the journal". Archive records, release tags, version numbers quoted in the text, the
  final availability statement, declarations and the AI-use statement go under "Before submission, once
  the code is final": never call them blockers or count them in the draft's readiness unless the authors
  say they are about to submit. Within a group, order by consequence for the claims, then by cost, and
  put an item that depends on another after it ("after the benchmark is rerun, update the numbers in the
  Abstract"). Omit an empty group.
- **Quote, do not point.** Each concern quotes the sentence or table row it is about and names its
  section ("Methods, Benchmark"; "Table 2, row rs429358"); a line number may follow in parentheses. For
  something missing, say where the panel looked.
- **Plain words.** Write each concern as connected sentences: what is wrong, why it matters for the
  paper, what to do. Say the severity and the kind of problem in words ("a major concern, because the
  headline accuracy claim rests on it"; "the analysis is sound, but this sentence reads as causal").
  Never show the panel's working vocabulary on its own: referee-seat names, finding ids (F01, EV-1),
  claim ids from the record (C2), verdicts, routes, triage classes or status tokens such as
  `not_assessed` or `unverified`. A seat name or claim id may follow a plain description in parentheses
  for traceability ("the benchmark claim (C2)").
- **Links.** Give every work the authors may need to open as a full URL: `https://doi.org/...`,
  `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`, `https://arxiv.org/abs/<id>`. Say in words when a prior
  work's identifier could not be resolved.
- **Count seats, do not vote.** "Raised by three of five simulated referees" describes the panel;
  agreement is not evidence. A concern raised by one referee and confirmed by the text outranks one
  raised by four and narrowed by the defence.
- **One concern per root cause**, with every location it affects. The script's groups are a starting
  point; merge the groups that share a root cause.
- **Calibrate severity** by the consequence for the claim, as in
  [adjudication.md](adjudication.md#8-merging-triage-and-ranking): a sentence about platform support or a
  missing version number is not major unless a headline claim depends on it.
- **Separate the authors' work from what an editor or venue asks.** Venue and policy points name the
  skill that handles them; they are not scientific defects.
- **Answered and dropped concerns** do not appear as concerns. Say in one sentence how many the paper
  already answers on a closer reading, and list any misreading they revealed under "Then the writing".
- **Reused checks and other remits.** Where an integrity, reference or reporting check already recorded
  a point a referee would raise, cite it in words ("the integrity check of 15 October 2026 found no
  archived software record") instead of presenting it as new, and say why when the panel judges it
  differently. A confirmed point in another check's remit (a number that disagrees, an availability or
  declaration statement, a TODO, a citation's identity) is never among the concerns: it goes under
  "Also found, belongs to other checks" when it is current work, or under "Before submission, once the
  code is final" when it waits for the end (a declaration, an archive record), naming the skill either
  way. Where those checks were not run, say so under "What this review did not have" and offer them; do
  not run them inside this review.
- **What this review did not have** is always present. Typical lines: supplementary files or data not
  supplied; figures available only as images or not at all; code not run; cited sources paywalled or
  not read; prior work whose identifiers could not be resolved; referees run one after another by one
  agent; one model family; no reviewer questions for the paper's field; the venue unknown, so the
  desk-editor judgement is generic.
- **Run the smell check before handing it over** (required):
  `uv run --script ../manuscript-prose-edit/scripts/style_profile.py REPORT.md --report --check`, then read
  the report against the pattern list it prints, from the prose-edit catalogue
  ([llm-smells.md](../../manuscript-prose-edit/references/llm-smells.md)), never a separately installed
  `humanizer` skill
  ([why](../../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)). Fix
  what reads as notes or stock phrasing without changing a fact, quote or number.
- `check_findings.py --md` writes a working file for adjudication, not the report. Write the report from
  the adjudicated findings in this format.

## Saving and the shared record

Seat workspaces, the merged findings and the check output are working files: keep them in a scratch
directory, not beside the manuscript, unless the project already keeps such files. Save the review only
where the authors keep project files or ask for it; never inside the manuscript source. When
`manuscript-record.yaml` exists, add each confirmed concern to `open_issues` (`from:
manuscript-peer-review`, its location, a one-line summary in plain words, `route`, `status: open`) and
one `checks` entry for the review (scope, manuscript sha256, date, output path, a one-line summary).
Only the authors set an issue to `waived`.
