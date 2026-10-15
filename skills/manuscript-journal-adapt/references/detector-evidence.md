# AI-text detectors, disclosure and humanizer tools: the 2026 evidence

Checked 2026-10-15 against primary sources. Several of these figures circulate with errors; the corrections
are noted where they apply.

## Detectors are weak evidence of authorship

- **Style is a confound.** Park H, Jeong G, Kim B. "Style as a Confound: False Positives in AI Detection of
  Non-Native Academic Writing." arXiv:2608.26710 (27 Aug 2026; the authors say it was presented at EMNLP
  2026). 135,389 pairs of human-written manuscripts by non-native authors, before and after professional
  editing (2018 to 2025), run through 13 detectors. False-positive rates ranged from 0.0% to 100.0% by
  detector, and professional editing moved scores in both directions. The same author and content can score
  anywhere.
- **Detectors are easy to defeat.** Gu Y, Li S, Hu X. "MASH: Evading Black-Box AI-Generated Text Detectors
  via Style Humanization." arXiv:2601.08564 (v2 19 Apr 2026; Findings of ACL 2026): 92% average attack
  success. That weakens detectors as evidence; it is not a recipe for a manuscript.
- Earlier work: older detectors flagged non-native writers' TOEFL essays at an average 61% false-positive
  rate (Liang et al. 2023); current commercial detectors flagged none of 495 human passages but missed a
  quarter of style-imitated AI text (Epoch AI, July 2026). See `../../manuscript-integrity-check/references/screening-signals.md` §4.

## What editorial bodies say about detector suspicion

- **COPE case 26-11, "Suspected AI-generated manuscripts"** (2026): editors "should not allow AI-detection
  tools to make the judgement for them", and concerns "must be validated via other means than the
  AI-detection tool". Advice from a few Council members, not formal COPE guidance.
- **COPE topic discussion "When editors suspect AI"** (Forum, March 2026): "editors should not cite
  suspected AI use as a reason for rejection if they cannot prove it". Forum comments, not formal advice.
- **Science**, Thorp HH, "Resisting AI slop", *Science* 391(6780):5 (1 Jan 2026), doi:10.1126/science.aee8267.
  The rules are in Science's AI-usage table: clarity editing, literature searches and gathering references
  need no declaration; drafting and translation are declared in acknowledgments with model and version;
  AI illustrative figures are "Not allowed; exceptions must be discussed with the editor".

## Disclosure does not count against a paper (where the publisher says so)

- **Springer Nature**, "AI use in manuscript preparation" policy page: "Declaration does not negatively
  influence editorial decisions". (The 10 Sep 2026 press release does not contain this sentence; cite the
  policy page.)
- **PLOS**, Ethical Publishing Practice FAQ: "Will AI use disclosures negatively affect my article's review
  or editorial decision?" "No."
- **ACM** Policy on Authorship, updated 14 May 2026: AI help with **writing** no longer needs disclosure; AI
  used in the research must be described in the methods. The FAQ adds that a work must not be "primarily the
  result of the tool's generative capabilities".
- **ICMJE** (January 2026): nondisclosure "may be construed as misconduct in some circumstances".

## How often authors disclose

- Perlis RH et al. *JAMA* 335(8):717–719 (2026), doi:10.1001/jama.2025.25300: 105,538 submissions to 13 JAMA
  Network journals (Aug 2023 to Oct 2025); declared AI use 3.3% overall, rising from 1.71% to 5.97%.
- AlFayyad I, Zeegers MP, Bouter L, Macdonald H, Schroter S. *JAMA* 335(8):719–721 (2026),
  doi:10.1001/jama.2025.25688: 25,114 submissions to 49 BMJ journals (8 Apr to 6 Nov 2024), AI use disclosed
  in 5.7%. (Reported in a *BMJ* news item, Khan Z, *BMJ* 392:s194, which is not the source of the numbers.)
- Observational: neither study shows that disclosure causes rejection.

## A documented example

Sharpton T, Davis EW II, Alexiev A. "A practical risk framework for large language model use in life science
research." *PLoS Comput Biol* 22(9):e1014776 (16 Sep 2026), doi:10.1371/journal.pcbi.1014776. Its own
disclosure states that the prose was written with Claude (web interface and Claude Code), and its prompt
tests name six models with a capture date. Published in a PLOS journal with that disclosure.

## Writing and thinking

Bietti LM, Bangerter A. "Will the widespread use of large language models in scientific writing undermine
scientists' critical thinking?" *PLoS Biol* 24(6):e3003801 (3 Jun 2026), doi:10.1371/journal.pbio.3003801.

## Open-source humanizer tools (GitHub, 15 Oct 2026)

| repository | stars | last push | fit for manuscripts |
|---|---:|---|---|
| blader/humanizer | 57,136 | 2026-09-28 | **Use for spotting patterns.** 26 patterns from Wikipedia's "Signs of AI writing", voice matching from a sample; aims at less generic writing, not detector bypass. Its permission to merge paragraphs and add personality is overridden by `humanize-contract.md`. MIT. |
| harshaneel/humanize | 539 | 2026-09-22 | **Do not use.** Of its nine "levers", perplexity injection and burstiness enforcement (with numeric targets) and "strip RLHF voice" ("targets what detectors actually detect") are detector evasion; it recommends detector-scored best-of-N selection and calls itself an open-source alternative to Undetectable.ai and StealthGPT. Levers 3 to 8 (hedge surgery, structural flattening, specificity, voice, transitions, punctuation) are ordinary editing already covered by the contract. MIT. |
| lynote-ai/humanize-text | 3,436 | 2026-10-13 | **Do not use.** LLM rewriting plus machine-translation stages; the README warns against misrepresenting authorship but advertises a paid API that "raises the detector-bypass rate by ~30%". Multi-stage rewriting risks semantic drift (a lost negation or qualifier). MIT. |
| epoko77-ai/im-not-ai | 5,996 | 2026-10-12 | Korean only. |
| LifelongLazyLearner/qu-ai-wei | 657 | 2026-09-10 | Chinese only. |
| Nanako0129/sepia | 3,182 | 2026-10-15 | General agent writing (StoryScope, arXiv:2604.03136); not for manuscripts. |

Stars measure popularity, not validation.
