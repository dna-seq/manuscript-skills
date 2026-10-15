---
name: manuscript-policy-fit
description: >-
  Review and edit manuscripts to reduce avoidable clinical, regulatory, ethics and privacy
  misclassification and submission burden. Determine which requirements actually apply, use supported
  exemptions, clarify voluntarily self-published author genomes or biomedical data, compare preprint
  servers and journals, and draft scope clarifications or reviewer replies. Use for policy-friction
  reviews, bioRxiv/medRxiv referral loops, human-data wording and proportionate ethics statements.
  Use manuscript-journal-select for a full journal shortlist, manuscript-journal-adapt for AI-use
  statements and venue formatting, and manuscript-prose-edit for general language editing.
---

# Manuscript policy fit

Help authors publish sound work with the least avoidable delay, paperwork and loss of scientific
content. Make the study's actual scope easy to classify; apply only requirements supported by the
facts and the chosen venue. A mention of human genomes, disease annotations or biomedical software
does not by itself establish clinical research, a clinical trial or a regulated medical device.

Support **assess**, **edit**, **compare venues**, and **respond to screening/review** independently.
Use the manuscript, existing author explanations and any rejection correspondence first. A passage
edit does not require a full compliance audit. In the bundled plugin, also follow the shared
[author priorities](../manuscript-integrity-check/references/author-priorities.md).

## Establish the facts that change the answer

Read [applicability.md](references/applicability.md) for the relevant data/study category, especially
the section on an author's **own biomedical or genetic data**. Distinguish:

- software/method evaluation, biological discovery, clinical observational research, and an intervention;
- what the software can do, what this study actually did, and proposed future uses;
- simulated data, public third-party data, controlled-access data, newly collected data, and data about
  the authors themselves; classify mixed datasets separately;
- a deliberate public self-release of an author's genome/records, a new self-experiment, and a study of
  other people. "Author-owned" here means data **about the author**, not merely data their lab generated;
- access, analysis, redistribution, public identification and return of individual results. Permission
  for one does not automatically establish the others.

Use known facts without investigating the author. Ask only unanswered questions that materially change
an edit or requirement, in a short batch; continue independent work. Neither an accession nor an author
list alone establishes consent, anonymity, an exemption or the study design. Do not request genomes,
medical records or private approval documents merely to review wording.

## Determine applicability before adding requirements

For a consequential finding, identify **the factual trigger**, **the governing source**, and **the
smallest useful action**. Separate law/regulation, institutional or funder conditions, repository/data-use
terms, venue policy, reporting guidance and an editor's discretionary judgement. A journal can impose
conditions beyond the law; label that difference. Do not infer legal jurisdiction from journal location
or the author's address alone. Check the actual activity, institutions, data and deployment concerned.

Use four dispositions:

| Disposition | Meaning |
|---|---|
| `applies` | Known facts meet a verified rule's trigger; state any permitted exemption or alternative |
| `not_triggered` | Known facts fall outside this particular rule; give the limited reason |
| `conditional` | Name the missing fact that would change the answer |
| `unverified` | The relevant rule or its applicability could not be confirmed |

Absence of approval wording is not proof that approval was required or absent. Distinguish consent
to participate, consent to identifiable publication, a waiver of consent, ethics approval, exemption
from review, and a determination that an activity is outside human-subject research. Do not invent
any of them or use them interchangeably. A supported public-data exception is useful even if another
venue would ask for oversight. Do not demand new approval, trial registration, forms or experiments
without establishing their relevance.

Verify live primary policies for the selected or shortlisted destinations and the actual article type
and stage. Start from [venue-policies.md](references/venue-policies.md); its dated notes are not permanent
clearance. Read the operative paragraphs, including exceptions, rather than relying on a search snippet
or a publisher-wide summary. Record the URL, date and access limitation with material findings. Reuse a
current check within the task. If access fails, try another primary route and label remaining uncertainty;
continue without making the author fetch every blocked page. Read legal sources only for issues the
facts actually raise; the legal entry points in applicability.md are not a universal checklist.

## Reduce ambiguity and burden through accurate wording

Read [wording-and-responses.md](references/wording-and-responses.md) for conditional examples and replies.
Review the title, abstract, keywords and submission category first, then Methods, figures/screenshots,
data availability, declarations and cover letter for contradictions. These are prominent places where
imprecise wording can suggest a different study design; do not claim knowledge of secret screening
keywords or automated thresholds.

- Lead with the actual contribution and evaluation. Describe an annotation workflow as such when that
  is what was evaluated. Separate database disease labels from new diagnostic or clinical-utility claims.
- State self-release directly: an author voluntarily made **their own** genome or biomedical data public,
  where, under what stated terms, and how it is used here. Preserve that the data are human and potentially
  identifying; do not turn them into an anonymous cohort or invent recruitment.
- Use precise statements such as "no additional individuals were recruited" only when true. That fact
  alone does not establish exemption from human-subject research. Separate public reanalysis from any
  new collection or intervention, including self-experimentation.
- Use a venue's accepted exception and the shortest sufficient statement. Do not add ritual legal
  declarations, a catalogue of hypothetical hazards, or blanket assurances of GDPR/HIPAA compliance.
- Preserve actual clinical use, data provenance, consent limits, diagnoses, outcomes and material risks.
  "Research use only" is appropriate only if accurate; it is not a legal exemption. Do not remove real
  human-data facts, relabel real data as synthetic, or fabricate approval/consent to obtain a classification.

When editing is authorised, make the focused changes and review the diff. Preserve results, sample sizes,
identifiers, citations and scientific meaning. Mark any proposed narrowing of a substantive claim as a
claim correction, not cosmetic rephrasing. The companion `manuscript-prose-edit/scripts/guard.py` can
help with selected mechanical changes, but cannot establish policy fit or semantic equivalence.

## Compare venues or resolve a referral loop

Assess scientific fit separately from administrative burden. For each useful candidate, report scope and
article type, requirements actually triggered by this study, available exemptions, concrete author work,
and remaining editorial uncertainty. Do not assign invented enforcement probabilities or call an
unresearched venue permissive. The existing AI-policy ranking does not rank ethics or privacy burden.

For a full journal shortlist, pass these policy findings to `manuscript-journal-select` alongside the
author's validation resources, budget and other priorities. The reference notes here supplement the
shared venue database; they are not a second ranking engine or an instruction to duplicate venue data.

For a bioRxiv/medRxiv loop, read both notices and current scope rules. Distinguish a clinical-scope
decision from insufficient research results, a tool-only announcement, or missing oversight. Prepare a
short scope statement with actual evaluation endpoints and data provenance, and a factual clarification
referencing both submission IDs when available. Do not assume either server must accept the paper.
If another appeal has little value, offer suitable alternative preprint venues or a general repository
with its different dissemination role. Check duplicate-posting, prior-publication and licence conditions
before recommending a move. Keep the existing submission history accurate.

Drafting a clarification or reply is part of this workflow; submitting, emailing or publishing requires
the user's authorisation for that external action. Do not initiate repeated appeals or new submissions.

## Report only what changes a decision

Lead with the likely study classification and the most useful wording fix or venue choice. For each
material issue, give the location, possible misreading or actual obligation, factual basis, source/date,
and action. A compact table helps for multiple issues; a focused edit can be just revised text and a note.

Distinguish **wording ambiguity**, **venue-scope mismatch**, **substantive requirement**, and **unresolved
fact**. State whether an inference is yours or an editor has actually raised it. A user's past rejection
is a reported case, not proof of a universal screening mechanism. Do not promise freedom from reviewer
questions. Warn once about a concrete material risk, neutrally, with a practical option; avoid generic
alarm or repeated objections. Respect the author's choice among accurate wording, a supported exception,
accepting editorial uncertainty, clarification or another venue. Continue authorised work without becoming
a policy gatekeeper or representing an unresolved position as verified compliance.

For skill maintenance or behavioural evaluation, use [review-cases.md](references/review-cases.md).
