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

The check every edit and every report must pass (`--check`) adds two verdicts and a reading list. With
`--before`, it names each pattern the edit added that the original did not have. It names each pattern used
three or more times under one heading (only the headings the edit changed, when `--before` is given): one
use can stand, a run of them is the habit a reader notices. And it prints every entry of the catalogue in
one line, because the counts find only the patterns that have a regular expression: the editor reads the
text against that list and finds the rest by reading. `--report` checks a report to the authors instead
of a manuscript: quoted manuscript text is skipped, and "you" and questions are expected there.

    uv run --script style_profile.py PAPER.md
    uv run --script style_profile.py PAPER.tex --sample earlier_paper.md --sample thesis_ch2.md --top 15
    uv run --script style_profile.py PAPER.md --json profile.json
    uv run --script style_profile.py EDITED.md --before ORIGINAL.md --check [--keep C1]
    uv run --script style_profile.py REPORT.md --report --check

Exit codes: 0 when the check passed or was not asked for, 1 while `--check` finds an added pattern or a
cluster that `--keep` does not name, 2 for a usage error.
"""

from __future__ import annotations

import csv
import hashlib
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
CATALOGUE_MD = HERE.parent / "references" / "llm-smells.md"
KOBAK_CSV = HERE.parents[1] / "manuscript-integrity-check" / "references" / "kobak_2024_style_words.csv"

# A report to the authors quotes the manuscript, addresses the authors and asks them questions.
REPORT_SKIPPED = {"C7": "a report asks the authors questions", "G2": "a report addresses the authors"}
QUOTED_SPAN = re.compile(r"“[^”]*”|\"[^\"\n]*\"|`[^`\n]*`")
BLOCKQUOTE = re.compile(r"^[ \t]*>.*$", re.MULTILINE)
CLUSTER = 3

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


def clean(text: str, latex: bool, report: bool = False) -> str:
    """Prose a reader sees, with line breaks kept so paragraph line numbers stay right.

    In a report, quotations, block quotes and code are the manuscript's words, not the report's: a quotation
    becomes as many neutral words, so a quoted "Moreover" is not counted against the report while the
    sentence quoting it keeps its length."""
    def blank(m: re.Match[str]) -> str:
        return "\n" * m.group(0).count("\n")

    def neutral(m: re.Match[str]) -> str:
        return "“" + " ".join(["q"] * max(len(WORD.findall(m.group(0))), 1)) + "”" + blank(m)

    text = HTML_COMMENT.sub(blank, text)
    if report:
        text = BLOCKQUOTE.sub("", text)
        text = QUOTED_SPAN.sub(neutral, text)
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


def profile_text(text: str, latex: bool, smells: dict[str, dict[str, Any]], kobak: set[str],
                 report: bool = False) -> dict[str, Any]:
    if report:
        smells = {sid: s for sid, s in smells.items() if sid not in REPORT_SKIPPED}
    cleaned = clean(text, latex, report)
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
                             "text": para[:160], "digest": hashlib.sha1(para.encode("utf-8")).hexdigest()[:12]})
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


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def _hit_keys(doc: dict[str, Any]) -> Counter[tuple[str, str]]:
    """Each hit as (pattern, matched words); a chain of short sentences (C16) counts once per heading."""
    keys: Counter[tuple[str, str]] = Counter()
    for p in doc["paragraphs"]:
        for sid, found in p["hits"].items():
            if sid == "C16":
                keys[(sid, p["section"])] += 1
            else:
                keys.update((sid, _norm(h)) for h in found)
    return keys


def added_hits(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Hits the edit introduced: found in the edited text more often than in the original.

    Matching is by the matched words, so a sentence moved or left alone is not reported, and a pattern kept
    while its sentence was rewritten around it is not reported either."""
    extra = _hit_keys(after) - _hit_keys(before)
    out: list[dict[str, Any]] = []
    for p in after["paragraphs"]:
        for sid, found in p["hits"].items():
            for h in (found[:1] if sid == "C16" else found):
                key = (sid, p["section"]) if sid == "C16" else (sid, _norm(h))
                if extra[key] > 0:
                    extra[key] -= 1
                    out.append({"id": sid, "text": h, "line": p["line"], "section": p["section"]})
    return out


def changed_sections(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    """Headings whose paragraphs differ between the two versions; a renamed heading counts as changed."""
    def by_section(doc: dict[str, Any]) -> dict[str, Counter[str]]:
        out: dict[str, Counter[str]] = {}
        for p in doc["paragraphs"]:
            out.setdefault(p["section"], Counter())[p["digest"]] += 1
        return out

    b, a = by_section(before), by_section(after)
    return {s for s in a if b.get(s) != a[s]}


def clusters(doc: dict[str, Any], sections: Optional[set[str]], threshold: int = CLUSTER) -> list[dict[str, Any]]:
    """A pattern used `threshold` or more times under one heading: once can stand, a run of them is a habit."""
    found: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for p in doc["paragraphs"]:
        if sections is not None and p["section"] not in sections:
            continue
        for sid, hits in p["hits"].items():
            uses = hits[:1] if sid == "C16" else hits
            found.setdefault((p["section"], sid), []).extend({"text": h, "line": p["line"]} for h in uses)
    return [{"id": sid, "section": section, "count": len(uses), "uses": uses}
            for (section, sid), uses in found.items() if len(uses) >= threshold]


def run_check(after: dict[str, Any], before: Optional[dict[str, Any]], keep: set[str],
              threshold: int = CLUSTER) -> dict[str, Any]:
    """The verdict `--check` gates on: what the edit added, and clusters under the headings it touched."""
    sections = changed_sections(before, after) if before is not None else None
    added = added_hits(before, after) if before is not None else []
    found = clusters(after, sections, threshold)
    return {"added": added, "clusters": found, "kept": sorted(keep), "threshold": threshold,
            "sections_checked": None if sections is None else sorted(sections),
            "passed": all(x["id"] in keep for x in added + found)}


def catalogue_entries(path: Path = CATALOGUE_MD) -> list[dict[str, str]]:
    """Every lettered entry of the catalogue: its group, ID, name and what to watch for, in one line each.

    The "Watch for" paragraph when the entry has one, else its first paragraph, so the reading list always
    says what the entry is about and is regenerated from the catalogue rather than kept by hand."""
    text = path.read_text(encoding="utf-8")
    out: list[dict[str, str]] = []
    group = ""
    for block in re.split(r"^(?=#{2,3} )", text, flags=re.MULTILINE):
        head = block.splitlines()[0] if block.strip() else ""
        g = re.match(r"^## ([A-K])\. (.+)$", head)
        if g:
            group = f"{g.group(1)}. {g.group(2).strip()}"
            continue
        if head.startswith("## "):
            group = ""
            continue
        e = re.match(r"^### ([A-K]\d+)\. (.+)$", head)
        if not e or not group:
            continue
        body = block[len(head):]
        watch = re.search(r"\*\*Watch for:\*\*\s*(.+?)(?:\n\s*\n|\n\*\*)", body, re.DOTALL)
        paras = [x for x in re.split(r"\n\s*\n", body) if x.strip()]
        line = " ".join((watch.group(1) if watch else (paras[0] if paras else "")).split())
        out.append({"group": group, "id": e.group(1), "name": e.group(2).strip(),
                    "watch": line if len(line) <= 400 else line[:399].rsplit(" ", 1)[0] + "…"})
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


def _quoted(uses: list[dict[str, Any]], limit: int = 4) -> str:
    """The distinct matched words, each once, with how often a repeated one occurs."""
    counts = Counter(u["text"] for u in uses)
    shown = [f"“{t}”" + (f" ({_times(n)})" if n > 1 else "") for t, n in counts.most_common()]
    rest = len(shown) - limit
    return _listed(shown[:limit] + ([_count(rest, "other", "others")] if rest > 0 else []))


def check_markdown(result: dict[str, Any], smells: dict[str, dict[str, Any]], compared: bool,
                   report: bool = False) -> str:
    """The verdict in sentences: what to fix before the text or the report is handed over.

    A pattern kept in a manuscript is named to the authors; in a report, the report is what they read."""
    keep = set(result["kept"])
    scope = "under the headings the edit changed" if compared else "under any heading"
    tell = "" if report else ", and tell the authors which sentence and why"
    out = ["", "## Before handing the text over", ""]
    if not result["added"] and not result["clusters"]:
        added = "The edit added no pattern the original did not have, and no" if compared else "No"
        out.append(f"{added} pattern is used {result['threshold']} or more times {scope}. Still read the text "
                   "against the list below: the counts find only some of the patterns.")
    for h in result["added"]:
        name = _pattern(h["id"], smells)
        what = (f"kept after review{tell}" if h["id"] in keep else
                f"rewrite it, or keep it only if its entry says to leave it{tell}")
        out.append(f"- The edit added {name} ({h['id']}): “{h['text']}”, in "
                   f"{place(h['section'], 'line ' + str(h['line']))}. It was not in the original; {what}.")
    for c in result["clusters"]:
        name = _pattern(c["id"], smells)
        lines = sorted({u["line"] for u in c["uses"]})
        span = f"line {lines[0]}" if len(lines) == 1 else f"lines {lines[0]} to {lines[-1]}"
        what = (f"Kept after review{tell}." if c["id"] in keep else
                "One use can stand where the reader needs it; a run of them is the habit a reader notices. "
                "Rewrite the ones that do not carry the argument, then check again.")
        out.append(f"- {name[:1].upper()}{name[1:]} ({c['id']}) is used {c['count']} times in "
                   f"{place(c['section'], span)}: {_quoted(c['uses'])}. {what}")
    if result["added"] or result["clusters"]:
        out += ["", "Passed." if result["passed"] else
                "Not passed: the text is not ready to hand over until each item above is rewritten or kept on "
                f"purpose{'' if report else ' and named to the authors'}."]
    return "\n".join(out) + "\n"


def reading_list(entries: list[dict[str, str]], smells: dict[str, dict[str, Any]], report: bool) -> str:
    """Every catalogue entry in one line, to read the text against: the patterns no count can find."""
    out = ["", "## Read the text against every pattern", "",
           "The counts above find only the patterns marked “counted”, and only in the wordings they know. Read "
           "the edited text against each line below, find the rest by reading, and fix what you find. Before "
           "changing a sentence, read that entry's “Leave it when” in the editor's catalogue; a sentence that "
           "still says something specific can stay."]
    if report:
        out += ["", "This is a report to the authors: addressing them as “you” and asking them questions is expected, "
                    "and the manuscript's words inside quotation marks are not the report's."]
    group = ""
    for e in entries:
        if e["group"] != group:
            group = e["group"]
            out += ["", f"### {group}", ""]
        counted = ", counted" if e["id"] in smells else ""
        out.append(f"- {e['name']} ({e['id']}{counted}): {e['watch']}")
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
    before: Annotated[Optional[Path], typer.Option(exists=True, dir_okay=False, readable=True,
                                                   help="The text before the edit: report the patterns the edit "
                                                        "added, and judge clusters only under the headings it "
                                                        "changed")] = None,
    check: Annotated[bool, typer.Option("--check", help="Exit 1 while the edit added a pattern or one pattern is "
                                                        "used --cluster times under a heading; print every "
                                                        "catalogue entry to read the text against")] = False,
    keep: Annotated[Optional[list[str]], typer.Option(help="A pattern ID reviewed and kept on purpose "
                                                           "(repeatable); name the sentences to the authors")] = None,
    cluster: Annotated[int, typer.Option(min=2, help="Uses of one pattern under one heading that make a "
                                                     "cluster")] = CLUSTER,
    report: Annotated[bool, typer.Option("--report", help="Check a report to the authors: skip quoted text, "
                                                          "and expect 'you' and questions")] = False,
) -> None:
    smells, kobak = load_smells(), load_kobak()
    latex = path.suffix == ".tex"
    doc = profile_text(path.read_text(encoding="utf-8"), latex, smells, kobak, report)
    if report:
        smells = {sid: s for sid, s in smells.items() if sid not in REPORT_SKIPPED}
    result = None
    if check or before:
        original = profile_text(before.read_text(encoding="utf-8"), latex, smells, kobak, report) if before else None
        result = run_check(doc, original, {k.strip().upper() for k in keep or []}, cluster)
        doc["check"] = result
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
    if result is not None:
        md += check_markdown(result, smells, before is not None, report)
    if check:
        md += reading_list(catalogue_entries(), smells, report)
    if md_out:
        md_out.write_text(md, encoding="utf-8")
        typer.echo(f"Wrote the report to {md_out}.")
    else:
        typer.echo(md)
    if check and result is not None and not result["passed"]:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
