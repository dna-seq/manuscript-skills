"""The scripts run the same on Linux, macOS and Windows.

Static checks over every skill script: text files are read and written as UTF-8 whatever the platform's
locale, subprocess output is decoded as UTF-8, console output is UTF-8 (a Windows console or pipe defaults to
the locale's code page, and the reports quote curly quotes, dashes and ≥), POSIX-only calls have a Windows
branch, and no committed file carries a developer's home folder.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted([*ROOT.glob("skills/*/scripts/*.py"), ROOT / "evals" / "stage.py"])
POSIX_ONLY = ("os.killpg", "os.setsid", "os.getuid", "os.getpgid", "signal.SIGKILL", "import fcntl", "os.fork(")
SUBPROCESS_CALLS = {"run", "Popen", "check_output", "check_call", "call"}


def _keywords(call: ast.Call) -> dict[str, ast.expr]:
    return {k.arg: k.value for k in call.keywords if k.arg}


def _is_true(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _text_mode(call: ast.Call) -> bool:
    """open(...) in text mode: no mode, or a constant mode without 'b'."""
    mode = _keywords(call).get("mode") or (call.args[1] if len(call.args) > 1 else None)
    if mode is None:
        return True
    return isinstance(mode, ast.Constant) and isinstance(mode.value, str) and "b" not in mode.value


def unportable_calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func, kw = node.func, _keywords(node)
        where = f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
        if name in {"read_text", "write_text"} and isinstance(func, ast.Attribute) and "encoding" not in kw:
            # str.write_text does not exist; any read_text/write_text here is pathlib's or zipfile.Path's.
            positional = 1 if name == "write_text" else 0
            if len(node.args) <= positional:
                problems.append(f"{where}: {name}() without encoding")
        elif name == "open" and isinstance(func, ast.Name) and _text_mode(node) and "encoding" not in kw:
            problems.append(f"{where}: open() in text mode without encoding")
        elif (name in SUBPROCESS_CALLS and isinstance(func, ast.Attribute)
              and isinstance(func.value, ast.Name) and func.value.id == "subprocess"
              and (_is_true(kw.get("text")) or _is_true(kw.get("universal_newlines"))) and "encoding" not in kw):
            problems.append(f"{where}: subprocess.{name}(text=True) without encoding")
    return problems


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_text_is_read_and_written_as_utf8(path: Path) -> None:
    assert unportable_calls(path) == []


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_posix_only_calls_have_a_windows_branch(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    used = [call for call in POSIX_ONLY if call in source]
    if used:
        assert re.search(r"os\.name\s*==\s*['\"]nt['\"]|sys\.platform|platform\.system\(\)", source), (
            f"{path.name} uses {', '.join(used)} with no Windows branch")


@pytest.mark.parametrize("path", [p for p in SCRIPTS if "__main__" in p.read_text(encoding="utf-8")],
                         ids=lambda p: p.relative_to(ROOT).as_posix())
def test_console_output_is_utf8(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    assert "reconfigure(" in source, f"{path.name} prints without making stdout and stderr UTF-8"


def test_no_committed_home_paths() -> None:
    """No developer's home folder in committed text, outside the archived 2026-10-19 eval bundle (its
    evidence is hash-pinned by its own index and kept as recorded) and the tests, which plant such paths
    on purpose for the local-path check."""
    archived = ROOT / "evals" / "results" / "2026-10-19-real-manuscripts"
    pattern = re.compile(r"(?:/home|/Users)/(?!user\b|me\b|you\b|name\b|USER\b|<)[A-Za-z][\w.-]+/")
    offenders = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if (not path.is_file() or rel.parts[0] in {".git", ".venv", ".pytest_cache", "tests"} or archived in path.parents
                or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".zip", ".gz", ".ico"}):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        offenders += [f"{rel.as_posix()}:{n}" for n, line in enumerate(text.splitlines(), 1) if pattern.search(line)]
    assert offenders == []
