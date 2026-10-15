# PGSAudit: reporting the ancestry behind a polygenic score

## Abstract

Polygenic scores are still trained mostly on people of European ancestry.
In the first decade of polygenic scoring (2008–2017), 67% of studies included only participants of European ancestry [1].
When it was first released, the PGS Catalog held 192 published polygenic scores from 78 publications [4].
We present PGSAudit, a command-line tool that reports the ancestry composition of the samples behind each score in a
scoring file and warns when a score is applied to a sample of another ancestry.

## Introduction

Ancestry imbalance in polygenic score research is well documented.
A further 29% of studies in that decade included only East Asian ancestry participants [1].
Only 3.8% of polygenic score studies from the same period included cohorts of African, Hispanic or Indigenous peoples [2].
European ancestry-derived polygenic scores performed comparably in African ancestry samples [1].
Genetic prediction has also been applied to longevity: a model of 150 SNPs was reported to predict exceptional longevity with 77% accuracy in an independent set of centenarians and controls [3].

## Discussion

PGSAudit makes the ancestry of the training samples visible at the point where a score is used.
Polygenic risk profiling has been proposed for stratifying screening, for example in breast cancer and coronary artery disease [5].
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
2. Cross B, Turner R, Pirmohamed M. Polygenic risk scores: an overview from bench to bedside for personalised medicine. Front Genet. 2022;13:1000667. doi:10.3389/fgene.2022.1000667
3. Sebastiani P, Solovieff N, Puca A, et al. Genetic signatures of exceptional longevity in humans. Science. 2010;329(5987). doi:10.1126/science.1190532
4. Lambert SA, Gil L, Jupp S, et al. The Polygenic Score Catalog: an open database for reproducibility and systematic evaluation. medRxiv. 2020. doi:10.1101/2020.05.20.20108217
5. Torkamani A, Wineinger NE, Topol EJ. The personal and clinical utility of polygenic risk scores. Nat Rev Genet. 2018;19(9):581-590. doi:10.1038/s41576-018-0018-x
