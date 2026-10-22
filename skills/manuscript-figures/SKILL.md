---
name: manuscript-figures
description: >-
  Review a manuscript's figures as its readers see them: render each figure at its printed size and look
  at it (legibility at the column width, axes and units, colour for colour-blind readers and greyscale
  print, clutter, consistent style, panel labels, resolution against the venue's rules), then check its
  content (one message, a complete caption, numbers that agree with the text and tables, cited in order
  and for a claim it shows) and, where the project has it, the code that draws it. Recommend which
  figures to keep, change or move to the supplement and which to add, each with its reason; which figures
  the paper has stays the authors' decision. Use for "check our figures", figure-led papers, "which
  figures should go to the supplement", and as the figures stage of manuscript-improve. It does not screen
  images for duplication or manipulation.
---

# Review the figures as readers see them

Many readers look at the figures before they read a sentence, and a referee judges a result by the figure
that shows it. A caption can be right while the figure is unreadable in print, and a figure can be
beautiful while it shows something other than what the text says. This skill looks at every figure as
printed, checks it against its caption, the text and the code that drew it, and tells the authors what to
keep, change, move or add.

Read the shared [author priorities](../manuscript-integrity-check/references/author-priorities.md),
including [readers first, referees second](../manuscript-integrity-check/references/author-priorities.md#readers-first-referees-second),
and, when it exists, the [manuscript record](../manuscript-integrity-check/references/manuscript-record.md):
its `venue` and `venue_facts` give the journal's figure rules, its `story` the direction the figures serve.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md):
resolve saved manuscript-project choices (including the connected code folders), ask only missing first-use
questions, and keep this skill's report, renders and failures in its subfolder of the run. This applies to
direct invocations too.

## 1. Render the figures at their printed size

Looking is the review; the script does what looking cannot. A model or a person sees pixels, not
millimetres: a 3,000-pixel plot looks sharp on screen while its labels print at 2 pt in a column. From this
skill directory:

```bash
uv run --script scripts/figures.py inventory PAPER.md --output-dir RUN/manuscript-figures/figures \
  --column-mm 85 --page-mm 178 --min-pt 6 --min-dpi 300
```

It reads Markdown or LaTeX (following `\input`), finds each figure's files, caption and label, and writes
per figure `sheet.png` (the printed size in colour, greyscale and two simulated red-green colour
blindnesses) and `view.png` (300 dpi, for details). It measures text size and line weight exactly where a
PDF or SVG keeps them as vectors, the resolution of a raster as printed, and lists uncited figures,
citations out of order and citations of figures that do not exist. `figures.md` lists every figure with
these notes; each note is a place to look, not a finding.

Take the widths, the smallest text, the resolution and the number of figures from the chosen journal's
rules, which [manuscript-journal-adapt](../manuscript-journal-adapt/SKILL.md) owns: the record's
`venue_facts`, or `../manuscript-journal-adapt/scripts/venues.py show KEY` and the guideline page it links.
Before a journal is chosen, use what every venue on the ladder shares, or the defaults above (common single-
and double-column widths, 6 pt, 300 dpi), and say in the report which values were used and why. For a Word
manuscript, convert it first (`pandoc paper.docx -t gfm --extract-media=. -o paper.md`); for a manuscript
that exists only as a PDF, open its pages directly and judge sizes against the page width. Register the
output with `runs.py add --role check`.

## 2. Look at each figure, then read it against the paper

Open every `sheet.png` and `view.png` (in Claude Code the Read tool shows images; in Codex, `view_image`),
and the original file when a detail needs it. Then work through [the checklist](references/figure-review.md)
for each figure:

- **As printed**: can every label, tick, legend and panel letter be read on the sheet's first panel? Axes
  labelled with units, scales stated (a log axis labelled, bars starting at zero), compared panels on
  shared axes. Do the series stay apart in greyscale and in the simulated panels? Is colour carrying
  meaning, consistently across figures (the same tool, the same colour)? Clutter, style shared with the
  other figures, resolution.
- **Its content**: the one message a reader should take from it, and whether the figure shows it first;
  the caption says what is shown, n, what error bars or bands show, the test, units and abbreviations;
  every number read off the figure agrees with the text and the tables that give it; it is cited in order,
  and each citing sentence claims what the figure shows.
- **Its code**, where the project has it: find what writes the figure file (`grep -rn FILE_STEM CODE_DIR`,
  notebooks included), read it, and check it plots what the caption says (the statistic, the samples or
  runs, the filters and the scale it states) and that the inputs it names exist. A Vega-Lite or other declarative spec
  is the figure's code and data: read its marks, encodings and data. Running the authors' code needs their
  permission or a project instruction that allows it; then run it through `runs.py exec`, writing only into
  the run folder. A screenshot or drawing has no code: say so, and check it by looking.

Reuse what other stages of the run found about a figure (a number integrity-check recomputed, a referee's
concern about a panel) instead of redoing it; the dashboard merges the records.

## 3. Recommend: keep, change, move, add

Give each figure a verdict, **keep**, **change** or **move to the supplement**, and propose the figures the
paper lacks, every one with its reason ([patterns and examples](references/figure-review.md#recommendations)):

- **Change** what it shows (split a figure with two messages, show the points behind a bar of means, plot
  what the caption says) or how (chart type, encoding, order by value, direct labels instead of a legend,
  an annotation on the comparison that matters, layout, a colour-blind-safe palette, text sized for the
  printed width). Name the measurement or the passage behind each change.
- **Move to the supplement** what serves a referee more than a reader: a sweep showing that a setting does
  not matter, every rerun, a sensitivity analysis the text sums up in a sentence. Never move out of the
  main text evidence that would change a reader's conclusion.
- **Add** what readers need and no figure gives: a schematic overview of a multi-step method, the real
  output a user would see (from the authors' own files, never made up), a key result that now sits only in
  a table. Say what it shows, what it is built from, where it goes and what it replaces to stay within the
  limit.
- **Respect the venue's limit** on figures or display items (figures and tables together where the venue
  counts them so). An addition over the limit names what moves to make room.
- **Which figures the paper has is the authors' decision.** Moving, adding, merging or splitting a figure
  is a finding with `decision: true`, under every `edits` setting; nothing is moved or added for them.
- **A redrawn draft** may be offered when the authors' code exists and may be run: a modified copy of their
  code in `RUN/manuscript-figures/proposed/`, run on the same inputs, its image saved there as
  `figure-2.proposed.png`, shown beside the original in the report and the dashboard. It never replaces or
  overwrites the authors' figure, code or data, and it is never drawn from data the authors did not supply.
- **Caption and citation fixes** (a missing n, a figure cited out of order) are text edits like any other:
  applied or proposed as the `edits` setting allows, recorded with `runs.py change` or as proposals in
  `findings.json`, each with its `why`. A question for the authors is the proposal's `comment`, never a
  placeholder in the text.

## 4. Report and findings

Write the report as [Writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)
asks: per figure, its verdict and the reason, the problems with the caption or citing sentence quoted and
its section, the recommended changes, and a link to its sheet in the run folder; then the figures to add;
then the decisions in one place; the rest grouped under
[Order the work by when it can be done](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done).
Say which venue values were used and what could not be checked (no code, a file that would not render).
Run the required smell check on the report.

Beside it, `findings.json` follows [stage findings](../manuscript-dashboard/references/stage-findings.md):
IDs `FG-1`, `FG-2`..., category "Figures and tables", the quote the caption or the citing sentence
verbatim (an absence has `quote: null` and `looked_in`). It also gives a `figures` object, which the
dashboard's Figures tab shows with each figure's image:

```json
"figures": {
  "limit": {"count": 6, "counts": "figures", "source": "the journal's author guidelines, https://..."},
  "items": [{"id": "Figure 3", "caption": "**Figure 3.** Association of 1.2 million variants with grip strength ...",
             "image": "figures/figure-3/view.png", "verdict": "change",
             "message": "Two loci pass genome-wide significance, and only one replicates",
             "why": "The chromosome labels print at about 3 pt, and the replication is told only in Table 2.",
             "recommendations": [{"kind": "visual", "change": "Redraw at 178 mm with 7 pt labels.", "why": "..."},
                                 {"kind": "content", "change": "Mark the replicated locus on the plot.", "why": "..."}],
             "proposed_image": "proposed/figure-3.proposed.png", "code": "analysis/manhattan.R",
             "finding_ids": ["FG-1", "FG-2"]}],
  "new": [{"title": "An overview of the analysis", "kind": "a schematic overview",
           "shows": "...", "why": "...", "source": "Methods 2.1 to 2.4", "placement": "start of the Results",
           "replaces": "Figure 5 moves to the supplement", "finding_ids": ["FG-6"]}]
}
```

Paths are relative to this stage's folder. Register the report, `findings.json`, the renders and any
proposed drafts with `runs.py add`, and finish with `runs.py finish`.

## The panels see the figures

Simulated referees and readers judge figures too, so their workspaces hold them:
`scripts/figures.py workspace PAPER --into WORKSPACE/figures` writes each figure as a PNG with an index of
numbers, captions and file names, and nothing this review found. `manuscript-peer-review` and
`manuscript-story` put it in every seat's workspace, and a figure-led paper can have a figures referee
([seats](../manuscript-peer-review/references/seats.md#optional-seats)).

## Boundaries

This skill does not screen images for duplication, splicing or manipulation: publishers' tools do that
(manuscript-integrity-check's [screening signals](../manuscript-integrity-check/references/screening-signals.md)
list them), and the integrity check's file hygiene reads figures' location and author metadata. Statistics
reporting checklists belong to manuscript-reporting-check; a journal's file formats and upload rules to
manuscript-journal-adapt; which figure carries the story is read with manuscript-story. This skill never
edits the authors' figure files, code or data, never invents a figure, an output or a value, and never
changes which figures the paper has without the authors.
