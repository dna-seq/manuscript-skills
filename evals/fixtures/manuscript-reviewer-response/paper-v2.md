# VarLens: fast annotation of personal genomes on a laptop

## Abstract

VarLens annotates a 30x human genome in under 11 minutes on a laptop with 16 GB of memory and 8 cores. On
two public short-read genomes it reproduced 99.2% of the annotations of its previous release, and its most
severe consequence calls agreed with the Ensembl Variant Effect Predictor (VEP) for 97.9% of variants. A
long-read genome took 12.6 minutes. VarLens may help researchers who cannot use a compute cluster.

## Introduction

Annotating a personal genome usually requires a server or a cloud account (Jones et al., 2019). Researchers
without such resources depend on hosted services, which require uploading the genome. VarLens runs on a
laptop and keeps the data on the user's machine.

## Methods

### Implementation

VarLens joins a normalised VCF against module tables stored as Parquet files and writes one annotated
table per module. The benchmark used module tables release 2026.03.

### Benchmark

We annotated two public short-read genomes from the Genome in a Bottle consortium, HG002 and HG005, and the
public PacBio HiFi callset of HG002, on a laptop with 16 GB of memory and 8 cores. Each run was repeated 3
times; we report the median and the range of wall-clock time. Peak memory is the maximum resident set size
of the process, which includes the module tables loaded into memory.

To compare VarLens with an established annotator, we ran VEP release 111 on the same input files on the same
laptop and compared the most severe consequence that each tool assigned to each variant.

To characterise the annotations that differ from the previous release, we compared the discordant indels
with the Genome in a Bottle v4.2.1 benchmark calls for HG002.

### Demonstration genome

The example report uses the genome of one author (A.B.), who released it publicly under a CC0 licence
before this study (Data availability) and agreed to its use in this paper. No other individuals were
recruited, and no clinical results were returned to anyone.

## Results

### Performance

The median runtime was 9.8 minutes for HG002 (range 9.6 to 10.1) and 10.4 minutes for HG005 (range 10.2 to
10.9). The HiFi callset of HG002 took 12.6 minutes (range 12.3 to 12.8). Peak memory, including the module
tables, was 6.1 GB for HG002 (Table 1).

Table 1. Runtime and peak memory over 3 runs per genome.

| Genome | Platform | Median runtime (min) | Range (min) | Peak memory (GB) |
|---|---|---|---|---|
| HG002 | Illumina | 9.8 | 9.6-10.1 | 6.1 |
| HG005 | Illumina | 10.4 | 10.2-10.9 | 5.9 |
| HG002 | PacBio HiFi | 12.6 | 12.3-12.8 | 6.4 |

### Comparison with VEP

On the same laptop, VEP took 41.2 minutes for HG002 and 44.8 minutes for HG005 (Table 2). The most severe
consequence agreed for 97.9% of variants. Most disagreements involved splice-region variants, where the two
tools use different window definitions.

Table 2. VarLens and VEP on the same genomes.

| Genome | VarLens runtime (min) | VEP runtime (min) | Consequence agreement (%) |
|---|---|---|---|
| HG002 | 9.8 | 41.2 | 97.9 |
| HG005 | 10.4 | 44.8 | 97.9 |

### Concordance

Against the previous release (v0.9), VarLens reproduced 99.2% of annotations. Of the 0.8% that differed,
71% were indels and 29% were multi-allelic sites (Table 3). Two discordant variants were classified as
pathogenic or likely pathogenic in ClinVar; in both, the new release corrected the representation of an
indel. All discordant indels in the Genome in a Bottle benchmark regions matched the benchmark
representation in the new release.

Table 3. Annotations that differ from the previous release, by variant class.

| Variant class | Share of discordant annotations (%) |
|---|---|
| Indel | 71 |
| Multi-allelic site | 29 |

## Discussion

VarLens makes genome annotation feasible on a laptop. Its annotations agreed with the previous release for
99.2% of variants, and the differences were concentrated in indels and multi-allelic sites. We tested three
callsets from two individuals, and the discordant variants were compared with benchmark calls rather than
validated experimentally.

## Code availability

The source code is available at https://example.org/varlens under the MIT licence. The version evaluated
here is archived as release v1.0.0 at https://example.org/varlens/releases/v1.0.0.

## Data availability

HG002 and HG005 are available from the Genome in a Bottle consortium. The author's genome is available at
https://example.org/genome under CC0.

## References

Smith, J., Lee, K. (2020). Cloud pipelines for clinical genome annotation. Journal of Examples 12, 1-10.
