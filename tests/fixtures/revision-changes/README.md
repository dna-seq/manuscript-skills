# Fixtures for `rev_marks.py changes`

Excerpts of a real marked master, Paper 1 of [dna-seq/just-dna-lite](https://github.com/dna-seq/just-dna-lite),
`docs/manuscript/`:

- `paper-v0.5.md`: `v0.5/paper1-just-dna-lite.md` at commit `966c29f`, where the v0.6 round opened: lines
  1-34 (title, draft note, authors, affiliations, abstract), 353-358 (the Discussion's opening) and 397-454
  (Conclusion to Competing Interests).
- `paper-v0.6.md`: `v0.6/paper1-just-dna-lite.md` at commit `2d6aae5`, the same sections: lines 1-31,
  381-386 and 425-480.
- `changes-from-v0.5.md`: the hand-written changelog of that round (`v0.6/changes-from-v0.5.md` at
  `2d6aae5`), cut to its section 1 and the section 2 rows for the sections above.

Each excerpt starts and ends outside every segment, so both lint clean. `tests/test_revision_changes.py`
checks that every id of the hand-written changelog is a row of `changes`.
