# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12"]
# ///
"""Check that an edited manuscript still says what the original said.

A copy-editing pass may change wording, never content. This compares the text before and after and reports
every number, citation, identifier, technical term, URL or code span that appeared, disappeared or changed
count, and every hedge, negation or causal verb that moved (the edits that turn a correct sentence into a
false one: a dropped "may", a lost "not", "is associated with" becoming "causes").

    uv run --script guard.py BEFORE.md AFTER.md
    uv run --script guard.py PAPER.md --against HEAD          # compare with the committed version
    uv run --script guard.py BEFORE.md AFTER.md --json report.json

Exit code 1 when a protected item changed (numbers, citations, identifiers, terms, URLs, code).
Hedge, negation and causal changes are warnings: read each one.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Annotated, Optional

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
LATEX_COMMENT = re.compile(r"(?<!\\)%.*$", re.MULTILINE)

# Protected: any change is a content change.
PROTECTED: dict[str, re.Pattern[str]] = {
    "numbers": re.compile(
        r"(?<![\w.])[-+−]?\d[\d,]*(?:\.\d+)?(?:\s?(?:%|×|-fold|fold|bp|kb|Mb|Gb|GB|MB|TB|ms|s|min|h|°C))?(?![\w])"),
    "citations": re.compile(
        r"\((?:[^()]*?\b(?:19|20)\d{2}[a-z]?\b[^()]*?)\)|\[\d+(?:\s*[-–,]\s*\d+)*\]|\\cite[pt]?\*?\{[^}]+\}|@[A-Za-z][\w:-]+"),
    "identifiers": re.compile(
        r"\b10\.\d{4,9}/[^\s\"<>)\],;]+|\bPMID:?\s*\d{5,9}\b|\barXiv\W{0,3}\d{4}\.\d{4,5}\b|\brs\d{3,}\b|"
        r"\bPGS\d{6}\b|\bGCST\d+\b|\bENS[GTP]\d{11}\b|\bchr(?:\d{1,2}|[XYM]|MT)\b", re.IGNORECASE),
    "urls": re.compile(r"https?://[^\s)>\]]+"),
    "code": re.compile(r"`[^`\n]+`"),
    # Technical terms: tokens with a digit or several capitals (GRCh38, APOE, CYP2D6, VCF, PRS, MCP).
    "terms": re.compile(r"\b(?:[A-Za-z]+\d(?:[\w-]|\.\d)*|[A-Z]{2,}[\w-]*|[a-z]+[A-Z][\w-]*)\b"),
}

# Watched: a change may be fine, but each one can flip or strengthen a claim.
WATCHED: dict[str, re.Pattern[str]] = {
    "hedges": re.compile(
        r"\b(?:may|might|could|can|suggests?|suggested|likely|unlikely|possibly|potentially|appears?|appeared|"
        r"approximately|roughly|about|around|probably|perhaps|preliminary|tentative(?:ly)?|estimated?|"
        r"partly|partially|some|often|usually|typically)\b", re.IGNORECASE),
    "negations": re.compile(r"\b(?:not|no|never|none|nor|neither|without|cannot|n't|fails?|failed|lacks?|absent)\b",
                            re.IGNORECASE),
    "causal": re.compile(
        r"\b(?:causes?|caused|causal(?:ly)?|leads? to|led to|drives?|drove|determines?|determined|proves?|proved|"
        r"demonstrates?|demonstrated|shows?|showed|shown|establish(?:es|ed)?|confirms?|confirmed|guarantees?|"
        r"ensures?|ensured|results? in|resulted in|due to|because)\b", re.IGNORECASE),
    "comparatives": re.compile(
        r"\b(?:more|less|fewer|faster|slower|higher|lower|better|worse|greater|smaller|larger|first|only|all|"
        r"every|always|best|most|least)\b", re.IGNORECASE),
}


def _prose(text: str) -> str:
    """The text a reader sees: drop HTML comments (revision markers, notes) and LaTeX comments."""
    return LATEX_COMMENT.sub("", HTML_COMMENT.sub("", text))


def _items(text: str, rx: re.Pattern[str]) -> Counter[str]:
    return Counter(" ".join(m.group(0).split()) for m in rx.finditer(text))


def _paragraphs(text: str) -> list[str]:
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]


def _diff(before: Counter[str], after: Counter[str]) -> dict[str, dict[str, int]]:
    removed = {k: before[k] - after[k] for k in before if before[k] > after[k]}
    added = {k: after[k] - before[k] for k in after if after[k] > before[k]}
    return {"removed": removed, "added": added}


def _rewritten_paragraphs(before: str, after: str, threshold: float) -> list[dict[str, object]]:
    """Paragraphs whose aligned counterpart shares less than `threshold` of its characters."""
    a, b = _paragraphs(before), _paragraphs(after)
    out: list[dict[str, object]] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "replace":
            continue
        for k in range(max(i2 - i1, j2 - j1)):
            old = a[i1 + k] if i1 + k < i2 else ""
            new = b[j1 + k] if j1 + k < j2 else ""
            ratio = SequenceMatcher(None, old, new, autojunk=False).ratio()
            if ratio < threshold:
                out.append({"similarity": round(ratio, 2), "before": old[:160], "after": new[:160]})
    return out


def compare(before_text: str, after_text: str, threshold: float = 0.5) -> dict[str, object]:
    before, after = _prose(before_text), _prose(after_text)
    protected = {name: _diff(_items(before, rx), _items(after, rx)) for name, rx in PROTECTED.items()}
    watched = {name: _diff(_items(before, rx), _items(after, rx)) for name, rx in WATCHED.items()}
    return {
        "protected": {k: v for k, v in protected.items() if v["removed"] or v["added"]},
        "watched": {k: v for k, v in watched.items() if v["removed"] or v["added"]},
        "rewritten_paragraphs": _rewritten_paragraphs(before, after, threshold),
        "words_before": len(before.split()),
        "words_after": len(after.split()),
    }


def _git_show(path: Path, ref: str) -> str:
    rel = subprocess.run(["git", "-C", str(path.parent), "ls-files", "--full-name", path.name],
                         capture_output=True, text=True, check=True).stdout.strip()
    if not rel:
        raise typer.BadParameter(f"{path} is not tracked by git")
    return subprocess.run(["git", "-C", str(path.parent), "show", f"{ref}:{rel}"],
                          capture_output=True, text=True, check=True).stdout


def to_markdown(report: dict[str, object]) -> str:
    lines = [f"# Edit guard: {report['words_before']} → {report['words_after']} words", ""]
    protected = report["protected"]
    lines.append("## Protected items (must not change)" + ("" if protected else ": none changed"))
    for name, d in protected.items():  # type: ignore[union-attr]
        for kind in ("removed", "added"):
            if d[kind]:
                lines.append(f"- **{name} {kind}**: " + ", ".join(f"`{k}`×{n}" for k, n in d[kind].items()))
    watched = report["watched"]
    lines += ["", "## Watched (read each one: did the claim change?)" + ("" if watched else ": no change")]
    for name, d in watched.items():  # type: ignore[union-attr]
        for kind in ("removed", "added"):
            if d[kind]:
                lines.append(f"- {name} {kind}: " + ", ".join(f"{k}×{n}" for k, n in d[kind].items()))
    rewritten = report["rewritten_paragraphs"]
    lines += ["", f"## Heavily rewritten paragraphs ({len(rewritten)})"]  # type: ignore[arg-type]
    for p in rewritten:  # type: ignore[union-attr]
        lines.append(f"- similarity {p['similarity']}: “{p['before']}…” → “{p['after']}…”")
    return "\n".join(lines) + "\n"


@app.command()
def main(
    before: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Original, or the edited file with --against")],
    after: Annotated[Optional[Path], typer.Argument(exists=True, dir_okay=False, help="Edited version")] = None,
    against: Annotated[Optional[str], typer.Option(help="Compare BEFORE (edited, on disk) with this git ref")] = None,
    threshold: Annotated[float, typer.Option(help="Flag paragraphs below this similarity")] = 0.5,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the report as JSON")] = None,
) -> None:
    if against:
        before_text, after_text = _git_show(before.resolve(), against), before.read_text(encoding="utf-8")
    elif after is not None:
        before_text, after_text = before.read_text(encoding="utf-8"), after.read_text(encoding="utf-8")
    else:
        raise typer.BadParameter("give AFTER, or --against REF")
    report = compare(before_text, after_text, threshold)
    if json_out:
        json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    typer.echo(to_markdown(report))
    raise typer.Exit(code=1 if report["protected"] else 0)


if __name__ == "__main__":
    app()
