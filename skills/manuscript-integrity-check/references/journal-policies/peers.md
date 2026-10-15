# Peer-venue journals: generative-AI policies (checked 2026-10-15)

> Cluster `peers`: the remaining journals where two tracked aging/bioinformatics researchers published since 2019. Lower priority than the core venues, so each section is short. Every AI rule relied on in `../venues.yaml` is quoted here verbatim. Re-fetch before relying on any rule.

## How this was read

- **Status marks.** VERIFIED: I read the venue's own page and, where it only links out, the publisher page too. PARTIAL: only part of the primary material was found. SECONDARY: third-party only. NOT FOUND: searched, nothing.
- **Routes.**
  - Headless Chrome (`--headless=new --dump-dom`, then `w3m -dump`) for MDPI, Frontiers, BMJ, link.springer.com, rombio.unibuc.ro and journals.unibuc.ro.
  - A Chrome DevTools (CDP) render that waits in real time, for pages behind a Cloudflare check that `--dump-dom` failed: journals.asm.org, tandfonline.com, journals.sagepub.com, sciencedirect.com, thelancet.com, amegroups.org, degruyterbrill.com, royalsociety.org.
  - Dated Wayback snapshots (`web.archive.org/web/<ts>id_/URL`) where every live route failed: portlandpress.com, royalsocietypublishing.org and journals.bioscientifica.com. Each item gives the snapshot date.
  - WebFetch for academic.oup.com (Reproduction). WebFetch returns short quoted fragments only.
  - `pdftotext` for The Lancet Microbe's Information for Authors PDF.
- **JIF.** Only what the journal's or publisher's own page shows. Most pages show no year (`jif_year: null`).
- **Publisher defaults written here:** `bmj`, `portland-press`, `asm`, `bioscientifica`, `de-gruyter`, `ame`. Inherited from other clusters: `mdpi`, `frontiers`, `springer-nature`, `taylor-francis`, `sage`, `elsevier`, `lancet`, `oup`, `royal-society`.
- **BMC journals.** These inherit `springer-nature`, not a `bmc` key. The springer cluster found the BMC policy page identical to the SN framework and wrote no `bmc` entry.
- **Page copies.** Kept only for the research session.

## Findings that change the picture

1. **Reproduction is no longer a Bioscientifica journal.** `rep.bioscientifica.com` now 301-redirects to `academic.oup.com/reproduction`. OUP's transition page says OUP publishes it "from 2026", and the ISSN record (via search) gives 1 Jan 2026. Bioscientifica's July 2026 journal list no longer includes it. So the OUP rules apply.
2. **ASM is the strictest publisher in this cluster.** Its policy: "AI tools should only be used to improve the language, accessibility, or quality of human-generated text", and every AI use must be disclosed in the cover letter.
3. **AME (Annals of Palliative Medicine) adopts WAME in full.** Authors must disclose "all prompts used to generate new text", plus "the time and date of a query".
4. **Bioscientifica requires a statement in every manuscript**, even one saying no AI was used. It treats non-disclosure as "research misconduct" leading to "immediate retraction".
5. **De Gruyter Brill's September 2026 policy names coding agents.** "code assistants like ClaudeCode or Cursor" count as generative AI tools.
6. **Taylor & Francis journals require a statement even when no AI was used** (Critical Reviews in Food Science and Nutrition, Drug Delivery).
7. **Romanian Biotechnological Letters has no AI policy at all.** Its OJS "Submission Guidelines" and "Statement of Publication Ethics" pages hold only placeholder text.

---

## Publisher defaults

### `bmj` — BMJ: VERIFIED

- **URL:** https://authors.bmj.com/policies/ai-use/ (dateModified 2026-05-21; footer © 2026). Read with Chrome.
- **Verbatim:**
  > "We expect authors or others who are creating content to disclose and describe use of AI technologies in (a) any content which is submitted to us, (b) any other work by the authors which underpins or is otherwise connected with the content submitted to us, and (c) any key sources which are cited, to the best of the authors' knowledge."
  > "Include an acknowledgement of AI use in the 'contributor' section of written material. If the AI use was in the course of research, a fuller description should be included in the methods section."
  > "What AI technology was used (the name of the technology)" / "Why this AI technology was used (the reason for its use)" / "How the AI technology was used (what the task of the technology was)"
  > "Consider including a summary of the input, output, and the way in which the AI output was reviewed on the part of the authors as supplementary files or additional information for the editor to review. The editor may ask for more information"
  > "BMJ will consider whether the way in which AI was used and declared is reasonable and consistent with its publication policies and practice. Content may be rejected or be subject to post-publication changes on the basis of inadequate declaration or on the particular circumstances of its use."
  > "We may, on a systematic or case by case basis, use screening tools pre-publication to assist with the identification of content generated (in whole or in part) through AI technologies. We may also use such tools post-publication."
  > Reviewers: "If reviewers use AI technology to improve word processing and language, they should declare this ... reviewers should preserve the confidentiality of the peer review process by not putting unpublished manuscripts ... into publicly available AI tools where ; the security of the confidential information cannot be guaranteed." (sic)
- **Answers.**
  - Writing help: allowed, with disclosure. There is no exemption for language editing, so I classed it `disclose_all`.
  - Disclosure: in the contributor section, plus Methods for research use. State what, why and how.
  - Prompts: a summary of input and output is encouraged (`prompts: encouraged`). The editor may ask for more.
  - Screening: AI-detection tools "may" be used, before and after publication.
  - Penalties: rejection or post-publication changes.
  - Disclosure neutral: **false**. The editor weighs "the particular circumstances of its use".

### `portland-press` — Portland Press / Biochemical Society: VERIFIED (via Wayback)

- **URL:** https://portlandpress.com/pages/editorial_policy, section "(iii) Guidance on the use of AI (Artificial Intelligence) during the publishing process".
- **Route:** the live site returned a Cloudflare page to headless Chrome, to CDP after 75 s, and 403 to WebFetch. I read the Wayback snapshot of **2026-10-01** (`web.archive.org/web/20261001065519/...`). No page date is shown.
- **Verbatim:**
  > "We allow authors to use AI to aid in the writing or editing of a manuscript or in the collection and analysis of data. However, authors must disclose, in the Materials and Methods (or similar section) of their paper, which AI tool was used and how it was used. If the AI tool is custom written, both the algorithm and the source of the data (or the data) on which it was trained should be made available to readers."
  > "Authors shall not use AI tools in generating images or videos for inclusion in their manuscript."
  > "Reviewers shall not use AI tools to summarise content that they are being asked to review. ... Uploading any article under review, including the abstract, to an AI tool will be breaking the privacy rules and is not permitted." / "Reviewers are permitted to use AI, where appropriate, to improve the language and readability of their reviewer report."
  > Plagiarism: "All papers are screened for plagiarism using Similarity Check."
- **Answers.**
  - Writing help: allowed. "Editing" is named with no exemption, so `disclose_all`.
  - Disclosure: Materials and Methods, giving the tool and how it was used.
  - Prompts: not mentioned.
  - Burden: custom AI tools must have their algorithm and training data made available. No AI images or videos.
  - Screening: Similarity Check.
  - Penalties: none stated.

### `asm` — American Society for Microbiology: VERIFIED

- **URL:** https://journals.asm.org/generative-ai (linked from https://journals.asm.org/editorial-policies). Read with CDP. The page shows no date; it links a webinar dated 25 Oct 2024.
- **Verbatim ("Guidelines for Authors Using AI Tools"):**
  > "Content completely generated by an AI tool without any significant human contribution is not allowed in ASM journals."
  > "AI tools should only be used to improve the language, accessibility, or quality of human-generated text."
  > "AI tools should not be used for images, cover art, videos, or schematics."
  > "If you use AI tools in your manuscript, it must be disclosed at submission in the cover letter."
  > "You can and may be requested to provide additional details (name and version of AI tool, purpose, prompts, input) in the manuscript."
  > "Certain exceptions can be allowed, such as manuscripts specifically about AI tools or machine learning."
  > "Authors are responsible for the accuracy of the text, figures, and references in their manuscript."
- **Plagiarism page** (https://journals.asm.org/plagiarism, "UPDATED November 2021"):
  > "ASM uses this software [iThenticate] to screen manuscripts for potential plagiarism."
- **Answers.**
  - Writing help: limited to improving human-written text. Generated content is out, so I classed it `banned_drafting`.
  - Disclosure: every AI use, in the cover letter at submission, language help included.
  - Prompts: on request (`on_request`).
  - Screening: iThenticate only.
  - Burden: no AI schematics or images.
  - Gap: AI-written analysis code is not addressed. Ask staff (exceptions are "evaluate[d] each case individually").
  - Reviewer rules: the reviewers page (https://journals.asm.org/reviewers) has no AI text.

### `bioscientifica` — Bioscientifica: VERIFIED (via Wayback)

- **URLs:** https://journals.bioscientifica.com/joe/pages/ethical-policy (Wayback **2026-08-08**) and https://journals.bioscientifica.com/joe/pages/author-guidelines (Wayback **2026-07-24**). These are Journal of Endocrinology pages; the author guidelines call the ethical-policy text "Our full publisher policy". The live site returned 403 to WebFetch and a Cloudflare page to Chrome. The bioscientifica.com "Ethics for authors" page (Wayback 2026-05-20) has no AI text.
- **Verbatim (ethical policy):**
  > "Any use of an LLM or AI technology should be described in detail within the Materials and Methods section of the article."
  > "AI-generative tools should also not be used to create images in submitted manuscripts, except when it is an integral part of the research design or methodology."
  > "Any failure to disclose the use of these tools will be considered research misconduct and will result in immediate retraction of the article."
  > "Disclosure is not required for reference management software, such as Mendeley, EndNote, Zotero and similar tools"
  > Reviewers: "not upload the document or otherwise input the content into an Artificial Intelligence, Large Language Model, or similar tool in the course of preparing their review"
- **Verbatim (author guidelines, "AI Disclosure"):**
  > "We ask all authors to disclose in a statement whether or not they have used generative AI in the preparation of their manuscript. ... This explanation must list the name, version, model, and source of the generative AI technology. Where no AI technology has been used in the preparation of the manuscript, please state the following: 'No generative Artificial Intelligence (AI) tools were used in the preparation of the written or visual content of this manuscript.'"
- **Answers.**
  - Writing help: allowed, with disclosure of any use (`disclose_all`).
  - Disclosure: Materials and Methods plus an AI Disclosure statement, which is required even when no AI was used.
  - Penalty: undisclosed use is misconduct, followed by retraction.
  - Reviewers: banned from using AI on the manuscript.
  - Applies to no journal in this cluster now (see Reproduction).

### `de-gruyter` — De Gruyter Brill: VERIFIED

- **URL:** https://www.degruyterbrill.com/publishing/for-authors/author-policies/artificial-intelligence ("As of September 2026"). Read with CDP; degruyter.com redirects to degruyterbrill.com.
- **Verbatim:**
  > "We do not accept papers (journal articles, book chapters, etc.) that are generated by Artificial Intelligence (AI) or Machine Learning Tools primarily because such tools cannot take responsibility for the submitted work"
  > "If Artificial Intelligence (AI) or machine learning tools or technologies are used as part of the design or methodology of a research study, their use should be clearly described in an acknowledgements section."
  > "The use of AI tools must be disclosed when their output has significantly contributed to any part of your manuscript. The use of such tools for simple proofreading and copy-editing does not have to be declared."
  > "Document which AI tools you use and how you use them throughout your research and writing process."
  > "Examples include ChatGPT, Copilot, Gemini and others, image generators such as Midjourney or DALL-E, and code assistants like ClaudeCode or Cursor."
  > "We permit the use of Generative AI tools to create images, including cover images and illustrative images ... authors must disclose the use of any AI-generated or AI-assisted images at the time of submission"
  > "The use of Generative AI to create, alter, manipulate, or enhance research data, figures, or experimental images is not permitted."
  > Peer review: "The manuscript or any parts thereof should not be entered into AI systems, such as Chat GPT, Grammarly, etc."
- **Answers.**
  - Writing help: allowed. Significant contributions must be disclosed; proofreading is exempt (`disclose`).
  - Disclosure: in an acknowledgements section.
  - Tracking: keeping records is recommended.
  - Coding agents are named, so code they wrote that "significantly contributed" is disclosable.
  - Papers "generated by AI" are not accepted.
  - Reviewers: banned.

### `ame` — AME Publishing Company: PARTIAL

- **URLs:** https://apm.amegroups.org/pages/view/guidelines-for-authors and https://tlcr.amegroups.org/pages/view/guidelines-for-authors. Both read with CDP and contain identical wording.
- **What I checked.** I found no publisher-wide AI page. APM's editorial-policies, publication-ethics and plagiarism-screening pages have no AI text. Quantitative Imaging in Medicine and Surgery's guidelines have no AI text either, so the clause is per journal. Hence PARTIAL.
- **Verbatim (APM, TLCR):**
  > "Authors must disclose in the Cover letter, Materials and Methods, and the Acknowledgement for applying any AI tools (e.g., ChatGPT, Bing) in the writing of a manuscript, production of images or graphical elements of the paper, or in the collection and analysis of data. Disclosure should include - but is not limited to - all prompts used to generate new text, or to convert text or text prompts into tables or illustrations; the full prompt used to generate the research results; the time and date of a query; and the AI tool used and its version."
  > "Referencing AI-generated material as the primary source is not acceptable."
- **Answers.**
  - Writing help: any AI use in writing is disclosed (`disclose_all`).
  - Disclosure: three places, the cover letter, Methods and Acknowledgement.
  - Prompts: **all** prompts are required, with dates and times (`prompts: required`, `tracking: required`).
  - Screening: iThenticate (APM plagiarism policy).

---

## Journals

### MDPI: Cancers, Metabolites, Pharmaceutics — VERIFIED

- **URLs:** https://www.mdpi.com/journal/{cancers,metabolites,pharmaceutics}/instructions; publisher policy https://www.mdpi.com/ethics ("Artificial Intelligence"). Read with Chrome. No page date.
- **Journal pages.** All three restate the MDPI rule in their own section text:
  > Methods: "Where applicable, authors are required to disclose in this section details of how GenAI has been used in the paper (e.g., to generate text, data or graphics or assist in study design or data collection, analysis or interpretation). The use of GenAI for superficial text editing (e.g., regarding grammar, spelling, punctuation and formatting) does not need to be declared."
  > Acknowledgments: "Where GenAI has been used for purposes such as generating text, data or graphics, study design, or data collection, analysis or interpretation, please add 'During the preparation of this manuscript/study, the author(s) used [tool name, version information] for the purposes of [description of use]. The authors have reviewed and edited the output and take full responsibility for the content of this publication'."
- **Publisher page adds:**
  > "authors are required to declare this during the submission process"
  > Reviewers: "Under no circumstances should reviewers upload manuscripts ... to any GenAI tools"
- **Difference between the two.** The journal pages exempt "superficial text editing" and drop the ethics page's word "structure".
- **JIF** (home page header, no year): Cancers 4.8, Metabolites 4.5, Pharmaceutics 6.9.
- **Cancers desk rules:**
  - A Simple Summary of at most 150 words; "Submissions without a simple summary will be returned directly".
  - "research articles using only one cell line ... will not be considered".
  - "Articles should have more than 30 references".
- **Answers.**
  - Writing help: disclose substantive use; superficial edits are exempt.
  - Disclosure: at submission, in Methods and in Acknowledgments.
  - Prompts: none required.
  - Screening: iThenticate (publisher).

### Frontiers: Nutrition, Microbiology, Oncology, Neuroscience — VERIFIED

- **URLs:** https://www.frontiersin.org/journals/{nutrition,microbiology,oncology,neuroscience}/for-authors/author-guidelines and the matching /article-types pages; publisher policy https://www.frontiersin.org/guidelines/policies-and-publication-ethics. Read with Chrome. No page date.
- **Journal pages ("Guidelines for artificial intelligence").** Identical on all four:
  > "If the author of a submitted manuscript has used written or visual content produced by or edited using a generative AI technology, such use must be acknowledged in the acknowledgements section of the manuscript and the methods section if applicable. This explanation must list the name, version, model, and source of the generative AI technology. We encourage authors to upload all input prompts provided to a generative AI technology and outputs received from a generative AI technology in the supplementary files for the manuscript."
- **Publisher page adds:**
  > "If AI tools have been used to generate main text, then this must be clearly disclosed in the acknowledgments."
  > "Frontiers' journals require that manuscripts primarily comprising solely of bioinformatics analyses, computational studies of public data, or findings from Mendelian Randomisation studies must include appropriate validation."
  > "All Frontiers' journals employ detection technologies and manual checks to identify submissions that exhibit characteristics of such misconduct" (paper mills).
  > Reviewers: "manuscript content must not be uploaded to external generative AI tools", but Frontiers provides "an internal AI tool within the review forum".
- **JIF** (journal home header, no year): Nutrition 5.5, Microbiology 5.8, Oncology 3.4, Neuroscience 4.0.
- **Limits:** 12,000 words for Original Research, Methods and Reviews.
- **Software:** only Frontiers in Microbiology lists **Technology & Code** ("new technology, code and/or software ... placed online in a repository").
- **Answers.**
  - Writing help: any content "produced by or edited using" generative AI is disclosed (`disclose_all`, inherited).
  - Prompts and outputs: encouraged as supplementary files.
  - Validation: a computational-only paper needs it.

### BMJ Open — VERIFIED

- **URLs:** https://bmjopen.bmj.com/pages/authors; home https://bmjopen.bmj.com/. Read with Chrome.
- **AI text.** The journal page has none. It says: "To view all BMJ Journal policies please refer to the BMJ Author Hub policies page." So the `bmj` default applies.
- **Other text:**
  > "BMJ runs manuscripts through iThenticate during the peer review process."
- **JIF:** "Impact Factor: 2.5" (no year).
- **Answers.**
  - BMJ default: declare in Contributors (and Methods); a summary of AI input and output is encouraged; AI detection may be used.
  - Other requirements: an open peer review history is published, and a Patient and Public Involvement statement is required.

### Biochemical Journal — VERIFIED (via Wayback)

- **URL:** https://portlandpress.com/biochemj/pages/instructions_to_authors. Wayback **2026-07-25**; the live site is Cloudflare-blocked.
- **AI text.** The page has none. Its menu links "Editorial policy", so the `portland-press` default applies.
- **JIF:** "Impact Factor: 4.3 2024 Impact Factor, Journal Citation Reports (Web of Science Group, 2025)", from the Impact_and_Information snapshot of 2025-07-13. The 2025 JIF was not seen.
- **Other rules:**
  - Methods sit in the main text after the Discussion.
  - A Data Availability Statement is required.
  - "meta-analyses, systematic and bibliographical reviews are not considered".

### Bioscience Reports — VERIFIED (via Wayback)

- **URLs:** https://portlandpress.com/bioscirep/pages/paper_types (Wayback **2026-07-14**) and /submission_checklist (Wayback 2025-07-16). The Portland Press-wide checklist (Wayback 2026-07-25) has no AI text either.
- **AI text.** None on the journal pages, so the `portland-press` default applies.
- **JIF:** "Impact Factor: 4.7 2024 Impact Factor ..." (snapshot of 2025-07-08).
- **Other:** an APC on all articles (Brief Reports pay a reduced charge); Brief Report at most 4,000 words.

### Microbiology Spectrum (ASM) — VERIFIED

- **URLs:** https://journals.asm.org/journal/spectrum/article-types, /journal/spectrum/about, and https://journals.asm.org/editorial-policies?journal=spectrum. Read with CDP.
- **AI text.** The journal pages have none; editorial-policies links "ASM policy on use of generative AI in your submission", so the `asm` default applies.
- **About page:** "an online-only, fully open-access journal". Articles are "Published Under CC-BY (4.0) License". No JIF shown.
- **Limits:** Research Articles, Resource Reports and Methods and Protocols are 5,000 words ("excluding Materials and Methods, References, tables, and figure legends"). The abstract is at most 250 words, plus an Importance section of at most 150.
- **Fit.** Resource Reports cover "technical advances and/or informational databases"; Methods and Protocols cover "bioinformatic or laboratory techniques".

### Reproduction (OUP since 2026) — VERIFIED (via WebFetch)

- **URLs:** https://academic.oup.com/reproduction/pages/author-guidelines, https://academic.oup.com/reproduction, https://academic.oup.com/pages/reproduction-transition. All read via WebFetch fragments; OUP blocks Chrome. `curl -I https://rep.bioscientifica.com/` returns `301 location: https://academic.oup.com/reproduction`.
- **Verbatim fragments (author guidelines):**
  > "Natural language processing tools driven by artificial intelligence (AI) do not qualify as authors," / "the Journal will screen for them in author lists."
  > "The use of AI (for example, to help generate content or images, write code, process data, or for translation)" / "should be disclosed both in cover letters to editors and in the Methods or Acknowledgements section of manuscripts."
  > "Please see the COPE position statement on Authorship and AI". The page links COPE, not the OUP policy page.
  > "Manuscripts will be screened using iThenticate to help detect publication misconduct including plagiarism"
- **Transition page:** "Oxford University Press to partner with the Society for Reproduction and Fertility to publish _Reproduction_ from 2026".
- **JIF:** 3.4, labelled "2025 Impact Factor" (journal home, via WebFetch).
- **Limits:** "Research Paper—maximum word count: 5000"; "Unstructured abstract—maximum word count: 250".
- **Answers.** The OUP default applies, under OUP's 13 July 2026 policy: disclose in the cover letter and in Methods or Acknowledgements, and update the disclosure at revision. Code, data processing and translation are named explicitly.

### BMC Cancer, BMC Microbiology, Cancer Cell International, Diabetology & Metabolic Syndrome (BMC) — VERIFIED

- **URLs:** https://link.springer.com/journal/{12885,12866,12935,13098}/submission-guidelines and their research-article pages (13098 uses `/research`). BMC Cancer's software-article page was read too. All read with Chrome.
- **Verbatim.** Each article-type page, under "Title page", has the BMC sentence, with no copy-editing exemption:
  > "Large Language Models (LLMs), such as ChatGPT, do not currently satisfy our authorship criteria. Notably an attribution of authorship carries with it accountability for the work, which cannot be effectively applied to LLMs. Use of an LLM should be properly documented in the Methods section (and if a Methods section is not available, in a suitable alternative part) of the manuscript."
- **Landing pages** advertise an AI language checker:
  > "You can also upload your manuscript and get a free language check from our partner AJE. The software uses AI to make suggestions that can improve writing quality."
- **JIF** ("Journal Impact Factor ... (2025)"): BMC Cancer 4.1, BMC Microbiology 5.4, Cancer Cell International 7.0, Diabetology & Metabolic Syndrome 4.9.
- **Abstracts:** at most 350 words.
- **Software:** BMC Cancer and BMC Microbiology have Software and Database article types; the other two do not.
- **Answers.** The SN framework applies (`red_line`): disclose in Methods and in an AI declaration. AI-written Results or Discussion is Red. SN runs publisher-wide detectors (see `springer-nature`).

### Cellular and Molecular Neurobiology, Applied Intelligence (Springer) — VERIFIED

- **URLs:** https://link.springer.com/journal/10571/submission-guidelines and https://link.springer.com/journal/10489/submission-guidelines. Read with Chrome.
- **Verbatim.** The Springer-brand sentence, with the exemption:
  > "Use of an LLM should be properly documented in the Methods section ... The use of an LLM (or other AI-tool) for 'AI assisted copy editing' purposes does not need to be declared. In this context, we define the term 'AI assisted copy editing' as AI-assisted improvements to human-generated texts for readability and style, and to ensure that the texts are free of errors in grammar, spelling, punctuation and tone. These AI-assisted improvements may include wording and formatting changes to the texts, but do not include generative editorial work and autonomous content creation."
  > "Please check Springer's policy on generative AI images and make sure your work adheres to the principles described therein."
- **JIF (2025):** Cellular and Molecular Neurobiology 7.4 ("now fully open access ... as of February 2024"); Applied Intelligence 3.5 (Hybrid).
- **Abstracts:** 150–250 words.

### Critical Reviews in Food Science and Nutrition, Drug Delivery (Taylor & Francis) — VERIFIED

- **URLs:** https://www.tandfonline.com/action/authorSubmission?show=instructions&journalCode=bfsn20 (read with CDP) and ...&journalCode=idrd20 (read with Chrome); journalInformation pages for the JIF; publisher policy https://taylorandfrancis.com/our-policies/ai-policy/ (read with Chrome).
- **Verbatim (both journals, checklist item 8):**
  > "Declaration of generative AI use. Please include a statement disclosing whether and how generative AI has been used in the research and manuscript preparation process. If generative AI was not used, please state this (suggested wording: The authors report generative AI was not used in their research or preparation of this manuscript)."
- **Verbatim (publisher page):**
  > "Authors must clearly acknowledge within the article or book any use of Generative AI tools through a statement that includes: the full name of the tool used (with version number), how it was used and the reason for use."
  > "Note that some journals may not allow use of Generative AI tools beyond language improvement"
  > "Authors should not submit manuscripts where Generative AI tools have been used in ways that replace core researcher and author responsibilities ... These types of cases may be subject to editorial investigation."
  > Reviewers: "Reviewers must not use artificial intelligence tools to generate manuscript and proposal review reports"
- **JIF (2025):** CRFSN 10.6, Drug Delivery 8.0.
- **CRFSN:** "There are no word limits for papers in this journal"; abstract 200 words; accepts "original articles"; Open Select (hybrid).
- **Drug Delivery:**
  - Abstract 250 words.
  - APC USD 3,940 invoiced once a paper has a DOI, so treated as fully OA.
  - Types include Methods and Data notes.
- **Answers.** A statement is required either way. Neither journal restricts AI beyond the T&F policy.

### Statistical Methods in Medical Research (Sage) — VERIFIED

- **URLs:** https://journals.sagepub.com/author-instructions/SMM (read with CDP), https://journals.sagepub.com/home/smm, and https://www.sagepub.com/journals/publication-ethics-policies/artificial-intelligence-policy (read with Chrome).
- **Journal page (verbatim):**
  > "Please note that AI chatbots, for example ChatGPT, should not be listed as authors. For more information see the policy on Use of ChatGPT and generative AI tools."
- **Publisher page (verbatim):**
  > "We distinguish various uses for AI and related technologies as: assistive (and no longer requiring disclosure), generative (requiring disclosure), and prohibitive."
  > "While submissions will not be rejected solely because of the disclosed use of GenAI tools, if the editor becomes aware that GenAI was inappropriately used in the preparation of a submission without disclosure, the editor reserves the right to reject the submission"
- **JIF:** "Impact Factor: 2.4" (no year).
- **Limits:** "Papers should be around 8,000 words"; "An abstract of up to 200 words".
- **OA:** Sage Choice (hybrid).

### Annals of Epidemiology, Hepatobiliary & Pancreatic Diseases International (Elsevier) — VERIFIED

- **URLs:** the ScienceDirect guide-for-authors pages for both journals. Read with CDP.
- **Verbatim (both guides, Elsevier 2026 text):**
  > "Authors must declare the use of generative AI tools in the manuscript preparation process upon submission of the paper."
  > "The use of AI tools in the manuscript preparation process must be declared by adding a statement at the end of the manuscript when the paper is first submitted. The statement will appear in the published work and should be placed in a new section before the reference list."
  > "The declaration does not apply to the use of basic tools, such as tools used to check grammar, spelling, and references."
  > "this journal does not currently allow academic editors and reviewers to upload an unpublished manuscript into a generative AI tool"
- **JIF** (header, no year): Annals of Epidemiology 3.6, HBPD Int 3.9.
- **Limits:**
  - Annals of Epidemiology: Original article "<=3000 words; structured abstract <=200 words".
  - HBPD Int: structured abstract "no more than 300 words".
- **Answers.** The Elsevier default applies: a declaration before the references, Methods for research use, and records kept in case editors ask.

### European Neuropsychopharmacology (Elsevier) — VERIFIED

- **URLs:** https://www.sciencedirect.com/journal/european-neuropsychopharmacology/publish/guide-for-authors (read with CDP); publisher policy https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals (read with CDP, "Policy updated June 2026.").
- **AI text.** The guide is an older free-text template with **no AI section**, so the Elsevier policy applies. Verbatim from the Elsevier page:
  > "Authors should disclose the use of AI tools for manuscript preparation in a separate AI declaration statement included in their manuscript upon submission."
  > "Inclusion of fabricated references may lead to rejection of a manuscript."
  > "Authors should keep a separate record of which tool and model was used, and how AI tools were used."
- **JIF:** 8.1 (no year).
- **Limits:** "Full length Research Papers ... max. 6500 words (including tables and legends to figures) and no more than 80 references". "your article may be checked by the originality detection service Crossref Similarity Check".

### The Lancet Microbe — VERIFIED

- **URLs:**
  - Information for Authors PDF: https://www.thelancet.com/pb-assets/Lancet/authors/tlmicro-info-for-authors-1787150928107.pdf, footer "www.thelancet.com August 2026". Read with curl and pdftotext.
  - Group policy: https://www.thelancet.com/editorial-policies (read with CDP).
  - About page: https://www.thelancet.com/lanmic/about.
  - The old URL /lanmic/information-for-authors returns "This page does not exist".
- **Verbatim (group page):**
  > "Upon submission, authors will be asked to declare the use of AI tools. ... Editors reserve the right to determine whether the use of AI is appropriate, and our policies differ depending on the content type."
- **Verbatim (journal PDF):**
  > "Authors should disclose the use of AI tools for manuscript preparation in a separate AI declaration statement at the end of their manuscript upon submission and this statement will appear in the published work. Authors should document their use of AI, including the name and version of the AI tool used, the purpose of the use, and the extent of their oversight. Prompts should be provided where applicable and editors reserve the right to ask authors for these."
  > "Basic checks of grammar, spelling, and punctuation need no declaration. AI use in the research process should be declared and described in detail in the Methods section."
  > "For figures, generative AI should be used primarily as a tool for brainstorming and suggesting image concepts. Its direct use in creating figures or artwork should be limited to demonstrations of its capabilities in specific contexts"
  > "For Comments and Correspondence, the use of AI-assisted tools and generative AI is permitted only to assist with grammar and spelling. ... Any breach of this policy will lead to rejection of your Comment or Correspondence."
- **JIF:** "21.9 Impact Factor ... Journal Citation Reports 2025 (Clarivate Analytics, 2026)".
- **OA:** "The Lancet Microbe is a gold open access journal."
- **Limits:** Articles "up to 3500 words (4500 for randomised controlled trials)"; summary "not exceeding 300 words".
- **Answers.**
  - Writing help: disclose beyond basic checks.
  - Disclosure: a published AI declaration, plus Methods for research use.
  - Prompts: "where applicable", and editors may ask (`on_request`).
  - Comments and letters: grammar and spelling only.

### Biology Letters (Royal Society) — VERIFIED

- **URLs:**
  - Author page: https://royalsocietypublishing.org/rsbl/pages/for-authors, Wayback **2026-10-04**. The live site is Cloudflare-blocked; Chrome, CDP and WebFetch all failed.
  - Home page: Wayback 2026-10-09.
  - Publisher policy: https://royalsociety.org/journals/ethics-policies/artificial-intelligence/, read live with CDP.
- **AI text.** The journal page has none. It says: "Please take care to follow the Royal Society Publishing Instructions for Authors ... Our editorial policies can be found here." So the `royal-society` default applies.
- **Verbatim (RS policy):**
  > "Authors must disclose in the manuscript their use and a statement will be required in the published work. ... Published articles in which the use of such technologies is subsequently discovered may be retracted."
  > "Where used in the writing process, these technologies should only be used to improve readability and language of the work. Use of AI in language editing must be declared."
  > "Journals reserve the right to ask authors who use AI for their corresponding prompts and outputs, which can be supplied as ESM files."
- **Journal page:**
  > "For Biology Letters the word limit is 3500 words for Research articles and Opinion pieces ... The word count is strictly enforced."
  > "Submissions are routinely screened for plagiarism and, where relevant, image integrity"
- **Home page:** "Impact factor: 2.7" (no year); "Open Access with no charges for authors or readers".
- **Answers.** Writing help is limited to readability, and even language editing is declared (`banned_drafting`, inherited). Prompts and outputs can be requested.

### Current Directions in Biomedical Engineering (De Gruyter Brill) — VERIFIED

- **URL:** https://www.degruyterbrill.com/journal/key/cdbme/html (read with CDP).
- **AI text.** The journal page has none beyond the publisher menu link "AI Guidelines for Authors", so the `de-gruyter` default applies.
- **Other text:** "Submission of conference proceedings contributions is only possible via the current year's organizers"; "All proceedings papers are published open access with a CC BY 4.0 license without costs for the author."
- **JIF:** none shown.

### Annals of Palliative Medicine (AME) — VERIFIED

- **URL:** https://apm.amegroups.org/pages/view/guidelines-for-authors (read with CDP). The AI clause is quoted under `ame` above.
- **Indexing:** the home page lists "PubMed/MEDLINE" and "Ovid" only. No JIF is shown.
- **Limits:** "Abstract: 200–450 words structured"; "there is no fixed word limit for research articles".
- **Plagiarism:** iThenticate (plagiarism-screening policy page).
- **Answers.** Every prompt must be disclosed, with the date and time of each query, in the cover letter, Methods and Acknowledgement. This is the heaviest prompt burden in the cluster.

### Romanian Biotechnological Letters — VERIFIED (no AI policy)

- **Publisher:** University of Bucharest. The OJS "About" page says "published by the University of Bucharest". Per the ISSN record (via search), the publisher was Ars Docendi until 2020.
- **Pages read with Chrome:**
  - legacy site: https://rombio.unibuc.ro/instructions-for-authors/ and https://rombio.unibuc.ro/ethics-and-malpractice/;
  - OJS site: https://journals.unibuc.ro/index.php/rbl, /about, /about/submissions, /guid, /spe, /peer_review_policy and /en/information/authors.
- **Finding.** No page mentions AI, LLMs or ChatGPT. The OJS policy pages are unfilled placeholders:
  > "Submission Guidelines here" (/guid) and "Statement of Publication Ethics here" (/spe).
- **What the instructions do require.** The cover letter must state "That the manuscript is conform with Uniform Requirements for Manuscripts Submitted to Biomedical Journals (ICMJE)". The ICMJE's January 2026 Section V asks for AI disclosure in the cover letter and the manuscript, so following ICMJE is the defensible course.
- **Other details:**
  - Plagiarism: the journal "manifests zero tolerance for plagiarism"; a published paper may be withdrawn for "plagiarism".
  - Licence: CC BY-NC-ND 4.0.
  - Abstract: at most 1,000 characters.
  - Current issue: "Vol. 28 No. 6 (2023)", "Published: 2025-09-15". This is a long backlog.
  - Indexing: claims SCIE; no JIF is shown.
- **Answers.** There is no rule on writing help, disclosure, prompts or detection. Disclose per ICMJE anyway: a cover-letter sentence plus Acknowledgements or Methods.

---

## Pages I could not read live

| Page | Problem | What I used |
|---|---|---|
| portlandpress.com (all pages) | Cloudflare, stuck at "Waiting for portlandpress.com to respond" in Chrome and CDP; WebFetch 403 | Wayback snapshots, 2025-07 to 2026-10-01 |
| royalsocietypublishing.org/rsbl | Cloudflare (Chrome, CDP); WebFetch 403 | Wayback 2026-10-04 and 2026-10-09 |
| journals.bioscientifica.com | WebFetch 403; Chrome passed once, then Cloudflare | Wayback 2026-07-24 and 2026-08-08 |
| academic.oup.com/reproduction | Cloudflare (not tried in Chrome, per brief) | WebFetch fragments |
| journals.asm.org | Chrome passed once, then Cloudflare; WebFetch 403 | CDP render worked |

Not found: a publisher-wide AME AI page; an AI policy of any kind for Romanian Biotechnological Letters or Bucharest University Press; a JIF on the Microbiology Spectrum, CDBME, APM and RBL pages.
