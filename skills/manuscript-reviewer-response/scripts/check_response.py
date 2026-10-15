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

Exit codes: 0 no blocking finding among the checks that ran (read the "not assessed" list: a check that
could not run did not pass, so exit 0 with checks not assessed is not a clean result); 1 at least one
blocking finding (with --strict, any finding); 2 unreadable or malformed input.
"""

from __future__ import annotations

import json
import re
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
        raise InputError(f"{path}: not UTF-8 text ({exc.reason}); convert it first") from exc
    except OSError as exc:
        raise InputError(f"{path}: cannot be read ({exc.strerror})") from exc


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


@dataclass
class Round:
    number: int
    items: list[Item]


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
        raise InputError(f"{path}: not valid YAML ({first})") from exc
    if not isinstance(data, dict):
        raise InputError(f"{path}: the ledger must be a mapping with `rounds:` (or `items:` for one round)")
    raw_rounds = data.get("rounds")
    if raw_rounds is None:
        if "items" not in data:
            raise InputError(f"{path}: no `rounds:` or `items:`")
        raw_rounds = [{"round": data.get("round", 1), "items": data["items"]}]
    if not isinstance(raw_rounds, list) or not raw_rounds:
        raise InputError(f"{path}: `rounds:` must be a non-empty list")
    rounds: list[Round] = []
    for r_index, entry in enumerate(raw_rounds):
        if not isinstance(entry, dict):
            raise InputError(f"{path}: round {r_index + 1} is not a mapping")
        try:
            number = int(entry.get("round", r_index + 1))
        except (TypeError, ValueError) as exc:
            raise InputError(f"{path}: round {r_index + 1} has a non-numeric `round:`") from exc
        raw_items = entry.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise InputError(f"{path}: round {number} has no items")
        items: list[Item] = []
        seen: set[str] = set()
        for k, raw in enumerate(raw_items):
            where = f"{path}: round {number}, item {k + 1}"
            if not isinstance(raw, dict):
                raise InputError(f"{where} is not a mapping")
            item_id = _text(raw.get("id"))
            if not ID_RE.fullmatch(item_id):
                raise InputError(f"{where}: missing or unusable id {item_id!r}")
            if item_id in seen:
                raise InputError(f"{where}: duplicate id {item_id!r}")
            seen.add(item_id)
            comment = _text(raw.get("comment"))
            if not comment:
                raise InputError(f"{where} ({item_id}): no `comment:` text")
            decision = (_text(raw.get("decision")).lower().replace("_", "-").replace(" ", "-") or "undecided")
            if decision not in DECISIONS:
                raise InputError(f"{where} ({item_id}): decision {decision!r} is not one of "
                                 f"{', '.join(sorted(DECISIONS))}")
            evidence = raw.get("evidence") or []
            evidence = [evidence] if isinstance(evidence, str) else [str(e).strip() for e in evidence]
            commitments: list[Commitment] = []
            for c in raw.get("commitments") or []:
                c = {"change": c} if isinstance(c, str) else c
                if not isinstance(c, dict):
                    raise InputError(f"{where} ({item_id}): a commitment is not a mapping")
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
                              sentence=_text(raw.get("sentence"))))
        rounds.append(Round(number, items))
    numbers = [r.number for r in rounds]
    if len(set(numbers)) != len(numbers):
        raise InputError(f"{path}: a round number occurs twice")
    return sorted(rounds, key=lambda r: r.number)


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
        return f'"{head}..."' if head else f"letter line {self.line}"


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


def resolve(loc: Location, revised: Doc | None, extras: list[Doc], line_check: bool) -> None:
    """Set loc.state: resolved, unresolved or not_assessed (with a note)."""
    if revised is None:
        loc.state, loc.note = "not_assessed", "no revised manuscript"
        return
    docs = [revised, *extras]
    if loc.kind == "page":
        loc.state, loc.note = "not_assessed", "page numbers cannot be checked in a text file"
    elif loc.kind == "lines":
        a, b = loc.key  # type: ignore[misc]
        if not line_check:
            loc.state, loc.note = "not_assessed", "line check switched off"
        elif a > b or a < revised.min_line or b > revised.max_line:
            loc.state = "unresolved"
            loc.note = (f"lines {a}-{b} lie outside {revised.path.name} "
                        f"(lines {revised.min_line}-{revised.max_line})")
        else:
            loc.state = "resolved"
    elif loc.kind == "object":
        kind, scope, num = loc.key  # type: ignore[misc]
        if any((kind, scope, num) in d.objects for d in docs):
            loc.state = "resolved"
        elif scope == "main" and revised.tex_counts.get(kind, 0) >= num:
            loc.state = "resolved"
        elif scope == "main" and revised.kind == "latex" and kind in revised.tex_counts:
            loc.state, loc.note = "unresolved", f"{revised.path.name} has {revised.tex_counts[kind]} {kind} environments"
        elif scope != "main" and not extras:
            loc.state, loc.note = "not_assessed", "supplementary material not supplied (--supplement)"
        else:
            loc.state, loc.note = "unresolved", "not mentioned in the revised manuscript or supplements"
    elif loc.kind == "section":
        stem = _section_stem(str(loc.key))
        if not any(d.headings for d in docs):
            loc.state, loc.note = "not_assessed", "no headings recognised in the revised manuscript"
        elif stem == "title" or any(stem in h for d in docs for h in d.headings):
            loc.state = "resolved"
        else:
            loc.state, loc.note = "unresolved", "no heading with this name"
    elif loc.kind == "heading":
        if not any(d.headings for d in docs):
            loc.state, loc.note = "not_assessed", "no headings recognised in the revised manuscript"
        elif any(str(loc.key) in h for d in docs for h in d.headings):
            loc.state = "resolved"
        else:
            loc.state, loc.note = "unresolved", "no heading contains this text"
    elif loc.kind == "secnum":
        numbered = [h for d in docs for h in d.raw_headings if re.match(r"\d+(?:\.\d+)*\b", h)]
        if not numbered:
            loc.state, loc.note = "not_assessed", "headings carry no printed numbers"
        elif any(re.match(re.escape(str(loc.key)) + r"(?:\.|\s|$)", h) for h in numbered):
            loc.state = "resolved"
        else:
            loc.state, loc.note = "unresolved", "no heading with this number"


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
}

CHECKS: list[tuple[str, str, set[str], str | None]] = [
    ("ledger", "Ledger comments occur verbatim in the reviews, in the referees' order",
     {"LEDGER_COMMENT_NOT_VERBATIM", "LEDGER_ORDER", "LEDGER_LINK_INVALID", "LEDGER_VOCAB"}, None),
    ("decisions", "Every item has the authors' decision, and a reason where it declines",
     {"DECISION_MISSING", "REASON_MISSING"}, None),
    ("coverage", "Exactly one reply block per ledger item, none orphaned",
     {"MISSING_REPLY", "DUPLICATE_REPLY", "ORPHAN_REPLY", "MERGED_REPLY", "NO_REPLY_BLOCKS", "EMPTY_REPLY"}, None),
    ("quotes", "Each reply quotes its comment verbatim and in full",
     {"QUOTE_NOT_VERBATIM", "QUOTE_PARTIAL", "QUOTE_WRONG_ITEM", "NO_QUOTE", "QUOTE_ELIDED"}, None),
    ("order", "Replies follow the referees' order", {"ORDER_MISMATCH"}, None),
    ("locations_named", "Each reply names a location, or says that nothing changed and why", {"NO_LOCATION"}, None),
    ("blanket", "No blanket replies", {"BLANKET_REPLY", "BLANKET_CLAIM"}, None),
    ("landed", "Every commitment has a landed location in the ledger",
     {"PROMISE_NOT_LANDED", "EARLIER_PROMISE_OPEN", "PROMISED", "NO_COMMITMENT"}, None),
    ("locations_resolve", "Named and landed locations exist in the revised manuscript",
     {"LOCATION_UNRESOLVED", "LANDED_UNRESOLVED", "LOCATION_MISMATCH", "LOCATION_DIFFERS"}, "revised"),
    ("revised_quotes", "Quoted revised text occurs in the revised manuscript", {"REVISED_QUOTE_NOT_FOUND"}, "revised"),
    ("numbers", "Numbers stated in replies occur in the revised manuscript", {"NUMBER_NOT_IN_MANUSCRIPT"}, "revised"),
    ("placeholders", "No [TBD: ...] placeholder remains", {"TBD_OPEN"}, None),
    ("rounds", "Links to earlier rounds exist and replies refer back to them",
     {"ROUND_LINK_INVALID", "NO_BACK_REFERENCE"}, "rounds"),
    ("guard", "Changes guard.py lists between the versions are mentioned in the letter",
     {"UNMENTIONED_CHANGE"}, "guard"),
    ("length", "Each referee's section is within the character limit", {"OVER_LIMIT"}, "max_chars"),
    ("openings", "Replies open with the answer, not with thanks, agreement or a promise (advisory)",
     {"OPENING_THANKS", "OPENING_AGREE", "FUTURE_TENSE"}, None),
]
# Checks that need a letter, and those that look only at reply blocks (not assessed when there are none).
LEDGER_CHECKS = {"ledger", "decisions", "rounds"}
REPLY_CHECKS = {"quotes", "order", "locations_named", "blanket", "openings", "locations_resolve", "revised_quotes",
                "numbers"}


@dataclass
class Finding:
    code: str
    item: str
    message: str
    line: int | None
    blocking: bool


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
    checks: list[dict[str, str]] = field(default_factory=list)
    reply_map: list[dict[str, object]] = field(default_factory=list)
    not_assessed: list[str] = field(default_factory=list)
    undecided: list[dict[str, object]] = field(default_factory=list)

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
                            "reply_blocks": self.blocks, "revised": self.revised,
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


class Checker:
    def __init__(self, reviews: str, rounds: list[Round], round_number: int, letter: str | None,
                 revised: Doc | None, original: Doc | None, supplements: list[Doc], mode: Mode,
                 line_check: bool) -> None:
        self.reviews = norm(reviews)
        self.rounds = rounds
        current = [r for r in rounds if r.number == round_number]
        if not current:
            raise InputError(f"the ledger has no round {round_number} (rounds: "
                             f"{', '.join(str(r.number) for r in rounds)})")
        self.round = current[0]
        self.items = self.round.items
        self.by_id = {it.id: it for it in self.items}
        self.letter = letter
        self.revised, self.original, self.supplements = revised, original, supplements
        self.mode, self.line_check = mode, line_check
        self.findings: list[Finding] = []
        self.not_assessed: list[str] = []
        self.cited: list[Location] = []
        self.undecided: list[Item] = []

    def add(self, code: str, item: str, message: str, line: int | None = None, blocking: bool | None = None) -> None:
        if blocking is None:
            blocking = code in BLOCKING
            if self.mode is Mode.rebuttal and code in {"QUOTE_PARTIAL", "QUOTE_ELIDED", "NO_QUOTE", "NO_LOCATION"}:
                blocking = False
        self.findings.append(Finding(code, item, message, line, blocking))

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
                ratio, near = nearest(item.comment, self.reviews, by_words=True)
                hint = f'; nearest referee text: "{near[:90]}"' if ratio >= 0.2 else ""
                self.add("LEDGER_COMMENT_NOT_VERBATIM", item.id, f"the ledger's comment text is not in the reviews{hint}")
                continue
            offsets.append((hit[0], item))
            last = hit[0]
            unknown = [e for e in item.evidence if e not in EVIDENCE]
            if unknown:
                self.add("LEDGER_VOCAB", item.id, f"unknown evidence type(s) {', '.join(unknown)}; "
                         f"use {', '.join(sorted(EVIDENCE))}", blocking=False)
        for pos in sorted(out_of_order([o for o, _ in offsets])):
            item = offsets[pos][1]
            self.add("LEDGER_ORDER", item.id, "the ledger lists this item out of the referees' order")
        self._check_links()
        plan = self.letter is None
        for item in self.items:
            if item.decision == "undecided":
                self.undecided.append(item)
                if not plan:
                    self.add("DECISION_MISSING", item.id, "the authors have not decided whether to address, decline "
                             "or treat this item as not on point; the decision is never inferred")
            elif item.decision in {"decline", "not-on-point"} and not item.reason:
                self.add("REASON_MISSING", item.id, f"decision '{item.decision}' has no reason")
            if plan:
                continue  # while planning, commitments are targets and are not expected to have landed
            if (item.decision == "address" and not item.commitments and not item.same_as
                    and not set(item.evidence) <= LETTER_ONLY_EVIDENCE):
                self.add("NO_COMMITMENT", item.id, "addressed, but the ledger records no commitment to check")
            for c in item.commitments:
                if c.is_landed:
                    continue
                what = f"'{c.change}'" if c.change else "a commitment"
                state = "empty" if not c.landed else f"'{c.landed}'"
                if self.mode is Mode.journal:
                    self.add("PROMISE_NOT_LANDED", item.id, f"{what} has not landed (landed: {state})")
                else:
                    self.add("PROMISED", item.id, f"{what} is promised for a later version (landed: {state}); "
                             "the reply must say so and claim nothing as done")

    def _check_links(self) -> None:
        """`same_as` names an earlier item of this round (a repeat, which takes over that item's decision);
        `sentence` names the first fragment of the referee sentence an item was split from."""
        seen: dict[str, Item] = {}
        for item in self.items:
            bad = [ref for ref in item.same_as if ref not in seen]
            if item.sentence and item.sentence not in seen and item.sentence != item.id:
                bad.append(item.sentence)
            if bad:
                self.add("LEDGER_LINK_INVALID", item.id, f"{', '.join(repr(b) for b in bad)} names no earlier item "
                         "of this round; same_as and sentence point back to the first occurrence")
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
                                     f"round {number} commitment '{c.change or 'unnamed'}' never landed")
        for item in self.items:
            for ref in item.previous:
                m = PREVIOUS_RE.match(ref)
                if not m:
                    self.add("ROUND_LINK_INVALID", item.id, f"previous link {ref!r} is not 'ROUND:ID'")
                    continue
                number, ref_id = int(m.group(1)), m.group(2)
                if number >= self.round.number or ref_id not in earlier.get(number, {}):
                    self.add("ROUND_LINK_INVALID", item.id, f"previous link {ref!r} names no item of an earlier "
                             "round in the ledger; never invent a link")
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
                    self.add("ORPHAN_REPLY", block.tag, "the tag names no item of this round's ledger", block.line)
                    continue
                if not block.quote:
                    self.add("NO_QUOTE", block.item.id, "the reply does not reproduce the referee's comment above it",
                             block.line)
                elif not block.quote_found:
                    self.add("QUOTE_NOT_VERBATIM", block.item.id, self._near_hint(block.quote), block.quote_line)
                elif block.quote_elided:
                    if self._elided_from(block.quote, span, block.item):
                        self._elided(block)
                    else:
                        self.add("QUOTE_WRONG_ITEM", block.item.id, "the quote is the referee's text but not this "
                                 "item's comment", block.quote_line)
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
                    self.add("MERGED_REPLY", other.id, f"answered inside the reply to {contained[0].id}; the ledger "
                             "split them because different actions satisfy them: give each its own reply",
                             block.quote_line)
                if not block.quote_found:
                    self.add("QUOTE_NOT_VERBATIM", block.item.id, self._near_hint(block.quote), block.quote_line)
                continue
            partial = [it for it in self.items if q and q in norm(it.comment)] if block.quote_found else []
            if partial:
                block.item = partial[0]
                self.add("QUOTE_PARTIAL", block.item.id, "the reply quotes only part of the comment",
                         block.quote_line)
                continue
            scored = sorted(((SequenceMatcher(None, q, norm(it.comment), autojunk=False).ratio(), it.index, it)
                             for it in self.items), key=lambda t: (-t[0], t[1]))
            if scored and scored[0][0] >= 0.6:
                block.item = scored[0][2]
                if block.quote_found:
                    self.add("QUOTE_WRONG_ITEM", block.item.id, "the quoted text is the referee's but does not "
                             "contain this item's comment", block.quote_line)
                else:
                    self.add("QUOTE_NOT_VERBATIM", block.item.id, self._near_hint(block.quote), block.quote_line)
                continue
            self.add("ORPHAN_REPLY", block.label(), "this reply matches no ledger item"
                     + ("" if block.quote_found else "; " + self._near_hint(block.quote)), block.quote_line)
        self._coverage(blocks, merged_into)

    @staticmethod
    def _elided_from(quote: str, span: str, item: Item) -> bool:
        """An elided quote belongs to an item when it spans the item's comment or is cut from inside it."""
        comment = _strip_quote_marks(norm(item.comment))
        return comment in span or find_folded(comment, quote) is not None

    def _elided(self, block: Block) -> None:
        assert block.item is not None
        self.add("QUOTE_ELIDED", block.item.id, "the quoted comment leaves part of the referee's text out; quote "
                 "the comment in full", block.quote_line)

    def _near_hint(self, quote: str) -> str:
        ratio, near = nearest(quote, self.reviews, by_words=True)
        hint = f'nearest referee text: "{near[:90]}"' if ratio >= 0.2 else "no similar referee text found"
        return f"the quoted comment is not verbatim in the reviews; {hint}"

    def _check_quote_matches_item(self, block: Block, item: Item) -> None:
        q = _strip_quote_marks(norm(block.quote))
        c = _strip_quote_marks(norm(item.comment))
        if c in q:
            return
        if q in c:
            self.add("QUOTE_PARTIAL", item.id, "the reply quotes only part of the ledger comment", block.quote_line)
        else:
            self.add("QUOTE_WRONG_ITEM", item.id, "the quote is the referee's text but not this item's comment",
                     block.quote_line)

    def _coverage(self, blocks: list[Block], merged_into: dict[str, str]) -> None:
        if not blocks:
            self.add("NO_REPLY_BLOCKS", "letter", "the letter has no reply blocks (an item tag or a quoted comment "
                     "followed by a reply), so nothing could be matched to the ledger")
            return
        first: dict[str, Block] = {}
        for block in blocks:
            if block.item is None:
                continue
            if block.item.id in first:
                self.add("DUPLICATE_REPLY", block.item.id, f"a second reply block for this item (first at letter "
                         f"line {first[block.item.id].line})", block.line)
            else:
                first[block.item.id] = block
        for item in self.items:
            if item.id not in first and item.id not in merged_into:
                self.add("MISSING_REPLY", item.id, "no reply block in the letter")
        ordered = sorted(first.values(), key=lambda b: b.line)
        for pos in sorted(out_of_order([b.item.index for b in ordered if b.item])):
            block = ordered[pos]
            assert block.item is not None
            self.add("ORDER_MISMATCH", block.item.id, "the reply stands out of the referees' order", block.line)

    def check_block(self, block: Block) -> dict[str, object]:
        item = block.item
        label = block.label()
        reply = block.reply_text
        row: dict[str, object] = {"item": label, "decision": item.decision if item else "", "letter_line": block.line,
                                  "locations": [], "landed": [c.landed for c in item.commitments] if item else []}
        if not reply:
            if block.quote:
                self.add("EMPTY_REPLY", label, "the comment is quoted but no reply follows it", block.quote_line)
            return row
        if TBD_RE.search(reply):
            self.add("TBD_OPEN", label, "a [TBD: ...] placeholder remains in the reply", block.line)
        locations = extract_locations(reply)
        has_location = bool(locations)
        no_change = bool(NO_CHANGE_RE.search(reply))
        needs_location = item is not None and item.decision == "address" and bool(item.commitments)
        blanket = BLANKET_RE.search(" ".join(reply.split()))
        if blanket and not has_location:
            self.add("BLANKET_REPLY", label, f'blanket wording "{blanket.group(0).strip()}" with no location; '
                     "say what changed and where", block.line)
        elif not has_location and (needs_location or not no_change):
            self.add("NO_LOCATION", label, "the reply names no location in the revised manuscript"
                     + ("" if needs_location else " and does not say that nothing changed"), block.line)
        first = first_sentence(reply)
        if THANKS_RE.match(first) and not re.search(r"[;:]|\d|,\s+(?:and\s+)?we\b", first):
            self.add("OPENING_THANKS", label, "the first sentence is only thanks; put the answer first and keep "
                     "thanks to a clause", block.line, blocking=False)
        else:
            rest = re.sub(r"^.*?\bfor\s+[^,;]*[,;]\s*", "", first, count=1) if THANKS_RE.match(first) else first
            if AGREE_RE.match(rest):
                self.add("OPENING_AGREE", label, "the reply opens with agreement; state the fact or the change "
                         "instead", block.line, blocking=False)
        unlanded = item is not None and any(not c.is_landed for c in item.commitments)
        if self.mode is Mode.journal and not unlanded:
            future = FUTURE_RE.search(reply)
            if future:
                self.add("FUTURE_TENSE", label, f'"{future.group(0)}": in a journal revision the change should '
                         "already be in the manuscript; if it is not, record it as not landed", block.line,
                         blocking=False)
        if item is not None and item.previous and not BACKREF_RE.search(reply):
            self.add("NO_BACK_REFERENCE", label, "this item follows up an earlier round, but the reply does not "
                     "refer back to it", block.line, blocking=False)

        # locations
        for loc in locations:
            resolve(loc, self.revised, self.supplements, self.line_check)
        self.cited.extend(loc for loc in locations if loc.state == "resolved")
        row["locations"] = list(dict.fromkeys(f"{loc.text} ({loc.state})" for loc in locations))
        bad = [loc for loc in locations if loc.state == "unresolved"]
        if bad:
            self.add("LOCATION_UNRESOLVED", label, "; ".join(f"{loc.text}: {loc.note}" for loc in bad), block.line)
        for loc in locations:
            if loc.state == "not_assessed":
                self.not_assessed.append(f"{label}: {loc.text} ({loc.note})")
        if item is not None and self.revised is not None and not unlanded:
            landed_locs = [loc for c in item.commitments if c.is_landed for loc in extract_locations(c.landed)]
            if locations and landed_locs and not any(_overlap(a, b) for a in locations for b in landed_locs):
                self.add("LOCATION_DIFFERS", label, "the reply's locations do not match where the ledger says the "
                         "change landed", block.line, blocking=False)

        # quoted revised text
        quote_spans: list[tuple[int, int]] = []
        if self.revised is not None:
            quote_spans = self._check_revised_quotes(block, label, reply)
            line_ranges = [loc for loc in locations if loc.kind == "lines" and loc.state == "resolved"]
            if quote_spans and line_ranges and not any(
                    a <= hi and lo <= b for (lo, hi) in quote_spans for (a, b) in (r.key for r in line_ranges)):
                spans = ", ".join(f"{lo}-{hi}" for lo, hi in quote_spans)
                cited = ", ".join(r.text for r in line_ranges)
                self.add("LOCATION_MISMATCH", label, f"the quoted revised text is at lines {spans}; the reply "
                         f"cites {cited}", block.line)
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
            where = ("it is the original wording, which the revised manuscript no longer contains" if in_original
                     else "it occurs in neither the revised manuscript nor the reviews")
            short = " ".join(text.split())[:70]
            self.add("REVISED_QUOTE_NOT_FOUND", label, f'quoted text "{short}..." : {where}', line, blocking=firm)
        return spans

    def _check_numbers(self, block: Block, label: str, reply: str) -> None:
        assert self.revised is not None
        text = " ".join(reply.split())
        for rx in (URL_RE, TBD_SPAN_RE, CITATION_RE, LINES_RE, PAGES_RE, TABFIG_RE, SUPPOBJ_RE, SECNUM_RE,
                   LABEL_REF_RE):
            text = rx.sub(" ", text)
        for m in list(INLINE_QUOTE_RE.finditer(text)):
            if find_folded(self.reviews, m.group(1)) or find_folded(self.revised.folded, m.group(1)):
                text = text.replace(m.group(0), " ")
        missing: list[str] = []
        stale: list[str] = []
        for m in NUM_RE.finditer(text):
            value = number_value(m.group(0))
            if value is None or _has_number(value, self.revised.values, self.revised.words):
                continue
            if any(_has_number(value, d.values, d.words) for d in self.supplements):
                continue
            if self.original and _has_number(value, self.original.values, self.original.words):
                stale.append(m.group(0))
            else:
                missing.append(m.group(0))
        if missing or stale:
            parts = []
            if missing:
                parts.append(f"{', '.join(dict.fromkeys(missing))} not in the revised manuscript")
            if stale:
                parts.append(f"{', '.join(dict.fromkeys(stale))} only in the original manuscript")
            self.add("NUMBER_NOT_IN_MANUSCRIPT", label, "; ".join(parts) + ". Correct the reply, add the result "
                     "to the manuscript, or say that it is reported in the letter only", block.line)

    def check_loose(self, loose: list[tuple[int, str, str]]) -> None:
        for line, _, text in loose:
            for loc in extract_locations(text):
                resolve(loc, self.revised, self.supplements, self.line_check)
                if loc.state == "resolved":
                    self.cited.append(loc)
            if TBD_RE.search(text):
                self.add("TBD_OPEN", "letter", "a [TBD: ...] placeholder remains", line)
            blanket = BLANKET_RE.search(text)
            if blanket:
                self.add("BLANKET_CLAIM", "letter", f'general claim "{blanket.group(0).strip()}"; it is true only '
                         "if every item is answered and every commitment landed", line, blocking=False)

    def check_length(self, max_chars: int) -> None:
        sections: dict[str, int] = {}
        heading = ""
        for line in self.letter.splitlines():
            h = HEADING_RE.match(line)
            if h:
                heading = h.group(1).strip()
                continue
            if heading and re.search(r"(?i)review|referee|\bR\d|editor", heading) and not OTHER_COMMENT_RE.match(line):
                sections[heading] = sections.get(heading, 0) + len(line.strip()) + (1 if line.strip() else 0)
        if not sections:
            self.not_assessed.append("length: no referee headings found to count")
        for heading, chars in sections.items():
            if chars > max_chars:
                self.add("OVER_LIMIT", heading, f"{chars} characters against a limit of {max_chars}")

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

    def reconcile_guard(self, path: Path) -> str:
        """Check each change guard.py lists between ORIGINAL and REVISED against the letter."""
        try:
            data = json.loads(read_text(path))
        except json.JSONDecodeError as exc:
            raise InputError(f"{path}: not valid JSON ({exc.msg})") from exc
        if not isinstance(data, dict) or not isinstance(data.get("protected"), dict):
            raise InputError(f"{path}: not a guard.py report; run guard.py ORIGINAL REVISED --revision --json FILE")
        letter_fold = norm(self.letter)
        quoted = [norm(m.group(1)) for m in INLINE_QUOTE_RE.finditer(" ".join(self.letter.split()))]
        changes = data.get("sentence_changes")
        if isinstance(changes, list):
            if self.revised is not None and self.revised.printed:
                return ("not reconciled: guard.py reports file lines, but the revised manuscript carries printed "
                        "line numbers; read guard.py's report against the letter")
            uncovered: dict[str, list[str]] = {"claim": [], "token": []}
            for c in changes:
                if not isinstance(c, dict) or c.get("severity") != "protected" or c.get("authorised"):
                    continue
                token = c.get("token")
                where = c.get("after_line")
                section = str(c.get("section") or "")
                if self._covered(where if isinstance(where, int) else None, section):
                    continue
                before = norm(str(c.get("before") or ""))
                if where is None and before and any(len(q.split()) >= 3 and q in before for q in quoted):
                    continue  # deleted text that the letter quotes
                if token is not None and norm(str(token)) in letter_fold and where is None:
                    continue
                place = f"line {where}" if where is not None else f"deleted from original line {c.get('before_line')}"
                tail = section.split(">")[-1].strip()
                what = (f"{c.get('kind')} {token} {c.get('change')}" if token is not None
                        else f"{c.get('kind')} {c.get('change')}")
                uncovered["token" if token is not None else "claim"].append(f"{place} ({tail}): {what}")
            for kind, entries in uncovered.items():
                if entries:
                    shown = "; ".join(entries[:15]) + (" ..." if len(entries) > 15 else "")
                    label = ("claim strength, scope or evidence wording" if kind == "claim"
                             else "numbers, citations or identifiers")
                    self.add("UNMENTIONED_CHANGE", "manuscript", f"{label} changed where no reply or summary names "
                             f"the location: {shown}", blocking=False)
            return ""
        # an older guard.py report: whole-text counts only
        letter_values = number_values(self.letter)
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
                shown = ", ".join(f"`{t}`" for t in missing[:15]) + (" ..." if len(missing) > 15 else "")
                self.add("UNMENTIONED_CHANGE", "manuscript", f"{category} changed between the versions but are not "
                         f"mentioned in the letter: {shown}", blocking=False)
        return "guard.py report without sentence changes: counts reconciled by token only"


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
            raise InputError(f"{', '.join(given)} need a response letter; without one only the ledger is checked")
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
    guard_note = ""
    if letter_text is not None:
        blocks, loose = parse_letter(letter_text, checker.is_comment)
        checker.map_blocks(blocks)
        reply_map = [checker.check_block(b) for b in blocks]
        checker.check_loose(loose)
        if max_chars:
            checker.check_length(max_chars)
        guard_note = checker.reconcile_guard(guard_json) if guard_json else ""

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
                    checker.add("LANDED_UNRESOLVED", item.id, "the ledger's landed location does not exist: "
                                + "; ".join(f"{loc.text}: {loc.note}" for loc in bad))

    findings = checker.findings
    reasons = {
        "revised": None if revised_doc else "no revised manuscript (--revised)",
        "rounds": None if has_rounds else "not applicable: first round with no links to earlier rounds",
        "guard": None if guard_json else "no guard.py report (--guard-json)",
        "max_chars": None if max_chars else "no character limit given (--max-chars)",
    }
    no_blocks = "the letter has no reply blocks, so no reply was checked"
    checks: list[dict[str, str]] = []
    for name, title, codes, needs in CHECKS:
        reason = reasons.get(needs) if needs else None
        if reason and needs in {"rounds", "max_chars"}:
            continue
        hits = [f for f in findings if f.code in codes]
        if letter_text is None and name not in LEDGER_CHECKS and not hits:
            continue  # plan mode: the letter checks do not apply, as the header says
        if not blocks and name in REPLY_CHECKS:
            reason = reason or no_blocks
        if reason and not hits:
            checks.append({"check": name, "description": title, "state": "not_assessed", "detail": reason})
            checker.not_assessed.append(f"{title}: {reason}")
            continue
        detail = f"{len(hits)} finding(s)" if hits else ""
        if name == "guard" and guard_note:
            detail = (detail + "; " if detail else "") + guard_note
        if name == "decisions" and letter_text is None and checker.undecided:
            detail = (detail + "; " if detail else "") + (f"{len(checker.undecided)} undecided, listed for the "
                                                           "authors (expected while planning)")
        if name == "rounds" and letter_text is None:
            detail = (detail + "; " if detail else "") + "links only; replies not checked (no letter)"
        checks.append({"check": name, "description": title, "state": "fail" if hits else "pass", "detail": detail})
    if letter_text is not None and mode is Mode.journal and revised_doc is None:
        checker.not_assessed.insert(0, "No revised manuscript: locations, quoted revised text and numbers were not "
                                       "checked, so this is not a complete journal check")
    findings.sort(key=lambda f: (not f.blocking, f.line if f.line is not None else 10 ** 9, f.code))
    numbering = ("printed line numbers" if revised_doc and revised_doc.printed else
                 "file lines" if revised_doc else "n/a")
    undecided = [{"id": it.id, "referee": it.referee, "must_fix": it.must_fix, "hand_to": it.hand_to}
                 for it in checker.undecided]
    report = Report(mode=mode.value, stage="ledger" if letter_text is None else "letter", round=number,
                    items=len(checker.items), blocks=sum(1 for b in blocks if b.item or b.tag or b.quote),
                    revised=str(revised) if revised else None, line_numbering=numbering, findings=findings,
                    checks=checks, reply_map=reply_map, not_assessed=list(dict.fromkeys(checker.not_assessed)),
                    undecided=undecided)
    return report


def to_markdown(report: Report) -> str:
    adv = len(report.findings) - report.blocking
    unassessed = report.unassessed_checks
    verdict = f"**{report.blocking} blocking, {adv} advisory" + (
        f"; {unassessed} check(s) not assessed, so this is not a clean result.**" if unassessed else ".**")
    if report.stage == "ledger":
        lines = ["# Review-ledger check", "",
                 f"Round {report.round}, ledger-only check (plan mode): {report.items} ledger items, "
                 f"{len(report.undecided)} undecided. With no response letter, no reply, location or landed "
                 "commitment of this round was checked; run the check again with the letter before sending it.", ""]
    else:
        lines = ["# Response-letter check", "",
                 f"Round {report.round}, {report.mode} mode. {report.items} ledger items, {report.blocks} reply "
                 f"blocks. Revised manuscript: {report.revised or 'not supplied'} (line numbers: "
                 f"{report.line_numbering}).", ""]
    lines += [f"{verdict} {report.limitation}", ""]
    for title, blocking in (("Blocking findings", True), ("Advisory findings", False)):
        group = [f for f in report.findings if f.blocking == blocking]
        if group:
            lines.append(f"## {title}")
            for f in group:
                where = f" (letter line {f.line})" if f.line else ""
                lines.append(f"- **{f.item}** `{f.code}`{where}: {f.message}")
            lines.append("")
    lines += ["## Checks", "", "| Check | State | Detail |", "|---|---|---|"]
    for c in report.checks:
        lines.append(f"| {c['description']} | {c['state']} | {c['detail']} |")
    if report.not_assessed:
        lines += ["", "## Not assessed", ""] + [f"- {n}" for n in report.not_assessed]
    if report.undecided:
        lines += ["", "## Undecided items", "", "The authors decide these; the decision is never inferred.", ""]
        for u in report.undecided:
            notes = (["must fix"] if u["must_fix"] else []) + (
                [f"hand to {', '.join(u['hand_to'])}"] if u["hand_to"] else [])  # type: ignore[arg-type]
            lines.append(f"- {u['id']}" + (f" ({'; '.join(notes)})" if notes else ""))
    if report.reply_map:
        lines += ["", "## Reply map", "", "| Item | Decision | Letter line | Locations named | Landed (ledger) |",
                  "|---|---|---|---|---|"]
        for row in report.reply_map:
            locs = "; ".join(row["locations"]) or "none"  # type: ignore[arg-type]
            landed = "; ".join(x or "(empty)" for x in row["landed"]) or "-"  # type: ignore[union-attr]
            lines.append(f"| {row['item']} | {row['decision']} | {row['letter_line']} | {locs} | {landed} |")
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
    app()
