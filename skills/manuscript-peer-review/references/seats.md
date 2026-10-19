# Reviewer seats

A seat is one simulated referee with a remit. Each seat reads the whole paper; the remit decides what it
reads most closely, not what it may mention. Seats work in isolation (SKILL.md, step 3) and write
findings in the [finding schema](finding-schema.md), then the summary and recommendation that open and
close a real referee report.

Every seat referees for a journal: the one the submission is simulated for, or each of the top three
journals of the authors' ladder (SKILL.md, step 2). What the journal publishes, what its editors check on
arrival and what it asks its referees reach the seat in `venue.md`. The journal sets the bar and the
scope a referee judges against; the remits below decide what each referee reads most closely.

## Choosing the panel

Start from `study.designs` and `study.domains` in `manuscript-record.yaml` when it exists, otherwise from
the manuscript (the design keys are listed in
[manuscript-record.md](../../manuscript-integrity-check/references/manuscript-record.md#study-design-keys)).
Add the journal and article type from step 2 of SKILL.md: referees and a desk editor judge against the
journal's scope and bar.

- **Three seats** by default: the design's main seat from the table, the skeptic and the champion, then
  the defender in adjudication (four whole-paper reads). The main seat also covers reproducibility, and
  the skeptic also covers claims and novelty. These are the three referees a journal would send the
  paper to: an expert on its main method, a hard expert reader, and a reader who values what the
  paper adds. When the simulation covers three journals, the same three seats each write one report
  with a recommendation for each journal; a separate panel per journal is the fuller option
  ([options.md](options.md#a-separate-panel-for-each-journal)).
- **Five seats** when the authors take up the offer or ask for a fuller panel: add the two seats of the
  "Five-seat panel adds" column. Never more than five: extra seats repeat each other and multiply the
  cost, since each one reads the whole paper.
- Load a domain module into the seat whose remit it serves (usually the main seat), or give it its own
  seat in a five-seat panel when the paper's main risk lies in that domain.

| Study design (any of) | Main seat | Five-seat panel adds | Domain modules to consider |
|---|---|---|---|
| `software-tool` | software-methods | claims-novelty, evidence-statistics | software-and-methods; genomics if it handles genomic data; ai-systems if the tool runs an LLM or other AI system |
| `method-benchmark` | evidence-statistics | claims-novelty, reproducibility | software-and-methods; the data's domain; ai-systems when the methods compared are AI systems |
| `database-resource` | software-methods (access, versions, licence, curation quality) | claims-novelty, evidence-statistics | software-and-methods; ai-systems if an AI system drafts or curates entries |
| `genetic-association`, `polygenic-score`, `mendelian-randomization` | evidence-statistics + genomics | claims-novelty, reproducibility | genomics; human-data-and-clinical |
| `observational-human`, `prediction-model`, `randomized-trial`, `case-report` | evidence-statistics + human-data-and-clinical | claims-novelty, reproducibility | human-data-and-clinical |
| `omics-profiling`, `public-data-reanalysis`, `microbiome-metagenomics` | evidence-statistics + genomics (batch, references) | claims-novelty, reproducibility | genomics (only the questions that fit) |
| `in-vitro-experiment`, `animal-experiment` | evidence-statistics (controls, replicates, blinding) | claims-novelty, reproducibility | none yet; use the seats' general questions |
| `systematic-review`, `simulation-theory`, `qualitative` | evidence-statistics | claims-novelty, reproducibility | none yet |
| `ai-generated-science` | as for the underlying design; the evidence seat uses [ai-science-design.md](../../manuscript-integrity-check/references/ai-science-design.md) | as for the underlying design | as for the underlying design |

For a mixed study, take the main seat of the design that carries the headline claim and add the modules
of the others. Run the panel without asking, state it at the top of the output and offer the five-seat
panel. Ask first only when the authors want to choose: one short message with the seats, the modules and
why, and the cost (number of whole-paper reads).

## Core seats

### claims-novelty

Judges what the paper claims and whether that is new and stated within its evidence. Reads the title,
abstract, introduction and conclusions against the results.

- Is the question and the contribution clear by the end of the introduction?
- Does a headline claim rest on a priority word ("first", "only", "novel", "unlike existing tools")?
  Quote it; adjudication judges it as manuscript-reference-check's
  [claim-support.md](../../manuscript-reference-check/references/claim-support.md#priority-and-absence-claims)
  says. A concern that the work is not new names the prior work and its identifier.
- Do the abstract and conclusions claim more than the results show (the claim ceiling)? Do they quietly
  switch to a different outcome than the one measured?
- Does the paper answer the question it poses, or a nearby easier one?

Leaves citation identity and the support of individual citations to manuscript-reference-check.

### evidence-statistics

Judges whether the design and analysis answer the question. This is the "methods reviewer" of the quick
pass.

- Do the design, controls, comparators and baselines answer the question asked? Is the obvious
  comparison present, and is it fair (same data, same tuning effort, same versions)?
- What else could produce the headline result: confounding, selection, leakage between training and
  test data, batch effects, regression to the mean, multiple comparisons, a circular label?
- Is the unit of analysis right; are uncertainty, effect sizes and the number of tests reported; are
  sample sizes consistent between the abstract, methods, tables and figures?
- Is the step from each result to its claim valid, and does a negative or null result get the same
  care as a positive one?

Leaves statistical reporting checklists and reporting guidelines to manuscript-reporting-check; raises a
reporting gap here only when it blocks judging a claim.

### reproducibility

Judges whether another group could repeat the work from what is written and released.

- Data: accessions, versions, release dates, access conditions, inclusion and exclusion steps.
- Software: versions, parameters, random seeds, environment; code released and archived at the version
  used; supplementary files that the text refers to actually exist.
- Could the main table or figure be regenerated from the stated inputs?

Leaves the formal availability statements to manuscript-reporting-check and
manuscript-integrity-check. Never installs or runs the authors' code unless asked (see
[software-and-methods.md](domains/software-and-methods.md)).

### champion

Says what is strong, as a supportive referee would, and keeps the review calibrated.

- What is new, useful or well done? Quote it. Which results would survive every likely objection?
- What should the authors keep and put forward more clearly?
- What would even a supportive referee still ask for? (Findings are allowed but not required.)

Strengths from every seat, not only the champion, reach the report; the champion makes sure the
review does not consist of complaints alone.

### skeptic ("Reviewer 2")

Looks for the reason a hostile but competent expert would give for rejection, under the same contract
and fairness filter as every other seat: hostile, never unfair.

- The strongest alternative explanation for each headline result.
- The comparison or control such a referee would demand first.
- The weakest link in the chain from data to the headline claim.
- The sentence most likely to be quoted back in a rejection letter, and why.

## Optional seats

- **desk-editor**: would an editor at the stated venue send this out for review? If not, the main
  reason: scope, article type, a contribution that the abstract does not make clear, an obvious flaw,
  length or structure. Venue-fit reasons route to manuscript-journal-select or
  manuscript-journal-adapt; they are not scientific defects.
- **software-methods**, **genomics**, **human-data-clinical**, **ai-systems**: a domain module run as
  its own seat. software-methods is also the main seat for software and resource papers, where it takes
  the reproducibility remit as well.
- **custom:<name>**: a seat the authors ask for (for example `custom:clinician` or
  `custom:statistician`), with a one- or two-sentence remit from them.

## Quick pass (for an integrity audit)

When manuscript-integrity-check or manuscript-improve asks for independent desk-editor and methods
reviewer passes, run two seats: desk-editor and evidence-statistics. Isolation, the contract and
adjudication apply unchanged; skip the panel question unless the authors want to choose. The seats skip
step 6 of the brief: a quick pass writes no report and no recommendation. Merge the
confirmed points into the calling report, in its stage groups, each saying in words which simulated
reviewer raised it ("the simulated desk editor"), quoting the manuscript with its section.

## Domain modules

| Module | Serves | Trigger summary |
|---|---|---|
| [domains/genomics.md](domains/genomics.md) | evidence-statistics, reproducibility, skeptic | variants, genome builds, GWAS, sequencing, expression or other genome-scale data |
| [domains/software-and-methods.md](domains/software-and-methods.md) | software-methods seat, reproducibility | the paper presents or benchmarks software, a pipeline, a method or a resource |
| [domains/human-data-and-clinical.md](domains/human-data-and-clinical.md) | evidence-statistics, claims-novelty, skeptic | data about people, health outcomes, risk, diagnosis or treatment language |
| [domains/ai-systems.md](domains/ai-systems.md) | software-methods, evidence-statistics, skeptic | the tool or method runs an LLM, an agent or another AI system, or the paper evaluates one |

Read the module's trigger and exclusion cues before loading it, and record in the report which modules
were loaded and why. Load the smallest set that fits. A module is a bank of reviewer questions, not a
checklist: a question that does not apply to this paper is skipped without comment.

## The seat brief

Each seat receives one self-contained brief and its own workspace (in a scratch directory) holding only:
the reading copy of the manuscript (HTML comments, LaTeX comments and revision markers removed, as an
editor would see it), its supplementary files, a copy of [finding-schema.md](finding-schema.md), and,
when a domain module is loaded for this seat, that module's questions as `domain-questions.md`. Domain
questions live only in the workspace of the seat they serve. Fill in the angle brackets:

> You are the **<seat>** on a simulated referee panel. <One journal: "The editor of <journal> has asked
> you to referee this manuscript, submitted as <article type>." Several: "The authors are considering
> <journal 1>, <journal 2> and <journal 3> for this manuscript. Referee it once, and give each journal
> your recommendation."> What each journal publishes, what its editors check and what it asks its
> referees are in `venue.md`. Study design: <keys>. Your remit: <remit from seats.md>. <If a module is
> loaded: "Your domain questions are in `domain-questions.md`.">
>
> Work only from the files in this directory. Do not look for other reviews of this work, the authors'
> notes or their views of it. Unfinished content (a TODO note, a placeholder) is not a referee concern;
> leave it to the integrity check.
>
> 1. Before opening the manuscript, read `venue.md` and write `criteria.md`: the three to eight problems
>    that, for your remit, this design and the journal's bar, would count as major. Do not edit it after
>    you start reading.
> 2. Read the whole manuscript, including tables, figure legends and the supplementary files here.
> 3. Write `findings.json` following `finding-schema.md`. Quote the manuscript exactly; for something
>    missing, list where you looked. Raise a concern only if resolving it could change the validity,
>    support, scope, reproducibility or interpretation of a claim, and name that claim. Say what would
>    change your mind. Do not call the work not novel without naming the prior work and its identifier,
>    or marking it unverified. Ask for new experiments or data only when the claim needs them, and say
>    whether narrowing the claim would do instead. "Not state of the art" is a concern only when the
>    paper claims superiority.
> 4. Add the paper's strengths to `findings.json` under `strengths`, each with a quote.
> 5. For each criterion with nothing to raise, add one line to `criteria.md` saying what you checked
>    and where.
> 6. Last, when your findings and strengths are complete, add `report` to `findings.json` as
>    `finding-schema.md` describes: your summary of the paper and your overall view, as the opening
>    paragraph of a referee report, and for each journal in `venue.md` the recommendation you would
>    give on its form (accept, minor revision, major revision or reject), with the reason and the ids of
>    your findings it rests on. Judge each journal by the scope, article type and bar `venue.md` gives:
>    the same concerns can mean minor revision at one journal and reject at another. Do not change a
>    finding to fit the recommendation.
>
> No scores, ratings or acceptance odds. There is no quota: no findings, with a coverage line per
> criterion, is a valid result, and so is a recommendation to accept.

Never put in a seat's workspace or brief: another seat's output, `manuscript-record.yaml` or its
claims and open issues, a cover letter or response letter, earlier reviews, the authors' own assessment
of the paper, why they chose the journal or how they ranked the ladder, or your claim map. A seat that
sees what the authors think is strong is no longer reviewing the paper.
