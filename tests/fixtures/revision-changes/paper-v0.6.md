# **Just-DNA-Lite: a Local-First, Open-Source Platform for Personal Genome Annotation and Polygenic Risk Scoring**

> **Draft v0.6 (Paper 1 of 2).** This is the platform paper: the local-first platform and the compute engines it runs — the annotation pipeline, the just-prs computation library **and its `just-prs-mcp` access layer**, the no-code module format, the web UI, `just-dna-format`, and the module registry. The boundary with the companion paper is *consuming* versus *authoring*: this paper covers how a compiled module or a published score is discovered, computed against a genome, and reported, including from an AI assistant that calls these operations as typed tools. The companion paper covers the other direction — an assistant *producing* new annotation content: the authoring plugin, the enrichment and compilation toolchain, and how modules are published and versioned. It is *Creating and Sharing Genomic Annotation Modules with AI: The Just-DNA Ecosystem* (<!-- @rev N6 rounds=2 by=claude:2026-10-15,claude:2026-10-19 -->entered at EASRP 2026 and not selected for the final, so its journal is still to be chosen; draft mirror: `paper2-just-module-creator.md`). See `docs/manuscript/v0.3/manuscript-strategy-v0.3.md` and, for venues, `docs/manuscript/manuscript_journal_strategy.md` (section "Venues, October 2026").<!-- @/rev N6 -->

<!-- @rev AU1 rounds=1 by=claude:2026-10-26 -->
**Authors:** Kulaga Anton^1,2,†^, Usanov Nikolay^3,4,†^, Borysova Olga^4^, Karmazin Alexey^3,4^, Koval Maria^4^, Pushkareva Malvina^4^, Zaharia Livia^1^, Fuellen Georg^1,\*^, Tacutu Robi^2,\*^
<!-- @/rev AU1 -->

**Affiliations:**

<!-- @rev AU2 rounds=1 by=claude:2026-10-26 -->
1. Institute for Biostatistics and Informatics in Medicine and Ageing Research, Rostock University Medical Center, Rostock, Germany
<!-- @rev R1 rounds=1 by=robi:2026-09-25 -->
2. Institute of Biochemistry of the Romanian Academy, Bucharest, Romania
<!-- @/rev R1 -->
3. HEALES (Healthy Life Extension Society)
4. SecvADN SRL
<!-- @/rev AU2 -->

<!-- @rev V7 rounds=1 by=claude:2026-10-19 -->
† These authors contributed equally. \* Co-supervising authors.
<!-- @/rev V7 -->

---

## **Abstract**

<!-- @rev C2a rounds=10 by=robi:2026-09-25,claude:2026-10-10,claude:2026-10-13,codex:2026-10-19,codex:2026-10-26,claude:2026-10-26,claude:2026-10-26,claude:2026-10-26,claude:2026-10-26,claude:2026-10-26 -->
Just-DNA-Lite is the core of an open-source ecosystem for reading a personal genome against published evidence on the user's own computer. Its web platform annotates a whole-genome VCF and computes polygenic risk scores locally, so the genome does not have to be uploaded. Every matched variant links to its reported effect and its sources. What the platform reports comes from modules, versioned tables of variant-trait associations that researchers write without programming. Ready-made modules cover longevity, disease predisposition and drug response. Researchers publish new ones to just-dna-registry, an open registry that works like an app store, where others browse, install and apply them with no software update. The just-module-creator plugin drafts modules from the literature and public databases inside the AI assistant a researcher already uses. Polygenic scores come from just-prs, a library that also works on its own. It places each PGS Catalog score within a reference population matched to the genome's inferred ancestry and shows all models for a trait side by side, so users see where the models agree and differ. AI assistants can also run annotation and scoring through Model Context Protocol servers, and a public demonstration lets anyone try the platform on public genomes.
<!-- @/rev C2a -->

## **5. Discussion**

<!-- @rev T6 rounds=2 by=codex:2026-10-19,claude:2026-10-26 -->
The platform connects a genome to the evidence used to annotate it, from an individual variant's supporting studies to the reference population behind a polygenic percentile.<!-- @rev F5 rounds=1 by=claude:2026-10-26 --> Because the same operations are reachable from a web interface, an AI assistant or a Python library, one installation serves people reading their own genome, researchers who publish and test modules, and developers who build on its libraries (Box 1).<!-- @/rev F5 --> The Longevity Variants example makes that connection visible at one locus; the module format lets researchers extend it to other questions without changing the annotation engine. Local execution and visible provenance address two practical barriers to exploration. Their value depends on the underlying calls, studies and curation, whose limits are discussed below.
<!-- @/rev T6 -->

### **5.6 Conclusion**

<!-- @rev R24 rounds=5 by=robi:2026-09-25,claude:2026-10-19,claude:2026-10-19,codex:2026-10-19,claude:2026-10-26 -->
Just-DNA-Lite gives people and researchers a local way to read a genome against published evidence. It offers a cleaned PGS Catalog of 6,117 scores with ancestry-matched percentiles and quality labels, a registry of installable annotation modules that grows as researchers publish them, whole-genome annotation in about a minute, and the same operations from a web interface, AI assistants and Python libraries. The reported benchmarks <!-- @rev A3c rounds=8 by=claude:2026-10-11,claude:2026-10-12,claude:2026-10-19,claude:2026-10-19,claude:2026-10-26,claude:2026-10-26,claude:2026-10-26,claude:2026-10-26 -->show annotation 128 to 231 times faster than the OakVar-based Generation I system run on the same machine and close numerical agreement between scoring engines, on four call sets from three people for annotation and one for scoring.<!-- @/rev A3c --> Evaluation across individuals, reference populations, and matched-variant sets remains necessary to establish the broader reliability of these workflows. The platform provides infrastructure for research and education, without establishing clinical validity for the findings it reports. Researchers can begin with the public-data demonstration, inspect the sources behind a report, and then apply or extend the same workflow locally for their own research questions.
<!-- @/rev R24 -->

## **Contribution Statements**

<!-- @rev P7 rounds=2 by=claude:2026-10-19,claude:2026-10-26 -->
- **Kulaga Anton**: co-founded the project, bioinformatic pipeline development, Just-DNA-Lite architecture (Dagster/Polars/DuckDB pipeline, uv workspace), just-prs library development and benchmarking, web UI development, team management, article writing
<!-- @rev R25 rounds=1 by=robi:2026-09-25 -->
- **Usanov Nikolay**: co-founded the project, Just-DNA-Lite platform development, <!-- @rev D3 rounds=2 by=claude:2026-10-10,usanov:2026-10-10 -->the module system, the population ancestry discriminator (detection and algorithm), AI-assisted module authoring<!-- @/rev D3 -->, fundraising
<!-- @/rev R25 -->
- **Borysova Olga**: <!-- @rev C12g rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->module curation<!-- @/rev C12g --> and report content (<!-- @rev C12f rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->longevity variants, cardiovascular traits, lipid metabolism, thrombophilia, VO2 max, athletic performance, pharmacogenomics, and the Superhuman module, built from George Church's Protective and Enhancing Alleles list<!-- @/rev C12f -->), LongevityMap database curation and expansion, pathway categorization, report structure, data collection and analysis
- **Karmazin Alexey**: lead architect of the <!-- @rev C37 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->report system of Generation I (the OakVar-based Just-DNA-Seq)<!-- @/rev C37 -->, OakVar report modules and preparation utilities, PRS modules
- **Koval Maria**: report modules, report template, <!-- @rev C12h rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->code of the trait annotation modules (thrombophilia, cardiovascular)<!-- @/rev C12h -->
- **Pushkareva Malvina**: software development and testing
- **Zaharia Livia**: beta-testing, provided her whole genome for testing and benchmarking
- **Fuellen Georg**: co-supervision, valuable suggestions and comments
- **Tacutu Robi**: <!-- @rev C38 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->co-supervision,<!-- @/rev C38 --> bioinformatics and ageing research advising, LongevityMap database
<!-- @/rev P7 -->

<!-- @rev AU3 rounds=1 by=claude:2026-10-26 -->
**Acknowledgments:** We thank Ryangguk Kim (Oak Bioinformatics, LLC), who created and maintains OakVar and extended it for the Generation I platform; Alina Fedorova for bioinformatic utilities and scientific literature exploration; Sergey Evfratov for developing the Generation I pharmacogenomics (drug) module; and Volodymir Semenuik for help with documentation.
<!-- @/rev AU3 -->

<!-- @rev V17 rounds=1 by=claude:2026-10-19 -->
**Use of AI tools.** Claude Code (Anthropic; mostly the Claude Opus 5.5 model) was the main AI assistant in this work, and Codex (OpenAI; mostly GPT-6.1 Sol) served as a second model that checked Claude Code's output from time to time, through harnesses the authors wrote to catch potential mistakes. [What the tools were used for, and in which parts: for example writing and testing the software and benchmark scripts, checking text against tables and sources, editing or drafting manuscript text.] The authors reviewed the output and take full responsibility for the content. Details are in Supplementary Note S11.
<!-- @/rev V17 -->

## **Funding**

<!-- @rev R26 rounds=3 by=robi:2026-09-25,claude:2026-10-13,claude:2026-10-19 -->
This work was supported by the Ministry of Investments and European Projects, through the Managing Authority for the Health Program [PS/272/PS_P5/OP1/RSO1.1/PS_P5_RSO1.1_A9–ROGEN Project, MySMIS 324809, to A.K. and R.T.]; and the Romanian Academy [to R.T.].
<!-- @/rev R26 -->

## **Code Availability**

<!-- @rev J15 rounds=2 by=claude:2026-10-13,codex:2026-10-19 -->
**Source code:** Just-DNA-Lite (AGPL-3.0), https://github.com/dna-seq/just-dna-lite; just-prs (MIT), https://github.com/dna-seq/just-prs. Table S8 lists the repositories of both generations.
<!-- @/rev J15 -->

<!-- @rev P6 rounds=1 by=claude:2026-10-19 -->
Annotation modules and reference datasets are published to the just-dna-seq organization on HuggingFace (annotators, ensembl_variations, clinvar, pgs-catalog, prs-percentiles), which is the default source for module auto-discovery. Other fsspec-compatible sources are also supported.
<!-- @/rev P6 -->

## **Data Availability**

<!-- @rev V3 rounds=5 by=claude:2026-10-19,claude:2026-10-19,codex:2026-10-19,claude:2026-10-19,claude:2026-10-26 -->
The two personal genomes used in the benchmarks are public on Zenodo: Anton Kulaga's whole-genome VCF (Kulaga, 2026; https://doi.org/10.5281/zenodo.18370498, CC0 1.0) and Livia Zaharia's (Zaharia, 2026; https://doi.org/10.5281/zenodo.19487816, CC BY 4.0). The HG002 VCF is the public output of the DeepVariant 1.0.0 whole-genome case study (https://storage.googleapis.com/deepvariant/case-study-outputs/1.0.0/WGS/output/HG002.output.vcf.gz). The 2023 call set of Anton Kulaga's genome (DeepVariant 1.3.0), on which the earlier Generation I times were measured, is not deposited. The annotation modules of Table 1 are published in the module registry (https://module-registry.just-dna.life, namespace `just-dna-seq`), in the versions the benchmark used (Table S4), and the reference datasets the platform downloads are published on HuggingFace (https://huggingface.co/just-dna-seq). The HuggingFace mirror of the modules (`just-dna-seq/annotators`), which the platform reads by default, differs from the registry for four of them (Table S4). The benchmark scripts, the record of every run and the generated tables are in the just-dna-lite repository (`docs/manuscript/benchmarks/a3/`) [and in the archived release, DOI to be added]; the just-prs rerun reported in Section 4.2 is in the just-prs repository (`just-prs/benchmarks/results/2026-10-11/`; https://github.com/dna-seq/just-prs/tree/main/just-prs/benchmarks/results/2026-10-11). Supplementary Tables S4 and S5 are provided as data files with this article.
<!-- @/rev V3 -->

## **Competing Interests**

- Anton Kulaga, Olga Borysova, Maria Koval, Nikolay Usanov, and Alexey Karmazin are co-founders of SecvADN SRL, which provides additional services on top of the open-source modules.
