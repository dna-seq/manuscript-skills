# Comparing the story with other papers

Two comparisons, for two questions. **Neighbours** answer the reader's question "I know that tool; why read
this?". **Exemplars** answer the authors' question "how do papers like ours hold a reader?". Neither is a
feature comparison: what each tool can do belongs in the paper's own comparison table, and claims such as
"first", "only" or "no existing tool" belong to `manuscript-integrity-check` and
`manuscript-reference-check`.

## Neighbours: for positioning

**Choose three to five**, in this order: the predecessors the authors name (ask once, if none are named);
the closest work the paper already cites or tabulates; the authors' own earlier versions and preprints;
the papers a reader of the target venue most likely knows; and anything closer that a search finds
(PubMed, Europe PMC, arXiv and bioRxiv). The authors' own earlier work is an earlier telling of this
paper's story, compared as a version, never as a competitor.

**Read** each one's Abstract and Introduction, and its Conclusion when it has one, from an open-access
copy; mark a paper read from its abstract alone. Note:

- the problem it states, in its own first sentences;
- the difference it claims from the work before it;
- what it argues against;
- its central idea and its headline number;
- what output it shows the reader.

**Report:**

- **The one-sentence difference** a reader who knows each neighbour wants, drafted for the Introduction
  in the paper's own voice and direction ("X lets you do A on a server; we do A on your own computer, and
  modules are data you can publish without code").
- **Neighbours the paper never cites**, and where a reader would expect them. A close predecessor missing
  from the main text is the commonest positioning gap: it leaves the reader to wonder, and an editor to ask.
- **A lineage**, when the paper descends from named predecessors: in two sentences, an origin story
  (what each generation changed) can carry the Introduction, if the authors' direction wants it.
- Claims in the paper that a neighbour contradicts, handed to `manuscript-integrity-check`.

## Exemplars: for craft

**Choose two or three** well-told papers of the same article type, and of the target venue when possible,
read in full from open-access copies. A paper qualifies by how it reads, not by its citations alone:
look for a stake in its first sentences, one memorable idea, one vivid number, a figure of real output and
an ending on use.

**Report** up to five devices the authors could use, each with the exemplar's passage quoted and where it
would go in this paper. Borrow devices, never wording.

Starting points read on 2026-10-19 (check each again before citing it):

| Paper | Format | What it does well |
|---|---|---|
| Hadfield et al. 2018, Nextstrain, *Bioinformatics* 34(23):4121. https://doi.org/10.1093/bioinformatics/bty407 | Application Note | The stake in sentence one (Ebola, Zika); the gap as timing ("after publication, which may be too late"); one vivid number (an epidemic's 1,581 genomes "in under 2 h on a modern laptop") |
| Ewels et al. 2016, MultiQC, *Bioinformatics* 32(19):3047. https://doi.org/10.1093/bioinformatics/btw354 | Application Note | The problem in one sentence; the idea in the title ("a single report"); where the tool came from |
| Bray et al. 2016, kallisto, *Nat Biotechnol* 34:525. https://doi.org/10.1038/nbt.3519 | Brief communication | A four-sentence Abstract: the claim with its number, the idea in one word, a laptop-scale scene, the payoff |
| Karczewski et al. 2012, Interpretome, *Pac Symp Biocomput* 2012:339–350. https://doi.org/10.1142/9789814366496_0033 | Proceedings paper | A contrast a reader keeps ("$1,000 genome", "$1,000,000 interpretation"); a one-sentence privacy promise; a scene with real users |
| Folkersen et al. 2020, Impute.me, *Front Genet* 11:578. https://doi.org/10.3389/fgene.2020.00578 | Original research | What it argues against, named and quantified; numbers about its users |
| Harris et al. 2020, NumPy, *Nature* 585:357. https://doi.org/10.1038/s41586-020-2649-2 | Review-style article | An origin story; the Abstract anchored on results readers know |

Counterexamples, which open with paragraphs of sequencing costs or field history before the problem:
McLaren et al. 2016, VEP (https://doi.org/10.1186/s13059-016-0974-4) and Greshake et al. 2014, openSNP
(https://doi.org/10.1371/journal.pone.0089204).

## Limits on the output

- One positioning sentence per neighbour at most, an optional two-sentence lineage, the list of missing
  citations and up to five devices. Never a new related-work section, and never a defensive paragraph
  answering a neighbour.
- Every paper named or cited passes `manuscript-reference-check` before it enters the manuscript; every
  quote is verbatim from a copy that was read.
- A comparison never changes the paper's direction by itself: a neighbour that suggests a different lead
  theme becomes one of the direction options for the authors.
