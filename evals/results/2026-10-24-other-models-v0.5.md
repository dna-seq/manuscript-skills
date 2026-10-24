# A referee panel on two models: Just-DNA-Lite v0.5 on Claude and Codex

Date: 2026-10-24. Skills: this repository at 0.15.0. Case: other-models-01, on a real manuscript instead of
the seeded fixture. Models: Claude Opus 5.5 (coordinator, the three host referees and the defender, as
Claude Code subagents) and GPT-5.6-Sol (the same three referees, through `models.py run codex`). Grader: the
coordinator, so this is a smoke run of the skill, not a blind evaluation: the coordinator wrote
manuscript-other-models in the same session.

## What was run

manuscript-peer-review on the v0.5 draft of Paper 1 (Just-DNA-Lite) and its supplement, simulated for the
top three journals of the authors' ladder (BMC Bioinformatics, Cell Reports Methods, Genome Biology). The
earlier runs' leftovers in the manuscript folder were archived and removed first. The panel was
software-methods (with the software-and-methods and genomics questions), skeptic (with the AI-systems
questions) and champion, each run on Claude and again on Codex as `SEAT@codex`, every one in a fresh
workspace prepared from the same reading copy, with the same brief. One defender on Claude then tested all
62 concerns, shuffled and stripped of seat, model and severity. The run, its report and the comparison stay
with the manuscript project (`just-dna-lite/docs/manuscript/v0.5/reviews/20261024T002252Z-682ded84/`), not
in this public repository: they quote the unpublished draft.

## Results

- 62 concerns (Claude 44, Codex 18) and 49 strengths, all meeting the finding contract with every quote
  found in the paper. Seven prior works the referees named all resolved to their records.
- The defender found no concern fully answered and no premise false: 26 partly answered, 36 not answered.
  Adjudication confirmed 36 and narrowed or downgraded 26; none refuted.
- 29 distinct problems by root cause, 5 major. The Claude referees raised 27 (4 major), the Codex referees
  12 (4 major), 10 of them shared. Codex alone raised 2: the annotation match described without an
  alternate-allele check (major), and the 181-fold speedup worded as an architectural gain (minor). Claude
  alone raised 17, among them the major percentile problem (variant-only VCFs against a full-genotype
  reference panel).
- Codex called 15 of its 18 concerns major, adjudication kept 8; Claude 17 of 44, kept 12.
- Recommendations: major revision at BMC Bioinformatics and reject at Genome Biology from all six; at Cell
  Reports Methods, major revision from three (two Claude, one Codex) and reject from three.
- Time per referee: Codex 3.8 to 4.8 minutes, Claude 7.7 to 13.2 minutes, run at the same time.

## Rubric (other-models-01)

| Item | Result |
|---|---|
| detect and check before the first Codex seat | Held. Codex's configured default (GPT-6.1-Sol) was refused for a ChatGPT sign-in and GPT-6-Astra needs a newer CLI; check showed both in Codex's words, and the seats ran on GPT-5.6-Sol. |
| every seat on the host and on Codex, fresh workspaces, same brief | Held. |
| `SEAT@codex`, `--isolation fresh-agent`, `--model` | Held: the seats wrote their plain seat name, and the coordinator added `@codex` when merging. |
| defender on the host without seat or model names | Held, with the findings also shuffled. |
| the report names the models | Held. |
| fail_if items | None occurred. |

## What it exposed, and what changed

- All three Claude subagent referees ran the panel's own `check_findings.py` from the plugin folder,
  against "work only from the files in this directory"; the Codex referees, confined to a copy, did not.
  The seat brief in `seats.md` now says to open or run nothing outside the workspace, not even the panel's
  scripts.
- The skill did not say how a seat on another model is named in its own files. SKILL.md now says the
  brief names the seat without its model and the coordinator sets `SEAT@CLI` and per-seat id prefixes when
  merging; and that the host's subagent seats, which start in the session's folder, need the workspace
  named by its absolute path.
- The output template said the referees share one model. It now covers several.
- Not changed: `figures.py workspace` covers only the main paper; the supplement's figure was added by
  hand. A `--supplement` option would remove that step.
