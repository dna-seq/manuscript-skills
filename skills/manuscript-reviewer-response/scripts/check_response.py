# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6"]
# ///
"""Check a point-by-point response letter against the referees' comments, the review ledger and the revision.

Structure only. It checks that every ledger item has exactly one reply, in the referee's order, under a
verbatim quote of the comment; that each reply names a location (or says nothing changed); that the
locations, quoted revised text and numbers a reply gives exist in the revised manuscript; that no
commitment is still only promised; and that no blanket reply or [TBD: ...] placeholder remains. It cannot
tell whether a reply answers the comment, whether the science is right or whether a change is adequate.
A clean run is not a good letter.

Without a letter it checks the ledger alone (plan mode): every comment verbatim and in the referees' order,
links between items, a reason for every decline; undecided items are listed, not failed.

Decisions: an item's `decision` is the authors' own, given item by item, or covered by their one
confirmation of the proposed decisions. Such an item has `proposed` (the decision the plan proposed) and
`confirmed: blanket`, and its round records the confirmation (`confirmation:` with `asked`, the question as it
was put, `answer`, the authors' words, and `named`, the items the question named). A blanket confirmation covers
items the plan proposes to address with text changes only; a proposed decline or "does not apply", and an item
whose answer needs new data or a new analysis, count as confirmed only when the question named them ("All as
proposed, including declining R2.4 and adding the replication in R1.3?"). An item it does not cover stays
undecided.

    uv run --script check_response.py REVIEWS LEDGER                    # plan mode: the ledger alone
    uv run --script check_response.py REVIEWS LEDGER LETTER --revised REVISED [--original ORIGINAL]
    uv run --script check_response.py reviews-r1.txt review-ledger.yaml response-r1.md \
        --revised paper-v2.md --original paper-v1.md --md check.md --json check.json
    uv run --script check_response.py reviews-r2.txt review-ledger.yaml response-r2.md --round 2 --revised paper-v3.md
    uv run --script check_response.py reviews.txt ledger.yaml rebuttal.md --mode rebuttal --max-chars 5000
    uv run --script check_response.py ... --guard-json guard.json    # reconcile guard.py ORIGINAL REVISED

Letter format (Markdown; convert a Word letter with `pandoc -t gfm`). A reply block is an item tag, the
referee's comment as a blockquote, then the reply. A later blockquote inside a reply quotes the revised
manuscript. Tags are optional: without them, blocks are matched to ledger items by their quotes.

    <!-- item: R1.2 -->
    > 2. Table 1 reports medians of 3 runs. Please report the spread across runs as well.

    Table 1 now gives the range across the three runs. (Results, "Performance", lines 47-49; Table 1)

Line numbers are checked against the revised file as given. A text export of a line-numbered PDF
(`pdftotext -layout`) is recognised and its printed numbers are used; use --no-line-check when the letter
cites numbering that the supplied file does not carry.

The Markdown report (printed, and written with --md) is for the authors: it quotes each comment with the
referee's own number and the letter or manuscript text a finding concerns, names places in words with line
numbers in parentheses, and groups the problems by when they can be fixed (the science and the evidence, then
the writing, then the venue's format, then end-of-project statements). The JSON (--json) keeps the codes, ids,
states and line numbers for other tools.

Exit codes: 0 no blocking finding among the checks that ran (read "What could not be checked": a check that
could not run did not pass, so exit 0 with checks not run is not a clean result); 1 at least one blocking
finding (with --strict, any finding); 2 unreadable or malformed input.
"""

from __future__ import annotations

import json
import re
import sys
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml

app = typer.Typer(add_completion=False, no_args_is_help=True)

LIMITATION = ("This check covers structure only. It cannot tell whether a reply answers the comment, whether "
              "the science is right or whether a change is adequate. A clean run is not a good letter.")
LEDGER_LIMITATION = ("This check covers the ledger's structure only. It cannot tell whether the comments are split "
                     "well, whether a concern is read right or whether a decision is sound.")


class Mode(str, Enum):
    journal = "journal"
    rebuttal = "rebuttal"


class InputError(Exception):
    """Unreadable or malformed input: the check cannot run (exit code 2)."""


# --------------------------------------------------------------------------------------------------------
# Text folding: typography, case and whitespace, keeping each folded character's source index
# --------------------------------------------------------------------------------------------------------

_FOLD = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'", "\u00b4": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2033": '"', "\u00ab": '"', "\u00bb": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2015": "-", "\u2212": "-",
    "\u00a0": " ", "\u2007": " ", "\u2009": " ", "\u202f": " ", "\u200b": "", "\u00ad": "", "\ufeff": "",
    "\u2026": "...", "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
    "*": "", "`": "",
}


def fold(raw: str) -> tuple[str, list[int]]:
    """Fold text for comparison and keep, for each output character, the index of its source character.

    Curly quotes, dash variants, special spaces, ligatures, emphasis asterisks and case are folded, runs of
    whitespace become one space, and a hyphen joining two letters is dropped (also across a line break, as
    PDF text leaves it), so "long-read", "long-\\nread" and "longread" compare equal. Signs on numbers stay.
    """
    out: list[str] = []
    src: list[int] = []
    for i, ch in enumerate(raw):
        for c in _FOLD.get(ch, ch):
            if c.isspace():
                if out and out[-1] != " ":
                    out.append(" ")
                    src.append(i)
                continue
            if c.isalpha():
                if len(out) > 1 and out[-1] == "-" and out[-2].isalpha():
                    out.pop()
                    src.pop()
                elif len(out) > 2 and out[-1] == " " and out[-2] == "-" and out[-3].isalpha():
                    del out[-2:]
                    del src[-2:]
                for low in c.lower():
                    out.append(low)
                    src.append(i)
                continue
            out.append(c)
            src.append(i)
    while out and out[-1] == " ":
        out.pop()
        src.pop()
    return "".join(out), src


def norm(text: str) -> str:
    return fold(text)[0]


def _strip_quote_marks(folded: str) -> str:
    return folded.strip(" \"'")


_ELLIPSIS = re.compile(r"\s*[\[(]?\.\.\.[\])]?\s*")
_SENT_SPLIT = re.compile(r"(?<=[.?!])\s+")


def find_folded(haystack: str, quote: str, start: int = 0) -> tuple[int, int, bool] | None:
    """Locate a quote in an already folded text: (start, end, elided) or None.

    A quote with an ellipsis matches when its parts occur in order; `elided` is then True.
    """
    q = _strip_quote_marks(norm(quote))
    if not q:
        return None
    parts = [p for p in _ELLIPSIS.split(q) if p.strip(" \"'")]
    if len(parts) <= 1:
        needle = parts[0].strip(" \"'") if parts else q
        k = haystack.find(needle, start)
        if k < 0 and start:
            k = haystack.find(needle)
        return (k, k + len(needle), len(parts) == 1 and needle != q) if k >= 0 else None
    pos, first = start, -1
    for part in parts:
        part = part.strip(" \"'")
        k = haystack.find(part, pos)
        if k < 0:
            return None
        first = k if first < 0 else first
        pos = k + len(part)
    return first, pos, True


_MARKER = re.compile(r"^\(?[\w]{1,4}[.)]$")


def _sentences(folded: str) -> list[str]:
    """Sentences of a folded text, with a bare list marker ("3.", "b)") joined to the sentence it opens."""
    out: list[str] = []
    for part in _SENT_SPLIT.split(folded):
        if not part:
            continue
        if out and _MARKER.match(out[-1]):
            out[-1] = f"{out[-1]} {part}"
        else:
            out.append(part)
    return out


def _windows(folded: str, size: int) -> list[str]:
    sents = _sentences(folded)
    size = max(1, size)
    return [" ".join(sents[i:i + size]) for i in range(max(1, len(sents) - size + 1))]


_STOP = frozenset("the and for with that this these those from into than then were was are have has had not but "
                  "also any all its their they them our out one such may can should would could please".split())


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text) if len(w) > 2 and w not in _STOP}


def nearest(text: str, folded_source: str, by_words: bool = False) -> tuple[float, str]:
    """The closest run of sentences in a folded source, with its similarity ratio.

    Character similarity decides whether a quote is the referee's or the manuscript's; word similarity
    finds the passage a paraphrase came from, for the hint.
    """
    q = _strip_quote_marks(norm(text))
    if not q or not folded_source:
        return 0.0, ""
    size = len(_sentences(q))
    best = (0.0, "")
    windows = {w for n in (size - 1, size, size + 1) if n >= 1 for w in _windows(folded_source, n)}
    for window in sorted(windows):
        if by_words:
            a, b = _content_words(q), _content_words(window)
            ratio = 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0
        else:
            ratio = SequenceMatcher(None, q, window, autojunk=False).ratio()
        if ratio > best[0]:
            best = (ratio, window)
    return best


# --------------------------------------------------------------------------------------------------------
# Numbers
# --------------------------------------------------------------------------------------------------------

NUM_RE = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)*")
_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
          "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]


def number_value(token: str) -> float | None:
    t = token.replace("\u2212", "-").strip()
    if re.fullmatch(r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", t):
        t = t.replace(",", "")
    elif t.count(",") == 1 and "." not in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def number_values(text: str) -> set[float]:
    return {v for v in (number_value(m.group(0)) for m in NUM_RE.finditer(text)) if v is not None}


def _has_number(value: float, values: set[float], words: set[str]) -> bool:
    if any(abs(value - v) < 1e-9 for v in values):
        return True
    return value.is_integer() and 0 <= value <= 20 and _WORDS[int(value)] in words


# --------------------------------------------------------------------------------------------------------
# Manuscripts
# --------------------------------------------------------------------------------------------------------

PRINTED_RE = re.compile(r"^\s*(\d{1,6})(?:\s+|$)")
MD_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
BOLD_HEADING_RE = re.compile(r"^\s*\*\*([^*]{2,80})\*\*\s*:?\s*$")
TEX_HEADING_RE = re.compile(r"\\(?:sub)*section\*?\s*\{([^}]*)\}|\\paragraph\*?\s*\{([^}]*)\}")
NUMBERED_LINE_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+([A-Z][^.]{0,78})$")
SECTION_NAMES = ["Abstract", "Introduction", "Background", "Materials and Methods", "Methods", "Results",
                 "Discussion", "Conclusions", "Conclusion", "Limitations", "Data availability",
                 "Code availability", "Software availability", "Availability", "Ethics", "Acknowledgements",
                 "Acknowledgments", "References", "Supplementary Information", "Supplementary Methods",
                 "Appendix", "Author contributions", "Funding", "Competing interests", "Title", "Summary"]
SECTION_RE = re.compile(r"\b(" + "|".join(sorted((re.escape(s) for s in SECTION_NAMES), key=len, reverse=True))
                        + r")\b")
TABFIG_RE = re.compile(r"\b(?P<supp>Supplementary\s+|Suppl\.\s*|Extended\s+Data\s+)?"
                       r"(?P<kind>Tables?|Tab\.|Figures?|Figs?\.?)\s*(?P<s>S)?(?P<num>\d+)(?P<panel>[a-z])?\b")
SUPPOBJ_RE = re.compile(r"\b(?:Supplementary|Suppl\.)\s+(?P<kind>Notes?|Files?|Data(?:sets?)?|Texts?)\s*"
                        r"(?P<s>S)?(?P<num>\d+)\b")
LINES_RE = re.compile(r"\b(?:lines?|ll\.|l\.)\s*(?P<list>\d+(?:\s*[-\u2013\u2014]\s*\d+)?"
                      r"(?:\s*(?:,|and|&)\s*\d+(?:\s*[-\u2013\u2014]\s*\d+)?)*)", re.IGNORECASE)
PAGES_RE = re.compile(r"\b(?:pages?|pp?\.)\s*\d+(?:\s*[-\u2013\u2014]\s*\d+)?", re.IGNORECASE)
SECNUM_RE = re.compile(r"\b[Ss]ections?\s+(\d+(?:\.\d+)*)")
HEADING_REF_RE = re.compile(
    r"(?:\b(?:[Ss]ub)?[Ss]ections?\s+|\b[Hh]eading\s+|\b(?:" + "|".join(re.escape(s) for s in SECTION_NAMES)
    + r")\s*,\s*)[\"\u201c\u2018']([^\"\u201d\u2019']{2,80})[\"\u201d\u2019']")


@dataclass
class Doc:
    path: Path
    lines: list[str]
    numbers: list[int]
    printed: bool
    folded: str
    src: list[int]
    line_starts: list[int]
    kind: str
    headings: list[str]
    raw_headings: list[str]
    objects: set[tuple[str, str, int]]
    tex_counts: dict[str, int]
    values: set[float]
    words: set[str]
    object_lines: dict[tuple[str, str, int], set[int]] = field(default_factory=dict)
    heading_lines: list[tuple[int, str]] = field(default_factory=list)

    def section_span(self, heading: str) -> tuple[int, int] | None:
        """Reader-visible lines from a heading (folded text) to the line before the next heading."""
        for k, (line, text) in enumerate(self.heading_lines):
            if text == heading:
                end = self.heading_lines[k + 1][0] - 1 if k + 1 < len(self.heading_lines) else self.max_line
                return line, max(line, end)
        return None

    def line_of(self, k: int) -> int:
        """Reader-visible line number of a folded offset."""
        raw = self.src[min(max(k, 0), len(self.src) - 1)] if self.src else 0
        idx = max(0, bisect_right(self.line_starts, raw) - 1)
        return self.numbers[idx] if self.numbers else idx + 1

    @property
    def max_line(self) -> int:
        return max(self.numbers) if self.numbers else 0

    @property
    def min_line(self) -> int:
        return min(self.numbers) if self.numbers else 0


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"{path} is not UTF-8 text ({exc.reason}); convert it first.") from exc
    except OSError as exc:
        raise InputError(f"{path} cannot be read ({exc.strerror}).") from exc


def _object_key(m: re.Match[str], kind_group: str = "kind") -> tuple[str, str, int]:
    kind = m.group(kind_group).lower()
    kind = ("table" if kind.startswith("tab") else "figure" if kind.startswith("fig") else
            "note" if kind.startswith("note") else "file" if kind.startswith("file") else
            "text" if kind.startswith("text") else "data")
    groups = m.groupdict()
    supp = (groups.get("supp") or "").strip().lower()
    scope = "ext" if supp.startswith("extended") else "supp" if (supp or groups.get("s")) else "main"
    if kind in {"note", "file", "data", "text"}:
        scope = "supp"
    return kind, scope, int(m.group("num"))


def find_objects(text: str) -> set[tuple[str, str, int]]:
    keys = {_object_key(m) for m in TABFIG_RE.finditer(text)}
    return keys | {_object_key(m) for m in SUPPOBJ_RE.finditer(text)}


CAPTION_RE = re.compile(r"^\s*(?:\*\*)?(?P<supp>Supplementary\s+)?(?P<kind>Table|Figure|Fig\.)\s*(?P<s>S)?"
                        r"(?P<num>\d+)\s*[.:|]")


def object_regions(lines: list[str], numbers: list[int], is_tex: bool) -> dict[tuple[str, str, int], set[int]]:
    """Lines that belong to each table or figure: its caption paragraph and a Markdown table right after it,
    or, in LaTeX, the Nth table or figure environment."""
    regions: dict[tuple[str, str, int], set[int]] = {}
    if is_tex:
        count = {"table": 0, "figure": 0}
        current: tuple[str, str, int] | None = None
        for i, line in enumerate(lines):
            m = re.search(r"\\begin\{(table|figure)\*?\}", line)
            if m:
                count[m.group(1)] += 1
                current = (m.group(1), "main", count[m.group(1)])
            if current:
                regions.setdefault(current, set()).add(numbers[i])
            if re.search(r"\\end\{(table|figure)\*?\}", line):
                current = None
        return regions
    i = 0
    while i < len(lines):
        m = CAPTION_RE.match(lines[i])
        if not m:
            i += 1
            continue
        key = _object_key(m)
        span = set()
        j = i
        while j < len(lines) and lines[j].strip():
            span.add(numbers[j])
            j += 1
        k = j
        while k < len(lines) and not lines[k].strip():
            k += 1
        if k < len(lines) and lines[k].lstrip().startswith("|"):
            while k < len(lines) and lines[k].strip():
                span.add(numbers[k])
                k += 1
        regions.setdefault(key, set()).update(span)
        i = max(j, i + 1)
    return regions


def load_doc(path: Path) -> Doc:
    raw = read_text(path)
    raw_lines = raw.splitlines()
    nonempty = [line for line in raw_lines if line.strip()]
    hits = [int(m.group(1)) for m in (PRINTED_RE.match(line) for line in nonempty) if m]
    printed = (len(nonempty) >= 5 and len(hits) >= 0.6 * len(nonempty)
               and sum(b > a for a, b in zip(hits, hits[1:])) >= 0.9 * (len(hits) - 1))
    lines: list[str] = []
    numbers: list[int] = []
    last = 0
    for i, line in enumerate(raw_lines):
        if printed:
            m = PRINTED_RE.match(line)
            if m:
                last = int(m.group(1))
                line = line[m.end():]
            numbers.append(last)
        else:
            numbers.append(i + 1)
        lines.append(line)
    text = "\n".join(lines)
    line_starts, pos = [], 0
    for line in lines:
        line_starts.append(pos)
        pos += len(line) + 1
    folded, src = fold(text)
    is_tex = path.suffix.lower() == ".tex" or "\\begin{document}" in text or "\\section{" in text
    raw_headings: list[str] = []
    heading_lines: list[tuple[int, str]] = []
    kind = "latex" if is_tex else "text"
    if is_tex:
        raw_headings = [a or b for a, b in TEX_HEADING_RE.findall(text)]
        heading_lines = [(numbers[i], norm(m.group(1) or m.group(2))) for i, line in enumerate(lines)
                         for m in TEX_HEADING_RE.finditer(line)]
        if "\\begin{abstract}" in text:
            raw_headings.append("Abstract")
        if "\\title{" in text:
            raw_headings.append("Title")
    else:
        for i, line in enumerate(lines):
            m = MD_HEADING_RE.match(line) or BOLD_HEADING_RE.match(line)
            if m:
                kind = "markdown"
                raw_headings.append(m.group(1).strip())
                heading_lines.append((numbers[i], norm(m.group(1))))
                continue
            n = NUMBERED_LINE_RE.match(line)
            stripped = line.strip().rstrip(":")
            if n:
                raw_headings.append(f"{n.group(1)} {n.group(2).strip()}")
            elif stripped and any(stripped.lower() == s.lower() for s in SECTION_NAMES):
                raw_headings.append(stripped)
        if kind == "markdown" and lines and MD_HEADING_RE.match(next((x for x in lines if x.strip()), "")):
            raw_headings.append("Title")
    tex_counts = {"table": len(re.findall(r"\\begin\{table\*?\}", text)),
                  "figure": len(re.findall(r"\\begin\{figure\*?\}", text))} if is_tex else {}
    return Doc(path=path, lines=lines, numbers=numbers, printed=printed, folded=folded, src=src,
               line_starts=line_starts, kind=kind, headings=[norm(h) for h in raw_headings],
               raw_headings=raw_headings, objects=find_objects(text), tex_counts=tex_counts,
               values=number_values(text), words=set(re.findall(r"[a-z]+", folded)),
               object_lines=object_regions(lines, numbers, is_tex), heading_lines=heading_lines)


# --------------------------------------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------------------------------------

DECISIONS = {"address", "decline", "not-on-point", "undecided"}
CONFIRMED = {"blanket", "item"}  # covered by the authors' one confirmation of the proposals, or decided on its own
NEW_WORK = {"new-data", "new-analysis"}  # an item needing these is never covered by a blanket yes unless named
EVIDENCE = {"new-data", "new-analysis", "table", "figure", "citation", "methods-text", "results-text",
            "discussion-text", "statement", "wording", "answer", "acknowledge"}
LETTER_ONLY_EVIDENCE = {"answer", "acknowledge"}
ID_RE = re.compile(r"[A-Za-z0-9][\w.()\-]*")
NOT_LANDED_RE = re.compile(r"(?:promised(?:\s+only)?|pending|planned|todo|to\s+do|tbd|not\s+yet|no)\.?",
                           re.IGNORECASE)
PREVIOUS_RE = re.compile(r"^\s*(?:round\s*)?(\d+)\s*[:/]\s*(\S+)\s*$", re.IGNORECASE)


@dataclass
class Commitment:
    change: str
    target: str
    landed: str

    @property
    def is_landed(self) -> bool:
        return bool(self.landed) and not NOT_LANDED_RE.fullmatch(self.landed.strip())


@dataclass
class Item:
    id: str
    referee: str
    comment: str
    decision: str
    reason: str
    evidence: list[str]
    must_fix: bool
    commitments: list[Commitment]
    previous: list[str]
    index: int
    hand_to: list[str] = field(default_factory=list)
    same_as: list[str] = field(default_factory=list)
    sentence: str = ""
    label: str = ""    # the referee's own marker ("2", "4a", "Suggestions 2"); empty when the authors added the id
    round: int = 1
    proposed: str = ""  # the decision the plan proposed to the authors
    confirmed: str = ""  # "blanket": covered by the round's confirmation; "item": decided on its own
    not_covered: str = ""  # why the round's confirmation does not cover an item marked blanket


@dataclass
class Round:
    number: int
    items: list[Item]
    confirmation: dict[str, object] = field(default_factory=dict)  # asked, answer (the authors' words), named


def _decision(value: object) -> str:
    return _text(value).lower().replace("_", "-").replace(" ", "-")


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _strings(value: object) -> list[str]:
    """A YAML scalar or list as a list of non-empty strings."""
    values = value if isinstance(value, list) else [] if value is None else [value]
    return [t for t in (_text(v) for v in values) if t]


def load_ledger(path: Path) -> list[Round]:
    try:
        data = yaml.safe_load(read_text(path))
    except yaml.YAMLError as exc:
        first = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
        raise InputError(f"The ledger {path} is not valid YAML ({first}).") from exc
    if not isinstance(data, dict):
        raise InputError(f"The ledger {path} must be a mapping with a `rounds:` list (or `items:` for a single round).")
    raw_rounds = data.get("rounds")
    if raw_rounds is None:
        if "items" not in data:
            raise InputError(f"The ledger {path} has neither `rounds:` nor `items:`.")
        raw_rounds = [{"round": data.get("round", 1), "items": data["items"]}]
    if not isinstance(raw_rounds, list) or not raw_rounds:
        raise InputError(f"In the ledger {path}, `rounds:` must be a non-empty list.")
    rounds: list[Round] = []
    for r_index, entry in enumerate(raw_rounds):
        if not isinstance(entry, dict):
            raise InputError(f"In the ledger {path}, round {r_index + 1} is not a mapping.")
        try:
            number = int(entry.get("round", r_index + 1))
        except (TypeError, ValueError) as exc:
            raise InputError(f"In the ledger {path}, round {r_index + 1} has a `round:` that is not a number.") from exc
        raw_items = entry.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise InputError(f"In the ledger {path}, round {number} has no items.")
        confirmation = entry.get("confirmation") or {}
        if not isinstance(confirmation, dict):
            raise InputError(f"In the ledger {path}, round {number} has a `confirmation:` that is not a mapping with "
                             "`asked`, `answer` and `named`.")
        items: list[Item] = []
        seen: set[str] = set()
        for k, raw in enumerate(raw_items):
            where = f"In the ledger {path}, item {k + 1} of round {number}"
            if not isinstance(raw, dict):
                raise InputError(f"{where} is not a mapping.")
            item_id = _text(raw.get("id"))
            if not ID_RE.fullmatch(item_id):
                raise InputError(f"{where} has a missing or unusable id {item_id!r}.")
            if item_id in seen:
                raise InputError(f"{where} has a duplicate id {item_id!r}; each item needs its own.")
            seen.add(item_id)
            comment = _text(raw.get("comment"))
            if not comment:
                raise InputError(f"{where} ({item_id}) has no `comment:` text.")
            decision = _decision(raw.get("decision")) or "undecided"
            if decision not in DECISIONS:
                raise InputError(f"{where} ({item_id}) has the decision {decision!r}, which is not one of "
                                 f"{', '.join(sorted(DECISIONS))}.")
            proposed = _decision(raw.get("proposed"))
            if proposed and proposed not in DECISIONS - {"undecided"}:
                raise InputError(f"{where} ({item_id}) proposes {proposed!r}, which is not one of "
                                 f"{', '.join(sorted(DECISIONS - {'undecided'}))}.")
            confirmed = _text(raw.get("confirmed")).lower()
            if confirmed and confirmed not in CONFIRMED:
                raise InputError(f"{where} ({item_id}) has `confirmed: {confirmed}`; use blanket (covered by the round's "
                                 "confirmation of the proposals) or item (decided on its own).")
            evidence = raw.get("evidence") or []
            evidence = [evidence] if isinstance(evidence, str) else [str(e).strip() for e in evidence]
            commitments: list[Commitment] = []
            for c in raw.get("commitments") or []:
                c = {"change": c} if isinstance(c, str) else c
                if not isinstance(c, dict):
                    raise InputError(f"{where} ({item_id}) has a commitment that is not a mapping.")
                commitments.append(Commitment(_text(c.get("change")), _text(c.get("target")),
                                              _text(c.get("landed"))))
            previous = raw.get("previous") or []
            previous = [previous] if isinstance(previous, str) else [str(p) for p in previous]
            # `hand_to` names the companion skill; ledgers written before the rename call it `route`
            hand_to = _strings(raw["hand_to"] if "hand_to" in raw else raw.get("route"))
            items.append(Item(id=item_id, referee=_text(raw.get("referee")), comment=comment, decision=decision,
                              reason=_text(raw.get("reason")), evidence=evidence,
                              must_fix=bool(raw.get("must_fix")), commitments=commitments, previous=previous,
                              index=k, hand_to=hand_to, same_as=_strings(raw.get("same_as")),
                              sentence=_text(raw.get("sentence")), label=_text(raw.get("label")), round=number,
                              proposed=proposed, confirmed=confirmed))
        rounds.append(Round(number, items, confirmation))
    numbers = [r.number for r in rounds]
    if len(set(numbers)) != len(numbers):
        raise InputError(f"In the ledger {path}, a round number occurs twice.")
    return sorted(rounds, key=lambda r: r.number)


# --------------------------------------------------------------------------------------------------------
# Plain words for the authors: the Markdown report quotes the comment and the text each finding concerns,
# names places in words with line numbers only in parentheses, and groups the work by when it can be done.
# The JSON keeps the codes, ids and states for other tools.
# --------------------------------------------------------------------------------------------------------

STAGES = (("now", "Fix now: the science and the evidence"), ("writing", "Then the writing"),
          ("journal", "Once you have chosen the journal"), ("final", "Before submission, once the code is final"))
STAGE_RANK = {key: k for k, (key, _) in enumerate(STAGES)}
# Evidence that changes what the paper reports or how it got there; `statement` is end-of-project packaging.
SCIENCE_EVIDENCE = {"new-data", "new-analysis", "table", "figure", "citation", "methods-text", "results-text"}
# Findings about a change that has not reached the manuscript, or a decision: their stage follows the evidence.
CONTENT_CODES = {"PROMISE_NOT_LANDED", "EARLIER_PROMISE_OPEN", "PROMISED", "LANDED_UNRESOLVED",
                 "REVISED_QUOTE_NOT_FOUND", "TBD_OPEN", "NO_COMMITMENT", "DECISION_MISSING", "REASON_MISSING"}
EVIDENCE_WORDS = {
    "new-data": "new data (an experiment, a measurement or a new cohort)",
    "new-analysis": "a new analysis of existing or public data", "table": "a new or changed table",
    "figure": "a new or changed figure", "citation": "a new or replaced reference",
    "methods-text": "new text in the Methods", "results-text": "new text in the Results",
    "discussion-text": "new text in the Discussion",
    "statement": "a statement such as data or code availability, ethics or funding",
    "wording": "a change of wording", "answer": "an answer in the letter", "acknowledge": "an acknowledgement",
}
DECISION_WORDS = {"address": "make the change", "decline": "decline", "not-on-point": "does not apply",
                  "undecided": "not decided yet"}
LOCATION_WORDS = {"resolved": "found", "unresolved": "not found", "not_assessed": "not checked"}
LABEL_NUMBER_RE = re.compile(r"^\(?(?:\d+(?:\.\d+)*[a-z]?|[a-z]|[ivx]+)[.)]?$", re.IGNORECASE)


def stage_for(code: str, evidence: list[str]) -> str:
    """When the authors can act on a finding: numbers that disagree and changed claims first; a change that has
    not landed by the kind of evidence it needs; the letter's own shape is writing; a length limit is the
    venue's."""
    if code in {"NUMBER_NOT_IN_MANUSCRIPT", "UNMENTIONED_CHANGE", "CLAIM_WIDENED"}:
        return "now"
    if code == "OVER_LIMIT":
        return "journal"
    if code in CONTENT_CODES:
        kinds = set(evidence)
        if not kinds or kinds & SCIENCE_EVIDENCE:
            return "now"
        return "final" if kinds <= {"statement"} else "writing"
    return "writing"


def _flat(text: str) -> str:
    return " ".join(text.split())


def _short(text: str, limit: int = 240) -> str:
    """A long passage cut in the middle with [...], keeping its start and end so it stays recognisable."""
    text = _flat(text)
    if len(text) <= limit:
        return text
    head = text[:int(limit * 0.6)].rsplit(" ", 1)[0]
    tail = text[-int(limit * 0.3):].split(" ", 1)[-1]
    return f"{head} [...] {tail}"


def _q(text: str, limit: int = 240) -> str:
    return "\u201c" + _short(text, limit) + "\u201d"


def _q_end(text: str, limit: int = 240) -> str:
    """A quotation that ends a sentence: a fragment's trailing comma goes, and a full stop follows unless the
    quote ends a sentence itself."""
    body = _short(text, limit).rstrip(",;: ")
    return "\u201c" + body + "\u201d" + ("" if body[-1:] in ".?!" else ".")


def _opening(text: str, words: int = 8) -> str:
    parts = _flat(text).split(" ")
    return "\u201c" + " ".join(parts[:words]).rstrip(",;:") + (" [...]" if len(parts) > words else "") + "\u201d"


def _listed(items: list[str], last: str = "and") -> str:
    items = list(dict.fromkeys(items))
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" {last} " + items[-1] if items else ""


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else many or one + 's'}"


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


_SMALL = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def _count(n: int, one: str, many: str | None = None) -> str:
    """'one check', 'three comments', '12 comments': small counts in words, for the start of a sentence."""
    return f"{_SMALL[n] if 0 <= n < len(_SMALL) else n} {one if n == 1 else many or one + 's'}"


def _quotes_end(texts: list[str]) -> str:
    """Several quotations as the end of a sentence."""
    texts = list(dict.fromkeys(texts))
    return _listed([_q(t) for t in texts[:-1]] + [_q_end(texts[-1])])


def referee_of(item: Item) -> str:
    """The referee as the journal names them, 'the editor' for the editor."""
    name = item.referee
    if not name:
        m = re.match(r"(Ed|R)(\d*)", item.id)
        name = ("Editor" if m.group(1) == "Ed" else f"Reviewer {m.group(2)}".strip()) if m else "the referee"
    return "the editor" if re.fullmatch(r"(?i)(?:the\s+)?(?:handling\s+|academic\s+|associate\s+)?editor", name) \
        else name


def comment_name(item: Item) -> str:
    """How the authors know a comment: the referee and the referee's own number ('Reviewer 1, comment 2',
    'Reviewer 2, Suggestions 2'), or the referee alone when they numbered nothing (the quote identifies it)."""
    who = _cap(referee_of(item))
    label = item.label.strip()
    if not label:
        return who
    return f"{who}, comment {label.strip('().')}" if LABEL_NUMBER_RE.match(label) else f"{who}, {label}"


def comment_ref(item: Item) -> str:
    """A comment named inside a sentence: its number, or the opening words of an unnumbered one."""
    if item.label.strip():
        name = comment_name(item)
        return name if name.startswith("Reviewer") or name.startswith("Referee") else name[:1].lower() + name[1:]
    who = referee_of(item)
    noun = "request" if who == "the editor" else "comment"
    return f"{who}'s {noun} beginning {_opening(item.comment)}"


def sentence_at(flat: str, k: int) -> str:
    """The sentence of a whitespace-flattened text that contains offset k."""
    bounds = [m.end() for m in re.finditer(r"[.!?][\"\u201d)]?\s+(?=[A-Z(\[\"\u201c])", flat)]
    start = max([0] + [b for b in bounds if b <= k])
    end = min([b for b in bounds if b > k] + [len(flat)])
    return flat[start:end].strip()


# --------------------------------------------------------------------------------------------------------
# Letter
# --------------------------------------------------------------------------------------------------------

HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
TAG_RE = re.compile(r"^\s*<!--\s*item\s*:\s*(?P<id>[^\s>]+)[^>]*-->\s*$", re.IGNORECASE)
OTHER_COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")
QUOTE_RE = re.compile(r"^\s{0,3}>\s?(.*)$")
LABEL_PREFIX_RE = re.compile(r"^\s*\**\s*(?:response|reply|answer|author(?:s'?)?\s+response)\s*\**\s*:\s*\**\s*",
                             re.IGNORECASE)


@dataclass
class Block:
    line: int
    heading: str
    tag: str | None = None
    quote: str = ""
    quote_line: int = 0
    reply: list[tuple[int, str]] = field(default_factory=list)
    inner_quotes: list[tuple[int, str]] = field(default_factory=list)
    item: Item | None = None
    quote_found: bool = False
    quote_elided: bool = False

    @property
    def reply_text(self) -> str:
        return LABEL_PREFIX_RE.sub("", "\n".join(t for _, t in self.reply).strip())

    def label(self) -> str:
        if self.item:
            return self.item.id
        if self.tag:
            return self.tag
        head = " ".join(self.quote.split())[:40]
        return f'"{head}..."' if head else "letter"


def parse_letter(text: str, is_comment: Callable[[str], bool]) -> tuple[list[Block], list[tuple[int, str, str]]]:
    """Split a Markdown letter into reply blocks and loose prose (line, heading, text)."""
    lines = text.splitlines()
    blocks: list[Block] = []
    loose: list[tuple[int, str, str]] = []
    current: Block | None = None
    heading = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        head = HEADING_RE.match(line)
        if head:
            if current:
                blocks.append(current)
            current, heading = None, head.group(1).strip()
            i += 1
            continue
        tag = TAG_RE.match(line)
        if tag:
            if current:
                blocks.append(current)
            current = Block(line=i + 1, heading=heading, tag=tag.group("id"))
            i += 1
            continue
        if QUOTE_RE.match(line):
            start, buf = i, []
            while i < len(lines):
                inner = QUOTE_RE.match(lines[i])
                if inner:
                    buf.append(inner.group(1))
                elif not lines[i].strip() and i + 1 < len(lines) and QUOTE_RE.match(lines[i + 1]):
                    buf.append("")
                else:
                    break
                i += 1
            quote = "\n".join(buf).strip()
            if current is not None and not current.quote and not current.reply:
                current.quote, current.quote_line = quote, start + 1
            elif current is not None and not is_comment(quote):
                current.inner_quotes.append((start + 1, quote))
            elif current is not None and current.quote and norm(quote) in norm(current.quote):
                pass  # the reply re-quotes part of its own comment
            else:
                if current:
                    blocks.append(current)
                current = Block(line=start + 1, heading=heading, quote=quote, quote_line=start + 1)
            continue
        if line.strip() and not OTHER_COMMENT_RE.match(line):
            if current is None:
                loose.append((i + 1, heading, line))
            else:
                current.reply.append((i + 1, line))
        i += 1
    if current:
        blocks.append(current)
    return blocks, loose


# --------------------------------------------------------------------------------------------------------
# Reply patterns
# --------------------------------------------------------------------------------------------------------

BLANKET_RE = re.compile(
    r"\b(?:revised|changed|corrected|amended|updated|modified)\s+(?:the\s+(?:manuscript|text|paper)\s+)?"
    r"accordingly\b"
    r"|\bwe\s+have\s+(?:carefully\s+)?(?:addressed|considered|incorporated|taken\s+into\s+account)\s+all\b"
    r"|\ball\s+(?:of\s+)?(?:the\s+)?(?:(?:reviewers?|referees?)'?s?\s+)?(?:minor\s+|other\s+|remaining\s+)?"
    r"(?:comments|points|concerns|suggestions|issues)\s+(?:have\s+been|were)\s+"
    r"(?:addressed|corrected|incorporated|fixed|revised|implemented)\b"
    r"|\bas\s+suggested\s+throughout\b|^\s*done\.?\s*$", re.IGNORECASE)
NO_CHANGE_RE = re.compile(
    r"\bno\s+(?:further\s+|manuscript\s+|textual\s+)?changes?\b|\b(?:did|do|have)\s+not\s+(?:change|revise|modify)"
    r"|\bunchanged\b|\bwithout\s+(?:a\s+)?change\b", re.IGNORECASE)
THANKS_RE = re.compile(r"^\s*(?:we\s+)?(?:(?:sincerely|warmly|kindly|truly|very\s+much)\s+)?"
                       r"(?:thank|are\s+(?:very\s+|most\s+|extremely\s+)?(?:grateful|thankful)|appreciate)\b",
                       re.IGNORECASE)
AGREE_RE = re.compile(r"^\s*(?:we\s+)?(?:fully\s+|completely\s+|entirely\s+|totally\s+|strongly\s+)?agree\b",
                      re.IGNORECASE)
FUTURE_RE = re.compile(
    r"\bwe\s+will\b|\bwill\s+be\s+(?:added|included|provided|revised|updated|clarified|discussed|corrected|"
    r"reported|expanded|extended)\b|\bwe\s+(?:plan|intend)\s+to\b|\bin\s+the\s+(?:final|next|camera-ready)\s+"
    r"version\b", re.IGNORECASE)
TBD_RE = re.compile(r"\[\s*TBD\b", re.IGNORECASE)
TBD_SPAN_RE = re.compile(r"\[\s*TBD\b[^\]]*\]", re.IGNORECASE)
BACKREF_RE = re.compile(r"\b(?:first|previous|earlier|last|original)\s+(?:round|revision|response|report|"
                        r"submission)\b|\bround\s+\d\b|\bin\s+our\s+(?:first|previous|earlier)\b", re.IGNORECASE)
INLINE_QUOTE_RE = re.compile(r"[\"\u201c]([^\"\u201c\u201d\n]{3,}?)[\"\u201d]")
REVISED_CUE_RE = re.compile(r"\b(?:now\s+reads?|reads\s+now|now\s+states?|revised\s+(?:text|sentence|wording)|"
                            r"new\s+(?:text|sentence)|we\s+(?:added|inserted|changed|replaced|rewrote|reworded|"
                            r"revised)|changed\s+to|reads:)", re.IGNORECASE)
OLD_CUE_RE = re.compile(r"\b(?:previously|originally|the\s+original|formerly|old\s+(?:text|sentence|wording)|"
                        r"replaced|removed|deleted|instead\s+of|changed|rather\s+than)\b", re.IGNORECASE)
LABEL_REF_RE = re.compile(r"\b(?:[Cc]omments?|[Pp]oints?|[Ii]tems?|[Qq]uestions?|[Rr]emarks?|[Rr]eviewers?|"
                          r"[Rr]eferees?|[Rr]ounds?|[Rr]esponses?|[Vv]ersions?\s+v?)\s*#?\s*\d+(?:\.\d+)*[a-z]?\b"
                          r"|\b(?:R\d+|Ed)(?:[.\-][\w()]+)+")
CITATION_RE = re.compile(r"\((?:[^()]*?\b(?:19|20)\d{2}[a-z]?\b[^()]*?)\)|\[\d+(?:\s*[-\u2013,]\s*\d+)*\]"
                         r"|\bet\s+al\.?,?\s*\(?(?:19|20)\d{2}")
URL_RE = re.compile(r"https?://\S+|\b10\.\d{4,9}/\S+")
FIRST_SENTENCE_RE = re.compile(r"^(.+?[.!?])(?=\s+[A-Z(\[\"\u201c]|\s*$)", re.DOTALL)


def first_sentence(text: str) -> str:
    guarded = re.sub(r"\b(Fig|Figs|Eq|Ref|Refs|Suppl|e\.g|i\.e|cf|vs|al|No|approx|Sect|Tab)\.", r"\1<dot>", text)
    m = FIRST_SENTENCE_RE.match(" ".join(guarded.split()))
    return (m.group(1) if m else " ".join(guarded.split())).replace("<dot>", ".")


@dataclass
class Location:
    text: str
    kind: str          # lines | page | object | section | heading | secnum
    key: object
    state: str = ""    # resolved | unresolved | not_assessed
    note: str = ""


def parse_line_list(spec: str) -> list[tuple[int, int]]:
    out = []
    for part in re.split(r"\s*(?:,|and|&)\s*", spec):
        nums = [int(n) for n in re.findall(r"\d+", part)]
        if nums:
            out.append((nums[0], nums[-1]))
    return out


def extract_locations(text: str) -> list[Location]:
    locs: list[Location] = []
    for m in LINES_RE.finditer(text):
        for a, b in parse_line_list(m.group("list")):
            locs.append(Location(m.group(0), "lines", (a, b)))
    for m in PAGES_RE.finditer(text):
        locs.append(Location(m.group(0), "page", m.group(0)))
    for m in TABFIG_RE.finditer(text):
        locs.append(Location(m.group(0), "object", _object_key(m)))
    for m in SUPPOBJ_RE.finditer(text):
        locs.append(Location(m.group(0), "object", _object_key(m)))
    for m in HEADING_REF_RE.finditer(text):
        locs.append(Location(m.group(1), "heading", norm(m.group(1))))
    for m in SECNUM_RE.finditer(text):
        locs.append(Location(m.group(0), "secnum", m.group(1)))
    for m in SECTION_RE.finditer(text):
        locs.append(Location(m.group(1), "section", m.group(1)))
    return locs


def _section_stem(name: str) -> str:
    s = norm(name).replace("acknowledgments", "acknowledgements")
    return s[:-1] if s.endswith("s") else s


NO_REVISED = "no revised manuscript was given"


def resolve(loc: Location, revised: Doc | None, extras: list[Doc], line_check: bool) -> None:
    """Set loc.state (resolved, unresolved or not_assessed) and, unless resolved, loc.note: a clause that reads
    after "names Table 9, but ..." or "was not checked because ..."."""
    if revised is None:
        loc.state, loc.note = "not_assessed", NO_REVISED
        return
    docs = [revised, *extras]
    name = revised.path.name
    if loc.kind == "page":
        loc.state, loc.note = "not_assessed", "page numbers cannot be checked in a text file"
    elif loc.kind == "lines":
        a, b = loc.key  # type: ignore[misc]
        if not line_check:
            loc.state, loc.note = "not_assessed", "the line check was switched off"
        elif a > b or a < revised.min_line or b > revised.max_line:
            loc.state = "unresolved"
            loc.note = (f"the line numbers of the revised manuscript ({name}) run from {revised.min_line} "
                        f"to {revised.max_line}")
        else:
            loc.state = "resolved"
    elif loc.kind == "object":
        kind, scope, num = loc.key  # type: ignore[misc]
        if any((kind, scope, num) in d.objects for d in docs):
            loc.state = "resolved"
        elif scope == "main" and revised.tex_counts.get(kind, 0) >= num:
            loc.state = "resolved"
        elif scope == "main" and revised.kind == "latex" and kind in revised.tex_counts:
            loc.state = "unresolved"
            loc.note = f"the revised manuscript ({name}) has only {_plural(revised.tex_counts[kind], kind)}"
        elif scope != "main" and not extras:
            loc.state, loc.note = "not_assessed", "the supplementary material was not given"
        else:
            loc.state = "unresolved"
            loc.note = ("neither the revised manuscript nor the supplements mention it" if extras
                        else "the revised manuscript does not mention it")
    elif loc.kind == "section":
        stem = _section_stem(str(loc.key))
        if not any(d.headings for d in docs):
            loc.state, loc.note = "not_assessed", "no headings were recognised in the revised manuscript"
        elif stem == "title" or any(stem in h for d in docs for h in d.headings):
            loc.state = "resolved"
        else:
            loc.state, loc.note = "unresolved", "the revised manuscript has no heading with this name"
    elif loc.kind == "heading":
        if not any(d.headings for d in docs):
            loc.state, loc.note = "not_assessed", "no headings were recognised in the revised manuscript"
        elif any(str(loc.key) in h for d in docs for h in d.headings):
            loc.state = "resolved"
        else:
            loc.state, loc.note = "unresolved", "no heading of the revised manuscript contains these words"
    elif loc.kind == "secnum":
        numbered = [h for d in docs for h in d.raw_headings if re.match(r"\d+(?:\.\d+)*\b", h)]
        if not numbered:
            loc.state, loc.note = "not_assessed", "the headings of the revised manuscript carry no numbers"
        elif any(re.match(re.escape(str(loc.key)) + r"(?:\.|\s|$)", h) for h in numbered):
            loc.state = "resolved"
        else:
            loc.state, loc.note = "unresolved", "no heading of the revised manuscript has this number"


def _unresolved(locs: list[Location]) -> str:
    """'Table 9, but the revised manuscript does not mention it; and lines 950-960, but ...'"""
    return "; and ".join(f"{_quoted_place(loc)}, but {loc.note}" for loc in locs)


def _quoted_place(loc: Location) -> str:
    return f"\u201c{loc.text}\u201d" if loc.kind == "heading" else loc.text


def _overlap(a: Location, b: Location) -> bool:
    if a.kind == b.kind == "lines":
        (a1, a2), (b1, b2) = a.key, b.key  # type: ignore[misc]
        return a1 <= b2 + 2 and b1 <= a2 + 2
    if a.kind in {"section", "heading"} and b.kind in {"section", "heading"}:
        return _section_stem(str(a.key)) == _section_stem(str(b.key))
    return a.kind == b.kind and a.key == b.key


# --------------------------------------------------------------------------------------------------------
# The check
# --------------------------------------------------------------------------------------------------------

BLOCKING = {
    "LEDGER_COMMENT_NOT_VERBATIM", "LEDGER_ORDER", "LEDGER_LINK_INVALID", "DECISION_MISSING", "REASON_MISSING", "MISSING_REPLY",
    "DUPLICATE_REPLY", "ORPHAN_REPLY", "MERGED_REPLY", "NO_REPLY_BLOCKS", "EMPTY_REPLY", "QUOTE_NOT_VERBATIM",
    "QUOTE_PARTIAL", "QUOTE_ELIDED", "QUOTE_WRONG_ITEM", "NO_QUOTE", "ORDER_MISMATCH", "NO_LOCATION", "BLANKET_REPLY",
    "PROMISE_NOT_LANDED", "EARLIER_PROMISE_OPEN", "LANDED_UNRESOLVED", "LOCATION_UNRESOLVED",
    "LOCATION_MISMATCH", "REVISED_QUOTE_NOT_FOUND", "TBD_OPEN", "ROUND_LINK_INVALID", "OVER_LIMIT",
    "CLAIM_WIDENED",
}

# (name, the question it answers for the authors, its finding codes, the input it needs, and what it looks at,
# for the sentence that says it did not run)
CHECKS: list[tuple[str, str, set[str], str | None, str]] = [
    ("ledger", "Does the ledger give each comment in the referees' own words and order?",
     {"LEDGER_COMMENT_NOT_VERBATIM", "LEDGER_ORDER", "LEDGER_LINK_INVALID", "LEDGER_VOCAB"}, None,
     "whether the ledger quotes the comments word for word"),
    ("decisions", "Does every comment have your decision, with a reason where you decline it or find that it does "
                  "not apply?", {"DECISION_MISSING", "REASON_MISSING"}, None, "your decisions"),
    ("coverage", "Does every comment have exactly one reply, and every reply a comment?",
     {"MISSING_REPLY", "DUPLICATE_REPLY", "ORPHAN_REPLY", "MERGED_REPLY", "NO_REPLY_BLOCKS", "EMPTY_REPLY"}, None,
     "whether every comment has a reply"),
    ("quotes", "Does each reply quote its comment word for word and in full?",
     {"QUOTE_NOT_VERBATIM", "QUOTE_PARTIAL", "QUOTE_WRONG_ITEM", "NO_QUOTE", "QUOTE_ELIDED"}, None,
     "how the replies quote the comments"),
    ("order", "Do the replies follow the referees' order?", {"ORDER_MISMATCH"}, None, "the order of the replies"),
    ("locations_named", "Does each reply say where the change is, or that nothing changed and why?",
     {"NO_LOCATION"}, None, "whether each reply says where the change is"),
    ("blanket", "Does every reply say what changed, rather than a general phrase such as \u201crevised "
                "accordingly\u201d?", {"BLANKET_REPLY", "BLANKET_CLAIM"}, None, "general phrases in the replies"),
    ("landed", "Is every change you committed to recorded in the ledger as made, with its place in the manuscript?",
     {"PROMISE_NOT_LANDED", "EARLIER_PROMISE_OPEN", "PROMISED", "NO_COMMITMENT"}, None,
     "whether the changes you committed to were made"),
    ("locations_resolve", "Do the places named in the replies and in the ledger exist in the revised manuscript?",
     {"LOCATION_UNRESOLVED", "LANDED_UNRESOLVED", "LOCATION_MISMATCH", "LOCATION_DIFFERS"}, "revised",
     "whether the places named in the replies and in the ledger exist in the revised manuscript"),
    ("revised_quotes", "Is the text the replies quote as revised really in the revised manuscript?",
     {"REVISED_QUOTE_NOT_FOUND"}, "revised", "the text the replies quote as revised"),
    ("numbers", "Are the numbers in the replies in the revised manuscript?", {"NUMBER_NOT_IN_MANUSCRIPT"},
     "revised", "the numbers in the replies"),
    ("placeholders", "Is every placeholder such as [TBD: ...] filled in?", {"TBD_OPEN"}, None, "placeholders"),
    ("rounds", "Are follow-up comments linked to the earlier round, and do their replies refer back to it?",
     {"ROUND_LINK_INVALID", "NO_BACK_REFERENCE"}, "rounds", "the links to earlier rounds"),
    ("guard", "Does the letter name the place of every change between the two versions of the manuscript, with no "
     "claim reaching further where a reply points?",
     {"UNMENTIONED_CHANGE", "CLAIM_WIDENED"}, "guard",
     "whether the letter names the place of every change between the two versions of the manuscript"),
    ("length", "Is each referee's section within the character limit?", {"OVER_LIMIT"}, "max_chars",
     "the length of each referee's section"),
    ("openings", "Does each reply open with the answer, not with thanks, agreement or a promise? (Advice only.)",
     {"OPENING_THANKS", "OPENING_AGREE", "FUTURE_TENSE"}, None, "how the replies open"),
]
# Checks that need a letter, and those that look only at reply blocks (not assessed when there are none).
LEDGER_CHECKS = {"ledger", "decisions", "rounds"}
REPLY_CHECKS = {"quotes", "order", "locations_named", "blanket", "openings", "locations_resolve", "revised_quotes",
                "numbers"}
SHOWN_CHANGES = 15  # changes between the versions listed per finding in the Markdown report


@dataclass
class Finding:
    code: str
    item: str
    message: str        # full sentences in plain words; the Markdown report adds the referee's comment before it
    line: int | None
    blocking: bool
    stage: str = "writing"   # now | writing | journal | final: when the authors can act on it
    details: list[dict[str, object]] = field(default_factory=list)


@dataclass
class Report:
    mode: str
    stage: str         # letter | ledger (no response letter: plan mode)
    round: int
    items: int
    blocks: int
    revised: str | None
    line_numbering: str
    findings: list[Finding] = field(default_factory=list)
    checks: list[dict[str, object]] = field(default_factory=list)
    reply_map: list[dict[str, object]] = field(default_factory=list)
    not_assessed: list[str] = field(default_factory=list)
    undecided: list[dict[str, object]] = field(default_factory=list)
    letter: str | None = None
    ledger: str = ""
    reviews: str = ""
    comments: dict[str, Item] = field(default_factory=dict)  # for the Markdown report; "N:id" for earlier rounds

    @property
    def blocking(self) -> int:
        return sum(f.blocking for f in self.findings)

    @property
    def unassessed_checks(self) -> int:
        return sum(c["state"] == "not_assessed" for c in self.checks)

    @property
    def limitation(self) -> str:
        return LEDGER_LIMITATION if self.stage == "ledger" else LIMITATION

    def to_dict(self) -> dict[str, object]:
        return {"summary": {"mode": self.mode, "stage": self.stage, "round": self.round, "ledger_items": self.items,
                            "reply_blocks": self.blocks, "letter": self.letter, "ledger": self.ledger,
                            "reviews": self.reviews, "revised": self.revised,
                            "line_numbering": self.line_numbering, "blocking": self.blocking,
                            "advisory": len(self.findings) - self.blocking,
                            "not_assessed_checks": self.unassessed_checks, "limitation": self.limitation},
                "checks": self.checks, "findings": [asdict(f) for f in self.findings],
                "undecided": self.undecided, "reply_map": self.reply_map, "not_assessed": self.not_assessed}


def out_of_order(seq: list[int]) -> set[int]:
    """Positions outside a longest increasing subsequence (earlier positions kept on ties)."""
    n = len(seq)
    length, prev = [1] * n, [-1] * n
    for i in range(n):
        for j in range(i):
            if seq[j] < seq[i] and length[j] + 1 > length[i]:
                length[i], prev[i] = length[j] + 1, j
    if not n:
        return set()
    end = max(range(n), key=lambda i: (length[i], -i))
    keep: set[int] = set()
    while end != -1:
        keep.add(end)
        end = prev[end]
    return set(range(n)) - keep


# guard.py's pattern for a numbered heading ("6. Conclusion", "5.1 Limitations", "A.2 Extra runs"), so that a
# change is placed in the same words as guard.py's own revision report
NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*|[A-Z](?:\.\d+)+|[A-Z](?=\.))\.?\s+(\S.*)$")


def _section_words(section: str, title: str | None = None) -> str:
    """guard.py's heading path in guard.py's words: 'the Results, Performance', or 'section 5.1, Limitations'
    for a numbered heading (which names its parents already), without the paper's title. Without the title in the
    report, a first heading that is not a usual section name is taken to be the title."""
    if title and section.startswith(title + " > "):
        section = section[len(title) + 3:]
    elif title and section == title:
        return "the text under the title"
    elif not title:
        parts = section.split(" > ")
        if len(parts) > 1 and not SECTION_RE.fullmatch(parts[0].strip()):
            section = " > ".join(parts[1:])
    if not section:
        return "the text before the first heading"
    numbered = NUMBERED_HEADING.match(section.split(" > ")[-1])
    if numbered:
        return f"section {numbered.group(1)}, {numbered.group(2)}"
    return "the " + section.replace(" > ", ", ")


TOKEN_NOUNS = {"number": "number", "citation": "citation", "identifier": "identifier", "url": "link"}


def change_words(c: dict[str, object]) -> str:
    """One change from guard.py's revision report, in plain words, ready to follow 'In the Results, ...'."""
    kind, change, token = str(c.get("kind")), str(c.get("change")), c.get("token")
    removed = [str(x) for x in c.get("removed") or []]  # type: ignore[union-attr]
    added = [str(x) for x in c.get("added") or []]  # type: ignore[union-attr]

    def words(xs: list[str]) -> str:
        return _listed([_q(x) for x in xs])

    if token is not None:
        verb = {"added": "is new", "removed": "was removed"}.get(change, f"changed ({change})")
        return f"the {TOKEN_NOUNS.get(kind, kind)} {_q(str(token))} {verb}"
    if kind in ("causal", "evidential"):
        what = {"raised": "the claim became stronger", "lowered": "the claim became weaker",
                "added": "a new sentence makes a claim", "removed": "a sentence that made a claim was deleted"}.get(
            change, "the strength of the claim changed")
        return what + (f" ({words(removed)} became {words(added)})" if removed and added else "")
    if kind == "generality":
        return ("wording that claims novelty or generality was added" if change in ("raised", "added")
                else "wording that claimed novelty or generality was removed") + (
            f" ({words(added or removed)})" if added or removed else "")
    if kind == "scope":
        if change == "replaced" and removed and added:
            return f"the scope qualifier {words(removed)} was replaced by {words(added)}"
        verb = "was added" if change == "added" else "was dropped"
        return f"the scope qualifier {words(added or removed)} {verb}" if added or removed else f"a scope qualifier {verb}"
    if kind == "limitation":
        verb = "was added" if change == "added" else "was dropped"
        return f"the limiting word {words(added or removed)} {verb}" if added or removed else \
            f"a limiting statement {verb}"
    if kind == "null_result":
        return "a null result is no longer stated" if change == "removed" else "a null result was added"
    if kind == "evidence_status":
        return "the wording that says how the finding was obtained changed"
    return f"the {kind.replace('_', ' ')} wording changed"


class Checker:
    def __init__(self, reviews: str, rounds: list[Round], round_number: int, letter: str | None,
                 revised: Doc | None, original: Doc | None, supplements: list[Doc], mode: Mode,
                 line_check: bool) -> None:
        self.reviews_raw = reviews
        self.reviews, self._reviews_src = fold(reviews)
        self.rounds = rounds
        current = [r for r in rounds if r.number == round_number]
        if not current:
            raise InputError(f"The ledger has no round {round_number} (its rounds: "
                             f"{', '.join(str(r.number) for r in rounds)}).")
        self.round = current[0]
        self.items = self.round.items
        self.by_id = {it.id: it for it in self.items}
        # every comment a finding can name: this round's by id, earlier rounds' as "ROUND:id"
        self.comments: dict[str, Item] = {f"{r.number}:{it.id}": it for r in rounds if r.number < round_number
                                          for it in r.items}
        self.comments.update(self.by_id)
        self.letter = letter
        self.revised, self.original, self.supplements = revised, original, supplements
        self.mode, self.line_check = mode, line_check
        self.findings: list[Finding] = []
        self.not_assessed: list[str] = []
        self.cited: list[Location] = []
        self.undecided: list[Item] = []
        self.blanket: list[Item] = []  # decisions the authors' one confirmation of the proposals covers

    def add(self, code: str, item: str, message: str, line: int | None = None, blocking: bool | None = None,
            details: list[dict[str, object]] | None = None) -> None:
        if blocking is None:
            blocking = code in BLOCKING
            if self.mode is Mode.rebuttal and code in {"QUOTE_PARTIAL", "QUOTE_ELIDED", "NO_QUOTE", "NO_LOCATION"}:
                blocking = False
        known = self.comments.get(item)
        stage = stage_for(code, known.evidence if known else [])
        self.findings.append(Finding(code, item, message, line, blocking, stage, details or []))

    def _raw(self, folded_text: str) -> str:
        """The reviews as written for a passage of their folded text (case, quotes and spacing restored)."""
        k = self.reviews.find(folded_text) if folded_text else -1
        if k < 0:
            return folded_text
        return self.reviews_raw[self._reviews_src[k]:self._reviews_src[k + len(folded_text) - 1] + 1]

    def _closest(self, text: str) -> str:
        """A sentence quoting the passage of the reviews closest to a misquoted comment."""
        ratio, near = nearest(text, self.reviews, by_words=True)
        if ratio < 0.2:
            return " No similar passage was found in the reviews."
        return f" The closest passage in the reviews reads {_q_end(self._raw(near))}"

    # -- quotes --------------------------------------------------------------------------------------
    def is_comment(self, quote: str) -> bool:
        q = _strip_quote_marks(norm(quote))
        if not q:
            return False
        if find_folded(self.reviews, quote):
            return True
        docs = [d for d in (self.revised, self.original, *self.supplements) if d]
        if any(find_folded(d.folded, quote) for d in docs):
            return False
        to_reviews = nearest(quote, self.reviews)[0]
        to_docs = max((nearest(quote, d.folded)[0] for d in docs), default=0.0)
        return to_reviews >= 0.5 and to_reviews >= to_docs

    # -- ledger --------------------------------------------------------------------------------------
    def check_ledger(self) -> None:
        offsets: list[tuple[int, Item]] = []
        last = 0
        for item in self.items:
            hit = find_folded(self.reviews, item.comment, last)
            if not hit:
                self.add("LEDGER_COMMENT_NOT_VERBATIM", item.id,
                         f"The ledger gives this comment as {_q(item.comment)}, but the reviews do not contain this "
                         f"wording.{self._closest(item.comment)} Copy the comment from the reviews word for word: "
                         "the letter quotes it from the ledger.")
                continue
            offsets.append((hit[0], item))
            last = hit[0]
            unknown = [e for e in item.evidence if e not in EVIDENCE]
            if unknown:
                self.add("LEDGER_VOCAB", item.id,
                         f"The ledger describes the work this comment needs as {_listed([_q(u) for u in unknown])}, "
                         f"which is not one of the kinds of evidence the ledger uses ({', '.join(sorted(EVIDENCE))}).",
                         blocking=False)
        for pos in sorted(out_of_order([o for o, _ in offsets])):
            item = offsets[pos][1]
            self.add("LEDGER_ORDER", item.id, "The ledger lists this comment out of the order in which the referees "
                     "wrote it. Move it to its place: the letter follows the referees' order, and the check compares "
                     "the two.")
        self._apply_confirmation()
        self._check_links()
        plan = self.letter is None
        for item in self.items:
            if item.decision == "undecided":
                self.undecided.append(item)
                if not plan:
                    cover = f" Your confirmation of the proposed decisions does not cover it: {item.not_covered}." if item.not_covered else ""
                    self.add("DECISION_MISSING", item.id, "You have not decided yet whether to make this change, to "
                             "decline it, or to explain that it does not apply. The letter cannot answer the comment "
                             f"until you decide; the check never guesses a decision.{cover}")
            elif item.decision == "decline" and not item.reason:
                self.add("REASON_MISSING", item.id, "You decided to decline this, and that is your decision, but the "
                         "ledger gives no reason for the reply to state. Add the reason as you would give it to the "
                         "referee: the study's design, its scope, access to data, or the time, cost or capacity it "
                         "would take.")
            elif item.decision == "not-on-point" and not item.reason:
                self.add("REASON_MISSING", item.id, "You decided that this comment does not apply, but the ledger "
                         "does not say why. Add the reason as you would give it to the referee, for example the "
                         "passage the comment misreads.")
            if plan:
                continue  # while planning, commitments are targets and are not expected to have landed
            if (item.decision == "address" and not item.commitments and not item.same_as
                    and not set(item.evidence) <= LETTER_ONLY_EVIDENCE):
                self.add("NO_COMMITMENT", item.id, "Your decision is to make this change, but the ledger records no "
                         "change for the check to look for in the manuscript. Record what changed and where, so that "
                         "the check can confirm it.")
            for c in item.commitments:
                if c.is_landed:
                    continue
                what = f"the change {_q(c.change)}" if c.change else "a change"
                recorded = (f"the ledger records it as {_q(c.landed)}" if c.landed
                            else "the ledger records no place for it")
                if self.mode is Mode.journal:
                    self.add("PROMISE_NOT_LANDED", item.id,
                             f"You committed to {what}, but it is not in the revised manuscript yet: {recorded}. "
                             "Make the change and record where it is; if it will not be part of this revision, take "
                             "it off the ledger's list of changes for this comment and say so in the reply.")
                else:
                    self.add("PROMISED", item.id,
                             f"You promise {what} for a later version ({recorded}). The reply must present it as a "
                             "promise and claim nothing as done.")

    def _apply_confirmation(self) -> None:
        """An item marked `confirmed: blanket` takes its proposed decision when the round records the authors' answer
        and the confirmation covers it: a change to the text, or a decline, a "does not apply" or new work that the
        question named. Otherwise it stays undecided, with the reason."""
        confirmation = self.round.confirmation
        answered = bool(_text(confirmation.get("answer")))
        named = set(_strings(confirmation.get("named")))
        for item in self.items:
            if item.confirmed != "blanket":
                continue
            decision = item.decision if item.decision != "undecided" else item.proposed
            if not answered:
                item.not_covered = "no confirmation is recorded for this round of comments"
            elif not decision:
                item.not_covered = "no decision was proposed for it"
            elif (decision != "address" or set(item.evidence) & NEW_WORK) and item.id not in named:
                kind = ("new data or a new analysis" if decision == "address" else
                        "declining it" if decision == "decline" else "finding that it does not apply")
                item.not_covered = (f"the proposal involves {kind}, which the question you confirmed has to name, "
                                    "and it did not")
            if item.not_covered:
                item.decision = "undecided"
            else:
                item.decision = decision
                self.blanket.append(item)

    def _check_links(self) -> None:
        """`same_as` names an earlier item of this round (a repeat, which takes over that item's decision);
        `sentence` names the first fragment of the referee sentence an item was split from."""
        seen: dict[str, Item] = {}
        for item in self.items:
            bad = [ref for ref in item.same_as if ref not in seen]
            if item.sentence and item.sentence not in seen and item.sentence != item.id:
                bad.append(item.sentence)
            if bad:
                self.add("LEDGER_LINK_INVALID", item.id, f"The ledger says this comment repeats or continues an "
                         f"earlier one ({', '.join(bad)}), but no earlier comment of this round has that label. Point "
                         "the link at the first comment it repeats or continues, or remove it.")
            elif item.same_as and item.decision == "undecided":
                first = seen[item.same_as[0]]
                item.decision, item.reason = first.decision, item.reason or first.reason
            seen[item.id] = item

    def check_rounds(self) -> bool:
        earlier = {r.number: {it.id: it for it in r.items} for r in self.rounds if r.number < self.round.number}
        linked = any(it.previous for it in self.items)
        if not earlier and not linked:
            return False
        for number, items in earlier.items():
            if self.mode is Mode.journal:
                for item in items.values():
                    for c in item.commitments:
                        if not c.is_landed:
                            self.add("EARLIER_PROMISE_OPEN", f"{number}:{item.id}",
                                     f"In round {number} you committed to "
                                     f"{_q(c.change) if c.change else 'a change'} for this comment, and the ledger "
                                     "never recorded it as made. Make the change now and record where it is, or say "
                                     "in this round's letter that it was not made and why.")
        for item in self.items:
            for ref in item.previous:
                m = PREVIOUS_RE.match(ref)
                if not m:
                    self.add("ROUND_LINK_INVALID", item.id, f"The ledger links this comment to an earlier round as "
                             f"{_q(ref)}, which is not in the form round:label (for example 1:R2.P1).")
                    continue
                number, ref_id = int(m.group(1)), m.group(2)
                if number >= self.round.number or ref_id not in earlier.get(number, {}):
                    self.add("ROUND_LINK_INVALID", item.id, f"The ledger links this comment to {ref}, but no comment "
                             "of an earlier round in the ledger has that label. Link it to the comment it follows up, "
                             "or remove the link; never invent one.")
        return True

    # -- letter --------------------------------------------------------------------------------------
    def map_blocks(self, blocks: list[Block]) -> None:
        merged_into: dict[str, str] = {}
        for block in blocks:
            span = ""
            if block.quote:
                hit = find_folded(self.reviews, block.quote)
                block.quote_found = bool(hit)
                block.quote_elided = bool(hit and hit[2])
                span = self.reviews[hit[0]:hit[1]] if hit else ""
            if block.tag:
                block.item = self.by_id.get(block.tag)
                if block.item is None:
                    self.add("ORPHAN_REPLY", block.tag, f"A reply in the response letter (line {block.line}) is "
                             f"tagged for {block.tag}, which is not a comment of this round in the ledger. Correct the "
                             "tag, or remove the reply if it answers nothing.", block.line)
                    continue
                if not block.quote:
                    self.add("NO_QUOTE", block.item.id, f"The reply in the response letter (line {block.line}) does "
                             "not quote the comment. Put the referee's words above the reply as a block quote, so "
                             "that the referee sees which point it answers.", block.line)
                elif not block.quote_found:
                    self._not_verbatim(block, block.item)
                elif block.quote_elided:
                    if self._elided_from(block.quote, span, block.item):
                        self._elided(block)
                    else:
                        self._wrong_item(block, block.item)
                else:
                    self._check_quote_matches_item(block, block.item)
                continue
            if not block.quote:
                continue
            q = _strip_quote_marks(norm(block.quote))
            if block.quote_elided:
                elided = [it for it in self.items if self._elided_from(block.quote, span, it)]
                if elided:
                    block.item = elided[0]
                    self._elided(block)
                    continue
            contained = [it for it in self.items if _strip_quote_marks(norm(it.comment)) in q]
            if contained:
                block.item = contained[0]
                for other in contained[1:]:
                    merged_into[other.id] = contained[0].id
                    self.add("MERGED_REPLY", other.id, f"This comment is answered inside the reply to "
                             f"{comment_ref(contained[0])} ({contained[0].id}) in the response letter (line "
                             f"{block.quote_line}). The ledger lists the two separately because different actions "
                             "satisfy them; give each its own reply.", block.quote_line)
                if not block.quote_found:
                    self._not_verbatim(block, block.item)
                continue
            partial = [it for it in self.items if q and q in norm(it.comment)] if block.quote_found else []
            if partial:
                block.item = partial[0]
                self._partial(block, block.item)
                continue
            scored = sorted(((SequenceMatcher(None, q, norm(it.comment), autojunk=False).ratio(), it.index, it)
                             for it in self.items), key=lambda t: (-t[0], t[1]))
            if scored and scored[0][0] >= 0.6:
                block.item = scored[0][2]
                if block.quote_found:
                    self._wrong_item(block, block.item)
                else:
                    self._not_verbatim(block, block.item)
                continue
            self.add("ORPHAN_REPLY", block.label(), f"A reply in the response letter (line {block.quote_line}) quotes "
                     f"{_q(block.quote)}, which matches none of the referees' comments in the ledger."
                     + ("" if block.quote_found else self._closest(block.quote)), block.quote_line)
        self._coverage(blocks, merged_into)

    @staticmethod
    def _elided_from(quote: str, span: str, item: Item) -> bool:
        """An elided quote belongs to an item when it spans the item's comment or is cut from inside it."""
        comment = _strip_quote_marks(norm(item.comment))
        return comment in span or find_folded(comment, quote) is not None

    def _elided(self, block: Block) -> None:
        assert block.item is not None
        self.add("QUOTE_ELIDED", block.item.id, f"The reply in the response letter (line {block.quote_line}) leaves "
                 f"part of the referee's text out: {_q_end(block.quote)} Quote the comment in full; a cut can drop "
                 "half of a request.", block.quote_line)

    def _not_verbatim(self, block: Block, item: Item) -> None:
        self.add("QUOTE_NOT_VERBATIM", item.id, f"The reply in the response letter (line {block.quote_line}) quotes "
                 f"the comment as {_q(block.quote)}, which is not the referee's wording.{self._closest(block.quote)} "
                 "Quote the comment exactly as written: a referee who does not recognise their own point may say "
                 "that it was not answered.", block.quote_line)

    def _wrong_item(self, block: Block, item: Item) -> None:
        self.add("QUOTE_WRONG_ITEM", item.id, f"The reply in the response letter (line {block.quote_line}) is meant "
                 f"for this comment but quotes another passage of the reviews: {_q_end(block.quote)} Quote this "
                 "comment, or move the reply to the comment it quotes.", block.quote_line)

    def _partial(self, block: Block, item: Item) -> None:
        self.add("QUOTE_PARTIAL", item.id, f"The reply in the response letter (line {block.quote_line}) quotes only "
                 f"part of the comment: {_q_end(block.quote)} Quote the whole comment.", block.quote_line)

    def _check_quote_matches_item(self, block: Block, item: Item) -> None:
        q = _strip_quote_marks(norm(block.quote))
        c = _strip_quote_marks(norm(item.comment))
        if c in q:
            return
        if q in c:
            self._partial(block, item)
        else:
            self._wrong_item(block, item)

    def _coverage(self, blocks: list[Block], merged_into: dict[str, str]) -> None:
        if not blocks:
            self.add("NO_REPLY_BLOCKS", "letter", "The response letter has no replies the check could pair with the "
                     "referees' comments: no reply is tagged with a comment's label, and none quotes a comment above "
                     "it. Nothing in the letter could be checked against the ledger.")
            return
        first: dict[str, Block] = {}
        for block in blocks:
            if block.item is None:
                continue
            if block.item.id in first:
                self.add("DUPLICATE_REPLY", block.item.id, f"The response letter answers this comment twice (lines "
                         f"{first[block.item.id].line} and {block.line}). Keep one reply.", block.line)
            else:
                first[block.item.id] = block
        for item in self.items:
            if item.id not in first and item.id not in merged_into:
                self.add("MISSING_REPLY", item.id, "The response letter has no reply to this comment. Add one, in its "
                         "place in the referees' order.")
        ordered = sorted(first.values(), key=lambda b: b.line)
        for pos in sorted(out_of_order([b.item.index for b in ordered if b.item])):
            block = ordered[pos]
            assert block.item is not None
            after = ordered[pos + 1].item if pos + 1 < len(ordered) else None
            before = ordered[pos - 1].item if pos else None
            if after is not None and after.index < block.item.index:
                where = f"before the reply to {comment_ref(after)}, which comes earlier in the reviews"
            elif before is not None and before.index > block.item.index:
                where = f"after the reply to {comment_ref(before)}, which comes later in the reviews"
            else:
                where = "out of the referees' order"
            self.add("ORDER_MISMATCH", block.item.id, f"The reply in the response letter (line {block.line}) stands "
                     f"{where}. Move it so that the replies follow the order of the referees' comments.", block.line)

    def check_block(self, block: Block) -> dict[str, object]:
        item = block.item
        label = block.label()
        reply = block.reply_text
        flat = _flat(reply)
        at = f"The reply in the response letter (line {block.line})"
        row: dict[str, object] = {"item": label, "decision": item.decision if item else "", "letter_line": block.line,
                                  "locations": [], "landed": [c.landed for c in item.commitments] if item else []}
        if not reply:
            if block.quote:
                self.add("EMPTY_REPLY", label, f"The response letter quotes this comment (line {block.quote_line}) "
                         "but gives no reply under it.", block.quote_line)
            return row
        tbd = TBD_RE.search(flat)
        if tbd:
            span = TBD_SPAN_RE.match(flat, tbd.start())
            placeholder = span.group(0) if span else flat[tbd.start():tbd.start() + 80]
            self.add("TBD_OPEN", label, f"{at} still holds a placeholder: {_q_end(placeholder)} Fill it in with the "
                     "result or decision it waits for, or remove it.", block.line)
        locations = extract_locations(reply)
        has_location = bool(locations)
        no_change = bool(NO_CHANGE_RE.search(reply))
        needs_location = item is not None and item.decision == "address" and bool(item.commitments)
        blanket = BLANKET_RE.search(flat)
        if blanket and not has_location:
            self.add("BLANKET_REPLY", label, f"{at} reads {_q(sentence_at(flat, blanket.start()))}, a general phrase "
                     "that names no place in the manuscript. Say what changed and where.", block.line)
        elif not has_location and needs_location:
            self.add("NO_LOCATION", label, f"{at} does not say where the change is in the revised manuscript. Name "
                     "the section, with the lines, table or figure.", block.line)
        elif not has_location and not no_change:
            self.add("NO_LOCATION", label, f"{at} names no place in the revised manuscript and does not say that "
                     "nothing changed. Name where the change is, or say that nothing changed and why.", block.line)
        first = first_sentence(reply)
        if THANKS_RE.match(first) and not re.search(r"[;:]|\d|,\s+(?:and\s+)?we\b", first):
            self.add("OPENING_THANKS", label, f"{at} opens with thanks alone: {_q_end(first)} Put the answer first "
                     "and keep thanks to a clause.", block.line, blocking=False)
        else:
            rest = re.sub(r"^.*?\bfor\s+[^,;]*[,;]\s*", "", first, count=1) if THANKS_RE.match(first) else first
            if AGREE_RE.match(rest):
                self.add("OPENING_AGREE", label, f"{at} opens with agreement: {_q_end(first)} Open with the fact or "
                         "the change instead.", block.line, blocking=False)
        unlanded = item is not None and any(not c.is_landed for c in item.commitments)
        if self.mode is Mode.journal and not unlanded:
            future = FUTURE_RE.search(flat)
            if future:
                self.add("FUTURE_TENSE", label, f"{at} describes the change as still to come: "
                         f"{_q_end(sentence_at(flat, future.start()))} In a journal revision the change should already "
                         "be in the manuscript; if it is not, record it in the ledger as not yet made.", block.line,
                         blocking=False)
        if item is not None and item.previous and not BACKREF_RE.search(reply):
            self.add("NO_BACK_REFERENCE", label, f"This comment follows up a comment of an earlier round, but {at[0].lower()}"
                     f"{at[1:]} does not refer back to what that round did. Say briefly what was done then and what "
                     "is new now.", block.line, blocking=False)

        # locations
        for loc in locations:
            resolve(loc, self.revised, self.supplements, self.line_check)
        self.cited.extend(loc for loc in locations if loc.state == "resolved")
        seen: dict[tuple[str, str], Location] = {}
        for loc in locations:
            seen.setdefault((loc.text, loc.state), loc)
        row["locations"] = [{"text": loc.text, "state": loc.state, "note": loc.note} for loc in seen.values()]
        bad = [loc for loc in locations if loc.state == "unresolved"]
        if bad:
            self.add("LOCATION_UNRESOLVED", label, f"{at} names {_unresolved(bad)}.", block.line)
        who = (f"The reply to {comment_ref(item)} ({item.id})" if item
               else f"A reply in the response letter (line {block.line})")
        unchecked: dict[str, list[str]] = {}
        for loc in seen.values():
            # without a revised manuscript no place is checked, and the summary says so once
            if loc.state == "not_assessed" and loc.note != NO_REVISED:
                unchecked.setdefault(loc.note, []).append(_quoted_place(loc))
        for note, places in unchecked.items():
            self.not_assessed.append(f"{who} names {_listed(places)}; {'that was' if len(places) == 1 else 'these were'}"
                                     f" not checked, because {note}.")
        if item is not None and self.revised is not None and not unlanded:
            landed = [c.landed for c in item.commitments if c.is_landed]
            landed_locs = [loc for text in landed for loc in extract_locations(text)]
            if locations and landed_locs and not any(_overlap(a, b) for a in locations for b in landed_locs):
                self.add("LOCATION_DIFFERS", label, f"{at} names {_listed([_quoted_place(x) for x in seen.values()])}, "
                         f"but the ledger records the change at {_listed([_q(t) for t in landed])}. One of the two is "
                         "out of date.", block.line, blocking=False)

        # quoted revised text
        quote_spans: list[tuple[int, int]] = []
        if self.revised is not None:
            quote_spans = self._check_revised_quotes(block, label, reply)
            line_ranges = [loc for loc in locations if loc.kind == "lines" and loc.state == "resolved"]
            if quote_spans and line_ranges and not any(
                    a <= hi and lo <= b for (lo, hi) in quote_spans for (a, b) in (r.key for r in line_ranges)):
                spans = _listed([f"lines {lo}-{hi}" if hi > lo else f"line {lo}" for lo, hi in quote_spans])
                cited = _listed([r.text for r in line_ranges])
                self.add("LOCATION_MISMATCH", label, f"{at} cites {cited}, but the revised text it quotes is at "
                         f"{spans} of the revised manuscript. Correct the line numbers.", block.line)
            self._check_numbers(block, label, reply)
        return row

    def _check_revised_quotes(self, block: Block, label: str, reply: str) -> list[tuple[int, int]]:
        assert self.revised is not None
        spans: list[tuple[int, int]] = []
        candidates: list[tuple[int, str, bool]] = [(line, q, True) for line, q in block.inner_quotes]
        flat = " ".join(reply.split())
        for m in INLINE_QUOTE_RE.finditer(flat):
            text = m.group(1)
            if len(text.split()) < 6:
                continue
            before = flat[max(0, m.start() - 120):m.start()]
            if find_folded(self.reviews, text):
                continue
            if OLD_CUE_RE.search(before) and self.original and find_folded(self.original.folded, text):
                continue
            candidates.append((block.line, text, bool(REVISED_CUE_RE.search(before))))
        for line, text, firm in candidates:
            hit = find_folded(self.revised.folded, text)
            if hit:
                spans.append((self.revised.line_of(hit[0]), self.revised.line_of(hit[1] - 1)))
                continue
            if any(find_folded(d.folded, text) for d in self.supplements):
                continue
            in_original = bool(self.original and find_folded(self.original.folded, text))
            why = ("that is the original wording, which the revised manuscript no longer contains" if in_original
                   else "neither the revised manuscript nor the reviews contain it")
            self.add("REVISED_QUOTE_NOT_FOUND", label, f"The reply in the response letter (line {line}) quotes "
                     f"{_q(text)} as revised text, but {why}. Quote the manuscript as it now stands, or make the "
                     "change the quote describes.", line, blocking=firm)
        return spans

    def _check_numbers(self, block: Block, label: str, reply: str) -> None:
        assert self.revised is not None
        flat = _flat(reply)
        text = flat
        for rx in (URL_RE, TBD_SPAN_RE, CITATION_RE, LINES_RE, PAGES_RE, TABFIG_RE, SUPPOBJ_RE, SECNUM_RE,
                   LABEL_REF_RE):
            text = rx.sub(lambda m: " " * len(m.group(0)), text)  # keep offsets, so sentences can be quoted
        for m in list(INLINE_QUOTE_RE.finditer(text)):
            if find_folded(self.reviews, m.group(1)) or find_folded(self.revised.folded, m.group(1)):
                text = text[:m.start()] + " " * len(m.group(0)) + text[m.end():]
        found: dict[str, dict[str, object]] = {}
        for m in NUM_RE.finditer(text):
            value = number_value(m.group(0))
            if value is None or _has_number(value, self.revised.values, self.revised.words):
                continue
            if any(_has_number(value, d.values, d.words) for d in self.supplements):
                continue
            where = "original" if self.original and _has_number(value, self.original.values,
                                                                  self.original.words) else "none"
            found.setdefault(m.group(0), {"number": m.group(0), "found_in": where,
                                          "sentence": sentence_at(flat, m.start())})
        if not found:
            return
        missing = [d["number"] for d in found.values() if d["found_in"] == "none"]
        stale = [d["number"] for d in found.values() if d["found_in"] == "original"]
        parts = []
        if missing:
            parts.append(f"{_listed([str(x) for x in missing])}, which the revised manuscript does not contain")
        if stale:
            parts.append(f"{_listed([str(x) for x in stale])}, which only the original manuscript contains")
        sentences = [str(d["sentence"]) for d in found.values()]
        self.add("NUMBER_NOT_IN_MANUSCRIPT", label, f"The reply in the response letter (line {block.line}) gives "
                 f"{'; and '.join(parts)}. It reads {_quotes_end(sentences)} Correct the reply, add the "
                 "result to the manuscript, or say in the reply that it is reported in the letter only.", block.line,
                 details=list(found.values()))

    def check_loose(self, loose: list[tuple[int, str, str]]) -> None:
        for line, _, text in loose:
            for loc in extract_locations(text):
                resolve(loc, self.revised, self.supplements, self.line_check)
                if loc.state == "resolved":
                    self.cited.append(loc)
            tbd = TBD_RE.search(text)
            if tbd:
                span = TBD_SPAN_RE.match(text, tbd.start())
                placeholder = span.group(0) if span else text[tbd.start():tbd.start() + 80]
                self.add("TBD_OPEN", "letter", f"The response letter still holds a placeholder (line {line}): "
                         f"{_q_end(placeholder)} Fill it in or remove it.", line)
            blanket = BLANKET_RE.search(text)
            if blanket:
                self.add("BLANKET_CLAIM", "letter", f"The response letter says {_q(text)} (line {line}). That is true "
                         "only if every comment has a reply and every change you committed to is in the manuscript.",
                         line, blocking=False)

    def check_length(self, max_chars: int) -> None:
        sections: dict[str, int] = {}
        heading = ""
        for line in (self.letter or "").splitlines():
            h = HEADING_RE.match(line)
            if h:
                heading = h.group(1).strip()
                continue
            if heading and re.search(r"(?i)review|referee|\bR\d|editor", heading) and not OTHER_COMMENT_RE.match(line):
                sections[heading] = sections.get(heading, 0) + len(line.strip()) + (1 if line.strip() else 0)
        if not sections:
            self.not_assessed.append("The character limit was not checked, because the letter has no referee "
                                     "headings to count under.")
        for heading, chars in sections.items():
            if chars > max_chars:
                self.add("OVER_LIMIT", heading, f"The letter's section {_q(heading)} has {chars:,} characters, and "
                         f"the limit is {max_chars:,}. Shorten it, keeping at least a line for every question.")

    def _covered(self, line: int | None, section: str) -> bool:
        """True when a location the letter names (a cited line range, a table or figure, or a quoted
        subsection heading) contains this line of the revised manuscript. Deleted text has no line there: it
        counts as mentioned when the letter cites lines inside the same section, where its rewrite would sit."""
        if self.revised is None:
            return False
        heading = norm(section.split(">")[-1]).strip() if section else ""
        span = self.revised.section_span(heading) if line is None and heading else None
        for loc in self.cited:
            if loc.kind == "heading" and heading and heading == loc.key:
                return True
            if loc.kind == "lines":
                a, b = loc.key  # type: ignore[misc]
                if (a <= line <= b) if line is not None else bool(span and a <= span[1] and span[0] <= b):
                    return True
            in_object = line is not None and loc.kind == "object"
            if in_object and line in self.revised.object_lines.get(loc.key, set()):  # type: ignore[arg-type]
                return True
        return False

    def reconcile_guard(self, path: Path) -> tuple[str, bool]:
        """Check each change guard.py lists between ORIGINAL and REVISED against the letter. Returns a note for
        the authors and whether the comparison could be made at all."""
        try:
            data = json.loads(read_text(path))
        except json.JSONDecodeError as exc:
            raise InputError(f"{path} is not valid JSON ({exc.msg}).") from exc
        if not isinstance(data, dict) or not isinstance(data.get("protected"), dict):
            raise InputError(f"{path} is not a guard.py report; run guard.py ORIGINAL REVISED --revision --json FILE.")
        letter_fold = norm(self.letter or "")
        quoted = [norm(m.group(1)) for m in INLINE_QUOTE_RE.finditer(" ".join((self.letter or "").split()))]
        changes = data.get("sentence_changes")
        title = str(data["title"]) if data.get("title") else None
        if isinstance(changes, list):
            if self.revised is not None and self.revised.printed:
                return ("the comparison of the two versions counts the lines of the files, but the revised "
                        "manuscript carries printed line numbers, so its changes could not be matched with the places "
                        "the letter names; read the comparison against the letter by hand", False)
            uncovered: dict[str, list[dict[str, object]]] = {"claim": [], "token": []}
            widened: list[dict[str, object]] = []  # an existing claim that now reaches further
            for c in changes:
                if not isinstance(c, dict) or c.get("severity") != "protected" or c.get("authorised"):
                    continue
                token = c.get("token")
                where = c.get("after_line")
                section = str(c.get("section") or "")
                entry = {
                    "section": _section_words(section, title), "line": where if isinstance(where, int) else None,
                    "original_line": c.get("before_line"), "kind": c.get("kind"), "change": c.get("change"),
                    "token": token, "before": str(c.get("before") or ""), "after": str(c.get("after") or ""),
                    "description": change_words(c)}
                if token is None and where is not None and c.get("before") and c.get("after"):
                    # Naming a place accounts for new text and numbers there, not for an existing claim that now
                    # reaches further; nor does leaving it unmentioned.
                    widened.append(entry)
                    continue
                if self._covered(where if isinstance(where, int) else None, section):
                    continue
                before = norm(str(c.get("before") or ""))
                if where is None and before and any(len(q.split()) >= 3 and q in before for q in quoted):
                    continue  # deleted text that the letter quotes
                if token is not None and norm(str(token)) in letter_fold and where is None:
                    continue
                uncovered["token" if token is not None else "claim"].append(entry)
            if widened:
                one = len(widened) == 1
                self.add("CLAIM_WIDENED", "manuscript",
                         f"{_cap(_count(len(widened), 'claim'))} of the original version now "
                         f"{'reaches' if one else 'reach'} further: a stronger verb, wider wording, or a dropped "
                         "limit, scope or null result. A reply that names the place does not account for that. "
                         "Restore the original wording unless a referee asked for the stronger claim; if one did, "
                         "the reply should say so.", details=widened)
            for kind, entries in uncovered.items():
                if entries:
                    what = ("what a claim says (its strength, scope or limits)" if kind == "claim"
                            else "a number, citation or identifier")
                    self.add("UNMENTIONED_CHANGE", "manuscript", f"{_cap(_count(len(entries), 'change'))} to {what} "
                             f"{'sits' if len(entries) == 1 else 'sit'} where no reply or summary in the letter names "
                             "the place. Each is either a change the letter should mention or one nobody asked for.",
                             blocking=False, details=entries)
            return "", True
        # an older guard.py report: whole-text counts only
        letter_values = number_values(self.letter or "")
        for category in ("numbers", "citations", "identifiers", "urls"):
            change = data["protected"].get(category) or {}
            missing = []
            for token in [*(change.get("added") or {}), *(change.get("removed") or {})]:
                values = number_values(token) if category == "numbers" else set()
                mentioned = (bool(values) and all(any(abs(v - w) < 1e-9 for w in letter_values) for v in values)
                             if category == "numbers" else norm(token) in letter_fold)
                if not mentioned:
                    missing.append(token)
            if missing:
                shown = ", ".join(_q(t) for t in missing[:SHOWN_CHANGES]) + (
                    f" and {len(missing) - SHOWN_CHANGES} more" if len(missing) > SHOWN_CHANGES else "")
                noun = "links" if category == "urls" else category
                self.add("UNMENTIONED_CHANGE", "manuscript", f"These {noun} changed between the two versions of the "
                         f"manuscript, but the letter does not mention them: {shown}.", blocking=False,
                         details=[{"category": category, "token": t} for t in missing])
        return ("the comparison of the two versions was of an older kind without sentences, so only its changed "
                "numbers, citations and identifiers were matched against the letter", True)


def run(reviews: Path, ledger: Path, letter: Path | None = None, *, revised: Path | None = None,
        original: Path | None = None, supplements: tuple[Path, ...] | list[Path] = (),
        round_number: int | None = None, mode: Mode | str = Mode.journal, line_check: bool = True,
        guard_json: Path | None = None, max_chars: int | None = None) -> Report:
    """Check a response letter, or with no letter (plan mode) the ledger alone."""
    mode = Mode(mode)
    if letter is None:
        given = [name for name, value in (("--revised", revised), ("--original", original),
                                          ("--supplement", supplements), ("--guard-json", guard_json),
                                          ("--max-chars", max_chars)) if value]
        if given:
            raise InputError(f"{', '.join(given)} need a response letter; without one only the ledger is checked.")
    rounds = load_ledger(ledger)
    number = round_number if round_number is not None else rounds[-1].number
    revised_doc = load_doc(revised) if revised else None
    original_doc = load_doc(original) if original else None
    supp_docs = [load_doc(p) for p in supplements]
    letter_text = read_text(letter) if letter is not None else None
    checker = Checker(read_text(reviews), rounds, number, letter_text, revised_doc, original_doc, supp_docs,
                      mode, line_check)
    checker.check_ledger()
    has_rounds = checker.check_rounds()
    blocks: list[Block] = []
    reply_map: list[dict[str, object]] = []
    guard_note, guard_ran = "", True
    if letter_text is not None:
        blocks, loose = parse_letter(letter_text, checker.is_comment)
        checker.map_blocks(blocks)
        reply_map = [checker.check_block(b) for b in blocks]
        checker.check_loose(loose)
        if max_chars:
            checker.check_length(max_chars)
        if guard_json:
            guard_note, guard_ran = checker.reconcile_guard(guard_json)

    if revised_doc is not None:
        for item in checker.items:
            for c in item.commitments:
                if not c.is_landed:
                    continue
                locs = extract_locations(c.landed)
                for loc in locs:
                    resolve(loc, revised_doc, supp_docs, line_check)
                bad = [loc for loc in locs if loc.state == "unresolved"]
                if bad:
                    what = f"the change {_q(c.change)}" if c.change else "a change"
                    checker.add("LANDED_UNRESOLVED", item.id, f"The ledger records {what} as made at "
                                f"{_q(c.landed)}, but "
                                + "; and ".join(f"for {_quoted_place(loc)} {loc.note}" for loc in bad)
                                + ". Record where the change really is, or make it.")

    findings = checker.findings
    reasons = {
        "revised": None if revised_doc else NO_REVISED,
        "rounds": None if has_rounds else "not applicable: first round with no links to earlier rounds",
        "guard": (None if guard_ran else guard_note) if guard_json else (
            "no comparison of the two versions of the manuscript was given (guard.py's revision report, passed "
            "with --guard-json)"),
        "max_chars": None if max_chars else "no character limit was given",
    }
    no_blocks = "the letter has no replies the check could pair with a comment"
    checks: list[dict[str, object]] = []
    unrun: dict[str, list[str]] = {}  # reason -> what the check did not look at
    for name, question, codes, needs, subject in CHECKS:
        reason = reasons.get(needs) if needs else None
        if reason and needs in {"rounds", "max_chars"}:
            continue
        hits = [f for f in findings if f.code in codes]
        if letter_text is None and name not in LEDGER_CHECKS and not hits:
            continue  # plan mode: the letter checks do not apply, as the header says
        if not blocks and name in REPLY_CHECKS:
            reason = reason or no_blocks
        if reason and not hits:
            checks.append({"check": name, "description": question, "state": "not_assessed", "problems": 0,
                           "detail": reason})
            unrun.setdefault(reason, []).append(subject)
            continue
        notes = []
        if name == "guard" and guard_note:
            notes.append(_cap(guard_note) + ".")
        if name == "decisions" and checker.blanket:
            n = len(checker.blanket)
            notes.append(f"{_cap(_count(n, 'decision'))} {'comes' if n == 1 else 'come'} from your one confirmation of the "
                         "proposed decisions.")
        if name == "decisions" and letter_text is None and checker.undecided:
            n = len(checker.undecided)
            notes.append(f"{_cap(_count(n, 'comment'))} still {'waits' if n == 1 else 'wait'} for your decision, as "
                         "expected while planning; they are listed above.")
        if name == "rounds" and letter_text is None:
            notes.append("Only the links were checked, since there are no replies yet.")
        detail = " ".join(([f"{_plural(len(hits), 'problem')}."] if hits else []) + notes)
        checks.append({"check": name, "description": question, "state": "fail" if hits else "pass",
                       "problems": len(hits), "detail": detail})
    unrun_sentences = []
    for reason, subjects in unrun.items():
        if reason == NO_REVISED and letter_text is not None and mode is Mode.journal:
            unrun_sentences.insert(0, "No revised manuscript was given, so the places, the quoted revised text and the "
                                      "numbers in the replies were not checked; this is not a complete check of a "
                                      "journal revision.")
        else:
            unrun_sentences.append(f"The check did not look at {_listed(subjects)}, because {reason}.")
    checker.not_assessed[:0] = unrun_sentences
    comments = checker.comments
    rank = {code: k for k, (_, _, codes, _, _) in enumerate(CHECKS) for code in codes}
    findings.sort(key=lambda f: (STAGE_RANK.get(f.stage, 9), not f.blocking,
                                 not (f.item in comments and comments[f.item].must_fix), rank.get(f.code, 99),
                                 f.line if f.line is not None else 10 ** 9, f.code))
    numbering = ("printed line numbers" if revised_doc and revised_doc.printed else
                 "file lines" if revised_doc else "n/a")
    undecided = [{"id": it.id, "referee": it.referee, "label": it.label, "comment": it.comment,
                  "must_fix": it.must_fix, "hand_to": it.hand_to, "evidence": it.evidence,
                  "proposed": it.proposed, "not_covered": it.not_covered,
                  "stage": stage_for("DECISION_MISSING", it.evidence)} for it in checker.undecided]
    report = Report(mode=mode.value, stage="ledger" if letter_text is None else "letter", round=number,
                    items=len(checker.items), blocks=sum(1 for b in blocks if b.item or b.tag or b.quote),
                    revised=str(revised) if revised else None, line_numbering=numbering, findings=findings,
                    checks=checks, reply_map=reply_map, not_assessed=list(dict.fromkeys(checker.not_assessed)),
                    undecided=undecided, letter=letter.name if letter else None, ledger=ledger.name,
                    reviews=reviews.name, comments=comments)
    return report


# --------------------------------------------------------------------------------------------------------
# The Markdown report: what the authors read
# --------------------------------------------------------------------------------------------------------

def _lead(f: Finding, report: Report) -> str:
    """The referee's comment a finding is about, by the referee's own number and quoted; empty for findings
    about the letter or the manuscript as a whole, whose message names its subject."""
    item = report.comments.get(f.item)
    if item is None:
        return ""
    name = comment_name(item) + (f", round {item.round}" if ":" in f.item else "")
    if f.code == "LEDGER_COMMENT_NOT_VERBATIM":  # the message quotes the ledger's wording and the reviews'
        return f"**{name}** ({f.item})."
    if f.code == "QUOTE_NOT_VERBATIM" and "closest passage" in f.message:
        return f"**{name}** ({f.item})."
    return f"**{name}** ({f.item}): {_q_end(item.comment)}"


def _change_line(d: dict[str, object]) -> str:
    if "description" not in d:
        return ""
    section = str(d.get("section") or "the text before the first heading")
    if d.get("line") is not None:
        place = f"In {section} (line {d['line']} of the revised manuscript)"
        text = str(d.get("after") or d.get("before") or "")
    else:
        place = f"In {section} (a sentence deleted from line {d.get('original_line')} of the original)"
        text = str(d.get("before") or "")
    return f"{place}, {d['description']}" + (f": {_q_end(text)}" if text else ".")


def _finding_lines(f: Finding, report: Report) -> list[str]:
    lead = _lead(f, report)
    advice = "" if f.blocking else " This is advice; the check does not stop on it."
    lines = [f"- {lead + ' ' if lead else ''}{f.message}{advice}"]
    changes = [_change_line(d) for d in f.details]
    changes = [c for c in changes if c]
    lines += [f"  - {c}" for c in changes[:SHOWN_CHANGES]]
    if len(changes) > SHOWN_CHANGES:
        lines.append(f"  - {_cap(_count(len(changes) - SHOWN_CHANGES, 'more change'))} of this kind "
                     f"{'is' if len(changes) - SHOWN_CHANGES == 1 else 'are'} listed in the comparison of the two "
                     "versions (guard.py's revision report).")
    return lines


def _decision_lines(u: dict[str, object], report: Report) -> list[str]:
    item = report.comments.get(str(u["id"]))
    if item is None:
        return [f"- {u['id']}"]
    out = f"- **{comment_name(item)}** ({item.id}): {_q_end(item.comment)}"
    kinds = [EVIDENCE_WORDS[e] for e in item.evidence if e in EVIDENCE_WORDS]
    if kinds:
        out += f" It asks for {_listed(kinds)}."
    if item.must_fix:
        out += (" The ledger marks it as essential: the editor made it a condition, or it questions the paper's "
                "validity.")
    if item.hand_to:
        out += f" Draft its reply with {_listed(item.hand_to)}."
    if item.proposed:
        out += f" The plan proposes: {DECISION_WORDS[item.proposed]}."
    if item.not_covered:
        out += f" Your confirmation of the proposed decisions does not cover it: {item.not_covered}."
    return [out]


def _answer(c: dict[str, object]) -> str:
    if c["state"] == "pass":
        note = str(c.get("detail") or "")
        return "Yes." + (f" {note}" if note else "")
    if c["state"] == "fail":
        n = int(c.get("problems") or 0)  # type: ignore[call-overload]
        return f"No, {_plural(n, 'problem')} listed above."
    return f"Not checked, because {c['detail']}."


def _place_cell(row: dict[str, object]) -> str:
    places = [f"\u201c{p['text']}\u201d ({LOCATION_WORDS.get(str(p['state']), p['state'])})"
              for p in row["locations"]]  # type: ignore[union-attr]
    return "; ".join(places) or "none named"


def to_markdown(report: Report) -> str:
    if report.stage == "ledger":
        n_open = len(report.undecided)
        waiting = ("every one has your decision" if not n_open else
                   f"{_SMALL[n_open] if n_open < len(_SMALL) else n_open} of them still "
                   f"{'waits' if n_open == 1 else 'wait'} for your decision")
        lines = ["# Review-ledger check", "",
                 f"This check read the ledger {report.ledger} (your revision plan) for round {report.round} against "
                 f"the referees' comments in {report.reviews}. The ledger lists "
                 f"{_count(report.items, 'comment')}, and {waiting}. There is no response letter yet, so no "
                 "reply, no place in the manuscript and no change you committed to was checked; run the check again "
                 "with the letter before sending it.", ""]
    else:
        kind = "a journal revision" if report.mode == "journal" else "a one-shot conference rebuttal"
        intro = (f"This check compared the response letter {report.letter} with the referees' comments in "
                 f"{report.reviews} and the ledger {report.ledger} (your revision plan), for round {report.round} of "
                 f"{kind}. The ledger lists {_count(report.items, 'comment')}, and the letter has "
                 f"{_count(report.blocks, 'reply', 'replies')} the check could read.")
        if report.revised and report.blocks:
            numbering = ("the line numbers printed in it" if report.line_numbering == "printed line numbers"
                         else "the lines of the file")
            intro += (f" Places, quoted text and numbers in the replies were checked against the revised manuscript "
                      f"{Path(report.revised).name}, counting {numbering}.")
        lines = ["# Response-letter check", "", intro, ""]
    adv = len(report.findings) - report.blocking
    unassessed = report.unassessed_checks
    target = "in the ledger" if report.stage == "ledger" else "to fix before the letter is sent"
    if report.blocking or adv:
        found = []
        if report.blocking:
            found.append(f"{_plural(report.blocking, 'problem')} {target}")
        if adv:
            found.append(f"{_plural(adv, 'point')} for you to judge")
        verdict = f"It found {_listed(found)}."
    else:
        verdict = "It found no problem."
    if unassessed:
        verdict += (f" {_cap(_count(unassessed, 'check'))} could not run (see \u201cWhat could not be checked\u201d), "
                    "so this is not a clean result.")
    lines += [f"**{verdict}** {report.limitation}", ""]

    for key, title in STAGES:
        group = [f for f in report.findings if f.stage == key]
        if group:
            lines += [f"## {title}", ""]
            for f in group:
                lines += _finding_lines(f, report)
            lines.append("")
    if report.stage == "ledger" and report.undecided:
        lines += ["## Decisions still needed from you", "",
                  "You decide each of these: make the change, decline it with your reason, or explain why it does "
                  "not apply. The check never guesses a decision. They are grouped by when the work could be done.", ""]
        for key, title in STAGES:
            group = [u for u in report.undecided if u.get("stage") == key]
            group.sort(key=lambda u: not u.get("must_fix"))
            if group:
                lines += [f"### {title}", ""]
                for u in group:
                    lines += _decision_lines(u, report)
                lines.append("")
    if report.not_assessed:
        lines += ["## What could not be checked", ""] + [f"- {n}" for n in report.not_assessed] + [""]
    lines += ["## What the check looked at", "", "| Question | Answer |", "|---|---|"]
    for c in report.checks:
        lines.append(f"| {c['description']} | {_answer(c)} |")
    if report.reply_map:
        lines += ["", "## Where each reply points", "",
                  "| Comment | Your decision | Places the reply names | Where the ledger records the change |",
                  "|---|---|---|---|"]
        for row in report.reply_map:
            item = report.comments.get(str(row["item"]))
            if item is not None:
                name = f"{comment_ref(item)} ({item.id}; letter line {row['letter_line']})"
            else:
                name = f"A reply that matches no comment (letter line {row['letter_line']})"
            decision = DECISION_WORDS.get(str(row["decision"]), "") if item is not None else ""
            landed = "; ".join(f"\u201c{x}\u201d" if x else "not recorded" for x in row["landed"]) or \
                "no change listed"  # type: ignore[union-attr]
            lines.append(f"| {_cap(name)} | {_cap(decision) or '-'} | {_place_cell(row)} | {landed} |")
    return "\n".join(lines) + "\n"


@app.command()
def main(
    reviews: Annotated[Path, typer.Argument(exists=True, dir_okay=False,
                                            help="The decision letter and referee reports as received (text)")],
    ledger: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="The review ledger (YAML)")],
    letter: Annotated[Optional[Path], typer.Argument(
        exists=True, dir_okay=False,
        help="The response letter (Markdown); leave out to check the ledger alone")] = None,
    revised: Annotated[Optional[Path], typer.Option(exists=True, dir_okay=False,
                                                    help="The revised manuscript the letter's locations refer to")] = None,
    original: Annotated[Optional[Path], typer.Option(exists=True, dir_okay=False,
                                                     help="The manuscript as first submitted (stale quotes, numbers)")] = None,
    supplement: Annotated[Optional[list[Path]], typer.Option(exists=True, dir_okay=False,
                                                             help="Supplementary text where locations may resolve; repeatable")] = None,
    round_number: Annotated[Optional[int], typer.Option("--round", help="Ledger round to check (default: the last)")] = None,
    mode: Annotated[Mode, typer.Option(help="journal: every change must have landed; rebuttal: one-shot conference "
                                            "rebuttal, promises allowed")] = Mode.journal,
    line_check: Annotated[bool, typer.Option("--line-check/--no-line-check",
                                             help="Check cited line numbers against the revised file")] = True,
    guard_json: Annotated[Optional[Path], typer.Option(exists=True, dir_okay=False,
                                                       help="guard.py ORIGINAL REVISED --json output to reconcile")] = None,
    max_chars: Annotated[Optional[int], typer.Option(help="Character limit per referee section (rebuttals)")] = None,
    strict: Annotated[bool, typer.Option(help="Fail on advisory findings too")] = False,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the report as JSON")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Write the report as Markdown")] = None,
) -> None:
    try:
        report = run(reviews, ledger, letter, revised=revised, original=original, supplements=supplement or [],
                     round_number=round_number, mode=mode, line_check=line_check, guard_json=guard_json,
                     max_chars=max_chars)
    except InputError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    markdown = to_markdown(report)
    if json_out:
        json_out.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    if md_out:
        md_out.write_text(markdown, encoding="utf-8")
    typer.echo(markdown)
    raise typer.Exit(code=1 if report.blocking or (strict and report.findings) else 0)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
