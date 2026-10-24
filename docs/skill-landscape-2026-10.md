# Manuscript skill landscape, October 2026

A survey of GitHub repositories that ship agent skills (Claude Code, Codex and similar) for academic
writing, reviewer simulation, revision and pre-submission checks. The question it answers: what should
manuscript-skills add to become a general manuscript-improvement toolkit, what it already covers, and
what to leave alone.

On 2026-10-22, the shared LLM-pattern catalogue, style profiler and optional reflection procedure moved
from prose-edit into `manuscript-deslop`. Prose-edit retains the editing contract, claim guard and
optional detectors; the dated survey below describes the earlier layout.

## Status (2026-10-16)

Most of this survey has been implemented:
- Three new skills: `manuscript-peer-review`, `manuscript-reviewer-response` and
  `manuscript-reporting-check`.
- Claim support (`support.py`) and stronger identity checks in `manuscript-reference-check`.
- Number, table and submission-package checks (`number_check.py`, `hygiene.py`) in
  `manuscript-integrity-check`.
- Claim-strength ladders and a revision inventory in `manuscript-prose-edit`'s guard.
- The optional shared record with study-design keys, and behavioural evaluations under `evals/`.

Every skill was then run on two real manuscripts and graded by independent evaluators; the defects found
were fixed. Still open from this list:
- An automated eval runner.
- Calibration of the reviewer panel against open life-science reviews.
- Field-corpus base rates for the style catalogue.
- Grant proposals.

Three proposals below were later dropped: an authorisation intake before reviewing
someone else's paper, asking the author to confirm the simulated reviewer panel, and Boom5426's rule
that a declined referee request may not cite time or money. The user decides what the skills are applied
to, so the invited-referee mode starts without questions; the panel is stated in the answer, where the
author can change it; and an in-silico-only budget is recorded as the real reason, beside what was done
instead.

## Where each skill stands against popular skill repos (2026-10-24)

A recheck of all seventeen skills against the most-starred skill repos for academic writing, as they stood
on 2026-10-24: [blader/humanizer](https://github.com/blader/humanizer) (60,114 stars),
[K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) (54,343),
[Imbad0202/academic-research-skills](https://github.com/Imbad0202/academic-research-skills) (ARS, 53,675),
[wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)
(ARIS, 17,990), [Galaxy-Dawn/claude-scholar](https://github.com/Galaxy-Dawn/claude-scholar) (5,888), and
[Boom5426/Nature-Paper-Skills](https://github.com/Boom5426/Nature-Paper-Skills) (626), the closest
life-science match. [Leey21/awesome-ai-research-writing](https://github.com/Leey21/awesome-ai-research-writing)
(35,213) holds only prompts and was left out.

**Method.** A shallow clone of each repo; their SKILL.md descriptions were read, and their Markdown, YAML and
JSON files searched for each capability below. None of their skills was run. A match means their files
describe the capability; whether it works was not tested, and a capability that lives only in their code
may be missed.

**No counterpart found in the six repos**

| Skill | What it does | Closest thing found |
|---|---|---|
| `manuscript-policy-fit` | Which clinical, ethics and privacy requirements apply, including authors' voluntarily public genomes and bioRxiv/medRxiv referral loops. | None. K-Dense mentions medRxiv only in its literature-search skills. |
| `manuscript-revision-marks`, `manuscript-mark-people` | Which passages an AI or agent wrote that no person has reviewed since, from marks in the source. | None. |
| `manuscript-story` | Simulated readers say where they would stop reading; the repair keeps the authors' direction and every caveat. | Boom5426 `manuscript-optimizer` restructures toward a claim chain for a broad reader, without simulated readers. |
| `manuscript-dashboard` | One offline file, and a Word version with tracked changes, of what a run found, changed and left open, and how much of a human review of the same draft it caught. | ARS keeps auditable quality-assurance files, not a dashboard. |
| `manuscript-journal-select` | Preprint and journal ladders ordered by the authors' priorities, AI-policy burden among them, from dated and sourced venue entries. | Boom5426 `nature-portfolio-playbook` (Nature, Nature Methods and Nature Biotechnology only); K-Dense `venue-templates` (formatting, not choice). |

**Ahead in a crowded area**

| Skill | Popular alternatives | What ours adds |
|---|---|---|
| `manuscript-prose-edit` | humanizer; claude-scholar `nature-polishing` | `guard.py` aligns the sentences of the two versions and fails a stronger claim, a lost qualifier or a changed number or citation. The alternatives edit without such a check; ARIS forbids new numbers and citations in an edit, a narrower rule. |
| `manuscript-integrity-check` | ARIS `integrity-forensics` and `paper-claim-audit`; Boom5426 `submission-audit` | `hygiene.py` checks the upload files for hidden text and prompts aimed at AI reviewers, LaTeX comments, secrets, EXIF data and anonymity; we found this in none of the six. Numbers are also checked against the project's code and run logs. ARIS checks numbers against raw result files, for ML papers. |
| `manuscript-figures` | Boom5426 `nature-figure` and `figure-style`; ARIS `paper-figure`; claude-scholar `publication-chart-skill` | These mostly make figures. Ours reviews the authors' existing figures at print size, in greyscale and as colour-blind readers see them, against caption, text and code, and gives a keep, change or supplement verdict without touching the files. |
| `manuscript-reporting-check` | K-Dense; Boom5426 `data-availability`; claude-scholar `nature-data` | `check_availability.py` resolves accessions and packages (GEO, EGA, dbGaP, Zenodo, Bioconductor, bioconda, PyPI, CRAN, RRID, Software Heritage), and the guidelines include DOME, STREGA, TRIPOD+AI and MDAR. The omics standards are no longer ours alone: K-Dense now names MINSEQE, MIAME and MIxS. |

**On par; the value is in the combination**

| Skill | Popular alternatives | Note |
|---|---|---|
| `manuscript-peer-review` | ARS `academic-paper-reviewer` (five seats, a calibration mode); K-Dense `peer-review`; Boom5426 `paper-reviewer` | ARS is more elaborate but CC BY-NC. Ours reviews for a real journal whose pages were read, with a defender, script-checked quotes and no scores. |
| `manuscript-reviewer-response` | Boom5426 `rebuttal-response`; ARIS `rebuttal`; ARS rebuttal-audit mode; claude-scholar `review-response` | `check_response.py` checks that each reply's location, quoted text and numbers exist in the revised manuscript, round after round. Boom5426 comes close. |
| `manuscript-reference-check` | ARIS `citation-audit`; Boom5426 `claim-source-verification`; K-Dense `citation-management` | Comparable: identity, retractions, preprints since published, and support quoted from the source. |
| `manuscript-deslop` | humanizer; claude-scholar `writing-anti-ai` | The same Wikipedia source. Ours adds exceptions for scientific writing and the counted before/after check. |
| `manuscript-journal-adapt` | K-Dense `venue-templates`; ARS disclosure mode | K-Dense ships LaTeX templates and we do not; `policy_watch.py` notices changed AI policies. |
| `manuscript-other-models` | ARIS (a Codex reviewer by default, with Gemini and Claude variants); ARS (Codex for citation checks) | Not new. Ours runs in either direction through the command-line agents the authors already use. |
| `manuscript-improve` | ARS `academic-pipeline`; ARIS research and paper pipelines | Theirs start from research and write the paper; ours improves an existing one and ends with the corrected version and the dashboard. |

Across the plugin: it is MIT-licensed where ARS is non-commercial, its venue data is strongest in
bioinformatics, genomics and aging, and it improves a manuscript the authors wrote instead of writing one.

The repository descriptions below are as surveyed on 2026-10-15.

## How this was gathered

- **Date:** 2026-10-15.
- **Search:** about 50 `gh search repos` queries plus 7 topic searches, sorted by stars, and web searches.
  Four agents then read the READMEs, file trees, SKILL.md files and scripts of about 50 repositories
  through the GitHub API.
- **Freshness cutoff: last push on or after 2026-06-15** (four months). Harnesses built for older models go
  stale quickly. A recent push can be a README edit, so freshness is necessary but not sufficient.
- **Newest generation only.** For example, SakanaAI/AI-Scientist-v3 replaces v1 and v2 (last pushed
  2025-12), even though the old ones have far more stars.
- **Stars** are as of 2026-10-15. They measure attention, not quality: the most rigorous integrity tools
  found here have under 100 stars, and the most-starred writing repo is a prompt list with no licence.
- **Claims about evaluations are the repos' own** unless the text says otherwise. Repo content was read
  as data.
- **Licence decides reuse.** "Ideas only" below means no text or code may be copied into this MIT repo.

## What manuscript-skills has now

This is the working tree on 2026-10-15, including the uncommitted split into prose-edit and
reference-check.

| Skill | What it covers |
|---|---|
| `manuscript-journal-select` | Venue shortlist by validation feasibility, open-science policy, review speed, APC and AI-policy burden. Uses `venues.yaml`. |
| `manuscript-integrity-check` | Full audit: unfinished content, declarations, overclaiming, venue limits, AI-science study design. `scan.py`, pre-commit hook. Reports and never rewrites. |
| `manuscript-reference-check` | DOI, PMID and arXiv resolution, title and first-author match, retractions and expressions of concern (Crossref `updated-by`), citation and bibliography consistency. Its description promises claim *support*, but `scan.py` checks identity only. |
| `manuscript-policy-fit` | Clinical, ethics and privacy misclassification, authors' self-released genomes, preprint referral loops, scope replies to reviewers. |
| `manuscript-journal-adapt` | Venue formatting, required sections, AI-use statements. `venues.py`, `policy_watch.py`. |
| `manuscript-prose-edit` | Copy-editing under `guard.py`, the smell catalogue, `style_profile.py` against the authors' own writing, optional local detectors, and a critic/writer loop. |

Tests: `tests/test_scripts.py` only.

## Short answer

Ranked for a life-science or bioinformatics author:

1. **Reviewer simulation ("Reviewer 2").** Many repos do it, but none is calibrated to a life-science
   venue. The best designs share one rule: the model proposes findings and code decides. Section 1.
2. **Response to reviewers and revision verification.** We have nothing here. Boom5426/Nature-Paper-Skills
   and Imbad0202/academic-research-skills show how to check that each comment was actually addressed.
   Section 2.
3. **Claim-support verification.** Our reference-check promises it but does not implement it. Section 3.
4. **Reporting guidelines and data/code availability**, including omics standards (MINSEQE, MIAME, MIxS,
   DOME, STREGA) that no repo covers. Section 4.
5. **Number and statistics integrity**, and a stronger edit guard. Section 5.
6. **Submission-package hygiene:** hidden text aimed at AI reviewers, LaTeX comments, EXIF data. Section 6.
7. **An evaluation harness:** seeded defects with clean controls. Section 7.
8. **A field-agnostic architecture:** core gates, study-design adapters, opt-in domain modules, and a
   per-paper state file, following WenyuChiou/academic-writing-skills. Section 8.

Two tools to wrap rather than rebuild:
- [amos689/paper-preflight](https://github.com/amos689/paper-preflight): deterministic reference checks
  with a measured false-positive rate.
- [pachterlab/paperpush](https://github.com/pachterlab/paperpush): dated venue requirements for
  Bioinformatics, NAR, Genome Biology and others, plus a hidden-text scanner.

## Capability map: have, extend, new

| Capability | manuscript-skills now | Best outside example | Verdict |
|---|---|---|---|
| Reference identity (DOI, PMID, arXiv; title and first author) | reference-check `scan.py` | paper-preflight | **Have.** Extend through preflight. |
| Retractions and expressions of concern | Crossref `updated-by` | co-researcher (found OpenAlex missed 3 of 40 retractions that Crossref caught) | **Have.** Add a second source and record `retraction_checked` / `retraction_source`. |
| Preprint since published, withdrawn arXiv, invented venue, dead link, software or dataset existence, all authors | no | paper-preflight REF015/018/019/020/021; absent-author `ref_verify.py` | **New** (wrap preflight). |
| Claim support (does the cited source say it?) | promised, not implemented | Boom5426 `claim-source-verification`, co-researcher quote gate, preflight `support` | **New.** |
| Chatbot leftovers, placeholders, missing declarations | integrity-check | K-Dense `lint_manuscript.py` | **Have.** |
| Overclaiming | integrity-check (prompt and vocabulary) | drpwchen `argdown_lint`, Orchestra claim-type table, Yila-AI claim ladder | **Extend.** |
| Edit guard (numbers, citations, hedges, negation) | prose-edit `guard.py` token counts | dsh-plugin-writing-guard clause-level ladders, academic-deai `revision_gate`, ARIS new-number rule | **Extend.** |
| De-slop pattern catalogue | prose-edit `smell-patterns.yaml` | Boom5426 `ai_tells.py` (rates per 10k words against 28 Nature-family methods papers), absent-author human p90 bands | **Have.** Calibrate on a field corpus. |
| Style against the authors' own writing | `style_profile.py` | dgilford per-author calibration | **Have.** |
| Critic/writer loop | prose-edit reflection mode | SNL-UCSB rule-ID ledger, ARIS fresh-context reviewer | **Have.** Tighten. |
| AI-text detectors | optional, local, calibrated on the authors' own text | most repos either refuse them or tune text to beat them | **Have.** Our stance is the defensible one. |
| Venue database and policy watch | `venues.yaml`, `policy_watch.py` | paperpush `manuscript_requirements.json` (source URLs, retrieval dates) | **Have.** Cross-check against paperpush. |
| Journal selection | journal-select | Awesome-Journal-Skills (unsourced cards) | **Have.** Ours is stronger. |
| Ethics, privacy, self-released genomes, referral loops | policy-fit | nothing comparable found | **Unique to us.** |
| AI-use statement | journal-adapt | absent-author (only from confirmed facts), AlterLab disclosure skill (ICMJE, NIH, ERC, EU AI Act Art. 50) | **Have.** Borrow the confirmed-facts rule. |
| Reviewer simulation | none | see section 1 | **New.** |
| Response letter and revision verification | none (policy-fit drafts scope replies only) | Boom5426, ARS, TobiasLee | **New.** |
| Reporting-guideline audit | notes in `screening-signals.md` | medsci (49 guidelines), aipoch | **New.** Omics standards are open. |
| Data, code and software availability | notes only | Boom5426 `data-availability`, preflight REF019 | **New.** |
| Numbers and statistics | none beyond the edit guard | absent-author `number_ledger.py`, Anti-Autoresearch GRIM/GRIMMER/statcheck, Boom5426 `stats-reporting-audit`, paperdelta | **New.** |
| Figures and source data | none | ai4s forensics, dgilford `figure-review`, Boom5426 `check_figure_refs.py` | **New**, lower priority. |
| Submission-package hygiene | none | paperpush `hidden_text.py` / `sensitive.py`, absent-author `pdf_hidden_text.py` | **New.** |
| Behavioural evals | one script test file | Boom5426 hidden rubrics, ARS seeded defects, GeoGeekLab matched controls, medsci challenge fixtures, preflight false-positive museum | **New.** |
| Field-agnostic structure | partly; venue data is life-science | WenyuChiou/academic-writing-skills | **New.** |
| Grant proposals | none | academic-humanizer (NIH, NSF) | Lower priority. Nobody covers ERC or DFG. |

## Repos worth reading, by area

All pushed on or after 2026-06-15. Stars as of 2026-10-15.

### Reviewer simulation and revision

| Repo | Stars | Last push | Licence | Why look | Verdict |
|---|---|---|---|---|---|
| [Imbad0202/academic-research-skills](https://github.com/Imbad0202/academic-research-skills) | 52,168 | 2026-10-13 | **CC BY-NC 4.0** | The most complete design: a 5-seat panel, criteria committed before reading, re-review before seeing the response letter, a deterministic decision checker, seeded-defect evals. | **Ideas only** (non-commercial). |
| [Imbad0202/academic-research-skills-codex](https://github.com/Imbad0202/academic-research-skills-codex) | 12,931 | 2026-10-03 | CC BY-NC 4.0 | The same suite packaged for Codex. | Ideas only. |
| [Boom5426/Nature-Paper-Skills](https://github.com/Boom5426/Nature-Paper-Skills) | 585 | 2026-10-13 | MIT + Apache-2.0 parts (NOTICE) | Life-science methods papers. Rebuttal chain with `check_coverage.py`, claim-source verification, stats audit, hidden-rubric evals. | **Closest match. Borrow freely** with NOTICE. |
| [Spark-To-Paper-Skills/paperjury](https://github.com/Spark-To-Paper-Skills/paperjury) | 1,222 | 2026-08-14 | MIT | Quote-verified complaints; a trial with defence, jurors and judge; three verdicts. Evaluated in arXiv 2606.16322 (12 CS papers). | Borrow verdict routing and the quote check. CS only, and costly (6.8M tokens per paper). |
| [pedrohcgs/claude-code-my-workflow](https://github.com/pedrohcgs/claude-code-my-workflow) | 1,661 | 2026-09-27 | MIT (referee text adapted from clo-author) | `--variance N` gives a decision distribution; `adjudicate-review`; `validate-findings.py --check-quotes`; "what would change my mind". | Borrow. Avoid its finding quotas and uncalibrated 0-100 bands. |
| [wanshuiyin/Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) (ARIS) | 17,521 | 2026-10-07 | MIT | Cross-family review gate that fails closed, a fresh reviewer each round, an edit whitelist (no new numbers or citations), rebuttal gates. | Borrow mechanisms. Avoid the edit-until-score loop. |
| [wanshuiyin/Anti-Autoresearch](https://github.com/wanshuiyin/Anti-Autoresearch) | 163 | 2026-10-06 | MIT | "The LLM reviewer never renders the final verdict": a deterministic adjudicator, GRIM/GRIMMER/statcheck, corrupt-a-fixture CI. | Borrow. |
| [poldrack/ai-peer-review](https://github.com/poldrack/ai-peer-review) | 156 | 2026-07-05 | MIT | The only real multi-family panel. Its `scientific-only.json` profile: raise a concern only if resolving it could change a claim's validity; "consensus is not evidence". | Borrow the profile rules. Its model list is stale. |
| [amirkiarafiei/open-scholar-peer](https://github.com/amirkiarafiei/open-scholar-peer) | 47 | 2026-10-04 | MIT | ScholarPeer (Google, arXiv 2601.22638). Literature-grounded review; "not verified" without an identifier; typed tool errors; ends with "What this review did not have". | Borrow the grounding rules. |
| [GeoGeekLab/nature-reviewer-skills](https://github.com/GeoGeekLab/nature-reviewer-skills) | 48 | 2026-09-23 | MIT | Nature-style referee roles; a benchmark of matched flawed and repaired excerpts, so flag-everything reviewers lose. | Borrow the benchmark design. No biomedical referee. |
| [xf686/Meet-Reviewer-2](https://github.com/xf686/Meet-Reviewer-2) | 46 | 2026-06-23 | MIT | Champion, Methodological Skeptic and Novelty Hawk; a "misread-risk" triage class; a fairness firewall against illegitimate critiques. | Borrow the triage classes. ML conferences only. |
| [Yule-Cai/aaai-review-simulator-prompt](https://github.com/Yule-Cai/aaai-review-simulator-prompt) | 241 | 2026-07-02 | MIT | "Why not higher / why not lower" per rating; never name missing papers without a search. | Two small rules. |
| [TobiasLee/Rebuttal-Skill](https://github.com/TobiasLee/Rebuttal-Skill) | 479 | 2026-08-20 | **none** | The best rebuttal structure: decide rebuttal vs resubmission first, intent-diagnosis cards, concern statuses, results validated before claims. | **Ideas only.** |
| [AutoLab-SAI-SJTU/Paper2Rebuttal](https://github.com/AutoLab-SAI-SJTU/Paper2Rebuttal) | 560 | 2026-08-04 | **no LICENSE file** | ACL 2026. Atomic issue extraction with verbatim quotes and paper hooks; `[TBD]` for missing numbers. | Ideas only. Avoid its "not recognisable as AI-written" instruction and its dropping of ethics comments. |
| [Galaxy-Dawn/claude-scholar](https://github.com/Galaxy-Dawn/claude-scholar) | 5,797 | 2026-09-23 | MIT | Rebuttal "evidence anchor rule" (a location, an artifact, or `unresolved`); keep / weaken / revise / remove. | Minor. |
| [SakanaAI/AI-Scientist-v3](https://github.com/SakanaAI/AI-Scientist-v3) | 8 | 2026-10-15 | Apache-2.0 | `agsci review`: five o4-mini reviews on the NeurIPS form, averaged by an Area Chair step; no evidence anchors. | Reference only. Avoid averaged scores shown as venue scores. |

### Claims, references, numbers and guidelines

| Repo | Stars | Last push | Licence | Why look | Verdict |
|---|---|---|---|---|---|
| [amos689/paper-preflight](https://github.com/amos689/paper-preflight) | 62 | 2026-10-15 | MIT | "No LLM in the verdicts". Crossref, PubMed, OpenAlex, DataCite, GitHub, PyPI, CRAN, Hugging Face. 0.9 false positives per 100 references; 142 of 151 hallucinated references flagged. Ships an MCP server. | **Wrap** from reference-check. |
| [amos689/paperdelta](https://github.com/amos689/paperdelta) | 64 | 2026-10-07 | MIT | Binds manuscript numbers to results files; lists stale numbers after a rerun. | Optional, for benchmark papers. |
| [Aperivue/medsci-skills](https://github.com/Aperivue/medsci-skills) | 340 | 2026-10-15 | MIT (some checklists CC BY-NC) | 49 reporting guidelines (incl. PGS-RS, STROBE-MR, TRIPOD+AI, ARRIVE 2.0), licence verified per checklist, `source_sha256` staleness check, challenge fixtures per script. | Borrow the pattern. No omics guidelines. |
| [aipoch/medical-research-skills](https://github.com/aipoch/medical-research-skills) | 1,957 | 2026-09-17 | MIT | Reporting-guideline checker with item states "missing / weakly reported / not applicable / unclear due to missing material"; a second-hand-citation rule. | Borrow the item states. Prompt-only. |
| [pachterlab/paperpush](https://github.com/pachterlab/paperpush) | 206 | 2026-10-02 | BSD-2-Clause | Venue requirements JSON with schema, `source_urls` and `retrieved` dates (Bioinformatics checked 2026-09-10); `hidden_text.py`, `sensitive.py`, `anonymity.py`. | **Reuse the data and scanners** with attribution. Skip its portal automation. |
| [THUROI0787/absent-author](https://github.com/THUROI0787/absent-author) | 119 | 2026-10-07 | MIT | `number_ledger.py`, `ref_verify.py` (every author, incl. the last), `pdf_hidden_text.py`; a "claim ceiling"; an Understand / Defend / Sign author checkpoint. Shares our anti-evasion stance. | Borrow. Its calibration is ML-only. |
| [Yila-AI/awesome-research-skills](https://github.com/Yila-AI/awesome-research-skills) | 136 | 2026-09-04 | Apache-2.0 | Source of the claim-strength ladder ARS credits (formerly `sci-ssci-skills`). | Copyable with NOTICE. |
| [xmutfyh/dsh-plugin-writing-guard](https://github.com/xmutfyh/dsh-plugin-writing-guard) | 46 | 2026-10-05 | MIT | Clause-level causal and evidential ladders, null-result, scope ("in this cohort") and evidence-status locks; 394 tests. | Borrow for `guard.py`. TypeScript, built for another host. |
| [heise3/academic-deai](https://github.com/heise3/academic-deai) | 156 | 2026-10-08 | MIT | `revision_gate.py` ("deliberately not an AI detector"), `content_lock.py`, a PICO-style claim-source ledger. | Borrow. |
| [poemswe/co-researcher](https://github.com/poemswe/co-researcher) | 131 | 2026-10-15 | MIT | Retraction ladder (OpenAlex, Europe PMC, Crossref); a quote gate where every number in a claim must occur in its quote; "unchecked, never clean". | Borrow. |
| [drpwchen/paper-review-and-digest](https://github.com/drpwchen/paper-review-and-digest) | 42 | 2026-08-22 | MIT | `argdown_lint.py` flags association→causal, surrogate→hard endpoint, subgroup→benefit; GRADE recomputed by script. | Borrow the lint for our overclaiming pass. |
| [ai4s-research/ai4s-skills](https://github.com/ai4s-research/ai4s-skills) | 237 | 2026-07-28 | MIT | Image and number forensics (perceptual hash, ORB, channel swaps, decimal and unit consistency, GRIM) with positive and negative controls. | Borrow for an authors' figure self-check. |
| [dgilford/ai-science-toolkit](https://github.com/dgilford/ai-science-toolkit) | 63 | 2026-10-01 | MIT | `figure-review` (pass / flag / by-design? / can't assess); `spot-ai` calibrated per author, "flags only". | Borrow figure-review. |
| [AlterLab-IEU/AlterLab-Academic-Skills](https://github.com/AlterLab-IEU/AlterLab-Academic-Skills) | 74 | 2026-10-14 | MIT; 4 core skills CC BY-NC | Citation taxonomy; "each flag must survive two independent re-checks"; trigger and near-miss eval schema. "Evaluated" means schema-gated plus LLM-judged. | Borrow conventions only. |
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 50,068 | 2026-10-12 | MIT | `peer-review` helps a human referee: an authorization intake gate, author and editor channels kept apart, offline lints. | Keep author and editor channels apart. Its intake gate was not adopted (the user decides what a skill is applied to). Avoid its footer that adds K-Dense's paper to users' references. |
| [Orchestra-Research/AI-Research-SKILLs](https://github.com/Orchestra-Research/AI-Research-SKILLs) | 13,587 | 2026-10-11 | MIT | `rigor-reviewer`: claim type → required evidence (a causal claim needs an isolating ablation, an improvement needs a baseline); decision by fixed rule. | Small borrow. Avoid its unsourced statistics. |

### Prose, venue and architecture

| Repo | Stars | Last push | Licence | Why look | Verdict |
|---|---|---|---|---|---|
| [WenyuChiou/academic-writing-skills](https://github.com/WenyuChiou/academic-writing-skills) | 106 | 2026-10-15 | MIT | The model for "universal": nine core gates, study-design adapters, opt-in domain modules, an overlay precedence order, and a per-paper `manuscript_state.json`. | **Borrow the architecture.** Not its phrase-presence tests or personal overlays. |
| [WenyuChiou/ai-research-skills](https://github.com/WenyuChiou/ai-research-skills) | 384 | 2026-10-15 | MIT | A catalog layer: `verified_on`, `verification_tier`, `human_gates` per skill; harness strategy "portable SKILL.md first". | Borrow the catalog fields if we split into many skills. |
| [labarba/sciwrite](https://github.com/labarba/sciwrite) | 856 | 2026-08-03 | CC BY 4.0 | Sainani's course as audits: the "Banana Rule" (Methods terms reused verbatim in Results and legends), N in the Abstract against Table 1, statistics cited only through reviews. | Borrow with attribution. Skip its dash advice. |
| [SNL-UCSB/paper-writing-skill](https://github.com/SNL-UCSB/paper-writing-skill) | 240 | 2026-07-31 | MIT | "Report the grep counts, not 'audited'"; a red-team that never sees the author's self-assessment; a rule-ID ledger; stop after two iterations without progress. | Borrow for our critic loop. Skip its passive-voice and "significant" bans. |
| [blader/humanizer](https://github.com/blader/humanizer) | 57,176 | 2026-09-28 | MIT | Its patterns are merged into prose-edit's catalogue; the skills no longer load the installed skill. | Have. |
| [AIScientists-Dev/academic-humanizer](https://github.com/AIScientists-Dev/academic-humanizer) | 2,143 | 2026-07-03 | MIT | A "preserve these" list (evidence-tied hedges, passive voice in Methods, "we"); an NIH/NSF grant mode. | Borrow the preserve list. **Its examples add numbers absent from the input.** |
| [HeartWise-AI/ai-writing-skills](https://github.com/HeartWise-AI/ai-writing-skills) | 26 | 2026-09-17 | **no LICENSE file** | Medical AI (TRIPOD+AI). The negative-space test: delete a sentence that would be equally true of a paper whose authors never considered the issue. | Ideas only. |
| [Leey21/awesome-ai-research-writing](https://github.com/Leey21/awesome-ai-research-writing) | 34,846 | 2026-08-19 | **none** | Prompts in Chinese. A no-change verdict when text is already natural; back-translation as a meaning check. | Ideas only. |
| [Master-cai/Research-Paper-Writing-Skills](https://github.com/Master-cai/Research-Paper-Writing-Skills) | 7,504 | 2026-06-23 | MIT packaging, unlicensed source notes | A claim / evidence / status map; reverse outlining. | Ideas only. |
| [brycewang-stanford/Awesome-Journal-Skills](https://github.com/brycewang-stanford/Awesome-Journal-Skills) | 1,258 | 2026-09-27 | MIT | 4,166 venue cards, mostly economics. Sources are search instructions, not dated URLs; no card for Bioinformatics. | Borrow the output template (fit, top risk, items to re-check, re-route). Do not trust the cards. |
| [kael-odin/awesome-academic-research-skills](https://github.com/kael-odin/awesome-academic-research-skills) | 154 | 2026-10-15 | MIT | Daily star ranking with JSON, CSV and RSS. Misses most integrity tools. | A feed for spotting new repos, not a quality index. |

## 1. Reviewer simulation: a proposed design

Pieced together from the repos above. No repo has a validated score calibration, so the skill should
never emit venue scores (ARS prints `NOT_CALIBRATED`; that is the right default).

- **Panel.** Propose 3 to 5 seats from the paper's study design, and let the author confirm them
  (paperjury, ARS):
  - claims and novelty;
  - evidence, controls and statistics;
  - reproducibility, data and software;
  - a champion as calibrator, and a skeptic as Reviewer 2 (Meet-Reviewer-2);
  - for software papers, a seat that installs and runs the tool. No repo has one.
- **Isolation.** Control what each seat can see; prompting alone does not do it:
  - each seat is a fresh subagent with the manuscript only, no other seat's report, and no
    self-assessment from the author (SNL-UCSB, ARS);
  - "A reviewer is only as blind as its working directory" (pedrohcgs).
- **Criteria before reading.** Each seat writes down what would count as a major problem before it sees
  the paper (ARS Phase 1).
- **Finding contract.** A model-written finding is only a proposal until it passes these:
  - a verbatim quote, checked by a script (paperjury, pedrohcgs `--check-quotes`);
  - an absence finding names where it looked;
  - "what would change my mind" (pedrohcgs);
  - poldrack's claim-consequence gate;
  - Meet-Reviewer-2's fairness firewall (no "not novel" without a citation, no "run experiment X" for
    its own sake);
  - no quotas, but a coverage receipt when a list is empty (ARS).
- **External claims.** A claim of "missing prior work" carries an identifier or is marked
  `not verified` (open-scholar-peer). Reuse reference-check rather than re-resolving.
- **Adjudication before the report.** Before anything reaches the report:
  - a defence pass looks for "addressed elsewhere in the paper";
  - each finding becomes CONFIRMED / REFUTED / DOWNGRADED ("Agreement is not confirmation", pedrohcgs);
  - each confirmed finding is routed to fixable in text, author required (needs new data, never patched)
    or dropped with a reason (paperjury).
- **Triage.** Substance, misread risk (sound work whose wording will trigger a reviewer), or polish
  (Meet-Reviewer-2). Rank by impact and cost.
- **Output:**
  - how often each concern recurs across seats;
  - a decision distribution only if asked (pedrohcgs `--variance`);
  - a closing "What this review did not have" (open-scholar-peer).
- **Model diversity** is optional, recorded, and never claimed as independence (ARS, ARIS). The manuscript
  leaves the machine only with the author's consent.
- **Robustness check.** Review a meaning-equivalent rewrite. If the verdict changes, the simulation is
  unreliable. This turns game-the-llm-reviewer's research into a test.
- **Evaluation:**
  - seeded-defect manuscripts with a clean control (ARS, Anti-Autoresearch);
  - matched flawed and repaired pairs (GeoGeekLab);
  - later, open life-science reviews: eLife assessments, Nature transparent peer-review files, and PeerJ,
    F1000 and BMC open reports. Beware label leaks: ARS voided an ICLR calibration because camera-ready
    PDFs reveal acceptance.

## 2. Response to reviewers and revision verification

The two strongest designs are Boom5426 (copyable) and ARS (ideas only).

- **Parse:**
  - split comments wherever a different action would satisfy the referee;
  - keep the referee's numbering ("Never renumber, never reorder, never regroup", Boom5426);
  - extract each commitment with the evidence type it needs (new table, Methods paragraph, citation;
    ARS).
- **Triage.** The author decides: will address (with exact targets), won't address, or not on point.
  Never infer a missing decision (ARS). Each comment ends in exactly one outcome (Boom5426).
- **Reply rules (Boom5426):**
  - state the fact, not the stance;
  - when disagreeing, lead with a result that would have come out differently if the referee were right;
  - for work that cannot be done, give the refusal and a design or scope reason in one sentence, not time
    or money;
  - "A proposed experiment is not a completed experiment."
- **Coverage checks.** Boom5426's `check_coverage.py` blocks on:
  - a quote that is not verbatim, or out of order;
  - a missing or orphan reply;
  - a reply with no location;
  - blanket replies ("revised accordingly");
  - a promise that never landed in the manuscript.

  Its caveat: "A clean run is not a good letter."
- **Verification (ARS):**
  - fix what "fully addressed" means for each must-fix item before reading the revision;
  - judge the revision before reading the response letter;
  - use five states: FULLY / PARTIALLY / NOT ADDRESSED / MADE WORSE / CANNOT VERIFY. The last three
    block acceptance;
  - the letter can change a verdict only by pointing to text in the manuscript;
  - classify new issues as regressions (can affect the decision) or previously missed (cannot escalate).
- **Our own piece.** Run `guard.py` on the old manuscript against the revised one, so a reply cannot
  silently change numbers, citations or claim strength. ARS measured silent claim strengthening in 2 of 8
  pressured revisions.
- **Gap.** Every rebuttal tool targets CS conference windows. Nobody handles a journal response letter
  across rounds that maps answers to revised line numbers and tracked changes.

## 3. Claim support

- **Four outcomes:** CONFIRMED / PARTIAL / REJECTED / BLOCKED, from a fresh-context skeptic whose default
  is reject. "No verbatim supporting sentence, no confirmation." Boom5426 calibrated this on 139 sources,
  rejecting 55.
- **A mechanical gate.** The quote must occur in the source, and every number in the claim must occur in
  the quote (co-researcher).
- **A flag must survive two independent re-checks** (AlterLab).
- **Do not rebuild the passage search.** Call paper-preflight's `support` / `preflight_cited_passages`.
- **Record the unchecked.** When the full text is unreachable, report BLOCKED or unchecked, never clean.

## 4. Reporting guidelines and availability

- **Item-level audit.** Use states PRESENT / PARTIAL / MISSING / N/A, adding aipoch's "unclear due to
  missing material".
- **Pick guidelines by study design.** STROBE, STROBE-MR, STREGA, TRIPOD+AI, ARRIVE, PRISMA, CONSORT,
  PGS-RS.
- **Licence each checklist individually.** Follow medsci's `LICENSES.md`: resolve each checklist's
  licence through Crossref and PMC, and keep CC BY-NC checklists out of the MIT payload.
- **Omics and ML-in-biology standards are covered by nobody:** MINSEQE, MIAME, MIxS, DOME, STREGA.
- **Availability checks:**
  - accessions resolve (GEO, SRA, ENA, dbGaP), as do Zenodo DOIs, RRIDs, GitHub tags and package
    versions (Bioconductor and bioconda: nobody);
  - flag "available upon request";
  - Bioinformatics' rule that software stays available for two years.

## 5. Numbers, statistics and the edit guard

- **Number ledger.** One quantity stated with different values; "x% of n" must be a whole count; N in the
  Abstract matches Table 1 (absent-author, sciwrite, medsci `check_cohort_arithmetic.py`).
- **Deterministic GRIM, GRIMMER and statcheck** (Anti-Autoresearch). Not model arithmetic: ARS has the
  model recompute and admits "Receipts prove auditability, not arithmetic truth".
- **Statistics reporting audit** (Boom5426, Apache-2.0):
  - n as the independent unit;
  - biological vs technical replicates;
  - s.d. vs confidence interval;
  - every declared test actually used;
  - `AUTHOR_INPUT_NEEDED` instead of invented values.
- **Inference-gap lint on the authors' own headline claims** (drpwchen `argdown_lint`): association to
  causal, surrogate to hard endpoint, subgroup to benefit, single study to "consistently shown".
- **Upgrade `guard.py`:**
  - clause-level causal and evidential ladders;
  - scope and evidence-status locks: "in this cohort" disappearing; "participants reported improvement"
    becoming "participants improved" (dsh-plugin-writing-guard);
  - the ARIS rule that a new number or citation must exist in the replaced lines;
  - a claim ceiling (absent-author): "edits may never raise certainty, causality, novelty, generality, or
    scope".

## 6. Submission-package hygiene

- **Hidden or injected text:** white text, fonts under 2 pt, Word `w:vanish`. Prompts aimed at AI
  reviewers are now desk-reject grounds.
- **Source leaks:** LaTeX `%` comments, EXIF GPS data, secrets and editable Google Docs links in the
  sources that arXiv and bioRxiv publish.
- **Anonymity** for double-blind venues.
- **What to reuse:** paperpush (BSD-2) has `hidden_text.py`, `sensitive.py` and `anonymity.py` with
  tests. absent-author has `pdf_hidden_text.py`.

## 7. Evaluation harness

We have one script test file. What the better repos do:

- **Seeded-defect manuscripts with a clean control.** A reviewer that flags the clean one fails (ARS,
  Anti-Autoresearch in CI).
- **Matched flawed and repaired pairs**, so flag-everything reviewers lose specificity (GeoGeekLab).
- **Behavioural cases in a fresh session, with hidden rubrics.** The runner never shows the model the
  rubric. Any numerical drift, invented evidence or false completion claim fails the case. Before and after
  runs per change (Boom5426).
- **Per-script challenge fixtures** with expected outputs (medsci). **A museum of past false positives**
  as a regression set, plus a measured false-positive rate per 100 references (paper-preflight).
- **Trigger and near-miss cases** for skill routing (AlterLab, WenyuChiou).
- **A field corpus for the smell catalogue.** Base rates per 10k words from open-access Bioinformatics,
  NAR and PLOS Computational Biology papers written before 2022 (the method of Boom5426 and
  absent-author; their numbers do not transfer).

## 8. Architecture for a universal toolkit (WenyuChiou)

The structure is worth adopting; its contents are not:

- **A field-agnostic core of gates:** authority, contract, alignment, method-evidence, claim scope,
  cross-artifact sync, version, release, prose.
- **Adapters chosen by study design, not discipline:** quantitative, experimental, qualitative,
  computational, AI/LLM, evidence synthesis, software or data paper.
- **Opt-in domain modules.** Each needs explicit trigger and exclusion cues and at least one boundary eval.
  Load the smallest sufficient set and record why. A genomics/omics module would be ours, and nobody has
  one.
- **An overlay taxonomy with fixed precedence:** safety and ethics, verified evidence, user instructions,
  venue, design, domain, reviewer preference. Never present a venue or reviewer preference as a universal
  rule.
- **A per-paper state file kept beside the manuscript, not in the plugin.** It holds the target venue with
  a checked date, locked claims and non-claims, terminology, facts with sources, and open issues. This
  would let integrity-check, prose-edit and the reviewer share one record.
- **What not to copy:**
  - tests that only assert a phrase exists in SKILL.md;
  - hard-coded personal projects and a named professor's style overlay inside the "universal" skill;
  - its citation support ("read enough of the source"), which ours already exceeds.

## Not useful, or to avoid

- **Detector evasion:**
  - [Moonlit-Pages/AIGC-Detector-Rewriter-Skill](https://github.com/Moonlit-Pages/AIGC-Detector-Rewriter-Skill)
    retests in a closed loop against Turnitin and CNKI until the AI score drops.
  - [AhmadHassan-BTed/Turnitout-Humanizer](https://github.com/AhmadHassan-BTed/Turnitout-Humanizer)
    describes itself as bypassing Turnitin, iThenticate and GPTZero (read from its description only).
  - Pattern 34 of [matsuikentaro1/humanizer_academic](https://github.com/matsuikentaro1/humanizer_academic)
    was tuned on local detectors.
- **Spin as a feature.** The core rules of
  [Adkid-Zephyr/anti-defensive-writing-Skill](https://github.com/Adkid-Zephyr/anti-defensive-writing-Skill)
  ("never volunteer weakness", "switch to an evaluation dimension that better reflects the value") are
  outcome switching in biomedical work. Boom5426's evidence-preserving version is the one to learn from.
- **Gaming automated reviewers.** The strategies in game-the-llm-reviewer optimise text for an automated
  evaluator, the same family as detector evasion. Use it only as a robustness test.
- **Loops that edit until a model is satisfied.** ARIS with human checkpoints off by default, and any
  quota-driven critique ("at least one major concern", "3-5 objections").
- **Uncalibrated scores presented as venue scores:** Sakana v3's averaged o4-mini scores, pedrohcgs'
  0-100 bands, "AAAI readiness XX/100".
- **Paper generators** that conflict with our stance:
  [federicodeponte/opendraft](https://github.com/federicodeponte/opendraft) (keep only its citation status
  vocabulary), the ai4s paper-writer, and
  [OpenDFM/Xcientist](https://github.com/OpenDFM/Xcientist) (ML experiment lineage, no manuscript
  checking).
- **Self-citation injection:** a K-Dense skill footer tells the agent to add K-Dense's paper to the user's
  references.
- **Fabrication by example:** academic-humanizer's "after" texts add numbers absent from the "before".
- **Unsourced statistics presented as fact:** Orchestra's "~40% error rate" for AI citations.
- **Licence traps:**
  - no licence: Leey21, TobiasLee, bahayonghang/academic-writing-skills;
  - no LICENSE file: HeartWise, Paper2Rebuttal;
  - non-commercial: ARS and its codex sibling, and AlterLab's four core skills;
  - unclear chain: Master-cai.

## Gaps nobody fills (where manuscript-skills can lead)

- **A reviewer calibrated to life-science venues:** Bioinformatics, NAR, Genome Biology, PLOS
  Computational Biology, eLife, Nature Methods, GigaScience. The only calibration data anywhere comes from
  ICLR, and from Nature chemistry and earth-science papers.
- **Omics reporting standards** (MINSEQE, MIAME, MIxS, DOME, STREGA) and **Bioconductor, bioconda and
  Zenodo checks**.
- **Genomics-specific review:**
  - genome build and coordinate consistency;
  - rsID, HGVS and HGNC validity;
  - GWAS thresholds and multiple testing;
  - ancestry and population stratification;
  - sample overlap;
  - train/test leakage in variant-effect benchmarks;
  - batch effects.
- **A reviewer for software and methods papers** who installs and runs the tool and compares it with
  existing ones. just-dna-lite's papers will meet exactly this reviewer.
- **Clinical overclaiming and genomic-data ethics** in review: causal language from associations, consent,
  controlled access, GDPR. policy-fit already covers the author side.
- **Journal response letters across rounds**, mapped to revised line numbers.
- **Grant proposals for ERC, DFG and Horizon Europe.**

## Dropped by the cutoff

Last push before 2026-06-15. Revisit if any of them moves again.

| Repo | Last push | Note |
|---|---|---|
| [SakanaAI/AI-Scientist](https://github.com/SakanaAI/AI-Scientist), [-v2](https://github.com/SakanaAI/AI-Scientist-v2) | 2025-12-19 | Superseded by v3. |
| [lishix520/academic-paper-skills](https://github.com/lishix520/academic-paper-skills) | 2026-01-04 | 7-dimension reviewer scoring. |
| [chenlu-hung/scientific-writing](https://github.com/chenlu-hung/scientific-writing) | 2026-02-22 | 3 reviewer subagents plus an area editor. |
| [stephenturner/skill-deslop](https://github.com/stephenturner/skill-deslop) | 2026-03-18 | |
| [isitcredible/reviewer2](https://github.com/isitcredible/reviewer2) | 2026-04-21 | |
| [ResearAI/DeepReviewer-v2](https://github.com/ResearAI/DeepReviewer-v2) | 2026-04-28 | |
| [Zhitao-He/RebuttalAgent](https://github.com/Zhitao-He/RebuttalAgent) | 2026-04-28 | ICLR 2026, theory of mind in rebuttals. |
| [AlexWortega/ai-peer-review-skill](https://github.com/AlexWortega/ai-peer-review-skill) | 2026-05-08 | Port of poldrack/ai-peer-review. |
| [Ahren09/AgentReview](https://github.com/Ahren09/AgentReview) | 2026-05-10 | EMNLP 2024; the "~37% of decisions vary with reviewer disposition" result. |
| [andrehuang/academic-writing-agents](https://github.com/andrehuang/academic-writing-agents) | 2026-05-11 | |
| [WantongC/journal-adapt-writing-skill](https://github.com/WantongC/journal-adapt-writing-skill) | 2026-05-15 | Style profile from target-journal papers; worth revisiting for `style_profile.py`. |
| [google-research/paper-orchestra](https://github.com/google-research/paper-orchestra) | 2026-05-17 | |
| [xiongqi123123/awesome-rebuttal](https://github.com/xiongqi123123/awesome-rebuttal) | 2026-06-13 | |

## Appendix A: other relevant repos, not read in depth

Pushed on or after 2026-06-15, found by the same searches, relevant by name and description. Stars as of
2026-10-15.

| Repo | Stars | Last push | Description |
|---|---|---|---|
| [MLNLP-World/Paper-Writing-Tips](https://github.com/MLNLP-World/Paper-Writing-Tips) | 4,676 | 2026-09-26 | MLNLP社区用来帮助大家避免论文投稿小错误的整理仓库。 Paper Writing Tips |
| [openags/paper-search-mcp](https://github.com/openags/paper-search-mcp) | 2,836 | 2026-10-02 | MCP, CLI, Skills for searching and downloading academic papers from multiple sources like arXiv, PubMed, bi... |
| [HughYau/AcademicForge](https://github.com/HughYau/AcademicForge) | 2,593 | 2026-08-30 | One Forge, All Skills: A curated skill collection for academic writing and research.  点开即用，按需配置的一站式学术研究skil... |
| [delibae/claude-prism](https://github.com/delibae/claude-prism) | 1,819 | 2026-08-28 | An offline-first scientific writing workspace powered by Claude. LaTeX + Python + 100+ scientific skills al... |
| [PaperDebugger/paperdebugger](https://github.com/PaperDebugger/paperdebugger) | 1,546 | 2026-07-03 | A Plugin-Based Multi-Agent System for In-Editor Academic Writing, Review, and Editing |
| [Kiterlin/anti-defensive-writing](https://github.com/Kiterlin/anti-defensive-writing) | 1,069 | 2026-10-01 | Codex skill for removing defensive writing and strengthening prose. |
| [writing-resources/awesome-scientific-writing](https://github.com/writing-resources/awesome-scientific-writing) | 1,011 | 2026-09-15 | :keyboard: A curated list of awesome tools, demos and resources to go beyond LaTeX |
| [LeonChaoX/qinyan-academic-skills](https://github.com/LeonChaoX/qinyan-academic-skills) | 955 | 2026-07-20 | A curated, multilingual library of 182 installable AI agent skills for end-to-end academic research - spannin... |
| [luwill/research-skills](https://github.com/luwill/research-skills) | 870 | 2026-10-10 | Some commonly used research experiences and processes are encapsulated into Agent skills. |
| [Ar9av/PaperOrchestra](https://github.com/Ar9av/PaperOrchestra) | 682 | 2026-10-11 | An automated AI research-paper writer based off Google's PaperOrchestra paper's implementation through a sk... |
| [hanlulong/econ-writing-skill](https://github.com/hanlulong/econ-writing-skill) | 663 | 2026-07-20 | Agent Skill that transforms AI assistants into expert economics paper writers. Synthesizes 50+ guides by Co... |
| [NeuroDong/Ai-Review](https://github.com/NeuroDong/Ai-Review) | 630 | 2026-08-25 | Large model-assisted paper review |
| [worldbench/awesome-ai-auto-research](https://github.com/worldbench/awesome-ai-auto-research) | 547 | 2026-10-15 | 🔥 A Survey on AI Auto-Research |
| [harshaneel/humanize](https://github.com/harshaneel/humanize) | 541 | 2026-09-22 | Best static AI text humanizer. Two research-grounded LLM-agnostic skills that make AI writing sound human a... |
| [appautomaton/latex-arxiv-SKILL](https://github.com/appautomaton/latex-arxiv-SKILL) | 465 | 2026-09-13 | A highly customizable agentic harness for arXiv-ready ML/AI review papers (and beyond). It drives agentic A... |
| [modelscope/Awesome-Vibe-Research](https://github.com/modelscope/Awesome-Vibe-Research) | 456 | 2026-10-15 | An open, collaboratively-built repository for AI-assisted scientific research - collecting and curating age... |
| [tizzy916/humanities-writing-companion](https://github.com/tizzy916/humanities-writing-companion) | 446 | 2026-09-22 | End-to-end humanities writing assistant - an Agent Skill (open SKILL.md format). 11 modes from Socratic res... |
| [fcakyon/phd-skills](https://github.com/fcakyon/phd-skills) | 422 | 2026-10-11 | PhD Research Skills for Claude Code: paper reproduction, experiment design, paper review, result comparison... |
| [jamditis/claude-skills-journalism](https://github.com/jamditis/claude-skills-journalism) | 422 | 2026-10-04 | Claude Code skills for journalism, media, and academia - verification, FOIA, data journalism, academic writ... |
| [Adkid-Zephyr/oral-paper-skill](https://github.com/Adkid-Zephyr/oral-paper-skill) | 408 | 2026-09-17 | 向顶会优秀论文学科研｜Oral Paper Skill - 从 883 篇 Oral 论文摘要中“蒸馏”共通做法，用于论文对照改进与学习复盘 · Skill + prompt pack (CN/EN). Learn... |
| [MLNLP-World/Paper-Rebuttal-Tips](https://github.com/MLNLP-World/Paper-Rebuttal-Tips) | 355 | 2026-10-06 | MLNLP社区用来帮助大家论文Rebuttal的整理仓库。 |
| [IMNMV/ClaudeR](https://github.com/IMNMV/ClaudeR) | 352 | 2026-09-30 | Connect RStudio to Claude Code, Codex, Gemini, and other LLM agents via MCP. Multi-agent orchestration, aut... |
| [Haojae/scipilot-writing-skill](https://github.com/Haojae/scipilot-writing-skill) | 230 | 2026-06-15 | SciPilot family: academic writing and polishing co-pilot, with a machine-checked writing-quality evidence c... |
| [brycewang-stanford/Auto-Research-Skills](https://github.com/brycewang-stanford/Auto-Research-Skills) | 207 | 2026-10-12 | A curated hub of autonomous-research skills & agents - from idea to paper, on autopilot. / 自主科研技能与智能体精选库  - ... |
| [gaasher/Agent-Loop-Skills](https://github.com/gaasher/Agent-Loop-Skills) | 175 | 2026-06-30 | Loop until it's better - drop-in agentic loops (autoresearch, scientific writing, data analysis, code/SQL/p... |
| [joshzyj/open-scholar-skill](https://github.com/joshzyj/open-scholar-skill) | 171 | 2026-09-18 | Open scholar skill, a claude code plugin, for academic research |
| [flonat/flonat-research](https://github.com/flonat/flonat-research) | 146 | 2026-09-29 | Shareable Claude Code + Codex infrastructure for PhD researchers - skills, agents, hooks, and rules for aca... |
| [htlin222/meta-pipe](https://github.com/htlin222/meta-pipe) | 143 | 2026-09-23 | Claude Code-powered end-to-end meta-analysis automation: AI-assisted literature review, screening, extracti... |
| [Worigin0314/academic-defensive-writing-auditor](https://github.com/Worigin0314/academic-defensive-writing-auditor) | 121 | 2026-08-30 | An open-source LLM skill for detecting and rewriting defensive academic writing while preserving necessary... |
| [Yrzsh/paper-workbench](https://github.com/Yrzsh/paper-workbench) | 114 | 2026-09-07 | Paper Workbench - 论文写作审查全流程工作台 / End-to-end academic writing & review workbench |
| [TyrealQ/q-skills](https://github.com/TyrealQ/q-skills) | 108 | 2026-09-23 | End-to-end skills for academic writing, data analysis, teaching, and research communication. |
| [Diaugeia/paper-glance-skill](https://github.com/Diaugeia/paper-glance-skill) | 105 | 2026-07-08 | 📄 A Claude skill for comprehensive academic paper analysis - deep reports, mind maps, peer review, and prom... |
| [Skywalkeryeahyeah/Paper-review-agent](https://github.com/Skywalkeryeahyeah/Paper-review-agent) | 92 | 2026-08-29 | AI-powered paper review assistant. |
| [mmTheBest/Research-Architect](https://github.com/mmTheBest/Research-Architect) | 69 | 2026-08-05 | An end-to-end research workflow skill for turning ideas into evidence-backed, citation-supported manuscript... |
| [yujie-jason-zhang/horizon-academic-writing](https://github.com/yujie-jason-zhang/horizon-academic-writing) | 65 | 2026-09-18 | A growing family of agent skills for rigorous, context-aware academic writing, peer review, and scholarly p... |
| [kgraph57/paper-writer-skill](https://github.com/kgraph57/paper-writer-skill) | 60 | 2026-08-12 | Claude Code skill for academic manuscript writing: IMRAD workflows, literature matrices, tables/figures, an... |
| [ShaishavMaisuria/research-paper-lifecycle-skills](https://github.com/ShaishavMaisuria/research-paper-lifecycle-skills) | 53 | 2026-06-27 | 42 AI agent skills for literature review, academic writing, citation verification, conference submission, r... |
| [dalbom/rev2agent](https://github.com/dalbom/rev2agent) | 51 | 2026-10-02 | Reviewer 2 is now your agent. Autonomous research bot that iterates from idea to manuscript. |
| [FanBroWell/AI-paper-reviewer](https://github.com/FanBroWell/AI-paper-reviewer) | 44 | 2026-10-15 | AI Paper Reviewer: LLM-based tool for academic paper review |

## Appendix B: AI-scientist systems (out of scope, for reference)

End-to-end research agents that also write papers. They are not manuscript-improvement tools, but their
review and audit stages are sometimes worth a look. SakanaAI/AI-Scientist-v3 is covered above.

| Repo | Stars | Last push | Description |
|---|---|---|---|
| [EvoScientist/EvoScientist](https://github.com/EvoScientist/EvoScientist) | 4,978 | 2026-10-15 | 🔬 Harness Vibe Research with Self-evolving AI Scientists |
| [OpenNSWM-Lab/FAROS](https://github.com/OpenNSWM-Lab/FAROS) | 3,039 | 2026-10-14 | A blueprint-driven AutoResearch runtime for orchestrating AI research workflows from idea generation and ex... |
| [mims-harvard/ToolUniverse](https://github.com/mims-harvard/ToolUniverse) | 1,738 | 2026-10-15 | Democratizing AI scientists with ToolUniverse |
| [OpenRaiser/NanoResearch](https://github.com/OpenRaiser/NanoResearch) | 1,341 | 2026-10-09 | 🦞+🔬 NanoResearch: The Autonomous AI Research Assistant |
| [Muuuun/luxas](https://github.com/Muuuun/luxas) | 1,169 | 2026-10-12 | An autonomous research colleague - from a question to a compiled manuscript, while you sleep. |
| [ARA-Labs/Agent-Native-Research-Artifact](https://github.com/ARA-Labs/Agent-Native-Research-Artifact) | 696 | 2026-10-11 | Research Artifact Protocol for Rigorous and Trustworthy AI Scientists |
| [QJHWC/PaperForge](https://github.com/QJHWC/PaperForge) | 636 | 2026-10-13 | End-to-end AI-powered academic paper writing system - from idea generation and literature search to experim... |
| [jimmc414/Kosmos](https://github.com/jimmc414/Kosmos) | 595 | 2026-10-09 | Kosmos: An AI Scientist for Autonomous Discovery - An implementation and adaptation to be driven by Claude... |
| [damonwan1/AutoScholarLoop](https://github.com/damonwan1/AutoScholarLoop) | 534 | 2026-09-24 | A multi-agent AUTO Research loop for idea discovery, experiment execution, evidence-grounded paper writing,... |
| [Omni-Scientist/OmniScientist](https://github.com/Omni-Scientist/OmniScientist) | 168 | 2026-09-26 | An Omni-Modal, Omni-Discipline AI Scientist |
| [ChicagoHAI/NeuriCo](https://github.com/ChicagoHAI/NeuriCo) | 156 | 2026-10-15 | AI Scientist by Chicago Human+AI Lab |
