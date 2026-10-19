# SIRT6 and Longevity (`longevity_sirt6`)

One variant, one paper, one honest hedge.

## Where this module came from

Nothing in the format records a module's origin, so it is recorded here.

This module was built from a **single source**, handed over as a DOI:

> Sheikholmolouki E, Sharifi F, Nickhah Z, Vahidi A, Lajevardi R, Haghpanah V, Amoli MM.
> *The association of the SIRT6 rs117385980 variant with frailty and longevity: an exploratory study.*
> **Sci Rep 15:40251 (2025).** PMID 41249831 · PMC12624115 · doi:10.1038/s41598-025-24018-3

The article was **read in full** (via PMC), not from its abstract. The PMID was taken from a
literature search result and the title read back, not recalled.

## What the source actually claims — and what it does not

This matters more than usual, because the paper's headline and its result point different ways.

- It is an **exploratory case-control study of 227 Iranian adults** aged 60–90, nested in the
  Birjand Longitudinal Aging Study. Genotyping was PCR-RFLP, validated by Sanger on three samples.
- **The frailty result is null.** No significant association at any model: univariate allele
  OR 1.42 (95% CI 0.18–11.67, p=0.75), final adjusted OR 0.96 (0.10–9.66, p=0.98).
- **The longevity result is a non-significant trend.** T-allele frequency was 1.39% at 60–69,
  4.65% at 70–79 and 0% at 80–90 (Fisher exact p=0.073). The paper's own conclusion calls this
  "a non-significant trend … which may imply a role in longevity."
- The T allele is rare in the cohort: **8 heterozygotes in 227 people**, and **no TT homozygote
  was observed at all**.

So the module carries **one row**, for the one genotype the paper measured, with `direction`
recorded as `unknown` and `stat_significance` as `not_significant`. It is not padded.

## Deliberate omissions

- **No `weight`, anywhere.** `weighting:` declares `scale: none`. A null result and a p=0.073 trend
  support no magnitude, and inventing one would look exactly as authoritative as a real one.
- **No `T/T` row.** The source observed no TT carrier. A conclusion for that genotype would be an
  allele-level inference the paper never makes. Left as a decision for a reviewer.
- **No `C/C` row.** Same reason in reverse: the paper's numbers are about heterozygotes.
- **No effect size.** Every odds ratio in the paper is either a frailty model (the null result) or
  an age-band Fisher contrast whose reference group is not stated. Attaching one to a longevity
  claim would misstate the endpoint.
- **No second study row.** The paper leans on Hirvonen et al. 2017 (BMC Med Genet 18), a Finnish
  male cohort, for the prior longevity association, and cites TenNapel 2014, You 2016 and Lin 2016
  for other SIRT6 variants. None of those was read here. **They are the natural second pass**, and
  the Finnish paper in particular is where the association claim actually originates.

## Provenance honesty

`studies.csv:provenance_quote` is a verbatim sentence from the article's Conclusions, **located by
an agent** (`curator: claude-opus-5`), not by a human reader. Recorded so a reviewer can route
scrutiny; responsibility for it rests with the human author regardless.

Because the fulltext was retrieved through this toolchain before the quote was written, the
enricher's `quotes_found` check on that row is **no longer independent evidence** that the claim is
in the literature. It has become a citation-pairing check — it still catches a quote filed against
the wrong PMID, and that is all it now proves.

`studies.csv:doi` is filled. That is deliberate and it is *not* self-referential: the DOI was
supplied by the human who commissioned the module, before any lookup, so the enricher's
`_doi_conflicts` check compares it against the registry's independently and could genuinely fail.

## Licensing — read this before selling anything

The article is **CC BY-NC-ND 4.0**. Because one verbatim sentence of it is redistributed inside
`studies.csv`, that licence reaches the module's **annotation layer**:

- `commercial_use: false` — **this module may not be sold.**
- `declared_use: non_commercial` — the position the compile gate reads.
- NoDerivatives: the quoted passage is unmodified and attributed. Adapted material derived from the
  article may not be shared under this licence.

The `pubmed` row at the `literature` layer records only the service the record was read through.
Its permission booleans are deliberately blank: undetermined is never permitted.

## Coordinates

Authored **rsid-only** on purpose. The paper states no assembly, so its build is *unknown* rather
than GRCh38, and no coordinate was copied from it. `resolution.csv` supplies the position
independently, which is what gives the compiler's rsid-vs-coordinate check something real to
compare.

## What this module is not

It is a rulebook, not a reading of anybody's genome. It does not interpret a genome, call a
genotype, or give medical advice — a consumer supplies the measurement. And a single exploratory
cohort of 227 people with 8 carriers is a starting point for a research question, nothing more.

## Publish readiness — measured, not assumed

Everything local is green: `validate_module(strict)` valid, `enrich_module(strict)` resolved 1 of 1,
`check_identifiers` 1/1 gene and 1/1 trait clean with no locus conflict, `compile_module(strict)`
successful, `verify_artifact` digests verified, and the module is **closed** with all 11 check
records intact (`dropped_checks: []`).

**One thing blocks an actual publish today, and it is not a defect in this module.**

`registry_check(target="test", strict=true)` returns:

    studies.csv line 2 [curator]: Extra inputs are not permitted

`StudyRow.curator` — the per-row record of *who located the provenance quote* — shipped in
**just-dna-format 0.6.5**. Both live registry instances currently serve **format 0.6.1**
(`/api/v1/version` on prod and polygon alike), and `StudyRow` is `extra="forbid"`, so a 0.6.1
server refuses the column. The version-contract check does not catch this: it is scoped to
major.minor, and 0.6 equals 0.6.

Measured counterfactual: an identical spec with the single `curator` column removed returns
`verdict: true`, `module_level_clear: true`, `blocking: []`.

**The column was kept deliberately.** Dropping it to obtain a green preflight would delete the
module's only record that an agent, not a human, located its one quote — conforming the module to
a registry that lags the format rather than the other way round. The remedy is a registry running
format ≥ 0.6.5; until then, publishing requires a conscious decision to drop the attribution, and
that decision belongs to a human.

## Decisions waiting for a human

1. **Keep `curator` and wait, or drop it and publish.** See above. Recommendation: keep it.
2. **Should there be a `T/T` row?** The source observed none. gnomAD records 183 global
   homozygotes, so the genotype exists. Adding it means making an allele-level inference the paper
   does not make; omitting it means a TT carrier gets no annotation.
3. **Should the row exist at all?** `state=alt` was chosen because the vocabulary has no member
   meaning *undecided*. `module-curate` says that where neither `neutral` nor a direction can be
   justified, the honest move may be to drop the row. Logged in `logs/authoring.log`.
4. **The `clingen` licence row.** `enrich_facts`' dosage pass recorded a ClinGen annotation-layer
   row (`CC0-1.0`) although it covered nothing (`missing: [SIRT6]`). That row is the sole cause of
   the compile warning about a licence mismatch. Removing it is a judgement, so it was left alone.
5. **Whether `commercial_use: false` is acceptable.** It follows from quoting a CC BY-NC-ND
   article. Paraphrasing instead of quoting would lift the restriction and lose the attestation.
6. **The second pass.** Hirvonen et al. 2017 (Finnish male cohort) is where the longevity
   association actually originates; this paper only echoes it. Reading it is the obvious next step.
