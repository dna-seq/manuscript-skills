# Response to the editor and reviewers

Manuscript VL-2026-0417, VarLens: fast annotation of personal genomes on a laptop.

We thank the editor and both reviewers. The main changes are a comparison with VEP on the same genomes
(Table 2), a long-read genome (Table 1), a breakdown of the annotations that differ from the previous
release (Table 3) and a Code availability statement. The Abstract (lines 5-8) now reports the comparison
with VEP and the long-read genome. Line numbers refer to the revised manuscript without tracked changes. Labels with a P (R2.P1 to R2.P4) and the parts (a) and (b) were added by us where a
comment was unnumbered or asked for two separate things.

## Editor

<!-- item: Ed.P1 -->
> Please also add a Code availability statement that cites an archived release of the software.

Added. The statement gives the repository and the archived release v1.0.0 of the version evaluated in the
paper. (Code availability, lines 95-96)

## Reviewer 1

<!-- item: R1.1 -->
> 1. The benchmark compares VarLens only with its own previous release. The authors should compare runtime
> and concordance with at least one widely used annotator, such as VEP, on the same genomes.

We compared VarLens with VEP release 111 on HG002 and HG005 on the same laptop. VEP took 41.2 and 44.8
minutes, against 9.8 and 10.4 minutes for VarLens, and the most severe consequence agreed for 98.6% of
variants; most disagreements were splice-region variants, where the tools use different window
definitions. (Methods, "Benchmark", lines 30-31; Results, "Comparison with VEP", lines 60-62; Table 2)

<!-- item: R1.2 -->
> 2. The authors should show the variability across the three runs in Table 1.

Table 1 and the Performance paragraph now give the range across the 3 runs for each genome, for example
9.6 to 10.1 minutes for HG002. (Results, "Performance", lines 46-48; Table 1)

<!-- item: R1.3a -->
> 3. The Discussion states that the rewrite "did not change results", but 0.8% of annotations were
> discordant. Please characterise the discordant annotations by variant class.

Of the annotations that differ from the previous release, 71% are indels and 29% are multi-allelic sites
(Table 3). We also replaced "did not change results" in the Discussion with the measured agreement. The
revised sentence reads: "Its annotations agreed with the previous release for 99.2% of variants, and the
differences were concentrated in indels and multi-allelic sites." (Results, "Concordance", lines 73-74;
Discussion, lines 88-89)

<!-- item: R1.3b -->
> Do any of them affect variants classified as pathogenic or likely pathogenic in ClinVar?

Yes, two. In both, the new release corrected the representation of an indel; the Results now say so.
(Results, "Concordance", lines 74-76)

<!-- item: R1.4b -->
> b) Please state the version of the module tables used in the benchmark.

We have revised the manuscript accordingly.

<!-- item: R1.4a -->
> a) The Abstract gives the memory of the laptop but not the number of cores.

The Abstract now gives both: 16 GB of memory and 8 cores. (Abstract, line 5)

## Reviewer 2

<!-- item: R2.P1 -->
> This is a practical tool paper. My main concern is generalisability. Only two genomes were tested, both
> sequenced on the same short-read platform. I would like to see results on a genome from a different
> platform, for example a long-read genome.

We will add the public PacBio HiFi callset of HG002, a long-read genome, to Table 1 in the final
version.

<!-- item: R2.P2a -->
> The authors also annotate the genome of one of the authors. Was ethics approval obtained for this?

No ethics approval was obtained. The genome is the author's own: A.B. released it publicly under a CC0
licence before this study, no other individuals were recruited, and no clinical results were returned. The
Methods now state this provenance. (Methods, "Demonstration genome", lines 38-40)

<!-- item: R2.P2b -->
> Did the author consent to the publication of their genome?

Yes. A.B. released the genome publicly and agreed to its use in this paper, as the Methods now state.
(Methods, "Demonstration genome", lines 38-39)

<!-- item: R2.P3 -->
> The concordance analysis would be more convincing with an experimental validation of a sample of the
> discordant variants, for example by Sanger sequencing.

We did not perform Sanger sequencing: this is a computational study without a laboratory component.
Instead, we compared the discordant indels with the Genome in a Bottle v4.2.1 benchmark calls for HG002,
and all discordant indels in the benchmark regions matched the benchmark representation in the new
release. The Discussion now states that the discordant variants were compared with benchmark calls rather
than validated experimentally. (Methods, "Benchmark", lines 33-34; Results, "Concordance", lines 76-77;
Discussion, lines 90-91)
