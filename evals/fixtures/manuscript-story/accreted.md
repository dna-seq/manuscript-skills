# Hearthread: an Open-Source Platform for Personal Genome Annotation

**Authors:** R. Ilves, M. Okafor, J. Brandt

## Abstract

**Motivation:** As genome sequencing becomes increasingly available, personal genome analysis requires
tools that make published variant associations accessible.

**Results:** Hearthread is an open-source platform for variant annotation with a web interface.
Annotation sets are versioned tables added without code. Annotation runs locally on downloaded reference
data. The platform is meant for research and education, is not a clinical tool and does not establish
clinical validity.

**Availability and implementation:** Hearthread is open source (MIT) and runs on Linux, macOS and Windows.

## 1. Introduction

By 2025, the cost of sequencing a human genome had fallen to a few hundred dollars for consumables and a
few thousand dollars overall (Ortiz et al., 2024; Hale et al., 2025). Several companies offer
direct-to-consumer sequencing (Ruiz et al., 2021). Researchers and individuals who receive variant files
often lack an accessible way to annotate them without specialised expertise (Chen et al., 2019).
Hearthread is not a clinical tool.

Hearthread is a ground-up rewrite of an earlier tool. It reads variant files with a columnar engine, joins
them with annotation sets and writes reports. Annotation sets are tables discovered from configured
sources. This paper presents the platform, its annotation sets and its benchmarks; it is not a clinical
tool and makes no clinical claims.

## 2. Methods

Hearthread normalises the variant file once, keeps it as a columnar table and joins it with each selected
annotation set by position and allele. An annotation set is a table of variants, genotypes, effects and
citations with a one-page description; sets are discovered from any web address or folder the user lists.
Reference data are downloaded once and cached.

## 3. Results

We benchmarked Hearthread against the previous tool on one workstation. The benchmark used version 0.3.1
of Hearthread for the first series and version 0.3.2 for the second, because version 0.3.1 did not record
peak memory; the second series was run on a different day with the desktop in light use. Each series
was preceded by one warm-up run, which was dropped. On one author's published genome (5.1 million
variants), annotation with all eight default sets took a median of 31 s (range 29 to 48 s) against
5,712 s for the previous tool, an approximately 184-fold speedup, although this ratio applies only to this
configuration and may not hold on other machines. The benchmark used SSD storage; it does not establish
performance on a laptop or on rotational disks, nor with other annotation sets. Peak memory was 2,105 MB,
albeit measured only for the second series. A rerun with version 0.3.3, which changed the allele check,
gave a median of 32 s; the earlier runs are kept in Table 1 because they used the fixed list of sets.

**Figure 1.** An earlier version of the interface. This screenshot does not show the current report, its
labels are not those of the current version, and it does not represent results reported in this paper.

**Table 1.** Annotation time on one author's published genome (median of 10 runs; first series).

| Tool | Version | Median, s |
|---|---|---|
| Hearthread | 0.3.1 | 31 |
| Previous tool | 2.1.0 | 5,712 |

## 4. Discussion

Variant annotation tools are based on statistical associations; most reported variants have no
established mechanism, effects shrink in replication, and the platform is not a clinical tool. Local
execution reduces the need to upload a genome, but it does not by itself establish regulatory compliance.

### 4.1 Limitations

The speed was measured on one genome and one computer. The report states what published studies found;
it is not a diagnosis, and most effects are small. Hearthread reads GRCh38 files only.

## 5. Conclusion

Hearthread integrates local variant annotation and inspectable reports with versioned annotation sets.
The benchmarks, albeit on one genome, show faster annotation than the previous tool, although evaluation
across more genomes remains necessary, and the platform does not establish clinical validity.

## References

Chen, L., et al. (2019). VariantKit: a toolkit for variant interpretation. *Journal of Tools*, 4, 1-9.

Hale, D., et al. (2025). The full cost of a genome. *Health Economics of Genomics*, 3, 10-18.

Ortiz, F., et al. (2024). Sequencing consumables in 2024. *Sequencing Today*, 8, 2-5.

Ruiz, P., et al. (2021). What consumer genomics reports leave out. *Genetics and Society*, 12, 33-41.
