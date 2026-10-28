# Section roles: what each part of a paper holds, and where a detail goes

Each section of a paper answers one question for its reader. A reader who wants to know what a tool does reads
the Introduction; one who wants to repeat the work reads Methods; one who wants to know how well it worked reads
Results. A detail in the wrong section costs both: the Introduction reads like a methods appendix, and the
measurement is missing where the reader who wants it looks.

Detail drifts over revision rounds. A referee asks "how many scores were withheld?", the answer lands in the
sentence the referee quoted, and the next round "brings the measured facts forward" so the Introduction looks
concrete. After enough rounds the Introduction's feature list holds the storage format, the audit thresholds and
the audit's counts, and Methods report a classifier's accuracy. This file is the shared rule every skill applies:
manuscript-story and manuscript-prose-edit when they edit, manuscript-integrity-check and manuscript-peer-review
when they review, manuscript-journal-adapt when it sets a venue's layout, and manuscript-improve when it verifies
the corrected version.

## What each section holds

| Section | Holds | Does not hold |
|---|---|---|
| **Abstract** | The problem, what was done, the main result with the number the central claim needs, and availability. The setup a headline number was measured on may stand beside it. | Procedure (formats, thresholds, how data were cleaned), the bookkeeping of a filter or an audit ("860 were withheld"), a list of every metric. |
| **Introduction**, with its feature or contribution list, overview and boxes | Why the problem matters, what is known and missing (cited), and what each contribution does and why it matters to the reader. At most a rounded figure per contribution ("about a minute", "more than a hundred times faster", "6,117 scores across 778 traits") and a pointer to the section with the measurement. | Procedure, data preparation, thresholds and parameters; measured counts, ranges, medians, decimals, accuracies; dated counts of what a resource held; any comparison whose fairness depends on its configuration. |
| **Methods** (also System and Methods, Design and Implementation, Implementation, Architecture, Algorithm, Approach, STAR Methods) | Procedure: data and their versions and dates, preparation steps, thresholds and rules stated as rules ("a score is withheld when at least four of the seven…"), parameters, software and versions, the size of the input a method is built from ("2,575 unrelated individuals"), and a pointer to where the outcome is reported ("Section 4.3 gives the counts"). | What the procedure produced on the data it was applied to: how many items passed or were withheld, a classifier's accuracy, a benchmark's numbers. Those are results. |
| **Results** (also Benchmarking, Validation, Evaluation, Performance, Use cases, Technical validation, Database content) | Measured outcomes, each beside the configuration that makes it fair (hardware, threads, versions, warm or cold, which data): audit counts, benchmark numbers, classifier accuracy, dated snapshot counts (a registry's contents on a date), real output of the tool. One clause of orientation to the procedure ("the audit of Section 3.2"). | The procedure at length (Methods), the run history and every version tried (Methods or the supplement), interpretation at length (Discussion). |
| **Discussion** | What the results mean, compared with prior work (cited), the limits that bear on the conclusions with their consequences, what would test the interpretation. | A result first stated here (a number no Methods or Results section has), procedure. |
| **Conclusion** | The finding and what a reader can do with it, numbers repeated from Results. | New numbers, new caveats. |
| **Supplement** | What a referee needs and a reader does not: every rerun, per-item tables, defensive detail. | The evidence the main claim rests on. |

Two facts are often mistaken for results. The size of a method's input (the training set after quality
control, a reference panel's sample count) is Methods: it says what the method was built from. Data versions and
their dates (the PGS Catalog release of 17 September 2026) are Methods: they are what makes the run repeatable.
Participant flow in an observational study follows its reporting guideline (STROBE puts the numbers at each stage
in Results); manuscript-reporting-check owns that.

## How a contribution is framed

The Introduction says what a contribution adds to the reader's work, not how its inputs were prepared. A tool
built on a public data source is framed by what it adds to that source (it computes the source's models,
places each result in a reference population, labels its quality, groups related results), never as a cleaned
copy of the data: the cleaning is how it works (Methods), and the data are someone else's contribution.

Paper 1 of Just-DNA-Lite (v0.6, 28 October 2026) shows the drift and its repair. Its first Key feature was "A
cleaned PGS Catalog, ready to use": a Parquet mirror, normalized genome-build labels, parsed performance metrics,
860 scores withheld and 847 of them for failing a scale check. The repaired item is "Polygenic scores with the
context to read them": the engine computes the Catalog's models and adds ancestry, an ancestry-matched percentile,
coverage, a quality label and a trait view, with one scale figure and a pointer to Sections 3.2 and 4.3. The
withholding rules stayed in Section 3.2, stated as rules; the counts moved to a new Section 4.3, and the ancestry
classifier's leave-one-out accuracy from Section 3.2.2 to a new Section 4.4. No number changed and no caveat was
dropped.

## Rounded figures and pointers

A rounded figure is one a reader keeps and that needs no caveat to be fair: "about a minute", "more than a hundred
times faster than the earlier workflow", "under a tenth of a second", a single count of what a resource covers.
These are measurements and stay in Results: a range or a median with its unit ("33 to 65 s", "a median of 0.08
s"), a count out of a total ("6,117 of 6,977"), a decimal percentage ("99.65%"), the outcome of a filter ("860
were withheld"), a dated count ("on 26 October 2026 the registry held 24 modules").

A comparison whose fairness depends on how it was run ("about seven times faster than PLINK2", where PLINK2 was
started once per score on four threads and the tool used sixteen) never stands in the Introduction without its
configuration, and with its configuration it is a Results paragraph. The Introduction keeps a comparison only when
it holds under any reasonable setup, rounded down ("more than a hundred times faster than the earlier workflow"),
or leaves it out.

Every rounded figure points to its measurement: "(Section 4.3)", "(Table 2)". A pointer costs the reader nothing
and tells the referee where to look.

## Layouts

The roles above hold in every layout; what changes is the order and the headings. Take a venue's headings, their
order and the abstract's parts from its author guide, as `../../manuscript-journal-adapt/scripts/venues.py show
<venue>` gives them (`required_sections`, the article type) or, where the catalogue has none, from the guide
itself, recorded with its date. Never from memory.

- **IMRaD, Methods before Results.** The common layout for research articles. Methods hold the procedure, Results
  the outcomes, and a Results paragraph can rely on the reader having passed through Methods, so one clause of
  orientation is enough.
- **Methods last** (Cell Press, many Nature-family and BMC journals; some journals let the authors choose).
  Results come straight after the Introduction, so each Results section opens with a sentence of what was done,
  enough to read the outcome
  ("We scored seven public genomes with every distribution before release"), and the procedure in full is in
  Methods at the end. That sentence is orientation, not misplaced procedure. Cell Press calls its Methods **STAR
  Methods**, with structured headings (resources, method details, quantification and statistical analysis, as the
  journal's current guide names them) and a Resource availability section; iScience's catalogue entry records the
  latter and asks that a first submission give "Sufficient experimental information for us to interpret the
  results in context."
- **Software and resource papers.** The headings name parts of the system instead of IMRaD sections, so map each
  to its role before checking: Overview, Features, Key features and a box of user groups inside the Introduction
  are Introduction; System and Methods, Design and Implementation, Implementation, Architecture and Algorithm are
  Methods; Benchmarking, Validation, Evaluation, Use cases, Usage examples, Technical validation and Database
  content are Results; Availability and future directions is Discussion with the availability statement. A
  section that mixes roles is common here ("Algorithm and Implementation" that ends on the registry's contents on
  a date, an example module with its counts): name the mix, and when the layout has a Results section, the
  measured part goes there. A short format without one (an application note whose body is Introduction,
  Implementation and a short discussion) keeps the measurement in the Implementation section, in a paragraph of
  its own after the procedure, with its configuration.
- **Structured abstracts** (Background, Methods, Results, Conclusions; Motivation, Results, Availability and
  Implementation) hold each role under its heading. A threshold under "Results" is still procedure.

Moving to a venue's layout is a journal step (stage `journal`, manuscript-journal-adapt), done once the journal is
chosen. Moving one misplaced detail to its section is a writing step (stage `writing`) in any layout.

## The finding: Misplaced detail

Report a misplaced detail with the category **Misplaced detail**
([stage findings](../../manuscript-dashboard/references/stage-findings.md#rules)), one record per passage or per
group of passages with one cause (a feature list that mixes procedure and results is one record). The summary
says which way the detail is misplaced, in these words:

| Direction | Example | Where it goes |
|---|---|---|
| Methods detail in the Abstract or Introduction | "just-prs mirrors the PGS Catalog's harmonized scoring files as Parquet, with cleaned metadata in which genome-build labels are normalized" | Methods; the Introduction says what the step gives the reader |
| Results detail in the Abstract or Introduction | "860 scores were withheld, 847 of them because…"; "in 33 to 65 s, 128 to 231 times faster"; "On 26 October 2026 the registry held 24 modules" | Results, beside its configuration; the Introduction keeps a rounded figure and a pointer |
| A comparison without its configuration | "about seven times faster than PLINK2", the thread counts in another section | Results, with the configuration |
| A result in Methods | "6,117 of 6,977 scores passed and 860 were withheld"; "99.65% were assigned their own superpopulation" | Results; Methods keeps the rule and a pointer |
| Procedure in Results | a Results paragraph that defines a filter or a scoring rule and reports nothing | Methods; Results keeps one clause of orientation |
| A result first stated in the Discussion or Conclusion | a number no Methods or Results section has | Results, where the Discussion can interpret it |
| A contribution framed by its preparation | "A cleaned PGS Catalog, ready to use" | the Introduction says what the contribution adds to the data |

- `quote`: the passage, verbatim. `action`: where the detail goes and what stays behind ("Move the counts to
  Results as Section 4.3; the feature keeps '6,117 scores across 778 traits' and a pointer").
- `severity`: `minor` by default. `major` when the placement changes how a reader judges a claim: a comparison
  read without the configuration that makes it fair, a result readers of Results will not find because it sits
  only in Methods, or a lead contribution framed as data preparation.
- `stage`: `writing`; `journal` when the move follows a chosen venue's layout.
- `decision`: false. Moving a detail changes no claim. Changing which contribution leads, or restructuring the
  paper into another layout before the journal is chosen, is the authors' choice
  ([story contract](../../manuscript-story/references/story-contract.md#direction-changes)).
- A Methods paragraph that ends on its own result in a layout with no Results section is not misplaced; a
  sentence of orientation at the head of a Results section in a methods-last layout is not misplaced either.

## Moving a detail without losing anything

- **Move, never delete.** Every number keeps its value and stays in the paper, in its home section. When the
  home section already states it, the copy that leaves is the duplicate.
- **The caveat travels with its number.** "This measures how well the five groups separate within the panel"
  goes to Results with the accuracy it bounds. A claim that stays in the Abstract or Introduction keeps every
  scope condition it had (the story contract's rule); a claim that leaves takes its caveat along.
- **Leave a pointer** where the detail was: "Section 4.3 gives the counts".
- **Rewrite rules as rules.** A Methods sentence that described a filter through its outcome ("For 847 of them,
  at least four of seven genomes fell…") becomes the rule ("A score is withheld when at least four of the seven
  fall…") and the outcome moves to Results.
- **A missing home is a new subsection**, named for what it measures ("4.3 PGS Catalog Coverage"), with a
  sentence added to the section's opening that lists what it measures.
- **The edits are recorded as moves**: a deletion where the text was and an addition, with its anchor, where it
  goes, under one summary ([stage findings](../../manuscript-dashboard/references/stage-findings.md#rules)).
  Under `edits: apply` a move is applied; `conservative` and `propose` propose it; `none` reports it.
- **Bringing a claim forward** (a stake, a hook, a headline in the Introduction) brings the claim, a rounded figure
  at most, and a pointer. The measured counts, ranges and the configuration stay in Results.

## The check

`scripts/section_roles.py` (in manuscript-integrity-check) lists candidate passages, section by section, with
the signal that put each on the list and the section it usually belongs in:

```bash
uv run --script ../manuscript-integrity-check/scripts/section_roles.py PAPER.md --md RUN/<skill>/section-roles.md
uv run --script ../manuscript-integrity-check/scripts/section_roles.py FINAL.md --before ORIGINAL.md  # what edits added
```

It reads section kinds from the headings with manuscript-story's classifier and looks for measurements (counts
out of totals, ranges and medians with units, decimal percentages, past-tense outcomes, dated counts), the
configuration of a comparison, and procedure (preparation steps, storage formats, gates, analysis parameters).
It leaves out sentences that cite other work outside Methods, rules stated with a comparator and data versions.
A candidate is a passage to read, not a finding: read it against this file, judge whether the layout or the venue
makes it right where it is, and report only what is misplaced. With `--before` it exits 1 when the new version has
a candidate whose text the earlier one does not, which is how manuscript-improve's verify stage catches an edit
that brought measured detail forward.
