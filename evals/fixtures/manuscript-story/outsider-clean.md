# SoilTrace: local taxonomic profiling of soil samples

## Abstract

Field ecologists need taxonomic profiles of soil samples without sending raw reads to a server. SoilTrace profiles
a sample on a laptop and reports the taxa it is confident of, either only those every replicate supports or
those most replicates support. On 40 field samples, its profiles agreed with a server-based reference pipeline.

## 1. Introduction

Soil microbial communities change with land use, and ecologists sample them to follow that change. Because soil
samples degrade within days at room temperature, they are best profiled where they are collected, so our
pipeline runs on a laptop.

Existing pipelines upload reads to a shared server, which field stations with slow connections cannot use.
SoilTrace has two modes (Section 2.3): strict mode reports fewer taxa than lenient mode, but each one it
reports is supported by every replicate.

## 2. Methods

### 2.1 Reads

Reads were trimmed with fastp (v0.23.4) using default settings. Samples sequenced before 2021 got a stricter
quality cut-off, as in an earlier study. Where such a sample's coverage fell below 10x, the default was kept.

### 2.2 Profiles

Reads are denoised into amplicon sequence variants (ASVs, exact sequences that stand in for species), rarefied
to the smallest library so that samples are compared at equal depth, and compared by Bray–Curtis dissimilarity,
a measure of how different two communities are, after a centred log-ratio (CLR) transform. A taxon is reported
when it appears in at least 4 of 7 replicate runs, the majority we calibrated on the mock community in Table S2,
and its abundance lies outside the outer 1% of the background distribution, scaled by a factor of 0.9 (chosen
by the authors; Table S3 shows the profiles with 0.8 and 1.0).

### 2.3 Modes

SoilTrace has two modes. Strict mode reports a taxon only when every replicate supports it; lenient mode
reports a taxon supported by most replicates.

## 3. Results

The abundance profiles of strict and lenient mode were practically identical (Pearson r = 0.99999871): the
modes differ in which taxa they report, not in how abundant they find them. Against the reference pipeline,
SoilTrace recovered 212 of 230 genera (92%) in lenient mode.
