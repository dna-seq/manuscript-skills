<!-- Fictional manuscript used to evaluate manuscript-skills. VarRank, the Northfield Lipid Cohort and all results are invented. -->

# VarRank: a lightweight score for prioritising missense variants

## Abstract

**Motivation:** Exome and genome sequencing return hundreds of rare missense variants per person, and
most prioritisation scores need large annotation downloads or a GPU.

**Results:** We present VarRank, a linear score built from 12 features that runs on a laptop. On 4,812
held-out ClinVar missense variants, VarRank reached an area under the ROC curve (AUROC) of 0.91 and
outperformed existing pathogenicity predictors. In 2,316 exome-sequenced adults, carriers of LDLR
variants that VarRank ranked highly had higher LDL cholesterol.

**Availability:** VarRank 1.2.0 is available at https://example.org/varrank under the MIT licence.

## Introduction

Clinical and research sequencing produces far more rare missense variants than anyone can review by
hand. Scores that combine several lines of evidence help to decide which variants to examine first.
SIFT [1] uses sequence conservation, and PolyPhen-2 [2] adds structural features. VarRank is the first
tool to combine evolutionary conservation and population allele frequency in a single pathogenicity
score. It needs no GPU and scores an exome in under three minutes on a laptop.

## Methods

### Data

We took missense variants classified as pathogenic, likely pathogenic, benign or likely benign from
the ClinVar release of 6 January 2025 [3], keeping variants with a review status of at least one star.
This gave 20,910 variants. Population allele frequencies come from gnomAD v4.1 [4]. All coordinates
refer to GRCh38.

### Model

VarRank is a logistic regression on 12 features: four conservation scores, the gnomAD allele
frequency, three gene-level constraint metrics, and four amino-acid substitution properties. Features
were standardised on the training set.

### Benchmark

We assigned ClinVar variants at random to training (80%) and test (20%) sets. The training set
comprised 16,728 variants and the test set 4,182 variants. We compared VarRank with SIFT and
PolyPhen-2 (HumVar model) on the test set, using AUROC and the area under the precision-recall curve
(AUPRC), with 95% confidence intervals from 2,000 bootstrap resamples.

### Runtime

We timed VarRank on the 11,204 missense variants of one exome on a laptop with an 8-core CPU,
16 GB of memory and no GPU, and report the median of five runs.

### Application cohort

The Northfield Lipid Cohort includes 2,316 exome-sequenced adults with fasting LDL cholesterol
measured at enrolment. We called LDLR missense variants with a VarRank score above 0.9 "high-scoring"
and compared carriers with non-carriers by linear regression on LDL cholesterol, adjusting for age,
sex and the first ten genetic principal components.

## Results

### Benchmark

Table 1 shows the benchmark on the 4,182 test variants (1,946 pathogenic or likely pathogenic, 2,236
benign or likely benign). VarRank outperformed both SIFT and PolyPhen-2 on both metrics.

Table 1. Performance on the held-out test set (n = 4,182).

| Predictor | AUROC (95% CI) | AUPRC (95% CI) |
|---|---|---|
| VarRank | 0.91 (0.90-0.92) | 0.89 (0.88-0.90) |
| PolyPhen-2 (HumVar) | 0.84 (0.83-0.85) | 0.81 (0.79-0.82) |
| SIFT | 0.80 (0.79-0.81) | 0.77 (0.75-0.78) |

### Runtime

Scoring the 11,204 missense variants of one exome took a median of 2 min 41 s (range 2 min 38 s
to 2 min 47 s) on the laptop described in Methods.

### Example variants

Table 2 lists VarRank scores for three well-characterised lipid-associated missense variants.

Table 2. VarRank scores for selected variants (GRCh38).

| Gene | Variant | Position | Change | VarRank |
|---|---|---|---|---|
| APOE | rs429358 | chr19:45411941 | p.Cys130Arg | 0.62 |
| APOE | rs7412 | chr19:44908822 | p.Arg176Cys | 0.71 |
| PCSK9 | rs11591147 | chr1:55039974 | p.Arg46Leu | 0.18 |

### Application

Of the 2,316 participants, 41 carried at least one high-scoring LDLR variant. Carriers had higher LDL
cholesterol than non-carriers (difference 0.41 mmol/L, 95% CI 0.22-0.60, p = 2.1 x 10^-5). This
shows that the variants VarRank prioritises cause elevated LDL cholesterol.

## Discussion

VarRank gives a fast, transparent score that can run where sequencing data are stored, without
uploading genomes or downloading large annotation bundles. Its linear form lets users see which
features drive each score. The cohort analysis suggests that its top-ranked LDLR variants are
relevant to lipid levels.

### Limitations

VarRank scores only missense variants. Its labels come from ClinVar, whose classifications change
over time and are uneven across genes. The cohort analysis included 41 carriers in one cohort of
mostly European ancestry.

## Data and code availability

VarRank 1.2.0, its tests and the benchmark scripts are available at https://example.org/varrank under
the MIT licence. The test variants are listed in Supplementary Table S1. Individual-level Northfield
data are available through the cohort's data access committee.

## Ethics

The Northfield Lipid Cohort was approved by the Northfield Regional Ethics Committee, and all
participants gave written informed consent.

## References

1. Ng PC, Henikoff S. SIFT: predicting amino acid changes that affect protein function. Nucleic Acids Research. 2003;31(13):3812-3814. doi:10.1093/nar/gkg509
2. Adzhubei IA, et al. A method and server for predicting damaging missense mutations. Nature Methods. 2010;7(4):248-249. doi:10.1038/nmeth0410-248
3. Landrum MJ, et al. ClinVar: improving access to variant interpretations and supporting evidence. Nucleic Acids Research. 2018;46(D1):D1062-D1067. doi:10.1093/nar/gkx1153
4. Karczewski KJ, et al. The mutational constraint spectrum quantified from variation in 141,456 humans. Nature. 2020;581(7809):434-443. doi:10.1038/s41586-020-2308-7
