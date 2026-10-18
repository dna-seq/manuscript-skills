# Claims and the evidence they need

Use this in the calibration step: a claim is calibrated when its wording asks no more of the reader than the
paper's evidence supplies. This file says which evidence each kind of claim needs and names the common
inference gaps. How strong a sentence is, its rung, is measured on the shared ladders in
[`claim-ladders.md`](../../manuscript-prose-edit/references/claim-ladders.md), which `guard.py`,
`manuscript-peer-review` and `manuscript-reviewer-response` use too:

- **causal force**: compatibility, association, prediction, contribution, effect, causation;
- **evidential force**: possibility, suggestion, indication, demonstration, proof;
- plus the markers for novelty and generality, scope (in this cohort, in mice), null results and evidence
  status (self-reported, predicted, measured).

Use those words in your working notes and the shared record, so that a later edit or a referee response can be
checked against the same scale. In the report, describe the gap in plain words and let the ladder names follow
in parentheses: "In the Results, 'higher numeracy caused better comprehension' states a cause, but the study
measured a correlation in one sample (causation stated, association shown)".

## Claim types

| Claim type | Typical wording | Evidence it needs | Typical gap |
|---|---|---|---|
| **Causal** | causes, drives, leads to, improves, reduces (effect or causation rung) | A manipulation of the cause with a comparison: randomisation, a controlled experiment, or a causal design (Mendelian randomisation, a natural experiment) whose assumptions are stated and probed. For a dose or a time course, the gradient. | An observational association written as an effect. |
| **Association** | is associated with, correlates with, is enriched in | The relation in a defined sample, with its size and uncertainty, adjusted for the confounders the design makes plausible, corrected for the number of tests; for genetic associations, replication. | Size or uncertainty missing; confounding by design (age, ancestry, batch, indication); many tests, one reported. |
| **Prediction or diagnostic performance** | predicts, classifies, detects, distinguishes, AUROC of | Performance on data the model never saw (held out, preferably external), discrimination **and** calibration with intervals, the reference standard, the setting and prevalence, a baseline, and no leakage between training and test. | Internal or resubstitution performance; leakage (the same person, family or batch on both sides); a case-control spectrum quoted as if it were the clinic. |
| **Improvement over existing methods** | outperforms, faster than, more accurate than, state of the art | The same data, metric and preprocessing for every method; current versions of competitors run with reasonable settings (not only the authors' tuned method); variation across runs or datasets; the size of the difference with its uncertainty. | Outdated or weakened baselines; a single dataset; a difference inside run-to-run noise. |
| **Generalisation** | robust, generalisable, across, in humans, universally | Tests in independent data that differ in the way the claim names: ancestry, platform, site, species, time. | One cohort, one ancestry, one sequencing platform, one simulated regime. |
| **Mechanism** | acts through, mediates, by (a pathway), underlies | A perturbation of the proposed intermediate that changes the outcome (knockdown with rescue, an inhibitor, a mediation analysis with its assumptions), beyond co-occurrence. | Co-expression, enrichment or co-localisation read as a pathway at work. |
| **Priority** | first, only, novel, unprecedented, no existing tool | The rule and its outcomes are in [claim-support.md](../../manuscript-reference-check/references/claim-support.md#priority-and-absence-claims): a reproducible, dated search the paper reports. | No search reported; "first" for a combination of known parts. |
| **Absence of an effect** | no effect, does not affect, is safe, independent of | An interval that excludes effects that would matter, or an equivalence or non-inferiority test with a stated margin; enough power to see the effect if it existed. | A non-significant p read as "no difference". |
| **Practical or clinical value** | clinically useful, actionable, improves care, reduces cost | Outcomes that matter to the people affected, a net-benefit or decision analysis, or a study of use in the setting named. | Accuracy or a surrogate offered as benefit. |

A claim can belong to two types ("outperforms in all cohorts" is an improvement and a generalisation); it
needs both kinds of evidence.

## Inference gaps

Each gap is a step from what the data show to a stronger statement. Report the step by name, with the two
rungs or the two scopes it joins.

| Gap | Looks like | What closes it, or the calibrated wording |
|---|---|---|
| **Association to causation** | "Higher numeracy caused better comprehension (r = .45)" | A design that manipulates the cause; otherwise "was associated with". |
| **Prediction to causation** | "Predictors of relapse" turning into "drivers of relapse" | Keep "predictor"; causal language needs a causal design. |
| **Surrogate to outcome** | Comprehension scores leading to "will reduce anxiety"; a biomarker change leading to "improves survival" | Measure the outcome, or name the surrogate as what was measured. |
| **Subgroup to overall benefit** | A benefit in one subgroup or secondary outcome presented as the result | The pre-specified primary analysis; label subgroups as exploratory. |
| **Single study to "consistently shown"** | "Has been consistently shown" citing one study | Cite the independent replications, or "one study found". |
| **Model system to human** | Cell-line or mouse results written as human biology | "In mice" kept beside the claim; human data for a human claim. |
| **Population to individual** | Group-level risk or a polygenic score read as an individual's fate | State it as a population-level estimate with its spread. |
| **Internal to external validity** | Cross-validated performance presented as clinic performance | An external test set from another site, period or population. |
| **Non-significance to no effect** | "Did not differ (p = .21)" becoming "has no effect" | The interval, an equivalence test, or "no difference was detected". |
| **Statistical to practical significance** | A tiny p presented as an important effect | The effect size in units a reader can judge. |
| **Relative to absolute** | "Halves the risk" when it falls from 2 in 10,000 to 1 in 10,000 | Give the absolute risks or the number needed to treat. |
| **Sample to population** | Volunteers, one hospital or one ancestry written as "patients" or "people" | Keep the scope qualifier ("in this cohort of volunteers"). |

## Ceilings by design

The highest causal rung a design supports without further argument. Higher rungs need the evidence in the
claim-type table.

| Design | Highest causal rung | Note |
|---|---|---|
| Case report, case series, qualitative study | compatibility | Describes; does not estimate. |
| Cross-sectional, case-control, cohort | association | Prediction once validated on held-out data. |
| Prediction model with external validation | prediction | Not a reason the outcome happens. |
| Mendelian randomisation, natural experiment | contribution or effect | Only with the instrument assumptions stated and probed; say so in the sentence. |
| Randomised trial, controlled experiment | effect | For the tested intervention, population, dose and duration. |
| Experiment perturbing the intermediate, with rescue | causation, mechanism | In the system tested. |
| Simulation or benchmark | effect, within the simulated or benchmarked conditions | Scope to the conditions. |

On the evidential ladder, one exploratory analysis supports suggestion or indication; demonstration needs a
pre-specified analysis or an independent replication; proof belongs to mathematics; "established" and
"consistently" need several independent studies, cited.

## How to use it (calibration step)

1. **List the load-bearing claims**: the title, the Abstract's conclusion, each "we show" or "we
   demonstrate", the conclusions and any cover-letter claim. Reuse `claims:` in `manuscript-record.yaml`
   when it exists; when creating the record, add them there with their evidence location.
2. **Type and place each claim**: its claim type, its causal and evidential rungs, and its scope.
3. **Find the evidence in the paper**: design, data, analysis and the location of the result. Name the
   highest rung that evidence supports.
4. **Report only a gap**: the claim quoted with its section, what it asks of the reader against what the
   evidence shows (the gap's name and both rungs in parentheses), and the smallest remedy. Offer narrower
   wording (a claim correction the authors decide) next to the evidence that would support the original
   claim, with a rough sense of its cost. Where the claim needs work the authors cannot
   afford, a venue that accepts the narrower claim is also a remedy (`manuscript-journal-select`).
5. **Leave calibrated claims alone.** Do not lower a claim the evidence supports, ask for evidence beyond
   the claim, or treat a stated non-claim ("no clinical utility is claimed") as missing evidence.

Example finding, as the authors would read it: *In the Results, "Higher numeracy caused better comprehension,
r(62) = .45" (line 53) states that numeracy is a cause, but the evidence is a correlation in one sample of 64
people, which cannot separate cause from association (association to causation). Either write "was associated
with", or test it with a design that varies numeracy support, which this study does not have; the authors
decide which.* Claim gaps belong to the report's "Fix now" group; rewording a claim to match its evidence is
"Then the writing" once the authors have chosen the narrower claim.

## Sources

The claim-type to evidence pairing follows the idea of the `rigor-reviewer` skill in
Orchestra-Research/AI-Research-SKILLs (MIT: a causal claim needs an isolating comparison, an improvement
needs a baseline, a generalisation needs varied conditions). The named gaps follow the inference-gap rules
of `argdown_lint.py` in drpwchen/paper-review-and-digest (MIT: association to causation, surrogate to hard
endpoint, subgroup to benefit, single study to consistency). The tables and wording here are written for this
plugin; the ladders are those of `claim-ladders.md`.
