# Section by section: what each part of a paper needs, and what reads as AI there

Use with `llm-smells.md` (pattern ids in brackets) and the shared venue checklist from
`../manuscript-journal-adapt/scripts/venues.py show` (relative to the prose-edit skill directory). The
venue's author guidelines override anything here (structured abstracts, section names, word limits).

These are editorial suggestions, not a mandatory template. Follow the shared author-priority rules;
preserve the author's effective style and the quantities needed for the paper's actual claims.

## Title

**Needs:** what was done or found, on what, in plain terms; the tool's name for software papers where the
venue asks for it.
**Reads as AI:** "Towards …", "Unlocking …", "Harnessing the power of …", "A comprehensive framework for
…", two colons, a slogan before the colon [A1, A4, H1].
**Example.** "Unlocking the Genome: A Novel, Comprehensive Framework for Privacy-Preserving Annotation" →
"Local annotation of personal genomes with versioned, shareable modules".

## Abstract

**Needs:** one sentence each for the problem, what was done, the main result, and what it means and for
whom; availability where required for software. Include the quantitative evidence the main claims need
and the journal's format requires, including relevant uncertainty. There is no universal metric quota.
**Reads as AI:** the field-landscape opener [A2]; "In this paper, we present a novel …" [C4, A5]; a dump of
every metric, interval and speed-up [A12]; vague boosters instead of a result [B3]; a closing implication
sentence [A3]; a triplet of benefits [C2].
**Check:** every number in the abstract appears in the body (the scan flags those that do not); no claim
the results do not support; within the word limit.

## Introduction

**Needs:** what is known (cited to specific work), what is missing, why it matters for this field, what
this paper does. Usually 3 to 6 paragraphs.
**Reads as AI:** textbook padding [A10]; vague authorities and citation bundles [A6]; "has garnered
significant attention" [A2]; a closing list of contributions in bullets [D2] (acceptable once in ML venues);
the contributions repeated later word for word [D5].
**Fix:** start from the gap; cite the closest prior work, including what it already does; state the aim as
the authors' choice ("We wanted …", "We asked whether …").

## Related work (where the venue has the section)

**Needs:** the closest tools or studies, what each does, and the specific difference, ideally in a table
with the same rows for every entry.
**Reads as AI:** every tool described in the same template sentence; comparisons on criteria only the new
tool meets; dismissive adjectives ("limited", "cumbersome") without a measurement.

## Methods

**Needs:** enough to reproduce: data sources with versions and accessions, software with versions and
parameters, thresholds and the reason for each non-default one, statistical tests and corrections, code
availability.
**Reads as AI:** "rigorous", "carefully", "meticulously" [B1, J6]; "a variety of filtering strategies" instead
of the filters [B11]; signposting [C4]; hidden decisions ("it was decided") [C10].
**Normal here:** passive voice, long parameter lists, repetitive sentence shapes across similar steps.

## Results

**Needs:** each result with its number, unit, uncertainty and the figure or table; past tense; ordered by
the argument, not by the order of the analyses.
**Reads as AI:** describing the figure instead of the result [E5]; boosters and "significantly" without a
test [B3, E3]; participle tails interpreting each result [A9]; mini-conclusions after each paragraph [A8].
**Check:** percentages recompute from their counts (the scan does this for "x of y (z%)"); tests named; the
same precision for the same measure throughout [E2].

## Discussion

**Needs:** what the results mean, compared with prior work (agreements and disagreements, cited); the
limitations that bear on the conclusions, each with its consequence; what would test the interpretation.
**Reads as AI:** restating the results [D5]; implications without content [A3]; speculative mechanism
filler [A11]; boilerplate limitations [A7]; symmetric strengths and weaknesses [D4]; a positive send-off
[A3].
**Fix:** organise by interpretive point; state the material limitations specifically; end on
the main limit or the next concrete step.

## Limitations (as its own section)

**Needs:** specific limits: of the data (ancestry, size, build), of the method (what it cannot detect),
of the evaluation (what was not measured), each with how it affects the claims.
**Reads as AI:** "Despite these promising results…" [A7]; limits phrased as future work; limits that apply
to every study.

## Conclusion (where the venue has one)

**Needs:** one or two sentences: the finding and its main condition.
**Reads as AI:** a third repetition of the contributions [D5]; "In conclusion, this work represents a
significant step towards…" [A1, A3, A8].

## Figure and table captions

**Needs:** what is plotted (axes, units), n, what error bars and boxes show, the statistical test, and
abbreviations used in the panel.
**Reads as AI:** "This figure illustrates…", "A comprehensive overview of…", interpretation in the caption
that belongs in Results.

## Availability statements and declarations

**Needs:** the exact URLs and archived DOIs, licences, accessions; the declarations the venue lists (data,
code, competing interests, funding, author contributions, AI use, ethics), in its wording.
**Reads as AI:** promises instead of links ("will be made available upon publication" where the venue
requires availability at submission); generic AI statements that name no tool or version.

## Cover letter

**Needs:** title and article type; two or three sentences on what the paper shows and why it fits this
journal (its scope, a related paper it published); the declarations the journal asks for (AI use,
preprint, competing interests, suggested or excluded reviewers if asked).
**Reads as AI:** "We are pleased to submit…", "We believe this work will be of great interest to your
readership", "We look forward to hearing from you at your earliest convenience" [G5]; superlatives about
the work [A1, A4].
**Length:** one page at most.

## Response to reviewers

**Needs:** each comment quoted, then what changed and where (page, line, section), or why not, with the
evidence.
**Reads as AI:** thanking for every "excellent" comment [G3]; long agreement without a change; restating
the reviewer's point back to them; defensive boilerplate. Some venues forbid AI-written responses; check
`venues.py show`.

## Plain-language and lay summaries

**Needs:** what was found and why it matters to the reader, in everyday words, with the main limit.
**Reads as AI:** the same hype as anywhere [A1, A3]; semicolons and nested clauses; analogies that add
nothing. Still no invented facts.
