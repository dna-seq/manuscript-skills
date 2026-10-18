# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6"]
# ///
"""Find where a manuscript reads as machine-written, and how far its style is from the authors' own.

Not an AI detector and not a probability. It counts named smells (references/smell-patterns.yaml, each
keyed to an entry of references/llm-smells.md with its fix), ranks paragraphs by smell density so editing
starts where it matters, and profiles style: sentence-length spread, connective density, lexical
diversity, LLM-vocabulary and em-dash rates, anchors (numbers and citations) per paragraph. Given a sample
of the authors' own writing, it reports which measures depart from that baseline.

    uv run --script style_profile.py PAPER.md
    uv run --script style_profile.py PAPER.tex --sample earlier_paper.md --sample thesis_ch2.md --top 15
    uv run --script style_profile.py PAPER.md --json profile.json
"""

from __future__ import annotations

import csv
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
import yaml

app = typer.Typer(add_completion=False, no_args_is_help=True)

HERE = Path(__file__).resolve().parent
PATTERNS_YAML = HERE.parent / "references" / "smell-patterns.yaml"
KOBAK_CSV = HERE.parents[1] / "manuscript-integrity-check" / "references" / "kobak_2024_style_words.csv"

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
LATEX_COMMENT = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
LATEX_CITE = re.compile(r"\\cite[pt]?\*?(?:\[[^\]]*\])?\{[^}]+\}")
LATEX_REF = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref)\{[^}]+\}")
LATEX_WRAP = re.compile(r"\\(?:textbf|textit|emph|texttt|textsc|underline|mbox)\{([^{}]*)\}")
LATEX_ENV_SKIP = re.compile(r"\\begin\{(table|figure|equation|align|tabular|verbatim|lstlisting)\*?\}.*?"
                            r"\\end\{\1\*?\}", re.DOTALL)
HEADING = re.compile(r"^\s*(?:#{1,6}\s|\\(?:sub)*section\*?\{|\\chapter\*?\{|\\paragraph\{)")
REFERENCES_HEADING = re.compile(r"^\s*(?:#{1,6}\s*\**\s*(?:\d+\.?\s*)?(?:references|bibliography|literature cited)\b|"
                                r"\\(?:section|chapter)\*?\{(?:references|bibliography)\}|\\begin\{thebibliography\}|"
                                r"\\bibliography\{)", re.IGNORECASE)
ABBREVIATIONS = re.compile(r"\b(?:et al|e\.g|i\.e|Fig|Figs|Eq|Eqs|Ref|Refs|vs|approx|cf|ca|No|Dr|Prof|Suppl|Tab|Sect)\.$",
                           re.IGNORECASE)
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
LIST_MARKER = re.compile(r"^[-*+]\s+")
NUMBER_ANCHOR = re.compile(r"(?<![A-Za-z])\d")
CITATION_ANCHOR = re.compile(r"\[\d+(?:\s*[-–,]\s*\d+)*\]|\((?:[^()]*?\b(?:19|20)\d{2}[a-z]?\b[^()]*?)\)|\[c\]")


# Words that tie a sentence to the one before it: connectives, subordinators, and anaphoric openers.
LINK_RE = re.compile(r"\b(?:because|since|so|thus|therefore|hence|consequently|as a result|which|whereas|while|"
                     r"although|though|but|however|yet|instead|if|when|unless|until|after|before|then|so that|"
                     r"this means|that is|for example|for instance|in turn|in contrast|by contrast)\b", re.IGNORECASE)
SHORT_SENTENCE_WORDS = 12


def declarative_chain(sents: list[str]) -> Optional[list[str]]:
    """Four or more sentences, mostly short, with almost nothing linking them (llm-smells C16)."""
    if len(sents) < 4:
        return None
    lengths = [len(WORD.findall(x)) for x in sents]
    short = sum(1 for n in lengths if n <= SHORT_SENTENCE_WORDS)
    links = sum(len(LINK_RE.findall(x)) for x in sents)
    if short / len(sents) >= 0.6 and links / len(sents) < 0.3:
        return [x for x, n in zip(sents, lengths) if n <= SHORT_SENTENCE_WORDS][:3]
    return None


def load_smells() -> dict[str, dict[str, Any]]:
    raw = yaml.safe_load(PATTERNS_YAML.read_text(encoding="utf-8"))["smells"]
    return {sid: {"name": s["name"], "scope": s.get("scope", "any"),
                  "patterns": [re.compile(p, re.IGNORECASE) for p in s["patterns"]]} for sid, s in raw.items()}


def load_kobak() -> set[str]:
    with KOBAK_CSV.open(encoding="utf-8") as fh:
        return {row["word"] for row in csv.DictReader(fh) if float(row["r"]) >= 2.0}


def clean(text: str, latex: bool) -> str:
    """Prose a reader sees, with line breaks kept so paragraph line numbers stay right."""
    def blank(m: re.Match[str]) -> str:
        return "\n" * m.group(0).count("\n")

    text = HTML_COMMENT.sub(blank, text)
    if latex:
        text = LATEX_COMMENT.sub("", text)
        text = LATEX_ENV_SKIP.sub(blank, text)
        text = LATEX_CITE.sub("[c]", text)
        text = LATEX_REF.sub("1", text)
        for _ in range(3):
            text = LATEX_WRAP.sub(r"\1", text)
    return text


def paragraphs(text: str) -> list[tuple[int, str]]:
    """(first line number, paragraph text) for prose paragraphs before the references."""
    out: list[tuple[int, str]] = []
    block: list[str] = []
    start = 0
    in_code = False
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if REFERENCES_HEADING.match(stripped):
            break
        skip = (in_code or not stripped or HEADING.match(stripped) or stripped.startswith(("|", "![", "<", "\\begin",
                                                                                              "\\end", "\\item[")))
        if skip:
            if block:
                out.append((start, " ".join(block)))
                block = []
            continue
        if not block:
            start = i
        block.append(LIST_MARKER.sub("", stripped))  # "- item" loses its marker; "**Figure 2.**" keeps its bold
    if block:
        out.append((start, " ".join(block)))
    return [(n, p) for n, p in out if len(WORD.findall(p)) >= 8]


HEADING_TEXT = re.compile(r"^\s*(?:(#{1,6})\s+(.+?)[\s#]*$|\\(chapter|section|subsection|subsubsection|paragraph)"
                          r"\*?(?:\[[^\]]*\])?\{(.*)\}\s*$)")
TEX_LEVEL = {"chapter": 1, "section": 2, "subsection": 3, "subsubsection": 4, "paragraph": 5}
# "6. Conclusion", "5.1 Limitations", "A.2 Extra runs"; a bare capital ("A Study of ...") is a word, not a number.
NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*|[A-Z](?:\.\d+)+|[A-Z](?=\.))\.?\s+(\S.*)$")


def headings(text: str) -> list[tuple[int, int, str]]:
    """(line, level, title) of each Markdown or LaTeX heading, without the paper's title (a lone level-1 heading)."""
    out: list[tuple[int, int, str]] = []
    in_code = False
    for i, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        m = None if in_code else HEADING_TEXT.match(line)
        if m:
            level = len(m.group(1)) if m.group(1) else TEX_LEVEL[m.group(3)]
            title = " ".join(re.sub(r"\\[A-Za-z]+\*?|[{}*_`]", "", m.group(2) or m.group(4)).split())
            if title:
                out.append((i, level, title))
    if len(out) > 1 and out[0][1] == 1 and sum(level == 1 for _, level, _ in out) == 1:
        out = out[1:]
    return out


def section_at(heads: list[tuple[int, int, str]], line: int) -> str:
    """The heading path in force at `line`, e.g. 'Results > Performance' ('' before the first heading)."""
    path: list[tuple[int, str]] = []
    for at, level, title in heads:
        if at > line:
            break
        while path and path[-1][0] >= level:
            path.pop()
        path.append((level, title))
    return " > ".join(title for _, title in path)


def place(section: str, lines: str) -> str:
    """'the Results, Performance (line 12)' or 'section 5.1, Limitations (lines 40 to 52)', ready to follow 'In'.

    A numbered heading names its parents already, so only the deepest one is given."""
    if not section:
        return f"the text before the first heading ({lines})"
    numbered = NUMBERED_HEADING.match(section.split(" > ")[-1])
    where = f"section {numbered.group(1)}, {numbered.group(2)}" if numbered else "the " + section.replace(" > ", ", ")
    return f"{where} ({lines})"


def sentences(paragraph: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\[“\"])", paragraph)
    merged: list[str] = []
    for part in parts:
        if merged and ABBREVIATIONS.search(merged[-1]):
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return [s.strip() for s in merged if WORD.search(s)]


def mtld(words: list[str], threshold: float = 0.72) -> Optional[float]:
    """Measure of textual lexical diversity (McCarthy & Jarvis 2010), mean of forward and backward passes."""
    if len(words) < 50:
        return None

    def one_pass(seq: list[str]) -> float:
        factors, types, count = 0.0, set(), 0
        for w in seq:
            count += 1
            types.add(w)
            if len(types) / count <= threshold:
                factors += 1
                types, count = set(), 0
        if count:
            factors += (1 - len(types) / count) / (1 - threshold)
        return len(seq) / factors if factors else float(len(seq))

    return round((one_pass(words) + one_pass(words[::-1])) / 2, 1)


def profile_text(text: str, latex: bool, smells: dict[str, dict[str, Any]], kobak: set[str]) -> dict[str, Any]:
    cleaned = clean(text, latex)
    paras = paragraphs(cleaned)
    heads = headings(cleaned)
    all_sentences: list[str] = []
    para_reports: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()
    for line, para in paras:
        sents = sentences(para)
        all_sentences += sents
        hits: dict[str, list[str]] = {}
        for k, sent in enumerate(sents):
            last = k == len(sents) - 1
            for sid, smell in smells.items():
                if smell["scope"] == "end" and not last:
                    continue
                for rx in smell["patterns"]:
                    target = sent.lstrip("\"“(") if smell["scope"] in ("start", "end") else sent
                    for m in rx.finditer(target):
                        if smell["scope"] == "start" and m.start() != 0:
                            continue
                        hits.setdefault(sid, []).append(m.group(0).strip())
        chain = declarative_chain(sents)
        if chain:
            hits["C16"] = chain
        words = WORD.findall(para)
        n_words = len(words)
        n_hits = sum(len(v) for v in hits.values())
        anchors = len(NUMBER_ANCHOR.findall(para)) + len(CITATION_ANCHOR.findall(para))
        totals.update({sid: len(v) for sid, v in hits.items()})
        para_reports.append({"line": line, "section": section_at(heads, line), "words": n_words,
                             "sentences": len(sents), "hits": hits,
                             "smells_per_100_words": round(100 * n_hits / n_words, 2), "anchors": anchors,
                             "text": para[:160]})
    words = [w.lower() for _, p in paras for w in WORD.findall(p)]
    n = max(len(words), 1)
    lengths = [len(WORD.findall(s)) for s in all_sentences]
    para_lengths = [p["words"] for p in para_reports]
    connectors = totals.get("C5", 0)
    body = " ".join(p for _, p in paras)

    def cv(xs: list[int]) -> Optional[float]:
        return round(statistics.pstdev(xs) / statistics.mean(xs), 2) if len(xs) > 1 and statistics.mean(xs) else None

    metrics = {
        "words": len(words),
        "paragraphs": len(paras),
        "sentences": len(lengths),
        "sentence_length_mean": round(statistics.mean(lengths), 1) if lengths else None,
        "sentence_length_sd": round(statistics.pstdev(lengths), 1) if len(lengths) > 1 else None,
        "sentence_length_cv": cv(lengths),
        "paragraph_length_cv": cv(para_lengths),
        "connector_starts_per_100_sentences": round(100 * connectors / max(len(lengths), 1), 1),
        "llm_vocabulary_per_1000_words": round(1000 * sum(1 for w in words if w in kobak) / n, 2),
        "em_dashes_per_1000_words": round(1000 * body.count("—") / n, 2),
        "semicolons_per_1000_words": round(1000 * body.count(";") / n, 2),
        "smells_per_1000_words": round(1000 * sum(totals.values()) / n, 2),
        "anchors_per_100_words": round(100 * sum(p["anchors"] for p in para_reports) / n, 2),
        "lexical_diversity_mtld": mtld(words),
    }
    return {"metrics": metrics, "smell_totals": dict(totals.most_common()), "paragraphs": para_reports}


# Measures compared with the authors' own writing, and the direction that reads as machine-written.
BASELINE_MEASURES = {
    "smells_per_1000_words": "higher",
    "llm_vocabulary_per_1000_words": "higher",
    "connector_starts_per_100_sentences": "higher",
    "em_dashes_per_1000_words": "higher",
    "sentence_length_cv": "lower",
    "paragraph_length_cv": "lower",
    "lexical_diversity_mtld": "either",
    "anchors_per_100_words": "lower",
}


def compare(doc: dict[str, Any], sample: dict[str, Any], factor: float = 1.5) -> list[dict[str, Any]]:
    """Measures where the manuscript departs from the authors' sample by more than `factor` in the telling direction."""
    out = []
    for key, direction in BASELINE_MEASURES.items():
        a, b = doc["metrics"].get(key), sample["metrics"].get(key)
        if a is None or b is None:
            continue
        if b == 0:
            departs = a > 0 and direction in ("higher", "either")
            ratio = None
        else:
            ratio = round(a / b, 2)
            departs = ((direction in ("higher", "either") and ratio >= factor)
                       or (direction in ("lower", "either") and ratio <= 1 / factor))
        out.append({"measure": key, "manuscript": a, "authors": b, "ratio": ratio, "departs": departs})
    return out


MEASURES = {
    "words": "Words of prose (headings, tables and references left out)",
    "paragraphs": "Paragraphs",
    "sentences": "Sentences",
    "sentence_length_mean": "Average sentence length, in words",
    "sentence_length_sd": "Spread of sentence lengths (standard deviation, in words)",
    "sentence_length_cv": "Variation in sentence length (standard deviation divided by the mean; a low value means "
                          "uniform sentences)",
    "paragraph_length_cv": "Variation in paragraph length (the same measure for paragraphs)",
    "connector_starts_per_100_sentences": "Sentences that open with a stock connector such as “Moreover” or "
                                          "“Furthermore”, per 100 sentences",
    "llm_vocabulary_per_1000_words": "Words that became far more frequent in scientific abstracts after 2023 (the "
                                     "excess-vocabulary list of Kobak et al.), per 1,000 words",
    "em_dashes_per_1000_words": "Em dashes per 1,000 words",
    "semicolons_per_1000_words": "Semicolons per 1,000 words",
    "smells_per_1000_words": "Stock phrases and sentence shapes (the patterns listed below), per 1,000 words",
    "anchors_per_100_words": "Numbers and citations per 100 words",
    "lexical_diversity_mtld": "Vocabulary diversity (MTLD, the measure of textual lexical diversity; higher means "
                              "more varied wording)",
}
SMALL_NUMBERS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def _count(n: int, one: str, many: str) -> str:
    return f"{SMALL_NUMBERS[n] if n < len(SMALL_NUMBERS) else n} {one if n == 1 else many}"


def _listed(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _times(n: int) -> str:
    return {1: "once", 2: "twice"}.get(n, f"{n} times")


def _pattern(sid: str, smells: dict[str, dict[str, Any]]) -> str:
    return smells[sid]["name"] if sid in smells else sid


def _value(v: Any) -> str:
    return "not measured (too little text)" if v is None else str(v)


def _paragraph_line(p: dict[str, Any], smells: dict[str, dict[str, Any]]) -> str:
    """One paragraph to reread, as a sentence: where it is, how dense the patterns are, and what they are."""
    n = sum(len(v) for v in p["hits"].values())
    found = [f"{_pattern(sid, smells)} ({sid}) in " + _listed([f"“{h}”" for h in v[:3]]) for sid, v in p["hits"].items()]
    anchors = ", and it has no number or citation" if p["anchors"] == 0 else ""
    where = place(p.get("section", ""), "line " + str(p["line"]))
    cut = "…" if len(p["text"]) >= 160 else ""
    return (f"- In {where}, a paragraph of {p['words']} words has {_count(n, 'pattern', 'patterns')} "
            f"({p['smells_per_100_words']} for every 100 words){anchors}. What was found: {'; '.join(found)}.\n"
            f"  The paragraph begins: “{p['text']}{cut}”")


def to_markdown(path: str, doc: dict[str, Any], smells: dict[str, dict[str, Any]], top: int,
                baseline: Optional[list[dict[str, Any]]], factor: float = 1.5) -> str:
    m = doc["metrics"]
    out = [f"# Writing patterns and style measures: {path}", "",
           "These counts show where to start editing. They are not an AI detector, and no number here is a "
           "probability that a person or a model wrote the text.", "",
           "| What is measured | Value |", "|---|---|"]
    out += [f"| {MEASURES.get(k, k.replace('_', ' '))} | {_value(v)} |" for k, v in m.items()]
    if baseline is not None:
        out += ["", "## Compared with the authors' own writing", "",
                f"A measure is far from the authors' own writing when the manuscript's value is at least {factor} "
                "times theirs, or that much lower, in the direction that reads as machine-written.", "",
                "| What is measured | This manuscript | The authors' writing | Ratio | Far from the authors' writing |",
                "|---|---|---|---|---|"]
        out += [f"| {MEASURES.get(r['measure'], r['measure'].replace('_', ' '))} | {r['manuscript']} | {r['authors']} "
                f"| {r['ratio'] if r['ratio'] is not None else 'none (the authors’ value is zero)'} "
                f"| {'**yes**' if r['departs'] else 'no'} |" for r in baseline]
    out += ["", "## The most frequent patterns", ""]
    totals = list(doc["smell_totals"].items())[:12]
    out += [f"- {_pattern(sid, smells)[:1].upper()}{_pattern(sid, smells)[1:]} ({sid}): {_times(n)}."
            for sid, n in totals] or ["None of the patterns was found."]
    ranked = sorted((p for p in doc["paragraphs"] if p["words"] >= 15 and p["hits"]),
                    key=lambda p: (-p["smells_per_100_words"], p["anchors"]))[:top]
    out += ["", "## Paragraphs to reread first", "",
            f"The {_count(len(ranked), 'paragraph', 'paragraphs')} with the most patterns for their length, densest "
            "first." if ranked else "No paragraph of 15 words or more has any of the patterns.", ""]
    out += [_paragraph_line(p, smells) for p in ranked]
    out += ["", "Each pattern marks a place to reread, not an error: a sentence that still says something specific "
                "can stay. The code in parentheses identifies the pattern in the editor's catalogue."]
    return "\n".join(out) + "\n"


@app.command()
def main(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    sample: Annotated[Optional[list[Path]], typer.Option(exists=True, dir_okay=False,
                                                         help="The authors' own writing, as a baseline (repeatable)")] = None,
    top: Annotated[int, typer.Option(help="How many paragraphs to list")] = 10,
    factor: Annotated[float, typer.Option(help="Ratio to the authors' baseline that counts as a departure")] = 1.5,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the full profile as JSON")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Write the Markdown report here")] = None,
) -> None:
    smells, kobak = load_smells(), load_kobak()
    doc = profile_text(path.read_text(encoding="utf-8"), path.suffix == ".tex", smells, kobak)
    baseline = None
    if sample:
        joined = "\n\n".join(s.read_text(encoding="utf-8") for s in sample)
        latex = all(s.suffix == ".tex" for s in sample)
        base = profile_text(joined, latex, smells, kobak)
        baseline = compare(doc, base, factor)
        doc["authors_baseline"] = base["metrics"]
        doc["comparison"] = baseline
    if json_out:
        json_out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    md = to_markdown(str(path), doc, smells, top, baseline, factor)
    if md_out:
        md_out.write_text(md, encoding="utf-8")
        typer.echo(f"Wrote the report to {md_out}.")
    else:
        typer.echo(md)


if __name__ == "__main__":
    app()
