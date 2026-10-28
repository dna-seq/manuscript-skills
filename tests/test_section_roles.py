"""The section-roles check (manuscript-integrity-check/scripts/section_roles.py) and its place in manuscript-improve's
re-check. Ground truth is Paper 1 of Just-DNA-Lite before and after the authors moved each detail to its section
(just-dna-lite commit bc27fe5, 28 October 2026): the eval case's seeded and clean fixtures.

Run with `uv run pytest tests/test_section_roles.py -vvv`.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evals" / "fixtures" / "manuscript-integrity-check"
SEEDED = FIXTURES / "section-roles-seeded.md"
CLEAN = FIXTURES / "section-roles-clean.md"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


roles = _load("section_roles", ROOT / "skills" / "manuscript-integrity-check" / "scripts" / "section_roles.py")
recheck = _load("recheck_for_roles", ROOT / "skills" / "manuscript-improve" / "scripts" / "recheck.py")
CASES = {c["id"]: c for c in yaml.safe_load((ROOT / "evals" / "manuscript-integrity-check.yaml").read_text(encoding="utf-8"))}


def _check(path: Path) -> list:
    return roles.check(path.read_text(encoding="utf-8"), str(path)).candidates


def _fold(text: str) -> str:
    return " ".join(re.sub(r"[*_`]", "", text).split()).lower()


# Each passage the authors moved, with the direction the check must give it.
MOVED = [
    ("passes its reference-distribution audit", "methods-detail-early", "abstract"),
    ("mirrors the PGS Catalog's harmonized scoring files as Parquet", "methods-detail-early", "introduction"),
    ("860 scores were withheld, 847 of them", "results-detail-early", "introduction"),
    ("On 26 October 2026 the registry held 24 modules", "results-detail-early", "introduction"),
    ("in 33 to 65 s, 128 to 231 times faster", "results-detail-early", "introduction"),
    ("computes a polygenic score in a median of 0.08 s", "results-detail-early", "introduction"),
    ("PLINK2 was started once per score on four threads", "results-detail-early", "introduction"),
    ("placed 6,910 of 6,991 files", "results-in-methods", "methods"),
    ("6,117 of 6,977 scores passed and 860 were withheld", "results-in-methods", "methods"),
    ("For 847 of them, at least four of seven", "results-in-methods", "methods"),
    ("99.65% were assigned their own superpopulation", "results-in-methods", "methods"),
]


@pytest.mark.parametrize(("passage", "direction", "kind"), MOVED)
def test_each_passage_the_authors_moved_is_listed_where_it_stood(passage: str, direction: str, kind: str) -> None:
    hits = [c for c in _check(SEEDED) if passage in c.quote]
    assert (direction, kind) in {(c.direction, c.section_kind) for c in hits}, (passage, hits)
    assert not [c for c in _check(CLEAN) if passage in c.quote]  # moved to its section, or rewritten as a rule


def test_the_repaired_paper_lists_nothing() -> None:
    assert _check(CLEAN) == []


def test_every_candidate_of_the_seeded_paper_is_a_passage_the_authors_moved() -> None:
    listed = _check(SEEDED)
    assert {c.direction for c in listed} == {d for _, d, _ in MOVED}
    for c in listed:
        assert any(passage in c.quote for passage, _, _ in MOVED), c.quote


def test_quotes_are_verbatim_and_lines_point_at_them() -> None:
    lines = SEEDED.read_text(encoding="utf-8").splitlines()
    for c in _check(SEEDED):
        assert c.quote in lines[c.line - 1], (c.line, c.quote)


def test_the_eval_case_plants_what_the_check_lists() -> None:
    """The behavioural case and the check agree: each anchored passage in the seeded file is a candidate."""
    case = CASES["integrity-section-roles-seeded"]
    quotes = [c.quote for c in _check(SEEDED)]
    for anchor in case["anchors"]:
        if anchor["file"].endswith("section-roles-seeded.md") and not anchor.get("in_clean"):
            assert any(_fold(anchor["anchor"]) in _fold(q) for q in quotes), anchor["id"]


def test_an_edit_that_brings_detail_forward_is_caught_and_its_repair_is_not() -> None:
    forward = roles.compare(_check_report(CLEAN), _check_report(SEEDED))
    assert {c.direction for c in forward["introduced"]} == {d for _, d, _ in MOVED}
    assert forward["resolved"] == []
    # the accuracy sentence is word for word the same in Results (clean) and in Methods (seeded): moving it counts
    assert any("99.65%" in c.quote for c in forward["introduced"])
    back = roles.compare(_check_report(SEEDED), _check_report(CLEAN))
    assert back["introduced"] == [] and len(back["resolved"]) == len(_check(SEEDED))


def _check_report(path: Path):
    return roles.check(path.read_text(encoding="utf-8"), str(path))


def test_the_command_line_exits_1_only_when_an_edit_introduced_a_candidate(tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "roles.json"
    forward = runner.invoke(roles.app, [str(SEEDED), "--before", str(CLEAN), "--json", str(out)])
    assert forward.exit_code == 1, forward.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["introduced"]) == len(data["candidates"]) == len(MOVED) + 1  # one sentence is listed both ways
    assert runner.invoke(roles.app, [str(CLEAN), "--before", str(SEEDED)]).exit_code == 0
    assert runner.invoke(roles.app, [str(SEEDED)]).exit_code == 0  # one version: candidates are for reading
    assert runner.invoke(roles.app, [str(tmp_path / "missing.md")]).exit_code == 2


PAPER = """# A Tool

## Abstract

{abstract}

## 1. Introduction

{introduction}

## 2. Methods

{methods}

## 3. Results

{results}

## 4. Discussion

{discussion}

## References

Smith, A. (2020). A paper. Journal 1, 1-2.
"""


def _paper(**parts: str) -> str:
    base = {"abstract": "We built a tool that reads a genome locally.", "introduction": "Genomes are hard to read.",
            "methods": "We wrote the tool in Python.", "results": "The tool read 4,661,444 records in 33.2 s.",
            "discussion": "The tool is fast."}
    return PAPER.format(**(base | parts))


def _directions(text: str) -> list[str]:
    return [c.direction for c in roles.check(text).candidates]


@pytest.mark.parametrize("sentence", [
    "A score is withheld when at least four of the seven genomes fall in the outermost 1% of the distribution.",
    "A file is approximated when 10% or more of its absolute weight is on rows that cannot be matched.",
    "Its training data are the panel's 2,575 unrelated individuals, after related ones were removed.",
    "We scored the PGS Catalog release of 17 September 2026.",
    "Each score carries a quality label, High when the AUROC is at least 0.7.",
])
def test_rules_input_sizes_and_data_versions_are_procedure_not_results(sentence: str) -> None:
    assert _directions(_paper(methods=sentence)) == []


def test_the_abstract_keeps_its_main_results_and_their_setup() -> None:
    assert _directions(_paper(abstract="It annotates a 30x genome in a median of 31.4 seconds on a laptop with "
                                       "8 cores.")) == []
    assert _directions(_paper(abstract="Annotation takes 38.9 s per genome, and agreement is 99.4%.")) == []
    assert _directions(_paper(abstract="It ran in 33 to 65 s, 128 to 231 times faster, and reruns took 16 to "
                                       "20 s.")) == ["results-detail-early"]
    assert _directions(_paper(abstract="Of 6,977 scores, 860 were withheld before release.")) == [
        "results-detail-early"]
    assert _directions(_paper(abstract="Scores are normalized and stored as Parquet.")) == ["methods-detail-early"]


def test_the_introduction_keeps_rounded_figures_pointers_and_cited_background() -> None:
    rounded = ("The ten default modules annotate a whole genome in about a minute, more than a hundred times faster "
               "than the earlier workflow, for 6,117 scores across 778 traits (Section 3).")
    cited = "The heritability of lifespan has been estimated at 20–25% in twin studies (Shenhar et al., 2026)."
    assert _directions(_paper(introduction=rounded + " " + cited)) == []
    assert _directions(_paper(introduction="It annotates a genome in a median of 33.2 s.")) == ["results-detail-early"]


def test_procedure_in_results_is_a_numberless_paragraph_of_steps() -> None:
    steps = ("Variant identifiers are normalized before the join. Scores are filtered when fewer than half of their "
             "variants match.")
    assert _directions(_paper(results=steps)) == ["procedure-in-results"]
    assert _directions(_paper(results=steps + " This kept 6,117 scores.")) == []  # an outcome beside its steps


def test_a_number_first_stated_in_the_discussion_is_listed_unless_it_is_a_plan() -> None:
    assert _directions(_paper(discussion="Across all runs the median was 41.7 s.")) == ["result-only-late"]
    assert _directions(_paper(discussion="Reading 4,661,444 records in 33.2 s makes it practical.")) == []
    assert _directions(_paper(discussion="A cohort of 5,000 individuals is planned.")) == []


def test_software_paper_headings_get_their_roles_and_subsections_inherit_them() -> None:
    text = ("# T\n\n## Abstract\n\nA tool.\n\n## 1. Introduction\n\n### 1.2 Overview\n\nIt reads genomes.\n\n"
            "## 2. System and Methods: Architecture\n\n### 2.1 Pipeline\n\nIt reads VCF files.\n\n"
            "## 3. Algorithm and Implementation\n\n### 3.1 Longevity module (example)\n\nA module.\n\n"
            "## 4. Use cases\n\nOne genome.\n\n## 5. Benchmarking and Validation\n\n### 5.1 Speed\n\nFast.\n")
    assert [(s["heading"], s["kind"]) for s in roles.check(text).sections][1:] == [
        ("Abstract", "abstract"), ("1. Introduction", "introduction"), ("1.2 Overview", "introduction"),
        ("2. System and Methods: Architecture", "methods"), ("2.1 Pipeline", "methods"),
        ("3. Algorithm and Implementation", "methods"), ("3.1 Longevity module (example)", "methods"),
        ("4. Use cases", "results"), ("5. Benchmarking and Validation", "results"), ("5.1 Speed", "results")]


def test_feature_list_items_are_read_one_by_one_and_comments_keep_line_numbers() -> None:
    text = _paper(introduction="**Key features.**\n\n<!-- @rev F1 rounds=2 by=claude:2026-10-27 -->\n"
                               "- **Easy.** It installs in one step.\n- **Fast.** It reads a genome in 33 to 65 s.\n"
                               "<!-- @/rev F1 -->")
    found = roles.check(text).candidates
    assert [(c.direction, c.quote) for c in found] == [("results-detail-early", "**Fast.** It reads a genome in 33 to 65 s.")]
    assert text.splitlines()[found[0].line - 1].endswith(found[0].quote)


def test_latex_sections_and_items_are_read() -> None:
    tex = (r"\documentclass{article}\begin{document}\begin{abstract}A tool.\end{abstract}" "\n"
           r"\section{Introduction}" "\n" r"\begin{itemize}" "\n"
           r"\item It mirrors the catalogue as Parquet and normalizes build labels." "\n" r"\end{itemize}" "\n"
           r"\section{Methods}" "\n" r"In leave-one-out tests, 99.65\% were assigned correctly (2,566 of 2,575)." "\n"
           r"\end{document}")
    assert sorted(_directions(tex)) == ["methods-detail-early", "results-in-methods"]


def test_the_recheck_counts_detail_an_edit_brought_forward(tmp_path: Path) -> None:
    before, after = tmp_path / "a.md", tmp_path / "b.md"
    before.write_text(CLEAN.read_text(encoding="utf-8"), encoding="utf-8")
    after.write_text(SEEDED.read_text(encoding="utf-8"), encoding="utf-8")
    compared = recheck.compare_candidates(recheck._candidates(before, False), recheck._candidates(after, False))
    introduced = compared["placement"]["introduced"]
    assert {c["check"] for c in introduced} == {d for _, d, _ in MOVED}
    assert all("belongs in" in c["message"] for c in introduced)
    undone = recheck.compare_candidates(recheck._candidates(after, False), recheck._candidates(before, False))
    assert undone["placement"]["introduced"] == [] and len(undone["placement"]["resolved"]) == len(introduced)
