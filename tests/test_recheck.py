"""manuscript-improve's independent re-check of the corrected version (recheck.py) and the dashboard's view of it: idea
5 of the 2026-10-24 comparison with academic-research-skills."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


viz = _load("dashboard", ROOT / "skills/manuscript-dashboard/scripts/dashboard.py")
revise = _load("revise", ROOT / "skills/manuscript-improve/scripts/revise.py")
recheck = _load("recheck", ROOT / "skills/manuscript-improve/scripts/recheck.py")

ORIGINAL = """# Foo and tumour growth

## Abstract

We studied 412 participants. Loss of Foo proves that Foo drives growth.

## Methods

We enrolled 412 participants at two sites.
"""
FIXED = "Loss of Foo suggests that Foo contributes to growth."
SOURCES = [{"path": "review.md", "quote": "The review."}]


def _inventory() -> dict:
    return {"schema_version": 2, "title": "Review", "run_id": "run", "scope": "Whole paper.",
            "coverage": [{"skill": "manuscript-peer-review", "status": "completed", "note": "Panel.", "evidence": SOURCES}],
            "findings": [{"id": "PR-1", "category": "Claims", "section": "Abstract", "summary": "A proof claim from an association",
                          "detail": "The study measured an association.", "action": "Say what the data show.",
                          "quote": "Loss of Foo proves that Foo drives growth.", "severity": "major",
                          "assessment": "confirmed", "resolution": "open", "skills": ["manuscript-peer-review"],
                          "evidence": SOURCES},
                         {"id": "PR-2", "category": "Numbers", "section": "Methods", "summary": "Sites not named",
                          "severity": "minor", "assessment": "confirmed", "resolution": "open",
                          "skills": ["manuscript-peer-review"], "evidence": SOURCES},
                         {"id": "PR-3", "category": "Claims", "section": "Abstract", "summary": "A candidate",
                          "severity": "minor", "assessment": "candidate", "resolution": "unknown",
                          "skills": ["manuscript-peer-review"], "evidence": SOURCES}],
            "manuscript": {"title": "Foo", "version": "v1", "path": "original.md", "sections": ["Abstract", "Methods"]},
            "changes": [{"id": "PR-C1", "kind": "Claim correction", "section": "Abstract", "summary": "Narrow the claim",
                         "status": "proposed", "before": "Loss of Foo proves that Foo drives growth.", "after": FIXED,
                         "finding_ids": ["PR-1"], "evidence": SOURCES}],
            "panel": {"reviewers": [{"seat": "skeptic", "concerns": [{"id": "SK-1", "concern": "Proof from an association.",
                                                                    "suggestion": "Report it as an association.",
                                                                    "finding_ids": ["PR-1"]}]}]}}


@pytest.fixture()
def run(tmp_path: Path) -> Path:
    (tmp_path / "review.md").write_text("The review.\n", encoding="utf-8")
    (tmp_path / "original.md").write_text(ORIGINAL, encoding="utf-8")
    (tmp_path / "working.md").write_text(ORIGINAL, encoding="utf-8")
    (tmp_path / "findings.json").write_text(json.dumps(_inventory()), encoding="utf-8")
    result = CliRunner().invoke(revise.app, [str(tmp_path / "original.md"), str(tmp_path / "working.md"),
                                             str(tmp_path / "findings.json"), "--output-dir", str(tmp_path / "revision")])
    assert result.exit_code == 0, result.output
    prepared = CliRunner().invoke(recheck.app, ["prepare", "--inventory", str(tmp_path / "findings.json"), "--revision",
                                                str(tmp_path / "revision"), "--original", str(tmp_path / "original.md"),
                                                "--into", str(tmp_path / "recheck")])
    assert prepared.exit_code == 0, prepared.output
    return tmp_path


def test_prepare_gives_the_agent_both_texts_the_changes_and_the_confirmed_problems_only(run: Path) -> None:
    folder = run / "recheck"
    assert sorted(p.name for p in folder.iterdir()) == ["brief.md", "changes.json", "concerns.json", "corrected.md",
                                                       "original.md"]
    concerns = json.loads((folder / "concerns.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in concerns] == ["PR-1", "PR-2"]  # the candidate is not a confirmed problem
    pr1 = concerns[0]
    assert pr1["settled_by"] == "Say what the data show.; Report it as an association."
    assert pr1["raised_by"] == ["peer-review", "skeptic"] and pr1["quote"].startswith("Loss of Foo proves")
    assert FIXED in (folder / "corrected.md").read_text(encoding="utf-8")
    changes = json.loads((folder / "changes.json").read_text(encoding="utf-8"))
    assert any(c["kind"] in ("causal", "evidential") for c in changes)
    brief = (folder / "brief.md").read_text(encoding="utf-8")
    assert "`corrected.md`" in brief and "the 2 problems" in brief and "Narrow the claim" not in brief  # no reasons


def _answer(run: Path, **extra) -> Path:
    body = {"concerns": [{"id": "PR-1", "verdict": "fully", "quote": FIXED, "why": "It now reports an association."},
                         {"id": "PR-2", "verdict": "unchecked", "why": "The sites are not in these texts."}],
            "new_problems": []}
    body.update(extra)
    path = run / "recheck" / "answer.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _check(run: Path, answer: Path, *more: str):
    return CliRunner().invoke(recheck.app, ["check", str(answer), "--out", str(run / "recheck.json"), *more])


def test_a_valid_answer_is_written_for_the_dashboard(run: Path) -> None:
    result = _check(run, _answer(run))
    assert result.exit_code == 0, result.output
    written = json.loads((run / "recheck.json").read_text(encoding="utf-8"))
    corrected = (run / "revision" / "proposed.md").read_text(encoding="utf-8")
    assert written["proposed_sha256"] == revise.digest(corrected) and written["isolation"] == "fresh-agent"
    assert [c["verdict"] for c in written["concerns"]] == ["fully", "unchecked"]
    assert written["concerns"][0]["raised_by"] == ["peer-review", "skeptic"]


def test_an_unchecked_problem_may_give_its_quote_as_null(run: Path) -> None:
    answer = _answer(run, concerns=[{"id": "PR-1", "verdict": "fully", "quote": FIXED, "why": "Fixed."},
                                    {"id": "PR-2", "verdict": "unchecked", "quote": None, "why": "Not in these texts."}])
    result = _check(run, answer)
    assert result.exit_code == 0, result.output
    assert json.loads((run / "recheck.json").read_text(encoding="utf-8"))["concerns"][1]["quote"] == ""


@pytest.mark.parametrize("extra, said", [
    ({"concerns": [{"id": "PR-1", "verdict": "fully", "quote": "Loss of Foo shows nothing at all.", "why": "Fixed."},
                   {"id": "PR-2", "verdict": "unchecked", "why": "Not here."}]}, "does not occur word for word"),
    ({"concerns": [{"id": "PR-1", "verdict": "fully", "quote": FIXED, "why": "Fixed."}]}, "PR-2 is answered 0 times"),
    ({"new_problems": [{"origin": "introduced", "section": "Methods", "quote": "We enrolled 412 participants",
                        "problem": "Sites are vague."}]}, "label it missed"),
    ({"new_problems": [{"origin": "missed", "section": "Abstract", "quote": "suggests that Foo contributes",
                        "problem": "Still causal."}]}, "label it introduced"),
])
def test_an_answer_that_breaks_the_contract_writes_nothing(run: Path, extra: dict, said: str) -> None:
    result = _check(run, _answer(run, **extra))
    assert result.exit_code == 1 and said in result.output
    assert not (run / "recheck.json").exists()


def test_an_edit_that_made_a_problem_worse_or_introduced_one_exits_3(run: Path) -> None:
    answer = _answer(run, new_problems=[{"origin": "introduced", "section": "Abstract", "quote": FIXED,
                                         "problem": "'Contributes' is still a causal verb for an association."}])
    result = _check(run, answer)
    assert result.exit_code == 3 and "hold or reverse those edits" in result.output
    assert json.loads((run / "recheck.json").read_text(encoding="utf-8"))["new_problems"][0]["origin"] == "introduced"


def test_the_number_and_reference_checks_run_on_both_versions(tmp_path: Path) -> None:
    before, after = tmp_path / "a.md", tmp_path / "b.md"
    before.write_text(ORIGINAL, encoding="utf-8")
    after.write_text(ORIGINAL.replace("We enrolled 412", "We enrolled 421"), encoding="utf-8")
    out = tmp_path / "numbers.json"
    assert CliRunner().invoke(recheck.app, ["numbers", "--original", str(before), "--proposed", str(after),
                                            "--json", str(out)]).exit_code == 0
    compared = json.loads(out.read_text(encoding="utf-8"))
    assert [c["check"] for c in compared["numbers"]["introduced"]] == ["ledger"]
    assert compared["numbers"]["resolved"] == [] and compared["proposed_sha256"] == revise.digest(after.read_text())
    swapped = recheck.compare_candidates(recheck._candidates(after, False), recheck._candidates(before, False))
    assert len(swapped["numbers"]["resolved"]) == 1  # the same edit undone resolves it


def test_the_recheck_and_its_number_comparison_reach_the_dashboard(run: Path) -> None:
    numbers = run / "recheck" / "numbers.json"
    corrected = run / "revision" / "proposed.md"
    assert CliRunner().invoke(recheck.app, ["numbers", "--original", str(run / "original.md"), "--proposed",
                                            str(corrected), "--json", str(numbers)]).exit_code == 0
    assert _check(run, _answer(run), "--numbers", str(numbers), "--model", "codex/gpt-5.6-sol").exit_code == 0
    summary = viz.render(run / "findings.json", run / "dashboard", revision=run / "revision")
    assert summary["recheck"]["verdicts"]["fully"] == 1 and summary["recheck"]["current"] is True
    page = (run / "dashboard" / "manuscript-dashboard.html").read_text(encoding="utf-8")
    start = page.index('<script type="application/json" id="inventory">') + len('<script type="application/json" id="inventory">')
    doc = json.loads(page[start:page.index("</script>", start)])
    by_id = {f["id"]: f for f in doc["inventory"]["findings"]}
    assert by_id["PR-1"]["resolution"] == "addressed" and by_id["PR-2"]["resolution"] == "unknown"
    assert by_id["PR-1"]["recheck"]["verdict"] == "fully" and "recheck" not in by_id["PR-3"]
    assert doc["recheck"]["model"] == "codex/gpt-5.6-sol" and "function recheckView" in page
    # The inventory file keeps its own resolutions: the re-check changes only what the page shows.
    assert json.loads((run / "findings.json").read_text(encoding="utf-8"))["findings"][0]["resolution"] == "open"


def test_a_recheck_of_an_earlier_build_is_shown_as_such(run: Path) -> None:
    assert _check(run, _answer(run)).exit_code == 0
    stale = json.loads((run / "recheck.json").read_text(encoding="utf-8")) | {"proposed_sha256": "0" * 64}
    (run / "recheck.json").write_text(json.dumps(stale), encoding="utf-8")
    assert viz.render(run / "findings.json", run / "dashboard", revision=run / "revision")["recheck"]["current"] is False
