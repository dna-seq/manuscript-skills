# SoilTrace: local taxonomic profiling of soil samples

## Abstract

Field ecologists need taxonomic profiles of soil samples without sending raw reads to a server. SoilTrace profiles
a sample on a laptop in strict mode or lenient mode and reports the taxa it is confident of. On 40 field samples,
its profiles agreed with a server-based reference pipeline.

## 1. Introduction

Soil microbial communities change with land use, and ecologists sample them to follow that change. Soil samples
degrade within days at room temperature. Our pipeline runs on a laptop.

Existing pipelines upload reads to a shared server, which field stations with slow connections cannot use. In
strict mode, SoilTrace reports fewer taxa than in lenient mode, but each one it reports is supported by every
replicate.

## 2. Methods

### 2.1 Reads

Reads were trimmed with fastp (v0.23.4) using default settings, except for samples sequenced before 2021, for
which a stricter quality cut-off was applied, unless their coverage fell below 10x, in which case the default
was retained (as in an earlier study).

### 2.2 Profiles

Reads are denoised into ASVs, rarefied to the smallest library, and compared by Bray–Curtis dissimilarity after
a CLR transform. A taxon is reported when it appears in at least 4 of 7 replicate runs and its abundance lies
outside the outer 1% of the background distribution, scaled by a factor of 0.9.

### 2.3 Modes

SoilTrace has two modes. Strict mode reports a taxon only when every replicate supports it; lenient mode
reports a taxon supported by most replicates.

## 3. Results

The abundance profiles of strict and lenient mode correlated with Pearson r = 0.99999871. Against the reference
pipeline, SoilTrace recovered 212 of 230 genera (92%) in lenient mode.
