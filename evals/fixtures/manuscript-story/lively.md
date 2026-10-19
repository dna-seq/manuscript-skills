# Hearthread: reading a personal genome on your own computer

**Authors:** R. Ilves, M. Okafor, J. Brandt

## Abstract

**Motivation:** People who receive their genome as a variant file must either upload it to a company that
will not say how its report was made, or learn a bioinformatics toolkit. Neither lets them see why a
result appears.

**Results:** Hearthread annotates a whole-genome variant file on the user's own computer in about half a
minute and shows, for every matched variant, the study and the rule behind it. Annotation sets are tables
anyone can publish without writing code.

**Availability and implementation:** Hearthread is open source (MIT) and runs on Linux, macOS and Windows.

## 1. Introduction

A person who sequences their genome receives a file with four to five million variants and no way to read
it. Consumer services will read it for them, but only after the file is uploaded, and their reports name
a result without the evidence or the rule that produced it (Ruiz et al., 2021). Research tools such as
VariantKit show everything but expect a command line and an afternoon of setup (Chen et al., 2019).

We wanted a tool a curious biologist could run on a laptop, that never sends the genome anywhere, and that
shows its working. Hearthread does three things: it reads the variant file locally, it joins it with
annotation sets, and it writes a report in which every line names its source. Its central idea is that
annotation sets are data, not code: a table and a short description, which anyone can publish and anyone
can audit.

## 2. Methods

Hearthread normalises the variant file once, keeps it as a columnar table and joins it with each selected
annotation set by position and allele. An annotation set is a table of variants, genotypes, effects and
citations with a one-page description; sets are discovered from any web address or folder the user lists.
Nothing is uploaded: reference data are downloaded once and cached.

## 3. Results

**A whole genome is annotated in about half a minute.** On one author's published genome (5.1 million
variants), annotation with all eight default sets took a median of 31 s on a desktop computer, against
about 95 minutes for the tool Hearthread replaced (Table 1).

**Every line of the report shows its working.** Figure 1 shows the report for that genome: for a variant
the person carries, the report gives the genotype, the reported effect, the study and the rule that
placed it there. A reader can follow any result back to its source in two clicks.

**Figure 1.** The report for one author's published genome: the lipid-metabolism set, with the carried
genotype, the reported effect and the study behind each line.

**Table 1.** Annotation time on one author's published genome (median of 10 runs).

| Tool | Median, s |
|---|---|
| Hearthread | 31 |
| Previous tool | 5,712 |

## 4. Discussion

Hearthread moves the reading of a genome to the person who owns it. Because annotation sets are tables,
a new study can reach users the week it is published, and anyone can check what a set claims.

### 4.1 Limitations

The speed was measured on one genome and one computer. The report states what published studies found;
it is not a diagnosis, and most effects are small. Hearthread reads GRCh38 files only.

## 5. Conclusion

Anyone with a variant file can now read it on their own computer and see where every result comes from.
Hearthread is ready to install, and we invite researchers to publish annotation sets for it.

## References

Chen, L., et al. (2019). VariantKit: a toolkit for variant interpretation. *Journal of Tools*, 4, 1-9.

Ruiz, P., et al. (2021). What consumer genomics reports leave out. *Genetics and Society*, 12, 33-41.
