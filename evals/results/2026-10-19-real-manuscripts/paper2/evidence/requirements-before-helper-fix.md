# What the venues on this ladder ask for: BMC Bioinformatics, Bioinformatics (Original Paper), bioRxiv and arXiv

Each requirement is listed with the venues that ask for it; "every venue" means all of them. A venue missing from an item may simply not have been researched for it (see the last section), which is not the same as having no rule.

## Adapt now: one version serves every venue

- [ ] Length of the body: at most 5000 words, the limit of every venue that states one (Bioinformatics (Original Paper), 5000).
- Sections to add (one a single venue requires costs the others little):
  - [ ] Background (BMC Bioinformatics)
  - [ ] Implementation (BMC Bioinformatics)
  - [ ] Results (BMC Bioinformatics)
  - [ ] Discussion (if appropriate) (BMC Bioinformatics)
  - [ ] Conclusions (BMC Bioinformatics)
  - [ ] Availability and requirements (BMC Bioinformatics)
  - [ ] Declarations (BMC Bioinformatics)
  - [ ] Data availability (Bioinformatics (Original Paper))
  - [ ] Availability and Implementation (in the abstract) (Bioinformatics (Original Paper))
- Rules the editors check on arrival, to check against the draft:
  - [ ] ML papers validated by leave-one-out are editorially rejected (Bioinformatics (Original Paper))
  - [ ] New methods compared with state of the art (Bioinformatics (Original Paper))
  - [ ] Pre-screen returns papers of less significance (Bioinformatics (Original Paper))
  - [ ] All data on which the conclusions are based publicly available in stable public repositories (Supporting Data) (Bioinformatics (Original Paper))
  - [ ] Complete manuscript with research output, rather than tool announcement (bioRxiv)
  - [ ] Scope decision remains with screening editors (bioRxiv)
  - [ ] FAQ permits updates until journal publication, but About page says until formal acceptance; schedule substantive revisions before acceptance to satisfy both (bioRxiv)
  - [ ] At most 2 submissions per calendar month and 3 active per submitter; rejected ones count (arXiv)
  - [ ] CS review and position papers need a peer-reviewed version (journal ref and DOI) (arXiv)
  - [ ] A full English version is required (arXiv)
  - [ ] New submitters need an endorsement (institutional email alone no longer suffices) (arXiv)

## Choose per venue: the venues disagree

These wait until the venue is chosen, or follow the first rung of the ladder.

- Length of the abstract: the limits differ (BMC Bioinformatics, 350; Bioinformatics (Original Paper), 150 words). Writing to the shortest, 150 words, fits all of them; whether that cut is worth making before the choice is your decision.
- Abstract headings differ: BMC Bioinformatics: Background, Results, Conclusions; Bioinformatics (Original Paper): Motivation, Results, Availability and Implementation, Contact, Supplementary Information.
- Rules that only some venues state. Those that cost the others nothing (alt text, dataset citations) can be adopted now; a section order or a reference style waits for the choice:
  - Provide anonymisable reviewer testing and a data availability statement. Include the software requirements and the required declaration headings, using Not applicable where appropriate (BMC Bioinformatics)
  - The sections of an Original Paper in this order: Title page, Structured Abstract, Introduction, System and methods, Algorithm, Implementation, Discussion, References (Bioinformatics (Original Paper))
  - Alt text for every image and figure of the main article, in the manuscript file directly under its legend (Bioinformatics (Original Paper))
  - Supplementary Data submitted for review apart from the manuscript, with all its text, figures and tables in a single file, and referred to in the main text (Bioinformatics (Original Paper))
  - The funding in a section titled Funding, first in the Acknowledgements, as a sentence that begins "This work was supported by", with the full agency names and the grant numbers in square brackets (Bioinformatics (Original Paper))
  - Every public dataset cited in the reference list with its identifier, the citation beginning with the tag [dataset] (Bioinformatics (Original Paper))
  - A cover letter that explains why the paper suits the journal, and why the manuscript departs from the instructions wherever it does (Bioinformatics (Original Paper))
  - A declaration, at the first submission, of any author or contributor who is the journal's Editor-in-Chief, an editor or an editorial board member (Bioinformatics (Original Paper))
- Not needed until after the first review:
  - The reference style, Oxford SCIMED (Bioinformatics (Original Paper))

## At the end, once the code, data and results are final

Done earlier, these have to be done twice.

- Software and availability:
  - [ ] Availability and requirements block with archived DOI (BMC Bioinformatics)
  - [ ] Open-source licence recommended but not required (BMC Bioinformatics)
  - [ ] Source at a stable URL at submission (Bioinformatics (Original Paper))
  - [ ] Archived version (Zenodo, Software Heritage or Figshare) URL in the abstract (Bioinformatics (Original Paper))
  - [ ] Test data (Bioinformatics (Original Paper))
  - [ ] Install and run documentation (Bioinformatics (Original Paper))
  - [ ] Instructions to reproduce each figure (Bioinformatics (Original Paper))
- Where the AI-use statement goes (one statement, placed everywhere a venue asks):
  - [ ] Methods or a suitable alternative section (BMC Bioinformatics)
  - [ ] Cover letter (Bioinformatics (Original Paper))
  - [ ] Methods or Acknowledgements (Bioinformatics (Original Paper))
  - [ ] Supplementary materials (Bioinformatics (Original Paper))
  - [ ] In the manuscript (bioRxiv)
  - [ ] As for other computational methods (bioRxiv)
  - [ ] In the work (arXiv)
  - [ ] As for other methodology (arXiv)
- What the AI-use statement states:
  - [ ] How AI was used (BMC Bioinformatics)
  - [ ] Human oversight and verification (BMC Bioinformatics)
  - [ ] Author accountability (BMC Bioinformatics)
  - [ ] Tool (Bioinformatics (Original Paper))
  - [ ] Version (Bioinformatics (Original Paper))
  - [ ] How used (Bioinformatics (Original Paper))
  - [ ] Which parts (Bioinformatics (Original Paper))
  - [ ] Author oversight (Bioinformatics (Original Paper))
  - [ ] Use of generative AI tools (bioRxiv)
  - [ ] Significant use of text-to-text generative AI (arXiv)
- Extra work about AI:
  - [ ] Supplementary documentation of any LLM help that produced part of the content (Bioinformatics (Original Paper))

## AI writing rules on the list

- BMC Bioinformatics: AI help is allowed if declared, and language polish needs no declaration.
- Bioinformatics (Original Paper): the journal asks authors not to have AI draft text; correction aids are allowed.
- bioRxiv: AI help is allowed if declared, and language polish needs no declaration.
- arXiv: AI help is allowed if declared, and language polish needs no declaration.

The strictest is Bioinformatics (Original Paper)'s: the journal asks authors not to have AI draft text; correction aids are allowed. A manuscript written and declared to that rule keeps every venue on the list open; whether to write to it is your decision.

## Not researched yet

Read these on the venue's own author guidelines, and add what you find to the manuscript record's `venue_facts` so the next run includes it:

- BMC Bioinformatics (https://link.springer.com/journal/12859/submission-guidelines/software-article): the length of the body and the rules checked on arrival.
- bioRxiv (https://www.biorxiv.org/about/FAQ): the length of the body, the length of the abstract, the abstract headings, the required sections, the other rules of its author guidelines and its software and availability rules.
- arXiv (https://info.arxiv.org/help/moderation/index.html): the length of the body, the length of the abstract, the abstract headings, the required sections, the other rules of its author guidelines and its software and availability rules.

Abbreviations: BMC, BioMed Central; DOI, digital object identifier; LLM, large language model; ML, machine learning.
