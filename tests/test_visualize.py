"""Evidence identity, honest counting and real Vega-Lite rendering for review infographics."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/manuscript-visualize/scripts/infographic.py"
spec = importlib.util.spec_from_file_location("infographic", SCRIPT)
visualize = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = visualize
spec.loader.exec_module(visualize)


@pytest.fixture()
def data(tmp_path: Path) -> dict:
    evidence = "The reference is wrong. The claim needs checking. Before A. After A. Before B. After B."
    (tmp_path / "review.md").write_text(evidence)
    sources = [{"path": "review.md", "quote": evidence}]
    def finding(fid, assessment, resolution):
        return {"id": fid, "category": "References", "section": "Discussion", "summary": f"Issue {fid}",
                "severity": "major", "assessment": assessment, "resolution": resolution,
                "skills": ["manuscript-reference-check", "manuscript-integrity-check"], "evidence": sources}
    def change(cid, state, fid, letter):
        return {"id": cid, "kind": "Reference correction", "section": "Discussion", "summary": f"Edit {cid}",
                "status": state, "finding_ids": [fid], "before": f"Before {letter}.", "after": f"After {letter}.",
                "evidence": sources}
    return {"schema_version": 1, "title": "Review findings", "run_id": "test-run", "scope": "Selected test records.",
            "illustrative": True,
            "coverage": [{"skill": skill, "status": "partial", "note": "Selected sections only.", "evidence": sources}
                         for skill in ("manuscript-reference-check", "manuscript-integrity-check")],
            "findings": [finding("F1", "confirmed", "addressed"), finding("F2", "confirmed", "open"),
                         finding("F3", "candidate", "unknown"), finding("F4", "dismissed", "unknown")],
            "changes": [change("C1", "applied", "F1", "A"), change("C2", "applied", "F1", "B"),
                        change("C3", "proposed", "F2", "A")]}


def test_counts_distinguish_edits_findings_attribution_and_candidates(data: dict) -> None:
    summary = visualize.summarize(visualize.Inventory.model_validate(data))
    assert summary["counts"] == {"confirmed_findings": 2, "addressed_findings": 1, "open_findings": 1,
                                 "resolution_unknown": 0, "candidate_findings": 1, "dismissed_flags": 1,
                                 "applied_edits": 2, "proposed_edits": 1}
    assert summary["by_category"] == {"References": 2}  # two reporting skills still count each finding once
    assert summary["by_resolution"] == {"addressed": 1, "open": 1}


@pytest.mark.parametrize("field", ["findings", "changes", "coverage"])
def test_duplicate_ids_are_rejected_instead_of_inflating_counts(data: dict, field: str) -> None:
    data[field].append(copy.deepcopy(data[field][0]))
    with pytest.raises(ValidationError, match="Duplicate"):
        visualize.Inventory.model_validate(data)


@pytest.mark.parametrize("mutation", ["proposal-only", "candidate", "unknown-link", "unknown-skill"])
def test_unsupported_resolution_or_attribution_is_rejected(data: dict, mutation: str) -> None:
    if mutation == "proposal-only":
        for change in data["changes"]:
            change["status"] = "proposed"
    elif mutation == "candidate":
        data["findings"][0]["assessment"] = "candidate"
    elif mutation == "unknown-link":
        data["changes"][0]["finding_ids"] = ["absent"]
    else:
        data["findings"][0]["skills"] = ["absent"]
    with pytest.raises(ValidationError):
        visualize.Inventory.model_validate(data)


def test_evidence_identity_and_applied_passages_are_checked(data: dict, tmp_path: Path) -> None:
    inventory = visualize.Inventory.model_validate(data)
    assert len(visualize.verify_evidence(inventory, tmp_path)["review.md"]) == 64
    inventory.findings[0].evidence[0].quote = "A quote the report never contained."
    with pytest.raises(ValueError, match="quote absent"):
        visualize.verify_evidence(inventory, tmp_path)
    inventory = visualize.Inventory.model_validate(data)
    inventory.changes[0].after = "An edit that was never applied."
    with pytest.raises(ValueError, match="before/after text absent"):
        visualize.verify_evidence(inventory, tmp_path)


def test_invalid_evidence_writes_no_infographic(data: dict, tmp_path: Path) -> None:
    data["findings"][0]["evidence"] = [{"path": "missing.md", "quote": "No report."}]
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data))
    with pytest.raises(OSError):
        visualize.render(source, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_offline_report_escapes_source_text_and_keeps_proposals_separate(data: dict) -> None:
    data["title"] = '<script>alert("title")</script>'
    data["findings"][0]["summary"] = '<img src=x onerror="alert(1)">'
    inventory = visualize.Inventory.model_validate(data)
    output = visualize.report_html(inventory, visualize.summarize(inventory), "<svg/>")
    assert '<script>alert("title")</script>' not in output and "&lt;script&gt;" in output
    assert '<img src=x' not in output and "&lt;img" in output
    assert "proposed · Reference correction" in output
    assert "Chart totals retain the full stated scope" in output
    assert '<script src=' not in output


def test_real_render_preserves_partial_scope_counts_and_previous_attempts(data: dict, tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data))
    output = tmp_path / "rendered"
    summary = visualize.render(source, output)
    svg = (output / "infographic.svg").read_text()
    assert "ILLUSTRATIVE EXAMPLE" in svg and "partial" in svg
    assert "Confirmed findings" in svg and "Candidate findings" in svg
    assert (output / "infographic.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert json.loads((output / "summary.json").read_text())["counts"] == summary["counts"]
    original = (output / "infographic.svg").read_bytes()
    with pytest.raises(ValueError, match="already exist"):
        visualize.render(source, output)
    assert (output / "infographic.svg").read_bytes() == original


def test_empty_findings_are_not_mislabeled_as_complete_review(data: dict) -> None:
    data["findings"], data["changes"] = [], []
    inventory = visualize.Inventory.model_validate(data)
    summary = visualize.summarize(inventory)
    assert not any(summary["counts"].values())
    spec = visualize.chart(inventory, summary)
    assert "No records in this scope" in json.dumps(spec) and "partial" in json.dumps(spec)


@pytest.mark.parametrize("count", [0, 1, 6, 51])
def test_count_axes_never_round_fractional_ticks_into_duplicate_integers(count: int) -> None:
    spec = visualize.bars("Edits", {"Applied": count}, "#6653a3")
    ticks = spec["encoding"]["x"]["axis"]["values"]
    assert ticks[0] == 0 and len(ticks) == len(set(ticks))
    assert all(isinstance(tick, int) for tick in ticks)


def test_worked_input_uses_actual_evidence_and_does_not_invent_edits() -> None:
    source = ROOT / "evals/fixtures/manuscript-visualize/reader-review.json"
    inventory = visualize.Inventory.model_validate_json(source.read_text())
    visualize.verify_evidence(inventory, source.parent)
    summary = visualize.summarize(inventory)
    assert summary["counts"]["confirmed_findings"] == 6
    assert summary["counts"]["applied_edits"] == 0
    assert summary["by_severity"] == {"unknown": 6}
    assert inventory.coverage[0].status == "partial" and "Selected" in inventory.scope
