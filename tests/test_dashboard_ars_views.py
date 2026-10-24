"""The dashboard's claim ladder, reviewers' criteria grid with where each expectation comes from, and reference strip
(added with ideas 8 and 6 of the 2026-10-24 comparison with academic-research-skills)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


visualize = _load("dashboard", ROOT / "skills/manuscript-dashboard/scripts/dashboard.py")
collect = _load("collect", ROOT / "skills/manuscript-dashboard/scripts/collect.py")

ORIGINAL = """# Loss of Foo and tumour growth

## Abstract

Loss of Foo reduces tumour growth by 40%.

## Results

In mice, loss of Foo was associated with a 40% reduction in tumour growth. Loss of Foo proves that Foo drives growth.

## Discussion

Foo may contribute to tumour growth in mice.
"""
PROPOSED = (ORIGINAL.replace("Loss of Foo proves that Foo drives growth.", "Loss of Foo suggests that Foo contributes to growth.")
            .replace("Foo may contribute to tumour growth in mice.", "Foo drives tumour growth in mice."))


def test_the_claim_ladder_places_each_moved_claim_and_says_what_asked_for_it(tmp_path: Path) -> None:
    requested = tmp_path / "requested-claims.yaml"
    requested.write_text(yaml.safe_dump([{"passage": "suggests that Foo contributes", "finding": "PR-2"}]), encoding="utf-8")
    claims = visualize.claim_movements(ORIGINAL, PROPOSED, requested)
    assert claims["requested"] is True
    lowered = [m for m in claims["moves"] if m["to"] < m["from"]]
    raised = [m for m in claims["moves"] if m["to"] > m["from"]]
    assert lowered and all(m["asked_by"] == ["PR-2"] for m in lowered)       # "proves" → "suggests", asked for
    assert raised and not raised[0]["asked_by"] and "Discussion" in raised[0]["where"]  # "may contribute" → "drives"
    assert [a["label"] for a in claims["axes"]["causal"]][0] == "compatibility with a finding"
    # The corrected Discussion now says "drives", so the Abstract's "reduces" has a body sentence as strong; its
    # dropped "in mice" is still a limit the body states.
    (summary,) = claims["summary"]
    assert summary["kind"] == "scope" and "ladder" not in summary and summary["where"].startswith("the Abstract")
    assert visualize.claim_movements(ORIGINAL, ORIGINAL, None) is None or not visualize.claim_movements(
        ORIGINAL, ORIGINAL, None)["moves"]


def test_without_requested_changes_a_stronger_claim_shows_no_requester() -> None:
    claims = visualize.claim_movements(ORIGINAL, PROPOSED, None)
    assert claims["requested"] is False and all(m["asked_by"] == [] for m in claims["moves"])


def test_collect_gives_each_reviewer_its_criteria_and_each_concern_where_its_expectation_comes_from(tmp_path: Path) -> None:
    folder = tmp_path / "manuscript-peer-review"
    folder.mkdir()
    doc = {"reports": [{"seat": "skeptic", "summary": "Sound.", "recommendations": []}], "strengths": [],
           "findings": [{"id": "SK-1", "seat": "skeptic", "severity": "major", "concern": "One cohort only.",
                         "change_my_mind": "Replication in an independent cohort.", "criterion": "C1",
                         "norm_source": "own: one cohort cannot show the effect generalises"},
                        {"id": "SK-2", "seat": "skeptic", "severity": "major", "concern": "The build is not stated.",
                         "off_criterion": "a mismatch would move every position"}]}
    (folder / "findings.adjudicated.json").write_text(json.dumps(doc), encoding="utf-8")
    (folder / "check.adjudicated.json").write_text(json.dumps({"criteria": {"skeptic": {"criteria": [
        {"id": "C1", "text": "A headline resting on one cohort.", "findings": ["SK-1"], "covered": False, "checked": ""},
        {"id": "C2", "text": "Leakage between training and test.", "findings": [], "covered": True,
         "checked": "nothing to raise; checked Methods"},
        {"id": "C3", "text": "A batch confounded with condition.", "findings": [], "covered": False, "checked": ""}]}}}),
        encoding="utf-8")
    (reviewer,) = collect.panel(tmp_path)["reviewers"]
    assert [c["id"] for c in reviewer["criteria"]] == ["C1", "C2", "C3"]
    assert reviewer["criteria"][1]["checked"] == "nothing to raise; checked Methods"
    sk1, sk2 = reviewer["concerns"]
    assert sk1["criterion"] == ["C1"] and sk1["norm_source"].startswith("own:")
    assert sk2["off_criterion"] == "a mismatch would move every position"
    visualize.Panel.model_validate({"reviewers": [reviewer]})  # the inventory accepts the new fields


def test_collect_reads_the_reference_list_with_each_entry_s_worst_state(tmp_path: Path) -> None:
    folder = tmp_path / "manuscript-reference-check"
    folder.mkdir()
    refs = [{"line": 10, "text": "Duncan L. Analysis. Nat Commun. 2019;10:3328.", "status": "resolved", "doi": "10.1/a"},
            {"line": 11, "text": "Torkamani A. Utility. Nat Rev Genet. 2016;17(9):581-590.", "status": "resolved", "doi": "10.1/b"},
            {"line": 12, "text": "Sebastiani P. Signatures. Science. 2010.", "status": "retracted", "doi": "10.1/c"},
            {"line": 13, "text": "Doe J. Invented. J Imag. 2024.", "status": "unresolved", "doi": "10.1/d"},
            {"line": 14, "text": "Roe K. Report. 2021.", "status": "no_identifier"},
            {"line": 15, "text": "Poe M. Preprint. arXiv.", "status": "lookup_failed", "arxiv": "2101.00001"}]
    findings = [{"check": "references", "severity": "minor", "line": 11, "excerpt": refs[1]["text"],
                 "message": "The DOI leads to the work, but the entry differs from that record in its year."},
                {"check": "references", "severity": "info", "line": 10, "excerpt": refs[0]["text"], "message": "A note."}]
    (folder / "references.json").write_text(json.dumps({"path": "paper.md", "online": True, "findings": findings,
                                                        "references": refs}), encoding="utf-8")
    listed = collect.reference_list(tmp_path)
    assert [r["state"] for r in listed] == ["fine", "corrected", "retracted", "wrong", "unverified", "not-checked"]
    assert listed[1]["notes"] == [findings[0]["message"]] and listed[0]["notes"] == []
    assert listed[0]["link"] == "https://doi.org/10.1/a" and listed[5]["link"] == "https://arxiv.org/abs/2101.00001"
    assert listed[4]["link"] == ""
    assert collect.reference_list(tmp_path / "nothing") == []


def test_the_dashboard_embeds_the_three_views(tmp_path: Path) -> None:
    evidence = "The reference is wrong."
    (tmp_path / "review.md").write_text(evidence, encoding="utf-8")
    sources = [{"path": "review.md", "quote": evidence}]
    data = visualize.Inventory.model_validate({
        "schema_version": 2, "title": "Review", "run_id": "R1", "scope": "Test.",
        "coverage": [{"skill": "manuscript-reference-check", "status": "completed", "note": "All.", "evidence": sources}],
        "findings": [], "changes": [],
        "panel": {"reviewers": [{"seat": "skeptic", "criteria": [{"id": "C1", "text": "One cohort."}],
                                 "concerns": [{"id": "SK-1", "concern": "One cohort only.", "norm_source": "own: generalising"}]}]},
        "reference_list": [{"n": 1, "text": "Duncan L. Analysis.", "state": "fine", "link": "https://doi.org/10.1/a"}]})
    claims = visualize.claim_movements(ORIGINAL, PROPOSED, None)
    page = visualize.dashboard_html(data, visualize.summarize(data), tmp_path, claims=claims)
    start = page.index('<script type="application/json" id="inventory">') + len('<script type="application/json" id="inventory">')
    doc = json.loads(page[start:page.index("</script>", start)])
    assert doc["claims"]["moves"] and doc["inventory"]["reference_list"][0]["state"] == "fine"
    assert doc["inventory"]["panel"]["reviewers"][0]["criteria"][0]["id"] == "C1"
    for view in ("function claimLadder", "function referenceStrip", "const criteriaGrid", "Where the reviewers"):
        assert view in page
