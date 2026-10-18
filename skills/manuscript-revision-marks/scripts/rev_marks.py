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

lint and report also take --config PATH (default: rev-marks.toml, found from FILE up to the git
root) and --unknown agent|human (overrides the config's `unknown`).

A rewritten segment sits between two HTML comments, which renderers and pandoc drop:

    <!-- @rev C3 rounds=2 by=owner:2026-09-25,agent:2026-10-10 -->
    The rewritten text.
    <!-- @/rev C3 -->

- The id is the comment it answers: capitals, digits, an optional lowercase letter (C3, N1, C3a), or a
  review-ledger item (R1.2, R2.W1, R1.4a; manuscript-reviewer-response's numbering). Ids are unique per
  file; one comment answered in several places takes C3a, C3b, grouped as C3 (R1.4a, R1.4b as R1.4).
- `rounds=` is a whole number of at least 1; `by=` is `name:YYYY-MM-DD`, comma-separated. Both are
  required, nothing else is allowed, and a count of entries unlike `rounds` is a warning.
- A mark on a line of its own goes with its line; an inline mark is glued to the text and goes
  alone, so a space beside it is text. Segments with different ids nest. A mark inside code is an
  example, not a mark. `strip` is the exact inverse: the twin is the file as it was before any mark
  went in, byte for byte, CRLF and other comments included.
- The twin is `<stem>.clean.md` beside FILE; a build reads the twin, never the marked source.
- A blind spot is a prose line (a paragraph, a list item, a table row) no segment overlaps.
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
  `\\footnote`, `\\item`, `\\emph`, `\\textbf`, `\\textit`). A sectioning line is a heading, as `#` is.

Standard library only. The mark format comes from the manuscript ledger of dna-seq/just-dna-lite.

EXIT STATUS  0 clean · 1 errors found, a stale twin, an unknown id · 2 usage, a malformed rev-marks.toml
             · 3 could not run
"""
from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import html
import re
import sys
import tomllib
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from string import ascii_lowercase

ID_PATTERN = r"[A-Z]+[0-9]+(?:\.[A-Z]*[0-9]+)*[a-z]?"
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
# Lines that carry no prose of their own: headings, rules, table rulers, comment-only lines.
NON_PROSE_RE = re.compile(r"^\s*(#|-{3,}\s*$|\*{3,}\s*$|\|?[\s:|-]*-{3,}[\s:|-]*\|?\s*$|<!--.*-->\s*$)")
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
    BAD_REVIEWER = "bad-reviewer"
    BAD_DATE = "bad-date"
    UNCLOSED = "unclosed"
    UNOPENED = "unopened"
    CROSSED = "crossed"
    SELF_NESTED = "self-nested"
    DUPLICATE_ID = "duplicate-id"
    EMPTY_SEGMENT = "empty-segment"
    ROUNDS_REVIEWERS_MISMATCH = "rounds-reviewers-mismatch"
    AMBIGUOUS_SPACE = "ambiguous-space"
    INLINE_AT_LINE_START = "inline-at-line-start"
    INLINE_MARK = "inline-mark"
    UNCLASSIFIED_NAME = "unclassified-name"


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
        return self.id.rstrip(ascii_lowercase)

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
    """One prose line and whether a segment covers it."""

    line: int
    start: int
    end: int
    text: str
    covered: bool


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
            issues.append(error(Code.BAD_REVIEWER, line, f"reviewer entry {item!r} is not name:YYYY-MM-DD"))
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
        issues.append(error(Code.BAD_ID, line, f"id {segment_id!r} does not match {ID_PATTERN} (C3, N1, C3a, R1.2, R2.W1)"))
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
        issues.append(warning(Code.ROUNDS_REVIEWERS_MISMATCH, line,
                              f"{segment_id}: rounds={attributes.rounds} but {len(attributes.by)} reviewer entries"))
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
                                f" id ({m.id.rstrip(ascii_lowercase)}a, …b)"))
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
        raise ValueError(f"reviewer name {name!r} must match {NAME_PATTERN}")
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


def paragraphs(found: Marks) -> list[Paragraph]:
    """Every prose line, covered when a segment overlaps it. One paragraph per line is the unit a
    reader's attention lands on; an uncovered one is a blind spot."""
    spans = [(s.open.start, s.close.end) for s in found.segments]
    tex = found.syntax == Syntax.TEX
    code = code_ranges_of(found.text, found.syntax)
    lo, hi = tex_body(found.text, code) if tex else (0, len(found.text))
    out: list[Paragraph] = []
    offset = 0
    for number, raw in enumerate(found.text.splitlines(keepends=True), start=1):
        start, end = offset, offset + len(raw)
        offset = end
        body = raw.strip()
        if not body or in_ranges(start, code) or not lo <= start < hi:
            continue
        if (not tex_prose(raw)) if tex else NON_PROSE_RE.match(body):
            continue
        out.append(Paragraph(number, start, end, body, any(lo_ < end and start < hi_ for lo_, hi_ in spans)))
    return out


def blind_spots(found: Marks) -> list[Paragraph]:
    return [p for p in paragraphs(found) if not p.covered]


def report_rows(found: Marks) -> list[dict[str, str]]:
    return [{"id": s.id, "rounds": str(s.rounds), "reviewers": ", ".join(e.render() for e in s.attributes.by),
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
    heads = ["id", "rounds", "reviewers", "line", "first words"]
    widths = {h: max([len(h), *(len(r[h]) for r in rows)]) for h in heads[:-1]}
    lines = ["  ".join([*(h.upper().ljust(widths[h]) for h in heads[:-1]), heads[-1].upper()])]
    for r in rows:
        cells = [r[h].rjust(widths[h]) if h in ("rounds", "line") else r[h].ljust(widths[h]) for h in heads[:-1]]
        lines.append("  ".join([*cells, r["first words"]]))
    lines += ["", ", ".join(f"{k}: {v}" for k, v in totals(found).items())]
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
    lines = [f"BLIND SPOTS ({len(spots)} of {len(paragraphs(found))} paragraphs no review round has touched)"]
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
        f'<td class="num">{r["rounds"]}</td><td>{html.escape(r["reviewers"])}</td>'
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
        '<div class="table-wrap"><table>\n<thead><tr><th>ID</th><th>Rounds</th><th>Reviewers</th>'
        f"<th>Line</th><th>Reviewed</th><th>First words</th></tr></thead>\n<tbody>\n{rows}\n</tbody>\n</table></div>\n"
        '<h2>Blind spots</h2>\n<p class="meta">Paragraphs no review round has touched; unshaded below.</p>\n'
        '<div class="table-wrap"><table class="blind">\n<thead><tr><th>Line</th><th>First words</th></tr></thead>\n'
        f"<tbody>\n{blind}\n</tbody>\n</table></div>\n"
        f'</header>\n<main>\n<div class="doc">{"".join(body)}</div>\n</main>\n</body>\n</html>\n')


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
    args = ap.parse_args(argv)
    for path in getattr(args, "files", None) or [args.file]:
        if not path.is_file():
            print(f"rev_marks.py: cannot read {path}", file=sys.stderr)
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
    sys.exit(main(sys.argv[1:]))
