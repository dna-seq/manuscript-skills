"""Seats free of the authors' own setup, and the paper's length in view, 0.47 (docs/run-audit-2026-10.md, items 10
and 11): in the Paper 1 v0.6 run the sceptical referee followed the authors' memory, and the stages' additions took
the running text from about 6,880 to 7,470 words with nothing recording it."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "manuscript-integrity-check" / "scripts"))

import project as projects  # noqa: E402
import runs  # noqa: E402

spec = importlib.util.spec_from_file_location("models_047", ROOT / "skills/manuscript-other-models/scripts/models.py")
models = importlib.util.module_from_spec(spec)
sys.modules["models_047"] = models
spec.loader.exec_module(models)
runner = CliRunner()


def test_each_cli_says_what_of_the_authors_setup_reaches_a_seat() -> None:
    assert models.CLIS["claude"].instructions.startswith("left out")
    assert models.CLIS["codex"].instructions.startswith("left out")
    assert models.CLIS["gemini"].instructions.startswith("partly")
    claude = models.claude_argv("sonnet", None, Path("last.txt"))
    assert claude[claude.index("--setting-sources") + 1] == "project,local"  # not "user": no CLAUDE.md, hooks, plugins
    assert "--ignore-user-config" in models.codex_argv("gpt-y", None, Path("last.txt"))


def test_a_codex_seat_keeps_the_configured_effort_its_ignored_config_would_have_given(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text('model = "gpt-z"\nmodel_reasoning_effort = "xhigh"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    assert models.codex_effort() == "xhigh"
    seen = {}
    monkeypatch.setitem(models.ADAPTERS, "codex", (lambda model, effort, last: seen.update(model=model, effort=effort)
                                                   or ["true"], models.ADAPTERS["codex"][1]))
    models.session("codex", tmp_path, "brief", None, None, 30, tmp_path / "out", tmp_path / "err")
    assert seen == {"model": "gpt-z", "effort": "xhigh"}
    models.session("codex", tmp_path, "brief", "gpt-y", "low", 30, tmp_path / "out", tmp_path / "err")
    assert seen == {"model": "gpt-y", "effort": "low"}  # the seat's own choice wins


PAPER = """# A tool

<!-- @rev C1 rounds=1 by=anna:2026-10-01 -->
It annotates a genome locally.
<!-- @/rev C1 -->

## Results

It is fast.

## References

Adams, A. (2020). One. *J*, 1.
"""


def test_the_length_counts_the_clean_running_text_up_to_the_references(tmp_path: Path) -> None:
    path = tmp_path / "paper.md"
    path.write_text(PAPER, encoding="utf-8")
    # "A tool", "It annotates a genome locally", "Results", "It is fast": the marks and the references not counted.
    assert runs.manuscript_words(path) == 2 + 5 + 1 + 3
    assert runs.manuscript_words(tmp_path / "missing.md") is None


@pytest.fixture()
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MANUSCRIPT_SKILLS_CONFIG", str(tmp_path / "global"))
    folder = tmp_path / "paper"
    folder.mkdir()
    (folder / "paper.md").write_text(PAPER, encoding="utf-8")
    assert runner.invoke(projects.app, ["configure", str(folder), "--manuscript", "paper.md", "--no-code",
                                        "--output-dir", "reviews"]).exit_code == 0
    started = runner.invoke(runs.app, ["start", str(folder / "paper.md"), "--skill", "manuscript-prose-edit"])
    assert started.exit_code == 0, started.output
    return Path(started.output.strip())


def test_the_run_records_the_length_at_the_start_and_after_each_stage_that_edits(run: Path) -> None:
    data = json.loads((run / "run.json").read_text(encoding="utf-8"))
    assert data["inputs"][0]["words"] == 11
    edits = run.parent / "edits.json"
    edits.write_text(json.dumps([{"before": "It is fast.", "after": "It is fast on a laptop with 16 GB of memory.",
                                  "reason": "Say on what."}]), encoding="utf-8")
    assert runner.invoke(runs.app, ["apply", str(run), "--skill", "manuscript-prose-edit", "--edits", str(edits),
                                    "--by", "claude"]).exit_code == 0
    report = run.parent / "stage-report.md"
    report.write_text("The prose edit.", encoding="utf-8")
    assert runner.invoke(runs.app, ["add", str(run), "--skill", "manuscript-prose-edit", "--file", str(report),
                                    "--role", "report", "--name", "stage-report.md"]).exit_code == 0
    (run / "manuscript-prose-edit" / "findings.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
    done = runner.invoke(runs.app, ["finish", str(run), "--skill", "manuscript-prose-edit", "--status", "completed"])
    assert done.exit_code == 0, done.output
    data = json.loads((run / "run.json").read_text(encoding="utf-8"))
    assert data["skills"]["manuscript-prose-edit"]["length"] == {"paper.md": 19}
    assert "Length after it: paper.md 19 words (+8 since the run began)." in (run / "README.md").read_text()
    # The coordinator's own revise step records its mark too.
    assert runner.invoke(runs.app, ["stage", str(run), "--name", "revise", "--status", "completed"]).exit_code == 0
    stages = json.loads((run / "run.json").read_text(encoding="utf-8"))["skills"]["manuscript-improve"]["stages"]
    assert stages["revise"]["length"] == {"paper.md": 19}
