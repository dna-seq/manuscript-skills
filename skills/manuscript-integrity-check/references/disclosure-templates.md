# AI-use disclosure templates

Dated examples researched 2026-10-15 (sources in `publisher-policies.md`), not a universal disclosure
requirement. Follow `author-priorities.md`, check the target journal's current exemptions, and use only the
relevant example and required fields. Reuse known facts; ask only for material facts still missing.
`manuscript-journal-adapt` drafts and places statements from these templates; `manuscript-integrity-check`
only checks that the venue's required statements are present and placed.

## Fields a venue may request

This table compares policies; it is not the union of fields to put in every statement. Recommended,
encouraged and on-request information is not automatically required at submission.

| field | required by |
|---|---|
| tool name **and version** (model id) | OUP, T&F, Frontiers, Science, JAMA, Wiley, MDPI; Elsevier for figures and research use |
| what it did, and why | everyone |
| which sections / figures / code it touched | IEEE (required); OUP, Wiley (recommended) |
| how the authors directed and verified the output | OUP, PLOS, Wiley, Elsevier ("extent of oversight") |
| dates of use | JAMA (required); OUP, Wiley (recommended) |
| manufacturer / developer | JAMA; Elsevier and Cell for research use |
| prompts | ICMJE "where applicable" when AI did the study; WAME; Frontiers (encouraged); Elsevier and Wiley on request |

Use only the places named by the applicable venue, including submission fields if relevant. Update the
account at revision when the use changes; do not create a new record for every editing session.

## Keep it short

First determine whether a disclosure is needed. When it is, one or two sentences may suffice, using only
the venue's required fields and what the authors say the tools did. The following is a starting point,
not mandatory wording; omit model, developer or section detail when neither requested nor useful:

> [Tool, model id] ([developer]) was used to [kind of help: edit the language of | revise | help draft]
> [sections]. The authors reviewed and edited all output and take full responsibility for the content.

Add a third sentence only for what the venue specifically asks (dates for JAMA; how output was validated
for PLOS; code help in Methods for Science, Wiley, Elsevier, ACM). Short is fine; smaller than the actual use
is not: describe the actual kind of help ("help draft" if a model drafted text). Do not infer the kind of use from commit trailers, revision markers or style; accept the author's account and apply the current
venue's rule. The changes a manuscript-skills run recorded are the exception, because they are a record of that
run: `manuscript-journal-adapt` drafts the statement's part for the run from them (`scripts/ai_use.py`), marked as
covering that run only, and the authors' own use outside it comes from their answer. If the author chooses a different interpretation, distinguish that decision from verified
compliance and continue without repeating a policy objection.

## *Bioinformatics* / *Briefings in Bioinformatics* (ISCB policy, OUP)

The dated journal notes below record cover letter, Methods/Acknowledgements and supplementary
documentation. Verify those locations on the current journal page before requiring them. The directly
fetched ISCB page on 2026-10-15 prohibits drafting paper sections and permits correction, translation,
evaluation and code assistance; it does not itself specify those supplementary-documentation details.
Source: https://transition.iscb.org/iscb-policy-statements/iscb-policy-for-acceptable-use-of-large-language-models

Acknowledgements / Methods:

> **Use of large language models.** [Tool, model id] ([developer]) was used [between dates, only if the
> current page asks for them] to [check
> grammar and spelling | find inconsistencies between sections | revise the authors' text in response to
> reviewer comments | assist in writing code for X, which the authors reviewed and tested | …]. [If an LLM is
> part of the method: describe it in Methods with model id, settings and prompts.] The authors reviewed every
> change and take full responsibility for the content. Details are in Supplementary Note [N].

Add a negative assertion about AI drafting only when known and needed; do not volunteer an unverifiable
authorship-history claim. Distinguish narrow correction from substantive drafting rather than treating
all revision as exempt. When the authors' use may conflict with the drafting rule, draft the statement they
ask for from the facts and add at most one sentence naming the conflict and its practical consequence; the
decision is theirs (`author-priorities.md`). A human editing pass does not establish that earlier drafting
did not occur or guarantee acceptance under the rule.

Supplementary Note: one short paragraph, not a log. Which tools and versions, the kind of help (language
editing, revision of the authors' text, code assistance), which sections, and how the authors checked it.
Use a Supplementary Note only when the current journal actually requires one. Do not create segment
counts or assert that counts alone satisfy the journal's requested detail.

## OUP default (NAR, GigaScience's base policy, other OUP journals)

Cover letter **and** Acknowledgements (Methods too when integral):

> During the preparation of this work the authors used [tool, version] [on dates, only if the current page
> asks for them] to [purpose], in
> [sections]. [Author initials] directed its use and reviewed all output for accuracy.

GigaScience additionally asks for in-text citation of the tool, a usage summary at the end of the paper, and
the outputs as a supplementary file in GigaDB or another open repository.

## Elsevier and Cell Press

A separately titled section (Elsevier: immediately before the references; Cell: after "Declaration of
interests"). Elsevier's own wording:

> **Declaration of generative AI and AI-assisted technologies in the manuscript preparation process.**
> During the preparation of this work the author(s) used [NAME OF TOOL / SERVICE] in order to [REASON]. After
> using this tool/service, the author(s) reviewed and edited the content as needed and take(s) full
> responsibility for the content of the published article.

Research use goes in Methods (STAR Methods at Cell) with model, version and developer. Grammar and spelling
checks need no statement.

## Springer Nature, Nature Portfolio, BMC

Follow the journal's page; Springer Nature's own pages disagree (Introduction/Acknowledgements vs Methods).
Green uses (language polishing) may be disclosed; Amber uses (methods suggestions, extensive writing support)
must be. Visual content: an AI Declaration plus a note in the caption.

> **AI declaration.** [Tool, version] was used to [purpose] in [sections/figures]. [Initials] verified [how].
> Hypotheses, analyses and conclusions are the authors'.

## PLOS

In a dedicated Methods subsection, the Acknowledgements, or the figure legend: tool names; how they were used
and which parts of the study, article, data or files were affected; **how the authors evaluated the validity
of the output**. Language edits for clarity need no disclosure.

## MDPI

Declared at submission, described in Materials and Methods, product details in Acknowledgments:

> During the preparation of this manuscript/study, the author(s) used [tool name, version information] for the
> purposes of [description of use]. The authors have reviewed and edited the output and take full
> responsibility for the content of this publication.

## JAMA Network

Acknowledgment section (Methods for research use): platform, version and extension numbers, manufacturer,
dates, how and where used, and a responsibility statement. Not allowed: AI-drafted opinion pieces and letters,
AI-generated or AI-formatted references, AI-written responses to reviewers.

## Science journals

Cover letter, plus Methods (code that changes functionality, data generation or analysis: model and version)
or Acknowledgments (drafting text: model and version). Not allowed: AI illustrative images without editor
permission, entering the manuscript into an LLM while revising, or the reviews while responding.

## ML venues

- **ICLR 2027**: a mandatory AI-use section in the paper.
- **NeurIPS 2026**: per the checklist; the position-paper track screened with Pangram and asked some authors for
  version history showing human authorship. Version history the authors already keep can answer such a request;
  do not ask them to start one for it.
- **ICML / ACL / EMNLP / CVPR / AAAI**: disclosure per the call; hallucinated references and hidden prompts are
  desk-reject or sanction grounds.

## arXiv, bioRxiv, medRxiv

arXiv: report "significant use" of text-to-text generative AI; authors answer for incorrect references.
bioRxiv/medRxiv: detail AI use in the manuscript.

## Optional stage-wise contribution table

Use this only for a venue that requests it or a study where the division of labour is part of the
contribution. A concise factual description is sufficient elsewhere. Agents4Science scale: **A** ≥95%
human, **B** mostly human, **C** mostly AI, **D** ≥95% AI. These levels are author-reported, not measurable
percentages inferable from the manuscript or commit counts.

| stage | level | what the AI did | what the humans did | evidence |
|---|---|---|---|---|
| hypothesis / question | | | | |
| study design | | | | |
| data curation | | | | |
| analysis and code | | | | |
| interpretation | | | | |
| writing | | | | |
| reference finding and checking | | | | |
