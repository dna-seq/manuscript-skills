"""Offline tests for the plugin-wide settings (manuscript-integrity-check/scripts/settings.py)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "manuscript-integrity-check" / "scripts" / "settings.py"
PRIORITIES = ROOT / "skills" / "manuscript-integrity-check" / "references" / "author-priorities.md"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


st = _load("settings", SCRIPT)
runner = CliRunner()


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty configuration folder of the test's own, as an eval run would set."""
    folder = tmp_path / "config"
    monkeypatch.setenv(st.ENV_DIR, str(folder))
    return folder / "settings.yaml"


def _run(*args: str):
    return runner.invoke(st.app, list(args))


def test_an_unset_setting_reads_as_not_set_and_asks_its_question(cfg: Path) -> None:
    result = _run("get", "reports")
    assert (result.exit_code, result.output.strip()) == (1, "not set")
    items = json.loads(_run("questions", "--json").output)
    assert [q["key"] for q in items] == ["reports", "edits", "keep"] == list(st.SETTINGS)
    assert {o["value"] for o in items[0]["options"]} == set(st.SETTINGS["reports"].options)
    assert items[0]["default"] == items[0]["recommended"] == "file" and items[0]["current"] is None
    assert all(q["recommended"] in {o["value"] for o in q["options"]} and q["why"] for q in items)
    assert not cfg.exists()  # reading never creates the file


@pytest.mark.parametrize("key, choice", [
    (key, choice) for key, setting in st.SETTINGS.items() for choice in setting.options
])
def test_a_saved_choice_round_trips_and_is_not_asked_again(cfg: Path, key: str, choice: str) -> None:
    assert _run("set", key, choice).exit_code == 0
    result = _run("get", key)
    assert (result.exit_code, result.output.strip()) == (0, choice)
    assert [q["key"] for q in json.loads(_run("questions", "--json").output)] == [
        other for other in st.SETTINGS if other != key
    ]
    again = json.loads(_run("questions", "--all", "--json").output)
    assert [(q["key"], q["current"]) for q in again] == [
        (other, choice if other == key else None) for other in st.SETTINGS
    ]
    assert json.loads(_run("show", "--json").output) == {
        "file": str(cfg), "settings": {other: choice if other == key else None for other in st.SETTINGS}
    }


def test_startup_resolves_safe_defaults_without_writing_or_asking(cfg: Path) -> None:
    result = _run("resolve", "--json")
    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "file": str(cfg),
        "effective": {"reports": "file", "edits": "conservative", "keep": "everything"},
        "sources": {"reports": "default", "edits": "default", "keep": "default"},
    }
    assert not cfg.exists()


def test_saved_edit_policy_and_report_destination_are_independent(cfg: Path) -> None:
    cfg.parent.mkdir(parents=True)
    cfg.write_text("reports: chat\nlanguage: british\n", encoding="utf-8")
    assert _run("set", "edits", "propose").exit_code == 0
    result = json.loads(_run("resolve", "--json").output)
    assert result["effective"] == {"reports": "chat", "edits": "propose", "keep": "everything"}
    assert result["sources"] == {"reports": "saved", "edits": "saved", "keep": "default"}
    assert yaml.safe_load(cfg.read_text(encoding="utf-8")) == {
        "reports": "chat", "edits": "propose", "language": "british"
    }
    assert _run("unset", "edits").exit_code == 0
    result = json.loads(_run("resolve", "--json").output)
    assert result["effective"] == {"reports": "chat", "edits": "conservative", "keep": "everything"}
    assert result["sources"] == {"reports": "saved", "edits": "default", "keep": "default"}
    assert yaml.safe_load(cfg.read_text(encoding="utf-8")) == {"reports": "chat", "language": "british"}


@pytest.mark.parametrize("body", ["edits: everything\n", "edits: [apply]\n", "edits: true\n"])
def test_invalid_edit_policy_falls_back_to_conservative_without_overwriting(cfg: Path, body: str) -> None:
    cfg.parent.mkdir(parents=True)
    cfg.write_text(body, encoding="utf-8")
    result = json.loads(_run("resolve", "--json").output)
    assert result["effective"]["edits"] == "conservative"
    assert result["sources"]["edits"] == "default"
    assert cfg.read_text(encoding="utf-8") == body


@pytest.mark.parametrize("args, message", [
    (("set", "reports", "email"), "'email' is not a choice for reports"),
    (("set", "colour", "blue"), "There is no setting 'colour'"),
    (("get", "colour"), "There is no setting 'colour'"),
    (("set", "reports", "FILE"), "'FILE' is not a choice"),
    (("set", "edits", "everything"), "'everything' is not a choice for edits"),
])
def test_unknown_settings_and_values_are_refused_without_writing(cfg: Path, args: tuple[str, ...],
                                                                  message: str) -> None:
    result = _run(*args)
    assert result.exit_code == 2 and message in result.output
    assert not cfg.exists()


def test_unset_forgets_one_choice_and_keeps_keys_this_version_does_not_know(cfg: Path) -> None:
    cfg.parent.mkdir(parents=True)
    cfg.write_text("reports: chat\nlanguage: british # from a newer version\n", encoding="utf-8")
    assert _run("unset", "reports").exit_code == 0
    assert yaml.safe_load(cfg.read_text(encoding="utf-8")) == {"language": "british"}
    assert _run("set", "reports", "both").exit_code == 0
    assert yaml.safe_load(cfg.read_text(encoding="utf-8")) == {"language": "british", "reports": "both"}
    assert cfg.read_text(encoding="utf-8").startswith("# manuscript-skills settings")
    assert [p.name for p in cfg.parent.iterdir()] == ["settings.yaml"]  # no temporary file left behind


@pytest.mark.parametrize("body", ["reports: [file\n", "- file\n- chat\n", "just a sentence\n"])
def test_a_broken_settings_file_is_reported_and_never_overwritten(cfg: Path, body: str) -> None:
    cfg.parent.mkdir(parents=True)
    cfg.write_text(body, encoding="utf-8")
    for args in (("get", "reports"), ("show",), ("resolve", "--json"), ("questions",),
                 ("set", "reports", "file"), ("set", "edits", "apply")):
        result = _run(*args)
        assert result.exit_code == 2 and "fix or delete it" in result.output, args
    assert cfg.read_text(encoding="utf-8") == body


@pytest.mark.parametrize("body", ["", "# only a comment\n", "reports: carrier-pigeon\n", "reports: 3\n"])
def test_an_empty_file_or_an_unknown_value_reads_as_not_set(cfg: Path, body: str) -> None:
    cfg.parent.mkdir(parents=True)
    cfg.write_text(body, encoding="utf-8")
    assert _run("get", "reports").output.strip() == "not set"
    assert [q["key"] for q in json.loads(_run("questions", "--json").output)] == ["reports", "edits", "keep"]


@pytest.mark.parametrize("platform, env, expected", [
    ("linux", {"HOME": "/home/a"}, "/home/a/.config/manuscript-skills"),
    ("linux", {"HOME": "/home/a", "XDG_CONFIG_HOME": "/xdg"}, "/xdg/manuscript-skills"),
    ("darwin", {"HOME": "/Users/a"}, "/Users/a/Library/Application Support/manuscript-skills"),
    ("win32", {"USERPROFILE": "C:/Users/a", "APPDATA": "C:/Users/a/AppData/Roaming"},
     "C:/Users/a/AppData/Roaming/manuscript-skills"),
    ("linux", {"HOME": "/home/a", "MANUSCRIPT_SKILLS_CONFIG": "/runs/case-1"}, "/runs/case-1"),
])
def test_the_settings_folder_follows_the_platform_and_the_override(platform: str, env: dict[str, str],
                                                                    expected: str) -> None:
    assert st.config_dir(env, platform) == Path(expected)


def test_the_shared_rule_names_every_setting_and_every_choice() -> None:
    """author-priorities.md tells every skill how to decide; it must offer the same choices the script accepts."""
    rule = " ".join(PRIORITIES.read_text(encoding="utf-8").split())
    for key, setting in st.SETTINGS.items():
        assert f"`{key}`" in rule
        for choice in setting.options:
            assert f"`{choice}`" in rule, choice
    assert "settings.py resolve --json" in rule
    assert "settings.py questions" in rule and "settings.py set" in rule
