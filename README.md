# Manuscript Skills

Skills for Claude Code and Codex that help scientists prepare manuscripts for publication. Start with
`manuscript-improve` for the full workflow, or choose one of fourteen focused skills: review a manuscript
before submission, check its references, reporting and statistics, clarify which ethics and privacy
rules apply, simulate the referees of a target journal, improve the prose, remove formulaic AI phrasing,
make the paper interesting to its readers again without changing its science or direction, choose where to preprint and
submit, prepare for a journal, answer referees after a decision, visualize what the reviews caught and
changed, or keep track of who revised each passage and which AI edits no person has reviewed yet.
They work with manuscripts written with or without AI assistance.

The aim is to help you publish sound research with less avoidable delay, expense and paperwork. Journal
recommendations take account of the research you have done, the validation you can afford and your
publication priorities. You decide which journal to pursue and how to handle uncertain or burdensome
requirements.

## Choose the task you need

| Your task | Skill | What you receive |
|---|---|---|
| Improve a manuscript from draft to submission | [manuscript-improve](skills/manuscript-improve/SKILL.md) | A coordinated workflow using the relevant skills below, in one of three modes (report only, routine fixes by default, or every change). You get the corrected version of the whole paper with track changes, kept beside your file until you accept it, a dashboard of what the run found and changed, and one summary of what is left, grouped by when it can be done, with the decisions that are yours. |
| Improve the writing | [manuscript-prose-edit](skills/manuscript-prose-edit/SKILL.md) | Edits for clarity, grammar and author voice, with a check, sentence by sentence, that no edit strengthened a claim, dropped a qualifier or null result, or changed numbers, citations or scientific terms, and a required check that the edit added no machine-written pattern and left no run of one. |
| Deslop scientific writing | [manuscript-deslop](skills/manuscript-deslop/SKILL.md) | Removes formulaic LLM phrasing, boilerplate and empty rhetoric while preserving scientific meaning and author voice. Also audits without editing; owns the shared pattern catalogue and style checker. |
| Show colleagues what the review caught | [manuscript-visualize](skills/manuscript-visualize/SKILL.md) | The last step of every improvement run. Collects each skill's findings from the run, merges what several skills found into one problem, and renders an offline dashboard: problems by kind, severity, stage, section and skill, coverage, the funnel from raw signals to confirmed problems, edits as before/after diffs, the reader and referee panels, the annotated manuscript, the corrected version as track changes, machine-writing patterns by type in each version, and, against a reference review such as a co-author's comments on the same version, what was caught and why the rest was missed. |
| Make the paper interesting to its readers | [manuscript-story](skills/manuscript-story/SKILL.md) | How the paper reads to the people it is for: a panel of fresh readers, reading measures compared with your earlier version, and a comparison with the closest papers and with well-told papers of the same format; then story edits within the direction you chose (the stake up front, one headline per result, your real output shown, every caveat kept but placed where it costs readers least), each checked against the science, the journal's format and screening, and machine-written patterns. A change of direction, such as leading with privacy instead of speed, is only ever offered as options. |
| Check the references | [manuscript-reference-check](skills/manuscript-reference-check/SKILL.md) | Verification of each reference's identity and authors, retractions, withdrawn preprints and preprints that have since been published, and whether the cited sources support the claims that carry the paper, with the supporting passage quoted and how many claims were checked. |
| Check reporting standards and availability | [manuscript-reporting-check](skills/manuscript-reporting-check/SKILL.md) | An item-by-item check against the reporting guidelines that fit your study design, a check that the data, code and software you name can actually be found, and a review of how statistics are reported. |
| Review the manuscript before submission | [manuscript-integrity-check](skills/manuscript-integrity-check/SKILL.md) | A report of unsupported claims, inconsistent numbers and statistics, reference problems, unfinished content, files that would leak private notes or hidden text, and applicable submission requirements, with suggested fixes, grouped by when each can be done. |
| Anticipate referees' objections | [manuscript-peer-review](skills/manuscript-peer-review/SKILL.md) | The reports three simulated referees would send from your target journal (or each of the top three on your ladder), each with a recommendation, strengths, and major and minor concerns that quote the paper; then the list of what to fix, in the order you can act on it, with the work only you can do. No scores or acceptance predictions. It can also draft your report on a paper you were invited to referee. |
| Choose where to preprint and submit | [manuscript-journal-select](skills/manuscript-journal-select/SKILL.md) | Two ladders, preprint servers and journals, ordered by your priorities (speed, reach, AI-policy burden, cost) after checking scientific fit, validation requirements, fees and the agreements that pay them, open-science preferences, review timing and AI policies, with the rule that decides each venue quoted and linked to its page; and what every venue on the ladders asks for, so the shared sections can be adapted before you choose. |
| Prepare for a chosen journal | [manuscript-journal-adapt](skills/manuscript-journal-adapt/SKILL.md) | Changes to length, structure and required statements, shown before and after, plus submission materials and a concise AI-use disclosure where needed. What waits until the code and results are final is listed separately. |
| Clarify study scope or policy requirements | [manuscript-policy-fit](skills/manuscript-policy-fit/SKILL.md) | An assessment of which clinical, ethics or privacy requirements apply, with the policy text quoted and linked, precise wording and drafts of scope clarifications or replies to policy questions. |
| Answer referees and check the revision | [manuscript-reviewer-response](skills/manuscript-reviewer-response/SKILL.md) | A plan of the referees' comments in their own numbering with the decisions you need to make, a point-by-point response letter tied to the changes you made, and a check that the revision addresses each comment. |
| See who revised what, and which AI edits await review | [manuscript-revision-marks](skills/manuscript-revision-marks/SKILL.md) | Revision marks in a Markdown or LaTeX manuscript checked and reported: the passages each review comment changed, in how many rounds and by whom, the prose no round has read, the AI edits no person has reviewed since, a heat map and a review PDF with those edits shaded, and a PDF build from the clean copy measured against a page limit. |
| List the people behind the marks | [manuscript-mark-people](skills/manuscript-mark-people/SKILL.md) | The people in the repository, from its history and author lists, kept apart from AI models and bots, proposed for you to confirm, so that an unlisted name never counts as a person's review. |

You can request any of these independently. Editing a paragraph does not require a full manuscript
review. A full submission review includes reference checks where relevant.

**Each skill works across the whole paper by default for the task you request.** You can ask to work
through selected sections or review one stage at a time, and change that preference as you go.

## Start with your manuscript

Once the plugin is installed, share your manuscript with the assistant and describe what you want done.
You can use ordinary language or name a skill from the table above.

The skills read Markdown, plain text and LaTeX directly; with LaTeX, include the bibliography files,
because the reference checks read them. For Word or Google Docs, use a document connection your
assistant has, or provide an export, and for a passage edit paste the passage.

Add the context that matters to your request: a target journal, article type, publication budget or
deadline, for example. For journal selection, explain which additional analyses or experiments are
feasible. If you have already received an editorial decision, include the relevant comments. The
assistant uses what you provide and asks about missing facts that would change its answer.

On first use with a manuscript project, the assistant asks only for missing context: the authoritative
manuscript and supplements, connected code repositories (none or unknown are valid), and the folder in
which to save skill runs. Choices are saved in `.manuscript-skills.yaml` in that manuscript project and
reused by every skill. A later skill or revision does not restart the questions. An explicit request or
a material inconsistency, such as a missing source or inaccessible destination, prompts only the needed
question. Related papers can be linked without sharing or overwriting their separate choices.

Current conversation instructions override saved project choices; project choices override global
defaults in `~/.config/manuscript-skills/settings.yaml` on Linux. `project.py resolve SOURCE --json`
reads that hierarchy without changing it. A one-run override is not a lasting preference.

Every run has an index and one subfolder per applied skill. Reports, actual reader/referee responses,
checks, contradictions, blocked sources, failed attempts and before/after passages remain inspectable.
The reply links the index and reports. Failed commands survive a successful retry; unrun and incomplete
stages are labeled. `runs.py validate RUN --final` checks delivery artifacts and panel coverage. It
cannot establish scientific correctness or verify that the conversation actually displayed an excerpt.
See the shared [project and run contract](skills/manuscript-integrity-check/references/project-workflow.md)
for setup, command examples and the limits of these checks.

`reports: file` gives the headline and urgent findings in chat; `chat` and `both` show the whole report
there. The run evidence stays saved in every mode. The `edits` setting is the mode of an improvement
run: `propose` reports only, `conservative` (the default) applies routine corrections that preserve
meaning and proposes consequential argument, claim or numerical changes, and `apply` makes authorized
substantive edits too. Every mode ends with the corrected version as a separate file, so you can read the
whole improved paper before accepting it. Exact consequential before/after text is shown promptly in chat
even with file reports.

Whole-manuscript improvement now defaults to `peer_review: auto`: three formal referees plus a defender.
Save `on-request` or `off` for a different project preference. This does not expand focused tasks into
peer review. Story review has its own simulated readers: by default a skimmer, a potential user and an
informed outsider, or the audiences you save for the project (`project.py configure ROOT --reader
"clinician: ..." --reader ...`). Each reads in its own order, and the panel reports where each would
close the paper, not just where attention dipped. They do not replace scientific referees.

Questions do not stop independent work. The assistant collects proposals and missing facts while
finishing the checks and edits it can complete without your answers. If asynchronous questions are
available, it can ask while continuing; otherwise it presents the remaining decisions together after
that work is done. Only the dependent work waits, and silence never counts as approval. You can still
request a pause or a checkpoint after each section or stage.

## Improve a manuscript from draft to submission

Use `manuscript-improve` to coordinate the focused skills:

> Use manuscript-improve to improve this paper for submission. Review the claims and references, check
> applicable policies, recommend suitable journals, edit the prose and adapt the paper to the chosen
> journal. Use our existing context, show the before/after changes and identify any decisions I need
> to make.

A useful sequence is:

1. **Review the draft and references.** Identify unsupported claims, citation problems, inconsistent
   numbers, reporting gaps and missing material through the integrity, reference and reporting checks.
   The project's referee policy then supplies a simulated panel, automatically by default for this full workflow.
2. **Resolve scope and choose a journal.** Use policy-fit assessment where the study raises clinical,
   ethics or privacy questions, then order the preprint servers and journals that fit your research and
   publication budget into two ladders by your priorities, and adapt what every venue on them shares.
   Use your existing target if you have already chosen one.
3. **Revise the paper.** Correct supported problems and improve the prose while preserving the results
   and their qualifications. Identify substantive claim changes separately from language edits. Remove
   the formulaic AI phrasing the draft already has (deslop). Then check how the revised paper reads to
   its readers, against the version you started from, and repair the story within the direction you
   chose.
4. **Prepare for the chosen journal.** Apply its length, structure and section requirements and draft the
   required statements and submission materials.
5. **Check the changes and show them.** Verify affected citations, claims and submission requirements,
   build the corrected version (every applied edit and every proposal, one choice per contested
   passage, with track changes), and render the dashboard of what the run found, changed and left open.
6. **Finish for submission.** Once the code, data and results are final, archive the release, complete the
   declarations, the AI-use statement and the cover letter, and check the files you will upload. These
   items wait until then and do not hold up work on a draft.

The skills contribute to the same manuscript and share findings across these steps. Some tasks may
already be complete or unnecessary for your study. By default, the assistant works across the whole
paper and continues through the authorised stages. Preparing a manuscript does not itself submit it
to a journal. When a decision arrives, `manuscript-reviewer-response` takes over: it plans the revision
from the referees' comments, drafts the response letter and checks it against the revised manuscript.

For work that spans several sessions, the assistant can keep a small
[shared record](skills/manuscript-integrity-check/references/manuscript-record.md) beside the manuscript
with the chosen journal or the ladders, your priorities, completed checks and open issues, so that later
steps reuse earlier work. It is created when the work spans sessions, when journal selection records
your priorities and ladders, or when you ask for it. Everything you are meant to open (a saved report, a
ladder, a heat map, a response letter) stays in the project or its configured output folder. The run
retains the evidence behind its findings; unrelated downloads may still use temporary storage.

## Choose how to review the work

You can ask for review points when using an individual skill or the full workflow:

- **By section:** "Edit the whole paper, section by section. Show before/after changes for each section
  and wait for my response before moving on." You can also name a single subsection to work on.
- **By stage:** "Use manuscript-improve one stage at a time. Cover the whole paper at each stage and
  let me review the findings or changes before continuing."
- **Before applying edits:** "Prepare proposed changes separately. Show me the original and proposed
  text, and wait for me to accept them before updating the manuscript."
- **With an interview:** "Interview me about the decisions we need to make." This can cover journal
  priorities, scientific wording, restructuring or how to handle review findings. You can limit the
  interview to one decision or stage.

Before/after review uses a diff, tracked changes where available or the original and revised passage.
For a stage such as journal selection, you review the recommendations and tradeoffs. Accepted edits
and decisions carry into the next step; you can ask to revisit them. Section review, stage checkpoints
and interviews start when you request them. Otherwise, the assistant completes the whole-paper task
using the supplied context and asks only for missing information that changes the work.

## Requests you can reuse

For a prose edit:

> Edit the Discussion for clarity and readability. Preserve the claims, numbers, citations and
> uncertainty, and keep our voice. Show me what changed.

For deslop:

> Deslop the Discussion. Cut boilerplate and repeated AI phrasing while keeping our claims,
> uncertainty, numbers and citations. Show the consequential changes.

Use `manuscript-deslop` for a focused pattern check or cleanup, and `manuscript-prose-edit` for broader
language editing. You can also ask to identify the patterns without editing. If another plugin supplies
a humanizer, selecting `manuscript-deslop` identifies this plugin's manuscript-specific workflow.

For the review dashboard (manuscript-improve builds it at the end of every run):

> Visualize what this manuscript-improve run caught and changed so I can show my colleagues. Use the
> saved evidence, separate problems from edits, and show what remains open and what was not checked.

> Compare this run on v0.3 with our co-author's comments on the same version: which did it catch, which
> did it miss, and why.

For the story:

> Our paper got boring after two rounds of referee comments. Compare it with the first draft from a
> reader's point of view, then make it interesting again without dropping any caveat the referees made
> us add. Keep the privacy angle; if another angle would read better, give us options.

For references:

> Verify the references in this manuscript. Check whether the sources support the main claims in the
> Abstract and Discussion, and distinguish incorrect citations from sources you could not verify.

For journal selection:

> Suggest journals for this computational aging paper. We can reanalyse public datasets but have no
> wet-lab budget. Compare scientific fit, publication costs and review speed. We used AI to revise the
> text, so explain the relevant writing policies too.

Journal selection first asks a short batch of priorities (speed, reach, AI-policy burden, cost, who
pays the fee) unless you have already given them, and keeps them in the shared record. You can also ask
for a fuller interview: what AI did in each section, which AI-policy burdens you refuse, and where named
colleagues publish. Journal adaptation checks whether a target journal's AI policy has changed since it
was last read.

For adaptation to a journal:

> Prepare this manuscript for initial submission to [journal]. Apply its abstract and length rules,
> check the required statements and draft the cover letter. Use free-format submission if it is allowed.

For a submission review:

> Review this manuscript before submission to [journal]. Prioritise problems that could affect the
> scientific conclusions or prevent review. Separate required fixes from optional improvements.

For reporting standards and availability:

> Check this genetic-association paper against the reporting guidelines that apply to it, and check
> that every accession, repository and package in the availability statement can be found.

For a simulated referee review:

> Show me what three referees at [journal] would send back on this draft, then what we should fix
> first. Tell me which concerns I can fix in the text and which need new work.

Without a named journal, the referees review for the journal in your shared record, or for each of the
top three journals on your ladder.

For a response to referees:

> We received a major revision. Plan it from this decision letter, keep the referees' numbering and
> list the decisions we need to make. Later, draft the response letter and check it against the revised
> manuscript.

For revision marks, where the manuscript keeps them:

> Which passages has no one checked since the AI rewrote them? Give Anna a PDF with those passages
> highlighted, and list the paragraphs no review round has touched.

For a scope or ethics question:

> This paper evaluates an annotation tool using my own publicly released genome. Check which
> requirements apply and clarify the wording so it accurately describes the study and data.

The policy-fit skill also helps with preprint screening decisions, including papers referred between
bioRxiv and medRxiv, and drafts factual clarifications based on the notices you received.

## How to interpret the results

Reports quote the passage each finding is about and name its section, link anything you need to open (a
DOI, a database record, a journal's policy page), and are written in plain sentences. The work is grouped
by when you can do it: first the science and the evidence, then the writing, then what depends on the
chosen journal, and last what waits until the code, data and results are final, such as archive DOIs,
declarations, the AI-use statement and the cover letter. Those last items are not problems with a draft.

You decide how to handle a journal's policy. If something you ask for conflicts with a journal's rule,
for example a ban on drafting text with AI, the assistant still does it, names the conflict once with its
practical consequence and lists it with your other decisions.

Prose editing aims to preserve your scientific meaning, including uncertainty and limitations. The
assistant reviews the changes and uses checks that can flag altered numbers, citations and terminology,
and claims that became stronger or lost a qualifier. These checks help catch mistakes; you should still
review the edited text before using it. A request for "punchier" wording improves the prose without
raising the certainty of a claim.

The simulated referee panel shows objections early, while you can still act on them. The referees
review for a real journal whose pages were read for them, and each writes the report a referee would
send: a recommendation (accept, minor revision, major revision or reject), a summary, strengths, and
major and minor concerns. A second part turns those reports into your list of what to fix, in the order
above. Every concern quotes the passage it is about and is checked against the rest of the paper before
it reaches you. Because the panel has never been calibrated against real editorial decisions, it gives
no scores, acceptance odds or predicted editorial decision, and its recommendations are labelled as
coming from simulated referees. Concerns that need new analyses or data are listed for you to decide on;
nothing is added to the paper on your behalf.

Reporting guidelines are checked when they fit your study design; a missing checklist item is a
requirement only when your target journal asks for that guideline. Reference and availability checks
look up public identifiers online (DOIs, PMIDs, accessions, package names, and links written in the
text); for a reference without a working identifier, the reference's own text is searched in Crossref,
and a match stays a candidate for you to confirm. The rest of the manuscript is not sent anywhere. Data
under controlled access, such as dbGaP or EGA, is reported as restricted, which the check accepts as a
legitimate route.

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
exemptions. Optional AI-text detector checks run only when requested. Their scores measure style and are
often wrong: they cannot show who wrote a passage, and a low score guarantees nothing at submission. A
hosted detector requires your agreement before the manuscript is sent to that service.

## Installation

Install **manuscript-skills** as a plugin in Claude Code or Codex. The plugin includes all fifteen skills.

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
their dependencies install on first use. Building a PDF from a marked manuscript also needs
[pandoc](https://pandoc.org/) and [tectonic](https://tectonic-typesetting.github.io/), which uv does not
install. Ask the assistant to check the setup if needed. Looking up
references and current journal policies requires internet access.

## Development

`uv run pytest` runs the offline tests of every script. Behavioural evaluations of the skills, with
seeded manuscripts and clean controls, are described in [evals/README.md](evals/README.md). The survey of
related projects behind the current design is in [docs/](docs/skill-landscape-2026-10.md).

## Licence

[MIT](LICENSE). Journal policies remain governed by the journals' own published guidance. Design ideas
borrowed from other projects are credited in [NOTICE](NOTICE).
