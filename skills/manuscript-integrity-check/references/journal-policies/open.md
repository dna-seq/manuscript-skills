# Generative-AI policies: open-access, society, software and aging venues (checked 2026-10-15)

> Cluster "open". Entries in `../venues.yaml`. Re-fetch a venue's page before relying on it.

## How this was read

- Status marks as in `target-journals.md`: **VERIFIED** (venue's or publisher's own page read), **PARTIAL**, **SECONDARY** (news or third party only), **NOT FOUND** (searched, nothing found).
- Route: every page was rendered with headless Chrome (`--headless=new --dump-dom`, 15-25 s virtual-time budget) and converted with `w3m -dump`, so quotes are exact text. Exceptions:
  - `www.pnas.org` and `royalsocietypublishing.org` show a Cloudflare check; a 40-60 s budget got through it.
  - The Science AI-usage table is a PDF, read with `curl` + `pdftotext -layout`.
  - WebSearch was used only to find URLs (Aging Biology, Ageing & Longevity, the new TCBB title) and for one SECONDARY note.
- Page copies were kept only for the research session.
- JIF: copied only where the venue's or publisher's own page shows it. Where the page gives no year, `jif_year` is null.

---

## Publisher defaults

### P1. PLOS (`plos`): VERIFIED

- https://journals.plos.org/plosone/s/ethical-publishing-practice, section "Artificial Intelligence Tools and Technologies". No date shown.
- I extracted the AI section from the PLOS ONE, Computational Biology, Genetics and Biology copies and diffed them: identical.
- Matches `publisher-policies.md` §4.6. New details below.

Verbatim:
> "AI tools may be used to support development or revision of a PLOS submission."
> "Any AI use to generate or revise content for a PLOS submission, or to support research reported in a PLOS article, must be clearly disclosed"
> "For AI use by authors, disclosures should be in the body of the article, either in a dedicated section of the Methods, in the Acknowledgement section, or in the relevant figure legend(s)."
> FAQ: "We do not require disclosure of AI use for language improvements, such as to correct spelling or grammar, or to rephrase content for clarity or conciseness. If an AI tool has been used for language translation, we recommend this be disclosed in order to preempt concerns, but this is not strictly required."
> FAQ: "Do I need to disclose AI use for generation or development of analysis scripts or software code? Yes."
> FAQ: "Will AI use disclosures negatively affect my article's review or editorial decision? No."
> FAQ: "We may use available AI detection tools in article-level checks or assessments"
> Reviewers: "Editorial Board members and reviewers must not upload submissions, submission summaries, or any comments that would reveal information about unpublished submissions to generative AI tools, web platforms, databases, or other services."
> "Concerns about undisclosed or unacceptable AI use by authors may prompt an integrity investigation, delay peer review, and/or lead to editorial action on the article such as a rejection, retraction, or publication of an Expression of Concern."

Answers
1. **Writing help:** allowed. Language polish and rephrasing are exempt. Generating or revising content must be disclosed.
2. **Disclosure:** in the article body: Methods section, Acknowledgements or figure legend. Name the tool, say how it was used, what it affected and how the output was validated. The cover letter needs nothing.
3. **Prompts:** not asked for.
4. **Screening:** "may use available AI detection tools". PLOS also uses AI tools for submission checks.
5. **Penalties:** investigation, delayed review, rejection, retraction, Expression of Concern, institution notified.
6. **Disclosure-neutral:** yes, an explicit "No" in the FAQ.
7. **Reviewers:** must not upload submission content to AI tools.
8. **Impact factor:** PLOS shows none: "We do not consider Impact Factor to be a reliable or useful metric to assess the performance of individual articles but will provide the metric to individuals when specifically requested."

### P2. Frontiers (`frontiers`): VERIFIED

- Policy: https://www.frontiersin.org/guidelines/policies-and-publication-ethics ("Artificial intelligence: fair use and disclosure policy"). No date shown (© 2026).
- Each journal's author-guidelines page carries the same text under "Guidelines for artificial intelligence".
- Reviewer tool: https://www.frontiersin.org/guidelines/aira-review-guide-reviewers
- AIRA: https://www.frontiersin.org/about/artificial-intelligence and the 7 July 2025 news item on Cactus and Clear Skies.

Verbatim (author side, matches `publisher-policies.md` §4.7):
> "If AI tools have been used to generate main text, then this must be clearly disclosed in the acknowledgments."
> "If the author of a submitted manuscript has used written or visual content produced by or edited using a generative AI technology, such use must be acknowledged in the acknowledgments section of the manuscript and the methods section, if applicable. This explanation must list the name, version, model, and source of the generative AI technology."
> "We encourage authors to upload all input prompts provided to a generative AI technology and outputs received from a generative AI technology in the supplementary files for the manuscript."

Verbatim (reviewer side, new since §4.7):
> "To protect confidentiality and intellectual property, manuscript content must not be uploaded to external generative AI tools."
> "To support peer reviewers, we provide an internal AI tool within the review forum, operating in a secure, closed environment. It helps by summarizing manuscript content, highlighting areas for analysis, and assisting in drafting constructive feedback - while fully preserving author privacy."
> "Any use of external AI tools must be discussed with the editorial team in advance, and - if approved - clearly disclosed to authors in the review."
> AIRA Review Guide page: "AIRA Review Guide contains ready-loaded prompts - questions designed to probe the integrity and accuracy of the study." "If you have used AIRA Review Guide, you are required to declare it in the review report questionnaire." "Report immediately to Frontiers' peer review team if you suspect improper AI use by authors."

Verbatim (screening):
> AI page: "It performs more than 40 quality checks in just a few minutes – from assessing language accuracy to detecting image manipulation. We use AIRA to provide decision support, but the final decision is always made by a human expert."
> 7 July 2025: "Cactus Communications' Paperpal Preflight and Clear Skies' Papermill Alarm and Oversight – have been integrated into" AIRA.

Answers
1. **Writing help:** allowed with disclosure. Text that was only "edited using" generative AI is also covered, and no grammar exemption is stated, so I classify it `disclose_all`.
2. **Disclosure:** Acknowledgments, plus Methods if applicable. Give the name, version, model and source.
3. **Prompts:** encouraged as supplementary files, together with the outputs.
4. **Screening:** AIRA integrity checks (language, images, papermill), Paperpal Preflight and Papermill Alarm. No AI-text detector is named.
5. **Penalties:** none stated in the AI policy itself.
6. **Disclosure-neutral:** the page says nothing either way.
7. **Frontiers' AI review assistant.** Reviewers may not use external AI, but Frontiers runs its own LLM tool, AIRA Review Guide, on the manuscript: it summarizes content and helps draft the review. Reviewers must declare its use. This makes `reviewer_ai` `restricted`, not `banned`. Authors should expect their manuscript to be processed by that tool.
8. **Validation rule:** "Frontiers' journals require that manuscripts primarily comprising solely of bioinformatics analyses, computational studies of public data, or findings from Mendelian Randomisation studies must include appropriate validation." Unchanged from §4.7.

### P3. MDPI (`mdpi`): VERIFIED

- https://www.mdpi.com/ethics, section "Artificial Intelligence". No date shown (© 2026).
- Matches `publisher-policies.md` §4.8.

Verbatim:
> "Where GenAI has been used for purposes such as generating text, data, graphics, and a study design, or for data collection, analysis, or the interpretation of data, authors are required to declare this during the submission process. Furthermore, for transparency, authors are required to disclose details on how the GenAI tool was used in the Materials and Methods section and provide the GenAI tool's product details in the Acknowledgments section."
> "The use of GenAI tools for the purposes of text editing (e.g., grammar, structure, spelling, punctuation, and formatting) is not covered by this policy and does not need to be declared."
> "MDPI reserves the right to request further information"
> Reviewers: "Under no circumstances should reviewers upload manuscripts either in whole or in part ... to any GenAI tools" ... "If it is determined that AI tools have been inappropriately used in the preparation of a review report, the report will be discarded."
> "All MDPI submissions are checked for plagiarism using the industry-standard software iThenticate."

Journal instruction pages (IJMS, Genes, Cells and Biomolecules carry the same wording) shorten the exemption:
> "The use of GenAI for superficial text editing (e.g., regarding grammar, spelling, punctuation and formatting) does not need to be declared."

That sentence drops "structure". A checker should follow the narrower journal text.

Answers
1. **Writing help:** allowed. Generated text must be disclosed; text editing is exempt.
2. **Disclosure:** three places: the submission form, Materials and Methods (how the tool was used), and Acknowledgments (product details, using the recommended statement).
3. **Prompts:** not asked for.
4. **Screening:** iThenticate.
5. **Penalties:** none AI-specific. MDPI "reserves the right to request further information".
6. **Disclosure-neutral:** the page says nothing either way.
7. **Reviewers:** may not upload manuscripts. Limited grammar help on their own report is allowed but must be disclosed.

### P4. AAAS / Science family (`aaas`): VERIFIED

- Editorial policies: https://www.science.org/content/page/science-journals-editorial-policies. No date shown.
- AI-use table: https://www.science.org/cms/asset/cea1081d-3aa4-42a2-96b7-72290067116a/sept26_science_journals_guidelines_ai_use.pdf ("sept26" in the filename; 2 pages).
- Reviewers: https://www.science.org/content/page/peer-review-science-publications

Verbatim (policy):
> "Authors who use AI-assisted technologies as components of their research study or as aids in the writing or presentation of the manuscript should note this in the cover letter and in the methods section or acknowledgments section of the manuscript (the location and details of the declaration will depend on use case; see our AI usage guidelines for specifics)."
> "Editors may decline to move forward with manuscripts if AI is used inappropriately."
> "Reviewers may not enter any part of the manuscript into an LLM or other AI tool because this could breach the confidentiality of the manuscript."
> "The Science journals use the Crossref Similarity Check service to detect plagiarism"; "Science journal editors may use Proofig to screen images."

Verbatim (table rows, `pdftotext -layout`):
> "Refinement, correction, editing, or formatting to improve clarity of language | Yes | No declaration needed"
> "Writing or drafting manuscript content | Yes, with conditions | Must be declared in the acknowledgments section, with model name and version number provided"
> "Writing code or editing code in a way that changes functionality | Yes, with conditions | Must be described in the methods section, with model name and version number provided"
> "Refinement or formatting of code | Yes | No declaration needed, as long as functionality remains unchanged"
> "Generation, refinement, correction, editing, or formatting of images, diagrams, or other figures for illustrative purposes only | No | Not allowed; exceptions must be discussed with the editor"
> "Revising the manuscript | Entering all or part of the manuscript into an LLM or other AI tool | No | Not allowed"
> "Responding to the reviews | Entering all or part of the review into an LLM or other AI tool to generate or augment a response | No | Not allowed"

**Difference from `publisher-policies.md` §4.9:** that summary omits the language-refinement row (no declaration needed), the code-refinement row and the "Formatting of data reported in the manuscript | Yes | No declaration needed" row. With those rows, Science sits at `disclose`, not `disclose_all`.

The table also contradicts itself:
- Language polishing before submission needs no declaration.
- But "Revising the manuscript: Entering all or part of the manuscript into an LLM" is "Not allowed".
- So at revision stage, no LLM may touch the manuscript, not even for polishing.

Answers
1. **Writing help:** allowed. Drafting must be declared in Acknowledgments with model and version. Language refinement needs no declaration.
2. **Disclosure:** a note in the cover letter, plus Acknowledgments (drafting, translation, data visualizations) or Methods (code that changes functionality, data generation or analysis).
3. **Prompts:** not asked for.
4. **Screening:** Crossref Similarity Check and Proofig. No AI detector is named.
5. **Penalties:** editors "may decline to move forward".
6. **Disclosure-neutral:** the page says nothing either way.
7. **Burden:**
   - no LLM on the manuscript during revision;
   - no AI-generated or AI-augmented response to reviewers;
   - no AI illustrative figures;
   - cited sources may not be AI-authored.

### P5. Impact Journals (`impact-journals`): VERIFIED

- Section "Artificial Intelligence Tools" on https://www.aging-us.com/editorial-policies and https://www.oncotarget.com/editorial-policies/. No date shown.
- After normalizing the journal name, I diffed the two sections: identical.
- The publisher's own https://www.impactjournals.com/about/editorial-policies/ has **no** AI section, and neither does /about/ethics. The publisher default here is that shared journal text.
- Publisher line on the Aging site: "Rapamycin Press LLC dba Impact Journals is the publisher of Aging".

Verbatim:
> "Large Language Models (LLMs), such as ChatGPT, currently do not meet the criteria for authorship. ... Researchers must document the use of LLMs in the Methods section of their manuscripts, or in an appropriate alternative section if a Methods section is not available."
> "the use of AI-generated images and videos in publications is generally not permitted unless the images are obtained from agencies with whom we have contractual agreements and are created in a legally acceptable manner."
> "AI tools and technologies contributing to a study or article must be clearly reported in the Methods or Acknowledgements section, detailing the tools used, their application, and the validation of their outputs."
> "A lack of compliance with this policy will be regarded as misrepresentation, and actions may include notifying the authors' institutions, rejecting the manuscript, retracting published articles, or issuing editorial notices."
> Reviewers: "Their evaluations must be based on their expertise and must not rely on generative AI tools ... manuscripts may contain sensitive or proprietary information that should not be shared with AI tools. Any use of AI tools in evaluating manuscripts must be transparently declared in the peer review report."
> Screening (Aging): "Plagiarism is checked using the service provided by Crossref (Crossref Similarity Check)." "All new submissions are screened for image irregularities by our Image Forensics team." The integrity page names ImageTwin.

Answers
1. **Writing help:** allowed. Any LLM use must be documented in Methods, and no language-editing exemption is stated, so `disclose_all`.
2. **Disclosure:** Methods (LLM use), Methods or Acknowledgements (AI tools), figure caption (non-generative AI image tools). Name the tools, describe the application and say how the outputs were validated.
3. **Prompts:** not asked for.
4. **Screening:** Crossref Similarity Check and ImageTwin. No AI detector is named.
5. **Penalties:** non-compliance counts as misrepresentation: institution notified, rejection, retraction, editorial notice.
6. **Reviewers:** must not share manuscripts with AI tools, and must declare any AI use.

### P6. Royal Society Publishing (`royal-society`): VERIFIED

- Policy: https://royalsociety.org/journals/ethics-policies/artificial-intelligence/ ("Use of Artificial intelligence (AI) and AI-assisted technologies"). No date shown.
- Author guidelines: https://royalsociety.org/journals/authors/author-guidelines/
- Referee rule: https://royalsociety.org/journals/ethics-policies/editorial-standards/

Verbatim:
> "Authors must disclose in the manuscript their use and a statement will be required in the published work. The statement should provide detail of which elements of the work were generated by AI and AI-assisted technologies. Editors and reviewers will judge if its use is appropriate. Published articles in which the use of such technologies is subsequently discovered may be retracted."
> "Where used in the writing process, these technologies should only be used to improve readability and language of the work. Use of AI in language editing must be declared."
> "They must not replace key researcher tasks such as producing scientific insights, analysing and interpreting data or drawing scientific conclusions."
> "The resulting work in its totality must be an accurate representation of the authors' underlying work and novel intellectual contributions and is not primarily the result of the tool's generative capabilities"
> "Journals reserve the right to ask authors who use AI for their corresponding prompts and outputs, which can be supplied as ESM files. Please note that journals may reject any submissions that are unable to provide these."
> Author guidelines: "You will be asked to declare whether you have used AI technologies in the preparation of your paper. If you have, please provide a statement about how you have used this – the statement will be published in the final article."
> "Submissions are routinely screened for plagiarism and, where relevant, image integrity (eg paper-mills). In addition, we collaborate with other publishers via the STM Integrity Hub"
> Referees: "Referees inputting manuscript details into generative AI tools is prohibited."

Answers
1. **Writing help:** narrow. Writing use is limited to "readability and language", so drafting is out (`banned_drafting`). Language editing must be declared too.
2. **Disclosure:** a declaration at submission and a published statement saying which elements AI generated.
3. **Prompts:** on request. Because a journal "may reject any submissions that are unable to provide these", I marked tracking `required`: keep the prompts and outputs.
4. **Screening:** plagiarism and image integrity, STM Integrity Hub. No AI detector is named.
5. **Penalties:** retraction if AI use is discovered after publication; rejection if prompts cannot be supplied.
6. **Disclosure-neutral:** **no.** "Editors and reviewers will judge if its use is appropriate."
7. **Reviewers:** banned.

---

## Journals

### 1. Aging (Albany NY) (`aging-us`): VERIFIED

- https://www.aging-us.com/editorial-policies. The AI section is the Impact Journals text (P5).
- **JIF:** the publisher page https://www.impactjournals.com/ has a table headed "IMPACT FACTOR (IF) WEB OF SCIENCE". It runs 2011-2021; the latest value is 5.955 for 2021, and no later year is shown.
- **OA:** full. "Aging applies the Creative Commons Attribution License (CC BY 4.0) to all works we publish". "A publication fee of $3,850 (USD) applies to Research Papers".
- **Limits:** "There is no word limit for any section of the paper, except for the abstract (no more than 200 words)".
- **Article types:** Research Papers, Reviews, Systematic Reviews, Case Reports, Research Perspectives, Commentaries. No software type.
- **Note:** the homepage's latest-publication list on 14-15 Oct 2026 includes two retraction notices.
- Answers: as P5. The journal page only carries the shared Impact Journals text.

### 2. Oncotarget (`oncotarget`): VERIFIED

- https://www.oncotarget.com/editorial-policies/. The AI section is identical to Aging's (P5).
- **Indexing:** the publisher lists "PubMed/Medline, PubMed Central, Scopus, and EMBASE" and "On September 15, 2022, Oncotarget was accepted again for indexing by MEDLINE". There is no Web of Science entry and no JIF.
- **Limits:** abstract "not more than 200 words". CC BY 4.0.
- Answers: as P5.

### 3. Aging and Disease (`aging-disease`): VERIFIED

- Policy: https://www.aginganddisease.org/EN/column/column227.shtml ("Artificial intelligence (AI) Use Policy"). Page shows "Pubdate：2025-04-14".
- Author guidelines: https://www.aginganddisease.org/EN/column/column217.shtml
- **Publisher:** "Published by the International Society on Aging and Disease (ISOAD, www.isoad.org)".
- **JIF:** the homepage shows "2025 Impact Factor 9.6"; the metrics page shows "2025 SCI impact factor:9.6".

Verbatim:
> "Aging and Disease does not recognize AI tools (e.g., ChatGPT, image generators) as authors or coauthors, and AI-generated content may not be cited as a source."
> "Authors using AI-assisted tools in research or manuscript preparation must disclose this in the cover letter, Acknowledgments, and Methods sections, including the tool name, version, and prompt used."
> "Reviewers are not allowed to use AI tools during the peer review process to ensure confidentiality and ethical compliance."
> "AI-generated images or multimedia are not permitted unless approved in advance by the editors."
> "A&D use the Crossref Similarity Check service to detect plagiarism"

Answers
1. **Writing help:** allowed with disclosure. Any "manuscript preparation" use counts and nothing is exempt, so `disclose_all`.
2. **Disclosure:** all three places (cover letter, Acknowledgments, Methods), each with tool name, version **and the prompt used**.
3. **Prompts:** required. It is the only venue in this cluster that asks for the prompt itself.
4. **Screening:** Crossref Similarity Check. The author guidelines add: "selected submitted manuscripts are scanned using the Plagiarism Prevention Software Turnitin".
5. **Penalties:** none stated.
6. **Reviewers:** banned from all AI use.
7. **Other details:**
   - Abstract up to 300 words.
   - APC $3,500 for an original article from 1 Oct 2026.
   - Full OA.

### 4. Aging Biology (`aging-biology`): VERIFIED

- Home: https://agingbiologyjournal.org/ (ISSN 2994-2578). Publisher: "Aging Biology, LLC".
- Policy: https://agingbiologyjournal.org/Scientific_Integrity/ (section "Artificial Intelligence"). No date shown.
- Origin: launched 2023. That former *Aging Cell* editors founded it comes only from a third-party domain page (netatlas.net), so it is **SECONDARY**. The site lists Vera Gorbunova and John Sedivy among the Editors-in-Chief.

Verbatim:
> "AI tools, such as ChatGPT, are acceptable at all stages of MS production, hypothesis generation, data analysis and manuscript writing. However, AI tools cannot be authors and so responsibility for any AI contributions is that of the listed authors, ultimately the senior/corresponding author. Results of AI writing tools should be verified for potential plagiarism, as this also is the responsibility of the authors."
> "Although not currently a member of the Committee on Publication Ethics (COPE), Aging Biology adheres to all such codes of publishing conduct"
> Peer review page: "Editors and reviewers are required to maintain confidentiality around the review process". Nothing on reviewer AI use.

Answers
1. **Writing help:** `free`. This is the only venue in the cluster that permits AI at every stage and asks for **no disclosure**.
2. **Disclosure:** none required. ICMJE/COPE norms would still favour one; that is my note, not the journal's.
3. **Prompts / screening / penalties:** none stated.
4. **Other details:**
   - Abstract 250 words or fewer; research articles up to 50,000 characters.
   - APC $4,000 for a research article. Free to read under CC BY.
   - Small output: Volume 4 (2026) lists 2 articles.

### 5. Ageing & Longevity (`ageing-longevity`): NOT FOUND (no AI policy on the journal's pages)

- Home: https://aging-longevity.org.ua/ (OJS). I found it through the ISSN Portal record for ISSN 2709-0205, which links `aging-longevity.org.ua`.
- Pages read: publication ethics, submissions, information for authors, peer review, payment, aims, about, retraction. None contains "AI", "artificial intelligence", "LLM", "generative" or "ChatGPT".
- **Publisher (journal site):** "Research Institute of Biology, V. N. Karazin Kharkiv National University, Ukraine". "Founded in 2020 by Professors Vladislav Bezrukov and Alexei Verkhratsky".
- The ISSN Portal (via WebSearch, so **SECONDARY**) names the D. F. Chebotarev Institute of Gerontology as the earliest publisher.
- Nearest rule, ethics page (author duties): "Fully disclosing Author Contributions and any external editing support, including that by commercial editing agencies".
- Screening: "we use dedicated software to check submissions against previous publications."
- **OA:** full and free to publish: "Articles in the Ageing & Longevity journal are published free of charge for all authors."
- **JIF:** none shown.
- Answers: no AI rule. A cautious author would disclose AI help under the "external editing support" duty; that is an inference.

### 6. Frontiers in Aging (`frontiers-aging`): VERIFIED

- Author guidelines: https://www.frontiersin.org/journals/aging/for-authors/author-guidelines. AI text identical to P2.
- **JIF:** the about page shows "4.9 Impact Factor" with no year.
- **Scope page:**
  > "Frontiers' journals require that manuscripts primarily comprising computational studies of public data, such as NHANES or Mendelian Randomization studies, must include appropriate validation. ... Manuscripts not adhering to these standards will not be considered."
- **Article types** include Original Research, Methods, Technology and Code, Data Report, Review, Perspective. Original Research and Technology and Code have a "maximum word count of 12,000".
- Answers: as P2.

### 7. Frontiers in Genetics (`frontiers-genetics`): VERIFIED

- https://www.frontiersin.org/journals/genetics/for-authors/author-guidelines. AI text as P2. JIF "3 Impact Factor" (about page), no year.
- **Scope:**
  > "Manuscripts consisting solely of bioinformatics, computational analyses of public data which are not accompanied by validation (independent clinical or patient cohort, or biological validation in vitro or in vivo) or are not highly innovative are not suitable for publication in this journal."
- Answers: as P2. The scope rule is the binding constraint for a pure-computational paper.

### 8. Frontiers in Bioinformatics (`frontiers-bioinformatics`): VERIFIED

- https://www.frontiersin.org/journals/bioinformatics/for-authors/author-guidelines. AI text as P2. JIF "3.6 Impact Factor", no year.
- **Scope:** "Please note this journal does not accept mendelian randomization or bibliometric studies."
- **Technology and Code** articles "present new technology, code and/or software" and "should be placed online in a repository, with an associated DOI/URI for retrieval". Maximum 12,000 words.
- Answers: as P2.

### 9-12. IJMS, Genes, Cells, Biomolecules (MDPI): VERIFIED

- Instructions pages: https://www.mdpi.com/journal/{ijms,genes,cells,biomolecules}/instructions. Each has the same GenAI text in "Materials and Methods" and "Acknowledgments", with the narrower "superficial text editing" exemption (P3).
- **JIF:**
  - IJMS: "Impact Factor: 5.6 (2025); 5-Year Impact Factor: 6.3 (2025)".
  - Genes 3.1, Cells 6.0, Biomolecules 5.6: shown on the journal tiles without a year.
- **Abstract:** about 200 words (IJMS, Cells, Biomolecules); about 250 words, structured (Genes).
- **Article types:** Article and Review on the instruction pages. I did not check MDPI's full article-type list.
- Answers: as P3.

### 13. PLOS ONE (`plos-one`): VERIFIED

- AI: P1. Submission guidelines: https://journals.plos.org/plosone/s/submission-guidelines
  > "Recapitulation of existing methods, software, or databases is not useful and will not be considered for publication."
  > Software "must be open source, deposited in an appropriate archive, and conform to the Open Source Definition."
  > Abstract: "Not exceed 300 words".
- Answers: as P1.

### 14. PLOS Genetics (`plos-genetics`): VERIFIED

- AI: P1 (identical). Submission guidelines: https://journals.plos.org/plosgenetics/s/submission-guidelines. It has the same "Methods, software, databases, and tools" criteria as PLOS ONE. Abstract "must not exceed 300 words".
- Answers: as P1.

### 15. PLOS Biology (`plos-biology`): VERIFIED

- AI: P1 (identical). Article types: https://journals.plos.org/plosbiology/s/what-we-publish
- "Methods and Resources Articles describe technical innovations ... Resources consist of data sets or other significant scientific resources". No software type is named.
- Answers: as P1.

### 16. Science (`science`): VERIFIED

- AI: P4.
- **JIF:** 47.3 on https://www.science.org/content/page/journal-metrics-overview ("The metrics listed below originate from third-party services Web of Science and SCOPUS. Metrics data are current as of June 2026."). I read this as the 2025 JIF.
- 2025 accept rate 5.3%.
- Abstract: "The abstract should be 125 words or less."
- Answers: as P4.

### 17. Science Advances (`science-advances`): VERIFIED

- AI: P4. Authors: https://www.science.org/content/page/science-advances-information-authors
- **JIF:** 13.9 (same metrics page).
- Research articles: "up to 15,000 words"; abstract "no more than 150 words".
- **Research Resources** "present a validated technique, tool, or informational database without substantial analysis that results in a new research insight". This is a software- and database-capable type.
- APC: "The base APC for articles published under a CC BY-NC or CC BY license is $5,450."
- Answers: as P4.

### 18. PNAS (`pnas`): VERIFIED (Cloudflare; 40 s render)

- Policy: https://www.pnas.org/author-center/editorial-and-journal-policies, section "Artificial intelligence". No date shown.
- Reviewers: https://www.pnas.org/reviewer

Verbatim:
> "As part of the journal's editorial assessment and peer review process, PNAS uses software that may leverage artificial intelligence (AI), such as iThenticate to screen for text similarity to published works, Pangram to detect content generated by AI, Prophy to assist matching submissions to editors and potential reviewers, and Web of Science Reviewer Locator to identify potential reviewers."
> "Use of AI and generative AI software, such as large language models (e.g., ChatGPT), during the research process must be disclosed in the Materials and Methods section (or Acknowledgments, if no Materials and Methods section is available) of the manuscript and may not be listed as an author. The name and specific model or version (e.g., GPT-4 or Claude 3.5 Sonnet) of any AI tool should be provided."
> "AI tools for creating images or graphics may not be used unless the software is the subject of the work under consideration or permission has been granted by the editorial office."
> Reviewers: "Reviewers may not submit any submitted manuscript or related materials to any generative artificial intelligence (AI) software, such as Large Language Models or ChatGPT. Using an AI tool to help revise your own writing is permitted if the system does not save or use your inputs to train the model."

Answers
1. **Writing help:** the policy names only AI used "during the research process". Writing assistance is neither exempted nor named. I set `disclose` as an interpretation.
2. **Disclosure:** Materials and Methods (or Acknowledgments). Give the name and specific model or version.
3. **Prompts:** not asked for.
4. **Screening:** **`ai_detector_deployed`**. PNAS names Pangram "to detect content generated by AI". In this cluster it is the only venue whose own page names an AI-text detector on submissions. AI-drafted text that is not disclosed carries real risk here.
5. **Penalties:** none stated.
6. **Reviewers:** banned from entering the manuscript.
7. **Other details:**
   - Hybrid OA: immediate OA $6,075 (site-license $5,575), or "free to read within six months".
   - Abstract up to 250 words, significance statement up to 120.
   - A 6-page Research Report is about 4,000 words.

### 19. Journal of Open Source Software (`joss`): VERIFIED

- Policy: https://joss.readthedocs.io/en/latest/policies.html ("AI usage policy").
- Also: https://joss.readthedocs.io/en/latest/submitting.html, https://joss.readthedocs.io/en/latest/review_criteria.html, https://joss.readthedocs.io/en/latest/paper.html
- Scope change: blog post "Preparing JOSS for a generative AI future", Arfon M. Smith, 5 Jan 2026, https://blog.joss.theoj.org/
- No date on the docs pages.

Verbatim (policy):
> "The Journal of Open Source Software permits the use of generative AI in submissions with mandatory disclosure and human oversight requirements."
> "The use of generative AI is permitted for most aspects of a JOSS submission (e.g., software creation and review, generating documentation, assisting with paper authoring), however all such use must be disclosed in an "AI usage disclosure" statement which includes: Tool use: The tools/models used (and versions) and where they were used (code, paper text, docs). The nature and scope of assistance: e.g., code generation, refactoring, test scaffolding, copy-editing, drafting. Confirmation of review: Authors must assert that human authors reviewed, edited, validated all AI-assisted outputs and made the core design decisions."
> "AI is not allowed for conversational interactions between authors and editors or reviewers unless it is being used for translation purposes."
> "Failure to provide a complete and accurate disclosure of AI usage may be considered an ethical breach. Consequences can include desk rejection, mandatory revisions, and post-publication correction or withdrawal. In cases of intentional misrepresentation or non-disclosure, JOSS reserves the right to notify the authors' institutions, funders, and/or relevant professional or scholarly societies"
> Reviewers: "Reviewers may use generative AI tools to assist with non-substantive tasks (e.g., grammar checks of their review text, contextualizing public materials and code snippets) and must disclose this briefly at the end of their review."

Verbatim (review checklist):
> "If no AI tools were used, this should be explicitly stated." ... "Bad (not acceptable): Missing section or vague/evasive language about AI usage"

Verbatim (pre-review gates):
> "The repository must have been public for more than six months prior to submission, with active development spanning that period. A repository made public immediately before submission, or one showing development concentrated into a few days or weeks, will not be accepted. We run automated checks on commit distribution — a repo dump is not a history."

Verbatim (blog, 5 Jan 2026):
> "very recent projects (particularly those with commit histories of only weeks) may warrant additional scrutiny to ensure they represent genuine collaborative scholarship rather than rapid AI-assisted code generation."

The blog post of 5 May 2026 (EiC search) mentions "a wave of 'vibe-coded' submissions" and describes the journal as "free to publish in and free to read (diamond open access)".

Answers
1. **Writing help:** allowed for code, documentation and paper. Every use, copy-editing included, goes in the disclosure (`disclose_all`).
2. **Disclosure:** a dedicated "AI usage disclosure" section in the paper. It is **mandatory even when no AI was used**. Give tools and versions, where they were used, the nature of help, and confirm human review and design decisions.
3. **Prompts:** not asked for.
4. **Screening:** automated commit-distribution checks; desk rejection for repositories public less than six months or built in a burst. No AI-text detector is named.
5. **Penalties:** desk rejection, mandatory revisions, correction or withdrawal; institutions or funders notified for intentional non-disclosure.
6. **Burden specific to an AI-assisted software paper:**
   - Replies to editors and reviewers in the GitHub review thread must be human-written (AI allowed only for translation).
   - Six months of public, iterative history.
   - Required sections: Statement of need, State of the field, Software design, Research impact statement, AI usage disclosure.
   - Paper of 750-1,750 words.
7. **Reviewers:** AI allowed for non-substantive tasks, with disclosure (`allowed`).

### 20. Journal of Open Research Software (`jors`): VERIFIED (journal page only points to the publisher policy)

- Journal: https://openresearchsoftware.metajnl.com/about/editorialpolicies:
  > "The Journal of Open Research Software follows the publisher's policy regarding the use of AI at any stage of the publishing process."
- Publisher: https://ubiquitypress.com/ai-policy, "Policy on the Use of GenAI Tools in the Publication Process", "Last updated: 10th November 2025".

Verbatim (Ubiquity):
> "Any use of GenAI beyond basic manuscript refinement (e.g. copyediting, formatting) must be explicitly declared, ideally in the Methods section of the manuscript."
> "We do not permit GenAI tools to be used to create, alter, or manipulate original research data, including images and measurements."
> Reviewers: "We do not permit the use of GenAI tools in the creation of a review of a paper" ... "Manuscripts under review should never be uploaded to publicly available GenAI services."
> "Editorial teams should consider the legitimacy of any declared use of GenAI tools on a case-by-case basis."
> "Ubiquity does not currently use bespoke or commercially available GenAI tools as part of the editorial process"
> JORS: "All submissions to the journal are checked via Crossref's Similarity Check"

Answers
1. **Writing help:** allowed. Copyediting and formatting are exempt; anything beyond must be declared.
2. **Disclosure:** ideally in Methods.
3. **Prompts:** not asked for.
4. **Screening:** Crossref Similarity Check.
5. **Penalties:** none stated.
6. **Disclosure-neutral:** no. Declared use is judged "on a case-by-case basis".
7. **Reviewers:** banned.
8. **Other details:** Software Metapaper APC £824; software must sit in a repository under an open licence.

### 21. GigaByte (`gigabyte`): VERIFIED

- https://gigabytejournal.com/information-for-authors, https://gigabytejournal.com/faq, https://gigabytejournal.com/reviewer-information. No dates shown.
- The /policies and /author-guidelines URLs return 404.

Verbatim:
> "Any use of AI and AI-assisted technologies such as generative AI in writing papers should be declared and transparently cited and referenced. ... A summary of use needs to be included at the end of the manuscript (e.g. in a "Disclosure of use of AI-assisted tools including generative AI" section), and any text or and other AI generated output such as images generated should also be included as a supplementary file hosted in GigaDB or other open repositories."
> "Use of AI-assisted technology (e.g. generative AI tools such as ChatGPT) in parts of the text or figures should also be cited, including information about the version of AI-assisted writing tool used, the model used, the date of use and the user's name."
> Cover letter: "Any use of AI-assisted technologies in the drafting of the manuscript should be declared"
> FAQ: "AI-usage for coding should also be declared."
> Reviewers: "Before publication, information about the manuscript should also not be shared with Large Language Models and AI tools."
> About: "GigaByte has signed The San Francisco Declaration on Research Assessment (DORA) declaration and refuses to use the Journal Impact Factor as a promotional tool."

Answers
1. **Writing help:** allowed. Every use is declared, cited and deposited (`disclose_all`).
2. **Disclosure:** in-text citation, a reference-list entry (version, model, date, user name), an end-of-paper summary section and the cover letter.
3. **Prompts:** not named. The **outputs** must be deposited in GigaDB or another open repository, so tracking is `required`. The existing `gigascience` entry marks prompts `encouraged` for the same wording; I kept `"no"` here because the text names outputs, not prompts.
4. **Screening:** nothing named on GigaByte's pages. GigaScience's "may use tools to detect" sentence is not repeated here.
5. **Reviewers:** banned.
6. **Other details:**
   - Article types: Technical Release (software) and Data Release.
   - APC $535.

### 22. Life Science Alliance (`life-science-alliance`): VERIFIED

- https://www.life-science-alliance.org/editorial-policies (section "Artificial Intelligence") and https://www.life-science-alliance.org/reviewers. No dates shown.
- Owners: "Life Science Alliance LLC is limited liability non-stock corporation jointly owned by Cold Spring Harbor Laboratory, EMBO Press Innovations gGmbH and The Rockefeller University".

Verbatim:
> "The use of AI tools or LLMs to generate article content should be documented in the Methods section of the manuscript. This includes reporting details on which parts of the article were generated with the assistance of AI, and details on the AI tool or LLM and version used with a description of how it was used. It is not necessary to acknowledge the use of AI-based grammar/spelling checkers or reference managers."
> Reviewers: "Reviewers are prohibited from uploading a manuscript to large language models (LLMs), or other generative Artificial Intelligence (AI) technologies that ingest user input for model training, noting this excludes most publicly available AI/LLM tools. This represents a breach of confidentiality."
> "Life Science Alliance uses Crossref Similarity Check to screen submitted content for plagiarism"

Answers
1. **Writing help:** allowed. Grammar and spelling checkers are exempt. Generated content goes in Methods.
2. **Disclosure:** Methods: which parts were AI-assisted, the tool and version, and how it was used. The wording is the same as Genome Research's (CSHL Press).
3. **Prompts:** not asked for.
4. **Screening:** Crossref Similarity Check.
5. **Penalties:** none AI-specific.
6. **Reviewers:** `restricted`. Tools that do not train on input are not ruled out.
7. **Other details:**
   - Fee $3,975.
   - Article types: Research, Methods, Resources.
   - No JIF on the pages read.

### 23. Royal Society Open Science (`rsos`): VERIFIED (Cloudflare; 60 s render)

- https://royalsocietypublishing.org/rsos/for-authors. AI rules come from the Royal Society policy (P6).
- **JIF:** https://royalsocietypublishing.org/rsos/pages/citation-metrics shows "2025 Journal Citation Reports (JCR) (Clarivate Analytics)" and "Impact Factor 3.0". The homepage shows "Impact factor: 3".
- Article types: "research article, review, perspective, Registered Report, replication, Evidence Synthesis, Science, Society and Policy, and comment and invited reply".
- "Authors may benefit from trying the Paperpal Preflight tool before submitting their work."
- Answers: as P6. Language-only AI use, declared and published; prompts and outputs on request.

### 24. IEEE Transactions on Computational Biology and Bioinformatics (`ieee-tcbb`): VERIFIED

- **Retitled.** CSDL: "As of 2025, IEEE/ACM Transactions on Computational Biology and Bioinformatics is published under the title IEEE Transactions on Computational Biology and Bioinformatics (TCBB)".
- The old title's IEEE Xplore page (punumber 8857) shows "4.1Impact Factor" and "This title ceased publication in 2024." The new title's page (punumber 10723156) shows "9.7CiteScore" and no impact factor, so `jif` is null.
- Submission page: https://www.computer.org/csdl/journal/tb/write-for-us/15053. "This journal is a hybrid publication". Regular paper "12 double column pages (Submissions may be up to 14 pages in length, subject to MOPC...)". OA APC $2,800 (Xplore).
- AI policy: IEEE-wide only, no TCBB-specific text. https://journals.ieeeauthorcenter.ieee.org/become-an-ieee-journal-author/publishing-ethics/guidelines-and-policies/submission-and-peer-review-policies/ (no date).

Verbatim:
> "The use of content generated by artificial intelligence (AI) in an article (including but not limited to text, figures, images, and code) shall be disclosed in the acknowledgments section of any article submitted to an IEEE publication. The AI system used shall be identified, and specific sections of the article that use AI-generated content shall be identified and accompanied by a brief explanation regarding the level at which the AI system was used to generate the content."
> "The use of AI systems for editing and grammar enhancement is common practice and, as such, is generally outside the intent of the above policy. In this case, disclosure as noted above is not required, but recommended."
> Reviewers: "Information or content contained in or about a manuscript under review shall not be processed through a public platform (directly or indirectly) for AI generation of content for a review."

Answers
1. **Writing help:** allowed. Generated content is disclosed. Editing and grammar are exempt (disclosure "recommended").
2. **Disclosure:** Acknowledgments, naming the system, the sections and the level of use.
3. **Prompts:** not asked for.
4. **Screening:** nothing AI-specific found.
5. **Reviewers:** no public platforms (`restricted`).

**Difference with the existing `ieee-access` entry.** That entry is `disclose_all` with an empty exempt list. The IEEE master policy now states grammar and editing use is "not required, but recommended" to disclose. IEEE Access's own submission guidelines say only:

> "The use of artificial intelligence (AI)–generated text in an article shall be disclosed in the acknowledgements section. The sections of the paper that use AI-generated text shall have a citation to the AI system used to generate the text."

They do not say editing is covered, so `ieee-access` should probably be `disclose` with the IEEE grammar exemption.

---

## Re-checks of existing entries

### eLife (`elife`): VERIFIED, AI text unchanged

- https://reviewer.elifesciences.org/author-guide/journal-policies, "Use of artificial intelligence tools and technology". The text matches §4.10:
  > "Whilst such AI tools might be used to aid researchers and authors in doing their work, they cannot be listed as or serve as co-authors of a paper, and their use must be clearly described in the Materials and Methods section."
- Differences and additions:
  - **Reviewer AI is allowed** (new field `reviewer_ai: allowed`). From https://reviewer.elifesciences.org/reviewer-guide/review-process: "While we do not prevent the use of generative artificial intelligence tools within the review process, editors and reviewers remain accountable for their contributions and the contents of their reviews. If generative AI tools are used by editors or reviewers, this must be disclosed."
  - **Software article:** the entry says `software_article: false`, but eLife has a **Tools and Resources** type: "relevant code must conform to the Open Source Definition and be deposited in an appropriate public repository". Consider `true`.
  - **Writing help:** the AI text names no language-editing exemption. `disclose` is a fair reading, but `disclose_all` is defensible.
  - **Fee:** "The fee for publishing with eLife for submissions from July 1, 2026 is $3,750".
  - **Screening:** "Manuscripts selected by eLife for peer review may be screened for plagiarism using Crossref Similarity Check" (matches `plagiarism`).
  - **Length:** Research Articles: "we suggest that authors try not to exceed 5,000 words in the main text".
  - **JIF:** none shown (entry has null, consistent).

### PLOS Computational Biology (`plos-comp-biol`): VERIFIED, AI text unchanged

- Ethics page AI section: byte-identical to PLOS ONE's (diffed).
- New fields: `disclosure_neutral: true`, `reviewer_ai: banned`.
- **Limits are stated** on https://journals.plos.org/ploscompbiol/s/submission-guidelines:
  - abstract "must not exceed 300 words";
  - Software articles "should be concise (less than 3500 words, not including supplementary material)".
  - So `limits` could be `{abstract_words: 300, body_words: 3500}` instead of null.
- **JIF 3.6 in venues.yaml is not shown by PLOS.** PLOS: "We do not consider Impact Factor to be a reliable or useful metric". The number came from circulating values.
- Software criteria unchanged:
  > "The software must be downloadable anonymously in source code form and licensed under an Open Source Initiative (OSI) compliant license"
  > "the results described in the paper must be reproducible when peer reviewers or editors choose to run the software on the deposited dataset".

---

## Cross-venue notes for this cluster

- **Most permissive:** Aging Biology (no disclosure at all).
- **Heaviest disclosure:**
  - Aging and Disease: the prompt, in three places.
  - GigaByte: citation, reference, summary section and deposited outputs.
  - JOSS: mandatory section even when no AI was used, plus human-only replies to reviewers.
- **Drafting limited to language:** Royal Society (RSOS), and even language editing must be declared.
- **AI-text detector named on the venue's own page:** PNAS (Pangram).
  - PLOS "may use available AI detection tools".
  - Frontiers runs AIRA (40+ checks including "language accuracy") but names no AI-text detector.
- **Reviewer AI:**
  - Banned: PLOS, MDPI, AAAS, Impact Journals, Royal Society, A&D, PNAS, Ubiquity/JORS, GigaByte.
  - Restricted: Frontiers (in-house tool only), LSA (non-training tools), IEEE (no public platforms).
  - Allowed with disclosure: JOSS, eLife.
- **Disclosure-neutral statements:**
  - Only PLOS says disclosure will not count against a paper.
  - Royal Society ("Editors and reviewers will judge if its use is appropriate") and Ubiquity ("consider the legitimacy of any declared use ... case-by-case") say declared use is judged.
- **Validation gates for pure-computational papers:** Frontiers (all three journals; Aging's scope page says such manuscripts "will not be considered", Genetics adds "or are not highly innovative") and PLOS (health databases).
- **Not in my list but surfaced:** PLOS has a journal named **PLOS Aging and Health** (on the PLOS publications menu). It is worth a look for the aging cluster. I did not read its pages.

## Pages I could not read or that gave nothing

- https://gigabytejournal.com/policies and /author-guidelines: 404. I used /information-for-authors, /faq and /reviewer-information instead.
- `ouci.dntb.gov.ua` (Ukrainian citation index record for Ageing & Longevity): Cloudflare 403 in WebFetch and Chrome. Not needed after the journal site was found.
- `royalsociety.org/journals/ethics-policies/`: the hub page loads the AI text dynamically. I read the dedicated subpage instead.
- I found no TCBB-specific AI text and no IEEE Computer Society-level AI text. The CS author-guidelines page has only an "Artificial Intelligence" topic link.
- Aging Biology's founding by former *Aging Cell* editors is SECONDARY (third-party domain page). The journal's pages do not say it.
