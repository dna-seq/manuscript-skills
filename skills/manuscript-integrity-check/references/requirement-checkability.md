# What journal requirements can actually be checked?

Use this distinction when advising on a journal's requirements or a material policy conflict. It is an
agent analysis aid, not a form for the author to fill in. Apply the author's decisions under
`author-priorities.md`. Presence of a requirement, ability to verify it, and likelihood of enforcement
are three different questions.

## Evidence classes

| Class | What can be established | Limit |
|---|---|---|
| **Observable** | A specified item is present, absent or within a measurable limit in supplied files or a submission form | The item can be checked without establishing that every assertion in it is true |
| **Testable with materials** | Code executes, numbers reproduce, a cited source supports a claim, or a deposited artifact contains a specified record | Needs accessible code, data, sources or records; a partial test supports only the tested part |
| **Author-reported process** | What the author says happened, with any records already available | The final prose alone cannot establish tool identity, drafting history, completeness of logs or human oversight |
| **Editorial judgement** | Scope fit, sufficient novelty, appropriate AI assistance, substantive authorship, acceptable risk | An agent can assess reasons; it cannot certify how an editor will decide |
| **Unknown enforcement** | No reliable evidence of a screening method or its use for this submission | A policy saying a journal "may" screen does not show routine screening, its accuracy or its thresholds |

## Requirement by requirement

| Requirement | Check now | What the check cannot prove |
|---|---|---|
| Word limits, abstract headings, declarations, disclosure locations | Count under the journal's counting rules; inspect all supplied submission components | Approximate text counts are not the submission system's count; a cover letter not supplied is unassessed |
| Tool name, version, date, purpose, sections affected | Check whether required fields are stated consistently | Whether the stated tool was actually used, the dates are complete, or the described role is exhaustive |
| No AI drafting; only spelling/grammar; no AI-written Results or Discussion | Compare the author's account with the current rule; inspect existing evidence if relevant | Reliable provenance or a clean history from final wording, style, detector scores or an AI commit trailer |
| Human review, intellectual contribution, responsibility | Check the statement and evidence already available | That every passage was reviewed, who originated each idea, or a percentage of human contribution |
| Prompt or output deposit | Check that a required file/link exists, is accessible and describes the named method | That it includes every interaction, was recorded contemporaneously or fully reproduces a hosted model |
| Original/revised versions or records kept on request | Check supplied versions and compare them if asked | That no intervening drafts exist or the history is complete; an absent public history does not show that private records do not exist |
| References, retractions and citation support | Resolve identifiers, compare metadata/status, read relevant source passages | A failed resolver request is not evidence of fabrication; metadata alone does not prove claim support |
| Data/code availability, archive DOI, licence | Open links; resolve the archive; inspect version, licence, documentation and files | Full reproducibility without running code with the relevant data/environment; access restrictions may be legitimate |
| Correct results, validation and controls | Recompute or test the relevant claims with available materials; review the design | Hidden analytic choices or the adequacy of all possible controls; identify the specific unresolved inference |
| Mandatory independent-cohort or experimental validation | Establish the rule's actual scope/alternatives and whether the described study supplies them; compare with available resources before selecting a venue | Data independence, biological suitability and sufficient validation may need scientific judgement; a requirement for a cohort does not necessarily require new recruitment |
| AI-generated or altered figures | Inspect captions and available source data, code or image provenance | Definitive origin from appearance alone; a real-looking figure can be synthetic and an unusual figure can be real |
| No simultaneous submission | Read the author's declaration and any explicit contradictory evidence | A complete search of private editorial systems |
| No plagiarism, novel contribution, appropriate AI use | Check identified overlaps and compare the closest work | Exhaustive absence of overlap, global novelty or a guaranteed editorial judgement |
| AI screening deployed or disclosed use penalised | Cite an explicit current statement or documented case and its scope | An undisclosed tool, future practices, a numerical rejection probability, or the outcome for this paper |

## Applying this to the venue catalogue

These examples describe the **kinds** of requirements recorded in `venues.yaml` and the dated research
notes. They do not refresh every venue's policy. Verify the actual target before calling a cached rule
current; journal-specific rules can differ from publisher defaults.

| Venue or policy family in the catalogue | Observable or testable portion | Process-dependent or judgement portion |
|---|---|---|
| Bioinformatics / Briefings in Bioinformatics / ISCB | Required declaration or supplement if confirmed on the journal page; article limits, abstract format, software links | Whether AI drafted sections or only corrected them; the boundary between revision and drafting |
| OUP default, NAR, Database | Required cover-letter/manuscript fields; availability artifacts for the actual article type and stage | Whether language help falls within an exemption; completeness of the account of use |
| Elsevier / Cell Press / iScience | Titled declaration and location; research-method details; figure source files if available | Extent of AI participation, supervision and origin of illustrative content |
| Springer Nature / BMC / Scientific Data / Genome Biology | Declarations, labels and method descriptions required by the current journal; reproducibility materials | Cached Green/Amber/Red boundaries, actual drafting history, sufficient intellectual responsibility |
| PLOS / PLOS Computational Biology | Required AI statement fields, figure disclosure, code/data links; no extra statement for exempt language editing | Whether output was fully validated, precise boundaries of exempt editing, unobserved tool use |
| CSBJ / Science Partner Journals | A prompt/tool/version is present in the required place if the current policy asks for it | That the prompt record is complete or captures all author/model contributions |
| GigaScience | Tool citation, required summary and deposited output files if applicable | Completeness and origin of the deposited outputs, actual allocation of intellectual work |
| PeerJ / Taylor & Francis / F1000 | Required statement; supplied original/revised files and requested records | Completeness of retained versions, actual oversight, boundary between refinement and generation |
| Science / JAMA | Required statements and fields for the article type; explicit examples or records when supplied | Whether a manuscript or review was entered into a tool, whether a response or opinion was AI-drafted |
| IEEE / ACM | Disclosure fields and affected sections where required by the current rule | Actual extent of writing versus research assistance and substantive author contribution |

PLOS's current FAQ exempts spelling, grammar, clarity and conciseness editing from disclosure; statement
presence therefore cannot be a universal AI-use test. Its FAQ also says it may use detection tools,
which does not establish that a particular submission was screened.
Source: [PLOS ethical publishing policy](https://journals.plos.org/ploscompbiol/s/ethical-publishing-practice),
read 2026-10-15.

The current [ISCB policy](https://transition.iscb.org/iscb-policy-statements/iscb-policy-for-acceptable-use-of-large-language-models),
read 2026-10-15, distinguishes drafting paper sections from correction and evaluation. That is a process
distinction; a detector score does not establish which happened. Verify disclosure placement separately
on the journal's own page.

## How to advise without becoming a policy gatekeeper

For each consequential issue, give the rule and its source/date, its evidence class, what is known,
what remains uncertain, and the least-work options. These may include a supported exemption, concise
wording, a different venue, editorial clarification, or proceeding under the author's interpretation.
Do not require a full matrix in every response; report only what changes a decision.

State enforcement evidence separately: documented routine checks, a discretionary power, an individual
case, or unknown. The absence of a reliable AI-authorship test supports uncertainty about provenance;
it does not establish immunity from questions, record requests or editorial decisions. Do not predict
"they cannot check" or assign an unsupported enforcement probability. Once the author decides, continue
the task and do not repeat the same policy dispute.
