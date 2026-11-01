# What a co-author's comments on Paper 1 v0.7 show the plugin missed (November 2026)

The `manuscript-improve` run on Paper 1 v0.7 of just-dna-lite (run `20261028T165906Z-154d8220`, started on
28 October 2026 on plugin 0.50.1) produced the version the authors released to their co-authors on Google Drive.
A senior co-author who works outside polygenic scores left 73 comments and 21 suggested edits on it, pulled on
1 November. The comments were left on the run's output, so they are a second reading of the text the run had just reviewed
and corrected, and they can measure the run the way a reference review does. This note says what the comments are
about, which of them the run had caught, and what to change in the skills. Release 0.51.0 makes the comparison a
feature: `comments.py gaps` and the gap report in the dashboard's Co-authors' comments tab. The verdict for every
comment is in the project's ledger,
[docs/manuscript/v0.7/comments.yaml](https://github.com/dna-seq/just-dna-lite/blob/main/docs/manuscript/v0.7/comments.yaml).

## In short

- **91 of the 94 items were judged** (three are questions the text already answers). The run had caught 22: 10 in
  full and 12 in part. It missed 66. Three more comments are on passages the run wrote itself.
- **Of the 66 misses, 45 were in a skill's remit and not looked at** and 11 were looked at and judged
  differently; 7 are the co-author's preferred wording and 3 are about the co-author's own author role, which only the
  authors could settle.
- **The largest group is text the co-author could not follow** (27 comments, most in Sections 3.2 to 4.3): terms used before
  they are defined ("what exactly is a site?", "light use", "page cache", T2T), sentences that do not parse, and
  numbers given without a reason ("why nine; why three?"). No reader in the run reads the methods for
  comprehension, and the prose stage reads only the sentences it edits.
- **Three passages the co-author could not follow were written by the run** to answer its own simulated referees: the quality
  score's formula ("it all looks arbitrary or overfitted"), the sentence on the untested FRAPOSA path ("Again,
  ???") and a bare "(Code Availability)" in Box 1 ("?"). The re-check confirmed each was accurate. Nothing checked
  that a reader could follow it.
- **What the run caught, it mostly left for the authors**: the Abstract's missing problem statement, a polygenic
  score defined only after the trait view, warm, full and cold runs used before they are defined. Each had a ready
  proposal; the co-author met the problem because the proposal was not applied.
- **Ten comments ask to call the first user group "researchers, including citizen scientists"** instead of
  "people", in Box 1, the overview, the Discussion and the Conclusion, with a "for research use only" line in the
  Abstract. No stage asked who the paper says its users are.
- **Related work**: the Introduction's comparators are from 2010 to 2016 ("nothing happening over the last 10
  years?"). The story stage judged the gap stated because Table S7 lists 23 tools.

## How this was checked

The ledger gives each comment, its anchor and its thread. The run's records came from the dashboard committed beside
the paper, which embeds the adjudicated inventory: 100 problems the run's own stages raised, six simulated referees'
concerns, the story tests, 72 dismissed flags, 36 checks that were not run and 181 edits. The run's folder itself
stayed on the computer that ran it. Each comment was read with its passage in the manuscript and matched by hand
(Claude, 1 November 2026), then checked with `comments.py gaps --check`. A comment counts as caught only when one of
the run's problems names the same thing; a problem of the same kind on a nearby sentence does not count, and a
dismissed flag never does. The worksheet `comments.py gaps` writes found the three passages the run wrote without
help (the comment's anchor sits in the new text of an applied edit and not in its old). "Partly" is a judgement and
can be argued either way for a few comments.

## What the comments are about

| Kind of comment | Comments | Caught | Partly | Missed | Written by the run | An example, quoted |
|---|---|---|---|---|---|---|
| Text the co-author could not follow | 27 | 4 | 1 | 20 | 2 | "what exactly is a site?" |
| Wording and grammar | 15 | | | 15 | | "uploaded to the Internet" (four places) |
| Who the users are | 10 | | | 10 | | "Researchers, incl. citizen scientists" for "People" |
| Questions a hostile referee would ask | 9 | 2 | 1 | 6 | | "does correlation with Plink results establish anything?" |
| Story and emphasis | 9 | 1 | 3 | 5 | | "I think most readers will NOT be much interested in speed." |
| Figures and numbers | 8 | 2 | 5 | 1 | | "a number is not a curve" |
| Authorship and the submission package | 6 | 1 | 1 | 4 | | a contribution line that is not authorship "by most definitions" |
| Rules and numbers without a reason | 4 | | 1 | 2 | 1 | "any reference/justification for the 4/7, 1%, etc???" |
| Related work | 3 | | | 3 | | "cite a few recent ones: they are the main comparators after all" |
| Total | 91 | 10 | 12 | 66 | 3 | |

## What the run caught, and why the co-author met it anyway

Ten comments name a problem one of the run's stages had raised: the Abstract has no problem statement (a sentence
was proposed), Section 3.2 shows the trait view before defining a polygenic score (a swap of two paragraphs was
proposed), Section 4.1 uses warm, full and cold runs before defining them (a reorder was proposed), agreement with
PLINK2 checks only the raw sum (two referees; left as a narrower claim or a new comparison), Table 1 gives no
variant counts for the ClinVar modules, the largest score difference is given only in raw units, "the Catalog" in
the Abstract is never named (the fix defined VCF and stopped there), and the contributions are not in CRediT roles.
None was fully resolved when the version went to the co-authors. Three had ready edits held for the authors: the
Abstract's sentence, the swap in Section 3.2 and the reorder of Section 4.1. The last two move paragraphs, which is
the authors' call, but defining a term where it is first used asks no decision; that edit could have been applied,
leaving the move as the proposal.

## The misses, by the skill whose remit covers them

Each count is of the comments the run did not catch in full (missed, partly caught or written by the run) whose
miss points at that skill; wording preferences and what only the authors could settle point at none.

1. **manuscript-story (23).** The readers read for the story: where they would stop, what they remember. None reads
   the methods and results asking "do I understand this sentence?". A scientist outside the field stopped at
   'rows' of a scoring file, "site", "light use", "page cache", T2T, a new measure introduced without saying why
   (the share of a score's variants matched), and a whole paragraph of Section 4.2 ("I didnt understand anything in
   this paragraph"). The connected-paragraphs test repaired two links in Section 1.1 and left three others the
   co-author found. The stage kept speed as a headline although only two of six readers remembered "about a
   minute", and it judged the related work as covered by Table S7 while the Introduction names only PLINK (2015),
   ANNOVAR (2010) and VEP (2016) and two commercial services without a citation. *Change:* a reader seat for the
   expert outside the field that reads Sections 2 to 4 sentence by sentence and lists every term used before it is
   defined, every sentence it cannot parse and every number given without its reason; and a related-work test that
   asks for the newest comparators in the main text, not only in a supplementary table.
2. **manuscript-prose-edit (13).** It reads only what it edits, and its report says so ("a full read of untouched
   text against the pattern catalogue" is listed as not done). "Model sites a variant-only VCF does not list are
   coded as homozygous reference, and sites whose alleles disagree with the model as missing." has been unchanged
   since v0.6; the co-author notes that a grammar checker cannot parse it either. Four suggestions add "to the
   Internet" after "uploaded", because "the genome does not have to be uploaded" leaves open where to. *Change:* a
   list-only pass over the whole text for sentences that do not parse, missing words and ambiguous references,
   without rewriting anything the stage was not asked to edit.
3. **manuscript-policy-fit (10).** The stage accepted the paper's research-and-education scope and dismissed the
   medical-device question on it, without noticing that Box 1 names lay "people with a genome from a sequencing
   provider" as the first user group. *Change:* check who the paper says its users are against the scope it claims,
   and say where they disagree.
4. **manuscript-integrity-check (7).** Limits stated without their cost: "a GRCh37 file would be joined at GRCh38
   coordinates without a warning" ("how bad is that?") and an indel written differently is not matched ("is that a
   problem?"). A claim with no pointer to where it is shown ("both engines compute the same score"). A list of MCP
   clients nobody tried: the stage listed the Cursor claim among the checks it did not run and raised no problem.
   A feature the code does not have ("self-exploration"). *Change:* for each stated limitation, ask what it costs the
   reader and whether the text says so; a claim the stage could not check becomes a problem that asks to soften it.
5. **manuscript-figures (6).** Caption wording it did not read for sense ("Only a dot's horizontal position is data",
   "height is the curve"), vector export for the one drawn figure, and what makes the third model in Figure 3 stand
   apart. *Change:* read each caption sentence against the figure as a reader would, and ask for vector export of
   drawn figures.
6. **manuscript-improve: the re-check (3, all written by the run).** The re-check asks whether each edit is accurate
   and answers its problem. It never asks whether a reader can follow the new text, and the three edits the
   co-author could not follow were all written to satisfy simulated referees. *Change:* the expert-outsider reader
   also reads every applied edit longer than a sentence; for an edit made for a referee, ask whether its detail
   belongs in the main text or the supplement.
7. **manuscript-peer-review (3).** The referees asked for the audit's thresholds so it can be repeated, not why four
   of seven test genomes, the outermost 1% or a 0.9 penalty were chosen. No referee asked why the coronary artery
   disease module has 27 variants when LongevityMap holds thousands. A concern about AI-assigned concepts was
   dismissed as an open author decision, and the concept-versus-trait-term wording was never questioned. *Change:*
   a referee asks for the reason behind every constant a method states, and for how complete each curated
   resource is.
8. **manuscript-journal-adapt (3).** It asked for contribution roles in a standard format, not whether each listed
   contribution meets authorship criteria (testing software and providing one's genome do not, under most
   definitions). It judged the AI-use statement complete, while the co-author would bring the substance of the AI
   note in the supplement into the paper. It left the length to the choice of journal without proposing to move
   technical paragraphs to the supplement, which the co-author asks for twice so the review task looks smaller.
9. **manuscript-reporting-check (2).** How the longevity module's weights follow from study quality, replication
   and significance is not described (the stage asked this only of the other expert modules), and a Pearson r of
   0.99999996 is reported without saying what it means for the scores.
10. **manuscript-deslop (1).** It looked at "extensible without code" and kept it as a list of requirements; the
    co-author did not know it means without writing code.

## What 0.51.0 adds

- `comments.py gaps LEDGER --inventory RUN/manuscript-dashboard/findings.json` (or the dashboard `.html` beside the
  paper) writes a worksheet: each comment with the run's applied edits that wrote its passage, and the problems,
  dismissed flags, unchecked items, referees' concerns and story tests nearest to it.
- `--merge GAPS.yaml` takes the verdicts into the ledger after checking them (never a dismissed flag or a problem
  the co-authors stage made from the comment, only applied edits, a reason and an owner for each miss); `--check`
  checks them again and lists what is not judged.
- `findings` carries the verdicts to the dashboard. The Co-authors' comments tab opens with "Did the run that
  produced v0.7 catch them?": caught, missed and written by the run, why the rest was missed, and the misses by the
  skill whose remit covers them; each comment shows its verdict with links to the run's problems and edits, and a
  filter shows the misses. The changes workbook gets a column "Did the run catch it".

For Paper 1 v0.7 the verdicts are in the ledger. The dashboard committed beside the paper was rendered before they
existed; rendering it again needs the run's folder, on the computer that ran it: run `comments.py findings` for
the ledger into the run's coauthors folder, then collect and render as manuscript-dashboard's SKILL.md says for a
reference that arrives after the corrected version was built.

## Suggested order

1. The expert-outsider reader, also reading the run's own longer edits (manuscript-story and the re-check): 23
   comments the run did not catch in full, and the three passages it wrote.
2. The list-only parse pass over the whole text (manuscript-prose-edit): five sentences that do not parse, four
   grammar slips and the four "uploaded" sentences.
3. Apply definitions where a term is first used, leaving paragraph moves as proposals (manuscript-improve): three of
   the caught comments would not have reached the co-author.
4. Limits with their cost, and unchecked claims as problems (manuscript-integrity-check).
5. Who the users are against the scope (manuscript-policy-fit).
6. The smaller ones: reasons for constants and the completeness of curated modules (peer review), authorship
   criteria (journal adaptation), caption sentences and vector export (figures).
