# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12"]
# ///
"""Measure how a manuscript reads, section by section, and how that changed between versions.

Not a verdict, not a quality score and not a check. Each measure stands for something a reader notices:
long sentences; caveats in the stress position at the end of a sentence, where the reader puts the
emphasis (Gopen & Swan 1990); negations, limiting words and hedges inside results rather than in
Limitations; numbers per hundred words; how often the authors speak as "we"; acronym and code density
(jargon: Martinez & Mammola 2021); and how much of the paper each kind of section takes. A measure that
moved is a place to read, never a reason to edit on its own: read it with the reader panel's findings.

    uv run --script reader_metrics.py PAPER.md
    uv run --script reader_metrics.py PAPER.md --before EARLIER.md          # what moved, and which way
    uv run --script reader_metrics.py v1.md v2.md v3.md --label v1 --label v2 --label v3   # oldest first
    uv run --script reader_metrics.py PAPER.tex --json metrics.json --md metrics.md

Only the body is measured: everything before the Abstract or Introduction (title, authors, notes) and the
back matter (references, declarations, availability, funding, contributions, acknowledgements) is left
out, and so are tables, code blocks, images, HTML comments (revision marks included) and citations.
Figure and table captions are measured separately. A subsection without a recognisable heading takes its
parent's kind ("4.1 Annotation Speed" under "4. Benchmarking" counts as results).

Exit codes: 0 for every report, 2 for a usage error.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import typer

app = typer.Typer(add_completion=False, help=__doc__.split("\n\n")[0])

# Section kinds, matched on the heading text in this order; the first match wins.
KINDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("back", re.compile(r"\b(references?|bibliography|acknowledg\w*|funding|contribution|competing|conflicts? of "
                        r"interest|availability|declarations?|ethics|author information|abbreviations|"
                        r"use of ai|supplementary (information|material|data)|appendix)\b", re.IGNORECASE)),
    ("abstract", re.compile(r"^(abstract|summary)\b", re.IGNORECASE)),
    ("limitations", re.compile(r"\blimitations?\b", re.IGNORECASE)),
    ("conclusion", re.compile(r"\bconclu\w*\b", re.IGNORECASE)),
    ("discussion", re.compile(r"\bdiscussion\b", re.IGNORECASE)),
    ("introduction", re.compile(r"\b(introduction|background)\b", re.IGNORECASE)),
    ("results", re.compile(r"\b(results?|benchmark\w*|validation|evaluation|performance|case stud\w*|"
                           r"experiments?|comparison)\b", re.IGNORECASE)),
    ("methods", re.compile(r"\b(methods?|implementation|system|architecture|design|materials|algorithms?|"
                           r"pipeline|approach)\b", re.IGNORECASE)),
)
BODY_START = {"abstract", "introduction"}

NEGATION = re.compile(r"\b(?:not|no|nor|never|neither|cannot|without)\b|n't\b", re.IGNORECASE)
LIMITING = re.compile(r"\b(?:only|merely|solely|albeit|although|though|even if|despite|in spite of|however|"
                      r"nevertheless|nonetheless)\b", re.IGNORECASE)
HEDGE = re.compile(r"\b(?:may|might|could|suggests?|suggested|appears?|appeared|likely|possibly|potentially|"
                   r"perhaps|presumably|arguably)\b", re.IGNORECASE)
CAVEAT = re.compile(f"(?:{NEGATION.pattern})|(?:{LIMITING.pattern})|(?:{HEDGE.pattern})", re.IGNORECASE)
FIRST_PERSON = re.compile(r"\b(?:we|our|ours|us)\b", re.IGNORECASE)
ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]*[A-Z0-9](?:s)?\b")
ROMAN = re.compile(r"^(?:I{1,3}|IV|VI{0,3}|IX|XI{0,3})$")
WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][\wÀ-ÖØ-öø-ÿ'’\-]*|\d+(?:[.,]\d+)*%?")
NUMBER = re.compile(r"^\d")
CLAUSE_BREAK = re.compile(r"[,;:–—(]")
ABBREVIATIONS = ("e.g.", "i.e.", "et al.", "etc.", "vs.", "Fig.", "Figs.", "approx.", "cf.", "No.", "Dr.",
                 "Suppl.", "Eq.", "ca.", "resp.")
LONG_SENTENCE = 35

# The direction in which each measure makes reading harder, for the comparison. None: descriptive only.
HARDER: dict[str, int | None] = {
    "words": None, "sentences": None,
    "mean_sentence_words": +1, "long_sentence_share": +1,
    "negations_per_100": +1, "limiting_per_100": +1, "hedges_per_100": +1,
    "caveat_ending_share": +1, "numbers_per_100": None,
    "first_person_per_100": -1, "acronyms_per_100": +1, "code_per_100": +1,
}
MEANING = {
    "mean_sentence_words": "average sentence length (words)",
    "long_sentence_share": f"share of sentences over {LONG_SENTENCE} words",
    "negations_per_100": "negations per 100 words",
    "limiting_per_100": "limiting or concessive words per 100 words",
    "hedges_per_100": "hedges per 100 words",
    "caveat_ending_share": "share of sentences that end on a caveat",
    "numbers_per_100": "numbers per 100 words",
    "first_person_per_100": "\"we\" and \"our\" per 100 words",
    "acronyms_per_100": "acronyms per 100 words",
    "code_per_100": "code names per 100 words",
}
# Where a caveat costs the reader least; elsewhere a rise reads as caveats moving into the story.
CAVEAT_HOME = {"limitations", "discussion"}


@dataclass
class Section:
    heading: str
    level: int
    kind: str
    text: list[str] = field(default_factory=list)
    captions: list[str] = field(default_factory=list)


def _kind(heading: str) -> str | None:
    plain = re.sub(r"^(?:\d+(?:\.\d+)*\.?|[SA]\d+\.?)\s*", "", re.sub(r"[*_`#]", "", heading).strip())
    for kind, rx in KINDS:
        if rx.search(plain):
            return kind
    return None


def _strip_markdown(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?", " ", text)          # images
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)                   # links keep their text
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"`[^`]+`", " CODESPAN ", text)
    text = re.sub(r"[*_]{1,3}", "", text)
    text = re.sub(r"\^[^^]*\^", "", text)                                   # pandoc superscripts
    return text


def _strip_latex(text: str) -> str:
    text = re.sub(r"(?<!\\)%.*", "", text)
    text = re.sub(r"\\(?:begin|end)\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:cite[tp]?|ref|eqref|label|autoref|cref|Cref|url)\*?(?:\[[^\]]*\])*\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:texttt|verb)\{[^}]*\}", " CODESPAN ", text)
    text = re.sub(r"\\(?:emph|textbf|textit|textsc|mbox|text)\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\$[^$]*\$", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    return text.replace("{", " ").replace("}", " ").replace("~", " ")


def _drop_citations(text: str) -> str:
    text = re.sub(r"\((?=[^()]*\b(?:1[89]|20)\d{2}[a-z]?\b)[^()]*\)", " ", text)  # (Author et al., 2020; ...)
    return re.sub(r"\[\d+(?:[,–-]\s*\d+)*\]", " ", text)                     # [3], [3-5]


def parse(text: str) -> list[Section]:
    """Split a Markdown or LaTeX manuscript into sections with their kind, body paragraphs and captions."""
    latex = bool(re.search(r"\\(?:section|begin\{document\}|documentclass)\b", text))
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"^```.*?^```", "", text, flags=re.DOTALL | re.MULTILINE)
    if latex:
        text = re.sub(r"\\begin\{abstract\}", "\n\\\\section{Abstract}\n", text)
        captions = re.findall(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", text)
        text = re.sub(r"\\begin\{(figure|table|equation|align|tabular)\*?\}.*?\\end\{\1\*?\}", "\n", text, flags=re.DOTALL)
    sections: list[Section] = [Section("(front matter)", 0, "front")]
    seen_body = False
    stack: list[Section] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            chunk = " ".join(para).strip()
            para.clear()
            if not chunk:
                return
            target = sections[-1]
            if re.match(r"^(\*\*)?(Figure|Fig\.|Table)\s+S?\d", chunk):
                target.captions.append(chunk)
            else:
                target.text.append(chunk)

    for line in text.splitlines():
        md = None if latex else re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        tex = re.match(r"^\s*\\(section|subsection|subsubsection)\*?\{(.*)\}\s*$", line) if latex else None
        if md or tex:
            flush()
            level = len(md.group(1)) if md else {"section": 1, "subsection": 2, "subsubsection": 3}[tex.group(1)]
            heading = (md or tex).group(2)
            own = _kind(heading)
            while stack and stack[-1].level >= level:
                stack.pop()
            parent = stack[-1].kind if stack else None
            if not seen_body:
                if own in BODY_START:
                    seen_body = True
                    kind = own
                else:
                    kind = "front"
            else:
                kind = own or (parent if parent not in (None, "front") else "other")
            section = Section(heading, level, kind)
            sections.append(section)
            stack.append(section)
            continue
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if not latex and (stripped.startswith("|") or stripped.startswith("![")):
            flush()
            continue
        para.append(stripped.lstrip("> ").lstrip("-*+ ") if not latex else stripped)
    flush()
    if not seen_body:  # no recognisable Abstract or Introduction: measure everything that is not back matter
        for s in sections:
            if s.kind == "front":
                s.kind = _kind(s.heading) or "other"
    if latex:
        first_body = next((s for s in sections if s.kind not in ("front", "back")), sections[-1])
        first_body.captions.extend(captions)
    return sections


def _clean(paragraph: str, latex: bool) -> str:
    paragraph = _strip_latex(paragraph) if latex else _strip_markdown(paragraph)
    return re.sub(r"\s+", " ", _drop_citations(paragraph)).strip()


def _sentences(text: str) -> list[str]:
    protected = text
    for i, abbr in enumerate(ABBREVIATIONS):
        protected = protected.replace(abbr, abbr.replace(".", f"\x00{i}\x00"))
    parts = re.split(r"(?<=[.!?])\s+(?=[\"“(\[]?[A-Z0-9])", protected)
    out = []
    for part in parts:
        restored = re.sub(r"\x00\d+\x00", ".", part).strip()
        if len(WORD.findall(restored)) >= 3:
            out.append(restored)
    return out


def measure(paragraphs: list[str], latex: bool = False) -> dict[str, float]:
    """The reading measures of a list of paragraphs."""
    text = " ".join(_clean(p, latex) for p in paragraphs)
    code = text.count("CODESPAN")
    text = text.replace("CODESPAN", "")
    sents = _sentences(text)
    words = WORD.findall(text)
    n = len(words) + code
    if not n or not sents:
        return {k: 0.0 for k in HARDER}
    lens = [len(WORD.findall(s)) for s in sents]
    endings = 0
    for s in sents:
        breaks = [m.end() for m in CLAUSE_BREAK.finditer(s.rstrip(".!?)"))]
        if breaks and CAVEAT.search(s[breaks[-1]:]):
            endings += 1
    acronyms = [a for a in ACRONYM.findall(text) if not ROMAN.match(a) and len(a.rstrip("s")) >= 2]
    per100 = lambda k: round(100 * k / n, 2)
    return {
        "words": n,
        "sentences": len(sents),
        "mean_sentence_words": round(sum(lens) / len(lens), 1),
        "long_sentence_share": round(sum(1 for x in lens if x > LONG_SENTENCE) / len(lens), 3),
        "negations_per_100": per100(len(NEGATION.findall(text))),
        "limiting_per_100": per100(len(LIMITING.findall(text))),
        "hedges_per_100": per100(len(HEDGE.findall(text))),
        "caveat_ending_share": round(endings / len(sents), 3),
        "numbers_per_100": per100(sum(1 for w in words if NUMBER.match(w))),
        "first_person_per_100": per100(len(FIRST_PERSON.findall(text))),
        "acronyms_per_100": per100(len(acronyms)),
        "code_per_100": per100(code),
    }


def profile(path: Path) -> dict[str, object]:
    """Measures for the body, each kind of section, each section and the captions of one manuscript."""
    raw = path.read_text(encoding="utf-8")
    latex = path.suffix == ".tex" or bool(re.search(r"\\(?:section|documentclass)\b", raw))
    sections = parse(raw)
    body = [s for s in sections if s.kind not in ("front", "back")]
    kinds: dict[str, list[str]] = {}
    for s in body:
        kinds.setdefault(s.kind, []).extend(s.text)
    whole = measure([p for s in body for p in s.text], latex)
    total = whole["words"] or 1
    by_kind = {}
    for k, paras in kinds.items():
        m = measure(paras, latex)
        if m["words"]:
            by_kind[k] = {**m, "share_of_body": round(m["words"] / total, 3)}
    return {
        "file": str(path),
        "body": whole,
        "kinds": by_kind,
        "sections": [{"heading": re.sub(r"[*_#]", "", s.heading).strip(), "kind": s.kind,
                      **measure(s.text, latex)} for s in body if s.text],
        "captions": {**measure([c for s in body for c in s.captions], latex),
                     "count": sum(len(s.captions) for s in body)},
    }


def changes(before: dict[str, object], after: dict[str, object], threshold: float = 0.15) -> list[dict[str, object]]:
    """Measures that moved by more than `threshold` (relative), with the direction a reader would feel."""
    found = []

    def compare(scope: str, b: dict[str, float], a: dict[str, float]) -> None:
        for key, harder in HARDER.items():
            if harder is None or key not in b or key not in a:
                continue
            if key in ("negations_per_100", "limiting_per_100", "hedges_per_100") and scope in CAVEAT_HOME:
                continue  # caveats belong here; more of them is not a cost to the story
            old, new = b[key], a[key]
            base = max(abs(old), 0.05 if "share" in key else 0.5)
            if abs(new - old) / base < threshold:
                continue
            harder_now = (new - old) * harder > 0
            found.append({"scope": scope, "measure": key, "before": old, "after": new,
                          "reads": "harder" if harder_now else "easier",
                          "sentence": f"{MEANING[key]} in {'the body' if scope == 'body' else scope} went from "
                                      f"{old:g} to {new:g}"})

    compare("body", before["body"], after["body"])
    for kind in sorted(set(before["kinds"]) & set(after["kinds"])):
        compare(kind, before["kinds"][kind], after["kinds"][kind])
    for kind in sorted(set(before["kinds"]) | set(after["kinds"])):
        b = before["kinds"].get(kind, {}).get("share_of_body", 0.0)
        a = after["kinds"].get(kind, {}).get("share_of_body", 0.0)
        if abs(a - b) >= 0.05:
            found.append({"scope": kind, "measure": "share_of_body", "before": b, "after": a, "reads": "changed",
                          "sentence": f"{kind} went from {b:.0%} to {a:.0%} of the body"})
    cb, ca = before["captions"], after["captions"]
    if ca.get("count") and ca["negations_per_100"] > cb.get("negations_per_100", 0) + 0.5:
        found.append({"scope": "captions", "measure": "negations_per_100", "before": cb.get("negations_per_100", 0),
                      "after": ca["negations_per_100"], "reads": "harder",
                      "sentence": "captions say more about what a figure does not show"})
    order = {"harder": 0, "easier": 1, "changed": 2}
    return sorted(found, key=lambda c: (order[c["reads"]], c["scope"] != "body", c["scope"]))


def markdown(profiles: list[dict[str, object]], labels: list[str], moved: list[dict[str, object]] | None) -> str:
    keys = [k for k in HARDER if k not in ("words", "sentences")]
    head = "| Measure | " + " | ".join(labels) + " |\n|---|" + "---|" * len(labels)
    rows = ["| words | " + " | ".join(f"{p['body']['words']:,.0f}" for p in profiles) + " |"]
    rows += [f"| {MEANING[k]} | " + " | ".join(f"{p['body'][k]:g}" for p in profiles) + " |" for k in keys]
    out = ["## The body", "", head, *rows, "", "## Share of the body by kind of section", ""]
    kinds = sorted({k for p in profiles for k in p["kinds"]})
    out += ["| Kind | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    out += [f"| {k} | " + " | ".join(f"{p['kinds'].get(k, {}).get('share_of_body', 0):.0%}" for p in profiles) + " |"
            for k in kinds]
    out += ["", "## Caveats by kind of section (negations, limiting words and hedges per 100 words)", ""]
    out += ["| Kind | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for k in kinds:
        cells = []
        for p in profiles:
            m = p["kinds"].get(k)
            cells.append("—" if not m else f"{m['negations_per_100'] + m['limiting_per_100'] + m['hedges_per_100']:.1f}")
        out.append(f"| {k} | " + " | ".join(cells) + " |")
    if moved is not None:
        out += ["", "## What moved", ""]
        if not moved:
            out.append("No measure moved by more than 15%.")
        for c in moved:
            mark = {"harder": "Harder to read:", "easier": "Easier to read:", "changed": "Changed:"}[c["reads"]]
            out.append(f"- {mark} {c['sentence']}.")
    out += ["", "These measures are proxies. Read the passages they point to before changing anything."]
    return "\n".join(out) + "\n"


@app.command()
def main(
    files: list[Path] = typer.Argument(..., help="One or more manuscripts, oldest first."),
    before: Path | None = typer.Option(None, "--before", help="An earlier version to compare the file with."),
    label: list[str] = typer.Option([], "--label", help="A column name per file, in order."),
    json_out: Path | None = typer.Option(None, "--json", help="Write every measure as JSON."),
    md_out: Path | None = typer.Option(None, "--md", help="Write the Markdown report to a file."),
) -> None:
    paths = ([before] if before else []) + list(files)
    for p in paths:
        if not p.is_file():
            typer.echo(f"not a file: {p}", err=True)
            raise typer.Exit(2)
    if label and len(label) != len(paths):
        typer.echo(f"{len(label)} labels for {len(paths)} files", err=True)
        raise typer.Exit(2)
    names = label or [p.stem if len({q.stem for q in paths}) == len(paths) else str(p) for p in paths]
    profiles = [profile(p) for p in paths]
    moved = changes(profiles[-2], profiles[-1]) if len(profiles) >= 2 else None
    report = markdown(profiles, names, moved)
    if json_out:
        json_out.write_text(json.dumps({"versions": [dict(p, label=n) for p, n in zip(profiles, names)],
                                        "moved": moved}, indent=2, ensure_ascii=False), encoding="utf-8")
    if md_out:
        md_out.write_text(report, encoding="utf-8")
    typer.echo(report, nl=False)


def _utf8_console() -> None:
    """Print UTF-8 whatever the console's code page (a Windows console is often cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # a stream that cannot change its encoding keeps it
                pass


if __name__ == "__main__":
    _utf8_console()
    app()
