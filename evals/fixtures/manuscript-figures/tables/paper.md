# Varlens: annotating a personal genome on your own computer

## Abstract

Varlens annotates a whole-genome variant file on a laptop. Annotation takes 38.9 s per genome warm, and
agreement with a curated reference is 99.4%.

## 1. Results

Table 2 gives the runtime of each configuration, and Table 1 the agreement with the curated reference.

**Table 1.** Agreement with the curated reference set (2,184 variants).

| Tool | Agreement | Disagreement |
|---|---|---|
| Varlens | 2,171 (99.4%) | 13 |
| Server annotator | 2,160 (98.9%) | 24 |

**Table 2.** Runtime of each configuration on one genome.

| Configuration | Runtime | Peak memory | Speed-up | Note |
|---|---|---|---|---|
| Varlens, warm | 31.4 | 512.25 | 172 | |
| Varlens, cold | 203.3 | 640.5 | 26.6 | first run of the day |
| Server annotator | 6,705 | 2,048 | 1 | |

**Figure 1.** The report a user sees for one variant.

The full runtime log of every run is in Supplementary Table 1.
