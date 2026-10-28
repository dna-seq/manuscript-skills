"""The supplement's corrected version and the second re-check, 0.45 (docs/run-audit-2026-10.md, items 2 and 3):
revise.py builds the supplement from its own changes, the re-check reads it, a second re-check reads only what the
fixes after the first changed, and a re-check that read another build stops the final validation."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "manuscript-integrity-check" / "scripts"))

import project as projects  # noqa: E402
import runs  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


viz = _load("dashboard", ROOT / "skills/manuscript-dashboard/scripts/dashboard.py")
revise = _load("revise", ROOT / "skills/manuscript-improve/scripts/revise.py")
recheck = _load("recheck", ROOT / "skills/manuscript-improve/scripts/recheck.py")
runner = CliRunner()


def said(output: str) -> str:
    """A command's message without the frame and line breaks of Typer's error box."""
    return " ".join(re.sub(r"[│╭╮╰╯─]", " ", output).split())

MAIN = """# Foo and tumour growth

## Abstract

We studied 412 participants. Loss of Foo proves that Foo drives growth.

## Methods

We enrolled 412 participants at two sites.
"""
SUPPLEMENT = """# Supplementary Data

**S1. Participants.** Table S1 lists 412 participants. The sites are listed.
"""
FIXED = "Loss of Foo suggests that Foo contributes to growth."
FIXED_AGAIN = "Loss of Foo is associated with slower growth."
SITES = "The sites are Rostock and Bucharest."
SOURCES = [{"path": "review.md", "quote": "The review."}]


def finding(fid: str, section: str, quote: str | None) -> dict:
    return {"id": fid, "category": "Claims", "section": section, "summary": f"Problem {fid}", "quote": quote,
            "severity": "major", "assessment": "confirmed", "resolution": "open", "skills": ["manuscript-peer-review"],
            "evidence": SOURCES}


def inventory(fix: str = FIXED) -> dict:
    return {"schema_version": 2, "title": "Review", "run_id": "run", "scope": "Whole paper.",
            "coverage": [{"skill": "manuscript-peer-review", "status": "completed", "note": "All.", "evidence": SOURCES}],
            "findings": [finding("PR-1", "Abstract", "Loss of Foo proves that Foo drives growth."),
                         finding("PR-2", "Methods", "We enrolled 412 participants at two sites."),
                         finding("PR-4", "Supplement S1", "The sites are listed.")],
            "manuscript": {"title": "Foo", "path": "original.md", "sections": ["Abstract", "Methods"]},
            "changes": [
                {"id": "PR-C1", "kind": "Claim correction", "section": "Abstract", "summary": "Narrow the claim",
                 "status": "proposed", "before": "Loss of Foo proves that Foo drives growth.", "after": fix,
                 "finding_ids": ["PR-1"], "evidence": SOURCES},
                {"id": "PR-C4", "kind": "Proposed edit", "section": "Supplement S1", "summary": "Name the sites",
                 "status": "proposed", "before": "The sites are listed.", "after": SITES, "finding_ids": ["PR-4"],
                 "evidence": SOURCES, "document": "supplement.md"},
                {"id": "prose-edit.C1", "kind": "Applied edit", "section": "Supplement S1", "summary": "Article",
                 "status": "applied", "before": "Table S1 lists 412 participants.",
                 "after": "Table S1 lists the 412 participants.", "evidence": SOURCES, "document": "supplement.md"}]}


@pytest.fixture()
def run(tmp_path: Path) -> Path:
    (tmp_path / "review.md").write_text("The review.\n", encoding="utf-8")
    (tmp_path / "original.md").write_text(MAIN, encoding="utf-8")
    (tmp_path / "working.md").write_text(MAIN, encoding="utf-8")
    (tmp_path / "sup-original.md").write_text(SUPPLEMENT, encoding="utf-8")
    (tmp_path / "sup-working.md").write_text(SUPPLEMENT.replace("lists 412", "lists the 412"), encoding="utf-8")
    (tmp_path / "findings.json").write_text(json.dumps(inventory()), encoding="utf-8")
    return tmp_path


def build(run: Path, folder: str, findings: str = "findings.json"):
    return runner.invoke(revise.app, [str(run / "original.md"), str(run / "working.md"), str(run / findings),
                                      "--output-dir", str(run / folder), "--supplement-original",
                                      str(run / "sup-original.md"), "--supplement-working", str(run / "sup-working.md")])


def test_the_supplement_gets_its_own_corrected_version_from_its_own_changes(run: Path) -> None:
    result = build(run, "revision")
    assert result.exit_code == 0, result.output
    folder = run / "revision"
    proposed = (folder / "proposed.md").read_text(encoding="utf-8")
    sup = (folder / "supplement-proposed.md").read_text(encoding="utf-8")
    assert FIXED in proposed and SITES not in proposed and "lists the 412" not in proposed
    assert SITES in sup and "Table S1 lists the 412 participants." in sup and FIXED not in sup
    assert (folder / "supplement-revised.md").read_text(encoding="utf-8") == (run / "sup-working.md").read_text()
    record = json.loads((folder / "revision.json").read_text(encoding="utf-8"))
    assert record["proposed_in_this_version"] == ["PR-C1"]
    assert record["supplement"]["document"] == "supplement.md"
    assert record["supplement"]["applied"] == ["prose-edit.C1"]
    assert record["supplement"]["proposed_in_this_version"] == ["PR-C4"]
    assert record["supplement"]["proposed_sha256"] == revise.digest(sup)
    assert "PR-C4" in (folder / "supplement-changes.md").read_text(encoding="utf-8")


def test_the_supplement_s_two_texts_go_together_and_an_unrecorded_supplement_edit_stops_the_build(run: Path) -> None:
    alone = runner.invoke(revise.app, [str(run / "original.md"), str(run / "working.md"), str(run / "findings.json"),
                                       "--output-dir", str(run / "revision"), "--supplement-original",
                                       str(run / "sup-original.md")])
    assert alone.exit_code == 2 and "together" in said(alone.output)
    (run / "sup-working.md").write_text(SUPPLEMENT.replace("lists 412", "lists all 412"), encoding="utf-8")
    assert build(run, "revision").exit_code == 2


def prepare(run: Path, into: str, *more: str):
    return runner.invoke(recheck.app, ["prepare", "--inventory", str(run / "findings.json"), "--revision",
                                       str(run / "revision"), "--original", str(run / "original.md"),
                                       "--supplement-original", str(run / "sup-original.md"), "--into", str(run / into),
                                       *more])


def answer(folder: Path, concerns: list[dict], new: list[dict] | None = None) -> Path:
    path = folder / "answer.json"
    path.write_text(json.dumps({"concerns": concerns, "new_problems": new or []}), encoding="utf-8")
    return path


def test_the_re_check_reads_the_supplement_too(run: Path) -> None:
    assert build(run, "revision").exit_code == 0
    result = prepare(run, "recheck")
    assert result.exit_code == 0, result.output
    folder = run / "recheck"
    assert {"original-supplementary.md", "corrected-supplementary.md"} <= {p.name for p in folder.iterdir()}
    assert [c["id"] for c in json.loads((folder / "concerns.json").read_text())] == ["PR-1", "PR-2", "PR-4"]
    assert any(c.get("file") == "supplement" for c in json.loads((folder / "changes.json").read_text()))
    brief = (folder / "brief.md").read_text(encoding="utf-8")
    assert "`corrected-supplementary.md`" in brief and "(the manuscript or the supplement)" in brief
    done = runner.invoke(recheck.app, ["check", str(answer(folder, [
        {"id": "PR-1", "verdict": "fully", "quote": FIXED, "why": "Narrowed."},
        {"id": "PR-2", "verdict": "unchecked", "why": "Not here."},
        {"id": "PR-4", "verdict": "fully", "quote": SITES, "why": "Named."}])), "--out", str(run / "recheck.json")])
    assert done.exit_code == 0, done.output


def first_pass(run: Path) -> None:
    assert build(run, "revision").exit_code == 0
    assert prepare(run, "recheck").exit_code == 0
    folder = run / "recheck"
    result = runner.invoke(recheck.app, ["check", str(answer(folder, [
        {"id": "PR-1", "verdict": "worse", "quote": FIXED, "why": "Now it overstates a different way."},
        {"id": "PR-2", "verdict": "not", "quote": "We enrolled 412 participants at two sites.", "why": "Still unnamed."},
        {"id": "PR-4", "verdict": "fully", "quote": SITES, "why": "Named."}],
        [{"origin": "introduced", "section": "Abstract", "quote": FIXED, "problem": "Contributes is vague."}])),
        "--out", str(run / "recheck.json")])
    assert result.exit_code == 3 and "second re-check" in result.output
    # The fixes: a new wording for the claim, and the corrected version rebuilt as the next attempt.
    (run / "findings.2.json").write_text(json.dumps(inventory(FIXED_AGAIN)), encoding="utf-8")
    assert build(run, "revision.2", "findings.2.json").exit_code == 0


def test_the_second_re_check_reads_only_what_the_fixes_changed_and_keeps_the_rest(run: Path) -> None:
    first_pass(run)
    result = runner.invoke(recheck.app, ["prepare", "--inventory", str(run / "findings.2.json"), "--revision",
                                         str(run / "revision.2"), "--original", str(run / "original.md"),
                                         "--supplement-original", str(run / "sup-original.md"), "--into",
                                         str(run / "recheck.2"), "--since", str(run / "recheck.json"),
                                         "--previous", str(run / "revision")])
    assert result.exit_code == 0, result.output
    folder = run / "recheck.2"
    concerns = json.loads((folder / "concerns.json").read_text(encoding="utf-8"))
    # PR-1 was made worse; the new problem was introduced; PR-2 and PR-4 keep verdicts whose quotes still stand.
    assert [c["id"] for c in concerns] == ["PR-1", "new-1"]
    assert concerns[0]["earlier_verdict"] == "worse"
    assert FIXED in (folder / "original.md").read_text() and FIXED_AGAIN in (folder / "corrected.md").read_text()
    assert "Second re-check" in (folder / "brief.md").read_text(encoding="utf-8")
    done = runner.invoke(recheck.app, ["check", str(answer(folder, [
        {"id": "PR-1", "verdict": "fully", "quote": FIXED_AGAIN, "why": "Reported as an association."},
        {"id": "new-1", "verdict": "fully", "quote": FIXED_AGAIN, "why": "The vague word is gone."}])),
        "--out", str(run / "recheck.2.json")])
    assert done.exit_code == 0, done.output
    second = json.loads((run / "recheck.2.json").read_text(encoding="utf-8"))
    assert second["round"] == 2 and second["carried_over"] == ["PR-2", "PR-4"]
    assert {c["id"]: c["verdict"] for c in second["concerns"]} == {"PR-1": "fully", "PR-2": "not", "PR-4": "fully"}
    assert second["new_problems"] == []  # the first's introduced problem was solved
    assert second["proposed_sha256"] == revise.digest((run / "revision.2/proposed.md").read_text(encoding="utf-8"))
    viz.Recheck.model_validate(second)
    # There is no third, and a second re-check needs the build the first one read.
    third = runner.invoke(recheck.app, ["prepare", "--inventory", str(run / "findings.2.json"), "--revision",
                                        str(run / "revision.2"), "--original", str(run / "original.md"), "--into",
                                        str(run / "recheck.3"), "--since", str(run / "recheck.2.json"), "--previous",
                                        str(run / "revision.2")])
    assert third.exit_code == 2 and "there is no third" in said(third.output)


def test_a_second_re_check_needs_the_build_the_first_read(run: Path) -> None:
    first_pass(run)
    wrong = runner.invoke(recheck.app, ["prepare", "--inventory", str(run / "findings.2.json"), "--revision",
                                        str(run / "revision.2"), "--original", str(run / "original.md"), "--into",
                                        str(run / "recheck.2"), "--since", str(run / "recheck.json"), "--previous",
                                        str(run / "revision.2")])
    assert wrong.exit_code == 2 and "read another version" in said(wrong.output)


def test_a_fix_that_makes_things_worse_in_the_second_re_check_ends_the_re_checks(run: Path) -> None:
    first_pass(run)
    assert runner.invoke(recheck.app, ["prepare", "--inventory", str(run / "findings.2.json"), "--revision",
                                       str(run / "revision.2"), "--original", str(run / "original.md"), "--into",
                                       str(run / "recheck.2"), "--since", str(run / "recheck.json"), "--previous",
                                       str(run / "revision")]).exit_code == 0
    done = runner.invoke(recheck.app, ["check", str(answer(run / "recheck.2", [
        {"id": "PR-1", "verdict": "worse", "quote": FIXED_AGAIN, "why": "Still wrong."},
        {"id": "new-1", "verdict": "not", "quote": FIXED_AGAIN, "why": "Still vague."}])),
        "--out", str(run / "recheck.2.json")])
    assert done.exit_code == 3 and "there is no third" in done.output
    kept = json.loads((run / "recheck.2.json").read_text(encoding="utf-8"))["new_problems"]
    assert [p["problem"] for p in kept] == ["Contributes is vague."]  # not solved, so it stays


# --- runs.py: the gate and the handover -------------------------------------------------------------------------

@pytest.fixture()
def project_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MANUSCRIPT_SKILLS_CONFIG", str(tmp_path / "global"))
    folder = tmp_path / "paper"
    folder.mkdir()
    (folder / "paper.md").write_text(MAIN, encoding="utf-8")
    (folder / "paper-supplementary.md").write_text(SUPPLEMENT, encoding="utf-8")
    assert runner.invoke(projects.app, ["configure", str(folder), "--manuscript", "paper.md", "--manuscript",
                                        "paper-supplementary.md", "--no-code", "--output-dir", "reviews"]).exit_code == 0
    started = runner.invoke(runs.app, ["start", str(folder / "paper.md"), "--skill", "manuscript-improve"])
    assert started.exit_code == 0, started.output
    run = Path(started.output.strip())
    revision = run / "manuscript-improve" / "revision"
    revision.mkdir(parents=True)
    (revision / "proposed.md").write_text(MAIN.replace("proves", "suggests"), encoding="utf-8")
    (revision / "supplement-proposed.md").write_text(SUPPLEMENT.replace("lists 412", "lists the 412"), encoding="utf-8")
    (revision / "revision.json").write_text(json.dumps({"supplement": {"document": "paper-supplementary.md"}}))
    return run


def test_a_re_check_of_another_build_stops_the_final_validation_unless_a_reason_is_recorded(project_run: Path) -> None:
    run = project_run
    data = json.loads((run / "run.json").read_text(encoding="utf-8"))
    corrected = run / "manuscript-improve" / "revision" / "proposed.md"
    (run / "manuscript-improve" / "recheck.json").write_text(json.dumps({"proposed_sha256": "0" * 64}))
    assert runs.stale_recheck(run, data) and "never re-checked" in runs.stale_recheck(run, data)
    (run / "manuscript-improve" / "recheck.2.json").write_text(json.dumps({"proposed_sha256": runs.digest(corrected)}))
    assert runs.stale_recheck(run, data) is None  # the newest re-check read this build
    (run / "manuscript-improve" / "recheck.2.json").unlink()
    data["skills"]["manuscript-improve"]["stages"] = {"recheck": {"status": "partial",
                                                                  "reason": "The fixes after it were not re-checked."}}
    assert runs.stale_recheck(run, data) is None


def test_the_supplement_s_corrected_version_is_handed_over_under_the_supplement_s_name(project_run: Path) -> None:
    result = runner.invoke(runs.app, ["handover", str(project_run)])
    assert result.exit_code == 0, result.output
    folder = project_run.parents[1]
    assert (folder / "paper.proposed.md").read_text(encoding="utf-8") == MAIN.replace("proves", "suggests")
    assert "lists the 412" in (folder / "paper-supplementary.proposed.md").read_text(encoding="utf-8")
