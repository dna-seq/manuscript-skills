#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "httpx>=0.27", "pydantic>=2.6", "pyyaml>=6"]
# ///
"""Pre-commit check for manuscript files: the offline integrity scan plus the style profile.

Without --advisory, fails on serious findings in the current work (chatbot leftovers or a recorded venue return
limit). With --strict it also fails on important (major) ones; with --max-smells it fails when a file's smell density
passes the threshold. Items for the last step before submission (statements, archives, placeholders) are listed in a
count and never fail the hook unless --final says the authors are about to submit. Offline: no reference resolution
and no third-party detectors (run those by hand, see the skills).

--hygiene also lists what the submission-package check (hygiene.py) finds in the file itself: LaTeX
comments with content, hidden text and prompts aimed at AI reviewers, secrets. These lines are advisory:
they never change the exit code, because a draft legitimately carries comments until it is submitted.

    uv run --script precommit.py paper.md [more files] [--venue KEY] [--strict] [--max-smells 8] [--hygiene] [--final]

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


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _times(n: int) -> str:
    return {1: "once", 2: "twice"}.get(n, f"{n} times")


def finding_line(scan: ModuleType, f: object) -> str:
    """One scan finding for the terminal, in sentences: how serious, when it can be fixed, what and where."""
    stage = scan.STAGE_TITLES[scan.Stage(f.stage or "now")].split(":")[0].lower()
    return f"  - {scan.SEVERITY_LEAD[f.severity]} ({stage}): " + " ".join(
        part for part in (scan._sentence(f.message), scan._place_sentence(f)) if part)


def pattern_line(profile: ModuleType, smells: dict, p: dict) -> str:
    """A paragraph dense in writing patterns, named by its section and line, each pattern by its catalogue name."""
    found = [f"{smells[sid]['name'] if sid in smells else sid} ({sid}), {_times(len(v))}"
             for sid, v in p["hits"].items()]
    return (f"  - In {profile.place(p.get('section', ''), 'line ' + str(p['line']))}, a paragraph has "
            f"{p['smells_per_100_words']} writing patterns for every 100 words: " + "; ".join(found) + ".")


@app.command()
def main(
    files: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False, readable=True)],
    venue: Annotated[Optional[str], typer.Option(help="Venue key for length limits")] = None,
    strict: Annotated[bool, typer.Option(help="Also fail on important (major) findings")] = False,
    advisory: Annotated[bool, typer.Option(help="Report findings without blocking the commit")] = False,
    max_smells: Annotated[Optional[float], typer.Option(help="Fail when smells per 1000 words exceed this")] = None,
    show: Annotated[int, typer.Option(help="Findings to print per file")] = 8,
    hygiene: Annotated[bool, typer.Option(help="Also list comments, hidden text and secrets in the file "
                                               "(advisory: never fails the commit)")] = False,
    final: Annotated[bool, typer.Option(help="The authors are about to submit: also count the items for the last "
                                              "step before submission (statements, archives, placeholders)")] = False,
) -> None:
    scan = _load("scan", HERE / "scan.py")
    package = _load("hygiene", HERE / "hygiene.py") if hygiene else None
    profile = _load("style_profile", HERE.parents[1] / "manuscript-deslop" / "scripts" / "style_profile.py")
    smells, kobak = profile.load_smells(), profile.load_kobak()
    failed = False
    for path in files:
        report = scan.scan(path, online=False, search_unidentified=False, venue=venue, final=final)
        counted = scan.counted_findings(report.findings, final)
        worst = [f for f in counted if f.severity in (scan.Severity.blocker, scan.Severity.major)]
        blockers = sum(f.severity == scan.Severity.blocker for f in worst)
        majors = len(worst) - blockers
        later = [f for f in report.findings if f not in counted and f.severity in (scan.Severity.blocker,
                                                                                    scan.Severity.major)]
        prof = profile.profile_text(path.read_text(encoding="utf-8"), path.suffix == ".tex", smells, kobak)
        density = prof["metrics"]["smells_per_1000_words"]
        summary = (f"{path}: {_plural(blockers, 'serious finding', 'serious findings')} and "
                   f"{_plural(majors, 'important one', 'important ones')} in the current work"
                   if worst else f"{path}: no serious or important finding in the current work")
        if later:
            summary += (f"; {_plural(len(later), 'more is', 'more are')} for the last step before submission and "
                        f"not counted (run with --final when you are about to submit)")
        typer.echo(summary + f". Writing patterns: {density} for every 1,000 words.")
        for f in worst[:show]:
            typer.echo(finding_line(scan, f))
        ranked = sorted((p for p in prof["paragraphs"] if p["hits"]), key=lambda p: -p["smells_per_100_words"])[:3]
        for p in ranked:
            typer.echo(pattern_line(profile, smells, p))
        if package is not None:
            leaks = [f for f in package.offline_text_checks(path) if f.check in ("comments", "hidden-text", "injection",
                                                                                 "invisible-characters", "secrets")]
            urgent = sum(f.stage == "now" for f in leaks)
            typer.echo(f"  Comments, hidden text and secrets (advisory, never fails the commit; comments are cleaned "
                       f"in the last step before submission): {_plural(len(leaks), 'finding', 'findings')}"
                       + (f", of which {urgent} cannot wait: a leaked key or text hidden for AI reviewers" if urgent
                          else "") + ".")
            for f in leaks[:show]:
                typer.echo(f"  - {package.SEVERITY_LEAD[f.severity]}: {package.finding_text(f)}")
        if blockers or (strict and majors) or (max_smells is not None and density > max_smells):
            failed = True
    if failed and not advisory:
        typer.echo("Manuscript check failed. Full reports: scan.py FILE --online, style_profile.py FILE.", err=True)
    raise typer.Exit(code=1 if failed and not advisory else 0)


if __name__ == "__main__":
    app()
