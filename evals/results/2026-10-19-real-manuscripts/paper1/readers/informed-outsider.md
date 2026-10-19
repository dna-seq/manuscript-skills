# Simulated informed-outsider reading report

This is a simulated reader perspective, not real participant evidence. I read as a biologist who understands genes, genotypes, association studies and basic statistics, but has no bioinformatics training and does not routinely handle VCFs or analysis software. I read the complete supplied manuscript and inspected Figures 1–3. This account describes my reading experience; it does not assess the science or make a publication recommendation.

## My one-sentence takeaway to a colleague

Just-DNA-Lite lets us explore a genome on our own computer, trace individual annotations back to their source studies, and compare polygenic scores with an ancestry-related reference population, while leaving us responsible for interpreting the evidence and its limits.

## Where my attention dropped

### 2.1 Annotation Pipeline: the software stack arrives before I have pictured the task

> “Just-DNA-Lite (Generation II) removes the OakVar dependency entirely and replaces it with our own standalone annotation engine, built with Dagster for workflow orchestration, polars-bio for VCF reading (a genomics library with a Polars interface; Wiewiórka et al., 2025), Polars for columnar processing, and DuckDB for out-of-core joins.”

I understood that the authors rebuilt the engine, but the product names did not tell me what I would experience as a user. My attention became passive at “columnar processing” and “out-of-core joins.” The numbered ingestion-to-report sequence brought me back: a file goes in, filters are applied, published annotations are matched, and a report comes out.

### 2.1 Annotation Pipeline: I could not picture the matching operation

> “For each selected annotation module, the pipeline performs a streaming join between the normalized VCF Parquet and the module's lead table (for most modules, `weights.parquet`): by position, with the reference allele required to agree where the module states one, or by rsID for older modules without coordinates.”

I followed the biological idea of matching a variant to an annotation. I did not know what made a table a “lead table,” or what “streaming” contributed to that operation. I mentally reduced this sentence to “the software matches my variants to the selected evidence,” and stopped carrying the rest forward.

### 2.2 Annotation Modules as Data: file identities displaced the biological question

> “The `just-dna-format` library defines the authored specification and the manifest, integrity and versioning contract of compiled artifacts.”

At this point I was unsure whether a module meant a table of associations, an installed software component, or a package containing several kinds of files. The preceding examples helped, but “authored specification,” “manifest,” “contract” and “compiled artifacts” were a cluster of new meanings. I retained that modules can be shared and updated independently of the application, but not the mechanics of creating or recognizing one. The FOXO3 example later gave the module a concrete biological purpose again.

### 3.2 Polygenic Risk Scores: the implementation paragraph exceeded what I could hold at once

> “They join the scoring file to the genome by chromosome and position, then check that the genotype record is the scoring row's variant, since an indel shares its first base with any SNV at that position: an SNV row scores only from a record with an SNV alternate allele, and an indel row only from a record whose alleles include its effect allele and, where the scoring file names one, its other allele.”

I understood why matching the correct alleles matters. I lost track of which file supplied the reference allele, effect allele, other allele and alternate allele. I continued reading but did not build a reliable picture of the operation. By the later chunk sizes and memory limits, I was scanning for the next statement about what the result meant for the user. I remembered the weighted-sum explanation and the existence of missing loci more clearly than either engine's procedure.

### 3.2, Figure 3: the qualification interrupted my attempt to interpret the display

> “This existing screenshot illustrates the interface layout; its absolute-risk display and inconsistent quality labels require replacement before submission and are not results reported in this paper.”

The bell curve and separated model markers immediately showed me that models can disagree about the same person. Then the caption made me stop interpreting the numbers and labels. I could not tell how much of the pictured interpretation belonged to the current workflow, so I retained only the idea of viewing several models together. The image was visually memorable, but it did not leave me confident that I understood a present-day PRS result.

### 3.2.2 Ancestry Inference: I reached my limit at the projection method

> “A user's genome is projected into it with the online augmentation, decomposition and Procrustes method of FRAPOSA (Zhang et al., 2020), and its superpopulation is the majority among its 20 nearest reference individuals on the first 10 components.”

I had a workable high-level understanding before this sentence: the program compares a genome with a reference panel and selects a broad reference population. “Online augmentation, decomposition and Procrustes” stopped me. I do not know these operations, and could not connect them to a visible user action. My attention returned at the final sentence about an unknown result and the user choosing the reference.

### 4.1 Annotation Speed: I retained the headline but skimmed the run taxonomy

> “Generation II annotated each genome with the ten modules of Table 1, with Ensembl annotation off, in three modes: *warm* runs reuse the sample's quality-filtered table, so the VCF is not read again; *full* runs start from a fresh instance and read the VCF, as every OakVar run does, so they are the counterpart of an OakVar run (same VCF and same kind of report, not the same computation); *cold* runs are full runs after the operating system's page cache has been dropped.”

I understood “about half a minute versus about a hundred minutes” and that this came from a fairly capable workstation. I did not retain the distinction between restarting the program and dropping the page cache. In Table 2 I checked the full-run medians, then skimmed the remaining rows and spread statistics. The detailed measurement story was no longer connected to my immediate question of whether I could use the program on my own computer.

### 4.2 PRS Computation: I stopped keeping the version-and-input comparisons straight

> “The allele-aware rerun is reported first; Tables 3 and 4 retain the earlier benchmark so that its results remain traceable to the recorded protocol.”

This warned me that I needed to hold more than one experiment in mind. Once I reached “original” versus “fixed” PLINK2 inputs alongside 0.10.1 and 0.10.2, I repeatedly checked which numbers belonged together. I eventually carried forward only that the two internal engines agreed closely and that matching choices affected agreement with the comparator. I did not retain the individual correlations or maximum differences. I was uncertain which table would answer a colleague asking about the version they could now use.

## Three things I remember

1. **FOXO3 G/T connected to several identifiable studies.** The worked example, especially the distinction between survival to old age and survival during old age, showed me what “inspectable evidence” means. The weight of 0.475 was explicitly not a predicted increase in lifespan.
2. **A genome can stay on my computer during core analysis.** I also remember the separate caution that an external AI assistant could receive results even when the raw genome file stays local.
3. **Different polygenic models can disagree about the same trait.** The program displays them together and uses a broad ancestry-related reference population for percentiles. I remember the coverage and ancestry qualifications more clearly than the scoring-engine names.

## What I wanted and did not get

I wanted to experience one complete research use from a question to an endpoint: what someone wanted to learn, what they selected, what they saw, and what they did after inspecting the cited evidence. The FOXO3 example took me through a useful result, but I still did not know what the researcher did with that information beyond reading the studies.

I wanted a similarly concrete encounter with a PRS result. I understood the definition of a percentile, but not how a user responds when several models give very different percentiles or when roughly half the scoring variants are matched. The paper tells me that these limits are visible; I did not come away knowing how I would reason through such a display.

I wanted a practical sense of the first local session: how I know that the file from my sequencing provider is suitable, what I must download before running it, and whether a normal laboratory laptop is enough. The paper gives file and genome-build requirements and reports workstation measurements, but I could not translate them into confidence that I could start alone.

I also wanted to know how a biologist chooses among modules in the registry. I understood the distinction between expert, database-derived and AI-generated content, but did not develop a picture of how I would recognize the appropriate module for a particular biological question.

## Terms, abbreviations and steps that stopped me

- **VCF, callset, called genotype and variant-only:** I worked out that a VCF contains variant calls, but the idea that a missing record might mean a reference genotype rather than unmeasured data required rereading. The two separate restoration discussions were difficult to keep apart.
- **Parquet, lead table, streaming join, LazyFrame, out-of-core and fsspec:** these describe storage and computation that I do not normally use. I could follow the overall workflow while leaving their meanings unresolved.
- **Manifest, compiled artifact, integrity contract and typed MCP tools:** I understood the intended benefits of identifiable modules and assistant access, but could not describe the corresponding objects or operations in my own words.
- **FRAPOSA, KING and Procrustes:** these names stopped my understanding of the ancestry method. I understood the reference-panel comparison before and after them.
- **AFR, AMR, EAS, EUR and SAS:** I recognized the intent to use five broad ancestry groups, but the abbreviations remained less immediate than population names would be in my own notes.
- **GRCh38, GRCh37/hg19 and T2T:** I knew these were genome-reference versions, but could not determine from the manuscript how to identify or verify the one used for an unfamiliar personal-genome file.
- **Warm/full/cold runs and original/fixed inputs:** these were the main procedural obstacles in the results section. I needed to reread definitions rather than move steadily through the comparisons.

## What I would do next

I would open the public-data demonstration and try to find the FOXO3 result described in the paper. I would expand its studies and check whether I can follow the path from genotype to annotation to source without help. Then I would inspect one PRS trait with several models, paying attention to its reference population and coverage rather than treating the percentile as a diagnosis. Before analysing a private file locally, I would ask a bioinformatics colleague to help identify its genome build and confirm that I have understood the input requirements and the distinction between absent and called genotypes. I would keep external AI explanations out of that first session until I understood which results they would receive.
