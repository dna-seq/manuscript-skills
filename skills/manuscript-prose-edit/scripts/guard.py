# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12"]
# ///
"""Flag content changes after a manuscript edit, or list them between two versions of a manuscript.

A copy-editing pass may change wording, never content. The guard compares the text before and after in two ways:

- whole-text counts of selected number, citation, identifier, term, URL and code-span patterns, plus selected
  hedges, negations and causal verbs (the `protected` and `watched` fields);
- sentence by sentence (`sentence_changes`): it aligns the sentences of BEFORE and AFTER, allowing for split,
  merged and moved sentences, and reports for each aligned pair a claim that moved on the causal or evidential
  ladder, novelty or generality wording that appeared or went, a scope qualifier ("in this cohort", "in mice"),
  limiting or concessive word ("only", "albeit", "despite"), null-result marker ("did not differ") or
  evidence-status word ("self-reported", "predicted") that disappeared or appeared, a changed negation, and every
  number, citation or identifier that one sentence has and its counterpart lacks, with section and line. The
  ladders are in references/claim-ladders.md.

It cannot prove semantic equivalence: swapped values and changed relationships can pass every check. Read the
diff in context.

    uv run --script guard.py BEFORE.md AFTER.md
    uv run --script guard.py PAPER.md --against HEAD                      # compare with the committed version
    uv run --script guard.py BEFORE.md AFTER.md --json report.json --md report.md
    uv run --script guard.py BEFORE.md AFTER.md --allow-strengthening     # an authorised claim correction
    uv run --script guard.py ORIGINAL.tex REVISED.tex --revision --json inventory.json

Edit mode (default). Exit code 1 when a protected item changed: a count of numbers, citations, identifiers,
terms, URLs or code; a claim that rose on a ladder or gained novelty or generality wording; a scope,
null-result or evidence-status marker that disappeared, or a limiting or concessive word that left a surviving
sentence; or a number, citation or identifier that is new to its sentence and its paragraph, or left them.
`--allow-strengthening` exempts the claim changes (never the counts or the tokens) when the authors authorised a
claim correction. Lowered claims, added qualifiers, negation changes and tokens moved within a paragraph are
warnings: read each one.

Revision mode (`--revision`): for an original and a revised manuscript where content changes are expected.
Lists every change of the kinds above with section and line, in the same fields, and always exits 0.

Exit codes: 0 no protected change (always with --revision), 1 a protected change, 2 usage error.
"""

from __future__ import annotations

import bisect
import json
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Annotated, Callable, Optional

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
LATEX_COMMENT = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
# A `%` starts a comment only in LaTeX; in Markdown it is a percent sign and must not hide the rest of the line.
LATEX_SIGNS = re.compile(r"\\(?:documentclass|usepackage|begin\{|(?:sub)*section\*?\{|[a-zA-Z]*cite[a-z]*\*?[\[{]|"
                         r"emph\{|textbf\{|textit\{|label\{|ref\{)")

# Protected patterns: a count change warrants review; it does not by itself prove semantic drift.
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


def _is_latex(text: str) -> bool:
    return bool(LATEX_SIGNS.search(text))


def _prose(text: str, latex: bool | None = None) -> str:
    """The text a reader sees: drop HTML comments (revision markers, notes) and, in LaTeX, `%` comments."""
    text = HTML_COMMENT.sub("", text)
    return LATEX_COMMENT.sub("", text) if (_is_latex(text) if latex is None else latex) else text


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


def change_rate(before: str, after: str) -> float:
    """Share of the original's words that did not survive in place (a word-level diff)."""
    a, b = before.split(), after.split()
    if not a:
        return 0.0
    kept = sum(block.size for block in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return round(1 - kept / len(a), 3)


CHANGE_WARN, CHANGE_STOP = 0.25, 0.50


# ---------------------------------------------------------------------------------------------------------------
# Sentences: segmentation with section and line, so every finding has a location
# ---------------------------------------------------------------------------------------------------------------

FRONT_MATTER = re.compile(r"\A---[ \t]*\n.*?\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)", re.DOTALL)
FENCED_CODE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[^\n]*\n.*?^[ \t]{0,3}\1[ \t]*$", re.DOTALL | re.MULTILINE)
DISPLAY_MATH = re.compile(r"\$\$.*?\$\$|\\\[.*?\\\]|\\begin\{(equation|align|gather|multline|eqnarray|displaymath)"
                          r"(\*?)\}.*?\\end\{\1\2\}", re.DOTALL)
MD_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t#]*$")
TEX_HEADING = re.compile(r"^\s*\\(part|chapter|section|subsection|subsubsection)\*?(?:\[[^\]]*\])?\{(.*)\}\s*$")
TEX_LEVEL = {"part": 0, "chapter": 1, "section": 2, "subsection": 3, "subsubsection": 4}
# Structural LaTeX lines that hold no prose (a caption or footnote does, so it is not listed).
TEX_STRUCTURE = re.compile(
    r"^\s*\\(?:begin|end|label|includegraphics|maketitle|centering|bibliography|bibliographystyle|usepackage|"
    r"documentclass|newcommand|renewcommand|input|include|title|author|date|affil\w*|keywords|tableofcontents|"
    r"clearpage|newpage|vspace|hspace|hline|toprule|midrule|bottomrule|noindent|appendix|small|footnotesize)\b"
    r"\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})*\s*$")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$|^[^\n]*&[^\n]*\\\\\s*$")
LIST_ITEM = re.compile(r"^(\s*(?:[-*+]|\d{1,3}[.)]|\\item(?:\[[^\]]*\])?)\s+)")
BOUNDARY = re.compile(r"[.!?][\"'”’)\]]*(?:\[[\d,\s–-]+\])?(?=[\s\x00]*\s[\s\x00]*[\"'“‘(\[*_\\$~]*[A-Z0-9])")
ABBREVIATIONS = {
    "al", "e.g", "i.e", "fig", "figs", "eq", "eqs", "ref", "refs", "tab", "no", "nos", "vs", "cf", "approx", "ca",
    "dr", "prof", "mr", "ms", "mrs", "st", "suppl", "sect", "sec", "ch", "vol", "pp", "resp", "incl", "est", "inc",
    "ltd", "co", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "sp", "spp",
    "var", "ed", "eds", "viz", "chr",
}
WORD = re.compile(r"[^\W\d_][\w'’-]*|\d+(?:[.,]\d+)*")
STOPWORDS = frozenset(
    "the a an of in on for to and or with by at from as is are was were be been being this that these those it its "
    "we our us which who whom whose than then there their they them has have had into onto over under also such "
    "both each other more most less very can will would should".split())


@dataclass
class Sentence:
    text: str          # the sentence as a reader sees it (comments removed), whitespace collapsed
    line: int          # 1-based line of its first character in the file
    block: int         # paragraph index (blank lines and headings separate paragraphs)
    section: str       # heading path, e.g. "Results > Performance"
    words: frozenset[str]


HIDDEN = "\x00"  # an inline comment: removed from the sentence text, but keeps every offset


def _spaces(m: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", m.group(0))


def _hidden(m: re.Match[str]) -> str:
    return re.sub(r"[^\n]", HIDDEN, m.group(0))


def _mask(text: str, latex: bool) -> str:
    """Blank out what is not prose while keeping every offset, so lines stay correct."""
    out = FRONT_MATTER.sub(_spaces, text)
    out = HTML_COMMENT.sub(_hidden, out)
    if latex:
        out = LATEX_COMMENT.sub(_hidden, out)
    out = FENCED_CODE.sub(_spaces, out)
    return DISPLAY_MATH.sub(_spaces, out)


def _clean_title(title: str) -> str:
    return " ".join(re.sub(r"\\[A-Za-z]+\*?|[{}*_`]", "", title).split())


def _content_words(text: str) -> frozenset[str]:
    return frozenset(w for w in (t.lower() for t in WORD.findall(text)) if w not in STOPWORDS and len(w) > 1)


def _is_abbreviation(chunk: str, dot: int) -> bool:
    prev = re.search(r"([A-Za-z][A-Za-z.]*)$", chunk[:dot])
    if not prev:
        return False
    word = prev.group(1)
    return (word.lower().rstrip(".") in ABBREVIATIONS or bool(re.fullmatch(r"(?:[A-Za-z]\.)+[A-Za-z]?", word))
            or bool(re.fullmatch(r"[A-Z]", word)))


def segment(text: str) -> list[Sentence]:
    """Split a Markdown or LaTeX manuscript into sentences with line, paragraph and section."""
    latex = _is_latex(text)
    masked = _mask(text, latex)
    line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
    out: list[Sentence] = []
    headings: list[tuple[int, str]] = []
    block = 0
    chunk: list[int] = []  # [start, end) of the running prose chunk

    def section() -> str:
        return " > ".join(t for _, t in headings)

    def emit(start: int, end: int, split: bool) -> None:
        piece = masked[start:end]
        cuts = [0]
        if split:
            cuts += [m.end() for m in BOUNDARY.finditer(piece) if not _is_abbreviation(piece, m.start())]
        cuts.append(len(piece))
        for a, b in zip(cuts, cuts[1:]):
            raw = piece[a:b].replace(HIDDEN, "")
            body = " ".join(raw.split())
            if not re.search(r"[A-Za-z]", body):
                continue
            offset = start + a + (len(piece[a:b]) - len(piece[a:b].lstrip(" \t\n\r" + HIDDEN)))
            out.append(Sentence(body, bisect.bisect_right(line_starts, offset), block, section(), _content_words(body)))

    def flush() -> None:
        if chunk:
            emit(chunk[0], chunk[1], True)
            chunk.clear()

    pos = 0
    previous_blank = True
    for raw_line in masked.split("\n"):
        start, end = pos, pos + len(raw_line)
        pos = end + 1
        line = raw_line.rstrip("\r")
        if not line.replace(HIDDEN, "").strip():
            flush()
            if not previous_blank:
                block += 1
            previous_blank = True
            continue
        previous_blank = False
        md, tex = MD_HEADING.match(line), TEX_HEADING.match(line)
        if md or tex:
            flush()
            level = len(md.group(1)) if md else TEX_LEVEL[tex.group(1)]
            title = _clean_title(md.group(2) if md else tex.group(2))
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, title))
            block += 1
            continue
        if latex and TEX_STRUCTURE.match(line):
            flush()
            continue
        if TABLE_ROW.match(line):
            flush()
            if not re.fullmatch(r"[\s|:\-+]+", line):
                emit(start, end, False)
            continue
        item = LIST_ITEM.match(line)
        if item:
            flush()
            chunk.extend([start + len(item.group(1)), end])
            continue
        if chunk:
            chunk[1] = end
        else:
            chunk.extend([start, end])
    flush()
    return out


# ---------------------------------------------------------------------------------------------------------------
# Alignment: identical sentences anchor; changed runs are aligned 1:1, split (1:2, 1:3) or merged (2:1, 3:1)
# ---------------------------------------------------------------------------------------------------------------

MIN_SIMILARITY, MOVE_SIMILARITY = 0.3, 0.5


@dataclass
class Group:
    before: list[int]
    after: list[int]
    kind: str  # equal | changed | split | merged | moved | deleted | inserted


def _dice(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0


def _align_run(bs: list[Sentence], as_: list[Sentence], i0: int, j0: int, n: int, m: int) -> list[Group]:
    """Best monotone alignment of a run of changed sentences (dynamic programming over group shapes)."""
    shapes = ((1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (3, 1), (1, 3))
    band = (15 + abs(n - m)) if n * m > 2500 else None
    neg = float("-inf")
    best = [[neg] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    union_b: dict[tuple[int, int], frozenset[str]] = {}
    union_a: dict[tuple[int, int], frozenset[str]] = {}

    def words(cache: dict[tuple[int, int], frozenset[str]], seq: list[Sentence], base: int, a: int, b: int):
        if (a, b) not in cache:
            cache[(a, b)] = frozenset().union(*(seq[base + k].words for k in range(a, b)))
        return cache[(a, b)]

    for i in range(n + 1):
        for j in range(m + 1):
            current = best[i][j]
            if current == neg:
                continue
            for di, dj in shapes:
                ni, nj = i + di, j + dj
                if ni > n or nj > m or (band is not None and abs(ni * m / max(n, 1) - nj) > band):
                    continue
                score = 0.0
                if di and dj:
                    wb, wa = words(union_b, bs, i0, i, ni), words(union_a, as_, j0, j, nj)
                    sim = _dice(wb, wa)
                    if sim < MIN_SIMILARITY:
                        continue
                    score = sim * (len(wb) + len(wa) + 1)
                if current + score > best[ni][nj]:
                    best[ni][nj] = current + score
                    back[ni][nj] = (i, j)
    groups: list[Group] = []
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj = back[i][j]  # type: ignore[misc]
        before, after = list(range(i0 + pi, i0 + i)), list(range(j0 + pj, j0 + j))
        kind = ("deleted" if not after else "inserted" if not before else "changed" if len(before) == len(after)
                else "split" if len(after) > len(before) else "merged")
        groups.append(Group(before, after, kind))
        i, j = pi, pj
    return groups[::-1]


def align(bs: list[Sentence], as_: list[Sentence]) -> list[Group]:
    groups: list[Group] = []
    keys_b, keys_a = [s.text for s in bs], [s.text for s in as_]
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, keys_b, keys_a, autojunk=False).get_opcodes():
        if tag == "equal":
            groups += [Group([i1 + k], [j1 + k], "equal") for k in range(i2 - i1)]
        else:
            groups += _align_run(bs, as_, i1, j1, i2 - i1, j2 - j1)
    # A sentence moved out of its run: pair leftover deletions and insertions by similarity, best first.
    deleted = [g for g in groups if g.kind == "deleted"]
    inserted = [g for g in groups if g.kind == "inserted"]
    pairs = sorted(((_dice(bs[d.before[0]].words, as_[a.after[0]].words), di, ai)
                    for di, d in enumerate(deleted) for ai, a in enumerate(inserted)), reverse=True)
    used_d: set[int] = set()
    used_a: set[int] = set()
    for sim, di, ai in pairs:
        if sim < MOVE_SIMILARITY:
            break
        if di in used_d or ai in used_a:
            continue
        used_d.add(di)
        used_a.add(ai)
        inserted[ai].before, inserted[ai].kind = deleted[di].before, "moved"
        deleted[di].kind = "absorbed"
    return [g for g in groups if g.kind != "absorbed"]


# ---------------------------------------------------------------------------------------------------------------
# Claim markers (references/claim-ladders.md explains each list)
# ---------------------------------------------------------------------------------------------------------------

Filter = Callable[[str, int, int], bool]

FIGURE_WORDS = re.compile(r"\b(?:fig(?:ure)?s?|tables?|panels?|insets?|diagrams?|schematics?|supplementary|"
                          r"appendix|box|screenshots?|below|above|example)\b", re.IGNORECASE)
PROCEDURAL_OBJECT = re.compile(
    r"^\s+(?:(?:a|an|the|our|new|its|their)\s+)?(?:[\w-]+\s+){0,2}?(?:baselines?|protocols?|pipelines?|frameworks?|"
    r"cohorts?|databases?|resources?|collaborations?|workflows?|colon(?:y|ies)|lines?|cultures?|criteria|standards?|"
    r"benchmarks?|registr(?:y|ies)|consortium|repositor(?:y|ies)|partnerships?|receipt|identity|configuration|"
    r"setup|installation|methods?|tools?|practices?|guidelines?|techniques?|software)\b", re.IGNORECASE)


def _not_descriptive(text: str, start: int, end: int) -> bool:
    """'Figure 2 shows the layout' describes a figure; 'Figure 2 shows that X' still makes a claim."""
    following = text[end:end + 30]
    if re.match(r"\s+that\b", following, re.IGNORECASE):
        return True
    if re.match(r"\s+(?:as|together|below|above|alongside|side by side|on (?:the|a) (?:left|right|map|screen|page))\b",
                following, re.IGNORECASE):
        return False
    return not FIGURE_WORDS.search(text[max(0, start - 30):end + 30])


def _not_procedural(text: str, start: int, end: int) -> bool:
    """'established a pipeline', 'confirmed the configuration', 'well-established methods' are not proof."""
    if re.search(r"well[- ]$", text[max(0, start - 5):start], re.IGNORECASE):
        return False
    return not PROCEDURAL_OBJECT.match(text[end:end + 60])


def _not_clearly_modifier(text: str, start: int, end: int) -> bool:
    return not re.match(r"\s+(?:defined|separated|visible|label+ed|distinct|stated|marked|shown in)\b", text[end:],
                        re.IGNORECASE)


@dataclass(frozen=True)
class Rung:
    level: int
    name: str
    rx: re.Pattern[str]
    keep: Optional[Filter] = None


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# Causal force. A sentence with no marker states a plain relation and sits at rung 4 ("affects").
CAUSAL: tuple[Rung, ...] = (
    Rung(0, "compatibility", _rx(r"\b(?:consistent|compatible|in line|in keeping) with\b")),
    Rung(1, "association", _rx(
        r"\bassociat(?:es|ed|ion|ions) (?:with|between)\b|\bassociations? of\b|\bcorrelat(?:es|ed|ion|ions) "
        r"(?:with|between)\b|\b(?:is|are|was|were) (?:\w+ )?(?:linked|related) (?:to|with)\b|"
        r"\blinked (?:[\w-]+ ){1,4}?(?:to|with)\b|\blinks? between\b|\bco-?occur(?:s|red|ring)? with\b|"
        r"\benriched (?:in|for|among)\b")),
    Rung(2, "prediction", _rx(r"\bpredict(?:s|ed|ing)?\b|\bpredictive (?:of|for)\b|\bpredictors? of\b|"
                              r"\bprognostic (?:for|of)\b|\bforecasts?\b")),
    Rung(3, "contribution", _rx(
        r"\bcontribut(?:es|ed|ing|e|ion|ions) (?:\w+ ){0,3}?to\b|\bplay(?:s|ed|ing)? an? (?:[\w-]+ ){0,2}?role in\b|"
        r"\b(?:is|are|was|were|be|been) involved in\b|\bparticipat(?:es|ed|e) in\b|\bmodulat(?:es|ed|e)\b|"
        r"\binfluenc(?:es|ed|e)\b")),
    Rung(4, "effect", _rx(
        r"\baffect(?:s|ed|ing)?\b(?! (?:individuals|patients|carriers|relatives|members|samples|subjects|tissues?|"
        r"cases|families|siblings|people|participants|genes?)\b)|\b(?:leads?|leading|led) to\b|"
        r"\bresult(?:s|ed|ing)? in\b|\b(?:gives?|gave|giving) rise to\b|\binduc(?:es|ed|e|ing)\b|"
        r"\bpromot(?:es|ed|e|ing)\b|\binhibit(?:s|ed|ing)?\b|\bprevent(?:s|ed|ing)?\b|\bprotect(?:s|ed|ing)? against\b|"
        r"\b(?:increas|decreas|reduc|lower|rais|elevat)(?:es|ed|e|ing|s)? the (?:risk|odds|likelihood|incidence|"
        r"probability) of\b")),
    Rung(5, "causation", _rx(
        r"\bcaus(?:es|ed|ing|e|al|ally|ative|ation)\b|\bdriv(?:es|en|ing|e)\b|\bdrove\b|\bdrivers? of\b|"
        r"\bdetermined by\b|\bdetermines\b|\b(?:is|are|was|were) (?:\w+ )?responsible for\b|\bunderl(?:ies|ie|ay)\b|"
        r"\bmediat(?:es|ed|e|ing)\b")),
)
CAUSAL_PLAIN = 4

# Evidential force. A sentence with no marker is a plain assertion and sits at rung 3 ("shows").
EVIDENTIAL: tuple[Rung, ...] = (
    Rung(0, "possibility", _rx(
        r"\b(?:may)\b(?!\s+\d)|\b(?:might|could|possibly|potentially|perhaps|conceivably|plausibly|likely|unlikely|"
        r"probably)\b|\b(?:appears?|appeared|seems?|seemed) to\b|\bit is possible that\b|"
        r"\bwe (?:speculate|hypothesi[sz]e)\b")),
    Rung(1, "suggestion", _rx(r"\bsuggest(?:s|ed|ing|ive of)?\b|\bhint(?:s|ed)? (?:at|that)\b|"
                              r"\bpoint(?:s|ed)? (?:to|towards)\b")),
    Rung(2, "indication", _rx(
        r"(?<!as )\bindicat(?:es|ed|e|ing)\b|\bsupport(?:s|ed|ing)? (?:the|our|this|a|an|these) (?:[\w-]+ ){0,2}?"
        r"(?:hypothes[ie]s|conclusions?|notion|idea|view|interpretation|claim|model|role|link)\b|"
        r"\b(?:provides?|provided|is|are|was|were|offers?) (?:\w+ )?evidence (?:for|that|of)\b")),
    Rung(3, "demonstration", _rx(r"\bshow(?:s|ed|n|ing)?\b|\bdemonstrat(?:es|ed|e|ing)\b|\breveal(?:s|ed|ing)?\b|"
                                 r"\b(?:find|finds|found) that\b"), _not_descriptive),
    Rung(4, "proof", _rx(r"\bprov(?:es|ed|en|e|ing)\b|\bproof (?:of|that)\b|\bestablish(?:es|ed|ing)?\b|"
                         r"\bconfirm(?:s|ed|ing)?\b|\bguarantee(?:s|d)?\b"), _not_procedural),
    Rung(4, "proof", _rx(r"\bconclusive(?:ly)?\b|\bdefinitive(?:ly)?\b|\bunequivocal(?:ly)?\b|\bunambiguous(?:ly)?\b|"
                         r"\bbeyond (?:any |reasonable )?doubt\b|\birrefutabl[ey]\b|\bundoubtedly\b|\bcertainly\b|"
                         r"\bunquestionabl[ey]\b|\bclearly\b"), _not_clearly_modifier),
)
EVIDENTIAL_PLAIN = 3

GENERALITY: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("novelty", _rx(
        r"\bfor the first time\b|\b(?:the|a) first (?:[\w-]+ ){0,2}?(?:study|studies|report|tool|method|approach|"
        r"framework|demonstration|analysis|evidence|description|map|atlas|resource|implementation|account|alternative|"
        r"platform|pipeline|system|model|software|assay|test|solution|database|benchmark|application)\b|\bfirst-ever\b|"
        r"\bnovel\b|\bunprecedented\b|\bpioneering\b|\bgroundbreaking\b|\bstate-of-the-art\b")),
    ("generality", _rx(
        r"\balways\b|\binvariably\b|\buniversal(?:ly)?\b|\bin (?:all|every) (?:[\w-]+ ){0,1}?(?:cases?|settings?|"
        r"populations?|patients|individuals|samples|species|tissues|conditions|contexts?|cohorts?)\b|"
        r"\bacross all\b|\bregardless of\b|\birrespective of\b|\bgenerali[sz]able\b|"
        r"\bbroadly applicable\b|\bin any (?:[\w-]+ )?(?:setting|population|"
        r"species|tissue|genome|context)\b")),
)

ANCESTRY = (r"european|east asian|south asian|african(?:[- ]american)?|hispanic|latin[oax]|latinx|asian|japanese|"
            r"chinese|han chinese|korean|finnish|british|white|black|caucasian|admixed|indigenous|native american|"
            r"ashkenazi(?: jewish)?")
MODEL_CANON = {"mice": "mouse", "murine": "mouse", "rats": "rat", "rodents": "rodent", "flies": "fly",
               "fruit flies": "fly", "drosophila": "fly", "worms": "worm", "nematodes": "worm", "c. elegans": "worm",
               "cell lines": "cells", "cell line": "cells", "cultured cells": "cells", "cell cultures": "cells",
               "cell culture": "cells", "animals": "animal", "animal models": "animal", "animal model": "animal",
               "organoids": "organoid", "xenografts": "xenograft", "macaques": "primate", "monkeys": "primate",
               "primates": "primate", "pigs": "pig", "dogs": "dog", "plants": "plant", "e. coli": "bacteria"}

# Scope rules in priority order: an earlier rule claims its span, so one phrase is counted once.
SCOPE: tuple[tuple[re.Pattern[str], Callable[[re.Match[str]], str]], ...] = (
    (_rx(r"\b(?:in|within) (?:this|the present|the current|our) (?:study|paper|work|article|manuscript|report)\b"),
     lambda m: "this-study"),
    (_rx(r"\b(?:in|within|across|among|from|on|for) (?:this|these|our|the present|the current|the studied|the tested|"
         r"the analy[sz]ed|the evaluated|the investigated|the sampled|the included) (?:[\w-]+ ){0,2}?(?:cohorts?|"
         r"samples?|datasets?|data|populations?|settings?|trials?|benchmarks?|participants|patients|individuals|"
         r"subjects|genomes|exomes|families|animals|cells|experiments?|analys[ie]s|systems?)\b|\bin our hands\b"),
     lambda m: "this-data"),
    (_rx(r"\bunder (?:these|the (?:tested|studied|experimental|present|current|same|given)|our|such|standard|"
         r"laboratory|controlled|experimental) conditions\b|\b(?:at|for|within|over) the (?:tested|studied|examined|"
         r"evaluated|investigated) (?:[\w-]+ ){0,2}?(?:ranges?|doses?|concentrations?|temperatures?|conditions|values|"
         r"parameters|settings)\b"),
     lambda m: "conditions"),
    (re.compile(rf"\b({ANCESTRY})[- ](?:ancestry|ancestries|descent|origin|populations?|individuals|participants|"
                rf"samples|cohorts?)\b|\bof ({ANCESTRY}) (?:ancestry|descent|origin)\b", re.IGNORECASE),
     lambda m: "ancestry:" + (m.group(1) or m.group(2)).lower()),
    (_rx(r"\bin (?:some|several|certain|selected|a few|most|many|a (?:subset|subgroup|minority|fraction|proportion) of)"
         r" (?:[\w-]+ ){0,2}?(?:cohorts?|patients|participants|individuals|samples|cases|studies|tissues|cell types|"
         r"conditions|settings|populations|genomes|datasets|species|strains|families|subjects)\b|"
         r"\bin (?:a |one )?subgroups?\b"),
     lambda m: "subset"),
    (_rx(r"\b(?:in vitro|in vivo|in silico|ex vivo|in situ|in utero)\b"), lambda m: " ".join(m.group(0).lower().split())),
    (_rx(r"\bin (?:a |an |the )?(?:[\w-]+ ){0,2}?(mice|mouse|murine|rats?|rodents?|zebrafish|fruit flies|flies|"
         r"drosophila|yeast|worms|nematodes|c\. elegans|primates|macaques|monkeys|pigs|dogs|animal models?|animals|"
         r"xenografts?|organoids|cell lines?|cultured cells|cell cultures?|cells|plants|arabidopsis|bacteria|"
         r"e\. coli)\b"),
     lambda m: "model:" + MODEL_CANON.get(m.group(1).lower(), m.group(1).lower())),
    (_rx(r"\bin (?:[\w-]+ ){0,2}?(humans|people|persons|patients|adults|children|adolescents|infants|neonates|men|"
         r"women|males|females|older adults|elderly|volunteers|twins|carriers|non-carriers)\b"),
     lambda m: "people:" + m.group(1).lower()),
    (_rx(r"\b(?:in|on|from|with|using) (?:the )?(simulated|synthetic|real|public|benchmark|training|validation|test|"
         r"held-out|independent|external|discovery|replication) (?:data|datasets?|sets?|cohorts?|samples|genomes|"
         r"reads|splits?)\b|\bin simulations?\b|\b(internally|externally) validated\b"),
     lambda m: "data:" + (m.group(1) or m.group(2) or "simulation").lower()),
)

NULL_RESULT = _rx(
    r"\bno (?:statistically )?significant\b|\bnot (?:statistically )?significant(?:ly)?\b|\bnon-?significant(?:ly)?\b|"
    r"\binsignificant(?:ly)?\b|\b(?:did|does|do) not (?:\w+ )?(?:differ|change|improve|reduce|increase|decrease|affect|"
    r"alter|predict|replicate|reach|associate|correlate|vary|survive|show|detect|find|support)\b|"
    r"\b(?:was|were|is|are|been) not (?:\w+ )?(?:associated|correlated|different|changed|altered|enriched|affected|"
    r"predictive|related|detected|replicated|observed|improved|reduced|increased)\b|"
    r"\bno (?:[\w-]+ ){0,2}?(?:association|associations|difference|differences|effect|effects|correlation|enrichment|"
    r"evidence|improvement|change|signal|relationship|benefit|link|increase|decrease|reduction)\b|"
    r"\bfail(?:s|ed)? to (?:\w+ )?(?:replicate|reach|detect|show|improve|reduce|predict|find|support|differ)\b|"
    r"\b(?:remained|was|were|is|are) unchanged\b|\bnull (?:results?|findings?|associations?|effects?)\b|"
    r"\bn\.s\.|\b[pP]\s*[>≥]\s*0?\.0[15]\b|\bno longer significant\b|\blost significance\b|\bnot replicated\b")

EVIDENCE_STATUS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("self-reported", _rx(r"\b(?:self|patient|participant|parent|caregiver|proxy|user)[- ]?report(?:ed|s)?\b")),
    ("reported", _rx(r"\breport(?:ed|edly)\b")),
    ("perceived", _rx(r"\bperceived\b|\bsubjective(?:ly)?\b")),
    ("predicted", _rx(r"\b(?:in silico |computationally )?predicted\b")),
    ("putative", _rx(r"\bputative(?:ly)?\b|\bpresum(?:ed|ptive)\b|\bsuspected\b|\bcandidate\b")),
    ("estimated", _rx(r"\bestimated\b|\bestimates?\b|\bimputed\b|\binferred\b|\bmodell?ed\b|\bsimulated\b|"
                      r"\bprojected\b|\bextrapolated\b|\bapproximated\b")),
    ("observed", _rx(r"\bobserved\b|\bmeasured\b|\bdetected\b|\brecorded\b|\bvalidated\b")),
)

# Limiting and concessive words ("tested on only four genomes", "Albeit tested on four genomes, ..."): losing one
# presents the evidence as broader than the authors wrote. A contrastive connector can carry the concession after a
# restructure ("Although X, Y" → "X. However, Y"), so it offsets a lost word; its own loss is a glue cut.
LIMITING = _rx(r"\bonly\b|\bmere(?:ly)?\b|\bsolely\b|\bas few as\b|\b(?:limited|restricted) to\b|"
               r"\bjust (?=(?:\d|one|two|three|four|five|six|seven|eight|nine|ten|a few|a handful|a single)\b)")
CONCESSIVE = _rx(r"\balbeit\b|\b(?:even )?(?:al)?though\b|\beven if\b|\bdespite\b|\bin spite of\b|"
                 r"\bnotwithstanding\b|\bwhil(?:e|st)\b")
CONTRASTIVE = _rx(r"\bhowever\b|\bbut\b|\byet\b|\bnevertheless\b|\bnonetheless\b|\bwhereas\b")
NOT_LIMITING = _rx(r"\b(?:not|the|an|its|their|our|if)\s+$")  # not only, the only tool, if only, not limited to


def _limitation_marks(text: str) -> tuple[list[str], int]:
    """Limiting and concessive words in a sentence, and the number of contrastive connectors that can stand in."""
    strong: list[str] = []
    offsets = len(CONTRASTIVE.findall(text))
    for rx in (LIMITING, CONCESSIVE):
        for m in rx.finditer(text):
            word = " ".join(m.group(0).lower().split())
            prefix = text[max(0, m.start() - 8):m.start()]
            if rx is LIMITING and NOT_LIMITING.search(prefix) or word == "though" and re.search(r"\bas\s+$", prefix):
                continue
            preceding = text[:m.start()].rstrip()
            if word.startswith("whil") and preceding and preceding[-1] not in ".;:(\"“*_":
                offsets += 1  # "X rose, while Y fell" contrasts; only a clause-initial "While X, Y" concedes
                continue
            strong.append(word)
    return strong, offsets


NEGATION = _rx(r"\b(?:not|no|never|none|nor|neither|without|cannot|absent|lacks?|lacked|lacking)\b|n['’]t\b")
FIRST_PERSON = _rx(r"\b(?:we|our|us)\b")


def _reported_is_status(text: str, start: int, end: int) -> bool:
    """'participants reported' is a status; 'we report', 'the reported benchmarks' and 'reported in Table 2' are not."""
    if re.search(r"\b(?:we|here|this (?:study|paper|article|work))\s+$", text[max(0, start - 20):start], re.IGNORECASE):
        return False
    if re.search(r"\b(?:the|our|these|those)\s+$", text[max(0, start - 8):start], re.IGNORECASE):
        return False  # "the reported benchmarks" names the paper's own results, not a self-report
    return not re.match(r"\s+(?:in|at)\s+(?:table|fig|figure|supplementary|section|appendix|box)", text[end:end + 30],
                        re.IGNORECASE)


def _ladder(text: str, rungs: tuple[Rung, ...]) -> list[tuple[int, str, str]]:
    found = []
    for rung in rungs:
        for m in rung.rx.finditer(text):
            if rung.keep is None or rung.keep(text, m.start(), m.end()):
                found.append((rung.level, rung.name, " ".join(m.group(0).lower().split())))
    return found


def _scope_keys(text: str) -> list[tuple[str, str]]:
    taken: list[tuple[int, int]] = []
    keys = []
    for rx, key in SCOPE:
        for m in rx.finditer(text):
            if any(m.start() < b and a < m.end() for a, b in taken):
                continue
            taken.append(m.span())
            keys.append((key(m), " ".join(m.group(0).split())))
    return keys


def _status_keys(text: str) -> list[tuple[str, str]]:
    taken: list[tuple[int, int]] = []
    keys = []
    for key, rx in EVIDENCE_STATUS:
        for m in rx.finditer(text):
            if any(m.start() < b and a < m.end() for a, b in taken):
                continue
            if key == "reported" and not _reported_is_status(text, m.start(), m.end()):
                continue
            taken.append(m.span())
            keys.append((key, m.group(0).lower()))
    return keys


def _keyed_diff(before: list[tuple[str, str]], after: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    """Surface forms of keys that lost or gained occurrences; synonyms within one key are not a change."""
    kb, ka = Counter(k for k, _ in before), Counter(k for k, _ in after)
    removed = [s for k in kb - ka for s in _surfaces(before, k)]
    added = [s for k in ka - kb for s in _surfaces(after, k)]
    return removed, added


def _surfaces(pairs: list[tuple[str, str]], key: str) -> list[str]:
    return sorted({s for k, s in pairs if k == key})


def _strength(markers: list[tuple[int, str, str]], plain: int) -> tuple[int, int]:
    levels = [level for level, _, _ in markers] + [plain]
    return min(levels), max(levels)


def _direction(before: list[tuple[int, str, str]], after: list[tuple[int, str, str]], plain: int) -> str | None:
    bmin, bmax = _strength(before, plain)
    amin, amax = _strength(after, plain)
    up, down = amin > bmin or amax > bmax, amin < bmin or amax < bmax
    return "mixed" if up and down else "raised" if up else "lowered" if down else None


def _rung_names(markers: list[tuple[int, str, str]]) -> str:
    names = [name for _, name, _ in sorted(set(markers))]
    return "+".join(dict.fromkeys(names)) or "plain statement"


# ---------------------------------------------------------------------------------------------------------------
# Numbers, citations and identifiers per sentence
# ---------------------------------------------------------------------------------------------------------------

CITE_TEX = re.compile(r"\\[a-zA-Z]*cite[a-zA-Z]*\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}")
CITE_PANDOC = re.compile(r"(?<![\w.])@([A-Za-z][\w:.#$%&+?<>~/-]*[\w])")
CITE_NUMERIC = re.compile(r"\[(\d+(?:\s*[-–—,]\s*\d+)*)\]")
CITE_PAREN = re.compile(r"\((?:[^()]*?\b(?:19|20)\d{2}[a-z]?\b[^()]*?)\)")
SURNAME = r"(?:(?:van|von|de|del|der|den|la|le|du) )*[A-ZÀ-ÖØ-ÞĀ-Ž][^\W\d_]*(?:['’\-][^\W\d_]+)*"
AUTHOR_YEAR = re.compile(rf"({SURNAME})(?:\s+(?:et al\.?|(?:and|&) {SURNAME}))?,?\s+((?:19|20)\d{{2}}[a-z]?)")
NARRATIVE = re.compile(rf"({SURNAME})(?:\s+(?:et al\.?|(?:and|&) {SURNAME}))?\s+\(((?:19|20)\d{{2}}[a-z]?)\)")
TEX_POINTERS = re.compile(r"\\(?:[a-zA-Z]*ref|label|url|href|includegraphics|input|include)\*?(?:\[[^\]]*\])?\{[^}]*\}")
TOKEN_KINDS = ("number", "citation", "identifier")


def _blank_spans(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for a, b in spans:
        chars[a:b] = " " * (b - a)
    return "".join(chars)


def _norm_number(s: str) -> str:
    s = s.replace("−", "-").replace("\u2009", "").replace("\u00a0", "").replace(" ", "")
    return re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", s).lower()


def _expand_numeric(group: str) -> list[int]:
    """'1-3, 5' → [1, 2, 3, 5], so adding reference 4 to [3] reports [4] alone."""
    out: list[int] = []
    for part in re.split(r"\s*,\s*", group.strip()):
        bounds = [int(x) for x in re.split(r"\s*[-–—]\s*", part) if x.strip().isdigit()]
        if len(bounds) == 2 and 0 <= bounds[1] - bounds[0] <= 50:
            out += range(bounds[0], bounds[1] + 1)
        else:
            out += bounds
    return out


def sentence_tokens(text: str) -> dict[str, Counter[str]]:
    """Numbers, citations and identifiers in one sentence, normalised so formatting alone is not a change."""
    cites: Counter[str] = Counter()
    spans: list[tuple[int, int]] = []
    for m in CITE_TEX.finditer(text):
        cites.update("\\cite{" + k.strip() + "}" for k in m.group(1).split(",") if k.strip())
        spans.append(m.span())
    for m in CITE_PANDOC.finditer(text):
        cites["@" + m.group(1)] += 1
        spans.append(m.span())
    for m in CITE_NUMERIC.finditer(text):
        cites.update(f"[{n}]" for n in _expand_numeric(m.group(1)))
        spans.append(m.span())
    for m in NARRATIVE.finditer(text):
        cites[f"{m.group(1)} {m.group(2)}"] += 1
        spans.append(m.span())
    masked = _blank_spans(text, spans)
    for m in CITE_PAREN.finditer(masked):
        for unit in AUTHOR_YEAR.finditer(m.group(0)):
            cites[f"{unit.group(1)} {unit.group(2)}"] += 1
            spans.append((m.start() + unit.start(), m.start() + unit.end()))
    masked = _blank_spans(text, spans)
    ids: Counter[str] = Counter()
    id_spans = []
    for m in PROTECTED["identifiers"].finditer(masked):
        ids[" ".join(m.group(0).split()).lower().rstrip(".,;:")] += 1
        id_spans.append(m.span())
    id_spans += [m.span() for m in PROTECTED["urls"].finditer(masked)]
    id_spans += [m.span() for m in TEX_POINTERS.finditer(masked)]
    masked = _blank_spans(masked, id_spans)
    numbers = Counter(_norm_number(m.group(0)) for m in PROTECTED["numbers"].finditer(masked))
    return {"number": numbers, "citation": cites, "identifier": ids}


# ---------------------------------------------------------------------------------------------------------------
# Sentence-level comparison
# ---------------------------------------------------------------------------------------------------------------

CLAIM_KINDS = ("causal", "evidential", "generality", "scope", "limitation", "null_result", "evidence_status")


def _finding(kind: str, change: str, severity: str, g: Group, bs: list[Sentence], as_: list[Sentence],
             **extra: object) -> dict[str, object]:
    before = " ".join(bs[i].text for i in g.before)
    after = " ".join(as_[j].text for j in g.after)
    out: dict[str, object] = {
        "id": 0, "kind": kind, "change": change, "severity": severity, "authorised": False,
        "section": as_[g.after[0]].section if g.after else bs[g.before[0]].section,
        "before_line": bs[g.before[0]].line if g.before else None,
        "after_line": as_[g.after[0]].line if g.after else None,
        "alignment": g.kind, "before": before, "after": after,
        "removed": [], "added": [], "strength_before": None, "strength_after": None,
        "token": None, "token_status": None, "note": "",
    }
    out.update(extra)
    return out


def _claim_findings(g: Group, bs: list[Sentence], as_: list[Sentence]) -> list[dict[str, object]]:
    tb = " ".join(bs[i].text for i in g.before)
    ta = " ".join(as_[j].text for j in g.after)
    found: list[dict[str, object]] = []
    negated = bool(NEGATION.search(tb) or NEGATION.search(ta))
    whole = "inserted" if not g.before else "deleted" if not g.after else None

    for kind, rungs, plain in (("causal", CAUSAL, CAUSAL_PLAIN), ("evidential", EVIDENTIAL, EVIDENTIAL_PLAIN)):
        mb, ma = _ladder(tb, rungs), _ladder(ta, rungs)
        removed = sorted((Counter(s for _, _, s in mb) - Counter(s for _, _, s in ma)).elements())
        added = sorted((Counter(s for _, _, s in ma) - Counter(s for _, _, s in mb)).elements())
        if not g.after or not g.before:
            markers = mb or ma
            if not markers:
                continue
            strong = max(level for level, _, _ in markers) >= 1
            change = "removed" if not g.after else "added"
            severity = "protected" if change == "added" and strong else "warning"
            note = ("Deleting a claim changes the science, so the authors must see it." if change == "removed"
                    else "A new claim needs the authors' approval and its evidence.")
            found.append(_finding(kind, change, severity, g, bs, as_, removed=removed, added=added,
                                  strength_before=_rung_names(mb) if mb else None,
                                  strength_after=_rung_names(ma) if ma else None, note=note))
            continue
        direction = _direction(mb, ma, plain)
        if direction is None:
            continue
        severity = "warning" if direction == "lowered" and not negated else "protected"
        note = ("The sentence is negated, so a weaker verb can make the claim stronger; read both versions." if negated
                else "Narrowing a claim is a correction the authors must approve." if direction == "lowered" else "")
        found.append(_finding(kind, direction, severity, g, bs, as_, removed=removed, added=added,
                              strength_before=_rung_names(mb), strength_after=_rung_names(ma), note=note))

    gen_removed, gen_added = _keyed_diff(
        [(k, " ".join(m.group(0).lower().split())) for k, rx in GENERALITY for m in rx.finditer(tb)],
        [(k, " ".join(m.group(0).lower().split())) for k, rx in GENERALITY for m in rx.finditer(ta)])
    if gen_added:
        found.append(_finding("generality", "raised", "protected", g, bs, as_, removed=gen_removed, added=gen_added,
                              note="The claim now reaches further than the authors wrote."))
    elif gen_removed:
        found.append(_finding("generality", "lowered", "warning", g, bs, as_, removed=gen_removed,
                              note="The claim now reaches less far, which the authors must approve."))

    sb, sa = _scope_keys(tb), _scope_keys(ta)
    if g.after and FIRST_PERSON.search(ta):  # "In this study, we show" → "We show" keeps the study as the scope
        sb = [(k, s) for k, s in sb if k != "this-study"]
    if not g.after:
        sb = [(k, s) for k, s in sb if k != "this-study"]
    s_removed, s_added = _keyed_diff(sb, sa)
    if s_removed:
        found.append(_finding("scope", "replaced" if s_added else "removed", "protected", g, bs, as_,
                              removed=s_removed, added=s_added, note="The claim may now read as more general than the "
                              "data."))
    elif s_added and whole is None:
        found.append(_finding("scope", "added", "warning", g, bs, as_, added=s_added,
                              note="This narrows the claim, so the authors must see it."))

    (lb, ob), (la, oa) = _limitation_marks(tb), _limitation_marks(ta)
    l_removed = sorted((Counter(lb) - Counter(la)).elements())
    l_added = sorted((Counter(la) - Counter(lb)).elements())
    if len(lb) > len(la) and len(lb) + ob > len(la) + oa and whole != "inserted":
        # The claim widens when its sentence survives without the limit; a deleted sentence and a claim narrowed in
        # the same edit (a lowered rung, an added qualifier) are warnings the authors must still see.
        narrowed = any(c["change"] == "lowered" and c["kind"] in ("causal", "evidential")
                       or (c["kind"] == "scope" and c["change"] == "added") for c in found)
        note = ("The sentence that held it was deleted, so list it for the authors." if whole else
                "The claim was also narrowed in the same edit, so check that the limit survives."
                if narrowed else "The claim may now read as resting on more evidence, or holding more widely, than "
                "the authors wrote.")
        severity = "warning" if whole or narrowed else "protected"
        found.append(_finding("limitation", "removed", severity, g, bs, as_, removed=l_removed, added=l_added,
                              note=note))
    elif len(la) > len(lb) and len(la) + oa > len(lb) + ob and whole is None:
        found.append(_finding("limitation", "added", "warning", g, bs, as_, removed=l_removed, added=l_added,
                              note="This narrows the claim, so the authors must see it."))

    nb, na = [m.group(0).lower() for m in NULL_RESULT.finditer(tb)], [m.group(0).lower() for m in NULL_RESULT.finditer(ta)]
    null_change = None
    if len(nb) > len(na) and whole != "inserted":
        null_change = "removed"
        found.append(_finding("null_result", "removed", "protected", g, bs, as_,
                              removed=sorted((Counter(nb) - Counter(na)).elements()) or sorted(set(nb)),
                              added=sorted((Counter(na) - Counter(nb)).elements()),
                              note="A null or negative result must stay stated as one: a rewording can turn "
                                   "absence of evidence into evidence of absence."))
    elif len(na) > len(nb):
        null_change = "added"
        found.append(_finding("null_result", "added", "warning", g, bs, as_,
                              added=sorted((Counter(na) - Counter(nb)).elements()) or sorted(set(na)),
                              note="A new null result changes what the sentence reports, so the authors must see "
                                   "it."))

    e_removed, e_added = _keyed_diff(_status_keys(tb), _status_keys(ta))
    if e_removed and whole != "inserted":
        found.append(_finding("evidence_status", "replaced" if e_added else "removed", "protected", g, bs, as_,
                              removed=e_removed, added=e_added,
                              note="The sentence now says the finding was obtained another way." if e_added else
                              "Readers can no longer tell how the finding was obtained."))
    elif e_added and whole is None:
        found.append(_finding("evidence_status", "added", "warning", g, bs, as_, added=e_added,
                              note="This changes how the finding is said to have been obtained, so the authors "
                                   "must see it."))

    gb, ga = [m.group(0).lower() for m in NEGATION.finditer(tb)], [m.group(0).lower() for m in NEGATION.finditer(ta)]
    if len(gb) != len(ga) and whole is None:  # a whole new or deleted sentence is reported by its claims and tokens
        change = "removed" if len(gb) > len(ga) else "added"
        if change != null_change:
            found.append(_finding("negation", change, "warning", g, bs, as_,
                                  removed=sorted((Counter(gb) - Counter(ga)).elements()),
                                  added=sorted((Counter(ga) - Counter(gb)).elements()),
                                  note="Check that the claim did not flip."))
    return found


def _token_findings(g: Group, bs: list[Sentence], as_: list[Sentence], tok_b: list[dict[str, Counter[str]]],
                    tok_a: list[dict[str, Counter[str]]], ctx: dict[str, object]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    b_blocks = {bs[i].block for i in g.before}
    a_blocks = {as_[j].block for j in g.after}
    near_b = b_blocks | {b for a in a_blocks for b in ctx["a2b"].get(a, ())}  # type: ignore[union-attr]
    near_a = a_blocks | {a for b in b_blocks for a in ctx["b2a"].get(b, ())}  # type: ignore[union-attr]
    for kind in TOKEN_KINDS:
        cb: Counter[str] = sum((tok_b[i][kind] for i in g.before), Counter())
        ca: Counter[str] = sum((tok_a[j][kind] for j in g.after), Counter())
        for token in sorted(ca - cb):
            in_paragraph = any(token in ctx["block_b"][b][kind] for b in near_b)  # type: ignore[index]
            status = ("moved_within_paragraph" if in_paragraph else
                      "from_elsewhere" if token in ctx["doc_b"][kind] else "new")  # type: ignore[index]
            found.append(_finding(kind, "added", "warning" if in_paragraph else "protected", g, bs, as_,
                                  added=[token], token=token, token_status=status,
                                  note={"new": "It is not in the original.", "from_elsewhere": "It appears "
                                        "elsewhere in the original, but not in this sentence or its paragraph.",
                                        "moved_within_paragraph": "It moved here from another sentence of the same "
                                        "paragraph."}[status]))
        for token in sorted(cb - ca):
            in_paragraph = any(token in ctx["block_a"][a][kind] for a in near_a)  # type: ignore[index]
            status = ("moved_within_paragraph" if in_paragraph else
                      "moved_elsewhere" if token in ctx["doc_a"][kind] else "removed")  # type: ignore[index]
            found.append(_finding(kind, "removed", "warning" if in_paragraph else "protected", g, bs, as_,
                                  removed=[token], token=token, token_status=status,
                                  note={"removed": "It is not in the edited text.", "moved_elsewhere": "It is now "
                                        "only in another paragraph.", "moved_within_paragraph": "It moved to another "
                                        "sentence of the same paragraph."}[status]))
    return found


def sentence_changes(before_text: str, after_text: str) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Align the sentences of two versions and list claim, scope and token changes with their locations."""
    bs, as_ = segment(before_text), segment(after_text)
    groups = align(bs, as_)
    tok_b = [sentence_tokens(s.text) for s in bs]
    tok_a = [sentence_tokens(s.text) for s in as_]

    def by_block(sents: list[Sentence], toks: list[dict[str, Counter[str]]]) -> dict[int, dict[str, Counter[str]]]:
        out: dict[int, dict[str, Counter[str]]] = {}
        for s, t in zip(sents, toks):
            slot = out.setdefault(s.block, {k: Counter() for k in TOKEN_KINDS})
            for k in TOKEN_KINDS:
                slot[k].update(t[k])
        return out

    b2a: dict[int, set[int]] = {}
    a2b: dict[int, set[int]] = {}
    for g in groups:
        for i in g.before:
            for j in g.after:
                b2a.setdefault(bs[i].block, set()).add(as_[j].block)
                a2b.setdefault(as_[j].block, set()).add(bs[i].block)
    ctx: dict[str, object] = {
        "b2a": b2a, "a2b": a2b, "block_b": by_block(bs, tok_b), "block_a": by_block(as_, tok_a),
        "doc_b": {k: set().union(*(t[k] for t in tok_b)) for k in TOKEN_KINDS},
        "doc_a": {k: set().union(*(t[k] for t in tok_a)) for k in TOKEN_KINDS},
    }
    changes: list[dict[str, object]] = []
    for g in groups:
        if g.kind == "equal":
            continue
        changes += _claim_findings(g, bs, as_)
        changes += _token_findings(g, bs, as_, tok_b, tok_a, ctx)
    changes.sort(key=lambda c: (c["after_line"] if c["after_line"] is not None else c["before_line"] or 0,
                                c["before_line"] or 0))
    for n, c in enumerate(changes, 1):
        c["id"] = n
    counts = Counter(g.kind for g in groups)
    alignment = {"sentences_before": len(bs), "sentences_after": len(as_), "unchanged": counts["equal"],
                 "changed": counts["changed"], "split": counts["split"], "merged": counts["merged"],
                 "moved": counts["moved"], "deleted": counts["deleted"], "inserted": counts["inserted"]}
    return changes, alignment


def document_title(text: str) -> Optional[str]:
    """The paper's title when it is the one level-1 Markdown heading above the sections, else None."""
    masked = _mask(text, _is_latex(text))
    headings = [(len(m.group(1)), _clean_title(m.group(2))) for m in map(MD_HEADING.match, masked.split("\n")) if m]
    if len(headings) > 1 and headings[0][0] == 1 and sum(level == 1 for level, _ in headings) == 1:
        return headings[0][1]
    return None


def compare(before_text: str, after_text: str, threshold: float = 0.5, *, revision: bool = False,
            allow_strengthening: bool = False) -> dict[str, object]:
    latex = _is_latex(before_text) or _is_latex(after_text)
    before, after = _prose(before_text, latex), _prose(after_text, latex)
    protected = {name: _diff(_items(before, rx), _items(after, rx)) for name, rx in PROTECTED.items()}
    watched = {name: _diff(_items(before, rx), _items(after, rx)) for name, rx in WATCHED.items()}
    changes, alignment = sentence_changes(before_text, after_text)
    if allow_strengthening:
        for c in changes:
            if c["kind"] in CLAIM_KINDS and c["severity"] == "protected":
                c["authorised"] = True
    summary = Counter(f"{c['severity']}" for c in changes)
    return {
        "mode": "revision" if revision else "edit",
        "title": document_title(after_text) or document_title(before_text),
        "allow_strengthening": allow_strengthening,
        "protected": {k: v for k, v in protected.items() if v["removed"] or v["added"]},
        "watched": {k: v for k, v in watched.items() if v["removed"] or v["added"]},
        "rewritten_paragraphs": _rewritten_paragraphs(before, after, threshold),
        "words_before": len(before.split()),
        "words_after": len(after.split()),
        "change_rate": change_rate(before, after),
        "sentence_changes": changes,
        "alignment": alignment,
        "summary": {"protected": summary["protected"], "warning": summary["warning"],
                    "authorised": sum(1 for c in changes if c["authorised"]),
                    "by_kind": dict(Counter(str(c["kind"]) for c in changes))},
    }


def exit_code(report: dict[str, object]) -> int:
    """1 when an edit made a protected change; revision inventories always return 0."""
    if report["mode"] == "revision":
        return 0
    if report["protected"]:
        return 1
    return int(any(c["severity"] == "protected" and not c["authorised"]
                   for c in report["sentence_changes"]))  # type: ignore[union-attr]


def _git_show(path: Path, ref: str) -> str:
    listed = subprocess.run(["git", "-C", str(path.parent), "ls-files", "--full-name", path.name],
                            capture_output=True, text=True)
    rel = listed.stdout.strip()
    if listed.returncode != 0 or not rel:
        raise typer.BadParameter(f"{path} is not tracked by git, so there is no earlier version to compare with.")
    shown = subprocess.run(["git", "-C", str(path.parent), "show", f"{ref}:{rel}"], capture_output=True, text=True)
    if shown.returncode != 0:
        raise typer.BadParameter(f"git has no version of {rel} at {ref!r}: {shown.stderr.strip()}")
    return shown.stdout


# ---------------------------------------------------------------------------------------------------------------
# The Markdown report: every change in plain words, with its section and the sentence quoted
# ---------------------------------------------------------------------------------------------------------------

CAUSAL_WORDS = {"compatibility": "compatibility with a finding", "association": "an association",
                "prediction": "a prediction", "contribution": "a contribution", "effect": "an effect",
                "causation": "a cause", "plain statement": "a plain statement of effect"}
EVIDENTIAL_WORDS = {"possibility": "a possibility", "suggestion": "a suggestion", "indication": "an indication",
                    "demonstration": "a demonstration", "proof": "proof", "plain statement": "a plain assertion"}
TOKEN_NOUNS = {"number": ("number", "numbers"), "citation": ("citation", "citations"),
               "identifier": ("identifier", "identifiers")}
COUNT_NOUNS = {"numbers": ("number", "numbers"), "citations": ("citation", "citations"),
               "identifiers": ("identifier", "identifiers"), "urls": ("link", "links"),
               "code": ("code span", "code spans"), "terms": ("technical term", "technical terms"),
               "hedges": ("hedge", "hedges"), "negations": ("negation", "negations"),
               "causal": ("causal or proof word", "causal or proof words"),
               "comparatives": ("comparative or quantifier", "comparatives and quantifiers")}
EXCERPT = 160


def _q(text: object) -> str:
    return "“" + str(text) + "”"


def _listed(items: list[str]) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


SMALL_NUMBERS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def _count_word(n: int, one: str, many: str) -> str:
    """'one place', 'three places', '12 places': small counts in words, as in running prose."""
    return f"{SMALL_NUMBERS[n] if n < len(SMALL_NUMBERS) else n} {one if n == 1 else many}"


def _quoted_list(words: object) -> str:
    return _listed([_q(w) for w in words])  # type: ignore[union-attr]


def _upper_first(sentence: str) -> str:
    return sentence[:1].upper() + sentence[1:]


def _lower_first(sentence: str) -> str:
    """'A negation changed' → 'a negation changed' after 'In the Results, '; 'APOE ...' and 'GRCh38 ...' stay."""
    first = sentence.split(" ", 1)[0]
    if len(first) > 1 and any(ch.isupper() or ch.isdigit() for ch in first[1:]):
        return sentence
    return sentence[:1].lower() + sentence[1:]


def excerpt(text: object, marks: object = (), width: int = EXCERPT) -> str:
    """The sentence quoted, cut to about `width` characters around the first changed word, which is in bold."""
    body = " ".join(str(text).split())
    spans: list[tuple[int, int]] = []
    for mark in marks or ():  # type: ignore[union-attr]
        if mark:
            spans += [m.span() for m in re.finditer(rf"(?<!\w){re.escape(str(mark))}(?!\w)", body, re.IGNORECASE)]
    lo, hi = 0, len(body)
    if len(body) > width + 40:
        first = min(spans)[0] if spans else 0
        lo = max(0, first - width // 3)
        hi = min(len(body), lo + width)
        lo = max(0, hi - width)
        if lo > 0:
            lo = body.find(" ", lo) + 1 or lo
        if hi < len(body):
            cut = body.rfind(" ", lo, hi)
            hi = cut if cut > lo else hi
    merged: list[list[int]] = []
    for a, b in sorted(spans):
        if a < lo or b > hi:
            continue
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    piece = body[lo:hi]
    for a, b in reversed(merged):
        piece = piece[:a - lo] + "**" + piece[a - lo:b - lo] + "**" + piece[b - lo:]
    return _q(("…" if lo else "") + piece + ("…" if hi < len(body) else ""))


# "6. Conclusion", "5.1 Limitations", "A.2 Extra runs"; a bare capital ("A Study of ...") is a word, not a number.
NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*|[A-Z](?:\.\d+)+|[A-Z](?=\.))\.?\s+(\S.*)$")


def _section(c: dict[str, object], title: Optional[str]) -> str:
    """'the Results, Performance' or 'section 5.1, Limitations': the heading path without the paper's title,
    ready to follow 'In'. A numbered heading names its parents already, so only the deepest one is given."""
    section = str(c["section"] or "")
    if title and section.startswith(title + " > "):
        section = section[len(title) + 3:]
    elif title and section == title:
        return "the text under the title"
    if not section:
        return "the text before the first heading"
    numbered = NUMBERED_HEADING.match(section.split(" > ")[-1])
    if numbered:
        return f"section {numbered.group(1)}, {numbered.group(2)}"
    return "the " + section.replace(" > ", ", ")


def _unit(text: object) -> str:
    """What the guard aligned: a sentence, or a table row (Markdown or LaTeX), which is compared as one unit."""
    return "table row" if TABLE_ROW.match(str(text or "")) else "sentence"


def _where(c: dict[str, object], title: Optional[str]) -> str:
    b, a = c["before_line"], c["after_line"]
    unit = _unit(c["after"] or c["before"])
    lines = (f"line {a}" if b == a else f"line {b} before the edit, line {a} after") if a and b else (
        f"a new {unit}, line {a}" if a else f"a deleted {unit}, line {b} before the edit")
    return f"{_section(c, title)} ({lines})"


def _became(removed: object, added: object) -> str:
    r, a = list(removed or []), list(added or [])  # type: ignore[call-overload]
    if r and a:
        return f"{_quoted_list(r)} became {_quoted_list(a)}"
    if r:
        return f"{_quoted_list(r)} {'was' if len(r) == 1 else 'were'} removed"
    return f"{_quoted_list(a)} {'was' if len(a) == 1 else 'were'} added"


def _strength_words(value: object, words: dict[str, str]) -> str:
    return _listed([words.get(n, n) for n in str(value or "plain statement").split("+")])


def describe(c: dict[str, object]) -> str:
    """What changed in one sentence, in plain words."""
    kind, change, removed, added = c["kind"], c["change"], c["removed"], c["added"]
    if kind in ("causal", "evidential"):
        words = CAUSAL_WORDS if kind == "causal" else EVIDENTIAL_WORDS
        measure = "the relation it states" if kind == "causal" else "its certainty"
        if change == "removed":
            return f"A {_unit(c['before'])} that claimed {_strength_words(c['strength_before'], words)} was deleted."
        if change == "added":
            return f"A new {_unit(c['after'])} claims {_strength_words(c['strength_after'], words)}."
        verdict = {"raised": "The claim became stronger", "lowered": "The claim became weaker",
                   "mixed": "The claim's strength changed in both directions"}[str(change)]
        moved = (f"{measure} went from {_strength_words(c['strength_before'], words)} to "
                 f"{_strength_words(c['strength_after'], words)}")
        return (f"{verdict}: {_became(removed, added)}, so {moved}." if removed or added else f"{verdict}: {moved}.")
    if kind == "generality":
        return (f"Wording that claims novelty or generality was added: {_quoted_list(added)}." if change == "raised"
                else f"Wording that claimed novelty or generality was removed: {_quoted_list(removed)}.")
    if kind == "scope":
        if change == "added":
            return f"The scope qualifier {_quoted_list(added)} was added."
        if change == "replaced":
            return f"The scope qualifier {_quoted_list(removed)} was replaced by {_quoted_list(added)}."
        return f"The scope qualifier {_quoted_list(removed)} was dropped."
    if kind == "limitation":
        if change == "added":
            return f"The limiting word {_quoted_list(added)} was added."
        return f"The limiting word {_quoted_list(removed)} was dropped."
    if kind == "null_result":
        return (f"The null result {_quoted_list(removed)} is no longer stated." if change == "removed"
                else f"A null result was added: {_quoted_list(added)}.")
    if kind == "evidence_status":
        if change == "added":
            return f"The word {_quoted_list(added)}, which says how the finding was obtained, was added."
        if change == "replaced":
            return f"{_upper_first(_became(removed, added))}, which says how the finding was obtained."
        return f"The word {_quoted_list(removed)}, which said how the finding was obtained, was dropped."
    if kind == "negation":
        return f"A negation changed: {_became(removed, added)}."
    return f"The {kind} changed: {_became(removed, added)}."


def _action(c: dict[str, object], revision: bool) -> str:
    if revision:
        return ""
    if c["authorised"]:
        return "The authors authorised this claim change; it is listed so they see it."
    if c["severity"] == "protected":
        return "Revert this unless the authors asked for it."
    return "Show this to the authors if it stays."


def _claim_lines(c: dict[str, object], title: Optional[str], revision: bool) -> list[str]:
    head = " ".join(x for x in (f"In {_where(c, title)}, {_lower_first(describe(c))}", str(c["note"] or ""),
                                _action(c, revision)) if x)
    out = [f"- {head}"]
    if c["before"]:
        out.append(f"  - Before the edit: {excerpt(c['before'], c['removed'])}")
    if c["after"]:
        out.append(f"  - After the edit: {excerpt(c['after'], c['added'])}")
    return out


TOKEN_SENTENCES = {
    "new": ("{items} {is} new: {they} {is} not in the original.", "Remove {them} unless the authors supplied {them}."),
    "from_elsewhere": ("{items} {is} new to this sentence and its paragraph; {they} {appear} elsewhere in the "
                       "original.", "Check that {they} {belong} here."),
    "moved_within_paragraph": ("{items} moved between sentences of the same paragraph.",
                               "Check that {they} still {belong} to the right claim."),
    "removed": ("{items} {was} removed and {is} not in the edited text.",
                "Restore {them} unless the authors asked for the change."),
    "moved_elsewhere": ("{items} {was} removed from this sentence and {is} now only in another paragraph.",
                        "Check that {they} still {belong} to the right claim."),
}


def _token_sentence(kind: str, status: str, tokens: list[str], revision: bool) -> str:
    one = len(tokens) == 1
    noun = TOKEN_NOUNS.get(kind, (kind, kind + "s"))[0 if one else 1]
    fill = {"items": f"The {noun} {_quoted_list(tokens)}", "is": "is" if one else "are", "was": "was" if one else "were",
            "they": "it" if one else "they", "them": "it" if one else "them", "appear": "appears" if one else "appear",
            "belong": "belongs" if one else "belong"}
    what, action = TOKEN_SENTENCES[status]
    return what.format(**fill) + ("" if revision else " " + action.format(**fill))


def _token_lines(tokens: list[dict[str, object]], title: Optional[str], revision: bool) -> list[str]:
    """One bullet per sentence pair; within it, one sentence per kind of token and what happened to it."""
    pairs: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for c in tokens:
        pairs.setdefault((c["before_line"], c["after_line"], c["before"], c["after"]), []).append(c)
    out = []
    for (_, _, before, after), items in pairs.items():
        groups: dict[tuple[str, str], list[str]] = {}
        for c in items:
            groups.setdefault((str(c["kind"]), str(c["token_status"])), []).append(str(c["token"]))
        sentences = [_token_sentence(kind, status, toks, revision) for (kind, status), toks in groups.items()]
        sentences[0] = f"In {_where(items[0], title)}, {_lower_first(sentences[0])}"
        out.append("- " + " ".join(sentences))
        marks = [str(c["token"]) for c in items]
        if before:
            out.append(f"  - Before the edit: {excerpt(before, marks)}")
        if after:
            out.append(f"  - After the edit: {excerpt(after, marks)}")
    return out


def _count_items(counts: dict[str, int]) -> str:
    return _listed([_q(k) + (f" ({n} times)" if n > 1 else "") for k, n in counts.items()])


def _count_lines(groups: dict[str, dict[str, dict[str, int]]]) -> list[str]:
    out = []
    for name, d in groups.items():
        for direction in ("removed", "added"):
            items = d.get(direction) or {}
            if not items:
                continue
            noun = COUNT_NOUNS.get(name, (name, name))[0 if len(items) == 1 else 1]
            out.append(f"- The {noun} {_count_items(items)} {'was' if len(items) == 1 else 'were'} "
                       f"{'removed' if direction == 'removed' else 'added'}.")
    return out


def to_markdown(report: dict[str, object]) -> str:
    revision = report.get("mode") == "revision"
    title = report.get("title")  # type: ignore[assignment]
    changes = report.get("sentence_changes", [])
    claims = [c for c in changes if c["token"] is None]  # type: ignore[union-attr]
    tokens = [c for c in changes if c["token"] is not None]  # type: ignore[union-attr]
    open_changes = [c for c in changes if c["severity"] == "protected" and not c["authorised"]]  # type: ignore[union-attr]
    shown = [c for c in changes if c["severity"] != "protected" or c["authorised"]]  # type: ignore[union-attr]
    rate = float(report["change_rate"])  # type: ignore[arg-type]
    lines = ["# Revision inventory: what changed between the two versions" if revision else "# What the edit changed",
             ""]
    if revision:
        lines.append(f"This is a revision, so content changes are expected. The comparison lists {len(changes)} "
                     "changes, sentence by sentence; check each against the response letter or the authors' "
                     "instructions. Nothing here fails the run.")
    elif open_changes:
        one = len(open_changes) == 1
        lines.append(f"The edit changed content in {_count_word(len(open_changes), 'place', 'places')}, listed below; "
                     f"revert {'it' if one else 'each'} unless the authors asked for {'it' if one else 'them'}."
                     + (f" {_upper_first(_count_word(len(shown), 'other change needs', 'other changes need'))} "
                        "only to be shown to the authors." if shown else ""))
    elif report["protected"]:
        lines.append("The edit added or removed a number, citation, identifier, link, code span or technical term "
                     "that no single sentence accounts for; the counts over the whole text below name it. Revert the "
                     "change unless the authors asked for it."
                     + (f" {_upper_first(_count_word(len(shown), 'other change needs', 'other changes need'))} "
                        "only to be shown to the authors." if shown else ""))
    elif shown:
        lines.append(f"The edit changed no content that must be reverted. "
                     f"{_upper_first(_count_word(len(shown), 'change', 'changes'))} should be shown to the authors.")
    else:
        lines.append("This comparison found no change of content. It cannot prove that the meaning is unchanged, so "
                     "read the edited passages in context.")
    level = (" More than half the words changed, so check the meaning and that the edit stayed within the request."
             if rate > CHANGE_STOP else " More than a quarter of the words changed, so reread the text for meaning."
             if rate > CHANGE_WARN else "")
    share = "Less than 1%" if 0 < rate < 0.005 else "None" if rate == 0 else f"About {round(100 * rate)}%"
    lines += ["", f"{share} of the original words changed ({report['words_before']} words before, "
                  f"{report['words_after']} after).{level}", ""]
    lines.append("## Changes to what the claims say, sentence by sentence")
    lines += [""] + ([x for c in claims for x in _claim_lines(c, title, revision)] or  # type: ignore[arg-type]
                     ["No sentence changed how strong, how general or how qualified its claim is."])
    lines += ["", "## Numbers, citations and identifiers, sentence by sentence", ""]
    lines += _token_lines(tokens, title, revision) or [  # type: ignore[arg-type]
        "No sentence gained or lost a number, citation or identifier."]
    summary = report.get("summary", {})
    if summary.get("authorised"):  # type: ignore[union-attr]
        n = summary["authorised"]  # type: ignore[index]
        marked = _count_word(n, "claim change is", "claim changes are")
        lines += ["", f"The authors asked for a claim correction, so {marked} marked as authorised. "
                      f"{'It is' if n == 1 else 'They are'} still listed above so that the authors see "
                      f"{'it' if n == 1 else 'each one'} in place."]
    lines += ["", "## Counts over the whole text", ""]
    lines += _count_lines(report["protected"]) or [  # type: ignore[arg-type]
        "No number, citation, identifier, link, code span or technical term was added or removed."]
    watched = _count_lines(report["watched"])  # type: ignore[arg-type]
    lines += ["", "Hedges, negations and claim words also change with ordinary editing, and these counts have no "
                  "location. The sections above list each sentence in which the checks saw a claim change; for a "
                  "word below that they do not explain, find it in the text and check its sentence." if watched else
              "No hedge, negation or claim word was added or removed."]
    if watched:
        lines += [""] + watched
    rewritten = report["rewritten_paragraphs"]
    lines += ["", "## Paragraphs that were largely rewritten", ""]
    for p in rewritten:  # type: ignore[union-attr]
        kept = round(100 * float(p["similarity"]))
        if p["before"] and p["after"]:
            lines.append(f"- A paragraph kept about {kept}% of its wording. It began {_q(str(p['before']) + '…')} "
                         f"and now begins {_q(str(p['after']) + '…')}.")
        elif p["after"]:
            lines.append(f"- A new paragraph begins {_q(str(p['after']) + '…')}.")
        else:
            lines.append(f"- A paragraph that began {_q(str(p['before']) + '…')} was removed.")
    if not rewritten:
        lines.append("No paragraph was largely rewritten.")
    return "\n".join(lines) + "\n"


@app.command()
def main(
    before: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Original, or the edited file with --against")],
    after: Annotated[Optional[Path], typer.Argument(exists=True, dir_okay=False, help="Edited version")] = None,
    against: Annotated[Optional[str], typer.Option(help="Compare BEFORE (edited, on disk) with this git ref")] = None,
    threshold: Annotated[float, typer.Option(help="Flag paragraphs below this similarity")] = 0.5,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the report as JSON")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Also write the Markdown report to this file")] = None,
    revision: Annotated[bool, typer.Option("--revision", help="Inventory mode for a revised manuscript: list every "
                                           "content change with section and line; always exit 0")] = False,
    allow_strengthening: Annotated[bool, typer.Option("--allow-strengthening", help="The authors authorised a claim "
                                                      "correction: report claim changes without failing on them")] = False,
) -> None:
    if against:
        before_text, after_text = _git_show(before.resolve(), against), before.read_text(encoding="utf-8")
    elif after is not None:
        before_text, after_text = before.read_text(encoding="utf-8"), after.read_text(encoding="utf-8")
    else:
        raise typer.BadParameter("Give the edited file as the second argument, or name the git version to "
                                 "compare with in --against.")
    report = compare(before_text, after_text, threshold, revision=revision, allow_strengthening=allow_strengthening)
    markdown = to_markdown(report)
    if json_out:
        json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if md_out:
        md_out.write_text(markdown, encoding="utf-8")
    typer.echo(markdown)
    raise typer.Exit(code=exit_code(report))


if __name__ == "__main__":
    app()
