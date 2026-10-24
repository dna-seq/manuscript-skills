# Auditing items

How to fill the table `scripts/guidelines.py items ID --manuscript PAPER` prints, and how to report it.

## States

Give every item exactly one state:

| State | Use when |
|---|---|
| present | The manuscript reports what the item asks, at a place you can cite. |
| partial | Part is reported (the platform but not the call rate; the test but not the correction). Say what is missing. |
| missing | You read where it belongs and in the supplement you were given, and it is not there. |
| not applicable | The item does not fit this study (loss to follow-up in a cross-sectional study). Give the reason in a few words. |
| unclear | The material needed to judge was not supplied (the supplement, a protocol, a figure). Name the material. |

Unclear is not missing: an item the authors may have reported in a supplement you did not receive is
unclear (material not supplied). A check that could not run is `not_assessed` in the shared vocabulary
of [manuscript-record.md](../../manuscript-integrity-check/references/manuscript-record.md#shared-outcome-words)
(the record and JSON); in this table the item is unclear, and the report says why in words.

## Evidence

- **Present and partial**: the section, table or figure (a line number in parentheses at most) and a short
  verbatim quote that shows it. Quote; do not paraphrase the manuscript into compliance.
- **Missing**: where you looked ("Methods, Statistical analysis; Supplementary Methods S2").
- **One item, one judgement.** An item met by a sentence that says something vaguer than the item asks
  (a "standard QC pipeline" for genotyping error and call rates) is `partial`, with the missing detail
  named.
- Do not mark an item present because a related item is. HWE testing is not population stratification;
  a significance threshold is not a multiple-testing method unless it states how it corrects.

## What a gap costs, and when it is fixed

Say what a missing item costs only when the venue requires the guideline or its form
(`guideline-selection.md`, case 1): the form missing at submission is often a return before review; an
item marked present that is not invites an office query; a substantive gap (no population stratification
method in a multi-ancestry association study) is a likely referee request. Without such a requirement the
gap is advice: rank it by what it does to the reader's ability to judge the result, not by checklist
order.

Each gap also has a stage, the
[order of work](../../manuscript-integrity-check/references/author-priorities.md#order-the-work-by-when-it-can-be-done).
A missing item that shows missing science (an analysis, comparison, correction or method the conclusions
need: no correction for 48 tests, no stratification method across ancestries) is **Fix now**. Every other
missing item of a checklist is **Once you have chosen the journal**: it is completed with the journal's
form, and it counts against readiness only when that journal requires the form and the authors are about
to submit.

## Severity in the report

Use the shared severities in
[author-priorities.md](../../manuscript-integrity-check/references/author-priorities.md#findings-and-stopping):

- **Blocker** only for a confirmed scientific defect (an analysis the conclusions need is missing or unsound,
  checked against the manuscript and its supplement), or a verified submission barrier when the authors are about
  to submit: the venue requires the form or guideline and the live page confirms it. If the authors decide not to
  provide a form, that is their decision, noted once with its consequence, not a blocker.
- **Major** for a gap that threatens how a result can be read (no correction for 48 tests with nominal
  P values reported as findings; no stratification control across ancestries), or an item the venue
  requires.
- **Optional** for the rest, with the benefit in one phrase.
- **Uncertain / not assessed** for unclear items whose material matters.

## Reporting gaps are not new experiments

A missing item asks the authors to **report** what they did. When they did not do it, say so plainly and
offer the options: report it as a limitation, run an analysis that existing data allow (adding principal
components from genotypes already in hand, applying a correction to P values already computed), or narrow
the claim. Do not turn a reporting gap into a demand for new samples, a new cohort or wet-lab work; that
is a scientific judgement for the authors and for `manuscript-peer-review`, and an unaffordable
requirement is a venue question for `manuscript-journal-select`.

Never write the missing text with invented values. Before asking, read the project's files when the manuscript
has a repository (run logs, release tags, configuration, result tables): a version or count tied to the run or
release behind the results (the tagged release, the benchmark's run log, the commit the paper cites) fills the gap,
quoted with its source; one that is not (a lock file or the latest tag shows today's project) is a proposal that
names its source, never a silent fill-in. Ask the authors only for what the files leave open (a call rate the logs
do not hold, the number genotyped), among the questions at the end of the report.

## The report

Lead with what matters, then the table:

1. The guidelines applied and why (designs, conditions met, venue requirement or none), with versions and
   the official page as a URL. A guideline you considered and found not to apply gets one sentence with
   the reason ("PRS-RS does not apply: the paper applies published scores and develops or validates
   none") and no item table.
2. The gaps that matter, under the report's stage headings (`../SKILL.md`, "The report"; "Fix now" first),
   major first within each. Each
   names the item in plain words (its number in parentheses), quotes the sentence that reports it only in
   part or says where you looked, says what to add, and gives its cost when the venue requires the
   guideline.
3. The facts only the authors can supply, as short questions.
4. The full item table, when the authors want it or the venue asks for a completed checklist. Otherwise
   offer it rather than printing 40 rows. For a venue's form, give one answer per official item number
   (state, location, short quote) ready to transfer; the authors complete the form, and its text is never
   copied.

Record the manuscript's sha256 (the `items --manuscript` header does this) so a later run can tell
whether the audit still describes the current text. When the project keeps `manuscript-record.yaml`, add
a `checks` entry for this skill with the scope (`reporting: STREGA+STROBE`), the sha256 and a one-line
summary that also names the guidelines considered and found not to apply, and hand unresolved gaps on as
`open_issues`. Reuse an earlier audit only for unchanged sections.
