---
name: manuscript-figures
description: >-
  Review a manuscript's figures and tables, in the paper and its supplement, as its readers see them:
  render each figure at its printed size and look at it (legibility at the column width, axes and units,
  colour for colour-blind readers and greyscale print, clutter, empty space, panel labels, resolution
  against the venue's rules), measure each table (width, units, precision, empty cells, length), then check
  content (one message, a complete caption, numbers that agree with the text, cited in order and for a
  claim it shows) and, where the project has it, the code that draws a figure. Recommend what to keep,
  change, make compact, merge, move to or from the supplement and add, each with its reason; which display
  items the paper has stays the authors' decision. Use for "check our figures" or "our tables", figure- or
  table-led papers, "what should go to the supplement", and as the figures and tables stage of
  manuscript-improve. It does not screen images for duplication or manipulation.
---

# Review the figures and tables as readers see them

Many readers look at the figures and tables before they read a sentence, and a referee judges a result by
the display item that shows it. A caption can be right while the figure is unreadable in print, a table can
be complete while no reader finds the row that carries the claim, and either can show something other
than what the text says. This skill looks at every figure as printed and at every table as set on the
page, in the paper and its supplement, checks each against its caption, the text and the code that drew
it, and tells the authors what to keep, change, move or add. A paper whose evidence sits in tables gets a
table review, not a report that it has no figures.

## Main text first, the supplement to a lighter standard

The main text's figures and tables are what readers and referees judge the paper by, so they get the
whole review below: printed legibility against the venue's rules, one message each, design and colour,
citation order, the venue's limit on display items. Supplementary figures and tables serve the reader who
wants the detail. They need to be readable at the page width, labelled with units, captioned so they stand
alone, consistent with the numbers in the paper and cited from the main text; design polish, compactness, one
message per item and a shared style are not asked of them, and their text and resolution are measured against
looser minimums. A supplementary item that carries a claim the paper makes may be recommended for the
main text; a main-text item that serves a referee more than a reader, for the supplement.

Read the shared [author priorities](../manuscript-integrity-check/references/author-priorities.md),
including [readers first, referees second](../manuscript-integrity-check/references/author-priorities.md#readers-first-referees-second),
and, when it exists, the [manuscript record](../manuscript-integrity-check/references/manuscript-record.md):
its `venue` names the journal whose figure rules apply, its `story` the direction the figures serve.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md):
resolve saved manuscript-project choices (including the connected code folders), ask only missing first-use
questions, and keep this skill's report, renders and failures in its subfolder of the run; end with its
[end-of-stage checklist](../manuscript-integrity-check/references/project-workflow.md#end-of-stage-checklist)
(report, smell check, `findings.json` with the prefix `FG`, applied edits recorded, `runs.py finish`). This
applies to direct invocations too.

## 1. Find every figure and table; render the figures at their printed size

Looking is the review; the script does what looking cannot. A model or a person sees pixels, not
millimetres: a 3,000-pixel plot looks sharp on screen while its labels print at 2 pt in a column. From this
skill directory:

```bash
uv run --script scripts/figures.py inventory PAPER.md --supplement SUPPLEMENT.md --output-dir RUN/manuscript-figures/figures \
  --column-mm 85 --page-mm 178 --min-pt 6 --min-dpi 300
```

It reads Markdown or LaTeX (following `\input`), the paper and each `--supplement` file, and finds every
figure (its files, caption and label) and every table (a pipe table or a `table` environment, with its
caption). For each figure it writes `sheet.png` (the printed size in colour, greyscale and two simulated
red-green colour blindnesses) and `view.png` (300 dpi, for details), and measures text size and line
weight exactly where a PDF or SVG keeps them as vectors, and the resolution of a raster as printed. It
measures the space each main-text figure takes: its printed size, the share of it that is empty (blank
margins and gaps wider than the spacing between panels) and the size it would print at cut to its content,
noted when that would make it a quarter shorter or its contents a quarter larger. A figure across the page
is also written as `column.png`, at the column width, with its smallest vector text there (noted when that
still meets the minimum); a column figure whose text is too small says the size it would reach across the
page. A caption with no image is listed as a figure whose file is missing. For each table it gives the columns and
rows, the width it needs at the table font (`--table-pt`, 8 pt) against the column and the page, and the
columns that mix decimal places, hold measured values with no unit, or have empty cells. Supplementary
items (from a `--supplement` file, or numbered S1, S2) are measured at the page width against
`--supplement-min-pt` and `--supplement-min-dpi` (5 pt and 150 dpi by default). It lists items never
cited, a supplementary item only the supplement cites, citations out of order and citations of items that
do not exist. `figures.md` lists every item, main text first; each note is a place to look, not a
finding.

Take the widths, the smallest text, the resolution and the number of figures from the chosen journal's
rules, which [manuscript-journal-adapt](../manuscript-journal-adapt/SKILL.md) owns: the venue catalogue's
`figure_rules` (`../manuscript-journal-adapt/scripts/venues.py show KEY`) and the guideline page it links.
Read a journal's figure page only when `venues.py stale KEY` lists its `figure_rules` or none are recorded, and
write what you read into the catalogue with the page and the date (`venues.py where` names the file; the fields
are in the header of `venues.yaml`), so the next run reuses it.
Before a journal is chosen, use what every venue on the ladder shares, or the defaults above (common single-
and double-column widths, 6 pt, 300 dpi), and say in the report which values were used and why. For a Word
manuscript, convert it first (`pandoc paper.docx -t gfm --extract-media=. -o paper.md`); for a manuscript
that exists only as a PDF, open its pages directly and judge sizes against the page width. An EPS figure
needs Ghostscript (`gs`; `gswin64c` on Windows) to render; without it the figure is listed as not rendered.
A second run of the inventory goes to a new folder (`figures.2`), which the script names when the first
exists.

Register the outputs with `runs.py add --role check`, each under its path in this skill's folder with
`--name`: every figure has its own `sheet.png` and `view.png` (and a figure across the page its `column.png`), so without `--name` the second `view.png`
lands at the folder's root and is refused as already registered:

```bash
uv run --script ../manuscript-integrity-check/scripts/runs.py add RUN --skill manuscript-figures --role check \
  --file RUN/manuscript-figures/figures/figures.json --name figures/figures.json
uv run --script ../manuscript-integrity-check/scripts/runs.py add RUN --skill manuscript-figures --role check \
  --file RUN/manuscript-figures/figures/figure-3/view.png --name figures/figure-3/view.png
```

and the same for `figures.md` and each figure's `sheet.png`, `view.png` and `column.png`.

## 2. Look at each figure and read each table, then read them against the paper

Open every `sheet.png` and `view.png` (in Claude Code the Read tool shows images; in Codex, `view_image`),
and the original file when a detail needs it; read every table as it is set. Then work through
[the checklist](references/figure-review.md) for each figure, [the one for tables](references/figure-review.md#reviewing-one-table)
for each table, and the [lighter standard](references/figure-review.md#supplementary-figures-and-tables)
for the supplement's items:

- **As printed**: can every label, tick, legend and panel letter be read on the sheet's first panel? Axes
  labelled with units, scales stated (a log axis labelled, bars starting at zero), compared panels on
  shared axes. Do the series stay apart in greyscale and in the simulated panels? Is colour carrying
  meaning, consistently across figures (the same tool, the same colour)? Clutter, style shared with the
  other figures, resolution.
- **Its content**: the one message a reader should take from it, and whether the figure shows it first;
  the caption says what is shown, n, what error bars or bands show, the test, units and abbreviations;
  every number read off the figure agrees with the text and the tables that give it; it is cited in order,
  and each citing sentence claims what the figure shows.
- **The space it takes** ([checklist](references/figure-review.md#the-space-it-takes)): the empty share and
  the cut size the inventory measured; for a figure across the page, whether `column.png` reads in one
  column; legends and axis titles repeated across panels; figures of the same runs or samples on a shared
  axis that would read as panels of one figure; a figure whose message is one number, and a small table that
  repeats a figure's quantity.
- **Its code**, where the project has it: find what writes the figure file (search the code folders,
  notebooks included, for its file name: `grep -rn FILE_STEM CODE_DIR` in a POSIX shell, the editor's search
  elsewhere), read it, and check it plots what the caption says (the statistic, the samples or runs, the
  filters and the scale it states) and that the inputs it names exist. A Vega-Lite or other declarative spec
  is the figure's code and data: read its marks, encodings and data. Running the authors' code needs their
  permission or a project instruction that allows it; then run it through `runs.py exec`, writing only into
  the run folder. A screenshot or drawing has no code: say so, and check it by looking.

- **Each table**: does it fit the printed page at the table font, or must it turn, split or wrap; does
  every column header name its quantity and unit; one precision per quantity; abbreviations defined in a
  footnote; what an empty or dashed cell means; can a reader find the rows that carry the claim, or would
  that result read better as a figure; does every number agree with the text and the figures.
- **Results with no display item**: read the Results for a result given only in the text, a paragraph that
  compares several numbers (conditions, tools, groups, time points) and cites no figure or table. Readers who
  skim the figures miss it, and a sentence of six numbers cannot be compared at a glance.

Reuse what other stages of the run found about a figure or table (a number integrity-check recomputed, a
referee's concern about a panel) instead of redoing it; the dashboard merges the records.

## 3. Recommend: keep, change, move, add

Give each figure and table a verdict, **keep**, **change**, **merge** (with the items named in
`merge_with`, into one figure or table), **move to the supplement** or, for a supplementary item that carries
a claim of the paper, **move to the main text**, and propose the figures the paper lacks, every one with its
reason ([patterns and examples](references/figure-review.md#recommendations)):

- **Change** what it shows (split a figure with two messages, show the points behind a bar of means, plot
  what the caption says) or how (chart type, encoding, order by value, direct labels instead of a legend,
  an annotation on the comparison that matters, layout, a colour-blind-safe palette, text sized for the
  printed width). Name the measurement or the passage behind each change.
- **Make it compact** where the measurements or the sheet show space a reader gains nothing from: cut the
  empty space, set a figure that reads in one column in one column, share a legend and the axis titles across
  panels, draw small multiples on shared axes. Give the size before and after; never compact by shrinking
  text below the venue's minimum. A layout change of one figure is a `change`.
- **Merge** figures (or a small table into a figure) that show the same runs, samples or quantity, on a shared
  axis, and serve one message: say which panel each becomes and what is drawn once. A merge is how a paper
  over the limit keeps a result in the main text that would otherwise move out.
- **Move to the supplement** what serves a referee more than a reader: a sweep showing that a setting does
  not matter, every rerun, a sensitivity analysis the text sums up in a sentence. Never move out of the
  main text evidence that would change a reader's conclusion.
- **Add** what readers need and no figure gives: a schematic overview of a multi-step method, the real
  output a user would see (from the authors' own files, never made up), a key result that now sits only in
  a table, a comparison the text gives only as numbers in a paragraph (built from those numbers, or the
  authors' data behind them; a small table when a figure would exceed the limit). Say what it shows, what it is built from, where it goes and what it replaces to stay within the
  limit.
- **Respect the venue's limit** on figures or display items (figures and tables together where the venue
  counts them so). An addition over the limit names what moves or merges to make room; merged items count as
  one.
- **Which figures the paper has is the authors' decision.** Moving, adding, merging or splitting a figure
  is a finding with `decision: true`, under every `edits` setting and also when the authors say "fix
  everything"; nothing is moved or added for them. These are held decisions: listed once, together, with
  the run's other decisions at the end, and nothing else waits on them.
- **A redrawn draft** may be offered when the authors' code exists and may be run: a modified copy of their
  code in `RUN/manuscript-figures/proposed/`, run on the same inputs, its image saved there as
  `figure-2.proposed.png`, shown beside the original in the report and the dashboard. It never replaces or
  overwrites the authors' figure, code or data, and it is never drawn from data the authors did not supply.
- **Caption and citation fixes** follow the `edits` setting like any other text edit. Under the default,
  a routine fix and a correction that a confirmed finding requires and the evidence settles are applied
  (a missing n or unit that the data or the code give, a citing sentence that names the wrong panel); each
  is shown before and after and recorded with `runs.py change`. Under `propose` each is a proposal; under
  `apply` the improvements are applied too. What needs a fact only the authors have, or renumbers the
  figures themselves, is a proposal in `findings.json`, with its `why`. A question for the authors is the proposal's `comment`, never a
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
dashboard's Figures tab shows with each figure's image, main text first. Each item says its `kind`
(`figure` or `table`) and its `part` (`main` or `supplement`); a table has no image:

```json
"figures": {
  "limit": {"count": 6, "counts": "figures", "source": "the journal's author guidelines, https://..."},
  "items": [{"id": "Figure 3", "kind": "figure", "part": "main", "caption": "**Figure 3.** Association of 1.2 million variants with grip strength ...",
             "image": "figures/figure-3/view.png", "verdict": "change",
             "message": "Two loci pass genome-wide significance, and only one replicates",
             "why": "The chromosome labels print at about 3 pt, and the replication is told only in Table 2.",
             "recommendations": [{"kind": "visual", "change": "Redraw at 178 mm with 7 pt labels.", "why": "..."},
                                 {"kind": "content", "change": "Mark the replicated locus on the plot.", "why": "..."}],
             "proposed_image": "proposed/figure-3.proposed.png", "code": "analysis/manhattan.R",
             "finding_ids": ["FG-1", "FG-2"]},
            {"id": "Figure 4", "kind": "figure", "part": "main", "verdict": "merge", "merge_with": ["Figure 5"],
             "why": "Figures 4 and 5 show memory and CPU use over the same run; as panels a and b on one time axis they take one slot.",
             "finding_ids": ["FG-4"]}],
  "new": [{"title": "An overview of the analysis", "kind": "a schematic overview",
           "shows": "...", "why": "...", "source": "Methods 2.1 to 2.4", "placement": "start of the Results",
           "replaces": "Figure 5 moves to the supplement", "finding_ids": ["FG-6"]}]
}
```

A `merge` names the other items in `merge_with`; the dashboard counts each merged group as one display item
against the limit. Paths are relative to this stage's folder. Register the report, `findings.json`, the renders and any
proposed drafts with `runs.py add`, each with `--name` set to that path (`--name figures/figure-3/view.png`,
`--name proposed/figure-3.proposed.png`), and finish with `runs.py finish`.

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
