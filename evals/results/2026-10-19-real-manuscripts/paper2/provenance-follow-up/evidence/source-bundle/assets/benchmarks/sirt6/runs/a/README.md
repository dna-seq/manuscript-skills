# SIRT6 rs117385980 and longevity

One variant, two studies, one honest trend.

## Where this module came from

Authored from a single paper supplied by the module owner:

> Sheikholmolouki E, Sharifi F, Nickhah Z, Vahidi A, Lajevardi R, Haghpanah V, Amoli MM.
> *The association of the SIRT6 rs117385980 variant with frailty and longevity: an exploratory study.*
> Sci Rep 15:40251 (2025). PMID 41249831. doi:10.1038/s41598-025-24018-3

That paper's own longevity claim rests on an earlier Finnish study, which it cites as its
reference 12. Because the requested subject is longevity rather than frailty, and because the
2025 paper's longevity claim is a replication of that earlier result rather than an independent
one, the primary source is carried as a second study row:

> Hirvonen K, Laivuori H, Lahti J, Strandberg T, Eriksson JG, Hackman P.
> *SIRT6 polymorphism rs117385980 is associated with longevity and healthy aging in Finnish men.*
> BMC Med Genet 18:41 (2017). PMID 28399814. doi:10.1186/s12881-017-0401-z

Both fulltexts were retrieved and read in full. No claim in this module comes from an abstract.

## What the evidence actually supports

The T allele of rs117385980 is **depleted among the longest-lived** in both cohorts, and the two
studies agree on direction. **Neither result is statistically significant.**

| | Hirvonen 2017 (Finland) | Sheikholmolouki 2025 (Iran) |
|---|---|---|
| Design | case-control, two cohorts combined | allele/genotype frequencies nested in a cohort |
| n | 198 combined | 227 |
| Longevity-relevant test | combined two-tailed Fisher exact | T-allele frequency across three age strata |
| p | 0.074 | 0.073 |
| Effect | OR 3.58 (95% CI 0.96–13.4) | no OR reported for this test |
| Power | 28.4% by the authors' own analysis | not stated; MAF ~0.018 in cohort |

The 2025 paper's **primary** hypothesis — association with frailty — was **null** (allelic
p = 0.36; fully adjusted OR 0.96, 95% CI 0.10–9.66). The module does not carry a frailty claim.

This is a research-grade trend. It is not a lifespan prediction for any individual, and the
module should not be read as one.

## Decisions a reviewer still has to make

Nothing below was settled silently. Each is a judgement this module deliberately left open.

1. **Only the C/T genotype is authored.** It is the only genotype either cohort observed —
   every carrier in both studies was heterozygous.
   - **C/C** — Hirvonen's discussion argues the CC genotype "could have a positive effect on the
     lifespan". That is an inference from the same 2×2 table, not a separate observation, so
     authoring it would double-count one test. Left out; a reviewer may disagree.
   - **T/T** — observed in **neither** cohort. gnomAD records 183 homozygotes globally
     (global AF 0.0218), so the genotype exists and no published evidence describes it.
2. **`state` = risk, `stat_significance` = suggestive.** Both papers frame their result as a
   trend that failed their own significance threshold. `suggestive` is the closest honest value;
   an argument for `not_significant` is defensible and would be a reviewer's call.
3. **The two papers disagree about what this variant *is*.** The 2025 paper calls it "a stop
   gained variant within the exon 2 of SIRT6". Hirvonen locates it "23 bases downstream of the
   exon 2 exon/intron border" and types it **intron variant** in both Table 1 and Table 2.
   gnomAD's 183 homozygotes at ~2.2% allele frequency argue against a stop-gained call in a gene
   whose inactivation is perinatally lethal (Ferrer 2018). **No molecular consequence is asserted
   in any cell of this module.** Resolving it needs a source neither paper is.
4. **`flags: pleiotropic`** records the 2025 paper's own "diverse effect": the T allele is
   depleted at advanced age yet *enriched* among robust (non-frail) participants. The paper
   raises antagonistic pleiotropy as one possible explanation. The counter-direction is written
   into the variant row's `negatives` rather than being dropped.

## What is not here

- **No weights.** See `weighting:` in `module_spec.yaml`.
- **No frailty rows.** The source's frailty result was null.
- **No rows for the other SIRT6 SNPs** the 2025 paper discusses secondhand (rs107251, rs350846,
  rs350852, rs350844, rs352493, rs4807546, rs3760905). Each belongs to a different paper that was
  not read here. Carrying them would assert claims this module has not checked.
- **No coordinates in the authored tables.** `rsid` alone is authored so that resolution supplies
  the coordinate independently and the compiler's rsid-vs-coordinate check has something real to
  compare.

## Licensing

`licensing.csv` carries a row per source. The two article rows sit at `layer=annotation` because
verbatim passages from both are quoted in `studies.csv`:

- PMID 41249831 — **CC BY-NC-ND 4.0**: not sellable, and the NoDerivatives term is recorded in
  that row's `notice`. Only verbatim quotation is carried.
- PMID 28399814 — **CC BY 4.0**.

The NC term on the 2025 article is the binding constraint on this module as a whole.

## What the gates said

Recorded here because a green build is not evidence a module is right, and the warnings are the
interesting output.

- `validate_module(strict=True)` — **valid**, two warnings, both expected:
  - no closure at the time of that run (closed afterwards);
  - one study quote comes from a `cc by-nc-nd` article (PMID 41249831), so the passage is
    publisher text in this module's annotation layer and a commercial distribution would have to
    answer for it. Recorded rather than adjudicated. This is the module's binding licence
    constraint and is why `license:` is declared `CC-BY-NC-ND-4.0`.
- `enrich_module` — 1 of 1 subject resolved from Ensembl, **no ref mismatch**, VRS id minted.
- `enrich_literature_pass` — both PMIDs exist; **2 of 2 provenance quotes found in retrieved
  fulltext**; no titles-as-quotes; no DOI conflict.
- `check_identifiers` — `SIRT6` approved (HGNC:14934), `OBA_VT0005372` current
  ("life span determination trait"). Gene-locus comparison **ran** and found no conflict.
- `enrich_gwas_effects` — the GWAS Catalog holds **no association** for rs117385980. Recorded as a
  `not_found` row, and it is a real fact about the variant: this signal has never been
  genome-wide significant anywhere.
- `audit_module` — one open decision: 3 of 11 recorded checks compared nothing. All three are
  structurally correct for this module — no row asserts a `clin_sig`, and rsid-only rows make no
  rsID-vs-coordinate pair claim to compare. Nothing here is a defect to repair.

### An honest limit on the quote check

Both `provenance_quote` values were located by an agent (`curator: claude-opus-5`) reading the
fulltext through `fetch_fulltext`. Because the text was read through the same retrieval the
checker uses, `quotes_found` on these rows is a **citation-pairing** check — it proves the passage
belongs to the PMID it is filed under, and it is *not* independent evidence that the claim is in
the literature. Stated rather than hidden.

## Status

Compiled and closed; **not published anywhere**, neither the polygon nor the catalog.

## One licence row this module did not author

`enrich_facts` ran three passes: `frequencies`, `gene_metrics` and `dosage`. The **dosage** pass
queried ClinGen and **found nothing for SIRT6** (`covered: []`, `missing: ["SIRT6"]`). It
nevertheless wrote a licence row:

```
clingen,annotation,CC0-1.0
```

Two things about that row are worth a reviewer's attention, and neither was repaired here:

1. **It sits at `layer=annotation`.** Per the schema, `annotation` means *the module's own authored
   tables*, and it is the only layer that carries a derivative-work obligation; ClinGen dosage data
   would land in `gene_metrics.csv`, a fact sidecar, for which the vocabulary already has a
   `gene_metrics` layer. Nothing from ClinGen is in this module's annotation layer, because nothing
   from ClinGen is in this module at all.
2. **It is what trips the compile warning** `module declares license 'CC-BY-NC-ND-4.0' but
   annotation-layer sources report ['CC-BY-4.0', 'CC0-1.0']`. A reviewer re-adjudicating that
   warning is being asked about a source that contributed zero rows.

Left in place deliberately: it was written by a pass, not by the author, and silently deleting or
relabelling another layer's output is the repair this project's rules forbid. Recorded here so the
warning is explicable rather than mysterious. A reviewer may reasonably decide the row should be
`layer=gene_metrics`, or should not exist.
