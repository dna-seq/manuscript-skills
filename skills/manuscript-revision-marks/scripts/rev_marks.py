# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Revision marks kept inside a Markdown or LaTeX document: which segments were rewritten, in how many
rounds, by whom; and the blind spots, prose no round has read.

    uv run --script rev_marks.py lint [--strict] FILE...          exit 1 on any error (or warning, with --strict)
    uv run --script rev_marks.py strip FILE [--out OUT] [--check]  write the clean twin, FILE minus its marks
    uv run --script rev_marks.py report FILE [--blind] [--unreviewed] [--html OUT]
    uv run --script rev_marks.py bump FILE ID --by NAME[:YYYY-MM-DD]
    uv run --script rev_marks.py changes OLD NEW [--seen SEEN] [--json] [--full] [--strict]

lint and report also take --config PATH (default: rev-marks.toml, found from FILE up to the git
root) and --unknown agent|human (overrides the config's `unknown`).

`changes` compares two rounds of a master (the previous round's file and this one's): every segment
that is new, removed, rewritten or given another round, with the heading it sits under, its old and new
text and its new `by=` entries, and every changed paragraph no segment covers. Without marks it lists the
changed paragraphs. The output is a Markdown table, Id | Where | Was | Now | Why with Why left empty, and
the record behind each row; --json gives the same rows to tools, --full puts whole texts in the cells, and
--strict exits 1 on a change that no new round records (no segment covers it, or its segment got no round).
--seen SEEN, the round as the co-authors last saw it within the round (a circulated commit), adds a column:
each row is new since then, changed again, or as they saw it.

A rewritten segment sits between two HTML comments, which renderers and pandoc drop:

    <!-- @rev C3 rounds=2 by=owner:2026-09-25,agent:2026-10-10 -->
    The rewritten text.
    <!-- @/rev C3 -->

- The id names what the passage answers: a comment (C3), a review-ledger item (R1.2, R2.W1, Ed.P1,
  R2.P3b; manuscript-reviewer-response's numbering), a finding of the run that asked for the edit
  (IC-1, RF-3), or N1, N2 for a revision nothing asked for (the authors' own, or a section's copy-edit
  round). An id opens with a capital letter, holds letters, digits, hyphens and dots, and has a digit
  somewhere. Ids are unique per file; one comment answered in several places takes C3a, C3b, grouped as
  C3 (R1.4a, R1.4b as R1.4).
- `rounds=` counts the passes over the passage, writing or approval; `by=` is `name:YYYY-MM-DD` for
  each, comma-separated: whoever wrote or approved that round. Both are required, nothing else is
  allowed, and a count of entries unlike `rounds` is a warning.
- A mark on a line of its own goes with its line; an inline mark is glued to the text and goes
  alone, so a space beside it is text. Segments with different ids nest. A mark inside code is an
  example, not a mark. `strip` removes exactly the marks: the twin is the current master with its
  marks removed, byte for byte, CRLF and other comments included.
- The twin is `<stem>.clean.md` beside FILE; a build reads the twin, never the marked source.
- A blind spot is a paragraph (lines no blank line separates: a list or a table is one) that no
  segment overlaps. Headings, YAML front matter, code and an image alone on its line are not prose.
- A segment is unreviewed when the last name in its `by=` is not a person: a name the project's
  rev-marks.toml lists in `agents`, or one matching ../references/agent-names.toml, or (with the default
  `unknown = "agent"`) one it lists nowhere. `humans` in rev-marks.toml outranks the agent list. lint
  warns once per name that is in neither list.

rev-marks.toml (all keys optional):

    humans = ["anna", "tom"]       # people; outranks the agent list
    agents = ["lab-bot"]           # more agent names or fnmatch patterns
    unknown = "agent"              # or "human": what a name in neither list counts as

A `.tex` file carries its marks as LaTeX comments, each on a line of its own, and its twin is
`<stem>.clean.tex`; every other file is Markdown:

    % @rev C3 rounds=2 by=owner:2026-09-25,agent:2026-10-10
    The rewritten text.
    % @/rev C3

- A comment runs to the end of its line, so a mark after text on its line is refused (inline-mark):
  it would swallow the text after it. Any unescaped `%` followed by `@rev` or `@/rev` is a mark;
  `\\%` is a percent sign, and a mark inside a verbatim environment or `\\verb` is an example.
- A prose line is a line of the document body (between `\\begin{document}` and `\\end{document}`,
  the whole file when there are none) that is not blank, not only a comment, carries a letter or a
  digit outside command names, and is not a line of commands alone (`\\section{…}`, `\\label{…}`,
  `\\begin{figure}`), unless that line opens with a command whose argument is prose (`\\caption`,
  `\\footnote`, `\\item`, `\\emph`, `\\textbf`, `\\textit`). A paragraph is a run of prose lines that
  no blank line and no line of commands alone separates; a comment line inside it does not end it.

Standard library only. The mark format comes from the manuscript ledger of dna-seq/just-dna-lite.

A PDF or Word file carries no marks this tool can read: `report` on one is exit 3, naming what to check
instead.

EXIT STATUS  0 clean · 1 errors found, a stale twin, an unknown id · 2 usage, a malformed rev-marks.toml
             · 3 could not run
"""
from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import html
import json
import re
import sys
import tomllib
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher
from enum import StrEnum
from pathlib import Path

# A capital letter, then letters, digits, hyphens and dotted parts, with a digit somewhere: C3, C3a, N1, R1.2,
# R2.W1, Ed.P1, R2.P3b, R1.6.1, IC-1, RP.RC-1, IC-1.20261024.
ID_PATTERN = r"(?=\S*[0-9])[A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*(?:\.[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)*"
ID_EXAMPLES = "C3, C3a, N1, R1.2, Ed.P1, IC-1"
NAME_PATTERN = r"[A-Za-z][A-Za-z0-9_.-]*"
CLEAN_SUFFIX = ".clean.md"
TEX_CLEAN_SUFFIX = ".clean.tex"
HEAT_LEVELS = 5
FIRST_WORDS = 8
CONFIG_NAME = "rev-marks.toml"
AGENT_NAMES = Path(__file__).resolve().parent.parent / "references" / "agent-names.toml"

ID_RE = re.compile(rf"^{ID_PATTERN}$")
NAME_RE = re.compile(rf"^{NAME_PATTERN}$")
ISO_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
KEY_VALUE_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*)=(?P<value>.*)$")
ROUNDS_RE = re.compile(r"^[0-9]+$")
# A mark candidate is any HTML comment whose body opens with `@rev` or `@/rev`. Anything else
# (`<!-- TODO … -->`) is ordinary text and survives `strip` untouched.
CANDIDATE_START_RE = re.compile(r"<!--[ \t\r\n]*@/?rev\b")
FENCE_OPEN_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(?<!`)(?P<ticks>`+)(?!`)(?:(?!\n[ \t]*\n).)+?(?<!`)(?P=ticks)(?!`)", re.DOTALL)
KNOWN_KEYS = ("rounds", "by")
# Markdown lines that end a paragraph and carry no prose: headings, rules, pandoc's div fences, and an image
# alone on its line (a figure).
MD_BREAK_RE = re.compile(r"^\s*(#|-{3,}\s*$|\*{3,}\s*$|_{3,}\s*$|:{3,}|!\[[^\]]*\]\([^)]*\)(?:\{[^}]*\})?\s*$"
                         r"|<img\b[^>]*>\s*$)")
# Markdown lines inside a paragraph that carry no prose: a table's ruler, a comment alone (a mark among them).
MD_ASIDE_RE = re.compile(r"^\s*(\|?[\s:|-]*-{3,}[\s:|-]*\|?\s*$|<!--.*-->\s*$)")
# Lines that carry no prose of their own, either kind.
NON_PROSE_RE = re.compile(f"{MD_BREAK_RE.pattern}|{MD_ASIDE_RE.pattern}")
# YAML front matter: a `---` line opening the file, closed by `---` or `...`.
FRONT_MATTER_RE = re.compile(r"\A\ufeff?---[ \t]*\r?\n(?:.*?\r?\n)??(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)", re.DOTALL)
# Files that are not text: a mark cannot be read from them.
BINARY_SUFFIXES = {".pdf": "a PDF", ".docx": "a Word file", ".doc": "a Word file", ".odt": "an OpenDocument file"}
# LaTeX: a mark is a comment whose text opens with @rev or @/rev. Whether its % is escaped is decided
# by the backslashes just before it: `\%` is a percent sign, `\\%` a line break and then a comment.
TEX_CANDIDATE_RE = re.compile(r"%[ \t]*@/?rev\b")
TEX_VERBATIM_RE = re.compile(
    r"\\begin\{(?P<env>verbatim\*?|Verbatim\*?|BVerbatim|lstlisting|minted)\}.*?\\end\{(?P=env)\}", re.DOTALL)
TEX_VERB_RE = re.compile(r"\\verb\*?(?P<d>[^A-Za-z\s*])[^\n]*?(?P=d)")
TEX_COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?")
TEX_DOCUMENT_RE = re.compile(r"\\(?P<edge>begin|end)\{document\}")
# A line of commands alone is structure, unless it opens with one of these: their argument is prose.
TEX_PROSE_COMMANDS = frozenset({"caption", "footnote", "item", "emph", "textbf", "textit"})
# Headings, for where a change sits.
MD_HEADING_RE = re.compile(r"^ {0,3}#{1,6}[ \t]+(?P<title>.*?)(?:[ \t]+#+)?[ \t]*$")
TEX_HEADING_RE = re.compile(
    r"^\s*\\(?:part|chapter|section|subsection|subsubsection|paragraph)\*?(?:\[[^\]]*\])?\{(?P<title>.*)\}")
EXCERPT_CONTEXT = 4  # unchanged words kept around each change in a table cell
EXCERPT_WORDS = 60  # a cell's length before the rest is counted, not shown
PAIR_RATIO = 0.4  # how alike (difflib's ratio of their words) two paragraphs must be to count as one revised


class Syntax(StrEnum):
    MARKDOWN = "markdown"
    TEX = "tex"


def syntax_for(path: Path) -> Syntax:
    """`.tex` is LaTeX; every other file is Markdown, as before the tool knew LaTeX."""
    return Syntax.TEX if path.suffix.lower() == ".tex" else Syntax.MARKDOWN


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class Code(StrEnum):
    MALFORMED = "malformed"
    BAD_ID = "bad-id"
    MISSING_KEY = "missing-key"
    UNKNOWN_KEY = "unknown-key"
    DUPLICATE_KEY = "duplicate-key"
    BAD_ROUNDS = "bad-rounds"
    BAD_BY = "bad-by-entry"
    BAD_DATE = "bad-date"
    UNCLOSED = "unclosed"
    UNOPENED = "unopened"
    CROSSED = "crossed"
    SELF_NESTED = "self-nested"
    DUPLICATE_ID = "duplicate-id"
    EMPTY_SEGMENT = "empty-segment"
    ROUNDS_BY_MISMATCH = "rounds-by-mismatch"
    AMBIGUOUS_SPACE = "ambiguous-space"
    INLINE_AT_LINE_START = "inline-at-line-start"
    INLINE_MARK = "inline-mark"
    UNCLASSIFIED_NAME = "unclassified-name"
    # The names before 0.19, kept as aliases: a by= name is whoever wrote or approved a round, not a reviewer.
    BAD_REVIEWER = "bad-by-entry"
    ROUNDS_REVIEWERS_MISMATCH = "rounds-by-mismatch"


@dataclass(frozen=True)
class Issue:
    severity: Severity
    code: Code
    line: int
    message: str


@dataclass(frozen=True)
class Entry:
    """One `name:YYYY-MM-DD` item of a mark's `by=` list."""

    name: str
    on: date

    def render(self) -> str:
        return f"{self.name}:{self.on.isoformat()}"


@dataclass(frozen=True)
class Attributes:
    """The checked content of an opening mark."""

    id: str
    rounds: int
    by: tuple[Entry, ...]

    @property
    def comment_id(self) -> str:
        """The comment this segment answers: `C3a` and `C3b` both answer `C3`."""
        return comment_of(self.id)

    def render(self, syntax: Syntax = Syntax.MARKDOWN) -> str:
        body = f"@rev {self.id} rounds={self.rounds} by={','.join(e.render() for e in self.by)}"
        return f"% {body}" if syntax == Syntax.TEX else f"<!-- {body} -->"


@dataclass(frozen=True)
class Mark:
    """One mark found in the source, with its offsets into the decoded text."""

    opens: bool
    id: str
    start: int
    end: int
    line: int = 0
    own_line: bool = False
    attributes: Attributes | None = None


@dataclass(frozen=True)
class Segment:
    attributes: Attributes
    open: Mark
    close: Mark
    depth: int
    text: str

    @property
    def id(self) -> str:
        return self.attributes.id

    @property
    def rounds(self) -> int:
        return self.attributes.rounds

    @property
    def last(self) -> str:
        """Who wrote the latest round."""
        return self.attributes.by[-1].name


@dataclass(frozen=True)
class Paragraph:
    """One paragraph (its prose lines, from the first to the last) and whether a segment covers it."""

    line: int  # its first prose line
    start: int
    end: int
    text: str
    covered: bool
    lines: tuple[int, ...] = ()  # every prose line in it


@dataclass(frozen=True)
class Marks:
    """Everything `parse` learned about one document."""

    text: str
    marks: tuple[Mark, ...]
    segments: tuple[Segment, ...]
    issues: tuple[Issue, ...]
    removals: tuple[tuple[int, int], ...]
    syntax: Syntax = Syntax.MARKDOWN

    @property
    def errors(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warnings(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severity == Severity.WARNING)

    def clean_text(self) -> str:
        return cut(self.text, self.removals)

    def segment(self, segment_id: str) -> Segment | None:
        return next((s for s in self.segments if s.id == segment_id), None)


def comment_of(segment_id: str) -> str:
    """The comment an id answers: a lowercase letter after a digit splits one comment over places
    (`C3a`, `R1.4b`); `Ed.P1` and `R1.Minor3` answer themselves."""
    return re.sub(r"(?<=[0-9])[a-z]$", "", segment_id)


def first_words(text: str) -> str:
    words = text.split()
    head = " ".join(words[:FIRST_WORDS])
    return f"{head} …" if len(words) > FIRST_WORDS else head


# --- parsing ---------------------------------------------------------------------------------


def code_ranges(text: str) -> list[tuple[int, int]]:
    """Fenced code blocks and inline code spans: a mark shown there is an example."""
    ranges: list[tuple[int, int]] = []
    prose: list[tuple[int, int]] = []
    offset = 0
    fence: str | None = None
    fence_start = prose_start = 0
    for line in text.splitlines(keepends=True):
        if fence is None:
            opened = FENCE_OPEN_RE.match(line)
            if opened:
                fence = opened.group("fence")
                fence_start = offset
                prose.append((prose_start, offset))
        elif re.match(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*\r?\n?$", line):
            fence = None
            ranges.append((fence_start, offset + len(line)))
            prose_start = offset + len(line)
        offset += len(line)
    if fence is None:
        prose.append((prose_start, len(text)))
    else:
        ranges.append((fence_start, len(text)))
    for start, end in prose:
        ranges.extend((start + m.start(), start + m.end()) for m in INLINE_CODE_RE.finditer(text[start:end]))
    return ranges


def tex_code_ranges(text: str) -> list[tuple[int, int]]:
    """Verbatim environments and `\\verb` spans: a mark shown there is an example."""
    ranges = [(m.start(), m.end()) for m in TEX_VERBATIM_RE.finditer(text)]
    ranges += [(m.start(), m.end()) for m in TEX_VERB_RE.finditer(text) if not in_ranges(m.start(), ranges)]
    return ranges


def code_ranges_of(text: str, syntax: Syntax) -> list[tuple[int, int]]:
    return tex_code_ranges(text) if syntax == Syntax.TEX else code_ranges(text)


def escaped(text: str, offset: int) -> bool:
    """An odd run of backslashes before *offset* escapes the character there."""
    run = 0
    while offset - run - 1 >= 0 and text[offset - run - 1] == "\\":
        run += 1
    return run % 2 == 1


def in_ranges(offset: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= offset < end for start, end in ranges)


def error(code: Code, line: int, message: str) -> Issue:
    return Issue(Severity.ERROR, code, line, message)


def warning(code: Code, line: int, message: str) -> Issue:
    return Issue(Severity.WARNING, code, line, message)


def iso_date(day: str) -> date | None:
    """A strict YYYY-MM-DD date, or None. `fromisoformat` alone also takes `20260925` and week dates."""
    if not ISO_DATE_RE.match(day):
        return None
    try:
        return date.fromisoformat(day)
    except ValueError:  # 2026-02-30, 2026-13-01
        return None


def parse_by(value: str, line: int, issues: list[Issue]) -> tuple[Entry, ...] | None:
    entries: list[Entry] = []
    for item in value.split(","):
        name, sep, day = item.partition(":")
        if not sep or not NAME_RE.match(name):
            issues.append(error(Code.BAD_BY, line, f"by= entry {item!r} is not name:YYYY-MM-DD"))
            return None
        on = iso_date(day)
        if on is None:
            issues.append(error(Code.BAD_DATE, line, f"{day!r} in {item!r} is not an ISO date (YYYY-MM-DD)"))
            return None
        entries.append(Entry(name, on))
    return tuple(entries)


def parse_candidate(text: str, start: int, line: int, issues: list[Issue],
                    syntax: Syntax = Syntax.MARKDOWN) -> Mark | None:
    if syntax == Syntax.TEX:  # a LaTeX comment runs to the end of its line, and so does the mark
        _, end, _ = line_bounds(text, start)
        body = text[start + 1 : end]
    else:
        end_body = text.find("-->", start + 4)
        if end_body == -1:
            issues.append(error(Code.MALFORMED, line, "mark comment is never closed with -->"))
            return None
        end = end_body + 3
        body = text[start + 4 : end_body]
        if "\n" in body:
            issues.append(error(Code.MALFORMED, line, "a mark must sit on one line"))
            return None
    tokens = body.split()
    if tokens[0] not in ("@rev", "@/rev"):
        issues.append(error(Code.MALFORMED, line, f"unknown mark word {tokens[0]!r}"))
        return None
    opens = tokens[0] == "@rev"
    if len(tokens) < 2:
        issues.append(error(Code.MALFORMED, line, f"{tokens[0]} needs a segment id"))
        return None
    segment_id = tokens[1]
    if not ID_RE.match(segment_id):
        issues.append(error(Code.BAD_ID, line, f"id {segment_id!r} is not an id: a capital letter, then letters,"
                                               f" digits, hyphens and dots, with a digit somewhere ({ID_EXAMPLES})"))
        return None
    if not opens:
        if len(tokens) != 2:
            issues.append(error(Code.MALFORMED, line, f"closing mark takes only the id, got {body.strip()!r}"))
            return None
        return Mark(False, segment_id, start, end)

    values: dict[str, str] = {}
    valid = True
    for token in tokens[2:]:
        pair = KEY_VALUE_RE.match(token)
        if pair is None:
            issues.append(error(Code.MALFORMED, line, f"{token!r} is not key=value"))
            valid = False
            continue
        key = pair.group("key")
        if key not in KNOWN_KEYS:
            issues.append(error(Code.UNKNOWN_KEY, line, f"unknown key {key!r} (known: rounds, by)"))
            valid = False
        elif key in values:
            issues.append(error(Code.DUPLICATE_KEY, line, f"key {key!r} given twice"))
            valid = False
        else:
            values[key] = pair.group("value")
    for key in KNOWN_KEYS:
        if key not in values:
            issues.append(error(Code.MISSING_KEY, line, f"{segment_id}: missing {key}="))
            valid = False
    rounds = values.get("rounds")
    if rounds is not None and (not ROUNDS_RE.match(rounds) or int(rounds) < 1):
        issues.append(error(Code.BAD_ROUNDS, line, f"rounds={rounds!r} must be a whole number of at least 1"))
        valid = False
    by = parse_by(values["by"], line, issues) if "by" in values else None
    if not valid or by is None or rounds is None:
        return Mark(True, segment_id, start, end)
    attributes = Attributes(segment_id, int(rounds), by)
    if attributes.rounds != len(attributes.by):
        issues.append(warning(Code.ROUNDS_BY_MISMATCH, line,
                              f"{segment_id}: rounds={attributes.rounds} but {len(attributes.by)} by= entries"))
    return Mark(True, segment_id, start, end, attributes=attributes)


def line_bounds(text: str, offset: int) -> tuple[int, int, int]:
    """(line start, end of line content, end including the terminator) around *offset*."""
    start = text.rfind("\n", 0, offset) + 1
    newline = text.find("\n", offset)
    if newline == -1:
        return start, len(text), len(text)
    content_end = newline - 1 if newline > start and text[newline - 1] == "\r" else newline
    return start, content_end, newline + 1


def removals_of(text: str, candidates: list[Mark]) -> tuple[list[tuple[int, int]], set[int]]:
    """Ranges `strip` deletes, and the starts of marks that own their whole line.

    A line holding nothing but marks and spaces goes with its terminator. When such lines end the
    file without a final terminator, the terminator before them goes instead, so the file neither
    gains nor loses a newline. Any other mark is cut exactly; whitespace beside it is text.
    """
    by_line: dict[int, list[Mark]] = {}
    for c in candidates:
        by_line.setdefault(line_bounds(text, c.start)[0], []).append(c)
    ranges: list[tuple[int, int]] = []
    own_line: set[int] = set()
    eof_block = False
    for line_start, members in by_line.items():
        _, content_end, line_end = line_bounds(text, line_start)
        rest = text[line_start:content_end]
        for m in sorted(members, key=lambda c: c.start, reverse=True):
            rest = rest[: m.start - line_start] + rest[m.end - line_start :]
        if rest.strip(" \t") == "":
            ranges.append((line_start, line_end))
            own_line.update(m.start for m in members)
            eof_block = eof_block or (line_end == len(text) and not text.endswith("\n"))
        else:
            ranges.extend((m.start, m.end) for m in members)
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    if eof_block and merged and merged[-1][1] == len(text) and merged[-1][0] > 0:
        start = merged[-1][0]
        start -= 2 if text[max(0, start - 2) : start] == "\r\n" else 1
        merged[-1] = (start, len(text))
    return merged, own_line


def cut(text: str, ranges) -> str:
    pieces: list[str] = []
    cursor = 0
    for start, end in ranges:
        pieces.append(text[cursor:start])
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def clip(ranges, lo: int, hi: int) -> list[tuple[int, int]]:
    return [(max(s, lo), min(e, hi)) for s, e in ranges if e > lo and s < hi]


def parse(text: str, syntax: Syntax = Syntax.MARKDOWN) -> Marks:
    """Find every mark, pair them, and report what is wrong. Never raises on a bad mark."""
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]

    def line_of(offset: int) -> int:
        return bisect_left(newlines, offset) + 1

    tex = syntax == Syntax.TEX
    code = code_ranges_of(text, syntax)
    issues: list[Issue] = []
    candidates: list[Mark] = []
    for match in (TEX_CANDIDATE_RE if tex else CANDIDATE_START_RE).finditer(text):
        if in_ranges(match.start(), code) or (tex and escaped(text, match.start())):
            continue
        if candidates and match.start() < candidates[-1].end:
            continue  # text of the mark before it on the line: that mark is refused below
        c = parse_candidate(text, match.start(), line_of(match.start()), issues, syntax)
        if c is not None:
            candidates.append(c)

    removals, own_line = removals_of(text, candidates)
    marks = [dataclasses.replace(c, line=line_of(c.start), own_line=c.start in own_line) for c in candidates]

    seen: dict[str, int] = {}
    for m in marks:
        if not m.opens:
            continue
        if m.id in seen:
            issues.append(error(Code.DUPLICATE_ID, m.line,
                                f"{m.id} is already used on line {seen[m.id]}; give each place its own"
                                f" id ({comment_of(m.id)}a, …b)"))
        else:
            seen[m.id] = m.line

    stack: list[Mark] = []
    segments: list[Segment] = []
    for m in marks:
        if m.opens:
            if any(o.id == m.id for o in stack):
                issues.append(error(Code.SELF_NESTED, m.line, f"{m.id} opens inside itself"))
            stack.append(m)
            continue
        if stack and stack[-1].id == m.id:
            opened = stack.pop()
            inner = cut(text[opened.end : m.start],
                        [(s - opened.end, e - opened.end) for s, e in clip(removals, opened.end, m.start)])
            if inner.strip() == "":
                issues.append(error(Code.EMPTY_SEGMENT, opened.line, f"{opened.id} wraps no text"))
            elif opened.attributes is not None:
                segments.append(Segment(opened.attributes, opened, m, len(stack), inner))
            continue
        index = next((i for i in range(len(stack) - 1, -1, -1) if stack[i].id == m.id), None)
        if index is None:
            issues.append(error(Code.UNOPENED, m.line, f"@/rev {m.id} closes nothing"))
            continue
        inner_open = stack[-1]
        issues.append(error(Code.CROSSED, m.line,
                            f"@/rev {m.id} closes while {inner_open.id} (line {inner_open.line}) is still open"))
        del stack[index]
    for m in stack:
        issues.append(error(Code.UNCLOSED, m.line, f"@rev {m.id} is never closed"))

    for m in marks:
        if m.own_line:
            continue
        if tex:
            issues.append(error(Code.INLINE_MARK, m.line,
                                f"mark for {m.id} follows text on its line; in a .tex file a mark is a comment"
                                " that runs to the end of the line, so it goes on a line of its own"))
            continue
        before = text[m.start - 1] if m.start > 0 else ""
        after = text[m.end] if m.end < len(text) else ""
        if before in (" ", "\t") and after in (" ", "\t"):
            issues.append(warning(Code.AMBIGUOUS_SPACE, m.line,
                                  f"inline mark for {m.id} has a space on both sides; strip keeps both"))
        if before in ("", "\n"):
            issues.append(warning(Code.INLINE_AT_LINE_START, m.line,
                                  f"inline mark for {m.id} opens the line; CommonMark renders that line as raw"
                                  " HTML, put the mark on its own line instead"))

    issues.sort(key=lambda i: (i.line, i.severity != Severity.ERROR))
    segments.sort(key=lambda s: s.open.start)
    return Marks(text, tuple(marks), tuple(segments), tuple(issues), tuple(removals), syntax)


# --- people ----------------------------------------------------------------------------------


class Kind(StrEnum):
    HUMAN = "human"
    AGENT = "agent"


class ConfigError(Exception):
    """rev-marks.toml (or the agent list) does not say what it must."""


@dataclass(frozen=True)
class People:
    """Who is a person and who is an agent, for one document."""

    humans: frozenset[str] = frozenset()
    agents: tuple[str, ...] = ()  # exact names and fnmatch patterns, lowercased
    unknown: Kind = Kind.AGENT
    config: Path | None = None

    def known(self, name: str) -> Kind | None:
        """HUMAN or AGENT when a list names *name*; None when neither does."""
        key = name.lower()
        if key in self.humans:
            return Kind.HUMAN
        if any(fnmatch.fnmatchcase(key, pattern) for pattern in self.agents):
            return Kind.AGENT
        return None

    def kind(self, name: str) -> Kind:
        return self.known(name) or self.unknown


def _strings(data: dict, key: str, where: Path) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ConfigError(f"{where}: {key} must be a list of names")
    return [v.strip().lower() for v in value]


def _choice(data: dict, key: str, enum, default, where: Path):
    value = data.get(key, default.value)
    try:
        return enum(value)
    except ValueError:
        raise ConfigError(f"{where}: {key} = {value!r}; one of {', '.join(e.value for e in enum)}") from None


def _read_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: not TOML: {exc}") from None


def agent_list() -> tuple[str, ...]:
    """The shipped agent names and patterns, lowercased."""
    data = _read_toml(AGENT_NAMES)
    return tuple(_strings(data, "names", AGENT_NAMES) + _strings(data, "patterns", AGENT_NAMES))


def find_config(start: Path) -> Path | None:
    """rev-marks.toml in *start*'s directory or above it, up to and including the git root."""
    here = start.resolve()
    for folder in (here, *here.parents) if here.is_dir() else here.parents:
        candidate = folder / CONFIG_NAME
        if candidate.is_file():
            return candidate
        if (folder / ".git").exists():
            return None
    return None


def load_people(start: Path, config: Path | None = None, unknown: str | None = None) -> People:
    """The people for a document at *start*: the shipped agent list, then the project's config."""
    path = config if config is not None else find_config(start)
    data = _read_toml(path) if path is not None else {}
    where = path or Path(CONFIG_NAME)
    unexpected = set(data) - {"humans", "agents", "unknown"}
    if unexpected:
        raise ConfigError(f"{where}: unknown key(s) {', '.join(sorted(unexpected))}")
    people = People(humans=frozenset(_strings(data, "humans", where)),
                    agents=agent_list() + tuple(_strings(data, "agents", where)),
                    unknown=_choice(data, "unknown", Kind, Kind.AGENT, where), config=path)
    return dataclasses.replace(people, unknown=Kind(unknown)) if unknown is not None else people


def unreviewed(found: Marks, people: People) -> list[Segment]:
    """Segments whose latest round no person wrote."""
    return [s for s in found.segments if people.kind(s.last) == Kind.AGENT]


def unclassified(found: Marks, people: People) -> list[Issue]:
    """One warning per `by=` name that neither list names, at its first line."""
    lines: dict[str, list[int]] = {}
    for m in found.marks:
        if m.attributes is not None:
            for e in m.attributes.by:
                if people.known(e.name) is None and m.line not in lines.setdefault(e.name, []):
                    lines[e.name].append(m.line)
    return [warning(Code.UNCLASSIFIED_NAME, at[0],
                    f"{name!r} (line{'s' if len(at) > 1 else ''} {', '.join(map(str, at))}) is in neither"
                    f" {CONFIG_NAME}'s humans nor the agent list; counted as {people.unknown}")
            for name, at in lines.items()]


# How a draft build shades a segment: (opening, closing) put where its marks were. A block segment
# (whole paragraphs) becomes a box; a run inside a paragraph becomes a span (Markdown, highlighted by
# the draft's Lua filter) or a coloured group (LaTeX). An own-line mark took its line ending with it.
DRAFT_TOKENS = {
    (Syntax.MARKDOWN, True): ("::: unreviewed\n", ":::\n"),
    (Syntax.MARKDOWN, False): ("[", "]{.unreviewed}"),
    (Syntax.TEX, True): ("\\begin{unreviewed}\n", "\\end{unreviewed}\n"),
    (Syntax.TEX, False): ("\\begingroup\\unrevtext%\n", "\\endgroup%\n"),
}


def is_block(found: Marks, s: Segment) -> bool:
    """Whole paragraphs: both marks on lines of their own, a blank line (or the file's edge) outside each."""
    if not (s.open.own_line and s.close.own_line):
        return False
    text = found.text
    before = text[: line_bounds(text, s.open.start)[0]]
    after = text[line_bounds(text, s.close.start)[2]:]
    edge_before = before == "" or before.endswith(("\n\n", "\n\r\n")) or before.strip() == "" or \
        (found.syntax == Syntax.TEX and before.rstrip().endswith("\\begin{document}"))
    edge_after = after == "" or after.startswith(("\n", "\r\n")) or after.strip() == "" or \
        (found.syntax == Syntax.TEX and after.lstrip().startswith("\\end{document}"))
    return edge_before and edge_after


def draft_text(found: Marks, ids: set[str]) -> tuple[str, list[str]]:
    """The clean text with the segments in *ids* shaded for a draft build, and the ids it could not shade
    (inline marks around more than one paragraph in Markdown). A segment inside one already shaded is
    covered by it."""
    targets = [s for s in found.segments if s.id in ids]
    skipped = [s.id for s in targets if found.syntax == Syntax.MARKDOWN and not is_block(found, s)
               and "\n\n" in s.text.replace("\r\n", "\n")]
    outer = [s for s in targets if s.id not in skipped]
    shaded = {s.id: s for s in outer if not any(o is not s and o.open.start < s.open.start and s.close.end < o.close.end
                                                 for o in outer)}
    tokens = {s.id: DRAFT_TOKENS[(found.syntax, is_block(found, s))] for s in shaded.values()}
    pieces: list[str] = []
    cursor = 0
    for start, end in found.removals:
        pieces.append(found.text[cursor:start])
        for m in found.marks:
            if start <= m.start < end and m.id in shaded:
                token = tokens[m.id][0 if m.opens else 1]
                if m.own_line and not token.endswith("\n") and not m.opens:
                    token += "\n"
                pieces.append(token)
        cursor = end
    pieces.append(found.text[cursor:])
    return "".join(pieces), skipped


# --- operations ------------------------------------------------------------------------------


class MarkErrors(Exception):
    """The document has mark errors; the operation refused to run."""

    def __init__(self, issues: tuple[Issue, ...]) -> None:
        super().__init__(f"{len(issues)} mark error(s)")
        self.issues = issues


def read_source(path: Path) -> str:
    """Decode without newline translation, so CRLF and a BOM survive the round trip."""
    return path.read_bytes().decode("utf-8")


def clean_suffix(syntax: Syntax) -> str:
    return TEX_CLEAN_SUFFIX if syntax == Syntax.TEX else CLEAN_SUFFIX


def clean_twin_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}{clean_suffix(syntax_for(path))}")


def strip_marks(text: str, syntax: Syntax = Syntax.MARKDOWN) -> str:
    found = parse(text, syntax)
    if found.errors:
        raise MarkErrors(found.errors)
    return found.clean_text()


def bump_segment(text: str, segment_id: str, entry: Entry, syntax: Syntax = Syntax.MARKDOWN) -> str:
    """Add one round to *segment_id* and append *entry*; nothing else in *text* changes."""
    found = parse(text, syntax)
    if found.errors:
        raise MarkErrors(found.errors)
    segment = found.segment(segment_id)
    if segment is None:
        known = ", ".join(s.id for s in found.segments) or "none"
        raise KeyError(f"no segment {segment_id!r} (known: {known})")
    a = segment.attributes
    bumped = dataclasses.replace(a, rounds=a.rounds + 1, by=(*a.by, entry))
    return text[: segment.open.start] + bumped.render(syntax) + text[segment.open.end :]


def parse_entry(value: str, today: date) -> Entry:
    """`NAME` or `NAME:YYYY-MM-DD`, the `--by` of `bump`."""
    name, sep, day = value.partition(":")
    if not NAME_RE.match(name):
        raise ValueError(f"name {name!r} must match {NAME_PATTERN}")
    if not sep:
        return Entry(name, today)
    on = iso_date(day)
    if on is None:
        raise ValueError(f"{day!r} is not an ISO date (YYYY-MM-DD)")
    return Entry(name, on)


def tex_uncommented(line: str) -> str:
    """*line* up to its first unescaped `%`."""
    at = next((m.start() for m in re.finditer("%", line) if not escaped(line, m.start())), len(line))
    return line[:at]


def tex_group_end(body: str, at: int) -> int | None:
    """The offset after the `{…}` or `[…]` opening at *at*: braces nest, a `]` closes only outside them."""
    closer = "}" if body[at] == "{" else "]"
    depth, k = 0, at + 1
    while k < len(body):
        ch = body[k]
        if ch == "\\":
            k += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            if depth == 0:
                return k + 1 if closer == "}" else None
            depth -= 1
        elif ch == "]" and closer == "]" and depth == 0:
            return k + 1
        k += 1
    return None


def tex_command_names(body: str) -> list[str] | None:
    """The command names of a line made of commands and their arguments alone, else None."""
    names: list[str] = []
    i, n = 0, len(body)
    while i < n:
        if body[i] in " \t":
            i += 1
            continue
        command = TEX_COMMAND_RE.match(body, i)
        if command is None:
            return None
        names.append(command.group().strip("\\*"))
        i = command.end()
        while True:
            j = i
            while j < n and body[j] in " \t":
                j += 1
            if j >= n or body[j] not in "[{":
                break
            close = tex_group_end(body, j)
            if close is None:
                return None  # an argument that runs on to the next line: prose, if it has words
            i = close
    return names or None


def tex_prose(raw: str) -> bool:
    body = tex_uncommented(raw).strip()
    if not re.search(r"[A-Za-z0-9]", TEX_COMMAND_RE.sub("", body)):
        return False  # blank, a comment, `\\`, `}`, `\]`: nothing a reader reads
    names = tex_command_names(body)
    return names is None or names[0] in TEX_PROSE_COMMANDS


def tex_body(text: str, code: list[tuple[int, int]]) -> tuple[int, int]:
    """The document body's offsets: the lines between `\\begin{document}` and `\\end{document}`."""
    lo, hi = 0, len(text)
    for m in TEX_DOCUMENT_RE.finditer(text):
        line_start, _, line_end = line_bounds(text, m.start())
        before = text[line_start : m.start()]
        if in_ranges(m.start(), code) or tex_uncommented(before) != before:
            continue  # an example, or inside a comment
        if m.group("edge") == "begin" and lo == 0:
            lo = line_end
        elif m.group("edge") == "end" and lo <= m.start():
            hi = line_start
            break
    return lo, hi


def front_matter_end(text: str) -> int:
    """Where a Markdown file's YAML front matter ends; 0 when it has none."""
    m = FRONT_MATTER_RE.match(text)
    return m.end() if m else 0


def line_kind(raw: str, syntax: Syntax) -> str:
    """`prose`; `aside`, a line inside a paragraph that carries no prose (a comment alone, a mark among
    them; a table's ruler); or `break`, a line that ends the paragraph (a heading, a figure, a line of
    LaTeX commands alone)."""
    if syntax == Syntax.TEX:
        if tex_uncommented(raw).strip() == "":
            return "aside"
        return "prose" if tex_prose(raw) else "break"
    body = raw.strip()
    if MD_ASIDE_RE.match(body):
        return "aside"
    return "break" if MD_BREAK_RE.match(body) else "prose"


def paragraphs(found: Marks) -> list[Paragraph]:
    """Every paragraph, covered when a segment overlaps it; an uncovered one is a blind spot. A paragraph
    is a run of prose lines that no blank line, heading, figure or code separates: the unit a reader's
    attention lands on. A list or a table without blank lines is one."""
    spans = [(s.open.start, s.close.end) for s in found.segments]
    tex = found.syntax == Syntax.TEX
    code = code_ranges_of(found.text, found.syntax)
    lo, hi = tex_body(found.text, code) if tex else (front_matter_end(found.text), len(found.text))
    out: list[Paragraph] = []
    block: list[tuple[int, int, int, str]] = []  # (line number, start, end, text) of each prose line

    def close() -> None:
        if block:
            start, end = block[0][1], block[-1][2]
            out.append(Paragraph(block[0][0], start, end, " ".join(b[3] for b in block),
                                 any(lo_ < end and start < hi_ for lo_, hi_ in spans), tuple(b[0] for b in block)))
            block.clear()

    offset = 0
    for number, raw in enumerate(found.text.splitlines(keepends=True), start=1):
        start, end = offset, offset + len(raw)
        offset = end
        body = raw.strip()
        if not body or in_ranges(start, code) or not lo <= start < hi:
            close()
            continue
        kind = line_kind(raw, found.syntax)
        if kind == "break":
            close()
        elif kind == "prose":
            block.append((number, start, end, body))
    close()
    return out


def blind_spots(found: Marks) -> list[Paragraph]:
    return [p for p in paragraphs(found) if not p.covered]


def report_rows(found: Marks) -> list[dict[str, str]]:
    """One row per segment; `rounds by` is whoever wrote or approved each round, in order."""
    return [{"id": s.id, "rounds": str(s.rounds), "rounds by": ", ".join(e.render() for e in s.attributes.by),
             "line": str(s.open.line), "first words": first_words(s.text)} for s in found.segments]


def totals(found: Marks) -> dict[str, int]:
    ps = paragraphs(found)
    return {
        "segments": len(found.segments),
        "rounds": sum(s.rounds for s in found.segments),
        "comments": len({s.attributes.comment_id for s in found.segments}),
        "max rounds": max((s.rounds for s in found.segments), default=0),
        "paragraphs": len(ps),
        "blind spots": sum(1 for p in ps if not p.covered),
    }


def format_report(found: Marks) -> str:
    rows = report_rows(found)
    heads = ["id", "rounds", "rounds by", "line", "first words"]
    widths = {h: max([len(h), *(len(r[h]) for r in rows)]) for h in heads[:-1]}
    lines = ["  ".join([*(h.upper().ljust(widths[h]) for h in heads[:-1]), heads[-1].upper()])]
    for r in rows:
        cells = [r[h].rjust(widths[h]) if h in ("rounds", "line") else r[h].ljust(widths[h]) for h in heads[:-1]]
        lines.append("  ".join([*cells, r["first words"]]))
    lines += ["", ", ".join(f"{k}: {v}" for k, v in totals(found).items()),
              "A round is one pass over a passage, writing it or approving it; ROUNDS BY names who did each."]
    return "\n".join(lines) + "\n"


def format_unreviewed(found: Marks, people: People) -> str:
    spots = unreviewed(found, people)
    lines = [f"UNREVIEWED ({len(spots)} of {len(found.segments)} segments: the latest round is not a person's)"]
    width = max((len(s.id) for s in spots), default=2)
    for s in spots:
        known = people.known(s.last)
        why = "agent" if known == Kind.AGENT else f"unlisted, counted as {people.unknown}"
        lines.append(f"{s.id.ljust(width)}  line {s.open.line}  {s.last} ({why})  {first_words(s.text)}")
    return "\n".join(lines) + "\n"


def format_blind_spots(found: Marks) -> str:
    spots = blind_spots(found)
    lines = [f"BLIND SPOTS ({len(spots)} of {len(paragraphs(found))} paragraphs no round, writing or approval, has"
             " touched)"]
    width = max((len(str(p.line)) for p in spots), default=4)
    lines += [f"{str(p.line).rjust(width)}  {first_words(p.text)}" for p in spots]
    return "\n".join(lines) + "\n"


HEATMAP_CSS = """
:root { --bg: #fbfaf7; --fg: #1d1c1a; --muted: #6b675f; --rule: #dedad2; --unrev: #7a3fc4; --unrev-hatch: #7a3fc433;
  --h1: #fdf1c7; --h2: #fbdc8e; --h3: #f6b866; --h4: #ee8d4f; --h5: #dd5f3f; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #1a1917; --fg: #ece9e2; --muted: #a39e94; --rule: #3a3833; --unrev: #c49cf5; --unrev-hatch: #c49cf544;
    --h1: #3d3520; --h2: #5a4520; --h3: #77501f; --h4: #94511f; --h5: #b0472a; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.6 Georgia, "Times New Roman", serif; }
header, main { max-width: 52rem; margin: 0 auto; padding: 1.5rem 16px; }
h1 { font-size: 1.4rem; margin: 0 0 .25rem; }
.meta { color: var(--muted); margin: 0 0 1rem; font-size: .95rem; }
.legend { display: flex; gap: .5rem; flex-wrap: wrap; margin: 0 0 1rem; font-size: .9rem; }
.legend span { padding: .1rem .6rem; border-radius: 3px; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { text-align: left; padding: .3rem .5rem; border-bottom: 1px solid var(--rule); vertical-align: top; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.doc { white-space: pre-wrap; overflow-wrap: anywhere; border-top: 1px solid var(--rule); padding-top: 1rem; }
mark { color: inherit; border-radius: 2px; }
.h1 { background: var(--h1); } .h2 { background: var(--h2); } .h3 { background: var(--h3); }
.h4 { background: var(--h4); } .h5 { background: var(--h5); }
mark.unrev { outline: 2px dashed var(--unrev); outline-offset: 1px;
  background-image: repeating-linear-gradient(135deg, transparent 0 6px, var(--unrev-hatch) 6px 8px); }
.legend .unrev { outline: 2px dashed var(--unrev); }
a { color: inherit; }
"""


def render_heatmap(found: Marks, title: str, people: People | None = None) -> str:
    """One self-contained page: the clean text, each segment shaded by its rounds, and outlined and hatched
    when its latest round is not a person's (with *people*)."""
    unrev = {s.id for s in unreviewed(found, people)} if people is not None else set()
    opening = {s.open.start: s for s in found.segments}
    closing = {s.close.start for s in found.segments}
    body: list[str] = []
    cursor = 0
    for start, end in found.removals:
        body.append(html.escape(found.text[cursor:start]))
        for m in found.marks:
            if not start <= m.start < end:
                continue
            if m.start in opening:
                s = opening[m.start]
                tip = f"{s.id}: {s.rounds} round(s); " + ", ".join(f"{e.name} {e.on.isoformat()}" for e in s.attributes.by)
                if s.id in unrev:
                    tip += f"; unreviewed: the latest round is {s.last}'s"
                extra = " unrev" if s.id in unrev else ""
                body.append(f'<mark id="seg-{s.id}" class="h{min(s.rounds, HEAT_LEVELS)}{extra}" data-id="{s.id}"'
                            f' data-rounds="{s.rounds}" data-reviewed="{str(s.id not in unrev).lower()}"'
                            f' title="{html.escape(tip)}">')
            elif m.start in closing:
                body.append("</mark>")
        cursor = end
    body.append(html.escape(found.text[cursor:]))
    rows = "\n".join(
        f'<tr><td><a href="#seg-{html.escape(r["id"])}">{html.escape(r["id"])}</a></td>'
        f'<td class="num">{r["rounds"]}</td><td>{html.escape(r["rounds by"])}</td>'
        f'<td class="num">{r["line"]}</td><td>{"no" if r["id"] in unrev else "yes" if people else ""}</td>'
        f'<td>{html.escape(r["first words"])}</td></tr>'
        for r in report_rows(found))
    blind = "\n".join(f'<tr><td class="num">{p.line}</td><td>{html.escape(first_words(p.text))}</td></tr>'
                      for p in blind_spots(found))
    summary = ", ".join(f"{k}: {v}" for k, v in totals(found).items())
    legend = "".join(f'<span class="h{n}">{n}{"+" if n == HEAT_LEVELS else ""} round{"s" if n > 1 else ""}</span>'
                     for n in range(1, HEAT_LEVELS + 1))
    if people is not None:
        legend += f'<span class="unrev">unreviewed: latest round not a person\'s ({len(unrev)})</span>'
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Revision heat map</title>\n<style>{HEATMAP_CSS}</style>\n</head>\n<body>\n"
        f'<header>\n<h1>Revision heat map</h1>\n<p class="meta">{html.escape(title)} · {summary}</p>\n'
        f'<div class="legend">{legend}</div>\n'
        '<p class="meta">A round is one pass over a passage: writing it or approving it. The shade counts the'
        ' rounds; a passage is reviewed when a person wrote or approved its latest round.</p>\n'
        '<div class="table-wrap"><table>\n<thead><tr><th>ID</th><th>Rounds</th><th>Written or approved by</th>'
        f"<th>Line</th><th>Reviewed</th><th>First words</th></tr></thead>\n<tbody>\n{rows}\n</tbody>\n</table></div>\n"
        '<h2>Blind spots</h2>\n<p class="meta">Paragraphs no round, writing or approval, has touched; unshaded'
        ' below.</p>\n'
        '<div class="table-wrap"><table class="blind">\n<thead><tr><th>Line</th><th>First words</th></tr></thead>\n'
        f"<tbody>\n{blind}\n</tbody>\n</table></div>\n"
        f'</header>\n<main>\n<div class="doc">{"".join(body)}</div>\n</main>\n</body>\n</html>\n')


# --- changes between rounds ------------------------------------------------------------------


class Change(StrEnum):
    NEW = "new"
    REMOVED = "removed"
    REVISED = "revised"  # its text changed
    ROUNDS = "rounds"  # rounds or by= changed, the text did not
    UNMARKED = "unmarked"  # changed text no segment covers


@dataclass(frozen=True)
class Block:
    """A paragraph of the clean text, or a heading or figure line, word by word."""

    first: int  # its first and last line in the marked file
    last: int
    heading: str  # the heading it sits under; a heading's own
    words: tuple[str, ...]
    lines: tuple[int, ...]  # the line of each word
    owners: tuple[int, ...]  # the innermost segment holding each word (an index into Marks.segments), or -1
    offsets: tuple[int, ...]  # where each word starts in the marked text

    @property
    def text(self) -> str:
        return " ".join(self.words)


@dataclass(frozen=True)
class Row:
    """One line of a round's changelog: a segment that changed, or a change no segment covers (id None)."""

    status: Change
    id: str | None
    where: str
    old_line: int | None
    new_line: int | None
    old_text: str
    new_text: str
    old_rounds: int | None = None
    new_rounds: int | None = None
    new_by: tuple[str, ...] = ()  # the by= entries NEW adds
    inside: tuple[str, ...] = ()  # its text changed only inside these nested segments
    unbumped: bool = False  # its own text changed and it got no new round
    history_rewritten: bool = False  # earlier by= entries changed, not only new ones added
    text_unchanged: bool = False  # a new or removed segment whose passage reads the same in both files


def norm(text: str) -> str:
    return " ".join(text.split())


def merged(ranges) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def clean_slice(text: str, lo: int, hi: int, cuts) -> str:
    """text[lo:hi] without the parts *cuts* (sorted, merged) names."""
    return cut(text[lo:hi], [(s - lo, e - lo) for s, e in clip(cuts, lo, hi)])


def kept(lo: int, hi: int, cuts) -> list[tuple[int, int]]:
    """The parts of [lo, hi) that *cuts* (sorted, merged) leave."""
    out: list[tuple[int, int]] = []
    cursor = lo
    for s, e in clip(cuts, lo, hi):
        if s > cursor:
            out.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < hi:
        out.append((cursor, hi))
    return out


def heading_title(line: str, syntax: Syntax) -> str | None:
    m = (TEX_HEADING_RE if syntax == Syntax.TEX else MD_HEADING_RE).match(line)
    if m is None:
        return None
    title = m.group("title")
    title = TEX_COMMAND_RE.sub("", title).replace("{", "").replace("}", "") if syntax == Syntax.TEX else \
        title.replace("*", "").replace("`", "")
    return norm(title)


def blocks(found: Marks) -> list[Block]:
    """The clean text as the units a change is read in: paragraphs (lines no blank line separates), and
    headings, figures, rules and comments (an author's note) each alone. Unlike `paragraphs`, the whole file
    counts (front matter, a preamble, code), since a change there is still a change."""
    text = found.text
    owner = [-1] * len(text)
    for index, s in sorted(enumerate(found.segments), key=lambda pair: pair[1].depth):
        owner[s.open.end : s.close.start] = [index] * (s.close.start - s.open.end)  # the innermost goes last
    out: list[Block] = []
    words: list[tuple[str, int, int, int]] = []  # (word, line number, owner, offset)
    heading = ""

    def close() -> None:
        if words:
            out.append(Block(words[0][1], words[-1][1], heading, *(tuple(w[k] for w in words) for k in range(4))))
            words.clear()

    offset = 0
    for number, raw in enumerate(text.splitlines(keepends=True), start=1):
        start, end = offset, offset + len(raw)
        offset = end
        pieces = kept(start, end, found.removals)
        clean = "".join(text[s:e] for s, e in pieces)
        if clean == "":
            continue  # a line of marks alone: the clean text has no such line
        if not clean.strip():
            close()
            continue
        kind = line_kind(clean, found.syntax)
        if kind == "aside":
            if not clean.lstrip().startswith(("%", "<!--")):
                continue  # a table's ruler
            kind = "break"
        where = [i for s, e in pieces for i in range(s, e)]  # each clean character's offset in the marked text
        line = [(m.group(), number, next((owner[where[i]] for i in range(m.start(), m.end()) if owner[where[i]] >= 0),
                                         -1), where[m.start()]) for m in re.finditer(r"\S+", clean)]
        if kind == "break":
            close()
            heading = heading_title(clean.strip(), found.syntax) or heading
            words.extend(line)
            close()
        else:
            words.extend(line)
    close()
    return out


Word = tuple[str, int, int, str, int, int]  # (word, line, owner, heading, block, offset)
Opcode = tuple[str, int, int, int, int]


def flat(bs: list[Block]) -> list[Word]:
    return [(w, line, own, b.heading, k, at) for k, b in enumerate(bs)
            for w, line, own, at in zip(b.words, b.lines, b.owners, b.offsets)]


def paired(old: list[Block], new: list[Block]) -> list[tuple[int | None, int | None]]:
    """The paragraphs of a changed stretch matched in order, each old one with the new one most like it
    (PAIR_RATIO of their words or more), so words are only ever compared within one paragraph; (i, None) is a
    paragraph cut, (None, j) one added."""
    m, n = len(old), len(new)
    score = [[0.0] * (n + 1) for _ in range(m + 1)]
    ratio: dict[tuple[int, int], float] = {}
    for i in range(m - 1, -1, -1):
        for j in range(n - 1, -1, -1):
            sm = SequenceMatcher(None, old[i].words, new[j].words, autojunk=False)
            r = sm.ratio() if sm.real_quick_ratio() >= PAIR_RATIO and sm.quick_ratio() >= PAIR_RATIO else 0.0
            ratio[i, j] = r
            score[i][j] = max(score[i + 1][j], score[i][j + 1], r + score[i + 1][j + 1] if r >= PAIR_RATIO else 0.0)
    out: list[tuple[int | None, int | None]] = []
    i = j = 0
    while i < m or j < n:
        if i < m and j < n and ratio[i, j] >= PAIR_RATIO and score[i][j] == ratio[i, j] + score[i + 1][j + 1]:
            out.append((i, j))
            i, j = i + 1, j + 1
        elif i < m and (j == n or score[i][j] == score[i + 1][j]):
            out.append((i, None))
            i += 1
        else:
            out.append((None, j))
            j += 1
    return out


def align(ob: list[Block], nb: list[Block]) -> tuple[list[Word], list[Word], list[Opcode]]:
    """Both texts word by word, and how the words of one map to the other: equal paragraphs are matched
    first, then within each stretch that differs the paragraphs alike, then their words."""
    a, b = flat(ob), flat(nb)
    starts_a = [0]
    for block in ob:
        starts_a.append(starts_a[-1] + len(block.words))
    starts_b = [0]
    for block in nb:
        starts_b.append(starts_b[-1] + len(block.words))
    ops: list[Opcode] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, [x.text for x in ob], [x.text for x in nb],
                                               autojunk=False).get_opcodes():
        if tag == "equal":
            ops.append(("equal", starts_a[i1], starts_a[i2], starts_b[j1], starts_b[j2]))
            continue
        at_a, at_b = starts_a[i1], starts_b[j1]
        for i, j in paired(ob[i1:i2], nb[j1:j2]):
            if j is None:
                ops.append(("delete", at_a, starts_a[i1 + i + 1], at_b, at_b))
            elif i is None:
                ops.append(("insert", at_a, at_a, at_b, starts_b[j1 + j + 1]))
            else:
                ops += [(t, at_a + x1, at_a + x2, at_b + y1, at_b + y2) for t, x1, x2, y1, y2 in SequenceMatcher(
                    None, ob[i1 + i].words, nb[j1 + j].words, autojunk=False).get_opcodes()]
            at_a, at_b = ops[-1][2], ops[-1][4]
    return a, b, ops


def counterpart(ops: list[Opcode], lo: int, hi: int, of_new: bool) -> tuple[int, int]:
    """The words of the other text that words lo..hi of this one (of *new*, or of *old*) stand in for:
    their equals, what they replaced, and what was cut or added inside them or at their edges. An empty
    range is where the other text has nothing for them."""
    spans: list[tuple[int, int]] = []
    for tag, i1, i2, j1, j2 in ops:
        s1, s2, o1, o2 = (j1, j2, i1, i2) if of_new else (i1, i2, j1, j2)
        if tag == "equal" and s1 < hi and s2 > lo:
            spans.append((o1 + max(lo, s1) - s1, o1 + min(hi, s2) - s1))
        elif tag != "equal" and ((s1 < hi and s2 > lo) or (s1 == s2 and lo <= s1 <= hi)):
            spans.append((o1, o2))
    return (min(s for s, _ in spans), max(e for _, e in spans)) if spans else (0, 0)


def words_in(offsets: list[int], s: Segment) -> tuple[int, int]:
    """The range of words (given by where each starts) inside segment *s*."""
    return bisect_left(offsets, s.open.end), bisect_left(offsets, s.close.start)


def nested_in(found: Marks, s: Segment) -> list[Segment]:
    return [c for c in found.segments if c is not s and s.open.end <= c.open.start and c.close.end <= s.close.start]


def own_text(found: Marks, s: Segment) -> str:
    """A segment's clean text without the segments nested in it."""
    cuts = merged([*found.removals, *((c.open.start, c.close.end) for c in nested_in(found, s))])
    return norm(clean_slice(found.text, s.open.end, s.close.start, cuts))


def added_rounds(old: Attributes, new: Attributes) -> tuple[tuple[Entry, ...], bool]:
    """The by= entries *new* adds, and whether it also changed the ones *old* had."""
    if new.by[: len(old.by)] == old.by:
        return new.by[len(old.by) :], False
    left = Counter(old.by)
    added: list[Entry] = []
    for e in new.by:
        if left[e]:
            left[e] -= 1
        else:
            added.append(e)
    return tuple(added), True


def changes(old: Marks, new: Marks) -> list[Row]:
    """Every segment that is new, removed, rewritten or given another round between two rounds of a master,
    and every changed paragraph no segment covers, in the order of *new* (a removed passage where it was)."""
    a, b, ops = align(blocks(old), blocks(new))
    a_at, b_at = [w[5] for w in a], [w[5] for w in b]
    end_line = new.text.count("\n") + 1

    def line_in(side: list[Word], k: int, last: int) -> int:
        return side[k][1] if k < len(side) else last

    def heading(side: list[Word], k: int) -> str:
        return side[min(k, len(side) - 1)][3] if side else ""

    def joined(side: list[Word], lo: int, hi: int) -> str:
        return " ".join(w[0] for w in side[lo:hi])

    olds = {s.id: s for s in old.segments}
    news = {s.id: s for s in new.segments}
    keyed: list[tuple[tuple[int, int], Row]] = []
    for s in new.segments:
        lo, hi = words_in(b_at, s)
        key = (s.open.line, s.open.start)
        before = olds.get(s.id)
        if before is None:  # what stood in its place: nothing, or a passage it now marks
            c1, c2 = counterpart(ops, lo, hi, of_new=True)
            keyed.append((key, Row(Change.NEW, s.id, heading(b, lo), a[c1][1] if c2 > c1 else None, s.open.line,
                                   joined(a, c1, c2), norm(s.text), None, s.rounds,
                                   tuple(e.render() for e in s.attributes.by),
                                   text_unchanged=hi > lo and joined(a, c1, c2) == joined(b, lo, hi))))
            continue
        revised = norm(before.text) != norm(s.text)
        if not revised and before.attributes == s.attributes:
            continue
        own = own_text(old, before) != own_text(new, s)
        added, rewritten = added_rounds(before.attributes, s.attributes)
        keyed.append((key, Row(Change.REVISED if revised else Change.ROUNDS, s.id, heading(b, lo), before.open.line,
                               s.open.line, norm(before.text), norm(s.text), before.rounds, s.rounds,
                               tuple(e.render() for e in added), unbumped=own and s.rounds <= before.rounds,
                               history_rewritten=rewritten)))
    for s in old.segments:
        if s.id in news:
            continue
        lo, hi = words_in(a_at, s)
        c1, c2 = counterpart(ops, lo, hi, of_new=False)
        keyed.append(((line_in(b, c1, end_line), -1), Row(
            Change.REMOVED, s.id, heading(a, lo), s.open.line, b[c1][1] if c2 > c1 else None, norm(s.text),
            joined(b, c1, c2), s.rounds, None, text_unchanged=hi > lo and joined(a, lo, hi) == joined(b, c1, c2))))

    fresh = {k for k, s in enumerate(new.segments) if s.id not in olds}
    keyed += [((at, 1 << 62), row) for at, row in unmarked(a, b, ops, fresh, end_line)]
    rows = [row for _, row in sorted(keyed, key=lambda kr: kr[0])]
    changed = {r.id for r in rows if r.status in (Change.NEW, Change.REMOVED, Change.REVISED)}
    out: list[Row] = []
    for r in rows:
        if r.status == Change.REVISED and r.id in olds and r.id in news and \
                own_text(old, olds[r.id]) == own_text(new, news[r.id]):
            inner = [c.id for c in (*nested_in(new, news[r.id]), *nested_in(old, olds[r.id])) if c.id in changed]
            r = dataclasses.replace(r, inside=tuple(dict.fromkeys(inner)))
        out.append(r)
    return out


def unmarked(a: list[Word], b: list[Word], ops: list[Opcode], fresh: set[int], end_line: int) -> list[tuple[int, Row]]:
    """The changes no segment records, each with the line of the new text it sorts at: new words no segment
    holds, and deleted words no segment held, unless a segment new in this round (one of *fresh*) borders the
    gap, since its row shows them. Changes a few words apart in one paragraph are one row."""
    loose: list[tuple[int, int, int, int]] = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            continue
        if j2 > j1:
            unrecorded = any(w[2] < 0 for w in b[j1:j2])
        else:
            bordered = any(0 <= j < len(b) and b[j][2] in fresh for j in (j1 - 1, j1))
            unrecorded = not bordered and any(w[2] < 0 for w in a[i1:i2])
        if unrecorded:
            loose.append((i1, i2, j1, j2))

    def block(side: list[Word], at: int) -> int:
        return side[at][4] if at < len(side) else -1

    groups: list[list[tuple[int, int, int, int]]] = []
    for op in loose:
        last = groups[-1][-1] if groups else None
        if last and op[0] - last[1] <= 2 * EXCERPT_CONTEXT and op[2] - last[3] <= 2 * EXCERPT_CONTEXT and \
                block(a, op[0]) == block(a, last[0]) and block(b, op[2]) == block(b, last[2]):
            groups[-1].append(op)
        else:
            groups.append([op])
    rows: list[tuple[int, Row]] = []
    for g in groups:
        i1, i2, j1, j2 = g[0][0], g[-1][1], g[0][2], g[-1][3]
        first = b[j1] if j2 > j1 else a[i1]
        # A side that only lost or only gained words shows the other side's context: the same words.
        was = around(a, i1, i2) if i2 > i1 else around(b, j1, j2, own=False)
        now = around(b, j1, j2) if j2 > j1 else around(a, i1, i2, own=False)
        rows.append((b[j1][1] if j1 < len(b) else end_line, Row(
            Change.UNMARKED, None, first[3], line_at(a, i1, i2, b, j1, j2), line_at(b, j1, j2, a, i1, i2), was, now)))
    return rows


def line_at(side: list[Word], lo: int, hi: int, other: list[Word], olo: int, ohi: int) -> int | None:
    """The line of side[lo:hi]. An empty range is where the other text's change sits inside a paragraph: the
    line of the word before it when the change has its paragraph's words before it, else of the word after;
    None when the change is whole paragraphs."""
    if hi > lo:
        return side[lo][1]
    if olo > 0 and other[olo - 1][4] == other[olo][4] and lo > 0:
        return side[lo - 1][1]
    if ohi < len(other) and other[ohi][4] == other[ohi - 1][4] and lo < len(side):
        return side[lo][1]
    return None


def around(side: list[Word], lo: int, hi: int, own: bool = True) -> str:
    """side[lo:hi] (lo < hi) with up to EXCERPT_CONTEXT words of its paragraph on each side. Without *own*,
    only those words: how the other text reads where it gained or lost side[lo:hi]."""
    first, last = side[lo][4], side[hi - 1][4]
    start, end = lo, hi
    while start > 0 and lo - start < EXCERPT_CONTEXT and side[start - 1][4] == first:
        start -= 1
    while end < len(side) and end - hi < EXCERPT_CONTEXT and side[end][4] == last:
        end += 1
    words = [w[0] for w in (*side[start:lo], *(side[lo:hi] if own else ()), *side[hi:end])]
    if not words:
        return ""
    if start > 0 and side[start - 1][4] == first:
        words.insert(0, "…")
    if end < len(side) and side[end][4] == last:
        words.append("…")
    return " ".join(words)


def excerpt(old: str, new: str) -> tuple[str, str]:
    """The changed words of *old* and *new*, each with a few unchanged words around it."""
    a, b = old.split(), new.split()
    if not a or not b:
        return capped(a), capped(b)
    was: list[str] = []
    now: list[str] = []
    for group in SequenceMatcher(None, a, b, autojunk=False).get_grouped_opcodes(EXCERPT_CONTEXT):
        for words, lo, hi, side in ((a, group[0][1], group[-1][2], was), (b, group[0][3], group[-1][4], now)):
            if lo > 0 and (not side or side[-1] != "…"):
                side.append("…")
            side.extend(words[lo:hi])
            if hi < len(words):
                side.append("…")
    return capped(was), capped(now)


def capped(words: list[str]) -> str:
    if len(words) <= EXCERPT_WORDS:
        return " ".join(words)
    rest = sum(1 for w in words[EXCERPT_WORDS:] if w != "…")
    return " ".join(words[:EXCERPT_WORDS]) + f" … ({rest} more words)"


def cell(text: str) -> str:
    return norm(text).replace("|", "\\|")


def table_row(r: Row, full: bool) -> list[str]:
    if r.status == Change.ROUNDS:
        was = now = "(text unchanged)"
    elif r.inside:
        was = now = f"(changed only inside {', '.join(r.inside)})"
    elif full:
        was, now = r.old_text, r.new_text
    elif r.status == Change.UNMARKED:  # already the changed words in their context
        was, now = capped(r.old_text.split()), capped(r.new_text.split())
    else:
        was, now = excerpt(r.old_text, r.new_text)
    if r.status == Change.NEW and r.text_unchanged:
        was = "(the same text, not marked)"
    return [r.id or "(none)", first_words(r.where) if r.where else "(before the first heading)",
            was or "Not present", now or "Removed", ""]


def record_line(r: Row) -> str:
    lines = (f"line {r.old_line} of OLD" if r.new_line is None else f"line {r.new_line} of NEW" if r.old_line is None
             else f"line {r.old_line} → {r.new_line}")
    head = f"- {r.id or '(none)'}: {r.status}, {lines}"
    if r.status == Change.UNMARKED:
        return f"{head}; no segment covers it."
    if r.status == Change.REMOVED:
        return f"{head}; had {r.old_rounds} round(s)" + \
            ("; its passage still reads the same, only the marks are gone." if r.text_unchanged else ".")
    if r.status == Change.NEW:
        return f"{head}; {r.new_rounds} round(s), by {', '.join(r.new_by)}" + \
            ("; its passage read the same in OLD, only the marks are new." if r.text_unchanged else ".")
    notes = [f"rounds {r.old_rounds} → {r.new_rounds}"]
    if r.new_by:
        counts = Counter(r.new_by)
        notes.append("new rounds by " + ", ".join(f"{e} (×{n})" if n > 1 else e for e, n in counts.items()))
    if r.inside:
        notes.append(f"changed only inside {', '.join(r.inside)}")
    if r.unbumped:
        notes.append("the text changed with no new round")
    if r.history_rewritten:
        notes.append("earlier by= entries changed")
    return f"{head}; {'; '.join(notes)}."


def present(fragment: str, text: str) -> bool:
    """Whether every piece of an excerpt (its parts between "…") reads in *text*."""
    pieces = [norm(p) for p in fragment.split("…") if norm(p)]
    return bool(pieces) and all(p in text for p in pieces)


def since_seen(rows: list[Row], seen: Marks) -> list[str]:
    """For each row of a round's changelog, how it stands against the draft the co-authors last saw: "new" (the
    draft still read as the round's base there), "changed" (they saw an earlier form of this change) or "same"."""
    seen_text = norm(seen.clean_text())
    out = []
    for r in rows:
        segment = seen.segment(r.id) if r.id else None
        if r.status == Change.REMOVED:
            out.append("new" if segment is not None or (r.old_text and present(r.old_text, seen_text)) else "same")
        elif r.status == Change.ROUNDS:
            out.append("same" if segment is not None and segment.rounds == r.new_rounds else "changed")
        elif segment is not None:
            then = norm(segment.text)
            out.append("same" if then == norm(r.new_text) else "new" if then == norm(r.old_text) else "changed")
        elif r.id is not None:
            out.append("new" if r.status == Change.NEW else "changed")
        elif r.old_text and present(r.old_text, seen_text):  # an unmarked change: the old words still read there
            out.append("new")
        else:
            out.append("same" if present(r.new_text, seen_text) else "changed")
    return out


SINCE = {"new": "New since then", "changed": "Changed again", "same": ""}


def change_totals(rows: list[Row]) -> dict[str, int]:
    return {c.value: sum(1 for r in rows if r.status == c) for c in Change}


def format_changes(old: Marks, new: Marks, old_name: str, new_name: str, rows: list[Row], full: bool = False,
                   since: list[str] | None = None, seen_name: str = "", why: list[str] | None = None) -> str:
    """The changelog table. With *since* (since_seen against SEEN), a column says which rows the co-authors
    have not seen; with *why*, the Why cells come from a record (manuscript-coauthors' ledger), else empty."""
    t = change_totals(rows)
    out = [f"# Changes from {old_name} to {new_name}", ""]
    if old.segments or new.segments:
        out.append(f"{len(new.segments)} segments in NEW, {len(old.segments)} in OLD: {t['new']} new,"
                   f" {t['removed']} removed, {t['revised']} revised, {t['rounds']} with new rounds alone (text"
                   f" unchanged); {t['unmarked']} change(s) no segment covers.")
    else:
        out.append(f"Neither file carries revision marks: each of the {t['unmarked']} changed paragraph(s) is"
                   " a row, with no id.")
    if not rows:
        return "\n".join([*out, "", "No changes."]) + "\n"
    if since is not None:
        out.append(f"Against {seen_name}, the draft the co-authors last saw: {since.count('new')} row(s) new since then,"
                   f" {since.count('changed')} changed again, {since.count('same')} as they saw them.")
    out += ["Why is empty: write it from the record (commit messages, the review run, the authors' words),"
            " never as a guess." if why is None else
            "Why comes from the co-authors' comments ledger where a row answers a comment; the rest is empty: write"
            " it from the record, never as a guess.", ""]
    head = ["Id", "Where", "Was", "Now", "Why"] + (["Since they saw it"] if since is not None else [])
    out += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for k, r in enumerate(rows):
        cells = table_row(r, full)
        if why is not None:
            cells[4] = why[k]
        if since is not None:
            cells.append(SINCE[since[k]])
        out.append("| " + " | ".join(cell(c) for c in cells) + " |")
    out += ["", "## The record behind each row", "",
            "For whoever writes Why, not for co-authors. Lines are in the marked masters."]
    out += [record_line(r) for r in rows]
    return "\n".join(out) + "\n"


def changes_json(old: Marks, new: Marks, old_name: str, new_name: str, rows: list[Row],
                 since: list[str] | None = None, seen_name: str = "") -> dict:
    return {"old": old_name, "new": new_name, "segments": {"old": len(old.segments), "new": len(new.segments)},
            "totals": change_totals(rows), **({"seen": seen_name} if since is not None else {}),
            "rows": [{**dataclasses.asdict(r), "status": r.status.value, "new_by": list(r.new_by),
                      "inside": list(r.inside), **({"since_seen": since[k]} if since is not None else {})}
                     for k, r in enumerate(rows)]}


# --- command line ----------------------------------------------------------------------------


def print_issues(path: Path, issues) -> None:
    for i in issues:
        print(f"{path}:{i.line}: {i.severity} {i.code}: {i.message}", file=sys.stderr)


def load(path: Path) -> Marks | None:
    """Parse *path* and print its issues; None when any is an error."""
    found = parse(read_source(path), syntax_for(path))
    print_issues(path, found.issues)
    return None if found.errors else found


def people_for(path: Path, args) -> People:
    return load_people(path, args.config, args.unknown)


def cmd_lint(args) -> int:
    failed = False
    for path in args.files:
        found = parse(read_source(path), syntax_for(path))
        issues = sorted([*found.issues, *unclassified(found, people_for(path, args))],
                        key=lambda i: (i.line, i.severity != Severity.ERROR))
        warnings = [i for i in issues if i.severity == Severity.WARNING]
        print_issues(path, issues)
        failed = failed or bool(found.errors) or (args.strict and bool(warnings))
        print(f"{path}: {len(found.segments)} segment(s), {len(found.errors)} error(s),"
              f" {len(warnings)} warning(s)")
    return 1 if failed else 0


def cmd_strip(args) -> int:
    path = args.file
    if path.name.endswith(clean_suffix(syntax_for(path))):
        print(f"{path} is already a clean twin; strip its source instead", file=sys.stderr)
        return 1
    target = args.out if args.out is not None else clean_twin_path(path)
    if target.resolve() == path.resolve():
        print(f"rev_marks.py: --out {target} is the marked file itself; the clean copy goes elsewhere", file=sys.stderr)
        return 2
    found = load(path)
    if found is None:
        return 1
    clean = found.clean_text().encode("utf-8")
    current = target.read_bytes() if target.is_file() else None
    if args.check:
        if current != clean:
            print(f"{target} is {'stale' if current is not None else 'missing'}", file=sys.stderr)
            return 1
        print(f"{target} is current")
        return 0
    if current != clean:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(clean)
    print(f"wrote {target}")
    return 0


def cmd_report(args) -> int:
    people = people_for(args.file, args)
    found = load(args.file)
    if found is None:
        return 1
    sys.stdout.write(format_report(found))
    if args.blind:
        sys.stdout.write("\n" + format_blind_spots(found))
    if args.unreviewed:
        sys.stdout.write("\n" + format_unreviewed(found, people))
    if args.html is not None:
        args.html.write_bytes(render_heatmap(found, args.file.name, people).encode("utf-8"))
        print(f"wrote {args.html}")
    return 0


def cmd_bump(args) -> int:
    try:
        entry = parse_entry(args.by, datetime.now().astimezone().date())
    except ValueError as exc:
        print(f"rev_marks.py: --by: {exc}", file=sys.stderr)
        return 2
    found = load(args.file)
    if found is None:
        return 1
    try:
        updated = bump_segment(found.text, args.id, entry, found.syntax)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 1
    args.file.write_bytes(updated.encode("utf-8"))
    print(f"{args.id}: rounds={parse(updated, found.syntax).segment(args.id).rounds}")
    return 0


def cmd_changes(args) -> int:
    old_path, new_path = args.old, args.new
    old, new = load(old_path), load(new_path)
    seen = load(args.seen) if args.seen else None
    if old is None or new is None or (args.seen and seen is None):
        return 1
    rows = changes(old, new)
    since = since_seen(rows, seen) if seen is not None else None
    if args.json:
        sys.stdout.write(json.dumps(changes_json(old, new, str(old_path), str(new_path), rows, since, str(args.seen)),
                                    ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(format_changes(old, new, str(old_path), str(new_path), rows, args.full, since, str(args.seen)))
    loose = [r for r in rows if r.status == Change.UNMARKED or r.unbumped]
    if args.strict and loose:
        print(f"{new_path}: {len(loose)} change(s) no new round records: "
              + ", ".join(r.id or f"line {r.new_line or r.old_line}" for r in loose), file=sys.stderr)
        return 1
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="rev_marks.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path, help=f"default: {CONFIG_NAME} from FILE up to the git root")
    common.add_argument("--unknown", choices=[k.value for k in Kind], help="what a name in neither list counts as")
    p = sub.add_parser("lint", help="check marks; exit 1 on any error", parents=[common])
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument("--strict", action="store_true", help="warnings fail too")
    p.set_defaults(run=cmd_lint)
    p = sub.add_parser("strip", help="write the clean twin")
    p.add_argument("file", type=Path)
    p.add_argument("--out", "-o", type=Path, help="default: <stem>.clean.md (.clean.tex for a .tex) beside FILE")
    p.add_argument("--check", action="store_true", help="write nothing; exit 1 if the twin is missing or stale")
    p.set_defaults(run=cmd_strip)
    p = sub.add_parser("report", help="segments, rounds, reviewers and totals", parents=[common])
    p.add_argument("file", type=Path)
    p.add_argument("--blind", action="store_true", help="also list the blind spots")
    p.add_argument("--unreviewed", action="store_true", help="also list segments whose latest round is not a person's")
    p.add_argument("--html", type=Path, help="also write a self-contained heat map")
    p.set_defaults(run=cmd_report)
    p = sub.add_parser("bump", help="add one round to a segment")
    p.add_argument("file", type=Path)
    p.add_argument("id", metavar="ID")
    p.add_argument("--by", required=True, help="NAME or NAME:YYYY-MM-DD (default date: today)")
    p.set_defaults(run=cmd_bump)
    p = sub.add_parser("changes", help="what changed between two rounds: the changelog's rows")
    p.add_argument("old", type=Path, metavar="OLD", help="the previous round's master")
    p.add_argument("new", type=Path, metavar="NEW", help="this round's master")
    p.add_argument("--json", action="store_true", help="the rows as JSON, for tools")
    p.add_argument("--full", action="store_true", help="whole old and new texts in the cells, not the changed words")
    p.add_argument("--strict", action="store_true",
                   help="exit 1 on a change no new round records: unmarked, or in a segment with no new round")
    p.add_argument("--seen", type=Path, metavar="SEEN",
                   help="this round as the co-authors last saw it: mark each row new, changed again or as they saw it")
    p.set_defaults(run=cmd_changes)
    args = ap.parse_args(argv)
    for path in getattr(args, "files", None) or [getattr(args, k) for k in ("file", "old", "new", "seen")
                                                  if getattr(args, k, None) is not None]:
        if not path.is_file():
            print(f"rev_marks.py: cannot read {path}", file=sys.stderr)
            return 3
        kind = BINARY_SUFFIXES.get(path.suffix.lower())
        if kind is not None:
            print(f"rev_marks.py: not run: {path} is {kind}, and marks are read from the Markdown or LaTeX source."
                  " A file typeset.py built carries none: it reads the clean twin. For one built elsewhere, check"
                  " the source it was built from, or extract its text (pdftotext, where installed) and search it"
                  " for @rev.", file=sys.stderr)
            return 3
    try:
        return args.run(args)
    except ConfigError as exc:
        print(f"rev_marks.py: {exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError) as exc:
        print(f"rev_marks.py: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
