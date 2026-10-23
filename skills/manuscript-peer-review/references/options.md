# Optional checks: robustness, model diversity, a panel per journal

None of these runs by default. Each multiplies the cost; offer them when the stakes justify it (a
high-impact submission, a resubmission after a rejection that felt arbitrary) or when the authors ask.

## Robustness check (meaning-equivalent rewrite)

Tests whether a confirmed finding is about the science or about the wording.

1. Pick the sections that carry the confirmed findings (often the abstract and the results paragraph
   behind the headline claim).
2. Write a meaning-equivalent rewrite of those sections under the
   [prose-edit contract](../../manuscript-prose-edit/references/prose-edit-contract.md): same claims,
   numbers, citations, hedges and scope. Check it with
   `../manuscript-prose-edit/scripts/guard.py ORIGINAL REWRITE` and read the diff. The rewrite is a test
   object; it never replaces the authors' text.
3. Run the seats that raised the findings again, fresh, on the manuscript with the rewritten sections.
4. Compare:
   - a finding that persists is about substance;
   - a finding that disappears depends on wording: either the original phrasing invites a misreading
     (triage it as a **misread risk** and say which phrasing triggered it) or the original finding was
     itself a misread (check it again before reporting);
   - a new finding that appears only on the rewrite usually means the rewrite changed meaning; check the
     guard output and the diff before trusting it.

This is a diagnostic of the review, not a way to tune text until an automated reviewer is satisfied.
Never iterate rewrites against the panel to reduce its findings.

## Model diversity

Seats can also run on other models, through the command-line agents the authors already use (Codex CLI,
Claude Code, Gemini CLI), with [manuscript-other-models](../../manuscript-other-models/SKILL.md): every
seat runs on the host and once more on each chosen model, as `skeptic@codex`, in a fresh session of its
own. It reduces shared blind spots somewhat; it does not make the seats independent, and the report never
calls them independent on that basis or counts agreement between models as confirmation. Record the model
of every seat (`runs.py add --model`). Send the manuscript to another provider only when the user asks
for that provider or saved it for the project (`other_models`), in either mode.

## A separate panel for each journal

When the simulation covers the top three journals of a ladder, the default panel referees the paper once
and each referee gives a recommendation for each journal (SKILL.md, step 2): the science it judges does
not change between journals, while the bar, the scope and the article type do. Authors who want each
journal's review to be independent of the others can ask for a separate panel per journal: three
referees with only that journal's `venue.md`, and one defence pass over all the findings. It triples the
whole-paper reads (nine instead of three, plus the defender) and mostly repeats the same concerns, so
offer it rather than run it.
