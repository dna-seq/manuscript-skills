# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6"]
# ///
"""Stage one behavioural case: its files in an empty folder outside the checkout, under neutral names.

A fixture's name says which condition it is (seeded.md, clean.md, edited-seeded.md, a seeded/ folder), and an
agent that reads the name knows what to look for. This copies each file of a case into a new folder outside the
repository, with "seeded" and "clean" taken out of every file and folder name (seeded.md becomes manuscript.md,
edited-clean.md edited.md, paper-v2-seeded.md paper-v2.md, a seeded/ or clean/ folder paper/), and rewrites the
file names in the prompt the same way. In the copied text files, file names are rewritten too, and a comment that
calls the file a fixture or names its condition is blanked, keeping its lines so cited line numbers still hold.
The case's `settings` go to a separate folder for MANUSCRIPT_SKILLS_CONFIG.

    uv run --script evals/stage.py peer-review-seeded-01                  # into a new temporary folder
    uv run --script evals/stage.py peer-review-seeded-01 --to /tmp/run-1  # an empty folder outside the checkout
    uv run --script evals/stage.py --list                                  # every case with its staged file names

It prints the working folder, the MANUSCRIPT_SKILLS_CONFIG folder and the prompt to give the agent. Nothing
else from the case (what was planted, the rubric) leaves the case file.

Exit codes: 0 staged, 2 an unknown case or an unusable destination.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
import yaml

EVALS = Path(__file__).resolve().parent
ROOT = EVALS.parent
CONDITIONS = {"seeded", "clean"}
# A file name in a prompt: a path-like token with a condition word in it ("seeded/paper.md", "edited-clean.md.").
PROMPT_NAME = re.compile(r"[\w./-]*(?:seeded|clean)[\w./-]*", re.IGNORECASE)
# A comment in a staged file that tells the agent it is reading a test: blanked, keeping its lines.
LEAK = re.compile(r"fixture|seeded|planted|\bevals?\b", re.IGNORECASE)
COMMENT = {".yaml": "#", ".yml": "#", ".toml": "#", ".py": "#", ".tex": "%", ".bib": "%"}
TEXT = {".md", ".html", ".htm", ".txt", ".tex", ".bib", ".yaml", ".yml", ".toml", ".json", ".csv", ".py", ".r"}

app = typer.Typer(add_completion=False, no_args_is_help=True)


def load_cases() -> dict[str, dict[str, Any]]:
    """Every case in evals/*.yaml by id."""
    cases: dict[str, dict[str, Any]] = {}
    for path in sorted(EVALS.glob("*.yaml")):
        for case in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            cases[str(case["id"])] = case
    return cases


def neutral(name: str, is_dir: bool) -> str:
    """One file or folder name without its condition word: seeded/ and clean/ become paper/, edited-seeded.md
    edited.md, and seeded.md, with nothing left, manuscript.md."""
    if is_dir:
        return "paper" if name.lower() in CONDITIONS else name
    stem, suffix = (name.rsplit(".", 1)[0], "." + name.rsplit(".", 1)[1]) if "." in name else (name, "")
    kept = [part for part in re.split(r"[-_]", stem) if part.lower() not in CONDITIONS]
    if len(kept) == len(re.split(r"[-_]", stem)):
        return name  # no condition word: the name stays as written
    return ("-".join(kept) or "manuscript") + suffix


def staged_path(entry: str) -> str:
    """Where a case's file goes in the working folder: its path below fixtures/<skill>/, each part neutral."""
    parts = [p for p in entry.split("/") if p]
    if parts[:1] == ["fixtures"]:
        parts = parts[2:]
    is_dir = entry.endswith("/")
    names = [neutral(p, is_dir=(n < len(parts) - 1 or is_dir)) for n, p in enumerate(parts)]
    return "/".join(names) + ("/" if is_dir else "")


def staged_prompt(prompt: str) -> str:
    """The prompt with every file or folder name made neutral; a plain word ("we'll clean it") stays."""
    def swap(m: re.Match[str]) -> str:
        token = m.group(0)
        core = token.rstrip(".,;:")
        tail = token[len(core):]
        if "/" not in core and "." not in core:
            return token
        parts = core.split("/")
        names = [neutral(p, is_dir=(n < len(parts) - 1 or "." not in p)) if p else p for n, p in enumerate(parts)]
        return "/".join(names) + tail
    return PROMPT_NAME.sub(swap, prompt)


def scrub(text: str, suffix: str) -> str:
    """A text file as the agent should see it: a comment that calls it a fixture or names its condition is blanked
    (its lines kept, so the line numbers the cases cite still hold), and file names in it are made neutral."""
    def blank(m: re.Match[str]) -> str:
        return "\n" * m.group(0).count("\n") if LEAK.search(m.group(0)) else m.group(0)
    if suffix in (".md", ".html", ".htm"):
        text = re.sub(r"<!--.*?-->", blank, text, flags=re.DOTALL)
    marker = COMMENT.get(suffix)
    if marker:
        text = "\n".join("" if line.lstrip().startswith(marker) and LEAK.search(line) else line
                         for line in text.split("\n"))
    return staged_prompt(text)


def _copy(source: Path, dest: Path) -> None:
    """Copy a file, or a folder with every name inside it made neutral; text files pass through scrub()."""
    if source.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir()):
            _copy(child, dest / neutral(child.name, child.is_dir()))
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in TEXT:
        dest.write_text(scrub(source.read_text(encoding="utf-8"), source.suffix.lower()), encoding="utf-8")
    else:
        shutil.copy2(source, dest)


def stage(case: dict[str, Any], to: Optional[Path] = None) -> dict[str, Any]:
    """Copy the case's files to `to`/work under neutral names and its settings to `to`/config. `to` must be outside
    the checkout and empty (a new temporary folder when not given). Returns the folders, the file map and the
    prompt to give the agent."""
    if to is None:
        to = Path(tempfile.mkdtemp(prefix="manuscript-skills-eval-"))
    to = to.resolve()
    if to == ROOT or ROOT in to.parents:
        raise ValueError(f"{to} is inside the repository; stage the case outside it, so the agent cannot read the "
                         "case files or the fixtures' real names")
    if to.exists() and any(to.iterdir()):
        raise ValueError(f"{to} is not empty; give a new or empty folder")
    work, config = to / "work", to / "config"
    work.mkdir(parents=True)
    config.mkdir()
    files: dict[str, str] = {}
    for entry in case.get("files") or []:
        target = staged_path(entry)
        if target in files.values():
            raise ValueError(f"two files of {case['id']} would both be staged as {target}")
        _copy(EVALS / entry, work / target)
        files[entry] = target
    if case.get("settings"):
        (config / "settings.yaml").write_text(yaml.safe_dump(case["settings"], sort_keys=False), encoding="utf-8")
    return {"work": work, "config": config, "files": files, "prompt": staged_prompt(str(case["prompt"]))}


@app.command()
def main(
    case_id: Annotated[Optional[str], typer.Argument(help="The case to stage, as its id in evals/*.yaml")] = None,
    to: Annotated[Optional[Path], typer.Option("--to", file_okay=False, help="An empty folder outside the checkout "
                                               "(default: a new temporary folder)")] = None,
    list_cases: Annotated[bool, typer.Option("--list", help="List every case with its staged file names")] = False,
) -> None:
    cases = load_cases()
    if list_cases:
        for cid, case in cases.items():
            typer.echo(f"{cid}: " + ", ".join(staged_path(e) for e in case.get("files") or []))
        return
    if case_id is None or case_id not in cases:
        typer.echo(f"No case {case_id!r}; --list shows the ids.", err=True)
        raise typer.Exit(code=2)
    try:
        staged = stage(cases[case_id], to)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2)
    typer.echo(f"Working folder: {staged['work']}")
    typer.echo(f"MANUSCRIPT_SKILLS_CONFIG={staged['config']}")
    typer.echo("Prompt:\n\n" + staged["prompt"].strip())


if __name__ == "__main__":
    app()
