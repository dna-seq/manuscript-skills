# Wiley, Taylor & Francis, Sage / Mary Ann Liebert and Karger: AI policies (checked 2026-10-15)

Cluster "wiley" for the venue database. Entries are in `../venues.yaml`. Status marks follow
`target-journals.md`: **VERIFIED** (I read the venue's or publisher's own page), **PARTIAL**, **SECONDARY**, **NOT FOUND**.

## How the pages were read

- **Headless Chrome** (`--dump-dom`, then `w3m -dump`), so quotes are exact text. Wiley Online Library, tandfonline.com and
  journals.sagepub.com sometimes return a Cloudflare "Performing security verification" page; a retry got through each time.
- **karger.com** returns 403 to curl and Cloudflare to Chrome. I used WebFetch (fragments of 125 characters or less) and,
  for verbatim text, the Wayback snapshot of 2026-10-01 (`curl` + `w3m`).
- **academic.oup.com/ger** (Gerontology): Chrome hit the Cloudflare challenge and Wayback has no snapshot, so this page was
  read **through WebFetch only** (short fragments).
- **Old Liebert policy**: Wayback snapshot 2025-07-09 of home.liebertpub.com.
- The JIF is quoted only where the journal's or publisher's page shows it. Wiley labels the figure "2025 Journal Impact
  Factor (Clarivate)". Sage gives "Journal Citation Reports from Clarivate, 2026". T&F shows "1.6 (2025) Impact Factor" and
  Oxford Academic "2025 Impact Factor". These are probably one JCR release labelled two ways; `jif_year` records each label as shown.

---

## Publisher defaults

### Wiley: VERIFIED

- Ethics guidelines: https://authorservices.wiley.com/ethics-guidelines/index.html. Page date: **"Last updated: July 2026."**
- AI guidelines for researchers: https://www.wiley.com/en-gb/publish/article/ai-guidelines/. No date shown; its
  FAQ-methods note says it was drafted with AI tools in July to August 2025.
- Image screening press release, 26 May 2026:
  https://newsroom.wiley.com/press-releases/press-release-details/2026/Wiley-Bolsters-Research-Integrity-Efforts-with-Imagetwins-Enhanced-Image-Screening/default.aspx
  (read through WebFetch).
- Route: Chrome for the two policy pages.
- Re-check of publisher-policies.md §4.3: the quotes there still match the live pages. New below: the
  disclosure-neutral sentence, the reviewer ban and the screening note.

Verbatim (ethics page):
> "Authors should document all AI Technology used, including its purpose, whether it influenced key arguments or conclusions, and how they personally reviewed and verified any AI-generated content. Authors must also disclose their use of AI Technologies when submitting a manuscript to a Wiley journal. If disclosure is not provided at submission, it may be requested during peer review or after publication."
> "If an author has used AI Technology to substantially edit, develop, or translate any part of a manuscript, its use must be described transparently and integrated into the manuscript ... AI Tools used solely for spelling, grammar, and general editing are not included in these disclosure requirements."
> "The final decision on whether using AI Technology is appropriate or permissible for a submitted manuscript or a published article belongs to the journal's editor"
> "Beyond this limited use, editors and peer reviewers are not permitted to upload manuscripts (or any parts of manuscripts including figures and tables) into AI Technology."

Verbatim (AI guidelines page):
> "Wiley requires disclosure of AI when used to generate substantial text or restructure arguments. ... Simple grammar correction, formatting, and word choice suggestions typically do not require disclosure."
> Placement: "In your Acknowledgments when AI assists with manuscript drafting, editing, translation, or formatting. In your Methods when AI is used to assist with your research methodology, data collection or analysis, or literature review processes. In your figure captions when AI generates or edits any visual content"
> Methods disclosure: "we require that you share: AI Technology name and version; Date/year of use; The AI Technology's role in your work ...; The author's role in directing or reviewing the work of the AI Technology; For sensitive, proprietary, or human subject data describe how privacy and compliance requirements were maintained"
> Code rows that require disclosure: "Programming: AI writes analysis scripts or algorithms"; "Software generation: AI develops custom research software or applications"; "Data pipeline design"; "Modeling". No disclosure: "Debugging", "Code style", "Documentation: AI generates comments or documentation", "Suggestions".
> "If AI contributed substantially to your analysis or methodology, you may be asked to provide supplemental documentation ... such as: Prompts or parameters used; AI settings or configurations; Code repository"
> "Document your AI use consistently throughout your project so you can adapt disclosures as needed (AI Technology and version, month accessed, why it was used)"
> **"At Wiley, AI use in manuscript development is not grounds for rejection."** Listed as "Evidence of integrity concerns that may warrant rejection": "Fabricated citations or references".
> Reviewers: "Manuscripts under review are confidential and must not be uploaded to AI Technologies, whether in full or in part." Reviewers may "Use AI to improve review clarity and tone or translate your review", and "We require disclosure of AI when it's used for drafting assistance in your reviews."
> Screening: "Integrity screening: AI Technologies are being used to detect plagiarism, image manipulation, and other research integrity issues during the editorial process."
> "AI-edited photographs are not permitted in Wiley journals." "Factual and evidential images are not permitted."

Press release (WebFetch): Imagetwin "detects a comprehensive range of integrity issues", including "AI-generated content"
in images. It rolls out from "life sciences, biomedical research, and materials science". **No AI-text detector is named.**

**Answers**
1. **Writing help:** allowed. Generating substantial text, restructuring arguments, translating, and tone or argument
   feedback all need disclosure. Polishing, conciseness and citation formatting are exempt.
2. **Disclosure:** at submission, then in the manuscript. AI help with writing goes in the Acknowledgments, research use in
   Methods, visuals in captions. Give the tool and version, the date, the tool's role, the sections and the author's oversight.
3. **Prompts:** on request ("may be asked").
4. **Screening:** AI integrity flags in Research Exchange, plus Imagetwin for images. No text detector.
5. **Penalties:** a missing disclosure can be requested later. Fabricated references may warrant rejection.
6. **Neutrality:** disclosed AI use "is not grounds for rejection".
7. **Costs authors work:** AI-written analysis code, pipelines and models go in Methods with version and date. You must
   check that the tool's terms do not claim rights over the manuscript or train on it. Keep a running log of AI use.

### Taylor & Francis: VERIFIED (new, stricter author-services page)

- Corporate policy: https://taylorandfrancis.com/our-policies/ai-policy/ (metadata datePublished 2025-11-19; the text
  matches publisher-policies.md §4.4).
- **Author-services page:** https://authorservices.taylorandfrancis.com/editorial-policies/using-ai-in-your-research-and-manuscript-preparations/
  (`article:modified_time` 2026-08-26).
- Authorship policy: https://authorservices.taylorandfrancis.com/editorial-policies/defining-authorship-research-paper/
  (modified 2026-08-18).
- Route: Chrome.

Verbatim (author-services page, table "Summary of permitted AI uses and declaration requirements"; row name, then the
"Permitted use" cell):
> Row "Drafting manuscript text": **"No – Taylor & Francis does not allow generative AI to create a first draft of a manuscript or sections of a manuscript."**
> Row "Copyediting & language refinement": "Yes – generative AI can be used to improve the spelling, grammar and flow of an article. It cannot be used to create or conclude the argument of an article."
> Row "Software coding assistance": "Yes – generative AI can be used to generate software code as long as it has been reviewed and verified by the author for accuracy."
> "Literature reviews ... It cannot be used to conduct and interpret the entire literature review ... It cannot be used to generate an entire reference list or bibliography."
> "Include a statement disclosing whether and how you used generative AI in your research or manuscript preparation. ... If you didn't use generative AI, state that clearly."
> Research methods: "Authors must retain full records of the methods undertaken, including full descriptions and records of the prompts used, which must be shared with the journal upon request."

Verbatim (authorship page):
> "Please add a Declaration of generative AI use statement disclosing whether and how generative AI has been used in the research and manuscript preparation process. If generative AI was not used, please state this"
> "Use of AI tools to assist copyediting, reference management and language refinement is permitted. ... Authors must retain the original and revised versions of the article, which must be shared with the Editor upon request. A declaration from the author must be included within the submission"
> "When you submit your work to a Taylor & Francis journal you may be asked to confirm that you have disclosed within your manuscript any use of AI tools. ... so that they can assess whether they have been used appropriately and responsibly."

Verbatim (corporate page):
> "Taylor & Francis will retain its discretion over publication of the work, to ensure that integrity and guidelines have been upheld."
> "Note that some journals may not allow use of Generative AI tools beyond language improvement"
> "peer reviewers must not upload unpublished manuscripts or project proposals, including any associated files, images, or information, into Generative AI tools. Reviewers must not use artificial intelligence tools to generate manuscript and proposal review reports ... However, Generative AI may be utilised to assist with improving review language."

**Answers**
1. **Writing help:** **a first draft of the manuscript or any section by AI is not allowed** (author-services page). AI may
   copyedit for "spelling, grammar and flow" but not "create or conclude the argument". Coding help is allowed if verified.
   The corporate page alone reads more permissively ("Text or code generation without rigorous revision" is barred). Follow
   the newer, stricter page.
2. **Disclosure:** a "Declaration of generative AI use" in every article, **including a statement that none was used**.
   It gives the tool and version, how and why it was used, and confirms originality and accuracy, that the tool's terms were
   checked, and that the authors take full responsibility including for the references. Research use goes in Methods as
   well; AI visuals in the figure legend.
3. **Prompts:** records kept and shared on request when AI is part of the research method or a literature review.
4. **Screening:** plagiarism only (journal pages name Crossref). No AI detector named.
5. **Penalties:** "editorial investigation"; T&F keeps "discretion over publication".
6. **Neutrality:** not neutral in wording. Editors "assess whether they have been used appropriately and responsibly".
7. **Costs authors work:** keep original and AI-revised versions of the text, and prompt logs for research use. The
   declaration is mandatory even when no AI was used.

### Sage: VERIFIED (no date on page)

- https://www.sagepub.com/journals/publication-ethics-policies/artificial-intelligence-policy. The section body is
  identical at /journals/editorial-policies/artificial-intelligence-policy and at /generative-AI-tools-policy-msg (the
  link every Sage and Liebert journal page uses); I diffed them.
- Route: Chrome. Matches publisher-policies.md §4.5.

Verbatim:
> "We distinguish various uses for AI and related technologies as: assistive (and no longer requiring disclosure), generative (requiring disclosure), and prohibitive."
> "AI tools that make suggestions to improve or enhance your own work, such as tools to improve language, grammar, or structure, are considered assistive AI tools and do not require disclosure by authors or reviewers."
> "The primary or partial use of AI tools and/or LLMs that produce content such as references, text, images, or any other content that directly impacts the research methodology, analysis, results and/or conclusions must be disclosed upon submission so the editorial team can evaluate the content generated."
> "Authors should consider the following as appropriate uses for GenAI in research publishing that require disclosure within the methods or acknowledgements: ... 3. Using software or code generated by AI to undertake additional research ... 6. Code enhanced or checked for errors by AI assistance"
> **"While submissions will not be rejected solely because of the disclosed use of GenAI tools, if the editor becomes aware that GenAI was inappropriately used in the preparation of a submission without disclosure, the editor reserves the right to reject the submission at any time during the publishing process."**
> Inappropriate use includes "2. Generation of data or submission using a series of prompts", "4. Analysis of experiences and themes", "7. Fabricated references or falsified claims", "9. Use of GenAI to generate peer review reports, such as uploading or copy-pasting the manuscript or parts of it to a GenAI tool".
> "Peer reviewers may use generative AI (GenAI) to help write and format the peer review reports, but they remain responsible for the content of the reports."

**Answers**
1. **Writing help:** language, grammar and structure suggestions on your own text need no disclosure. Generated content
   needs disclosure. A submission generated "using a series of prompts" is prohibited, so `red_line`.
2. **Disclosure:** at submission, in Methods or Acknowledgements. No fields are specified.
3. **Prompts:** not mentioned.
4. **Screening:** none named on the AI page (journal pages link a plagiarism policy).
5. **Penalties:** rejection at any stage for undisclosed inappropriate use. Published articles get a joint Sage and editor
   investigation under COPE.
6. **Neutrality:** yes ("will not be rejected solely because of the disclosed use").
7. **Costs authors work:** cite original sources, not the AI tool. AI-written or AI-checked code must be disclosed.

### Mary Ann Liebert (now Sage): VERIFIED

- Migration hub: https://journals.sagepub.com/liebert-info: "The journals are now available on the Sage Journals platform
  (beginning 1 January 2026)" and "30th March 2026: dual access period ends and redirects initiated from the Mary Ann Liebert
  platform to Sage Journals". `curl` confirms that liebertpub.com/journal/{rej,cmb,omi} return 301 to journals.sagepub.com.
- **Policy now applied: Sage's.** Every Liebert journal page I read (Rejuvenation Research, J Comput Biol, OMICS) carries
  Sage's standard text and links the Sage AI policy:
  > "These resources describe ethical conduct and publication requirements for authors and editors to uphold accuracy, transparency, and disclosure – including authors' appropriate disclosure of AI use as well as a list of prohibited uses of AI."
  > "Please note that AI chatbots, for example ChatGPT, should not be listed as authors. For more information see the policy on Use of ChatGPT and generative AI tools."
- **Superseded Liebert policy** (Wayback 2025-07-09, J Comput Biol "For Authors"), quoted so a checker can recognise old
  author kits:
  > "Liebert Journals require authors to disclose any use of AI systems in their research and manuscript preparation."
  > "Authors are required to provide descriptions of an AI system's use in their Materials and Methods section. Include the name and version of the software, the date of the original use, and all relevant prompts, queries or cues that initiated the AI's response."
  > Reviewers: "processing any portion of the submission text using an external Generative AI is considered a compromise to the confidentiality of the review process"

**Answers:** as Sage. The old prompt requirement no longer appears on any live Liebert page I found.

### Karger: VERIFIED (via WebFetch, and Wayback 2026-10-01 for verbatim text)

- https://karger.com/pages/publication-ethics, section "Generative Artificial Intelligence (GenAI)". No page date.
- https://karger.com/pages/karger-ai-principles (WebFetch). Its only date is the EU AI Act's entry into force.
- Ownership: OUP completed its acquisition of Karger on 4 Dec 2025 (Karger and OUP press releases, seen in search results
  only, so SECONDARY). Gerontology's guidelines now live on Oxford Academic (see below).

Verbatim (Wayback 2026-10-01; WebFetch of the live page returned the same fragments):
> "If a Large Language Model (LLM), or other generative AI-based tool (e.g. chatbots or image creators), has been used as part of a study or manuscript, the use must be clearly declared in the manuscript Methods, or Acknowledgements section, if the article type does not include a Methods section."
> "Any software used must be cited in the References, in line with our software citation policy."
> "The manuscript must include detail on how the accuracy of any generative AI-based output was verified. Authors are encouraged to include the original input prompts and outputs from the tools used as supplementary material. Failure to comply with the above will be considered a violation of our Editorial Policies and may result in the rejection of a manuscript or post-publication notice."
> Reviewers and editors: "It is not appropriate to input any of the contents of a submission under review to a Large Language Model (LLM) or any machine learning algorithm as this would be a violation of the privacy of peer review."
> AI principles (WebFetch): "Karger uses and tests AI powered tools and technologies in the screening of submissions for completeness"
> Plagiarism: "Karger uses Crossref Similarity Check, powered by iThenticate to identify potentially inappropriate text overlap." Images "may be subjected to investigation using image integrity software."

**Answers**
1. **Writing help:** allowed, but **any** LLM use "as part of a study or manuscript" must be declared, with no
   language-editing exemption (`disclose_all`).
2. **Disclosure:** in Methods (or Acknowledgements), the tool cited in References, and how each output's accuracy was
   checked.
3. **Prompts:** encouraged as supplementary material, with the outputs.
4. **Screening:** AI-assisted completeness and integrity checks, Crossref Similarity Check and image software. No AI-text
   detector named.
5. **Penalties:** a violation of Editorial Policies, leading to rejection or a post-publication notice.
6. **Neutrality:** silent.
7. **Costs authors work:** a reference entry for the AI tool, a verification description, and prompts and outputs
   (encouraged).

---

## Journals

### Aging Cell (Wiley / Anatomical Society): VERIFIED

- https://onlinelibrary.wiley.com/page/journal/14749726/homepage/forauthors.html; metrics:
  https://onlinelibrary.wiley.com/journal/14749726/journal-metrics ("2025 Journal Impact Factor (Clarivate): 7.7"). Chrome.
- **No AI section.** The page only links Wiley:
  > "Aging Cell is a member of the Committee on Publication Ethics (COPE). Read Wiley's Top 10 Publishing Ethics Tips for Authors here. Please see Wiley's Publication Ethics Guidelines here."
  > "Plagiarism checking - To verify originality, articles will be checked by iThenticate's CrossCheck software"; "Image checking - All figures will undergo an integrity check."
- OA: "Aging Cell is a Gold Open Access journal." Research articles: 7,500 words, abstract 250 words, 45 references max.
- **Answers:** the Wiley default applies in full. No journal-specific AI rule. Every figure gets an integrity check.

### Human Mutation (Wiley, Hindawi-model OA): VERIFIED

- https://onlinelibrary.wiley.com/page/journal/humu/homepage/author-guidelines; JIF "2025 Journal Impact Factor
  (Clarivate): 1.8". Chrome.
- **No AI section.** "This journal uses iThenticate's CrossCheck software ... Read Wiley's Top 10 Publishing Ethics Tips for
  Authors and Wiley's Publication Ethics Guidelines."
- "The journal is open access." Abstract "should not exceed 300 words". "authors will be limited to having three
  manuscripts under review at any point in time." Article types: Research, Review, Research Letter, Letter to the Editor
  (case reports only as letters). No software type.
- **Answers:** the Wiley default applies. No journal AI rule.

### Clinical Genetics (Wiley): VERIFIED

- https://onlinelibrary.wiley.com/page/journal/13990004/homepage/forauthors.html; JIF "2025 Journal Impact Factor
  (Clarivate): 2.1". Chrome.
- **No AI section.** "Note this journal uses iThenticate's CrossCheck software ... Read Wiley's Top 10 Publishing Ethics
  Tips for Authors and Wiley's Publication Ethics Guidelines."
- Hybrid ("If you choose to publish open access you will be charged a fee"). Original Article 6,000 words *including*
  cover page, abstract, references and legends; abstract 200 words.
- **Answers:** the Wiley default applies. No journal AI rule.

### Genetic Epidemiology (Wiley / IGES): VERIFIED

- https://onlinelibrary.wiley.com/page/journal/10982272/homepage/forauthors.html; JIF "2025 ... 3.4". Chrome.
- **No AI section.** "This journal is a member of the Committee on Publication Ethics (COPE). Read Wiley's Top 10 Publishing
  Ethics Tips for Authors here. Wiley's Publication Ethics Guidelines can be found here."
- Hybrid (open access optional). Abstract 200 words. Types: Research Articles ("innovative statistical, computational, or
  genomic methodologies"), Reviews, Letters, Brief Report, Perspectives. No software type.
- **Answers:** the Wiley default applies. No journal AI rule.

### Molecular Ecology Resources (Wiley): VERIFIED

- https://onlinelibrary.wiley.com/page/journal/17550998/homepage/forauthors.html; JIF "2025 ... 5.9". Chrome.
- **No AI section.** "Note this journal uses iThenticate's CrossCheck software ... Wiley's Publication Ethics Guidelines can
  be found at authorservices.wiley.com/ethics-guidelines/index.html."
- "Molecular Ecology Resources joined Wiley's Open Access portfolio as of January 1, 2026."
- Software: a "Computer Programs" resource category ("new computer software or substantial updates of existing programs").
  "Upon submission, the journal requires authors to provide all data, metadata and code for review by editors and referees."
  "at least a snapshot of these resources must be posted on Dryad, CRAN, Zenodo or similar". Resource articles: 8,000
  words, abstract 250 words.
- Fit: "Molecular Ecology Resources does not publish empirical research." The scope is ecology, evolution and conservation.
- **Answers:** the Wiley default applies. No journal AI rule. Code and data must reach reviewers at submission.

### CPT: Pharmacometrics & Systems Pharmacology (Wiley / ASCPT): VERIFIED, journal-specific rule

- https://ascpt.onlinelibrary.wiley.com/page/journal/21638306/guidetoauthors; JIF "2025 ... 2.8". Chrome (third try).
- Verbatim, "Use of Artificial Intelligence (AI)":
  > "AI tools cannot be listed as authors, as they cannot be accountable for the work. AI tools may be used in drafting assistance or to help in developing figures and tables. **These tools should only be used to improve readability and language. All AI use must be credited, either in the acknowledgements or methods section.** Authors remain responsible for all work submitted under their name."
- "All articles selected for acceptance in PSP will be published open access." Types include "Databases" (4,000 words) and
  Tutorial. Article: 4,000 words, abstract 250 words.
- **Answers**
  1. **Writing help:** only to improve readability and language (stricter than Wiley). The same paragraph also allows
     "drafting assistance", so the text contradicts itself; I classed it `banned_drafting`, and authors should ask the editor
     before relying on more than language help.
  2. **Disclosure:** every AI use, language editing included, in the Acknowledgements or Methods.
  3. **Prompts, screening, penalties:** none beyond Wiley's.

### Clinical Pharmacology & Therapeutics (Wiley / ASCPT): VERIFIED, journal-specific rule

- https://ascpt.onlinelibrary.wiley.com/page/journal/15326535/guidetoauthors; JIF "2025 ... 4.9". Chrome.
- The same "Use of Artificial Intelligence (AI)" paragraph as CPT:PSP, word for word, plus "An artificial intelligence may
  not be listed as an author."
- Hybrid ("Open Access is available to authors who wish..."). Article: 4,000 words. "*If the word count exceeds the posted
  limit, please provide overage justification upon submission." Abstract 250 words. Tutorials, White Papers, Letters.
- **Answers:** as CPT:PSP (AI for readability and language only; all use credited).

### Advanced Science (Wiley): VERIFIED, journal paragraph

- Author guidelines: https://onlinelibrary.wiley.com/page/journal/21983844/homepage/author-guidelines. Editorial policies:
  https://advanced.onlinelibrary.wiley.com/hub/editorial-policies. Reviewer guidelines:
  https://advanced.onlinelibrary.wiley.com/hub/reviewer-guidelines. JIF "2025 ... 14.1". Chrome.
- Verbatim (identical on the author guidelines and the editorial policies):
  > "If an author has used a GenAI tool to develop any portion of a manuscript, its use must be described, transparently and in detail, in the Methods section (or via a disclosure or within the Acknowledgements section, as applicable)."
  > "Generative AI tools should not be used to create cover images."
  > Reviewers: "Reviewers may not share or upload any part of a submitted manuscript with any generative artificial intelligence (AI) tool. Reviewers may only use AI tools as a companion to the reviewing process, such as for polishing the language of your report."
- "Advanced Science ... is an open access interdisciplinary journal" (homepage). Research Article abstract 200 words;
  articles "can be any length".
- **Answers:** the Wiley default, with Methods as the preferred place and "in detail". No AI cover art. No AI rule beyond that.

### Quantitative Biology (Wiley / Higher Education Press): VERIFIED

- https://onlinelibrary.wiley.com/page/journal/20954697/homepage/author-guidelines; JIF "2025 ... 2.2". Chrome.
- Publisher check: the journal is now on Wiley Online Library, and the guidelines footer names Higher Education Press.
  Editorial office qb@pub.hep.cn. The old HEP page (journal.hep.com.cn/qb/EN/guidelines) rendered empty.
- **No AI section.** "This journal follows the core practices of the Committee on Publication Ethics (COPE)"; "This journal
  uses iThenticate's CrossCheck software ... Read Wiley's Top 10 Publishing Ethics Tips for Authors and Wiley's Publication
  Ethics Guidelines."
- "This journal is a Gold Open Access title." "Technical Note" includes "additions to established tools ... description of
  a database ... new algorithm or computational method ... new implementation of an existing algorithm". The page also
  lists a Data Article type.
- **Answers:** the Wiley default applies. No journal AI rule.

### Proteomics (Wiley): VERIFIED

- https://analyticalsciencejournals.onlinelibrary.wiley.com/hub/journal/16159861/homepage/2120_authorguidelines.html;
  JIF "2025 ... 4.1". Chrome. The /page/journal/16159861/homepage/forauthors.html URL returns 404.
- **No AI section.** "all manuscripts prior to acceptance will be subject to testing using the CrossCheck software."
- Hybrid (OnlineOpen). Technical Briefs: "new software or other technical advancements used in (prote)omics analysis".
  Research Articles 8,000 words; abstract 200 words. "Deposition of supporting proteomics data in a public and global open
  access database is mandatory". The page reads as years old (2013-era funder text).
- **Answers:** the Wiley default applies (the page does not even link it). No journal AI rule.

### Rejuvenation Research (Mary Ann Liebert / Sage): VERIFIED

- https://journals.sagepub.com/author-instructions/REJ. Header "Impact Factor: 1.8 / 5-Year Impact Factor: 2.1"; metadata
  source "Journal Citation Reports from Clarivate, 2026". Chrome.
- AI: only the two Sage sentences quoted under Liebert (link to the Sage AI policy; no chatbot authors).
- "Access: Subscription", with Sage Choice open access → hybrid. Mandatory page charges: "$90/page". Original Articles: 4,000
  words, abstract 250 words.
- **Answers:** the Sage policy (see above). The journal page only links it.

### Journal of Computational Biology (Mary Ann Liebert / Sage, RECOMB): VERIFIED

- https://journals.sagepub.com/author-instructions/CPB. Sage uses code **CPB**; /CMB returns "Journal not found". JIF 1.3
  (source "JCR from Clarivate, 2026"). Chrome.
- AI: only the Sage link sentences.
- Hybrid; "$90/page". "Research and software articles should report unique findings not previously published." Research
  Articles: "3,000-word limit ... Longer articles may also be submitted." Software Articles "approximately 2-4 pages",
  accompanied by "a cover letter that concisely states the novel implementation and algorithmic challenges the software
  tackles". Abstract 250 words.
- **Answers:** the Sage policy. The page only links it.

### OMICS: A Journal of Integrative Biology (Mary Ann Liebert / Sage): VERIFIED

- https://journals.sagepub.com/author-instructions/OMI. JIF 2.0 (JCR 2026 label). Chrome.
- AI: only the Sage link sentences. "Access: Subscription"; "There are no fees payable to submit or publish". Original
  Articles: 4,000 words, abstract 200 words. Protocol articles must "compare the new process to existing processes".
- **Answers:** the Sage policy. The page only links it.

### Bioinformatics and Biology Insights (Sage): VERIFIED

- https://journals.sagepub.com/author-instructions/BBI. JIF 2.0 (JCR 2026 label). Chrome.
- AI: only the Sage link sentences.
- "Bioinformatics and Biology Insights is an open access, peer-reviewed journal." APC $3,200. Data Article: "Discussing
  software, code, or a database ... reviewers must be able to use the example anonymously." Abstract 150 to 200 words.
- **Answers:** the Sage policy. The page only links it.

### Evolutionary Bioinformatics (Sage; page shows the Mary Ann Liebert imprint): VERIFIED

- https://journals.sagepub.com/author-instructions/EVB. JIF 1.6 (JCR 2026 label). Chrome.
- AI: only the Sage link sentences.
- "Effective September 1, 2025, Evolutionary Bioinformatics will transition to a hybrid publication model." No fees unless
  open access. Research Articles: 4,000 to 6,000 words; structured abstract up to 300 words. Software appears only as
  "Software or database review – review should discussing software, code, or a database" under Review.
- **Answers:** the Sage policy. The page only links it.

### Gerontology (Karger / OUP, on Oxford Academic): VERIFIED (via WebFetch only)

- karger.com/ger/pages/guidelines → **301 to https://academic.oup.com/ger/pages/author-guidelines**. The Oxford Academic
  page lists "Karger Publications" and "Copyright © 2026 Karger".
- JIF: "3.1" labelled "2025 Impact Factor" on https://academic.oup.com/ger (karger.com/ger shows 3.1 with no year).
- Verbatim fragments (WebFetch, at most 125 characters each):
  > "Natural language processing tools driven by artificial intelligence (AI) do not qualify as authors," / "and the Journal will screen for them in author lists."
  > "The use of AI (for example, to help generate content or images, write code, process data, or for translation)" / "should be disclosed both in cover letters to editors and in the Methods or Acknowledgements section of manuscripts."
  > "Manuscripts submitted to the Journal may be screened with plagiarism-detection software."
- The page links Karger's Publication Ethics and Editorial Policies page (https://karger.com/pages/publication-ethics) and
  OUP's ethics page. It does **not** link OUP's 13 July 2026 "Policy on AI Use & Disclosure", so whether that policy also
  binds Gerontology is unstated.
- From WebFetch's summary, not verbatim: hybrid (standard licence free, or CC BY / CC BY-NC for a fee); Research Articles
  about 5,000 words; pages beyond five cost $500 each unless open access; no abstract limit given beyond a 250-word lay summary.
- **Answers:** the Karger rule (Methods, tool cited in References, verification described, prompts encouraged) **plus a
  cover-letter disclosure** from the OUP clause. Doing both satisfies both.

### Pharmacogenomics (Taylor & Francis, Expert Medicine): VERIFIED

- Instructions: https://www.tandfonline.com/action/authorSubmission?show=instructions&journalCode=ipgs20. JIF: "1.6 (2025)
  Impact Factor" (https://www.tandfonline.com/journals/ipgs20/about-this-journal). Chrome.
- Expert Medicine Author Guidelines PDF (https://files.taylorandfrancis.com/expert-medicine-author-guidelines.pdf),
  "Version: September 2026". Read with curl + pdftotext.
- Verbatim (instructions):
  > "7. Declaration of generative AI use. Please include a statement disclosing whether and how generative AI has been used in the research and manuscript preparation process. If generative AI was not used, please state this (suggested wording: The authors report generative AI was not used in their research or preparation of this manuscript). Please read our guidance on using AI tools in your research and manuscript preparation"
  > (The guidance link is the T&F author-services page with the drafting ban.)
  > "Please note that Pharmacogenomics uses Crossref™ to screen papers for unoriginal material."
- Verbatim (PDF): "All use of Artificial Intelligence (AI) needs to be declared in the Acknowledgments section."
- Hybrid ("Open Select"). Research Article 5,000 to 8,000 words, abstract 200 words. The PDF's article-type grid offers
  Software Tool only in Bioanalysis and Epigenomics, **not Pharmacogenomics**.
- **Answers:** the T&F default (no AI first drafts; a declaration in every paper, including "not used"). The Expert
  Medicine kit adds the Acknowledgments as the place for **all** AI use.

---

## Re-check of the existing `peerj` entry (https://peerj.com/about/policies-and-procedures/, Chrome)

The live page still matches the entry's core: a statement in Methods or Acknowledgments (tool and version, how, why). It
still permits copyediting with a declaration and with the original and revised versions kept. It still lists "undisclosed
use of generative AI" as misconduct. Differences and additions:

1. **JIF:** PeerJ's own pages show **2.9 (2025)** for both PeerJ (Life & Environment) and PeerJ Computer Science
   (https://peerj.com/life-environment/, https://peerj.com/computer-science/). venues.yaml has 3.8.
2. **Decline wording is wider than quoted.** The full text reads: "PeerJ maintains editorial discretion to decline manuscripts if AI is used inappropriately. This includes cases where AI use compromises the integrity of the research, **or where the extent of AI contribution raises concerns about the authors' contribution.**" So `disclosure_neutral: false`: the declared extent of AI use can count.
3. **Data visualisations:** "Use of AI tools to assist research data visualisations is permitted. Authors must retain all versions of the images and records of the prompts used, which must be shared upon request." The figure legend must name the tool and version. This is not in the entry's `extra_burden`.
4. **Research-method use:** "Authors must retain full records of the methods undertaken, including full descriptions and records of the prompts used" (target-journals.md quotes this; venues.yaml has `prompts: on_request`, which is consistent).
5. **Drafting ban not repeated.** PeerJ's page does not carry the T&F author-services rule ("does not allow generative AI to create a first draft of a manuscript or sections"). It does say "Please bookmark the Taylor & Francis AI policy to keep up to date with the latest guidance." A cautious checker should warn PeerJ authors that the parent publisher's newest page bans AI first drafts.
6. `reviewer_ai` is not on the PeerJ page. The T&F corporate rule (`banned`) presumably applies.

---

## Cross-cluster notes

- **Strictest on drafting:** the T&F author-services page (no AI first draft of a manuscript or any section) and the ASCPT
  journals (AI "only ... to improve readability and language"). Both sit beside ISCB's ban.
- **Disclosure even when none was used:** T&F (and so Pharmacogenomics) requires a Declaration of generative AI use that
  says "not used".
- **No language-polish exemption:** Karger (any LLM use), ASCPT (all AI use credited), and T&F (copyediting declared, versions kept).
- **Explicitly neutral about disclosed use:** Wiley ("not grounds for rejection") and Sage ("will not be rejected solely
  because of the disclosed use").
- **AI tool cited in References:** Karger (software citation policy). Sage says the opposite ("cite original sources,
  rather than GenAI tools as primary sources").
- **Named detectors:** none for AI text in this cluster. Wiley: AI integrity screening plus Imagetwin (detects AI-generated
  image content). Karger: AI completeness and integrity checks. Everyone else names plagiarism tools (iThenticate,
  CrossCheck, Crossref).
- **Platform moves in 2026:** the Liebert journals moved to Sage Journals (1 Jan 2026, redirects from 30 Mar 2026), Gerontology
  moved to Oxford Academic, and Molecular Ecology Resources went fully open access (1 Jan 2026).

## Not found or not fully read

- academic.oup.com/ger read only through WebFetch fragments (Cloudflare; no Wayback snapshot).
- karger.com read through WebFetch plus the Wayback snapshot of 2026-10-01 (live page blocked to curl and Chrome).
- Sage's reviewer FAQ (journalssolutions.sagepub.com, article 7000090480) returned only "Self Service Portal": NOT FOUND.
- The HEP-hosted Quantitative Biology guidelines (journal.hep.com.cn/qb/EN/guidelines) rendered empty; the Wiley-hosted
  page was used instead.
- No dates shown on the Sage, Karger or Wiley AI-guidelines pages, nor on any journal page except the Expert Medicine PDF
  ("Version: September 2026").
- No 2026 news found of AI-text detectors or desk-rejection drives at Wiley, T&F, Sage or Karger. Wiley's 2024 papermill
  pilot with a gen-AI content check was seen only in search snippets (SECONDARY, not followed).
- aging-mental-health: skipped as instructed.
