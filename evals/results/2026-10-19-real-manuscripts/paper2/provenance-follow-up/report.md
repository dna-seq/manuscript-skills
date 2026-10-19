# Paper2: which SIRT6 round does the table describe?

19 October 2026. Focused manuscript-integrity check of the authoritative
`just-module-creator/docs/manuscript/manuscript.tex`, Evaluation dimensions,
lines 469–517. This is not a full reference, submission, reporting or peer-review audit.

## Finding and correction

**The older preparation corpus does not demonstrate an error in the manuscript table.**
The table describes a deliberately substituted later round. My earlier selection report
overstated a numerical contradiction by comparing different rounds before tracing their history.
That diagnosis is withdrawn. The remaining issue is reproducibility: the later raw outputs and
running-version evidence have not been recovered in the searched local locations.

The table says “Three runs of one prompt scored against an expert-curated reference module,
plugin version fixed.” It prints pair recall **0.67, 1.00, 1.00**, citation recall **1.00** in
each run and direction agreement **1.00** in each run. These numbers are unchanged.

## What settles the distinction

1. [Introduction commit, fab4db5](evidence/round-introduced.git-show.txt), 31 August 2026,
   explicitly says: “The a/b/a2 rows are out. They were prep runs across three plugin builds and the
   table now holds three runs at a fixed version, with two rows pending.” Its diff replaces
   A/B/C values 0.33/1.00/0.33 with run 1 at 0.67 and runs 2/3 marked TBD.
2. [Completion commit, 221b95f](evidence/round-completed.git-show.txt), the same morning,
   fills runs 2 and 3 and records the reported direction, citation and significance-verdict results.
   Its message also describes transcript checks. These are contemporary accounts, not recovered
   transcripts or raw output verification.
3. `pyproject.toml` at both commits declares **0.27.0**, corroborated by the changelog account.
   This identifies the intended source version. It does not establish the running MCP server's
   imported build or every dependency version; the project's own runbook describes stale-server risk.
4. The committed `a/b/a2` corpus remains the preparation round. Its values are reproducible,
   but applying them to runs 1/2/3 would substitute a different experiment.

The earlier ambiguity “newer table or stale table” is therefore partly resolved: there is direct
historical evidence for the newer-table explanation. The commits do not independently establish
that its numbers are correct.

## What was actually reproduced

[Fresh scorer JSON](commands/0006.stdout.txt) and [compact CSV](evidence/preparation-scores.csv):

| Preparation run | Pair recall | Citation recall | Direction agreement | Denominator for direction |
|---|---:|---:|---:|---:|
| a | 1/3 = 0.3333 | 2/2 = 1.00 | 1.00 | 1 jointly asserted pair |
| b | 3/3 = 1.00 | 2/2 = 1.00 | 1.00 | 2 jointly asserted pairs |
| a2 | 1/3 = 0.3333 | 1/2 = 0.50 | not computed | 0 jointly asserted pairs |

All three recover the one reference rsID; no designated decoy is present. Citation recall here
compares the expected identifiers with authored identifiers. Citation identity accuracy is
`null` because this execution used no resolver; free-text conclusions are not scored. None of
these are new validations of the later round's citations or conclusions.

Command, run from the repository root:

```sh
uv run python scripts/bench_score.py --fixture assets/benchmarks/sirt6 \
  assets/benchmarks/sirt6/runs/a assets/benchmarks/sirt6/runs/b \
  assets/benchmarks/sirt6/runs/a2
```

The reference metadata describes a human-adjudicated merge of preparation runs a and b.
It is not an independent reference for those two preparation outputs. That lineage alone does
not establish that later agents accessed it. The later reference bytes and isolation checks
still need the corresponding archive.

## Recovery coverage and limits

The historical runbook puts fresh runs and working notes in gitignored
`data/interim/repro-bench-N/`; the contemporary notes name `repro-bench-2/`. That directory is
absent in this checkout. Searches covered the connected repositories' local data/docs,
just-module-creator assets and `.claude`, all locally available Git refs, and its local Claude
project transcript directory. The latter contains memory files but no JSONL transcripts.
Relevant Git paths contain the preparation corpus, not later run directories.

[Provenance JSON](evidence/provenance.json) records the exact search roots, matched paths,
source hashes and version declarations. A [source bundle](evidence/source-bundle/) retains the
actual preparation inputs, scorer and runbook. The original machine's private archive, remote
Claude session and unavailable storage were not retrieved. “Not found here” does not mean lost
everywhere. An author question asking for that archive's location is pending.

The smallest next step is to recover the **later** run modules, actual prompt, exact reference,
scorer revision, model/host and server/dependency build record; then score them and map run IDs
to the printed rows. Keep transcript evidence supporting the reported isolation checks.
Do not rerun authoring on the current 0.48.0 checkout and describe it as the historical round.
If the archive cannot be recovered, decide explicitly between reporting the available preparation
round with its limits and conducting a new, separately identified evaluation. No numerical rewrite
is justified solely by this check.

## Changes delivered

- Corrected the current selection report, shared publication strategy and scientific record.
  Journal priorities remain speed first and impact factor above 3; fee funding and venue selection
  remain unconfirmed. Also closed the stale priority question left open inside the saved record.
- Preserved before/after copies and excerpts in [evidence](evidence/). Earlier completed run reports
  remain intact as historical evidence; this report supersedes their contradiction diagnosis.
- Added a narrow instruction to the plugin to identify evaluation rounds before calling differing
  scores an error, plus a behavioural case using this real history. This session is a recovery
  investigation, not an independent fresh-session evaluation of that new case.
- No manuscript source, bibliography or numerical result was edited.

## Failures retained

Commands 0001/0002 exited zero with empty output because their relative Git pathspecs ran from
the manuscript directory, the helper's default working directory. They prove nothing. Commands
0003/0004 repeated them from the explicit repository root. This explains why exit zero alone
cannot establish a scientific check. The subsequent planning-update command's uv environment
warning is retained; uv used the declared project environment and the command completed.

Real source-bundle registration then exposed a helper defect: it reserved every `README.md`
basename, including module documentation in nested evidence folders. The [failure record](evidence/readme-registration-failure.md)
and failing regression output are retained. The fix reserves only the generated skill-root index;
the subsequent real registration preserves the source READMEs unchanged.

Additional exploratory reads found no `data/interim/` directory or old `/data/sources/` checkout;
one attempted preservation-reference filename was incorrect and one bare `python` invocation was
unavailable outside uv. Neither altered inputs or supports a scientific conclusion. The correct
skill contract and project runtime were used for the delivered work.

**Coverage:** the focused provenance investigation is complete for the available local evidence.
The later evaluation remains unverified pending archive recovery; full manuscript readiness is
not assessed by this run.

Verification of the plugin follow-up: **211 relevant tests passed** (integrity and project-run
helpers), including the new source-README regression; the modified skill passed package metadata
validation. The new regression was first watched to fail against the original helper; both attempts
are retained. Those checks do not validate
the missing historical evaluation or establish a fresh-session pass of the added behavioural case.
