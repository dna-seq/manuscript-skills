# Elsevier, Cell Press and The Lancet Group: AI policies of candidate venues (read 2026-10-15)

Cluster `elsevier`. Entries in `../venues.yaml`. Page copies were kept only for the research session.

## How this was read

- **ScienceDirect Guides for Authors** (all Elsevier-owned journals): headless Chrome `--dump-dom`, then `w3m -dump`. No Cloudflare block.
- **Impact Factor and OA model** (ScienceDirect journals, including the Cell Press titles): the "Journal insights" page (`/journal/<slug>/about/insights`). The year is only in a popover, so the page was opened over the Chrome DevTools protocol and the Impact Factor button clicked. Every popover read: "The Impact Factor measures the average number of citations received in a particular year by papers published in the journal during the two preceding years. 2025 Journal Citation Reports (Clarivate Analytics, 2026)". The OA model comes from the "Article publishing options" block on the same page: "Open Access" plus "Subscription" means hybrid, "Open Access" alone means full OA.
- **cell.com and thelancet.com**: WebFetch returned 403. A plain `--dump-dom` stopped at the Cloudflare check, so the pages were opened in one Chrome session over DevTools with a real 45–90 s wait. Some cell.com pages still stopped at the check on the first try and were fetched again later.
- **Lancet Information for Authors PDFs**: `curl`, then `pdftotext` (PDF metadata: created 19 Aug 2026).
- **Diffs**: the AI section of every ScienceDirect guide was diffed word by word against Ageing Research Reviews' section. The Cell Press journal-policies AI section was diffed against Cell's. Where this file says "identical", that diff was empty.

Status marks follow BRIEF.md: VERIFIED (read on the venue's or publisher's own page), PARTIAL, SECONDARY, NOT FOUND.

---

## 0. Publisher defaults

### 0.1 Elsevier: VERIFIED (`elsevier`)

- URL: https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals
- Page date: footer "Policy updated June 2026." The announcement (https://www.elsevier.com/connect/updated-generative-ai-policies-for-journals-supporting-responsible-use-while-protecting-trust) is dated 18 August 2026 (WebFetch).
- Route: headless Chrome. This matches publisher-policies.md §4.1; nothing has changed since that file was written.

Verbatim:
> "Authors should disclose the use of AI tools for manuscript preparation in a separate AI declaration statement included in their manuscript upon submission. This statement will appear in the published article to ensure transparency. Authors should document their use of AI, including the name of the AI tool used, the purpose of its use, and the extent of their oversight."
> "Basic checks of grammar, spelling and punctuation do not need a declaration statement. However, when an AI tool makes substantive changes to sentence structure or organization of a part of the text, this should be disclosed."
> "Where AI tools are used as part of the research process rather than manuscript preparation, this use should be described in detail in the Methods section."
> FAQ (code): "If authors write or edit code using AI tools as part of their research, they should declare this in detail in the Methods section ... If authors only use AI tools to improve the presentation of their code in a manuscript, for example, for formatting, this should still be done with human control and oversight and should be reported in the AI declaration."
> FAQ (references): "Inclusion of fabricated references may lead to rejection of a manuscript." and "If these or any other AI tool are used to select, collate, generate or edit references, this should be declared in the manuscript."
> FAQ (records): "Authors should keep a separate record of which tool and model was used, and how AI tools were used. This may include retaining logs provided by the tool, saving prompts and generated outputs, and keeping evidence of how the content was reviewed and edited, for example through tracked changes or annotated drafts. ... If requested by editors, authors should be able to provide documentation of their use of AI tools."
> FAQ (inappropriate use): "Generating sections of a manuscript without genuine intellectual contribution from the author."
> Reviewers: "Reviewers should not upload a submitted manuscript or any part of it into an AI tool". The reviewer FAQ goes further: "Even if an AI tool is described as "private," uploading a manuscript still means sharing confidential and unpublished research with a third-party system. For these reasons, reviewers must not upload submitted manuscripts, or any information from them, into AI Tools."
> Publisher screening: "Our teams use AI tools to support them in: ... Performing research integrity checks to ensure compliance with our policies." Editors have "AI tools that assist in identifying relevant reviewers, matching the scope of submissions, and detecting duplicate submissions."

Inconsistency inside the page: the reviewer section says "reviewers should only use private AI tools to assist in the review process", while the reviewer FAQ says not even a "private" tool may receive the manuscript. Both forbid uploading the manuscript, so `reviewer_ai: banned` holds either way.

**Answers**
1. **Writing help:** allowed with disclosure (`disclose`). The page names organizing and structuring content and improving language as appropriate uses. Basic grammar, spelling and punctuation checks are exempt; substantive restructuring is not.
2. **Disclosure:** a separate published section before the references. Methods for research use and AI-written code. Figure captions for AI-assisted explanatory images.
3. **Prompts:** not required in the paper. They belong in the record authors keep and must produce if asked (`on_request`); keeping that record is `tracking: recommended`.
4. **Screening:** Elsevier runs AI "research integrity checks" and duplicate-submission detection (`integrity_signals`). No AI-text detector is named.
5. **Penalties:** fabricated references "may lead to rejection".
6. **Disclosure neutral:** the page is silent (`null`).
7. **Extra work:** a usage log (prompts, outputs, tracked changes). AI cover art needs prior permission. No general-purpose generative-AI graphical abstracts.

### 0.2 Elsevier Guide-for-Authors template (2026), quoted once

Eleven ScienceDirect guides carry this "Declaration of generative AI use" section word for word: ARR (the diff reference), MAD, EG, AGG, NBA, CBM, JBI, Genomics, Gene, SoftwareX and IJBCB. Genetics in Medicine and TMA do not (see their sections).
> "Authors must declare the use of generative AI tools in the manuscript preparation process upon submission of the paper."
> "Authors preparing a manuscript for this journal may use AI tools to support them. However, these tools must never be used as a substitute for human critical thinking, expertise, and evaluation. AI tools may only be applied with human oversight and control."
> "The use of AI tools in the manuscript preparation process must be declared by adding a statement at the end of the manuscript when the paper is first submitted. The statement will appear in the published work and should be placed in a new section before the reference list."
> "Title of new section: Declaration of generative AI and AI-assisted technologies in the manuscript preparation process. Statement: During the preparation of this work the author(s) used [NAME OF TOOL/SERVICE] to [REASON]. After using this tool/service, the author(s) reviewed and edited the content as needed and take(s) full responsibility for the content of the published article."
> "The declaration does not apply to the use of basic tools, such as tools used to check grammar, spelling, and references."
> "Please note: to protect authors' rights and the confidentiality of their research, this journal does not currently allow academic editors and reviewers to upload an unpublished manuscript into a generative AI tool"

Every one of these journal pages links "Elsevier's GenAI policies for journals" (§0.1). None of them names a similarity-check or AI-detection service.

Observation (VERIFIED, ScienceDirect journal header): each guide page advertises Elsevier's own AI writing tool: "Identify evidence gaps in your manuscript / Double-check your claims with LeapSpace's Writing Coach." Neither the policy nor the guide says whether using it needs a declaration. The policy's general rule would cover it.

### 0.3 Cell Press: VERIFIED (`cell-press`, carrying the old `patterns` values)

- URLs:
  - https://www.cell.com/cell/information-for-authors/journal-policies
  - https://www.cell.com/cell/information-for-authors/revise-manuscript (section `#declaration-ai`)
  - https://www.cell.com/reviewers
- Page date: none shown (© 2026).
- Route: Chrome over DevTools with a real-time wait (WebFetch 403).

Verbatim (journal policies):
> "Authors must declare the use of generative AI in scientific manuscript preparation upon submission of the paper, as outlined in the Elsevier policy"
> "Authors preparing a manuscript for submission can use generative AI tools, including agents and deep research tools, to synthesize complex literature, provide an overview of a field or research question, identify research gaps, generate ideas, and provide tailored support for tasks such as content organization and improving language and readability, within the limitations described on the Elsevier policy page."
> "The statement will appear in the published work and should be placed in a new section after the "declaration of interests" section."
> "The declaration does not apply to the use of basic tools, such as tools used to check grammar, spelling, and references. If you have nothing to disclose, you do not need to add a statement."
> "When the use of AI tools forms part of the research design or research methods, the use of the tools must be described in the manuscript in a reproducible manner in the methods or STAR Methods section and in the AI disclosure statement. This description should include the name of the model or tool, the version used, and the developer or manufacturer, where applicable."
> "Does not permit use of generative AI or AI-assisted tools to create or alter research or data images in submitted manuscripts, including but not limited to adjustments of brightness, contrast, or color balance"
> "Does not permit use of generative AI or AI-assisted tools in the production of cover art. An editorial exception may be granted only when the use of AI or AI-assisted tools are integral to the research described in the manuscript. General-purpose generative AI image tools may not be used in creation of graphical abstracts."
> Screening: "your article will be checked by the originality detection service Crossref Similarity Check ... Manuscripts are also screened against a Cell Press cross-journal database." "We screen all accepted manuscripts for image irregularities."

Revise-manuscript page:
> "This section is required for any papers in which generative AI and AI-assisted technologies were used in preparing the manuscript. ... Other uses of AI tools (e.g., to analyze and draw insights from data as part of the research process) must be reported within the methods or STAR Methods."

Reviewers page:
> "Reviewers should not upload a submitted manuscript or any part of it into any public or private generative AI tool or AI-assisted technologies, such as ChatGPT ... Private generative AI tools may be used only in a supportive context, for example to improve language and structure of a review report."

**Answers**
1. **Writing help:** allowed with declaration (`disclose`). Literature synthesis, idea generation and content organization are named as acceptable.
2. **Disclosure:** a published section after Declaration of interests. Methods or STAR Methods (model, version, developer) when AI is part of the research. Figure legends for AI-assisted explanatory images.
3. **Prompts:** not on the Cell Press pages. The Elsevier record-keeping FAQ applies (`on_request`).
4. **Screening:** Similarity Check, a cross-journal database and image screening (`integrity_signals`). No AI detector.
5. **Penalties:** none on the Cell Press page. Elsevier's fabricated-reference rule applies.
6. **Disclosure neutral:** silent (`null`).
7. **Extra work:** stricter on images than Elsevier (no AI cover art at all, no AI brightness or contrast changes).

### 0.4 The Lancet Group: VERIFIED (`lancet`, a separate default because it differs from Elsevier)

- URLs:
  - https://www.thelancet.com/editorial-policies (Lancet Group, section "Use of generative AI and AI-assisted technologies")
  - Journal PDFs:
    - https://www.thelancet.com/pb-assets/Lancet/authors/tl-info-for-authors-1787150940677.pdf (The Lancet)
    - https://www.thelancet.com/pb-assets/Lancet/authors/tlhl-info-for-authors.pdf (Healthy Longevity)
    - https://www.thelancet.com/pb-assets/Lancet/authors/ebm-info-for-authors.pdf (eBioMedicine)
  - https://www.thelancet.com/peer-review
- Page date: the PDF footers read "www.thelancet.com August 2026". The eBioMedicine PDF mixes "April 2026" and "August 2026" pages.
- Route: CDP Chrome for the HTML pages; curl and pdftotext for the PDFs.

Verbatim (Lancet Group editorial policies):
> "Upon submission, authors will be asked to declare the use of AI tools. ... Editors reserve the right to determine whether the use of AI is appropriate, and our policies differ depending on the content type."

Verbatim (Information for Authors). The main AI paragraphs, from "Use of generative AI" through the figure rule, are identical in all three PDFs (605 words, diffed); only the content-type paragraph differs:
> "Authors should disclose the use of AI tools for manuscript preparation in a separate AI declaration statement at the end of their manuscript upon submission and this statement will appear in the published work. Authors should document their use of AI, including the name and version of the AI tool used, the purpose of the use, and the extent of their oversight. Prompts should be provided where applicable and editors reserve the right to ask authors for these. ... Basic checks of grammar, spelling, and punctuation need no declaration. AI use in the research process should be declared and described in detail in the Methods section. Editors reserve the right to determine whether the use of AI is appropriate."
> "For figures, generative AI should be used primarily as a tool for brainstorming and suggesting image concepts. Its direct use in creating figures or artwork should be limited to demonstrations of its capabilities in specific contexts, such as academic articles."
> The Lancet only: "Use of AI-assisted tools and generative AI is not allowed for the World Report and Perspectives sections. For Comments and Correspondence, the use of generative AI is permitted only to assist with grammar and spelling; however, as your Comment or Correspondence will be edited to our house style, this should be rarely needed."
> LANHL and eBioMedicine ("Blue section content, which includes Comments and Correspondence"): "For Comments and Correspondence, the use of AI-assisted tools and generative AI is permitted only to assist with grammar and spelling. AI-assisted tools must not be used to: translate Comments or Correspondence at the submission stage, in whole or in part; improve arguments; generate new content or sentences; reorder content; shorten or summarise content; alter meaning; or generate, complete, or verify references or citations. ... Any breach of this policy will lead to rejection of your Comment or Correspondence."
> Screening (The Lancet PDF): "All Seminars, Series, Reviews, Therapeutics papers, and other non-research material that we are interested in publishing will be checked by editors using CrossCheck". The LANHL PDF says "At our discretion, material that we are interested in publishing will be checked by editors using CrossCheck".
> Reviewers (peer-review page): "Reviewers should not use Artificial Intelligence (AI) or AI-assisted technologies to assist in the scientific review of a manuscript ... Reviewers should not upload the manuscript, or any part of it, into an AI tool".

**How it differs from Elsevier §0.1:**
- requires the tool **version**;
- says **prompts should be provided** where applicable;
- asks about AI use in the submission system;
- states editorial discretion over whether a disclosed use is acceptable;
- bans AI by content type (Comments and Correspondence, and at The Lancet also World Report and Perspectives);
- discourages direct AI figure creation;
- bans reviewer AI use even for assistance.

It does not repeat Elsevier's record-keeping FAQ, so no `tracking` value is set.

**Answers**
1. **Writing help:** allowed with disclosure for research papers (`disclose`). Grammar and spelling only for Comments and Correspondence. None at all for The Lancet's World Report and Perspectives.
2. **Disclosure:** a submission question, then a published declaration at the end of the manuscript (tool, version, purpose, oversight, prompts where applicable). Methods for research use.
3. **Prompts:** "should be provided where applicable" (`required`, conditional), and editors may ask for them.
4. **Screening:** editors run CrossCheck (`plagiarism`). No AI detector is named.
5. **Penalties:** editors decide whether the use was appropriate. A breach of the Comment and Correspondence rule means rejection.
6. **Disclosure neutral:** **false**. "Editors reserve the right to determine whether the use of AI is appropriate" means a declared use can count against the paper.

---

## 1. Elsevier journals (inherit `elsevier`)

All are VERIFIED unless marked otherwise.
- **URL:** `https://www.sciencedirect.com/journal/<slug>/publish/guide-for-authors`. JIF and OA from `/about/insights` on the same journal.
- **Page date:** none shown (© 2026).
- **AI section:** the template in §0.2, unless stated otherwise.

### 1.1 Ageing Research Reviews (`ageing-research-reviews`): VERIFIED
- Slug `ageing-research-reviews`. JIF 15.5 (2025 JCR). Hybrid (APC USD 5,460, or subscription).
- AI: §0.2 template, identical. "Authors must declare the use of generative AI tools in the manuscript preparation process upon submission of the paper." The page links to the Elsevier policy for details.
- Answers: as Elsevier. Reviews only: "Review Article", "Short Review" (~2,500 words), "View Point" (~2,000 words, max 3 figures). Systematic-review authors must show "relevant subject-matter expertise in the cover letter". Abstract max 250 words.

### 1.2 Mechanisms of Ageing and Development (`mech-ageing-dev`): VERIFIED
- JIF 6.5 (2025). Hybrid (APC USD 4,850).
- AI: §0.2 template, identical.
- Answers: as Elsevier. "Research papers, including a Summary of 100-200 words"; the generic abstract section says max 250. Short Communications "should not exceed 1,000 words". Reviews and opinion/progress papers are partly solicited.

### 1.3 Experimental Gerontology (`exp-gerontol`): VERIFIED
- JIF 5.1 (2025). **Full OA**: the header reads "Open access", and the insights page lists only the APC option (USD 3,660, geographical pricing).
- AI: §0.2 template, identical.
- Answers: as Elsevier. "Experimental Gerontology publishes original research, short reports, reviews and mini-reviews." Abstract max 250.

### 1.4 Archives of Gerontology and Geriatrics (`arch-gerontol-geriatr`): VERIFIED
- JIF 4.7 (2025). Hybrid (APC USD 4,110).
- AI: §0.2 template, identical.
- Answers: as Elsevier. The guide lists no article types; the scope covers experimental, clinical and social gerontology. Abstract max 250.

### 1.5 Neurobiology of Aging (`neurobiol-aging`): VERIFIED
- JIF 4.0 (2025). Hybrid (APC USD 3,460).
- AI: §0.2 template, identical.
- Answers: as Elsevier. "Regular Articles" give priority to "hypothesis-driven studies". "For review articles, publication will generally be limited to systematic reviews". Alzheimer's studies need imaging or biomarker classification. Abstract max 250.

### 1.6 Translational Medicine of Aging (KeAi) (`transl-med-aging`): PARTIAL
- URLs:
  - https://www.sciencedirect.com/journal/translational-medicine-of-aging/publish/guide-for-authors
  - https://www.keaipublishing.com/en/journals/translational-medicine-of-aging/guide-for-authors/
  - https://www.keaipublishing.com/en/for-authors/publishing-ethics-authors/
- JIF: **not shown**. The insights page shows "3.0 CiteScore" only, and the KeAi page shows "CiteScore 3". Full OA (APC: USD 350 on the insights page, USD 700 in the guide text).
- AI: **NOT FOUND** on any of the three pages. The guide has no "Declaration of generative AI" section, and the KeAi ethics page has no AI text; it only points to "Elsevier's policies and ethics page". The `inherits: elsevier` entry is an inference: KeAi is hosted by Elsevier ("Production and hosting by Elsevier on behalf of KeAi Communications Co. Ltd"). Ask the editorial office.
- Screening (journal-specific, verbatim): "Submissions to KeAi journals are automatically screened using iThenticate's CrossCheck within the editorial system to detect plagiarism issues ... High similarity papers will be desk rejected."
- Answers: unknown beyond the inferred Elsevier default. TMA Express: "Articles do not exceed 1,500 words" and "Manuscripts submitted as TMA Express that do not meet these criteria will be returned to authors."

### 1.7 Computers in Biology and Medicine (`comput-biol-med`): VERIFIED, venue flagged
- JIF: **not shown**. The insights page shows "13.1 CiteScore" and no Impact Factor. Hybrid (APC USD 3,080).
- Journal notice (verbatim): "Computers in Biology and Medicine was placed 'On Hold' in April 2024 and had its coverage in the Web of Science Core Collection discontinued on November 17, 2025. As a result, any content published by the journal after Volume 172 (2024) is not currently indexed ... Elsevier's Research Integrity & Publishing Ethics team is conducting in-depth investigations."
- AI: §0.2 template, identical.
- Answers: as Elsevier. Desk rules: CBM "does not consider submissions" with "unclear dataset division into training/validation/test sets" or "minor architecture/model modifications and only slight increase in performance". Abstract max 250. Types: Full Length Article, Review, Letter, Discussion, Tutorial.

### 1.8 Journal of Biomedical Informatics (`j-biomed-inform`): VERIFIED
- JIF 5.9 (2025). Hybrid (APC USD 3,550).
- AI: §0.2 template, identical. The only other AI text is research-reporting guidance: "If your study includes generative artificial intelligence (AI)-driven chatbots used to summarize clinical evidence or provide health advice: please use the Chatbot Assessment Reporting Tool (CHART)".
- Answers: as Elsevier. Limits: "structured abstract (... with a total of <=300 words)", body "<=6000 words", figures plus tables <= 8. Methods journal: a paper must "evaluate its appropriateness in comparison to the current state-of-the-art (SoA) methods". "JBI publishes bioinformatics papers only if they deal with issues in translational (human) science". A Special Communication may "report on widely adopted biomedical informatics tools or standards (e.g., REDCap, FHIR, OMOP, openEHR)". Methodological reviews are by invitation only.

### 1.9 Genomics (`genomics`): VERIFIED
- JIF 3.6 (2025). **Full OA** (header "Open access"; APC USD 3,460).
- AI: §0.2 template, identical.
- Answers: as Elsevier. Desk rule: "Manuscripts analysing existing sequence data only are no longer suitable, unless adding new sequence data or a introducing a new algorithm for analysis. The algorithm must be made publicly available through a web page or as code." "Our goal is to accept only the top 25-30% of submitted manuscripts." Abstract max 250.

### 1.10 Gene (`gene`): VERIFIED
- JIF 2.7 (2025). Hybrid (APC USD 3,650).
- AI: §0.2 template, identical.
- Answers: as Elsevier.
  - "Computational approaches are welcome ... provided they are supported by appropriate experimental evidence or other compelling lines of validation."
  - Methodological papers: "Minor improvements to existing methods are not acceptable."
  - "The journal does not consider systematic reviews or meta-analyses."
  - Abstract max 250.

### 1.11 SoftwareX (`softwarex`): VERIFIED
- JIF 1.9 (2025). **Full OA** (APC USD 1,920).
- AI: §0.2 template, identical. Nothing AI-specific about code beyond the Elsevier FAQ (AI-written code is declared in Methods; AI code formatting goes in the AI declaration).
- Answers: as Elsevier. "A short descriptive paper of 4000-word limit" plus "An open-source software distribution with support material". The journal templates (Original software publication, Software update) are mandatory. Accepted code is copied to the journal's GitHub repository. Abstract max 250.

### 1.12 Genetics in Medicine (ACMG) (`genetics-in-medicine`): VERIFIED, **journal text stricter than Elsevier's**
- JIF 6.2 (2025). Hybrid (APC USD 5,500).
- AI: the guide does **not** use the 2026 template. It keeps Elsevier's 2023 "in scientific writing" wording (verbatim):
> "Where authors use generative artificial intelligence (AI) and AI-assisted technologies in the writing process, authors should: • Only use these technologies to improve readability and language, not to replace key researcher tasks such as interpreting data or drawing scientific conclusions."
> "Authors must disclose the use of generative AI and AI-assisted technologies in the writing process by adding a statement at the end of their manuscript in the core manuscript file, before the References list. The statement should be placed in a new section entitled 'Declaration of AI and AI-assisted technologies in the writing process'."
> "This declaration does not apply to the use of basic tools for checking grammar, spelling, references etc."
- Answers:
  - **Writing help:** limited to readability and language (`banned_drafting` in our scale). The text links "Elsevier's AI policy for authors", whose June 2026 version allows much more. The journal's own page is the safer reading; ask the office before relying on the newer policy.
  - **Disclosure:** the section above, before the References. Even language help beyond basic grammar or spelling tools must be declared.
  - **Limits:** Article 4,000 words, structured abstract of 200 words, 5 display items, 40 references. The table marks Article limits "enforced? No".
  - **Scope:** Mendelian randomization is "generally not within the scope"; "GWAS ... are generally low priority".

### 1.13 The International Journal of Biochemistry & Cell Biology (`int-j-biochem-cell-biol`): VERIFIED
- JIF 3.5 (2025). Hybrid (APC USD 3,570).
- AI: §0.2 template, identical.
- Answers: as Elsevier.
  - Research articles: "Up to 5,000 words".
  - Out of scope: "Computational/bioinformatic studies without clear significant novelty in analysis approach and/or experimental validation of the computed findings".
  - Abstract max 250.

---

## 2. Lancet Group journals (inherit `lancet`)

### 2.1 The Lancet Healthy Longevity (`lancet-healthy-longevity`): VERIFIED
- URLs:
  - https://www.thelancet.com/pb-assets/Lancet/authors/tlhl-info-for-authors.pdf (August 2026)
  - https://www.thelancet.com/lanhl/about
  - https://www.thelancet.com/submission-guidelines?journal=lanhl
- JIF 20.5 (About page: "ranks second among 72 geriatrics and gerontology journals (2025 Journal Citation Reports®, Clarivate 2026)"; the value has no year label of its own). Full OA: "The Lancet Healthy Longevity is a gold open access journal."
- AI: the §0.4 text, verbatim the same as The Lancet's. The content-type paragraph covers "Blue section content, which includes Comments and Correspondence" (grammar and spelling only); there is no World Report or Perspectives ban in this PDF.
- Answers:
  - As `lancet`: version, prompts where applicable, a submission declaration, and editors judging appropriateness.
  - Articles "up to 3500 words (4500 for randomised controlled trials) with 30 references", abstract "not exceeding 250 words" in five paragraphs, plus a Research in context panel.
  - "For any Review, Health Policy, Viewpoint, or Comment, the use of medical writers is not permitted unless ... their role is purely technical (eg, editing a first draft for language and grammar)". That rule is about human writers; the PDF does not apply it to AI.

### 2.2 eBioMedicine (`ebiomedicine`): VERIFIED
- URLs:
  - https://www.thelancet.com/pb-assets/Lancet/authors/ebm-info-for-authors.pdf
  - https://www.thelancet.com/ebiom/about
- JIF 11.2 (About page cites "2025 Journal Citation Reports®, Clarivate 2026" for its ranking). Full OA ("gold open access journal").
- AI: the §0.4 text, verbatim the same, including the Comments and Correspondence paragraph.
- Answers: as `lancet`. Abstract max 250 words, five paragraphs. The PDF gives no word limit for Articles. Reviews are up to 4,500 words.

---

## 3. Cell Press journals (inherit `cell-press`)

URL pattern: `https://www.cell.com/<journal>/information-for-authors/journal-policies`; article types at `/information-for-authors/article-types`. JIF and OA come from ScienceDirect insights pages, since cell.com showed no Impact Factor on the pages read. Page date: none shown (© 2026). The AI section is identical to Cell's (§0.3) unless stated otherwise.

### 3.1 Cell (`cell`): VERIFIED
- JIF 45.1 (2025). Hybrid (APC USD 11,400).
- AI: §0.3, read on Cell's own page.
- Answers: as Cell Press. Research articles "must be under 7,000" words (excluding STAR Methods and references) with at most 7 figures or tables; Summary "no more than 150 words". Resource: "significant technical advances and/or major informational databases". Theory articles are also offered.

### 3.2 Cell Metabolism (`cell-metabolism`): VERIFIED
- JIF 37.0 (2025). Hybrid (APC USD 10,400).
- AI: identical to Cell.
- Answers: as Cell Press. Research and Clinical and translational reports "under 7,000" words. The "Technology" format covers "new reagents, methods, tools, and other technologies".

### 3.3 Cell Systems (`cell-systems`): VERIFIED
- JIF 7.5 (2025). Hybrid (APC USD 9,350).
- AI: identical to Cell.
- Answers: as Cell Press. Formats are limited by display items, not words. "Methods provide access to new biological problems ... They contain up to 7 figures or tables."

### 3.4 Cell Reports (`cell-reports`): VERIFIED
- JIF 7.7 (2025). Full OA (APC USD 5,790, geographical pricing).
- AI: identical to Cell.
- Answers: as Cell Press. Research articles and Resources up to 7,000 words; Reports up to 4,000. "Cell Reports requires that all resources provide new biological insight as a demonstration of utility of the resource."

### 3.5 Cell Reports Methods (`cell-reports-methods`): VERIFIED
- JIF 5.8 (2025). Full OA (APC USD 4,970).
- AI: identical to Cell.
- Answers: as Cell Press. "The primary criterion for publication in Cell Reports Methods is a robust, reproducible method". Articles: "under 7,000 words", with "presentation of the method, a comparison of the method with related methods when appropriate, and validation". There is no software-specific article type.

### 3.6 American Journal of Human Genetics (Cell Press / ASHG partner) (`ajhg`): VERIFIED, **journal text stricter than Cell Press's**
- URL: https://www.cell.com/ajhg/authors (the `/information-for-authors/journal-policies` path returns "This page does not exist"). JIF 7.7 (2025). Hybrid (APC USD 5,150).
- AI (verbatim, AJHG's own section "Declaration of generative AI in scientific writing"):
> "The below guidance only refers to the writing process, and not to the use of AI tools to analyze and draw insights from data as part of the research process."
> "Where authors use generative artificial intelligence (AI) and AI-assisted technologies in the writing process, authors should only use these technologies to improve readability and language."
> "Authors must disclose the use of generative AI and AI-assisted technologies in the writing process by adding a statement at the end of their manuscript in the core manuscript file, before the references list."
> "This declaration does not apply to the use of basic tools for checking grammar, spelling, references etc."
- Answers:
  - **Writing help:** readability and language only (`banned_drafting`).
  - **Disclosure:** before the references, not after Declaration of interests as at Cell Press journals.
  - **Reviewers:** no journal page was read; the Cell Press reviewer page (banned) is inherited.
  - **Limits:** abstract 250 words; Reports ~3,600 words; Research Letters 800 words.

### 3.7 Human Genetics and Genomics Advances (`hgg-advances`): VERIFIED
- URL: https://www.cell.com/hgg-advances/authors. JIF 3.1 (2025). Full OA (APC USD 3,300).
- AI: the same text as AJHG, word for word, with the section title ending "manuscript preparation process."
- Answers: as AJHG. Abstract 250 words; Brief communications max 2,500 words; Reports 3,500–4,000 words.

### 3.8 Trends in Genetics (`trends-genetics`): VERIFIED, **journal text stricter than Cell Press's**
- URL: https://www.cell.com/trends/genetics/authors. The text sits in a collapsed tab and was read from the dumped HTML. JIF 12.9 (2025). Hybrid (APC USD 7,030).
- AI (verbatim):
> "Authors must declare the use of generative AI in scientific writing upon submission of the paper. The below guidance only refers to the writing process, and not to the use of AI tools to analyze and draw insights from data as part of the research process."
> "Generative AI and AI-assisted technologies should only be used in the writing process to improve the readability and language of the manuscript."
> "Title of new section: Declaration of generative AI and AI-assisted technologies in the writing process." (placed "after the "declaration of interests" section")
> "this journal does not currently allow the use of Generative AI or AI-assisted technologies such as ChatGPT or similar services by reviewers or editors in the peer review and manuscript evaluation process."
- Answers:
  - **Writing help:** readability and language only (`banned_drafting`).
  - **Disclosure:** after Declaration of interests.
  - **Reviewers:** banned.
  - **Fit:** "All articles are commissioned"; "TiG is not a primary publication and thus cannot consider manuscripts that rely on unpublished data." Reviews run 3,000–3,500 words with a 100–120-word abstract.

---

## 4. Re-check of existing venues.yaml entries

| Entry | AI text | Differences from venues.yaml |
|---|---|---|
| `patterns` | journal-policies AI section identical to Cell's (diffed). | (1) `jif: 7.4` is **not on any publisher page read**: the ScienceDirect insights page has no metrics, and the cell.com home shows only editorial-speed metrics. Set it to null unless the integrator has another source. (2) `software_article: false` is wrong. The Resource article type "describe[s] a tool, project, or other major data science resource ... Strong candidates include workflows, software, platforms, repositories, frameworks, services, or datasets." (3) Full OA (APC USD 4,900). The `url` still points to Cell's journal-policies page; Patterns' own page is `/patterns/information-for-authors/journal-policies` (same text). |
| `cell-genomics` | identical to Cell's. | JIF on ScienceDirect is **8.4** (2025 JCR), not 9.0. Full OA ("a Cell Press fully open access journal"). Its "Technology" format covers "new experimental or computational methods and other technologies", so `software_article: true` fits. Articles are under 8,000 words. |
| `iscience` | journal-policies AI section identical to Cell's. | JIF on ScienceDirect is **4.5** (2025 JCR), not 4.1. URL unchanged. Full OA (APC USD 3,240). Cosmetic: the iScience authors-page sidebar still titles the section "Declaration of generative AI in scientific writing" (the old name), while the policy page and the manuscript checklist use the new title. |

The `cell-press` publisher entry now carries the values the old `patterns` entry held. I re-checked them against the live pages; the only addition is `reviewer_ai: banned`, from the Cell Press reviewers page. Suggested replacement entries for all three (inheriting `cell-press`) were merged into `../venues.yaml` on 2026-10-15.

---

## 5. Cross-venue notes

- **Three generations of Elsevier AI text are live at once:**
  - **Elsevier June 2026 policy and 2026 Guide template:** drafting support allowed with a declaration before the references.
  - **Cell Press:** the same allowance, with the declaration after Declaration of interests and stricter image rules.
  - **The 2023 wording** at Genetics in Medicine, AJHG, HGG Advances and Trends in Genetics: "only ... improve readability and language". For an AI-assisted manuscript these four journals are as restrictive as ISCB, at least on paper, and their own pages contradict the Elsevier policy they link to.
- **Lancet Group:** the only cluster member that asks for prompts in the paper, asks at submission, and says editors may judge a declared use inappropriate (`disclosure_neutral: false`).
- **No AI-text detector named anywhere in the cluster.** Screening named: Elsevier AI "research integrity checks" (unspecified); Crossref Similarity Check and image screening (Cell Press); CrossCheck (Lancet editors; KeAi, with desk rejection for high similarity).
- **Reviewers:** every page read bars uploading manuscripts to AI tools. The Lancet and Trends in Genetics bar reviewer AI use altogether.
- **Hallucinated references:** Elsevier's FAQ is the only explicit penalty line ("may lead to rejection"). The Lancet bans AI for generating, completing or verifying references only in Comments and Correspondence.

## 6. Not read or not found

- **TMA (KeAi):** no AI policy text on any TMA or KeAi page (NOT FOUND); the Elsevier default is inferred.
- **No JIF on the publisher page:** Translational Medicine of Aging, Computers in Biology and Medicine (WoS coverage discontinued) and Patterns.
- **AJHG and HGG Advances:** no journal-specific reviewer AI text was read; the Cell Press reviewers page was used.
- **The Lancet's 30 November 2024 editorial** "Generative AI: ensuring transparency and emphasising human intelligence and accountability", linked from the peer-review page, was not opened.
- **Word limits** for Cell Metabolism, Cell Systems, Cell Reports, Cell Reports Methods, Cell Genomics and iScience summaries were not read; only Cell's revise-manuscript page (Summary ≤150 words) was opened.
