# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12"]
# ///
"""List passages whose detail may belong in another section of the paper (references/section-roles.md).

Each section of a paper has a job. The Abstract and the Introduction (with its feature lists and boxes) say what the
work does and why it matters, with at most a rounded figure and a pointer to the section that has the measurement;
Methods hold procedure, data preparation, thresholds and rules; Results hold measured outcomes beside the
configuration that makes them fair; the Discussion interprets, compares and bounds. Over revision rounds detail
drifts out of its section: measured counts and the procedure behind them reach the Introduction, and audit counts or
a classifier's accuracy settle in Methods. This script lists the candidates. Whether each one is misplaced is the
reading's job, never the script's: a candidate is a passage to read, not a finding.

    uv run --script section_roles.py PAPER.md
    uv run --script section_roles.py PAPER.md --json roles.json --md roles.md
    uv run --script section_roles.py FINAL.md --before ORIGINAL.md       # what an edit moved into the wrong section

What is listed, by where the passage stands:

- Introduction: a measured result (a count out of a total, a range or a median with its unit, a decimal
  percentage, a count with a past-tense outcome such as "were withheld", a dated count of what a resource held), a
  comparison stated with the configuration that makes it fair (threads, a benchmark configuration), or procedure (a
  preparation step such as normalizing, parsing or mirroring as a storage format, a gate a result passes, analysis
  parameters).
- Abstract: procedure, the bookkeeping of a filter or an audit ("860 were withheld"), and a sentence of three or more
  measurements. The Abstract gives the main results with their numbers and the setup they were measured on.
- Methods: a measured result, that is what the procedure produced on the data it was applied to. A rule stated with
  a comparator ("at least four of the seven") is procedure, and so are data versions and input sizes.
- Results: a paragraph of procedure (two or more preparation steps or rules) that states no number.
- Discussion and Conclusion: a precise number that no Methods or Results section states.

Outside Methods, a sentence that cites other work is background and is left out (in Methods a cited source is often
the data the procedure ran on), and so is a sentence about plans in the Discussion. Section kinds come from the
headings as manuscript-story's reader_metrics.py reads them, one classifier for the plugin: "System and Methods" and
"Implementation" are Methods, "Benchmarking and Validation" and "Use cases" are Results, and a subsection whose
heading names no kind takes its parent's ("1.2 Overview" under "1. Introduction" is Introduction).

Exit codes: 0 when the report is written, whatever it lists; with --before, 1 when the new version has a candidate
the earlier one did not (an edit put detail in the wrong section, or moved a passage into one); 2 usage error.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Annotated, Optional

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)

SKILLS = Path(__file__).resolve().parents[2]


def _reader_metrics() -> ModuleType:
    """manuscript-story's reading measures, for the heading classifier and the text cleaning they share."""
    name = "section_roles_reader_metrics"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, SKILLS / "manuscript-story" / "scripts" / "reader_metrics.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


RM = _reader_metrics()

NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
WORDNUM = r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|sixteen|twenty|thirty|sixty|hundred"
COMPARATOR = re.compile(r"(?:at least|at most|fewer than|more than|less than|greater than|no more than|up to|over|"
                        r"under|below|above|about|around|approximately|nearly|almost|roughly|~|≥|≤|<|>|=)\s*$",
                        re.IGNORECASE)
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE = re.compile(rf"\b\d{{1,2}}\s+{MONTH}\s+\d{{4}}\b|\b{MONTH}\s+\d{{1,2}},?\s+\d{{4}}\b|\b\d{{4}}-\d{{2}}-\d{{2}}\b")
UNIT = r"(?:s|sec|seconds?|ms|min|minutes?|h|hours?|days?|GB|MB|KB|TB|GiB|MiB|times|×|x|-?fold|%)"

# What a measurement looks like in a sentence: each pattern names a signal the report prints.
MEASURED: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("count out of a total", re.compile(rf"(?<![\w.,])(?:{NUM})\s+(?:out\s+)?of\s+(?:the\s+)?"
                                        rf"(?:{NUM}|them|these|those|which)\b")),
    ("decimal percentage", re.compile(r"(?<![\w.,])\d+\.\d+\s*%")),
    ("range with a unit", re.compile(rf"(?<![\w.,])(?:{NUM})\s*(?:to|–|-|and)\s*(?:{NUM})\s*{UNIT}(?![\w])")),
    ("median or mean with its value", re.compile(rf"\b(?:median|mean|average)\s+(?:of\s+)?(?:{NUM})\s*{UNIT}?(?![\w])",
                                                 re.IGNORECASE)),
    ("decimal value with a unit", re.compile(r"(?<![\w.,])\d+\.\d+\s*(?:s|ms|seconds?|min|GB|MB)(?![\w])")),
    ("a count with its outcome", re.compile(rf"\b(?:{NUM}|{WORDNUM})\b[^.;]{{0,60}}?\b(?:were|was)\s+"
                                            r"(?:then\s+|also\s+)?(?:withheld|excluded|rejected|discarded|flagged|"
                                            r"misassigned|misclassified|assigned|classified|passed|failed|detected|"
                                            r"recovered|matched)\b", re.IGNORECASE)),
    ("a metric with its value", re.compile(rf"\b(?:accuracy|sensitivity|specificity|precision|recall|AUROC|AUC|"
                                           rf"F1|concordance|correlation|kappa)\s+(?:of|was|were|=|:|reached)\s+(?:{NUM})",
                                           re.IGNORECASE)),
)
DATED_COUNT = "a dated count of what a resource held"
CONFIGURATION: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("threads or cores", re.compile(rf"\b(?:{NUM}|{WORDNUM})\s+(?:threads?|CPU cores?|cores?)\b", re.IGNORECASE)),
    ("a benchmark configuration", re.compile(r"\bbenchmark(?:ing)?\s+(?:configuration|setup|settings)\b", re.IGNORECASE)),
)
PROCEDURE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("a preparation step", re.compile(r"\b(?:is|are|was|were|been|being)\s+(?:\w+ly\s+)?(?:normali[sz]ed|parsed|"
                                      r"harmoni[sz]ed|mirrored|converted|filtered|pruned|imputed|lifted over|"
                                      r"thresholded|binned|deduplicated|audited|re-?anchored|left-aligned|"
                                      r"serialized|stored as)\b", re.IGNORECASE)),
    ("a preparation step", re.compile(r"\b(?:normali[sz]es|parses|mirrors|harmoni[sz]es|deduplicates|re-?anchors)\b",
                                      re.IGNORECASE)),
    ("a storage format", re.compile(r"\b(?:as|in|into|to)\s+(?:\w+\s+)?(?:Parquet|Arrow|Feather|HDF5|Zarr|SQLite|"
                                    r"DuckDB)\b")),
    ("a gate a result passes", re.compile(r"\bpass(?:es|ed|ing)?\s+(?:its|the|their|a|an)\s+(?:[\w-]+\s+){0,2}"
                                          r"(?:audit|filter|check|QC|quality control|threshold)\b", re.IGNORECASE)),
    ("analysis parameters", re.compile(r"\bk\s*=\s*\d|\bP\s*[<≤]\s*\d|\bminor allele frequency\b|\bMAF\b|"
                                       r"\bHardy[–-]Weinberg\b|\bkinship\b|\blinkage pruning\b|\bLD[- ]pruned\b")),
)
RULE = re.compile(r"\b(?:when|if|unless|whenever)\b[^.;]*\b(?:at least|at most|fewer than|more than|less than|below|"
                  r"above)\b", re.IGNORECASE)
CITES = re.compile(r"\((?=[^()]*\b(?:1[89]|20)\d{2}[a-z]?\b)[^()]*(?:et al\.|[A-Z][\w'’-]+,?\s+(?:1[89]|20)\d{2})[^()]*\)|"
                   r"\[\d+(?:[,–-]\s*\d+)*\]|\\cite[tp]?\*?(?:\[[^\]]*\])*\{")
PLANNED = re.compile(r"\b(?:will|would|planned|plans? to|underway|future)\b", re.IGNORECASE)
PRECISE = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{3,})(?![\w,]*\d)")
YEAR = re.compile(r"^(?:1[89]|20)\d{2}$")

EARLY = {"abstract", "introduction"}
DUMP = 3  # measurements in one Abstract sentence that read as a table (deslop A12)
LATE = {"discussion", "conclusion", "limitations"}
DIRECTIONS = {
    "results-detail-early": "Results detail in the {kind}",
    "methods-detail-early": "Methods detail in the {kind}",
    "results-in-methods": "A result in Methods",
    "procedure-in-results": "Procedure in Results",
    "result-only-late": "A result first stated in the {kind}",
}
HOME = {"results-detail-early": "Results, beside its configuration; the {kind} keeps a rounded figure and a pointer",
        "methods-detail-early": "Methods; the {kind} says what the step gives the reader",
        "results-in-methods": "Results; Methods keeps the rule and points to the result",
        "procedure-in-results": "Methods; Results keeps one clause of orientation and the outcome",
        "result-only-late": "Results, where the {kind} can interpret it"}


@dataclass
class Block:
    heading: str
    kind: str
    line: int
    text: str


@dataclass
class Candidate:
    direction: str
    label: str
    section: str
    section_kind: str
    line: int
    quote: str
    signals: list[str]
    belongs: str
    introduced: Optional[bool] = None


@dataclass
class Report:
    file: str
    sections: list[dict[str, str]] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)


def _plain(heading: str) -> str:
    return re.sub(r"[*_`#]", "", heading).strip()


def blocks(text: str) -> tuple[list[Block], list[dict[str, str]]]:
    """Paragraphs and list items (each item its own block) with their section, kind and first line; tables,
    figures, code and comments are left out."""
    latex = bool(re.search(r"\\(?:section|begin\{document\}|documentclass)\b", text))
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))  # noqa: E731  keeps every line number
    text = re.sub(r"<!--.*?-->", blank, text, flags=re.DOTALL)
    text = re.sub(r"^```.*?^```", blank, text, flags=re.DOTALL | re.MULTILINE)
    if latex:
        text = re.sub(r"(?<!\\)%[^\n]*", blank, text)
        text = re.sub(r"\\begin\{(figure|table|equation|align|tabular)\*?\}.*?\\end\{\1\*?\}", blank, text, flags=re.DOTALL)
        text = re.sub(r"\\begin\{abstract\}", r"\\section{Abstract}", text)
    out: list[Block] = []
    sections: list[dict[str, str]] = []
    stack: list[tuple[int, str]] = []
    heading, kind, seen_body = "(front matter)", "front", False
    para: list[str] = []
    start = 0

    def flush() -> None:
        nonlocal para
        if para:
            chunk = " ".join(para).strip()
            if chunk and not re.match(r"^(\*\*)?(Figure|Fig\.|Table)\s+S?\d", chunk):
                out.append(Block(heading, kind, start, chunk))
        para = []

    for n, line in enumerate(text.splitlines(), start=1):
        md = None if latex else re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        tex = re.match(r"^\s*\\(section|subsection|subsubsection)\*?\{(.*)\}\s*$", line) if latex else None
        if md or tex:
            flush()
            level = len(md.group(1)) if md else {"section": 1, "subsection": 2, "subsubsection": 3}[tex.group(1)]
            heading = _plain((md or tex).group(2))
            own = RM._kind(heading)
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else None
            if not seen_body and own in RM.BODY_START:
                seen_body = True
            if not seen_body:
                kind = "front"
            else:
                kind = own or (parent if parent not in (None, "front") else "other")
            stack.append((level, kind))
            sections.append({"heading": heading, "kind": kind})
            continue
        stripped = line.strip()
        if not stripped or (not latex and (stripped.startswith("|") or stripped.startswith("!["))):
            flush()
            continue
        bullet = None if latex else re.match(r"^(?:[-*+]|\d+[.)])\s+", stripped)
        if bullet or (latex and stripped.startswith("\\item")):
            flush()
            stripped = stripped[bullet.end():] if bullet else stripped[len("\\item"):].strip()
        if not para:
            start = n
        para.append(stripped.lstrip("> "))
    flush()
    return out, sections


def sentences(text: str) -> list[str]:
    """The block's sentences as written (markup kept, so a quote can be found in the source)."""
    protected = text
    for i, abbr in enumerate(RM.ABBREVIATIONS):
        protected = protected.replace(abbr, abbr.replace(".", f"\x00{i}\x00"))
    parts = re.split(r"(?<=[.!?])\s+(?=[\"“(\[*_]*[A-Za-z0-9])", protected)
    return [re.sub(r"\x00\d+\x00", ".", p).strip() for p in parts if len(RM.WORD.findall(p)) >= 3]


def _clean(sentence: str) -> str:
    return re.sub(r"\s+", " ", RM._drop_citations(RM._strip_markdown(sentence))).strip()


def _hits(patterns: tuple[tuple[str, re.Pattern[str]], ...], text: str, rule_free: bool = False) -> list[str]:
    found = []
    for name, rx in patterns:
        for m in rx.finditer(text):
            if rule_free and COMPARATOR.search(text[max(0, m.start() - 20):m.start()]):
                continue  # "at least four of the seven", "10% or more": a rule, not a measurement
            found.append(name)
            break
    return list(dict.fromkeys(found))


def measured(text: str) -> tuple[list[str], int]:
    """The kinds of measurement in a sentence, and how many measurements it gives: "a median of 31.4 seconds" is
    one, however many patterns it matches."""
    names, spans = [], []
    for name, rx in MEASURED:
        for m in rx.finditer(text):
            if not COMPARATOR.search(text[max(0, m.start() - 20):m.start()]):
                names.append(name)
                spans.append((m.start(), m.end()))
    count, end = 0, -1
    for a, b in sorted(spans):
        count, end = (count + 1, b) if a >= end else (count, max(end, b))
    return list(dict.fromkeys(names)), count


def dated_count(text: str) -> bool:
    """A date and a count in one sentence: what a registry or a catalogue held on a day."""
    if not DATE.search(text):
        return False
    rest = DATE.sub(" ", text)
    return bool(re.search(rf"(?<![\w.]){NUM}(?![\w.])|\b(?:{WORDNUM})\b", rest)) and bool(
        re.search(r"\b(?:held|holds|had|has|listed|lists|contained|contains|included|includes|counted|reached|"
                  r"numbered|hosted|hosts)\b", rest))


def _precise(text: str) -> set[str]:
    return {m.group(1) for m in PRECISE.finditer(text) if not YEAR.match(m.group(1))}


def check(text: str, file: str = "") -> Report:
    """Every candidate in a manuscript, in reading order."""
    found, sections = blocks(text)
    report = Report(file=file, sections=sections)
    known = set()
    for b in found:
        if b.kind in ("methods", "results"):
            known |= _precise(_clean(b.text))
    for b in found:
        if b.kind in ("front", "back", "other"):
            continue
        name = b.kind.capitalize()

        def add(direction: str, quote: str, signals: list[str]) -> None:
            report.candidates.append(Candidate(direction, DIRECTIONS[direction].format(kind=name), b.heading, b.kind,
                                               b.line, quote, signals, HOME[direction].format(kind=name)))

        if b.kind == "results":
            plain = _clean(b.text)
            steps = _hits(PROCEDURE, plain) + (["a rule with its threshold"] if RULE.search(plain) else [])
            if len(steps) >= 2 and not re.search(r"\d", plain):
                add("procedure-in-results", sentences(b.text)[0] if sentences(b.text) else b.text, steps)
            continue
        for s in sentences(b.text):
            if b.kind != "methods" and CITES.search(s):
                continue  # background: someone else's result (in Methods, a cited source is often the data)
            plain = _clean(s)
            if b.kind in EARLY:
                kinds, count = measured(plain)
                setup = _hits(CONFIGURATION, plain)
                results = kinds + ([DATED_COUNT] if dated_count(plain) else []) + setup
                # The Abstract gives the main results with their numbers and setup; it is listed for the bookkeeping
                # of a filter or an audit, or a sentence of three or more measurements.
                abstract_too_much = "a count with its outcome" in kinds or count >= DUMP
                if results and (b.kind == "introduction" or abstract_too_much):
                    add("results-detail-early", s, results)
                methods = _hits(PROCEDURE, plain)
                if methods:
                    add("methods-detail-early", s, methods)
            elif b.kind == "methods":
                results, _ = measured(plain)
                if results:
                    add("results-in-methods", s, results)
            elif b.kind in LATE and not PLANNED.search(plain):
                new = sorted(_precise(plain) - known)
                if new:
                    add("result-only-late", s, [f"{', '.join(new)} is in no Methods or Results section"])
    return report


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return " ".join(re.sub(r"[*_`]", "", text).split()).lower()


def compare(before: Report, after: Report) -> dict[str, list[Candidate]]:
    """Candidates the new version has and the old one did not (introduced), and the old ones that are gone. A
    candidate is its passage and its direction, so a sentence moved word for word from Results into Methods is
    introduced, and one moved back is resolved."""
    had = {(_fold(c.quote), c.direction) for c in before.candidates}
    has = {(_fold(c.quote), c.direction) for c in after.candidates}
    for c in after.candidates:
        c.introduced = (_fold(c.quote), c.direction) not in had
    return {"introduced": [c for c in after.candidates if c.introduced],
            "resolved": [c for c in before.candidates if (_fold(c.quote), c.direction) not in has]}


def markdown(report: Report, moved: dict[str, list[Candidate]] | None = None) -> str:
    out = [f"# Detail in the wrong section? {Path(report.file).name}", "",
           "Each passage below has detail that usually belongs in another section (references/section-roles.md). "
           "These are candidates to read, not findings: a paper's own layout or its venue can make one right where "
           "it is.", ""]
    shown = moved["introduced"] if moved is not None else report.candidates
    if moved is not None:
        out += [f"{len(moved['introduced'])} new in this version, {len(moved['resolved'])} gone since the earlier one.",
                ""]
    if not shown:
        out.append("Nothing to list." if moved is None else "The edits put no detail in the wrong section.")
    for direction in DIRECTIONS:
        group = [c for c in shown if c.direction == direction]
        if not group:
            continue
        where = "Abstract or Introduction" if direction.endswith("early") else "Discussion"
        out += ["", f"## {DIRECTIONS[direction].format(kind=where)}", ""]
        for c in group:
            out.append(f"- {c.section} (line {c.line}): \"{c.quote}\"  ")
            out.append(f"  Signals: {'; '.join(c.signals)}. Belongs in: {c.belongs}.")
    if moved is not None and moved["resolved"]:
        out += ["", "## Gone since the earlier version", ""]
        out += [f"- {c.label}, {c.section}: \"{c.quote}\"" for c in moved["resolved"]]
    out += ["", "Sections read as: " + "; ".join(f"{s['heading']} ({s['kind']})" for s in report.sections) + "."]
    return "\n".join(out) + "\n"


@app.command()
def main(
    paper: Annotated[Path, typer.Argument(help="The manuscript (Markdown or LaTeX)")],
    before: Annotated[Optional[Path], typer.Option("--before", help="An earlier version: list only what is new")] = None,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the candidates as JSON")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Write the report as Markdown")] = None,
) -> None:
    for p in [paper] + ([before] if before else []):
        if not p.is_file():
            typer.echo(f"not a file: {p}", err=True)
            raise typer.Exit(2)
    text = paper.read_text(encoding="utf-8")
    report = check(text, str(paper))
    moved = None
    if before:
        moved = compare(check(before.read_text(encoding="utf-8"), str(before)), report)
    body = markdown(report, moved)
    if json_out:
        data = asdict(report)
        if moved is not None:
            data["introduced"] = [asdict(c) for c in moved["introduced"]]
            data["resolved"] = [asdict(c) for c in moved["resolved"]]
        json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if md_out:
        md_out.write_text(body, encoding="utf-8")
    typer.echo(body, nl=False)
    if moved is not None and moved["introduced"]:
        raise typer.Exit(1)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
