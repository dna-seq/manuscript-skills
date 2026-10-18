# Statistics reporting

A reading checklist for how a manuscript reports its statistics. It is about whether a reader can tell
what was done, not about re-running the analysis. Arithmetic checks (percentages against counts, GRIM,
P values recomputed from test statistics, one quantity reported with different values) belong to
**manuscript-integrity-check's numbers check**; use that rather than recomputing here.

Work through the analyses that carry the paper's claims: the abstract's results, the main figures and
tables, and every comparison the Discussion leans on. For each one, find the answers below in the text,
legends or supplement. Report what is missing with its location; never fill a gap with a value you
inferred.

## The unit and the n

- **n is the independent unit.** State what one unit is (a participant, an animal, a culture, a donor, a
  sequencing library, a simulation run) and give n per group. Cells, fields of view, repeated readings,
  variants or reads are not independent units of a between-group comparison unless the design makes them
  so.
- **Biological versus technical replicates.** Say which are which and how technical replicates were
  combined before inference. "Three independent experiments" needs to say what was independent.
- **Flow of units.** Numbers at each stage (eligible, included, genotyped, analysed), exclusions with
  reasons, and whether exclusion rules were set before the analysis.
- **Sample size.** How n was chosen (power calculation, all available samples, a fixed budget). "All
  available" is an honest answer; a missing answer is a gap.

## The test for each comparison

- Name the test or model **for each comparison**, not one list for the whole paper. Paired or unpaired,
  one- or two-sided, parametric or not, fixed and random effects, covariates in the model.
- Assumptions: how they were checked, or why the method does not need them.
- **Every declared method is used, and every reported statistic has a declared method.** A test listed in
  Methods and never reported, or a P value with no named test, are both gaps.
- Repeated measures, clustering (families, sites, batches) and relatedness are in the model, not ignored.

## Multiple testing

- Say how many tests were run (including those not shown) and how the false-positive rate was controlled:
  Bonferroni, Holm, Benjamini-Hochberg FDR, permutation, a genome-wide threshold with its value
  (commonly 5 × 10^-8 for GWAS), or a pre-specified primary comparison.
- A threshold of P < 0.05 across many tests, with nominal hits reported as findings, is the commonest gap.
  The fix is to report the correction (often possible on P values already computed) or to label the hits
  as exploratory; it is not new data.
- Report results after correction (adjusted P or q values), not only which passed.

## Effect sizes and uncertainty

- Report the effect (difference, ratio, beta, correlation, AUC) with a confidence or credible interval,
  not only a P value or stars.
- Give exact P values where the venue allows, and define any stars once.
- Association language stays associative; a significant result is not by itself a large or important one.

## Error bars and summaries

- Table arithmetic (column totals, SEM against SD/√n) is checked by
  `../../manuscript-integrity-check/scripts/number_check.py`; reuse its output rather than recomputing.
- Say what every error bar and ± shows: **SD** (spread of the data), **SEM** (precision of a mean, which
  shrinks with n) or **CI** (with its level). An undefined ± is a gap.
- Box plots: what the box, whiskers and points show. Medians with interquartile ranges for skewed data.
- The n behind each plotted summary appears in the legend.

## Software, versions and randomness

- Software and packages with versions, and the options or settings that change results (STREGA 12a asks
  this of genetic studies; most venues ask it of everyone).
- Random seeds, the number of runs, and how results were aggregated across runs for anything stochastic
  (machine-learning training, permutations, simulations, bootstraps).
- Where the analysis code is (cross-check with `availability.md`).

## Timing and resource benchmarks

Software papers compare run time and memory rather than test outcomes. For each benchmark table or claim
("N times faster", "under a minute"):

- **Repeats and spread.** How many runs per tool and input, and the spread (SD, IQR or range), not only a
  mean or median. One run per condition is a single observation; say so.
- **n per arm and the unit.** What one observation is (a run, an input file, a score) and n for each tool
  and input. A mean ± SEM over n = 2 says little; give the values.
- **Pooled conditions.** Whether runs pool different states (cold and warm cache, idle and loaded machine,
  different sessions or days, warm-up runs) and whether any were dropped.
- **Hardware and software.** CPU model and cores, memory, storage type, operating system, the version of
  every tool compared, thread or worker settings, and whether all tools had the same inputs and limits.
- **What was measured.** Wall-clock or CPU time, which stages are included, and how peak memory was
  sampled (the same way for every tool, or say they are not comparable).
- **Ratios.** Which summary a speed-up comes from (ratio of medians or median of ratios), so the reader
  can recompute it from the table.

## Blinding and randomisation

Where the design has them: how units were allocated, and whether outcome assessment was blinded. Where it
does not, say nothing is required; do not ask a computational reanalysis to describe blinding.

## Reporting a gap

Write each finding as connected sentences ([writing for the authors](../../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)):
quote the sentence, table row or legend it concerns and name its section or table (a line number in
parentheses at most), say what is missing and why it matters for the claim, and what to add. Put it under
the [stage](../../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done) at which it can be fixed: **Fix now**
when the analysis the claim needs is missing or unsound (no correction across 48 tests, technical
replicates counted as independent units), **Then the writing** when what was done is only unclearly
reported (an undefined ±, a test not named for its comparison, a missing version of a tool that was
used). The version of the authors' own software quoted in the text becomes final with the code, so it
belongs under **Before submission, once the code is final**. When the
authors must supply a fact (the n, the test, the correction, a version), add it to the questions at the
end of the report. Never invent a value, a test or a correction, and never propose wording that implies
an analysis was done when the manuscript does not say it was.

The design follows the statistics-reporting audit in Boom5426/Nature-Paper-Skills (stats-reporting-audit,
Apache-2.0, itself from Yuan1z0825/nature-skills); this file is written in our own words.
