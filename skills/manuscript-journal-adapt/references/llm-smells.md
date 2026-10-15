# LLM smells in scientific manuscripts: a catalogue

What makes text read as machine-written, with an example of each and how to fix it. Sections B, C, F, G,
H, I and K apply to any prose (a paper, a cover letter, a grant, documentation, an email to an editor);
sections A, D and E add what is specific to scientific manuscripts. The last section settles the points on
which humanizer guides disagree.

Sources: Wikipedia's "Signs of AI writing" (WikiProject AI Cleanup); the blader/humanizer skill (MIT,
© 2025 Siqi Chen), whose 33 general patterns are adapted here; the editing levers 3 to 8 and the
rhetorical-scaffolding checklist of harshaneel/humanize (MIT, © 2026 Harshaneel Gokhale), whose
detector-evasion levers are left out; ideas from 28 further open-source writing skills surveyed on
2026-10-15 (listed in the plugin's NOTICE), paraphrased; corpus studies of post-2023 abstracts (Kobak et al. 2025; Juzek &
Ward 2025; Liang et al. 2025) for the vocabulary; Reinhart et al. (PNAS 2025) for the grammatical profile;
and, for the scientific patterns (numbers, statistics, citations, section structure), what editors and
reviewers name when they reject "AI slop".

Read every entry as **a cluster signal, not a verdict**. One "notably" means nothing. "Notably" plus a
participle tail plus "plays a pivotal role" plus a paragraph ending "Overall, these findings highlight…"
is what a reviewer notices. Fix the cluster, and fix it by making the sentence say something specific, not
by swapping one word for a synonym.

All examples are invented for illustration. Citations appear as `[n]`.

Each entry: **Watch for** (words and shapes), **Why it reads as AI**, **Before / After**, **Leave it when**.

---

## A. Significance, hype and empty claims

### A1. Significance inflation

**Watch for:** plays a pivotal / crucial / vital / key role, is of paramount importance, a cornerstone of,
represents a paradigm shift, transformative, revolutionizes, game-changing, groundbreaking, a significant
milestone, sheds new light on, unlocks the potential of.

**Why:** LLMs attach importance to everything. Reviewers read inflated importance as a substitute for
evidence.

**Before:**
> Long-read sequencing plays a pivotal role in the rapidly evolving landscape of structural variant
> detection, representing a paradigm shift that unlocks the full potential of clinical genomics.

**After:**
> Long reads span repeats that short reads cannot, so they resolve structural variants that short-read
> callers miss: in [12], 31% of the deletions longer than 1 kb were found only with long reads.

**Leave it when:** the importance is the finding and the sentence gives its measure ("APOE ε4 is the
strongest common genetic risk factor for late-onset Alzheimer's disease, with an odds ratio near 3 per
allele [4]").

### A2. The field-landscape opener

**Watch for:** In recent years, … has garnered significant / considerable / growing attention; With the
advent of …; In the era of big data / precision medicine; The rapidly evolving field of …; … has emerged as
a powerful tool; a growing body of evidence suggests.

**Why:** The first sentence of half of all LLM introductions. It says nothing a reader of the journal does
not know.

**Before:**
> In recent years, polygenic risk scores have garnered significant attention as a powerful tool in the era
> of precision medicine.

**After:**
> A polygenic risk score sums the effects of many common variants into one number per person. The PGS
> Catalog now lists more than 5,000 such scores [3], but most were trained on European-ancestry cohorts.

**Leave it when:** the opener carries a fact the reader needs (a date, a count, the state of a method).

### A3. Empty implications and send-offs

**Watch for:** has important implications for, paves the way for, opens new avenues for, holds great
promise for, lays the groundwork for, contributes to a deeper understanding of, provides valuable
insights into, offers a promising avenue, will be invaluable for future research.

**Why:** An implication with no content. Reviewers ask "which implication?" and find none.

**Before:**
> These findings have important implications for personalized medicine and pave the way for future
> research into the genetic architecture of longevity.

**After:**
> If the association replicates outside European cohorts, the variant could be added to longevity panels;
> until then it should not be reported to individuals. (Or cut the sentence.)

**Leave it when:** the implication is named, with whom it affects and what limits it.

### A4. Promotional tool language

**Watch for:** seamless(ly), user-friendly, intuitive, powerful, cutting-edge, state-of-the-art (with no
comparison), robust (not in its statistical sense), comprehensive, versatile, flexible, scalable (with no
scaling measurement), efficient (with no time or memory figure), easy-to-use, streamlined, one-stop.

**Why:** Software papers written by LLMs read like product pages. "Scalable" and "efficient" are claims;
without a measurement they are marketing.

**Before:**
> We present a powerful, user-friendly and highly scalable pipeline that seamlessly integrates variant
> annotation into existing workflows.

**After:**
> The pipeline annotates a 4 GB whole-genome VCF in 40 s on a laptop (Table 2) and reads and writes
> standard VCF and Parquet, so it fits after any variant caller.

**Leave it when:** the adjective is followed by its evidence in the same sentence or the next one.

### A5. Priority claims nobody checked

**Watch for:** the first, novel, unprecedented, unique, for the first time, to the best of our knowledge
(with no search described), no previous study has.

**Why:** LLMs add priority claims by default. A reviewer who knows one earlier paper stops trusting the
rest.

**Before:**
> To the best of our knowledge, this is the first comprehensive tool for local genome annotation.

**After:**
> Of the 22 tools compared in Table S7, none runs locally with a graphical interface and an extensible
> annotation format.

**Leave it when:** the comparison that supports it is in the paper.

### A6. Vague authorities

**Watch for:** Studies have shown, It is well established that, Research suggests, Experts agree,
Researchers increasingly, It has been widely reported, Recent studies (with no citation, or with a bundle
of 8 citations for a generic statement).

**Why:** An attribution with no specific source is the classic LLM move. A citation bundle `[3–15]` on a
general sentence looks like padding and gets checked.

**Before:**
> Studies have shown that rare variants contribute substantially to complex disease risk [3–15].

**After:**
> In UK Biobank exomes, rare protein-truncating variants in 8 genes reached exome-wide significance for
> type 2 diabetes [7].

**Leave it when:** the statement is textbook-level and one review is cited for it.

### A7. Boilerplate "challenges and future directions"

**Watch for:** Despite these promising results, several limitations remain; Further research is needed;
Future studies should explore; larger and more diverse cohorts are needed; Despite these challenges, …
continues to.

**Why:** Generic limitations could be pasted into any paper. Reviewers reward the two limitations that
actually threaten the conclusions.

**Before:**
> Despite these promising results, our study has some limitations. Future studies with larger and more
> diverse cohorts are needed to validate these findings.

**After:**
> Two limitations bear directly on the result. The benchmark used one hardware profile, so the runtimes
> may not hold on machines with less than 16 GB of memory. And 92% of the scoring files were trained on
> European-ancestry cohorts, so percentiles for other ancestries are less certain.

**Leave it when:** a short closing sentence points to concrete next work the authors are doing.

### A8. Mini-conclusions and restated summaries

**Watch for:** paragraphs that end with Overall, …; Taken together, …; In summary, …; Collectively, these
results …; These findings underscore / highlight / demonstrate the importance of …; a Conclusion that
repeats the abstract.

**Why:** LLMs close every paragraph by restating it. In a paper this doubles the length of the argument.

**Before:**
> … the median runtime was 40 s. Overall, these results highlight the efficiency and scalability of the
> proposed approach.

**After:**
> … the median runtime was 40 s. (Stop. The reader can see that 40 s is fast; if the comparison matters,
> give it: "four times faster than the previous version".)

**Leave it when:** one "Taken together" joins several separate results into a conclusion they only support
jointly.

### A9. Participle tails ("…, highlighting the importance of …")

**Watch for:** a sentence that ends with `, highlighting / underscoring / emphasizing / demonstrating /
reflecting / showcasing / ensuring / contributing to / paving the way for …`.

**Why:** Instruction-tuned models use present participial clauses several times as often as people do
(Reinhart et al. 2025: 2.6 to 5.3 times). The tail claims a significance the sentence did not earn.

**Before:**
> The variant was present in 12% of centenarians, highlighting its potential role in healthy ageing.

**After:**
> The variant was present in 12% of centenarians and 7% of controls (odds ratio 1.8, 95% CI 1.2–2.7).

**Leave it when:** the participle states a real, separate fact ("…, reducing memory use from 12 to 3 GB").

### A10. Textbook padding

**Watch for:** definitions every reader of the journal knows (DNA, PCR, GWAS, machine learning), a
history of the field, "X is a complex and multifaceted process".

**Why:** LLMs write for a general reader. A specialist journal's reader skips it and wonders who wrote it.

**Before:**
> Genome-wide association studies (GWAS) are a powerful approach that examines genetic variants across the
> entire genome to identify associations with traits.

**After:** cut it, or keep only what this paper needs: "We used the GWAS summary statistics of [9]
(n = 1.2 million)."

**Leave it when:** the venue is broad (Nature, Science, a general audience) or the term is used in an
unusual sense here.

### A11. Speculative mechanism filler

**Watch for:** This may be attributed to the complex interplay of genetic and environmental factors;
potentially due to various underlying mechanisms; may reflect intricate regulatory networks.

**Why:** When a model has no explanation it writes one with no content. Reviewers ask what the mechanism
is.

**Before:**
> The weaker effect in Asian cohorts may be attributed to the complex interplay of genetic, environmental
> and lifestyle factors.

**After:**
> The weaker effect in East Asian cohorts may reflect the lower frequency of the risk allele there (4% vs
> 15%), which reduces power; we did not test other explanations.

**Leave it when:** never as a filler. If no explanation was tested, say so.

### A12. Metric dump in the abstract (and the introduction)

**Watch for:** an abstract that lists every benchmark number: several percentages, decimals, speed-ups,
memory figures, dataset counts and intervals in one or two sentences; the same in the last paragraph of
the Introduction or the first of the Discussion; strings like "(F1 = 0.94, AUROC = 0.97, 4.2×, 3.1 GB)".

**Why:** Models try to make every claim concrete by stuffing in numbers, and an abstract is where they
stuff most. A reader cannot take in eight figures in two sentences, and a reviewer reads the dump as
compensating for a weak headline. The full set of metrics belongs in Results and its tables.

**Before:**
> Our method achieved 94.3% recall (95% CI 92.1–96.0), 91.7% precision, an F1 of 0.930 and an AUROC of
> 0.971 across 12 datasets (n = 48,213), while running 4.2× faster (40.1 s vs 168.4 s) and using 3.1 GB of
> memory (a 74.2% reduction).

**After:**
> Across 12 benchmark datasets, the method found more true variants than the next-best tool at similar
> precision, and ran about four times faster on a laptop.

(The individual figures stay in Results and Table 2. If the venue wants a number in the abstract, give
the one that carries the main claim: "recall 0.94 vs 0.88".)

**Leave it when:** the venue's abstract format requires them. Clinical and trial abstracts (CONSORT, many
medical journals) must report the primary outcome with its effect size and interval; keep those, and only
those.

---

## B. Vocabulary

### B1. The overused words

**Watch for** (the core list; the scanner reports density against the full Kobak list): delve, underscore,
showcase, intricate / intricacies, pivotal, meticulous(ly), commendable, notably, noteworthy, realm,
tapestry, landscape (abstract), interplay, multifaceted, nuanced, garner, bolster, foster, harness,
leverage (verb), unveil, unravel, elucidate, navigate (figurative), embark, endeavor, paramount, holistic,
synergy, seamless, invaluable, profound, burgeoning, enduring, vibrant, testament, crucial, comprehensive,
robust, valuable, enhance, align with, highlight (verb).

**Why:** Their frequency in PubMed abstracts rose sharply after 2023 (delves ×28, underscores ×14,
showcasing ×11 in 2024; Kobak et al. 2025). Single words fade as models change; the overall style
persists, so a list is a prompt to look, not a rule.

**Before:**
> We delve into the intricate interplay between gut microbiota and host metabolism, showcasing a
> multifaceted landscape of interactions that underscores the pivotal role of microbial diversity.

**After:**
> We measured how gut microbial diversity relates to fasting glucose in 1,214 adults. Higher Shannon
> diversity was associated with lower glucose (β = −0.12 mmol/L per SD).

**Leave it when:** the word has its technical meaning (fitness landscape, robust standard errors, a
nuanced phenotype definition the paper defines) or appears once in a long paper.

### B2. Inflated verbs and nominalizations

**Watch for and replace:**

| inflated | plain |
|---|---|
| utilize, leverage, employ | use |
| facilitate, enable | let, allow, help (or say how) |
| demonstrate (for an observation) | show |
| implement (for "do") | do, add, write |
| perform / conduct an analysis of | analyse |
| carry out an investigation into | investigate |
| exhibit | show, have |
| possess | have |
| commence, initiate | start |
| endeavor | try |
| subsequently | then, later |
| prior to | before |
| in order to | to |
| due to the fact that | because |
| in the event that | if |
| a large number of | many |
| a wide range / variety of, various | name them, or "several" |
| with regard to, in terms of, with respect to | about, for, in |
| has the ability to, is able to | can |
| it is worth noting that, it should be noted that | (delete) |
| plays a role in | affects, contributes to (or say how) |
| the integration of X | integrating X |
| provides an overview of | describes |

**Why:** LLMs prefer the longer, more abstract form. Nominalizations are 1.5 to 2 times as frequent in
instruction-tuned output as in human text (Reinhart et al. 2025).

**Before:**
> In order to facilitate the identification of pathogenic variants, we performed an analysis of ClinVar
> annotations utilizing a variety of filtering strategies.

**After:**
> To find pathogenic variants, we filtered ClinVar by review status and clinical significance (Methods).

**Leave it when:** the longer form is the field's term ("implementation" of a method; "exhibit" in a
legal or museum sense).

### B3. Booster and intensifier stacks

**Watch for:** significantly (with no test), highly, extremely, remarkably, substantially, dramatically,
markedly, considerably, notably improved, vastly, greatly, a myriad of.

**Why:** "Significantly" without a test is a statistical claim nobody made. Boosters replace the number
that should be there.

**Before:**
> Our method significantly outperforms existing tools and dramatically reduces runtime.

**After:**
> Our method had higher recall than the next-best tool (0.94 vs 0.88; Table 3) and ran 4.2 times faster
> (40 s vs 168 s).

**Leave it when:** "significantly" reports a named test with its p-value or interval.

### B4. Hedge stacks and hedge loss

**Watch for:** may potentially, could possibly suggest, might perhaps, it is possible that … may, appears
to potentially; and the opposite, a hedge removed during editing ("may affect" → "affects").

**Why:** LLMs over-hedge in one place and overstate in the next. A stack of hedges sounds evasive; a lost
hedge is a changed claim (the guard flags it).

**Before:**
> These results may potentially suggest a possible association.

**After:**
> These results suggest an association. (One hedge, sized to the evidence.)

**Leave it when:** two qualifiers say different things ("may, in some cohorts, …").

### B5. Filler phrases

**Watch for:** It is important / worth / interesting to note that; It should be noted that; As mentioned
above / previously; In this context; In this regard; It goes without saying; Needless to say; First and
foremost; Last but not least; At the end of the day; In today's (fast-paced) world; generally speaking;
in many cases; it can be argued that; it is clear that; for the purpose of; in light of the fact that;
despite the fact that; the fact that.

**Why:** They delay the content. Readers skip them, and so should the paper.

**Before:**
> It is important to note that, in this context, the coverage was lower for chromosome X.

**After:**
> Coverage was lower on chromosome X (median 18× vs 31×).

**Leave it when:** never needed; "Note that" before a counterintuitive point is acceptable once.

### B6. Copula avoidance

**Watch for:** serves as, stands as, functions as, acts as, represents, constitutes, boasts, features,
offers (for "is" or "has").

**Why:** LLMs avoid plain "is" and "has"; corpus studies saw "is" and "are" drop by more than 10% in
academic writing in 2023.

**Before:**
> The module serves as a container for variant annotations and boasts over 900 curated entries.

**After:**
> The module is a table of variant annotations with 911 curated rows.

**Leave it when:** the verb carries meaning ("the control group acts as the reference").

### B7. Synonym cycling of technical terms

**Watch for:** one object called by three names in three sentences: module / annotation package / plugin;
participants / subjects / individuals / patients; score / risk estimate / PRS value; pipeline / workflow /
framework / system.

**Why:** Repetition penalties push models to vary words. In science, a new word signals a new thing, so
variation creates ambiguity. Reviewers read it as carelessness.

**Before:**
> Each module is validated before release. The annotation package is then compiled, and the plugin is
> published to the registry.

**After:**
> Each module is validated, compiled and published to the registry.

**Leave it when:** the words name different things, defined as such.

### B8. Abstract nouns as actors

**Watch for:** This approach enables researchers to…; The integration of X facilitates…; This framework
empowers…; The proposed method ensures…

**Why:** LLMs make methods and frameworks the subject of every sentence. Science reports what people did
and what the data showed.

**Before:**
> This approach enables researchers to seamlessly identify clinically relevant variants.

**After:**
> With this filter, 214 of the 4.1 million variants in a genome remain for review.

**Leave it when:** the method genuinely does the action ("The aligner discards reads with MAPQ < 20").

---

### B9. Ornamental adverbs

**Watch for:** markedly, remarkably, strikingly, profoundly, critically, fundamentally, uniquely, deeply,
truly, genuinely, clearly, obviously, essentially, actually, really, very, quite.

**Deletion test:** delete the adverb. If nothing about size, frequency, direction or calibration is lost,
it was ornament. Keep the functional ones: approximately, slightly, modestly, consistently, almost, only,
largely, relatively, statistically significantly.

**Before:**
> The effect was remarkably consistent across the four cohorts.

**After:**
> The effect was consistent across the four cohorts (hazard ratios 0.81 to 0.86).

### B10. Grand nouns and metaphorical verbs

**Watch for:** tapestry, journey, beacon, cornerstone, linchpin, nexus, mosaic, hallmark, symphony, fabric,
treasure trove, double-edged sword, ecosystem or landscape used as metaphors; navigate (challenges),
unpack, harness, unlock, bridge the gap, illuminate, ignite, unravel, elevate, empower, spearhead,
catalyze, reimagine, embark, embrace, resonate, weave.

**Fix:** the literal noun or verb. "The results shed light on X" → "The results show X".

**Before:**
> This framework bridges the gap between raw sequence data and clinical insight, empowering clinicians to
> navigate the complexities of variant interpretation.

**After:**
> The framework turns a VCF into a report that lists each variant's classification and its evidence.

**Leave it when:** the word is the technical term (an ecosystem in ecology, a fitness landscape).

### B11. Mannered metaphor where a literal phrase exists

**Watch for:** a figure of speech standing in for a plain technical statement ("a dial worth turning" for a
parameter worth varying; "this check earns its keep"; "the data whisper"). Claude-family drafts are prone to
this.

**Fix:** use the literal phrase. Metaphor is for explaining a mechanism, not for decorating a claim.

### B12. Moral and "real" adjectives on technical nouns

**Watch for:** an honest estimate, a principled approach, genuine accuracy, true performance, real
improvement, faithful reproduction, when no dishonest or false counterpart is in view.

**Fix:** drop the adjective or say what makes it so ("an estimate on held-out data").

### B13. Universal quantifiers and lazy extremes

**Watch for:** every, all, always, never, nobody, universally, in every case, across all settings, where
the evidence covers some.

**Fix:** the actual scope ("in all four cohorts", "in 11 of 12 datasets"). Keep a force-bearing "never",
"must" or "all" in rules, inclusion criteria and safety statements.

### B14. Loose word choices in biomedical prose

| loose | precise |
|---|---|
| linked to (for a statistical result) | associated with |
| via (for a mechanism or route) | through, by |
| yields (for an analysis output) | produces, gives (keep for chemical yields) |
| where (as a loose connector) | with, in which, or a new sentence |
| leads to (for an association) | is associated with (unless causal) |
| patients (for animals or cell lines) | mice, animals, cells, samples |
| remain speculative | are speculative |

### B15. Vocabulary drifts by model era

Lists decay. Words that marked GPT-4 text (delve, tapestry) fell after publicity; newer models favour other
words. Reported in 2026: challenge, clearer, dependable, echoed, foster, leverage, matters, multifaceted,
practical, prioritize, quietly, steady, universally (GPT-6 era); causal, empirical, correlate (Grok);
genuinely, fascinating, nuanced, refreshingly, quietly (Claude family). Treat any list as a prompt to look,
re-check it against your own model's drafts in your field, and date it.

**Never swap one listed word for another.** Several humanizer tables replace "unprecedented" with
"groundbreaking" or "underscore" with "highlight". Restructure the sentence instead.

## C. Sentence shapes

### C1. Negative parallelism

**Watch for:** not only X but also Y; It is not merely X, it is Y; not just X, but Y; rather than simply X;
X, not Y (as a flourish); no X, no Y (tailing fragments).

**Why:** A rhetorical contrast where there is no contrast to make.

**Before:**
> The tool is not only fast but also accurate, offering not just annotation but a complete interpretation
> framework.

**After:**
> The tool annotates a genome in 40 s with 99.8% concordance to the reference implementation.

**Leave it when:** the contrast is the point ("The effect was driven not by the common allele but by two
rare haplotypes").

### C2. Rule of three

**Watch for:** triplets everywhere: fast, accurate and scalable; transparency, reproducibility and
accessibility; to identify, characterize and prioritize.

**Why:** LLMs group ideas in threes to sound complete. Three items when the paper supports one reads as
padding.

**Before:**
> Our framework improves transparency, reproducibility and accessibility in genomic research.

**After:**
> Every annotation in the report links to the row of the module that produced it.

**Leave it when:** there really are three things and each is argued.

### C3. False ranges

**Watch for:** from X to Y where X and Y are not on one scale: from basic research to clinical practice;
from single nucleotides to whole genomes; from bench to bedside.

**Before:**
> Applications range from basic research to clinical decision-making.

**After:**
> The tool is meant for research use; it is not validated for clinical decisions.

**Leave it when:** the range is a real interval ("from 18 to 95 years").

### C4. Signposting and announcements

**Watch for:** In this section, we will explore / discuss / delve into; Let us now turn to; We begin by;
The following section provides an overview of; Here, we present a comprehensive analysis of; This paper
aims to shed light on.

**Why:** Announcing instead of doing. Headings already say what a section is.

**Before:**
> In this section, we will provide a comprehensive overview of the benchmarking results.

**After:** delete, and start with the first result.

**Leave it when:** one sentence at the end of the Introduction maps a long paper ("Section 3 describes…")
and the venue expects it.

### C5. Sentence-initial connector piles

**Watch for:** Furthermore, Moreover, Additionally, In addition, Notably, Importantly, Interestingly,
Crucially, Consequently, Thus, Hence, starting consecutive sentences.

**Why:** LLMs chain sentences with explicit connectors. Human writing lets order carry most of the logic.

**Before:**
> Furthermore, the runtime was lower. Moreover, memory use decreased. Additionally, the results were
> consistent across genomes. Notably, no errors occurred.

**After:**
> Runtime and memory use both fell, and the results were the same across the four genomes, with no errors.

**Leave it when:** one connector marks a real turn ("However, …" before a contrary result).

### C6. Persuasive authority tropes

**Watch for:** At its core, Fundamentally, In essence, Crucially, The key insight is, What truly matters,
The real question is, It is clear that, Undoubtedly, Indeed (as an opener).

**Before:**
> Crucially, at its core, the method relies on a simple insight.

**After:**
> The method relies on one observation: most variants in a VCF match no annotation, so the join can be
> restricted to positions that appear in some module.

### C7. Rhetorical questions

**Watch for:** But what drives this effect? How can we bridge this gap? Why does this matter?

**Why:** A blog device. In a paper, the question is the Introduction's job, stated as an aim.

**Before:**
> But how can researchers access their own genomic data without compromising privacy?

**After:**
> We wanted a tool that annotates a genome without uploading it anywhere.

**Leave it when:** the venue's style allows it (some perspectives and essays).

### C8. Uniform mid-length sentences

**Watch for:** paragraph after paragraph of sentences of 20 to 25 words, each subject-verb-object with
one subordinate clause.

**Why:** LLM prose has an even cadence. **Do not fix this by inserting random short sentences** (that is
detector gaming and reads worse). Fix it with content: put the number first and stop, split a sentence
that carries two claims, merge two that carry one.

**Before:**
> The pipeline was evaluated on four whole genomes from public repositories. The annotation step was
> completed in less than one minute for each genome. The memory usage remained below four gigabytes
> during all runs.

**After:**
> We ran the pipeline on four public genomes. Each annotated in under a minute, in less than 4 GB of
> memory.

### C9. Dangling "This"

**Watch for:** sentences starting "This highlights / suggests / demonstrates / enables …" where "this"
could refer to three things.

**Before:**
> Coverage was low in GC-rich regions and the caller missed several indels. This suggests a limitation.

**After:**
> Coverage was low in GC-rich regions, so the caller missed indels there, including two in APOE.

### C10. Aphorisms and slogans

**Watch for:** Data is the new …; X is the language of Y; X is not a tool but a mirror; the currency of
trust; democratizing genomics.

**Before:**
> Transparency is the currency of trust in personal genomics.

**After:**
> Users can see which study and which genotype produced each statement in the report.

### C11. Passive voice that hides who decided

**Watch for:** It was decided to; It was found that; Variants were considered relevant if…; subjectless
fragments ("No configuration needed").

**Why:** Passive voice is normal in Methods. The smell is a passive that hides a judgement the authors
made.

**Before:**
> It was decided to exclude variants with low quality.

**After:**
> We excluded variants with QUAL < 30, because below that threshold the concordance with the truth set fell
> under 95%.

**Leave it when:** the actor does not matter ("Samples were centrifuged at 2,000 g").

---

### C12. Content-free evaluation sentences

**Watch for:** a sentence whose only content is that something matters: This is a noteworthy finding.
These results are of clinical significance. This deserves further attention. The implications are
significant.

**Fix:** delete it, or give the reason in the same sentence ("…, which would change the dose for carriers").

### C13. Cleft and wh- constructions

**Watch for:** What makes this hard is X; What matters is X; It is the validation cohort that carries the
evidence; Where the method shines is X.

**Fix:** plain subject and verb: "X makes this hard", "The validation cohort carries the evidence". An
interrogative opener that frames a real analytic question is fine.

### C14. False agency

**Watch for:** inanimate subjects doing what only people do: the data tells us, the analysis decided, the
Methods section excludes participants, the decision emerged, this course cannot exclude.

**Fix:** name who judged ("We excluded participants who…"). Keep display and evidence verbs for objects
("Figure 1 shows", "These data suggest"). Name the agent when who did it is the claim ("we reproduced").

### C15. Measurement words are load-bearing

**Watch for, when editing:** measured, estimated, apparent, reported, observed, self-reported, predicted,
in this cohort, at this threshold.

**Rule:** never delete them in a style edit. "The apparent diffusion coefficient was lower" and "The
diffusion coefficient was lower" are different claims.

### C16. A sentence that starts with a digit

**Before:** "49 samples were excluded after quality control."
**After:** "We excluded 49 samples after quality control." (or "Forty-nine samples…")
Never fix it by moving the number away from its denominator.

### C17. Condensed expressions

**Watch for:** dash compounds standing for a mechanism (the sleep–mood–cognition pathway), shorthand with no
mechanism (mutual reinforcement, bidirectional relationship, complex interplay), arrow chains in prose
(A → B → disease).

**Fix:** write the relation out: "the pathway linking sleep, mood and cognition", and say which direction
was measured.

### C18. Over-compression and chopping

The opposite failure of a de-slop pass. **Never cut** a unit, a denominator, an n, a condition, or the
qualifier that makes a claim true. **Do not chop** sentences into fragments for rhythm, or turn reasoning
into a run of blunt declaratives where "because", "although" or "so" carried the logic. Keep the authors'
own short sentences. A de-slopped paragraph is plainer, not terser.

### C19. Connective-preserving cuts

When you delete "Additionally," or a participle tail, the logical link it carried must survive: restore it
with a fitting connective, an echoed key noun (old information first, new last), or by merging the two
sentences. Bare deletion leaves choppy asyndeton, itself a sign of automated cleanup. Plain "because" and
"so" are underused by models; use them where the relation is causal.

### C20. Clause-stacked sentences

**Watch for:** sentences over about 30 words with three or more subordinate clauses chained by which, that,
while, with; a subject and its verb more than about 12 words apart.

**Fix:** one idea per sentence; keep subject and verb close; put the new information at the end.

### C21. Abstract wrappers

**Watch for:** a sense of, a mix of, the weight of, a constant reminder of, the notion of, the realm of, the
concept of, paired abstractions ("curiosity and caution").

**Fix:** name the concrete thing.

### C22. Declarative chains: slogans with no transitions

**Watch for:** a paragraph of short, self-contained declarative sentences, each sounding like a headline,
with nothing linking one to the next: no "because", "so", "which means", "as a result", "but", no
subordinate clause, no echoed noun carrying the thought forward. It reads as a list of declarations, not an
argument in which each step follows from the one before.

**Why:** Models produce this when asked to be concise or "punchy", and humanizers produce it when they
delete connectors without restoring the logic (C18, C19). Readers cannot tell which statement is the cause,
which the consequence and which an aside; reviewers read it as slogan-writing.

**Before:**
> Genomes are sensitive. Cloud tools require uploads. Uploads create risk. Local processing removes it. Our
> tool runs locally. It is fast. It is extensible.

**After:**
> Genomes are sensitive personal data, and most annotation services work only after the genome is uploaded
> to their servers. Running the annotation on the user's own machine removes that step, so we built the tool
> to run locally; it still annotates a whole genome in under a minute, and new annotation modules are added
> as data files rather than code.

**Fix:** decide how each sentence relates to the previous one (cause, consequence, contrast, condition,
example) and say it: a connective, a subordinate clause, or the previous sentence's key noun at the start of
the next. Merge only where the relation is close; do not swing to C20 (clause-stacked monsters).

**Leave it when:** a short sentence states a result on its own ("The largest difference was cost."), or a
list of criteria or steps is meant to be read as a list.

## D. Paragraph and section structure

### D1. The template paragraph

**Watch for:** every paragraph is topic sentence, three supporting sentences, and an "Overall" closer, all
of similar length.

**Why:** Human scientific paragraphs are uneven: a result paragraph may be two sentences, a method choice
may need eight.

**Fix:** size each paragraph to its content. Spend length on the two things that need arguing; give
routine items a sentence.

### D2. Bullet lists in place of argument

**Watch for:** bulleted lists in the Introduction or Discussion; inline bold headers ("**Scalability:** …");
contribution lists of five items each starting with a gerund.

**Why:** A chatbot's default output shape. Journals expect argued prose; lists of contributions are
acceptable in some fields (ML) once, at the end of the Introduction.

**Before:**
> - **Speed:** The tool is fast.
> - **Privacy:** Data stays local.
> - **Extensibility:** Modules can be added.

**After:**
> The tool runs locally, so genomes never leave the user's machine, and new annotation modules are added
> as data files rather than code. A whole genome annotates in 40 s.

### D3. Heading restatement and over-sectioning

**Watch for:** a heading followed by a sentence that restates it ("## Benchmarking. Benchmarking is
essential to…"); many short subsections of one paragraph each; title-case headings in journals that use
sentence case.

**Fix:** delete the restatement; merge one-paragraph subsections; follow the journal's heading case.

### D4. Symmetric balance

**Watch for:** strengths and limitations of equal length; "on the one hand… on the other hand" for every
issue; advantages and disadvantages tables with three rows each.

**Why:** Models balance by default. Real assessments are lopsided.

### D5. The same three claims, everywhere

**Watch for:** the abstract, the end of the Introduction, the Discussion opening and the Conclusion all
repeat one list of three contributions in similar words.

**Fix:** the Introduction states the aim, the Results give the evidence, the Discussion interprets and
limits it, the Conclusion is one or two sentences (or absent where the journal has none).

### D6. Changelog writing in the body

**Watch for:** In this revised version we have added…; As requested by the reviewers…; We now include…;
Previously, … but now …

**Why:** Revision notes belong in the response letter. In the manuscript they read as an assistant's diff
narration.

---

### D7. A sentence the reader already has

**Test:** for each sentence, does the reader learn something they did not have from the previous text?
Previews of what follows, recaps of what was just said and summaries at paragraph, section and paper level
fail it. **No repetition across sections:** define a term, describe a method or state a result once, in its
place; later mentions refer back. (Repeating the same technical *term* is required; repeating the same
*content* is the defect.)

### D8. Reshuffle and outline tests

Two diagnostics for machine-shaped structure:
- **Reshuffle:** if two body paragraphs could swap places without breaking the argument, the section is a
  list of points, not an argument.
- **Outline:** if the first sentences of all paragraphs, read alone, form a clean summary, and every
  paragraph runs topic → evidence → takeaway, the shape is templated. Vary it by content: lead one paragraph
  with the example, let another end on the evidence, add the comparison or verification step a reviewer
  would make.

### D9. A list wearing prose

**Watch for:** "The first limitation is… The second limitation is… The third limitation is…"; an intro
sentence and three parallel sentences that are bullets without the bullets.

**Fix:** order by importance and say why each matters; merge minor ones. Keep real enumerations (inclusion
criteria, materials, parameters, steps).

### D10. Writing for the wrong reader

**Watch for:** in cover letters, responses and emails, re-explaining what the editor or reviewer already
knows before the point.

**Fix:** lead with the decision or the answer; keep only the reasoning that would change their view.

### D11. The meandering introduction

**Watch for:** several paragraphs of definitions, history and "why this matters" before the first specific
fact or gap.

**Fix:** reach the gap by the second paragraph; move background the reader needs to where it is used.

### D12. Headings that name nothing

**Watch for:** Overview, Key points, Key takeaways, Final thoughts, Three pillars, The future of X;
question-format headings; a top heading repeating the title; skipped levels.

**Fix:** follow the venue's section names (IMRAD); a subheading names the test, result or decision
("Recall on low-coverage genomes", not "Robustness").

### D13. Where to look hardest

Machine-written text is least visible in the opening and closing (they are edited most) and most visible in
the middle of a section. Review the middle paragraphs first.

## E. Numbers, statistics and evidence

### E1. Adjectives where numbers belong (in Results)

**Watch for:** in Results and Methods: substantially faster, considerably more accurate, a large cohort,
high concordance, low memory footprint, a small number of errors.

**Fix:** in Results, the number, its unit and its comparison: "4.2 times faster (40 s vs 168 s)",
"n = 12,408", "concordance 99.8% (1,204 of 1,206 scores)". In the Abstract, Introduction and Discussion,
a plain comparison backed by those Results is usually better than repeating the figures (see A12); one
headline number is enough.

### E2. Spurious or inconsistent precision

**Watch for:** 95.3472% from n = 40; three decimals in one table column and one in the next; percentages
that do not recompute from their counts.

**Fix:** precision the sample supports; one convention per column; recompute every percentage from its
counts (the integrity scan flags abstract numbers that never reappear).

### E3. Statistical boilerplate

**Watch for:** "p < 0.05 was considered statistically significant" with no test named; "significant" with
no test; "a significant correlation (p < 0.05)" with no effect size; no multiple-testing correction where
many tests were run.

**Fix:** name the test, report the effect size with its interval and the exact p-value, and say how
multiple testing was handled.

### E4. Claims beyond the design

**Watch for:** association reported as causation (causes, drives, leads to, determines); "demonstrates"
for one observation; "proves"; "validates" for agreement with one dataset; "generalizes" from one cohort.

**Fix:** use the verb the design supports: "is associated with", "was higher in", "agreed with … in one
cohort". The guard flags added causal verbs.

### E5. Citation smells

**Watch for:** a review cited for a specific number; one citation reused for unrelated claims; "recent
studies" with no citation; citation bundles on generic sentences; a reference whose title does not match
the claim; any reference the integrity scan cannot resolve.

**Fix:** cite the original study for the number; one claim, its own source; check each cited source says
what the sentence says.

### E6. Results that describe the figure instead of the result

**Watch for:** As shown in Figure 2, … Figure 2 illustrates …; This figure shows a comparison of …

**Before:**
> Figure 3 illustrates a comparison of runtime across different tools, showing the performance of each.

**After:**
> The new pipeline was fastest on all four genomes (Figure 3), by a factor of 3.8 to 4.6.

---

### E7. Citation dumping

**Watch for:** "Many methods have been proposed [3, 7, 9, 12, 15]"; a citation bundle at the end of a
paragraph.

**Fix:** cite the one or two that matter, say what each did and how this work differs. A related-work
section synthesises ("Both rely on X; neither handles Y"); it does not annotate ("Smith finds X. Jones finds
Y.").

### E8. Citations as content

**Watch for:** "According to research, …", "Smith (2020) discusses X", citations hung off the end of a vague
sentence.

**Fix:** make the finding the content and engage with it ("Lambert et al. found X in 1.2 million genomes,
but only in European-ancestry samples [3]").

### E9. Secondhand statistics

A number cited through a review, a textbook or another paper's introduction should be traced to the primary
study and cited there. Copying a citation from a citation is how wrong numbers and wrong references spread.

### E10. Canned attribution

**Watch for:** published in a prestigious / leading journal; a landmark study by renowned investigators;
widely cited; has garnered significant attention.

**Fix:** the plain citation. The venue of a paper is not evidence of its claim.

### E11. The strongest baseline

Lead with the comparison to the strongest competitor, not the weakest. Attribute each number to its
method, metric and baseline. "Better than random" or "better than the 2015 version" is not a result a
reviewer accepts.

### E12. Experiments without a claim

Every experiment answers one of: does it work, why, which alternative explanation is excluded, where does
it apply. Name the claim an experiment cannot support ("without an ablation of the filter, the gain cannot
be attributed to it") instead of implying it.

### E13. Complete reporting

Keep null, negative and unfavourable results that bear on the interpretation; label exploratory and post
hoc analyses; do not change an evaluation criterion after seeing the result; state trade-offs exactly
("latency fell from 100 to 60 ms, accuracy from 90% to 89%"). A style edit never removes a result.

## F. Formatting and punctuation

### F1. Em dashes

**Watch for:** — and spaced — dashes; en dashes used as em dashes; double hyphens.

**Why:** A frequently cited tell, and Claude in particular still uses them more than professional writers.
Many house styles avoid them anyway.

**Fix:** a comma, a colon, parentheses or two sentences. Keep the en dash in numeric ranges (10–20) where
the journal style uses it. In LaTeX, `---` is the same dash. Do not convert every dash to a period: text whose only
punctuation is commas and periods is becoming a sign of its own (see the last section).

### F2. Bold and italic emphasis

**Watch for:** bold phrases inside paragraphs; italics for emphasis rather than for gene names, species
and variables.

**Fix:** remove emphasis; scientific style uses italics for genes, species and symbols only.

### F3. Markdown and chat residue

**Watch for:** `**bold**`, `##` headings, `- ` bullets inside a LaTeX or Word manuscript; emojis; ✅/❌ in
running text.

**Fix:** convert to the manuscript's markup. (Check and cross marks in a feature-comparison table are a
normal convention.)

### F4. Abbreviation sprawl

**Watch for:** an abbreviation defined for a term used once or twice; the same abbreviation defined again
in each section; "(e.g., …)" and "(i.e., …)" in every sentence.

**Fix:** define only abbreviations used at least three times; define once, at first use in the main text.

### F5. Uniform hyphenation and quote style

**Watch for:** every compound hyphenated regardless of position ("the data is high-quality"); curly and
straight quotes mixed.

**Fix:** hyphenate compound modifiers before a noun only; one quote style (the journal's).

---

### F6. Leaked machine artifacts

**Watch for:** § signs and "(Methods §2.3)" self-references in a journal that does not use them; Markdown
syntax in a Word or LaTeX manuscript; placeholders ("[Insert Table 1 here]", "2025-XX-XX", "<!-- add
citation -->"); citation-markup tokens; `utm_source=chatgpt.com` in URLs; zero-width characters, soft
hyphens and non-breaking-space clusters (strip and normalise them); a trailing "↩".

### F7. Mechanical consistency

One spelling variety (models default to American English); P or p, consistently; a space between value and
unit ("5 mg"); digits or words for numbers per house style; abbreviations defined once, at first use, and
never before; the same number written identically in the abstract, text, tables and figures.

## G. Communication artifacts

### G1. Chat leftovers

**Watch for:** Certainly, here is…; I hope this helps; Let me know if…; As an AI language model; as of my
last update; [Insert citation]; illustrative values to be replaced. **Desk-reject triggers**; the
integrity scan finds them.

### G2. Addressing the reader

**Watch for:** you, your, we encourage the reader to, imagine that.

**Fix:** a paper reports; it does not address a reader (except in tutorials and protocols).

### G3. Sycophancy in responses to reviewers

**Watch for:** We thank the reviewer for this excellent / insightful / valuable comment (on every point);
We completely agree; This is a great point.

**Why:** Editors read dozens of AI-written response letters. Some journals forbid AI-written responses.

**Fix:** one thank-you at the start; then, per point, what changed and where ("We added the GRCh37 runtime
to Table 2, page 7").

### G4. Gap-filling about what is unknown

**Watch for:** While specific details are limited…; based on available information; it is believed that;
not well documented, suggesting…

**Fix:** say what is not known, or cut the sentence.

---

## H. Rhetorical scaffolding, rhythm and punctuation (any prose)

These feel like good writing, which is why they survive a quick edit. They are the patterns a model
learned from polished text and applies too evenly. Scan for each one by name; a general "does this read
as AI?" read misses most of them.

### H1. Mini-aphorism closer

**Watch for:** a paragraph that ends in a short quotable "lesson": That is the real advantage. Speed is
not optional. Data never lies.

**Before:**
> … each sample was annotated in under a minute. Speed, in the end, is what makes privacy practical.

**After:**
> … each sample was annotated in under a minute, short enough to run on the user's own machine.

### H2. Thesis-first opener and pattern announcement

**Watch for:** paragraphs that open with a framing claim before the substance ("The key insight is
simple.", "The challenge here is twofold.", "The pattern is clear:"); announcement colons ("The rule we
follow: …", "The bottom line:").

**Fix:** start with the concrete thing and let the point emerge; state the rule instead of announcing it.

**Before:**
> The challenge is twofold: data are sensitive, and tools are hard to install.

**After:**
> Genomes are sensitive personal data, and most annotation tools need a server and a bioinformatician.

### H3. Setup-and-reveal and "turns out" pivots

**Watch for:** What we did not expect was X; It turns out that X; As it turns out; Surprisingly, it
turned out; The answer, it turns out, is X; What X really means is Y.

**Before:**
> What we did not expect was that most of the runtime came from parsing.

**After:**
> Parsing took 70% of the runtime.

### H4. Comparative and diminishment framing

**Watch for:** more X than Y (as a flourish); feels less like X and more like Y; not a X but a Y; less
about X, more about Y; it is not X, it is Y.

**Fix:** say what the thing is. Keep a comparison only when both sides are measured.

**Before:**
> The registry is less a database than a living ecosystem of curated knowledge.

**After:**
> The registry stores versioned modules; authors publish new versions and users choose which to install.

### H5. Either/or binaries

**Watch for:** Whether X or Y, …; Either we accept X or we accept Y; two clean options presented for what
is really a spectrum.

**Fix:** name the actual situation and its gradations.

### H6. Anaphora and parallel-subject mirrors

**Watch for:** consecutive sentences that open with the same word or mirrored subjects ("The code is
open. The data is open. The process is open." / "Building the index is one task. Maintaining it is
another.").

**Fix:** merge, or vary the structure because the content differs.

**Before:**
> The pipeline is local. The pipeline is fast. The pipeline is extensible.

**After:**
> The pipeline runs locally, annotates a genome in under a minute, and accepts new modules as data files.

### H7. Tricolons and escalating lists

**Watch for:** three parallel beats with the same grammar, often growing in weight and without "and":
"hours of debugging, dozens of failed runs, a pipeline nobody trusted". (See also C2.)

**Fix:** keep the items that matter, joined plainly; two is often right.

### H8. Chiasmus and balanced opposition

**Watch for:** reversed-parallel constructions that sound like insight ("we do not annotate genomes to find
variants; we find variants to annotate genomes"), and symmetric trade-offs in one sentence ("faster but
less flexible, or flexible but slower").

**Fix:** state the asymmetric truth: which option is better for what, by how much.

### H9. Parallel reason chains

**Watch for:** three consecutive sentences of the form subject + because/when + reason.

**Fix:** keep the reasons, vary the structure because the reasons differ in weight; often one sentence
with the main reason and a clause for the minor one.

### H10. Manufactured punchlines and staccato drama

**Watch for:** a run of very short sentences built for effect ("Then came long reads. No more gaps. No
more guesswork. The rules had changed.").

**Fix:** one plain sentence with the fact. A single short sentence for emphasis is fine; a run of them is
a performance.

### H11. Fake candour and conversational hooks

**Watch for:** Honestly?, Here is the thing, The thing is, Let us be honest, Make no mistake, as standalone
openers before an ordinary point.

**Fix:** say the point.

### H12. Reframe pivots and landing phrases

**Watch for:** Seen this way, …; Put differently, …; In other words, … (when nothing new follows); … is
where the real work happens; … is what truly matters; that is the whole point.

**Fix:** if the reframing adds nothing, delete it; if it adds something, state that thing directly.

### H13. Self-aware parentheticals and meta-commentary

**Watch for:** comments on one's own writing or state ("(which we choose to see as a feature)", "(more
on this below)", "as we will see").

**Fix:** keep forward references only where the reader needs them ("Section 4"); cut the rest.

### H14. Generic positive endings

**Watch for:** a final paragraph or sentence that is upbeat and empty: The future of personal genomics is
bright; This work represents an exciting step forward; We hope this tool will empower researchers.

**Fix:** end on the last concrete fact, the main limit, or the next specific step.

### H15. Quantifier and scope inflation

**Watch for:** a myriad of, a plethora of, a wide array of, countless, numerous (for three), in the realm
of, across diverse domains, a broad spectrum of.

**Fix:** the count, or the named items.

### H16. Templated openings and closings in letters

**Watch for:** in cover letters and emails to editors: We are pleased to submit our manuscript entitled …
for your kind consideration; We believe this work will be of great interest to your readership; We look
forward to hearing from you at your earliest convenience; Please do not hesitate to contact us.

**Fix:** what the paper shows in two sentences, why it fits this journal (its scope statement, a recent
related paper it published), the declarations the journal requires. One closing line is enough.

### H17. Punctuation habits

- **Em dashes** (see F1). Claude and other assistants overproduce them; scan the finished text and count,
  do not rely on memory.
- **Colons in mid-thought.** "The answer: start earlier." A colon is fine after a complete sentence that
  introduces something; elsewhere use a full sentence.
- **Semicolons** are normal in academic prose (and in lists whose items contain commas). In letters,
  emails and plain-language summaries, a semicolon where a period would do reads as machine polish.
- **Curly vs straight quotes.** Follow the journal or the document's existing style consistently; mixed
  styles in one file are the tell, not either style.
- **Exclamation marks** have no place in a manuscript.

### H18. Over-smooth coherence

**Watch for:** paragraphs where every sentence opens with a link to the previous one and closes its own
point, so that any sentence could be deleted without a gap; every paragraph opens with a claim and ends
by confirming it.

**Fix:** not by inserting awkwardness (that is the detector-evasion move these skills refuse), but by
content: delete the sentences that only restate or bridge, so each remaining sentence carries something
the paragraph needs. Tight coherence is a virtue in abstracts and Methods; the smell is coherence built
from connective tissue rather than content.

---

## I. Hedging and certainty

Calibration is where an AI pass does the most damage, in both directions: models over-hedge where the
evidence is solid, overstate where it is weak, and add new disclaimers when asked to make text "safer".

### I1. Verbs matched to the design

Causal verbs (show, demonstrate, establish, identify, cause) for controlled comparisons in the authors' own
data; associative ones (is associated with, is consistent with, supports, suggests) for correlational data;
speculative ones (may, could, one possibility is) for mechanisms and hypotheses. Never "prove" for an
empirical result; never turn an association into a cause, or a non-significant difference into
equivalence.

### I2. One accurate hedge per claim, never zero where the evidence is uncertain

Collapse a stack ("may potentially suggest") to one hedge. Keep the hedge on observational and exploratory
findings. State a randomised primary result directly.

### I3. Vagueness as hedging: quantify it

**Watch for:** somewhat, relatively, fairly, to some extent, considerably, a large improvement.

**Fix:** the number, the range, the test, the comparator, from the paper.

### I4. Name the source of the uncertainty

**Before:** "These results should be interpreted with caution."
**After:** "The cohort was 92% European ancestry, so the effect size may not hold in other populations."

### I5. A rewrite adds no new doubt

Do not introduce a limitation, a softened claim or a disclaimer the authors did not write. Models add these
("does not by itself establish…", "should be treated as…rather than…", "this is not to say…") when asked to
make text accurate or review-proof, and in 2026 such unprompted disclaimers are themselves a tell. Do not
weaken an expectation the authors state as theirs.

### I6. A rewrite does not upgrade either

No claim in the abstract or conclusion stronger than the Results paragraph that supports it. Keep each
finding's tense, population, setting and quantification: a cohort result is not a general law.

### I7. The same certainty in every section

A claim carries the same strength in the abstract, introduction, results and discussion. It may soften
towards speculation in the Discussion; it never strengthens backwards.

### I8. Defensive writing

**Watch for:** repeated "we do not claim"; caveats in the high-impact positions (the abstract's first
sentence, the contribution statement, the conclusion); paragraphs that open with a limitation;
"Unfortunately, our method only…".

**Fix:** state scope positively ("The analysis covers cases from 2015 to 2023"), and give the limitations once,
in the Limitations or Discussion.

### I9. Stance where a judgement is owed

A comparison without a recommendation, or a discussion that will not choose between explanations it can
rank, under-claims. Reviewers penalise that about as much as over-claiming. Hedge once per genuinely fragile
claim, not once per sentence.

### I10. False concession and both-sidesism

**Watch for:** "While X offers benefits, it also presents challenges" with both halves vague; "on the one
hand… on the other hand" that never concludes.

**Fix:** make each half specific, or cut the frame.

### I11. Arguing with no one

**Watch for:** "One might be tempted to…", "While some might argue…", "A naive approach would be…", "It would
be easy to dismiss this as…", rebuttals of objections nobody raised.

**Fix:** delete them. Keep an objection the text attributes (to a cited study or a reviewer) and answers.

### I12. Narrated candour and self-description

**Watch for:** "To be fully transparent", "We want to be upfront", "this comprehensive analysis", "a thorough
examination of", "the table below compares", descriptions of how the text was assembled.

**Fix:** delete; let the content show it. Keep conflict-of-interest wording and source credits.

### I13. Leftover hedge debris

A qualifier ("arguably", "to some extent", "in some ways") left beside an otherwise confident sentence after
an edit. Either the claim is hedged, with a reason, or it is not.

---

## K. Voice and register

### K1. The human voice of a manuscript is neutral and precise

No injected personality: no humour, anecdote, first-person singular, contractions, rhetorical questions or
self-interruptions in a research article (general humanizers add these; they are wrong here). "We" for the
authors' work is standard.

### K2. Match the venue's register from its own papers

Read two or three recent papers in the target journal and article type: claim strength, hedging, person and
voice (some journals want passive abstracts without "we"), section names, how results are reported. Run
`style_profile.py --sample` on them to see where the manuscript departs from the venue's style.

### K3. Match the authors' own earlier writing

See the writer profile in `humanize-contract.md`. Draw replacements from the authors' repertoire; never
upgrade their vocabulary.

### K4. Terms earn their place

Keep the field's exact terms without glosses (they are a correctness requirement), but strike vocabulary the
manuscript invented for its own convenience, including invented concept labels used as if established ("the
calibration paradox").

### K5. Method names in Methods, consequences in Discussion

Methods name the rule, the software version, the threshold. Results state what was measured. The Discussion
says what it means; it does not repeat method names or "we carefully checked".

### K6. Claims of competent practice

**Watch for, outside Methods:** using standard methods, after careful review, we carefully tuned, following
standard protocol, rigorous.

**Fix:** cut, unless the check establishes fairness (matched budgets, the same seeds), in which case give it.

### K7. Reviewer-reply register in the body

**Watch for:** body text arguing with an imagined reviewer: "it is worth clarifying that…", "this should not
be understood as…", "we emphasize that this metric reflects…".

**Fix:** plain narration of what was done and found.

### K8. Register shifts inside one document

One section full of listed vocabulary while the rest is plain; polished opening and closing around a rough
middle; American spelling in one section only. These show where AI text was pasted in; edit that section to
match the rest.

### K9. Over-polishing

Do not sand every irregularity. Leave ordinary sentences alone. Inverting every tell produces its own
fingerprint (the "humanizer voice" of fragments and forced variety).

---

## How we settled the disagreements between sources

Humanizer guides contradict each other on several points. For scientific manuscripts:

| question | our rule |
|---|---|
| Em dashes | Avoid them where the house style does (and Claude over-produces them). Wikipedia now lists dash overuse as a historical sign; text whose only punctuation is commas and periods is becoming a sign of its own, so do not replace every dash with a period. Keep en dashes in ranges. |
| Semicolons | Fine in academic prose for closely related clauses and in lists whose items contain commas; not as a reflex replacement for removed dashes; avoid in letters and lay summaries. |
| Passive voice | Conventional in Methods; follow the venue for abstracts; convert only passive that hides a judgement (C11). Models now under-use the Methods passive, so a Methods section in "We heated… We recorded…" throughout can itself look generated. |
| Moreover, Furthermore, Additionally | Cut piles; one where it marks a real step is fine; when cutting, restore the link (C19). |
| Notably, Importantly, Interestingly | Cut as emphasis; keep where it marks a genuine contrast with expectation, once. |
| Taken together, In conclusion | Cut as a paragraph closer; one "Taken together" that joins separate results into a conclusion is fine. |
| novel, demonstrate, first | Allowed when the evidence is there: "novel" once, backed by a comparison; "demonstrate" for controlled own data; "first" only after a search. |
| Hedging | One accurate hedge, never zero for uncertain claims, never stacked (I2). |
| Lists of three | Fine when the content has three items; the smell is triads by default. |
| "in order to" | Wordy, but a single instance is not evidence of anything. |
| Synonym cycling | Always a defect in science: one term per concept. |
| Bullets | Not in Abstract, Introduction, Results or Discussion prose; real enumerations (criteria, parameters, steps) and venue-required contribution lists are fine. |
| Contractions, first person singular | None in manuscripts; "we" is fine. |
| Questions | No rhetorical questions; a question stating the study's aim is acceptable in some fields. |
| "associated with" | The correct statistical term; the smell is using it to avoid stating a known relation, or "linked to" in its place. |
| Replacement tables | Never replace one listed word with another; restructure. |

---

## What not to flag (scientific false positives)

- **Passive voice in Methods.** It is the convention in most life-science journals.
- **Field terms that are also on the lists.** Fitness landscape, robust regression, comprehensive
  metabolic panel, key (cryptographic), significant (with a test), novel (a novel variant is one not seen
  before), interplay (when the paper measures an interaction).
- **One "however", "moreover" or "notably".** Connectors are smells in piles.
- **Formal register and perfect grammar.** Polish is not evidence of anything, and many authors use
  professional editing.
- **Words common among non-native writers.** Corpus studies note that reviewers misread non-native English
  as AI; do not "correct" an author's natural word choice into another generic one.
- **Standard section formulas the journal requires** (structured abstracts, "Availability and
  Implementation", data availability boilerplate the journal supplies).
- **Comparison tables with check marks.**
- **Quoted text, titles, gene and product names**, and passages where a phrase is discussed rather than
  used.
- **Low-variance or very regular style** (common in neurodivergent and non-native writers), and any text
  under about 40 words: too little to judge.
- **Text written before 30 November 2022** (ChatGPT's release), with rare exceptions.
- **Conventional templates**: IMRAD headings, reporting-guideline phrasing, "Here we show".
- **One of anything**: one dash, one semicolon, one triad, one "delve". Act on clusters.

## Signs of human scientific writing (preserve them)

- Specific, awkward, hard-to-invent detail: a failed run and why it failed, a batch effect found by
  accident, the exact threshold and the reason for it.
- Uneven emphasis: a long paragraph on the one design decision that mattered, a line for the rest.
- The lab's own vocabulary, used consistently, even when it is a little odd.
- Honest uncertainty with a reason ("we could not tell whether…, because…").
- Numbers where the result is reported, not adjectives; and not a pile of them in the abstract.
- Credit to specific prior work, including work that did something similar.

When the authors' text has these, edit lightly. Over-editing removes exactly what makes it read as theirs.
