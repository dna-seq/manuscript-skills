# Story tests

Each test asks one question a reader answers without knowing it, says how to check it, and what to do when
the paper fails it. Report a failed test with the passage quoted and its section; the fix is an edit that
keeps the direction ([story-contract.md](story-contract.md)) or, when the fix would change the direction,
an option for the authors.

## The opening

1. **The stake.** Does the first paragraph say why the recorded readers should care, in terms of the
   paper's lead theme, before the field's background? A first sentence about how much cheaper sequencing
   has become, how fast a field is growing or how important a topic is gives the reader nothing the next
   sentence needs (the field-landscape opener, A2 in the
   [smell catalogue](../../manuscript-prose-edit/references/llm-smells.md)). Fix: open with the problem a
   reader has, or the consequence of not solving it, and move the background after it.
2. **One sentence.** Can the Abstract's first three sentences be read as "And, But, Therefore": what is
   known and wanted, what blocks it, what this paper does about it (Olson 2015)? A list of facts joined by
   "and" has no story. Fix: find the "but" the paper already has and put it second.
3. **The gap.** Is what is missing stated as a specific limitation of named existing work, so that the
   reader knows what the paper adds? Fix: name the closest work and what it does not do (see
   [comparisons.md](comparisons.md)); a gap with no neighbour named reads as unsupported.
4. **One idea.** Is the central contribution in the title, and is there one phrase a reader can repeat
   ("pseudoalignment"; "modules are data, not code")? A paper that pursues several contributions is less
   convincing about each (Mensh & Kording 2017, rule 1). Fix: name the idea once, early, and reuse it.

## The middle

5. **A headline per result.** Does each results section open with its finding in plain words, before the
   numbers, setup and versions? Fix: a first sentence that says what was found and the number a reader
   keeps; the run history follows or moves to the supplement.
6. **Show the output.** Does the paper show what a user actually gets: a report row, a screenshot of a
   real result, the output for a named input? For a tool or platform paper this is the single strongest
   device; its absence is the most common reason a reader cannot say what the tool does. Fix: a worked
   example from the authors' own outputs; never a constructed one.
7. **Connected sentences.** Does each sentence follow from the one before by cause, contrast or time?
   Connectedness was the narrative feature most associated with citation in one study of 732 abstracts
   (Hillier et al. 2016; correlational, small effect). Fix: reorder so each sentence picks up the last
   one's new information; a connective word is not a connection.
8. **Autobiography.** Does the text tell how the authors did the project (the order runs were made, the
   versions tried) where it should tell why a reader should believe the result? Fix: lead with the
   result and the reason to believe it; keep the history in Methods or the supplement.

## Caveats and accretion

9. **Caveats in their place.** Sort every caveat as the contract does. Flag key sentences that end on a
   caveat (the stress position, Gopen & Swan 1990), inline caveat clauses in the Abstract and
   Introduction, and results paragraphs that end on what the result does not show.
   `reader_metrics.py` gives caveats per kind of section and the share of sentences ending on one.
10. **Accretion.** Against the earlier version: what was added since, and for whom? For each addition ask
    whether it tells the reader what was found or tells a referee why an objection does not overturn it;
    the second kind belongs in the supplement or the response letter. Also list what was lost: a hook, an
    example, a voice, an argument. The reading measures' "What moved" list is the starting point.
11. **Said once.** The same disclaimer, pointer or limitation repeated in the Abstract, Introduction,
    Discussion and Conclusion. Fix: once, in the place a reader looks for it.

## The ending and the whole

12. **What the paper argues against.** If the recorded direction has one, is it named fairly, with a
    citation, early enough to give the reader a reason to read on? Never invent one.
13. **The ending.** Does the last paragraph end on what the reader can do (use it, try the demo, extend
    it), or on the open question the work raises, rather than on a limitation or a restatement?
14. **Memory.** After the reader panel, do the three things readers remember match `story.remember`?
15. **The boring checklist.** A satirical guide to writing boringly lists "avoid focus", "avoid
    originality and personality", "remove implications and speculations" and "use many abbreviations"
    (Sand-Jensen 2007). Read a revision against it: each point a revision moved towards is a cost to the
    reader. Acronyms in the title and Abstract also go with fewer citations (Martínez & Mammola 2021).

## Sources

- Gopen, G. D., & Swan, J. A. (1990). The science of scientific writing. *American Scientist*, 78(6),
  550–558.
- Gustafson, A., & Rice, R. E. (2020). A review of the effects of uncertainty in public science
  communication. *Public Understanding of Science*, 29(6), 614–633. https://doi.org/10.1177/0963662520942122
- Hillier, A., Kelly, R. P., & Klinger, T. (2016). Narrative style influences citation frequency in climate
  change science. *PLoS ONE*, 11(12), e0167983. https://doi.org/10.1371/journal.pone.0167983
- Martínez, A., & Mammola, S. (2021). Specialized terminology reduces the number of citations of scientific
  papers. *Proceedings of the Royal Society B*, 288, 20202581. https://doi.org/10.1098/rspb.2020.2581
- Mensh, B., & Kording, K. (2017). Ten simple rules for structuring papers. *PLoS Computational Biology*,
  13(9), e1005619. https://doi.org/10.1371/journal.pcbi.1005619
- Olson, R. (2015). *Houston, We Have a Narrative*. University of Chicago Press.
  https://doi.org/10.7208/chicago/9780226270982.001.0001
- Sand-Jensen, K. (2007). How to write consistently boring scientific literature. *Oikos*, 116(5),
  723–727. https://doi.org/10.1111/j.0030-1299.2007.15674.x
- Schimel, J. (2012). *Writing Science: How to Write Papers That Get Cited and Proposals That Get Funded*.
  Oxford University Press.
- van der Bles, A. M., van der Linden, S., Freeman, A. L. J., & Spiegelhalter, D. J. (2020). The effects of
  communicating uncertainty on public trust in facts and numbers. *PNAS*, 117(14), 7672–7683.
  https://doi.org/10.1073/pnas.1913678117
