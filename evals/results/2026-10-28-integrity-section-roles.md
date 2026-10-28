# Each detail in its section: the paired case before and after 0.40.0

Date: 28 October 2026. Skill: manuscript-integrity-check at 0.39.0 (commit d207019, "before", with no section
roles) and at 0.40.0 with this commit's description and case fixes ("after"). Model: Claude Opus 5.5 for every
agent, each a fresh Claude Code subagent given only its staged folder and, for the skill arms, the skill folder.
Grader: one fresh agent per answer, given the fixture, the answer and the case's rubric under a neutral label, so
it did not know which arm wrote the answer. This is one run per arm.

## The case

`integrity-section-roles-seeded` and `integrity-section-roles-clean` in
[manuscript-integrity-check.yaml](../manuscript-integrity-check.yaml): Paper 1 of Just-DNA-Lite before and after
the authors moved each detail to its section (just-dna-lite commit bc27fe5). The seeded version frames just-prs
as "A cleaned PGS Catalog", carries the storage format, the withheld counts, measured ranges, a dated registry
count and a thread-dependent PLINK2 comparison in the Key features, and reports two audits' counts and a
classifier's accuracy in Methods. The request: "A co-author says the Introduction of our software paper reads
like a methods section. Check whether each part of this excerpt, software-paper.md, holds what belongs there, and
tell us what should move where. Report only, please: don't change the file."

## The automatic run that did not test anything

`plugin_eval.py run --case "integrity-section-roles-*" --runs 1` (claude plugin eval, with and without the plugin)
ran on 0.40.0 and scored every arm 0.14 to 0.29, for $1.45. Its transcripts show two failures of the setup, not
of the skill:

- Every Bash call in the evaluated agents failed with `apply-seccomp: write /proc/self/setgroups ... Permission
  denied`. The agents start a sandbox of their own, and the session that launched the evaluation was itself
  sandboxed, which does not allow a nested one. Running the evaluation outside the session's sandbox was refused
  by the session's permission mode, so the automatic route was dropped.
- The prompt said "this excerpt" without naming the file, so with no directory listing every agent guessed file
  names and stopped. The fixtures are now `software-paper-seeded.md` and `software-paper-clean.md` (staged as
  `software-paper.md`, a name that does not announce what is being tested), and the prompts name the file.

The with-plugin arms also never called the Skill tool. Since nothing could be read, that does not show whether
the request routes to the skill; the skill's description now names "detail in the wrong section (results in the
Introduction or Methods)" and "a section check", within the 1,024-character limit, so that it can.

## Results

| Arm | Verdict | Rubric items held (of 8) | fail_if |
|---|---|---|---|
| Seeded, no skill | FAIL | 3: Methods detail to 3.2; two of three Methods results; no edits | occurred: "the Introduction mostly needs deleting, not moving"; the Fast ranges and the PLINK2 ratio left the paper |
| Seeded, skill before | FAIL | 3: Methods detail to 3.2; the Fast item as Results; no edits | none |
| Seeded, skill after | PASS | 8 | none |
| Clean control, skill after | FAIL | 1 of 2: no edits | none |

What only the skill after got right, item by item:

- **The framing.** "The heading frames just-prs as a cleaned copy of someone else's data. What it actually adds to
  the Catalog is computing the Catalog's models on the reader's genome, giving each result an ancestry-matched
  percentile, its coverage and a quality label". Both other arms kept the title; the arm with no skill rewrote
  the bullet around "cleaned metadata".
- **Counts in the Introduction are results, not Methods.** The two other arms sent "860 scores were withheld, 847
  of them" back to Section 3.2 ("Delete; 3.2 already has it in full"), where it was a result in Methods too.
- **The dated registry count.** Kept in the Introduction by both other arms, without its date in one of them.
- **Results in Methods.** The skill after moved all three (both audits' counts and the leave-one-out accuracy) to
  two new Section 4 subsections, with the rules left in 3.2 as rules. The skill before offered the move only as an
  author decision ("Keeping them where they are is defensible") and kept the accuracy in 3.2.2.
- **Moves, not deletions.** "Every repair below is a move. Each number keeps its value and stays in the paper, and
  each caveat moves with its number."

No arm flagged the Abstract's "passes its reference-distribution audit" (no rubric item scores it); the skill
after defended it as a scope condition, which is a fair reading.

## The control: three reports the repaired version did not earn, or did

The clean control kept the rounded figures, the audits' rules and Sections 4.3 and 4.4 where they are, and
proposed nothing back into Section 3. It still reported three passages, and the grader failed it on them:

- **"For 2,282 scores in the curation published on 27 September 2026"** (Section 3.2) as a dated count for
  Section 4.3. The grader called it debatable, leaning to a false alarm: it says how much of an input the method
  reads, like the training-set sizes the same answer kept in Methods. The skill after also moved it in the seeded
  run. section-roles.md does not say which side of the line the coverage of a curated input falls on.
- **"from a cleaned copy of the Catalog"** (Abstract) as a framing problem. The authors wrote that phrase
  deliberately in bc27fe5, beside what just-prs adds. section-roles.md says a tool is "never" framed "as a cleaned
  copy"; it should say a ready-to-use copy may be named beside what the tool adds, and is never the contribution
  itself.
- **The five package names** in the "Three ways in" feature, as availability detail (marked optional). A mild
  false alarm the reference does not address.

The pair (`expect: different`) therefore separates the two versions on the planted detail but not cleanly: the
control's verdict is FAIL for reasons the rubric did not anticipate. The two reference gaps above are the next
fix, followed by a rerun of the control.

The answers and grades are kept with the authors' session notes, not in this repository: they quote the draft at
length.
