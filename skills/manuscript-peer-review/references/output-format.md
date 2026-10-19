# Output for the authors' own draft

The result has two parts, because the authors need two different things from it.

- **Part 1, the referees' reports**: what the journal would send back. One report per referee, in the
  form referees write: the recommendation, a summary of the paper and the referee's view of it,
  strengths, major concerns, minor concerns and questions. When the simulation covers three journals,
  each report gives a recommendation for each.
- **Part 2, what to fix, in order**: what the authors do about it. The concerns of all the referees,
  merged by root cause and ordered by when the authors can act on them, each with what to do and what
  it costs.

Never include scores, ratings, an acceptance probability, an average of the recommendations or a
predicted editorial decision. Each referee's recommendation is reported as that referee gave it, per
journal, and labelled as coming from simulated referees.

Everything in the result follows "Writing for the authors", and Part 2 follows "Order the work by when it
can be done", in the
[author priorities](../../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done):
the content rules below say how they apply here. For someone else's paper, use the referee report in
[invited-referee.md](invited-referee.md) instead.

## Template

```markdown
# Simulated peer review: <short title>

<Where the paper lands, first: "Simulated as an Original Paper at Bioinformatics, the three referees
recommend major revision, major revision and minor revision." For three journals, one sentence each.
Then two or three sentences on the overall picture, e.g. "The tool and its speed claim are well
supported. The accuracy claim is not yet, because the benchmark omits the predictors referees will
expect and its split can leak gene identity." Then one sentence naming the concerns that need new
work, if any.>

<The journal and the panel in plain words. Which journal and article type the submission was simulated
for, and why: "the journal you named", "the journal in your manuscript record", "the top three journals
of your ladder of 19 October 2026", or "no journal was named, so a generic journal in genomics". What
the referees were told about it and where that was read ("its author guidelines and its guidelines for
reviewers, read on 19 October 2026: <URL>"), or that its guidelines for reviewers could not be found.
Then the referees: "Three simulated referees read the paper, each in its own session: an expert on the
software and its methods, a hard expert reader and a supportive one (software-methods, skeptic,
champion). A fourth reader then checked every concern against the paper." Say instead when they ran as
sequential passes by one agent, which are not independent. Name the reviewer questions loaded and why,
and the earlier checks reused with their date. Offer the five-referee panel after a three-referee one,
and a separate panel per journal after a ladder run (options.md).>
These are simulated referees sharing one model; their recommendations are not a prediction of the
editor's decision.

## Part 1: the referees' reports

### Before review: the editor's desk screen

<Only when a rule the journal's editors check on arrival would stop or risk this draft, for each journal
it applies to: the rule, quoted with its page, and the fact about the draft that meets it, e.g. "The
body is about 7,900 words. Bioinformatics allows 'up to 7 pages, this is approx. 5000 words', and papers
20% or more over 'are usually returned by the Editorial Office immediately'
(https://academic.oup.com/bioinformatics/pages/author-guidelines)." Omit the section when no rule
applies.>

### Referee 1: <expertise in plain words, e.g. "the software and its methods">

**Recommendation:** <Major revision> <(on the journal's form: "Major revision")>. <The reason, in the
referee's words.> <For three journals, one line each instead: "Bioinformatics: major revision, because
... BMC Bioinformatics: minor revision, because ...".> <When the defence refuted or narrowed what the
recommendation rests on, one sentence saying so.>

**Summary.** <The referee's opening paragraph: what the authors claim, how they support it, and whether
it holds.>

**Strengths.**
- <The strength as a sentence>, as the <section> shows: "<short quote>".

**Major concerns.**
1. <In the <section>, the authors write "<quote>" (line <n>). What is wrong and why it matters for the
   claim at stake, in the referee's voice. What would change the referee's mind.>

**Minor concerns.**
1. <The same form, in one to three sentences.>

**Questions for the authors.**
1. <Only when the referee has any.>

### Referee 2: <expertise in plain words>

<The same form.>

### Referee 3: <expertise in plain words>

<The same form.>

## Part 2: what to fix, in order

<Only when the authors asked for the split, as the opening: "You can fix items 2, 3 and 5 in the text.
Item 1 needs new analysis (rerunning the benchmark on a split that keeps each gene's variants on one
side); narrowing the claim to what the current benchmark shows is the cheaper alternative.">

### Fix now: the science and the evidence

1. **<The problem, as one plain sentence.>** Raised by <Referee 1 (major concern 2) and Referee 2 (major
   concern 1)>. <What to do and what it costs, e.g. "This needs new analysis: rerun the benchmark on a
   split that keeps each gene on one side. The cheaper alternative is to narrow the Abstract's claim to
   the current benchmark." or "A sentence in the Methods fixes this."> <For a concern the paper partly
   answers: which part it already answers, with a quote, and what is still open.>

### Then the writing

<Wording that invites a misreading although the work is sound, including passages a referee misread
because the answer sits far from the claim, then polish worth doing, in the same form. At most a few
polish points; the rest in one sentence ("Six smaller wording points are in the full record").>

### Once you have chosen the journal

<What the journal, or each journal of the ladder, asks of this draft: scope, article type, length,
required sections, the desk-screen points above. Omit when there are none.>

### Also found, belongs to other checks

<Only when the panel confirmed current-work points in another check's remit; omit when empty.>
- <The point as a sentence, with its section and quote.> <Which skill handles it, and what that check
  found: "The integrity check of 15 October 2026 found the same mismatch." | "That check judged it
  differently, because ..." | "That check has not been run; it can be.">

### Before submission, once the code is final

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

### Part 1: the referees' reports

- **Write each report as the referee would.** In the referee's voice ("The authors claim ...", "I would
  ask the authors to ..."), from its `report` (summary and recommendations) and its confirmed and
  downgraded findings, which `check_findings.py --adjudicated` sorts into major concerns, minor concerns
  and questions. A narrowed finding appears narrowed. A refuted or dropped finding never appears in a
  report; a misreading it reveals goes to Part 2, "Then the writing". Concerns overlap between referees,
  as they do in real reports: write each from that referee's angle, and keep the remedy and its cost
  for Part 2.
- **A referee notices what referees notice.** A report may mention a point that Part 2 hands to another
  check or keeps for the end (a number that disagrees, a missing archive record), as real referees do;
  an end-stage point is at most a minor concern there, never a major one.
- **Recommendations as given.** Each with its reason and, for three journals, one line per journal. When
  the defence refuted or narrowed what a recommendation rests on, add one sentence after it, as
  [adjudication.md](adjudication.md#9-the-referees-recommendations) says; never change the
  recommendation. A referee that gave none is reported as giving none, never filled in. The opening
  sentence of the result reports the recommendations per journal, never an average, a percentage, a
  score or an editorial outcome.
- **The desk screen applies rules, not taste.** Only rules that can be checked against the draft: article
  type, length, required abstract headings, an excluded study design, a required item such as a cover
  letter. Each quotes the journal's page and says what the draft does. A rule that needs judgement
  ("papers of less significance") is left to the referees.

### Part 2: what to fix

- **One item per root cause**, merging the referees, with every location it affects. Each item opens
  with the problem as a plain sentence that stands alone, names the referees and the concern numbers
  that raised it (the reports' own numbering), and ends with what to do: a text fix, or new work with
  the cheaper alternative of narrowing the claim. The script's groups are a starting point; merge the
  groups that share a root cause.
- **Group by when the authors can act**, with the headings above, current work first. A concern that
  threatens the support for a claim goes under "Fix now", including new analysis the claim needs. A
  misreading the wording invites, and polish, go under "Then the writing". Venue routes and the desk
  screen's points go under "Once you have chosen the journal". Archive records, release tags, version
  numbers quoted in the text, the final availability statement, declarations and the AI-use statement go
  under "Before submission, once the code is final": never call them blockers or count them in the
  draft's readiness unless the authors say they are about to submit. Within a group, order by
  consequence for the claims, then by cost, and put an item that depends on another after it ("after the
  benchmark is rerun, update the numbers in the Abstract"). Omit an empty group.
- **Count referees, do not vote.** "Raised by all three referees" describes the panel; agreement is not
  evidence. A concern raised by one referee and confirmed by the text outranks one raised by three and
  narrowed by the defence.
- **Calibrate severity** by the consequence for the claim, as in
  [adjudication.md](adjudication.md#8-merging-triage-and-ranking): a sentence about platform support or a
  missing version number is not major unless a headline claim depends on it.
- **Separate the authors' work from what an editor or venue asks.** Venue and policy points name the
  skill that handles them; they are not scientific defects.
- **Answered and dropped concerns** are not items. Say in one sentence how many the paper already
  answers on a closer reading, and list any misreading they revealed under "Then the writing".
- **Reused checks and other remits.** Where an integrity, reference or reporting check already recorded
  a point a referee raised, cite it in words ("the integrity check of 15 October 2026 found no archived
  software record") instead of presenting it as new, and say why when the panel judges it differently.
  A confirmed point in another check's remit (a number that disagrees, an availability or declaration
  statement, a TODO, a citation's identity) is never ranked among the items: it goes under "Also found,
  belongs to other checks" when it is current work, or under "Before submission, once the code is final"
  when it waits for the end (a declaration, an archive record), naming the skill either way. Where those
  checks were not run, say so under "What this review did not have" and offer them; do not run them
  inside this review.

### Both parts

- **Quote, do not point.** Each concern in a report quotes the sentence or table row it is about and
  names its section ("Methods, Benchmark"; "Table 2, row rs429358"); a line number may follow in
  parentheses. For something missing, say where the referee looked. A Part 2 item quotes again only
  when its passage is not in the reports.
- **Plain words.** Write in connected sentences: what is wrong, why it matters for the paper, what to do.
  Say the severity and the kind of problem in words ("a major concern, because the headline accuracy
  claim rests on it"; "the analysis is sound, but this sentence reads as causal"). Never show the
  panel's working vocabulary on its own: referee-seat names, finding ids (F01, EV-1), claim ids from the
  record (C2), verdicts, routes, triage classes or status tokens such as `not_assessed` or `unverified`.
  A seat name or claim id may follow a plain description in parentheses for traceability ("the
  benchmark claim (C2)"). Referee and concern numbers ("Referee 2, major concern 1") are the reports'
  own numbering and may be used.
- **Links.** Give every work the authors may need to open as a full URL: `https://doi.org/...`,
  `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`, `https://arxiv.org/abs/<id>`, and each journal rule as its
  page. Say in words when a prior work's identifier could not be resolved.
- **Proportion.** Each referee report about a page, as real reports are: its major concerns in full,
  minor ones in one to three sentences each. Part 2 a page or two. With many concerns, a report folds
  its smaller minor points into one sentence, and Part 2 lists the remaining polish in one sentence and
  offers the full record of every finding, in the same plain form.
- **What this review did not have** is always present. Typical lines: supplementary files or data not
  supplied; figures available only as images or not at all; code not run; cited sources paywalled or
  not read; prior work whose identifiers could not be resolved; the journal's guidelines for reviewers
  not found, so its form and recommendation options were assumed; referees run one after another by one
  agent; one model family; no reviewer questions for the paper's field.
- **Run the smell check before handing it over** (required):
  `uv run --script ../manuscript-prose-edit/scripts/style_profile.py REPORT.md --report --check`, then read
  the report against the pattern list it prints, from the prose-edit catalogue
  ([llm-smells.md](../../manuscript-prose-edit/references/llm-smells.md)), never a separately installed
  `humanizer` skill
  ([why](../../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)). Fix
  what reads as notes or stock phrasing without changing a fact, quote, number or recommendation.
- `check_findings.py --md` writes a working file for adjudication, not the result. Write the result from
  the adjudicated findings and the referees' reports in this format.

## Saving and the shared record

Seat workspaces, the merged findings and the check output are working files: keep them in a scratch
directory, not beside the manuscript, unless the project already keeps such files.

Where the review goes follows the plugin-wide `reports` setting, decided as
[the author priorities](../../manuscript-integrity-check/references/author-priorities.md#minimum-useful-work)
say (the request, the project's instructions, the saved setting, else one question for the whole
plugin):

- `file` (the default when the authors cannot be asked): save the review in the folder the authors
  name, else beside the manuscript source (or where the project keeps its review files), named after the
  manuscript (`paper.peer-review.md`); never inside the manuscript source itself and never at a scratch
  path. A rerun replaces the file; when the authors have written in it, ask before replacing it. The
  reply gives the file's path relative to the project, where the paper lands (each referee's
  recommendation, per journal) and the "Fix now" items in a sentence each, and says the full review is
  in the file.
- `chat`: give the whole review in the reply, in the same form, and save no file.
- `both`: save the file and give the whole review in the reply.

When
`manuscript-record.yaml` exists, add each confirmed concern to `open_issues` (`from:
manuscript-peer-review`, its location, a one-line summary in plain words, `route`, `status: open`) and
one `checks` entry for the review (scope, manuscript sha256, date, output path, a one-line summary).
Only the authors set an issue to `waived`.
