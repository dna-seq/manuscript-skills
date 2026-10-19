# Independent review and retest: manuscript projects and durable runs

Review date: 2026-10-19. Retested the uncommitted working tree after the fixes to the initial independent review. **All six original findings are resolved in the tested paths. No remaining concrete regression was observed in this pass.**

This was a read-only source review plus isolated command execution. Source, manuscript and existing review artifacts were not edited. The only repository file created by this pass is this requested report. Synthetic projects and command outputs used a fresh temporary directory with a separate `MANUSCRIPT_SKILLS_CONFIG`; the results below do not depend on retaining that directory.

## Original findings and retest results

| Original finding | Current implementation and direct reproduction | Result |
|---|---|---|
| Interrupted commands lost output and attempt metadata. | `scripts/runs.py:261-277` records the running attempt before launching and sends subprocess stdout/stderr directly to exclusive durable files. Launched a command that printed `durable-before-interrupt` with `flush=True`, wrote a startup marker and slept. After observing the marker, terminated its POSIX process group with SIGTERM. Output and the running attempt remained. A retry retained the original output, registered all four stdout/stderr artifacts and produced attempts `(1, interrupted, null)` and `(2, finished, 0)` plus explicit interruption issues. | Fixed. The new pytest regression independently exercises actual process-group SIGKILL. |
| A manuscript folder resolved ready, then crashed startup. | `scripts/project.py:144-152` flags a local manuscript source that is not a file. Configured `--manuscript .` in a synthetic folder containing `main.tex`. Resolve returned exit 3, status `conflict`, with the instruction to select the authoritative source file. Start returned exit 3 and did not create the output directory. The shared workflow now explains how to handle a supplied folder. | Fixed through targeted setup validation. |
| The documented two-seat quick review could never complete. | `scripts/runs.py:173-181` validates the recorded mode. Added a report, `seat` artifacts for `desk-editor` and `evidence-statistics`, and defence/adjudication artifacts. Default full-mode completion correctly failed; `finish --review-mode quick --status completed` succeeded, and final validation returned `valid: true`, `workflow_complete: true`. The index records the selected mode. | Fixed without fabricating full referee reports. |
| Lasting edit preferences were saved globally and remained ineffective in an initialized project. | `references/author-priorities.md:119-121` now routes manuscript preferences through `project.py configure PROJECT --edits CHOICE`, reserving `settings.py` for explicit global changes. Ran the documented project command with `apply`: resolve returned `apply` from `project`; a transient `propose` override applied once; the following resolve returned `apply`; no global settings file was created. `manuscript-story/SKILL.md:29` now names the project resolver. | Fixed in both instructions and command behavior. |
| Invited-referee instructions conflicted with durable evidence retention. | `manuscript-peer-review/references/invited-referee.md:28-32` now retains the draft report, seat findings and checks in the configured private run folder, forbids automatic deletion/publication, and handles explicit confidentiality/deletion instructions as stated retention limits. Read against the shared project contract and the skill's existing panel instructions. | Fixed. Invited mode uses the full panel; the initial panel-validation incompatibility concerned quick mode. |
| Deleting an authoritative manuscript silently passed final validation. | `scripts/runs.py:146-151` now reports a missing original. Started a run, added a report, finished it, then deleted only the synthetic source. `validate --final` returned exit 1, `valid: false`, `workflow_complete: false`, with `Authoritative source is missing or no longer a file`. | Fixed. |

Script paths in the first four and final rows are relative to `skills/manuscript-integrity-check/`.

## Checks executed

```text
uv run pytest tests/test_project_runs.py tests/test_settings.py tests/test_scripts.py tests/test_peer_review.py tests/test_story.py -q
395 passed in 12.87s

git diff --check
exit 0; no diagnostics
```

The suite includes the genuine interrupted-command regression and the three additional journal-helper regressions: an unknown venue limit cannot become a shared mandatory cap, a disclosure rule cannot invent a language-polish exemption, and a selected journal watches inherited publisher policies. Their implementation diffs were also inspected.

The direct reproductions used `typer.testing.CliRunner` for setup, run creation, registration, finishing and validation. The interruption reproduction launched the actual `runs.py exec` command with the active Python interpreter and a new process session; termination happened only after the child marker proved that the command had started. No network calls or real manuscript analysis were needed.

## Scope and limits

This pass verifies the original behavioral defects, related instructions and the offline regressions. It does not establish scientific correctness, reviewer independence, completeness of manual edit classification, actual before/after delivery in a conversation, cloud upload behavior or Windows process termination. The helper and shared contract appropriately describe those limits. Existing actual-manuscript smoke outputs were left unchanged.

## Reviewed file fingerprints

These hashes identify the uncommitted source revisions read at report creation; a later source change requires a new review rather than treating this report as validation of that change.

Recorded at: 2026-10-19T15:40:25.253257+00:00

- `skills/manuscript-integrity-check/scripts/project.py`: `af8ed09586dfe48dcf853aadd8e0244c9c0625afe86c8f32a107fce37293f987`
- `skills/manuscript-integrity-check/scripts/runs.py`: `e7a4af71c1a3b544de8c8fc4b74a574c19d449ca9bce685abb1f788356e20b16`
- `skills/manuscript-integrity-check/references/project-workflow.md`: `3089ba7b9e837395b8c4d604c2050f2d3c9137225540a0e36b2f5e5adffbe6f7`
- `skills/manuscript-integrity-check/references/author-priorities.md`: `e70732f6fcfb0623a900361f3c7b79237d2adc62c25808b4766af8a88042eb56`
- `skills/manuscript-story/SKILL.md`: `a2a3dd06a6110974f5e245ad32a2194a416e0a6b5692248d1626a0af8bc67510`
- `skills/manuscript-peer-review/references/invited-referee.md`: `a2699466a3c631f4bd1c26489ff575dca34d261c16e5f612350f37569def58be`
- `skills/manuscript-journal-adapt/scripts/venues.py`: `48a9a37b281e61cfdbf5b1c3ab369fa5a84a3bf88c07f871cb24ee7c81cc8cf4`
- `skills/manuscript-journal-adapt/scripts/policy_watch.py`: `3bbeceb6e59bcc6db7d6a751a7a22504708b0205ada142d32ff9ca434a3d113b`
- `tests/test_project_runs.py`: `14bcfb5904f476724387b3d791a669318afe8ce7f4bbe398c81ab2d808b14922`
- `tests/test_scripts.py`: `971fac3d78123684f745da078f4731e2ecf2651069fc12635161e7a10fea7d5c`
