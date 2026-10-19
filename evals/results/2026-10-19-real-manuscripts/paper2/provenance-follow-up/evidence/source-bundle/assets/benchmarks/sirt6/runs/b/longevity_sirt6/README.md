# SIRT6 rs117385980 and human longevity

One variant, three genotypes, two papers. Both papers point the same way and neither reaches
statistical significance. This module exists to record that direction honestly, with its limits
attached, rather than to assert an effect on lifespan.

## What the module claims

`rs117385980` is a C>T single-nucleotide polymorphism in *SIRT6* on chromosome 19. Two independent
cohorts report the T allele as less common among their oldest and longest-lived participants:

- **Hirvonen et al. 2017** (PMID 28399814), Finnish men. The T allele appeared in 1 of 43 long-lived
  healthy men and 9 of 92 men who had died at a mean age of 66.6, plus 2 of 63 healthy men of mean
  age 83 in a replication cohort. Combined two-tailed Fisher exact test: OR 3.58, 95% CI 0.96 to 13.4,
  **p = 0.074**. The authors report the study's power as 28.4 per cent.
- **Sheikholmolouki et al. 2025** (PMID 41249831), Iranian adults aged 60 to 90 in the Birjand
  Longitudinal Aging Study. The T allele was absent from all 40 participants aged 80 to 90 and present
  at 1.39 and 4.65 per cent in the two younger age bands, **p = 0.073** across the three bands.

Neither crosses p < 0.05. The 2025 paper is explicitly framed by its own authors as exploratory, and
its primary question was frailty rather than longevity: on frailty it found nothing at all (p = 0.36,
every adjusted model crossing one). Its longevity signal is a secondary observation.

**The direction is not clean.** The same 2025 paper found the T allele slightly *more* common among
robust than among frail participants, which points the other way, and its authors describe the effect
as "diverse". The module records the age-related direction because both cohorts agree on it, and the
row conclusions carry the contradiction.

## Two discrepancies in the sources, recorded rather than resolved

Both are in `studies.csv` conclusions as well, because a reader may never open this file.

1. **The two papers disagree about what the variant does.** Hirvonen 2017, who found it by sequencing,
   calls it an **intron variant** situated 23 bases downstream of the exon 2 exon/intron border.
   Sheikholmolouki 2025 calls it a **stop-gained variant within exon 2**. These are very different
   functional claims and the 2025 paper offers no source for its version. This module asserts neither;
   it records the disagreement. Resolving it needs a current transcript-level annotation, which nothing
   in this module's evidence base supplies.
2. **Hirvonen's odds ratio is stated twice, differently.** The abstract says 3.53; the Results text and
   Table 2 both say 3.58, with the same confidence interval. `studies.csv` records **3.58**, the table's
   value. An author transcribing from the abstract alone would have written 3.53.

## Genotypes

| Genotype | State | Direction | Weight | Why |
|---|---|---|---|---|
| `C/T` | risk | risk | -0.2 | The only genotype either study observed carrying T. Both cohorts trend against it for longevity; neither significantly. |
| `C/C` | ref | neutral | 0.0 | The common genotype. Weight is an explicit zero, not a blank: no advantage is asserted, because the trend in its favour was not significant. Carries `requires_callable=true` so a no-call is not read as this result. |
| `T/T` | alt | unknown | *(unweighted)* | **Not observed in either cohort.** Both carried T only heterozygously. Nothing in this evidence base speaks to it, so no direction and no weight are asserted. |

## Weights

See the `weighting:` block in `module_spec.yaml` for the scale in full. In short: minus one to plus one,
curator-set, positive is protective, ordinal **within this module only**. The magnitudes are small on
purpose because nothing behind them is significant. They are not comparable with any other module's
weights, and summing weights across modules produces a number this scale does not support.

## Sources and licensing

The two articles are recorded at `layer=annotation` in `licensing.csv`, because a verbatim sentence
from each is carried as a `provenance_quote`:

- Sheikholmolouki 2025 is **CC-BY-NC-ND-4.0** — non-commercial, and no derivatives. Whether a short
  verbatim quotation counts as quotation or as adapted material under the ND clause is a genuine
  question this module does not settle. It is flagged in that row's `notice`.
- Hirvonen 2017 is **CC-BY-4.0**.

The module-level `license:` is declared as the more restrictive of the two, CC-BY-NC-ND-4.0.

Bibliographic services actually used (PubMed, Europe PMC, OpenAlex, Crossref, Unpaywall) each carry a
`layer=literature` row with permission flags left **unknown** rather than assumed, since their terms
were not read as licence documents. Two services were queried and contributed nothing to this module,
so neither has a row: the preprint index returned records none of which are cited, and Semantic Scholar
was rate-limited on every attempt and answered nothing at all. That is unchecked, not empty.

## What this module is not

It does not interpret a genome, call a genotype, or give medical or lifestyle advice. It is an
annotation table: a consumer supplies the measurement. The `actionability` on every row is
`descriptive`, which is the honest value here.

It is also **not evidence that SIRT6 variation affects human lifespan**. It is a record of two small,
non-significant studies that lean the same way. The heterozygous genotype it describes is carried by
roughly two per cent of people, and neither study observed enough carriers to say anything firm.

## Provenance of the quotes

Both `provenance_quote` values were located by an AI agent reading each article's full text through
Europe PMC, and `studies.csv:curator` records that on both rows. The human author holds responsibility
for them regardless. Note the honest cost: because the quotes were located in the same Europe PMC full
text that the enrichment pass checks them against, `quotes_found` on these rows is a citation-pairing
check — it catches a quote filed against the wrong PMID — and is not independent evidence that the
claim appears in the literature.
