# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6"]
# ///
"""Deterministic number and statistics checks for a manuscript (Markdown, LaTeX or plain text).

Four checks. Each reports candidates for the authors to verify, with the arithmetic shown:

1. **Number ledger.** A named quantity stated with values that disagree between sections: a sample size
   ("412 participants", "patients (n = 412)", a table header "All participants (n = 421)") or a headline
   metric ("AUROC 0.87") in the Abstract, Methods, Results, tables and Conclusions.
2. **GRIM and GRIMMER.** A mean, and its SD, of integer-valued data (Likert ratings, counts) that no set of
   n whole numbers can produce at the reported precision; a percentage of n that is no whole count.
   Applied only where the text gives n and names integer data, or with --assume-integer.
3. **Statcheck-style recomputation.** The p-value implied by a reported t, F, chi-square, r or z
   statistic and its degrees of freedom, allowing for the rounding of both. An inconsistency is "gross"
   when it changes significance at the stated alpha (default 0.05).
4. **Table arithmetic.** A column total, in a "Total" row or in a sentence that cites the table ("across 19
   versions"), against the sum of the column's cells, allowing for their rounding; and a "mean ± SEM" column
   against its SD column divided by the square root of the row's n.

A calculator cannot know whether a number is exact or rounded, which data are integers, or which n a mean
was computed over. Every finding is a candidate, never a verdict. A statement that looks like a test
result or an integer mean but cannot be parsed is skipped and counted as not assessed, never passed.

Covered by scan.py instead: percentages stated beside their counts ("12 of 40 (30%)") and Abstract
figures that never reappear in the body.

Statistics use only the standard library: math.erfc for z, and the regularised incomplete beta (t, F, r)
and gamma (chi-square) functions computed by continued fractions. No scipy.

    uv run --script number_check.py PAPER.md
    uv run --script number_check.py PAPER.tex --alpha 0.01 --json numbers.json --md numbers.md
    uv run --script number_check.py PAPER.md --assume-integer     # GRIM every mean that states its n

Exit codes: 0 no major or minor candidate (informational ones, such as adjusted p-values, may remain); 1 at least
one major or minor candidate (read each in context); 2 usage error.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from pydantic import BaseModel

app = typer.Typer(add_completion=False, no_args_is_help=True)


class Severity(str, Enum):  # the same tiers as scan.py; this script never emits a blocker
    blocker = "blocker"
    major = "major"
    minor = "minor"
    info = "info"


class Finding(BaseModel):
    check: str  # ledger | grim | grimmer | percent-of-n | table-percent | table-total | sem-sd | statcheck
    severity: Severity
    line: Optional[int] = None
    excerpt: str = ""
    message: str
    arithmetic: str = ""
    suggestion: str = ""
    section: Optional[str] = None  # where a reader finds it: "Results", "Table 1, row Women"
    quote: str = ""  # the sentence or table row as written, shortened with [...] around the number
    quote_span: Optional[tuple[int, int]] = None  # where the number sits inside `quote`
    # Numbers that disagree are fixed now, while the analysis is open (references/author-priorities.md).
    stage: str = "now"


class Skipped(BaseModel):
    line: Optional[int] = None
    excerpt: str = ""
    reason: str
    section: Optional[str] = None


class CheckSummary(BaseModel):
    assessed: int = 0  # statements the check could evaluate
    consistent: int = 0
    candidates: int = 0  # inconsistent: a finding was written
    not_informative: int = 0  # evaluated, but the precision and n make every value possible
    not_assessed: list[Skipped] = []


class StatResult(BaseModel):
    line: Optional[int]
    excerpt: str
    test: str
    df: list[float]
    statistic: str
    reported_p: str
    p_two_tailed: tuple[float, float]
    p_one_tailed: Optional[tuple[float, float]] = None
    status: str  # consistent | consistent-one-tailed | inconsistent | gross | adjusted?
    note: str = ""


class Mention(BaseModel):
    key: str
    value: str
    line: Optional[int]
    section: str
    excerpt: str


class NumbersReport(BaseModel):
    path: str
    sha256: str
    alpha: float
    alpha_source: str
    findings: list[Finding]
    checks: dict[str, CheckSummary]
    statistics: list[StatResult]
    ledger: dict[str, list[Mention]]


# --------------------------------------------------------------------------------------------------
# Distributions (standard library only)
# --------------------------------------------------------------------------------------------------

_TINY = 1e-300


def _beta_cf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (modified Lentz evaluation)."""
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1.0)
    d = 1.0 / (d if abs(d) > _TINY else _TINY)
    h = d
    for m in range(1, 5000):
        for numerator in (m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m)),
                          -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))):
            d = 1.0 + numerator * d
            d = 1.0 / (d if abs(d) > _TINY else _TINY)
            c = 1.0 + numerator / c
            c = c if abs(c) > _TINY else _TINY
            h *= d * c
        if abs(d * c - 1.0) < 1e-15:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(log_front) * _beta_cf(a, b, x) / a
    return 1.0 - math.exp(log_front) * _beta_cf(b, a, 1.0 - x) / b


def gammaincc(a: float, x: float) -> float:
    """Regularised upper incomplete gamma function Q(a, x)."""
    if x <= 0.0:
        return 1.0
    log_front = -x + a * math.log(x) - math.lgamma(a)
    if x < a + 1.0:  # series for P(a, x)
        term = total = 1.0 / a
        ap = a
        for _ in range(10000):
            ap += 1.0
            term *= x / ap
            total += term
            if abs(term) < abs(total) * 1e-16:
                break
        return max(0.0, 1.0 - total * math.exp(log_front))
    b = x + 1.0 - a  # continued fraction for Q(a, x)
    c, d = 1.0 / _TINY, 1.0 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = 1.0 / (d if abs(d) > _TINY else _TINY)
        c = b + an / c
        c = c if abs(c) > _TINY else _TINY
        h *= d * c
        if abs(d * c - 1.0) < 1e-15:
            break
    return math.exp(log_front) * h


def p_z(z: float) -> float:
    """Two-tailed p for a standard normal statistic."""
    return math.erfc(abs(z) / math.sqrt(2.0))


def p_t(t: float, df: float) -> float:
    """Two-tailed p for Student's t."""
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def p_f(f: float, df1: float, df2: float) -> float:
    """Upper-tail p for F(df1, df2)."""
    if f <= 0:
        return 1.0
    return betainc(df2 / 2.0, df1 / 2.0, df2 / (df2 + df1 * f))


def p_chi2(x: float, df: float) -> float:
    """Upper-tail p for chi-square(df)."""
    return gammaincc(df / 2.0, x / 2.0)


def p_r(r: float, df: float) -> float:
    """Two-tailed p for a Pearson correlation with df = n - 2 (through its t statistic)."""
    if abs(r) >= 1.0:
        return 0.0
    return p_t(r * math.sqrt(df / (1.0 - r * r)), df)


# --------------------------------------------------------------------------------------------------
# Reading the manuscript
# --------------------------------------------------------------------------------------------------

NUM = r"(?:\d+(?:\.\d+)?|\.\d+)"
INT = r"(?:\d{1,3}(?:,\d{3})+|\d+)"

SECTION_NAMES = [
    ("abstract", r"abstract|summary|author summary|significance(?: statement)?|key points"),
    ("introduction", r"introduction|background"),
    ("methods", r"(?:materials? and |patients and |subjects and |participants and )?methods?(?: and materials)?|"
                r"online methods|star methods|methodology|study design|experimental (?:procedures|design)|"
                r"statistical analys[ie]s|participants|data(?: collection| sources)?|implementation"),
    ("results", r"results(?: and discussion)?|findings|evaluation|benchmarks?"),
    ("discussion", r"discussion|limitations"),
    ("conclusion", r"conclusions?|concluding remarks"),
    ("references", r"references|bibliography|literature cited|works cited"),
    ("supplement", r"supplementary.*|supporting information|appendi(?:x|ces).*"),
    ("back", r"acknowledge?ments?|funding|declarations?|competing interests?|conflicts? of interest|"
             r"author contributions?|data availability|code availability|availability.*|ethics.*"),
]
_SECTION_RES = [(label, re.compile(rf"^(?:[\dIVX]+[.)]?\s*)?(?:{pattern})\s*:?$", re.IGNORECASE))
                for label, pattern in SECTION_NAMES]
HEADLINE = {"abstract", "conclusion"}
TOTAL_SECTIONS = {"abstract", "methods", "table", "conclusion"}  # where a study states its sample size
UNCHECKED = {"references", "back"}

MD_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
BOLD_HEADING = re.compile(r"^\*\*([^*]{2,60})\*\*\s*:?\s*$")
TEX_HEADING = re.compile(r"\\(section|subsection|subsubsection|paragraph)\*?\s*(?:\[[^\]]*\])?\s*"
                         r"\{((?:[^{}]|\{[^{}]*\})*)\}")
TEX_LEVEL = {"section": 1, "subsection": 2, "subsubsection": 3, "paragraph": 4}
TABLE_CAPTION = re.compile(r"^\W{0,3}(?:table|tab\.)\s+([A-Z]?\d+[A-Za-z]?|[IVX]+)\b", re.IGNORECASE)

_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")


def _canonical(title: str) -> Optional[str]:
    title = re.sub(r"[*_`]|\\[a-z]+\{|[{}]", "", title).strip()
    for label, rx in _SECTION_RES:
        if rx.match(title):
            return label
    return None


def _tex_comment_free(line: str) -> str:
    """The line up to its first unescaped %."""
    i = 0
    while i < len(line):
        if line[i] == "\\":
            i += 2
            continue
        if line[i] == "%":
            return line[:i]
        i += 1
    return line


TEX_SUBS = [
    (re.compile(r"\\%"), "%"), (re.compile(r"\\pm(?![a-zA-Z])"), "±"), (re.compile(r"\\(?:times|cdot)(?![a-zA-Z])"), "×"),
    (re.compile(r"\\chi\s*\^\s*\{?\s*2\s*\}?"), "χ2"), (re.compile(r"\\chi(?![a-zA-Z])"), "χ"),
    (re.compile(r"\\leq?(?![a-zA-Z])|\\leqslant"), "≤"), (re.compile(r"\\geq?(?![a-zA-Z])|\\geqslant"), "≥"),
    (re.compile(r"\\textless(?![a-zA-Z])"), "<"), (re.compile(r"\\textgreater(?![a-zA-Z])"), ">"),
    (re.compile(r"\\alpha(?![a-zA-Z])"), "α"), (re.compile(r"\\approx(?![a-zA-Z])"), "≈"),
    (re.compile(r"\\(?:textit|emph|mathit|mathrm|textrm|text|textbf|mathbf|mbox|textsf|mathsf|textup|textnormal)"
                r"\s*\{([^{}]*)\}"), r"\1"),
    (re.compile(r"\\multicolumn\{[^{}]*\}\{[^{}]*\}\{([^{}]*)\}"), r"\1"),
    (re.compile(r"\^\s*\{\s*([-−]?\s*\d+)\s*\}"), r"^\1"), (re.compile(r"_\s*\{([^{}]*)\}"), r"\1"),
    (re.compile(r"\\[,;:! ]"), " "), (re.compile(r"(?<!\\)~"), " "), (re.compile(r"(?<!\\)\$"), ""),
    (re.compile(r"\{,\}"), ","), (re.compile(r"---?"), "–"),
    (re.compile(r"\\(?:hline|toprule|midrule|bottomrule|cmidrule(?:\([^)]*\))?\{[^}]*\})"), " "),
]
MD_SUBS = [
    (re.compile(r"<sup>\s*([^<]*?)\s*</sup>"), r"^\1"), (re.compile(r"</?(?:sub|em|i|b|strong)>"), ""),
    (re.compile(r"(?<![\w*])\*{1,2}([^*\n]{1,60}?)\*{1,2}(?![\w*])"), r"\1"),
    (re.compile(r"(?<![\w])_{1,2}([^_\n]{1,40}?)_{1,2}(?![\w])"), r"\1"),
]
COMMON_SUBS = [
    (re.compile(r"(?<=\d)[\u2009\u202f](?=\d{3}\b)"), ""), (re.compile(r"[\u00a0\u2009\u202f]"), " "),
    (re.compile(r"\u2212"), "-"), (re.compile(r"χ²|Χ2|Χ²|X²"), "χ2"), (re.compile(r"R²"), "R2"),
    (re.compile(r"h²"), "h2"),
]


def _normalise(line: str, latex: bool) -> str:
    for rx, sub in (TEX_SUBS if latex else MD_SUBS):
        line = rx.sub(sub, line)
    for rx, sub in COMMON_SUBS:
        line = rx.sub(sub, line)
    return line.translate(_SUPERSCRIPTS)


@dataclass
class Table:
    label: str
    caption: str = ""
    start_line: int = 0
    header: list[str] = field(default_factory=list)
    col_n: dict[int, int] = field(default_factory=dict)
    rows: list["Unit"] = field(default_factory=list)
    ref_key: str = ""  # the LaTeX \label, which the text cites as \ref{key}


@dataclass
class Unit:
    text: str
    starts: list[tuple[int, int]]  # (offset into text, source line number)
    section: str  # canonical label
    section_id: str  # what a reader calls the place: "Abstract", "Methods", "Table 1"
    kind: str = "prose"  # prose | row | caption
    table: Optional[Table] = None
    cells: list[str] = field(default_factory=list)

    def line_at(self, offset: int) -> int:
        line = self.starts[0][1]
        for start, number in self.starts:
            if start > offset:
                break
            line = number
        return line


@dataclass
class Document:
    units: list[Unit]
    latex: bool
    text: str  # normalised body text, for document-wide cues (one-tailed tests, alpha)


def _split_cells(row: str, latex: bool) -> list[str]:
    if latex:
        row = re.sub(r"\\\\\s*(?:\[[^\]]*\])?\s*$", "", row.strip())
        return [c.strip() for c in re.split(r"(?<!\\)&", row)]
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _column_n(cells: list[str]) -> dict[int, int]:
    out: dict[int, int] = {}
    for j, cell in enumerate(cells):
        m = re.search(rf"\b[nN]\s*=\s*({INT})\b", cell)
        if m:
            out[j] = int(m.group(1).replace(",", ""))
    return out


def _strip_comments(raw: str, latex: bool) -> list[str]:
    """Source lines with comments, commented-out blocks and the LaTeX preamble blanked; line numbers kept."""
    blank = lambda m: "\n" * m.group(0).count("\n")  # noqa: E731
    if not latex:
        return re.sub(r"<!--.*?-->", blank, raw, flags=re.DOTALL).split("\n")
    text = "\n".join(_tex_comment_free(l) for l in raw.splitlines())
    for rx in (r"\\begin\{comment\}.*?\\end\{comment\}", r"\\iffalse\b.*?\\fi\b"):
        text = re.sub(rx, blank, text, flags=re.DOTALL)
    doc_start = re.search(r"\\begin\{document\}", text)
    if doc_start:  # the preamble is not the paper
        text = "\n" * text[:doc_start.end()].count("\n") + text[doc_start.end():]
    return text.split("\n")


class _Builder:
    """Turns normalised source lines into units: prose paragraphs, table rows and table captions."""

    def __init__(self, lines: list[str], latex: bool) -> None:
        self.lines, self.latex = lines, latex
        self.units: list[Unit] = []
        self.section, self.section_id = "other", "Body"
        self.stack: list[tuple[int, Optional[str], str]] = []
        self.para: list[tuple[int, str]] = []
        self.consumed: set[int] = set()  # line indexes already used as table captions
        self.tex_tables = 0

    def flush(self) -> None:
        if not self.para:
            return
        parts, starts, offset = [], [], 0
        for number, content in self.para:
            starts.append((offset, number))
            parts.append(content)
            offset += len(content) + 1
        self.units.append(Unit(" ".join(parts), starts, self.section, self.section_id))
        self.para.clear()

    def heading(self, level: int, title: str) -> None:
        self.flush()
        canonical = _canonical(title)
        while self.stack and self.stack[-1][0] >= level:
            self.stack.pop()
        self.stack.append((level, canonical, title))
        named = next((c for _, c, _ in reversed(self.stack) if c), None)
        clean = lambda t: re.sub(r"[*_`{}]|\\[a-z]+", "", t).strip()  # noqa: E731
        self.section = named or "other"
        first = next((k for k, (_, c, _) in enumerate(self.stack) if c), 0)  # not the document title
        self.section_id = ", ".join(clean(t) for _, _, t in self.stack[first:])

    def set_section(self, section: str, section_id: str) -> None:
        self.flush()
        self.stack.clear()
        self.section, self.section_id = section, section_id

    def build(self) -> list[Unit]:
        if self.latex:
            self._latex()
        else:
            self._markdown()
        self.flush()
        return self.units

    def _markdown(self) -> None:
        lines, i = self.lines, 0
        if lines[:1] == ["---"]:  # pandoc YAML front matter: an `abstract:` block is the abstract
            i = 1
            while i < len(lines) and lines[i].strip() not in ("---", "..."):
                stripped = lines[i].strip()
                if re.match(r"^abstract\s*:", stripped, re.IGNORECASE):
                    self.set_section("abstract", "Abstract")
                    rest = stripped.split(":", 1)[1].strip(" |>")
                    if rest:
                        self.para.append((i + 1, rest))
                elif re.match(r"^[A-Za-z][\w-]*\s*:", lines[i]):
                    self.set_section("other", "Front matter")
                elif self.section == "abstract" and stripped:
                    self.para.append((i + 1, stripped))
                i += 1
            self.set_section("other", "Body")
            i += 1
        while i < len(lines):
            line, stripped = lines[i], lines[i].strip()
            if i in self.consumed:
                i += 1
                continue
            heading = MD_HEADING.match(line)
            bold = BOLD_HEADING.match(stripped)
            if heading:
                self.heading(len(heading.group(1)), heading.group(2))
            elif bold and _canonical(bold.group(1)):
                self.heading(2, bold.group(1))
            elif not self.para and stripped and len(stripped.split()) <= 5 and _canonical(stripped):
                self.heading(2, stripped)  # a bare "Methods" line in a plain-text export
            elif stripped.startswith("|"):
                self.flush()
                end = i
                while end < len(lines) and lines[end].strip().startswith("|"):
                    end += 1
                self._md_table(i, end)
                i = end
                continue
            elif not stripped:
                self.flush()
            else:
                self.para.append((i + 1, stripped))
            i += 1

    def _md_table(self, start: int, end: int) -> None:
        lines = self.lines
        caption, label, caption_index = "", f"the table at line {start + 1}", None
        before = [j for j in range(start - 1, max(-1, start - 4), -1)]
        after = [j for j in range(end, min(len(lines), end + 3))]
        for j in before + after:
            candidate = lines[j].strip().lstrip(":").strip()
            match = TABLE_CAPTION.match(candidate)
            if match:
                caption, label, caption_index = candidate, "Table " + match.group(1), j
                break
        table = Table(label=label, caption=caption, start_line=start + 1)
        if caption_index is not None:
            if caption_index < start:  # already read as a paragraph: make that paragraph the caption
                for unit in reversed(self.units):
                    if unit.kind == "prose" and len(unit.starts) == 1 and unit.starts[0][1] == caption_index + 1:
                        unit.section, unit.section_id, unit.kind, unit.table = "table", label, "caption", table
                        break
            else:
                self.consumed.add(caption_index)
                self.units.append(Unit(caption, [(0, caption_index + 1)], "table", label, "caption", table))
        rows = [(k + 1, lines[k]) for k in range(start, end) if not re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", lines[k])]
        for number, row in rows:
            self._row(table, _split_cells(row, latex=False), number)

    def _row(self, table: Table, cells: list[str], number: int) -> None:
        if not table.header:
            table.header = cells
        if not table.col_n:
            table.col_n = _column_n(cells)
        unit = Unit(" | ".join(cells), [(0, number)], "table", table.label, "row", table, cells)
        table.rows.append(unit)
        self.units.append(unit)

    def _latex(self) -> None:
        table: Optional[Table] = None
        rows: Optional[list[tuple[int, str]]] = None
        bare = False
        for i, line in enumerate(self.lines):
            number = i + 1
            if re.search(r"\\begin\{abstract\}", line):
                self.set_section("abstract", "Abstract")
                line = line.split("\\begin{abstract}", 1)[1]
            if re.search(r"\\end\{abstract\}", line):
                self.para.append((number, line.split("\\end{abstract}", 1)[0]))
                self.set_section("other", "Body")
                continue
            if re.search(r"\\begin\{thebibliography\}|\\bibliography\{|\\printbibliography", line):
                self.set_section("references", "References")
                continue
            heading = TEX_HEADING.search(line)
            if heading and table is None:
                self.heading(TEX_LEVEL[heading.group(1)], heading.group(2))
                continue
            if re.search(r"\\begin\{table\*?\}", line):
                self.flush()
                self.tex_tables += 1
                table, bare = Table(label=f"Table {self.tex_tables}", start_line=number), False
            if re.search(r"\\begin\{tabular", line):
                self.flush()
                if table is None:
                    table, bare = Table(label=f"the table at line {number}", start_line=number), True
                rows = []
                line = re.sub(r"^.*?\\begin\{tabular[x*]?\}(?:\{[^{}]*\})?(?:\{(?:[^{}]|\{[^{}]*\})*\})?", "", line)
            if table is not None:
                label = re.search(r"\\label\{([^}]*)\}", line)
                if label and rows is None:
                    table.ref_key = label.group(1)
                caption = re.search(r"\\caption\s*(?:\[[^\]]*\])?\s*\{(.*)", line)
                if caption and rows is None:
                    table.caption = caption.group(1).rstrip("} ")
                    self.units.append(Unit(table.caption, [(0, number)], "table", table.label, "caption", table))
                elif rows is not None:
                    content = line.split("\\end{tabular", 1)[0]
                    if content.strip():
                        rows.append((number, content))
                    if "\\end{tabular" in line:
                        self._latex_rows(table, rows)
                        rows = None
                        if bare:
                            table = None
                if table is not None and re.search(r"\\end\{table\*?\}", line):
                    table = None
                continue
            if not line.strip():
                self.flush()
            else:
                self.para.append((number, line.strip()))

    def _latex_rows(self, table: Table, rows: list[tuple[int, str]]) -> None:
        joined, starts = "", []
        for number, content in rows:
            starts.append((len(joined), number))
            joined += content + " "
        position = 0
        for chunk in re.split(r"\\\\(?:\s*\[[^\]]*\])?", joined):
            line = next((n for off, n in reversed(starts) if off <= position + len(chunk) - len(chunk.lstrip())),
                        starts[0][1])
            position += len(chunk) + 2
            if "&" in chunk and chunk.strip():
                self._row(table, _split_cells(chunk, latex=True), line)


def parse(path: Path) -> Document:
    raw = path.read_text(encoding="utf-8", errors="replace")
    latex = path.suffix.lower() in {".tex", ".ltx"} or bool(re.search(r"\\begin\{document\}|\\section\*?\{", raw))
    lines = [_normalise(l, latex) for l in _strip_comments(raw, latex)]
    units = _Builder(lines, latex).build()
    body = "\n".join(u.text for u in units if u.section not in UNCHECKED)
    return Document(units, latex, body)


ABBREVIATIONS = re.compile(r"(?:\bet al|\be\.g|\bi\.e|\bvs|\bFig|\bFigs|\bEq|\bNo|\bapprox|\bca|\bcf|\bRef|\bSupp|\bTab)\.$",
                           re.IGNORECASE)


def sentences(unit: Unit) -> list[tuple[int, str]]:
    """(offset, sentence) pairs; a table row or caption is one sentence."""
    if unit.kind != "prose":
        return [(0, unit.text)]
    out: list[tuple[int, str]] = []
    start = 0
    for m in re.finditer(r"(?<=[.!?])\s+(?=[A-Z(\[])", unit.text):
        candidate = unit.text[start:m.start()]
        if ABBREVIATIONS.search(candidate):
            continue
        out.append((start, candidate))
        start = m.end()
    out.append((start, unit.text[start:]))
    return out


def _excerpt(text: str, start: int, end: int, width: int = 50) -> str:
    lo, hi = max(0, start - width), min(len(text), end + width)
    return ("…" if lo else "") + text[lo:hi].strip() + ("…" if hi < len(text) else "")


QUOTE_WIDTH = 160


def _quote(text: str, start: int = 0, end: int = 0, width: int = QUOTE_WIDTH) -> tuple[str, Optional[tuple[int, int]]]:
    """The text as written, cut to about `width` characters around [start, end) at word boundaries and marked
    [...] where shortened, with the span's place in the result (the same rule as scan.py)."""
    text = re.sub(r"[\r\n\t]", " ", text)
    lead = len(text) - len(text.lstrip())
    body = text.strip()
    start, end = min(max(0, start - lead), len(body)), min(max(0, end - lead), len(body))
    end = min(max(end, start), start + width)
    if len(body) <= width:
        return body, (start, end) if end > start else None
    lo = max(0, start - (width - (end - start)) // 2)
    hi = min(len(body), max(lo + width, end))
    if hi == len(body):
        lo = max(0, min(lo, hi - width))
    if lo > 0:
        space = body.find(" ", lo, start + 1)
        lo = space + 1 if space >= 0 else lo
    if hi < len(body):
        space = body.rfind(" ", end, hi)
        hi = space if space > end else hi
    prefix, suffix = ("[...] " if lo > 0 else ""), (" [...]" if hi < len(body) else "")
    shift = len(prefix) - lo
    return prefix + body[lo:hi].strip() + suffix, ((start + shift, end + shift) if end > start else None)


def _place_name(unit: Unit) -> str:
    """What a reader calls the unit's place: its section, a table, or a table's row."""
    if unit.kind == "row" and unit.table is not None and unit.cells:
        label = re.sub(r"[*_`]", "", unit.cells[0]).strip()
        return f"{unit.table.label}, row “{label[:60]}”" if label else unit.table.label
    return unit.section_id


def _cell_offset(unit: Unit, j: int) -> int:
    """Where cell j starts in a row unit's text (its cells joined by ' | ')."""
    return sum(len(c) + 3 for c in unit.cells[:j])


def _placed(finding: Finding, unit: Unit, start: int, end: int) -> Finding:
    """The finding with its section and the unit's text quoted around [start, end)."""
    finding.section = _place_name(unit)
    finding.quote, finding.quote_span = _quote(unit.text, start, end)
    finding.message = finding.message[:1].upper() + finding.message[1:]
    return finding


def _decimals(literal: str) -> int:
    literal = literal.replace(",", "")
    return len(literal.split(".", 1)[1]) if "." in literal else 0


def _half_ulp(literal: str) -> float:
    return 0.5 * 10 ** -_decimals(literal)


CITATION = re.compile(r"\[\d+(?:\s*[-–,]\s*\d+)*\]|\\cite|\bet al\.?,? \(?(?:19|20)\d{2}|\((?:[A-Z][A-Za-z'-]+[^()]{0,40}?,? "
                      r"(?:19|20)\d{2}[a-z]?(?:; ?)?)+\)|\[@")


# --------------------------------------------------------------------------------------------------
# 1. Number ledger
# --------------------------------------------------------------------------------------------------

SAMPLE_NOUNS = {
    "participants": r"participants?", "patients": r"patients?", "subjects": r"subjects?",
    "individuals": r"individuals?", "people": r"people|persons", "respondents": r"respondents?",
    "volunteers": r"volunteers?", "donors": r"donors?", "cases": r"cases?", "controls": r"controls?",
    "probands": r"probands?", "families": r"famil(?:y|ies)", "trios": r"trios?", "samples": r"samples?",
    "specimens": r"specimens?", "genomes": r"genomes?", "exomes": r"exomes?", "children": r"child(?:ren)?",
    "adults": r"adults?", "infants": r"infants?", "women": r"wom[ae]n", "men": r"m[ae]n", "students": r"students?",
    "mice": r"mice|mouse", "rats": r"rats?", "animals": r"animals?", "studies": r"stud(?:y|ies)",
    "users": r"users?", "clinicians": r"clinicians?", "raters": r"raters?", "isolates": r"isolates?",
}
_NOUN_ALT = "|".join(f"(?P<{k}>{v})" for k, v in SAMPLE_NOUNS.items())
_STOP_ADJ = {"of", "and", "or", "the", "more", "fewer", "were", "was", "from", "with", "in", "to", "for", "per", "at",
             "on", "by", "had", "have", "than", "these", "those", "out", "a", "an", "each", "other", "same"}
COUNT_NOUN = re.compile(rf"(?<![\w.,%-])(?P<num>{INT})\s+(?P<adj>(?:[a-z][a-z-]+\s+){{0,2}})(?:{_NOUN_ALT})\b")
NOUN_N = re.compile(rf"\b(?:{_NOUN_ALT})\s*[(\[,]\s*[nN]\s*=\s*(?P<num>{INT})\b")
N_NOUN = re.compile(rf"\b[nN]\s*=\s*(?P<num>{INT})\s+(?:[a-z][a-z-]+\s+)?(?:{_NOUN_ALT})\b")
OVERALL_N = re.compile(rf"\b(?:all|total|overall|whole sample|entire (?:sample|cohort)|full cohort)\s*[(\[,]?\s*[nN]\s*=\s*"
                       rf"(?P<num>{INT})\b", re.IGNORECASE)
TOTAL_CONTEXT = re.compile(r"\b(?:total|all|overall|in all|enrol+ed|recruited|included|randomi[sz]ed|analy[sz]ed|"
                           r"completed|participated|took part|sequenced|genotyped|comprised|consisted|sample of|"
                           r"cohort of|study population|eligible|surveyed|interviewed|N\s*=)\b", re.IGNORECASE)

METRICS = {  # abbreviations are case-sensitive ("OR" is an odds ratio, "or" is not); names are not
    "AUROC": r"AUROC|AUC(?:-ROC)?|ROC[- ]AUC|(?i:area under the (?:receiver[- ]operating[- ]characteristic )?"
             r"(?:\(ROC\) )?curve)",
    "AUPRC": r"AUPRC|PR[- ]AUC|AUC[- ]PR|(?i:area under the precision[- ]recall curve)",
    "C-index": r"C[- ]index|(?i:concordance index)|C[- ]statistic",
    "balanced accuracy": r"(?i:balanced accuracy)",
    "accuracy": r"(?i:(?<!balanced )accuracy)",
    "sensitivity": r"(?i:sensitivity)",
    "specificity": r"(?i:specificity)",
    "PPV": r"PPV|(?i:positive predictive value)",
    "NPV": r"NPV|(?i:negative predictive value)",
    "precision": r"(?i:precision)",
    "recall": r"(?i:recall)",
    "F1": r"F1(?:[- ]score)?|(?i:F-score|F-measure)",
    "MCC": r"MCC|(?i:Matthews(?:'s)? correlation coefficient)",
    "R2": r"R2|R\^2|(?i:R-squared|coefficient of determination)",
    "heritability": r"(?i:SNP[- ]heritability|heritability)|h2",
    "odds ratio": r"(?i:odds ratio)|OR",
    "hazard ratio": r"(?i:hazard ratio)|HR",
    "relative risk": r"(?i:relative risk|risk ratio)|RR",
    "kappa": r"(?i:Cohen's kappa|kappa)|κ",
}
METRIC_RES = {key: re.compile(rf"(?:{pattern})(?![\w-])") for key, pattern in METRICS.items()}
_METRIC_ALT = "|".join(f"(?:{v})" for v in METRICS.values())
METRIC_AFTER = re.compile(rf"(?<![\w-])(?P<name>{_METRIC_ALT})(?![\w-])\s*(?:\([^()]{{0,30}}\)\s*)?"
                          rf"(?i:of|=|:|was|were|is|reached|achieved|of up to)?\s*(?i:approximately|about|~|≈)?\s*"
                          rf"(?P<num>-?{NUM})\s*(?P<pct>%)?(?![\d.])")
METRIC_BEFORE = re.compile(rf"(?<![\w.])(?P<num>{NUM})\s*(?P<pct>%)\s+(?P<name>(?i:accuracy|sensitivity|specificity|"
                           rf"precision|recall))\b")
METRIC_PAIR = re.compile(rf"(?<![\w-])(?P<a>(?i:sensitivity|specificity|precision|recall|accuracy)|PPV|NPV)\s+"
                         rf"(?i:and|/)\s+(?P<b>(?i:sensitivity|specificity|precision|recall|accuracy)|PPV|NPV)\s*"
                         rf"(?i:of|were|=|:)?\s*(?P<v1>{NUM})\s*(?P<p1>%)?\s*(?i:and|/)\s*(?P<v2>{NUM})\s*(?P<p2>%)?")
BARE_NUMBER = re.compile(rf"(?<![\w.])(?P<num>{INT}(?:\.\d+)?|\.\d+)\s*(?P<pct>%)?")


@dataclass
class LedgerMention:
    key: str
    kind: str  # sample | metric
    literal: str
    percent: bool
    unit: Unit
    offset: int
    total_like: bool
    cited: bool

    @property
    def value(self) -> float:
        return float(self.literal.replace(",", ""))

    @property
    def line(self) -> int:
        return self.unit.line_at(self.offset)


def _same_value(a_lit: str, a_pct: bool, b_lit: str, b_pct: bool) -> bool:
    va, vb = float(a_lit.replace(",", "")), float(b_lit.replace(",", ""))
    ha, hb = _half_ulp(a_lit), _half_ulp(b_lit)
    if a_pct and not b_pct and vb <= 1.0:
        va, ha = va / 100, ha / 100
    elif b_pct and not a_pct and va <= 1.0:
        vb, hb = vb / 100, hb / 100
    return abs(va - vb) <= max(ha, hb) + 1e-9


def _looks_like_year(sentence: str, start: int, literal: str) -> bool:
    return (re.fullmatch(r"(?:19|20)\d{2}", literal) is not None
            and re.search(r"(?:\bin|since|from|during|by|until|of)\s*$", sentence[max(0, start - 8):start],
                          re.IGNORECASE) is not None)


def _sample_key(match: re.Match[str]) -> Optional[str]:
    return next((k for k in SAMPLE_NOUNS if match.groupdict().get(k)), None)


def ledger_mentions(doc: Document) -> tuple[list[LedgerMention], dict[str, int]]:
    mentions: list[LedgerMention] = []
    skipped = {"cited": 0, "introduction": 0}
    overall: list[LedgerMention] = []
    for unit in doc.units:
        if unit.section in UNCHECKED:
            continue
        for s_off, sent in sentences(unit):
            cited = bool(CITATION.search(sent))
            total_like = bool(TOTAL_CONTEXT.search(sent)) or unit.kind in ("row", "caption")
            found: list[LedgerMention] = []
            taken: list[tuple[int, int]] = []
            for rx, explicit in ((NOUN_N, True), (N_NOUN, True), (COUNT_NOUN, False)):
                for m in rx.finditer(sent):
                    span = m.span("num")
                    if any(a <= span[0] < b for a, b in taken):
                        continue
                    if not explicit and any(w in _STOP_ADJ for w in m.group("adj").split()):
                        continue
                    key = _sample_key(m)
                    if key is None or _looks_like_year(sent, m.start("num"), m.group("num")):
                        continue
                    taken.append(span)
                    found.append(LedgerMention(key, "sample", m.group("num"), False, unit, s_off + span[0],
                                               total_like or explicit, cited))
            for m in OVERALL_N.finditer(sent):
                if not any(a <= m.start("num") < b for a, b in taken):
                    overall.append(LedgerMention("overall n", "sample", m.group("num"), False, unit,
                                                 s_off + m.start("num"), True, cited))
            pair_spans: list[tuple[int, int]] = []
            for m in METRIC_PAIR.finditer(sent):
                pair_spans.append(m.span())
                for name, value, pct in ((m.group("a"), m.group("v1"), m.group("p1")),
                                         (m.group("b"), m.group("v2"), m.group("p2") or m.group("p1"))):
                    key = _metric_key(name)
                    if key:
                        found.append(LedgerMention(key, "metric", value, bool(pct), unit, s_off + m.start(), False, cited))
            for rx in (METRIC_AFTER, METRIC_BEFORE):
                for m in rx.finditer(sent):
                    if any(a <= m.start() < b for a, b in pair_spans):
                        continue
                    key = _metric_key(m.group("name"))
                    if key is None:
                        continue
                    found.append(LedgerMention(key, "metric", m.group("num"), bool(m.group("pct")), unit,
                                               s_off + m.start("num"), False, cited))
            for mention in found:
                if mention.cited:
                    skipped["cited"] += 1
                elif unit.section == "introduction":
                    skipped["introduction"] += 1
                else:
                    mentions.append(mention)
    # "All (n = 64)" in a table header counts towards the paper's main sample noun.
    sample_keys = [m.key for m in mentions if m.kind == "sample" and m.unit.section in ("abstract", "methods")]
    main_key = max(set(sample_keys), key=sample_keys.count) if sample_keys else None
    for mention in overall:
        if mention.cited or mention.unit.section == "introduction":
            continue
        mention.key = main_key or "overall n"
        mentions.append(mention)
    return mentions, skipped


def _metric_key(text: str) -> Optional[str]:
    return next((key for key, rx in METRIC_RES.items() if rx.match(text.strip())), None)


def _number_index(doc: Document) -> dict[str, list[tuple[str, bool]]]:
    index: dict[str, list[tuple[str, bool]]] = {}
    for unit in doc.units:
        if unit.section in UNCHECKED:
            continue
        for m in BARE_NUMBER.finditer(unit.text):
            index.setdefault(unit.section_id, []).append((m.group("num"), bool(m.group("pct"))))
    return index


def _appears_in(index: dict[str, list[tuple[str, bool]]], sections: set[str], literal: str, pct: bool) -> bool:
    return any(_same_value(literal, pct, lit, p) for sid in sections for lit, p in index.get(sid, []))


def _where(m: LedgerMention) -> str:
    return f"{m.unit.section_id} (line {m.line})"


def check_ledger(doc: Document, summary: CheckSummary) -> tuple[list[Finding], dict[str, list[Mention]]]:
    mentions, skipped = ledger_mentions(doc)
    index = _number_index(doc)
    all_sections = {u.section_id for u in doc.units if u.section not in UNCHECKED}
    by_key: dict[str, list[LedgerMention]] = {}
    for m in mentions:
        by_key.setdefault(m.key, []).append(m)
    findings: list[Finding] = []
    for key, group in sorted(by_key.items()):
        sections = {m.unit.section_id for m in group}
        if len(sections) < 2:
            continue
        summary.assessed += 1
        reported: set[tuple[str, str]] = set()
        problems: list[str] = []
        anchor: Optional[LedgerMention] = None
        # Rule 1: within the sample-size statements that read as totals, a section whose values share
        # nothing with any other section, and whose values occur nowhere else as a number.
        if group[0].kind == "sample":
            totals = [m for m in group if m.total_like]
            per_section: dict[str, list[LedgerMention]] = {}
            for m in totals:
                per_section.setdefault(m.unit.section_id, []).append(m)
            if len(per_section) >= 2:
                for sid, ms in per_section.items():
                    if ms[0].unit.section not in TOTAL_SECTIONS:
                        continue  # a Results or Discussion count is usually a subgroup; it only counts as "other"
                    others = [o for o in totals if o.unit.section_id != sid]
                    if any(_same_value(m.literal, m.percent, o.literal, o.percent) for m in ms for o in others):
                        continue
                    if any(_appears_in(index, all_sections - {sid}, m.literal, m.percent) for m in ms):
                        continue
                    for m in ms:
                        reported.add((m.unit.section_id, m.literal))
                    anchor = anchor or ms[0]
                    problems.append(f"{sid} states {', '.join(sorted({m.literal for m in ms}))}")
        # Rule 2: a value stated in the Abstract or Conclusions that the body never states for this quantity.
        body = [m for m in group if m.unit.section not in HEADLINE]
        if body:
            body_sections = {sid for sid in all_sections
                             if not any(u.section_id == sid and u.section in HEADLINE for u in doc.units)}
            for m in group:
                if m.unit.section not in HEADLINE or (m.unit.section_id, m.literal) in reported:
                    continue
                if any(_same_value(m.literal, m.percent, b.literal, b.percent) for b in body):
                    continue
                if _appears_in(index, body_sections, m.literal, m.percent):
                    continue
                reported.add((m.unit.section_id, m.literal))
                anchor = anchor or m
                problems.append(f"{m.unit.section_id} states {m.literal}{'%' if m.percent else ''}, which the body "
                                f"never states")
        if not problems:
            summary.consistent += 1
            continue
        summary.candidates += 1
        values: dict[str, list[str]] = {}
        for m in group:
            values.setdefault(m.literal + ("%" if m.percent else ""), []).append(_where(m))
        stated = [f"{v} in {' and '.join(dict.fromkeys(places))}" for v, places in values.items()]
        listing = stated[0] if len(stated) == 1 else ", ".join(stated[:-1]) + " and " + stated[-1]
        assert anchor is not None
        findings.append(_placed(Finding(
            check="ledger", severity=Severity.major, line=anchor.line,
            excerpt=_excerpt(anchor.unit.text, anchor.offset, anchor.offset + len(anchor.literal)),
            message=f"'{key}' is stated with different values: {'; '.join(problems)}.",
            arithmetic=f"'{key}' is stated as {listing}.",
            suggestion="Check each value against the data. If both are right (a subset, an exclusion, another "
                       "dataset), say which population or analysis each describes where it is stated."),
            anchor.unit, anchor.offset, anchor.offset + len(anchor.literal)))
    for reason, count in skipped.items():
        if count:
            summary.not_assessed.append(Skipped(reason=f"{count} {'statement was' if count == 1 else 'statements were'} "
                                                       f"skipped because {'it reports' if count == 1 else 'they report'} "
                                                       f"{'cited prior work' if reason == 'cited' else 'background in the Introduction'}"))
    ledger = {key: [Mention(key=key, value=m.literal + ("%" if m.percent else ""), line=m.line,
                            section=m.unit.section_id, excerpt=_excerpt(m.unit.text, m.offset, m.offset + len(m.literal), 30))
                    for m in group] for key, group in sorted(by_key.items())}
    return findings, ledger


# --------------------------------------------------------------------------------------------------
# 2. GRIM and GRIMMER
# --------------------------------------------------------------------------------------------------

INTEGER_CONTEXT = re.compile(r"likert|\b\d+[- ]point\b|\bratings?\b|\brated\b|\bnumber of\b|\bcounts?\b|\b(?:visits|episodes|"
                             r"admissions|errors|relapses|pregnancies|siblings|teeth|cigarettes|drinks)\b|\bitems?\b|"
                             r"\b(?:sum|total) score|\bscored? (?:on|from) (?:a|the)?\s*\d", re.IGNORECASE)
NOT_INTEGER = re.compile(r"\bage[ds]?\b|\byears?\b|\bBMI\b|\bweight\b|\bheight\b|\blength\b|\bconcentration|\bkg\b|"
                         r"\bmg\b|\bml\b|\bmmol|\bseconds?\b|\bminutes?\b|\bhours?\b|\bdays?\b", re.IGNORECASE)
ITEMS = re.compile(r"\b(\d+)[- ]item\b", re.IGNORECASE)
SD_LABEL = re.compile(r"\bSD\b|\bs\.d\.|standard deviation", re.IGNORECASE)
SE_LABEL = re.compile(r"\bSEM?\b|\bs\.e\.(?:m\.)?|standard error|\bCI\b|confidence interval", re.IGNORECASE)
MEAN_APA = re.compile(rf"(?<![\w])M\s*=\s*(?P<mean>-?{NUM})(?:\s*[,;(]\s*SD\s*[=:]\s*(?P<sd>{NUM}))?")
MEAN_WORD = re.compile(rf"\bmean\b(?:\s*(?:\(\s*SD\s*\)|±\s*SD))?[^0-9;±]{{0,60}}?(?<![\w.])(?P<mean>-?{NUM})"
                       rf"(?:\s*\(\s*(?:SD\s*[=:]?\s*)?(?P<sd>{NUM})\s*\)|\s*±\s*(?P<sd2>{NUM})|\s*[,;]\s*SD\s*[=:]?\s*(?P<sd3>{NUM}))?",
                       re.IGNORECASE)
PLUS_MINUS = re.compile(rf"(?<![\w.])(?P<mean>-?{NUM})\s*±\s*(?P<sd>{NUM})")
N_IN_TEXT = re.compile(rf"\b[nN]\s*=\s*(?P<num>{INT})\b")
PERCENT_OF_N = re.compile(rf"(?<![\w.])(?P<pct>{NUM})\s?%\s+of\s+(?:the\s+|all\s+)?(?P<num>{INT})\s+"
                          rf"(?:[a-z][a-z-]+\s+){{0,2}}(?:{_NOUN_ALT})\b")
CELL_MEAN_SD = re.compile(rf"^\s*(?P<mean>-?{NUM})\s*(?:\(\s*(?P<sd>{NUM})\s*\)|±\s*(?P<sd2>{NUM}))\s*$")
CELL_COUNT_PCT = re.compile(rf"^\s*(?P<k>{INT})\s*\(\s*(?P<pct>{NUM})\s*%?\s*\)\s*$")


def grim_sums(mean: str, n: int) -> list[int]:
    """Whole-number sums S with S/n rounding to the reported mean under any common rounding rule."""
    m, h = float(mean), _half_ulp(mean)
    lo, hi = math.floor((m - h) * n) - 1, math.ceil((m + h) * n) + 1
    return [s for s in range(lo, hi + 1) if abs(s / n - m) <= h + 1e-9]


def grim_informative(mean: str, n: int) -> bool:
    return n < 10 ** _decimals(mean)


def grimmer_consistent(mean: str, sd: str, n: int) -> Optional[bool]:
    """False when no whole-number data of size n give this mean and SD (sample or population SD).

    The sum of squares Q of whole numbers is a whole number with the parity of their sum S. For each sum S
    that passes GRIM, the reported SD (allowing for its rounding) bounds Q; no admissible Q means the pair
    is impossible. None when the bound is too wide to exclude anything.
    """
    sums = grim_sums(mean, n)
    if not sums or n < 2:
        return None if n < 2 else False
    s, h = float(sd), _half_ulp(sd)
    s_lo, s_hi = max(0.0, s - h), s + h
    if (n - 1) * (s_hi ** 2 - s_lo ** 2) >= 2:
        return None
    for total in sums:
        for divisor in (n - 1, n):  # sample SD, then population SD
            q_lo = divisor * s_lo ** 2 + total * total / n
            q_hi = divisor * s_hi ** 2 + total * total / n
            for q in range(math.ceil(q_lo - 1e-9), math.floor(q_hi + 1e-9) + 1):
                if (q - total) % 2 == 0:
                    return True
    return False


def _round_display(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}"


def _grim_arithmetic(mean: str, n: int, items: int) -> str:
    d, total_n = _decimals(mean), n * items
    product = float(mean) * total_n
    lo, hi = math.floor(product), math.ceil(product)
    if lo == hi:
        hi = lo + 1
    unit = f"{n} × {items} items = {total_n}" if items > 1 else f"n = {n}"
    return (f"{mean} × {total_n} = {product:.{max(d, 2)}f} ({unit}). Whole-number sums {lo} and {hi} give means "
            f"{lo / total_n:.{d + 3}f} and {hi / total_n:.{d + 3}f}, which round to {_round_display(lo / total_n, d)} "
            f"and {_round_display(hi / total_n, d)}, not {mean}.")


def _nearest_n(sentence: str, position: int, unit: Unit, col_n: Optional[int]) -> Optional[int]:
    if col_n:
        return col_n
    candidates = [(abs(m.start() - position), int(m.group("num").replace(",", ""))) for m in N_IN_TEXT.finditer(sentence)]
    candidates += [(abs(m.start() - position), int(m.group("num").replace(",", "")))
                   for m in COUNT_NOUN.finditer(sentence)
                   if not any(w in _STOP_ADJ for w in m.group("adj").split())]
    if not candidates:
        return None
    return min(candidates)[1]


def check_grim(doc: Document, assume_integer: bool, grim: CheckSummary, grimmer: CheckSummary,
               percent: CheckSummary) -> list[Finding]:
    findings: list[Finding] = []
    for unit in doc.units:
        if unit.section in UNCHECKED:
            continue
        if unit.kind == "row" and unit.table is not None:
            findings += _grim_table_row(unit, assume_integer, grim, grimmer, percent)
            continue
        if unit.kind == "row":
            continue
        for s_off, sent in sentences(unit):
            findings += _grim_sentence(unit, s_off, sent, assume_integer, grim, grimmer)
            for m in PERCENT_OF_N.finditer(sent):
                findings += _percent_of_n(unit, s_off + m.start(), sent, m, percent)
    return findings


def _mean_candidates(sentence: str) -> list[tuple[int, str, Optional[str]]]:
    out: dict[int, tuple[int, str, Optional[str]]] = {}
    sd_ok = bool(SD_LABEL.search(sentence)) and not SE_LABEL.search(sentence)
    for m in MEAN_APA.finditer(sentence):
        out[m.start("mean")] = (m.start("mean"), m.group("mean"), m.group("sd"))
    for m in MEAN_WORD.finditer(sentence):
        sd = m.group("sd3") or ((m.group("sd") or m.group("sd2")) if sd_ok else None)
        out.setdefault(m.start("mean"), (m.start("mean"), m.group("mean"), sd))
    if re.search(r"\bmean\b|\bM\b", sentence):
        for m in PLUS_MINUS.finditer(sentence):
            out.setdefault(m.start("mean"), (m.start("mean"), m.group("mean"), m.group("sd") if sd_ok else None))
    return sorted(out.values())


def _grim_one(unit: Unit, offset: int, text: str, position: int, mean: str, sd: Optional[str], n: int, items: int,
              grim: CheckSummary, grimmer: CheckSummary, where: str = "") -> list[Finding]:
    line = unit.line_at(offset)
    excerpt = _excerpt(text, position, position + len(mean))
    total_n = n * items
    if not grim_informative(mean, total_n):
        grim.not_informative += 1
        return []
    grim.assessed += 1
    if not grim_sums(mean, total_n):
        grim.candidates += 1
        assumption = (f"assuming each of the {items} items is a whole number" if items > 1
                      else "assuming one whole-number value per participant")
        return [_placed(Finding(check="grim", severity=Severity.major, line=line, excerpt=excerpt,
                                message=f"Mean {mean}{where} with n = {n} is not possible for whole-number data "
                                        f"({assumption}).",
                                arithmetic=_grim_arithmetic(mean, n, items),
                                suggestion="Check the mean and n against the data: the n behind this mean may differ "
                                           "(missing responses, exclusions), the data may not be whole numbers, or a "
                                           "digit may be mistyped."), unit, offset, offset + len(mean))]
    grim.consistent += 1
    if sd is None:
        return []
    if items > 1:
        grimmer.not_assessed.append(Skipped(line=line, excerpt=excerpt, reason="multi-item scale: GRIMMER needs "
                                                                               "single whole-number values"))
        return []
    verdict = grimmer_consistent(mean, sd, n)
    if verdict is None:
        grimmer.not_informative += 1
        return []
    grimmer.assessed += 1
    if verdict:
        grimmer.consistent += 1
        return []
    grimmer.candidates += 1
    s, h = float(sd), _half_ulp(sd)
    sums = grim_sums(mean, n)
    ranges = []
    for total in sums:
        q_lo = (n - 1) * max(0.0, s - h) ** 2 + total * total / n
        q_hi = (n - 1) * (s + h) ** 2 + total * total / n
        ranges.append(f"sum {total}: sum of squares between {q_lo:.3f} and {q_hi:.3f}")
    return [_placed(Finding(check="grimmer", severity=Severity.major, line=line, excerpt=excerpt,
                    message=f"SD {sd} with mean {mean}{where} and n = {n} is not possible for whole-number data.",
                    arithmetic=f"SD {sd} (±{h:g} rounding) implies, for each sum that fits the mean, "
                               + "; ".join(ranges) + ". The sum of squares of whole numbers is a whole number with "
                               "the same parity as their sum; none fits (sample or population SD).",
                    suggestion="Check the SD, the mean and n against the data, and whether the dispersion is an SD "
                               "and not a standard error."), unit, offset, offset + len(mean))]


def _grim_sentence(unit: Unit, s_off: int, sent: str, assume_integer: bool, grim: CheckSummary,
                   grimmer: CheckSummary) -> list[Finding]:
    means = _mean_candidates(sent)
    if not means:
        return []
    if not (assume_integer or INTEGER_CONTEXT.search(sent)):
        return []
    items_m = ITEMS.search(sent)
    items = int(items_m.group(1)) if items_m else 1
    out: list[Finding] = []
    for position, mean, sd in means:
        # "mean age 41.3 years" in a sentence about ratings is not a rating: judge each mean by its own words
        if not assume_integer and NOT_INTEGER.search(sent[max(0, position - 30):position + len(mean) + 12]):
            continue
        n = _nearest_n(sent, position, unit, None)
        if n is None:
            grim.not_assessed.append(Skipped(line=unit.line_at(s_off + position),
                                             excerpt=_excerpt(sent, position, position + len(mean)),
                                             reason="mean of whole-number data with no n in the sentence"))
            continue
        out += _grim_one(unit, s_off + position, sent, position, mean, sd, n, items, grim, grimmer)
    return out


def _percent_of_n(unit: Unit, offset: int, sent: str, m: re.Match[str], percent: CheckSummary) -> list[Finding]:
    pct, n = m.group("pct"), int(m.group("num").replace(",", ""))
    d = _decimals(pct)
    if n == 0 or 100 / n <= 10 ** -d:
        percent.not_informative += 1
        return []
    percent.assessed += 1
    h = _half_ulp(pct)
    target = float(pct) * n / 100
    ks = [k for k in range(max(0, math.floor(target) - 1), min(n, math.ceil(target) + 1) + 1)
          if abs(100 * k / n - float(pct)) <= h + 1e-9]
    if ks:
        percent.consistent += 1
        return []
    percent.candidates += 1
    lo, hi = math.floor(target), math.ceil(target) if math.ceil(target) != math.floor(target) else math.floor(target) + 1
    return [_placed(Finding(check="percent-of-n", severity=Severity.major, line=unit.line_at(offset),
                            excerpt=_excerpt(sent, m.start(), m.end()),
                            message=f"{pct}% of {n} is not a whole count.",
                            arithmetic=f"{pct}% × {n} = {target:.3f}; {lo}/{n} = {100 * lo / n:.{d + 2}f}% and "
                                       f"{hi}/{n} = {100 * hi / n:.{d + 2}f}%, neither of which rounds to {pct}%.",
                            suggestion="Check the percentage and its denominator."),
                    unit, offset, offset + m.end() - m.start())]


def _grim_table_row(unit: Unit, assume_integer: bool, grim: CheckSummary, grimmer: CheckSummary,
                    percent: CheckSummary) -> list[Finding]:
    table = unit.table
    assert table is not None
    if not unit.cells or unit.cells is table.header:
        return []
    label = unit.cells[0]
    context = f"{label} {table.caption}"
    out: list[Finding] = []
    count_pct = bool(re.search(r"\bn\s*\(\s*%\s*\)|\bno\.\s*\(\s*%\s*\)|\(%\)", context, re.IGNORECASE))
    mean_sd = bool(re.search(r"mean\s*(?:\(\s*SD\s*\)|±\s*SD)|\bM\s*\(\s*SD\s*\)", context, re.IGNORECASE))
    integer = assume_integer or (INTEGER_CONTEXT.search(label) and not NOT_INTEGER.search(label))
    for j, cell in enumerate(unit.cells[1:], start=1):
        n = table.col_n.get(j)
        cm = CELL_COUNT_PCT.match(cell)
        if cm and (count_pct or "%" in cell):
            if n is None:
                percent.not_assessed.append(Skipped(line=unit.line_at(0), excerpt=f"{label}: {cell}",
                                                    reason="count (%) cell with no column n"))
                continue
            k, pct = int(cm.group("k").replace(",", "")), cm.group("pct")
            percent.assessed += 1
            actual = 100 * k / n
            if k <= n and abs(actual - float(pct)) <= _half_ulp(pct) + 1e-9:
                percent.consistent += 1
                continue
            percent.candidates += 1
            header = table.header[j] if j < len(table.header) else f"column {j + 1}"
            at = _cell_offset(unit, j)
            out.append(_placed(Finding(check="table-percent", severity=Severity.major, line=unit.line_at(0),
                                       excerpt=f"{label}: {cell}",
                                       message=f"{table.label}, row '{label}', column '{header}': {k} of {n} is "
                                               f"{actual:.{max(1, _decimals(pct))}f}%, not {pct}%.",
                                       arithmetic=f"100 × {k} / {n} = {actual:.3f}.",
                                       suggestion="Recompute from the count and the column n, or correct the n in "
                                                  "the header."), unit, at, at + len(cell)))
            continue
        mm = CELL_MEAN_SD.match(cell)
        if mm and mean_sd and integer:
            if n is None:
                grim.not_assessed.append(Skipped(line=unit.line_at(0), excerpt=f"{label}: {cell}",
                                                 reason="mean (SD) cell with no column n"))
                continue
            items_m = ITEMS.search(context)
            out += _grim_one(unit, _cell_offset(unit, j), cell, 0, mm.group("mean"), mm.group("sd") or mm.group("sd2"), n,
                             int(items_m.group(1)) if items_m else 1, grim, grimmer,
                             where=f" ({table.label}, '{label}')")
    return out


# --------------------------------------------------------------------------------------------------
# Table arithmetic: column totals, and SEM against SD / sqrt(n)
# --------------------------------------------------------------------------------------------------

TOTAL_ROW = re.compile(r"^\W*(?:total|sum|overall|all)\b", re.IGNORECASE)
CELL_NUMBER = re.compile(rf"^\s*(?P<num>{INT}(?:\.\d+)?)\s*(?P<pct>%)?\s*(?:[a-z][a-z ]{{0,24}})?$", re.IGNORECASE)
EMPTY_CELL = re.compile(r"^\s*(?:[-–—]{1,2}|n/?a|\.|)\s*$", re.IGNORECASE)
NOT_A_SUM = re.compile(r"mean|median|average|\bavg\b|\bsd\b|\bsem?\b|ratio|rate|%|percent|proportion|fraction|score|"
                       r"p[- ]?value|\bci\b|±|range|\bmin|\bmax|time|age\b|accuracy|recall|precision|auc|\bf1\b|"
                       r"\br2\b|÷|fold|ram|cpu|memory", re.IGNORECASE)
TOTAL_CUE = re.compile(r"\b(?:total|in all|altogether|overall|combined|together|across|sum|holds?|contains?|"
                       r"compris\w+)\b", re.IGNORECASE)
N_HEADER = re.compile(r"^\s*(?:n|no\. of runs|number of (?:runs|samples|replicates))\b(?!\s*\(\s*%)", re.IGNORECASE)
SEM_HEADER = re.compile(r"\bSEM?\b|standard error", re.IGNORECASE)
SD_HEADER = re.compile(r"\bSD\b|standard deviation", re.IGNORECASE)
PM_CELL = re.compile(rf"^\s*-?{INT}(?:\.\d+)?\s*±\s*(?P<num>{INT}(?:\.\d+)?)\s*$")


def _cell_value(cell: str) -> Optional[str]:
    m = CELL_NUMBER.match(cell)
    return m.group("num") if m else None


def _noun_forms(header: str) -> set[str]:
    words = re.findall(r"[A-Za-z]{3,}", header)
    if not words:
        return set()
    w = words[-1].lower()
    forms = {w, w + "s", w[:-1] if w.endswith("s") else w}
    if w.endswith("ies"):
        forms.add(w[:-3] + "y")
    if w.endswith("y"):
        forms.add(w[:-1] + "ies")
    return forms


def _column_sum(j: int, rows: list[Unit]) -> tuple[list[str], Optional[str]]:
    """The numbers in column j of the data rows, or why the column cannot be added up."""
    literals: list[str] = []
    for row in rows:
        cell = row.cells[j] if j < len(row.cells) else ""
        if EMPTY_CELL.match(cell):
            continue
        literal = _cell_value(cell)
        if literal is None:
            return literals, f"cell '{cell}' (row '{row.cells[0]}') is not a plain number"
        literals.append(literal)
    return literals, None if len(literals) >= 2 else "fewer than two numbers to add"


def check_tables(doc: Document, totals: CheckSummary, sem: CheckSummary) -> list[Finding]:
    findings: list[Finding] = []
    tables = {id(u.table): u.table for u in doc.units if u.table is not None and u.kind == "row"}
    for table in tables.values():
        if table is None or len(table.rows) < 3 or any(u.section in UNCHECKED for u in table.rows[:1]):
            continue
        header = table.header
        body = table.rows[1:]
        total_at = next((k for k, row in enumerate(body) if row.cells and TOTAL_ROW.match(row.cells[0])), None)
        data = body[:total_at] if total_at is not None else body
        findings += _table_totals(doc, table, header, data, body[total_at] if total_at is not None else None, totals)
        findings += _table_sem(table, header, data, sem)
    return findings


def _text_totals(doc: Document, table: Table, forms: set[str]) -> list[tuple[Unit, int, str]]:
    """(unit, offset, number) for each sentence that cites the table and states a total of this column's noun."""
    out: list[tuple[Unit, int, str]] = []
    if not forms:
        return out
    noun = re.compile(rf"(?<![\w.,])(?P<num>{INT})\s+(?:[a-z-]+\s+){{0,2}}(?:{'|'.join(sorted(forms))})\b")
    for unit in doc.units:
        if unit.kind != "prose" or unit.section in UNCHECKED:
            continue
        cites = (table.ref_key and f"\\ref{{{table.ref_key}}}" in unit.text) or (
            table.label.startswith("Table") and re.search(rf"\b{re.escape(table.label)}\b", unit.text))
        if not cites:
            continue
        for s_off, sent in sentences(unit):
            if TOTAL_CUE.search(sent):
                out += [(unit, s_off + m.start(), m.group("num")) for m in noun.finditer(sent)]
    return out


def _table_totals(doc: Document, table: Table, header: list[str], data: list[Unit], total_row: Optional[Unit],
                  summary: CheckSummary) -> list[Finding]:
    """A column's total, in a total row or in a sentence that cites the table, against the sum of its cells."""
    out: list[Finding] = []
    for j in range(1, len(header)):
        name = header[j]
        stated = _cell_value(total_row.cells[j]) if total_row is not None and j < len(total_row.cells) else None
        texts = [] if NOT_A_SUM.search(name) else _text_totals(doc, table, _noun_forms(name))
        if stated is None and not texts:
            continue
        where_line = total_row.line_at(0) if stated is not None else texts[0][0].line_at(texts[0][1])
        literals, reason = _column_sum(j, data)
        if NOT_A_SUM.search(name) or reason:
            summary.not_assessed.append(Skipped(line=where_line, excerpt=name, reason=f"{table.label}, column "
                                                f"'{name}': {reason or 'not a column of counts'}"))
            continue
        column = sum(float(v.replace(",", "")) for v in literals)
        rounding = lambda v: _half_ulp(v) if "." in v else 0.0  # noqa: E731  (whole-number cells are exact counts)
        tolerance = sum(rounding(v) for v in literals)
        place = f"{table.label} ({table.ref_key})" if table.ref_key else table.label
        claims = [(stated, f"the total row says {total_row.cells[j]} (line {total_row.line_at(0)})",
                   total_row.line_at(0), total_row, _cell_offset(total_row, j), len(total_row.cells[j]))
                  ] if stated is not None else []
        claims += [(number, f"the text says {number} (line {unit.line_at(offset)})", unit.line_at(offset), unit, offset,
                    len(number)) for unit, offset, number in texts]
        wrong = [c for c in claims if abs(column - float(c[0].replace(",", ""))) > tolerance + rounding(c[0]) + 1e-9]
        summary.assessed += 1
        if not wrong:
            summary.consistent += 1
            continue
        summary.candidates += 1
        in_row = stated is not None and wrong[0][2] == total_row.line_at(0)
        shown = f"{column:.{max(_decimals(v) for v in literals)}f}"
        out.append(_placed(Finding(check="table-total", severity=Severity.major if in_row else Severity.minor,
                                   line=wrong[0][2], excerpt=f"{place}: {name}",
                                   message=f"{place}, column '{name}': the cells add up to {shown}, but "
                                           + "; ".join(c[1] for c in wrong) + ".",
                                   arithmetic=" + ".join(literals) + f" = {shown}"
                                              + (f" (± {tolerance:g} from the cells' rounding)." if tolerance >= 0.05
                                                 else "."),
                                   suggestion="Recount the column, or say what the total covers if it includes items "
                                              "the table leaves out."),
                           wrong[0][3], wrong[0][4], wrong[0][4] + wrong[0][5]))
    return out


def _table_sem(table: Table, header: list[str], data: list[Unit], summary: CheckSummary) -> list[Finding]:
    n_col = next((j for j, h in enumerate(header) if N_HEADER.match(h)), None)
    sem_col = next((j for j, h in enumerate(header) if SEM_HEADER.search(h)), None)
    sd_col = next((j for j, h in enumerate(header) if SD_HEADER.search(h) and not SEM_HEADER.search(h)), None)
    if n_col is None or sem_col is None or sd_col is None:
        return []
    out: list[Finding] = []
    for row in data:
        cells = row.cells
        if max(n_col, sem_col, sd_col) >= len(cells):
            continue
        n_lit = _cell_value(cells[n_col])
        sem_m = PM_CELL.match(cells[sem_col])
        sem_lit = sem_m.group("num") if sem_m else _cell_value(cells[sem_col])
        sd_m = PM_CELL.match(cells[sd_col])
        sd_lit = sd_m.group("num") if sd_m else _cell_value(cells[sd_col])
        if not (n_lit and sem_lit and sd_lit):
            if any(not EMPTY_CELL.match(cells[k]) for k in (n_col, sem_col, sd_col)):
                summary.not_assessed.append(Skipped(line=row.line_at(0), excerpt=f"{cells[0]}",
                                                    reason=f"{table.label}: n, SEM or SD is not a plain number"))
            continue
        n = int(float(n_lit.replace(",", "")))
        if n < 2:
            continue
        sd, h_sd = float(sd_lit.replace(",", "")), _half_ulp(sd_lit)
        se, h_se = float(sem_lit.replace(",", "")), _half_ulp(sem_lit)
        lo, hi = max(0.0, sd - h_sd) / math.sqrt(n), (sd + h_sd) / math.sqrt(n)
        summary.assessed += 1
        if _overlaps((lo, hi), (se - h_se, se + h_se)):
            summary.consistent += 1
            continue
        summary.candidates += 1
        at = _cell_offset(row, sem_col)
        out.append(_placed(Finding(check="sem-sd", severity=Severity.major, line=row.line_at(0), excerpt=f"{cells[0]}",
                           message=f"{table.label}, row '{cells[0]}': SEM {sem_lit} does not match SD {sd_lit} and "
                                   f"n = {n}.",
                           arithmetic=f"SD / √n = {sd_lit} / √{n} = {sd / math.sqrt(n):.{_decimals(sem_lit) + 2}f} "
                                      f"(between {lo:.{_decimals(sem_lit) + 2}f} and {hi:.{_decimals(sem_lit) + 2}f} "
                                      f"with the SD's rounding), not {sem_lit}.",
                           suggestion="Recompute the SEM from the SD and the number of runs, or check which n each "
                                      "statistic was computed over."), row, at, at + len(cells[sem_col])))
    return out


# --------------------------------------------------------------------------------------------------
# 3. Test statistics and their p-values
# --------------------------------------------------------------------------------------------------

P_NUMBER = r"(?P<p>(?:\d+(?:\.\d+)?|\.\d+)(?:\s*[×x*]\s*10\s*\^?\s*[-–]?\s*\d+|[eE][-–]?\d+)?)"
STAT_RE = re.compile(
    r"(?<![\w^])(?P<kind>t|F|r|z|Z|χ2|X2|chi[- ]?squared?|chi2)"
    r"\s*(?:[(\[]\s*(?P<df1>\d+(?:\.\d+)?)\s*(?:,\s*(?P<df2>\d+(?:\.\d+)?))?\s*(?:,\s*[nN]\s*=\s*[\d,]+\s*)?[)\]])?"
    r"\s*(?P<op>=|<|>|≤|≥)\s*(?P<stat>[-–]?\s*(?:\d+(?:\.\d+)?|\.\d+))"
    r"(?P<mid>[^;]{0,45}?)"
    r"(?<![\w])[pP](?:[- ]?value)?\s*(?P<prel><=|>=|=|<|>|≤|≥)\s*" + P_NUMBER)
LOOSE_STAT = re.compile(r"(?<![\w^])(?:t|F|r|z|Z|χ2|X2|chi[- ]?squared?|chi2)\s*(?:[(\[][^)\]]{0,25}[)\]])?\s*(?:=|<|>|≤|≥)"
                        r"\s*[-–]?\s*\.?\d")
OTHER_TESTS = re.compile(r"(?<![\w])(?:U|W|H|V|Q|D)\s*(?:[(\[][^)\]]{0,15}[)\]])?\s*=\s*\d[^;]{0,40}?\b[pP]\s*[=<>≤]")
LONE_P = re.compile(r"(?<![\w])[pP](?:[- ]?value)?\s*(?:<=|=|<|≤)\s*(?:\d+(?:\.\d+)?|\.\d+)")
ONE_TAILED = re.compile(r"one[- ]tailed|one[- ]sided|directional (?:test|hypothes)", re.IGNORECASE)
ADJUSTED = re.compile(r"bonferroni|holm|benjamini|hochberg|\bfdr\b|false discovery|adjusted|corrected|\bq[- ]values?\b",
                      re.IGNORECASE)
ALPHA_RES = [
    re.compile(r"(?<!cronbach's )(?<!cronbach )(?:α|alpha|significance (?:level|threshold))\s*(?:of|=|was set (?:at|to)|<|≤|:)"
               r"\s*(0?\.\d+)", re.IGNORECASE),
    re.compile(r"[pP]\s*(?:<|≤|<=)\s*(0?\.\d+)\s+(?:was|were) (?:considered|deemed|taken as|regarded as|defined as) "
               r"(?:statistically )?significant", re.IGNORECASE),
    re.compile(r"significan(?:ce|t) (?:was set |was defined )?at (?:[pP]\s*(?:<|≤)\s*)?(0?\.\d+)", re.IGNORECASE),
]


def _parse_p(text: str) -> tuple[float, float]:
    """(value, half rounding unit) for '.04', '0.040', '1.2 × 10^-5', '1.2e-5'."""
    text = text.replace("–", "-").replace(" ", "")
    m = re.match(r"(\d+(?:\.\d+)?|\.\d+)(?:[×x*]10\^?(-?\d+)|[eE](-?\d+))?$", text)
    if not m:
        raise ValueError(text)
    mantissa = m.group(1)
    exponent = int(m.group(2) or m.group(3) or 0)
    return float(mantissa) * 10 ** exponent, _half_ulp(mantissa) * 10 ** exponent


def find_alpha(text: str) -> tuple[float, str]:
    values = []
    for rx in ALPHA_RES:
        for m in rx.finditer(text):
            v = float(m.group(1))
            if 0.001 <= v <= 0.1:
                values.append(v)
    distinct = sorted(set(values))
    if len(distinct) == 1:
        return distinct[0], "stated in the text"
    if len(distinct) > 1:
        return 0.05, f"default (the text states several: {', '.join(f'{v:g}' for v in distinct)}; pass --alpha)"
    return 0.05, "default (none stated)"


def _p_interval(kind: str, stat: float, h: float, df1: Optional[float], df2: Optional[float],
                hdf1: float, hdf2: float) -> tuple[float, float]:
    """Range of the recomputed p over the rounding intervals of the statistic and the df."""
    lo_x, hi_x = max(0.0, abs(stat) - h), abs(stat) + h
    if kind == "r":
        lo_x, hi_x = min(lo_x, 1.0), min(hi_x, 1.0)
    values = []
    for x in (lo_x, hi_x):
        for d1 in ((df1 - hdf1, df1 + hdf1) if df1 is not None else (None,)):
            for d2 in ((df2 - hdf2, df2 + hdf2) if df2 is not None else (None,)):
                if kind == "z":
                    values.append(p_z(x))
                elif kind == "t":
                    values.append(p_t(x, d1))
                elif kind == "r":
                    values.append(p_r(x, d1))
                elif kind == "F":
                    values.append(p_f(x, d1, d2))
                else:
                    values.append(p_chi2(x, d1))
    return min(values), max(values)


def _kind(raw: str) -> str:
    if raw in ("t", "F", "r"):
        return raw
    if raw in ("z", "Z"):
        return "z"
    return "chi2"


def _overlaps(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] <= b[1] + 1e-12 and b[0] <= a[1] + 1e-12


def _fmt_p(p: float) -> str:
    return f"{p:.2e}" if p < 1e-4 else f"{p:.4f}"


def check_statistics(doc: Document, alpha: float, summary: CheckSummary,
                     results: list[StatResult]) -> tuple[list[Finding], int, int]:
    findings: list[Finding] = []
    lone_p = other_tests = 0
    one_tailed_anywhere = bool(ONE_TAILED.search(doc.text))
    for unit in doc.units:
        if unit.section in UNCHECKED:
            continue
        for s_off, sent in sentences(unit):
            parsed_spans: list[tuple[int, int]] = []
            position = 0
            while (m := STAT_RE.search(sent, position)) is not None:
                inner = LOOSE_STAT.search(m.group("mid"))
                if inner:  # another statistic sits between this one and the p-value: resume from that one
                    position = m.start("mid") + inner.start()
                    continue
                position = m.end()
                parsed_spans.append(m.span())
                finding = _check_one(unit, s_off, sent, m, alpha, one_tailed_anywhere, summary, results)
                if finding:
                    findings.append(_placed(finding, unit, s_off + m.start(), s_off + m.end()))
            for m in LOOSE_STAT.finditer(sent):
                if any(a <= m.start() < b for a, b in parsed_spans):
                    continue
                window = sent[m.start():m.start() + 80]
                if not re.search(r"(?<![\w])[pP](?:[- ]?value)?\s*(?:<=|>=|=|<|>|≤|≥)", window):
                    continue
                summary.not_assessed.append(Skipped(line=unit.line_at(s_off + m.start()),
                                                    excerpt=_excerpt(sent, m.start(), m.end()),
                                                    reason="test statistic and p-value could not be parsed together"))
            other_tests += len(OTHER_TESTS.findall(sent))
            lone_p += sum(1 for m in LONE_P.finditer(sent) if not any(a <= m.start() < b for a, b in parsed_spans))
    return findings, lone_p, other_tests


def _check_one(unit: Unit, s_off: int, sent: str, m: re.Match[str], alpha: float, one_tailed_anywhere: bool,
               summary: CheckSummary, results: list[StatResult]) -> Optional[Finding]:
    kind = _kind(m.group("kind"))
    line = unit.line_at(s_off + m.start())
    excerpt = sent[m.start():m.end()].strip()
    df1_s, df2_s = m.group("df1"), m.group("df2")
    if df1_s is None:
        df_mid = re.search(r"\bdf\s*=\s*(\d+(?:\.\d+)?)", m.group("mid"))
        df1_s = df_mid.group(1) if df_mid else None
    missing = {"t": df1_s is None, "r": df1_s is None, "chi2": df1_s is None, "F": df1_s is None or df2_s is None,
               "z": False}[kind]
    if missing:
        summary.not_assessed.append(Skipped(line=line, excerpt=excerpt, reason="no degrees of freedom stated"))
        return None
    if m.group("op") != "=":
        summary.not_assessed.append(Skipped(line=line, excerpt=excerpt, reason="statistic reported as a bound"))
        return None
    stat_s = m.group("stat").replace("–", "-").replace(" ", "")
    stat = float(stat_s)
    if kind == "r" and abs(stat) > 1:
        summary.assessed += 1
        summary.candidates += 1
        return Finding(check="statcheck", severity=Severity.major, line=line, excerpt=excerpt,
                       message=f"A correlation of {stat_s} is impossible (|r| ≤ 1).",
                       suggestion="Check the coefficient; it may be another statistic.")
    try:
        p_val, p_h = _parse_p(m.group("p"))
    except ValueError:
        summary.not_assessed.append(Skipped(line=line, excerpt=excerpt, reason="p-value could not be read"))
        return None
    df1 = float(df1_s) if df1_s else None
    df2 = float(df2_s) if df2_s else None
    two = _p_interval(kind, stat, _half_ulp(stat_s), df1, df2, _half_ulp(df1_s) if df1_s and "." in df1_s else 0.0,
                      _half_ulp(df2_s) if df2_s and "." in df2_s else 0.0)
    one = (two[0] / 2, two[1] / 2) if kind in ("t", "z", "r") else None
    rel = {"<=": "≤", ">=": "≥"}.get(m.group("prel"), m.group("prel"))
    note = ""
    if rel == "=" and p_val == 0:
        reported = (0.0, p_h)
        note = "p reported as zero; report it as a bound (for example p < .001)."
    elif rel == "=":
        reported = (max(0.0, p_val - p_h), min(1.0, p_val + p_h))
    elif rel in ("<", "≤"):
        reported = (0.0, p_val)
    else:
        reported = (p_val, 1.0)
    summary.assessed += 1
    df_text = ", ".join(x for x in (df1_s, df2_s) if x)
    stat_text = f"{m.group('kind')}({df_text}) = {stat_s}" if df_text else f"{m.group('kind')} = {stat_s}"
    tails_here = bool(ONE_TAILED.search(sent))
    status = "consistent"
    if _overlaps(reported, two):
        pass
    elif one and _overlaps(reported, one) and tails_here:
        status = "consistent-one-tailed"
    else:
        status = "inconsistent"
    result = StatResult(line=line, excerpt=excerpt, test=kind, df=[x for x in (df1, df2) if x is not None],
                        statistic=stat_s, reported_p=f"p {rel} {m.group('p')}", p_two_tailed=two,
                        p_one_tailed=one, status=status, note=note)
    results.append(result)
    if status != "inconsistent":
        summary.consistent += 1
        return None
    # The reported decision against the computed one, each only where it is determinate.
    if rel == "=":
        reported_sig: Optional[bool] = p_val < alpha
    elif rel in ("<", "≤"):
        reported_sig = True if p_val <= alpha else None
    else:
        reported_sig = False if p_val >= alpha else None
    computed_sig = True if two[1] < alpha else False if two[0] >= alpha else None
    gross = reported_sig is not None and computed_sig is not None and reported_sig != computed_sig
    adjusted = bool(ADJUSTED.search(sent)) and reported[0] > two[1]
    one_match = one is not None and _overlaps(reported, one)
    one_note = ""
    if one_match:
        one_note = (" The value matches a one-tailed test; the paper mentions one-tailed tests elsewhere, so say beside "
                    "this result if it was one." if one_tailed_anywhere else
                    " The value matches a one-tailed test, which the text does not state.")
    computed_text = f"{_fmt_p(two[0])}–{_fmt_p(two[1])}" if _fmt_p(two[0]) != _fmt_p(two[1]) else _fmt_p(two[0])
    arithmetic = (f"{stat_text} gives a {'two-tailed ' if one else ''}p of {computed_text} (allowing for the rounding "
                  f"of the statistic{' and df' if df1_s and '.' in df1_s else ''})"
                  + (f"; one-tailed {_fmt_p(one[0])}–{_fmt_p(one[1])}" if one else "")
                  + f". Reported: p {rel} {m.group('p')}.")
    summary.candidates += 1
    if adjusted:
        result.status = "adjusted?"
        return Finding(check="statcheck", severity=Severity.info, line=line, excerpt=excerpt,
                       message="Reported p is larger than the p recomputed from the statistic; the sentence mentions a "
                               "multiplicity adjustment, which would explain it.",
                       arithmetic=arithmetic, suggestion="Confirm the p is adjusted and say which adjustment.")
    if gross:
        result.status = "gross"
        direction = ("significant" if reported_sig else "not significant")
        return Finding(check="statcheck", severity=Severity.major, line=line, excerpt=excerpt,
                       message=f"Gross inconsistency: the reported p reads as {direction} at α = {alpha:g}, the "
                               f"recomputed p does not.",
                       arithmetic=arithmetic + one_note,
                       suggestion="Recheck the statistic, the df and the p against the analysis output; if a one-tailed "
                                  "or adjusted test was used, say so beside the result.")
    return Finding(check="statcheck", severity=Severity.minor, line=line, excerpt=excerpt,
                   message="The reported p does not match the p recomputed from the test statistic and df (the "
                           "conclusion at α = {:g} is unchanged).".format(alpha),
                   arithmetic=arithmetic + one_note,
                   suggestion="Recheck the statistic, the df and the p against the analysis output.")


# --------------------------------------------------------------------------------------------------


def run(path: Path, alpha: Optional[float] = None, assume_integer: bool = False) -> NumbersReport:
    doc = parse(path)
    found_alpha, alpha_source = find_alpha(doc.text)
    if alpha is None:
        alpha = found_alpha
    else:
        alpha_source = "--alpha"
    checks = {name: CheckSummary() for name in ("ledger", "grim", "grimmer", "percent-of-n", "table-total", "sem-sd",
                                                "statcheck")}
    statistics: list[StatResult] = []
    findings, ledger = check_ledger(doc, checks["ledger"])
    findings += check_grim(doc, assume_integer, checks["grim"], checks["grimmer"], checks["percent-of-n"])
    findings += check_tables(doc, checks["table-total"], checks["sem-sd"])
    stat_findings, lone_p, other_tests = check_statistics(doc, alpha, checks["statcheck"], statistics)
    findings += stat_findings
    if lone_p:
        one = lone_p == 1
        checks["statcheck"].not_assessed.append(Skipped(
            reason=f"{lone_p} p-value{'' if one else 's'} {'stands' if one else 'stand'} without a test statistic beside "
                   f"{'it' if one else 'them'}, so {'it' if one else 'they'} cannot be recomputed"))
    if other_tests:
        checks["statcheck"].not_assessed.append(Skipped(
            reason=f"{other_tests} {'result comes' if other_tests == 1 else 'results come'} from tests this script does "
                   f"not recompute (Mann-Whitney U, Wilcoxon W, Kruskal-Wallis H and others)"))
    places = {number: _place_name(unit) for unit in doc.units for _, number in unit.starts}
    for summary in checks.values():
        for item in summary.not_assessed:
            item.section = places.get(item.line) if item.line else None
    order = {s: i for i, s in enumerate(Severity)}
    findings.sort(key=lambda f: (order[f.severity], f.line or 0))
    return NumbersReport(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), alpha=alpha,
                         alpha_source=alpha_source, findings=findings, checks=checks, statistics=statistics,
                         ledger=ledger)


CHECK_TITLES = {"ledger": "The same quantity stated with different values",
                "grim": "Means of whole-number data (GRIM test)",
                "grimmer": "Standard deviations of whole-number data (GRIMMER test)",
                "percent-of-n": "Percentages of a stated n",
                "table-total": "Table column totals against their cells",
                "sem-sd": "Standard errors in a table against the SD and n",
                "statcheck": "Test statistics against their p-values"}
def _alpha_source(source: str) -> str:
    several = re.search(r"states several: ([^;)]+)", source)
    if several:
        return (f"the usual default, because the text states several levels ({several.group(1)}); give the one that "
                f"applies with --alpha")
    return {"stated in the text": "as the text states", "--alpha": "as set with --alpha"}.get(
        source, "the usual default, because the text states none")


SEVERITY_LEAD = {Severity.blocker: "Serious", Severity.major: "Important", Severity.minor: "Minor",
                 Severity.info: "To look at"}
NUMBERED = re.compile(r"^(?P<number>(?:\d+(?:\.\d+)*|[IVX]+))[.)]?\s+(?P<title>\S.*)$")
# Headings read naturally after "the" ("in the Methods"); any other heading is quoted ("in the section “Speed”").
PLAIN_HEADINGS = re.compile(r"^(?:abstract|introduction|background|methods?|materials|results|discussion|conclusions?|"
                            r"references|bibliography|acknowledge?ments|funding|supplementary|appendix|limitations|"
                            r"data|code|availability|declarations?|author|competing|ethics)\b", re.IGNORECASE)


def _where_in(section: Optional[str], line: Optional[int]) -> str:
    """'In the Results (line 12)', 'In Table 1, row “Women” (line 30)', 'In section 2.1, Data (line 8)'."""
    at = f" (line {line})" if line else ""
    if not section:
        return f"At line {line}" if line else "In the manuscript"
    if section.lower().startswith(("table", "the table")):
        return f"In {section}{at}"
    numbered = NUMBERED.match(section.split(", ")[-1])
    if numbered:
        return f"In section {numbered.group('number')}, {numbered.group('title')}{at}"
    return f"In the {section}{at}" if PLAIN_HEADINGS.match(section) else f"In the section “{section}”{at}"


def _marked(quote: str, span: Optional[tuple[int, int]]) -> str:
    quote = re.sub(r"\*\*|__|`", "", quote) if not span else quote
    if span and span[1] > span[0]:
        a, b = span
        quote = re.sub(r"\*\*|__|`", "", quote[:a]) + "**" + re.sub(r"\*\*|__|`", "", quote[a:b]).strip() + "**" + \
            re.sub(r"\*\*|__|`", "", quote[b:])
    return f"“{quote}”"


def _sentence(text: str) -> str:
    text = " ".join(text.split())
    return text if not text or text[-1] in ".!?”" else text + "."


def _finding_line(f: Finding) -> str:
    place = ""
    if f.quote:
        end = "" if f.quote[-1:] in ".!?" else "."
        place = f"{_where_in(f.section, f.line)}, the manuscript reads {_marked(f.quote, f.quote_span)}{end}"
    arithmetic = ("" if not f.arithmetic else _sentence(f.arithmetic) if f.check == "ledger"
                  else f"The arithmetic: {_sentence(f.arithmetic)}")
    parts = [_sentence(f.message), place, arithmetic, _sentence(f.suggestion)]
    return f"- **{SEVERITY_LEAD[f.severity]}.** " + " ".join(p for p in parts if p)


def to_markdown(report: NumbersReport) -> str:
    out = [f"# Numbers and statistics in {Path(report.path).name}", "",
           "These are candidates for the authors to check, each with its arithmetic. A calculator cannot tell an exact "
           "value from a rounded one, or know which n a value was computed over, so none of them is a verdict. "
           f"Gross inconsistencies in test results are judged at a significance level of α = {report.alpha:g}, "
           + _alpha_source(report.alpha_source) + ".", "",
           "| What was checked | Statements checked | Consistent | To check | Too imprecise to tell | Could not be read |",
           "|---|---|---|---|---|---|"]
    for name, s in report.checks.items():
        out.append(f"| {CHECK_TITLES[name]} | {s.assessed} | {s.consistent} | {s.candidates} | {s.not_informative} | "
                   f"{len(s.not_assessed)} |")
    out.append("")
    if report.findings:
        out += ["## Fix now: the science and the evidence", "",
                "Within this group the most serious findings come first: “Important” marks what an editor or referee "
                "would object to, “Minor” a value that is off without changing a conclusion, and “To look at” what "
                "may be fine.", ""]
        out += [_finding_line(f) for f in report.findings]
        out.append("")
    else:
        out += ["No candidate was found by these checks. This does not establish that the numbers are right.", ""]
    skipped = [(name, s) for name, s in report.checks.items() if s.not_assessed]
    if skipped:
        out += ["## What could not be checked", ""]
        for name, s in skipped:
            out += [f"**{CHECK_TITLES[name]}.**", ""]
            for item in s.not_assessed:
                if item.line:
                    quoted = f", “{item.excerpt}”," if item.excerpt else ""
                    out.append(f"- {_where_in(item.section, item.line)}{quoted} could not be checked ({item.reason}).")
                else:
                    out.append(f"- {_sentence(item.reason[:1].upper() + item.reason[1:])}")
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


@app.command()
def main(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    alpha: Annotated[Optional[float], typer.Option(help="Significance level for gross inconsistencies (default: "
                                                        "the one the text states, else 0.05)")] = None,
    assume_integer: Annotated[bool, typer.Option(help="Apply GRIM/GRIMMER to every mean that states its n, not only "
                                                      "to ratings and counts")] = False,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the full report as JSON")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Write the Markdown report here (default: stdout)")] = None,
) -> None:
    if alpha is not None and not 0 < alpha < 1:
        raise typer.BadParameter("--alpha must be between 0 and 1")
    report = run(path, alpha, assume_integer)
    md = to_markdown(report)
    if json_out:
        json_out.write_text(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    if md_out:
        md_out.write_text(md, encoding="utf-8")
        typer.echo(f"wrote {md_out}")
    else:
        typer.echo(md)
    raise typer.Exit(code=1 if any(f.severity in (Severity.major, Severity.minor) for f in report.findings) else 0)


if __name__ == "__main__":
    app()
