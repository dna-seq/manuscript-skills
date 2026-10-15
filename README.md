# Manuscript Skills

Six skills for Claude Code and Codex that help scientists prepare manuscripts for publication. Use them
to check references, improve prose, choose a suitable journal and prepare a submission. They work with
manuscripts written with or without AI assistance.

The aim is to help you publish sound research with less avoidable delay, expense and paperwork. Journal
recommendations take account of the research you have done, the validation you can afford and your
publication priorities. You decide which journal to pursue and how to handle uncertain or burdensome
requirements.

## Choose the task you need

| Your task | Skill | What you receive |
|---|---|---|
| Improve the writing | [manuscript-prose-edit](skills/manuscript-prose-edit/SKILL.md) | Edits for clarity, grammar and author voice, with checks for unintended changes to claims, numbers, citations and scientific terms. |
| Check the references | [manuscript-reference-check](skills/manuscript-reference-check/SKILL.md) | Verification of citation details, recorded retractions and whether sources support the claims, with unresolved checks identified. |
| Choose where to submit | [manuscript-journal-select](skills/manuscript-journal-select/SKILL.md) | A shortlist based on scientific fit, validation requirements, publication costs, open-science preferences, review timing and AI policies. |
| Prepare for a chosen journal | [manuscript-journal-adapt](skills/manuscript-journal-adapt/SKILL.md) | Changes to length, structure and required statements, plus submission materials and a concise AI-use disclosure where needed. |
| Review the manuscript before submission | [manuscript-integrity-check](skills/manuscript-integrity-check/SKILL.md) | A prioritised report of unsupported claims, reference problems, unfinished content and applicable submission barriers, with suggested fixes. |
| Clarify study scope or policy requirements | [manuscript-policy-fit](skills/manuscript-policy-fit/SKILL.md) | An assessment of which clinical, ethics or privacy requirements apply, precise wording and drafts of scope clarifications or reviewer replies. |

You can request any of these independently. Editing a paragraph does not require a full manuscript
review. A full submission review includes reference checks where relevant.

## Start with your manuscript

Once the plugin is installed, share your manuscript with the assistant and describe what you want done.
You can use ordinary language or name a skill from the table above.

Markdown, plain text and LaTeX manuscripts can be checked directly. Include the bibliography files with
a LaTeX manuscript. For Word or Google Docs, use a document connection available to your assistant or
provide an export. For a passage edit, pasting the text is enough.

Add the context that matters to your request: a target journal, article type, publication budget or
deadline, for example. For journal selection, explain which additional analyses or experiments are
feasible. If you have already received an editorial decision, include the relevant comments. The
assistant uses what you provide and asks about missing facts that would change its answer.

## Improve a manuscript from draft to submission

To ask the assistant to combine the six skills, use a request such as:

> Help me improve this manuscript for submission. Use the six Manuscript Skills where relevant: review
> the scientific claims and references, clarify applicable policies, recommend suitable journals, edit
> the prose and adapt the paper to the chosen journal. Start from the manuscript and our existing
> context. Explain decisions that need my input, make the agreed edits and finish by checking the
> changes. Reuse completed checks rather than repeating them.

A useful sequence is:

1. **Review the draft and references.** Identify unsupported claims, citation problems and missing
   material through the integrity and reference checks.
2. **Resolve scope and choose a journal.** Use policy-fit assessment where the study raises clinical,
   ethics or privacy questions, then shortlist journals within your research and publication budget.
   Use your existing target if you have already chosen one.
3. **Edit and prepare the submission.** Improve the prose and apply the chosen journal's requirements,
   preserving the results and their qualifications.
4. **Check the changes.** Verify affected citations, claims and submission requirements, and report any
   unresolved issues.

The skills contribute to the same manuscript and share findings across these steps. Some tasks may
already be complete or unnecessary for your study. You can also ask to stop after the review or journal
shortlist; preparing a manuscript does not itself submit it to a journal.

## Requests you can reuse

For a prose edit:

> Edit the Discussion for clarity and readability. Preserve the claims, numbers, citations and
> uncertainty, and keep our voice. Show me what changed.

For references:

> Verify the references in this manuscript. Check whether the sources support the main claims in the
> Abstract and Discussion, and distinguish incorrect citations from sources you could not verify.

For journal selection:

> Suggest journals for this computational aging paper. We can reanalyse public datasets but have no
> wet-lab budget. Compare scientific fit, publication costs and review speed. We used AI to revise the
> text, so explain the relevant writing policies too.

You can also ask for an interview to establish your journal preferences, compare AI-policy burdens,
find journals where named colleagues publish, or check whether a target journal's AI policy has changed.

For adaptation to a journal:

> Prepare this manuscript for initial submission to [journal]. Apply its abstract and length rules,
> check the required statements and draft the cover letter. Use free-format submission if it is allowed.

For a submission review:

> Review this manuscript before submission to [journal]. Prioritise problems that could affect the
> scientific conclusions or prevent review. Separate required fixes from optional improvements.

For a scope or ethics question:

> This paper evaluates an annotation tool using my own publicly released genome. Check which
> requirements apply and clarify the wording so it accurately describes the study and data.

The policy-fit skill also helps with preprint screening decisions, including papers referred between
bioRxiv and medRxiv, and drafts factual clarifications based on the notices you received.

## How to interpret the results

Prose editing aims to preserve your scientific meaning, including uncertainty and limitations. The
assistant reviews the changes and uses checks that can flag altered numbers, citations and terminology.
These checks help catch mistakes; you should still review the edited text before using it.

Reference checking distinguishes a source's identity from its support for a particular sentence. A DOI
that resolves to the right paper does not establish that the paper supports your claim. The assistant
reads the relevant source material and identifies what it could not verify; a failed lookup alone is
not evidence that a reference was invented.

Journal coverage is strongest in bioinformatics, genomics, genetics and aging research. The catalogue
also includes preprint servers and policy notes for machine-learning conferences. Entries have sources
and dates, but some are incomplete and policies change. The assistant checks current requirements that
affect its recommendations and reports material uncertainties. Review-time comparisons distinguish
initial editorial decisions from decisions after external peer review.

For ethics and privacy questions, the assessment depends on what the study actually did, the data used
and the chosen journal. Public reanalysis, an author's voluntary release of their own data and research
involving recruited participants can raise different requirements. Applicable exceptions are considered;
a missing declaration alone does not establish that an approval was required.

AI-use statements draw on your account of what the tools did and the journal's required fields and
exemptions. Optional AI-text detector checks run only when requested. Their scores are fallible style
signals, not evidence of authorship or a guarantee of acceptance. A hosted detector requires your
agreement before the manuscript is sent to that service.

## Installation

Install **manuscript-skills** as a plugin in Claude Code or Codex. The plugin includes all six skills.

In **Codex**, install it from the **DNA Seq Genomics** marketplace.

<details>
<summary>Installation commands for Claude Code</summary>

From the DNA Seq marketplace:

```bash
claude plugin marketplace add dna-seq/dna-seq-claude-marketplace
claude plugin install manuscript-skills@dna-seq
```

Or directly from this repository:

```bash
claude plugin marketplace add dna-seq/manuscript-skills
claude plugin install manuscript-skills@manuscript-skills
```

</details>

The automated checks require [uv](https://docs.astral.sh/uv/) on the computer running the assistant;
their dependencies install on first use. Ask the assistant to check the setup if needed. Looking up
references and current journal policies requires internet access.

## Licence

[MIT](LICENSE). Journal policies remain governed by the journals' own published guidance.
