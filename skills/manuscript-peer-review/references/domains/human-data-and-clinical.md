# Domain module: human data and clinical claims

Questions a clinical or epidemiological referee asks about what the paper concludes from data about
people. They are reviewer questions, not a checklist. Whether ethics approval, consent or privacy rules
apply is not decided here: hand that to manuscript-policy-fit.

## Load it when

- the design is `observational-human`, `randomized-trial`, `prediction-model`, `case-report`,
  `genetic-association`, `polygenic-score` or `mendelian-randomization` applied to people;
- or the paper reports measurements, outcomes or genomes of identifiable groups of people, or uses
  language about risk, diagnosis, prognosis, treatment, screening, patients or clinical use.

## Do not load it when

- human reference data (a reference genome, public summary statistics, a benchmark variant set) are used
  only to evaluate a method and the paper makes no claim about people or health;
- the only human data are the authors' own voluntarily released genome or records used to demonstrate a
  tool: ask the questions about claims below if the paper makes health claims, and send every
  applicability question to manuscript-policy-fit.

## Causal language from associations

- Does the paper use causal words ("causes", "drives", "leads to", "protective", "effect of", "due to")
  for results from an observational or cross-sectional design? Quote the sentence and the design that
  cannot carry it.
- Are confounding, selection into the cohort, reverse causation and survival bias considered for the
  headline association? Is adjustment described, and are adjusted and unadjusted estimates both shown?
- Mendelian randomisation and other causal designs: are their assumptions stated and probed
  (instrument strength, pleiotropy, sample overlap), or is "causal" taken from the method's name?

## Diagnostic, prognostic and clinical-utility claims

- Is the claim about accuracy (discrimination), calibration, or benefit to patients? They need
  different evidence: an AUROC does not show clinical utility.
- Is performance reported at a clinically meaningful threshold, with sensitivity, specificity and
  predictive values for a stated prevalence, not only an AUROC?
- Was the model validated in data separate from its development, and in the population where it would
  be used? Internal cross-validation alone supports a narrower claim.
- Do phrases like "can be used to diagnose", "clinically actionable" or "ready for the clinic" go beyond
  what was evaluated? The fitting claim is often "may help prioritise for clinical review", stated with
  the population studied.
- Surrogate outcomes presented as hard outcomes; subgroup findings presented as the main result.

## Generalisation

- Who was studied (ancestry, age, sex, setting, recruitment route), and do the conclusions stay within
  that? Missing groups limit the claim, not necessarily the study.
- Are results from one cohort presented as general, without replication?

## Handing over

- Ethics approval, consent (to participate, to publish identifiable data), data access conditions,
  privacy and whether the work counts as clinical research: route `policy`, `hand_to:
  manuscript-policy-fit`. A missing statement is not by itself evidence that approval was needed.
- Reporting guidelines for the design (STROBE, TRIPOD+AI, CONSORT and others): route the gap to
  manuscript-reporting-check; raise it here only when the missing item stops a claim from being
  judged.
