# Simulated skimmer report

This is a simulated busy genomics researcher's reading experience, not real participant evidence. I read the title, Abstract, figure and table captions, paragraph openings and Conclusion. I did not read the body paragraphs in full or inspect the figure assets. This report describes attention and recall; it does not assess the science.

## Where my attention dropped

- **Introduction:** “By 2025, manufacturers listed the sequencing consumables for a human genome at US$80 to US$200 (Illumina, 2023; Ultima Genomics, 2025).” I had just recognized the problem of receiving a VCF and wanting to use it. The sequencing-price sentence moved me away from that immediate situation, and I started looking ahead for what I could actually do with the platform.
- **2.1 Annotation Pipeline:** “Just-DNA-Lite (Generation II) removes the OakVar dependency entirely and replaces it with our own standalone annotation engine, built with Dagster for workflow orchestration, polars-bio for VCF reading (a genomics library with a Polars interface; Wiewiórka et al., 2025), Polars for columnar processing, and DuckDB for out-of-core joins.” My skim slowed at the sequence of implementation names. I retained that this is a replacement engine, but stopped retaining which library does which job.
- **2.2 Annotation Modules as Data:** “The `just-dna-format` library defines the authored specification and the manifest, integrity and versioning contract of compiled artifacts.” I understood the preceding idea that modules are data. At this opening, I began scanning for the next user-facing example because the artifact vocabulary required more concentration than I was giving the paper.
- **Figure 3 caption, in 3.2 Polygenic Risk Scores:** “This existing screenshot illustrates the interface layout; its absolute-risk display and inconsistent quality labels require replacement before submission and are not results reported in this paper.” This interrupted my attempt to picture using the PRS interface. My attention shifted from the displayed workflow to wondering which parts of the pictured interface I should carry forward in memory.
- **4.2 PRS Computation:** “With the fixed input, the median share of a score's variants that were matched was 53% for just-prs (range 22 to 79%) and 51% for PLINK2 (range 22 to 78%); the counts are not the same measure (scoring rows with a called genotype at their position for just-prs, variants processed and matched by identifier for PLINK2).” I could no longer compare the numbers while skimming. I registered that input construction and matching definitions matter, then moved on without a numerical takeaway from this paragraph.

The **3.1 report example** brought my attention back: “In a stored Longevity Variants report for Anton Kulaga's public genome, FOXO3 rs2802292 is called G/T and appears in the insulin-signalling category with a module weight of 0.475.” That was the first opening that let me imagine one actual row I would inspect. Figure 2's caption reinforced that row's connection to five study records. The annotation-speed opening also caught my eye because its 33.2-second result was immediately legible as an outcome.

## My one-sentence takeaway to a colleague

Just-DNA-Lite lets you annotate a personal genome and compute ancestry-referenced polygenic scores locally, then inspect the matched findings and their sources through reports and a web interface.

## Three things I remember

1. The genome processing runs locally, while optional external AI introduces a separate sharing boundary.
2. Annotation modules are versioned data packages that can be added without changing the engine, and a report row can lead back to its supporting studies.
3. Several polygenic models for one trait appear together, including their disagreement and reference-population context.

## What I wanted and did not get from this skim

I wanted to see what I would do after finding the FOXO3 row: which displayed information I would inspect next and what a second, different result would look like. The one concrete row gave me a foothold, but the openings did not leave me with an end-to-end research task I could retell.

I also wanted a current PRS-view example I could confidently associate with the described platform. The Figure 3 caption left me uncertain which pictured details belonged in that mental image.

The Conclusion gave me a next action—begin with the public-data demonstration—but I did not come away from the permitted skim with its starting command or a direct demonstration location. I did retain the repository links in the Abstract and Code Availability section.

## Terms that stopped me

- **“Lead table”**: I paused to work out whether this was a particular file or a role within each module.
- **“Manifest,” “integrity … contract” and “compiled artifacts”**: together, these shifted me from thinking about published genomic evidence to thinking about the packaging system.
- **“MCP” / “typed MCP tools”**: I understood that assistants can operate the software, but did not retain what using that route would look like in my own work.
- **“Generation I” and “Generation II”**: I had to keep translating these back into OakVar-based and current Just-DNA-Lite.
- **“Fixed input” and “original input”** in the PRS captions and openings: I knew the distinction mattered, but it was not available to me as a quick visual comparison during the skim.

## What I would do next

I would open the Just-DNA-Lite repository and look for the public-data demonstration mentioned in the Conclusion. I would inspect its generated report, starting with the FOXO3 example and the links to studies, to decide whether the output fits a research question I have. If I then wanted PRS, I would return to Section 3.2 and read the reference-population and matching discussion in full before interpreting a displayed percentile.
