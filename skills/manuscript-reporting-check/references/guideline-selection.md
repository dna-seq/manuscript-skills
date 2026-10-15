# Choosing reporting guidelines

Read this before selecting guidelines for a manuscript. The data is `guidelines.yaml`; the helper is
`scripts/guidelines.py select`.

## Select by design, not by field

A discipline label ("bioinformatics", "genomics", "epidemiology") does not choose a guideline. The study's
design does. Use the keys in
[manuscript-record.md](../../manuscript-integrity-check/references/manuscript-record.md#study-design-keys),
taken from the record when it exists, otherwise from the Methods. Confirm the designs with the authors only
when the Methods leave them genuinely open; do not interview them for what the paper already says.

- **Mixed studies list several keys.** A GWAS whose hits feed a polygenic score and an MR analysis is
  `genetic-association`, `polygenic-score` and `mendelian-randomization`: STREGA (with STROBE), PRS-RS
  and STROBE-MR each apply to their own part. Audit each part against its own guideline; do not force the
  whole paper through one checklist, and do not claim compliance with one when another part needs a second.
- **Extensions bring their base** when `base_items` is `interleave` or `append` (STREGA keeps all STROBE
  items; STARD-AI keeps STARD's content). STROBE-MR is stand-alone (`base_items: none`).
- **`applies_if` is a condition, not a suggestion.** STARD is a candidate for an observational study but
  applies only when the study estimates diagnostic accuracy against a reference standard; DOME only when a
  supervised model is trained or evaluated; PRS-RS only when a polygenic score is developed, validated or
  its predictive performance reported (a tool or report that applies published scores names their PGS
  Catalog IDs, build and missing-variant handling instead); MINSEQE only for sequencing data, MIAME only
  for microarrays. Decide from the Methods and say which way you decided.
- **Minimum-information standards** (MINSEQE, MIAME, MIxS) describe what a deposited dataset must carry.
  Audit them against the deposition and its description in the paper, together with the archive's own
  submission rules (GEO, ArrayExpress and the INSDC archives enforce most of them at deposit).

## When there is no guideline

A software tool, a database or resource, a method benchmark and a simulation study have no EQUATOR
reporting guideline. Say so in one line, then carry the weight with the availability and reproducibility
checks (`availability.md`) and the venue's own software or resource rules. Do not borrow STROBE or
TRIPOD for a tool paper, and do not invent a checklist. A tool that contains a trained model still gets DOME
for the model's validation; a tool paper that also reports an association study still gets STREGA for that
part. `design_notes` in `guidelines.yaml` holds the per-design advice.

Qualitative studies use SRQR or COREQ. Their texts are not bundled (no open licence was found), so audit
against the official checklist linked in `design_notes`.

## The venue decides what is required

Separate three cases and say which one applies:

1. **The venue requires the guideline or its form** (a reporting checklist on submission, a Reporting
   Summary, STAR Methods, an MDAR-based author checklist). `guidelines.py select --venue KEY` prints the
   rule venues.yaml records with its read date; verify it on the live page before calling it binding. Only
   then does a missing item have a cost: say whether it is likely a desk return (the form itself is
   missing), a query from the editorial office (an item marked present that is not), or a referee
   question.
2. **The venue endorses guidelines in general** ("we encourage EQUATOR guidelines"). Items are advice
   that makes review easier; report the gaps that affect validity or reproducibility first.
3. **Nothing is required.** Report gaps as optional advice. Do not demand a checklist the venue does not
   ask for, and never count a missing optional form as a defect.

Venue checklists (`kind: venue-checklist`) are selected only for the venues their `match` rule names, and
never for any other venue. `nature-editorial-policy-checklist` is recorded as withdrawn so that nobody asks
the authors for it.

## Versions, sources and licences

- Use the current version recorded in `guidelines.yaml` (CONSORT 2025, not 2010; TRIPOD+AI, not TRIPOD
  2015). If a venue explicitly asks for an older version, follow the venue and say so.
- Every entry records its EQUATOR page or defining paper, its licence and the date it was checked. If an
  entry's `checked` date is more than a year old, or a venue names a version the file does not have,
  re-check online before relying on it, and say what you checked.
- Item texts in `guidelines.yaml` are our paraphrases. Several checklists are not openly licensed (CARE is
  non-commercial; STARD-AI, PRS-RS, DOME and MIAME have no open licence found). When a venue wants the
  completed official form, prepare the answers keyed by the form's official item numbers (where in the
  manuscript, a short quote) for the authors to transfer into it; do not reproduce checklist text into the
  manuscript, the answers or the plugin.

## Hand-offs

- `manuscript-policy-fit` decides whether ethics approval, consent, trial registration or privacy rules
  apply. This skill only checks that a declaration the chosen guideline or venue requires is present, and
  routes any question of applicability there.
- `manuscript-journal-select` handles a venue whose required checklist is unaffordable (for example one
  that needs data the authors cannot obtain); this skill reports the requirement, not a new study.
