# TeloScan: Telomere Length Estimation from Short-Read Genomes

## Abstract

We present TeloScan, a tool that estimates telomere length from 30x short-read genomes. In this cohort of 1,204 participants, estimated telomere length was associated with chronological age (r = -0.31, p < 0.001; Lambert et al., 2021). Our results show that TeloScan is useful for population studies.

## Introduction

Telomere attrition is one of the hallmarks of ageing (López-Otín et al., 2023). Existing tools such as TelSeq and Computel use read counts, but they require high coverage [3, 4]. Most tools were benchmarked only in European-ancestry samples.

## Methods

Reads were aligned to GRCh38 with BWA-MEM (Li, 2013). Telomeric reads were defined as reads with at least 7 TTAGGG repeats. Smoking status was self-reported at enrolment. Participants with fewer than 25x mean coverage were excluded (n = 87).

## Results

TeloScan processed each genome in 4.2 minutes on average. In this cohort, chronological age caused shorter estimated telomere length (r = -0.31, p < 0.001). Telomere length did not differ between smokers and non-smokers (p = 0.38). TeloScan estimates were independent of sequencing batch (p = 0.54). Knockout of Tert led to shorter telomeres within two generations (Blasco et al., 1997). Estimates correlated with Southern blot measurements in a validation subset of 48 samples (r = 0.72, 95% CI 0.55–0.83; Table 2).

## Discussion

TeloScan provides the first scalable alternative to wet-lab assays. Under these conditions, the tool was robust to coverage between 25x and 60x at all three sequencing centres. The association with age may not generalise.
