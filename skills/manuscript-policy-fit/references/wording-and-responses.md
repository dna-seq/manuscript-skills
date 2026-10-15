# Precise wording and proportionate replies

Examples are conditional, not facts about Just-DNA-Seq or a supplied manuscript. Verify every factual
clause against the manuscript and the author's explanation. Replace bracketed fields with confirmed
facts; omit irrelevant clauses. Do not silently turn a new study into a public-data reanalysis, remove
real human involvement, or add an exemption statement just to reassure a screener.

## Wording that may suggest the wrong study

| Ambiguous wording | Possible misreading | More precise wording, only if true |
|---|---|---|
| "We tested the platform on a patient genome" | Recruited patient, clinical evaluation | "We evaluated the workflow using one author's own publicly released genome ([accession])." If it really is patient material, retain that provenance. |
| "Participants donated genomes" | Recruitment and biospecimen donation | "Two authors each contributed their own previously released genome for the software evaluation." Do not replace actual recruitment. |
| "We collected human data" | New sample collection or health-record access | "We downloaded the previously public dataset [accession] to benchmark [technical endpoint]." Keep original data provenance. |
| "Clinical validation" | Diagnostic accuracy or clinical utility study | "Technical evaluation of [concordance/runtime/output correctness] against [reference]." A clinical evaluation actually performed must remain labelled accurately. |
| "The tool diagnoses genetic disease" | Patient diagnosis or an intended medical function | "The tool annotates variants with disease associations from [database/version]." This is a substantive claim correction if diagnosis was originally claimed, not a synonym. |
| "Personalised treatment recommendations" | Clinical decision support or intervention | Describe the actual output, e.g. "retrieves published pharmacogenomic annotations" if that is all it does. Do not conceal treatment recommendations it actually generates. |
| "We assessed the author's disease risk" | A new individual health inference | Name the actual computation and its evidence. If only retrieving existing annotations, say so; if estimating disease risk, retain that fact and its limits. |
| "An anonymised open genome" | Anonymity asserted despite public identity linkage | "An openly released genome contributed by author [identifier]." Use the level of public identification the author actually chose; do not add a new identity link. |
| "All data are open source" | Code licence treated as consent or a data licence | "Source code is available under [licence]. The author's genome is available at [accession] under [stated terms]." If data terms are unstated, say that rather than inventing them. |
| "No human subjects were involved" while using an author's genome | Contradiction or an unsupported regulatory conclusion | "The evaluation used one author's own genome; no additional individuals were recruited." Any regulatory outside-scope determination is separate. |
| "Ethics approval was waived because these are our data" | A committee decision that may never have happened | State the actual self-release and analysis facts. Add a specific exception or documented determination only if established. |
| "All biomedical data are available on request for privacy reasons" for a deliberately public author dataset | A false restriction that obstructs reproducibility | Give the existing public accession and actual reuse terms. Do not invent privacy restrictions for data the author intentionally released. |

Do not maintain a blacklist of "clinical", "patient", "human" or disease names. Use each when it
describes the work. Where a tool processes human genomes, "genomic data" is not a reason to erase the
human origin. Correct scope drift across the title, abstract, results, screenshot labels, code examples,
availability statement and submission category. A disclaimer cannot repair contradictory evidence.

## Author self-release: short statements

**Existing public genome, technical evaluation:**

> The workflow was evaluated using the genome of one author, who had voluntarily made these data
> publicly available at [accession/link] under [stated terms]. The analysis assessed [technical
> endpoints]. No additional individuals were recruited, and no clinical intervention was performed.

The final sentence is optional and must be true. "No additional individuals" preserves the author's
involvement. Do not add "anonymous", "no human data", "IRB-exempt" or "legally unrestricted" by inference.
Mention that release preceded this study only if known; provide a date only when useful or required.

**Author biomedical records made public with this paper:**

> Author [identifier] voluntarily makes their own [specified records/data] publicly available with
> this article at [location] and agrees to their publication in this form. These data are used to
> illustrate [actual analysis]; [state actual additional recruitment/intervention facts if relevant].

Use only after the author's decision is established. This describes personal publication choice; it
does not claim pre-existing public-data status or substitute for oversight of any new research.
Do not add other records or disclose a private identity to fill the template.

**Several authors' personal data:**

> The demonstration datasets consist of the contributing authors' own [data types]. Each contributing
> author voluntarily released their own data at [accessions] under [terms] and agreed to the use
> described here.

Do not treat agreement to be a coauthor as that permission. If permission is known for only one author,
draft only that portion and identify the specific missing fact.

**Documented exception or determination, only when needed:**

> [Body] determined that [specified activity] [did not constitute human-subject research / was exempt
> from review under provision], [reference/date if required].

Choose the actual determination, not both alternatives. A waiver of consent is different. If relying
directly on a verified venue public-data exception without a committee decision, cite that exception
in the advice and write a factual public-data statement; do not manufacture a committee or approval ID.

## Scope statement for a software/methods paper

A possible title shape, if the contribution supports it:

> Just-DNA-Seq: a reproducible workflow for annotation and visualisation of individual genomes

This is an illustration, not an assessment of the unavailable first manuscript. The scope statement
could say:

> This manuscript reports a computational workflow and evaluates [actual technical endpoints] using
> [actual dataset provenance]. Its contribution is [specific method/software result]. [If true: It does
> not evaluate diagnostic accuracy, treatment effects or patient outcomes.]

Put the actual contribution and results first. Avoid an abstract padded with defensive declarations.
A single personal genome may demonstrate functionality but cannot establish population-level clinical
performance. Offer accurate claim limits rather than demanding a clinical cohort for a software paper.

## bioRxiv/medRxiv referral loop

Read the rejection notices and both live policies before choosing a response. A referral can concern
clinical scope, while a later rejection can concern tool-only content or oversight; the reasons need
not be the same. The user's reported experience does not establish a universal keyword rule.

Draft, without sending:

> Regarding [submission ID/title]: bioRxiv referred this manuscript to medRxiv on [stated grounds],
> while medRxiv declined it on [stated grounds; second ID if known]. The paper reports [contribution]
> with [actual methods/results]. Its human-data component is [precise provenance, including voluntary
> author self-release where applicable]. [If true: No additional individuals were recruited and no
> clinical intervention was performed.] We have clarified [specific wording] to distinguish the software
> evaluation from clinical research. Could you reassess its fit under [specific scope criterion]?

Do not claim a transfer recommendation is acceptance, fabricate a notice/ID, disguise a prior rejection
as a fresh submission, or keep retrying without new information. Offer an alternative with verified
scope and posting conditions when further correspondence is unlikely to help.

## Reviewer replies

**Public personal data mistaken for a recruited cohort:**

> The dataset is the author's own [genome/records], voluntarily released at [accession]. The paper
> reports [actual analysis] of those data; no additional individuals were recruited. We have clarified
> the provenance in [section]. [If established: The applicable [venue rule/determination] is [specific
> basis], rather than the requirements for [the misidentified design].]

**Request for an ethics approval number where none was required:**

Give the established reason and its scope. If only the author's interpretation is available, distinguish
it from an independent determination and explain the venue's remaining requirement once. Do not
assert an exemption solely from ownership or demand retrospective approval as a default remedy.

**Request for clinical validation beyond a technical paper's claims:**

> The study evaluates [technical question], using [endpoints]. We have limited the claims to that
> evaluation and clarified that [clinical outcome/utility] was not assessed. Clinical validation would
> address a different question from the one tested here.

This reply is appropriate only if the manuscript no longer claims the untested clinical benefit. Retain
limitations that affect actual results. The author may instead choose a more suitable article type or
venue; adding patients or experiments is not the automatic answer to a classification dispute.
