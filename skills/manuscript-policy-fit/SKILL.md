---
name: manuscript-policy-fit
description: >-
  Review and edit manuscripts to reduce avoidable clinical, regulatory, ethics and privacy
  misclassification and submission burden. Determine which requirements actually apply, use supported
  exemptions, clarify voluntarily self-published author genomes or biomedical data, compare preprint
  servers and journals, and draft scope clarifications and replies to ethics, consent, clinical-scope or
  privacy comments. Use for policy-friction reviews, bioRxiv/medRxiv referral loops, human-data wording
  and proportionate ethics statements. Use manuscript-reviewer-response for the full response letter to
  referees, manuscript-reporting-check for reporting checklists and availability statements,
  manuscript-journal-select for a full journal shortlist, manuscript-journal-adapt for AI-use statements
  and venue formatting, and manuscript-prose-edit for general language editing.
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

Apply the requested task across the whole paper unless the author specifies a narrower scope.
Follow the shared [workflow controls](../manuscript-integrity-check/references/author-priorities.md#scope-iteration-and-review)
for requested section or stage review, before/after comparisons and optional interviews.

Before work, follow the shared [project setup and run-output contract](../manuscript-integrity-check/references/project-workflow.md): resolve saved manuscript-project choices, ask only missing first-use questions, and retain this skill’s report, evidence and failures in its subfolder of the linked run. This applies to direct invocations too. End with its [end-of-stage checklist](../manuscript-integrity-check/references/project-workflow.md#end-of-stage-checklist): `stage-report.md`, the smell check on it, `findings.json` with the prefix `PF`, and every applied edit recorded with `runs.py change`.

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

The backticked names are for these instructions. In the report write them as words: "applies", "does
not apply to this study, because ...", "depends on whether ...", "could not be confirmed, because ...".

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
current check within the task. If access fails, try another primary route (the same journal's article-type
or ethics page, the publisher-wide policy, a headless browser, the authors' own browser when a
browser-control tool is connected, an archived copy labelled with its date; the order is in the shared
[rule for blocked pages](../manuscript-integrity-check/references/author-priorities.md#minimum-useful-work))
and label remaining uncertainty; continue without making the author fetch every blocked page. A
summarising fetch tool paraphrases: quote a rule only from text retrieved word for word, and say so when
a quotation is a paraphrase. For which rules can be checked from the files and which rest on editorial
judgement, see
[requirement-checkability.md](../manuscript-integrity-check/references/requirement-checkability.md).
Read legal sources only for issues the facts actually raise; the legal entry points in applicability.md
are not a universal checklist.

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
  identifying; do not turn them into an anonymous cohort or invent recruitment. Put the detail in Methods
  or Data availability and add to the abstract only what its word limit allows. Whether to name the person
  whose data it is stays the authors' decision, weighed against the venue's rules on identifiable
  individuals (some preprint servers have them).
- Use precise statements such as "no additional individuals were recruited" only when true. That fact
  alone does not establish exemption from human-subject research. Separate public reanalysis from any
  new collection or intervention, including self-experimentation.
- Use a venue's accepted exception and the shortest sufficient statement. Do not add ritual legal
  declarations, a catalogue of hypothetical hazards, or blanket assurances of GDPR/HIPAA compliance.
- Preserve actual clinical use, data provenance, consent limits, diagnoses, outcomes and material risks.
  "Research use only" is appropriate only if accurate; it is not a legal exemption. Do not remove real
  human-data facts, relabel real data as synthetic, or fabricate approval/consent to obtain a classification.
- Draft a declaration (consent, ethics, competing interests, funding, author contributions) only from facts
  the authors or the project's own files supplied. One that needs a fact nobody gave is a held proposal with
  the question as its comment, never a plausible default, and an author's credit is never dropped or narrowed.

When editing is authorised, make the focused changes and review the diff. Preserve results, sample sizes,
identifiers, citations and scientific meaning. Mark any proposed narrowing of a substantive claim as a
claim correction, not cosmetic rephrasing. The companion `../manuscript-prose-edit/scripts/guard.py` can
help with selected mechanical changes, but cannot establish policy fit or semantic equivalence. Text you
write into the manuscript (a scope clarification, an ethics or data statement) passes the required smell
check, `../manuscript-deslop/scripts/style_profile.py AFTER --before BEFORE --check`, with a read
against the pattern list it prints ([prose-edit contract, §5.3](../manuscript-prose-edit/references/prose-edit-contract.md#53-the-smell-check)).
When the authors authorised a claim correction, or supplied the facts of a declaration (consent, ethics,
approval or exemption) that the edit writes, list each one in `RUN/manuscript-policy-fit/requested-claims.yaml`
as `- {passage: "a verbatim, contiguous run of at least three words from the sentence", finding: "authors'
request"}` (or the finding's id) and run the guard with `--authorised RUN/manuscript-policy-fit/requested-claims.yaml`:
that change is then listed as requested, and any other widened claim and any changed number or citation
still fails, so restore its wording.

## Compare venues or resolve a referral loop

Assess scientific fit separately from administrative burden. For each useful candidate, report scope and
article type, requirements actually triggered by this study, available exemptions, concrete author work,
and remaining editorial uncertainty. Do not assign invented enforcement probabilities or call an
unresearched venue permissive. The existing AI-policy ranking does not rank ethics or privacy burden.

For a full journal shortlist, pass these policy findings to `manuscript-journal-select` alongside the
author's validation resources, budget and other priorities. Record each venue-specific finding (a server
that declines tool announcements without results, a journal's rule on identifiable individuals) in the shared
venue catalogue, in that venue's `other_desk_rules`, with the URL of the page and the date read
(`provenance: {other_desk_rules: {source, checked}}`): `../manuscript-journal-adapt/scripts/venues.py where`
names the file, the shipped `venues.yaml` in the plugin's own checkout or the user's own catalogue in an
installed plugin ([selection-fields.md](../manuscript-journal-select/references/selection-fields.md)). A list
replaces the older list, so write the venue's existing rules with the new one. Read first what
`venues.py stale KEY` says is due; a rule recorded within the year needs no second reading.
`manuscript-journal-select` then reruns `ladder` and `common`, so the rule reaches both ladders and the
requirements file. The reference notes here supplement the shared venue database; they are not a second
ranking engine or an instruction to duplicate venue data.

For a bioRxiv/medRxiv loop, read both notices and current scope rules. Distinguish a clinical-scope
decision from insufficient research results, a tool-only announcement, or missing oversight. Prepare a
short scope statement with actual evaluation endpoints and data provenance, and a factual clarification
referencing both submission IDs when available. Do not assume either server must accept the paper.
If another appeal has little value, offer suitable alternative preprint venues or a general repository
with its different dissemination role. Check duplicate-posting, prior-publication and licence conditions
before recommending a move. Keep the existing submission history accurate.

Drafting a clarification or reply is part of this workflow; submitting, emailing or publishing requires
the user's authorisation for that external action. Do not initiate repeated appeals or new submissions.

When a decision letter mixes policy comments with scientific ones, `manuscript-reviewer-response` keeps the
comment ledger and the response letter. Draft the replies to the ethics, consent, clinical-scope and
privacy items here and hand them back for the letter. `manuscript-reporting-check` checks that required
declarations and checklist items are present; deciding which of them apply stays with this skill.

## Report only what changes a decision

Open with one line giving the likely study classification, then the four groups below. For each
material issue, quote the passage it concerns and name its section (a line number may follow in
parentheses), then give the possible misreading or actual obligation, its factual basis and the action.
Quote the policy text a finding rests on with the URL of the page it is on and the date read, and say
when only part of the page could be read. A compact table helps for multiple issues if every cell is a
readable phrase; a focused edit can be just revised text and a note. Write as
[Writing for the authors](../manuscript-integrity-check/references/author-priorities.md#writing-for-the-authors)
describes: plain words, acronyms spelled out at first use, full sentences.

Order the issues as
[Order the work by when it can be done](../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done)
describes: facts the authors must establish and claims that misdescribe the study first, then wording
(the most useful wording fix leads this group), then requirements of the chosen venue (or, before the choice,
the venue comparison), and last the final declarations (the ethics, consent and data availability statements
as submitted). The last group is not a blocker for a draft.

Distinguish **wording ambiguity**, **venue-scope mismatch**, **substantive requirement**, and **unresolved
fact**, in plain words. State whether an inference is yours or an editor has actually raised it. A user's
past rejection is a reported case, not proof of a universal screening mechanism. Do not promise freedom
from reviewer questions.

A conflict between a venue's policy and what the authors chose (a named self-released genome at a server
that bars identifying information, AI use at a journal that restricts it) is a decision for the authors,
listed with their other decisions, never a required fix or a blocker. Name it once, in one sentence with
its practical consequence; avoid generic alarm or repeated objections. A journal's AI-use policy is
outside this skill: `manuscript-journal-adapt` drafts the statement. Respect the author's choice among
accurate wording, a supported exception, accepting editorial uncertainty, clarification or another venue.
Continue authorised work without becoming a policy gatekeeper or representing an unresolved position as
verified compliance.

For skill maintenance or behavioural evaluation, use [review-cases.md](references/review-cases.md).
