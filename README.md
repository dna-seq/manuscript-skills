# Manuscript Skills

Skills that help scientists prepare manuscripts for publication, for
[Claude Code](https://claude.com/claude-code) and [Codex](https://github.com/openai/codex) (AI assistants
that work with the files on your computer). They review a draft, check its references and figures,
simulate the referees of a target journal, edit the prose, choose and prepare for a journal, and answer
the referees after a decision. They work with manuscripts written with or without AI assistance.

Start with `manuscript-improve`. One request runs the relevant checks and edits across the whole paper
and ends with a corrected version and a dashboard of what the run found. For a single task, use
[one of the fifteen focused skills](#choose-the-task-you-need).

The aim is to help you publish sound research with less avoidable delay, expense and paperwork. You
decide which journal to pursue and how to handle uncertain or burdensome requirements. Made by
[DNA Seq](https://github.com/dna-seq) and released under the MIT licence.

## What a run gives you

![The Overview of a manuscript-improve dashboard: 114 confirmed problems, what to fix now, the journals to target, AI-policy red flags, the corrected version and the coverage of every skill](docs/images/dashboard-overview.png)

Every `manuscript-improve` run ends with `manuscript-dashboard.html`, one file that opens offline in a
browser. The dashboard above is from a run on draft v0.3 of a real software paper, Just-DNA-Lite. The
run found 114 confirmed problems, each counted once however many skills found it, and sorted them by
what to fix now. A co-author had reviewed the same draft separately; the run saw neither that review nor
any later version of the paper. Of the co-author's 125 points, the run found 79 (27 of them only in
part) and missed 46.

The dashboard is self-contained, so you can send it to a colleague as it is. The same review also comes
as a Word document: the corrected version as tracked changes signed by each stage, with the problems,
the questions for you and the reason for each edit as margin comments. Google Docs opens it with the
changes as suggestions. No question for you is ever written into the paper's text, where it could be
submitted by mistake.

<table>
<tr>
<td width="50%"><img src="docs/images/dashboard-manuscript.png" alt="The manuscript with each problem highlighted by severity and the skills' comments in the margin"><br><b>The paper itself</b>, each problem highlighted where a skill quoted it, with what is wrong and what to do beside it.</td>
<td width="50%"><img src="docs/images/dashboard-revised.png" alt="The corrected version as track changes, with the list of applied and proposed edits"><br><b>The corrected version</b> as track changes: routine fixes applied, every substantive change a proposal you accept or not.</td>
</tr>
<tr>
<td width="50%"><img src="docs/images/dashboard-journals.png" alt="The three chosen journals with their AI policies as icons"><br><b>The journals</b> chosen by your priorities, each AI rule shown as an icon, and a red flag for rules that can cost you, such as a ban on AI drafting or an AI detector.</td>
<td width="50%"><img src="docs/images/dashboard-reviewers.png" alt="The simulated reviewers' concerns, each with its suggestion and the adjudication's verdict"><br><b>The simulated reviewers</b>: a recommendation per journal, and every concern with its suggestion, whether it held up when checked against the paper, and who can act on it.</td>
</tr>
</table>

## How it differs from other academic-writing skills

Several popular skill collections also review, edit and reference-check papers. Compared with the
most-starred of them in October 2026 ([the comparison](docs/skill-landscape-2026-10.md#where-each-skill-stands-against-popular-skill-repos-2026-10-24)),
these parts have no counterpart there:

- **Which rules apply to the study.** [manuscript-policy-fit](skills/manuscript-policy-fit/SKILL.md)
  works out which clinical, ethics and privacy requirements apply, including to authors' own public
  genomes and to papers referred between bioRxiv and medRxiv, and drafts the clarification.
- **Journals ordered by the authors' priorities, AI rules included.**
  [manuscript-journal-select](skills/manuscript-journal-select/SKILL.md) ranks preprint servers and
  journals by speed, reach, cost and how strict their AI policies are, with the deciding rule quoted and
  linked.
- **Readers as well as referees.** [manuscript-story](skills/manuscript-story/SKILL.md) has simulated
  readers say where they would stop reading, then repairs the text without dropping a caveat.
- **AI edits no person has reviewed.** For manuscripts that keep revision marks,
  [manuscript-revision-marks](skills/manuscript-revision-marks/SKILL.md) shows which passages an AI or
  agent rewrote that no co-author has checked since.
- **A run measured against a human review.** Given a co-author's review of the same draft,
  [the dashboard](skills/manuscript-dashboard/SKILL.md) shows which of its points the run caught and which
  it missed.

Where other skills do the same job, these parts add a check:

- **Every edit is checked by a script**, sentence by sentence, for a stronger claim, a dropped qualifier
  or a changed number or citation.
- **The upload files are checked too:** hidden text and prompts aimed at AI reviewers, LaTeX
  comments, leaked keys and location data in figures.
- **Figures are judged as printed:** at the journal's column width, in greyscale and as colour-blind
  readers see them, against the caption, the text and the code that draws them.
- **Data and code availability is looked up:** each accession, archive DOI and package name must resolve.

## Quick start

1. **Install the plugin.** In Claude Code, run:

   ```bash
   claude plugin marketplace add dna-seq/dna-seq-claude-marketplace
   claude plugin install manuscript-skills@dna-seq
   ```

   In Codex, install **manuscript-skills** from the **DNA Seq Genomics** marketplace. The checks also
   need [uv](https://docs.astral.sh/uv/), a small tool that runs the plugin's Python scripts.
2. **Share the manuscript, its supplements and its code.** Start the assistant in the manuscript's
   folder or give it the file paths. Markdown, plain text and LaTeX (with its bibliography files) are
   read directly; for Word or Google Docs, provide an export or use a document connection the assistant
   has. With the code repository, the paper's numbers and descriptions of its software are checked
   against the code, results and run logs.
3. **Ask in plain words**, for example:

   > Use manuscript-improve to improve this paper for submission. Show the before/after changes and
   > identify any decisions I need to make.

   By default a run applies routine fixes and proposes every substantive change; story edits that keep
   the direction you chose count as routine. Ask for a report only if you want nothing applied.

On first use the assistant asks, in one batch, only for what it cannot find (the manuscript files, any
code repository and where to save the runs) and how you want it to work: how much it may change by
itself, whether full reports also appear in the chat, and whether to keep every intermediate file. Each
question comes with the recommended answer and the reason for it, so one "yes" accepts them all. The
answers are saved in `.manuscript-skills.yaml` beside your manuscript, and every skill reuses them.

## Choose the task you need

| Your task | Skill | What you get |
|---|---|---|
| Improve a manuscript from draft to submission | [manuscript-improve](skills/manuscript-improve/SKILL.md) | The skills below as one workflow, ending with the corrected paper (a separate file in the run folder, also shown as track changes), a dashboard, and the decisions left to you. |
| Improve the writing | [manuscript-prose-edit](skills/manuscript-prose-edit/SKILL.md) | Edits for clarity, grammar and your voice. Each sentence is checked: no claim grows stronger, no number, citation, scientific term, qualifier or null result changes, and no AI phrasing is added. |
| Remove AI phrasing ("deslop") | [manuscript-deslop](skills/manuscript-deslop/SKILL.md) | Stock LLM phrasing, boilerplate and empty rhetoric cut while the science and your voice stay, or only a list of the patterns. |
| Make the paper interesting to its readers | [manuscript-story](skills/manuscript-story/SKILL.md) | Simulated readers say where they would stop reading; edits then fix the opening, the result headlines and where caveats sit. The science and every caveat stay, and a change of direction is only ever offered as options. |
| Review the manuscript before submission | [manuscript-integrity-check](skills/manuscript-integrity-check/SKILL.md) | Unsupported claims, inconsistent numbers and statistics, reference problems, unfinished content, files that would leak private notes or hidden text, and submission requirements, with suggested fixes. |
| Check the references | [manuscript-reference-check](skills/manuscript-reference-check/SKILL.md) | Each reference's identity and authors, retractions, withdrawn preprints and preprints since published, and whether the sources support the claims that carry the paper, with the passage quoted. |
| Check reporting standards and availability | [manuscript-reporting-check](skills/manuscript-reporting-check/SKILL.md) | An item-by-item check against the reporting guidelines for your study design (CONSORT, STROBE, PRISMA, ARRIVE and others). It also checks that your data, code and software can be found, and how statistics are reported. |
| Review the figures and tables | [manuscript-figures](skills/manuscript-figures/SKILL.md) | Every figure seen as it will be printed (at the journal's column width, in greyscale and as colour-blind readers see it) and every table as it is set (width, units, precision, empty cells), in the paper and its supplement. Each is checked against its caption, the text, the order it is cited in and the code that draws it; main-text items get the full review, supplementary ones a lighter one. You get a verdict per item (keep, change, or move to or from the supplement) and the figures worth adding; your files are never overwritten. |
| Anticipate referees' objections | [manuscript-peer-review](skills/manuscript-peer-review/SKILL.md) | Reports from three simulated referees at your target journal, each quoting the paper, then what to fix first, including the work only you can do. No scores or acceptance odds. It can also draft your report when you are the referee. |
| Clarify study scope or policy requirements | [manuscript-policy-fit](skills/manuscript-policy-fit/SKILL.md) | Which clinical, ethics or privacy requirements apply, with the policy quoted and linked, and drafts of scope clarifications or replies to policy questions. |
| Choose where to preprint and submit | [manuscript-journal-select](skills/manuscript-journal-select/SKILL.md) | Two ranked lists ("ladders"), of preprint servers and of journals, ordered by your priorities: speed, reach, AI-policy burden, cost. Each venue is first checked for scientific fit, the validation you can afford, fees, review times and AI policies, with the deciding rule quoted and linked. |
| Prepare for a chosen journal | [manuscript-journal-adapt](skills/manuscript-journal-adapt/SKILL.md) | Length, structure and required statements adapted to the journal and shown before and after, plus submission materials and an AI-use disclosure where needed. |
| Answer referees and check the revision | [manuscript-reviewer-response](skills/manuscript-reviewer-response/SKILL.md) | A revision plan in the referees' own numbering with the decisions you need to make, a point-by-point response letter, and a check that the revision answers each comment. |
| Show colleagues what the review caught | [manuscript-dashboard](skills/manuscript-dashboard/SKILL.md) | The offline dashboard every improvement run ends with. Given a co-author's review of the same version, it shows what the run caught and why it missed the rest. |
| See who revised what, and which AI edits await review | [manuscript-revision-marks](skills/manuscript-revision-marks/SKILL.md) | For manuscripts with revision marks: notes in the Markdown or LaTeX source recording who rewrote each passage, when and why. The marks are checked and reported: which passages each review comment changed, in how many rounds and by whom, which AI edits no person has reviewed and which prose no round has read. You also get a heat map, a review PDF with those edits shaded, and a PDF measured against a page limit. |
| List the people behind the revision marks | [manuscript-mark-people](skills/manuscript-mark-people/SKILL.md) | The people in the repository, from its history and author lists, kept apart from AI models and bots. You confirm the list, so an unlisted name never counts as a person's review. |
| Have more than one AI model read the paper | [manuscript-other-models](skills/manuscript-other-models/SKILL.md) | Only when you ask: the simulated referees and readers also read on another model, through the command-line agents you already use and pay for (from Claude Code on Codex, from Codex on Claude Code, or on Gemini), without API keys. Each seat runs in a fresh session that sees only its own copy of the paper, and every report says which model wrote it. |

manuscript-improve runs the other skills as its stages, so you do not need to run them first. Each
skill also works on its own when you want only that service: a paragraph edit needs no full manuscript
review, and a full submission review includes the reference checks where relevant. Skills cover the whole paper by default;
you can ask for selected sections or one stage at a time instead.

## What leaves your computer

- Reference and availability checks look up public identifiers online: DOIs, PMIDs, accessions,
  package names and links in the text. A reference without a working identifier is searched in Crossref
  by its own text. Nothing else from the manuscript is sent.
- Journal requirements are read from the journals' own pages.
- AI-text detector checks run only when you ask. The default detector runs on your computer; a hosted
  one requires your agreement before the manuscript is sent to it.
- Simulated referees and readers run on a second AI model only when you ask for it by name or save it for
  the project. The reading copy of the paper then goes to that model's provider, under your own account
  with its command-line agent.
- Reports, the corrected version and the dashboard are saved in the manuscript project or the output
  folder you chose, with the evidence behind each finding. Unrelated downloads may still use temporary
  storage.

## What a run leaves in your folder

Each run gets its own folder, by default under `reviews/` in the manuscript's folder. It holds:

- the run index (`README.md`), which links everything below;
- each skill's report and, for an improvement run, the dashboard and the corrected version of the paper;
- the evidence behind each finding: every simulated referee's and reader's report, each check and its
  output, the commands that ran and the before and after of each edit.

The evidence is many files, often more than a hundred for one skill. It is kept because the work depends
on it: a resumed run and the dashboard read it instead of repeating the work, and you can trace any
finding to the check, referee or reader behind it. This is the recommended setting, `keep: everything`.
If you only want to see the outcome, choose `keep: results`: once a run is finished, everything except
the index, the reports, the dashboard and the corrected version is packed into one `evidence.zip` in the
same folder, and unpacked again if the run continues. Nothing is deleted. The assistant asks which you
prefer on first use; to change it later, say "keep only the results" or "keep everything".

What you open goes beside the manuscript as well, named after it:

- `paper.dashboard.html`, the dashboard of the latest run (each run folder keeps its own);
- `paper.review.docx`, the same as a Word document with tracked changes and comments. If you already
  have one, the assistant asks before replacing it, since you may have commented in it;
- `paper.proposed.md`, the corrected version;
- from journal selection, the journal ladder, the venue requirements and the shared record.

```
paper/
├── paper.md                  your manuscript
├── paper.dashboard.html      the latest run's dashboard
├── paper.review.docx         the same in Word, tracked changes and comments
├── paper.proposed.md         the corrected version
└── reviews/
    └── 20261024T101500Z-3f2a91c0/   one folder per run: index, reports, evidence
```

## More details

<details>
<summary><b>Example requests</b></summary>

For a prose edit:

> Edit the Discussion for clarity and readability. Preserve the claims, numbers, citations and
> uncertainty, and keep our voice. Show me what changed.

For deslop:

> Deslop the Discussion. Cut boilerplate and repeated AI phrasing while keeping our claims,
> uncertainty, numbers and citations. Show the consequential changes.

Use `manuscript-deslop` for a focused pattern check or cleanup, and `manuscript-prose-edit` for broader
language editing; either can list the patterns without editing. If another installed plugin also offers
a "humanizer", name `manuscript-deslop` to get this plugin's version, written for manuscripts.

For the review dashboard (manuscript-improve builds it at the end of every run):

> Visualize what this manuscript-improve run caught and changed so I can show my colleagues. Use the
> saved evidence, separate problems from edits, and show what remains open and what was not checked.

> Compare this run on v0.3 with our co-author's comments on the same version: which did it catch, which
> did it miss, and why.

> Give me the corrected version as a Word document with the review as comments, so my co-authors can
> accept or reject each change.

For the figures:

> Check our figures as they will look in Bioinformatics: can every label be read in print, do the
> numbers match the text, and which figures should go to the supplement? Our plotting code is in
> analysis/. Don't change the figure files.

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
pays the fee) unless you have already given them, and keeps them in the shared record. You can ask for a
fuller interview instead: what AI did in each section, which AI-policy burdens you refuse, and where
named colleagues publish. Journal adaptation checks whether a target journal's AI policy has changed
since it was last read.

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

</details>

<details>
<summary><b>The full workflow, step by step</b></summary>

A request that names every stage:

> Use manuscript-improve to improve this paper for submission. Review the claims and references, check
> applicable policies, recommend suitable journals, edit the prose and adapt the paper to the chosen
> journal. Use our existing context, show the before/after changes and identify any decisions I need
> to make.

The stages:

1. **Review the draft and references.** The integrity, reference and reporting checks find unsupported
   claims, citation problems, inconsistent numbers, reporting gaps and missing material. A panel of
   simulated referees reviews the draft too, by default for this full workflow. Every figure is looked
   at as it will be printed and checked against its caption, the text and its code.
2. **Resolve scope and choose a journal.** Where the study raises clinical, ethics or privacy questions,
   the policy-fit assessment says which rules apply. The preprint servers and journals that fit your
   research and publication budget are then ordered into two ladders by your priorities, and the
   sections every venue on them shares are adapted. An existing target is used if you have one.
3. **Revise the paper.** Supported problems are corrected and the prose improved, with the results and
   their qualifications preserved; substantive claim changes are kept apart from language edits. Then
   the formulaic AI phrasing the draft already has is removed (deslop), and the story is checked against
   the version you started from and repaired within the direction you chose.
4. **Prepare for the chosen journal.** Its length, structure and section requirements are applied, and
   the required statements and submission materials drafted.
5. **Check the changes and show them.** The corrected version is built with every applied edit and
   every proposal as track changes, with one choice per contested passage. The affected citations,
   claims and submission requirements are then verified in it, and the dashboard shows what the run
   found, changed and left open.
6. **Finish for submission.** Once the code, data and results are final: archive the code release with a
   DOI, complete the declarations, the AI-use statement and the cover letter, and check the files you
   will upload. These items wait until then and do not hold up work on a draft.

The skills work on the same manuscript and share findings across these stages. Some stages may already be
done or unnecessary for your study. Preparing a manuscript does not submit it to a journal. When a
decision arrives, `manuscript-reviewer-response` takes over: it plans the revision from the referees'
comments, drafts the response letter and checks it against the revised manuscript.

For work that spans several sessions, the assistant can keep a small
[shared record](skills/manuscript-integrity-check/references/manuscript-record.md) beside the manuscript:
the chosen journal or the ladders, your priorities, completed checks and open issues, so later steps
reuse earlier work. It is created when the work spans sessions, when journal selection records your
priorities and ladders, or when you ask for it.

</details>

<details>
<summary><b>Stopping to review: by section, by stage, or before edits</b></summary>

By default the assistant completes the whole-paper task from the context you gave and asks only for
missing information that changes the work. You can ask it to stop for review instead, with a single
skill or the full workflow:

- **By section:** "Edit the whole paper, section by section. Show before/after changes for each section
  and wait for my response before moving on." You can also name a single subsection to work on.
- **By stage:** "Use manuscript-improve one stage at a time. Cover the whole paper at each stage and
  let me review the findings or changes before continuing."
- **Before applying edits:** "Prepare proposed changes separately. Show me the original and proposed
  text, and wait for me to accept them before updating the manuscript."
- **With an interview:** "Interview me about the decisions we need to make." This can cover journal
  priorities, scientific wording, restructuring or how to handle review findings, or only one decision
  or stage.

Changes are shown as a diff, as tracked changes where available, or as the original and revised passage;
for a stage such as journal selection, you review the recommendations and tradeoffs. Accepted edits and
decisions carry into the next step, and you can ask to revisit them.

While it waits for your answers, the assistant finishes the checks and edits that do not depend on them.
If it can ask while it works, it does; otherwise it presents the remaining decisions together at the end.
Only the dependent work waits, and silence never counts as approval.

</details>

<details>
<summary><b>What to share and which context to add</b></summary>

The skills read Markdown, plain text and LaTeX directly; with LaTeX, include the bibliography files,
because the reference checks read them. For Word or Google Docs, use a document connection your
assistant has or provide an export. For a passage edit, paste the passage.

Include the supplements and, when the paper describes software or analyses, its code repository. The
simulated referees and the reference check read the supplementary files, including their reference
lists. With the repository, a number that matches no table, a quoted version or a description of what
the software ships is checked against the project's own files (benchmark tables, run logs, release tags,
the code that writes the output) before it is reported, and the assistant asks you only what those files
leave open. The code is context for the review; the skills do not edit it.

Add the context that matters to your request, for example a target journal, article type, publication
budget or deadline. For journal selection, say which additional analyses or experiments are feasible.
If you have already received an editorial decision, include the relevant comments. The assistant uses
what you provide and asks about missing facts that would change its answer.

</details>

<details>
<summary><b>How to read the results, and their limits</b></summary>

Reports quote the passage each finding is about, name its section, and link anything you need to open
(a DOI, a database record, a journal's policy page). The work is grouped by when you can do it: first
the science and the evidence, then the writing, then what depends on the chosen journal, and last what
waits until the code, data and results are final, such as archive DOIs, declarations, the AI-use
statement and the cover letter. Those last items are not problems with a draft.

You decide how to handle a journal's policy. If something you ask for conflicts with a journal's rule,
for example a ban on drafting text with AI, the assistant still does it, names the conflict once with its
practical consequence and lists it with your other decisions.

Prose editing aims to preserve your scientific meaning, including uncertainty and limitations. The
checks can flag altered numbers, citations and terminology, and claims that became stronger or lost a
qualifier. They help catch mistakes; review the edited text before you use it. A request for "punchier"
wording improves the prose without raising the certainty of a claim.

The simulated referees show objections early, while you can still act on them. Each reviews for a real
journal whose pages were read for it, and writes the report a referee would send: a recommendation
(accept, minor revision, major revision or reject), a summary, strengths, and major and minor concerns.
Every concern quotes the passage it is about and is checked against the rest of the paper before it
reaches you, and a second part turns the reports into your list of what to fix, in the order above. The
panel has never been calibrated against real editorial decisions, so it gives no scores, acceptance odds
or predicted decision, and its recommendations are labelled as coming from simulated referees. Concerns
that need new analyses or data are listed for you to decide on; nothing is added to the paper on your
behalf. The story skill's simulated readers do not replace scientific referees either.

Reporting guidelines are checked when they fit your study design; a missing checklist item is a
requirement only when your target journal asks for that guideline. Data under controlled access, such
as dbGaP or EGA, is reported as restricted, which the availability check accepts as a legitimate route.

Reference checking keeps a source's identity apart from its support for a particular sentence: a DOI
that resolves to the right paper does not establish that the paper supports your claim. The assistant
reads the relevant source material and says what it could not verify; a failed lookup alone is not
evidence that a reference was invented. A Crossref match for a reference without a working identifier
stays a candidate for you to confirm.

Journal coverage is strongest in bioinformatics, genomics, genetics and aging research. The catalogue
also includes preprint servers and policy notes for machine-learning conferences. Entries have sources
and dates, but some are incomplete and policies change, so the assistant checks the current requirements
that affect its recommendations and reports material uncertainties. Review-time comparisons distinguish
initial editorial decisions from decisions after external peer review.

For ethics and privacy questions, the assessment depends on what the study actually did, the data used
and the chosen journal. Public reanalysis, an author's voluntary release of their own data and research
involving recruited participants can raise different requirements. Applicable exceptions are considered;
a missing declaration alone does not establish that an approval was required.

AI-use statements draw on your account of what the tools did and the journal's required fields and
exemptions. Detector scores measure style and are often wrong: they cannot show who wrote a passage,
and a low score guarantees nothing at submission.

</details>

<details>
<summary><b>Settings and saved runs</b></summary>

On first use with a manuscript project, the assistant saves your answers in `.manuscript-skills.yaml`
in that project, and every skill reuses them, so a later skill or revision does not restart the
questions. Only what you answered is saved: a setting you skipped uses its default, unsaved, until you
choose. It asks again only when you request it or something no longer matches, such as a missing
source or a destination it cannot reach. Related papers can be linked without sharing or overwriting
their separate choices.

Ask the assistant to change a setting for one request or for the project. What you say in the
conversation overrides the project's saved choices, and those override your global defaults in
`~/.config/manuscript-skills/settings.yaml` on Linux. A one-run override is not a lasting preference.

| Setting | Choices (default first) | What it changes |
|---|---|---|
| `edits` | `conservative`, `propose`, `apply` | How much an improvement run changes by itself. `conservative` applies routine corrections that preserve meaning (for the story stage, also edits that keep the direction you recorded) and proposes consequential argument, claim or numerical changes; `propose` only reports; `apply` makes authorised substantive edits too. Every mode ends with the corrected version as a separate file, so you can read the whole improved paper before accepting it, and exact consequential before/after text is shown promptly in the chat, even with file reports. |
| `reports` | `file`, `chat`, `both` | `file` saves each report and gives the headline and urgent findings in the chat; `chat` and `both` show the whole report there. The run evidence is saved in every mode. |
| `keep` | `everything`, `results` | What stays in a run's folder once it ends. `everything` keeps every intermediate file, which later steps and the dashboard read and which let you trace each finding; `results` keeps the index, the reports, the dashboard and the corrected version, and packs the rest into `evidence.zip` (see [What a run leaves in your folder](#what-a-run-leaves-in-your-folder)). |
| `peer_review` | `auto`, `on-request`, `off` | Whether a whole-manuscript improvement includes the simulated referee panel: three referees plus a defender, who tests their concerns against the paper. Focused tasks never expand into peer review. |
| `readers` | a skimmer, a potential user and an informed outsider | Who reads the paper for `manuscript-story`. Each reads in its own order and says where it would close the paper, not just where attention dipped. Save your own audiences with `project.py configure ROOT --reader "clinician: ..." --reader ...`. |
| `other_models` | none | Other models the simulated referees, readers and critics also run on, through [manuscript-other-models](skills/manuscript-other-models/SKILL.md): `project.py configure ROOT --other-model codex/gpt-5.6-sol`; `--one-model` returns to the host model alone. Every seat on another model sends the reading copy to its provider. |

Every run has an index and one subfolder per applied skill. Reports, the simulated readers' and
referees' actual responses, checks, contradictions, blocked sources, failed attempts and before/after
passages stay there to inspect, and the assistant's reply links the index and reports. Failed commands
are kept after a successful retry, and stages that did not run or did not finish are labelled.
`runs.py validate RUN --final` checks the delivered files and panel coverage; it cannot establish
scientific correctness or verify that the conversation actually displayed an excerpt.
`project.py resolve SOURCE --json` shows the settings in force without changing them. The shared
[project and run contract](skills/manuscript-integrity-check/references/project-workflow.md) has setup,
command examples and the limits of these checks.

</details>

<details>
<summary><b>Other ways to install, and what else the checks need</b></summary>

To install in Claude Code directly from this repository instead of the DNA Seq marketplace:

```bash
claude plugin marketplace add dna-seq/manuscript-skills
claude plugin install manuscript-skills@manuscript-skills
```

The plugin installs all seventeen skills. The automated checks need [uv](https://docs.astral.sh/uv/) on
the computer running the assistant; their dependencies install on first use. Building a PDF from a
marked manuscript also needs the document tools [pandoc](https://pandoc.org/) and
[tectonic](https://tectonic-typesetting.github.io/), which uv does not install. Looking up references
and current journal policies requires internet access. Ask the assistant to check the setup if needed.

</details>

## Development

`uv run pytest` runs the offline tests of every script. Behavioural evaluations of the skills, with
seeded manuscripts and clean controls, are described in [evals/README.md](evals/README.md). The survey of
related projects behind the current design is in [docs/](docs/skill-landscape-2026-10.md).

## Licence

[MIT](LICENSE). Journal policies remain governed by the journals' own published guidance. Design ideas
borrowed from other projects are credited in [NOTICE](NOTICE).
