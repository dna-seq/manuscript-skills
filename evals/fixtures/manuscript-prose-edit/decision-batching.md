# A configurable workflow for environmental observations

## Abstract

We describe a configurable workflow that separates observation records from interpretation rules.
The workflow supports local reanalysis when a rule changes. It does not establish that the resulting
interpretations improve environmental decisions.

## Introduction

No existing tool makes it straightforward to reanalyse an observation with a different interpretation
rule. Commercial platforms conceal how their interpretations are curated.

## Methods

The workflow recieve observations as a table. Each interpretation rule is stored separately from the
processing code. We tested the workflow using observations from one monitoring site. The monitoring
period and the site's inclusion criteria still need to be supplied by the authors.

## Results

The test included 80 observations. The first rule accepted 32 observations and rejected 48. The
second rule accepted 40 observations and rejected 40. These are counts from one demonstration;
they do not measure performance at other sites.

## Discussion

The configuration files is readable without running the workflow. The rules can be inspected before
reanalysis. We have not compared the workflow with other tools under a common workload.

The manuscript's target journal has not been chosen.
