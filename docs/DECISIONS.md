# Decisions

What was decided about how this repository is worked, each with the alternative it rejected, newest last.
A decision about what a skill does is in that skill's `SKILL.md` and in `AGENTS.md`; this file holds the
ones that are about the work itself.

## D1 — The repository runs seats: one, the lead (2026-11-18)

The maintainer adopted the seats kit (agent-seat-blueprints) with `/seats:onboard`. Their words: "seat must
be on the server", and "make lead seat, it is enough so far".

- **One seat, `lead`** (`docs/seats/LEAD.md`). Rejected for now: a second seat for the plugin's outside
  users and what it depends on (the kit's `correspondence`), which is added when reports arrive as issues.
- **It runs on the always-on server**, not on a laptop.
- **The seat files are tracked** (`.blueprints.toml`, `docs/seats/`), as in the organisation's other
  repositories. Rejected: an untracked overlay, which would keep them out of every other clone and out of
  what a user installs; the files are small and say nothing private. The kit's version stays pinned in each
  machine's own settings, never in this repository.
- **The lead pushes its own `build/` and `fix/` branches and opens pull requests; `main` is the
  maintainer's merge**, since a release pushed to `main` reaches every user through the catalogue.
  Rejected: commit only (every branch would wait for a hand push), and pushing releases itself (a faulty
  release would ship before the maintainer saw it).
- **The team file is on the organisation's desk**, not here: the repository is public. The maintainer is
  its owner; the organisation's other people stand as the desk gives those who join.

The second, third and fourth were the wizard's defaults, taken when the maintainer answered only the
first; each is changed by one pull request.
