<!-- Evaluation fixture for manuscript-story: an excerpt of a real manuscript by the plugin's authors (Just-DNA-Lite, Paper 1, v0.3, the earliest draft the authors keep), trimmed. -->

# **Just-DNA-Lite: a Local-First, Open-Source Platform for Personal Genome Annotation and Polygenic Risk Scoring**

*Excerpt: Sections 2 and 4, most of Sections 3 and 5, the figures, the references and the supplement are not included.*

## **Abstract**

Personal genome analysis requires tools that make published variant associations accessible while allowing users to inspect the methods and retain control of their data.

We present Just-DNA-Lite, an open-source platform that combines local variant annotation and polygenic risk score (PRS) computation in a web interface. Annotation modules contain variant-trait tables and metadata, allowing researchers to extend the catalogue without writing executable plugins. A shared module contract, automatic source discovery, and a versioned registry connect published annotation content to local analysis and downloadable reports. The just-prs library provides scoring through web, command-line, Python, and Model Context Protocol interfaces.

For one public whole-genome VCF, warm-run annotation averaged 38.9 seconds across 11 runs, approximately 172 times faster than the earlier OakVar-based Just-DNA-Seq configuration on the same hardware. In a separate benchmark of 100 polygenic scores on the same individual's genome, DuckDB and Polars had median per-score runtimes 12.3 and 5.7 times faster than PLINK2, respectively. Correlation with PLINK2 across the 96 scores completed by all engines was Pearson r = 0.999859. These measurements assess computational performance and numerical agreement for one genome; they do not establish predictive accuracy or agreement in rankings across individuals.

Core annotation and scoring run locally, with reference datasets downloaded and cached on the user's machine. Optional external AI services introduce a separate data-sharing boundary. Just-DNA-Lite is released under AGPL v3 for research and education; it does not provide diagnoses or establish clinical validity for the associations it reports.

## **1. Introduction**

Whole genome sequencing costs have fallen from billions of dollars to under a thousand since the completion of the Human Genome Project in 2003, and several companies now offer direct-to-consumer sequencing services (Whitley et al., 2020). Yet the gap between sequencing accessibility and variant annotation remains wide. Researchers and individuals receive raw variant files (VCFs) containing millions of variants but lack accessible tools to annotate them against published databases without specialized bioinformatics expertise.

Existing solutions occupy two extremes. Commercial platforms such as DNA Complete (formerly Nebula Genomics) and Dante Labs provide curated reports, but the curation is opaque: users cannot verify which polymorphisms contributed to a score, whether the methodology is appropriate for their ancestry, or how findings were weighted. At the other end, research-grade tools like PLINK, ANNOVAR, and VEP are powerful but demand command-line proficiency and significant setup effort. There is no open-source platform that combines comprehensive variant annotation with ease of use, transparency, and extensibility.

The genetics of longevity illustrates the need for extensible annotation tools. The field is rapidly evolving: traditional twin studies placed the heritability of lifespan at 20–25%, but a recent study in *Science* by Shenhar et al. (2025) estimates the intrinsic heritability at approximately 50% after correcting for extrinsic mortality confounders. GWAS studies have identified candidate loci including APOE and FOXO3 as consistently associated with longevity across populations (Broer et al., 2014; Caruso et al., 2022), and the catalogue of longevity-associated variants continues to grow. Databases such as LongevityMap within the Human Ageing Genomic Resources (HAGR) (Tacutu et al., 2017) have compiled thousands of variant-trait associations, but no existing tool makes it straightforward to annotate a personal VCF against these databases transparently and extensibly. This exemplifies a broader pattern: variant-trait associations are published faster than any single curation team can integrate them, motivating a platform where new annotation modules can be created rapidly.

A platform for personal genome annotation must therefore solve three problems simultaneously: it must be easy to use (web interface, no bioinformatics training), transparent in its methods (open-source, auditable scoring), and extensible (researchers should be able to add new annotation modules as the literature evolves, without writing code). Furthermore, privacy is a first-order concern: genomic data is among the most sensitive personal information, and uploading it to third-party servers introduces risks that many individuals and regulatory frameworks (such as the GDPR and the European Health Data Space) seek to avoid.

We developed Just-DNA-Lite as a ground-up rewrite of Just-DNA-Seq, whose first generation ran on OakVar (Kulaga et al., 2024). Just-DNA-Lite removes the OakVar dependency entirely and replaces it with our own standalone annotation engine, built with Dagster for workflow orchestration, polars-bio for VCF reading, Polars for columnar processing, and DuckDB for out-of-core joins. It also replaces Python annotation plugins with declarative data modules discoverable from configured sources (Section 2.2). In the reported same-hardware comparison, mean annotation runtime fell from 6,705 seconds for Generation I to 38.9 seconds for warm runs of Just-DNA-Lite (Section 5.1). Supplementary File S1 describes Generation I.

This paper presents the standalone annotation engine, the reusable just-prs scoring library, the web interfaces, and MCP interfaces for calling these tools programmatically from AI assistants. Together, these components let users discover annotation content, apply it to a genome, compute published polygenic scores, and inspect reports. The contribution is computational; the reported associations come from existing databases and literature. AI-assisted module authoring is introduced in Section 4 and treated in detail in the companion paper. Section 6 discusses the intended research and educational use and its limitations.

## **3. Annotation Modules and Polygenic Scoring**

Just-DNA-Lite ships with a set of expert-curated annotation modules developed by geneticist Olga Borysova, illustrating the platform's module system across several trait domains. These modules represent the default set; the platform is designed so that users, researchers within the ROGEN consortium, and the broader community can easily add their own modules, either by hand or with AI assistance (Section 4). The modules annotate user variants against published variant-trait association databases; they do not perform clinical interpretation or generate diagnoses.

These default modules originate in the first generation of the platform, the OakVar-based Just-DNA-Seq (Kulaga et al., 2024). That system was built around longevity and longevity-associated traits, which is why the default set centres on that domain; for the second generation we ported most modules largely unchanged, to serve as worked examples of the no-code module format rather than as a definitive trait catalogue.

**Table 1.** Default annotation modules shipped with Just-DNA-Lite.

| Module | Description | Curator |
|---|---|---|
| Longevity Map | Variant-trait associations from the LongevityMap database | Expert (Olga Borysova) |
| Coronary Artery Disease | Variants associated with cardiovascular traits from GWAS literature | Expert |
| Lipid Metabolism | Variants associated with lipid metabolism traits | Expert |
| VO2 Max | Variants associated with oxygen uptake capacity from exercise genomics literature | Expert |
| Superhuman / Athletic Performance | Variants associated with elite athletic performance traits | Expert |
| Longevity Variants 2026 | Variants from recent familial longevity and multimorbidity GWAS studies | AI-generated |

### **3.1 Longevity Variants Module (example)**

The Longevity Variants module illustrates how existing variant-trait association databases can be wrapped into the platform's no-code module format. It builds upon the LongevityMap database (Tacutu et al., 2017), which contains 3,144 variant-trait associations in 884 genes. Our contribution here is not re-annotation or re-validation of these variants, but (1) curation and expansion with post-2017 literature, adding 50 new entries and editing 876 existing records; (2) assignment of weighted scores based on study quality, replication across populations, and statistical significance; and (3) pathway-based categorization for structured browsing.

## **7. Conclusion**

Just-DNA-Lite integrates local variant annotation, polygenic scoring, and inspectable reports with a portable annotation-module contract and versioned content discovery. Typed MCP tools make the PRS engine available to AI assistants. On one public genome, the reported benchmarks show faster annotation than the earlier Just-DNA-Seq configuration and close numerical agreement between scoring engines. Evaluation across individuals, reference populations, and matched-variant sets remains necessary to establish the broader reliability of these workflows. The platform provides infrastructure for research and education, without establishing clinical validity for the findings it reports.
