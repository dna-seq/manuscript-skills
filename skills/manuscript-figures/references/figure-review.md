# Reviewing one figure

Look first, then read. Open the figure's `sheet.png`: its first panel is the figure at the size it will be
printed, and that panel is what a reader of the journal sees. `view.png` is for details. A note from
`figures.py` points at something to check on the sheet; it is not a finding until you have looked.

## As printed

- **Legibility.** Every axis label, tick label, legend entry, annotation and panel letter can be read on
  the printed-size panel. The script's measurement settles vector text (below the venue's minimum is a
  finding); for a raster, judge on the sheet, and say "about" when you estimate a size.
- **Axes and scales.** Each axis is labelled with the quantity and its unit. A logarithmic axis says so and
  its ticks are readable. Bars start at zero; a broken or truncated axis is marked. Panels that are
  compared share their scale, or say they do not.
- **Line weights and marks.** Lines, error bars and points stay visible at the printed size; a hairline
  axis or a marker smaller than the line it sits on is lost in print.
- **Colour.** In the greyscale and the two simulated colour-blind panels, the series are still told apart
  (by lightness, shape, line style or a direct label). Colour carries meaning, the same meaning in every
  figure (one tool, one colour throughout), and a sequential quantity uses a sequential palette, not a
  rainbow. Red against green with no other cue fails about one man in twelve.
- **Clutter.** Nothing that carries no data: 3D effects, heavy grids, shadows, a legend that repeats the
  axis, more series than a reader can follow. Direct labels beat a legend the eye must travel to.
- **Style across figures.** The same font, sizes, palette and panel-letter style in every figure, and the
  same name for the same thing in the figures and the text.
- **Panels.** Multi-panel figures have letters, in reading order, each one used in the caption and the
  text.
- **Resolution.** A raster reaches the venue's resolution at its printed width; a photograph and a line
  drawing may have different minimums. Prefer vector formats for plots.

## Its content

- **One message.** Say in one sentence what a reader should take from the figure. If you cannot, or need
  two sentences, it has two messages or none. The message should be visible first: the comparison that
  matters is the largest, nearest or annotated thing.
- **The caption** says what is shown, then how: what each panel, colour and mark is; n, and what it counts
  (samples, runs, people); what error bars, bands or boxes show (standard deviation, standard error, a
  confidence interval, the range); the test and any correction behind a p-value or asterisk; units and
  abbreviations. A reader should understand the figure from the caption without the text.
- **Numbers.** Read every value off the figure (bar labels, annotated values, the height of the key bar on
  its axis) and compare it with each sentence and table that gives the same quantity. A disagreement is a
  finding with both values quoted; find its cause when the code or the data can show it (a mean plotted
  where the text gives the median, an older run).
- **Citations.** Each figure is cited in the text, first in numerical order, and every citing sentence
  claims what the figure shows: a sentence that cites Figure 3 for a result Figure 3 does not show is a
  finding, quoted.

## Its code

Find the code that writes the figure file (search the connected code folders for the file's stem;
notebooks count). Read it:

- Does it plot what the caption says: the statistic (median or mean), the runs or samples included, the
  filter, the transformation, the scale?
- Do the inputs it names exist, in the version the paper describes?
- Does running it reproduce the figure? Run it only with the authors' permission or a project instruction
  that allows it, through `runs.py exec`, writing into the run folder. Report a figure that cannot be
  regenerated, and why (an input missing, a hard-coded path, a value typed in by hand).

A declarative spec (Vega-Lite, a ggplot object saved with its data) is the code and the data together:
check its marks, encodings, transforms and data the same way.

## Recommendations

Each recommendation names the figure, the change and the reason, with the measurement or passage behind it.

| Situation | Recommendation | Reason to give |
|---|---|---|
| Labels print below the venue's minimum | Redraw at the printed width with text at the minimum or above | "The chromosome labels print at 3 pt in a 178 mm figure; the journal asks for 6 pt." |
| Series merge in greyscale or for colour-blind readers | A colour-blind-safe palette with a second cue (line style, direct labels) | "In greyscale the treated and control lines have the same grey." |
| A bar chart of means with few points | Show the points, or a dot plot with the interval | "With six mice per group, the bars hide the spread a reader needs to judge the difference." |
| Two messages in one figure | Split it, or lead with one and move the other | "Panel a is the main comparison; panel b checks a preprocessing setting." |
| A legend far from the data | Label the lines directly | Readers match colours to names once instead of for every line. |
| A key result only in a table | A figure of that result, the table kept or moved to the supplement | "Replication in the second cohort is a headline claim and no figure shows it." |
| A method with many steps and no overview | A schematic of the steps, inputs and outputs | Readers who skim see figures and captions first. |
| A tool paper with no example of output | A figure of real output from the authors' files | "What would I see?" is the potential user's first question. |
| A figure that defends a choice | Move it to the supplement, keep one sentence in the text | "The text already says in one sentence that the result does not depend on the cut-off." |
| More figures than the venue allows | Name which move to the supplement or merge | The limit, quoted with its source. |

Moving, adding, merging and splitting figures are decisions for the authors (`decision: true`). A caveat a
figure carries moves with it and is never lost; evidence that would change a reader's conclusion stays in
the main text.
