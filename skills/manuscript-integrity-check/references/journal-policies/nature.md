# Nature Portfolio, EJHG and EMBO Press: generative-AI policies (checked 2026-10-15)

> Cluster "nature" for the manuscript-skills venue database. Entries: `../venues.yaml`.
> Researched 2026-10-15. Re-fetch a venue's page before relying on it.

## How this was read

- **Route.** Every page was rendered with headless Chrome (`--headless=new --dump-dom --virtual-time-budget=15000`) and converted with `w3m -dump`. nature.com, springernature.com and link.springer.com all rendered. No WebFetch, no Wayback. The two PDFs (Reporting Summary, code-submission guidelines) were downloaded with curl and read with `pdftotext`.
- **Diffing.** Each journal's AI page was cut from its heading to "Governance and review" and diffed line by line against the Nature Portfolio page.
  - All 15 Nature Portfolio journal pages in this cluster are identical to the portfolio page, Scientific Data included.
  - The only difference is the npj heading "Artificial Intelligence" where the others have "Artificial Intelligence (AI)".
  - The "Editorial use" paragraph is identical too.
- **Dates.** No Nature Portfolio or Springer Nature AI page shows a date; the footers say "© 2026 Springer Nature Limited". The framework launch date (10 Sept 2026) comes from publisher-policies.md §3.1.
- **JIF.** Taken from the "Citation Impact" block of each journal's own metrics page (`/<journal>/journal-impact`, `/ejhg/journal-information`, or the Springer Nature Link home page for EMBO Press). Every Nature-hosted page states "(2025)".
- **Status marks.** As in target-journals.md: VERIFIED, PARTIAL, SECONDARY, NOT FOUND.

---

## 0. `springer-nature` publisher default (Green/Amber/Red framework): VERIFIED

**URLs**
- https://www.nature.com/nature-portfolio/editorial-policies/ai (Nature Portfolio framework page)
- https://www.springernature.com/gp/policies/editorial-policies/ai-manuscript-preparation (author page)
- https://www.springernature.com/gp/policies/editorial-policies/using-ai-in-research
- https://www.springernature.com/gp/policies/editorial-policies/using-ai-in-peer-review
- https://www.springernature.com/gp/policies/editorial-policies/ai-editor-guidance
- https://www.springernature.com/gp/policies/editorial-policies (index: "Specific guidance is available for AI use in manuscript preparation, AI use in research practice, AI use in peer review, and editor AI use and assessment guidance.")

**Page date:** none shown.

**Verbatim, nature.com framework page.**

Core expectations:
> "Human accountability is non‑transferable"; "AI may support, but must not replace, scholarly judgement"; "Transparent declaration of AI builds trust and confidence, and removes ambiguity about how AI might have been used."; "Manuscripts, peer review reports, and sensitive data must not be shared with unsecured or public AI systems."

Green tier:
> "Using an LLM to polish or refine the language"; "Suggesting structure or formatting of manuscript sections"; "Translation, structuring or clarifying reviewer comments"; "Comparing methodological options"; "Stress-testing research questions"; "Data cleaning and deduplication" → "Permitted. Disclosure enhances trust and transparency and clearly demonstrates human accountability."

Amber tier:
> "Suggesting analytical, experimental or methodological approaches"; "Drafting explanatory summaries"; "Comparing results to existing literature"; "Extensive copy editing or writing support"; ... → "Permitted with human oversight, verification, and transparency through disclosure."

Red tier:
> "Generating hypotheses, analyses or conclusions and presenting them as human-derived"; "Fabricating data, citations or results"; "Using an LLM to generate core research reasoning without disclosure"; "Assigning authorship or accountability to AI systems or tools"; "Delegating peer review to an LLM"; "Creating photorealistic images (deepfakes)" → "Not permitted."

Role-specific responsibilities:
> Authors: "Remain fully accountable for originality, accuracy, and integrity"; "Disclose AI use for trust and transparency".
> Reviewers: "May use AI to support peer review but must not upload manuscript content to unsecured or public AI tools".

Editorial use:
> "Nature Portfolio journals occasionally use artificial intelligence tools developed or approved by Springer Nature to support different tasks in the generation of accessory content or to support the editorial process."

Governance:
> "Existing research integrity, ethics, and editorial governance processes apply to all AI‑related concerns."

**Compared with publisher-policies.md §3.1.** The live page also lists:
- Green: "Comparing methodological options", "Stress-testing research questions" and "Data cleaning and deduplication";
- Amber: "Drafting explanatory summaries";
- Red: "Fabricating data, citations or results" and "Delegating peer review to an LLM".

§3.1 said the BMC copy alone adds "Delegating peer review to an LLM". The nature.com page now carries it too.

**Verbatim, SN author page (manuscript preparation).**

Risk table:
> Green: "Grammar and language editing; improving readability and flow; formatting; translation; summarising author-written text" → "Clearly describe use and confirm author accountability".
> Amber: "Generating outlines; drafting sections based on author input; suggesting alternative phrasing or framing; reference management support; creating visual content with verifiable source data or material" → same declaration; "all AI generated or assisted content must be clearly labelled".
> Red (not permitted): "Writing results or discussion independently; generating scientific claims or interpretations; producing data or figures as if empirical; listing AI as an author; creating content from text prompts or without verifiable source data or material".

Drafting and visuals:
> "AI can assist with expression, but the argument, interpretation, and conclusions must be author-led."
> "AI generated visual content that is not derived from independently verifiable data, source material, methods, computational outputs or author-developed content is considered opaque and is not permitted by Springer Nature policy."
> "Where AI-generated or AI-assisted visual content is published, information about the AI system used, the purpose of its use, and the extent of its contribution should be provided in an AI Declaration in your manuscript. Specific disclosure should be provided within the caption or legend of the visual content."

Declaration:
> "Declaration does not negatively influence editorial decisions"; "Where AI use is not declared, editors may need to investigate or request clarification, which can delay the review process".

**Verbatim, SN research-practice page.**
> Green: "code scaffolding" ("Describe tool and purpose and take accountability").
> Amber: "Identifying patterns in datasets; supporting statistical modelling; qualitative coding; generating explanatory summaries or comparisons" → "Provide clear methodological description and validation steps and take accountability".
> Red: "Generating hypotheses, analyses, or conclusions without human oversight; fabricating data or references; using sensitive or restricted data in public tools" → "Not permitted".
> "Authors should be able to clearly describe how AI was used, what inputs and outputs were involved and how results were validated."
> "Declaration does not disadvantage your manuscript".

**Verbatim, SN peer-review page.**
> Red: "Uploading manuscripts to public/unsecured tools; generating full review reports; producing accept/reject recommendations".
> "Manuscript text, figures, or identifiable content should not be uploaded into these types of tools." (public or open tools)
> "Dependent on the data and privacy policies and settings of these tools limited use of manuscript content may be acceptable." (secure or institutionally approved tools)

**Verbatim, SN editor guidance.**
> "The accuracy and usefulness of such tools is far from definitive, and no tool is able to confirm whether the AI use was safe and policy compliant."
> "In practice, Springer Nature does not expect editors to identify or investigate undisclosed or unsafe uses of AI."
> AI Declarations policy: "sets out the expectation for clear declaration of any AI use, including for research purposes, for writing/manuscript preparation and for peer review."
> "As we roll out this policy across our submission and peer review workflows authors and reviewers will also be asked to confirm that they have read and complied with the Springer Nature AI Editorial Policies when submitting a manuscript"
> "The presence of an AI Declaration, or the disclosure of AI use, should not in itself be considered a cause for concern."

**Conflicts still live on 2026-10-15** (re-checked):
- **Copy editing and disclosure location.** The group page (https://group.springernature.com/gp/group/ai/ai-guidance-for-our-researchers-and-communities) still says: "The use of generative AI tools should be declared in the Introduction or Acknowledgements of the manuscript. The use of an AI tool for 'AI assisted copy editing' purposes does not need to be declared." It also says: "Their use must be documented in the manuscript's Methods section (or equivalent)".
- **AI images.** The group page says "Are generative AI images allowed in publications? Generally no." It also carries the "AIGC" block asking for "tool versions, usage dates, prompts, and the extent of AI contribution".
- **Reviewers.** The Nature Portfolio peer-review page (https://www.nature.com/nature-portfolio/editorial-policies/peer-review, section "AI use by peer reviewers") still says: "we ask that, while Springer Nature explores providing our peer reviewers with access to safe AI tools, peer reviewers do not upload manuscripts into generative AI tools." That is stricter than the framework's "unsecured or public" wording.
- **Older guideline text.** Every Nature-branded journal's author guidelines still carry the pre-framework sentence: "Use of an LLM should be properly documented in the Methods section".

**Other Nature Portfolio pages (no AI rule).**
- The authorship and image-integrity pages have no AI text now. The old "generative AI images" text is gone from the image page.
- Neither the Reporting Summary PDF (nr-reporting-summary-flat.pdf) nor the code guidelines PDF (GuidelinesCodePublication.pdf) mentions AI or LLMs.
- No hallucinated-reference clause appears on any nature.com page read. The SN citation policy with that clause was verified on the BMC page (publisher-policies.md §3.2).

**Answers**
1. **Writing help:** `red_line`.
   - Allowed with declaration: polishing (Green), and outlines plus "drafting sections based on author input" (Amber).
   - Not permitted: "Writing results or discussion independently" and "creating content from text prompts" (Red).
2. **Disclosure:**
   - An "AI Declaration in your manuscript" (SN).
   - Methods, according to the journal author guidelines.
   - The caption or legend for AI visual content.
   - State how AI was used and confirm author accountability; label Amber content. For research use, give inputs, outputs and validation.
   - No exemption at the framework level: Green uses also "Clearly describe use". The group page and Communications Biology exempt copy editing (conflict).
3. **Prompts:** not required ("no"). Only the group page's AIGC block mentions prompts.
4. **Screening:**
   - Publisher-wide Geppetto and the irrelevant-reference checker (press releases, target-journals.md §8): `ai_detector_deployed`.
   - The editor guidance discounts detectors and says editors need not look for undisclosed AI use.
5. **Penalties:**
   - Red-tier uses are "Not permitted".
   - Withdrawal after a reference-checker flag.
   - Rejection or retraction for hallucinated references (SN citation policy).
   - Undeclared use can cause delay or investigation.
6. **disclosure_neutral:** true ("Declaration does not negatively influence editorial decisions"; "Declaration does not disadvantage your manuscript").
7. **reviewer_ai:** `restricted`. Secure or approved tools only, with limited use. The portfolio peer-review page is still a blanket no-upload.
8. **Extra burden:**
   - Label all AI-assisted content.
   - A submission-time confirmation of compliance (being rolled out).
   - AI visuals only from verifiable inputs, disclosed twice.

---

## Nature-branded journals: common pattern

Each of the 15 journal AI pages below is the framework verbatim (diffed; see "How this was read"). Each journal's own author pages add only the items listed in its section. Two passages recur and are quoted once here.

**(a) The older LLM sentence.** On every Nature research journal's "Preparing your material" page, Nature's "Initial submission" page, the npj submission guidelines, Scientific Reports, Nature Communications ("How to submit"), EJHG and Scientific Data:
> "Large Language Models (LLMs), such as ChatGPT, do not currently satisfy our authorship criteria. Notably an attribution of authorship carries with it accountability for the work, which cannot be effectively applied to LLMs. Use of an LLM should be properly documented in the Methods section (and if a Methods section is not available, in a suitable alternative part) of the manuscript."

Scientific Reports, Nature Communications, Scientific Data and the npj journals add:
> "In response to emerging information, advice, guidance and policy around artificial intelligence (AI), we have created a dedicated AI section in our Editorial Policy page. Please familiarize yourself with this content and comply with relevant policies."

**(b) Cover images.** On the "AIP and formatting" pages of Nature Aging, Nature Biotechnology, Nature Methods, Nature Genetics, Nature Medicine, Nature Machine Intelligence and Nature Computational Science:
> "Images created with Generative AI (such as from DALL-E, Stable Diffusion, and Midjourney) are not permitted."

The context is issue-cover submissions.

**Code (all Nature Portfolio journals)** (https://www.nature.com/nature-portfolio/editorial-policies/reporting-standards, re-read):
> "For all studies using custom code or mathematical algorithm that is deemed central to the conclusions, a statement must be included under the heading "Code availability" ... Code availability statements should be provided as a separate section after the data availability statement but before the references."
> "Code should be deposited in a DOI-minting repository such as Zenodo or Code Ocean and cited in the reference list"
> "For code/algorithm peer review, we require sharing of code/algorithm during the peer review process with editors and reviewers"

**Journal editorials on AI-written submissions:** NOT FOUND. Three web searches (2026 editorials in Nature, Nature Methods/Biotechnology/Genetics, Nature Machine Intelligence/Computational Science) returned only third-party summaries. None named a journal-level desk-rejection rule or AI questionnaire beyond the SN submission confirmation above.

---

## 1. Nature: VERIFIED

**URLs**
- AI policy: https://www.nature.com/nature/editorial-policies/ai (framework verbatim)
- Author guidance: https://www.nature.com/nature/for-authors/initial-submission (passage (a), after "Authors. Corresponding author(s) should be identified with an asterisk.")
- Formatting guide: https://www.nature.com/nature/for-authors/formatting-guide

**JIF:** "Journal Impact Factor: 56.1 (2025)" (https://www.nature.com/nature/journal-impact).

**OA model:** hybrid.
> "Authors submitting primary research articles to Nature have the option of publishing their research using either: 1 – Traditional subscription publishing model ... 2 – Gold Open Access"

**Limits:** guidance, not caps.
> "a fully referenced summary paragraph, ideally of no more than 200 words"
> "A typical 8-page Article contains about 4300 words of text"

**Answers:** as the publisher default. Disclosure in Methods (journal text) plus an AI Declaration (SN). No cover-image AI clause was found on Nature's own pages. No software article type.

## 2. Nature Aging: VERIFIED

**URLs**
- AI policy: https://www.nature.com/nataging/editorial-policies/ai (verbatim)
- Author pages: https://www.nature.com/nataging/submission-guidelines/preparing-your-submission (passage (a)) and /aip-and-formatting (passage (b))

**JIF:** "Journal Impact Factor: 25.0 (2025)".

**OA model:** hybrid ("Traditional subscription publishing model" or "Gold Open Access").

**Article (content types page):** "Main text – up to 4,500 words" and "Abstract – up to 150 words".

**Resource type:** "presents a large and newly-generated data set, a new data platform or library, or a collection of reagents or tools".

**Answers:** as the publisher default, plus no generative-AI cover images.

## 3. Nature Biotechnology: VERIFIED

**URLs**
- AI policy: https://www.nature.com/nbt/editorial-policies/ai (verbatim)
- Author pages: passages (a) and (b)

**JIF:** "Journal Impact Factor: 44.5 (2025)".

**OA model:** hybrid.

**Article:** "Main text – up to 3,000 words"; "Abstract – up to 150 words".

**Other types:** Brief Communication; Resource ("a large data set"). There is no dedicated software type.

**Answers:** as the publisher default, plus the cover-image clause.

## 4. Nature Methods: VERIFIED

**URLs**
- AI policy: https://www.nature.com/nmeth/editorial-policies/ai (verbatim)
- Author pages: passages (a) and (b)

**JIF:** "Journal Impact Factor: 28.3 (2025)".

**OA model:** hybrid.

**Article:** "An Article is a report describing a novel method or tool." "Main text – 3,000 words (up to 5,000 words with editorial discretion)"; "Abstract – up to 150 words".

**Brief Communication:** covers "software platforms". "Main text – 1,200 words"; "Abstract – up to 70 words".

**Other types:** Analysis (method comparisons); Resource ("a collection of tools or a large dataset"); Registered Report.

**Answers:** as the publisher default, plus the cover-image clause. This is the cluster's only software-friendly article type (`software_article: true`).

## 5. Nature Genetics: VERIFIED

**URLs**
- AI policy: https://www.nature.com/ng/editorial-policies/ai (verbatim)
- Author pages: passages (a) and (b)

**JIF:** "Journal Impact Factor: 25.5 (2025)".

**OA model:** hybrid.

**Article:** "Main text – up to 4,000 words"; "Abstract – up to 150 words".

**Other types:** Analysis; Letter; Brief Communication; Technical Report ("a new technique").

**Answers:** as the publisher default, plus the cover-image clause.

## 6. Nature Medicine: VERIFIED

**URLs**
- AI policy: https://www.nature.com/nm/editorial-policies/ai (verbatim)
- Author pages: passages (a) and (b)

**JIF:** "Journal Impact Factor: 52.5 (2025)".

**OA model:** hybrid.

**Article:** "Main text – up to 4,000 words"; "Abstract – up to 150 words".

**Other types:** Resource; Analysis.

**Reporting guidelines:** no AI-specific requirement was found on the pages read. TRIPOD-LLM was published in Nature Medicine, but no page read makes it mandatory.

**Answers:** as the publisher default, plus the cover-image clause.

## 7. Nature Machine Intelligence: VERIFIED

**URLs**
- AI policy: https://www.nature.com/natmachintell/editorial-policies/ai (verbatim)
- Author pages: passages (a) and (b)

**JIF:** "Journal Impact Factor: 29.8 (2025)".

**OA model:** hybrid.

**Article:** "Main text – up to 3,500 words"; "Abstract – up to 150 words".

**Other types:** Analysis; Reusability Report.

**Answers:** as the publisher default, plus the cover-image clause. Nothing extra for an AI-focused journal.

## 8. Nature Computational Science: VERIFIED

**URLs**
- AI policy: https://www.nature.com/natcomputsci/editorial-policies/ai (verbatim)
- Author pages: passages (a) and (b)

**JIF:** "Journal Impact Factor: 20.3 (2025)".

**OA model:** hybrid.

**Article:** "Main text – up to 3,500 words"; "Abstract – up to 150 words".

**Other types:** Brief Communication; Resource ("a large data set"); Analysis.

**Answers:** as the publisher default, plus the cover-image clause.

## 9. Nature Communications: VERIFIED

**URLs**
- AI policy: https://www.nature.com/ncomms/editorial-policies/ai (verbatim)
- How to submit: https://www.nature.com/ncomms/submit/how-to-submit (passage (a) plus the "dedicated AI section" sentence)
- Policy Guide: https://www.nature.com/ncomms/submit/policy

**Policy Guide, "11. AI Authorship and Generative AI images":**
> "Artificial Intelligence (AI) is an area of on-going rapid development for which related polices are closely monitored and reviewed. For more information, please refer to the Nature Portfolio Artificial Intelligence page."

**JIF:** "Journal Impact Factor: 18.1 (2025)".

**OA model:** full.
> "All articles published in Nature Communications are made freely and permanently available online immediately upon publication"

**Article:**
> "Ideally, the main text ... should be limited to 5,000 words"
> "abstract — which should be no more than 200 words"

**Other types:** Registered Report; Reviews, Perspectives and Comments are commissioned.

**Answers:** as the publisher default. The journal page only links to the portfolio policy.

## 10. Communications Biology: VERIFIED (journal text conflicts with SN)

**URLs**
- AI policy: https://www.nature.com/commsbio/editorial-policies/ai (verbatim)
- Policy Guide: https://www.nature.com/commsbio/submit/policy, section "AI authorship and Generative AI images"

**Verbatim, Policy Guide:**
> "Large Language Models (LLMs), such as ChatGPT, do not currently satisfy our Authorship Criteria and cannot be listed as authors."
> "Use of an LLM should be properly documented in the Methods section, though use of an LLM or other AI-tool for "AI assisted copy editing" purposes does not need to be declared."
> "While legal issues relating to AI-generated images and videos remain broadly unresolved, Springer Nature journals are unable to permit its use for publication."

The "Generative AI Images" link points to `https://www.nature.com/commsbio/editorial-policies/ai#generative-ai-images`. That anchor no longer exists on the rewritten page.

**JIF:** "Journal Impact Factor: 5.8 (2025)".

**OA model:** full ("All articles published in Communications Biology are made freely and permanently available online").

**Article:** Formatting Guidelines table: abstract "150 - 250", "5000 words (not incl. Methods)".

**Answers**
1. **Writing help:** `red_line` (inherited). The journal exempts "AI assisted copy editing" from declaration; the SN author page does not.
2. **Disclosure:** Methods.
3. **Images:** the journal text bans AI images outright. The SN author page allows visuals derived from verifiable inputs. Follow the stricter journal page, or ask the editor.

## 11. Scientific Reports: VERIFIED

**URLs**
- AI policy: https://www.nature.com/srep/journal-policies/ai (verbatim; linked as "Artificial Intelligence (AI)" from https://www.nature.com/srep/journal-policies/editorial-policies)
- Submission guidelines: https://www.nature.com/srep/author-instructions/submission-guidelines (passage (a) plus the "dedicated AI section" sentence)

**JIF:** "Journal Impact Factor: 4.9 (2025)".

**OA model:** full.

**Formats:**
> "Scientific Reports publishes original research in two formats: Article and Registered Report."
> "The main text should be no more than 4,500 words"; "The abstract should be no more than 200 words" (stated as strong recommendations).

**Enforcement news:** searched for 2026 Scientific Reports retractions over AI text or hallucinated references; none was found (NOT FOUND).

**Answers:** as the publisher default.

## 12. npj Aging: VERIFIED

**URLs**
- AI policy: https://www.nature.com/npjamd/editorial-policies/artificial-intelligence (verbatim)
- Submission guidelines: https://www.nature.com/npjamd/for-authors-and-referees/submission-guidelines (passage (a) plus the "dedicated AI section" sentence)

**JIF:** "Journal Impact Factor: 13.0 (2025)".

**OA model:** full.
> "npj Aging is an open access journal: authors pay an article processing charge (APC)"

**Article:** "Abstract: No subheadings permitted and up to 150 words in length". No main-text cap is stated for Articles.

**Code:**
> "Any previously unreported custom computer code or scripts used to generate results reported in the manuscript that are central to the main claims must be made available to Editors and referees upon request."

**Answers:** as the publisher default.

## 13. npj Digital Medicine: VERIFIED

**URLs**
- AI policy: https://www.nature.com/npjdigitalmed/editorial-policies/artificial-intelligence (verbatim)
- Submission guidelines: https://www.nature.com/npjdigitalmed/for-authors-and-referees/submission-guidelines (passage (a) plus the "dedicated AI section" sentence)

**JIF:** "Journal Impact Factor: 18.0 (2025)".

**OA model:** full ("All articles published in npj Digital Medicine are made freely and permanently available online immediately upon publication").

**Limits:** abstract 150 words; code rule as npj Aging.

**Reporting guidelines:** the guide to authors "strongly encourage[s]" EQUATOR checklists ("Diagnostic/prognostic studies (STARD and TRIPOD)"). No LLM-specific reporting rule was found (TRIPOD-LLM not required on the pages read).

**Answers:** as the publisher default.

## 14. npj Systems Biology and Applications: VERIFIED

**URLs**
- AI policy: https://www.nature.com/npjsba/editorial-policies/artificial-intelligence (verbatim)
- Submission guidelines: passage (a)

**JIF:** "Journal Impact Factor: 4.4 (2025)".

**OA model:** full.
> "npj Systems Biology and Applications is an open access journal: authors pay an article processing charge (APC)"

**Limits:** abstract 150 words.

**Fetch note:** the first render of `/npjsba/editorial-policies` came back empty; a second render worked.

**Answers:** as the publisher default.

## 15. npj Genomic Medicine: VERIFIED

**URLs**
- AI policy: https://www.nature.com/npjgenmed/editorial-policies/artificial-intelligence (verbatim)
- Submission guidelines: passage (a)

**JIF:** "Journal Impact Factor: 5.3 (2025)".

**OA model:** full ("npj Genomic Medicine is an open access journal").

**Content types:** Article (abstract up to 150 words), Case Report, Protocol, Review, Perspective, Comment, Matters Arising.

**Answers:** as the publisher default.

## 16. European Journal of Human Genetics (ESHG, published by Springer Nature): VERIFIED, framework not linked

**URLs**
- Guide to Authors: https://www.nature.com/ejhg/authors-and-referees/gta (passage (a), the only AI text)
- Editorial Policies: https://www.nature.com/ejhg/authors-and-referees/policies (no AI text)
- Referees page: no AI text

**Journal-specific text.** EJHG's menu has no AI-policy item, and none of its pages links to the Nature Portfolio or SN AI pages. Its only AI text is passage (a), which places the LLM note on the title-page instructions. The SN framework is publisher-wide, so it is recorded as inherited. That is an inference.

**Screening (policies page):**
> "Springer Nature is a member of Similarity Check (formerly CrossCheck)"

**JIF:** "Journal Impact Factor: 4.6 (2025)" (https://www.nature.com/ejhg/journal-information; `/ejhg/journal-impact` returns "Page not found").

**OA model:** hybrid.
> "Authors can also choose to publish under the traditional publishing model (no APC charges apply); both options will be offered after the paper has been accepted."

**Limits:**
> Article: "Unstructured abstract max. 250 words; Main body of text ... not to exceed 4,000 words"

**Answers:** disclosure in Methods (journal text). Everything else follows the SN default by inheritance; EJHG states nothing beyond the Methods sentence.

---

## 17. Molecular Systems Biology (EMBO Press): VERIFIED — EMBO Press's own policy, not the SN framework

**Which AI policy applies.**
- The old URL https://www.embopress.org/page/journal/17444292/authorguide now redirects to Springer Nature Link: "EMBO Press journals have moved to Springer Nature Link."
- The MSB submission guidelines (https://link.springer.com/journal/44320/submission-guidelines) link only the "EMBO Press editorial policies" (https://link.springer.com/partners/embo-press/editorial-policies).
- That page has its own "Artificial intelligence" section and does not link the SN framework.
- So EMBO Press's own policy governs. It is stricter on drafting.

**Page date:** none. The authorship section cites "the ICMJE authorship guidelines, accessed July 2025".

**Verbatim, EMBO Press editorial policies, "Artificial intelligence":**
> "1. An Artificial Intelligence (AI) or Large Language Model (LLM) program cannot be listed as an author of an article."
> "2. Use of AI programs should be primarily restricted to improve the style, accessibility or quality of human generated text and images, including schemata and data figures. Any part of an article assembled with the use of an AI based program must be thoroughly checked and verified by the authors, including deriving an understanding of the provenance of new information and ideas. ... Authors must disclose their use in the published article, including details on which parts of the article were assembled with the assistance of AI programs and details on the tools employed."
> "3. ... AI programs can be used in the collection and analysis of data if this is documented in the Methods section of the paper. If AI is used to generate synthetic data, this must be clearly labeled in the main text and figure, and it must also be documented in the Methods section. AI must not be used to synthesise or edit experimental data in a manner that misrepresents the findings. AI programs may be used to display data or for illustrative purposes, as long as that is declared and attribution is provided, where appropriate."

Authorship section:
> "Authorship implies adherence to the journal's AI tools policy."

Screening:
> "Journal staff undertake routine image analysis of data in manuscripts submitted for publication"
> "The journal uses CrossCheck to screen submitted content for plagiarism (including self-plagiarism) prior to publication."

**Reviewer guidelines** (https://link.springer.com/partners/embo-press/editorial-policies/reviewer-guidelines):
- Strict confidentiality: "Manuscripts should not be discussed with anyone not directly involved in the review process."
- Nothing on AI tools. A BioRender policy-checker summary says EMBO reviewers must not share manuscripts with AI systems; that is SECONDARY only.

**JIF** (journal home, https://link.springer.com/journal/44320):
> "Since the 2025 JIF was erroneous, we exceptionally report the official, corrected number here: 7.0"

**OA model:** "Publishing model: Open access".

**Article types:** Research Article, Report ("limited to 25,000 characters"), Method, Review, Perspective, Comment, Correspondence, Opinion, News & Views. Research Articles have "no strict format limitations".

**Scope:** includes "AI (Artificial Intelligence)" and "Computational biology and Modeling"; "Reports of new methods and resources are also considered".

**Answers**
1. **Writing help:** recorded as `banned_drafting`. Use "should be primarily restricted" to improving human-generated text and images. That is softer wording than ISCB's "not acceptable", but no drafting use is sanctioned.
2. **Disclosure:** all use, "in the published article" (section not named). Name which parts AI assembled and which tools. Methods for AI in data collection or analysis; labels in text and figure for synthetic data. No language-polish exemption.
3. **Prompts:** not mentioned.
4. **Screening:** CrossCheck plagiarism screening and routine image analysis. No AI detector named.
5. **Penalties:** none AI-specific; the general scientific-integrity investigations apply.
6. **disclosure_neutral:** null (silent).
7. **reviewer_ai:** null (not found on EMBO pages).

## 18. EMBO Reports (EMBO Press): VERIFIED

**URLs**
- https://link.springer.com/journal/44319/submission-guidelines (the embopress.org author guide redirects here)
- Same EMBO Press editorial-policies page as MSB; no journal-specific AI text.

**JIF:** not shown on the journal home page (null). The home page shows only "Submission to first decision (median) 5 days" and downloads.

**OA model:** "Publishing model: Open access".

**Article types:** Research Article, Report, Exploratory Report ("up to 3,000 words"), Method, Resource ("broadly relevant datasets (for example, screens, omics data, computational modelling)"), Review, Perspective, Comment, Correspondence, Opinion.

**Answers:** as Molecular Systems Biology.

---

## Re-check of the existing `scientific-data` entry

- https://www.nature.com/sdata/policies/ai, rendered 2026-10-15.
- **AI page:** the body is identical to the Nature Portfolio page (diffed, 84 lines, 0 differences), "Editorial use" included. It is the same text that target-journals.md §3 quotes: Amber "Drafting explanatory summaries", Red "Fabricating data, citations or results".
- **Authorship text:** the LLM-in-Methods sentence is still on https://www.nature.com/sdata/policies/editorial-and-publishing-policies, now followed by the "dedicated AI section" sentence.
- **Difference:** the JIF. The journal page shows "Journal Impact Factor: 7.2 (2025)" (https://www.nature.com/sdata/journal-impact); venues.yaml has `jif: 6.9`.
- **No other policy change found.**

## Not found or not verified

- Journal-level 2026 editorials on AI-written submissions for any journal in this cluster: NOT FOUND (web searches gave only third-party summaries).
- 2026 Scientific Reports retractions tied to Springer Nature's AI or reference tools: NOT FOUND.
- An EMBO Press rule on reviewers and AI: NOT FOUND on EMBO pages (SECONDARY claim in an aggregator only).
- EMBO Reports JIF: not shown on its page.
- A hallucinated-reference clause on nature.com itself: not found. The SN citation policy is on the BMC page (publisher-policies.md §3.2).
- No page in this cluster requires prompts, deposited outputs, or kept versions (no `tracking` value set).
