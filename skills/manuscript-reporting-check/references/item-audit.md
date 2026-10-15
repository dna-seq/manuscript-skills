# Auditing items

How to fill the table `scripts/guidelines.py items ID --manuscript PAPER` prints, and how to report it.

## States

Give every item exactly one state:

| State | Use when |
|---|---|
| `present` | The manuscript reports what the item asks, at a place you can cite. |
| `partial` | Part is reported (the platform but not the call rate; the test but not the correction). Say what is missing. |
| `missing` | You read where it belongs and in the supplement you were given, and it is not there. |
| `not_applicable` | The item does not fit this study (loss to follow-up in a cross-sectional study). Give the reason in a few words. |
| `unclear` | The material needed to judge was not supplied (the supplement, a protocol, a figure). Name the material. |

`unclear` is not `missing`: an item the authors may have reported in a supplement you did not receive is
`unclear (material not supplied)`. A check that could not run is `not_assessed` in the shared vocabulary
of [manuscript-record.md](../../manuscript-integrity-check/references/manuscript-record.md#shared-outcome-words);
in this table the item is `unclear`.

## Evidence

- **Present and partial**: a location (section and line, table or figure) and a short verbatim quote that
  shows it. Quote; do not paraphrase the manuscript into compliance.
- **Missing**: where you looked ("Methods, Statistical analysis; Supplementary Methods S2").
- **One item, one judgement.** An item met by a sentence that says something vaguer than the item asks
  (a "standard QC pipeline" for genotyping error and call rates) is `partial`, with the missing detail
  named.
- Do not mark an item present because a related item is. HWE testing is not population stratification;
  a significance threshold is not a multiple-testing method unless it states how it corrects.

## What a gap costs

Say what a missing item costs only when the venue requires the guideline or its form
(`guideline-selection.md`, case 1): the form missing at submission is often a return before review; an
item marked present that is not invites an office query; a substantive gap (no population stratification
method in a multi-ancestry association study) is a likely referee request. Without such a requirement the
gap is advice: rank it by what it does to the reader's ability to judge the result, not by checklist
order.

## Severity in the report

Use the shared severities in
[author-priorities.md](../../manuscript-integrity-check/references/author-priorities.md#findings-and-stopping):

- **Blocker** only for a verified submission barrier: the venue requires the form or guideline and the
  live page confirms it.
- **Major** for a gap that threatens how a result can be read (no correction for 48 tests with nominal
  P values reported as findings; no stratification control across ancestries), or an item the venue
  requires.
- **Optional** for the rest, with the benefit in one phrase.
- **Uncertain / not assessed** for `unclear` items whose material matters.

## Reporting gaps are not new experiments

A missing item asks the authors to **report** what they did. When they did not do it, say so plainly and
offer the options: report it as a limitation, run an analysis that existing data allow (adding principal
components from genotypes already in hand, applying a correction to P values already computed), or narrow
the claim. Do not turn a reporting gap into a demand for new samples, a new cohort or wet-lab work; that
is a scientific judgement for the authors and for `manuscript-peer-review`, and an unaffordable
requirement is a venue question for `manuscript-journal-select`.

Never write the missing text with invented values. Where a sentence needs a fact only the authors have
(a call rate, a software version, the number genotyped), mark it `author input needed` and ask.

## The report

Lead with what matters, then the table:

1. The guidelines applied and why (designs, conditions met, venue requirement or none), with versions.
2. The gaps that matter: major first, each with item, location or where you looked, what to add, and its
   cost when the venue requires the guideline.
3. `author input needed`: the facts only the authors can supply, as short questions.
4. The full item table, when the authors want it or the venue asks for a completed checklist. Otherwise
   offer it rather than printing 40 rows. For a venue's form, give one answer per official item number
   (state, location, short quote) ready to transfer; the authors complete the form, and its text is never
   copied.

Record the manuscript's sha256 (the `items --manuscript` header does this) so a later run can tell
whether the audit still describes the current text. When the project keeps `manuscript-record.yaml`, add
a `checks` entry for this skill with the scope (`reporting: STREGA+STROBE`), the sha256 and a one-line
summary, and hand unresolved gaps on as `open_issues`. Reuse an earlier audit only for unchanged
sections.
