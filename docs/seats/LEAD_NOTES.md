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
  order RM1, RM2, RM3 was put to the maintainer in `#manuscript-skills>decisions` with that order as the
  default; RM3 is never called done before their own try from the desktop.
- **The channel:** `state` (a kept message, `watchdog.py keep lead state`), `decisions`, `daily` opened.
- **Acting duties** (no pm or correspondence seat in the table): `milestones`, done as the kept `state`
  message and a `milestones` post per landed release; `upstream-index`, nothing declared: the plugin builds
  on no in-house library or framework from the package index (its scripts carry their own inline
  dependencies), and what it does depend on (the plugin formats, the Google connectors) is not published
  there. Declare the watcher if that changes.

## Open

- **Picture:** this machine cannot draw; asked in `#agent-chat>avatars` for "a fountain pen leaning over a
  manuscript page, red proofreading marks in the margin and one green tick, flat warm colours". Set it from
  the reply: `watchdog.py avatar lead --from ID --says TEXT`.
- **The maintainer's branch `fix/decisions-skip-resolved`** holds one local commit not on origin. Theirs:
  not pushed, merged or rebased by this seat unless they say so.

## For the maintainer, by hand

- Say where panes and Doc postings are looked at.
