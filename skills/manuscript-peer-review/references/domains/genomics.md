# Domain module: genomics

Questions a genomics or statistical-genetics referee asks. They are prompts for the seats that load this
module, not a checklist: skip what does not apply, and raise a concern only when it passes the
claim-consequence gate.

## Load it when

- `study.domains` includes `genomics`, `genetics` or `statistical-genetics`; or the design is
  `genetic-association`, `polygenic-score`, `mendelian-randomization` or `omics-profiling`;
- or the paper works with variants, genotypes, VCF/BAM/CRAM files, rsIDs, HGVS names, genome builds
  (GRCh37/hg19, GRCh38/hg38, T2T-CHM13), GWAS or QTL summary statistics, gnomAD, ClinVar, sequencing
  cohorts, or expression and other genome-scale profiles.

## Do not load it when

- a gene, variant or sequencing method is mentioned only in passing (background, a cited example);
- the paper is software that merely reads a genomic file format and makes no claim about the biology or
  the data: use [software-and-methods.md](software-and-methods.md) instead;
- for microbial or non-human genomes, load only the build, reference-version and batch questions; the
  human identifier and ancestry questions do not apply.

Record in the output why the module was loaded.

## Genome build and coordinates

- Is one build stated, and used consistently in the text, tables, figures and supplementary files? A
  seat can spot-check a few positions it can see: an rsID's position differs between builds, and a
  well-known variant at its other-build position is a reportable inconsistency (quote both places).
- If data from different builds were combined, is the liftover described (tool, chain file, how many
  variants failed or moved chromosome)?
- Are coordinates 0-based or 1-based where it matters (BED against VCF)? Chromosome naming (`chr1`
  against `1`, `chrM` against `MT`) can silently drop data in joins.
- Are positions of indels anchored as the stated convention requires, so that they can be matched?

## Identifiers

- rsIDs: merged or withdrawn identifiers, and claims that depend on an rsID mapping to one position.
- HGVS: transcript given with its version (`NM_000527.5`, not `NM_000527`), syntax that parses, protein
  and coding changes that agree.
- Gene symbols: current HGNC symbols, not aliases or previous symbols that point to another gene.
- Strand and allele orientation, especially for palindromic (A/T, C/G) SNPs when summary statistics are
  combined.

Lookups of public identifiers (dbSNP, HGNC, Ensembl) are allowed with the authors' agreement to go
online; in invited-referee mode only the identifier leaves the session, never manuscript text.

## Reference and annotation versions

- Are the versions and dates of gnomAD, ClinVar, Ensembl/VEP, GENCODE, dbSNP and any gene panel stated?
  A ClinVar release date matters because classifications change.
- Do labels and features come from sources that could share information (a predictor score that was
  itself evidence for a ClinVar classification used as a label)?

## Association testing

- Genome-wide significance: the threshold used (5 x 10^-8 or a justified alternative) and the number of
  tests actually made, including traits, models and subgroups.
- Multiple testing for candidate or gene-based analyses: which correction, over which family of tests.
- Effect sizes from the discovery sample are inflated (winner's curse); is there replication, or are
  discovery estimates presented as final?
- Conditional and fine-mapping claims: is a "causal variant" a statistical credible-set member or
  experimentally supported?

## Ancestry and population structure

- How was stratification handled (principal components, mixed models, genomic control, LD score
  intercept)? Is relatedness accounted for?
- What is the ancestry composition of training, discovery and evaluation sets? Do claims extend to
  populations that were not studied (polygenic scores transfer poorly across ancestries)?

## Sample overlap

- Between discovery and replication samples; between the GWAS used to build a polygenic score and the
  cohort in which it is evaluated; between exposure and outcome samples in Mendelian randomisation.
- Between the training data of compared predictors and the benchmark's test set.

## Leakage in variant-effect benchmarks

- A random split by variant puts variants from the same gene, or the same position, on both sides;
  gene-level features then let a model score genes rather than variants. Is the split by gene, protein
  family or time?
- Circularity: predictors trained on ClinVar or HGMD labels evaluated on overlapping labels; tools whose
  scores were used as evidence for the labels they are tested on. Grimm et al. describe both types
  (Human Mutation 2015, doi:10.1002/humu.22768).
- Are the compared tools given the same inputs and versions, and are their published thresholds used
  rather than thresholds tuned on the test set?

## Batch effects and data generation

- Are sequencing centre, platform, capture kit, read length, calling pipeline or processing date
  confounded with case status, label or group?
- Were cases and controls called jointly or separately? Do coverage differences explain variant
  counts?
- For expression and other profiles: is batch separable from condition in the design, and was it
  modelled rather than removed after looking at the outcome?

## Variant interpretation

- Are "pathogenic", "damaging" and "deleterious" used for predicted effects, ACMG/AMP classifications or
  observed phenotypes? Each supports a different claim.
- Hard-to-map regions, segmental duplications and pseudogenes (for example around CYP2D6, GBA1, PMS2):
  are calls there validated, or excluded and said so?
