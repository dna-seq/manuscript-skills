# What actually triggers a requirement?

Use the study facts first. The distinctions below guide a targeted review, not a compulsory author
questionnaire. A software article may use human data without evaluating clinical outcomes; it may
still have data-use or ethics conditions. Conversely, mentioning a disease in background material
does not establish that such data were used at all.

## Study and data categories

| Facts of this paper | First interpretation to investigate | Do not infer |
|---|---|---|
| No human specimens/data used; disease applications only discussed | Software, methods or non-human research; check actual evaluation and article type | Human-subject research or clinical utility from future-use language |
| Simulated genomes or synthetic records | Computational evaluation; identify simulation and any real source/model-training data | Synthetic status if records actually came from identifiable people; absence of disclosure risk solely from the label |
| Public reference genomes, benchmark data or published summary statistics | Secondary computational use; check provenance, access conditions and applicable public-data exceptions | A newly recruited cohort; blanket ethics exemption for every public dataset |
| An author's own openly released genome or medical records | Deliberate personal self-disclosure plus this study's particular analysis; use the dedicated section below | A patient cohort, clinical care, anonymity, or a universal self-research exemption |
| Controlled-access genomes, clinical records or biobank data | Secondary use under the actual agreement, consent scope and applicable oversight route | Open permission to redistribute because the paper/software is open source |
| Newly collected samples, surveys, usability evaluations or health measurements from others | Human-participant/data research questions; distinguish technical testing from health endpoints | That a software label or a small sample eliminates oversight questions |
| An author undertakes an intervention and measures their response | Self-experimentation; assess design and applicable institutional/venue requirements | Mere reanalysis of an existing public genome, or automatic exemption because n=1 |
| Software recommendations used in patient care or outcomes assessed | Clinical research and possibly device/CDS questions, depending on activity and jurisdiction | Regulatory clearance from the phrase "research use only" |

Separate components in a mixed paper. An author's open genome does not cover collaborators' patient
records; adding a public benchmark does not turn controlled data into public data. Do not expand an
ethics question about one component into a demand for clinical validation of the entire tool.

## The author's own genome or biomedical data

This means data **about the author personally**: their genome, genotype file, laboratory results,
medical history, imaging or other biomedical measurements. It does not mean all samples a lab owns,
data the authors collected from patients, or records whose copyright the institution holds.

Treat voluntary self-publication as a legitimate and potentially decisive fact. Do not discourage an
author from making their own data public merely because the data are biomedical or genetic. An author
who deliberately released an identifiable genome should be described as such, rather than forced into
an invented anonymised-patient narrative. Use established release facts and the author's account; do not
demand an identity investigation or newly signed forms by default.

Establish only what affects the decision:

- **Whose data?** One author, several authors each contributing their own data, or other individuals too?
  Coauthorship alone is not permission to release a coauthor's biomedical data. Do not infer that the
  corresponding author's decision covers everyone.
- **What was deliberately released?** Record the actual accession/DOI, data type, public link and stated
  reuse terms if available. A code licence does not necessarily license accompanying records. Public
  access, licensing, consent for publication and ethics review are distinct; an absent explicit licence
  does not by itself prove unlawful use or require drafting a new licence.
- **When and why?** Distinguish an existing public release used for this evaluation from data first
  collected or released as part of this study. Making data public during a study does not retroactively
  establish that the earlier collection/intervention needed no oversight. Check the venue's meaning of
  "already openly available" instead of silently stretching it.
- **What did this paper do?** Annotation, runtime benchmarking, visualisation, a biomedical inference,
  a new measurement, or an intervention? A disease annotation is not a demonstrated diagnosis, but a real
  diagnosis or self-experiment must not be edited out of the account.
- **What authority is actually needed?** Use the selected venue's public-data exception or a documented
  institutional/legal determination where applicable. Do not invent an IRB waiver, nor demand one if no
  applicable rule requires it. State a remaining gap plainly when a venue requires independent oversight.

Consent to deliberate public identification can be described accurately; do not call that dataset
anonymous. If separate formal publication consent is required by the target, prepare the shortest
appropriate wording from confirmed facts. Do not treat an author's self-release as a universal substitute
for oversight, or a journal's extra requirement as proof that public self-disclosure is illegal.

Inspect only concrete third-party issues in the supplied material: another person's report in the
same upload, named relatives and their diagnoses, clinical correspondence, or identifiable screenshots.
A genome can permit inferences about relatives, but that alone is not a universal requirement for family
consent or a reason to suppress voluntary self-release. Flag a material applicable constraint or actual
third-party disclosure proportionately; do not append a generic genetics warning to every edit.

Do not upload or publish additional biomedical files as a side effect of editing. Existing permission
to publish a particular genome does not authorise disclosure of unrelated records or redistribution to
external manuscript-analysis services.

## Keep the questions separate

| Question | Evidence that can resolve it | Common overreach |
|---|---|---|
| Is this a clinical paper for this server? | Purpose, endpoints, actual application, current scope policy and any screening notice | Treating the word "human" as the rule, or claiming the editor's decision is predictable |
| Does human-research oversight apply? | Actual activity, jurisdiction/institution, existing determination, current venue conditions and exceptions | Assuming all human data require new IRB approval, or that all public/self data are exempt |
| Is there a clinical trial? | Actual prospective assignment to a health-related intervention and the applicable definition | Calling every software benchmark a trial; ignoring a real intervention because it is self-directed |
| May these files be accessed, analysed or redistributed? | Release terms, consent scope, data-use agreements and applicable law for each action | Equating downloadable, open source, owned, consented and unrestricted |
| Is identifiable publication authorised? | The person's deliberate release/publication decision and any required consent | Calling a named genome anonymous, or claiming copyright alone settles privacy |
| Is the software a regulated product/function? | Intended purpose, functionality, deployment and current jurisdiction-specific criteria | Claiming that a disclaimer or article category determines regulatory status |
| Which reporting checklist is relevant? | Study design and the target's article-specific instructions | Applying CONSORT, STROBE, STARD, TRIPOD or ARRIVE together to every biomedical tool |

For only the applicable subjects, also check actual conditions on animal work, biospecimens/cell lines,
embryos, fieldwork/collection permits, biosecurity/dual use, community data governance, conflicts and
availability. Mere background discussion does not trigger experimental requirements. For analyses of
public pathogen sequences, distinguish computation from new pathogen experiments rather than assuming
a biosafety protocol is missing.

## Primary legal and regulatory starting points

These are targeted research routes, not a certificate of legal compliance. Recheck the operative text,
jurisdiction and institutional conditions when a recommendation depends on them. Dates below refer to
the access described, not a claim to have completed a legal assessment of a manuscript.

- **US human-subject research:** [45 CFR part 46, HHS](https://www.hhs.gov/ohrp/regulations-and-policy/regulations/45-cfr-46/index.html),
  particularly 46.101 (application), 46.102 (definitions) and 46.104(d)(4) (secondary-research exemptions).
  Direct text was blocked on 2026-10-15. The official [revised Common Rule preamble](https://www.hhs.gov/ohrp/regulations-and-policy/regulations/2018-req-preamble/index.html)
  has an indexed explanation of the public-information secondary-use exemption; it is not a substitute
  for applying the current regulation. Distinguish outside-scope research, exempt research and a waiver
  of consent. Do not export US definitions to every country or invent an institutional determination.
- **EU data protection:** [GDPR official text](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng/).
  On 2026-10-15, official indexed text was accessible but full HTML retrieval was blocked. Check Articles
  2–3 (scope), 4 (definitions), 5–6 (principles/lawful basis), 9 (health/genetic data) and 89 (research
  safeguards) as relevant. Article 9(2)(e) addresses data manifestly made public by the data subject;
  deliberate public self-release can matter. It is not a blanket exclusion from GDPR or an automatic
  Article 6 basis. Pseudonymisation is not anonymisation. Do not assume all downstream inferences about
  relatives were themselves deliberately made public. Verify the relevant provision before relying on
  it in an ethics statement; explicit consent and other possible bases require their own assessment.
- **US health privacy:** [HHS HIPAA de-identification guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html),
  indexed primary text checked 2026-10-15. Establish covered-entity/business-associate and data scope
  before asserting HIPAA applies. Personal public self-disclosure is not automatically a covered-entity
  disclosure. Removing names is not proof of a HIPAA de-identification determination; do not certify one.
- **US software:** [FDA Clinical Decision Support Software](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software),
  official indexed January 2026 guidance and [FDA CDS FAQs](https://www.fda.gov/medical-devices/software-medical-device-samd/clinical-decision-support-software-frequently-asked-questions-faqs)
  checked 2026-10-15. Follow current criteria for the particular function and intended use. Publication
  of a computational method does not itself establish a marketed device, and describing real patient-care
  functionality as a research tool does not settle device status.
- **EU software:** [European Commission MDCG 2019-11 rev.1 notice](https://health.ec.europa.eu/latest-updates/update-mdcg-2019-11-rev1-qualification-and-classification-software-regulation-eu-2017745-and-2025-06-17_en),
  June 2025 revision verified in the official index on 2026-10-15. Use the current guidance and MDR/IVDR
  provisions for an actual qualification question. Do not assume that all genomic analysis is medical
  device software or that a publication disclaimer removes a genuine intended medical purpose.

When a genuine legal determination needs expertise or missing facts, identify that narrow issue and
continue the manuscript work that can be completed. Do not turn uncertainty into a demand for a broad
legal review, a new study or a stack of declarations.
