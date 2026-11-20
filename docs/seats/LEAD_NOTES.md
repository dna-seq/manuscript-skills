# Lead notes

The state the lead's last holder left. State, not rules: the rules are the priming, `LEAD.md` beside this
file, and the kit's role `classes/lead/LEAD.md`.

## 2026-11-18 — first seating, on the server

- **Seated** in the session that ran the adoption; the kit moved to v0.1.247 at the take.
- **The repository's own machinery:** none to retire, move or keep. `hooks/progress` is the plugin's product.
- **The suite here:** `uv run pytest`, 2614 passed, 3 skipped, about 8.5 minutes at low priority.
- **What cannot be checked here:** no paper's run folder is on this machine, and the progress pane and the
  Google connectors run only in the desktop app. Changes under `hooks/progress`, and anything that posts
  to a Doc, are "tested, not viewed" until the maintainer names where they are looked at.
- **The roadmap:** RM1 to RM3, all `unattended`, owner lead (on `main` since 2026-11-19). The
  order question in `#manuscript-skills>decisions` was withdrawn the same night (an order alone is no real
  fork): built RM1, RM2, RM3 in turn; RM3 is never called done before their own try from the desktop.

## 2026-11-19 — RM1 built (0.69.0)

- The reader from outside the field (`manuscript-story/scripts/comprehension.py`, the panel's fourth seat, and
  improve's step 7 on the run's own passages). Tested on fixtures only: no run folder of a real paper is here, so
  its first real reading is the next improve run; `comments.py gaps` on the round after it measures it.
- The rest of the gap note's order is RM4 (one change per skill), `unattended`.

## 2026-11-20 — RM2 built (0.71.0)

- The cover letter in the improve run, its gaps as the stage's own findings (so To-do, Word and workbook carry them
  with no new to-do kind), and the letters on the Journals tab. The tab's script is compiled with QuickJS (`uv run
  --with quickjs`; no node here), never viewed: the maintainer sees it on the next run he asks for.
- **The channel:** `state` (a kept message, `watchdog.py keep lead state`), `decisions`, `daily` opened.
- **Acting duties** (no pm or correspondence seat in the table): `milestones`, done as the kept `state`
  message and a `milestones` post per landed release; `upstream-index`, nothing declared: the plugin builds
  on no in-house library or framework from the package index (its scripts carry their own inline
  dependencies), and what it does depend on (the plugin formats, the Google connectors) is not published
  there. Declare the watcher if that changes.

## Standing word from the maintainer

- **No manuscript runs without asking** (Anton, 2026-11-19, relayed by the desk's secretary to every lead): no
  seat starts a run of this plugin's skills (review panels, improve, dashboard, other-model runs) unless Anton asked
  for that run in his own words or said yes when asked; "manuscript skills is super token consuming". The lead builds
  and tests the plugin on fixtures; a run on a real paper to try a feature (RM1's reader) is asked for first.

## Open

- **Picture:** this machine cannot draw; asked in `#agent-chat>avatars` for "a fountain pen leaning over a
  manuscript page, red proofreading marks in the margin and one green tick, flat warm colours". Set it from
  the reply: `watchdog.py avatar lead --from ID --says TEXT`.
- **The maintainer's branch `fix/decisions-skip-resolved`** holds one local commit not on origin. Theirs:
  not pushed, merged or rebased by this seat unless they say so.

## For the maintainer, by hand

- Optional: add the `IBIMA_PIN_TOKEN` secret (a fine-grained token for longevity-genie/ibima-marketplace,
  Actions read and write), so a release push pins itself; until then the lead starts the pin.

- Say where panes and Doc postings are looked at.
