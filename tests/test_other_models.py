"""Offline tests for manuscript-other-models/scripts/models.py, with fake `claude`, `codex` and `gemini` commands on
PATH that record how they were started and answer the way the real ones do. Run with `uv run pytest`."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "skills" / "manuscript-other-models" / "scripts" / "models.py"

spec = importlib.util.spec_from_file_location("models", MODELS)
models = importlib.util.module_from_spec(spec)
sys.modules["models"] = models
spec.loader.exec_module(models)

runner = CliRunner()

# One fake for all three CLIs: it logs its arguments, folder, prompt and environment, writes what a seat would write,
# tampers with the paper it was given, and answers in its CLI's own output format. FAKE_MODE=fail answers with the
# CLI's error, FAKE_MODE=sleep never answers.
FAKE = '''#!{python}
import json, os, sys, time
from pathlib import Path
name, args = Path(sys.argv[0]).name, sys.argv[1:]
if args == ["--version"]:
    print(name + " 9.9.9")
    sys.exit(0)
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps({{"cli": name, "argv": args, "cwd": os.getcwd(), "prompt": prompt,
                          "claudecode": os.environ.get("CLAUDECODE")}}) + "\\n")
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "sleep":
    time.sleep(60)
if mode == "ok" and prompt.startswith("Reply with the single word READY") is False:
    Path("findings.json").write_text("[]")
    Path("notes").mkdir(exist_ok=True)
    Path("notes/criteria.md").write_text("criteria")
    if Path("paper.md").exists():
        Path("paper.md").write_text("tampered")
answer = "Answer from " + name
if name == "claude":
    if mode == "fail":
        print(json.dumps({{"type": "result", "subtype": "success", "is_error": True, "result": "Not logged in"}}))
        sys.exit(1)
    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": answer,
                      "session_id": "s1", "modelUsage": {{"claude-sonnet-5-5": {{}}}}, "total_cost_usd": 0.01}}))
elif name == "codex":
    print(json.dumps({{"type": "thread.started", "thread_id": "t1"}}))
    if mode == "fail":
        inner = json.dumps({{"type": "error", "status": 400, "error": {{"message": "model not supported"}}}})
        print(json.dumps({{"type": "turn.failed", "error": {{"message": inner}}}}))
        sys.exit(1)
    Path(args[args.index("-o") + 1]).write_text(answer)
    print(json.dumps({{"type": "turn.completed", "usage": {{"input_tokens": 5}}}}))
else:
    if mode == "fail":
        sys.stderr.write("[STARTUP] noise\\n" + json.dumps({{"session_id": "g1", "error": {{"message": "GEMINI_API_KEY missing", "code": 41}}}}, indent=2))
        sys.exit(41)
    print(json.dumps({{"session_id": "g1", "response": answer, "stats": {{"models": {{"gemini-x": {{}}}}}}}}))
'''


@pytest.fixture
def fakes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A PATH holding only the fake CLIs, no host session variables, and a Codex home with a default model it does
    not list. Returns the log the fakes write to."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("claude", "codex", "gemini"):
        path = bin_dir / name
        path.write_text(FAKE.format(python=sys.executable), encoding="utf-8")
        path.chmod(0o755)
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text('model = "gpt-old"\n', encoding="utf-8")
    (home / "models_cache.json").write_text(json.dumps({"models": [{"slug": "gpt-y", "visibility": "list"},
                                                                  {"slug": "gpt-hidden", "visibility": "hide"}]}))
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "fake.log"))
    for var in ("CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "GEMINI_CLI", "CODEX_SANDBOX_NETWORK_DISABLED",
                "FAKE_MODE"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path / "fake.log"


def calls(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def seat(tmp_path: Path, name: str = "ws") -> tuple[Path, Path]:
    workspace = tmp_path / "project" / "reviews" / name
    workspace.mkdir(parents=True)
    (workspace / "paper.md").write_text("original", encoding="utf-8")
    brief = tmp_path / f"brief-{name}.md"
    brief.write_text(f"You are the skeptic. Work only from the files in {workspace}.\n", encoding="utf-8")
    return workspace, brief


def test_detect_names_the_host_the_other_families_and_a_codex_default_it_does_not_list(fakes, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    result = runner.invoke(models.app, ["detect", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    clis = {c["cli"]: c for c in data["clis"]}
    assert data["host"] == "claude" and clis["claude"]["host"] and not clis["claude"]["other_family"]
    assert clis["codex"]["other_family"] and clis["gemini"]["other_family"] and clis["codex"]["version"] == "codex 9.9.9"
    assert clis["codex"]["models"] == ["gpt-y"] and "gpt-old" in clis["codex"]["notes"][0]
    # A Codex session started from Claude Code inherits CLAUDECODE: the innermost host is Codex.
    monkeypatch.setenv("CODEX_THREAD_ID", "t")
    monkeypatch.setenv("CODEX_SANDBOX_NETWORK_DISABLED", "1")
    text = runner.invoke(models.app, ["detect"]).output
    assert "Host: Codex CLI (OpenAI)" in text and "without network" in text
    assert "claude: Claude Code claude 9.9.9, Anthropic; another model family" in text


@pytest.mark.parametrize("cli, extra, model, argv_has", [
    ("claude", ["--model", "sonnet", "--effort", "low"], "claude/claude-sonnet-5-5",
     ["-p", "--tools", "Read,Glob,Grep,Write,Edit", "--permission-mode", "acceptEdits", "--strict-mcp-config",
      "--disable-slash-commands", "--no-session-persistence", "--effort", "low"]),
    ("codex", ["--model", "gpt-y", "--effort", "high"], "codex/gpt-y",
     ["exec", "--skip-git-repo-check", "--ephemeral", "-s", "workspace-write", "-m", "gpt-y",
      "model_reasoning_effort=high", "-"]),
    ("gemini", [], "gemini/gemini-x", ["-o", "json", "--approval-mode", "auto_edit"]),
])
def test_a_seat_runs_in_a_throwaway_copy_and_only_its_new_files_come_back(
        fakes, tmp_path, cli: str, extra: list[str], model: str, argv_has: list[str]) -> None:
    workspace, brief = seat(tmp_path)
    result = runner.invoke(models.app, ["run", cli, "--workspace", str(workspace), "--brief", str(brief), *extra])
    assert result.exit_code == 0, result.output
    [call] = calls(fakes)
    copy = Path(call["cwd"])
    assert not copy.is_relative_to(tmp_path / "project") and not copy.exists()  # outside the project, then deleted
    assert all(arg in call["argv"] for arg in argv_has), call["argv"]
    assert "Bash" not in " ".join(call["argv"]) and "danger" not in " ".join(call["argv"])
    assert call["claudecode"] is None
    assert str(workspace) not in call["prompt"] and f"files in {copy}." in call["prompt"]
    assert (workspace / "findings.json").read_text() == "[]" and (workspace / "notes/criteria.md").is_file()
    assert (workspace / "paper.md").read_text() == "original"  # the seat's change to a given file stays in the copy
    assert (workspace / "seat-answer.md").read_text() == f"Answer from {cli}\n"
    assert (workspace / "seat-run.prompt.md").read_text() == call["prompt"]
    record = json.loads((workspace / "seat-run.json").read_text())
    assert record["status"] == "answered" and record["model"] == model and record["exit_code"] == 0
    assert record["returned"] == ["findings.json", "notes/criteria.md"] and record["changed_not_returned"] == ["paper.md"]
    assert record["workspace_path_in_brief_replaced"] == 1 and record["version"] == f"{cli} 9.9.9"


def test_codex_without_a_model_is_recorded_with_its_configured_default(fakes, tmp_path) -> None:
    workspace, brief = seat(tmp_path)
    assert runner.invoke(models.app, ["run", "codex", "--workspace", str(workspace), "--brief", str(brief)]).exit_code == 0
    assert json.loads((workspace / "seat-run.json").read_text())["model"] == "codex/gpt-old"
    assert "-m" not in calls(fakes)[0]["argv"]


@pytest.mark.parametrize("cli, message", [
    ("claude", "Not logged in"), ("codex", "model not supported"), ("gemini", "GEMINI_API_KEY missing")])
def test_a_failed_session_says_why_in_the_clis_own_words(fakes, tmp_path, monkeypatch, cli: str, message: str) -> None:
    monkeypatch.setenv("FAKE_MODE", "fail")
    workspace, brief = seat(tmp_path)
    result = runner.invoke(models.app, ["run", cli, "--workspace", str(workspace), "--brief", str(brief)])
    assert result.exit_code == 1 and message in result.output
    record = json.loads((workspace / "seat-run.json").read_text())
    assert record["status"] == "failed" and message in record["error"] and record["answer"] is None
    assert not (workspace / "seat-answer.md").exists()


def test_a_session_past_its_timeout_is_stopped(fakes, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "sleep")
    workspace, brief = seat(tmp_path)
    started = time.monotonic()
    result = runner.invoke(models.app, ["run", "codex", "--workspace", str(workspace), "--brief", str(brief),
                                        "--timeout", "1"])
    assert result.exit_code == 3 and time.monotonic() - started < 30
    assert json.loads((workspace / "seat-run.json").read_text())["status"] == "timeout"


def test_a_used_workspace_and_bad_arguments_are_refused_before_anything_runs(fakes, tmp_path, monkeypatch) -> None:
    workspace, brief = seat(tmp_path)
    assert runner.invoke(models.app, ["run", "claude", "--workspace", str(workspace), "--brief", str(brief)]).exit_code == 0
    again = runner.invoke(models.app, ["run", "codex", "--workspace", str(workspace), "--brief", str(brief)])
    assert again.exit_code == 2 and "fresh workspace" in again.output
    other, brief2 = seat(tmp_path, "other")
    for args in (["run", "cursor"], ["run", "gemini", "--effort", "high"], ["run", "codex", "--model", "gpt y; rm"]):
        assert runner.invoke(models.app, [*args, "--workspace", str(other), "--brief", str(brief2)]).exit_code == 2, args
    monkeypatch.setenv("PATH", str(tmp_path))  # no CLI installed
    missing = runner.invoke(models.app, ["run", "codex", "--workspace", str(other), "--brief", str(brief2)])
    assert missing.exit_code == 2 and "not installed" in missing.output
    assert len(calls(fakes)) == 1


def test_check_makes_one_tiny_call_without_the_manuscript(fakes) -> None:
    result = runner.invoke(models.app, ["check", "codex", "--model", "gpt-y"])
    assert result.exit_code == 0 and "Codex CLI: ready, model codex/gpt-y" in result.output
    [call] = calls(fakes)
    assert call["prompt"] == models.PING and not Path(call["cwd"]).exists()
