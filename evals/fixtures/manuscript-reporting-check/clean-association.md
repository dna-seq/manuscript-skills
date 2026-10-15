<!-- Evaluation fixture for manuscript-reporting-check: a fictional study. The cohort, authors, results and
accessions other than the public dbGaP study are invented for testing and describe no real data. -->

# Common variants in urate transporter genes and serum urate in the Northfield Ageing Cohort

A. Author, B. Author, C. Author

## Abstract

**Background.** Serum urate is highly heritable, and variants in renal and intestinal urate transporters
explain part of its variation. We examined candidate variants in four transporter genes in a cohort of
older adults.

**Methods.** In a cross-sectional analysis of 2,418 adults aged 60 to 85 years from the Northfield Ageing
Cohort, we tested 48 candidate single-nucleotide polymorphisms (SNPs) in *SLC2A9*, *ABCG2*, *SLC17A1* and
*SLC22A12* for association with serum urate using linear regression under an additive model. In 96
participants we measured whole-blood gene expression by RNA sequencing.

**Results.** Two SNPs were associated with serum urate after Bonferroni correction. The strongest was
rs2231142 in *ABCG2* (beta = 0.31 mg/dL per T allele, 95% CI 0.17 to 0.45, P = 2.1 × 10^-5).

**Conclusions.** Common transporter variants are associated with serum urate in older adults.

## Introduction

Raised serum urate precedes gout and is associated with cardiovascular and kidney disease. Genome-wide
studies have located most of its common-variant heritability in a few transporter genes, led by *SLC2A9*
and *ABCG2*. Whether these associations hold with similar effect sizes in older adults, whose kidney
function varies widely, is less clear. We tested candidate variants in four transporter genes in a
population cohort aged 60 and over.

## Methods

### Participants

The Northfield Ageing Cohort recruited 2,603 community-dwelling adults aged 60 to 85 years between 2019 and
2021 from primary-care registers in one region. Exclusion criteria were dialysis, a kidney transplant and
current urate-lowering treatment. Self-reported ancestry was European for 71%, South Asian for 18% and
other for 11% of participants. Serum urate was measured by the uricase method on fasting samples. Body mass
index (BMI), estimated glomerular filtration rate (eGFR, CKD-EPI 2021) and diuretic use were recorded at the
same visit.

### Genotyping

DNA was extracted from whole blood and genotyped on the Illumina Infinium Global Screening Array v3.0 at
the Northfield Genomics Facility in two batches. Genotypes were called with GenomeStudio 2.0 (GenCall
threshold 0.15). Of 2,449 samples genotyped, 31 were excluded for a call rate below 97%, leaving 2,418.
SNPs with a call rate below 98% or a Hardy-Weinberg equilibrium P value below 1 × 10^-6 were excluded; all
48 candidate SNPs passed. The 48 SNPs were chosen from published urate genome-wide studies (Supplementary
Table S1).

### RNA sequencing

Whole-blood RNA from 96 participants who consented to open data release was sequenced (Illumina NovaSeq
6000, 2 × 100 bp, 30 million read pairs per sample). Reads were aligned to GRCh38 with STAR 2.7.10a and
counted with featureCounts 2.0.3 against GENCODE v44.

### Statistical analysis

Serum urate was regressed on allele count for each SNP, adjusting for age, sex, BMI, eGFR and diuretic
use. To control the family-wise error rate across the 48 SNPs we used a Bonferroni-corrected threshold
of P < 1.04 × 10^-3 (0.05/48) and report Bonferroni-adjusted P values. Expression of *ABCG2* by
rs2231142 genotype was compared with a linear model on log2 counts per million, adjusted for age and sex.
To address population stratification, all association models also included the first ten principal
components of the genotype matrix, computed in PLINK from 48,212 linkage-disequilibrium-pruned autosomal
SNPs; we repeated the analysis separately in participants of European and of South Asian self-reported
ancestry (Supplementary Table S3). No participants were related closer than third degree (KING
kinship below 0.044). Analyses used PLINK v1.90b6.21 and R 4.3.1. Values are mean ± standard deviation
(SD) unless stated.

### Replication

Lead SNPs were examined in Framingham Heart Study participants (dbGaP study phs000007.v35.p16), obtained
through dbGaP authorized access.

## Results

Participants had a mean age of 71.4 ± 6.2 years; 54% were women. Mean serum urate was 5.6 ± 1.4 mg/dL.

Two of the 48 SNPs passed the Bonferroni-corrected threshold; three more had nominal P values below 0.05
that did not survive correction (Table 1; all 48 in Supplementary Table S2). Effect estimates were
similar in the European and South Asian ancestry groups (Supplementary Table S3).

Table 1. SNPs with nominal P < 0.05 for serum urate (n = 2,418).

| SNP | Gene | Effect allele | Beta (mg/dL) | 95% CI | P | Bonferroni-adjusted P |
|---|---|---|---|---|---|---|
| rs2231142 | ABCG2 | T | 0.31 | 0.17 to 0.45 | 2.1 × 10^-5 | 1.0 × 10^-3 |
| rs16890979 | SLC2A9 | C | 0.22 | 0.10 to 0.34 | 4.0 × 10^-4 | 0.019 |
| rs1165205 | SLC17A1 | A | 0.12 | 0.03 to 0.21 | 0.012 | 0.58 |
| rs505802 | SLC22A12 | C | 0.10 | 0.01 to 0.19 | 0.027 | 1.00 |
| rs3775948 | SLC2A9 | G | 0.09 | 0.00 to 0.18 | 0.041 | 1.00 |

In the 96 participants with RNA sequencing, *ABCG2* expression did not differ by rs2231142 genotype
(difference per T allele −0.08 log2 CPM, 95% CI −0.31 to 0.15). In the Framingham data the direction of
effect was the same for both SNPs that passed correction.

## Discussion

Two transporter variants were associated with serum urate in older adults after correction for 48
tests; three further nominal associations did not survive correction and need replication. The *ABCG2*
and *SLC2A9* signals agree with published genome-wide studies. The absence of an expression effect for
rs2231142 is consistent with its known effect on protein function rather than on transcription.
Limitations are the cross-sectional design, a single region and modest power for the RNA-sequencing
comparison.

## Data availability

Whole-blood RNA-sequencing reads and gene counts have been deposited in the Gene Expression Omnibus under
accession GSE158904. Individual-level genotype and phenotype data cannot be made public because
participants consented to controlled access only. They are available to bona fide researchers through
the Northfield Ageing Cohort Data Access Committee (dac@northfield-cohort.example) under a data access
agreement. Association results for all 48 SNPs are in Supplementary Table S2.

## Code availability

Analysis scripts are available at https://github.com/northfield-genetics/urate-assoc (release v1.2.0,
the version used for every result here), archived at Zenodo (https://doi.org/10.5281/zenodo.1234567).

## Ethics

The study was approved by the Northfield Research Ethics Committee (reference NREC-2018-044). All
participants gave written informed consent.

## Competing interests

None declared.

## Funding

Northfield Health Research Fund (grant NHRF-2019-12).

## References

1. Example A, Example B. Genome-wide association analyses of serum urate. Example Journal. 2020.
2. Example C. Urate transporters in health and disease. Example Reviews. 2019.
