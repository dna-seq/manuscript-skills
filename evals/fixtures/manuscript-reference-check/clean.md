# PGSAudit: reporting the ancestry behind a polygenic score

## Abstract

Polygenic scores are still trained mostly on people of European ancestry.
In the first decade of polygenic scoring (2008–2017), 67% of studies included only participants of European ancestry [1].
As of December 2020, the PGS Catalog contained 657 polygenic scores curated from 119 publications [2].
We present PGSAudit, a command-line tool that reports the ancestry composition of the samples behind each score in a
scoring file and warns when a score is applied to a sample of another ancestry.

## Introduction

Ancestry imbalance in polygenic score research is well documented.
A further 19% of studies in that decade included only East Asian ancestry participants [1].
Only 3.8% of studies from the same period were among cohorts of African, Hispanic or Indigenous peoples [1].
The predictive performance of European ancestry-derived polygenic scores was lower in non-European ancestry samples, including African ancestry samples [1].

## Discussion

PGSAudit makes the ancestry of the training samples visible at the point where a score is used.
Polygenic risk profiling has been proposed for stratifying screening, for example in breast cancer and coronary artery disease [3].
Reporting the ancestry behind each score is a precondition for any such use.

## Data availability

The scoring files used in the examples are public in the PGS Catalog.

## Code availability

https://github.com/example/pgsaudit, archived at Zenodo (10.5281/zenodo.0000000).

## Competing interests

None.

## Funding

None.

## Author contributions

A.B. wrote the software and the paper.

## References

1. Duncan L, Shen H, Gelaye B, Meijsen J, Ressler K, Feldman M, Peterson R, Domingue B. Analysis of polygenic risk score usage and performance in diverse human populations. Nat Commun. 2019;10:3328. doi:10.1038/s41467-019-11112-0
2. Lambert SA, Gil L, Jupp S, Ritchie SC, Xu Y, Buniello A, McMahon A, Abraham G, Chapman M, Parkinson H, Danesh J, MacArthur JAL, Inouye M. The Polygenic Score Catalog as an open database for reproducibility and systematic evaluation. Nat Genet. 2021;53(4):420-425. doi:10.1038/s41588-021-00783-5
3. Torkamani A, Wineinger NE, Topol EJ. The personal and clinical utility of polygenic risk scores. Nat Rev Genet. 2018;19(9):581-590. doi:10.1038/s41576-018-0018-x
