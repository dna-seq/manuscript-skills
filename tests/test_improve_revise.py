"""The corrected version: applied edits verified against the original, every proposal placed or listed with its reason."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


viz = load("dashboard", ROOT / "skills/manuscript-dashboard/scripts/dashboard.py")
revise = load("revise", ROOT / "skills/manuscript-improve/scripts/revise.py")

ORIGINAL = """# A tool

## 1. Introduction

Genomes are cheap. This tool plays a crucial role in annotation. We use HuggingFace for data.

## 2. Methods

The pipeline joins by rsID. It is fast.
"""
WORKING = ORIGINAL.replace("HuggingFace", "Hugging Face")
PROPOSED = """# A tool

## 1. Introduction

Genomes are cheap. This tool annotates variants. We use Hugging Face Hub for data.

## 2. Methods

The pipeline joins by position and genotype. It is fast.

## 3. Data availability

Data are on Zenodo.
"""


def change(cid: str, status: str, before: str | None, after: str | None, **extra) -> dict:
    return {"id": cid, "kind": "Proposed edit", "section": "1. Introduction", "summary": f"Edit {cid}", "status": status,
            "before": before, "after": after, "evidence": [{"path": "review.md", "quote": "The review."}], **extra}


def inventory() -> dict:
    return {
        "schema_version": 2, "title": "Review", "run_id": "run", "scope": "Whole paper.",
        "coverage": [{"skill": "manuscript-improve", "status": "completed", "note": "All stages.",
                      "evidence": [{"path": "review.md", "quote": "The review."}]}],
        "findings": [],
        "manuscript": {"title": "A tool", "version": "v1", "path": "original.md", "sections": ["1. Introduction", "2. Methods"]},
        "changes": [
            change("PE.C1", "applied", "Genomes are cheap. This tool plays a crucial role in annotation. We use HuggingFace for data.",
                   "Genomes are cheap. This tool plays a crucial role in annotation. We use Hugging Face for data."),
            change("ST-C1", "proposed", "This tool plays a crucial role in annotation.", "This tool annotates variants."),
            change("DS-C1", "proposed", "This tool plays a crucial role in annotation.", "The tool annotates."),
            change("IC-C1", "proposed", "The pipeline joins by rsID.", "The pipeline joins by position and genotype."),
            change("JA-C1", "proposed", None, "## 3. Data availability\n\nData are on Zenodo.", anchor="It is fast."),
            change("ST-C2", "proposed", "Genomes are cheap.", "Sequencing costs fell."),
            change("RF-C1", "proposed", "A sentence the paper never had.", "Anything."),
            change("PE-C2", "proposed", "Hugging Face", "Hugging Face Hub"),
        ],
    }


CHOICES = {"prefer": ["ST-C1"], "hold": [{"id": "ST-C2", "why": "Waits for the authors' decision on the opening."}]}


def test_applied_edits_then_every_chosen_proposal_give_the_corrected_version() -> None:
    data = viz.Inventory.model_validate(inventory())
    document, record = revise.build(ORIGINAL, WORKING, data, CHOICES)
    assert document.current() == PROPOSED
    assert document.previous() == ORIGINAL
    assert record["applied"] == ["PE.C1"]
    assert sorted(record["proposed_in_this_version"]) == ["IC-C1", "JA-C1", "PE-C2", "ST-C1"]
    assert record["held"] == [{"id": "ST-C2", "why": "Waits for the authors' decision on the opening."}]
    assert record["alternatives"] == [{"id": "DS-C1", "chosen": "ST-C1"}]
    assert record["not_placed"] == [{"id": "RF-C1", "why": "its passage is not in the working copy"}]


def test_an_edit_nobody_recorded_stops_the_build() -> None:
    data = viz.Inventory.model_validate(inventory())
    with pytest.raises(ValueError, match="outside the recorded applied edits"):
        revise.build(ORIGINAL, WORKING.replace("It is fast.", "It is very fast."), data, CHOICES)


def test_competing_proposals_need_a_choice_and_names_must_be_proposals() -> None:
    data = viz.Inventory.model_validate(inventory())
    with pytest.raises(ValueError, match="ST-C1, DS-C1"):
        revise.build(ORIGINAL, WORKING, data, {})
    with pytest.raises(ValueError, match="not proposals"):
        revise.build(ORIGINAL, WORKING, data, {**CHOICES, "hold": [{"id": "PE.C1", "why": "applied"}]})


def test_an_addition_without_an_anchor_is_listed_and_a_supplied_anchor_places_it() -> None:
    raw = inventory()
    raw["changes"][4].pop("anchor")
    data = viz.Inventory.model_validate(raw)
    _, record = revise.build(ORIGINAL, WORKING, data, CHOICES)
    assert {"id": "JA-C1", "why": "an addition that names no anchor passage"} in record["not_placed"]
    document, _ = revise.build(ORIGINAL, WORKING, data, {**CHOICES, "anchor": [{"id": "JA-C1", "after": "It is fast."}]})
    assert document.current() == PROPOSED


def test_a_proposal_around_an_applied_edit_takes_it_in_and_one_across_another_proposal_is_not_placed() -> None:
    raw = inventory()
    raw["changes"][7] = change("PE-C2", "proposed", "We use Hugging Face for data.", "Data come from Hugging Face.")
    raw["changes"] = [c for c in raw["changes"] if c["id"] not in ("ST-C1", "DS-C1")]
    document, record = revise.build(ORIGINAL, WORKING, viz.Inventory.model_validate(raw), {"hold": CHOICES["hold"]})
    assert "Data come from Hugging Face." in document.current() and document.previous() == ORIGINAL
    assert "PE-C2" in record["proposed_in_this_version"] and "PE.C1" in record["applied"]
    raw["changes"].append(change("DS-C9", "proposed", "annotation. We use", "annotation; we use"))
    _, record = revise.build(ORIGINAL, WORKING, viz.Inventory.model_validate(raw), {"hold": CHOICES["hold"]})
    assert {"id": "PE-C2", "why": "it overlaps DS-C9"} in record["not_placed"]  # the earlier passage is placed first


def test_track_changes_keep_headings_tables_and_links_intact() -> None:
    original = "# T\n\n| Tool | Mode |\n|---|---|\n| A (GVCF) | x |\n\nSee [the site](https://a.org/x) now.\n"
    raw = inventory()
    raw["changes"] = [change("A1", "proposed", "| A (GVCF) | x |", "| A (gVCF) | x |"),
                      change("A2", "proposed", "https://a.org/x", "https://b.org/y"),
                      change("A3", "proposed", None, "## New section\n\nText.", anchor="now.")]
    document, record = revise.build(original, original, viz.Inventory.model_validate(raw), {})
    body, edits = revise.track_changes(document, ".md")
    assert len(edits) == 3 and not re.search("[\\ue000-\\ue005]", body)
    assert body.count("<ins") == body.count("</ins>") and body.count("<del") == body.count("</del>")
    assert '<h2><ins class="proposed"' in body
    assert "<td>A (<del" in body and 'href="https://b.org/y"' in body


@pytest.fixture()
def run(tmp_path: Path) -> Path:
    (tmp_path / "review.md").write_text("The review.\n" + ORIGINAL + WORKING)
    (tmp_path / "original.md").write_text(ORIGINAL)
    (tmp_path / "working.md").write_text(WORKING)
    (tmp_path / "findings.json").write_text(json.dumps(inventory()))
    (tmp_path / "choices.json").write_text(json.dumps(CHOICES))
    return tmp_path


def test_the_command_writes_the_corrected_version_and_keeps_earlier_attempts(run: Path) -> None:
    args = [str(run / "original.md"), str(run / "working.md"), str(run / "findings.json"),
            "--choices", str(run / "choices.json"), "--output-dir", str(run / "revision")]
    result = CliRunner().invoke(revise.app, args)
    assert result.exit_code == 0, result.output
    assert (run / "revision/proposed.md").read_text() == PROPOSED
    assert (run / "revision/revised.md").read_text() == WORKING
    assert "{~~plays a crucial role in annotation~>annotates variants~~}{>>ST-C1<<}" in (run / "revision/changes.md").read_text()
    record = json.loads((run / "revision/revision.json").read_text())
    assert record["proposed_sha256"] == revise.digest(PROPOSED) and "<ins" in record["body_html"]
    assert CliRunner().invoke(revise.app, args).exit_code != 0


def test_the_dashboard_shows_the_corrected_version_and_counts_patterns_in_each_version(run: Path) -> None:
    CliRunner().invoke(revise.app, [str(run / "original.md"), str(run / "working.md"), str(run / "findings.json"),
                                    "--choices", str(run / "choices.json"), "--output-dir", str(run / "revision")])
    summary = viz.render(run / "findings.json", run / "dashboard", revision=run / "revision")
    assert summary["revision"]["proposed_in_this_version"] == 4 and summary["revision"]["not_placed"] == 1
    patterns = summary["writing_patterns"]
    assert patterns["original"]["by_pattern"].get("A1") == 1 and "A1" not in patterns["proposed"]["by_pattern"]
    page = (run / "dashboard/manuscript-dashboard.html").read_text()
    assert "__REVISION_HTML__" not in page and '<ins class="proposed"' in page
    assert sorted(p.name for p in (run / "dashboard").iterdir()) == ["manuscript-dashboard.html", "summary.json"]


def test_a_corrected_version_from_another_inventory_is_refused(run: Path) -> None:
    CliRunner().invoke(revise.app, [str(run / "original.md"), str(run / "working.md"), str(run / "findings.json"),
                                    "--choices", str(run / "choices.json"), "--output-dir", str(run / "revision")])
    (run / "findings.json").write_text(json.dumps({**inventory(), "title": "Changed after the revision"}))
    with pytest.raises(ValueError, match="another inventory"):
        viz.render(run / "findings.json", run / "dashboard", revision=run / "revision")


@pytest.mark.parametrize("second", [("which serves as the source", "which is the source"),
                                    ("Hugging Face, which serves", "HF, which is")])
def test_an_applied_edit_a_later_stage_changed_again_is_still_found(second: tuple[str, str]) -> None:
    original = "# T\n\nWe use HuggingFace, which serves as the source.\n"
    first = original.replace("HuggingFace", "Hugging Face")
    working = first.replace(*second)
    raw = inventory()
    raw["changes"] = [change("PE.C1", "applied", "We use HuggingFace, which serves as the source.",
                             "We use Hugging Face, which serves as the source."),
                      change("DS.C1", "applied", first.splitlines()[2], working.splitlines()[2])]
    document, record = revise.build(original, working, viz.Inventory.model_validate(raw), {})
    assert document.previous() == original and document.current() == working
    assert sorted(record["applied"]) == ["DS.C1", "PE.C1"] and not record["not_placed"]


def test_collect_counts_an_applied_edit_that_a_later_stage_changed_again(tmp_path: Path) -> None:
    collect = load("collect", ROOT / "skills/manuscript-dashboard/scripts/collect.py")
    original = "# T\n\nWe use HuggingFace, which serves as the source.\n"
    working = "# T\n\nWe use Hugging Face, which is the source.\n"
    for skill, number, before, after in (("manuscript-prose-edit", 1, original.splitlines()[2], "We use Hugging Face, which serves as the source."),
                                         ("manuscript-deslop", 1, "We use Hugging Face, which serves as the source.", working.splitlines()[2])):
        path = tmp_path / skill / "changes" / f"{number:04d}.md"
        path.parent.mkdir(parents=True)
        path.write_text(f"# Intro\n\nReason: why\n\n## Before\n\n{before}\n\n## After\n\n{after}\n")
    data = {"skills": {s: {"changes": [{"path": f"{s}/changes/0001.md"}]} for s in ("manuscript-prose-edit", "manuscript-deslop")}}
    records = collect.recorded_changes(tmp_path, data, tmp_path, working, original)
    assert [r["status"] for r in records] == ["applied", "applied"]


def test_a_held_proposal_joins_no_group_and_two_compatible_choices_both_apply() -> None:
    raw = inventory()
    raw["changes"].append(change("JA-C9", "proposed", "Genomes are cheap. This tool plays a crucial role in annotation.",
                                 "**Background:** Genomes are cheap. This tool plays a crucial role in annotation."))
    held = {"hold": [*CHOICES["hold"], {"id": "JA-C9", "why": "Genes only"}], "prefer": ["ST-C1"]}
    _, record = revise.build(ORIGINAL, WORKING, viz.Inventory.model_validate(raw), held)
    assert record["alternatives"] == [{"id": "DS-C1", "chosen": "ST-C1"}]
    raw["changes"][2] = change("DS-C1", "proposed", "This tool plays a crucial role in annotation.", "This tool plays a role in annotation.")
    raw["changes"].append(change("PE-C9", "proposed", "This tool plays a crucial role in annotation.", "That tool plays a crucial role in annotation."))
    _, record = revise.build(ORIGINAL, WORKING, viz.Inventory.model_validate(raw), {**held, "prefer": ["DS-C1", "PE-C9"]})
    assert {"DS-C1", "PE-C9"} <= set(record["proposed_in_this_version"]) and {"id": "ST-C1", "chosen": "DS-C1, PE-C9"} in record["alternatives"]


def test_additions_to_a_reference_list_go_on_their_own_lines_and_keep_their_order() -> None:
    original = "# T\n\nText.\n\n## References\n\nAdams, A. (2020). One.\nCole, C. (2021). Three.\n\n## End\n"
    raw = inventory()
    raw["changes"] = [change("RF-C1", "proposed", None, "Baker, B. (2019). Two.", anchor="Adams, A. (2020). One."),
                      change("JA-C1", "proposed", None, "## Ethics\n\nNone.", anchor="Text."),
                      change("JA-C2", "proposed", None, "## Consent\n\nGiven.", anchor="Text.")]
    document, record = revise.build(original, original, viz.Inventory.model_validate(raw), {})
    assert document.current() == ("# T\n\nText.\n\n## Ethics\n\nNone.\n\n## Consent\n\nGiven.\n\n## References\n\n"
                                  "Adams, A. (2020). One.\nBaker, B. (2019). Two.\nCole, C. (2021). Three.\n\n## End\n")
    assert not record["not_placed"]
