# Number and statistics checks: reading `number_check.py`

`scripts/number_check.py` finds candidates; the agent checks each against the manuscript in context and against
the project's files and data before anything reaches the authors. A calculator cannot tell an exact value from a
rounded one, which data are whole numbers, or which n a value was computed over, but the project often can: the
result table or run log behind the number, the code that computes it, the analysis output with its n. A candidate
the files settle is a confirmed finding, reported with its arithmetic and the file that settles it and corrected
under the `edits` setting like any confirmed finding, or a dismissed one. Only a provenance question the files
leave open (which n, which run, whether a value is rounded from another) goes to the authors, in the report's one
batch of questions. Never call a candidate an error, fabrication or misconduct.

## Which script covers what

| Check | Script | What it compares |
|---|---|---|
| Percentage beside its counts ("12 of 40 (30%)") | `scan.py` | the percentage against the counts |
| Abstract figure with a unit that never reappears | `scan.py` | the Abstract against the body, by number only |
| Number ledger | `number_check.py` | one named quantity (a sample size, a headline metric) across sections |
| GRIM, percentage of n, Table "n (%)" cells | `number_check.py` | a mean or percentage against the n it claims |
| GRIMMER | `number_check.py` | an SD against its mean and n |
| Statcheck | `number_check.py` | a p-value against its test statistic and df |
| Table column totals | `number_check.py` | a "Total" row, or a total stated in a sentence that cites the table, against the column's sum |
| SEM in a table | `number_check.py` | a "mean ± SEM" column against the row's SD column divided by √n |
| Statistics reporting (n per analysis, replicates, SD versus CI, every declared test used) | `manuscript-reporting-check` | the Methods and Results against reporting expectations |

## Number ledger

A quantity is a sample-size noun ("participants", "patients", "genomes", "mice"; also "All participants
(n = 421)" in a table header) or a named metric (AUROC, accuracy, sensitivity, F1, R², odds ratio and others).
Two rules raise a candidate:

1. Where a study states its totals (Abstract, Methods, tables, Conclusions), a section whose sample size
   shares no value with any other section and never appears elsewhere as a number.
2. A value stated in the Abstract or Conclusions that the body never states for the same quantity.

Sentences citing other work and the Introduction are skipped and counted. A Results count is usually a
subgroup ("the 31 participants who completed follow-up") and only serves as a value the others can match.
Values compare with their rounding: 0.9 matches 0.87, 91% matches 0.912.

Common legitimate explanations: a subset (analysed versus recruited), another dataset (validation versus
test), exclusions after quality control. The fix is usually a clause saying which population each number
describes, not a new number.

## GRIM and GRIMMER

- **GRIM** (Brown and Heathers, *Soc Psychol Personal Sci* 2017, doi:10.1177/1948550616673876): the mean
  of n whole numbers is a whole number divided by n, so some reported means are impossible at their
  precision. It is informative only when n is smaller than 10 to the power of the decimals (n < 100 for two
  decimals); larger n is counted as "not informative", not as passed.
- **GRIMMER** (Anaya, *PeerJ Preprints* 2016, doi:10.7287/peerj.preprints.2400v1): the sum of squares of
  whole numbers is a whole number with the parity of their sum, which excludes some SDs. The script accepts
  a pair when either the sample (n − 1) or the population (n) SD fits, and declines when the SD's rounding
  leaves too wide a range.
- The script applies both only where the sentence or table row names whole-number data (Likert or point
  scales, ratings, counts, "number of", items) and states n, or with `--assume-integer`. Ages, weights,
  durations and concentrations are left out by their own words.
- For a k-item scale reported as a mean item score it uses n × k, which can only make a failure rarer.
  GRIMMER is not applied to multi-item means.

Legitimate reasons for a failure: the mean is over fewer people than the stated n (missing answers,
exclusions), the scale score is not a whole number (weighted or reverse-scored items averaged), or a typo.
Ask which.

## Test statistics (statcheck)

The idea follows statcheck (Nuijten et al., *Behav Res Methods* 2016, doi:10.3758/s13428-015-0664-2);
statcheck itself is GPL-3 and none of its code is used. The script reads APA-style results
(`t(28) = 2.10, p = .04`, `F(1, 62) = 4.41`, `χ2(1, N = 64) = 4.71`, `r(62) = .45`, `z = 2.10`, Welch
fractional df) in Markdown, LaTeX and plain text, recomputes p over the rounding interval of the statistic
(and of a fractional df), and compares it with the reported p:

- **consistent**: the intervals overlap; `p < .001` is consistent when the recomputed p can be below .001;
- **consistent-one-tailed**: the reported p fits the one-tailed value and the same sentence says the test was
  one-tailed;
- **inconsistent** (minor): they do not overlap, but significance at α is the same;
- **gross** (major): the reported p and the recomputed p fall on opposite sides of α;
- **adjusted?** (info, an optional note that does not change the exit code): the reported p is larger and the
  sentence names a multiplicity adjustment (Bonferroni, Holm, false discovery rate, q-values), which would explain
  it.

These five words are the script's labels (the JSON's `status`). In the report, say what they mean: "the reported p = .04 does not
fit t(28) = 1.20, which gives p = .24, and the result would no longer be significant at .05 (statcheck)".

α is the one the text states ("P < 0.05 was considered significant", "α = .01"), else 0.05; `--alpha`
overrides. A one-tailed p counts as consistent only when the same sentence says the test was one-tailed; if
the paper mentions one-tailed tests elsewhere the candidate carries a note asking the authors to say so beside
the result. Results the script cannot read (no df, a statistic given as a bound, tests such as U, W, H) are
listed as not assessed, never as passed.

The p-values come from the standard library (math.erfc for z; continued fractions for the regularised
incomplete beta and gamma functions for t, F, r and χ²). They agree with scipy to better than 1e-10 relative
error over the ranges papers report.

## Table arithmetic

A column total is compared with the sum of the column's numbers, in a total row (first cell "Total", "Sum",
"Overall" or "All") and in a sentence that cites the table and states a total of the column's noun ("across 19
versions"). Decimal cells widen the tolerance by their rounding; whole-number cells are exact counts. Columns of
means, rates, percentages, times or memory are not sums and are listed as not assessed; so is a column with a cell
that is not a plain number. A mismatch in the total row is major; one stated only in the text is minor, since the
text may count something the table leaves out. For a "mean ± SEM" column beside an SD column and an n column, SD /
√n (over the SD's rounding interval) must reach the reported SEM. The usual explanation is an n that differs between
the statistics.

## Benchmark arithmetic by hand

Software and benchmark papers usually have no means of whole-number data, no test statistics and no SD column, so
`number_check.py` often reports nothing to test. That is not a clean result. Recompute from the printed values:

- **Ratios and fold changes**: divide the two numbers the ratio names and compare with the stated value at its
  rounding (612.4 s / 3.4 s = 180.1, stated as 180x). Say whether the paper divides medians or means; when both
  are printed and give different ratios (7x for the medians against 4x for the means), the text should say which
  one it quotes.
- **Means, SDs and SEMs from listed runs**: recompute the mean and SD from the individual runs when they are given;
  SEM = SD / √n, with n the number of runs that went into the mean (not the number of inputs or of scores). With
  n = 2 the SD is |a − b| / √2 and the SEM is |a − b| / 2.
- **Few runs per arm**: with two or three runs per arm, give the range of the per-run ratios beside the ratio of
  medians, from the fastest run of the slower tool divided by the slowest run of the faster one, to the slowest
  divided by the fastest; a headline speed-up should not rest on a ratio the range does not support.
- **Totals**: stage times against the total run time (a constant gap in every row is overhead the text should
  name), peak values against the table they cite, counts in the text against the table rows they summarise
  ("12 tools" against a table of 13 rows).

Report each disagreement under "Fix now" with its arithmetic, and say in one sentence what you recomputed and found
consistent, so the authors know what was covered.

## Reporting a candidate

Quote the sentence or table row with its section, the line number only in parentheses, then the arithmetic and
the smallest check, in full sentences: "In the Results, 'the layered group rated it 5.64 on average (n = 32)'
cannot be right for whole-number ratings: 180/32 = 5.625 and 181/32 = 5.656, so no total gives 5.64 (GRIM test).
Recompute the mean from the data." Name a check by what it tests, with its name in parentheses. Number
candidates belong to the report's "Fix now" group. Group findings with one root cause (a wrong n explains a
ledger conflict and the GRIM failures that use it). For a revision, rerun the script and compare.
