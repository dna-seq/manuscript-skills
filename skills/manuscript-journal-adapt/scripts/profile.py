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

    uv run --script profile.py PAPER.md
    uv run --script profile.py PAPER.tex --sample earlier_paper.md --sample thesis_ch2.md --top 15
    uv run --script profile.py PAPER.md --json profile.json
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
NUMBER_ANCHOR = re.compile(r"(?<![A-Za-z])\d")
CITATION_ANCHOR = re.compile(r"\[\d+(?:\s*[-–,]\s*\d+)*\]|\((?:[^()]*?\b(?:19|20)\d{2}[a-z]?\b[^()]*?)\)|\[c\]")


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
        block.append(stripped.lstrip("-*+ ").strip())
    if block:
        out.append((start, " ".join(block)))
    return [(n, p) for n, p in out if len(WORD.findall(p)) >= 8]


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
    paras = paragraphs(clean(text, latex))
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
        words = WORD.findall(para)
        n_words = len(words)
        n_hits = sum(len(v) for v in hits.values())
        anchors = len(NUMBER_ANCHOR.findall(para)) + len(CITATION_ANCHOR.findall(para))
        totals.update({sid: len(v) for sid, v in hits.items()})
        para_reports.append({"line": line, "words": n_words, "sentences": len(sents), "hits": hits,
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


def to_markdown(path: str, doc: dict[str, Any], smells: dict[str, dict[str, Any]], top: int,
                baseline: Optional[list[dict[str, Any]]]) -> str:
    m = doc["metrics"]
    out = [f"# Style profile: {path}", "",
           "Counts of named patterns and style measures. Not an AI detector; no number here is a probability.", "",
           "| measure | value |", "|---|---|"]
    out += [f"| {k.replace('_', ' ')} | {v if v is not None else 'n/a'} |" for k, v in m.items()]
    if baseline is not None:
        out += ["", "## Compared with the authors' own writing", "",
                "| measure | manuscript | authors | ratio | departs |", "|---|---|---|---|---|"]
        out += [f"| {r['measure'].replace('_', ' ')} | {r['manuscript']} | {r['authors']} | {r['ratio'] or 'n/a'} "
                f"| {'**yes**' if r['departs'] else ''} |" for r in baseline]
    out += ["", "## Most frequent smells", ""]
    out += [f"- {sid} {smells[sid]['name']}: {n}" for sid, n in list(doc["smell_totals"].items())[:12]] or ["- none"]
    ranked = sorted((p for p in doc["paragraphs"] if p["words"] >= 15 and p["hits"]),
                    key=lambda p: (-p["smells_per_100_words"], p["anchors"]))[:top]
    out += ["", f"## Paragraphs to edit first (top {len(ranked)} by smell density)", ""]
    for p in ranked:
        if not p["hits"]:
            continue
        hits = "; ".join(f"{sid} {smells[sid]['name']}: " + ", ".join(f"“{h}”" for h in v[:3])
                         for sid, v in p["hits"].items())
        anchor_note = " **no numbers or citations**" if p["anchors"] == 0 else ""
        out.append(f"- **L{p['line']}** ({p['words']} words, {p['smells_per_100_words']} per 100 words,"
                   f" {p['anchors']} anchors{anchor_note}): {hits}\n  > {p['text']}…")
    out += ["", "Each id is an entry in `references/llm-smells.md`, with its fix and its \"Leave it when\"."]
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
    md = to_markdown(str(path), doc, smells, top, baseline)
    if md_out:
        md_out.write_text(md, encoding="utf-8")
        typer.echo(f"wrote {md_out}")
    else:
        typer.echo(md)


if __name__ == "__main__":
    app()
