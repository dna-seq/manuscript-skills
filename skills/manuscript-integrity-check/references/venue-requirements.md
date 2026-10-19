# Venue requirements: what to check for the chosen venue

Used by Step 4 of the integrity check. Look the venue up first (from the skill directory,
`uv run --script ../manuscript-journal-adapt/scripts/venues.py show KEY`; then `journal-policies/`,
`publisher-policies.md` or `venues-and-preprints.md`), then re-check the live page under ground rule 5.
Apply only the chosen venue's rules for this article type and submission stage.
Reporting-guideline checklists and whether availability links resolve are `manuscript-reporting-check`'s;
ethics, consent, privacy and clinical scope are `manuscript-policy-fit`'s.

In the report these items sit in the last two stage groups of `author-priorities.md`: scope, limits, structure,
abstract format and the venue's checklist under "Once you have chosen the journal"; the AI-use statement,
availability statements, archives and other declarations under "Before submission, once the code is final",
which for a draft are not blockers. Quote the venue's rule with the URL of its page and the date it was read.

- **AI disclosure**: present in every place the venue asks (cover letter, Methods, Acknowledgements, a titled
  declaration, the supplement, figure captions), with the fields it requires (tool and version, dates, what it
  did, which sections, how the output was verified) **only where required**, and AI-assisted **code** described
  where this venue's policy asks. Report what is missing or misplaced; drafting and placing the statement is
  `manuscript-journal-adapt`'s. When what AI did conflicts with the venue's rule (a drafting ban, for example),
  that is one sentence among the decisions for the authors, not a required fix.
- **Author list** has no AI; no AI output cited as a primary source.
- **Availability**: which statements, deposits and licences the venue requires for this article type and
  stage; whether they resolve is `manuscript-reporting-check`'s. Do not demand a DOI, repository deposit or new
  test dataset when neither the paper's reproducibility nor the venue requires it.
- **Limits and structure**: abstract and body length, abstract headings, article-type rules. A return rule for
  overlength papers applies when the venue entry records one (`over_limit_return`), from the current page or,
  when the live page cannot be read to that section, from the most recent complete copy (`quoted_from` says
  which); say which in the report.
- **Validation and affordability**: record actual independent-cohort, biological-validation or other
  expensive study requirements, including scope and permitted computational alternatives. Surface an
  unmet requirement early, as a question for the authors of whether this venue is worth its cost to them, and
  use `manuscript-journal-select` to find feasible alternatives. Do not silently turn it into a new experiment
  for the author or confuse an independent existing dataset with new recruitment.
- **Figures**: distinguish primary data, research image processing and illustrations; apply the selected
  venue's actual rules and preserve accurate representation of the data.
- **Preprint overlap**: check the relevant venue's preprint and simultaneous-submission rules. Check a
  preprint server's current limits only if posting there is part of the task.
- **Double-blind review**: when the venue anonymises, run the package check with `--anonymous` and the
  author names (`submission-package.md`), then apply the venue's own rule on acknowledgements,
  self-citation and repository links.
