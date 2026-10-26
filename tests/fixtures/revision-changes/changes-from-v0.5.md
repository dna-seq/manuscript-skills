# Paper 1: changes from v0.5 to v0.6

Round opened on 26 October 2026 from the v0.5 master (commit `966c29f`). Each entry says what the text was,
what it is now and why. The id is the revision-ledger segment in `paper1-just-dna-lite.md`
(`<!-- @rev ID … -->`), so `uv run manuscript ledger report` finds the passage. For the full wording of
both versions, compare the two files:
`git diff --no-index --word-diff docs/manuscript/v0.5/paper1-just-dna-lite.md docs/manuscript/v0.6/paper1-just-dna-lite.md`.

The Supplementary Data, Tables S4 and S5, the figures and the venue files are unchanged copies of v0.5.

## 1. Authors, affiliations and acknowledgements

Requested by Anton Kulaga on 26 October 2026.

| Id | Where | Was | Now | Why |
|---|---|---|---|---|
| AU1 | Author line | Twelve authors, including Ryangguk Kim, Alina Fedorova and Sergey Evfratov | Nine authors; those three moved to the Acknowledgments | Their contributions (OakVar; utilities and literature exploration; the Generation I drug module) fit an acknowledgement better than authorship of this paper |
| AU1 | Kulaga Anton | Affiliations 1, 2, 4 (IBIMA, IBAR, SecvADN) | 1, 2 (IBIMA, IBAR) | Anton's affiliations are IBAR and IBIMA |
| AU1 | Tacutu Robi | 2, 9 (IBAR, Romanian Bioinformatics Cluster) | 2 (IBAR) | Robi is now affiliated with IBAR only |
| AU1 | Zaharia Livia | 3 (HEALES) | 1 (IBIMA) | Livia belongs under IBIMA |
| AU1 | Karmazin Alexey | 4 (SecvADN) | 3, 4 (HEALES, SecvADN) | Alexey Karmazin is at HEALES; SecvADN kept because he co-founded it (see Competing Interests) |
| AU2 | Affiliation list | Nine entries | Four: IBIMA, IBAR, HEALES, SecvADN | Dropped the Bioinformatics Cluster and CellFabrik (requested), the Glushkov Institute (the Ukrainian affiliation, requested), Oak Bioinformatics (its only author moved to the Acknowledgments) and MitoSpace (no author had it, in v0.5 either) |
| AU3 | Acknowledgments | Volodymir Semenuik only | Ryangguk Kim (Oak Bioinformatics), Alina Fedorova, Sergey Evfratov and Volodymir Semenuik, each with what they did | Moved from the author list |
| P7 | Contribution Statements | Entries for the three moved authors | Entries removed | They are no longer authors |
| (none) | Competing Interests | "Ryangguk Kim is a co-founder of OakVar Inc." | Removed | Competing interests are declared for authors |
| (none) | Header | "Draft v0.5" | "Draft v0.6" | New round |

## 2. Putting the features and the users first (the rows for the sections in this excerpt)

| Id | Where | Was | Now | Why |
|---|---|---|---|---|
| C2a | Abstract | Described the ecosystem in general terms; no number; no user groups | Four features with their numbers (6,117 scores for 778 traits with ancestry-matched percentiles and 860 broken scores withheld; 24 registry modules from five publishers; whole-genome annotation in 33 to 65 s, 128 to 231 times faster than Generation I; web UI, AI assistants via MCP and skills, Python libraries) and the user groups | A reader of the Abstract alone did not learn what the software does better than alternatives, how large its catalogue is, or who it serves. The v0.5 improvement run had flagged "The Abstract states no measured result" (ST-10) but left it as an open decision |
| F5 (inside T6) | Discussion, opening | Connection of genome to evidence | Adds one sentence: the same operations from a web UI, an assistant or a library serve several groups at once (Box 1) | Ties the Discussion to the user groups |
| R24, A3c | Conclusion | Opened on architecture ("integrates local variant annotation … with a portable annotation-module contract"); said "faster annotation … albeit on four call sets" | Opens on what users get (catalogue, registry, speed, three ways in); states the 128 to 231 times speedup; keeps the scope (four call sets from three people, one for scoring) and every later caveat | The Conclusion should restate the value, then the limits |
