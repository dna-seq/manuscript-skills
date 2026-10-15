# Design review for AI-scientist and AI-assisted papers

> Researched 2026-10-15 for the `manuscript-integrity-check` skill. Policies move monthly: re-fetch the target venue's page before relying on any rule here, and treat SECONDARY items as reports, not rules.

Checked 2026-10-15. Distilled from an AI-generated research brief ("Publishing AI-Scientist-Based Papers in 2026",
15 Oct 2026) after a claim-by-claim fact-check against primary sources (`notes-factcheck.md`). Corrections
are applied below and listed at the end; cite the primary sources, never the brief.

Use this file when the manuscript reports results an AI system produced (hypotheses, analyses, effect sizes,
modules, code that does the science), or when the paper's contribution *is* an AI system. A paper that only
used AI for language editing needs the disclosure in `publisher-policies.md`, not this review.

## Step 1: one primary contribution

Name which one the paper claims, and test the evidence against it:

| contribution | the evidence it needs | typical venues |
|---|---|---|
| **the system** | benchmark with baselines and ablations, several runs, cost | *Bioinformatics*, NAR (web server), Nat Comput Sci, Cell Systems, npj Digit Med, ML venues |
| **the finding** | a validated biological result, judged as if a human had proposed it; AI is method | domain journals (*Aging Cell*, *GeroScience*, *Nature Aging*) |
| **the evaluation** | a rigorous assessment of AI scientists | ML venues, meta-research journals |

A paper that claims all three with evidence for none is the commonest failure. Flag it as **major**.

## Step 2: the checklist

Each item: what to look for in the text, and the fix to suggest when it is missing. Mark an item
`not_assessed` when the manuscript gives no way to tell, never "pass".

| # | item | look for | suggest when missing |
|---|---|---|---|
| D1 | Pre-registered protocol | OSF/AsPredicted link with a date before the first agent run: tasks, data, model versions, run count, metrics, case-selection rule, contamination controls, human-intervention policy | If runs already happened, say so plainly and label the analysis exploratory; pre-register the *next* evaluation |
| D2 | Full denominator | Every run, task and hypothesis with success / failure / abandoned counts; a CONSORT-style flow ("N generated → N triaged → N tested → N confirmed"), in the abstract too | Add the flow diagram and the run table; put failures in the main text |
| D3 | Case-selection rule | "the first k in the pre-registered list" or "k sampled with seed s" | State the rule actually used; if cases were hand-picked, say so and add at least one failure |
| D4 | Run-to-run variance | ≥3 (better ≥5) runs per task, CI or spread | Rerun, or downgrade single-run claims to anecdote |
| D5 | Forking paths | Re-runs, restarts and human interventions counted | Report how many there were; count restarts as analyses |
| D6 | Baselines | human expert with the same time budget; scripted pipeline; single non-agentic LLM call; permuted/shuffled-label control the agent must fail; previous system version | Add at least the scripted pipeline and the permuted control |
| D7 | Ablations | remove literature search, tools, memory, reviewer loop one at a time | Add, or drop claims that a component helps |
| D8 | Independent re-analysis | a human re-derived every headline number; a discrepancy table | Re-derive; report agent vs human values side by side |
| D9 | External validation | second cohort, second lab, wet lab, or prospective target | Add, or narrow the claim to "rediscovery on known data" |
| D10 | Blinded expert rating | AI and human outputs mixed, raters blinded, ≥2 raters, Cohen's/Fleiss' κ or ICC | Add, or remove quality claims that rest on author judgement |
| D11 | Error quantification | statement-level accuracy by category, hallucinated-reference rate, code-failure rate | Sample statements by a stated rule and score them |
| D12 | Cost and effort | API cost, wall-clock time, human hours | Report them; reviewers now expect it (Beel et al. 2025) |
| D13 | Division of labour | stage-wise table (hypothesis, design, analysis, writing) on the Agents4Science scale: A ≥95% human … D ≥95% AI | Add the table |
| D14 | Artifacts (only where the AI system is the research method, not for writing help) | model ids with dates, system prompts, seeds/temperatures, tool lists, full traces, code with DOI, complete run table | Deposit them (Zenodo); Nature encourages transcripts of prompts and responses |
| D15 | Reporting guideline | REFORMS for any ML-based claim; TRIPOD-LLM for biomedical LLM studies; TRIPOD+AI for prediction models; CHART for chatbot health advice; STROBE for observational analyses; ARRIVE 2.0 for animal work | Attach the checklist as a supplement |

## Step 3: contamination (four channels)

| channel | the question | mitigations, strongest first |
|---|---|---|
| training data | did the model already know the published answer? | sealed unpublished target held by a collaborator; post-cutoff data (post-training can extend past the stated cutoff); private cohorts |
| retrieval | could the agent find the answer at run time? | block the target paper and its preprint; keep retrieval logs; report whether a blocked source appeared |
| benchmark | were test items or their source papers in pretraining? | frozen private or post-cutoff test split with canary strings; pre/post-cutoff stratification (absence of a signal is not proof of absence) |
| classic ML leakage | preprocessing on all data, duplicates across splits, non-temporal splits | REFORMS; Kapoor & Narayanan's leakage taxonomy; perturbation tests (rename genes, permute labels, inject a known effect: recall should fail, analysis should succeed) |

Wording follows from this: a known-answer success is **rediscovery** or **recapitulation**. Reserve
**discovery** for prospectively validated or novel findings. Avoid "autonomous", "superhuman", "PhD-level"
unless the evidence is prospective and independent, and say when an evaluation was designed and scored by
the developers themselves.

## Step 4: public-cohort papers (NHANES, UK Biobank, FinnGen, MIMIC, FAERS, GBD, CHARLS, TriNetX, CDC WONDER)

These datasets are named as paper-mill "templates"; PLOS auto-rejects such papers without extra validation and
Frontiers requires independent validation for any paper that is "solely" computational on public data. Check:

1. a pre-specified, theory-grounded question with a time-stamped plan made before any agent saw outcomes;
2. justified cycles, subsets and exclusions; overlapping NHANES cycles handled (a *Sci Rep* paper was retracted
   for combining 2017–2018 with 2017–March 2020);
3. survey weights and design variables used;
4. many exposures or outcomes with FDR control, not a single association;
5. replication in an independent cohort, ideally non-public; a second public "template" dataset is weak, since
   the same spurious signal can appear in two datasets from one source;
6. STROBE (STROBE-MR for Mendelian randomization);
7. an explicit statement of how the paper differs from existing papers on the same pairing.

## Anticipated objections and the pre-emptive answer

| objection | what the manuscript should already contain |
|---|---|
| "The model already knew the answer." | post-cutoff or private data, retrieval blocklist, perturbation test, pre/post-cutoff stratification |
| "You cherry-picked successes." | pre-registered selection rule, full denominator, flow diagram, all runs in the supplement |
| "Is the AI better than a simple pipeline?" | baselines (human, script, single LLM call, permuted) and ablations |
| "Effect sizes are agent-reported." | independent human re-analysis and a discrepancy table |
| "Human role understated." | stage-wise A–D table |
| "Another public-dataset association paper." | pre-specified multi-exposure design, FDR, external cohort, mechanistic link |
| "Not reproducible." | model versions, prompts, seeds, logs, code DOI, variance over ≥3–5 runs |

## Evidence base (verified 2026-10-15; cite these, with the corrections)

- Lu C. et al. "Towards end-to-end automation of AI research." *Nature* 651:914–919 (2026), doi:10.1038/s41586-026-10265-5
  (Sakana's AI Scientist and AI Scientist-v2; the blind workshop-review details in the notes were not re-checked).
- Editorial, "AI scientists are changing research — institutions, funders and publishers must respond." *Nature* 651:853–854 (2026),
  doi:10.1038/d41586-026-00934-w (encourages transcripts of prompts and responses; warns of skew to data-rich fields).
- Gottweis J. et al. "Accelerating scientific discovery with Co-Scientist." *Nature* 655:487–496 (2026), doi:10.1038/s41586-026-10644-y.
- Ghareeb A.E. et al. "A multi-agent system for automating scientific discovery." *Nature* 655:497–505 (2026),
  doi:10.1038/s41586-026-10652-y (Robin; preprint arXiv:2505.13400).
- Mitchener L. et al. "Kosmos: An AI Scientist for Autonomous Discovery." arXiv:2511.02824 (79.4% of 102 statements accurate;
  57.9% for the paper's "synthesis statements").
- Bianchi F. et al. "Exploring the use of AI authors and reviewers at Agents4Science." arXiv:2511.15534; *Nat Biotechnol* 44:11–14 (2026),
  doi:10.1038/s41587-025-02963-8 (315 submissions, 253 complete, 79 to human experts, 48 accepted; ~44% free of hallucinated references;
  accepted papers had more human guidance).
- Beel J., Kan M.-Y., Baumgart M. "Evaluating Sakana's AI Scientist…" *ACM SIGIR Forum* 59(1):1–20 (2025), doi:10.1145/3769733.3769747.
- Miyai A. et al. "Jr. AI Scientist and Its Risk Report…" arXiv:2511.04583.
- Luo Z., Kasirzadeh A., Shah N.B. "The More You Automate, the Less You See: Hidden Pitfalls of AI Scientist Systems." arXiv:2509.08713.
- Russinovich M. et al. "Phantom References: Hallucinated Citations That Survive Peer Review at Top-Tier Conferences." arXiv:2607.00738.
- Wang Z. et al. "FIRE-Bench: Evaluating AI Agents on the Rediscovery of Scientific Insights." arXiv:2602.02905.
- Angulo et al. "Benchmark Contamination: A Taxonomy Organized by Defeated Mitigation." arXiv:2608.29463.
- Ding et al. "Autonomous Research Agents: A Survey of AI Scientists and the Verification Gap." arXiv:2608.05179.
- Suchak T. et al. *PLoS Biol* 23(5):e3003152 (2025), doi:10.1371/journal.pbio.3003152 (341 single-factor NHANES papers);
  Byrne J.A., Stender S. *PLoS Biol* 23(5):e3003167 (2025).
- Maupin D., Suchak T., Barnett A., Spick M. "Dramatic increases in redundant publications in the Generative AI era." *BMC Med* 24:29 (2026),
  doi:10.1186/s12916-025-04569-y (411 redundant publications across 156 exposure–outcome pairs).
- Cunha A. et al. "Setting the standard for high-quality studies using open health datasets." *PLoS Med* 22(12):e1004854 (2025).
- Pruller J., Mockridge J., Vousden G. "Expectations for Mendelian randomization research in PLOS One." *PLoS One* 20(11):e0337199 (2025).
- Kapoor S., Narayanan A. "Leakage and the reproducibility crisis in machine-learning-based science." *Patterns* 4(9):100804 (2023),
  doi:10.1016/j.patter.2023.100804; Kapoor S. et al. "REFORMS…" *Sci Adv* 10(18):eadk3452 (2024).
- Gallifant J. et al. TRIPOD-LLM, *Nat Med* 31:60–69 (2025), doi:10.1038/s41591-024-03425-5; Collins G.S. et al. TRIPOD+AI,
  *BMJ* 385:e078378 (2024), doi:10.1136/bmj-2023-078378; Huo B. et al. CHART, *BMC Med* 23:447 (2025), doi:10.1186/s12916-025-04274-w.
- Templates for blinded benchmarks and validation requirements: Jarchow H. et al. *npj Digit Med* 8:631 (2025), doi:10.1038/s41746-025-01996-2 (blinded LLM benchmark);
  Fuellen G. et al. *Ageing Res Rev* 104:102617 (2025), doi:10.1016/j.arr.2024.102617 (validation requirements).

### Corrections to figures often repeated about these papers

- **Robin's effect size.** The 7.5-fold (agent) vs 1.75-fold (human) gap is in arXiv:2505.13400 **v1 only**. The *Nature* version
  reports 1.89-fold vs 1.75-fold. Cite it as "the preprint's agent analysis overstated the effect several-fold before human
  re-analysis", naming the version, or not at all.
- **Retracted NHANES paper.** doi:10.1038/s41598-025-88794-8 is the *Retraction Note* (*Sci Rep* 15:5032, 2025). The retracted paper is
  Yang Z. et al., *Sci Rep* 14:13801 (2024), doi:10.1038/s41598-024-63965-1.
- **Frontiers' 1,382 NHANES rejections** come from Frontiers' own post (15 Sep 2025), not from the *Science* article
  (O'Grady, 8 Oct 2025, doi:10.1126/science.z6eukgo), which carries the ">5000 papers" quote from Elena Vicario and PLOS's policy.
- **Kapoor & Narayanan**: 294 papers in the *Patterns* version; the current arXiv version says 329.
- **arXiv:2603.03352** is a physics-olympiad paper (Huang Y., Gemini agent on IPhO 2025); check it is the one meant before citing it
  for post-cutoff training.
- **ICMJE Section V** is titled "Use of Artificial Intelligence in Publishing". The Methods sentence on "tool used, version, and prompts
  where applicable" predates January 2026; new in 2026 are the consolidated section and the sentence that nondisclosure "may be
  construed as misconduct in some circumstances".
