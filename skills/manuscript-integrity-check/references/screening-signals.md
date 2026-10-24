# What editors and integrity teams screen for (as of October 2026)

> Researched 2026-10-15 for the `manuscript-integrity-check` skill. Policies move monthly: re-fetch the target venue's page before relying on any rule here, and treat SECONDARY items as reports, not rules.

Research date: 2026-10-15. Purpose: give a pre-submission skill the same checks that publisher
integrity screening runs, so we can find and fix real problems (verify, disclose, calibrate)
before submission. The goal is not to evade detectors.

These are dated observations about tools and claims, not additional author obligations. Use
`author-priorities.md` and `requirement-checkability.md`. A vendor feature, publisher-wide integrity tool
or possible screening power does not establish reliable AI attribution or routine use on a given paper.
The operational report should contain material, contextual findings rather than this entire catalogue.

Status legend:

- **VERIFIED**: I fetched and read the primary source (or a full-text copy of it), or reproduced the
  number from the authors' published data.
- **SECONDARY**: seen only through a search summary, news coverage, a vendor partner, or a mirror.
- **NOT FOUND**: searched for and not found.

Vendor and publisher pages are primary sources for *what a tool claims to check*. They are not
independent evidence that the tool works. Accuracy figures from vendors are marked as vendor claims.

Supporting data (inputs, not reports):

- `kobak_2024_style_words.csv` (beside this file):
  the 379 excess *style* words of 2024, recomputed from Kobak et al.'s published counts (see 2.1).
- The downloaded sources (Liang PDF, Wikipedia wikitext, Cabanac PDF, Spick preprint, STM classification,
  Juzek & Ward PDF) were kept only for the research session; re-fetch from the URLs in §8.

---

## 1. Screening tools in use

### 1.1 Publisher consortium: STM Integrity Hub

| Item | Status | Source |
|---|---|---|
| The Hub page lists these integrations: Springer Nature's "AI-Powered Text Detection Tool", Clear Skies' Papermill Alarm, the PubPeer database "in screening tool", an STM Solutions paper-mill detection MVP, and Manuscript Manager. It describes looking at "a wide variety of patterns that are indicative of paper mills". | VERIFIED (undated page) | http://stm-assoc.org/stm-integrity-hub/ |
| Scale: more than 35 publishers, over 125,000 papers screened a month, about 1,000 suspected paper-mill submissions intercepted a month (15 Sep 2025). | VERIFIED (UKSG newsletter) | https://www.uksg.org/newsletter/stm-integrity-hub-expands-collaborative-efforts/ |
| Duplicate-submission tool: pilot from October 2023. It compares full text across journals, publishers and submission systems under confidentiality. By May 2024, 12 publishers and 35,000 manuscripts a month, with about 1% duplicated. About half of duplicates were thought to be paper-mill products. | SECONDARY | https://www.stm-assoc.org/stm-integrity-hub-launches-new-research-integrity-tool (search summary) |
| A Dec 2025 *Science Editor* piece reports 40 publishers and 7 editorial systems. **Caution:** the csescienceeditor.org URL redirected to an unrelated casino domain when fetched, so I did not follow it. | SECONDARY | https://www.csescienceeditor.org/article/the-stm-integrity-hub/ |
| "15 different checks" (Chemistry World). The Oct 2025 Chemistry World feature I fetched did not contain this. | SECONDARY, unconfirmed | https://www.chemistryworld.com/features/ai-tools-tackle-paper-mill-fraud-overwhelming-peer-review/4022253.article |

### 1.2 Clear Skies: Papermill Alarm and Oversight

| Item | Status | Source |
|---|---|---|
| Papermill Alarm Public was integrated into the Hub (1 Sep 2023) as a "traffic-light rating system". Red means strong overlap with known paper-mill content, orange moderate, green none. The Public version is "optimized for the general area of cancer research". | VERIFIED | https://stm-assoc.org/stm-integrity-hub-incorporates-clear-skies-papermill-alarm-screening-tool/ |
| In ScholarOne (13 May 2025) it alerts at submission, "powered by advanced machine learning, authorship network analysis, and content profiling". No thresholds or accuracy figures are published. | VERIFIED | https://www.silverchair.com/news/clear-skies-and-silverchair-partner-to-integrate-papermill-detection-and-journal-integrity-metrics-into-peer-review-workflows/ |
| It analyses titles and abstracts for text similar to known paper-mill articles (Nature news, 2023). | SECONDARY | https://www.hifa.org/node/96851866 (mirror) |
| Oversight is "the first index of research integrity", a journal-level index. Both tools are integrated into Frontiers' AIRA (7 Jul 2025). | VERIFIED | https://www.frontiersin.org/news/2025/07/07/frontiers-broadens-ai-driven-integrity-checks-with-integration-of-cactus |
| Oversight flags "mass retraction" journals (30 or more retractions in one journal in one calendar year). | SECONDARY (Medium blog returned 403) | https://clearskiesadam.medium.com/oversight-integrity-metrics-for-journals-875f2764bf72 |

### 1.3 Signals (Research Signals Ltd)

| Item | Status | Source |
|---|---|---|
| "Signals Manuscript Checks" claims "30+ automated signals". **Author & Institution**: "Authors' prior retractions", "High institution retraction rate", "Risky email addresses". **References**: "Retractions and self-citation rates", "Hallucinated references", "Reference relevance". **Content**: "Nonsense or irrelevant text", "Tortured phrases", "AI misuse". | VERIFIED (vendor page, undated) | https://research-signals.com/ |
| Free submission checks launched 14 Oct 2024. | VERIFIED | https://www.uksg.org/newsletter/uksg-enews-574/signals-launches-free-research-integrity-submissions-evaluation-platform-to-help-restore-trust-in-research/ |
| Editorial Manager (Aries) integration that checks authorship, references and content after submission and revision. Enago integration (May 2026). | SECONDARY | https://www.enago.com/publishers/resources/reports-enago-signals-integrated |

### 1.4 Problematic Paper Screener (Cabanac, Labbé, Magazinov)

| Item | Status | Source |
|---|---|---|
| Detectors currently listed: "Annulled", "Concerning", "Feet of Clay", "Tortured", "Suspect", "SCIgen", "Mathgen", "Citejacked", "Seek&Blastn", "Problematic Cell Lines". Last update shown: 2026-09-21. There is no upload function (it screens indexed literature). | VERIFIED | https://dbrech.irit.fr/pls/apex/f?p=9999:1 |
| Method: "fingerprint-queries" against Dimensions.ai, confirmed by human assessors. As of Oct 2021 it used 276 tortured phrases, flagging 1,694 papers. Example: "fake neural organization" for "artificial neural network". | VERIFIED | https://arxiv.org/pdf/2210.04895 (WCRI 2022 abstract) |
| Feet of Clay (papers citing retracted or annulled work): "more than 1.1 million research papers referencing about 12,000 annulled studies" (16 Feb 2026). Cabanac urges publishers to check bibliographies. | VERIFIED | https://www.timeshighereducation.com/node/741371 |
| Tortured-phrase seed list (Table 1 of Cabanac et al. 2021) is reproduced in 2.6. | VERIFIED | https://arxiv.org/abs/2107.06751 |

### 1.5 Springer Nature in-house tools

| Item | Status | Source |
|---|---|---|
| Irrelevant reference checker, launched 7 Apr 2025 across almost all SN journals and books. If "a number of references are identified as irrelevant", the manuscript is "flagged to RIG who will manually check the manuscript" and may be withdrawn. Framed against AI-generated fake papers. | VERIFIED | https://group.springernature.com/gp/group/media/press-releases/new-research-integrity-ai-tool/27769148 |
| Blog post (6 Aug 2025) listing four tools. (a) **Non-standard phrases tool** (tortured phrases, built on the PPS catalogue): manuscripts with "a significant number" of them are withdrawn. (b) **Nonsense text detector** (formerly "Geppetto"): "AI-generated nonsense text", donated to the STM Integrity Hub. (c) **SnappShot**: duplicated or manipulated gel and blot images, checked against a library of known problematic images, being extended to microscopy. (d) **Irrelevant reference checker**. Also uses iThenticate (Crossref Similarity Check) and Proofig for Nature journals. | VERIFIED | https://www.springernature.com/gp/advancing-discovery/springboard/blog/blogposts-trust-integrity/harnessing-technology-to-strengthen-research-integrity/27802690 |

### 1.6 Wiley

| Item | Status | Source |
|---|---|---|
| Papermill Detection service pilot (13 Mar 2024), with six tools: "Papermill similarity detection"; "Problematic phrase recognition" (tortured phrases); "Unusual publication behavior detection"; "Researcher identity verification"; "Gen-AI generated content detection"; "Journal scope checker" ("analyzes the article's relevance to the journal"). | VERIFIED | https://newsroom.wiley.com/press-releases/press-release-details/2024/Wiley-announces-pilot-of-new-AI-powered-Papermill-Detection-service/default.aspx |
| Imagetwin integrated into Research Exchange (26 May 2026). It detects "image duplication, manipulation, plagiarism, and AI-generated content" and adds to "the 25+ research integrity checks already embedded in Research Exchange". In a pilot it found more than 3x as many image issues as human reviewers (vendor and publisher claim). | VERIFIED | https://newsroom.wiley.com/press-releases/press-release-details/2026/Wiley-Bolsters-Research-Integrity-Efforts-with-Imagetwins-Enhanced-Image-Screening/default.aspx |

### 1.7 Elsevier

| Item | Status | Source |
|---|---|---|
| "More than 100 signals that indicate there might be something wrong with an article", processing up to 7,500 manuscripts an hour. Named signals: tortured phrases, changes in authorship, simultaneous submissions. Flags go to in-house experts. Undated page, after 2025. | VERIFIED | https://elsevier.shorthandstories.com/investing-in-integrity-how-publishers-are-safeguarding-science/index.html |
| Proprietary "Check Integrity" tool and Crossref Similarity Check at intake. | SECONDARY | casrai.org summaries |

### 1.8 Frontiers AIRA

| Item | Status | Source |
|---|---|---|
| The papermill check (since 2022) now uses "more than 15 data points and signals". Papermill Alarm, Oversight and Paperpal Preflight were integrated in 2025. "Enhanced reference and citation checks and authorship validation checks" are planned for later in 2026. | VERIFIED (7 Jul 2025) | https://www.frontiersin.org/news/2025/07/07/frontiers-broadens-ai-driven-integrity-checks-with-integration-of-cactus |
| AIRA checks "language quality, the integrity of figures and images, plagiarism, and conflicts of interest", including flagging past collaboration between authors and their editors or reviewers. | SECONDARY | https://www.frontiersin.org/about/technology-and-platforms |
| Public-dataset policy: since July 2024, "independent external validation for all health-dataset MR studies"; from 2025 the requirement covers "all papers based on simple queries of public data, including NHANES". Frontiers reports rejecting 5,513 MR studies and 1,382 NHANES submissions (15 Sep 2025, self-reported). | VERIFIED | https://www.frontiersin.org/news/2025/09/15/cutting-through-fast-churn-science-how-frontiers-raised-the-bar |

### 1.9 Cactus Paperpal Preflight and Morressier

| Item | Status | Source |
|---|---|---|
| Preflight for Editorial Desk (16 Jul 2025) has five categories. **Textual Integrity** flags "AI-generated or manipulated language, poor grammar, and unnatural phrasing". **Authorship Verification** checks affiliations and prior retractions. **Citation Analysis** flags "excessive self-citation, citation clustering, or unrelated references". **Image Review** detects AI-generated or fabricated images. **Methodology-Results Correlation** asks "whether experimental methods align with the results reported". | VERIFIED | https://cactusglobal.com/media-center/detecting-fraudulent-submissions-using-paperpal-preflight-for-editorial-desk/ |
| Paperpal Reference Checker (19 Jun 2026) covers a "Retracted research scan", "AI hallucination detection", "Broken links detection" (dead URLs, invalid DOIs) and a "Citation relevance check" ("each reference actually supports the specific claim"). It also checks self-citation, citation density and older references against a 250M+ article database. | VERIFIED | https://paperpal.com/blog/news-updates/reference-checker-verify-citations-before-you-submit |
| Morressier Integrity Manager (May 2023) covers plagiarism, citation misconduct, AI text (Copyleaks), image manipulation, institution verification and tortured phrases. | SECONDARY | https://blog.alpsp.org/2024/08/spotlight-on-morressiers-integrity.html |

### 1.10 Image tools

| Item | Status | Source |
|---|---|---|
| Proofig AI-generated image detection covers microscopy, histology, cell plates, animal imaging, medical scans, and Western blots and gels. Vendor benchmarks: microscopy 95.41% true positives and 0.0093% false positives on 200K real images; blots 97.68% and 0.0020%. Undated, method not described. | VERIFIED (vendor claim) | https://www.proofig.com/ai-generated-image-detection/ |
| Imagetwin: see Wiley 2026 above. An Aries flyer says it flags AI images and names the likely generator. | VERIFIED / SECONDARY | see 1.6; https://www.ariessys.com/wp-content/uploads/Imagetwin-Flyer.pdf |

### 1.11 AI-text detectors as screening tools

| Item | Status | Source |
|---|---|---|
| Turnitin (23 May 2023, vendor): document-level false-positive rate "less than 1%" for documents with over 20% AI writing; sentence-level about 4%. Scores under 20% carry an asterisk because false positives are higher there. Minimum length raised to 300 words. | VERIFIED (vendor claim) | https://www.turnitin.co.uk/blog/ai-writing-detection-update-from-turnitins-chief-product-officer |
| GPTZero and Pangram: see Part 4 for the independent evaluations. | | |

### 1.12 Reference and citation checkers

| Item | Status | Source |
|---|---|---|
| Crossref carries Retraction Watch data in the REST API (`update-to` entries with `source: retraction-watch`). A daily CSV is at gitlab.com/crossref/retraction-watch-data (CC BY 4.0; docs last updated 19 Jan 2025). Example query: `api.crossref.org/v1/works?filter=update-type:retraction`. To find whether a cited work is retracted, query it and read its `update-to` / `updated-by` relations, or join the CSV on DOI. | VERIFIED | https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/ |
| RefChecker (Russinovich et al., MIT licence) checks existence, titles, authors, years, venues, DOIs, arXiv IDs and URLs against Semantic Scholar, OpenAlex, Crossref, DBLP and ACL Anthology. It flags a DOI or arXiv ID that resolves to a different paper. Input: PDF, .tex, .bib/.bbl, text. `pip install academic-refchecker[llm]`; `academic-refchecker --paper paper.pdf`; `--no-llm` for structural parsing only. The deep hallucination check needs an LLM. | VERIFIED | https://github.com/markrussinovich/refchecker |
| "Phantom References" (1 Jul 2026) audits ICLR, ICML, NeurIPS and USENIX Security camera-ready papers. It defines a hallucination narrowly as "identity-level failures: non-existent works and substantial author-list mismatches", and treats venue or year drift as ordinary error. Reference-level rates are "usually below 1%". In 2025 "roughly one in twenty NeurIPS and USENIX Security papers" had at least two likely hallucinated references. | VERIFIED (abstract) | https://arxiv.org/abs/2607.00738 |
| Badalova & Mayr (Jul 2026) compare CheckIfExist, HalluCiteChecker, Hallucinator, HalRef and RefChecker. Failure modes: extraction errors, incomplete metadata, limited database coverage, inconsistent verdicts. | VERIFIED (abstract) | https://arxiv.org/abs/2607.22693 |
| GPTZero "Hallucination Check": flagged citations "are not automatically hallucinations" and each is verified by a human. | VERIFIED (vendor) | https://gptzero.me/news/neurips/ |
| scite Reference Check, Edifix (Inera; flags PubMed or Crossref retraction metadata and "RETRACTED ARTICLE" titles, queries Retraction Watch), Zotero retraction alerts. | SECONDARY | https://support.inera.com/support/solutions/articles/11000120609-how-does-edifix-detect-retracted-articles- |
| A tool named "CiteCheck". | NOT FOUND | |

---

## 2. Linguistic markers (each list cited to where it comes from)

### 2.1 Kobak et al., *Science Advances* 11(27): eadt3813, 2 Jul 2025 (VERIFIED and reproduced)

- Source: https://arxiv.org/html/2406.07016v5, data and code at https://github.com/berenslab/llm-excess-vocab
- Corpus: more than 15M PubMed abstracts, 2010–2024. At least 13.5% of 2024 abstracts were LLM-processed.
  The 13.5% is a lower bound, with subgroups ranging from under 5% to over 40%. Computational fields and
  bioinformatics are about 0.20.
- Method: counterfactual frequency `q = p_{-2} + 2*max(p_{-2} - p_{-3}, 0)` from the 2021 and 2022
  frequencies. Ratio `r = p/q`, gap `δ = p - q`. A word is excess if `δ > 0.01` or
  `log10 r > -(log10 2 / 4) * log10 p`, restricted to words with p > 1e-4 in both 2023 and 2024.
- **Reproduced:** applying this to the repo's `results/yearly-counts.csv.gz` gives 469 excess words
  in 2024, of which **379 are annotated "style"**. This matches the paper's 379. "delves" comes out at
  r = 28.03 (paper: 28.0), "underscores" 13.77 (13.8), "showcasing" 10.67 (10.7).
- Top 2024 style words by ratio (reproduced): delves 28.0, underscores 13.8, delved 12.2,
  showcasing 10.7, meticulously 10.4, delve 7.9, intricacies 7.6, underscoring 7.5, intricate 7.4,
  surpassing 7.1, delving 6.9, commendable 6.8, underscore 6.7, excels 5.8, garnered 5.3,
  underscored 5.1, intricately 5.0, realm 5.0, encompassed 4.9, renowned 4.9, grappling 4.9,
  groundbreaking 4.9, emphasizing 4.7, encompassing 4.4, necessitating 4.3, offering 4.3,
  revolutionizing 4.1, aligning 4.0, revolutionize 3.9, formidable 3.9.
- All 182 style words with r >= 2 (reproduced; full 379 in the CSV): delves, underscores, delved,
  showcasing, meticulously, delve, intricacies, underscoring, intricate, surpassing, delving,
  commendable, underscore, excels, garnered, underscored, intricately, realm, encompassed, renowned,
  grappling, groundbreaking, emphasizing, encompassing, necessitating, offering, revolutionizing,
  aligning, revolutionize, formidable, showcases, consolidates, emphasising, showcased, surpasses,
  bolstering, comprehending, endeavors, advancements, heightened, expediting, overlooking, escalating,
  notable, unveiled, stands, aiding, holds, pioneers, scrutinizing, emerges, pinpointed, fostering,
  meticulous, advocating, adept, discernible, leveraging, seamlessly, encompass, pivotal, dependable,
  pinpointing, transformative, advancing, aligns, swift, multifaceted, crafting, urging, exceptional,
  harnesses, accentuates, enhancements, nuanced, underexplored, unveils, unraveling, refining,
  interconnectedness, upholding, realms, emphasizes, notably, promise, inquiries, fosters, delineates,
  highlighting, surpassed, pioneering, necessitates, streamlining, scrutinize, encapsulates,
  exacerbating, gauged, discerning, bolstered, leverages, enhancing, illuminates, emphasises,
  propelling, paving, exceeding, hinges, poses, posing, culminating, akin, groundwork, avenues,
  encompasses, uncharted, employs, burgeoning, exhibiting, necessitate, streamlines, employing,
  endeavours, streamline, elucidates, categorizing, noteworthy, elucidating, emulation, poised, hinting,
  introduces, surmount, inadequately, uphold, unveiling, enhances, juxtaposed, warranting, pinpoint,
  discerned, facilitating, seamless, unveil, addressing, spanning, empowers, bolster, refines, revolves,
  augmenting, interplay, crucial, impressive, utilizing, integrates, discern, garnering, necessity,
  detrimentally, foundational, offers, solidify, enduring, conversely, explores, substantiated,
  capitalizing, affirming, insights, distinctions, shedding, alongside, pressing, elevates, featuring,
  equipping, heighten, refine, valuable, advancement, emulating, nuances.
- Largest absolute gaps (common words, weak alone): potential (δ 0.052), findings, crucial,
  additionally, exhibited, insights, particularly, comprehensive, enhance, notably, enhancing.
- 66% of the 2024 excess style words are verbs and 14% adjectives.
- **Caveat (from the paper):** the analysis is corpus-level and "cannot identify individual
  abstracts that may have been processed by an LLM".
- **Drift (VERIFIED, repo figure `post-publication-updates/delving_2025_july.png`):** monthly data to
  mid-2025 show "delves" peaking at about x39.5 in 2024 and falling to x8.0 by mid-2025, while the
  aggregate excess of style words (291 rare and 10 common) keeps rising. Single words fade; the
  overall style persists.

### 2.2 Liang et al., *Nature Human Behaviour*, "Quantifying large language model usage in scientific papers" (DOI 10.1038/s41562-025-02273-8; received 2 May 2024; published Aug 2025) (VERIFIED)

- Source: https://nlp.stanford.edu/~manning/papers/Liang_et_al-2025-Nature_Human_Behaviour.pdf
- 1,121,912 papers (arXiv, bioRxiv, Nature portfolio), Jan 2020 to Sep 2024. Uses a distributional
  (population-level) estimate of the fraction α of LLM-modified sentences.
- By Sep 2024, α was 22.5% for computer-science abstracts and 19.6% for introductions; 7.7% (math) and
  8.9% (Nature portfolio) for abstracts. The pre-ChatGPT baseline of 2.4–3.4% matches the method's
  false-positive rate.
- Higher in abstracts, introductions, related work and conclusions than in methods and experiments.
  Higher for shorter papers, crowded fields and prolific preprint posters.
- Fig. 5 names the four words "most disproportionately generated by LLMs": **realm, intricate,
  showcasing, pivotal**.
- States the method "does not detect individual cases of use". It also cites Lepp & Smith: reviewers
  now read words like "delve" as indicators that an author "might not be a native English speaker".
  This is a bias hazard for any word screen.

### 2.3 Juzek & Ward, "Why Does ChatGPT 'Delve' So Much?" (COLING 2025, arXiv 2412.11385) (VERIFIED)

- 21 focal words from Table 3: advancements, aligns, boasts, comprehending, delve, delves, delved,
  delving, emphasizing, garnered, groundbreaking, intricate, intricacies, realm, showcases, showcasing,
  surpasses, surpassing, underscore, underscores, underscoring.
- They find no evidence that architecture, algorithms or training data cause the overuse. Their
  results are "consistent with RLHF playing a role".

### 2.4 Grammatical profile: Reinhart et al., *PNAS* 122(8), Feb 2025 (VERIFIED via arXiv 2410.16107 Table 3)

Relative to human text (human = 100%), instruction-tuned models overuse:

- present participial clauses: GPT-4o 527%, GPT-4o-mini 481%, Llama-3-70B-Instruct 261%
- "that"-clauses as subject: 173–331%
- nominalizations: 145–214%
- phrasal coordination: 144–194%

GPT-4o uses agentless passives at about half the human rate. Base models stay near human rates. This
is the measurable form of the "-ing tail" pattern ("..., highlighting the importance of ...").

### 2.5 Wikipedia, "Wikipedia:Signs of AI writing" (VERIFIED page, revision 1380310647, 2026-10-15T00:31:43Z; community-curated, so its claims are secondary)

URL: https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing

- **Words to watch (AIVOCAB box):** Additionally (sentence-initial), align with, boasts (meaning
  "has"), bolstered, crucial, deep dive, delve, emphasizing, enduring, enhance, fostering, garner,
  highlight (verb), interplay, intricate/intricacies, key (adjective; marked citation needed),
  landscape (abstract noun), meticulous/meticulously, pivotal, robust, showcase, tapestry (abstract
  noun), testament, underscore (verb), valuable, vibrant. Cited sources: Kobak, Juzek & Ward, Russell
  et al., Geng & Trotta, Reinhart et al., Kriss (NYT), The Economist (Jul 2026).
- **Eras (community observation):** 2023–mid-2024 (GPT-4): delve, tapestry, testament, intricate,
  pivotal, underscore, meticulously, landscape. Mid-2024–mid-2025 (GPT-4o): align with, enhance,
  fostering, highlighting, showcasing, vibrant. Mid-2025–mid-2026 (GPT-5): emphasizing, enhance,
  highlighting, showcasing. Mid-2026 on: challenge, clearer, dependable, echoed, foster, leverage,
  matters, multifaceted, practical, prioritize, quietly, steady, universally, plus shorter sentences.
  Grok overuses "causal", "empirical", "correlate", "underscore".
- **Phrase families:** "stands/serves as", "is a testament/reminder", "a crucial/pivotal/vital/
  significant/key role/moment", "underscores/highlights its importance", "reflects broader",
  "setting the stage for", "evolving landscape", "focal point", "indelible mark", "deeply rooted".
  Superficial -ing analyses: "highlighting/underscoring/emphasizing ...", "ensuring ...",
  "contributing to ...", "fostering ...", "valuable insights", "align/resonate with".
  Copula avoidance: "serves as/stands as/marks/functions as/represents", "boasts/features/offers"; the
  page cites a study measuring an over 10% drop in "is"/"are" in academic writing in 2023.
  Negative parallelism: "Not only ... but ...", "It is not just ..., it's ...". Rule of three.
  Outline-like conclusions: "Despite its ... faces several challenges", "Despite these challenges",
  "Future Outlook". Vague attributions: "Experts argue", "Industry reports", "several sources".
  Didactic disclaimers: "it's important/critical/crucial to note/remember/consider", "worth noting",
  "may vary". Section summaries: "In summary", "In conclusion", "Overall".
- **Formatting:** title-case headings, mechanical boldface, inline-bold-header bullet lists, emoji,
  Markdown residue, thematic breaks. Curly quotes alone do not count.
- **Em dashes:** listed as "Overuse of em dashes (2022–September 2026)", now a historical indicator.
  The page says AI em dashes are often spaced, and that newer models are tuned to avoid them, so a
  lack of punctuation variety is becoming its own tell (marked citation needed). It cites The Economist
  (30 Jul 2026, SECONDARY) as finding that of contemporary models "only Claude used em dashes more than
  professional writers". This matters whenever Claude is in the toolchain.
- **Chatbot leftovers:** "I hope this helps", "Of course!", "Certainly!", "You're absolutely right!",
  "Would you like...", "is there anything else", "let me know", "here is a". Placeholders:
  "[Your Email Address]", "[Article Title 1]", access dates like "2025-XX-XX". Refusals: "as an AI
  language model", "as a large language model", "I'm sorry". Knowledge cutoff: "as of my last
  knowledge update", "Up to my last training update". Hedges about sources: "While specific details
  are limited/scarce", "not widely available/documented".
- **Markup and citation artifacts:** ChatGPT: `contentReference`, `oaicite`, `oai_citation`,
  `turn0search0`, `attributableIndex`, "+1". Gemini: `[cite: 1]`, `[span_1](start_span)`. Grok:
  `grok_card`, `grok_render_citation_card_json`. DeepSeek: lenticular brackets 【】 and daggers.
  Perplexity: `attached_file`, `ppl-ai-file-upload`. Also `:::writing` and `utm_source=chatgpt.com`.
  Invalid DOIs or ISBN checksums, DOIs that lead to unrelated articles, dead links, references
  declared but never cited.
- **Ineffective indicators (do not flag):** perfect grammar; mixed registers; "bland" prose; formal or
  "fancy" prose in general (only *specific* words are overused); transition words in isolation;
  unsourced content; curly quotes; Markdown alone (in some contexts).
- **Instruction from the page:** "Please do not merely treat these signs as the problems to be fixed;
  that could just make detection harder." The signs point to deeper problems (unverified claims,
  fabricated sources). This matches the fix-not-obfuscate rule of these skills.

### 2.6 Tortured phrases: Cabanac, Labbé & Magazinov (arXiv 2107.06751, Jul 2021), Table 1 (VERIFIED)

Each tortured phrase is followed by the expected term. profound neural organization → deep neural
network; (fake | counterfeit) neural organization → artificial neural network; versatile
organization → mobile network; organization (ambush | assault) → network attack; organization
association → network connection; (enormous | huge | immense | colossal) information → big data;
information (stockroom | distribution center) → data warehouse; (counterfeit | human-made)
consciousness → artificial intelligence; elite figuring → high performance computing; haze figuring →
fog/cloud computing; designs preparing unit → GPU; focal preparing unit → CPU; work process motor →
workflow engine; facial acknowledgement → face recognition; discourse acknowledgement → voice
recognition; mean square (mistake | blunder) → mean square error; mean (outright | supreme)
(mistake | blunder) → mean absolute error; (motion | flag | indicator | sign | signal) to (clamor |
commotion | noise) → signal to noise; worldwide parameters → global parameters; (arbitrary |
irregular) get right of passage to → random access; (arbitrary | irregular) (backwoods | timberland
| lush territory) → random forest; (arbitrary | irregular) esteem → random value; subterranean insect
/ underground creepy crawly (state | province | area | region | settlement) → ant colony; leftover
vitality → remaining energy; territorial normal vitality → local average energy; motor vitality →
kinetic energy; (credulous | innocent | gullible) Bayes → naive Bayes; individual computerized
collaborator → personal digital assistant.

The same paper lists other red flags: "references to non-existing literature", "references to
non-existing internal entities of the paper (e.g., theorems and variables in formulas)", text or
image reuse without acknowledgement, and "sentences for which we failed to infer any meaning". The
PPS now holds many more fingerprints. I found no bulk download of the current list (NOT FOUND).

### 2.7 Chatbot fingerprints in published papers

- **Academ-AI (Glynn; arXiv 2411.15218; IntelliSys 2026, LNNS vol. 2077)** (VERIFIED): 768 documented
  examples, more common in journals with higher citation metrics and APCs; few are corrected. The v1
  Methods search dictionary (500 documents) with the share of documents matching each feature:
  - data cutoff or update ("update", "cutoff", "cut-off", "training data", "up until", "up to my",
    "my last"): 49.0%
  - "regenerate response": 11.6%
  - "certainly here": 31.8%
  - first-person singular ("i'm", "i have", "i can*", "i must", "i do*", "i am", "i recommend",
    "i advise", "i apologize", "i would", "i encourage", "i provide", "my", "me"): 55.2%
  - lack of access ("don't have access", "don't have real-time access", "real-time information", ...): 8.6%
  - second person ("you", "your", "you're", "you've"): 13.8%
  - "language model": 8.6%
  - referral to other sources ("recent", "latest", "up-to-date"): 20.6%, needs manual screening

  Google Scholar was also searched for "as an AI language model", "certainly, here are" and "don't have
  access to real-time".
  https://arxiv.org/html/2411.15218v1
- **Retraction Watch list** "Papers and peer reviews with evidence of ChatGPT writing", built on
  Cabanac's search strategy and posted to PubPeer: 95 entries when fetched (VERIFIED).
  https://retractionwatch.com/papers-and-peer-reviews-with-evidence-of-chatgpt-writing/
- **Strzelecki, "As of my last knowledge update", *Learned Publishing* 38(1), 2025
  (DOI 10.1002/leap.1650)**: undisclosed ChatGPT text in premier journals, including "regenerate
  response", plus "silent corrections" by publishers (SECONDARY).

### 2.8 Hype and overclaiming lexicons

- **Vinkers, Tijdink & Otte, *BMJ* 2015;351:h6467** (VERIFIED, Europe PMC full text PMC4677695). The 25
  positive words: amazing, assuring, astonishing, bright, creative, encouraging, enormous, excellent,
  favourable, groundbreaking, hopeful, innovative, inspiring, inventive, novel, phenomenal, prominent,
  promising, reassuring, remarkable, robust, spectacular, supportive, unique, unprecedented. The share
  of abstracts using them rose from 2.0% to 17.5% (1974–2014), driven by "robust", "novel",
  "innovative" and "unprecedented". Authors at institutions in non-English-speaking countries used
  more of them, another fairness caveat.
- **Millar, Batalo & Budgell, *JAMA Netw Open* 2022 (DOI 10.1001/jamanetworkopen.2022.28676)** (VERIFIED,
  PMC9412227). 139 hype adjective forms in NIH grant abstracts, 130 of them increasing. Box categories:
  Importance (compelling, critical, crucial, essential, foundational, fundamental, imperative,
  important, indispensable, invaluable, key, major, paramount, pivotal, significant, strategic,
  timely, ultimate, urgent, vital); **Novelty** (creative, emerging, first, groundbreaking,
  innovative, latest, novel, revolutionary, unique, unparalleled, unprecedented); Rigor (accurate,
  advanced, careful, cohesive, detailed, nuanced, powerful, quality, reproducible, rigorous, robust,
  scientific, sophisticated, strong, systematic); Scale (ample, biggest, broad, comprehensive,
  considerable, deeper, diverse, enormous, expansive, extensive, fastest, greatest, huge, immediate,
  immense, interdisciplinary, international, interprofessional, largest, massive, multidisciplinary,
  myriad, overwhelming, substantial, top, transdisciplinary, tremendous, vast); Utility (accessible,
  actionable, deployable, durable, easy, effective, efficacious, efficient, generalizable, ideal,
  impactful, intuitive, meaningful, productive, ready, relevant, rich, safer, scalable, seamless,
  sustainable, synergistic, tailored, tangible, transformative, user-friendly); Quality (ambitious,
  collegial, dedicated, exceptional, experienced, intellectual, longstanding, motivated, premier,
  prestigious, promising, qualified, renowned, senior, skilled, stellar, successful, talented,
  vibrant); Attitude (attractive, confident, exciting, incredible, interesting, intriguing, notable,
  outstanding, remarkable, surprising); Problem (alarming, daunting, desperate, devastating, dire,
  dismal, elusive, stark, unanswered, unmet). Largest absolute increases: novel, critical, key.
- Most of these are ordinary scientific words. A skill should not ban them. It should require that each
  priority claim ("first", "novel", "only", "unprecedented") or utility claim ("scalable", "seamless",
  "user-friendly") be backed by a stated comparison or measurement in the paper.

---

## 3. Content-level red flags that editors cite

| Flag | Evidence | Status |
|---|---|---|
| **Hallucinated references** | Topaz et al. (Lancet letter, 7 May 2026) audited about 2.5M PubMed-indexed papers and 97.1M references. They found 4,046 fabricated references in 2,810 papers, rising from 1 in 2,828 papers (2023) to 1 in 458 (2025) and 1 in 277 (early 2026). 91% of affected papers had only one or two fabricated references; reviews had a 57% higher rate. https://retractionwatch.com/2026/05/07/one-in-277-pubmed-indexed-papers-in-2026-shows-fabricated-references-says-analysis/ | VERIFIED (RW report) |
| | Grounded AI with Nature (5 Apr 2026): more than 110,000 (1.65%) of 2025 publications have at least one hallucinated citation. Five publishers sampled; only the top-100 risk papers were manually validated. https://groundedai.company/research/hallucinated-citations-nature-2026/ ; Nature feature https://www.nature.com/articles/d41586-026-00969-z (paywalled) | VERIFIED (Grounded AI page); Nature SECONDARY |
| | GPTZero (21 Jan 2026): 100 confirmed hallucinated citations in more than 51 NeurIPS 2025 accepted papers (4,841 scanned). Error types: combined or paraphrased elements of real sources; fabricated authors, title, URL/DOI or venue; modified authors (a first name extrapolated from an initial, authors dropped or added); arXiv IDs pointing to a different paper; placeholders such as "John Doe", "Firstname Lastname". | VERIFIED (vendor) |
| | Walters & Wilder, *Sci Rep* 2023: 55% of GPT-3.5 and 18% of GPT-4 citations fabricated; 43% and 24% of the real ones had substantive errors. | SECONDARY |
| | **arXiv** (14 May 2026, CS section chair Dietterich): one-year ban for "incontrovertible evidence" that authors did not check LLM output (hallucinated references, leftover chatbot text, placeholder values). Later submissions must first be accepted at a peer-reviewed venue. I found no official arXiv policy page. | SECONDARY |
| **Citations to retracted papers** | Feet of Clay (1.12M papers); Signals, Paperpal and Edifix check this; Crossref exposes it. Clarivate excluded citations to retracted papers from 2025 JIF calculations (RW, 18 Jun 2025). | VERIFIED / Clarivate SECONDARY |
| **Irrelevant references** | SN irrelevant reference checker (2025); Signals "Reference relevance"; Paperpal "Citation relevance check"; Wiley "Journal scope checker" (article to journal). | VERIFIED |
| **Self-citation and citation cartels** | Paperpal "excessive self-citation, citation clustering"; Signals "self-citation rates". Clarivate suppressed 20 journals' JIFs in 2025 (4 for stacking, the rest for self-citation), comparing against the subject category rather than a fixed cutoff. https://retractionwatch.com/2025/06/18/clarivate-impact-factor-suppression-list-2025-self-citation-stacking/ | VERIFIED (tools) / SECONDARY (Clarivate). **NOT FOUND:** any published numeric self-citation threshold for a single manuscript. |
| **Mismatched numbers, placeholders, dangling internal references** | Paperpal "Methodology-Results Correlation"; Cabanac 2021 "references to non-existing internal entities"; arXiv "placeholder values". GRIM test (Brown & Heathers): about half of testable psychology articles had an inconsistent mean (SECONDARY). INSPECT-SR (BMJ 2025, 21 checks in 4 domains, for RCT trustworthiness; SECONDARY). | VERIFIED (tool categories). **NOT FOUND:** a study measuring abstract-versus-text number mismatch as an LLM marker. |
| **Generic limitations** | Wikipedia "outline-like conclusions about challenges" (verified page). arXiv 2601.11578 reports single-prompt LLMs generate shallow limitations (dataset bias, generalizability) that echo what authors disclosed (SECONDARY). | **NOT FOUND** as an explicit editor or tool screen |
| **Overclaiming ("novel", "first", "groundbreaking")** | Vinkers 2015; Millar 2022; Kobak 2024 excess words include groundbreaking, revolutionize, revolutionizing, transformative, pioneering, unprecedented-adjacent forms. | VERIFIED (lexicons). **NOT FOUND:** a publisher tool that flags priority claims. |
| **Template public-database papers** | Spick et al., medRxiv 2025.07.07.25331008 (9 Jul 2025): of 34 open datasets, 5 show paper-mill hallmarks (FAERS, NHANES, UK Biobank, FinnGen, GBD). Title tokens that rose 2021→2024: NHANES "association" 20.9→44.5%, "cross-sectional" 7.2→21.2%; FinnGen "mendelian randomization" 50.7→77.0%, "causal" 11.0→35.4%, "bidirectional" 4.1→16.9%; FAERS "real world" 12.1→34.7%, "pharmacovigilance" 18.8→36.4%; GBD "burden" 41.0→64.2%. Also a shift in last-author geography. Study designs: single-factor association with logistic regression or cubic splines; disproportionality ROR/PRR/BCPNN mining; MR for implausible causal links. The published version (J Clin Epidemiol 2026, PMC13178217) extends this to 9 datasets (adds CHARLS, MIMIC III/IV, TriNetX, CDC WONDER) and estimates about 11,577 excess papers a year by 2025. Suchak et al., *PLOS Biol* 2025 (NHANES, 341 papers). Frontiers external-validation policy. Stender et al. 2024 advise editors to reject MR-only papers. | Spick preprint VERIFIED; journal version, Suchak and Stender SECONDARY; Frontiers VERIFIED |
| **Statistical boilerplate** | Single-factor models ignoring multifactorial causes, no false-discovery control, unexplained subsetting of data years (Suchak; Spick). | SECONDARY / VERIFIED (Spick) |
| **Figures that don't match the text; AI images** | Paperpal "Image Review" (illegible labels, inconsistencies); Proofig, Imagetwin, SnappShot. STM category 9 forbids presenting AI-generated content as research data. | VERIFIED |
| **Missing code and data availability** | Bioinformatics requires source at a stable URL; the submitted version and test data archived (Zenodo, Figshare, Software Heritage, CRAN, Bioconductor) with the URL in the abstract's availability section; an open-source licence (OSI); a data availability statement; software available for 2 years after publication (Application Notes). https://academic.oup.com/bioinformatics/pages/author-guidelines | VERIFIED |
| **Authorship and identity** | Signals "Risky email addresses", "Authors' prior retractions"; Wiley "Researcher identity verification"; Elsevier "changes in authorship"; AIRA author-editor collaboration conflicts (SECONDARY). | VERIFIED |
| **Duplicate or simultaneous submission** | STM Hub duplicate tool; Elsevier "simultaneous submissions". | VERIFIED (Elsevier) / SECONDARY (STM specifics) |

---

## 4. How reliable AI-text detectors are

| Finding | Status | Source |
|---|---|---|
| Liang, Yuksekgonul, Mao, Wu & Zou, *Patterns* 2023 (arXiv 2304.02819v3). Seven detectors misclassified TOEFL essays by non-native writers as AI at an **average false-positive rate of 61.22%**. All seven agreed on 18/91 (19.78%); at least one flagged 89/91 (97.80%). US 8th-grade essays were classified near-perfectly. Asking ChatGPT to "enhance word choices" cut the FPR to 11.77%, so the detectors measure low perplexity, not authorship. | VERIFIED | https://arxiv.org/abs/2304.02819 |
| Weber-Wulff et al., *Int J Educ Integrity* 19:26 (2023): 14 tools (incl. Turnitin) judged "neither accurate nor reliable", biased towards labelling AI text as human; obfuscation degrades them. Figures such as "all below 80% accuracy" come from a summary. | SECONDARY | https://link.springer.com/article/10.1007/s40979-023-00146-z |
| Turnitin vendor claim: <1% document FPR (above 20% AI), about 4% at sentence level, higher FPR below 20%. | VERIFIED (vendor) | 1.11 |
| Jabarian & Imas, NBER w34223 (Sep 2025): commercial detectors beat open-source RoBERTa. Pangram had "near-zero FNR and FPR" and was the only one to meet a strict FPR <= 0.005 "policy cap". Grammar-correction uses are hard to separate from other uses. | VERIFIED | https://www.nber.org/papers/w34223 |
| Epoch AI (15 Jul 2026): 495 human passages (blog, fiction, scientific). Pangram 0/495 and GPTZero 0/495 false positives; Originality.ai 19/495 (3.8%), all on pre-ChatGPT text. Style-imitated AI text evaded detectors 10–18% of the time overall, and in **scientific writing 24–29%** (worst genre). | VERIFIED | https://epoch.ai/data-insights/ai-detectors-false-negatives |
| Pangram technical report (arXiv 2402.14873): 0% FPR on the 91 TOEFL essays, 0.09% on ICNALE. GPTZero 7.7% on the TOEFL set. Self-reported. | SECONDARY | https://arxiv.org/pdf/2402.14873 |
| Russell, Karpinska & Iyyer (ACL 2025): the majority vote of five frequent LLM users misclassified 1 of 300 articles. They relied on "AI vocabulary" plus formality, originality and clarity, and beat most detectors even after paraphrasing or humanizing. | VERIFIED (abstract) | https://aclanthology.org/2025.acl-long.267/ |
| Untrained humans are no better than chance (Cheng et al. 2025, *Adv Simul*); 57% (AI) and 64% (human) recognition on German theses (Fiedler & Döpke 2025). Detection scores are explicitly not grounds for Wikipedia's G15 speedy deletion. | SECONDARY (via Wikipedia) | Wikipedia 2.5 |
| The corpus-level studies (Kobak; Liang NHB) state they cannot identify individual papers. | VERIFIED | 2.1, 2.2 |

**What follows for the skill:**

1. Detector scores are not evidence about one manuscript. The 2023 studies show large,
   language-background-dependent false positives. The 2025–26 studies show the best commercial
   detectors now rarely flag human prose, but they still miss style-imitated scientific text a
   quarter of the time. In both cases a score says nothing about whether the claims, numbers and
   references are right, which is what editors act on (references, relevance, numbers,
   availability, disclosure).
2. If the text was substantially drafted by an LLM, modern detectors will likely say so. What follows is an
   accurate disclosure where the chosen venue asks for one; whether to rewrite is the authors' decision, and a
   rewrite does not undo earlier drafting. Rewriting only to lower a detector score (synonym-swapping
   "humanizer" tools, as opposed to editing for clarity) does not help the paper and is the mechanism that
   produces tortured phrases, the oldest paper-mill fingerprint.
3. Word lists flag non-native writers and LLM-assisted language polishing, which ISCB and OUP permit.
   Report density per section with the source of each word, never a verdict.

---

## 5. Worked example: the policies that bind a Bioinformatics submission with an arXiv preprint

| Policy | Text | Status | Source |
|---|---|---|---|
| **Bioinformatics author guidelines**, "Policy for Acceptable Use of Large Language Models" | Follows ISCB policy. "It is not acceptable to use LLMs or related technologies to draft papers." LLMs cannot be authors. LLM use that produced content must be "explicitly declared and documented with sufficient details in the supplementary materials", and disclosed in the cover letter and Methods or Acknowledgements. Reviewers may not upload manuscripts to an LLM. | VERIFIED (undated, © 2026) | https://academic.oup.com/bioinformatics/pages/author-guidelines |
| **ISCB Acceptable Use of LLMs** (updated 3 Apr 2025) | Unacceptable: drafting paper sections or abstracts ("papers/abstracts MUST be written by humans"), reviewing, LLM authorship. Acceptable: spell and grammar correction; translation (human responsible); **"Evaluation, to find inconsistencies or anomalies"**; labelled LLM text snippets as examples; code writing and documentation (human responsible); background research verified against trusted sources. OUP has also accepted it for *Bioinformatics*. | VERIFIED | https://www.iscb.org/about-iscb/policy-statements-bylaws-and-legal-documents/acceptable-use-of-large-language-models-policy |
| **OUP ethics page** | Generating content or images, writing code, processing data or translating with AI "must be disclosed both in cover letters to editors and in the Methods or Acknowledgements". OUP screens author lists for AI tools. | VERIFIED (undated) | https://academic.oup.com/pages/authoring/journals/preparing_your_manuscript/ethics |
| **ICMJE V.A** (2026) | Describe AI use "in both the cover letter and the submitted work". Chatbots are not authors. Humans are responsible. "Referencing AI-generated material as the primary source is not acceptable." Nondisclosure "may be construed as misconduct". | VERIFIED | https://www.icmje.org/recommendations/browse/artificial-intelligence/ai-use-by-authors.html |
| **COPE position** (13 Feb 2023) | AI cannot be an author. Disclose the tool and its use in Methods. | SECONDARY | https://publicationethics.org/guidance/cope-position/authorship-and-ai-tools |
| **STM classification of AI use** (draft 7 Apr 2025; final Sep 2025 SECONDARY) | Nine categories. 1 language editing (2023 STM guidelines: disclosure not necessary); 2 writing or drafting content; 3 translation; 4 formatting reported data; 5 illustrative images; 6 visualising research data; 7 refining reported code; **8 compiling reference lists (excludes "AI generation of plausible-sounding references that do not exist")**; 9 presenting AI content as original data (not allowed). | VERIFIED (draft) | https://stm-assoc.org/new-stm-draft-report-classifying-ai-use-in-manuscript-preparation/ |

**Design consequence:** under ISCB and Bioinformatics policy, a pre-submission checker fits the
permitted "Evaluation, to find inconsistencies or anomalies" use; rewriting the prose is less clearly covered
(only correction aids are named). That is a point for the authors to weigh, not a limit on the skills: when
they ask for edits, make them and, if the venue's rule is relevant, say so once (`author-priorities.md`, "The
author decides"). A review-only request gets findings that quote the passage with its section, name the rule
with its source, and say what the authors would change: verify, delete, re-measure, cite, disclose. Where AI
was used (for example code, figures, language polishing, these checks), the disclosure statement is drafted by
`manuscript-journal-adapt` (tool, version, where, how verified); this check only reports whether one is
required and present.

---

## 6. Consolidated, mechanically checkable signals (source-attributed)

Severity: **H** means editors or tools act on it directly (desk-rejection, withdrawal, or the arXiv
ban class). **M** means it routes the manuscript to manual review. **L** is a soft stylistic signal:
report its density, never a verdict. The fix column is always substantive. The letters and the IDs (A1 to
D12) label this catalogue for the agent; a report describes the signal in plain words, quotes the passage with
its section, and places it by when it can be fixed (`author-priorities.md`), with an ID at most in parentheses.
Severity here is how editors react, not when the authors can act: availability and disclosure items (D7, D8)
are end-stage work for a draft.

### A. Chatbot leftovers and artifacts (H)

| ID | Check (case-insensitive, outside quoted examples and code) | Source | Fix |
|---|---|---|---|
| A1 | `regenerate response`, `certainly, here`, `here is a`, `as an ai language model`, `as a large language model`, `i hope this helps`, `let me know`, `would you like`, `is there anything else`, `of course!`, `you're absolutely right` | Academ-AI Table 1; Wikipedia WP:CERTAINLY, Prompt refusal | Delete, then re-verify every claim in that paragraph. Check whether the chosen venue requires an AI-use statement for that use (`manuscript-journal-adapt`); disclose only where it does. |
| A2 | Cutoff and access disclaimers: `as of my last knowledge update`, `up to my last training update`, `my last (update\|training)`, `training data` (outside an ML methods context), `don't have (real-time\|direct\|specific) access`, `real-time (information\|updates\|statistics)` | Academ-AI; Wikipedia WP:AICUTOFF | Delete. Replace any "latest" claim with a dated, cited fact. |
| A3 | First-person singular (`\bI (recommend\|advise\|apologize\|can\|must\|would)\b`, `\bI'm\b`) and reader address (`\byou(r)?\b`) in body text of a multi-author paper | Academ-AI | Rewrite as an authorial statement, or delete if it was chatbot advice. |
| A4 | Placeholders: `\[(Insert\|Your\|Article Title\|Author\|Citation\|TODO)[^\]]*\]`, `XX` in dates or numbers, `TBD`, `TODO`, `lorem ipsum`, `(Add .* here)` | Wikipedia WP:AIPLACEHOLDER; arXiv ban ("placeholder values") | Fill from the actual result or remove. |
| A5 | Tool markup: `contentReference`, `oaicite`, `oai_citation`, `turn0search\d`, `citeturn`, `attributableIndex`, `\[cite: ?\d+\]`, `\[span_\d+\]`, `start_span`, `grok_card`, `grok_render_citation_card_json`, `attached_file`, `ppl-ai-file-upload`, `:::writing`, `【`, `】`, `utm_source=(chatgpt\.com\|openai)` | Wikipedia §Markup, §utm_source | Remove. Re-source the attached claim from the primary literature. |
| A6 | Dangling internal references: LaTeX `??` or undefined labels; "Figure N", "Table N", "Supplementary Table SN", "Eq. N" pointing at items that do not exist; symbols used but never defined | Cabanac et al. 2021 ("references to non-existing internal entities") | Fix the reference or remove the claim. |
| A7 | Markdown residue in a LaTeX or Word manuscript (`**bold**`, `## `, `- **Header**:` inline-bold bullet lists, emoji) | Wikipedia §Style, §Markdown | Convert to journal style. Check that the list was not a chatbot outline pasted in. |

### B. References (H; the 2026 focus of SN, Signals, Paperpal, AIRA, arXiv)

| ID | Check | Source | Fix |
|---|---|---|---|
| B1 | Every DOI resolves (doi.org / Crossref `works/{doi}`), every PMID resolves (E-utilities `esummary`), every arXiv ID resolves (arXiv API). The resolved title fuzzy-matches the cited title and the first author matches. | GPTZero taxonomy; RefChecker; Phantom References; Wikipedia (invalid DOI, DOI to unrelated article); Paperpal broken links | Replace with the verified record or delete the citation and its claim. Never "fix" by searching for any paper that fits. |
| B2 | Identity-level mismatch: the identifier resolves to a different work; the author list differs substantially; a real title with invented authors (chimeric); "John Doe", "Firstname Lastname", or "et al." with invented names | GPTZero NeurIPS; Phantom References definition | Same as B1. Treat it as unconfirmed until checked by hand; a mismatch alone is not proof of fabrication. |
| B3 | References without DOI, PMID or URL are found by title search in Crossref, OpenAlex or Semantic Scholar. No hit means "Unverified". | RefChecker ("Unverified" verdict); Badalova & Mayr (database coverage limits) | Supply an identifier, or justify (book with ISBN and pages, standard, dataset DOI). |
| B4 | Retraction or expression of concern: `update-to` / `updated-by` relations with `type: retraction` (or `source: retraction-watch`) in Crossref, or a DOI join against the Retraction Watch CSV (daily) | Crossref docs; Feet of Clay; Signals; Paperpal; Edifix | Remove, or keep only when discussing the retraction and say so in the text. |
| B5 | Relevance: similarity between the citing sentence and the cited abstract or title (embedding or keyword overlap). Low scores go to the author for manual confirmation. | SN irrelevant reference checker; Signals "Reference relevance"; Paperpal "Citation relevance" | Cite the source that supports the specific claim, or remove the claim. |
| B6 | Self-citation share (references with any manuscript author), top-author concentration, single-journal clustering | Signals "self-citation rates"; Paperpal "citation clustering"; Clarivate stacking | Report only (no published per-paper threshold found). Remove citations that do not support a specific statement. |
| B7 | Bibliography hygiene: entries never cited in text and in-text citations missing from the list; dead URLs (HTTP status), checked against the Internet Archive | Wikipedia ("named references declared but unused", dead links) | Fix or remove. |
| B8 | Version drift: preprint cited when a published version exists (Crossref `is-preprint-of` relation) | RefChecker-style metadata; Phantom References treats it as non-hallucination drift | Cite the version of record. Low severity. |

### C. Lexical and stylistic signals (L; density with attribution, never a verdict)

| ID | Check | Source | Fix |
|---|---|---|---|
| C1 | Density per 1,000 words, per section (abstract and intro weighted as Liang found them highest), of: the 182 Kobak 2024 style words with r >= 2; Juzek & Ward's 21 focal words; Liang's four (realm, intricate, showcasing, pivotal); the Wikipedia AIVOCAB box. Report each hit with the list it came from. | Kobak 2025; Juzek & Ward 2025; Liang 2025; Wikipedia | Ask whether the word says something precise. If not, write the specific fact (what was measured, how much). Never swap in a synonym: synonyms are not the problem, and swapping is how tortured phrases arise. |
| C2 | Phrase templates: `plays? an? (crucial\|pivotal\|key\|vital) role`, `(serves\|stands) as`, `is a testament to`, `underscor(es\|ing) the (importance\|need)`, `valuable insights`, `(sheds?\|shedding) light`, `paves? the way`, `in the realm of`, `(evolving\|changing) landscape`, `it is (important\|crucial\|worth) (to note\|noting)`, `may vary`, `not only .{1,80} but also`, `it'?s not .{1,60}, it'?s`, `despite these (challenges\|limitations)`, sentence-initial `Additionally,` / `Notably,` / `Overall,` / `In conclusion,` / `In summary,` | Wikipedia (sections in 2.5); Kobak (additionally, notably) | Replace the template with the claim it stands for, or delete it if it adds nothing. |
| C3 | Present-participle tails: main clause + `, (highlighting\|underscoring\|emphasizing\|showcasing\|demonstrating\|reflecting\|ensuring\|fostering\|enhancing\|paving\|contributing) ` | Reinhart 2025 (participial clauses 2–5x); Wikipedia "Superficial analyses" | Either state the evidence for the implication in its own sentence, or cut the tail. |
| C4 | Copula avoidance ratio: (`serves as\|stands as\|functions as\|represents\|boasts\|features\|offers`) / (`is\|are`) | Wikipedia WP:AINOCOPULA (cites a >10% drop in is/are, 2023) | Use "is" where "is" is meant. |
| C5 | Rule-of-three density: `\w+, \w+(,)? and \w+` triplets per paragraph, flagged when most paragraphs end in one | Wikipedia WP:RO3 | Keep the items that are real. A list of three should have three members because there are three. |
| C6 | Hype and priority claims: each `first`, `novel`, `only`, `unprecedented`, `groundbreaking`, `revolutionary`, `unique`, `state-of-the-art`, `seamless`, `user-friendly`, `scalable`, `comprehensive` must be backed by a cited comparison or a measurement in the paper | Vinkers 2015; Millar 2022; Kobak 2024 | Add the comparison (what was searched, when) or remove the adjective. For "scalable" or "fast", give the measured numbers. |
| C7 | Em-dash rate (and spaced em dash ` — `); en dashes used as em dashes | Wikipedia WP:AIDASH (historical 2022–Sep 2026; Claude still heavy per The Economist, SECONDARY); follow the project's own house style (CLAUDE.md, AGENTS.md) where it sets one | Use commas, colons, parentheses or full stops for what the clause actually does. |
| C8 | Title case in headings where the journal uses sentence case; mechanical boldface | Wikipedia §Style | Follow the journal style. |
| C9 | Tortured phrases: regex from Cabanac Table 1 (2.6), plus any PPS fingerprints we can collect | Cabanac et al. 2021; PPS; SN non-standard phrases tool (withdraws on "a significant number"); Wiley; Signals; Elsevier | Use the established term. Find out how the phrase got there (paraphrasing tool). |
| C10 | Do **not** flag: perfect grammar, formal register, curly quotes, transition words in isolation, the mere use of "robust" or "significant" in a statistical sense | Wikipedia "Ineffective indicators" | n/a |

### D. Content consistency and completeness (M to H)

| ID | Check | Source | Fix |
|---|---|---|---|
| D1 | Every number in the abstract (counts, percentages, sample sizes, versions, runtimes) appears identically in the results, tables or supplement. Percentages recompute from their stated numerator and denominator. Table totals add up. Rounding is consistent. | Paperpal "Methodology-Results Correlation"; arXiv placeholder class; GRIM-style arithmetic checks (SECONDARY) | Regenerate the numbers from code (one source of truth) and cite the script or commit. |
| D2 | Every figure and table is referenced in the text and every reference has a target. The n in captions matches the text. Figure labels are legible. | Cabanac 2021; Paperpal "Image Review" | Fix the text or the figure. |
| D3 | Claim to evidence: each `we show\|demonstrate\|establish\|prove` sentence points to a result, figure or table | Paperpal methodology-results; Wikipedia superficial analyses | Weaken the verb to what was measured, or add the evidence. |
| D4 | Specific limitations: a limitations section exists and names concrete failure modes with numbers or scope. Flag generic-only items (`generalizability`, `dataset bias`, `future work could explore`, `may vary`, `further research is needed`). | Wikipedia outline-like conclusions (verified); arXiv 2601.11578 (SECONDARY); editor screen NOT FOUND | Name what the method or tool cannot do (a reference build it does not support, a step it does not perform, an inference it does not make) and what that means for a reader. |
| D5 | Statistical boilerplate: `p ?< ?0\.05 was considered (statistically )?significant` with no test named; many associations with no multiple-testing correction; unexplained data-year or cohort subsets | Suchak 2025 (SECONDARY); Spick 2025 | Name the test, the correction and the subset rationale, or remove the inference. |
| D6 | Template public-dataset pattern: title or abstract tokens from Spick Table 3 (`NHANES`, `cross-sectional`, `association`, `Mendelian randomization`, `causal`, `bidirectional`, `FinnGen`, `UK Biobank`, `real world`, `pharmacovigilance`, `FAERS`, `burden`, `global`, `GBD`, `CHARLS`, `MIMIC`, `TriNetX`) together with a single-exposure single-outcome design | Spick 2025; Frontiers policy | If it applies, add external or own validation. For a software or tool paper it often does not apply; then report it only. |
| D7 | Availability: abstract has an "Availability and implementation" statement with a stable source URL, an archived version DOI (Zenodo or Software Heritage) for the *submitted* version, test data archived, an OSI licence named, and a data availability statement present | Bioinformatics author guidelines | Add the missing parts and mint a Zenodo DOI for the submission tag, once the code is final (an end-stage item, not a blocker for a draft). |
| D8 | AI-use statement fields and locations required by the current target, after exemptions | Applicable journal rule; cached Bioinformatics example above | Check presence and consistency separately from truth of process claims. Do not demand STM categories or a supplement unless required, or prescribe an author rewrite as a guaranteed cure for a drafting-policy conflict. Follow the author's decision. |
| D9 | Consistent author metadata; ORCID and contact details where actually required; no AI tool as an author | Journal author instructions; vendor identity checks | Correct actual inconsistencies. A vendor risk signal does not justify requiring every author to obtain ORCID or an institutional email. |
| D10 | Scope and length: article type and word count fit the journal (Bioinformatics Original Paper ~5,000 words or 7 pages; Application Note ~2,600 words or 4 pages) | Wiley "Journal scope checker"; Bioinformatics guidelines | Cut or move material to the supplement. |
| D11 | Overlap and duplicate submission: text overlap with the authors' own preprint, docs and earlier papers is declared; there is no parallel submission | STM duplicate submission; Elsevier simultaneous submissions; iThenticate | Declare any preprint of the work in the cover letter, as the venue asks. Cite the authors' own earlier text where it is reused. |
| D12 | Images: any AI-generated illustration is disclosed (STM category 5). No generated image stands in for data (category 9). Screenshots are real. | STM; Proofig; Imagetwin | Disclose, or replace with a real figure. |

---

## 7. Gaps (NOT FOUND or unverified)

- No official arXiv policy page for the May 2026 one-year ban (only the CS chair's X post and news).
- No published numeric threshold for per-manuscript self-citation, or for "how many irrelevant
  references" triggers SN's manual review.
- No current downloadable PPS tortured-phrase fingerprint list (only the 2021 Table 1 seed).
- No study measuring abstract-versus-body number mismatch, or generic limitations, as an LLM marker
  or as an editor screen.
- STM Hub's full list of checks (the "15 checks") and its duplicate-submission internals.
- Papermill Alarm thresholds and accuracy (no peer-reviewed method paper found).
- Independent Turnitin false-positive measurements for scientific prose.
- A tool named "CiteCheck".
- FAERS- or GBD-specific publisher rejection policies (only Frontiers' NHANES and MR policy found).
- The *Science Editor* (CSE) Integrity Hub article could not be read. Its URL redirected to an
  unrelated gambling domain.

## 8. Source list (fetched unless marked)

- Kobak et al. 2025: https://arxiv.org/html/2406.07016v5 ; https://github.com/berenslab/llm-excess-vocab
- Liang et al. 2025 NHB: https://nlp.stanford.edu/~manning/papers/Liang_et_al-2025-Nature_Human_Behaviour.pdf
- Liang et al. 2023 Patterns: https://arxiv.org/abs/2304.02819
- Juzek & Ward 2025: https://arxiv.org/abs/2412.11385
- Reinhart et al. 2025: https://arxiv.org/html/2410.16107v1
- Russell et al. 2025: https://aclanthology.org/2025.acl-long.267/
- Vinkers et al. 2015: Europe PMC PMC4677695 (https://www.ebi.ac.uk/europepmc/webservices/rest/PMC4677695/fullTextXML)
- Millar et al. 2022: Europe PMC PMC9412227
- Wikipedia Signs of AI writing (rev 1380310647): https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing
- Cabanac et al. 2021: https://arxiv.org/abs/2107.06751 ; PPS: https://dbrech.irit.fr/pls/apex/f?p=9999:1 ; WCRI abstract: https://arxiv.org/pdf/2210.04895
- Academ-AI: https://arxiv.org/abs/2411.15218 ; https://arxiv.org/html/2411.15218v1
- Retraction Watch ChatGPT list: https://retractionwatch.com/papers-and-peer-reviews-with-evidence-of-chatgpt-writing/
- Topaz et al. via RW: https://retractionwatch.com/2026/05/07/one-in-277-pubmed-indexed-papers-in-2026-shows-fabricated-references-says-analysis/
- Grounded AI / Nature: https://groundedai.company/research/hallucinated-citations-nature-2026/
- GPTZero NeurIPS: https://gptzero.me/news/neurips/ ; arXiv ban: https://gptzero.me/news/arxiv-ban/ ; https://library.smu.edu.sg/topics-insights/arxiv-tightens-policy-hallucinated-references-what-researchers-should-know-about
- Phantom References: https://arxiv.org/abs/2607.00738 ; RefChecker: https://github.com/markrussinovich/refchecker ; Badalova & Mayr: https://arxiv.org/abs/2607.22693
- Crossref RW: https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/
- Feet of Clay (THE): https://www.timeshighereducation.com/node/741371
- Springer Nature: https://group.springernature.com/gp/group/media/press-releases/new-research-integrity-ai-tool/27769148 ; https://www.springernature.com/gp/advancing-discovery/springboard/blog/blogposts-trust-integrity/harnessing-technology-to-strengthen-research-integrity/27802690
- Wiley: https://newsroom.wiley.com/press-releases/press-release-details/2024/Wiley-announces-pilot-of-new-AI-powered-Papermill-Detection-service/default.aspx ; https://newsroom.wiley.com/press-releases/press-release-details/2026/Wiley-Bolsters-Research-Integrity-Efforts-with-Imagetwins-Enhanced-Image-Screening/default.aspx
- Elsevier: https://elsevier.shorthandstories.com/investing-in-integrity-how-publishers-are-safeguarding-science/index.html
- STM: http://stm-assoc.org/stm-integrity-hub/ ; https://stm-assoc.org/stm-integrity-hub-incorporates-clear-skies-papermill-alarm-screening-tool/ ; https://www.uksg.org/newsletter/stm-integrity-hub-expands-collaborative-efforts/ ; https://stm-assoc.org/new-stm-draft-report-classifying-ai-use-in-manuscript-preparation/
- Clear Skies: https://www.silverchair.com/news/clear-skies-and-silverchair-partner-to-integrate-papermill-detection-and-journal-integrity-metrics-into-peer-review-workflows/ ; https://clear-skies.co.uk/
- Frontiers: https://www.frontiersin.org/news/2025/07/07/frontiers-broadens-ai-driven-integrity-checks-with-integration-of-cactus ; https://www.frontiersin.org/news/2025/09/15/cutting-through-fast-churn-science-how-frontiers-raised-the-bar
- Signals: https://research-signals.com/ ; https://www.uksg.org/newsletter/uksg-enews-574/signals-launches-free-research-integrity-submissions-evaluation-platform-to-help-restore-trust-in-research/
- Cactus/Paperpal: https://cactusglobal.com/media-center/detecting-fraudulent-submissions-using-paperpal-preflight-for-editorial-desk/ ; https://paperpal.com/blog/news-updates/reference-checker-verify-citations-before-you-submit
- Proofig: https://www.proofig.com/ai-generated-image-detection/
- Turnitin: https://www.turnitin.co.uk/blog/ai-writing-detection-update-from-turnitins-chief-product-officer
- Jabarian & Imas: https://www.nber.org/papers/w34223 ; Epoch AI: https://epoch.ai/data-insights/ai-detectors-false-negatives
- Spick et al. preprint: https://www.medrxiv.org/content/medrxiv/early/2025/07/09/2025.07.07.25331008.full.pdf
- Bioinformatics: https://academic.oup.com/bioinformatics/pages/author-guidelines ; ISCB: https://www.iscb.org/about-iscb/policy-statements-bylaws-and-legal-documents/acceptable-use-of-large-language-models-policy ; OUP: https://academic.oup.com/pages/authoring/journals/preparing_your_manuscript/ethics ; ICMJE: https://www.icmje.org/recommendations/browse/artificial-intelligence/ai-use-by-authors.html
- Secondary only: COPE https://publicationethics.org/guidance/cope-position/authorship-and-ai-tools ; Weber-Wulff https://link.springer.com/article/10.1007/s40979-023-00146-z ; Pangram report https://arxiv.org/pdf/2402.14873 ; Suchak https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12061153/ ; Clarivate via RW https://retractionwatch.com/2025/06/18/clarivate-impact-factor-suppression-list-2025-self-citation-stacking/ ; Strzelecki DOI 10.1002/leap.1650 ; Walters & Wilder DOI 10.1038/s41598-023-41032-5 ; Morressier https://blog.alpsp.org/2024/08/spotlight-on-morressiers-integrity.html
