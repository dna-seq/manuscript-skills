# Optional checks: robustness, model diversity, decision distribution

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

Seats can run on different model families. It reduces shared blind spots somewhat; it does not make
the seats independent, and the report never calls them independent on that basis. Record the model used
for each seat. Send the manuscript to another provider only when the user agrees to that provider, in
either mode.

## Decision distribution (only on request)

When the authors ask how referees might decide, run a separate step after adjudication: give each seat
(fresh) the manuscript and ask for the decision it would recommend (accept, minor revision, major
revision, reject) with its main reason. Report the counts, for example "of five simulated seats: three
major revision, two reject; the reject reasons both cite the benchmark split". Label it:

> Uncalibrated. These are the dispositions of simulated seats sharing one model, not editors' decisions
> or a probability of acceptance.

Never convert the counts into a percentage or a score, and never ask for decisions in the same pass as
findings: a seat that has committed to a decision argues for it.
