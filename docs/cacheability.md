# What a rerun could reuse (analysis, not built)

A `manuscript-improve` run on Paper 1 of just-dna-lite takes two to four hours, and the next version's run, a day
later, repeats much of the same work: it fetches the same sources again, resolves the same references and checks
the same links. This note measures, from two runs one version apart, what a cache could have reused. It also
records what a cache must not reuse, and proposes a design.

Material: the v0.5 run (`docs/manuscript/v0.5/reviews/20261025T235613Z-1931e926`, manuscript-skills 0.26.1,
finished) and the v0.6 run (`v0.6/reviews/20261027T125139Z-488af17b`, 0.29.1; only stages completed by
2026-10-27 19:00 UTC were read). Times are minutes after the run's start, taken from `run.json` records and the
modification times of fetched files; each agent's time and tool calls come from the v0.6 coordinator's session
transcript (its subagents' records), read without changing it. Measured on 2026-10-27.

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
- **The saving is agent work, not hours.** Fetching and looking things up took 31 of the 217 minutes of agent
  work in v0.6's review stages (14%); 12 of them were the reference check's (a third of its own 36 minutes). The
  review stages run in parallel, and peer review ran longest in both runs (v0.6: until 60.5 min; the reference
  check ended at 47.6 min), so caching the reference check saves agent minutes and tokens, but the run would not
  have finished sooner.
- **The long browser work was venue facts.** The journal selection redone the night before the v0.6 run spent
  28 of its two agents' 43 minutes fetching journal pages (72 browser JavaScript calls, 60 WebFetch calls), and
  the peer-review stage spent 3 of the 10 minutes before its referees could start fetching the three journals'
  reviewer pages. Both are what the venue catalogue (0.30.0) now keeps with dates; on a rerun they are read
  again only when `venues.py stale` says so.
- **The cheapest minutes are not cached ones.** The host refused the first report file of all 13 stage agents in
  the v0.6 run; each wrote it again, losing 11 minutes of agent time, 5.4 of them on the critical path (see the
  last section).

## Where the agents' time went (v0.6)

Each agent's records split into its tool calls and the model's time before each call. "Fetching" counts calls
that reach the network (`scan.py --online`, `support.py --online`, curl, WebFetch, WebSearch, the browser) and
the model's time preparing them; "waiting" is time the agent sat idle while the coordinator ran a later agent.

| Agent | Span | Waiting | Own work | Fetching | Turns | Output tokens |
| --- | --- | --- | --- | --- | --- | --- |
| Reference check | 45.0 min | 8.9 (the skeptic) | 36.1 | 12.0 (6.5 of it network) | 119 | 178k |
| Skeptic reader | 8.4 | | 8.4 | 0.5 | 34 | 50k |
| Integrity check | 30.5 | | 30.5 | 2.3 | 148 | 145k |
| Reporting check | 18.6 | | 18.6 | 4.9 | 88 | 88k |
| Figures | 26.0 | | 26.0 | 1.8 | 128 | 128k |
| Policy fit | 20.1 | | 20.1 | 5.6 | 98 | 106k |
| Peer review (setup, merge, adjudication) | 57.9 | 24.8 (seats, defender) | 33.1 | 3.9 | 139 | 189k |
| Three referee seats | 9.8 to 12.2 each | | 33.2 | 0 | 21 to 23 each | 59k to 75k each |
| Defender | 11.1 | | 11.1 | 0 | 27 | 72k |
| Journal facts, the night before (two agents) | 19.0 and 24.3 | | 43.3 | 27.8 | 127 and 134 | 53k and 73k |

In the reference check, the network part was the registry lookups (`scan.py`, 35 s for the paper and 118 s for
the supplement), the source fetch (`support.py --online`, 151 s for 27 DOIs) and 17 curl calls for publisher XML,
web pages and the arXiv PDF. The rest of its own work was reading the sources against the sentences (6 min), the
scripts (6 min) and writing the claims file and the report (10 min). Each agent processed tens of millions of
input tokens over its turns (38 million for the reference check), almost all of them re-read from the prompt
cache; a fetch adds its page to every later turn's context, so a text taken from a cache costs fewer tokens
as well as less time.

## The two runs, stage by stage

| Stage (v0.6) | Wall time | Repeated from v0.5 (measured) | Cacheable? |
| --- | --- | --- | --- |
| Reference identity lookups (`scan.py --references-only --online`) | 33 s + 85 s; the integrity stage runs `scan.py --online` on the same paper (31.5 s) | 29 of 31 main entries and 55 of 59 supplement entries with identical text; 28 of the 29 got an identical lookup result (the 29th failed in v0.5 and resolved in v0.6) | Yes: the identity part. The retraction part needs a short life |
| Source texts (support.py, curl, browser) | 12.0 of the agent's 36 minutes of own work went to fetching and lookups; `support.py --online` took 151 s for 27 DOIs | 62 of 87 files byte-identical to a v0.5 file (54 under the same name, 8 renamed); 42 of 47 works already held, 44 counting v0.5's policy-fit stage | Yes, keyed by the work |
| Claim support, first reader | the rest of the 28 min | 18 of 51 distinct readings had the same sentence and reference; 15 kept their verdict | No (see the test case) |
| Skeptic and adjudication | 32.5 to 47.6 min | read 29 readings, 7 stricter verdicts stood | No: independent by design |
| Code claims (`code_claims.py`) | about 12 min (20.6 to 32.9 min) | 9 of 31 claims with the same text; 8 kept their verdict | Not the verdict; the evidence lookups only |
| Number checks (`number_check.py`) | under 1 s for the script | the agent's number work reads tables against the text, and the captions of Tables 2, 3, 4, S2 and S10 changed | No: nothing slow to save |
| Upload and hygiene scan (`hygiene.py`) | 3 s | the files changed | Not worth it |
| Availability and links (`check_availability.py --online`) | 13 to 17 s, run 3 times | 34 of 35 identifiers shared; all 34 with an identical result | Yes, with a life per kind |
| Figures: renders (`figures.py`) | 2 to 3 s | Figure 2 and Figure S1 unchanged (image and caption); their renders byte-identical | Renders and measurements yes; verdicts no |
| Figures: review | 24 min | v0.6 found cross-figure problems (Figure 2 repeats a row Figure 1b now shows) that a per-figure cache would not have raised | No |
| Policy fit | 20 min, 5.6 of them fetching | 3 of the 13 policy URLs v0.6 read were read in v0.5; the venue ladder changed | Venue facts: the venue catalogue |
| Peer review: venue brief | 3 of the 10 min before the seats started | the journals' reviewer pages (iScience, Frontiers, JAMIA Open) | Yes: the catalogue's `reviewer_form` |
| Peer review: seats, defender, adjudication | 12.6 to 60.5 min | prior-work lists shared 2 of 4 to 5 entries | No: fresh seats are the point |
| Deslop | 12.8 min, one agent | none of v0.6's 6 findings repeats one of v0.5's 5; the one pattern the authors kept carried over in `kept-patterns.txt` | Author decisions already carry over; findings no |
| Story readers | 3.5 to 4.5 min each | v0.6's story stage had not finished | No: fresh readers are the point; the metrics scripts take under 1 s |

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
| Policy pages and venue facts | the venue and the field, with its page and `checked` date | the venue edits the page | the venue catalogue owns this (0.30.0): `venues.py stale` lists what is due (AI policy after 60 days, an impact factor after a newer JCR release, anything else after a year); `policy_watch.py` diffs the AI-policy pages |
| An author's decision (a pattern kept on purpose, a finding waived) | the pattern or finding plus where it sits | the passage changes | already carried over (`kept-patterns.txt`, the record's `waived`); key it by the passage's text, not only its heading: the one kept pattern was filed under "5. Discussion > 5.1 Limitations of Variant Annotation" in v0.5 and "5.1 Limitations of Variant Annotation" in v0.6 |
| Claim-support verdicts, referee seats, skeptic, defender, readers, critics | | | not cached |

## Design

**Where it lives.** In the platform's cache folder, outside the plugin (so it survives plugin updates) and
outside any one version folder: `~/.cache/manuscript-skills/` on Linux (`support.py`'s `platform_cache_root()`
already finds it on Linux, macOS and Windows). A per-project cache under `reviews/` would not work for this
project: each version folder (`v0.5/`, `v0.6/`) has its own `.manuscript-skills.yaml` and its own `reviews/`.
Everything kept is public material (registry records, open-access texts, public pages) or the hash of a project
file, so a user-level store is safe to share across projects. A run still copies each text it reads into its own
`sources/`, so a run folder stays self-contained, as `support.py` asks today.

It is a cache, unlike the venue catalogue, which keeps the user's venue facts as data in the configuration
folder beside `settings.yaml`: anything in it can be fetched again or rebuilt from earlier run folders, so it may
be deleted at any time. That matters for a text read in a browser, which no script can fetch again:
`support.py seed RUN` indexes an earlier run's `sources/` (and `skeptic/sources/`) into the cache, so the first
run after this ships can use v0.5's and v0.6's texts, and a cleared cache loses nothing a run folder still holds.

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
above allows. `finish` already stores each stage's `counts` (findings, proposals, decisions, since 0.30.0); it
would add `reused` and `fetched`, so the progress view and the run index show them without reading the
artifacts. The dashboard's coverage view already knows `reused` for whole stages; it would show reused inputs
per stage.

**Which scripts read and write it.**

- `support.py`: look up the work in the user cache (by every alias) before fetching; write each fetched text;
  add `support.py save WORK FILE --via browser --url URL`, so a text the agent read in a browser (the Mordaunt
  case) goes into the cache, not only into one run, and `support.py seed RUN` for earlier runs.
- `scan.py` (reference identity, and the integrity stage's `--online`): read and write `registry.jsonl`; the
  integrity and reference stages of one run then resolve each reference once.
- `check_availability.py`: read and write `links.jsonl` with the lives above; `--final` and a submission
  ignore the cache.
- `figures.py`: key renders by image sha256 and printed width; the stored measurements go beside them.
- `code_claims.py`: no verdict cache; `deps` and the evidence lookups could take a per-file hash index later.
- `runs.py`: the `reuse` command and the `reused_from` field; `validate` checks them.
- `policy_watch.py`, `venues.py` and venue facts: the venue catalogue, unchanged.

**Verdicts: diff, don't reuse.** After a fresh reading, the coordinator can compare each verdict with the last
run's for the same sentence, reference and source, and send the adjudication every reading where the verdict or
the source text differs, with both texts. For Mordaunt, the adjudication would have seen that v0.5 confirmed
"equipment" from a text v0.6 did not have. This costs one comparison, takes nothing from the readers'
independence, and catches regressions as well as last run's misses.

## Changes ranked by saving per unit of work

1. **Keep every text read for a work, and use it again** (`support.py`: user cache by work, aliases, `save` for
   browser-read texts, `seed` from earlier runs). Small change: the cache code exists and only points at the run
   folder. In this pair it would have saved most of the reference check's 12 minutes of fetching (42 of 47 works
   were already held), the browser reads that scripts cannot repeat, and one false finding (RC-10).
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
as peer review: 10 minutes of setup before the seats could start (1.4 reading the skill, the paper and the
catalogue's entries, 3 fetching the three journals' reviewer pages, about 6 writing the claim map, venue brief,
desk screen and briefs and building the seats' workspaces with a script the agent wrote for the run), seats until
30.1 min, then the defender, the merge and the adjudication until 60.5 min, 19 minutes of which came after the
defender. Peer review ended 13 minutes after the next-longest stage, so each minute taken off it shortens the run.
The venue catalogue's `reviewer_form` takes the 3 minutes of fetching off a run for a journal it holds. Since
0.32.0, `manuscript-peer-review/scripts/workspaces.py` builds the seats' workspaces and fills in their briefs: 3 s
on Paper 1 v0.6, giving the same reading copies (word for word), figures and domain questions the agent made by
hand, and the same supplementary files less one PNG nothing names. It also builds the defender's workspace and
the findings stripped of who raised them, which the agent scripted by hand between the seats and the defender.
What the 19 minutes after the defender went to, and how little of it a script can take, is the next section.

## The 19 minutes after the defender

From the peer-review agent's records, between the coordinator's message that the defender had finished and the
agent's hand-back (minutes of agent time; tool calls and the model's time before them):

| Step | Minutes | What it was | Scriptable? |
| --- | --- | --- | --- |
| Testing the defender's answers | 6.7 | 21 lookups in the code, the data, the just-prs repository, a dataset README and arXiv (3.7 min), then about 3 min deciding | No: this is adjudication. Some lookups re-derived what other stages had recorded by then: the web interface's restoration default is the integrity check's code claim CC22, and the Generation I preprint is in the reference check's sources |
| Quote checks | 0.5 | the coordinator's `check_quotes.py` on the planned quotes | Already a script |
| Writing the 63 verdicts | 2.2 | a 40,000-character script: verdict, severity, triage, route, stage, group and evidence for each finding, plus about 30 lines that map the defender's answers back and write `findings.adjudicated.json` | The 30 lines only: tens of seconds |
| Checking the adjudicated set | 1.6 | `check_findings.py`, a quote search, two greps | Already scripts |
| The report | 2.4 | 6,830 words written in one go | No: only 4 of its 297 sentences of eight words or more are copied from the seats or the verdicts |
| The report again | 1.6 | the host refused the agent's `Write` of `report.md` ("Subagents should return findings as text, not write report files"), and the agent sent the same 42,500 characters again through the shell | Yes: see below |
| Checking the report | 0.6 | a quote check and the style profile on the report | Already scripts |
| The stage's `findings.json` | 3.2 | a 46,000-character script: 34 findings and 20 proposed changes for the authors | Little: the texts are new (median similarity of a finding's detail to the adjudicated concern 0.06, of its action to `change_my_mind` 0.28), and severity and stage are set again per group (10 and 22 of 30 groups keep a member's) |
| Registering and finishing | 0.3 | `runs.py add` and `finish` | Already scripts |

So a script takes about half a minute off this part (folding the defender's answers into the findings and leaving
a verdict per finding to fill in). The rest is judgement and writing for the authors; it gets shorter only by
asking for less (a shorter report, or the referees' reports given as the seats wrote them rather than rewritten),
which is a decision about the deliverable, not about speed.

**The refused report is the larger loss, and it is not peer review's alone.** In the v0.6 run the host refused the
first `Write` of a report by every stage agent: all 13 (reference, integrity, reporting, figures, policy fit, peer
review, revise, prose edit, deslop, story and the three readers), 9,000 to 43,000 characters each. Each agent then
wrote the same report again through the shell, or the readers returned it as text, 24 to 93 seconds later: 11
minutes of agent time and about 235,000 characters sent twice. About 5.4 of those minutes lie on the critical path
(peer review 1.6, then the editing stages one after another: revise 0.8, prose edit 0.6, deslop 0.6, story 1.4, and
the readers, who run side by side, 0.5). The refusal is a rule of Claude Code (seen in 2.1.304), not of this
plugin: its `Write` tool refuses a delegated agent a file whose name matches `^(REPORT|SUMMARY|FINDINGS|ANALYSIS).*\.md$`
(regardless of case, so `report.md` and `report.2.md` too), meant to stop agents leaving report files instead of
answering; the main session may write such a file, and a shell command is not checked. In the v0.6 run all 14
refused writes were a subagent's `report.md`, and none of its other 28 writes (other Markdown, JSON, YAML, Python)
was refused. project-workflow.md already expects the refusal and asks the agent to
return the report as text for the coordinator to save; no agent did that, and each lost its first attempt instead.
Telling stage agents in the stage brief to write their report files with a shell command from the start (as every
one of them ended up doing), or giving `runs.py` a command that saves a report from standard input and registers it,
would take those 5.4 minutes off every run for a paragraph of instructions or a few lines of code: more than any
cache in this note.
