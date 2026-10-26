# **Just-DNA-Lite: a Local-First, Open-Source Platform for Personal Genome Annotation and Polygenic Risk Scoring**

> **Draft v0.5 (Paper 1 of 2).** This is the platform paper: the local-first platform and the compute engines it runs — the annotation pipeline, the just-prs computation library **and its `just-prs-mcp` access layer**, the no-code module format, the web UI, `just-dna-format`, and the module registry. The boundary with the companion paper is *consuming* versus *authoring*: this paper covers how a compiled module or a published score is discovered, computed against a genome, and reported, including from an AI assistant that calls these operations as typed tools. The companion paper covers the other direction — an assistant *producing* new annotation content: the authoring plugin, the enrichment and compilation toolchain, and how modules are published and versioned. It is *Creating and Sharing Genomic Annotation Modules with AI: The Just-DNA Ecosystem* (<!-- @rev N6 rounds=2 by=claude:2026-10-15,claude:2026-10-19 -->entered at EASRP 2026 and not selected for the final, so its journal is still to be chosen; draft mirror: `paper2-just-module-creator.md`). See `docs/manuscript/v0.3/manuscript-strategy-v0.3.md` and, for venues, `docs/manuscript/manuscript_journal_strategy.md` (section "Venues, October 2026").<!-- @/rev N6 -->

**Authors:** Kulaga Anton^1,2,4,†^, Usanov Nikolay^3,4,†^, Borysova Olga^4^, Karmazin Alexey^4^, Koval Maria^4^, Fedorova Alina^4^, Pushkareva Malvina^4^, Evfratov Sergey^4^, Ryangguk Kim^8^, Zaharia Livia^3^, Fuellen Georg^1,\*^, Tacutu Robi^2,9,\*^

**Affiliations:**

1. Institute for Biostatistics and Informatics in Medicine and Ageing Research, Rostock University Medical Center, Rostock, Germany
<!-- @rev R1 rounds=1 by=robi:2026-09-25 -->
2. Institute of Biochemistry of the Romanian Academy, Bucharest, Romania
<!-- @/rev R1 -->
3. HEALES (Healthy Life Extension Society)
4. SecvADN SRL
5. CellFabrik SRL
6. MitoSpace
7. M. Glushkov Institute of Cybernetics of National Academy of Sciences of Ukraine
8. Oak Bioinformatics, LLC
<!-- @rev R2 rounds=1 by=robi:2026-09-25 -->
9. Romanian Bioinformatics Cluster, Târgu Mureș, Romania
<!-- @/rev R2 -->

<!-- @rev V7 rounds=1 by=claude:2026-10-19 -->
† These authors contributed equally. \* Co-supervising authors.
<!-- @/rev V7 -->

---

## **Abstract**

<!-- @rev C2a rounds=8 by=robi:2026-09-25,claude:2026-10-10,claude:2026-10-13,codex:2026-10-19,codex:2026-10-26,claude:2026-10-26,claude:2026-10-26,claude:2026-10-26 -->
Just-DNA-Lite is the core of an open-source ecosystem for reading a personal genome against published evidence on the user's own computer. The platform annotates a whole-genome VCF and computes polygenic risk scores locally through a web interface, so the genome does not have to be uploaded. Its annotation content comes as modules: versioned tables of variant-trait associations with their sources, written without code. Modules are published to just-dna-registry, an open registry that works like an app store: users browse modules, install them and apply them to their own genomes, with no new software release. The just-module-creator plugin lets researchers draft new modules from the literature and public databases with the AI assistant they already use. The just-prs library, usable inside the platform or on its own, scores PGS Catalog models and places each score within a reference population matched to the genome's inferred ancestry, with all models for a trait side by side. Ready-made modules cover longevity, disease predisposition and drug response, and every matched variant in a report leads to its reported effect and the studies behind it. Through Model Context Protocol servers, AI assistants can run annotation and scoring and read the results.
<!-- @/rev C2a -->

## **5. Discussion**

<!-- @rev T6 rounds=1 by=codex:2026-10-19 -->
The platform connects a genome to the evidence used to annotate it, from an individual variant's supporting studies to the reference population behind a polygenic percentile. The Longevity Variants example makes that connection visible at one locus; the module format lets researchers extend it to other questions without changing the annotation engine. Local execution and visible provenance address two practical barriers to exploration. Their value depends on the underlying calls, studies and curation, whose limits are discussed below.
<!-- @/rev T6 -->

### **5.6 Conclusion**

<!-- @rev R24 rounds=4 by=robi:2026-09-25,claude:2026-10-19,claude:2026-10-19,codex:2026-10-19 -->
Just-DNA-Lite integrates local variant annotation, polygenic scoring, and inspectable reports with a portable annotation-module contract and versioned content discovery. Typed MCP tools make the annotation workflow and the PRS engine available to AI assistants. The reported benchmarks <!-- @rev A3c rounds=7 by=claude:2026-10-11,claude:2026-10-12,claude:2026-10-19,claude:2026-10-19,claude:2026-10-26,claude:2026-10-26,claude:2026-10-26 -->show faster annotation than the OakVar-based Generation I system run on the same machine and close numerical agreement between scoring engines, albeit on four call sets from three people for annotation and one for scoring.<!-- @/rev A3c --> Evaluation across individuals, reference populations, and matched-variant sets remains necessary to establish the broader reliability of these workflows. The platform provides infrastructure for research and education, without establishing clinical validity for the findings it reports. Researchers can begin with the public-data demonstration, inspect the sources behind a report, and then apply or extend the same workflow locally for their own research questions.
<!-- @/rev R24 -->

## **Contribution Statements**

<!-- @rev P7 rounds=1 by=claude:2026-10-19 -->
- **Kulaga Anton**: co-founded the project, bioinformatic pipeline development, Just-DNA-Lite architecture (Dagster/Polars/DuckDB pipeline, uv workspace), just-prs library development and benchmarking, web UI development, team management, article writing
<!-- @rev R25 rounds=1 by=robi:2026-09-25 -->
- **Usanov Nikolay**: co-founded the project, Just-DNA-Lite platform development, <!-- @rev D3 rounds=2 by=claude:2026-10-10,usanov:2026-10-10 -->the module system, the population ancestry discriminator (detection and algorithm), AI-assisted module authoring<!-- @/rev D3 -->, fundraising
<!-- @/rev R25 -->
- **Borysova Olga**: <!-- @rev C12g rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->module curation<!-- @/rev C12g --> and report content (<!-- @rev C12f rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->longevity variants, cardiovascular traits, lipid metabolism, thrombophilia, VO2 max, athletic performance, pharmacogenomics, and the Superhuman module, built from George Church's Protective and Enhancing Alleles list<!-- @/rev C12f -->), LongevityMap database curation and expansion, pathway categorization, report structure, data collection and analysis
- **Karmazin Alexey**: lead architect of the <!-- @rev C37 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->report system of Generation I (the OakVar-based Just-DNA-Seq)<!-- @/rev C37 -->, OakVar report modules and preparation utilities, PRS modules
- **Koval Maria**: report modules, report template, <!-- @rev C12h rounds=2 by=robi:2026-09-24,claude:2026-10-13 -->code of the trait annotation modules (thrombophilia, cardiovascular)<!-- @/rev C12h -->
- **Fedorova Alina**: bioinformatic utilities, scientific literature exploration
- **Pushkareva Malvina**: software development and testing
- **Evfratov Sergey**: pharmacogenomics (drug) module development
- **Ryangguk Kim**: created and maintained OakVar, extended it for the Generation I platform
- **Zaharia Livia**: beta-testing, provided her whole genome for testing and benchmarking
- **Fuellen Georg**: co-supervision, valuable suggestions and comments
- **Tacutu Robi**: <!-- @rev C38 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->co-supervision,<!-- @/rev C38 --> bioinformatics and ageing research advising, LongevityMap database
<!-- @/rev P7 -->

**Acknowledgments:** Volodymir Semenuik for help with documentation.

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

- Ryangguk Kim is a co-founder of OakVar Inc.
- Anton Kulaga, Olga Borysova, Maria Koval, Nikolay Usanov, and Alexey Karmazin are co-founders of SecvADN SRL, which provides additional services on top of the open-source modules.
