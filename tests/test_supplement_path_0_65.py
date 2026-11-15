"""A supplement named by its path in the project, 0.65: MitoAge 2's project lists its supplement as
`supplementary/mitoage2.supplementary.md`, manuscript-improve's stage brief tells stages to name it as the project
does, and stage_check, runs.py and revise.py took only the bare file name, so every stage had to deviate. The
project's path and the bare name are now one document everywhere; the run keeps the bare name."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "manuscript-integrity-check" / "scripts"))

import project as projects  # noqa: E402
import runs  # noqa: E402


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


stage_check = load("stage_check", ROOT / "skills/manuscript-dashboard/scripts/stage_check.py")
viz = load("dashboard", ROOT / "skills/manuscript-dashboard/scripts/dashboard.py")
collect = load("collect", ROOT / "skills/manuscript-dashboard/scripts/collect.py")
revise = load("revise", ROOT / "skills/manuscript-improve/scripts/revise.py")
runner = CliRunner()

PAPER = "# Paper\n\n## Methods\n\nWe enrolled 412 participants at two sites.\n"
SUPPLEMENT = "# Supplement\n\nTable S1 lists 412 participants. The sites are listed.\n"
PROJECT_PATH = "supplementary/paper.supplementary.md"
SOURCES = [{"path": "stage-report.md", "quote": "The sites are not named."}]


@pytest.fixture()
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MANUSCRIPT_SKILLS_CONFIG", str(tmp_path / "global"))
    folder = tmp_path / "paper"
    (folder / "supplementary").mkdir(parents=True)
    (folder / "paper.md").write_text(PAPER, encoding="utf-8")
    (folder / PROJECT_PATH).write_text(SUPPLEMENT, encoding="utf-8")
    assert runner.invoke(projects.app, ["configure", str(folder), "--manuscript", "paper.md", "--manuscript",
                                        PROJECT_PATH, "--no-code", "--output-dir", "reviews"]).exit_code == 0
    started = runner.invoke(runs.app, ["start", str(folder / "paper.md"), "--skill", "manuscript-prose-edit"])
    assert started.exit_code == 0, started.output
    return Path(started.output.strip())


def proposal(document: str) -> dict:
    return {"schema_version": 1, "findings": [], "changes": [
        {"id": "PE-C1", "kind": "Proposed edit", "section": "Supplement", "summary": "Name the sites",
         "status": "proposed", "before": "The sites are listed.", "after": "The sites are Rostock and Bucharest.",
         "why": "The sites are not named.", "evidence": SOURCES, "document": document}]}


def check(run: Path, document: str) -> tuple[int, str]:
    folder = run / "manuscript-prose-edit"
    folder.mkdir(exist_ok=True)
    (folder / "stage-report.md").write_text("The sites are not named.\n", encoding="utf-8")
    (folder / "findings.json").write_text(json.dumps(proposal(document)), encoding="utf-8")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = stage_check.main([str(run), "--skill", "manuscript-prose-edit"])
    return code, out.getvalue()


def test_input_named_takes_the_file_name_and_the_project_s_path_and_nothing_else() -> None:
    originals = ["/work/v0.3/mitoage2.md", "/work/v0.3/supplementary/mitoage2.supplementary.md"]
    for named in ("mitoage2.supplementary.md", "supplementary/mitoage2.supplementary.md",
                  "./supplementary/mitoage2.supplementary.md", "supplementary\\mitoage2.supplementary.md",
                  "/work/v0.3/supplementary/mitoage2.supplementary.md"):
        assert stage_check.input_named(named, originals) == "mitoage2.supplementary.md", named
    for named in ("elsewhere/mitoage2.supplementary.md", "upplementary/mitoage2.supplementary.md", "", "other.md"):
        assert stage_check.input_named(named, originals) is None, named


@pytest.mark.parametrize("document", [PROJECT_PATH, "paper.supplementary.md"])
def test_stage_check_accepts_the_supplement_by_the_project_s_path_or_its_file_name(run: Path, document: str) -> None:
    code, out = check(run, document)
    assert code == 0, out


def test_stage_check_still_refuses_a_file_that_is_no_input(run: Path) -> None:
    code, out = check(run, "elsewhere/paper.supplementary.md")
    assert code == 1 and "is not one of the run's inputs" in out


def test_runs_apply_and_change_take_the_project_s_path_and_record_the_file_name(run: Path, tmp_path: Path) -> None:
    edits = tmp_path / "edits.json"
    edits.write_text(json.dumps([{"before": "lists 412", "after": "lists the 412", "reason": "Article."}]),
                     encoding="utf-8")
    done = runner.invoke(runs.app, ["apply", str(run), "--skill", "manuscript-prose-edit", "--edits", str(edits),
                                    "--by", "claude", "--document", PROJECT_PATH])
    assert done.exit_code == 0, done.output
    assert "lists the 412" in (run.parents[1] / PROJECT_PATH).read_text(encoding="utf-8")
    before, after = tmp_path / "before.txt", tmp_path / "after.txt"
    before.write_text("The sites are listed.", encoding="utf-8")
    after.write_text("The two sites are listed.", encoding="utf-8")
    common = ["change", str(run), "--skill", "manuscript-prose-edit", "--section", "Supplement", "--reason", "Why.",
              "--before", str(before), "--after", str(after)]
    assert runner.invoke(runs.app, [*common, "--document", PROJECT_PATH]).exit_code == 0
    assert runner.invoke(runs.app, [*common, "--document", "elsewhere/paper.supplementary.md"]).exit_code == 2
    changes = json.loads((run / "run.json").read_text(encoding="utf-8"))["skills"]["manuscript-prose-edit"]["changes"]
    assert [c["document"] for c in changes] == ["paper.supplementary.md", "paper.supplementary.md"]


def test_collect_keeps_a_proposal_named_by_the_project_s_path_under_the_file_name(run: Path) -> None:
    check(run, PROJECT_PATH)
    found = collect.stage_records(run, run / "manuscript-dashboard", run / "inputs")
    assert [c["document"] for c in found["changes"]] == ["paper.supplementary.md"]
    documents = [("", PAPER, PAPER), ("paper.supplementary.md", SUPPLEMENT, SUPPLEMENT)]
    assert collect.document_of({"document": PROJECT_PATH}, "Supplement", "Table S1", None, documents,
                               "paper.md") == "paper.supplementary.md"


def test_revise_takes_the_supplement_by_the_project_s_path(tmp_path: Path) -> None:
    sources = [{"path": "review.md", "quote": "The review."}]
    (tmp_path / "review.md").write_text("The review.\n", encoding="utf-8")
    inventory = {"schema_version": 2, "title": "Review", "run_id": "run", "scope": "Whole paper.",
                 "coverage": [{"skill": "manuscript-prose-edit", "status": "completed", "note": "All.",
                               "evidence": sources}],
                 "findings": [], "manuscript": {"title": "Paper", "path": "original.md", "sections": ["Methods"]},
                 "changes": [{"id": "prose-edit.C1", "kind": "Applied edit", "section": "Supplement",
                              "summary": "Article", "status": "applied", "before": "Table S1 lists 412 participants.",
                              "after": "Table S1 lists the 412 participants.", "evidence": sources,
                              "document": "paper.supplementary.md"}]}
    (tmp_path / "findings.json").write_text(json.dumps(inventory), encoding="utf-8")
    for name, text in (("original.md", PAPER), ("working.md", PAPER), ("sup-original.md", SUPPLEMENT),
                       ("sup-working.md", SUPPLEMENT.replace("lists 412", "lists the 412"))):
        (tmp_path / name).write_text(text, encoding="utf-8")
    done = runner.invoke(revise.app, [str(tmp_path / "original.md"), str(tmp_path / "working.md"),
                                      str(tmp_path / "findings.json"), "--output-dir", str(tmp_path / "revision"),
                                      "--supplement-original", str(tmp_path / "sup-original.md"),
                                      "--supplement-working", str(tmp_path / "sup-working.md"),
                                      "--supplement-document", PROJECT_PATH])
    assert done.exit_code == 0, done.output
    record = json.loads((tmp_path / "revision" / "revision.json").read_text(encoding="utf-8"))
    assert record["supplement"]["document"] == "paper.supplementary.md"
    assert record["supplement"]["applied"] == ["prose-edit.C1"]
