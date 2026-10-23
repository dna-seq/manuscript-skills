#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6"]
# ///
"""User-wide defaults for manuscript skills; saved manuscript-project choices take precedence.

Use project.py for ordinary skill startup and project preferences. Project setup copies the choices saved
here into a new project once; later changes here do not silently replace a manuscript's saved choices.
Use this script to change an explicitly global preference, or to inspect defaults for new projects.
The precedence and run-artifact contract live in ../references/author-priorities.md and project-workflow.md.

    uv run --script settings.py show                 # every setting, its value or "not set", and the file
    uv run --script settings.py get reports          # the value; prints "not set" and exits 1 when unset
    uv run --script settings.py resolve --json       # effective saved choices or defaults, without questions
    uv run --script settings.py set reports chat     # save a choice the authors stated
    uv run --script settings.py set edits conservative
    uv run --script settings.py set keep results     # pack a finished run's evidence into one archive
    uv run --script settings.py unset reports        # forget it; the default applies until chosen again
    uv run --script settings.py questions [--json]   # the one-time question for each setting not yet chosen

The file is `$MANUSCRIPT_SKILLS_CONFIG/settings.yaml` when that variable names a folder (evals and tests set it
so that runs do not share a choice), else `settings.yaml` in the platform's configuration folder for
`manuscript-skills` (`~/.config/manuscript-skills/` on Linux). Keys this version does not know are kept.

Exit codes: 0 done; 1 `get` on a setting that is not set; 2 an unknown setting or value, or a settings file
that is not a YAML mapping (fix or delete it; it is never overwritten).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

app = typer.Typer(add_completion=False, no_args_is_help=True)

ENV_DIR = "MANUSCRIPT_SKILLS_CONFIG"
APP_DIR = "manuscript-skills"
HEADER = ("# manuscript-skills settings: global defaults, overridden by saved manuscript-project choices.\n"
          "# Change one with `settings.py set KEY VALUE`, or edit this file.\n")


@dataclass(frozen=True)
class Setting:
    question: str
    options: dict[str, str]  # value -> what choosing it means, in the authors' terms
    default: str  # effective when unset, and the recommended answer; using it does not save it
    why: str  # why the default is recommended, said with the question


SETTINGS: dict[str, Setting] = {
    "reports": Setting(
        question="Where should the manuscript skills put their reports (reviews, audits, check results)?",
        options={
            "file": "Save each report in the manuscript project's run folder, and give the "
                    "headline and the most urgent points in the chat.",
            "chat": "Show each report in full in the chat; retain the project's inspectable run evidence too.",
            "both": "Save the file, and also show the full report in the chat.",
        },
        default="file",
        why="The chat stays short enough to follow, and the full reports are saved where you and your co-authors "
            "can open them. Consequential before/after changes are shown in the chat whatever you choose.",
    ),
    "edits": Setting(
        question="Which manuscript changes may the skills apply without your approval? "
                 "Independent checks and permitted edits continue while proposals await your decision.",
        options={
            "conservative": "Apply routine corrections that preserve meaning; propose changes to arguments, "
                            "claims, emphasis, numerical content and substantial structure for approval.",
            "propose": "Prepare all changes to your documents as proposals and apply them only after approval; "
                       "continue checks and prepare the report.",
            "apply": "Apply substantive changes within the requested scope, showing consequential changes "
                     "before and after in the chat; never invent facts or decisions.",
        },
        default="conservative",
        why="Routine fixes save you work, and nothing that changes what the paper claims, reports or "
            "emphasises is applied without your approval.",
    ),
    "keep": Setting(
        question="When a run ends, which of its files should stay in the run folder?",
        options={
            "everything": "Keep every file the run produced: each referee's and reader's report, every check "
                          "and its output, the commands that ran and the before/after of each edit.",
            "results": "Keep the run index, each skill's report, the dashboard and the corrected version, and "
                       "pack everything else into one evidence.zip in the same folder. Nothing is deleted, and "
                       "a run that continues unpacks it first.",
        },
        default="everything",
        why="The intermediate files are how the work holds together: a resumed run and the dashboard read what "
            "earlier steps kept instead of repeating them, and every finding can be traced to the check, "
            "referee or reader behind it. Choose results if you only want to see the outcome.",
    ),
}


class SettingsError(ValueError):
    """An unknown setting or value, or a settings file that cannot be read safely."""


def config_dir(env: dict[str, str] | None = None, platform: str | None = None) -> Path:
    """The folder holding settings.yaml: $MANUSCRIPT_SKILLS_CONFIG, else the platform's configuration folder."""
    env = dict(os.environ) if env is None else env
    platform = sys.platform if platform is None else platform
    if env.get(ENV_DIR):
        return Path(env[ENV_DIR]).expanduser()
    home = Path(env.get("HOME") or env.get("USERPROFILE") or Path.home())
    if platform.startswith("win"):
        return Path(env.get("APPDATA") or home / "AppData" / "Roaming") / APP_DIR
    if platform == "darwin":
        return home / "Library" / "Application Support" / APP_DIR
    return Path(env.get("XDG_CONFIG_HOME") or home / ".config") / APP_DIR


def settings_path() -> Path:
    return config_dir() / "settings.yaml"


def load(path: Path) -> dict[str, Any]:
    """Every key in the file, known or not. A missing or empty file is no settings at all."""
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SettingsError(f"{path} is not valid YAML ({exc}); fix or delete it.") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise SettingsError(f"{path} does not hold a mapping of settings; fix or delete it.")
    return data


def _check(key: str, value: str | None = None) -> Setting:
    if key not in SETTINGS:
        raise SettingsError(f"There is no setting '{key}'; the settings are {', '.join(SETTINGS)}.")
    setting = SETTINGS[key]
    if value is not None and value not in setting.options:
        raise SettingsError(f"'{value}' is not a choice for {key}; choose {', '.join(setting.options)}.")
    return setting


def value(data: dict[str, Any], key: str) -> str | None:
    """The saved choice for a known setting, or None when it is not set or not one of its choices."""
    setting = _check(key)
    raw = data.get(key)
    return raw if isinstance(raw, str) and raw in setting.options else None


def effective(data: dict[str, Any]) -> dict[str, str]:
    """Saved choices or defaults for starting work without a settings interview; never writes a file."""
    return {key: value(data, key) or setting.default for key, setting in SETTINGS.items()}


def save(path: Path, data: dict[str, Any]) -> None:
    """Write the whole mapping atomically, so an interrupted write never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = HEADER + yaml.safe_dump(data, sort_keys=True, allow_unicode=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False,
                                     prefix=".settings-", suffix=".yaml") as tmp:
        tmp.write(body)
    os.replace(tmp.name, path)


def put(path: Path, key: str, new: str | None) -> dict[str, Any]:
    """Set (or, with None, remove) one setting and keep every other key, known or not."""
    _check(key, new)
    data = load(path)
    if new is None:
        data.pop(key, None)
    else:
        data[key] = new
    save(path, data)
    return data


def questions(data: dict[str, Any], every: bool = False) -> list[dict[str, Any]]:
    """The one-time question for each setting not yet chosen (every setting with every=True)."""
    out = []
    for key, setting in SETTINGS.items():
        current = value(data, key)
        if current is None or every:
            out.append({"key": key, "question": setting.question, "current": current, "default": setting.default,
                        "recommended": setting.default, "why": setting.why,
                        "options": [{"value": v, "meaning": m} for v, m in setting.options.items()]})
    return out


def _fail(exc: SettingsError) -> None:
    typer.echo(str(exc), err=True)
    raise typer.Exit(code=2)


@app.command()
def show(as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output")] = False) -> None:
    """Every setting with its value or "not set", and where the file is."""
    path = settings_path()
    try:
        data = load(path)
    except SettingsError as exc:
        _fail(exc)
    rows = {key: value(data, key) for key in SETTINGS}
    if as_json:
        typer.echo(json.dumps({"file": str(path), "settings": rows}, indent=2))
        return
    typer.echo(f"Settings file: {path}" + ("" if path.is_file() else " (not created yet)"))
    for key, current in rows.items():
        meaning = SETTINGS[key].options[current] if current else f"not set; default: {SETTINGS[key].default}"
        typer.echo(f"- {key}: {current or 'not set'}. {meaning}")


@app.command()
def get(key: str) -> None:
    """Print one setting's value; print "not set" and exit 1 when it has none."""
    try:
        current = value(load(settings_path()), key)
    except SettingsError as exc:
        _fail(exc)
    typer.echo(current or "not set")
    if current is None:
        raise typer.Exit(code=1)


@app.command()
def resolve(as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output")] = False) -> None:
    """Effective choices and their sources, for every skill to read before work; no questions or writes."""
    path = settings_path()
    try:
        data = load(path)
    except SettingsError as exc:
        _fail(exc)
    choices = effective(data)
    sources = {key: "saved" if value(data, key) is not None else "default" for key in SETTINGS}
    if as_json:
        typer.echo(json.dumps({"file": str(path), "effective": choices, "sources": sources}, indent=2))
        return
    typer.echo(f"Settings file: {path}")
    for key, current in choices.items():
        typer.echo(f"- {key}: {current} ({sources[key]}). {SETTINGS[key].options[current]}")


@app.command("set")
def set_(key: str, new: str) -> None:
    """Save an explicitly global default; use project.py configure for a manuscript-only choice."""
    path = settings_path()
    try:
        put(path, key, new)
    except SettingsError as exc:
        _fail(exc)
    typer.echo(f"Saved {key}: {new} in {path}. {SETTINGS[key].options[new]}")


@app.command()
def unset(key: str) -> None:
    """Forget a saved setting; its default applies until the authors choose again."""
    path = settings_path()
    try:
        put(path, key, None)
    except SettingsError as exc:
        _fail(exc)
    typer.echo(f"Removed {key} from {path}; default: {SETTINGS[key].default}.")


@app.command("questions")
def questions_cmd(
    every: Annotated[bool, typer.Option("--all", help="Include settings already chosen (to change them)")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output, for a question tool")] = False,
) -> None:
    """The one-time question for each setting not yet chosen: ask them all in one round."""
    try:
        items = questions(load(settings_path()), every)
    except SettingsError as exc:
        _fail(exc)
    if as_json:
        typer.echo(json.dumps(items, indent=2))
        return
    if not items:
        typer.echo("Every setting is chosen; nothing to ask.")
        return
    for q in items:
        typer.echo(f"{q['key']}: {q['question']}")
        for o in q["options"]:
            mark = " (default)" if o["value"] == q["default"] else ""
            typer.echo(f"  - {o['value']}{mark}: {o['meaning']}")


if __name__ == "__main__":
    app()
