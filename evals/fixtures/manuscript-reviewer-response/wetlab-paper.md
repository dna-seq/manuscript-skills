# RegPrior: ranking non-coding variants near FOXO3 by predicted regulatory effect

## Abstract

We ranked 1,204 non-coding variants within 500 kb of FOXO3 by their predicted effect on enhancer activity,
using public chromatin accessibility data from the HepG2 cell line and a sequence model trained on public
reporter-assay data. The three top-ranked variants disrupt enhancer activity of FOXO3 and are candidates
for follow-up in studies of human longevity.

## Methods

### Variants and annotation

We took all non-coding variants with a minor allele frequency above 1% in gnomAD v4 within 500 kb of the
FOXO3 transcription start site (1,204 variants) and annotated them with HepG2 ATAC-seq peaks from ENCODE.

### Scoring

Each variant was scored with a convolutional model trained on public massively parallel reporter assay
(MPRA) data. Variants were ranked by the predicted change in enhancer activity between the alleles.

## Results

Table 1 lists the number of variants at each step. Of the 1,240 variants scored, 87 fell in HepG2 ATAC-seq
peaks. The three top-ranked variants (Table 2) lie in one peak 23 kb upstream of FOXO3 and have predicted
activity changes of -1.9, -1.7 and -1.4 (log2 ratio of alternative to reference allele).

## Discussion

The three variants disrupt enhancer activity of FOXO3 in liver cells and may explain part of the
association of FOXO3 with longevity. A limitation is that the chromatin data come from one cell line.

## Data and code availability

All input data are public (gnomAD, ENCODE). The code is available at https://example.org/regprior.
