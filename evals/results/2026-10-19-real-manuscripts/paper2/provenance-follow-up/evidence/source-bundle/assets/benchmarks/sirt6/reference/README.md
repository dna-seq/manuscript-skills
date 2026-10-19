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
2. **`direction` = risk, and `unknown` is as defensible.** This is the module's largest single
   judgement and it was not flagged here until 2026-08-31. Against `risk`: the combined OR is 3.58
   with a **95% CI of 0.96–13.4**, an interval containing 1, at 28.4% power by the authors' own
   analysis — and this row's own `negatives` records the allele running the *opposite* way among
   robust participants, which is why `flags: pleiotropic` is set. For `risk`: `direction` and
   `stat_significance` are orthogonal columns, two cohorts point the same way, `suggestive` already
   says the result is not established, and the row carries no weight, so nothing downstream scales by
   the sign. A rerun of the same prompt over the same paper wrote `unknown`; a reviewer may prefer it.

3. **`state` = risk, `stat_significance` = suggestive.** Both papers frame their result as a
   trend that failed their own significance threshold. `suggestive` is the closest honest value;
   an argument for `not_significant` is defensible and would be a reviewer's call.
4. **The two papers disagree about what this variant *is*.** The 2025 paper calls it "a stop
   gained variant within the exon 2 of SIRT6". Hirvonen locates it "23 bases downstream of the
   exon 2 exon/intron border" and types it **intron variant** in both Table 1 and Table 2.
   gnomAD's 183 homozygotes at ~2.2% allele frequency argue against a stop-gained call in a gene
   whose inactivation is perinatally lethal (Ferrer 2018). **No molecular consequence is asserted
   in any cell of this module.** Resolving it needs a source neither paper is.
5. **`flags: pleiotropic`** records the 2025 paper's own "diverse effect": the T allele is
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

`licensing.csv` carries a row per source **that contributed data**. The two article rows sit at
`layer=annotation` because verbatim passages from both are quoted in `studies.csv`:

- PMID 41249831 — **CC BY-NC-ND 4.0**: not sellable, and the NoDerivatives term is recorded in
  that row's `notice`. Only verbatim quotation is carried.
- PMID 28399814 — **CC BY 4.0**.

The NC term on the 2025 article is the binding constraint on this module as a whole.

**Five `literature`-layer rows were removed on 2026-08-31** — `crossref`, `europepmc`, `openalex`,
`pubmed`, `unpaywall`. They were written while authoring to record which services were consulted, and
they are the wrong home for that: a literature source's terms are per *article*, not per source, and
this module's are already on `literature.csv` per PMID (`license`, `share_alike`, `commercial_use`,
`redistribution`). Upstream has no `pubmed` entry in `TERMS_BY_SOURCE` and will not add one (RM46).

Measured before removing them: **validate and compile are byte-identical either way** — same verdict,
same warnings — because literature-layer rows are exempt from the orphan check outright. So the rows
bought no enforcement, and a source-level row invites source-level permission booleans about metadata
while the constraint that binds is the article's `commercial_use: false`. `content_signature` and the
closure hash are unchanged by the removal (`licensing.csv` is outside both); `artifact.digest` moved,
because the rows reach `sources.parquet`.

Two of our own skills disagreed about this and the run that produced `run-sirt6-a2` reported the
contradiction. `module-tables/references/licensing.md` owns the rule; `module-start` carried a "must
cover … including PubMed" claim whose premise — that the row is the only record of a literature
source's terms — is false, and it has been struck.

## What the gates said

Recorded here because a green build is not evidence a module is right, and the warnings are the
interesting output.

- `validate_module(strict=True)` — **valid**, zero findings as it now stands. At the time of the
  original run it reported two warnings, both since resolved: no closure (closed afterwards) and the
  `cc by-nc-nd` quote note, which the *compile* still reports and which is recorded below.

  Historical note on the two warnings that run saw:
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

---

# This is the benchmark reference, and it is a merge of two runs

Adjudicated 2026-08-31 from `run-sirt6-a` and `run-sirt6-b`, given byte-identical prompts and the
same paper. Both closed clean and they disagreed on the cells that matter, so the reference takes the
better half of each rather than crowning a winner. Closed at authored bytes `sha256:fdc55e99…`,
content signature `sha256:cdeebbf4…`, compiled `artifact.digest sha256:7610f0fa…`.

**It compiles with two warnings, not zero, and this file used to say zero.** Both are documented
below and neither is a defect in the module: the `cc by-nc-nd` quote note, which is the module's real
licence constraint and is why `license:` is what it is, and the licence-disagreement note, which is
fired by the machine-written ClinGen row and is itself partly misreported by the compiler (filed as
`S79` — it prints only the sources that mismatch, so a declaration matching one of two annotation-layer
rows reads as matching none). A reference described as warning-free would have been a reference nobody
could reproduce.

## What came from where, and why

**Base: `run-sirt6-a`** — its studies, licensing, README argument and fact-pass sidecars. It did three
things the sibling did not: fetched the *primary* longevity source (PMID 28399814) unprompted after
noticing the assigned paper's longevity claim was a replication rather than its own; caught the
paper contradicting itself (`stop-gained` in prose, *intron variant* in two tables) and asserted **no
molecular consequence in any cell**; and left `weight` empty, which is what `module-weights` says of a
cell only a pilot settles.

**`C/T` row: `run-sirt6-a` verbatim.** It carries `flags: pleiotropic` and a `negatives` entry
recording the counter-direction — the T allele is depleted at advanced age yet *enriched* among
robust participants, which the paper itself raises as possible antagonistic pleiotropy. The sibling
dropped that entirely. `stat_significance: suggestive` over the sibling's `not_significant`: both
studies land at p ≈ 0.073–0.074, which is the band the `suggestive` value exists to name — a
vocabulary offering `significant | suggestive | not_significant | unknown` and never using the middle
term for a p of 0.07 would not need it.

**`C/C` and `T/T` rows: `run-sirt6-b`.** This reverses `run-sirt6-a`'s refusal, and the reason it is
safe to reverse is that the sibling's rows do not make the claim `run-sirt6-a` objected to.
`run-sirt6-a` withheld `C/C` because the paper's remark that CC "could have a positive effect on the
lifespan" is an inference from the same 2×2 table, so authoring it would double-count one test — a
correct objection to a **protective** call. The sibling's `C/C` is `direction: neutral` and says only
that the minor allele is absent and this is the common genotype, which double-counts nothing. `T/T`
is `direction: unknown`, `stat_significance: unknown`, and says outright that neither cohort observed
it.

The gain is real: a `C/C` or `T/T` carrier now receives an annotation where `run-sirt6-a` alone gave
them nothing. `module-consumer` is explicit that absence is not a reference call, so a module that
answers only the heterozygote leaves the common case unanswered.

**Weights: dropped from the sibling's rows.** `run-sirt6-b` authored −0.2 / 0.0 on a non-significant
trend. No tool fills `weight` and only a pilot settles it; a weight asserted on p ≈ 0.07 is exactly
the judgement that needs a human, so the merged rows carry none and `weighting:` says so.

## The one warning that is a known defect, kept rather than hand-fixed

`licensing.csv` carries a `clingen / CC0-1.0` row written by the dosage pass, which covered nothing
(`dosage: missing: [SIRT6]`). It is filed upstream as `S77`. It is **left in place on purpose**: it is
machine-written, it would return on the next pass, and hand-editing licence rows is a worse habit than
the defect. A future run of this paper will carry it too until `S77` lands, so the reference stays
comparable.
