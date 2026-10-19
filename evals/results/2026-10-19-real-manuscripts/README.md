# Real-manuscript smoke runs: project settings and retained skill evidence

Date: 2026-10-19. Plugin version: 0.7.0. These are actual runs on the authors' two connected manuscripts, not outputs generated from evaluation fixtures. The complete local runs retain source snapshots and command histories; selected actual reports and failure evidence are committed here for skill maintenance. Input/output hashes are in [evidence-index.json](evidence-index.json).

## Results

| Actual task | Report and evidence | Coverage |
|---|---|---|
| Paper 1, current Just-DNA-Lite v0.5 | [Story report](paper1/report.md), [three actual reader responses](paper1/readers/), [measures before/after](paper1/metrics-before-after.md) | Fresh independent skimmer, potential user and informed outsider; no manuscript-master edits. Partial full-story workflow: neighboring/exemplar comparison and full story gates were not repeated. |
| Paper 2, authoritative just-module-creator TeX, with bibliography and Paper 1 context | [Venue/sequence report](paper2/report-final.md), [conditional journal ladders](paper2/manuscript.journal-ladder.csv), [above-5 scenario](paper2/manuscript.journal-ladder-above5.csv), [preprint ladder](paper2/manuscript.preprint-ladder.csv), [record](paper2/manuscript.record.yaml) | Bounded standalone selection: three journals and two preprint routes. Both manuscript masters and existing venue strategy remain unchanged. Author priorities still need confirmation, so scenarios are conditional. |
| Paper 2 follow-up: trace the evaluation round | [Correction and provenance report](paper2/provenance-follow-up/report.md), [actual Git evidence](paper2/provenance-follow-up/evidence/round-completed.git-show.txt) | Local provenance investigation; later round identified, raw later archive unavailable. The earlier contradiction diagnosis is withdrawn. |

The original reports/records above are historical outputs, retained unchanged. Later the author
confirmed **fast publication, impact factor above 3**; the manuscript project's current recommendation
is BMC Bioinformatics then Bioinformatics. Funding and final venue choice remain unconfirmed.
The provenance follow-up below supersedes the original scientific diagnosis.

## What the real runs exposed

- The three readers remembered the FOXO3 example but continued to lose attention in implementation/PRS bookkeeping. Mixed measures (fewer long sentences, more words and slightly more caveat-ending sentences) were preserved rather than called a blanket improvement. A draft notice remained in the reading export; that limitation is recorded and the reader-panel preparation instructions now address it.
- The original Paper 2 report overstated a contradiction by comparing different rounds. A subsequent real-history investigation found that `fab4db5` intentionally replaced preparation a/b/a2 and `221b95f` completed later runs 1/2/3. The older scorer output remains valid for the older corpus; it cannot establish an error in the later table. The missing later raw archive is a reproducibility issue. The correction, contrary evidence and narrow instruction change are retained; old reports were not rewritten to hide this failure.
- The journal strategy had stale metrics/policy interpretations. The current primary-page findings and blocked reads are retained in [policy evidence](paper2/evidence/policy-evidence.md). The global venue catalogue was not silently rewritten by the smoke run; manuscript-specific records carry the observations.
- Two concurrent command captures collided in the first implementation. The helper now uses a filesystem lock and fails a competing writer without overwriting evidence. The surviving failed attempts and later successful checks remain visible.
- Independent forward testing found six additional gaps: actual interruption durability, folder sources, quick-pass panel validation, edit-preference scope, invited-review retention and missing authoritative sources. All six were fixed and independently retested; see [the independent report](../2026-10-19-project-runs-independent-review.md).
- Real journal generation exposed a sole known word cap promoted to a shared requirement, an invented language-polish exemption and missed inherited policy URLs. These were fixed and regenerated. An initial inheritance fix over-attributed another journal's fees/scope pages; its correction is covered by a separate regression. The original generated requirements are preserved beside the corrected output.
- Nine rejected artifact-role registrations exposed poor CLI discoverability. Roles are now a typed enum shown in help and rejected during argument parsing. See [failures](paper2/evidence/failures-and-contradictions.md) and [resolutions](paper2/evidence/smoke-resolutions.md).
- The provenance follow-up exposed an overbroad `README.md` reservation while retaining real source modules. The helper now protects only the generated skill-root index. Nested source READMEs retain their original paths/bytes. The new regression failed before the fix; all 211 integrity/project-run tests then passed. [Actual failure and retry context](paper2/provenance-follow-up/evidence/readme-registration-failure.md).

## Publication/update sequence produced by the smoke run

Make Paper 1 citable first. Reconcile Paper 2's evaluation before posting it, then cite Paper 1's preprint; Paper 2 need not await Paper 1's journal acceptance. Archive each paper's exact evidence/software versions, disclose overlap, and update companion citations when identifiers become available. The report retains preprint-route restrictions and the unresolved paper2 priority choice. This is a proposed plan, not a submission or publication action.

Follow-up: recover and reproduce the later round rather than substituting preparation scores. The
author's journal priorities are now resolved. No manuscript numerical correction was made.

## Verification and limits

The final full offline suite passed **1,188 tests**. The independent retest passed 395 relevant tests and confirmed its six original findings were fixed. Both real run manifests passed final artifact validation; Paper 1 remains explicitly partial. A successful manifest check establishes file delivery/coverage consistency, not scientific correctness or that an excerpt actually appeared in chat.

After that full-suite run, global-settings help wording and same-project source-revision guidance were clarified; the 54 project/settings tests were rerun. No validation logic changed in that final documentation clarification. No fresh full reference audit, formal referee panel, new biological experiment, manuscript rewrite, submission or external document update is represented by these smoke runs.

Final package validation found and repaired five pre-existing discovery-description issues, then passed
all 13 skills. The [initial failures and correction](../2026-10-19-package-validation.md) are retained.
