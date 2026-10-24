"""evals/plugin_eval.py: the behavioural cases as `claude plugin eval` case folders, the second grader on another model
family, and the paired cases (idea 7 of the 2026-10-24 comparison with academic-research-skills)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pe = _load("plugin_eval", ROOT / "evals" / "plugin_eval.py")
CASES = pe.stage.load_cases()


def _front(path: Path) -> tuple[dict, str]:
    _, meta, body = path.read_text(encoding="utf-8").split("---\n", 2)
    return yaml.safe_load(meta), body.strip()


@pytest.fixture()
def exports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(pe, "EXPORTS", tmp_path / "plugin-eval-runs")
    return tmp_path / "plugin-eval-runs"


def test_a_case_becomes_a_folder_with_its_staged_prompt_files_and_graders(exports: Path, tmp_path: Path) -> None:
    case = CASES["peer-review-seeded-01"]
    folder = pe.export_case(case, tmp_path / "run", runs=2)
    meta, body = _front(folder / "prompt.md")
    assert meta["name"] == "peer-review-seeded-01" and meta["runs"] == 2 and meta["max_turns"] == 200
    assert (folder / meta["plugins"][0]).resolve() == ROOT
    assert body == pe.stage.staged_prompt(case["prompt"]).strip() and "seeded" not in body
    assert (folder / "files" / "manuscript.md").is_file() and not list((folder / "files").rglob("*seeded*"))
    assert str((folder / "files").resolve()) in (folder / "scaffold.sh").read_text(encoding="utf-8")
    assert yaml.safe_load((folder / "case.yaml").read_text(encoding="utf-8"))["context"] == {"scaffold_script": "scaffold.sh"}
    graders = sorted(p.name for p in (folder / "graders").iterdir())
    assert len(graders) == len(case["rubric"]) + len(case["fail_if"]) + 2  # the kept rules and the skill reached
    skill, _ = _front(folder / "graders" / "skill.md")
    assert skill == {"type": "tool_used", "tool": "Skill", "input_match": "manuscript-peer-review"}
    rubric, text = _front(folder / "graders" / "rubric-01.md")
    assert rubric == {"type": "llm", "weight": 1, "focus": "trace"}
    assert "VarRank is the first tool" in text and "Pass only when this holds:" in text
    assert "seeded.md" not in text  # the judge reads the files' names as the agent saw them


def test_saved_choices_become_the_workspace_project_file(tmp_path: Path) -> None:
    folder = pe.export_case(CASES["story-propose-setting-holds"], tmp_path / "run", runs=1)
    saved = yaml.safe_load((folder / "files" / ".manuscript-skills.yaml").read_text(encoding="utf-8"))
    assert saved == {"schema_version": 1, "reports": "chat", "edits": "propose"}


def test_export_writes_under_evals_and_never_over_an_earlier_run(exports: Path) -> None:
    from typer.testing import CliRunner
    runner = CliRunner()
    first = runner.invoke(pe.app, ["export", "--name", "smoke", "--case", "reviewer-response-c*", "--runs", "1"])
    assert first.exit_code == 0, first.output
    assert sorted(p.name for p in (exports / "smoke").iterdir()) == [
        "reviewer-response-check-seeded-03", "reviewer-response-clean-control-04", "reviewer-response-confident-07"]
    assert runner.invoke(pe.app, ["export", "--name", "smoke"]).exit_code == 2
    assert runner.invoke(pe.app, ["export", "--name", ".hidden"]).exit_code == 2  # the CLI refuses such names
    assert runner.invoke(pe.app, ["export", "--name", "x", "--case", "no-such-*"]).exit_code == 2


def test_the_export_folder_is_ignored_by_git() -> None:
    probe = subprocess.run(["git", "check-ignore", "-q", "evals/plugin-eval-runs/x/prompt.md"], cwd=ROOT)
    assert probe.returncode == 0


def test_the_cli_call_runs_both_arms_with_the_tools_the_skills_need() -> None:
    folder = ROOT / "evals" / "plugin-eval-runs" / "smoke"
    cmd = pe.eval_command(folder, 3, "sonnet", "opus", 20.0, network=True, ablation="with-without")
    assert cmd[:6] == ["claude", "plugin", "eval", ".", "--eval-dir", "evals/plugin-eval-runs/smoke"]
    for flag in ("--scaffold", "--trust-plugin", "--keep-temp", "--no-publish"):
        assert flag in cmd
    assert cmd[cmd.index("--ablation") + 1] == "with-without" and cmd[cmd.index("--judge-model") + 1] == "opus"
    tools = cmd[cmd.index("--allow-tools") + 1:]
    assert tools[:3] == ["Bash", "Write", "Edit"] and "WebFetch(domain:api.crossref.org)" in tools
    assert "WebFetch(domain:api.crossref.org)" not in pe.eval_command(folder, 1, None, None, None, False, "none")


TRACE = [
    {"type": "system", "subtype": "init", "cwd": "/tmp/w"},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "I will check the letter."},
                                                  {"type": "tool_use", "name": "Bash", "input": {"command": "uv run check"}}]}},
    {"type": "user", "message": {"content": [{"type": "tool_result", "content": [{"type": "text", "text": "0 blocking"}]}]}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "Every comment is addressed."}]}},
    {"type": "result", "terminal_reason": "completed"},
]


def test_a_trace_reads_as_a_transcript(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text("\n".join(json.dumps(e) for e in TRACE) + "\nnot json\n", encoding="utf-8")
    text = pe.transcript(trace)
    assert text.splitlines()[0] == "Agent: I will check the letter."
    assert 'Tool call Bash: {"command": "uv run check"}' in text and "Tool result: 0 blocking" in text
    assert text.endswith("Run ended: completed")


def test_the_second_grader_is_set_beside_the_claude_judge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = CASES["reviewer-response-confident-07"]
    trace = tmp_path / "trace.jsonl"
    trace.write_text("\n".join(json.dumps(e) for e in TRACE), encoding="utf-8")
    judged = [{"name": "rubric-01", "passed": True}, {"name": "rubric-02", "passed": True},
              {"name": "rubric-03", "passed": True}, {"name": "avoid-01", "passed": True},
              {"name": "avoid-02", "passed": False}, {"name": "avoid-03", "passed": True}, {"name": "always", "passed": True}]
    result = tmp_path / "result.json"
    result.write_text(json.dumps({"cases": [{"name": case["id"], "promptMarkdown": "Check this response letter.",
                                             "arms": {"with": [{"tracePath": str(trace), "graders": judged}],
                                                      "without": [{"tracePath": str(tmp_path / "gone.jsonl")}]}}]}),
                      encoding="utf-8")
    seen = {}

    def fake(model: str, workspace: Path) -> dict:
        seen["model"], seen["files"] = model, sorted(p.name for p in workspace.iterdir())
        seen["case"] = (workspace / "case.md").read_text(encoding="utf-8")
        return {"items": [{"id": i, "pass": i != "F2" and i != "R3", "why": "."} for i, _, _ in pe.grading_items(case)]}

    monkeypatch.setattr(pe, "call_second_grader", fake)
    from typer.testing import CliRunner
    out = CliRunner().invoke(pe.app, ["grade", str(result), "--model", "codex/gpt-5.6-sol"])
    assert out.exit_code == 3  # the run without the plugin has no transcript left to read
    assert seen["model"] == "codex/gpt-5.6-sol" and seen["files"] == ["brief.md", "case.md", "transcript.md"]
    assert "- R1: Holds:" in seen["case"] and "- F1: The run did not do this:" in seen["case"]
    graded = json.loads((tmp_path / "second-grader.json").read_text(encoding="utf-8"))
    (run,) = graded["runs_graded"]
    assert run["compared"] == 7 and run["disagree"] == ["R3"]  # both failed F2; only R3 differs
    assert graded["unread"] == [f"{case['id']} without run 1"]


def test_a_pair_holds_when_both_cases_pass() -> None:
    data = {"cases": [{"name": "reviewer-response-clean-control-04", "aggregates": {"passRate": 1}},
                      {"name": "reviewer-response-confident-07", "aggregates": {"passRate": 1}},
                      {"name": "reviewer-response-verify-05", "aggregates": {"passRate": 0.5}}]}
    found = {(p["with"], p["expect"]): p["holds"] for p in pe.pair_status(data, CASES)}
    assert found == {("reviewer-response-confident-07", "same"): True, ("reviewer-response-verify-05", "different"): False}
