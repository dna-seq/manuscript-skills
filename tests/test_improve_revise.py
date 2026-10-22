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


def test_notes_to_the_authors_become_comments_and_never_reach_the_text(tmp_path: Path) -> None:
    """A question for the authors is a comment: a [AUTHORS: ...] note a stage left in a proposal is lifted out of
    its text, and a proposal that is only a question is listed, not placed."""
    data = inventory()
    data["changes"] = [
        change("PE.C1", "applied", "We use HuggingFace for data.", "We use Hugging Face for data."),
        change("JA-C4", "proposed", "Rostock, Germany", "[AUTHORS: postal code] Rostock, Germany, [AUTHORS: city]"),
        change("IC-C1", "proposed", "The pipeline joins by rsID.", "The pipeline joins by position and genotype.",
               comment="Which genome build do the positions use?"),
        change("ST-C3", "proposed", "It is fast.", "It is fast. [AUTHORS: confirm that this is planned]"),
        change("JA-C9", "proposed", None, "[AUTHORS: tool, version and model]", anchor="It is fast."),
    ]
    original = ORIGINAL.replace("Genomes are cheap.", "Genomes are cheap. Rostock, Germany.")
    working = original.replace("HuggingFace", "Hugging Face")
    document, record = revise.build(original, working, viz.Inventory.model_validate(data), {})
    proposed = document.current()
    assert "AUTHORS" not in proposed and "[" not in proposed.split("# A tool")[1]
    assert "Rostock, Germany." in proposed and "position and genotype" in proposed
    asked = {(c["ids"][0], c["question"], c["placed"]) for c in record["comments"]}
    assert asked == {("JA-C4", "postal code", False), ("JA-C4", "city", False),
                     ("IC-C1", "Which genome build do the positions use?", True),
                     ("ST-C3", "confirm that this is planned", False), ("JA-C9", "tool, version and model", False)}
    not_placed = {x["id"]: x["why"] for x in record["not_placed"]}
    assert set(not_placed) == {"JA-C4", "ST-C3", "JA-C9"} and all("only asks them" in why for why in not_placed.values())
    assert record["notes_in_text"] == []
    assert "{>>IC-C1 · Question for the authors: Which genome build do the positions use?<<}" in revise.critic(
        document, {"IC-C1": ["Which genome build do the positions use?"]})


def test_a_note_an_applied_edit_left_leaves_the_corrected_version_as_a_comment() -> None:
    data = inventory()
    data["changes"] = [change("PE.C1", "applied", "We use HuggingFace for data.",
                              "We use Hugging Face [AUTHORS: which version?] for data.")]
    working = ORIGINAL.replace("We use HuggingFace for data.", "We use Hugging Face [AUTHORS: which version?] for data.")
    document, record = revise.build(ORIGINAL, working, viz.Inventory.model_validate(data), {})
    assert "[AUTHORS" not in document.current() and "We use Hugging Face for data." in document.current()
    assert {"ids": ["PE.C1"], "question": "which version?"}.items() <= next(c for c in record["comments"] if c["ids"] == ["PE.C1"]).items()
    assert record["notes_in_text"] == [] and [n["line"] for n in record["notes_in_working_copy"]] == [5]


def test_a_note_in_the_authors_own_draft_is_listed_not_removed() -> None:
    original = ORIGINAL.replace("It is fast.", "It is fast. [AUTHORS: add the timing table]")
    document, record = revise.build(original, original, viz.Inventory.model_validate({**inventory(), "changes": []}), {})
    assert "[AUTHORS: add the timing table]" in document.current()
    assert [n["note"] for n in record["notes_in_text"]] == ["[AUTHORS: add the timing table]"]


@pytest.mark.parametrize("deleted, working", [
    ("This tool plays a crucial role in annotation.", ORIGINAL.replace(" This tool plays a crucial role in annotation.", "")),
    ("This tool plays a crucial role in annotation. ", ORIGINAL.replace("This tool plays a crucial role in annotation. ", "")),
])
def test_an_applied_deletion_is_placed_back_from_the_words_around_it(deleted: str, working: str) -> None:
    raw = inventory()
    raw["changes"] = [change("DS.C1", "applied", deleted, None)]
    document, record = revise.build(ORIGINAL, working, viz.Inventory.model_validate(raw), {})
    assert document.previous() == ORIGINAL and document.current() == working and record["applied"] == ["DS.C1"]


def test_the_command_puts_each_question_on_its_edit_and_the_dashboard_lists_them(run: Path) -> None:
    data = json.loads((run / "findings.json").read_text())
    for c in data["changes"]:
        if c["id"] == "IC-C1":
            c["after"] = "The pipeline joins by position and genotype [AUTHORS: which genome build?]."
    (run / "findings.json").write_text(json.dumps(data))
    result = CliRunner().invoke(revise.app, [str(run / "original.md"), str(run / "working.md"), str(run / "findings.json"),
                                             "--choices", str(run / "choices.json"), "--output-dir", str(run / "revision")])
    assert result.exit_code == 0, result.output
    assert (run / "revision/proposed.md").read_text() == PROPOSED
    record = json.loads((run / "revision/revision.json").read_text())
    assert [e["comments"] for e in record["edits"] if "IC-C1" in e["ids"]] == [["which genome build?"]]
    assert "Question for the authors: which genome build?" in (run / "revision/changes.md").read_text()
    summary = viz.render(run / "findings.json", run / "dashboard", revision=run / "revision")
    assert summary["revision"]["questions"] == 1 and summary["revision"]["notes_in_text"] == 0


def test_a_proposal_that_still_has_a_gap_is_not_placed_and_its_question_is_listed() -> None:
    """A placeholder in another form, or the empty brackets a lifted note leaves, never reaches the text."""
    data = inventory()
    data["changes"] = [
        change("PE.C1", "applied", "We use HuggingFace for data.", "We use Hugging Face for data."),
        change("JA-C12", "proposed", "The pipeline joins by rsID.",
               "The pipeline ([AUTHORS: year]) joins by rsID [Data set, revision AUTHORS]."),
        change("JA-C13", "proposed", "It is fast.", "It is fast (TBD seconds)."),
    ]
    document, record = revise.build(ORIGINAL, WORKING, viz.Inventory.model_validate(data), {})
    assert document.current() == WORKING
    assert {x["id"] for x in record["not_placed"]} == {"JA-C12", "JA-C13"}
    asked = [c["question"] for c in record["comments"] if c["ids"] == ["JA-C12"]]
    assert asked[0] == "year" and any("revision AUTHORS" in q for q in asked) and any("()" in q for q in asked)


def test_a_note_that_fills_a_slot_in_a_sentence_holds_the_proposal_and_a_plain_authors_does_not() -> None:
    data = inventory()
    data["changes"] = [
        change("PE.C1", "applied", "We use HuggingFace for data.", "We use Hugging Face for data."),
        change("JA-C8", "proposed", "It is fast.", "It is fast. The authors used [AUTHORS: tool and version] to draft it."),
        change("JA-C10", "proposed", "The pipeline joins by rsID.", "The remaining authors declare that the pipeline joins by rsID."),
    ]
    document, record = revise.build(ORIGINAL, WORKING, viz.Inventory.model_validate(data), {})
    assert [x["id"] for x in record["not_placed"]] == ["JA-C8"]
    assert "The remaining authors declare" in document.current() and "used" not in document.current().split("It is fast.")[1]
    assert any("The authors used …" in c["question"] for c in record["comments"] if c["ids"] == ["JA-C8"])
