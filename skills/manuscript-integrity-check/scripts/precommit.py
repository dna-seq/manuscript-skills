#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "httpx>=0.27", "pydantic>=2.6", "pyyaml>=6"]
# ///
"""Pre-commit check for manuscript files: the offline integrity scan plus the style profile.

Without --advisory, fails on mechanical blockers (chatbot leftovers or a recorded venue return limit).
With --strict it also fails on
major findings; with --max-smells it fails when a file's smell density passes the threshold. Offline: no
reference resolution and no third-party detectors (run those by hand, see the skills).

    uv run --script precommit.py paper.md [more files] [--venue KEY] [--strict] [--max-smells 8]

As a pre-commit hook (in the manuscript repository's .pre-commit-config.yaml):

    - repo: https://github.com/dna-seq/manuscript-skills
      rev: main
      hooks:
        - id: manuscript-check
          files: ^docs/manuscript/.*\\.(md|tex)$
          args: [--venue, <venue-key>]
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Annotated, Optional

import typer

HERE = Path(__file__).resolve().parent
app = typer.Typer(add_completion=False)


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # pydantic resolves deferred annotations through sys.modules
    spec.loader.exec_module(module)
    return module


@app.command()
def main(
    files: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False, readable=True)],
    venue: Annotated[Optional[str], typer.Option(help="Venue key for length limits")] = None,
    strict: Annotated[bool, typer.Option(help="Also fail on major findings")] = False,
    advisory: Annotated[bool, typer.Option(help="Report findings without blocking the commit")] = False,
    max_smells: Annotated[Optional[float], typer.Option(help="Fail when smells per 1000 words exceed this")] = None,
    show: Annotated[int, typer.Option(help="Findings to print per file")] = 8,
) -> None:
    scan = _load("scan", HERE / "scan.py")
    profile = _load("style_profile", HERE.parents[1] / "manuscript-journal-adapt" / "scripts" / "style_profile.py")
    smells, kobak = profile.load_smells(), profile.load_kobak()
    failed = False
    for path in files:
        report = scan.scan(path, online=False, search_unidentified=False, venue=venue)
        worst = [f for f in report.findings if f.severity in (scan.Severity.blocker, scan.Severity.major)]
        blockers = sum(f.severity == scan.Severity.blocker for f in report.findings)
        majors = len(worst) - blockers
        prof = profile.profile_text(path.read_text(encoding="utf-8"), path.suffix == ".tex", smells, kobak)
        density = prof["metrics"]["smells_per_1000_words"]
        typer.echo(f"{path}: {blockers} blocker, {majors} major; {density} smells per 1000 words")
        for f in worst[:show]:
            typer.echo(f"  {f.severity.value:7} L{f.line or '-'} {f.check}: {f.message}")
        ranked = sorted((p for p in prof["paragraphs"] if p["hits"]), key=lambda p: -p["smells_per_100_words"])[:3]
        for p in ranked:
            typer.echo(f"  smells  L{p['line']}: " + ", ".join(f"{sid}×{len(v)}" for sid, v in p["hits"].items()))
        if blockers or (strict and majors) or (max_smells is not None and density > max_smells):
            failed = True
    if failed and not advisory:
        typer.echo("Manuscript check failed. Full reports: scan.py FILE --online, style_profile.py FILE.", err=True)
    raise typer.Exit(code=1 if failed and not advisory else 0)


if __name__ == "__main__":
    app()
