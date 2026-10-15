# Domain module: AI systems

Questions a referee asks when the paper's tool or method runs a large language model, an agent or
another AI system as part of what it delivers. They are prompts for the seats that load this module,
not a checklist: skip what does not apply, and raise a concern only when it passes the
claim-consequence gate.

## Load it when

- the contribution drafts, extracts, curates, classifies, codes or answers with an LLM, an agent, an
  assistant plugin or tool server (for example an MCP server), or another generative or foundation
  model, and the paper claims something about what that system produces;
- or the paper evaluates such systems: a benchmark of LLMs or agents, a comparison of assistants, an
  error or hallucination audit.

## Do not load it when

- AI helped write the paper or the code and is not part of the contribution: that is a disclosure
  question for manuscript-journal-adapt and manuscript-integrity-check, never a referee concern;
- the model is a conventionally trained predictor (a regression, a gradient-boosted model, a CNN)
  evaluated on held-out data in the usual way: the evidence-statistics seat's questions and, for
  genomic data, [genomics.md](genomics.md) cover it;
- AI produced the paper's scientific content (an AI-scientist study, design `ai-generated-science`):
  use [ai-science-design.md](../../../manuscript-integrity-check/references/ai-science-design.md) as
  [seats.md](../seats.md#choosing-the-panel) says, and this module only for the system's own outputs.

Record in the output why the module was loaded.

## Baseline without the tool

- Is the same task done without the tool and scored the same way: the model alone (no tools, no
  retrieval, the same prompt), a simple script or an existing tool, and a person where the claim is
  about saving expert time? Without one, a score shows what the system produces, not what the tool
  adds.
- When the paper credits a component (retrieval, a validator, a tool call) for the result, is there a
  comparison with that component removed, or should the credit be stated more narrowly?

## Errors and hallucinations, with denominators

- Is each error class counted with its denominator and sampling: fabricated identifiers or citations,
  wrong values, statements the cited source does not support, omissions? "Few errors" without "of how
  many items, chosen how" cannot be judged.
- Are errors counted before and after the tool's own checks, so the checks' contribution is visible?
- A provenance audit (do the cited sources exist) is not a hallucination rate (do the sources say what
  the output says). Which one did the paper measure?
- Who built the reference the outputs are scored against, and was it built independently of the
  system's developers and held out from prompt tuning? Was scoring blinded to which system produced
  the output? How many curators, and how far did they agree?

## Curator correction burden

- When people review the system's drafts before use, what share of outputs needed correction, how much
  was changed (rows edited, values overridden, items rejected) and how long did review take? A
  correct-after-review result says little about the system without this.
- Does the output work for its purpose downstream (a generated module annotates correctly, generated
  code runs on the stated inputs), or was only its format validated?

## Prompt injection and untrusted input

- The system reads content it does not control (papers, web pages, user files, tool outputs). Can that
  content instruct it? Is the behaviour under adversarial input described or tested?
- Which actions can the system take without a person confirming (writing files, publishing, deleting,
  registry or account actions), and with whose permissions? A claim of safety or "human in the loop"
  needs the boundary stated.

## Models, versions and reproducibility

- Are the model names, versions or snapshot dates, providers, decoding settings (temperature, seed
  where available) and the prompts released, so that the evaluation can be repeated?
- How much do results vary between runs of the same model? A claim that the tool works "with any
  assistant" or across hosts needs results from more than one model; otherwise it is a claim about the
  model tested.
- Could test items, or the papers they come from, be in the model's training data? The contamination
  channels are listed in
  [ai-science-design.md](../../../manuscript-integrity-check/references/ai-science-design.md#step-3-contamination-four-channels).

## Cost

- Tokens or API cost, wall time and hardware per item or per run, when the paper claims the tool saves
  time or money, or invites adoption.

## Conclusions that no evaluation scores

- Which outputs are free text (conclusions, summaries, interpretations, recommendations) that no
  metric in the paper measures? Claims about their quality then rest on examples alone.
- Can a user tell what came from a cited source from what the model inferred? When outputs make
  statements about health, load [human-data-and-clinical.md](human-data-and-clinical.md) as well.

## What the seat does not demand

- Every model on the market, or closed models the authors cannot access or afford; the comparators a
  referee will expect are the model without the tool and the obvious non-AI route.
- A user study when no claim is about users, or a fixed number of runs, raters or ablations as a
  package: ask for what a claim needs.
- "AI-generated" as a defect in itself. The question is whether the outputs are measured.

## Handing over

- Disclosure of AI use in writing the paper: manuscript-journal-adapt.
- Reporting guidelines for AI evaluations (TRIPOD-LLM, TRIPOD+AI, REFORMS and others): route the gap
  to manuscript-reporting-check; raise it here only when the missing item stops a claim from being
  judged.
- Data protection when the system sends user data to a model provider: manuscript-policy-fit.
