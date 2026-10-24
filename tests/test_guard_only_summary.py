"""guard.py --only (an edit stays inside the sections it was asked for) and --summary (the title, Abstract and
Conclusions claim no more than the body): ideas 8 and 6 of the 2026-10-24 comparison with academic-research-skills."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard = _load("guard_only_summary", ROOT / "skills" / "manuscript-prose-edit" / "scripts" / "guard.py")

PAPER = """# Loss of Foo and tumour growth

## Abstract

Loss of Foo reduces tumour growth by 40%. Survival did not differ between the groups.

## Introduction

Earlier studies showed that Foo regulates growth in yeast.

## 2. Methods

Mice were genotyped at weaning.

## Results

### Growth

In mice, loss of Foo was associated with a 40% reduction in tumour growth.

### Survival

Survival did not differ between the groups (p = 0.41).

## Discussion

These results suggest that loss of Foo may slow tumour growth in mice.

### Limitations

The cohort was small.
"""


def _edit(old: str, new: str, text: str = PAPER) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


# --- --only ---------------------------------------------------------------------------------------------------

def test_an_edit_inside_the_requested_section_passes() -> None:
    after = _edit("The cohort was small.", "The cohort was small, so the estimate is imprecise.")
    report = guard.compare(PAPER, after, only=["Discussion"])
    assert report["only"] == {"sections": ["Discussion"], "outside": []}  # Limitations sits under Discussion
    assert report["summary"]["outside_scope"] == 0 and guard.exit_code(report) == 0


@pytest.mark.parametrize("old, new, section", [
    ("Earlier studies showed", "Earlier work showed", "Introduction"),          # reworded
    ("Mice were genotyped at weaning.", "", "2. Methods"),                    # deleted
    ("The cohort was small.", "The cohort was small. Mice were genotyped at weaning.", "Limitations"),  # added
])
def test_a_sentence_changed_outside_the_requested_sections_fails(old: str, new: str, section: str) -> None:
    report = guard.compare(PAPER, _edit(old, new), only=["Results"])
    outside = report["only"]["outside"]
    assert outside and outside[0]["section"].endswith(section)
    assert guard.exit_code(report) == 1
    md = guard.to_markdown(report)
    assert "## Changes outside the requested sections" in md and "restore" in md


def test_sections_match_by_heading_path_and_ignore_numbering() -> None:
    after = _edit("Mice were genotyped at weaning.", "Mice were genotyped at three weeks.")
    assert not guard.compare(PAPER, after, only=["Methods"])["only"]["outside"]  # "2. Methods"
    after = _edit("Survival did not differ between the groups (p = 0.41).",
                  "Survival did not differ between the two groups (p = 0.41).")
    assert not guard.compare(PAPER, after, only=["Results > Survival"])["only"]["outside"]
    assert guard.compare(PAPER, after, only=["Results > Growth"])["only"]["outside"]


def test_a_revision_inventory_fails_on_a_change_outside_the_sections_too() -> None:
    after = _edit("Earlier studies showed", "Earlier work showed")
    assert guard.exit_code(guard.compare(PAPER, after, revision=True, only=["Discussion"])) == 1
    assert guard.exit_code(guard.compare(PAPER, after, revision=True)) == 0


def test_without_only_the_report_is_unchanged() -> None:
    report = guard.compare(PAPER, _edit("Earlier studies showed", "Earlier work showed"))
    assert "only" not in report and "outside_scope" not in report["summary"]


def test_a_section_the_paper_does_not_have_is_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no section is named 'Conclusions'.*Abstract, Introduction"):
        guard.compare(PAPER, PAPER, only=["Conclusions"])
    before, after = tmp_path / "a.md", tmp_path / "b.md"
    before.write_text(PAPER, encoding="utf-8")
    after.write_text(PAPER, encoding="utf-8")
    assert CliRunner().invoke(guard.app, [str(before), str(after), "--only", "Conclusions"]).exit_code == 2


def test_the_cli_takes_only_more_than_once(tmp_path: Path) -> None:
    before, after = tmp_path / "a.md", tmp_path / "b.md"
    before.write_text(PAPER, encoding="utf-8")
    after.write_text(_edit("Earlier studies showed", "Earlier work showed"), encoding="utf-8")
    runner = CliRunner()
    assert runner.invoke(guard.app, [str(before), str(after), "--only", "Discussion"]).exit_code == 1
    assert runner.invoke(guard.app, [str(before), str(after), "--only", "Discussion",
                                     "--only", "Introduction"]).exit_code == 0


# --- --summary ------------------------------------------------------------------------------------------------

def _kinds(report: dict, part: str) -> set[tuple[str, str]]:
    return {(f["kind"], f["change"]) for f in report["findings"] if f["part"] == part}


def test_an_abstract_that_states_a_cause_and_drops_the_model_system_is_flagged() -> None:
    report = guard.summary_check(PAPER)
    assert ("causal", "raised") in _kinds(report, "abstract")
    assert not _kinds(report, "title")  # "Loss of Foo and tumour growth" names a topic and claims nothing
    (scope,) = [f for f in report["findings"] if f["kind"] == "scope"]
    assert scope["removed"] == ["In mice"] and scope["body_section"].endswith("Growth")
    md = guard.summary_markdown(report)
    assert "## Claims stronger than the body" in md and "It leaves out the scope the body states" in md


def test_a_summary_the_body_supports_passes() -> None:
    text = _edit("Loss of Foo reduces tumour growth by 40%.",
                 "In mice, loss of Foo was associated with a 40% reduction in tumour growth.")
    assert not _kinds(guard.summary_check(text), "abstract")


def test_a_scope_the_abstract_states_once_is_not_asked_again_in_every_sentence() -> None:
    text = _edit("Loss of Foo reduces tumour growth by 40%.",
                 "We studied Foo in mice. Loss of Foo was associated with a 40% reduction in tumour growth.")
    assert not [f for f in guard.summary_check(text)["findings"] if f["kind"] == "scope"]


def test_a_null_result_the_abstract_turns_into_a_difference_is_flagged() -> None:
    text = _edit("Survival did not differ between the groups.", "Survival differed between the groups.")
    assert ("null_result", "removed") in _kinds(guard.summary_check(text), "abstract")


def test_the_introduction_never_supports_a_summary_claim() -> None:
    text = _edit("Earlier studies showed that Foo regulates growth in yeast.",
                 "Loss of Foo reduces tumour growth by 40%.")
    assert ("causal", "raised") in _kinds(guard.summary_check(text), "abstract")


def test_conclusions_and_titles_are_summary_parts_too() -> None:
    text = PAPER.replace("# Loss of Foo and tumour growth", "# Loss of Foo causes smaller tumours") + \
        "\n### Conclusions\n\nFoo loss slows tumour growth.\n"
    report = guard.summary_check(text)
    assert ("causal", "raised") in _kinds(report, "title")
    assert _kinds(report, "conclusions")  # a Conclusions subsection of the Discussion


def test_a_front_matter_title_and_a_latex_abstract_are_read() -> None:
    md = "---\ntitle: \"Loss of Foo causes smaller tumours\"\n---\n" + PAPER.split("\n", 1)[1]
    assert "title" in {f["part"] for f in guard.summary_check(md)["findings"]}
    tex = ("\\documentclass{article}\n\\title{Loss of Foo causes smaller tumours}\n\\begin{document}\n"
           "\\begin{abstract}\nLoss of Foo reduces tumour growth by 40\\%.\n\\end{abstract}\n"
           "\\section{Results}\nIn mice, loss of Foo was associated with a 40\\% reduction in tumour growth.\n"
           "\\end{document}\n")
    assert {f["part"] for f in guard.summary_check(tex)["findings"]} == {"title", "abstract"}


def test_a_summary_sentence_no_body_sentence_is_close_to_is_listed_and_passes() -> None:
    text = _edit("Survival did not differ between the groups.",
                 "Survival did not differ between the groups. Software is available on request.")
    report = guard.summary_check(text)
    assert [u["sentence"] for u in report["unmatched"]] == ["Software is available on request."]


def test_summary_needs_headings_and_the_cli_checks_one_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="needs a title"):
        guard.summary_check("Just one paragraph with no headings at all.\n")
    paper = tmp_path / "paper.md"
    paper.write_text(PAPER, encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(guard.app, [str(paper), "--summary", "--json", str(tmp_path / "s.json")])
    assert result.exit_code == 1 and "Claims stronger than the body" in result.output
    assert json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))["mode"] == "summary"
    assert runner.invoke(guard.app, [str(paper), str(paper), "--summary"]).exit_code == 2


@pytest.mark.parametrize("name", ["seeded.md", "clean.md"])
def test_the_peer_review_fixtures_summaries_restate_their_bodies(name: str) -> None:
    """Neither fixture plants a summary that outruns its body; an Abstract's benchmark sentence is not the body's
    "VarRank scores only missense variants" (0.29 similar), so its "only" is not asked for."""
    text = (ROOT / "evals" / "fixtures" / "manuscript-peer-review" / name).read_text(encoding="utf-8")
    assert guard.summary_check(text)["findings"] == []
