# Seats

The standing roles agent sessions take in this repository, run by the seats kit (agent-seat-blueprints).
The seat table is `.blueprints.toml` at the root; a session takes a seat with `/seats:seat NAME`, one
session per seat. None of this is part of the plugin: a user who installs manuscript-skills needs no seat.

| Seat | Role (the kit's) | Owns | Priming | Notes |
|---|---|---|---|---|
| `lead` | `lead` | `docs/roadmap.md`, `docs/DECISIONS.md`, the skills, the hooks, the tests and their docs | [LEAD.md](LEAD.md) | [LEAD_NOTES.md](LEAD_NOTES.md) |
