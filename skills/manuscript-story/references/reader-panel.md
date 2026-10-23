# The reader panel

Referees decide whether a paper is published; readers decide whether to keep reading it. The panel gives
the authors the second judgement while they can still act on it. It is three readers who have never seen
the paper, each reading as one kind of reader would. They report what happened to their attention; they
do not grade the paper and they do not referee it.

## Independence

Prepare the reading copy before dispatch: remove revision markers, hidden comments and internal draft
notices or author planning notes that will not appear in the paper. Preserve scientific text and caveats.
Keep the source snapshot and record what was excluded in the parent run, outside the readers' briefs.
Reading measures that omit front matter do not make the exported file itself a clean reading copy.
If a source artifact cannot be removed confidently, retain it and state the resulting limit on the panel.

Each seat is a separate fresh agent, as
[Independent readers and referees](../../manuscript-integrity-check/references/project-workflow.md#independent-readers-and-referees)
requires: a new agent per reader, never a fork of the coordinator and never one that has worked on the paper,
started by the session that can start agents (in manuscript-improve, the coordinator itself). Give it the
manuscript, its figures as images and its seat's brief, nothing else: not the record, not
the authors' notes or messages, not earlier reports, not the other seats' answers, not this skill's other
files, and no summary or hint from the coordinator. Record each reader with `--isolation fresh-agent`. When the authors chose more than one model, each reader
also reads on each chosen model, as `skimmer@codex`, through
[manuscript-other-models](../../manuscript-other-models/SKILL.md), recorded with `--model`; readers on
different models are reported side by side, never averaged. Only
when the host cannot start agents at all, read once per seat, in order, do not revise one seat's answer
after reading as the next, record `--isolation one-agent` and say in the report that these readers were not
independent. A seat that has read the authors' intentions can no longer tell them whether the text conveys
them.

Readers look at figures before they read sentences, so every seat's workspace holds them: `figures/`, made
with `uv run --script ../manuscript-figures/scripts/figures.py workspace PAPER --into WORKSPACE/figures`,
one PNG per figure (a PDF, SVG or EPS figure rendered) and `index.md` with each figure's number, caption and
file. Nothing else goes with them: no measurement and no other stage's view of a figure.

## The seats

The authors choose who reads. Use, in this order: the readers saved for the project
(`readers` in `.manuscript-skills.yaml`, set with `project.py configure ROOT --reader "clinician: a
hospital physician who orders genetic tests" --reader ...`), the readers the record names
(`story.readers`), or these three defaults. Ask once, at first use, only when the paper's audience is
unclear: one question listing the defaults and a few alternatives that fit the paper (a bioinformatician,
a wet-lab biologist, a clinician, a biology student, an informed enthusiast, a random curious person),
and save the answer. Each seat reads the whole paper, so more than five or six costs more than it adds.

1. **The skimmer.** A busy researcher in the field deciding, from a preprint feed or a table of contents,
   whether to read on. Reads the title and the Abstract, looks at every figure with its caption and every
   table caption, then reads the first sentence of each paragraph and the Conclusion, in that order, and
   nothing else.
2. **The potential user.** Someone who could use the method, tool or result in their own work. Reads the
   whole paper asking: what would I get, what would I see, could I run or apply it, what would stop me.
3. **The informed outsider.** A scientist from a neighbouring field (for a genomics tool, a biologist or a
   clinician-scientist without bioinformatics training; for a method paper, a domain scientist who would
   use its results). Reads the whole paper and notes every term, abbreviation or step that stopped them.

A seat the authors name gets a brief in the same form: who the reader is, why they opened the paper, and
the order they read in (a skim like the skimmer's, or the whole paper).

## Reading is a funnel, along each reader's own path

Readers do not read in page order. A skimmer reads the Abstract and the figures; a clinician jumps from
the Abstract to the results and the Discussion; a potential user goes to the methods and the
availability statement; many skip the Methods entirely. Each seat reads in the order a reader of its kind
would, and records its **path**: the sections it visited, in that order, each read, skimmed or skipped.
Skipping a section is not leaving. **Leaving** is closing the paper: the place on the path where a real
reader of this kind would stop and not come back. Before that, each **dip** is a passage where attention
dropped and came back. After leaving, the seat may read on for the panel (to report what it would have
missed), but its verdict, `next`, follows from where it left. A reader who left before reaching what it
came for can only stop, bookmark the paper or forward it to someone better placed; "try it" and "cite it"
need a reader who got that far.

## What each seat returns

```yaml
seat: skimmer | potential-user | informed-outsider | the name of a reader saved for the project
path:                                    # the sections in the order this reader visited them
  - {section: "Abstract", how: read}     # read | skimmed | skipped
  - {section: "Figure 1", how: skimmed}
  - {section: "2. Platform Architecture", how: skipped}
  - {section: "5. Benchmarking and Validation", how: read}
left:                                    # where on that path a real reader of this kind would close the paper
  section: "5.2 PRS Computation"         # or "finished" when they reached the end of their path
  quote: "the sentence where they gave up, verbatim"
  why: "one sentence in the reader's own terms"
dips:                                    # attention dropped and came back, before leaving
  - section: "2.2"
    quote: "verbatim"
    why: "one sentence"
takeaway: "the one sentence I would tell a colleague about this paper, from what I read before leaving"
remembered: ["up to three things I would still remember tomorrow"]
wanted:                                  # what I looked for and did not find
  - looked_for: "what a report looks like"
    looked_in: "Figures 1 to 3, section 2.3"
stumbles:                                # terms or passages that stopped me
  - quote: "verbatim"
    section: "2.2"
    problem: "undefined term | assumed knowledge | lost the thread | repetition | too many numbers"
next: "stop here | bookmark | forward it | read the full text | try it | cite it"
because: "one sentence; a reader who left before what it came for cannot try or cite it"
```

No scores, ratings or predictions. Quotes are verbatim; a seat that cannot point to a passage says where
it looked. The parent checks that `next` agrees with `left` and returns a seat's answer that does not.

## Prompt for a seat

> You are [seat brief]. You have never seen this paper and know nothing about its authors. Read it as that
> reader would, [reading order for the seat]. The figures are images in `figures/` (listed in
> `figures/index.md`): open each one when your reading reaches it, as you would look at it on the page, and
> say what it told you or where it lost you, like any passage. Then answer in the format below. Be honest about where your
> attention dropped and why; quote the paper's own words. Do not review its science, recommend a decision
> or suggest edits: say only what happened to you as a reader.

## Putting the answers together

- Put the three takeaways beside `story.remember`, the sentence the authors want readers to keep. Where
  they differ, quote both: that difference is the main finding of the panel.
- Draw the funnel along each reader's path: how many seats were still in the paper at each step, and
  which sections each skipped. Where readers leave is the main thing to fix, and two seats leaving at
  the same passage is a strong signal; a section most readers skip is only a problem when what they
  came for is in it.
- List the dips by section; they are places to read, not places readers were lost.
- Merge what readers wanted and did not find; each item is a question for the story tests (an output not
  shown, a difference from a known tool not stated).
- Collect stumbles into a list of terms to define at first use or keep out of the Abstract.
- Never average, count votes or turn the answers into a score.

## Limits

Simulated readers are not readers. They read every word they are told to, tire less and know more than
the people they stand for; a colleague's cold read is better evidence, and the authors may prefer to give
the panel's brief to one. Use the panel to find passages to fix, not to show that a paper is interesting.
