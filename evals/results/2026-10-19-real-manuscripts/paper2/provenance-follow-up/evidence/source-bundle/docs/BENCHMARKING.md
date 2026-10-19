# Running an authoring benchmark

How to run a round, and how to prove afterwards that the runs did not read the answer.
`docs/manuscript/claw-bio-inspired-benchmark.md` describes what the scorer measures and why;
this is the operational half — the prompt, the isolation, the leak checks, and the pitfalls
that have actually bitten.

## What exists

| Where | What |
|---|---|
| `assets/benchmarks/` | Committed corpus: three papers, one prompt each, the runs, and one expert-adjudicated reference (`sirt6/`). Reachable by tests. |
| `src/just_module_creator/bench.py` | The scorer. Three modes; `scripts/bench_score.py` is the argv shim. |
| `data/interim/repro-bench-N/` | Working notes and fresh runs for round *N*. Gitignored, never travels. |

```bash
# primary: against the adjudicated reference
uv run python scripts/bench_score.py --fixture assets/benchmarks/sirt6 <RUN_SPEC> [...]
# secondary: run against run, no reference needed
uv run python scripts/bench_score.py <REFERENCE_SPEC> <RUN_SPEC> [...]
# reference-free: what a run asserts vs withholds
uv run python scripts/bench_score.py --census <RUN_SPEC>
```

## Running a round

1. **Pin the version.** Every run in a table must be one build. The 2026-08-31 prep round spanned
   three, which is the only reason its numbers could not carry a claim. Put the expected version in
   the prompt and have the agent stop if the MCP server reports another.
2. **One run per agent, its own scratchpad, its own run directory.**
3. **Reuse the prompt verbatim** from `assets/benchmarks/<fixture>/prompt.txt`, substituting only
   the run directory. It names no rsID and no PMID — a prompt that leaks the answer measures
   nothing, and a test pins that.
4. **Score, then read the census** before concluding anything (see *Reading a score* below).

### The isolation clauses the prompt must carry

Beyond the task itself:

- **Do not read _or list_ anything under `data/interim/` or `assets/benchmarks/`** other than your
  own run directory. **"Read" alone is not enough** — a run took `ls data/interim/` as permitted and
  saw five directory names. Harmless in that instance, and it disclosed it unprompted, but the ban
  has to name listing.
- **Exactly one spec directory in the run directory.** Probes go to scratch. A run that left a
  throwaway copy beside its module made `locate_spec` refuse to score — correct behaviour, and
  avoidable.
- **No git commands.**
- Name the scratchpad explicitly, and forbid reading any other.

## Verifying a run did not cheat

**Ask the agent, and also check independently.** Its recollection is weak evidence; its transcript
is strong. Both were done on 2026-08-31 and they agreed, which is the outcome that makes the
agreement worth something.

Transcript lives at
`~/.claude/projects/<project-slug>/subagents/agent-<agentId>.jsonl`.

**Parse the `tool_use` blocks — do not count name mentions.** `registry_search` and
`registry_download` appeared 18 times in one transcript and were invoked **zero** times; the hits
were tool-schema text carried in the prompt.

```python
import json, pathlib
p = pathlib.Path("~/.claude/projects/<slug>/subagents/agent-<id>.jsonl").expanduser()
FORBIDDEN = ("assets/benchmarks", "reference-", "HANDOFF", "repro-bench-2")
for line in p.read_text(errors="replace").splitlines():
    d = json.loads(line)
    for b in (d.get("message") or {}).get("content") or []:
        if isinstance(b, dict) and b.get("type") == "tool_use":
            inp = json.dumps(b.get("input") or {})
            if any(n in inp for n in FORBIDDEN):
                print(b["name"], inp[:200])
```

Then check three more things:

1. **Registry reads.** `registry_download` / `registry_get_module` / `registry_search` could each
   return a published module. `registry_check` against the run's own spec is fine.
2. **Where the answer first appeared.** Find the first transcript line containing the variant and
   look at the tool call before it. In a clean run it is a real source call — for SIRT6,
   `literature_search` on the DOI, whose paper title happens to contain `rs117385980`.
3. **The reasoning chain, asked separately.** Grep cannot distinguish a plausible independent
   derivation from a reconstruction. Ask *how* the agent reached the hardest cell and read the
   answer for whether it names the tool output that prompted it.

**A "yes" is not a failed run.** A contaminated run is still data; an undetected one poisons a
published table. Say so in the ask, so the agent has no reason to shade it.

## Reading a score

**Separate axes, on purpose.** A single number cannot say which failure happened.

- **`rsid_recall` against `pair_recall`** — the gap is the "right variant, wrong genotypes"
  signal. There is no partial credit, because averaging destroys exactly that.
- **`decoy_rate`, not precision.** A variant absent from one curation may still be correct; a decoy
  is one an expert designated non-associated. `precision_over_fixture` is computed and named for its
  denominator.
- **An empty denominator is `not computed`**, its threshold `null`. A check that could not run is
  not a check that passed.
- **Then read `--census`** to tell *authoring latitude* from *inconsistency*. Two runs can lower
  `pair_recall` identically — one by omitting a genotype row, one by authoring it and withholding
  the claim — and those are different findings. The census shows `unknown` versus absent.

### The trap that matters most

**Convergence on the reference partly measures our own guidance, not the runs.** Two runs matched
the adjudicated SIRT6 reference cell-for-cell on all three genotypes. Then one volunteered why, and
it verified: `validate_module` names the missing row outright — *"a gap in a set the author
started … e.g. rs117385980 T/T"* — and `skills/module-weights/GUIDE.md:122` states *"A zero is a
claim too — it says this genotype changes nothing, which is different from a blank."*

So the claim the data supports is narrower than it looks: **the workflow is prescriptive enough to
produce consistent output from independent runs.** Reading it as *two judgements agreed, therefore
the answer is right* is the same self-agreement defect as the title-as-quote finding.

**When a benchmark scores well, go find the tool output or skill line that made it score well
before crediting the run.**

## Pitfalls, in the order they have bitten

1. **Project memory pointed every run at the answer key.** A memory entry read *"read
   `data/interim/repro-bench-2/HANDOFF.md` first"* — the round's own handoff, naming the reference
   and the findings. One run flagged the conflict and declined; the next might not have. Retired
   2026-08-31. **Audit the injected context, not only the prompt**: `CLAUDE.md`, the memory index and
   the skills all reach the agent unasked, and a benchmark's isolation is only as good as the
   quietest of them.

   **Then the write-up of that lesson re-created it.** The field note recording pitfall 1 quoted the
   `validate_module` warning that produced the convergence — *verbatim*, so `rs117385980` was in
   `CLAUDE.md` §11 and in the memory index, injected into every subagent this project ever runs. It
   landed at 09:04 on 2026-08-31, sixteen minutes after the last scored SIRT6 run, so no run in that
   round read it; every SIRT6 run after it and before the mask on 2026-08-31 would have been void.
   Both quotes are masked now (`<the fixture's rsID>`), which loses nothing — the point of the quote
   is that the tool names a missing genotype, not which one. **Grep the injected context for the
   answer before each round, not once**: an evidence quote is exactly the shape a leak arrives in,
   and the person writing it is trying to be rigorous.
2. **Runs span versions.** See step 1 of *Running a round*.

   **And a fix made mid-round does not reach the running server.** The MCP server is a long-lived
   stdio process that imported its modules when the session connected; editing the checkout, bumping
   the three version files and running `uv sync` change nothing about what it serves. On 2026-08-31 a
   pair was launched onto a 0.28.0 tree through a process that had started 43 minutes before the first
   of those edits, and every other signal agreed with the tree — `pyproject.toml`,
   both plugin manifests, and `importlib.metadata.version` all said 0.28.0. **Restart the transport
   between the fix and the next pair**, and confirm the version from the server's own instructions
   header rather than from the disk. This is the whole reason step 1 puts the expected version in the
   prompt: both runs of that pair read the header, saw 0.27.0, and stopped without authoring anything.
   The pin is the only check in the round that can see a stale process, so never drop it as a
   formality.
3. **Layout is not uniform.** Runs have put the spec at the run root, under `spec/`, and under
   `longevity_*/`. All satisfy the ask; `locate_spec` finds it and refuses rather than guessing when
   two exist.
4. **Parallelism starves itself.** Six agents share one `ServiceGate`; one reported *"pacing is
   tight enough that even pairs fail"*. Two or three at a time.
5. **`JUST_DNA_PIPELINES_CACHE_DIR` must be set.** Unset falls back to `~/.cache` and a 14 GB
   Ensembl snapshot filled the root filesystem mid-round.
6. **Rate limits are not results.** Semantic Scholar 429s and a rate-limited `registry_check` are
   *unchecked*, not *clean*. A run that reports either has an unknown, and the score must not read
   it as a pass.
7. **`build/` is not committed.** A compile is deterministic; the digests a recompile is checked
   against live in each fixture's `metadata.json`. `*.parquet` and
   `assets/benchmarks/**/build/` are in `.gitignore` so a stray `git add` cannot sweep one in.

## What a round still needs

The framework is built; a round that could carry a performance claim has not been run.

1. More than one adjudicated reference — one of three papers has one.
2. Repeats per prompt, so a number has a spread rather than a value.
3. A second host. Every run so far is one model through one host, so nothing separates the tool from
   the model. Codex is the plan.
