# AI-use disclosure templates

Researched 2026-10-15 (sources in `publisher-policies.md`). Fill every bracket with facts the authors confirm.
Never guess what a tool did, and never reuse one venue's statement for another: the fields and places differ.

## What every statement needs

| field | required by |
|---|---|
| tool name **and version** (model id) | OUP, T&F, Frontiers, Science, JAMA, Wiley, MDPI; Elsevier for figures and research use |
| what it did, and why | everyone |
| which sections / figures / code it touched | IEEE (required); OUP, Wiley (recommended) |
| how the authors directed and verified the output | OUP, PLOS, Wiley, Elsevier ("extent of oversight") |
| dates of use | JAMA (required); OUP, Wiley (recommended) |
| manufacturer / developer | JAMA; Elsevier and Cell for research use |
| prompts | ICMJE "where applicable" when AI did the study; WAME; Frontiers (encouraged); Elsevier and Wiley on request |

Where it goes: the **cover letter** (ICMJE, OUP, *Bioinformatics*, Science) plus the venue's place in the
manuscript, at first submission and updated at every revision (OUP).

## Keep it short

A disclosure needs only the fields its venue lists, and none asks for a narrative. Default to two
sentences, written once at submission from what the authors say the tools did:

> [Tool, model id] ([developer]) was used to [kind of help: edit the language of | revise | help draft]
> [sections]. The authors reviewed and edited all output and take full responsibility for the content.

Add a third sentence only for what the venue specifically asks (dates for JAMA; how output was validated
for PLOS; code help in Methods for Science, Wiley, Elsevier, ACM). Short is fine; smaller than the actual use
is not: write the kind of help that happened ("help draft" if a model drafted text), because version history,
co-author trailers in public repositories and revision markers can contradict an understated statement, and
ICMJE treats nondisclosure as possible misconduct.

## *Bioinformatics* / *Briefings in Bioinformatics* (ISCB policy, OUP)

Three places: cover letter; Methods or Acknowledgements; and **documentation "with sufficient details in the
supplementary materials"**. Drafting text, figures, tables or references from a prompt is not acceptable at
all, so the statement can only describe acceptable uses (correction, translation, evaluation, code help,
documentation, an LLM as a research technique).

Acknowledgements / Methods:

> **Use of large language models.** [Tool, model id] ([developer]) was used between [dates] to [check
> grammar and spelling | find inconsistencies between sections | revise the authors' text in response to
> reviewer comments | assist in writing code for X, which the authors reviewed and tested | …]. [If an LLM is
> part of the method: describe it in Methods with model id, settings and prompts.] The authors reviewed every
> change and take full responsibility for the content. Details are in Supplementary Note [N].

Add "No text, figure, table or reference was generated from a prompt" **only if it is true**. Refining text
the authors wrote is not drafting from a prompt; a new paragraph an LLM wrote in answer to a reviewer comment
is closer to it, even inside a human-written paper. The ISCB policy names only spelling and grammar
correction as an acceptable writing aid, so substantive rewording is a grey zone that ISCB judges case by
case: disclose it in full, and make sure a human has edited and owns every segment the LLM wrote.

Supplementary Note: one short paragraph, not a log. Which tools and versions, the kind of help (language
editing, revision of the authors' text, code assistance), which sections, and how the authors checked it.
If the project already marks AI-revised segments, a count per section is enough.

## OUP default (NAR, GigaScience's base policy, other OUP journals)

Cover letter **and** Acknowledgements (Methods too when integral):

> During the preparation of this work the authors used [tool, version] on [dates] to [purpose], in
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
  version history showing human authorship; keep that history.
- **ICML / ACL / EMNLP / CVPR / AAAI**: disclosure per the call; hallucinated references and hidden prompts are
  desk-reject or sanction grounds.

## arXiv, bioRxiv, medRxiv

arXiv: report "significant use" of text-to-text generative AI; authors answer for incorrect references.
bioRxiv/medRxiv: detail AI use in the manuscript.

## Stage-wise contribution table (AI-scientist and AI-assisted research papers)

Agents4Science scale: **A** ≥95% human, **B** mostly human, **C** mostly AI, **D** ≥95% AI. Put it in Methods
or the supplement.

| stage | level | what the AI did | what the humans did | evidence |
|---|---|---|---|---|
| hypothesis / question | | | | |
| study design | | | | |
| data curation | | | | |
| analysis and code | | | | |
| interpretation | | | | |
| writing | | | | |
| reference finding and checking | | | | |
