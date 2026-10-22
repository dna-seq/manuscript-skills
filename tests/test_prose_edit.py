"""Offline tests for manuscript-prose-edit's guard: sentence-aligned claim checks and the revision inventory.

Run with `uv run pytest tests/test_prose_edit.py -vvv`.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evals" / "fixtures" / "manuscript-prose-edit"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard = _load("prose_edit_guard", ROOT / "skills" / "manuscript-prose-edit" / "scripts" / "guard.py")
CLAIM_KINDS = {"causal", "evidential", "generality", "scope", "limitation", "null_result", "evidence_status", "negation"}


def _changes(before: str, after: str) -> list[dict]:
    return guard.sentence_changes(before, after)[0]


def _claims(before: str, after: str) -> list[dict]:
    return [c for c in _changes(before, after) if c["kind"] in CLAIM_KINDS]


def _only(changes: list[dict], kind: str) -> dict:
    found = [c for c in changes if c["kind"] == kind]
    assert len(found) == 1, (kind, changes)
    return found[0]


# --- ladders: every step up is protected, every step down a warning ---------------------------------------------

SUBJECT, OBJECT = "Carriers of the APOE e4 allele", "shorter telomeres in the replication cohort"
CAUSAL_STEPS = ["are consistent with", "are associated with", "predict", "contribute to", "lead to", "cause"]
CLAIM = "lower TERT expression in older donors limits DNA repair"
EVIDENTIAL_STEPS = ["may reflect", "suggest", "indicate", "show", "prove"]


def _ladder_cases(steps: list[str], make) -> list[tuple[str, str, str]]:
    cases = []
    for low, high in zip(steps, steps[1:]):
        cases.append((make(low), make(high), "raised"))
        cases.append((make(high), make(low), "lowered"))
    return cases


@pytest.mark.parametrize(("before", "after", "direction"), _ladder_cases(
    CAUSAL_STEPS, lambda v: f"{SUBJECT} {v} {OBJECT}."))
def test_causal_ladder_step(before: str, after: str, direction: str) -> None:
    claims = _claims(before, after)
    finding = _only(claims, "causal")
    assert finding["change"] == direction
    assert finding["severity"] == ("protected" if direction == "raised" else "warning")
    assert (finding["before"], finding["after"]) == (before, after)
    assert {c["kind"] for c in claims} == {"causal"}
    assert guard.exit_code(guard.compare(before, after)) == (1 if direction == "raised" else 0)


@pytest.mark.parametrize(("before", "after", "direction"), _ladder_cases(
    EVIDENTIAL_STEPS, lambda v: f"These results {v} that {CLAIM}."))
def test_evidential_ladder_step(before: str, after: str, direction: str) -> None:
    finding = _only(_claims(before, after), "evidential")
    assert finding["change"] == direction
    assert finding["severity"] == ("protected" if direction == "raised" else "warning")
    assert finding["before_line"] == finding["after_line"] == 1


def test_a_dropped_hedge_raises_and_a_stacked_hedge_does_not() -> None:
    raised = _only(_claims("These data may suggest a role for APOE in repair.",
                           "These data suggest a role for APOE in repair."), "evidential")
    assert (raised["change"], raised["removed"]) == ("raised", ["may"])
    assert _claims("Smoking may potentially shorten telomeres in older donors.",
                   "Smoking may shorten telomeres in older donors.") == []


def test_a_lowered_claim_in_a_negated_sentence_is_protected() -> None:
    finding = _only(_claims("The variant did not cause disease in carriers of the founder haplotype.",
                            "The variant was not associated with disease in carriers of the founder haplotype."),
                    "causal")
    assert (finding["change"], finding["severity"]) == ("lowered", "protected")


def test_descriptive_and_procedural_verbs_are_not_claims() -> None:
    assert _claims("Figure 2 shows the layout of the annotation pipeline.",
                   "Figure 2 presents the layout of the annotation pipeline.") == []
    assert _claims("We established a pipeline for annotating whole genomes.",
                   "We built a pipeline for annotating whole genomes.") == []
    assert _only(_claims("Figure 2 suggests that coverage limits recall.",
                         "Figure 2 shows that coverage limits recall."), "evidential")["change"] == "raised"


@pytest.mark.parametrize("after, added", [
    ("TeloScan is the first scalable alternative to wet-lab telomere assays.", "the first scalable alternative"),
    ("TeloScan is a novel scalable alternative to wet-lab telomere assays.", "novel"),
    ("TeloScan is always a scalable alternative to wet-lab telomere assays.", "always"),
])
def test_novelty_and_generality_wording_is_protected(after: str, added: str) -> None:
    finding = _only(_claims("TeloScan is a scalable alternative to wet-lab telomere assays.", after), "generality")
    assert (finding["change"], finding["severity"], finding["added"]) == ("raised", "protected", [added])


# --- scope, null results and evidence status ----------------------------------------------------------------------

@pytest.mark.parametrize("before, lost", [
    ("In this cohort, rs429358 was associated with shorter telomeres.", "In this cohort"),
    ("Knockout of Tert led to shorter telomeres in mice within two generations.", "in mice"),
    ("In our data, carriers of rs429358 had shorter telomeres than non-carriers.", "In our data"),
    ("Under these conditions, the annotation was robust to coverage between 25x and 60x.", "Under these conditions"),
    ("The score was calibrated in European-ancestry samples from three biobanks.", "European-ancestry"),
    ("Binding of the inhibitor to TERT was observed in vitro at nanomolar doses.", "in vitro"),
    ("The variant was associated with longevity in some cohorts of older adults.", "in some cohorts"),
])
def test_a_lost_scope_qualifier_is_protected(before: str, lost: str) -> None:
    after = before.replace(lost + ", ", "").replace(" " + lost, "").replace(lost, "")
    after = after[0].upper() + after[1:]
    finding = _only(_claims(before, after), "scope")
    assert (finding["change"], finding["severity"]) == ("removed", "protected")
    assert finding["removed"] == [lost]
    assert guard.exit_code(guard.compare(before, after)) == 1


@pytest.mark.parametrize("before, after", [
    ("In this cohort, rs429358 was associated with shorter telomeres.",
     "In our cohort, rs429358 was associated with shorter telomeres."),
    ("Knockout of Tert led to shorter telomeres in mice within two generations.",
     "Knockout of Tert led to shorter telomeres in a mouse model within two generations."),
    ("In this study, we present a tool that estimates telomere length.",
     "We present a tool that estimates telomere length."),
])
def test_scope_synonyms_and_paper_framing_are_not_changes(before: str, after: str) -> None:
    assert [c for c in _claims(before, after) if c["kind"] == "scope"] == []


def test_an_added_qualifier_is_a_warning() -> None:
    finding = _only(_claims("Carriers of rs429358 had shorter telomeres than non-carriers.",
                            "In this cohort, carriers of rs429358 had shorter telomeres than non-carriers."), "scope")
    assert (finding["change"], finding["severity"]) == ("added", "warning")


@pytest.mark.parametrize("before, after", [
    ("We found no significant difference in telomere length between arms.",
     "We found a difference in telomere length between arms."),
    ("Telomere length did not differ between smokers and non-smokers.",
     "Telomere length differed between smokers and non-smokers."),
    ("The variant was not associated with body mass index in the cohort.",
     "The variant was associated with body mass index in the cohort."),
    ("The variant was not associated with body mass index in the cohort.",
     "The variant was independent of body mass index in the cohort."),
])
def test_a_lost_null_result_is_protected(before: str, after: str) -> None:
    finding = _only(_claims(before, after), "null_result")
    assert (finding["change"], finding["severity"]) == ("removed", "protected")
    assert [c for c in _claims(before, after) if c["kind"] == "negation"] == []  # one change, reported once


def test_a_reworded_null_result_is_not_a_change() -> None:
    assert [c for c in _claims("Telomere length did not differ between smokers and non-smokers.",
                               "Telomere length showed no difference between smokers and non-smokers.")
            if c["kind"] == "null_result"] == []


@pytest.mark.parametrize("before, after, change, lost", [
    ("Participants reported improvement in sleep quality after the intervention.",
     "Participants improved in sleep quality after the intervention.", "removed", ["reported"]),
    ("Self-reported smoking was associated with shorter telomeres in the cohort.",
     "Smoking was associated with shorter telomeres in the cohort.", "removed", ["self-reported"]),
    ("Predicted loss-of-function variants were enriched in long-lived individuals.",
     "Observed loss-of-function variants were enriched in long-lived individuals.", "replaced", ["predicted"]),
])
def test_a_changed_evidence_status_is_protected(before: str, after: str, change: str, lost: list[str]) -> None:
    finding = _only(_claims(before, after), "evidence_status")
    assert (finding["change"], finding["severity"], finding["removed"]) == (change, "protected", lost)


def test_reporting_verbs_are_not_an_evidence_status() -> None:
    assert _claims("Here we report a tool that estimates telomere length.",
                   "Here we present a tool that estimates telomere length.") == []
    assert _claims("Runtimes are reported in Table 2 for every genome.",
                   "Runtimes are listed in Table 2 for every genome.") == []


# --- limiting and concessive words ---------------------------------------------------------------------------------

# The smoke run's Paper 1 Conclusion (markers kept as in the file): "Albeit tested on" went and the guard exited 0.
P1_CONCLUSION_BEFORE = (
    "Albeit tested on<!-- @rev A3c rounds=2 by=claude:2026-10-11,claude:2026-10-12 --> four genomes for annotation "
    "and one for scoring, the reported benchmarks show faster annotation than the OakVar-based Generation I system "
    "run on the same machine<!-- @/rev A3c --> and close numerical agreement between scoring engines.\n")
P1_CONCLUSION_AFTER = (
    "<!-- @rev A3c rounds=2 by=claude:2026-10-11,claude:2026-10-12 -->In the reported benchmarks on four genomes for "
    "annotation and one for scoring, annotation was faster than in the OakVar-based Generation I system run on the "
    "same machine<!-- @/rev A3c -->, with close numerical agreement between scoring engines.\n")


@pytest.mark.parametrize("before, after, lost", [
    ("The annotation was tested on only four genomes and was faster than the Generation I system.",
     "The annotation was tested on four genomes and was faster than the Generation I system.", "only"),
    (P1_CONCLUSION_BEFORE, P1_CONCLUSION_AFTER, "albeit"),
    ("Although tested on four genomes, the benchmarks show faster annotation than the Generation I system.",
     "Tested on four genomes, the benchmarks show faster annotation than the Generation I system.", "although"),
    ("Even though the benchmark used one genome for scoring, the two engines agreed closely on every score.",
     "The benchmark used one genome for scoring, and the two engines agreed closely on every score.", "even though"),
    ("Despite the small benchmark of four genomes, annotation was faster than in the Generation I system.",
     "With a benchmark of four genomes, annotation was faster than in the Generation I system.", "despite"),
    ("While the benchmark covered four genomes, annotation was faster than in the Generation I system.",
     "The benchmark covered four genomes, and annotation was faster than in the Generation I system.", "while"),
])
def test_a_lost_limiting_or_concessive_word_is_protected(before: str, after: str, lost: str) -> None:
    finding = _only(_claims(before, after), "limitation")
    assert (finding["change"], finding["severity"], finding["removed"]) == ("removed", "protected", [lost])
    assert guard.exit_code(guard.compare(before, after)) == 1
    assert guard.exit_code(guard.compare(before, after, allow_strengthening=True)) == 0
    assert guard.exit_code(guard.compare(before, after, revision=True)) == 0


@pytest.mark.parametrize("before, after, lost", [
    # the claim was narrowed in the same edit (a lowered rung and an added qualifier)
    ("Although tested on four genomes, the benchmarks show faster annotation than the Generation I system.",
     "On these four genomes, the benchmarks suggest faster annotation than the Generation I system.", "although"),
    # the whole sentence went: a deletion the authors must see, not a claim that now reads wider
    ("Annotation was faster than in the Generation I system. A limitation is that we tested only two genomes.",
     "Annotation was faster than in the Generation I system.", "only"),
])
def test_a_lost_limiting_word_is_a_warning_when_the_claim_was_narrowed_or_deleted(before: str, after: str,
                                                                                  lost: str) -> None:
    finding = _only(_claims(before, after), "limitation")
    assert (finding["change"], finding["severity"], finding["removed"]) == ("removed", "warning", [lost])
    assert guard.exit_code(guard.compare(before, after)) == 0


@pytest.mark.parametrize("before, after", [
    ("Although tested on only four genomes, the benchmarks show faster annotation.",
     "The benchmarks show faster annotation, although they were run on only four genomes."),
    ("Although the benchmark covered four genomes, annotation was faster than in the Generation I system.",
     "The benchmark covered four genomes. However, annotation was faster than in the Generation I system."),
    ("However, biology is not linear, and interactions are not always captured by a polygenic score.",
     "Biology is not linear, though, and interactions are not always captured by a polygenic score."),
    ("However, most scoring files were derived from European cohorts in the catalogue.",
     "Most scoring files were derived from European cohorts in the catalogue."),
    ("The annotation was tested on only four genomes in the benchmark.",
     "The annotation was tested on merely four genomes in the benchmark."),
    ("The tool annotates not only single-nucleotide variants but also short indels.",
     "The tool annotates single-nucleotide variants and short indels."),
    ("It is the only annotation tool that runs offline on a laptop.",
     "It is an annotation tool that runs offline on a laptop."),
    ("Annotation took longer on the long-read genome, while memory stayed under the limit.",
     "Annotation took longer on the long-read genome; memory stayed under the limit."),
])
def test_a_concession_kept_moved_or_replaced_and_non_limiting_uses_are_not_changes(before: str, after: str) -> None:
    assert [c for c in _claims(before, after) if c["kind"] == "limitation"] == []


def test_an_added_limiting_word_is_a_warning() -> None:
    finding = _only(_claims("The benchmarks show faster annotation than the Generation I system.",
                            "The benchmarks show faster annotation than the Generation I system, although only on "
                            "four genomes."), "limitation")
    assert (finding["change"], finding["severity"]) == ("added", "warning")


# --- numbers, citations and identifiers per sentence ---------------------------------------------------------------

def test_a_new_number_inside_a_rephrased_sentence_is_located() -> None:
    before = "## Results\n\nThe new caller was substantially faster than GATK on all benchmark genomes (Table 2).\n"
    after = "## Results\n\nThe new caller was 4.2 times faster than GATK on every benchmark genome (Table 2).\n"
    finding = _only(_changes(before, after), "number")
    assert (finding["token"], finding["token_status"], finding["severity"]) == ("4.2", "new", "protected")
    assert (finding["section"], finding["before_line"], finding["after_line"]) == ("Results", 3, 3)


def test_a_number_moved_within_its_paragraph_is_a_warning_and_from_elsewhere_is_protected() -> None:
    before = ("The caller was substantially faster than GATK on the benchmark genomes. Table 2 lists a 4.2-fold "
              "speed-up.\n\nMemory use stayed under 8 GB on every genome.\n")
    within = ("The caller was 4.2-fold faster than GATK on the benchmark genomes. Table 2 lists the "
              "speed-up.\n\nMemory use stayed under 8 GB on every genome.\n")
    statuses = {(c["change"], c["token_status"], c["severity"]) for c in _changes(before, within)}
    assert statuses == {("added", "moved_within_paragraph", "warning"), ("removed", "moved_within_paragraph", "warning")}
    elsewhere = before.replace("on every genome.", "on every genome, 8 GB in total.").replace(
        "substantially faster than GATK", "substantially faster than GATK with 8 GB")
    finding = [c for c in _changes(before, elsewhere) if c["token"] == "8gb" and c["before_line"] == 1]
    assert [(c["token_status"], c["severity"]) for c in finding] == [("from_elsewhere", "protected")]


@pytest.mark.parametrize("before, after, token", [
    ("Existing tools require high coverage (Ding et al., 2014).",
     "Existing tools need high coverage (Ding et al., 2014; Nersisyan and Arakelyan, 2015).", "Nersisyan 2015"),
    ("Existing tools require high coverage [3].", "Existing tools need high coverage [3, 4].", "[4]"),
    ("Existing tools require high coverage~\\citep{ding2014}.\n\\section{Methods}",
     "Existing tools need high coverage~\\citep{ding2014,nersisyan2015}.\n\\section{Methods}",
     "\\cite{nersisyan2015}"),
    ("Existing tools require high coverage [@ding2014].", "Existing tools need high coverage [@ding2014; @lee2021].",
     "@lee2021"),
    ("Telomere attrition is a hallmark of ageing (Müller et al., 2019).",
     "Telomere attrition is a hallmark of ageing (Müller et al., 2019; Østergaard, 2020).", "Østergaard 2020"),
])
def test_a_new_citation_is_reported_alone(before: str, after: str, token: str) -> None:
    found = [c for c in _changes(before, after) if c["kind"] == "citation"]
    assert [(c["token"], c["token_status"], c["change"]) for c in found] == [(token, "new", "added")]


def test_reformatting_a_number_or_citation_is_not_a_sentence_change() -> None:
    assert _changes("We sequenced 1,204 genomes (Lambert et al., 2021) at 30x.",
                    "We sequenced 1204 genomes (Lambert et al. 2021) at 30x.") == []


# --- alignment: split, merged and moved sentences -----------------------------------------------------------------

def test_split_and_merged_sentences_align_without_findings() -> None:
    before = ("TeloScan processed each genome in 4.2 minutes, and in this cohort, telomere length was associated "
              "with age (r = -0.31). The tool is robust to coverage. This held at all three centres.\n")
    after = ("TeloScan processed each genome in 4.2 minutes. In this cohort, telomere length was associated "
             "with age (r = -0.31). The tool is robust to coverage at all three centres.\n")
    changes, alignment = guard.sentence_changes(before, after)
    assert changes == []
    assert (alignment["split"], alignment["merged"]) == (1, 1)


def test_a_scope_lost_while_splitting_is_still_caught() -> None:
    before = "TeloScan processed each genome in 4.2 minutes, and in mice, telomere length fell with age.\n"
    after = "TeloScan processed each genome in 4.2 minutes. Telomere length fell with age.\n"
    changes, alignment = guard.sentence_changes(before, after)
    assert alignment["split"] == 1
    assert [(c["kind"], c["removed"], c["alignment"]) for c in changes] == [("scope", ["in mice"], "split")]


def test_a_moved_sentence_is_not_a_change() -> None:
    before = ("Variants were called with DeepVariant on every genome. Reads were aligned with BWA-MEM to GRCh38.\n\n"
              "Coverage was computed with mosdepth for each sample.\n")
    after = ("Variants were called with DeepVariant on every genome.\n\nCoverage was computed with mosdepth for each "
             "sample. Reads were aligned with BWA-MEM to GRCh38.\n")
    changes, alignment = guard.sentence_changes(before, after)
    assert changes == [] and alignment["moved"] == 1


def test_a_deleted_limitation_and_a_new_claim_sentence_are_reported() -> None:
    before = "Telomere length fell with age. The effect may not generalise beyond European-ancestry samples.\n"
    after = "Telomere length fell with age. Telomere shortening drives frailty in older adults.\n"
    kinds = {(c["kind"], c["change"], c["severity"]) for c in _claims(before, after)}
    assert ("scope", "removed", "protected") in kinds
    assert ("causal", "added", "protected") in kinds


def test_dynamic_programming_alignment_scales_to_a_long_manuscript() -> None:
    before = "\n\n".join(f"Sample group {i} had a median coverage of {i} reads at locus L{i} in the cohort."
                         for i in range(800))
    after = before.replace(" had a median coverage ", " showed a median coverage ")
    changes, alignment = guard.sentence_changes(before, after)
    assert alignment["changed"] == alignment["sentences_before"] == 800 and changes == []


# --- Markdown and LaTeX structure ---------------------------------------------------------------------------------

MARKDOWN = """---
title: TeloScan
---

# Results

## Performance

<!-- @rev C3 rounds=1 by=x:2026-10-01 -->Each genome took 4.2 minutes in this cohort.<!-- @/rev C3 -->

- Peak memory was 7.5 GB.
- Runtime scaled linearly with coverage.

| Tool | Minutes |
|---|---|
| TeloScan | 4.2 |

```python
x = 1  # not prose
```

In 40% of runs (Smith et al., 2020) the cache was warm.
"""


def test_markdown_sections_lines_lists_tables_and_comments() -> None:
    sentences = guard.segment(MARKDOWN)
    by_text = {s.text: s for s in sentences}
    assert by_text["Each genome took 4.2 minutes in this cohort."].line == 9
    assert by_text["Peak memory was 7.5 GB."].section == "Results > Performance"
    assert "| TeloScan | 4.2 |" in by_text and not any("not prose" in t for t in by_text)
    edited = MARKDOWN.replace("| TeloScan | 4.2 |", "| TeloScan | 4.9 |").replace("rounds=1", "rounds=2")
    numbers = [c for c in _changes(MARKDOWN, edited) if c["kind"] == "number"]
    assert {(c["token"], c["change"], c["after_line"]) for c in numbers} == {("4.2", "removed", 16),
                                                                            ("4.9", "added", 16)}


def test_a_percent_sign_in_markdown_does_not_hide_the_rest_of_the_line() -> None:
    edited = MARKDOWN.replace("(Smith et al., 2020)", "(Lee et al., 2021)")
    report = guard.compare(MARKDOWN, edited)
    assert report["protected"]["citations"] == {"removed": {"(Smith et al., 2020)": 1},
                                                "added": {"(Lee et al., 2021)": 1}}
    assert {c["token"] for c in report["sentence_changes"]} == {"Smith 2020", "Lee 2021"}


LATEX = r"""\documentclass{article}
\begin{document}
\section{Results}
\subsection{Association}
Variants in \textit{APOE} were associated with longevity in this cohort~\citep{smith2020}. % 40% done
Runtime fell by 12\% (Fig.~\ref{fig:runtime}).
\begin{equation}
y = 2x + 3
\end{equation}
\end{document}
"""


def test_latex_sections_comments_and_citation_keys() -> None:
    sentences = guard.segment(LATEX)
    assert [(s.line, s.section) for s in sentences] == [(5, "Results > Association"), (6, "Results > Association")]
    assert guard.compare(LATEX, LATEX.replace("% 40% done", "% 90% done"))["sentence_changes"] == []
    edited = LATEX.replace("were associated with longevity in this cohort~\\citep{smith2020}",
                           "drive longevity~\\citep{smith2020,lee2021}")
    found = {(c["kind"], c["change"], c["after_line"]) for c in _changes(LATEX, edited)}
    assert found == {("causal", "raised", 5), ("scope", "removed", 5), ("citation", "added", 5)}


# --- malformed and boundary input ---------------------------------------------------------------------------------

@pytest.mark.parametrize("before, after", [
    ("", ""),
    ("# Only a heading\n", "# Only a heading\n"),
    ("   \n\n\t\n", ""),
    ("No terminal punctuation in this line", "No terminal punctuation in this line"),
])
def test_empty_and_degenerate_input(before: str, after: str) -> None:
    changes, alignment = guard.sentence_changes(before, after)
    assert changes == [] and alignment["changed"] == alignment["deleted"] == alignment["inserted"] == 0


def test_abbreviations_do_not_split_sentences() -> None:
    texts = [s.text for s in guard.segment("As in Fig. 2 and Smith et al. (2020), e.g. at 4.2 Mb, it held. Next.\n")]
    assert texts == ["As in Fig. 2 and Smith et al. (2020), e.g. at 4.2 Mb, it held.", "Next."]


# --- the fixtures: clean control and seeded edit ------------------------------------------------------------------

ORIGINAL = (FIXTURES / "original.md").read_text(encoding="utf-8")

# (kind, change, after line) of every change planted in edited-seeded.md.
PLANTED = {
    ("evidential", "raised", 5),        # "suggest ... may be useful" → "show ... is useful"
    ("citation", "added", 9),           # [3] → [3, 4]
    ("causal", "raised", 17),           # "was associated with" → "caused", inside a split sentence
    ("evidence_status", "removed", 17),  # "self-reported smokers" → "smokers"
    ("null_result", "removed", 17),     # "were not associated" → "were independent of"
    ("causal", "raised", 17),           # the same sentence: the association verb went under negation
    ("scope", "removed", 17),           # "In mice" dropped
    ("number", "added", 17),            # a confidence interval added: 95%, 0.55, 0.83
    ("evidential", "raised", 21),       # "suggest ... may provide" → "provides"
    ("generality", "raised", 21),       # "the first scalable alternative"
    ("scope", "removed", 21),           # "beyond European-ancestry samples" dropped
}


def test_clean_control_passes_with_no_sentence_finding() -> None:
    report = guard.compare(ORIGINAL, (FIXTURES / "edited-clean.md").read_text(encoding="utf-8"))
    assert report["sentence_changes"] == [] and report["protected"] == {}
    assert guard.exit_code(report) == 0
    assert report["alignment"]["split"] == report["alignment"]["merged"] == 1


def test_seeded_edit_reports_each_planted_change_at_its_location() -> None:
    report = guard.compare(ORIGINAL, (FIXTURES / "edited-seeded.md").read_text(encoding="utf-8"))
    found = {(c["kind"], c["change"], c["after_line"]) for c in report["sentence_changes"]}
    assert found == PLANTED
    numbers = {c["token"] for c in report["sentence_changes"] if c["kind"] == "number"}
    assert numbers == {"95%", "0.55", "0.83"}
    assert guard.exit_code(report) == 1


def test_allow_strengthening_authorises_claims_but_never_numbers() -> None:
    seeded = (FIXTURES / "edited-seeded.md").read_text(encoding="utf-8")
    report = guard.compare(ORIGINAL, seeded, allow_strengthening=True)
    authorised = {c["kind"] for c in report["sentence_changes"] if c["authorised"]}
    assert authorised == {"causal", "evidential", "generality", "scope", "null_result", "evidence_status"}
    assert not any(c["authorised"] for c in report["sentence_changes"] if c["kind"] in ("number", "citation"))
    assert guard.exit_code(report) == 1
    claim_only = ("These results suggest that lower TERT expression limits repair.",
                  "These results show that lower TERT expression limits repair.")
    assert guard.exit_code(guard.compare(*claim_only)) == 1
    assert guard.exit_code(guard.compare(*claim_only, allow_strengthening=True)) == 0


def test_revision_mode_lists_changes_and_never_fails() -> None:
    revised = (FIXTURES / "revised.md").read_text(encoding="utf-8")
    report = guard.compare(ORIGINAL, revised, revision=True)
    assert report["mode"] == "revision" and guard.exit_code(report) == 0
    assert report["protected"]  # the revision changes content, and it is still listed
    for c in report["sentence_changes"]:
        assert c["section"] and (c["before_line"] or c["after_line"])
        assert set(c) >= {"id", "kind", "change", "severity", "before", "after", "removed", "added", "token",
                          "token_status", "alignment", "authorised", "note"}
    assert [c["id"] for c in report["sentence_changes"]] == list(range(1, len(report["sentence_changes"]) + 1))
    assert guard.to_markdown(report).startswith("# Revision inventory")


def test_existing_guard_example_also_gets_sentence_findings() -> None:
    before = ("Annotating a 4.5 GB VCF took 40 s on GRCh38 (Lambert et al., 2021). It is important to note that "
              "this matters.\n\nThe APOE variant rs429358 is associated with lower longevity in some cohorts, and "
              "the effect may not replicate.\n")
    after = ("Annotating a 4.6 GB VCF took 40 s on GRCh38. This matters.\n\n"
             "The APOE variant rs429358 causes lower longevity in cohorts, and the effect replicates.\n")
    found = {(c["kind"], c["change"]) for c in _changes(before, after)}
    assert {("causal", "raised"), ("evidential", "raised"), ("scope", "removed"), ("negation", "removed"),
            ("number", "added"), ("number", "removed"), ("citation", "removed")} <= found


# --- command line -------------------------------------------------------------------------------------------------

def test_cli_writes_json_and_markdown_and_uses_documented_exit_codes(tmp_path: Path) -> None:
    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    seeded, clean = FIXTURES / "edited-seeded.md", FIXTURES / "edited-clean.md"
    runner = CliRunner()
    result = runner.invoke(guard.app, [str(FIXTURES / "original.md"), str(seeded), "--json", str(out_json),
                                       "--md", str(out_md)])
    assert result.exit_code == 1
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["mode"] == "edit" and data["summary"]["protected"] > 0
    assert out_md.read_text(encoding="utf-8") == result.output.rstrip("\n") + "\n"
    assert runner.invoke(guard.app, [str(FIXTURES / "original.md"), str(clean)]).exit_code == 0
    assert runner.invoke(guard.app, [str(FIXTURES / "original.md"), str(seeded), "--revision"]).exit_code == 0
    assert runner.invoke(guard.app, [str(FIXTURES / "original.md")]).exit_code == 2


def test_cli_against_a_git_ref(tmp_path: Path) -> None:
    paper = tmp_path / "paper.md"
    paper.write_text(ORIGINAL, encoding="utf-8")

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "T")
    git("add", paper.name)
    git("commit", "-q", "-m", "original")
    paper.write_text((FIXTURES / "edited-seeded.md").read_text(encoding="utf-8"), encoding="utf-8")
    result = CliRunner().invoke(guard.app, [str(paper), "--against", "HEAD", "--revision"])
    assert result.exit_code == 0 and "the scope qualifier \u201cIn mice\u201d was dropped" in result.output


def test_dropping_the_article_adjective_reported_is_not_an_evidence_status_change() -> None:
    """'The reported benchmarks' names the paper's own results; only a self-report status is protected."""
    def kinds(before: str, after: str) -> set[tuple[str, str]]:
        report = guard.compare(before, after)
        return {(c["kind"], c["severity"]) for c in report["sentence_changes"]}
    assert ("evidence_status", "protected") not in kinds(
        "The reported benchmarks ran on one laptop.\n", "The benchmarks ran on one laptop.\n")
    assert ("evidence_status", "protected") in kinds(
        "Participants reported less pain after treatment.\n", "Participants had less pain after treatment.\n")


# --- the Markdown report reads as prose for the authors -----------------------------------------------------------

def _markdown(before: str, after: str, **options: bool) -> str:
    return guard.to_markdown(guard.compare(before, after, **options))


def test_a_finding_continues_its_sentence_in_lower_case_but_keeps_acronyms() -> None:
    """'In the Results (line 3), a negation changed', never 'In the Results (line 3), A negation changed'."""
    report = _markdown("# Results\n\nThe tool does not need a GPU.\n", "# Results\n\nThe tool needs a GPU.\n")
    assert "In the Results (line 3), a negation changed" in report
    assert ", A " not in report
    assert guard._lower_first("APOE carriers lived longer.") == "APOE carriers lived longer."
    assert guard._lower_first("GRCh38 coordinates were used.") == "GRCh38 coordinates were used."
    assert guard._lower_first("The number changed.") == "the number changed."


@pytest.mark.parametrize("headings, place", [
    ("## 5. Discussion\n\n### 5.1 Limitations\n\n", "In section 5.1, Limitations (line 5)"),
    ("## 6. Conclusion\n\n", "In section 6, Conclusion (line 3)"),
    ("## A.2 Extra runs\n\n", "In section A.2, Extra runs (line 3)"),
    ("## Discussion\n\n### Limitations\n\n", "In the Discussion, Limitations (line 5)"),
    ("## A Study of Mice\n\n", "In the A Study of Mice (line 3)"),  # a capital word, not a section number
])
def test_numbered_headings_are_named_by_their_number_and_title(headings: str, place: str) -> None:
    report = _markdown(headings + "Only four genomes were tested.\n", headings + "Four genomes were tested.\n")
    assert place in report
    assert "the 5." not in report and "the 6." not in report


def test_a_table_row_is_not_called_a_sentence() -> None:
    table = "# Results\n\n| Module | Content |\n|---|---|\n| Athletes | Variants associated with sprint speed |\n"
    report = _markdown(table, table.replace("| Athletes | Variants associated with sprint speed |\n", ""))
    assert "(a deleted table row, line 5 before the edit), a table row that claimed an association" in report
    assert "deleted sentence" not in report


@pytest.mark.parametrize("words, share", [(300, "Less than 1%"), (10, "About 10%")])
def test_the_change_rate_never_reads_as_zero_when_words_changed(words: int, share: str) -> None:
    before = " ".join(f"word{i}" for i in range(words)) + ".\n"
    report = _markdown(before, before.replace("word3 ", "other "))
    assert f"{share} of the original words changed" in report and "About 0%" not in report
    assert "None of the original words changed" in _markdown(before, before)


def test_a_change_only_the_whole_text_counts_see_is_described_in_a_full_sentence() -> None:
    """A technical term has no sentence-level check, so only the whole-text counts move."""
    report = guard.compare("We stored the calls as VCF files.\n", "We stored the calls as BCF files.\n")
    assert report["sentence_changes"] == [] and report["protected"]["terms"]
    markdown = guard.to_markdown(report)
    assert "not in any one" not in markdown
    assert "no single sentence accounts for" in markdown and guard.exit_code(report) == 1


def test_the_report_names_no_command_line_flags_or_internal_terms() -> None:
    seeded = (FIXTURES / "edited-seeded.md").read_text(encoding="utf-8")
    for options in ({}, {"allow_strengthening": True}, {"revision": True}, {"relocated": True}):
        markdown = guard.to_markdown(guard.compare(ORIGINAL, seeded, **options))
        for internal in ("--allow-strengthening", "--revision", "--relocated", "relocated_to", "protected", "rung",
                         "token_status", "severity", "moved_within_paragraph", "from_elsewhere", "evidential",
                         "the guard"):
            assert internal not in markdown, (options, internal)
    authorised = guard.to_markdown(guard.compare(ORIGINAL, seeded, allow_strengthening=True))
    assert "The authors asked for a claim correction, so nine claim changes are marked as authorised." in authorised


def test_usage_errors_say_what_to_give(tmp_path: Path) -> None:
    runner = CliRunner()
    missing = runner.invoke(guard.app, [str(FIXTURES / "original.md")])
    assert missing.exit_code == 2 and "second argument" in missing.output
    paper = tmp_path / "paper.md"
    paper.write_text(ORIGINAL, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    untracked = runner.invoke(guard.app, [str(paper), "--against", "HEAD"])
    assert untracked.exit_code == 2 and "not tracked by git" in untracked.output
    for args in (["config", "user.email", "t@example.invalid"], ["config", "user.name", "T"], ["add", "paper.md"],
                 ["commit", "-q", "-m", "original"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)
    unknown = runner.invoke(guard.app, [str(paper), "--against", "no-such-version"])
    assert unknown.exit_code == 2 and "git has no version of paper.md" in unknown.output


# --- a dropped sentence, paragraph pairing and text moved to another file -----------------------------------------

# An abstract rewritten for a journal: the Results paragraph is condensed, a plain claim sentence with no hedge,
# number or citation is dropped, and so are "declarative", "downloadable" and "local". Revision markers wrap the
# paragraphs as in the paper the smoke run edited.
ABSTRACT_BEFORE = """## Abstract

<!-- @rev C2b rounds=3 by=robi:2026-09-25,claude:2026-10-13 -->
**Results:** We present TeloKit, an open-source platform that combines local variant annotation and polygenic risk \
score (PRS) computation in a web interface. Annotation modules are declarative, versioned packages of variant-trait \
tables and their sources, allowing researchers to extend the catalogue without writing code. A registry distributes \
modules, and the platform applies them to the user's genome to produce downloadable reports. The scoring library \
provides scoring through web, command-line, Python, and Model Context Protocol interfaces.
<!-- @/rev C2b -->
<!-- @rev C2c rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->
Reports list each matched variant with its reported effect and sources. Polygenic scores are shown as percentiles \
within a reference population matched to the genome's inferred ancestry, with all models for a trait shown together. \
New modules can also be drafted with general-purpose AI assistants through a plugin, and pass the same validation as \
hand-written ones.
<!-- @/rev C2c -->
"""
ABSTRACT_AFTER = """## Abstract

<!-- @rev C2b rounds=4 by=robi:2026-09-25,claude:2026-10-13,claude:2026-10-19 -->
**Results:** TeloKit is an open-source platform for variant annotation and polygenic risk scoring with a web \
interface. Annotation modules are versioned packages of variant-trait tables and their sources, added without code \
and distributed through a registry.
<!-- @/rev C2b -->
<!-- @rev C2c rounds=3 by=robi:2026-09-25,claude:2026-10-10,claude:2026-10-19 -->
Reports list each matched variant with its reported effect and sources. The scoring library scores through web, \
command-line, Python and Model Context Protocol interfaces and shows percentiles within a reference population \
matched to the genome's inferred ancestry, with all models for a trait together.
<!-- @/rev C2c -->
"""
DROPPED = "New modules can also be drafted with general-purpose AI assistants"


@pytest.mark.parametrize("revision", [False, True])
def test_a_dropped_claim_sentence_is_reported_in_both_modes(revision: bool) -> None:
    report = guard.compare(ABSTRACT_BEFORE, ABSTRACT_AFTER, revision=revision)
    dropped = [c for c in report["sentence_changes"] if DROPPED in c["before"]]
    assert [(c["kind"], c["change"], c["after"], c["severity"]) for c in dropped] == [
        ("sentence", "removed", "", "warning")]
    registry = [c for c in report["sentence_changes"] if c["before"].startswith("A registry distributes")]
    assert [(c["kind"], c["change"]) for c in registry] == [("sentence", "removed")]
    markdown = guard.to_markdown(report)
    assert "In the Abstract (a deleted sentence, line 7 before the edit), the sentence is gone" in markdown
    assert f"Before the edit: “{DROPPED}" in markdown


@pytest.mark.parametrize("revision", [False, True])
def test_a_plain_statement_deleted_on_its_own_is_reported(revision: bool) -> None:
    """No hedge, number or citation: before the fix a deleted plain statement produced no finding at all."""
    before = (f"Telomeres shorten with age in this cohort.\n\n{DROPPED} through a plugin.\n\n"
              "Reports list each matched variant.\n")
    after = "Telomeres shorten with age in this cohort.\n\nReports list each matched variant.\n"
    changes = guard.compare(before, after, revision=revision)["sentence_changes"]
    assert [(c["kind"], c["change"], c["before_line"], c["alignment"]) for c in changes] == [
        ("sentence", "removed", 3, "deleted")]


def test_an_edit_may_cut_a_stock_sentence_unreported_and_the_inventory_still_lists_it() -> None:
    """The contract lets an edit cut a mini-conclusion; a revision inventory lists every deleted sentence."""
    before = ("Telomeres shorten with age in this cohort. In conclusion, these findings have important implications "
              "for ageing research.\n")
    after = "Telomeres shorten with age in this cohort.\n"
    assert guard.compare(before, after)["sentence_changes"] == []
    listed = guard.compare(before, after, revision=True)["sentence_changes"]
    assert [(c["kind"], c["change"]) for c in listed] == [("sentence", "removed")]


def test_a_sentence_merged_into_another_is_one_only_when_it_lends_it_words() -> None:
    """A 2:1 merge must not swallow a sentence that shares nothing with the merged one."""
    bs, as_ = guard.segment(ABSTRACT_BEFORE), guard.segment(ABSTRACT_AFTER)
    for g in guard.align(bs, as_):
        for i in g.before:
            if DROPPED in bs[i].text:
                assert g.kind == "deleted" and g.after == []


def test_the_revision_inventory_names_words_a_rewritten_sentence_dropped() -> None:
    report = guard.compare(ABSTRACT_BEFORE, ABSTRACT_AFTER, revision=True)
    dropped = {w for c in report["sentence_changes"] if c["kind"] == "wording" for w in c["removed"]}
    assert {"declarative", "local"} <= dropped
    first = [c for c in report["sentence_changes"] if c["before"].startswith("**Results:** We present")]
    assert first and "local" in first[0]["removed"] and "We present TeloKit" in first[0]["before"]
    markdown = guard.to_markdown(report)
    assert "“local”" in markdown and "“declarative”" in markdown
    # an edit is a copy edit: rewording is its job, so only the deleted sentences are listed
    edit = guard.compare(ABSTRACT_BEFORE, ABSTRACT_AFTER)
    assert not [c for c in edit["sentence_changes"] if c["kind"] == "wording"]


def test_a_kept_paragraph_next_to_a_removed_one_is_not_reported_as_removed() -> None:
    """Paragraphs of a changed run are paired by their words, not by position."""
    kept = ("On the primary genome, the median full run took 33.2 s against 6,005.4 s for the old pipeline, an "
            "approximately 181-fold speedup. Peak memory was 2,054 MB (Table 3).")
    caption = ("**Table 3.** Stage times and resources of the full runs (medians unless stated). Peak RAM is the "
               "resident memory summed over the whole process tree.")
    before = f"## Results\n\n{caption}\n\n| Stage | Time |\n|---|---|\n| Load | 4 s |\n\n{kept}\n"
    after = f"## Results\n\n{kept.replace('(Table 3)', '(Supplementary Table S10)')}\n"
    report = guard.compare(before, after, revision=True)
    starts = [(p["before"][:20], p["after"][:20]) for p in report["rewritten_paragraphs"]]
    assert ("On the primary genom", "") not in starts
    assert (caption[:20], "") in starts and ("| Stage | Time | |--", "") in starts
    assert "was removed" in guard.to_markdown(report)
    assert "On the primary genome, the median full run took 33.2 s against 6,005.4 s for the old pipeline, an " \
           "approximately 181-fold speedup. Peak memory was 2,054 MB (Table 3).…” was removed" not in \
           guard.to_markdown(report)


MOVED_SECTION = """## S9. Sex chromosomes

On chromosome X, both engines count a male's call as one copy and treat a heterozygous call as a no-call, \
since a single X cannot be heterozygous. The pseudoautosomal regions count as two copies in either sex.

The sample was marked male in PLINK2, and the engine inferred it as male (XY) from 1,204 chromosome X calls.
"""
MAIN_BEFORE = ("# Paper\n\n## Results\n\nScores were computed for 6,991 PGS IDs on GRCh38. The median run took "
               "12.5 s.\n\n" + MOVED_SECTION)
MAIN_AFTER = ("# Paper\n\n## Results\n\nScores were computed for 6,991 PGS IDs on GRCh38. The median run took "
              "12.5 s. Sex chromosomes are handled as described in Supplementary S9.\n")


def test_text_moved_verbatim_to_another_file_is_moved_not_removed(tmp_path: Path) -> None:
    supplement = "# Supplementary material\n\n" + MOVED_SECTION
    without = guard.compare(MAIN_BEFORE, MAIN_AFTER)
    assert {c["token_status"] for c in without["sentence_changes"] if c["token"]} == {"removed"}
    assert guard.exit_code(without) == 1
    report = guard.compare(MAIN_BEFORE, MAIN_AFTER, moved=[("supplementary.md", supplement)])
    assert not [c for c in report["sentence_changes"] if c["change"] == "removed"]
    assert report["protected"].get("numbers", {}).get("removed", {}) == {}
    assert report["alignment"]["moved_to_other_file"] == 3
    assert report["moved_to"]["files"] == ["supplementary.md"]
    assert not [p for p in report["rewritten_paragraphs"] if not p["after"]]
    assert guard.exit_code(report) == 0
    markdown = guard.to_markdown(report)
    assert "Restore" not in markdown and "supplementary.md" in markdown
    # the command line takes the files the text went to, as often as needed
    files = {name: tmp_path / name for name in ("before.md", "after.md", "supplementary.md", "notes.md")}
    for (name, path), text in zip(files.items(), (MAIN_BEFORE, MAIN_AFTER, supplement, "Notes.\n")):
        path.write_text(text, encoding="utf-8")
    runner = CliRunner()
    assert runner.invoke(guard.app, [str(files["before.md"]), str(files["after.md"])]).exit_code == 1
    moved = runner.invoke(guard.app, [str(files["before.md"]), str(files["after.md"]), "--moved-to",
                                      str(files["supplementary.md"]), "--moved-to", str(files["notes.md"])])
    assert moved.exit_code == 0 and "Restore" not in moved.output


def test_a_number_changed_on_the_way_to_another_file_is_still_reported() -> None:
    supplement = "# Supplementary material\n\n" + MOVED_SECTION.replace("1,204 chromosome X calls", "1,240 chromosome "
                                                                         "X calls")
    report = guard.compare(MAIN_BEFORE, MAIN_AFTER, moved=[("supplementary.md", supplement)])
    numbers = {(c["token"], c["change"], c["after_file"]) for c in report["sentence_changes"] if c["kind"] == "number"}
    assert numbers == {("1204", "removed", "supplementary.md"), ("1240", "added", "supplementary.md")}
    assert guard.exit_code(report) == 1
    assert "now in supplementary.md" in guard.to_markdown(report)


def test_a_deleted_passage_is_not_hidden_by_naming_a_file_it_did_not_go_to() -> None:
    report = guard.compare(MAIN_BEFORE, MAIN_AFTER, moved=[("notes.md", "# Notes\n\nUnrelated text about lab work.\n")])
    assert {c["kind"] for c in report["sentence_changes"] if c["change"] == "removed"} >= {"sentence", "number"}
    assert guard.exit_code(report) == 1


# --- caveats moved to another sentence on purpose (relocated) -----------------------------------------------------

def _paper(conclusion: str, limitation: str = "", kept: str = "Memory use was not profiled.") -> str:
    """A Discussion whose Limitations can gain a sentence, then a Conclusion. The unchanged sentence `kept` between
    them stops a caveat moved into the Limitations from aligning as a split of the sentence it left."""
    return ("# TeloKit\n\n## Discussion\n\nThe annotation ran offline on one laptop.\n\n### Limitations\n\n"
            f"The benchmark used a single laptop for every run. {limitation}{kept}\n\n## Conclusion\n\n{conclusion}\n")


def _line_of(text: str, sentence: str) -> int:
    return next(n for n, line in enumerate(text.splitlines(), 1) if sentence in line)


@pytest.mark.parametrize("conclusion_before, conclusion_after, limitation, word", [
    ("Albeit tested on four genomes, the annotation was faster than the Generation I system.",
     "The annotation was faster than the Generation I system.",
     "The speed comparison holds, albeit on four genomes for annotation and one for scoring.", "albeit"),
    ("Despite the small benchmark of four genomes, annotation was faster than in the Generation I system.",
     "Annotation was faster than in the Generation I system.",
     "The speed comparison held despite the small benchmark of four genomes.", "despite"),
])
def test_a_concession_moved_into_the_limitations_is_a_warning_only_with_relocated(
        tmp_path: Path, conclusion_before: str, conclusion_after: str, limitation: str, word: str) -> None:
    before, after = _paper(conclusion_before), _paper(conclusion_after, limitation + " ")
    without = guard.compare(before, after)
    assert [(c["kind"], c["severity"], c["removed"]) for c in without["sentence_changes"]] == [
        ("limitation", "protected", [word])]
    assert guard.exit_code(without) == 1
    assert "relocated" not in without and "relocated" not in without["summary"]
    assert not [c for c in without["sentence_changes"] if "relocated_to" in c]  # no new fields without the flag

    report = guard.compare(before, after, relocated=True)
    finding = _only(report["sentence_changes"], "limitation")
    line = _line_of(after, limitation)
    assert (finding["severity"], finding["removed"], finding["section"]) == ("warning", [word], "TeloKit > Conclusion")
    assert finding["relocated_to"] == [{"marker": word, "section": "TeloKit > Discussion > Limitations", "line": line,
                                        "file": None, "sentence": limitation}]
    assert finding["note"].startswith(f"It moved to the Discussion, Limitations (line {line})")
    assert guard.exit_code(report) == 0 and report["relocated"] is True and report["summary"]["relocated"] == 1
    assert guard.exit_code(guard.compare(before, after, relocated=True, revision=True)) == 0
    assert _only(guard.compare(before, after, relocated=True, revision=True)["sentence_changes"],
                 "limitation")["relocated_to"] == finding["relocated_to"]

    markdown = guard.to_markdown(report)
    assert (f"In the Conclusion (line {_line_of(after, conclusion_after)}), the limiting word “{word}” was dropped. "
            f"It moved to the Discussion, Limitations (line {line})") in markdown
    assert f"  - Where it is now: “{limitation.replace(word, f'**{word}**')}”" in markdown
    assert "One caveat moved from its sentence to another one" in markdown
    assert "Revert" not in markdown and "Revert this unless" in guard.to_markdown(without)

    files = {name: tmp_path / name for name in ("before.md", "after.md")}
    files["before.md"].write_text(before, encoding="utf-8")
    files["after.md"].write_text(after, encoding="utf-8")
    runner = CliRunner()
    assert runner.invoke(guard.app, [str(files["before.md"]), str(files["after.md"])]).exit_code == 1
    assert runner.invoke(guard.app, [str(files["before.md"]), str(files["after.md"]), "--relocated"]).exit_code == 0


SCOPE_BEFORE = "# TeloKit\n\n## Results\n\nIn this cohort, rs429358 was associated with shorter telomeres.\n"
SCOPE_AFTER = "# TeloKit\n\n## Results\n\nrs429358 was associated with shorter telomeres.\n"
SCOPE_SUPPLEMENT = ("# Supplementary material\n\n## S3 Cohort\n\nThe donors were recruited at three centres.\n\n"
                    "All association results come from this cohort of older adults.\n")


def test_a_scope_qualifier_moved_to_the_supplement_names_the_file(tmp_path: Path) -> None:
    moved = [("supplementary.md", SCOPE_SUPPLEMENT)]
    assert _only(guard.compare(SCOPE_BEFORE, SCOPE_AFTER, moved=moved)["sentence_changes"], "scope")["severity"] == \
        "protected"
    report = guard.compare(SCOPE_BEFORE, SCOPE_AFTER, moved=moved, relocated=True)
    finding = _only(report["sentence_changes"], "scope")
    destination = "All association results come from this cohort of older adults."
    assert (finding["severity"], finding["removed"]) == ("warning", ["In this cohort"])
    assert finding["relocated_to"] == [{"marker": "from this cohort", "section": "Supplementary material > S3 Cohort",
                                        "line": _line_of(SCOPE_SUPPLEMENT, destination), "file": "supplementary.md",
                                        "sentence": destination}]
    assert (f"It moved to supplementary.md, in the S3 Cohort (line {_line_of(SCOPE_SUPPLEMENT, destination)})"
            in guard.to_markdown(report))
    assert guard.exit_code(report) == 0

    paths = {name: tmp_path / name for name in ("before.md", "after.md", "supplementary.md")}
    for path, text in zip(paths.values(), (SCOPE_BEFORE, SCOPE_AFTER, SCOPE_SUPPLEMENT)):
        path.write_text(text, encoding="utf-8")
    args = [str(paths["before.md"]), str(paths["after.md"]), "--moved-to", str(paths["supplementary.md"])]
    runner = CliRunner()
    assert runner.invoke(guard.app, args).exit_code == 1
    out = tmp_path / "r.json"
    assert runner.invoke(guard.app, [*args, "--relocated", "--json", str(out)]).exit_code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [c["relocated_to"][0]["file"] for c in data["sentence_changes"] if c["relocated_to"]] == ["supplementary.md"]


def test_each_new_marker_accounts_for_one_lost_marker() -> None:
    # one sentence loses two "only"s and one comes back elsewhere: the sentence still lost one
    report = guard.compare(
        _paper("The annotation was tested on only four genomes and only one laptop, and was faster than the "
               "Generation I system."),
        _paper("The annotation was tested on four genomes and one laptop, and was faster than the Generation I "
               "system.", "The benchmark covered only four genomes. "), relocated=True)
    finding = _only(report["sentence_changes"], "limitation")
    assert (finding["severity"], finding["removed"]) == ("protected", ["only", "only"])
    assert [spot["marker"] for spot in finding["relocated_to"]] == ["only"]
    assert finding["note"].endswith("but no other new or changed sentence holds the remaining “only”.")
    assert guard.exit_code(report) == 1
    # two sentences lose one "only" each and one comes back elsewhere: one of them is still a lost caveat
    report = guard.compare(
        _paper("Annotation was tested on only four genomes. It was faster than the Generation I system on the same "
               "laptop. Scoring used only one genome."),
        _paper("Annotation was tested on four genomes. It was faster than the Generation I system on the same laptop. "
               "Scoring used one genome.", "The benchmark covered only four genomes and one scoring genome. "),
        relocated=True)
    limits = [c for c in report["sentence_changes"] if c["kind"] == "limitation"]
    assert sorted((c["severity"], bool(c["relocated_to"])) for c in limits) == [("protected", False), ("warning", True)]
    assert guard.exit_code(report) == 1


CONCESSION = ("Despite the small benchmark of four genomes, annotation was faster than in the Generation I system.",
              "Annotation was faster than in the Generation I system.")


@pytest.mark.parametrize("limitation", [
    "",  # dropped, and no sentence took it
    "The benchmark was small, with four genomes. ",  # moved, but reworded so that "despite" went
])
def test_a_caveat_with_no_sentence_holding_its_marker_stays_protected(limitation: str) -> None:
    report = guard.compare(_paper(CONCESSION[0]), _paper(CONCESSION[1], limitation), relocated=True)
    finding = _only(report["sentence_changes"], "limitation")
    assert (finding["severity"], finding["relocated_to"]) == ("protected", None)
    assert guard.exit_code(report) == 1


def test_a_lost_number_stays_protected_when_its_caveat_moved() -> None:
    before = _paper("Albeit tested on 4 genomes, the annotation was faster than the Generation I system.")
    after = _paper("The annotation was faster than the Generation I system.",
                   "The speed comparison holds, albeit on 4 genomes. ")
    report = guard.compare(before, after, relocated=True)
    assert _only(report["sentence_changes"], "limitation")["severity"] == "warning"
    numbers = [c for c in report["sentence_changes"] if c["kind"] == "number"]
    assert {(c["token"], c["change"], c["severity"], c["relocated_to"]) for c in numbers} == {
        ("4", "removed", "protected", None), ("4", "added", "protected", None)}
    assert guard.exit_code(report) == 1


ONLY = ("The annotation was tested on only four genomes and was faster than the Generation I system.",
        "The annotation was tested on four genomes and was faster than the Generation I system.")


@pytest.mark.parametrize("kept_before, kept_after", [
    ("Scoring used only one genome.", "Scoring used only one genome."),  # unchanged
    ("Scoring used only one genome.", "Scoring was run on only one genome."),  # changed, but its "only" was there
    ("Scoring used only one genome.", "Scoring used only one genome, albeit a deep one."),  # what it gained is not "only"
])
def test_a_marker_a_sentence_already_had_does_not_absorb_a_lost_one(kept_before: str, kept_after: str) -> None:
    report = guard.compare(_paper(ONLY[0], kept=kept_before), _paper(ONLY[1], kept=kept_after), relocated=True)
    lost = [c for c in report["sentence_changes"] if c["kind"] == "limitation" and c["change"] == "removed"]
    assert [(c["removed"], c["severity"], c["relocated_to"]) for c in lost] == [(["only"], "protected", None)]
    assert guard.exit_code(report) == 1


def test_two_sentences_that_swap_qualifiers_are_not_relocations() -> None:
    """Each sentence gained the other's qualifier, but lost one of the same kind, so neither is a destination."""
    before = ("# Results\n\nTERT knockdown shortened telomeres in mice over two generations.\n\n"
              "The inhibitor bound TERT in vitro at nanomolar doses.\n")
    after = before.replace("in mice", "IN_VITRO").replace("in vitro", "in mice").replace("IN_VITRO", "in vitro")
    report = guard.compare(before, after, relocated=True)
    scopes = [c for c in report["sentence_changes"] if c["kind"] == "scope"]
    assert [(c["change"], c["severity"], c["relocated_to"]) for c in scopes] == [
        ("replaced", "protected", None), ("replaced", "protected", None)]


# --- skill files and eval cases -----------------------------------------------------------------------------------

SKILL = ROOT / "skills" / "manuscript-prose-edit"


def _slug(heading: str) -> str:
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


@pytest.mark.parametrize("skill", ["manuscript-prose-edit", "manuscript-deslop", "manuscript-visualize"])
def test_relative_links_in_the_skill_resolve_with_their_anchors(skill: str) -> None:
    for md in (ROOT / "skills" / skill).rglob("*.md"):
        for target in re.findall(r"\]\(([^)\s]+)\)", md.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path, _, anchor = target.partition("#")
            dest = (md.parent / path).resolve() if path else md
            assert dest.exists(), f"{md.relative_to(ROOT)} links to missing {target}"
            if anchor and dest.suffix == ".md":
                headings = re.findall(r"^#+\s+(.*)$", dest.read_text(encoding="utf-8"), re.M)
                assert anchor in {_slug(h) for h in headings}, f"{md.relative_to(ROOT)}: no #{anchor} in {path}"


@pytest.mark.parametrize("skill", ["manuscript-prose-edit", "manuscript-deslop", "manuscript-visualize", "manuscript-improve"])
def test_eval_cases_are_complete_and_their_files_exist(skill: str) -> None:
    cases = yaml.safe_load((ROOT / "evals" / f"{skill}.yaml").read_text(encoding="utf-8"))
    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        assert case["skill"] == skill and case["prompt"].strip(), case["id"]
        assert case["rubric"] and case["fail_if"] and case["planted"], case["id"]
        for name in case["files"]:
            assert (ROOT / "evals" / name).is_file(), (case["id"], name)
