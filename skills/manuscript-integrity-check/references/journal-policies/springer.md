# Springer and BMC journals of Springer Nature: generative-AI policies (checked 2026-10-15)

> Cluster `springer`. Every journal here inherits the `springer-nature` publisher default (written by another agent: Green/Amber/Red framework, `writing_help: red_line`). This file records only what the journal pages add.

## How this was read

- **Fetch route.** All link.springer.com pages refuse plain HTTP clients ("JavaScript is disabled"). Every page was rendered with headless Chrome (`--headless=new --dump-dom`, 15 s virtual time budget), then converted with `w3m -dump`. The quotes below are exact text from those renders.
- **ZGG PDFs.** The Zeitschrift für Gerontologie und Geriatrie guidelines live in PDFs on media.springer.com. They were fetched with curl and read with `pdftotext`.
- **Page dates.** No page in this cluster shows a "last updated" date. Every footer reads "© 2026 Springer Nature". The ZGG guideline PDFs carry a 2022 modification date in their metadata.
- **JIF.** Each JIF is the "Journal Impact Factor" line in the "Journal metrics" box of the journal's own link.springer.com home page. All of them read "(2025)".
- **Searches.** I looked for journal-specific AI editorials or desk-rejection notices for GeroScience, JTM, J Cheminformatics, BioData Mining, and for any of these journals in 2026 news. **NOT FOUND**: no such item for any journal in this cluster.

## Two templates cover the whole cluster

### A. Springer-brand journals (GeroScience, Biogerontology, ACER, Human Genetics, MGG)

The journal home page's "Editorial policies" link goes to https://link.springer.com/brands/springer/journal-policies. Section 11 there, "Artificial intelligence (AI)", is word for word the same as the BMC brand section (diffed word by word).

The journal's own submission-guidelines page, in its "Title Page" section, adds this text (VERIFIED, identical on all five pages):
> "Large Language Models (LLMs), such as ChatGPT, do not currently satisfy our authorship criteria. Notably an attribution of authorship carries with it accountability for the work, which cannot be effectively applied to LLMs. Use of an LLM should be properly documented in the Methods section (and if a Methods section is not available, in a suitable alternative part) of the manuscript. The use of an LLM (or other AI-tool) for "AI assisted copy editing" purposes does not need to be declared. In this context, we define the term "AI assisted copy editing" as AI-assisted improvements to human-generated texts for readability and style, and to ensure that the texts are free of errors in grammar, spelling, punctuation and tone. These AI-assisted improvements may include wording and formatting changes to the texts, but do not include generative editorial work and autonomous content creation. In all cases, there must be human accountability for the final version of the text and agreement from the authors that the edits reflect their original work."

Each of these pages also has, twice, a heading "Generative AI Images" followed by:
> "Please check Springer’s policy on generative AI images and make sure your work adheres to the principles described therein."

That link (https://www.springer.com/us/editorial-policies/artificial-intelligence--ai-/25428500) now lands on the brand journal-policies page. The page has no separate AI-image section any more. Only two image rules remain:
- the framework's Red example "Creating photorealistic images (deepfakes)";
- the SN author-page rule on visuals (publisher level).

### B. BMC journals (BMC Genomics, BMC Biology, BMC Medical Genomics, Immunity & Ageing, BioData Mining, AMB, JBS, J Cheminformatics, JTM, plus Genome Biology, Genome Medicine and BMC Bioinformatics)

**Where the text is.** The submission-guidelines landing pages carry no AI sentence. The sentence is on each article-type page (Software, Research, Methodology), under "Title page". The words are identical on every page I read, apart from a trailing full stop on three of them:
> "Large Language Models (LLMs), such as ChatGPT, do not currently satisfy our authorship criteria. Notably an attribution of authorship carries with it accountability for the work, which cannot be effectively applied to LLMs. Use of an LLM should be properly documented in the Methods section (and if a Methods section is not available, in a suitable alternative part) of the manuscript"

There is no copy-editing exemption in the BMC version.

**One exception.** The AMB *Research articles* page is an older template with no AI sentence. Its *Software article* page has the sentence.

**An AI tool offered by the publisher.** Every BMC landing page advertises an AI language checker:
> "You can also upload your manuscript and get a free language check from our partner AJE. The software uses AI to make suggestions that can improve writing quality."

### The `bmc` publisher default: not written

The brief asked for a `bmc` entry only if the BMC policy page adds to the framework. It does not, so BMC journals inherit `springer-nature` directly.

- **The AI section.** Section 19, "Artificial Intelligence (AI)", on https://link.springer.com/brands/bmc/editorial-policies matches the Nature Portfolio page (https://www.nature.com/nature-portfolio/editorial-policies/ai) word for word. The only difference is NP's extra "Editorial use" paragraph about NP's own use of AI.
- **Correction for publisher-policies.md §3.1.** That section says "The BMC copy adds 'Delegating peer review to an LLM'". The Nature Portfolio page carries that example too, so it is no longer a BMC addition.
- **What lives elsewhere on the BMC page.** The BMC page also has the following, but each item is publisher-wide: the Springer brand page has the same text.
  1. **Citations.** Already in publisher-policies.md §3.2. One sentence is new against the §3.2 quote:
     > "Carefully review citations following any use of AI in manuscript preparation, including use of AI for copy-editing and translation, as the AI tool may make changes to the citation text. Use of AI to generate citations can result in non-existent/hallucinated citations."
  2. **Peer review.** An older reviewer paragraph that contradicts the framework's reviewer line:
     > "we ask that, while Springer Nature explores providing our peer reviewers with access to safe AI tools, peer reviewers do not upload manuscripts into generative AI tools." ... "If any part of the evaluation of the claims made in the manuscript was in any way supported by an AI tool, we ask peer reviewers to declare the use of such tools transparently in the peer review report."

     The framework, by contrast, says: "May use AI to support peer review but must not upload manuscript content to unsecured or public AI tools".
- **URL update.** publisher-policies.md §3.2 cites `biomedcentral.com/getpublished/editorial-policies`. The live copy is https://link.springer.com/brands/bmc/editorial-policies.
- **Merge option.** BMC journal pages share one sentence: Methods placement, no exemption. If the merger wants less repetition, a `bmc` entry holding `disclosure_places` and `exempt: []` would carry it. I kept those two fields on each journal instead, as the brief directs.

---

## 1. GeroScience: VERIFIED

- **URLs**
  - Guidelines: https://link.springer.com/journal/11357/submission-guidelines
  - Home: https://link.springer.com/journal/11357
  - Policy: https://link.springer.com/brands/springer/journal-policies
- **Facts from the pages**
  - Official journal of the American Aging Association.
  - "Publishing model: Hybrid"; "Journal Impact Factor 6.0 (2025)".
- **AI text:** template A, verbatim. Nothing else about AI.
- **Other rules**
  - Abstract: "Please provide an abstract of 150 to 250 words."
  - Screening: "Manuscripts rejected without review comprise the majority of submissions given the current acceptance rate of ~25% of submitted original research articles."
  - Self-citation: "The authors are requested to avoid references to previously published articles in the journal, which could be construed as excess journal self-citation."
- **Article types**
  - Research Articles, Review, Mini-Review, Systematic Review, Editorial, Editorial Focus, Perspectives (~1,500 words), Innovative Methodology.
  - No software type. Innovative Methodology requires "a "proof of principle" demonstration" and, "Where possible, the method should be applied to real geroscience research."

**Answers**
1. **Writing help:** red_line (inherited). "AI assisted copy editing" of human-written text is exempt from declaration. "Generative editorial work and autonomous content creation" is not covered by the exemption.
2. **Disclosure:** in Methods, or "a suitable alternative part". The SN author guidance asks for an AI Declaration; doing both satisfies both.
3. **Prompts:** not mentioned.
4. **Screening and penalties:** none on the journal page; publisher level applies.
5. **Cost to authors:** none beyond the disclosure. The fit is the problem: there is no software type.

## 2. Biogerontology: VERIFIED

- **URLs**
  - Guidelines: https://link.springer.com/journal/10522/submission-guidelines
  - Home: https://link.springer.com/journal/10522
- **Facts:** "Hybrid"; JIF "5.3 (2025)".
- **AI text:** template A, verbatim.
- **Abstract:** 150 to 250 words.
- **Types of Papers**
  - REVIEW (proposal to the Editor first), RESEARCH (CONSORT/SPIRIT/STROBE checklists), METHODOLOGY, PERSPECTIVE, EDITORIAL.
  - METHODOLOGY "denotes an article that presents a new experimental or computational method, test or procedure, or an improvement to an existing method."
  - No software type.

**Answers:** as GeroScience (red_line inherited; copy-editing exemption; Methods; no prompts; nothing journal-specific on screening).

## 3. Zeitschrift für Gerontologie und Geriatrie: VERIFIED (the journal page only links to the publisher policy)

- **URLs**
  - Guidelines: https://link.springer.com/journal/391/submission-guidelines
  - Home: https://link.springer.com/journal/391
  - Guideline PDFs: https://media.springer.com/full/springer-instructions-for-authors-assets/pdf/1027243_Guideline_OriginalStudies.pdf and 69332_Leitfaden_Originalien.pdf, 587803_Guideline_Reviews_FocusArticles.pdf, 69331_Leitfaden_Uebersichten_Leitthemen_Schwerpunkt.pdf (same folder)
- **Facts**
  - "Hybrid"; JIF "1.1 (2025)".
  - © Springer Medizin Verlag.
  - Society partners: Deutsche Gesellschaft für Gerontologie und Geriatrie and Deutsche Gesellschaft für Geriatrie.
- **AI text:** none.
  - The German-language guidelines page has no AI/KI/LLM text.
  - The four guideline PDFs (PDF ModDate March and May 2022) have none either.
  - The only screening line is "Hinweis: Die Zeitschrift kann Software zum Auffinden von Plagiaten einsetzen."
- **Applicable policy:** the "Editorial policies" link on the journal home page, i.e. the Springer brand framework.
- **Limits** (Original Studies PDF):
  - "Total length: max. 25,000 characters including spaces".
  - German abstract and English abstract each "max. 1800 characters incl. spaces".
- **Rubriken:** Leitthema, Übersichten, Schwerpunkt, Originalien, CME, Journal Club. No software type.

**Answers:** the publisher framework only. No journal exemption or placement rule. Plagiarism software may be used.

## 4. Aging Clinical and Experimental Research: VERIFIED

- **URLs**
  - Guidelines: https://link.springer.com/journal/40520/submission-guidelines
  - Home: https://link.springer.com/journal/40520
- **Facts**
  - "Publishing model: Open access"; the home page says "Fully open access (OA) as of 1 January 2024".
  - Official journal of ESCEO.
  - JIF "4.7 (2025)".
- **AI text:** template A, verbatim.
- **Limits:** "Research Papers should not exceed 5.000 words including an abstract of no more than 250 words, unlimited references, no more than 5 tables and/or figures."
- **Other rule:** "pre-submission enquiries will not be considered or replied to."
- **Types:** Review (invited), Systematic Review, Research, Brief report, Perspective, Correspondence, Position Statement, Guidelines. No software type.

**Answers:** as GeroScience. The only extra burden is the 5,000-word cap, which includes the abstract.

## 5. Human Genetics: VERIFIED

- **URLs**
  - Guidelines: https://link.springer.com/journal/439/submission-guidelines
  - Home: https://link.springer.com/journal/439
- **Facts:** "Hybrid"; JIF "3.4 (2025)".
- **AI text:** template A, verbatim.
- **Abstract:** 150 to 250 words.
- **Types**
  - Research Articles, Brief Report, Correspondence, Review, Perspective.
  - Brief Reports run to "750–1,000 words in the main text" and may include "new methodological advances". Their Methods go to Supplementary Material.
  - No software type.

**Answers:** as GeroScience.

## 6. Molecular Genetics and Genomics: VERIFIED (journal-specific restatement)

- **URLs**
  - Guidelines: https://link.springer.com/journal/438/submission-guidelines
  - Home: https://link.springer.com/journal/438
- **Facts:** "Hybrid"; JIF "2.2 (2025)".
- **AI text.** The journal's own "Instructions for Authors" restate the rule in stronger words ("must"):
  > "Use of large language models (LLMs) or other AI tools must be documented in the Methods section (or an appropriate alternative). Use of AI for copy editing only does not need to be declared. "AI-assisted copy editing" refers to improvements in readability, style, and correctness (grammar, spelling, punctuation, and tone) without generating new content. In all cases, authors remain fully accountable for the final text and must agree that edits accurately reflect their original work."

  Template A appears again under Title Page.
- **Types**
  - Research papers, Brief Reports, Methodology Papers, Editorials, Reviews.
  - "Methodology Papers describe and document new or substantially improved methods, approaches, software, or databases without applying them to a research question (which would constitute a Research Paper). The method should be broadly useful to many laboratories." I counted this as `software_article: true`.
- **Abstract:** 150 to 250 words.

**Answers:** red_line inherited. Copy editing that generates no new content is exempt. Everything else goes in Methods. Prompts are not mentioned.

## 7. BMC Genomics: VERIFIED

- **URLs**
  - https://link.springer.com/journal/12864/submission-guidelines/software-article (AI sentence; same on /research-article)
  - https://link.springer.com/journal/12864/submission-guidelines
- **Facts:** "Open access"; JIF "3.9 (2025)".
- **AI text:** template B.
- **Sound-science policy:** "As a BMC Series journal, BMC Genomics does not make editorial decisions based on the perceived interest or potential impact of a study."
- **Types:** Research article, Database article, Software article, Review, Matters Arising, Comment.
- **Software article**
  - "a significant advance over previously published software (usually demonstrated by direct comparison with available related software)".
  - "BMC Genomics recommends, but does not require, that the source code of the software should be made available under a suitable open-source license".
  - "The Abstract should not exceed 350 words", structured as Background/Results/Conclusions.
  - An "Availability and requirements" block is required. The landing page asks for "Archived version: DOI or unique identifier of archived software or code in repository (e.g. Zenodo)".

**Answers**
1. **Writing help:** red_line inherited. No exemption on the journal page.
2. **Disclosure:** in Methods. Add the AI Declaration from the SN author guidance.
3. **Prompts:** none.
4. **Screening:** publisher level.

## 8. BMC Biology: VERIFIED

- **URLs**
  - https://link.springer.com/journal/12915/submission-guidelines/software (also /research-article)
  - Home: https://link.springer.com/journal/12915
- **Facts:** "Open access"; JIF "5.4 (2025)".
- **AI text:** template B.
- **Selectivity:** a "selective journal" with in-house editors: "published articles represents advances that are of high interest to a broad readership".
- **Types:** Research article, Methodology, Software, Review, Opinion, Registered Report, Comment, Matters Arising.
- **Software:** "BMC Biology publishes outstanding new software that will be of utility to a wide audience."; "BMC Biology operates a strict open access, open source and open data policy."
- **Abstracts:** research 250 words, software 350 words.

**Answers:** as BMC Genomics, plus the open-source requirement.

## 9. BMC Medical Genomics: VERIFIED

- **URLs**
  - https://link.springer.com/journal/12920/submission-guidelines/software-article (also /research-article)
  - Home: https://link.springer.com/journal/12920
- **Facts:** "Open access"; JIF "2.6 (2025)". BMC Series sound-science statement, the same as BMC Genomics.
- **Scope:** includes "novel bioinformatics methods on medical data" and "clinical genomics, and precision medicine".
- **Types:** Research, Software, Database, Case report, Study protocol, Systematic review, Review, Comment, Matters Arising.
- **Software:** open source "recommends, but does not require". Abstract 350 words.

**Answers:** as BMC Genomics.

## 10. Immunity & Ageing: VERIFIED

- **URLs**
  - https://link.springer.com/journal/12979/submission-guidelines/research-articles
  - Home: https://link.springer.com/journal/12979
- **Facts:** "Open access"; JIF "8.3 (2025)".
- **AI text:** template B.
- **Scope exclusion:** "Immunity & Ageing will not consider papers dealing with any aspect of ageing that does not include a substantial immunological element, or work solely reporting in silico analyses of publicly-available data."
- **Types:** Research articles, Brief reports, Reviews, Comment, Correspondence. No software type. Abstract 350 words.

**Answers:** as BMC Genomics. A pure software or computational paper is out of scope.

## 11. BioData Mining: VERIFIED

- **URLs**
  - https://link.springer.com/journal/13040/submission-guidelines/software-article (also /research)
  - Home: https://link.springer.com/journal/13040
- **Facts:** "Open access"; JIF "7.9 (2025)". Described as "an open access, open peer-reviewed informatics journal".
- **AI text:** template B.
- **Scope:** names "Foundation models, representation learning, probing, adapter methods, retrieval-augmented systems, and agentic AI approaches" and "Open-source software, benchmarks, datasets, databases, and web services".
- **Types:** Research, Methodology, Software article, Review, Short report.
- **Software:** open source "recommends, but does not require". Abstract 350 words.

**Answers:** as BMC Genomics. Open peer review means reviewer reports are public.

## 12. Algorithms for Molecular Biology: VERIFIED

- **URLs**
  - https://link.springer.com/journal/13015/submission-guidelines/software-article
  - https://link.springer.com/journal/13015/submission-guidelines/research-articles (old template, no AI sentence)
- **Facts:** "Open access"; JIF "1.6 (2025)".
- **AI text:** template B, on the Software page only.
- **Scope:** "Articles about novel software tools and benchmarking studies will be considered for publication if they contain algorithmically interesting aspects. The journal does not publish applications of established tools, methods, or workflows to particular biological case studies and descriptions of incremental improvements of software tools or data resources."
- **Types:** Research articles, Software article, Review article, Brief report, Comment, Debate article, Meeting report.
- **Software:** open source recommended, not required. Abstract 350 words.

**Answers:** as BMC Genomics.

## 13. Journal of Biomedical Semantics: VERIFIED

- **URLs**
  - https://link.springer.com/journal/13326/submission-guidelines/software (also /research)
  - Home: https://link.springer.com/journal/13326
- **Facts:** "Open access"; JIF "2.6 (2025)".
- **AI text:** template B.
- **Data rule:** "Authors must deposit their datasets in publicly available repositories prior to peer review, or include them as supplementary information files with their manuscript. The data will be assessed and reviewed as part of the journal's standard peer-review process".
- **Types:** Research, Software, Database, Review. Abstract 350 words.

**Answers:** as BMC Genomics, plus data deposition before review.

## 14. Journal of Cheminformatics: VERIFIED

- **URLs**
  - https://link.springer.com/journal/13321/submission-guidelines/software (also /research)
  - Home: https://link.springer.com/journal/13321
- **Facts:** "Open access"; JIF "7.9 (2025)".
- **AI text:** template B.
- **Software rules**
  - "Journal of Cheminformatics will only publish research or software that is entirely reproducible by third parties."
  - "For any software, the source code must be provided."
  - "freely and anonymously available under an OSI-approved Open Source license".
  - "a source code distribution must include documentation that states the software license(s), the list of authors".
  - Zenodo archiving is "strongly encouraged".
- **Abstract rule:** "The abstract should contain a section titled "Scientific Contribution"... a maximum of 3 sentences". No abstract word limit is stated.
- **Types:** Research, Methodology, Software, Database, Data Note, Review, Educational, Brief report, Comment, Correspondence, Meeting report.

**Answers:** as BMC Genomics. The extra cost is software quality and licence work, not AI work.

## 15. Journal of Translational Medicine: VERIFIED

- **URLs**
  - https://link.springer.com/journal/12967/submission-guidelines/methodology (also /research-article)
  - Home: https://link.springer.com/journal/12967
- **Facts:** "Open access"; JIF "9.7 (2025)".
- **AI text:** template B.
- **Types:** Research article, Methodology, Review, Commentary, Letter to the Editor. No software type.
  - Methodology: "a new experimental or computational method, test or procedure ... The article must describe a demonstrable advance on what is currently available."
  - Sections include "Medical Bioinformatics" and "Translational Genomics and Genetics".
  - Abstract 350 words.

**Answers:** as BMC Genomics.

---

## Re-check of the existing entries (genome-biology, genome-medicine, bmc-bioinformatics)

The AI policy has not changed. All three journals still carry the template-B sentence on their article-type pages, and their policy link is the BMC brand page (the SN framework). The differences are in JIF, software rules and URLs.

**genome-biology**
- **JIF:** the metrics box shows "Journal Impact Factor 9.2 (2025)". The overview text still says "with 9.4 Impact Factor", which is where venues.yaml's 9.4 came from. The current value is 9.2.
- **Software rule, now VERIFIED** on https://link.springer.com/journal/13059/submission-guidelines/software. publisher-policies.md §3.4 and §7 had it only from a search snippet (SECONDARY). Verbatim:
  > "Source code for tools described in Method or Software articles should be deposited in a public repository, with an OSI-compliant license. The access information and the license should be clearly stated in the manuscript. We also recommend a static deposition of the version described in the manuscript in a repository that assigns DOIs".
- **Limits:** the Software abstract "should not exceed 100 words" and is unstructured. The Research abstract is capped at 250 words. The entry has `limits: null`.

**genome-medicine**
- **JIF:** "10.8 (2025)" on the page; venues.yaml has 11.2.
- **Inherited software list is wrong.** The entry inherits genome-biology's `software` list ("public repository with OSI licence"). The Genome Medicine software page states no OSI or public-repository rule. What it does ask: "The abstract should summarize the work as briefly as possible and should include the URL linking to the main website for the software project."
- **Limits:** abstract 350 words.

**bmc-bioinformatics**
- **JIF:** "4.4 (2025)" on the page; venues.yaml has 3.3.
- **Inherited software list is wrong.** "BMC Bioinformatics recommends, but does not require, that the source code of the software should be made available under a suitable open-source license" contradicts the "OSI licence" item it inherits from genome-biology.
- **Sound-science policy:** it is a BMC Series journal ("does not make editorial decisions based on the perceived interest or potential impact of a study").
- **URL:** the entry's url (`/12859/submission-guidelines`) is the landing page, which has no AI sentence. The sentence is on https://link.springer.com/journal/12859/submission-guidelines/software-article.
- **Limits:** abstract 350 words.

Suggested replacement values (my reading of the live pages; the merger decides):

```yaml
genome-biology:
  jif: 9.2
  jif_year: 2025
  oa: full
  fields: [genomics, bioinformatics]
  article_types: [research, methods, software, database, review, letter]
  limits: {abstract_words: 100, body_words: null, over_limit_return: null}   # Software article; Research 250
  software: [public repository with OSI-compliant licence (Method and Software articles), DOI-assigning static deposit recommended, Availability and requirements block with archived DOI]

genome-medicine:
  jif: 10.8
  jif_year: 2025
  oa: full
  fields: [genomics, clinical]
  article_types: [research, methods, software, database, review, perspective, letter]
  limits: {abstract_words: 350, body_words: null, over_limit_return: null}
  software: [software project URL in the abstract, Availability and requirements block with archived DOI]

bmc-bioinformatics:
  jif: 4.4
  jif_year: 2025
  oa: full
  url: https://link.springer.com/journal/12859/submission-guidelines/software-article
  fields: [bioinformatics, software]
  article_types: [research, database, software, review, perspective, letter]
  limits: {abstract_words: 350, body_words: null, over_limit_return: null}
  software: [Availability and requirements block with archived DOI, open-source licence recommended but not required]
  fit_note: "BMC series: judged on scientific validity, not perceived interest"
```

## Not found or not read

- **Journal-specific AI editorials** or desk-rejection notices for any journal in this cluster: NOT FOUND (web search only).
- **Page dates:** none shown on any page.
- **ZGG:** no AI text in either the web page or its 2022 PDFs. The publisher policy is the only applicable rule.
