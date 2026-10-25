# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6"]
# ///
"""Check a paper's claims about its own software against the code, one claim at a time, each with its file and line.

    uv run --script code_claims.py check RUN/manuscript-integrity-check/code-claims.yaml --code CODE \\
        --manuscript PAPER.md [--findings RUN/manuscript-integrity-check/findings.json] [--json OUT.json]
    uv run --script code_claims.py deps CODE [--json OUT.json]

A software paper says what its code does: which step joins what, the defaults a user gets, how a number was
measured, which repository holds which part. Each such claim the integrity check examined goes in the ledger,
code-claims.yaml, whether the code agrees or not:

    claims:
      - id: CC1
        claim: "Joins are performed by rsID (default) or genomic position."   # verbatim from the manuscript
        where: "Section 2.1, step 3: the join of the VCF with each module"  # the step, join or stage the text names
        kind: behaviour      # behaviour, default, measurement, availability or version
        verdict: differs     # matches, differs or not-settled
        evidence:
          - path: just-dna-pipelines/src/just_dna_pipelines/annotation/hf_logic.py
            line: 212
            quote: 'join_on: str = "position"'
        why: "The module join defaults to position and genotype; rsID is the fallback for modules without coordinates."

`check` refuses (exit 1) what does not hold up, for the agent to fix:
- a claim that is not a verbatim quote of the manuscript, or that runs over more than one sentence: one claim per
  entry, so a list of topics cleared together ("validator, curator field, chr stripping") cannot pass;
- a missing `where`: the code that settles a claim is the code of the step the text names (the module join, not
  the Ensembl join), so the entry says which step that is;
- a `matches` or `differs` verdict without evidence, or with evidence whose quote is not in that file within 3
  lines of the line given (the line where it does occur is named);
- a measurement settled without the code that took it (a timer, a memory tracker, the benchmark script), and an
  availability claim settled without the dependency file that declares the package (`deps` lists them);
- with --findings, a dismissal in the stage's findings.json that clears a passage against the code or repository
  without naming exactly one ledger entry (`"claims": ["CC4"]`) whose verdict is `matches`.
A `differs` entry is a finding of its own; a `not-settled` one needs its `why` and is a question for the authors,
or, for a measurement, a finding that the paper reports a number whose method the repository does not hold.

`deps` lists what each manifest in the code declares (pyproject.toml, requirements*.txt, package.json): the package
names, the dependencies with their line, and where each comes from (a registry, a git URL, a workspace member), for
checking the paper's repository and availability table against them.

Exit codes: 0 every entry holds; 1 an entry fails (listed); 2 a bad option or an unreadable file.
"""
from __future__ import annotations

import json
import re
import sys
import tomllib
import unicodedata
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
import yaml

app = typer.Typer(add_completion=False, no_args_is_help=True)
KINDS = {"behaviour", "default", "measurement", "availability", "version"}
VERDICTS = {"matches", "differs", "not-settled"}
WINDOW = 3  # lines either side of the given line where the quote may start
MANIFESTS = re.compile(r"^(?:pyproject\.toml|requirements[\w.-]*\.txt|package\.json|setup\.cfg|setup\.py|Cargo\.toml|"
                       r"environment\.ya?ml|uv\.lock|poetry\.lock|go\.mod|DESCRIPTION)$")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".tox"}
# A dismissal that clears a passage against the project's code.
CODE_CLEARANCE = re.compile(r"\b(?:match(?:es|ed)?|agrees?(?: with)?|consistent with|as in|confirmed (?:in|by))\b"
                            r".{0,80}\b(?:code|repository|snapshot|source|pyproject|implementation)\b", re.I | re.S)


def folded(text: str) -> str:
    """Text as a quote is matched against it: Unicode forms, typographic quotes and dashes, emphasis marks and
    whitespace set aside; the words and their order stay."""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "−": "-"}))
    text = re.sub(r"[*_`]+", "", text)
    return " ".join(text.split())


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])", text.strip()) if s]


def inside(code: Path, relative: str) -> Path | None:
    path = (code / relative).resolve()
    return path if path.is_file() and (path == code or code in path.parents) else None


def located(path: Path, line: int, quote: str) -> tuple[bool, int | None]:
    """Whether the quote starts within WINDOW lines of `line`, and the first line where it does occur."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    want = folded(quote)
    if not want:
        return False, None
    span = quote.count("\n") + 1

    def starts(index: int, extra: int = 0) -> bool:  # extra: one more line, for code wrapped where the quote is not
        return want in folded(" ".join(lines[index:index + span + extra]))

    first = next((i for i in range(len(lines)) if starts(i)), None)
    if first is None:
        first = next((i for i in range(len(lines)) if starts(i, 1)), None)
    near = first is not None and any(starts(i, 1) for i in range(max(0, line - 1 - WINDOW), min(len(lines), line + WINDOW)))
    return near, None if first is None else first + 1


def check_entry(entry: Any, number: int, code: Path, paper: str) -> list[str]:
    if not isinstance(entry, dict):
        return [f"entry {number}: not a mapping"]
    cid = str(entry.get("id") or f"entry {number}")
    problems = []
    claim = str(entry.get("claim") or "").strip()
    if not claim:
        problems.append(f"{cid}: no claim; quote the sentence of the manuscript that makes it")
    elif folded(claim) not in paper:
        problems.append(f"{cid}: the claim is not a verbatim quote of the manuscript; quote the words that make it, "
                        "one claim per entry")
    elif len(sentences(claim)) > 1:
        problems.append(f"{cid}: the claim runs over {len(sentences(claim))} sentences; give each its own entry")
    if not str(entry.get("where") or "").strip():
        problems.append(f"{cid}: no `where`: name the step, join or stage the text places this in, so the evidence is "
                        "the code of that step")
    kind, verdict = entry.get("kind"), entry.get("verdict")
    if kind not in KINDS:
        problems.append(f"{cid}: kind is one of {', '.join(sorted(KINDS))}")
    if verdict not in VERDICTS:
        problems.append(f"{cid}: verdict is one of {', '.join(sorted(VERDICTS))}")
        return problems
    evidence = entry.get("evidence") or []
    if verdict in {"differs", "not-settled"} and not str(entry.get("why") or "").strip():
        problems.append(f"{cid}: a {verdict} verdict says why")
    if verdict == "not-settled":
        return problems
    if not evidence:
        problems.append(f"{cid}: a {verdict} verdict needs evidence: the file, line and quoted code that settle it")
        return problems
    in_manifest = False
    for n, item in enumerate(evidence, 1):
        where = f"{cid} evidence {n}"
        if not isinstance(item, dict) or not all(item.get(k) for k in ("path", "line", "quote")):
            problems.append(f"{where}: give path, line and quote")
            continue
        path = inside(code, str(item["path"]))
        if path is None:
            problems.append(f"{where}: {item['path']} is not a file in the code")
            continue
        try:
            line = int(item["line"])
        except (TypeError, ValueError):
            problems.append(f"{where}: line is a number")
            continue
        near, first = located(path, line, str(item["quote"]))
        if not near:
            problems.append(f"{where}: the quote is not in {item['path']} near line {line}"
                            + (f"; it occurs at line {first}" if first else "; it does not occur in that file"))
        in_manifest |= bool(MANIFESTS.match(path.name))
    if kind == "availability" and not in_manifest:
        problems.append(f"{cid}: an availability claim is settled by the dependency file that declares the package "
                        "(see `deps`), quoted with its line")
    if kind == "measurement" and all(MANIFESTS.match(Path(str(i.get('path', ''))).name) for i in evidence
                                     if isinstance(i, dict)):
        problems.append(f"{cid}: a measurement is settled by the code that took it (the timer, the memory tracker, the "
                        "benchmark script); without it the verdict is not-settled")
    return problems


def check_dismissals(findings: dict, claims: dict[str, dict]) -> list[str]:
    problems = []
    for n, item in enumerate(findings.get("dismissed") or [], 1):
        if not isinstance(item, dict):
            continue
        text = f"{item.get('summary', '')} {item.get('why', '')}"
        if not CODE_CLEARANCE.search(text):
            continue
        named = item.get("claims") or []
        label = f"dismissed {n} ({str(item.get('summary', ''))[:60]})"
        if len(named) != 1:
            problems.append(f"{label}: a passage cleared against the code names exactly one ledger entry "
                            f"(\"claims\": [\"CC4\"]); {'it names none' if not named else 'split it, one per claim'}")
        elif named[0] not in claims:
            problems.append(f"{label}: {named[0]} is not in the ledger")
        elif claims[named[0]].get("verdict") != "matches":
            problems.append(f"{label}: {named[0]} does not have the verdict matches")
    return problems


@app.command()
def check(
    ledger: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="code-claims.yaml")],
    code: Annotated[Path, typer.Option(exists=True, file_okay=False, help="The code the paper describes")],
    manuscript: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="The manuscript the claims quote")],
    findings: Annotated[Optional[Path], typer.Option(exists=True, dir_okay=False,
                                                     help="The stage's findings.json, whose code clearances are checked")] = None,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the result here")] = None,
) -> None:
    """Check each claim's quote, place and evidence."""
    try:
        data = yaml.safe_load(ledger.read_text(encoding="utf-8")) or {}
        entries = data.get("claims")
        found = json.loads(findings.read_text(encoding="utf-8")) if findings else None
    except (OSError, yaml.YAMLError, json.JSONDecodeError, AttributeError) as exc:
        typer.echo(f"Cannot read the ledger or findings: {exc}", err=True)
        raise typer.Exit(2) from exc
    if not isinstance(entries, list):
        typer.echo("The ledger has no `claims` list.", err=True)
        raise typer.Exit(2)
    code, paper = code.resolve(), folded(manuscript.read_text(encoding="utf-8"))
    problems: list[str] = []
    ids = [str(e.get("id")) for e in entries if isinstance(e, dict) and e.get("id")]
    if duplicated := sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"IDs used twice: {', '.join(duplicated)}")
    for number, entry in enumerate(entries, 1):
        problems += check_entry(entry, number, code, paper)
    claims = {str(e["id"]): e for e in entries if isinstance(e, dict) and e.get("id")}
    if found is not None:
        problems += check_dismissals(found, claims)
    by = {v: [i for i, e in claims.items() if e.get("verdict") == v] for v in sorted(VERDICTS)}
    result = {"claims": len(entries), "by_verdict": {v: len(i) for v, i in by.items()}, "differs": by["differs"],
              "not_settled": by["not-settled"],
              "measurements_without_code": [i for i, e in claims.items()
                                            if e.get("kind") == "measurement" and e.get("verdict") == "not-settled"],
              "problems": problems}
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if json_out:
        json_out.write_text(text + "\n", encoding="utf-8")
    typer.echo(text)
    raise typer.Exit(1 if problems else 0)


def _line_of(lines: list[str], needle: str) -> int | None:
    pattern = re.compile(rf"(?<![\w.-]){re.escape(needle)}(?![\w-])", re.I)
    return next((n for n, text in enumerate(lines, 1) if pattern.search(text)), None)


def _requirement_name(spec: str) -> str:
    return re.split(r"[\s<>=!~;\[(@]", spec.strip(), maxsplit=1)[0]


def pyproject(path: Path) -> dict[str, Any]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    lines = path.read_text(encoding="utf-8").splitlines()
    project = data.get("project") or {}
    poetry = ((data.get("tool") or {}).get("poetry") or {})
    sources = ((data.get("tool") or {}).get("uv") or {}).get("sources") or {}
    specs = [(s, "dependencies") for s in project.get("dependencies") or []]
    specs += [(s, f"optional: {group}") for group, items in (project.get("optional-dependencies") or {}).items()
              for s in items]
    specs += [(s, f"group: {group}") for group, items in (data.get("dependency-groups") or {}).items()
              for s in items if isinstance(s, str)]
    specs += [(f"{name} {value if isinstance(value, str) else ''}".strip(), "poetry")
              for name, value in (poetry.get("dependencies") or {}).items() if name != "python"]
    deps = []
    for spec, group in specs:
        name = _requirement_name(spec)
        origin = sources.get(name) or {}
        source = ("workspace member" if origin.get("workspace") else origin.get("git") or
                  (f"path {origin['path']}" if origin.get("path") else "") or (spec.split("@", 1)[1].strip()
                                                                                if "@" in spec else "registry"))
        deps.append({"name": name, "spec": spec, "group": group, "source": source, "line": _line_of(lines, name)})
    members = ((data.get("tool") or {}).get("uv") or {}).get("workspace", {}).get("members") or []
    return {"package": project.get("name") or poetry.get("name"), "version": project.get("version"),
            "workspace_members": members, "dependencies": deps}


def requirements(path: Path) -> dict[str, Any]:
    deps = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = raw.split("#", 1)[0].strip()
        if text and not text.startswith("-"):
            deps.append({"name": _requirement_name(text), "spec": text, "group": "requirements",
                         "source": text.split("@", 1)[1].strip() if "@" in text else "registry", "line": n})
    return {"package": None, "version": None, "workspace_members": [], "dependencies": deps}


def package_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = path.read_text(encoding="utf-8").splitlines()
    deps = [{"name": name, "spec": f"{name} {spec}", "group": group,
             "source": spec if re.match(r"^(?:git|github:|https?:|file:)", str(spec)) else "registry",
             "line": _line_of(lines, f'"{name}"')}
            for group in ("dependencies", "devDependencies", "peerDependencies")
            for name, spec in (data.get(group) or {}).items()]
    return {"package": data.get("name"), "version": data.get("version"), "workspace_members": data.get("workspaces") or [],
            "dependencies": deps}


def manifests(code: Path) -> list[dict[str, Any]]:
    readers = {"pyproject.toml": pyproject, "package.json": package_json}
    out = []
    for path in sorted(code.rglob("*")):
        folders = path.relative_to(code).parts[:-1]
        if not path.is_file() or any(f in SKIP_DIRS or f.startswith(".") or f.endswith(".lock") for f in folders):
            continue
        reader = readers.get(path.name) or (requirements if re.match(r"^requirements[\w.-]*\.txt$", path.name) else None)
        if reader is None:
            continue
        try:
            out.append({"file": path.relative_to(code).as_posix(), **reader(path)})
        except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
            out.append({"file": path.relative_to(code).as_posix(), "unreadable": str(exc)})
    return out


@app.command()
def deps(
    code: Annotated[Path, typer.Argument(exists=True, file_okay=False, help="The code the paper describes")],
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the listing here")] = None,
) -> None:
    """List each manifest's package and the dependencies it declares, with their line and source."""
    found = manifests(code.resolve())
    if json_out:
        json_out.write_text(json.dumps(found, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = []
    for m in found:
        head = f"## {m['file']}" + (f": {m['package']}" if m.get("package") else "") + (
            f" {m['version']}" if m.get("version") else "")
        lines += [head, ""]
        if m.get("unreadable"):
            lines += [f"Could not be read: {m['unreadable']}", ""]
            continue
        if m["workspace_members"]:
            lines += [f"Workspace members: {', '.join(map(str, m['workspace_members']))}", ""]
        lines += [f"- {d['spec']} ({d['group']}; {d['source']}; line {d['line'] or '?'})" for d in m["dependencies"]]
        lines.append("")
    typer.echo("\n".join(lines).rstrip() or "No manifest found.")


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
