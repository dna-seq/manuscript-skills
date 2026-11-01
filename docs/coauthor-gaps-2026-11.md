# What two co-authors' comments on Paper 1 v0.7 show the plugin missed (November 2026)

The `manuscript-improve` run on Paper 1 v0.7 of just-dna-lite (run `20261028T165906Z-154d8220`, started on
28 October 2026 on plugin 0.50.1) produced the version the authors released to their co-authors on Google Drive.
Two co-authors commented on it by 1 November: Georg Fuellen, a senior bioinformatician who works outside polygenic
scores (73 comments and 23 suggested edits), and Livia Zaharia, one of the two people whose genomes the paper
analyses (7 comments and 5 suggested edits, and replies on three of Georg's). The comments were left on the run's
output, so they are a second reading of the text the run had just reviewed and corrected, and they measure the run
the way a reference review does. This note says, for each co-author, what the comments are about and which of
them the run had caught, then what to change in the skills. Release 0.51.0 made the comparison a feature
(`comments.py gaps`, the gap report in the dashboard's Co-authors' comments tab) and 0.52.0 groups it by
co-author. The verdict for every comment is in the project's ledger,
[docs/manuscript/v0.7/comments.yaml](https://github.com/dna-seq/just-dna-lite/blob/main/docs/manuscript/v0.7/comments.yaml).

## In short

| | Judged | Caught in full | Partly | Missed | On passages the run wrote |
|---|---|---|---|---|---|
| Georg Fuellen | 93 | 10 | 12 | 68 | 3 |
| Livia Zaharia | 11 | 2 | 2 | 7 | 0 |
| Both | 104 | 12 | 14 | 75 | 3 |

- **Of the 75 misses, 48 were in a skill's remit and not looked at** and 13 were looked at and judged differently;
  10 are a co-author's preferred wording and 4 are about authorship marks, which only the authors could settle.
- **Georg's largest group is text the reader could not follow** (27 comments, most in Sections 3.2 to 4.3): terms
  used before they are defined ("what exactly is a site?", "light use", "page cache", T2T), sentences that do not
  parse and numbers given without a reason ("why nine; why three?"). No reader in the run reads the methods for
  comprehension, and the prose stage reads only the sentences it edits.
- **Three passages Georg could not follow were written by the run** to answer its own simulated referees: the
  quality score's formula ("it all looks arbitrary or overfitted"), the sentence on the untested FRAPOSA path
  ("Again, ???") and a bare "(Code Availability)" in Box 1 ("?"). The re-check confirmed each was accurate. Nothing
  checked that a reader could follow it.
- **Livia's comments are about the opening**: the Abstract should first say what the paper presents and name the
  companion paper, abbreviations should be spelled out, the polygenic-score sentence needs rewording for a reader
  new to it, and the Introduction's first paragraph needs a link between its two sentences.
- **The two co-authors meet on two points and part on two.** Both found the missing link in the Introduction's
  first paragraph and the undefined abbreviations. Both want the Abstract to open differently, in different ways (a
  problem statement first, or what the paper presents), and they name the first user group in opposite directions
  ("researchers, including citizen scientists" against "users", genomic enthusiasts included). No stage asked who
  the paper says its users are.
- **What the run caught, it mostly left for the authors**: the Abstract's missing problem statement, a polygenic
  score defined only after the trait view, warm, full and cold runs used before they are defined, the undefined
  abbreviations of the Abstract. The co-authors met these because the proposals or fixes were not applied in full.

## How this was checked

The ledger gives each comment, its anchor and its thread, pulled from the v0.7 Google Doc with `rounds.py pull`
(Georg's on the morning of 1 November, Livia's that evening). The run's records came from the dashboard committed
beside the paper, which embeds the adjudicated inventory: 100 problems the run's own stages raised, six simulated
referees' concerns, the story tests, 72 dismissed flags, 36 checks that were not run and 181 edits. The run's folder
itself stayed on the computer that ran it. Each comment was read with its passage in the manuscript and matched by
hand (Claude, 1 November 2026), then checked with `comments.py gaps --check`. A comment counts as caught only when
one of the run's problems names the same thing; a problem of the same kind on a nearby sentence does not count, and
a dismissed flag never does. The worksheet `comments.py gaps` writes found the three passages the run wrote without
help (the comment's anchor sits in the new text of an applied edit and not in its old). "Partly" is a judgement and
can be argued either way for a few comments.

Two of Georg's suggestions came back from the evening pull as new items because the Doc had changed under them:
the author-line edit without the asterisk part someone accepted, and "Researchers, incl. citizen scientists" after
Livia changed "incl." to "including". They are judged like the originals. Four comments are not judged: three of
Georg's and one of Livia's ask for nothing (questions the text answers, and Livia's note explaining one of the suggested edits). Six
open points the v0.6 run carried into the ledger are not co-authors' comments and stay unjudged.

## Georg Fuellen's comments

| Kind of comment | Comments | Caught | Partly | Missed | Written by the run | An example, quoted |
|---|---|---|---|---|---|---|
| Text the reader could not follow | 27 | 4 | 1 | 20 | 2 | "what exactly is a site?" |
| Wording and grammar | 15 | | | 15 | | "uploaded to the Internet" (four places) |
| Who the users are | 11 | | | 11 | | "Researchers, incl. citizen scientists" for "People" |
| Questions a hostile referee would ask | 9 | 2 | 1 | 6 | | "does correlation with Plink results establish anything?" |
| Story and emphasis | 9 | 1 | 3 | 5 | | "I think most readers will NOT be much interested in speed." |
| Figures and numbers | 8 | 2 | 5 | 1 | | "a number is not a curve" |
| Authorship and the submission package | 7 | 1 | 1 | 5 | | a contribution line that is not authorship "by most definitions" |
| Rules and numbers without a reason | 4 | | 1 | 2 | 1 | "any reference/justification for the 4/7, 1%, etc???" |
| Related work | 3 | | | 3 | | "cite a few recent ones: they are the main comparators after all" |
| Total | 93 | 10 | 12 | 68 | 3 | |

Georg's misses point at the story stage (23), the prose stage (13), policy fit (11), the integrity check (7),
figures (6), the re-check of the run's own edits (3), peer review (3), journal adaptation (3), the reporting check
(2) and the deslop stage (1).

## Livia Zaharia's comments

| Comment, in plain words | Verdict | What the run had |
|---|---|---|
| Spell out PGS where the Abstract first uses it | Caught | The story stage flagged the Abstract's undefined abbreviations; the fix spelled out VCF only |
| Define every abbreviation before using it ("stephanie and benjamin nagged me") | Caught | The same finding |
| Open the Abstract with what the paper presents and name the companion paper | Partly | The story stage put the Abstract's opening to the authors and recommended keeping it |
| Reword the polygenic-score sentence of the Abstract for a reader new to it | Partly | The Catalog flagged as undefined, not that the sentence never says what a score adds up |
| The draft note on the two papers is convoluted; split it into simple sentences | Missed | Left as a working note that leaves before submission |
| A sentence linking the researchers' and the consumers' sentences in Section 1.1 | Missed | The connected-paragraphs test repaired other links in Section 1.1 and passed this one (Georg found it too) |
| "both individuals and regulations" in the privacy sentence | Missed | Not read by the prose stage (Georg questioned the same "and") |
| Call the first user group users, not researchers | Missed | No stage asked who the users are |
| Rename "Background and Significance" to "The problem" | Missed (a preference) | JAMIA Open asks for the heading as it is |
| Join the two sequencing-cost sentences into one contrast | Missed (a preference) | |
| "including" for Georg's "incl." | Missed (a preference) | |

Livia's replies on Georg's comments add proposals the ledger now carries: "uploaded to a publicly accessible
location" instead of "uploaded to the Internet", "without the coding skills to edit the code directly" for
"without code", and that modules have versions, so a new version of a module reaches users without a software
release.

## Where the two co-authors agree and disagree

- **The Introduction's first paragraph** goes from researchers to consumers with no link: Georg ("there no real
  'glue' between these two sentences") and Livia (a suggested sentence, "i added this to make the connection").
- **Abbreviations**: Livia asks for every one to be spelled out; Georg stopped at T2T and asked "which Catalog?".
- **The Abstract's opening**: Georg asks for a problem statement first, Livia for what the paper presents and its
  companion paper. One sentence of each would answer both.
- **The first user group**: Georg would call it "researchers, including citizen scientists", Livia "users", since
  "researchers imply that they have some more knowledge in the area" and the group includes genomic enthusiasts.
  This is the authors' decision; the run never raised it.

## What the run caught, and why the co-authors met it anyway

Twelve comments name a problem one of the run's stages had raised: the Abstract has no problem statement (a
sentence was proposed), Section 3.2 shows the trait view before defining a polygenic score (a swap of two paragraphs
was proposed), Section 4.1 uses warm, full and cold runs before defining them (a reorder was proposed), agreement
with PLINK2 checks only the raw sum (two referees; left as a narrower claim or a new comparison), Table 1 gives no
variant counts for the ClinVar modules, the largest score difference is given only in raw units, the contributions
are not in CRediT roles, and the Abstract's abbreviations are undefined (Georg's "which Catalog?" and both of Livia's
abbreviation comments; the fix spelled out VCF and stopped there). None was fully resolved when the version went to
the co-authors. Three had ready edits held for the authors: the Abstract's sentence, the swap in Section 3.2 and the
reorder of Section 4.1. The last two move paragraphs, which is the authors' call, but defining a term where it is
first used asks no decision; that edit could have been applied, leaving the move as the proposal. The abbreviation
fix is the clearest case: finishing it needed no one.

## The misses, by the skill whose remit covers them

Each count is of the comments the run did not catch in full (missed, partly caught or written by the run) whose miss
points at that skill, both co-authors together; wording preferences and what only the authors could settle point at
none.

1. **manuscript-story (26: Georg 23, Livia 3).** The readers read for the story: where they would stop, what they
   remember. None reads the methods and results asking "do I understand this sentence?". A scientist outside the
   field stopped at 'rows' of a scoring file, "site", "light use", "page cache", T2T, a new measure introduced
   without saying why (the share of a score's variants matched), and a whole paragraph of Section 4.2 ("I didnt
   understand anything in this paragraph"). The connected-paragraphs test repaired two links in Section 1.1 and left
   the one both co-authors found, and two more Georg found. The stage kept speed as a headline although only two of
   six readers remembered "about a minute", judged the related work as covered by Table S7 while the Introduction
   names only PLINK (2015), ANNOVAR (2010) and VEP (2016) and two commercial services without a citation, and kept
   the Abstract's opening without offering the one Livia asks for. *Change:* a reader seat for the expert outside the
   field that reads Sections 2 to 4 sentence by sentence and lists every term used before it is defined, every
   sentence it cannot parse and every number given without its reason; a related-work test that asks for the newest
   comparators in the main text, not only in a supplementary table; and an Abstract test that the opening says what
   the paper presents.
2. **manuscript-prose-edit (15: Georg 13, Livia 2).** It reads only what it edits, and its report says so ("a full
   read of untouched text against the pattern catalogue" is listed as not done). "Model sites a variant-only VCF does
   not list are coded as homozygous reference, and sites whose alleles disagree with the model as missing." has been
   unchanged since v0.6; Georg notes that a grammar checker cannot parse it either. Four suggestions add "to the
   Internet" after "uploaded", because "the genome does not have to be uploaded" leaves open where to. It also left
   the draft note at the top unedited as a working note, which Livia reads as the one statement of how the two papers
   divide the work. *Change:* a list-only pass over the whole text, the draft note included, for sentences that do
   not parse, missing words and ambiguous references, without rewriting anything the stage was not asked to edit.
3. **manuscript-policy-fit (12: Georg 11, Livia 1).** The stage accepted the paper's research-and-education scope and
   dismissed the medical-device question on it, without noticing that Box 1 names lay "people with a genome from a
   sequencing provider" as the first user group. The two co-authors then pulled the name in opposite directions.
   *Change:* check who the paper says its users are against the scope it claims, and say where they disagree.
4. **manuscript-integrity-check (7, Georg).** Limits stated without their cost: "a GRCh37 file would be joined at
   GRCh38 coordinates without a warning" ("how bad is that?") and an indel written differently is not matched ("is
   that a problem?"). A claim with no pointer to where it is shown ("both engines compute the same score"). A list of
   MCP clients nobody tried: the stage listed the Cursor claim among the checks it did not run and raised no problem.
   A feature the code does not have ("self-exploration"). *Change:* for each stated limitation, ask what it costs the
   reader and whether the text says so; a claim the stage could not check becomes a problem that asks to soften it.
5. **manuscript-figures (6, Georg).** Caption wording it did not read for sense ("Only a dot's horizontal position is
   data", "height is the curve"), vector export for the one drawn figure, and what makes the third model in Figure 3
   stand apart. *Change:* read each caption sentence against the figure as a reader would, and ask for vector export
   of drawn figures.
6. **manuscript-improve: the re-check (3, all written by the run, Georg).** The re-check asks whether each edit is
   accurate and answers its problem. It never asks whether a reader can follow the new text, and the three edits Georg
   could not follow were all written to satisfy simulated referees. *Change:* the expert-outsider reader also reads
   every applied edit longer than a sentence; for an edit made for a referee, ask whether its detail belongs in the
   main text or the supplement.
7. **manuscript-peer-review (3, Georg).** The referees asked for the audit's thresholds so it can be repeated, not why
   four of seven test genomes, the outermost 1% or a 0.9 penalty were chosen. No referee asked why the coronary artery
   disease module has 27 variants when LongevityMap holds thousands. A concern about AI-assigned concepts was
   dismissed as an open author decision, and the concept-versus-trait-term wording was never questioned. *Change:* a
   referee asks for the reason behind every constant a method states, and for how complete each curated resource is.
8. **manuscript-journal-adapt (3, Georg).** It asked for contribution roles in a standard format, not whether each
   listed contribution meets authorship criteria (testing software and providing one's genome do not, under most
   definitions). It judged the AI-use statement complete, while Georg would bring the substance of the AI note in the
   supplement into the paper. It left the length to the choice of journal without proposing to move technical
   paragraphs to the supplement, which Georg asks for twice so the review task looks smaller.
9. **manuscript-reporting-check (2, Georg).** How the longevity module's weights follow from study quality,
   replication and significance is not described (the stage asked this only of the other expert modules), and a
   Pearson r of 0.99999996 is reported without saying what it means for the scores.
10. **manuscript-deslop (1, Georg).** It looked at "extensible without code" and kept it as a list of requirements;
    Georg did not know it means without writing code.

## What 0.51.0 and 0.52.0 add

- `comments.py gaps LEDGER --inventory RUN/manuscript-dashboard/findings.json` (or the dashboard `.html` beside the
  paper) writes a worksheet, grouped by co-author: each comment with the run's applied edits that wrote its passage,
  and the problems, dismissed flags, unchecked items, referees' concerns and story tests nearest to it.
- `--merge GAPS.yaml` takes the verdicts into the ledger after checking them (never a dismissed flag or a problem
  the co-authors stage made from the comment, only applied edits, a reason and an owner for each miss); `--check`
  checks them again, counts them for each co-author and lists what is not judged.
- `findings` carries the verdicts to the dashboard. The Co-authors' comments tab opens with "Did the run that
  produced v0.7 catch them?": caught, missed and written by the run, then one bar and one row per co-author (select
  a bar to list that co-author's comments the run did not catch in full; the row names the skills those misses
  point at), why the rest was missed, and the misses by skill. Each comment shows its verdict with links to the
  run's problems and edits. The changes workbook gets a column "Did the run catch it".
- `rounds.py routes` says which ways to the Google Docs the machine has (rclone, a synced folder, a Google Drive
  connector the agent reports). With none, the run goes on and records one setup note for the authors (`runs.py
  issue --kind setup`: how to connect Google Drive in Claude or Codex, or set up rclone), which the progress pane
  lists under "For a better run (nothing waits for this)" and toasts once.

For Paper 1 v0.7 the verdicts are in the ledger. The dashboard committed beside the paper was rendered before they
existed; rendering it again needs the run's folder, on the computer that ran it: run `comments.py findings` for
the ledger into the run's coauthors folder, then collect and render as manuscript-dashboard's SKILL.md says for a
reference that arrives after the corrected version was built.

## Suggested order

1. The expert-outsider reader, also reading the run's own longer edits (manuscript-story and the re-check): 26
   comments the run did not catch in full, and the three passages it wrote.
2. The list-only parse pass over the whole text, the draft note included (manuscript-prose-edit): five sentences
   that do not parse or follow, five grammar slips, the four "uploaded" sentences and the draft note.
3. Finish a fix that needs no decision, and apply definitions where a term is first used, leaving paragraph moves
   as proposals (manuscript-improve): six of the caught comments would not have reached the co-authors.
4. Who the users are against the scope (manuscript-policy-fit): the one question both co-authors answered, in
   opposite directions.
5. Limits with their cost, and unchecked claims as problems (manuscript-integrity-check).
6. The smaller ones: reasons for constants and the completeness of curated modules (peer review), authorship
   criteria (journal adaptation), caption sentences and vector export (figures).
