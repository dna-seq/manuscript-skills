#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6"]
# ///
"""Persistent manuscript-project context, shared by every skill.

`resolve PAPER --json` discovers the nearest .manuscript-skills.yaml without writing.
`configure ROOT ...` saves answers once; repeat it only for explicit lasting changes.
Conversation overrides on resolve affect this invocation, never the saved configuration.

`questions` are the locations a run cannot start without. `preferences` are the settings nobody has chosen
for this project (here or globally), each with its recommended answer and why: ask them in the same
first-use batch, but never wait for them, since their defaults are safe. A setting reaches the project
file only as an answer: setup copies the choices saved globally, never the defaults.

A global settings file that cannot be read never stops the work: `resolve` still answers `ready` when the
project is, with `settings_error`, `edits: propose` and `versions: immutable` unless this manuscript or the
conversation chose otherwise (nothing is applied or replaced on a choice nobody can read), and the repair as one
item of `decisions`. The file is kept.

A connected (remote) manuscript is read through a local reading copy, an export of the connected document:
`configure ROOT --manuscript URL --reading-copy FILE` saves where that export is kept (one `--reading-copy` per
remote `--manuscript`, in the same order), and `runs.py start` snapshots it with the connected version.

Paths in the saved file and in the JSON output use forward slashes on every platform.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

import typer
import yaml

import settings

app = typer.Typer(add_completion=False, no_args_is_help=True)
CONFIG = ".manuscript-skills.yaml"
PEER_REVIEW = ("auto", "on-request", "off")
OUTPUT_DIR = "reviews"
# A seat on another model, run by manuscript-other-models: a CLI, or a CLI and the model it should use.
OTHER_MODEL = re.compile(r"[a-z][a-z0-9-]*(/[\w.:@\[\]-]+)?")
OUTPUT_WHY = ("A reviews/ folder in the manuscript's folder keeps every run with the paper: you and your co-authors "
              "find the reports where the paper is, and later runs and the next revision can reuse them.")


class ProjectError(ValueError):
    """An unreadable or inconsistent manuscript-project mapping."""


def is_remote(location: str) -> bool:
    return urlparse(location).scheme in {"https", "http", "doi", "s3", "gs"}


def local_path(root: Path, location: str) -> Path:
    path = Path(location).expanduser()
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def stored_location(root: Path, location: str) -> str:
    """How a location is saved: a URL as it is, a local path relative to the project folder with forward
    slashes, or absolute when it is on another drive (Windows) and has no relative path."""
    if is_remote(location):
        return location
    path = local_path(root, location)
    try:
        return Path(os.path.relpath(path, root)).as_posix()
    except ValueError:  # Windows: another drive than the project's
        return path.as_posix()


def posix(path: Path | None) -> str | None:
    return path.as_posix() if path is not None else None


def config_path(target: str, project: Path | None = None) -> Path:
    if project is not None:
        selected = project.expanduser().resolve()
        return selected if selected.name == CONFIG else selected / CONFIG
    if is_remote(target):
        raise ProjectError("A connected manuscript URL needs --project pointing to its local project folder.")
    path = Path(target).expanduser().resolve()
    folder = path if path.is_dir() else path.parent
    for candidate in (folder, *folder.parents):
        if (candidate / CONFIG).is_file():
            return candidate / CONFIG
    return folder / CONFIG


def read(path: Path) -> dict[str, Any]:
    try:
        data = settings.load(path)
    except (settings.SettingsError, OSError) as exc:
        raise ProjectError(str(exc)) from exc
    if not data:
        return {}
    if data.get("schema_version") != 1:
        raise ProjectError(f"{path}: unsupported project schema_version; preserve the file and resolve the conflict.")
    for key in ("manuscripts", "code_roots", "connected_documents", "related_manuscripts", "readers", "referees"):
        if key not in data or (key == "code_roots" and data[key] is None):
            continue
        if not isinstance(data[key], list) or any(not isinstance(v, str) or not v.strip() for v in data[key]):
            raise ProjectError(f"{path}: {key} must be a list of non-empty locations.")
    if "other_models" in data and (not isinstance(data["other_models"], list)
                                   or any(not isinstance(v, str) or not OTHER_MODEL.fullmatch(v) for v in data["other_models"])):
        raise ProjectError(f"{path}: other_models must be a list of CLI or CLI/MODEL names, such as codex/gpt-5.6-sol.")
    if "manuscripts" in data and not data["manuscripts"]:
        raise ProjectError(f"{path}: manuscripts cannot be empty.")
    for key in ("output_dir", "output_url"):
        if key in data and (not isinstance(data[key], str) or not data[key].strip()):
            raise ProjectError(f"{path}: {key} must be a non-empty location.")
    copies = data.get("reading_copies", {})
    if not isinstance(copies, dict) or any(not isinstance(k, str) or not is_remote(k) or not isinstance(v, str)
                                           or not v.strip() or is_remote(v) for k, v in copies.items()):
        raise ProjectError(f"{path}: reading_copies must map each connected manuscript's URL to a local file.")
    if data.get("output_dir") and is_remote(data["output_dir"]):
        raise ProjectError("output_dir must be a local working folder; record a cloud destination as output_url.")
    choices = data.get("settings", {})
    if not isinstance(choices, dict):
        raise ProjectError(f"{path}: settings must be a mapping.")
    for key in settings.SETTINGS:
        if key in choices and settings.value(choices, key) is None:
            raise ProjectError(f"{path}: invalid project setting {key}: {choices[key]!r}.")
    if "peer_review" in choices and choices["peer_review"] not in PEER_REVIEW:
        raise ProjectError(f"{path}: peer_review must be one of {', '.join(PEER_REVIEW)}.")
    return data


def write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False,
                                     prefix=".project-", suffix=".yaml") as handle:
        handle.write("# Manuscript Skills: choices for this manuscript project.\n")
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)
    os.replace(handle.name, path)


def context(target: str, project: Path | None = None, overrides: dict[str, str] | None = None) -> dict[str, Any]:
    path = config_path(target, project)
    data = read(path)
    # An unreadable global file never stops the work: its keys fall back to the safe choices, and its repair is
    # one decision for the authors (author-priorities.md, "Resolve the manuscript project before work").
    global_file = settings.settings_path()
    global_data, settings_error = settings.load_or_error(global_file)
    effective = settings.effective(global_data, unreadable=settings_error is not None) | {"peer_review": "auto"}
    sources = {key: "global" if settings.value(global_data, key) else
               "settings_error" if settings_error and key in settings.WHEN_UNREADABLE else "default"
               for key in settings.SETTINGS}
    sources["peer_review"] = "default"
    for key, choice in data.get("settings", {}).items():
        if key in effective:
            effective[key], sources[key] = choice, "project"
    for key, choice in (overrides or {}).items():
        if key == "peer_review":
            if choice not in PEER_REVIEW:
                raise ProjectError(f"Invalid peer_review override: {choice}.")
        else:
            try:
                settings._check(key, choice)
            except settings.SettingsError as exc:
                raise ProjectError(str(exc)) from exc
        effective[key], sources[key] = choice, "conversation"
    questions = []
    for key, question in (
        ("manuscripts", "Which files or connected documents are the authoritative manuscript and supplements?"),
        ("code_roots", "Which code repositories are connected? None or unknown are valid answers."),
        ("output_dir", f"Where should inspectable skill runs be saved? Recommended: {OUTPUT_DIR}/ in the manuscript's folder."),
    ):
        if key not in data:
            questions.append({"key": key, "question": question}
                             | ({"recommended": OUTPUT_DIR, "why": OUTPUT_WHY} if key == "output_dir" else {}))
    saved = data.get("settings", {})
    preferences = [q for q in settings.questions(global_data) if q["key"] not in saved]
    issues = []
    root = path.parent
    requested = target if is_remote(target) else str(Path(target).expanduser().resolve())
    configured = [v if is_remote(v) else str(local_path(root, v)) for v in data.get("manuscripts", [])]
    configured += [str(local_path(root, v)) for v in data.get("reading_copies", {}).values()]  # a connected one's export
    if configured and requested not in configured:
        issues.append({"scope": "manuscript", "message": "Requested manuscript is not in this project's saved sources; confirm the mapping."})
    for key in ("manuscripts", "code_roots"):
        for location in data.get(key) or []:
            if is_remote(location):
                continue
            local = local_path(root, location)
            if not local.exists():
                issues.append({"scope": key, "message": f"Saved location is missing: {local}"})
            elif key == 'manuscripts' and not local.is_file():
                issues.append({"scope": key, "message": f"Select the authoritative source file inside this manuscript folder: {local}"})
    output = local_path(root, data["output_dir"]) if data.get("output_dir") else None
    if output:
        ancestor = output
        while not ancestor.exists():
            ancestor = ancestor.parent
        if not ancestor.is_dir() or not os.access(ancestor, os.W_OK):
            issues.append({"scope": "output_dir", "message": f"Output folder cannot be used: {output}"})
    decisions = [settings.repair_decision(global_file, settings_error, proposing=sources["edits"] == "settings_error")
                 ] if settings_error else []
    return {"status": "conflict" if issues else "setup_required" if questions else "ready",
            "project_file": posix(path), "project_root": posix(root), "project": data,
            "effective": effective, "sources": sources, "output_dir": posix(output),
            "questions": questions, "preferences": preferences, "issues": issues,
            "settings_error": settings_error, "decisions": decisions}


@app.command()
def resolve(
    target: str,
    project: Annotated[Path | None, typer.Option(help="Explicit manuscript-project folder")] = None,
    reports: str | None = None,
    edits: str | None = None,
    versions: str | None = None,
    keep: str | None = None,
    peer_review: str | None = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Read the project, effective settings and only genuinely missing setup questions. Never writes."""
    overrides = {k: v for k, v in {"reports": reports, "edits": edits, "versions": versions, "keep": keep,
                                    "peer_review": peer_review}.items() if v is not None}
    try:
        result = context(target, project, overrides)
    except ProjectError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False) if as_json
               else yaml.safe_dump(result, sort_keys=False, allow_unicode=True))
    if result["issues"]:
        raise typer.Exit(3)


@app.command()
def configure(
    root: Path,
    manuscript: Annotated[list[str] | None, typer.Option("--manuscript")] = None,
    code: Annotated[list[str] | None, typer.Option("--code")] = None,
    no_code: bool = False,
    unknown_code: bool = False,
    output_dir: Path | None = None,
    output_url: str | None = None,
    document: Annotated[list[str] | None, typer.Option("--document")] = None,
    reading_copy: Annotated[list[str] | None, typer.Option(
        "--reading-copy", help="Where the local export of a connected (URL) manuscript is kept: one per URL "
                               "--manuscript, in the same order; repeat")] = None,
    related_manuscript: Annotated[list[str] | None, typer.Option("--related-manuscript")] = None,
    reader: Annotated[list[str] | None, typer.Option("--reader", help="A reader seat for manuscript-story, e.g. 'clinician: orders genetic tests'; repeat")] = None,
    referee: Annotated[list[str] | None, typer.Option("--referee", help="An extra referee seat for manuscript-peer-review; repeat")] = None,
    default_panels: Annotated[bool, typer.Option("--default-panels", help="Forget saved readers and referees")] = False,
    other_model: Annotated[list[str] | None, typer.Option("--other-model", help="Also run the panels' seats on this CLI, or CLI/MODEL (manuscript-other-models); repeat")] = None,
    one_model: Annotated[bool, typer.Option("--one-model", help="Forget the other models: seats run on the host only")] = False,
    reports: str | None = None,
    edits: str | None = None,
    versions: str | None = None,
    keep: str | None = None,
    peer_review: str | None = None,
) -> None:
    """Save stated project choices. Omitted fields survive; use only for explicit lasting choices."""
    path = config_path(str(root), root)
    try:
        if sum((bool(code), no_code, unknown_code)) > 1:
            raise ProjectError("Choose --code, --no-code or --unknown-code, not more than one.")
        data = read(path)
        data.setdefault("schema_version", 1)
        if manuscript is not None:
            data["manuscripts"] = [stored_location(path.parent, v) for v in manuscript]
            # A connected source that is no longer listed loses its saved reading copy.
            kept = {k: v for k, v in data.get("reading_copies", {}).items() if k in data["manuscripts"]}
            data["reading_copies"] = kept
        if reading_copy:
            remote = [v for v in data.get("manuscripts", []) if is_remote(v)]
            if len(reading_copy) > len(remote):
                raise ProjectError(f"{len(reading_copy)} reading copies for {len(remote)} connected manuscript(s); "
                                   "give one --reading-copy per URL --manuscript, in the same order.")
            data["reading_copies"] = data.get("reading_copies", {}) | {
                url: stored_location(path.parent, copy) for url, copy in zip(remote, reading_copy)}
        if not data.get("reading_copies"):
            data.pop("reading_copies", None)
        if code is not None or no_code or unknown_code:
            data["code_roots"] = None if unknown_code else [stored_location(path.parent, v) for v in code or []]
        if output_dir is not None:
            data["output_dir"] = stored_location(path.parent, str(output_dir))
        if output_url is not None:
            data["output_url"] = output_url
        for key, locations in (("connected_documents", document), ("related_manuscripts", related_manuscript)):
            if locations is not None:
                data[key] = [stored_location(path.parent, v) for v in locations]
        if default_panels:
            data.pop("readers", None)
            data.pop("referees", None)
        if other_model and one_model:
            raise ProjectError("Choose --other-model or --one-model, not both.")
        if one_model:
            data.pop("other_models", None)
        if other_model:
            if bad := [v for v in other_model if not OTHER_MODEL.fullmatch(v.strip())]:
                raise ProjectError(f"Not a CLI or CLI/MODEL name: {', '.join(bad)} (for example codex/gpt-5.6-sol).")
            data["other_models"] = list(dict.fromkeys(v.strip() for v in other_model))
        for key, seats, limit in (("readers", reader, 8), ("referees", referee, 2)):
            if seats:
                if len(seats) > limit:
                    raise ProjectError(f"At most {limit} {key}: every seat reads the whole paper.")
                data[key] = [seat.strip() for seat in seats]
        if "settings" not in data:  # a new project starts from the choices saved globally, never the defaults
            global_data, settings_error = settings.load_or_error(settings.settings_path())
            if settings_error:  # nothing to copy; the setup goes on and the file is kept as it is
                typer.echo(f"{settings_error} No global choice was copied into this project.", err=True)
            data["settings"] = {key: settings.value(global_data, key) for key in settings.SETTINGS
                                if settings.value(global_data, key)}
        choices = data["settings"]
        for key, choice in {"reports": reports, "edits": edits, "versions": versions, "keep": keep,
                            "peer_review": peer_review}.items():
            if choice is None:
                continue
            if key == "peer_review":
                if choice not in PEER_REVIEW:
                    raise ProjectError(f"peer_review must be one of {', '.join(PEER_REVIEW)}.")
            else:
                settings._check(key, choice)
            choices[key] = choice
        if not choices:
            data.pop("settings")
        write(path, data)
    except (ProjectError, settings.SettingsError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    typer.echo(path.as_posix())


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 whatever the console's code page (Windows)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
