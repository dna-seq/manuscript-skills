# Maintain the shared venue catalogue

Use this workflow when updating venue records or policy snapshots. A manuscript adaptation request does
not require refreshing unrelated catalogue entries. Verify current decision-changing target policies
during the manuscript task and reuse those checks.

Commands below are relative to `manuscript-journal-adapt/`:

```bash
uv run --script scripts/policy_watch.py check --venue aging-cell
uv run --script scripts/policy_watch.py check --stale-days 30 --update
uv run --script scripts/policy_watch.py list
uv run --script scripts/policy_watch.py record URL saved.html
```

`policy_watch.py` watches the pages cited by `venues.yaml` (`url`, `ai_policy_url`, `sources`), reduces
them to passages about AI and compares them with
`../../manuscript-integrity-check/references/policy-snapshots/`. Snapshots are plain text tracked in git;
`git log -p` on a snapshot shows the policy history. This watcher does not establish that non-AI scope,
validation, fees or other selection requirements are unchanged.

It tries plain HTTP, then headless Chrome, then the newest Wayback copy. A page none of them can read is
`not_assessed`, never `unchanged`. An archived snapshot is historical evidence, not verification of the
current rule. Try available browsing tools for blocked pages; ask the author for a copy only if this is
the remaining obstacle to a material decision. Do not treat a paraphrased fetch as an exact quotation.

`changed` means the AI passages differ. Read the diff and determine whether the rule changed, then update
the shared venue fields, `checked` date and relevant reference notes. Exit code 1 means something changed
or disappeared. Use [selection-fields.md](../../manuscript-journal-select/references/selection-fields.md)
when recording selection requirements. Preserve one authoritative venue database.
