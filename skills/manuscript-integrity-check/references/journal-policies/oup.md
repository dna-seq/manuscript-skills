# OUP cluster: AI policies of Oxford University Press journals (checked 2026-10-15)

Entries in `../venues.yaml`. Publisher-level background is in `publisher-policies.md` §2; this file only adds what was read today.

## How the pages were read

- **academic.oup.com** blocks headless Chrome (Cloudflare "Performing security verification"), curl and the r.jina.ai reader. Two routes worked:
  - **WebFetch**: gets through, but returns quoted fragments of at most 125 characters, and on long pages (OUP pages carry 3–4 MB of HTML) it truncates. Quotes marked *(WebFetch)* are such fragments; "..." joins two fragments of one sentence.
  - **Wayback snapshots** (`web.archive.org/web/<ts>id_/URL`, gunzipped, `w3m -dump`): full text. Quotes marked *(Wayback YYYY-MM-DD)* are exact.
- **transition.iscb.org**: read in headless Chrome (`--dump-dom`, then `w3m`); exact text.
- JIFs: the "2025 Impact Factor" figure in the metrics block of each journal's Oxford Academic home page (WebFetch, 2026-10-15). For MBE, Innovation in Aging, GBE and Bioinformatics the block was re-read word for word to rule out a summarising error.
- No OUP journal page shows a "last updated" date. Only the OUP policy (13 July 2026) and the ISCB page (3 April 2025) are dated.
- Page copies are in `../pages/oup/` (`wb_*.txt` snapshots, `iscb.html`).

---

## Publisher defaults

### `oup`: OUP "Policy on AI Use & Disclosure for OUP Journals Authors": VERIFIED (WebFetch)

- URL: https://academic.oup.com/pages/for-authors/journals/preparing-and-submitting-your-manuscript/ai-principles-for-oxford-journals/policy-on-ai-use-and-disclosure-for-oxford-journals-authors
- Re-checked today; unchanged from `publisher-policies.md` §2.1. Date: "_Policy last updated on: 13 July 2026_".
- Precedence and journal variation *(WebFetch)*: "individual journals may have custom requirements, in addition to those stated here"; "authors should follow the journal’s specific guidance."; "Please visit the journal’s Author Guidelines page to check for journal specific exceptions to the policy"; "You will be required to assert upon submission of your article in your journal’s submission system".
- Consequences, under the heading "Consequences of non-disclosure" *(WebFetch)*: "Each journal retains editorial discretion in determining whether submitted content is appropriate for publication." "Transparent disclosure of AI use supports informed editorial judgment and contributes to the integrity" ... "and reliability of the scholarly record." "Pre-publication: where disclosed use of Gen AI Tools does not align with journal policy, authors will be informed" ... "of the next steps, which may include being asked to revise their manuscript accordingly." "Failure to disclose use of Gen AI Tools may be grounds for rejection."
- Standards cited: "STM Recommendations for a Classification of AI Use" (links the STM PDF) and "industry standards such as the Committee on Publication Ethics (COPE)". The words "Vancouver" and "Global Reporting Standard" do not appear on the policy page. Only the 10 September 2026 announcement (https://corp.oup.com/news/supporting-researchers-to-disclose-ai-use-with-confidence/) says "As efforts continue to develop a global reporting standard for AI disclosure in research". `publisher-policies.md` §1.6 says OUP's policy says it will follow that standard. Strictly, it is the news release that says so, not the policy.
- Not on the page: "peer review", "reviewers", "confidential", "detection", "screen" (WebFetch word check). The parent "AI Principles for OUP Journals" page (no date) lists five principles and says they "underpin role-specific guidance for authors, reviewers, and editors", but links no reviewer policy. I found no OUP-wide reviewer AI policy (two web searches): `reviewer_ai: null`.
- The same announcement reports: "With 44% of researchers concerned that disclosing their use of AI will negatively impact how others view their work".

**Answers**
1. **Writing help:** disclose. Exempt: "Improving clarity of language (e.g. spelling or grammar correction)" and "Formatting references to comply with journal style requirements". Substantial editing or rewriting, translation and code generation are permitted with disclosure.
2. **Disclosure:** cover letter + Acknowledgements (+ Methodology if integral). Give the tool and version, how it was used, and the author's oversight; dates and sections are recommended. Update it at each revision.
3. **Prompts:** not mentioned.
4. **Screening:** the policy names none. OUP journal pages carry the same paragraph: iThenticate, plus "Manuscripts may also be screened, including with services provided by third parties, to help detect integrity issues such as inappropriate image alteration and papermill activity" (hence `integrity_signals`). NAR adds ScholarOne Unusual Activity Detection and a "third-party service that evaluates journal trust and integrity".
5. **Penalties:** rejection for non-disclosure; correction or retraction.
6. **Disclosure neutral:** silent (`null`). Rejection is tied to non-disclosure. A disclosed use that breaks journal policy leads to "next steps" such as revision. The page never says that a compliant disclosed use is neutral.

### `iscb`: ISCB Policy for Acceptable Use of Large Language Models: VERIFIED (Chrome)

- URL: https://transition.iscb.org/iscb-policy-statements/iscb-policy-for-acceptable-use-of-large-language-models (the plain iscb.org URL 404s, per `publisher-policies.md`). Date: "Updated 3 April 2025".
- Scope, verbatim: "The ISCB Acceptable Use of Large Language Models Policy is applied to all scientific research submissions for ISCB Conferences, as well as research submissions to the ISCB/OUP Bioinformatic Advances journal. OUP has also accepted the use of the policy for research submissions to OUP Bioinformatics journal." "ISCB strongly encourages its affiliated groups and affiliated conferences to apply the Policy to scientific research submissions for their individual conferences and journals."
- Unacceptable, verbatim: "It is not acceptable to use LLMs or related technologies to draft paper sections. In essence, papers MUST be written by humans." "It is not acceptable to use LLMs or related technologies to carry out reviewing activities, such as scientific peer reviews and promotion and tenure reviews. ... review processes are in general confidential and should not be shared with third parties, including commercial LLM providers." "LLMs cannot be listed as authors as they do not fulfill the requirements of authorship as laid out in the ICMJE guidelines."
- Acceptable, verbatim: "As an algorithmic technique for research study in your research e.g. LLMs for protein structure prediction"; "As an aid to correct written text (spell checkers, grammar checkers)"; "As an aid to language translation, however, the human is responsible for the accuracy of the final text"; "As an evaluation technique (to assist in finding inconsistencies or other anomalies)"; "It is permissible to include LLM generated text snippets as examples in research papers where appropriate, but these MUST be clearly labeled and their use explained."; "Assist in code writing, however, the human is responsible for the code."; "Create documentation for code, however, the human is responsible for the correct documentation."; "To discover background information on a topic, subject to verification from trusted sources."
- Confidentiality: "Note that acceptable use cases only apply where confidentiality is not an issue."
- Detection: "At present, we do not intend to systematically detect usage of these models, but we will investigate reported instances on a case-by-case basis."
- **The ISCB page and the OUP journal pages word the policy differently.**
  - ISCB page: "draft paper sections".
  - Bioinformatics, Bioinformatics Advances and BiB pages: "draft papers (including but not limited to text, figures, tables, and references) from a prompt text. In essence, papers must be written by researchers."
  - The ISCB page states no disclosure duty. The journal versions add "Any acceptable use of LLMs or related technologies to produce, or help to produce, part of the text, figures or other contents of the paper should be explicitly declared and documented with sufficient details in the supplementary materials."
  - The ISCB page lists "background information"; the journal versions drop it.
  - The Bioinformatics Advances page's unacceptable list has no reviewer bullet; Bioinformatics has one. Reviewers at Bioinformatics Advances are covered by the ISCB page itself.
  - The `iscb` entry records the journal-printed version (stricter wording, supplement documentation) and `inherits: oup` for the OUP-only fields (penalties, revision updates). For an ISCB conference, ignore the OUP-derived fields.

**Answers**
1. **Writing help:** `banned_drafting`. Only correction, translation, code and documentation aids are named.
2. **Disclosure:** the ISCB page itself asks only that example snippets be labelled. The journal versions require supplementary documentation, plus OUP's cover letter and Methods or Acknowledgements.
3. **Prompts:** no.
4. **Screening:** no systematic detection; reported cases are investigated.
5. **Reviewers:** banned.
6. **Disclosure neutral:** silent.

---

## Journals

### Bioinformatics Advances (`bioinformatics-advances`): VERIFIED; adopts ISCB

- URLs: https://academic.oup.com/bioinformaticsadvances/pages/author-guidelines (live via WebFetch; full text via Wayback 2026-02-16). Home page: "2.6 / 2025 Impact Factor"; "a fully open access, peer-reviewed, and interdisciplinary journal"; "published jointly by Oxford University Press and by the International Society for Computational Biology."
- Verbatim *(Wayback 2026-02-16; the live WebFetch fragments match)*: "Policy for acceptable use of large language models (LLMS)". "The International Society for Computational Biology has created an acceptable use policy for LLMs, which the journal follows." The acceptable/unacceptable lists match the Bioinformatics version, including "Any acceptable use of LLMs or related technologies to produce, or help to produce, part of the text, figures or other contents of the paper should be explicitly declared and documented with sufficient details in the supplementary materials." and "It is not acceptable to use LLMs or related technologies to draft papers (including but not limited to text, figures, tables, and references) from a prompt text. In essence, papers must be written by researchers."
- It also prints the OUP clause, here without "or images" and "translation": "The use of AI (for example, to help generate content, write code, or process data) should be disclosed both in cover letters to editors and in the Methods or Acknowledgements section of manuscripts." "If your usage of LLMs is not covered by any of these use cases, then please contact the Editor of the journal or Editorial Office."
- Answer to the task question: **yes**. The ISCB page says the policy applies to Bioinformatics Advances, and the journal page says "which the journal follows".
- Article types *(Wayback)*:
  - Original Article "up to 8 pages", "abstract—maximum word count: 200"
  - Application Note "up to 4 pages"
  - Scientific Data "up to 4 pages"
  - Discovery Notes "up to 6 pages"
  - Review, Opinion, Perspective, Letter to the Editor, Feature
- Screening: "Manuscripts may be screened using iThenticate to help detect publication misconduct including plagiarism and redundant publication."

**Answers**
1. **Writing help:** banned drafting (ISCB).
2. **Disclosure:** cover letter + Methods or Acknowledgements + supplementary documentation.
3. **Prompts:** no.
4. **Screening:** iThenticate plus OUP third-party integrity screening; ISCB does not systematically detect AI use.
5. **Penalties:** OUP's.
6. **Reviewers:** banned (ISCB).
7. **Extra work:** supplementary documentation of LLM help.

### NAR Genomics and Bioinformatics (`nar-genomics-bioinformatics`): VERIFIED (WebFetch)

- URLs: https://academic.oup.com/nargab/pages/author-guidelines; https://academic.oup.com/nargab/pages/scope_and_criteria. Home: "3.0 / 2025 Impact Factor"; "fully open access journal". No Wayback copy since 2025.
- AI text (the standard OUP clause, under Authorship) *(WebFetch)*: "Natural language processing tools driven by artificial intelligence (AI) do not qualify as authors" ... "and the Journal will screen for them in author lists." "The use of AI (for example, to help generate content or images, write code, process data, or for translation)" ... "should be disclosed both in cover letters to editors and in the Methods or Acknowledgements section of manuscripts." "Please see the COPE position statement on Authorship and AI". No ISCB text. No link to the OUP policy page.
- Scope page *(WebFetch)*: "Application Notes": "relatively brief communications - max 3000 words, 3 figures/tables or equivalent and 30 references"; Standard Papers, Methods Papers, "Methods and Benchmark Surveys", Opinion Articles. "Manuscripts will only be considered for review if the new software is released as open-source". The page also says it "welcomes the development or application of artificial intelligence approaches" (about research, not about writing).

**Answers:** the OUP default, with nothing added. Disclose in the cover letter and in Methods or Acknowledgements. Prompts are not asked for. Screening: iThenticate and plagiarism software.

### Genomics, Proteomics & Bioinformatics (`gpb`): VERIFIED (WebFetch)

- URL: https://academic.oup.com/gpb/pages/general-instructions (the home page's "Author Guidelines" link; `/author-guidelines` is a 404).
- Home: "7.2 / 2025 Impact Factor". It names the Beijing Institute of Genomics, CAS / China National Center for Bioinformation and the Genetics Society of China. Submission is via Editorial Manager.
- Instructions: "The Journal is fully open access, meaning all papers in the Journal are published under an open access license."
- **Is GPB on OUP? Yes.** It is on Oxford Academic, with OUP's open-access and Read and Publish sections.
- AI text, the only one on the page, under Publication and Research Ethics > Authorship *(WebFetch)*: "Neither symbolic figures such as Camille Noûs nor natural language processing tools driven by artificial intelligence (AI)" ... "such as ChatGPT qualify as authors, and OUP will screen for them in author lists." There is no disclosure sentence and no link to the OUP policy, so the OUP default governs disclosure. The page has no AI section heading (a full heading list was taken; the tail of the page was truncated after "Charges").
- Article types and limits *(WebFetch)*:
  - Research article under 6000 words; Protocol under 6000 words
  - Method and Application note 4–6 pages
  - Database and Webserver under 3000 words
  - Review 5000–8000 words
- Screening: "Manuscripts submitted to the Journal may be screened with plagiarism-detection software." "Manuscripts may also be screened, including with services provided by third parties,".

**Answers:** the OUP default applies. The page itself only forbids AI authorship.

### Briefings in Functional Genomics (`briefings-functional-genomics`): VERIFIED (WebFetch + Wayback 2026-04-20)

- URL: https://academic.oup.com/bfg/pages/author-guidelines.
- Home: "3.2 / 2025 Impact Factor"; "As of January 1, 2025, _Briefings in Functional Genomics_ is fully open access."
- AI text *(Wayback 2026-04-20, matches live)*: the standard OUP clause, ending "Please see the COPE position statement on Authorship and AI tools for more details."
- **No ISCB text**, unlike its sibling Briefings in Bioinformatics.
- Article types: "primary research and authoritative reviews", plus protocol articles. No word limits.

**Answers:** the OUP default.

### NAR Cancer (`nar-cancer`): VERIFIED (WebFetch + Wayback 2026-03-27)

- URL: https://academic.oup.com/narcancer/pages/author-guidelines. Home: "4.6 / 2025 Impact Factor"; "a fully open access journal".
- AI text *(Wayback 2026-03-27, matches live)*: the heading "AI-powered language processing models", then the standard OUP clause, word for word as in NAR.
- Types: "NAR Cancer publishes Standard, Review, and Cancer Data Resource articles." Cancer Data Resources "describe queryable databases, web-based services, or stand-alone software implementations ... Authors must commit to maintaining availability of the Resource under the same URL for a minimum of 5 years."
- Screening: as NAR (iThenticate, third-party integrity screening, "a third-party service that evaluates journal trust and integrity").

**Answers:** the OUP default.

### GENETICS (`genetics`): VERIFIED (WebFetch live + Wayback 2026-02-07); journal-specific rule

- URLs: https://academic.oup.com/genetics/pages/author-guidelines; reviewer page https://academic.oup.com/genetics/pages/guidelines-for-reviewers. Home: "6.5 / 2025 Impact Factor". Hybrid: "The Journal offers the option of publishing under either a non-open access (standard) license" (WebFetch).
- Authorship (standard OUP clause) *(Wayback)*: "Natural language processing tools driven by artificial intelligence (AI) do not qualify as authors, and the Journal will screen for them in author lists. The use of AI (for example, to help generate content or images, write code, process data, or for translation) should be disclosed both in cover letters to editors and in the Methods or Acknowledgements section of manuscripts."
- **Materials and methods, GSA-specific** *(Wayback 2026-02-07; live WebFetch confirms the first and last fragments)*: "If you have used a Large Language Models (LLMs), such as ChatGPT, please provide full technical specifications of the LLM used (name, version, model, source) and method of application (query structure, syntax). Authors are responsible for the work performed by a LLM in the paper (including the accuracy of what is presented, and the absence of plagiarism) and for appropriate attribution of all sources (including for material produced by the LLM)."
- Reviewers *(WebFetch)*: "Please note: The use of Large Language Models (LLMs), such as ChatGPT, to write your review is prohibited." ... "uploading a manuscript or associated files or manuscript information to a LLM will violate the confidentiality agreement".
- Types: Investigations ("There are no length restrictions"); Brief Investigations ("should not exceed 3000 words"); Knowledgebase and Database Resources; Reviews; Perspectives; Primers; Letters. "Abstracts have a maximum length of 250 words" (WebFetch). Scope includes "Knowledgebases, databases, software and computational resources".

**Answers**
1. **Writing help:** the OUP default (disclose).
2. **Disclosure:** cover letter + Methods or Acknowledgements. Any LLM use also needs a technical specification in Methods.
3. **Prompts:** **required** in the CSE form "method of application (query structure, syntax)". That is how the prompts were built, not necessarily every prompt word for word (`prompts: required`).
4. **Screening:** iThenticate plus third-party integrity screening.
5. **Reviewers:** banned.

### G3: Genes|Genomes|Genetics (`g3`): VERIFIED (WebFetch live + Wayback 2026-04-11)

- URL: https://academic.oup.com/g3journal/pages/author-guidelines. Home: "2.4 / 2025 Impact Factor"; "G3 is the open access (OA) journal from the Genetics Society of America (GSA)."
- Same Authorship clause as GENETICS (live, WebFetch). The LLM Methods paragraph is word for word the GENETICS one *(Wayback 2026-04-11)*. The live WebFetch view ends in "Read and Publish", before the Methods guidance, so that paragraph was not seen live.
- Reviewers *(WebFetch, live)*: "Please note: The use of Large Language Models (LLMs), such as ChatGPT, to write your review is prohibited." "Additionally, uploading a manuscript or associated files or manuscript information to a LLM will violate" ... "the confidentiality agreement in place for authors and the journal."
- Types: "Investigations and Reports", which cover Genome Reports, Genetic Screen Reports, Molecular Method Reports, Omics Reports and Software and Workflow Reports. Original research is published "regardless of length".

**Answers:** as GENETICS (prompts in query-structure form; reviewers banned).

### Molecular Biology and Evolution (`mbe`): VERIFIED (WebFetch + Wayback 2026-03-09)

- URL: https://academic.oup.com/mbe/pages/author-guidelines. Home metrics block, word for word: "6.4 2025 Impact Factor", "14.7 2025 5 Year Impact Factor". Instructions: "is a peer-reviewed fully open access journal publishing 12 issues per year online".
- AI text: only the standard OUP clause, under "Publication and research ethics → Authorship". WebFetch confirms there is no "strongly discouraged" or "proofreading" wording, unlike GBE.
- Types *(Wayback)*: Discoveries, Methods, Resources ("Resources describe significant advances in widely-used software tools and databases for molecular evolutionary studies ... All research resources must be made available for general usage at the time of publication."), Reviews, Protocols, Brief Communications, Perspectives. No word limits found.

**Answers:** the OUP default.

### Genome Biology and Evolution (`gbe`): VERIFIED (WebFetch + Wayback 2026-03-30); journal-specific, stricter than OUP

- URL: https://academic.oup.com/gbe/pages/General_Instructions (`/author-guidelines` is a 404). Home metrics, word for word: "Impact Factor: 3.3 (20 out of 52 in Evolutionary Biology)", "5 Year Impact Factor: 3.5". **No year is shown** (`jif_year: null`). Instructions: "Genome Biology and Evolution is a peer reviewed fully open access journal publishing 12 issues per year online."
- Verbatim *(Wayback 2026-03-30; live WebFetch fragments match: "strongly discouraged", "Any use of AI, including for proofreading, should be disclosed both in the cover letter")*, under "Publication Ethics and the Use of AI" > "Artificial Intelligence":
  > "The use of AI (e.g. to create content or images, generate complex code, process data or modify language) is strongly discouraged. Any use of AI, including for proofreading, should be disclosed both in the cover letter and in the Methods and/or Acknowledgements section of the manuscript. Natural language processing tools driven by artificial intelligence (AI) do not qualify as authors, and the Journal will screen for them in author lists. Please see the COPE position statement on Authorship and AI for more details."
- Limits (Table 1, WebFetch):
  - Articles and Methods: 10,000 words, abstract 250 words, significance statement 150 words
  - Genome Resources: 2,500 words
  - Letters and Perspectives: 2,500 words

**Answers**
1. **Writing help:** `disclose_all`. Even proofreading is disclosed, and all AI use, language modification included, is "strongly discouraged".
2. **Disclosure:** cover letter + Methods and/or Acknowledgements.
3. **Prompts:** no.
4. **Screening:** third-party integrity screening (papermill, images).
5. **Disclosure neutral:** set to **false** as an interpretation. The page does not say a disclosure counts against the paper, but it strongly discourages the very uses it asks authors to declare.

### DNA Research (`dna-research`): PARTIAL

- URL: https://academic.oup.com/dnaresearch/pages/Instructions_To_Authors (`/author-guidelines` is a 404).
- Home: "2.8 / 2025 Impact Factor"; "fully open access journal"; official journal of the Kazusa DNA Research Institute.
- Live page via WebFetch: 15,883 characters. The table of contents lists "Ethics" and "Misconduct", but those sections are not in the text WebFetch receives. No AI text was seen.
- Full-text Wayback snapshot 2026-03-31: **no AI, LLM or ChatGPT text at all**. The only AI hit is the site's "AI Discovery Assistant". Screening there: "Manuscripts submitted may be screened with iThenticate anti-plagiarism software" and "Manuscripts may also be screened, including with services provided by third parties, to help detect integrity issues such as inappropriate image alteration and papermill activity." Misconduct "will lead to immediate rejection".
- Limits: "Manuscripts are limited to 10 typeset pages in principle (approximately 7,000 words or 30 manuscript pages)"; abstract "no more than 200 words".
- Types: Research Article, Resource Article: Genomes Explored, Review, Meeting Report.

**Answers:** no journal AI rule, so the OUP default applies by inference. PARTIAL because the snapshot predates the July 2026 OUP policy and the live Ethics section is unreadable.

### Human Molecular Genetics (`hmg`): VERIFIED (WebFetch + Wayback 2026-08-03)

- URLs: https://academic.oup.com/hmg/pages/author-guidelines; reviewer page https://academic.oup.com/hmg/pages/reviewer-instructions.
- Home: "3.1 / 2025 Impact Factor"; "HMG provides open access options for authors". Hybrid: "The Journal offers the option of publishing under either a non-open access (standard) license" ... "or an open access (Creative Commons) license."
- AI text: the standard OUP clause only. The page also offers an AI tool: "In partnership with Cactus, we are offering authors free usage of their Paperpal Preflight tool pre-submission. This is an AI-driven tool that performs technical checks tailored to Human Molecular Genetics. ... Please note that this is not mandatory and suggested corrections are optional." (Wayback)
- Reviewers *(WebFetch)*: "Use of AI tools, including LLMs, to prepare your review is not allowed". "Also, reviewers should not use AI tools to screen manuscripts, even if they suspect text/images were generated by AI."
- Limits *(WebFetch)*: Original Articles "unstructured abstract of no more than 250 words"; "The main text should be no more than 4000 words." Research Letters 1,000 words.

**Answers:** the OUP default. Reviewers are banned from AI. The journal itself offers an AI pre-submission checker.

### Human Reproduction (`human-reproduction`): VERIFIED (WebFetch); no AI text

- URLs: https://academic.oup.com/humrep/pages/General_Instructions (hub), https://academic.oup.com/humrep/pages/Manuscript_Preparation, https://academic.oup.com/humrep/pages/Policies. (`/author-guidelines` is a 404.) Home: "2025 Impact Factor of 6.8".
- WebFetch read all three pages. **None has an AI, LLM, ChatGPT or NLP sentence**, not even the OUP authorship clause. The Authorship and Disclosures subsections were quoted and checked.
- Hybrid: "_Human Reproduction_ offers the option of publishing under either a standard licence or an open access licence."
- Screening: "A proportion of manuscripts submitted to the ESHRE Journals are routinely screened with iThenticate anti-plagiarism software"; "Prior to final acceptance any manuscript that has not already been screened will be put through iThenticate".
- Types: Original Articles, Mini-reviews, Opinions and Debates, Case Reports, Letters to the Editor. "Papers should be of a length appropriate for the amount of information they contain."
- A web search for an ESHRE-level AI policy found nothing (NOT FOUND).

**Answers:** no journal rule. The OUP default applies (OUP's policy covers all its journals and requires the submission assertion). The page does not link to it.

### Molecular Human Reproduction (`mol-hum-reprod`): VERIFIED (WebFetch); no AI text

- URLs: https://academic.oup.com/molehr/pages/General_Instructions (hub), `/Instructions_For_Authors`, `/To_Accompany_Manuscript_Submission`, `/Processes_And_Policies`, `/Policies`.
- Home: "4.2 / 2025 Impact Factor"; "authors from participating institutions can publish open access". `oa: hybrid` is my inference from that and from the ESHRE licence model ("authors assign a 'licence to publish' to ESHRE").
- **No AI sentence on any of the five pages.**
- Screening: "Manuscripts submitted to the Journal may be screened with iThenticate plagiarism-detection software."; "Manuscripts may also be screened, including with services provided by third parties"; "All manuscripts accepted by MHR are screened with iThenticate anti-plagiarism software".
- Types: Original Research Articles, Concise Communications, Positions and Proceedings, Reviews, Correspondence. No word limits.

**Answers:** as Human Reproduction. The OUP default applies.

### The Journals of Gerontology, Series A (`j-gerontol-a`): VERIFIED (WebFetch); GSA's own AI section

- URLs: hub https://academic.oup.com/biomedgerontology/pages/General_Instructions; Biological Sciences https://academic.oup.com/biomedgerontology/pages/General_Instructions_1; Medical Sciences https://academic.oup.com/biomedgerontology/pages/General_Instructions_2.
- Home: "4.6 / 2025 Impact Factor"; "Published on behalf of The Gerontological Society of America".
- Hybrid: "offers the option of publishing under either a standard license or an open access license."
- Verbatim fragments, under "Additional Policies and Considerations > Authorship > Artificial Intelligence (AI)-Assisted Technology" *(WebFetch, Biological Sciences page; the Medical Sciences page has the same sentences)*:
  - "Following COPE and the International Committee of Medical Journal Editors"
  - "The use of artificial intelligence (AI) tools cannot meet the requirements for authorship" ... "as they cannot take responsibility for the submitted work."
  - "Authors who use AI tools in the writing of a manuscript, production of images or graphical elements of the paper" ... "must be transparent in disclosing in the Materials and Methods (or similar section) of the paper" ... "how the AI tool was used and which tool was used."
  - "Authors are fully responsible for the content of their manuscript, even those parts produced by an AI tool" ... "and are thus liable for any breach of publication ethics."
  - "Thereby, authors are required to disclose whether they used artificial intelligence (AI)-assisted technologies" ... "(such as Large Language Models [LLMs], chatbots, or image creators) in the production of submitted work" ... "in the Methods (or similar section) of the paper, which AI tool was used, and how the AI tool was used."
  - "Authors should not list AI and AI-assisted technologies as an author or co-author, nor cite AI as an author."
  - "Authors should be able to assert that there is no plagiarism in their paper" ... "including in text and images produced by the AI." "Humans must ensure there is appropriate attribution of all quoted material, including full citations."
- Limits *(WebFetch)*:
  - Biological Sciences Original Article "The maximum allowable word count is 5800 words."; abstract "250 words, (unstructured)"
  - Medical Sciences Research Article "The maximum allowable word count is 5200 words." "The word count includes the title page, abstract and main text."; structured 250-word abstract
  - "The abstract limit of 250 words is not negotiable."
- Reviewer AI: not looked for (null).

**Answers**
1. **Writing help:** `disclose_all`. The text covers any use "in the writing of a manuscript" and states no language-editing exemption. (OUP's default exempts spelling and grammar, and OUP says journal guidance wins where they differ.)
2. **Disclosure:** Methods (or similar section): which tool, and how it was used. The page asks for neither a cover-letter nor an Acknowledgements statement. Adding OUP's is harmless.
3. **Prompts:** no.
4. **Screening:** third-party integrity screening.
5. **Penalties:** none of its own ("liable for any breach of publication ethics"). The OUP defaults apply.

### Innovation in Aging (`innovation-in-aging`): VERIFIED (WebFetch)

- URL: https://academic.oup.com/innovateage/pages/author_guidelines. The menu link `/general_instructions` returns only navigation.
- Home: metrics block word for word "6.2 2025 Impact Factor", "1/49 Gerontology (Rank by Impact Factor)"; "Fully Open Access model of publishing". Instructions: "Innovation in Aging is a fully open access journal".
- AI text: the same GSA section as J Gerontol A, word for word in every fragment. It adds the COPE clause "or in the collection and analysis of data, must be transparent in disclosing".
- Limits: Original Research Article "6,000" words of text, abstract "250 (structured)"; Research Report "3,000".
- Screening: "Manuscripts will be screened using iThenticate to help detect publication misconduct, including plagiarism" and third-party integrity screening.

**Answers:** as J Gerontol A.

### Age and Ageing (`age-ageing`): VERIFIED (WebFetch + Wayback 2026-02-04)

- URL: https://academic.oup.com/ageing/pages/General_Instructions. Home: "7.4 Impact Factor (2025)"; British Geriatrics Society.
- Hybrid: "The journal offers the option of publishing under either a non-open access (standard) licence".
- AI text: the standard OUP clause under "Publication and research ethics › Authorship". Nothing else.
- Screening: "Manuscripts will be screened using tool including iThenticate" (sic) ... "to help detect publication misconduct including plagiarism, duplicate submission, and redundant publication."
- Limits: Research Papers "Maximum 3,000 words (excluding the abstract), 250-word abstract, 5 tables/figures"; Short Reports 1,500 words.

**Answers:** the OUP default.

### JAMIA (`jamia`): VERIFIED (WebFetch + Wayback 2026-01-29)

- URL: https://academic.oup.com/jamia/pages/General_Instructions. Home: "7.1 / 2025 Impact Factor"; © American Medical Informatics Association.
- Hybrid: "JAMIA offers the option of publishing under either a standard licence or an open access licence."
- AI text: the standard OUP clause under "About the journal > Authorship". WebFetch found no AI text in the second half of the page and no reporting-guideline requirement for AI or LLM studies (TRIPOD-LLM, CONSORT-AI, MI-CLAIM).
- Screening: "Papers submitted to the journal will be screened for plagiarism using Similarity Check / iThenticate". There is no papermill sentence on this page (hence `plagiarism`).
- Research and Applications *(Wayback)*: "can, for example, report on an innovative application of information technology, the detailed description of a new methodology"; "Word count: up to 4000 words. Structured abstract: up to 250 words." Brief Communications 2000 words, abstract 150.

**Answers:** the OUP default.

### Database (`database`): PARTIAL (unchanged status; fields filled where possible)

- URLs: https://academic.oup.com/database/pages/instructions_for_authors; hub https://academic.oup.com/database/pages/General_Instructions (navigation only).
- Home: "2.7 / 2025 Impact Factor"; "4.6 / 2025 5 Year Impact Factor"; International Society for Biocuration.
- Instructions (WebFetch): "all articles are published in the journal under an open access licence immediately upon publication", "fully open access".
- **Why still PARTIAL:** WebFetch receives only 10,773 characters of the live page. It stops in the "Read and Publish" participating-institutions table, before the sections that follow; an in-page link to `#pre-submission-technical-checks` shows more exists. The only 2026 Wayback capture of the page is a 403 (2026-07-23). Chrome and r.jina.ai hit the Cloudflare check.
- No AI text and no ISCB text in what was read, nor in the 2025-04-18 snapshot (per `target-journals.md`). The OUP default applies by inference.
- Aims (WebFetch): "Shorter papers describing significant updates to established databases."; "User tutorials for database tools."

**Answers:** unknown beyond the OUP default. Re-read the live page in a normal browser.

---

## Re-check of existing entries (`nar`, `briefings-bioinformatics`, `gigascience`)

The AI text is **unchanged** on all three live pages. The only differences are JIF and access fields, which the existing entries predate. The JIF and screening updates below were applied to `../venues.yaml` on 2026-10-15.

- **`nar`**: https://academic.oup.com/nar/pages/author-guidelines (WebFetch live + Wayback 2026-05-20).
  - Same heading "AI-powered language processing models" and the same OUP clause. The page still "does not link to an OUP 'Policy on AI Use & Disclosure'"; it links only COPE. The software rules match.
  - Home shows **"15.0 / 2025 Impact Factor"** (entry: 13.1) and "17.6 / 2025 5 Year Impact Factor". It says NAR "was the first OUP journal to flip to fully open access".
  - Screening is wider than the entry's `plagiarism`:
    - "Manuscripts may also be screened, including with services provided by third parties, to help detect integrity issues such as inappropriate image alteration and papermill activity."
    - "We will be screening your manuscript using a third-party service that evaluates journal trust and integrity."
    - "The Journal uses ScholarOne's Unusual Activity Detection tool to build confidence in the identity of authors and reviewers."
  - Suggested: `jif: 15.0, jif_year: 2025, oa: full, screening: integrity_signals`, `inherits: oup` (the AI fields equal the OUP default).
- **`briefings-bioinformatics`**: https://academic.oup.com/bib/pages/general_instructions (WebFetch live).
  - The "Policy for Acceptable Use of Large Language Models" section is unchanged. It names ISCB, carries the same acceptable and unacceptable lists, and requires supplementary documentation ("should be explicitly declared and documented with sufficient details in the supplementary materials").
  - Pre-screen and data rules were not re-read.
  - Home shows **"7.3 / 2025 Impact Factor"** (entry: 7.7). Instructions: "Briefings in Bioinformatics is a peer-reviewed fully open access journal publishing 6 issues per year online."
  - Suggested: `jif: 7.3, jif_year: 2025, oa: full`; it could `inherits: iscb` instead of `bioinformatics`.
- **`gigascience`**: https://academic.oup.com/gigascience/pages/editorial_policies_and_reporting_standards (WebFetch live + Wayback 2026-04-06).
  - "Use of AI Tools and Technologies in Writing" and "Misuse of AI-assisted technologies" are unchanged, word for word with the entry's quotes, including the "GigaScence may use tools to detect undeclared or misuse of AI." typo.
  - The page has no sentence on reviewers and AI.
  - The home page shows **no Impact Factor**, so `jif` should become null under the new page-only rule. It says "an open access, open data, open peer-review journal" (`oa: full`).
- Aside, not in my list: the **Bioinformatics** home page shows "5.5 / 2025 Impact Factor" (entry: 5.4) and offers OA with a 15% society discount on APCs.

## Pages I could not read

- **Database** instructions past the open-access section (see above).
- **DNA Research**: the live Ethics and Misconduct sections (read only on the 2026-03-31 snapshot).
- **G3**: the live LLM Methods paragraph (read on the 2026-04-11 snapshot).
- No OUP-wide reviewer AI policy found (NOT FOUND). Reviewer AI was checked only for GENETICS, G3 and HMG (all banned); other journals stay `null`.
- No ESHRE, GSA (Gerontological Society) or SMBE society-level AI policy found outside the journal pages (one search each, NOT FOUND).
