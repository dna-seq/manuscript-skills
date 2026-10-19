# Interview mode: choosing a journal by the AI-policy burden the authors accept

Use this interview when the authors ask to be interviewed about journal choice or AI-policy tradeoffs.
Skip questions the manuscript or conversation already answers. Ask a short batch of unresolved choices,
using the environment's supported question interface when available, then rank after the answers arrive.
For a ranking without an interview request, use the field mapping and score explanations below without
starting a questionnaire. Only genuinely missing decision-changing facts need questions.

## Questions and the flags they set

Ask in plain words, as the first column does ("Would you rule out journals that ban AI drafting?"); the
flags and `--refuse` values are for the command, not for the question.

| ask | `venues.py rank` flag |
|---|---|
| field and kind of paper: research, methods, software or tool, database, data, review, perspective | `--field aging\|bioinformatics\|genomics\|genetics\|systems-biology\|clinical\|general\|data\|software`, `--type …` |
| what AI did to the text: polish, revision or drafting (per section if it differs) | `--ai-use polish\|revision\|drafting` |
| which AI-policy burdens they will not carry (multi-select) | `--refuse` (repeatable), values below |
| a floor: JIF, open access only | `--min-jif`, `--oa full` |
| whose venues to consider: colleagues, a lab, the authors they cite most | `peers "Name" …`, then `rank --only KEY …` |
| validation they have or can afford, for public-data work | `--study-design`, `--validation-available` (see `selection-fields.md`) |
| a preprint first | `rank --preprints` (arXiv, bioRxiv, medRxiv, Research Square, SSRN, Preprints.org) |
| what matters most, in order, for each ladder: speed, reach, AI-policy burden, cost (and, for the preprint ladder, a direct transfer to the first journals) | `ladder --priority …` (`speed`, `reach`, `ai`, `cost`, `transfer`), recorded as `priorities` in the shared record |

`--refuse` values, each a burden the authors can decline:

| value | excludes venues that |
|---|---|
| `drafting-ban` | forbid drafting text from a prompt (ISCB journals, Royal Society, Taylor & Francis, some society journals) |
| `red-line` | forbid AI-written results or discussion (the Springer Nature framework, Sage) |
| `prompts` | require or encourage prompts in the paper or the supplement |
| `tracking` | require AI records beyond one acknowledgement: deposited outputs, kept versions (left out by default; `--include-tracking` lists them) |
| `ai-detector` | name AI-text detection at submission (PNAS uses Pangram) or say they may use it |
| `supplement` | want AI use documented in supplementary material too |
| `multi-place` | want the disclosure in three or more places |
| `disclosure-penalty` | say disclosed AI use may weigh in the decision |

## Reading the friction score

The score measures administrative burden for AI-assisted text, not the chance of rejection:

- the writing rule: free 0, disclose 1, disclose everything (no language-polish exemption) 2, red line 2,
  drafting ban 5;
- record keeping, counted once at its highest level: prompts on request, records recommended or prompts
  encouraged 1, prompts required or records required 3;
- AI-text screening: named detector 2, "may use detection tools" 1, plagiarism and paper-mill checks 0;
- listed extra burdens (deposited outputs, AI-free replies to reviewers, no LLM during revision, the tool
  cited as a reference, labelled AI text), at most 2;
- +1 when the policy says disclosed use may count against the paper, −1 when it says it will not.

Tiers: 0–1 light, 2–3 moderate, 4–5 heavy, 6 and more severe. AI image rules are listed by `show` but not
scored. The "for this AI use" column states what the rule means for the authors' actual use, which matters
more than the total: a drafting ban costs nothing for polish, and for an AI-drafted paper it is a policy
conflict that the authors decide how to handle. Show that venue as "Depends", with the rule quoted, its
page linked and one sentence on what it means for this manuscript, and list the conflict with the
authors' other decisions; never exclude the venue for it.

## Report

Write the shortlist as the selection skill's delivery section describes: plain words, each rule quoted
with the URL of its page, acronyms spelled out, full sentences. Keep friction and fit apart and give the
burden each venue would put on this manuscript in words ("6 points, severe: the journal asks authors not
to have AI draft text"), with the date each policy was read. Re-read the policy pages of the two or three
venues you recommend (`policy_watch.py check --venue KEY`). Say which venues' entries were checked only in
part, rest on secondary sources, or have not been researched.
