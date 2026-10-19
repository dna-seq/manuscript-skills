# The reader panel

Referees decide whether a paper is published; readers decide whether to keep reading it. The panel gives
the authors the second judgement while they can still act on it. It is three readers who have never seen
the paper, each reading as one kind of reader would. They report what happened to their attention; they
do not grade the paper and they do not referee it.

## Independence

Run each seat as a separate agent with fresh context when the harness offers one. Give it the manuscript
(and its figures, when they are files) and its seat's brief, nothing else: not the record, not the
authors' notes or messages, not earlier reports, not the other seats' answers, not this skill's other
files. Without agents, read once per seat, in order, and do not revise one seat's answer after reading as
the next. A seat that has read the authors' intentions can no longer tell them whether the text conveys
them.

## The seats

Adapt the seats to the readers the record names (`story.readers`): when the authors name specific
audiences, give each seat one of them. Otherwise use these three.

1. **The skimmer.** A busy researcher in the field deciding, from a preprint feed or a table of contents,
   whether to read on. Reads the title, the Abstract, every figure and table caption, the first sentence of
   each paragraph and the Conclusion, in that order, and nothing else.
2. **The potential user.** Someone who could use the method, tool or result in their own work. Reads the
   whole paper asking: what would I get, what would I see, could I run or apply it, what would stop me.
3. **The informed outsider.** A scientist from a neighbouring field (for a genomics tool, a biologist or a
   clinician-scientist without bioinformatics training; for a method paper, a domain scientist who would
   use its results). Reads the whole paper and notes every term, abbreviation or step that stopped them.

## What each seat returns

```yaml
seat: skimmer | user | outsider          # or the reader named in story.readers
stopped_at:                              # where attention dropped, or "finished"
  section: "4.2 PRS Computation"
  quote: "the first sentence where it dropped, verbatim"
  why: "one sentence in the reader's own terms"
takeaway: "the one sentence I would tell a colleague about this paper"
remembered: ["up to three things I would still remember tomorrow"]
wanted:                                  # what I looked for and did not find
  - looked_for: "what a report looks like"
    looked_in: "Figures 1 to 3, section 2.3"
stumbles:                                # terms or passages that stopped me
  - quote: "verbatim"
    section: "2.2"
    problem: "undefined term | assumed knowledge | lost the thread | repetition | too many numbers"
next: "read the full text | try it | cite it | forward it | stop here"
because: "one sentence"
```

No scores, ratings or predictions. Quotes are verbatim; a seat that cannot point to a passage says where
it looked.

## Prompt for a seat

> You are [seat brief]. You have never seen this paper and know nothing about its authors. Read it as that
> reader would, [reading order for the seat]. Then answer in the format below. Be honest about where your
> attention dropped and why; quote the paper's own words. Do not review its science, recommend a decision
> or suggest edits: say only what happened to you as a reader.

## Putting the answers together

- Put the three takeaways beside `story.remember`, the sentence the authors want readers to keep. Where
  they differ, quote both: that difference is the main finding of the panel.
- List the places attention dropped, by section; two seats stopping at the same passage is a strong
  signal, one seat is a place to read.
- Merge what readers wanted and did not find; each item is a question for the story tests (an output not
  shown, a difference from a known tool not stated).
- Collect stumbles into a list of terms to define at first use or keep out of the Abstract.
- Never average, count votes or turn the answers into a score.

## Limits

Simulated readers are not readers. They read every word they are told to, tire less and know more than
the people they stand for; a colleague's cold read is better evidence, and the authors may prefer to give
the panel's brief to one. Use the panel to find passages to fix, not to show that a paper is interesting.
