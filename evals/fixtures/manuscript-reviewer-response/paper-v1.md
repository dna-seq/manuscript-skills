# VarLens: fast annotation of personal genomes on a laptop

## Abstract

VarLens annotates a 30x human genome in under 11 minutes on a laptop with 16 GB of memory. On two public
genomes it reproduced 99.2% of the annotations of its previous release. VarLens may help researchers who
cannot use a compute cluster.

## Introduction

Annotating a personal genome usually requires a server or a cloud account (Jones et al., 2019). Researchers
without such resources depend on hosted services, which require uploading the genome. VarLens runs on a
laptop and keeps the data on the user's machine.

## Methods

### Implementation

VarLens joins a normalised VCF against module tables stored as Parquet files and writes one annotated
table per module.

### Benchmark

We annotated two public genomes from the Genome in a Bottle consortium, HG002 and HG005, on a laptop with
16 GB of memory and 8 cores. Each run was repeated 3 times; we report the median wall-clock time.

### Demonstration genome

The example report uses the genome of one author.

## Results

### Performance

The median runtime was 9.8 minutes for HG002 and 10.4 minutes for HG005 (Table 1). Peak memory was 6.1 GB.

Table 1. Runtime and peak memory.

| Genome | Median runtime (min) | Peak memory (GB) |
|---|---|---|
| HG002 | 9.8 | 6.1 |
| HG005 | 10.4 | 5.9 |

### Concordance

Against the previous release (v0.9), VarLens reproduced 99.2% of annotations. The discordant annotations
were mostly indels.

## Discussion

VarLens makes genome annotation feasible on a laptop. The concordance with the previous release suggests
that the rewrite did not change results. A limitation is that we tested only two genomes.

## Data availability

HG002 and HG005 are available from the Genome in a Bottle consortium. The author's genome is available at
https://example.org/genome.

## References

Smith, J., Lee, K. (2020). Cloud pipelines for clinical genome annotation. Journal of Examples 12, 1-10.
