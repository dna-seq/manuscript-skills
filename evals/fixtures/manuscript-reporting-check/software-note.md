<!-- Evaluation fixture for manuscript-reporting-check: a fictional software tool. The tool, repository,
authors and timings are invented for testing. -->

# varmerge: fast merging of per-sample VCF annotations

D. Author, E. Author

## Abstract

**Summary.** Annotation pipelines often write one annotated VCF per sample, and merging them into a
cohort table is slow with general-purpose tools. varmerge merges per-sample annotations into a single
Parquet table with one row per variant and sample, streaming the input so that memory stays constant.

**Availability and Implementation.** varmerge is written in Rust and is available at
https://github.com/varmerge-dev/varmerge under the MIT licence, with binaries for Linux and macOS.

**Contact.** d.author@example.org

**Supplementary information.** Supplementary data are available online.

## Introduction

Cohort studies annotate each sample's VCF with tools such as Ensembl VEP and then need one table for
analysis. Merging annotated VCFs with bcftools and converting the result is slow and memory-hungry for
thousands of samples. varmerge does the merge in one streaming pass and writes Parquet directly.

## Implementation

varmerge reads bgzipped, tabix-indexed VCFs, aligns records by position and allele, and writes
annotation fields declared in a TOML configuration to Parquet with a fixed schema. It runs on one machine
and needs no database. Installation:

```
conda install -c bioconda varmerge
```

The repository contains test data (ten chromosome 22 VCFs) and a script that reproduces each figure.

## Results

We merged VEP-annotated chromosome 22 VCFs for the 2,504 samples of the 1000 Genomes Project Phase 3
release on a laptop with 16 GB of memory. varmerge took 6.1 minutes and used at most 1.2 GB of memory;
bcftools merge 1.17 followed by conversion to Parquet took 41.3 minutes and 9.8 GB (Supplementary Table
S1). Outputs agreed on all 1,066,557 variant records.

## Data availability

The benchmark used the 1000 Genomes Project Phase 3 VCF files
(https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/). The test data are in the repository.

## Funding

None.

## Conflict of interest

None declared.

## References

1. Example F. The 1000 Genomes Project Phase 3. Example Journal. 2015.
