# Readers first: why manuscript-story exists, and what it borrows (October 2026)

## The problem

Each skill in this plugin makes a manuscript safer: claims cannot rise, numbers cannot drift, referees'
objections are anticipated and answered. Together they had one blind spot. Nothing in the plugin worked
for the paper's readers, and several rules pushed against them:

- The skills mentioned referees or reviewers 687 times and readers 66 times.
- The prose guard failed an edit that removed a limiting word or a scope qualifier from a sentence, and
  let an edit that added one pass. Caveats could be added freely and never moved.
- The section guide told the Discussion to "end on the main limit" and the Conclusion to give "the finding
  and its main condition".
- Simulated referees' "fixable in text" items went to prose-edit with no question of where each addition
  should go.

Measured on one platform paper's own drafts (an early draft against the version after several
referee-driven rounds, with `reader_metrics.py`): the results grew from 11% to 22% of the body; negations
in the results rose from 0.39 to 0.69 per 100 words and the share of results sentences ending on a caveat
from 5% to 13%; the Conclusion went from no limiting words to about one in every hundred; "we" fell from
1.5 to 0.2 per 100 words in the Discussion. The later Abstract was far tighter, and the paper was more
correct. It had also lost its stake, its argument and every picture of what the tool produces.

## What the evidence says

- Narrative features of abstracts, connectedness above all, go with more citations (Hillier, Kelly &
  Klinger 2016, *PLoS ONE*, doi:10.1371/journal.pone.0167983; 732 abstracts, correlational, small effect).
- Abstracts rewritten in a more accessible style were read, understood and trusted better in an
  experiment with 170 readers (Freeling et al. 2021, *Front Psychol*, doi:10.3389/fpsyg.2021.714321).
- Jargon in titles and abstracts goes with fewer citations (Martínez & Mammola 2021, *Proc R Soc B*,
  doi:10.1098/rspb.2020.2581); readability of abstracts has fallen for a century (Plavén-Sigray et al.
  2017, *eLife*, doi:10.7554/eLife.27725).
- Narratives help non-specialists understand and engage (Dahlstrom 2014, *PNAS*,
  doi:10.1073/pnas.1320645111).
- Caveats do not cost trust; vague verbal hedging costs a little: quantified uncertainty had "only
  positive or null effects" across 48 studies (Gustafson & Rice 2020, doi:10.1177/0963662520942122);
  communicating uncertainty caused "only a small decrease in trust… mostly for verbal uncertainty" (van der
  Bles et al. 2020, *PNAS*, doi:10.1073/pnas.1913678117); hedged reporting made scientists look more
  trustworthy (Jensen 2008, doi:10.1111/j.1468-2958.2008.00324.x). All three used lay readers; no study
  we found measured hedge density in research papers with expert readers.
- Writing guides that agree with this: Gopen & Swan 1990 (*American Scientist* 78(6), the stress position
  at the end of a sentence); Mensh & Kording 2017 (doi:10.1371/journal.pcbi.1005619, one central
  contribution, stated in the title); Schimel 2012 (*Writing Science*, Opening, Challenge, Action,
  Resolution); Olson 2015 (And, But, Therefore; doi:10.7208/chicago/9780226270982.001.0001); Romano &
  Moore 2020 for software papers (doi:10.1371/journal.pcbi.1008390); and, as satire, Sand-Jensen 2007,
  "How to write consistently boring scientific literature" (doi:10.1111/j.0030-1299.2007.15674.x).

## Software papers that read well, and some that do not

Read on 2026-10-19 (full text unless marked): Nextstrain (doi:10.1093/bioinformatics/bty407) and MultiQC
(doi:10.1093/bioinformatics/btw354), both Bioinformatics Application Notes with a stake in the first
sentence and one vivid number; kallisto (doi:10.1038/nbt.3519, abstract only), a four-sentence template;
Interpretome (doi:10.1142/9789814366496_0033), closest to a local personal-genome tool, with a contrast a
reader keeps ("$1,000 genome", "$1,000,000 interpretation"); Impute.me (doi:10.3389/fgene.2020.00578),
which names and quantifies what it argues against; DeepVariant (doi:10.1038/nbt.4235, abstract only);
Bioconda (doi:10.1038/s41592-018-0046-7); NumPy (doi:10.1038/s41586-020-2649-2). Counterexamples that open
with sequencing costs or field history before the problem: VEP (doi:10.1186/s13059-016-0974-4), openSNP
(doi:10.1371/journal.pone.0089204) and GenomeChronicler (doi:10.3389/fgene.2020.518644); pgsc_calc
(doi:10.1038/s41588-024-01937-x) and OpenCRAVAT (doi:10.1200/CCI.19.00132) read as feature lists.

## Public skills on storytelling and reader-first editing

Surveyed on 2026-10-19; only repositories pushed on or after 2026-06-19 are kept. Very little exists, and
none of these projects measured whether readers found the result more interesting.

| Repository | Last push | Licence | What it offers | Used here |
|---|---|---|---|---|
| ipeirotis/blue-pencil | 2026-10-17 | MIT | "Maximize reader understanding, not textual polish"; hedges sorted into three kinds and moved, not deleted; no inline caveats in the Abstract and Introduction; a running example the editor "may not invent" | The caveat sort and placement rules |
| Yuan1z0825/nature-skills | 2026-10-19 | Apache-2.0 | "Every requested addition triggers a deletion check across the whole affected paragraph"; reader-or-referee test per sentence | The accretion check, in story tests and reviewer-response |
| Boom5426/Nature-Paper-Skills (anti-defensive-writing) | 2026-10-13 | MIT | "Most audit and defensive text is added during editing, not during drafting" | The premise of the readers-first rules |
| Kiterlin/anti-defensive-writing | 2026-10-17 | MIT | "Write as an author explaining an argument to the reader, not as an author negotiating with an imagined critic" | Same |
| Rimagination/good-story | 2026-06-28 | MIT | OCAR, ABT, CARS and Toulmin combined; one-sentence, gap-lock, memory and autobiography tests (it counts referees in its audience) | The four tests |
| Worigin0314/academic-defensive-writing-auditor | 2026-08-30 | MIT | A taxonomy of defensive caveats | Not used |
| kangning-huang/knhuang-research-skills | 2026-07-06 | MIT | "Transitions are NOT conjunctions" | The connected-sentences test |
| seandavi/scriptorium (argumentative-flow) | 2026-10-01 | MIT | Notes on narrative frameworks; keeps every hedge in place | Not used: it preserves the defensive draft |
| anthropics/skills (doc-coauthoring) | 2026-10-09 | not stated | "Test the doc with a fresh Claude (no context)" | The reader panel's independence, as an idea |
| hanlulong/econ-writing-skill | 2026-07-20 | MIT | Anti-patterns such as "bait-and-switch" and "travelogue" | Not used |

Ideas only, from projects without a licence: borgr/paper-sharpener ("readers scan for tension, not for
addition"), lyndonkl/claude (a "boredom budget"). Outside the window: kangning-huang/science_narrative_skills
(January 2026) and sulfierry/mcp's nature-science-narrative (2026-06-16).

## What changed in the plugin

- **manuscript-story** (new): the reader panel, `reader_metrics.py`, the story tests, comparisons with
  neighbours and exemplars, story edits within the authors' recorded direction, direction changes only
  as options, and three gates on every edit (the science guard, the journal's format and screening
  signals, the AI-writing check), with science first, the journal's format second and the story third.
- **author-priorities.md**: "Readers first, referees second", beside "authors first, journals second";
  the `edits` setting treats story edits that keep the recorded direction as routine for manuscript-story.
- **manuscript-record.md**: a `story` entry (direction, themes, readers, what readers should remember).
- **guard.py**: `--relocated`, so a caveat moved to a new or changed sentence elsewhere is reported as
  moved, not lost.
- **section-guide.md**: a stake before background, a headline before a result's numbers, endings on the
  next step rather than a caveat, captions that say what a figure shows.
- **manuscript-peer-review**: a `placement` for every text fix, and hand-offs to manuscript-story.
- **manuscript-reviewer-response**: where each change made for a referee goes, and the deletion check.
- **manuscript-improve**: a reading check after the revision stage.
