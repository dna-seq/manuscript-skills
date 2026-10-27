"""hooks/progress: the progress view of a run, a Claude Code hooks module (docs/progress-ui.md).

`claude plugin validate` reads the manifest, the hooks module and its state contract the way Claude Code loads
them, and `claude plugin test` runs hooks/progress/run.test.tsx against the engine. Both need a Claude Code with
function hooks (2.1.299 or newer) on PATH, or named in CLAUDE_BIN; without one they are skipped. The static
checks below run everywhere.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _claude() -> str | None:
    found = os.environ.get("CLAUDE_BIN") or shutil.which("claude")
    if not found:
        return None
    try:
        probe = subprocess.run([found, "plugin", "test", "--help"], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    # a release without `plugin test` answers with the general plugin help
    return found if "plugin test" in probe.stdout else None


CLAUDE = _claude()
needs_claude = pytest.mark.skipif(CLAUDE is None, reason="needs Claude Code 2.1.299 or newer (claude plugin test)")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([CLAUDE, "plugin", *args, str(ROOT)], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300, cwd=ROOT)


def test_hooks_json_loads_on_older_claude_code() -> None:
    """Claude Code before function hooks requires a `hooks` record in hooks/hooks.json and otherwise reports the
    plugin's hooks as failed to load; the empty record keeps it quiet there while newer releases load `modules`."""
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert hooks["hooks"] == {}
    assert hooks["modules"] == ["./progress/register.tsx"]
    assert (ROOT / "hooks" / "progress" / "register.tsx").is_file()


def test_manifest_names_the_state_contract() -> None:
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    contract = ROOT / manifest["types"]
    assert contract.is_file()
    # state is keyed by the plugin's name, so a rename of the plugin must rename the contract and the module's refs
    assert f"'{manifest['name']}': {{" in contract.read_text(encoding="utf-8")
    module = (ROOT / "hooks" / "progress" / "register.tsx").read_text(encoding="utf-8")
    assert f"plugin: '{manifest['name']}'" in module
    assert f"mcp__{manifest['name']}__show_run" in module


@needs_claude
def test_claude_plugin_validate() -> None:
    ran = _run("validate")
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert "Validation passed" in ran.stdout
    assert "progress/register.tsx hooks:" in ran.stdout


@needs_claude
def test_claude_plugin_test() -> None:
    ran = _run("test")
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert " 0 fail" in ran.stdout + ran.stderr
