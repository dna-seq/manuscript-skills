# What a rerun could reuse (analysis, not built)

A `manuscript-improve` run on Paper 1 of just-dna-lite takes two to four hours, and the next version's run, a day
later, repeats much of the same work: it fetches the same sources again, resolves the same references and checks
the same links. This note measures, from two runs one version apart, what a cache could have reused. It also
records what a cache must not reuse, and proposes a design.

Material: the v0.5 run (`docs/manuscript/v0.5/reviews/20261025T235613Z-1931e926`, manuscript-skills 0.26.1,
finished) and the v0.6 run (`v0.6/reviews/20261027T125139Z-488af17b`, 0.29.1; only stages completed by
2026-10-27 15:00 UTC were read). Times are minutes after the run's start, taken from `run.json` records and the
modification times of fetched files. Measured on 2026-10-27.

## In short

- **Cache the inputs, not the judgements.** Fetched source texts, registry records, link states and figure
  renders depend only on things a key can name (a DOI, a URL and a date, an image hash). Between v0.5 and v0.6,
  42 of the 47 works the reference check read had already been fetched by v0.5's reference check, and all 34
  shared links had the same online result.
- **A source cache would have prevented one wrong finding.** v0.5 read Mordaunt et al. 2024's open-access full
  text in the app's browser (curl was blocked by a Cloudflare check) and saved the passage that names equipment.
  v0.6 had only the abstract, wrote that "both full texts are paywalled", and proposed deleting "equipment" from
  the paper (RC-10). What helps here is keeping every text read for a work, and not only the one a script can fetch.
- **Carried-forward verdicts would have hidden real disagreements.** Of 18 readings (sentence plus cited
  reference) present in both runs, 2 of the 17 whose source text was unchanged got a different verdict from a
  fresh reader. Of 9 code claims present in both runs, the one whose verdict changed (CC22) changed because v0.5
  had missed code that already existed. Reusing verdicts would have carried all three forward.
- **The saving is mostly agent work, not hours.** The review stages run in parallel, and peer review, which no
  cache can shorten, ran longest in both runs (v0.6: until 60.5 min; the reference check ended at 47.6 min).
  Caching the reference check's inputs saves agent minutes and tokens, but the run would not have finished
  sooner.

## The two runs, stage by stage

| Stage (v0.6) | Wall time | Repeated from v0.5 (measured) | Cacheable? |
| --- | --- | --- | --- |
| Reference identity lookups (`scan.py --references-only --online`) | 33 s + 85 s; the integrity stage runs `scan.py --online` on the same paper (31.5 s) | 29 of 31 main entries and 55 of 59 supplement entries with identical text; 28 of the 29 got an identical lookup result (the 29th failed in v0.5 and resolved in v0.6) | Yes: the identity part. The retraction part needs a short life |
| Source texts (support.py, curl, browser) | fetch window 10.0 to 24.0 min, inside a 28-min first reading; 27 DOIs took 2.3 min of it | 62 of 87 files byte-identical to a v0.5 file (54 under the same name, 8 renamed); 42 of 47 works already held, 44 counting v0.5's policy-fit stage | Yes, keyed by the work |
| Claim support, first reader | the rest of the 28 min | 18 of 51 distinct readings had the same sentence and reference; 15 kept their verdict | No (see the test case) |
| Skeptic and adjudication | 32.5 to 47.6 min | read 29 readings, 7 stricter verdicts stood | No: independent by design |
| Code claims (`code_claims.py`) | about 12 min (20.6 to 32.9 min) | 9 of 31 claims with the same text; 8 kept their verdict | Not the verdict; the evidence lookups only |
| Number checks (`number_check.py`) | under 1 s for the script | the benchmark tables were rerun between versions | No: the numbers depend on changed data |
| Upload and hygiene scan (`hygiene.py`) | 3 s | the files changed | Not worth it |
| Availability and links (`check_availability.py --online`) | 13 to 17 s, run 3 times | 34 of 35 identifiers shared; all 34 with an identical result | Yes, with a life per kind |
| Figures: renders (`figures.py`) | 2 to 3 s | Figure 2 and Figure S1 unchanged (image and caption); their renders byte-identical | Renders and measurements yes; verdicts no |
| Figures: review | 24 min | v0.6 found cross-figure problems (Figure 2 repeats a row Figure 1b now shows) that a per-figure cache would not have raised | No |
| Policy fit | about 20 min | 3 of the 13 policy URLs v0.6 read were read in v0.5; the venue ladder changed | Venue facts: see the venue catalogue |
| Peer review: seats, defender, adjudication | 12.6 to 60.5 min | prior-work lists shared 2 of 4 to 5 entries | No: fresh seats are the point |
| Story readers, deslop critics | | | No: fresh readers are the point; the metrics scripts take under 1 s |

The manuscript text itself: 294 of 465 sentences of the main paper (63%) and 252 of 293 of the supplement
(86%) are identical between v0.5 and v0.6. The cited sentences churn more (18 of 51 readings, 35%), because a
version fixes exactly the sentences the previous run flagged. Two readings whose sentences were edited after
v0.5 (Ultima Genomics, Tacutu) moved from partial to confirmed, as they should.

The coordinator's count of 62 readings in v0.5 left out the five Table S7 rows of the random sample
(`claims-sample.2.yaml`): v0.5 has 67 readings (65 distinct). v0.5 had a skeptic too (16 readings, 6
downgraded); v0.6's read 29.

## The test case: three verdicts that changed

The three readings with the same sentence and reference whose verdict changed between the runs changed for
three different reasons:

| Reading | v0.5 | v0.6 | Source text | Why it changed | A verdict cache keyed on sentence, reference and source hash |
| --- | --- | --- | --- | --- | --- |
| Mordaunt et al. 2024, costs sentence | confirmed (first reader and skeptic) | partial (skeptic, adjudicated) | v0.5: a browser-read excerpt of the open-access full text naming "equipment"; v0.6: the abstract only | v0.6 had less text and was wrong: the paper is open access, not paywalled | misses (different text); a source cache by work gives v0.6 the excerpt and avoids the false finding |
| Ehman et al. 2025, same sentence | confirmed (skeptic: the two sources read together) | partial (skeptic: read alone, no "equipment") | the same abstract, byte-identical | two independent readers disagreed on the same text | hits, and carries "confirmed" over the stricter reading |
| Zook et al. 2016, Ethics Statement | confirmed | partial ("the" Genome in a Bottle sample should be "a") | identical full text | the fresh first reader was stricter, and right | hits, and suppresses a valid correction |

Code claim CC22 ("it is off by default and not applied to gVCF input") is the same lesson in code. v0.5 cited
only the library default and said it matched. v0.6 also read the web interface, which turns restoration on for
every whole-genome sample, and said it differs. That code was already at the commit v0.5 checked (c7a7ed6,
`webui/src/webui/state.py` line 4213). A cache keyed on the claim plus the hashes of the files v0.5 cited would
have missed only because just-prs was upgraded in between (the quoted line moved from 1009 to 1677 in
`.venv/.../just_prs/prs.py`, a file `git diff` does not see). Without that upgrade, the cache would have carried
v0.5's miss forward.

So a cached verdict is wrong whenever a later reader would have read more or read differently, and the key cannot
see that. It also anchors: a reader shown last run's quote and verdict tends to confirm them, and v0.6's Zook
reading found its problem by quoting a different passage. Seats, the skeptic, the defender, story readers and
deslop critics must never see a cached verdict.

## What each check depends on, and how it goes stale

| Check | Key | Goes stale when | Rule |
| --- | --- | --- | --- |
| Reference identity | the normalised entry text plus its identifiers | the entry changes | reuse until the entry changes; never store a failed lookup as a result (keep it 1 day) |
| Retraction, correction, withdrawal, published version | DOI or PMID | a notice is issued at any time | reuse for 7 days within a round; always fresh before a submission or a revision, as the reference check already says |
| Source text | the work (DOI, PMID, PMCID and arXiv id resolved to one work), plus how it was read (`full_text`, `abstract`, `excerpt`, `browser`), with the text's sha256 | a correction or new version of the work; a web page's update | publisher texts: keep while the work's record shows no correction or new version; web pages: 30 days; keep every text read for a work, and give the reader the fullest |
| Link and availability state | the URL or identifier | a repository is renamed, made private or gets a release | 7 days; 1 day before a submission |
| Code-claim evidence | claim text plus the hashes of every file under the code roots the claim's `where` names (the step's package, not only the cited lines) | any of those files changes, including installed packages in `.venv` | reuse the file and line lookups as a starting point; the verdict is read fresh |
| Figure render and measurements | the image's sha256 plus the printed width | the image or the venue's column width changes | reuse the render and the measured text sizes; the review of the figure against its caption and the text is fresh |
| Policy pages and venue facts | URL and date | the venue edits the page | the venue catalogue, as the dated store of venue facts, owns this (being designed in a parallel session); `policy_watch.py` already snapshots and diffs these pages |
| Claim-support verdicts, referee seats, skeptic, defender, readers, critics | | | not cached |

## Design

**Where it lives.** In the platform's cache folder, outside the plugin (so it survives plugin updates) and
outside any one version folder: `~/.cache/manuscript-skills/` on Linux (`support.py`'s `platform_cache_root()`
already finds it on Linux, macOS and Windows). A per-project cache under `reviews/` would not work for this
project: each version folder (`v0.5/`, `v0.6/`) has its own `.manuscript-skills.yaml` and its own `reviews/`.
Everything kept is public material (registry records, open-access texts, public pages) or the hash of a project
file, so a user-level store is safe to share across projects. A run still copies each text it reads into its own
`sources/`, so a run folder stays self-contained, as `support.py` asks today.

```
~/.cache/manuscript-skills/
  blobs/<sha256>                        # texts, renders, saved pages: content-addressed, written once
  works.jsonl                           # one line per text read for a work
  registry.jsonl                        # identity and retraction lookups
  links.jsonl                           # availability states
  renders.jsonl                         # figure renders and measurements by image hash
```

A record (one JSON line, appended; the newest valid one wins):

```json
{"kind": "source", "key": "doi:10.1016/j.gim.2023.101058", "aliases": ["pmid:...", "pmcid:..."],
 "scope": "excerpt", "via": "browser", "url": "https://www.gimjournal.org/article/S1098-3600(23)01074-2/fulltext",
 "blob": "sha256:...", "characters": 2453, "read_at": "2026-10-26T00:24:22Z",
 "run": "20261025T235613Z-1931e926", "plugin": "0.26.1", "expires": null}
```

**How a stage asks it, and how the run records a hit.** A script looks the key up before it fetches (as
`support.py`'s `fetch_identifier` already does in the run's own folder) and, on a hit, copies the blob into the
run. The run must show the reuse, so the dashboard and `validate` can see it: the artifact gets
`"reused_from": {"run": "...", "read_at": "...", "key": "..."}` beside its sha256, and `runs.py` gains
`runs.py reuse RUN --skill NAME --key KEY --file PATH`, which registers a cached file that way. A report says, for
example, "35 of 47 source texts reused from earlier reads (oldest 2026-10-26); 12 fetched now". `validate` checks
that each reused artifact's sha256 matches its blob, and that no reuse in a review stage is older than the rule
above allows. The dashboard's coverage view already knows `reused` for whole stages; it would show reused inputs
per stage.

**Which scripts read and write it.**

- `support.py`: look up the work in the user cache (by every alias) before fetching; write each fetched text;
  add `support.py save WORK FILE --via browser --url URL`, so a text the agent read in a browser (the Mordaunt
  case) goes into the cache, not only into one run.
- `scan.py` (reference identity, and the integrity stage's `--online`): read and write `registry.jsonl`; the
  integrity and reference stages of one run then resolve each reference once.
- `check_availability.py`: read and write `links.jsonl` with the lives above; `--final` and a submission
  ignore the cache.
- `figures.py`: key renders by image sha256 and printed width; the stored measurements go beside them.
- `code_claims.py`: no verdict cache; `deps` and the evidence lookups could take a per-file hash index later.
- `runs.py`: the `reuse` command and the `reused_from` field; `validate` checks them.
- `policy_watch.py` and venue facts: left to the venue catalogue.

**Verdicts: diff, don't reuse.** After a fresh reading, the coordinator can compare each verdict with the last
run's for the same sentence, reference and source, and send the adjudication every reading where the verdict or
the source text differs, with both texts. For Mordaunt, the adjudication would have seen that v0.5 confirmed
"equipment" from a text v0.6 did not have. This costs one comparison, takes nothing from the readers'
independence, and catches regressions as well as last run's misses.

## Changes ranked by saving per unit of work

1. **Keep every text read for a work, and use it again** (`support.py`: user cache by work, aliases, `save` for
   browser-read texts). Small change: the cache code exists and only points at the run folder. It saves the
   fetch window (up to 14 of the first reader's 28 minutes in v0.6, about 3 minutes of it network), the browser
   reads that scripts cannot repeat, and in this pair one false finding (RC-10).
2. **Record reuse in the run** (`runs.py reuse`, `reused_from`, `validate`). Small; needed before any of the
   others, so a reused input is visible with its date and run.
3. **Verdict diff for the adjudication.** Small (a comparison of two claims files); no time saved, but it
   catches the Mordaunt kind of regression and last run's misses.
4. **Registry lookups once per run and across runs** (`scan.py`). Small; saves about 1 to 2 minutes of script
   time per run and the duplicate lookup in one run; retraction status stays fresh before a submission.
5. **Figure renders by image hash** (`figures.py`). Small, but saves seconds: renders take 2 to 3 s. Worth it
   only for the stored measurements of an unchanged figure.
6. **Link states with a life** (`check_availability.py`). Saves 13 to 17 s per call. Do it with 4, or skip it.
7. **Do not build**: cached claim-support verdicts, code-claim verdicts, figure verdicts, seats, the skeptic, the
   defender, readers or critics. In this pair they would have carried forward 2 of 17 contested reference
   verdicts and 1 of 9 code verdicts, one of them (CC22) a missed problem in what the paper says the software
   does.

To make the run finish sooner, look at the critical path, not at caching. In v0.6 the review phase lasted as long
as peer review (seats 12.6 to 30.1 min, defender and adjudication until 60.5 min). Starting the seats sooner
(they waited 12.6 minutes for the venue brief) or giving the defender the reference check's texts and the code
ledger would cut more wall time than any cache above.
